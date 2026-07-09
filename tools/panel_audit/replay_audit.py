#!/usr/bin/env python3
"""Panel-audit deterministic replay harness.

Takes a recorded ``agent_view_runs/`` bundle, extracts the EXACT agent action
script (the ``handled_intent`` stream: probe / commit / inspect / lookup / undo /
...) from ``views/<tree>/manager_results/turn_*.json``, and replays it
deterministically through a fresh ``ProofNodeManager`` built from the CURRENT
checkout.  No live LLM is in the loop -- the moves are fixed, from the bundle.

For every turn we capture, side by side:

  * ``raw_ec.txt`` / ``raw_ec_actions.json`` -- the GENUINE raw EasyCrypt backend
    stdout/stderr for the backend calls this turn made.  This is the ground
    truth.  ``command_summary`` normally discards the full stdout (keeps only
    char counts + a parsed observation), so we surgically patch it for the
    duration of the run to retain the raw text.
  * ``current_view.json`` -- the CURRENT-code agent-facing ProverWorkspaceView
    (all panels: current_goal, candidate_moves, program_frontier / Call
    Frontier, call_site_surface, facts_and_diagnostics, goal class, ...).
  * ``current_panel.md`` -- the CURRENT-code "inline read" the prover would see
    this turn (rendered by the SAME ``_render_manager_followup`` the live loop
    uses), at L4 and (re-rendered) L1.
  * ``recorded_view.json`` / ``recorded_panel.md`` -- what the bundle captured at
    run time, for cross-reference (what the agent saw THEN vs NOW).

Auditors then compare the current panel against the raw EC ground truth to find
loss / divergence / hallucination -- WITHOUT re-running EC.

Usage:
  python3 tools/panel_audit/replay_audit.py \
    --bundle agent_view_runs/mee_decrypt_correct/2026-06-06_0152__e4a69e8-dirty \
    --tree Tree_0_0 \
    --file eval/examples/MEE-CBC/FunctionalSpec.ec \
    --lemma mee_decrypt_correct \
    --include-dir easycrypt-src/theories \
    --surface-profile l4_checked_action_surface \
    --out-dir artifacts/panel_audit/mee_decrypt_correct/Tree_0_0
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _jsonable(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        if isinstance(obj, dict):
            return {k: _jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_jsonable(v) for v in obj]
        if hasattr(obj, "to_dict"):
            try:
                return _jsonable(obj.to_dict())
            except Exception:
                return str(obj)
        return str(obj)


def _extract_steps(bundle: Path, tree: str) -> list[dict[str, Any]]:
    """Ordered handled_intent stream from the bundle's manager_results."""
    mr_dir = bundle / "views" / tree / "manager_results"
    steps: list[tuple[int, dict[str, Any]]] = []
    for f in sorted(mr_dir.glob("turn_*.json")):
        data = _read_json(f)
        turn = data.get("turn")
        if not isinstance(turn, int):
            try:
                turn = int(f.stem.split("_")[-1])
            except Exception:
                continue
        if turn <= 0:
            continue  # turn_000 is the bootstrap handoff, not an agent move
        intent = data.get("handled_intent")
        if not isinstance(intent, dict) or not intent.get("intent"):
            continue
        steps.append((turn, {"intent": str(intent["intent"]),
                             "payload": dict(intent.get("payload") or {})}))
    steps.sort(key=lambda t: t[0])
    return [s for _, s in steps]


# --------------------------------------------------------------------------
# Ground-truth raw-EC capture: patch command_summary to retain full stdout.
# --------------------------------------------------------------------------
_RAW_BACKEND_CALLS: list[dict[str, Any]] = []


def _install_raw_capture() -> None:
    import workflow.proof_management.repl_session as repl_mod
    original = repl_mod.command_summary

    def _patched(label, cmd, result, duration_ms, *a, **k):
        action = original(label, cmd, result, duration_ms, *a, **k)
        raw = {
            "label": label,
            "args": [str(c) for c in cmd],
            "returncode": getattr(result, "returncode", None),
            "raw_stdout": getattr(result, "stdout", "") or "",
            "raw_stderr": getattr(result, "stderr", "") or "",
        }
        # Stash on the action (so it rides through manager_actions) AND in a
        # global side-channel keyed by call order (robust to any manager-side
        # action re-summarisation).
        try:
            action["_raw_stdout"] = raw["raw_stdout"]
            action["_raw_stderr"] = raw["raw_stderr"]
        except Exception:
            pass
        _RAW_BACKEND_CALLS.append(raw)
        return action

    repl_mod.command_summary = _patched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--tree", default="Tree_0_0")
    ap.add_argument("--file", required=True)
    ap.add_argument("--lemma", required=True)
    ap.add_argument("--include-dir", default="")
    ap.add_argument("--surface-profile", default="l4_checked_action_surface")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-steps", type=int, default=0)
    args = ap.parse_args()

    bundle = Path(args.bundle).resolve()
    tree = args.tree
    out_dir = Path(args.out_dir).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = _extract_steps(bundle, tree)
    if args.max_steps:
        steps = steps[: args.max_steps]
    if not steps:
        raise SystemExit(f"no steps extracted from {bundle}/views/{tree}/manager_results")

    _install_raw_capture()

    from workflow.proof_node_manager import ProofNodeManager
    from workflow.proof_node_runtime import NodeMemory, _render_manager_followup
    from core.easycrypt.session_workspace_view_manager import WorkspaceViewManager

    wvm = WorkspaceViewManager()

    def agent_surface(view: dict[str, Any]) -> dict[str, Any]:
        try:
            return wvm.agent_display_view(view)
        except Exception:
            return dict(view or {})

    session_tag = f"panel_audit_{args.lemma}_{int(time.time())}"
    manager = ProofNodeManager(
        file_path=args.file,
        lemma_name=args.lemma,
        include_dir=args.include_dir,
        session_tag=session_tag,
        node_id="panel-audit",
        run_dir=out_dir / "_run",
        project_root=PROJECT_ROOT,
        surface_profile=args.surface_profile or None,
    )
    manager.repl.session_dir = str(out_dir / "_run" / ".ec_session")
    memory = NodeMemory(out_dir / "_run", "panel-audit",
                        surface_profile=args.surface_profile or None)

    bootstrap = manager.bootstrap()
    boot_raw = dict(bootstrap.get("workspace_view") or manager.latest_view)
    _write_json(out_dir / "bootstrap_current_view.json", agent_surface(boot_raw))
    memory.record_bootstrap(bootstrap)

    index: list[dict[str, Any]] = []
    for i, step in enumerate(steps, start=1):
        turn_dir = out_dir / "steps" / f"turn_{i:03d}"
        turn_dir.mkdir(parents=True, exist_ok=True)
        _RAW_BACKEND_CALLS.clear()

        intent_json = json.dumps(step, separators=(",", ":"))
        t0 = time.perf_counter()
        try:
            turn = manager.handle_agent_message(intent_json)
            err = None
        except Exception as exc:  # capture, keep going
            turn = None
            err = f"{type(exc).__name__}: {exc}"
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Genuine raw EC ground truth for this turn.
        raw_calls = [dict(c) for c in _RAW_BACKEND_CALLS]
        raw_txt_parts = []
        for c in raw_calls:
            raw_txt_parts.append(f"$ {' '.join(c['args'])}  (rc={c['returncode']})")
            if c["raw_stdout"].strip():
                raw_txt_parts.append("--- STDOUT ---\n" + c["raw_stdout"].rstrip())
            if c["raw_stderr"].strip():
                raw_txt_parts.append("--- STDERR ---\n" + c["raw_stderr"].rstrip())
            raw_txt_parts.append("")
        (turn_dir / "raw_ec.txt").write_text("\n".join(raw_txt_parts), encoding="utf-8")
        _write_json(turn_dir / "raw_ec_actions.json", raw_calls)
        _write_json(turn_dir / "intent.json", step)

        current_view: dict[str, Any] = {}
        current_panel = ""
        snap: dict[str, Any] = {}
        if turn is not None:
            current_view = agent_surface(dict(turn.workspace_view or {}))
            # Match the live bridge: record the turn into node-memory BEFORE
            # rendering, so the "Already tried at this exact state" block
            # accumulates real history (it reads timeline.jsonl/attempts.jsonl).
            try:
                memory.record_turn(
                    turn_index=i, raw_text=intent_json, handled_intent=step, turn=turn,
                )
            except Exception:
                pass
            # The live bridge renders with the manager's latest FULL view, not
            # the turn's lean workspace_view.
            full_view = getattr(manager, "latest_full_view", None)
            if not isinstance(full_view, dict):
                full_view = dict(turn.workspace_view or {})
            try:
                current_panel = _render_manager_followup(
                    turn, i,
                    handled_intent=step,
                    memory=memory,
                    full_view=full_view,
                    surface_profile=args.surface_profile or None,
                )
            except Exception as exc:
                current_panel = f"<<render error: {type(exc).__name__}: {exc}>>"
            # Same EC state, rendered at the L1 goal-only baseline -- for the
            # L4-vs-L1 noise auditor (apples-to-apples, no extra EC run).
            try:
                current_panel_l1 = _render_manager_followup(
                    turn, i,
                    handled_intent=step,
                    memory=memory,
                    full_view=full_view,
                    surface_profile="l1_goal_projection",
                )
            except Exception as exc:
                current_panel_l1 = f"<<render error: {type(exc).__name__}: {exc}>>"
            (turn_dir / "current_panel_l1.md").write_text(current_panel_l1, encoding="utf-8")
            if getattr(turn, "snapshot", None) is not None:
                snap = _jsonable(turn.snapshot.to_dict())
                snap["goal_lines"] = (current_view.get("current_goal") or {}).get("lines")

        (turn_dir / "current_panel.md").write_text(current_panel, encoding="utf-8")
        _write_json(turn_dir / "current_view.json", current_view)
        _write_json(turn_dir / "snapshot.json", snap)
        _write_json(turn_dir / "manager_actions.json",
                    _jsonable(getattr(turn, "manager_actions", []) if turn else []))

        # Recorded bundle references for the same turn.
        rec_view = bundle / "views" / tree / f"turn_{i:03d}.json"
        rec_panel = bundle / "views" / tree / "followups" / f"turn_{i:03d}.md"
        if rec_view.exists():
            _write_json(turn_dir / "recorded_view.json", _read_json(rec_view))
        if rec_panel.exists():
            (turn_dir / "recorded_panel.md").write_text(
                rec_panel.read_text(encoding="utf-8"), encoding="utf-8")

        row = {
            "turn": i,
            "intent": step["intent"],
            "payload": step["payload"],
            "ok": bool(getattr(turn, "ok", False)) if turn else False,
            "error": err,
            "elapsed_ms": elapsed_ms,
            "goal_hash": snap.get("goal_hash"),
            "n_backend_calls": len(raw_calls),
            "raw_rc": [c["returncode"] for c in raw_calls],
        }
        index.append(row)
        print(f"{i:03d} {step['intent']:<15} ok={row['ok']} "
              f"{elapsed_ms:>6}ms calls={len(raw_calls)} rc={row['raw_rc']}"
              + (f" ERR={err}" if err else ""), flush=True)

    _write_json(out_dir / "audit_index.json", {
        "bundle": str(bundle),
        "tree": tree,
        "file": args.file,
        "lemma": args.lemma,
        "include_dir": args.include_dir,
        "surface_profile": args.surface_profile,
        "n_steps": len(steps),
        "steps": index,
    })
    print(f"\nwrote audit to {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
