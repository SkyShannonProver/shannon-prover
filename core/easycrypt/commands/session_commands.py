"""CLI handlers for session-lifecycle commands: -start, -status,
-checkpoint, -replay.

These manage the session directory's metadata (history.ec,
session_meta.json, checkpoint_*.json) and provide the entry point
into a fresh proof attempt.

Phase 4: extracted from session_cli.main() to keep main() as pure
dispatch.
"""
from __future__ import annotations

import json
import json as _json
import os
import re
import sys
from datetime import datetime
from datetime import datetime as _dt
from pathlib import Path
from typing import Any


# ─── -start ──────────────────────────────────────────────────────────────

def handle_start(session, args) -> int:
    """Initialize / restart a session. Pre-checks for stale-meta
    conflicts (warns when -lemma was previously set but is now
    omitted), records restart count + saves a recoverable checkpoint
    of the prior tactics if any were committed, then either extracts
    a section-local lemma (`-lemma`) or loads the whole file.
    """
    from core.easycrypt.session_common import trim_after_last_prompt  # type: ignore

    meta_path = session.dir / "session_meta.json"
    prev_restart_count = 0
    if meta_path.exists():
        try:
            prev = json.loads(meta_path.read_text())
            prev_restart_count = prev.get("restart_count", 0)
            if args.file:
                prev_file = prev.get("file", "")
                prev_lemma = prev.get("lemma")
                curr_file = str(Path(args.file).resolve())
                if prev_file == curr_file and prev_lemma and not args.lemma:
                    sys.stderr.write(
                        f"[session_cli] WARNING: This session directory "
                        f"was previously initialized with -lemma "
                        f"'{prev_lemma}' for {Path(args.file).name}.\n"
                        f"  You are now starting WITHOUT -lemma, which "
                        f"will load the entire file.\n"
                        f"  Loading the full file may place EasyCrypt "
                        f"in the middle of an existing proof (e.g. "
                        f"smt/why3 obligations), not at the target "
                        f"lemma.\n"
                        f"  If you want the same lemma context, use: "
                        f"-lemma '{prev_lemma}'\n"
                        f"  To suppress this warning, use a different "
                        f"-d session directory.\n",
                    )
        except Exception:
            pass

    # Proof-progress restart warning
    hist_path = session.dir / "history.ec"
    if hist_path.exists() and hist_path.stat().st_size > 0:
        hist_lines = [
            l for l in hist_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        if hist_lines:
            has_qed = any(
                l.strip().lower().rstrip(".").strip() == "qed"
                for l in hist_lines
            )
            pinned_session = bool(os.environ.get("EC_SESSION_DIR", "").strip())
            if pinned_session and not getattr(args, "force_restart", False):
                sys.stderr.write(
                    f"[session_cli] Refusing mid-proof -start in pinned "
                    f"prover session `{os.environ.get('EC_SESSION_DIR')}`.\n"
                    f"  This session already has {len(hist_lines)} committed "
                    f"tactic(s){' and includes qed' if has_qed else ''}.\n"
                    f"  Restarting here would discard the current proof "
                    f"frontier and can make the tree/session state drift.\n"
                    f"  Use -agent-view / -status to inspect, -prev to undo "
                    f"specific tactics, -checkpoint/-replay for controlled "
                    f"branching, or ask the human to rerun with "
                    f"`--force-restart` if wiping this session is intended.\n"
                )
                return 2
            sys.stderr.write(
                f"[session_cli] Restart #{prev_restart_count + 1}: "
                f"discarding {len(hist_lines)} committed tactic(s)"
                f"{' (proof was COMPLETE — qed present)' if has_qed else ''}.\n"
                f"  The {len(hist_lines)} prior tactics are saved to "
                f"a checkpoint file (see RESTART-NOTICE below) in "
                f"case you decide to replay. Proceeding with fresh "
                f"session.\n",
            )

    briefing = session.start()
    session.emit_event("session.started", {
        "file": str(Path(args.file).resolve()) if args.file else None,
        "lemma": args.lemma,
        "include_dirs": list(args.include_dirs or []),
        "discarded_tactic_count": briefing.get(
            "discarded_tactic_count", 0,
        ),
        "pre_restart_checkpoint_path": briefing.get(
            "pre_restart_checkpoint_path",
        ),
        "restart_count": prev_restart_count + 1,
    })
    if briefing.get("discarded_tactic_count", 0) > 0:
        _write_legacy_output(_format_restart_notice(session, briefing))

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"File not found: {args.file}\n")
            return 1
        if args.lemma:
            from core.easycrypt.lemma_extract import extract_lemma  # type: ignore
            try:
                extracted = extract_lemma(
                    file_path, args.lemma, open_proof=True,
                )
            except ValueError as e:
                _print_extract_error(file_path, args.lemma, e)
                return 1
            safe_lemma_fname = re.sub(
                r"[^a-zA-Z0-9_-]", "_", args.lemma,
            )
            extracted_path = (
                session.dir / f"extracted_{safe_lemma_fname}.ec"
            )
            extracted_path.write_text(extracted, encoding="utf-8")
            session.load_context(extracted_path)
            _write_legacy_output(
                f"[start] extracted lemma '{args.lemma}' from "
                f"{file_path.name}\n",
            )
        else:
            session.load_context(file_path)

        # Run EC on the context to show initial state, then strip
        # context-processing transcript (extracted lemmas may include
        # downstream lemmas with not-yet-cloned types — benign errors
        # we want to compress out of the visible state).
        session._run_ec(session.history, session.curr)
        session._compress_curr_inplace()
        state = session.read_state()
        snippet = state.raw_for_goal_tools or state.active_output
        if not snippet:
            snippet = "\n".join(state.raw_current.splitlines()[-20:])
        if snippet and not snippet.endswith("\n"):
            snippet += "\n"
        snippet = trim_after_last_prompt(snippet)
        if not args.lemma:
            n_lines = sum(1 for _ in file_path.read_text().splitlines())
            _write_legacy_output(
                f"[start] session initialized, loaded "
                f"{file_path.name} ({n_lines} lines)\n",
            )
        _write_legacy_output(snippet)
    else:
        _write_legacy_output("[start] session initialized\n")

    # Save metadata for stale-session detection on future starts
    meta = {
        "file": str(Path(args.file).resolve()) if args.file else None,
        "lemma": args.lemma,
        "timestamp": datetime.now().isoformat(),
        "restart_count": prev_restart_count + 1,
    }
    (session.dir / "session_meta.json").write_text(
        json.dumps(meta, indent=2),
    )
    if _structured_only_output():
        view = _build_start_agent_view(session, args, briefing)
        sys.stdout.write(
            _json.dumps(_stdout_structured_view(view), indent=2, sort_keys=True)
            + "\n"
        )
    return 0


def _write_legacy_output(text: str) -> None:
    if not text or _structured_only_output():
        return
    sys.stdout.write(text)


def _structured_only_output() -> bool:
    return _legacy_display_mode() in {"off", "hide", "hidden", "none"}


def _legacy_display_mode() -> str:
    from core.easycrypt.session_tool_view import legacy_display_mode
    return legacy_display_mode(default="full")


def _stdout_structured_view(
    view: dict,
    *,
    proof_context_payload: dict[str, Any] | None = None,
    agent_view_payload: dict[str, Any] | None = None,
) -> dict:
    if view.get("kind") in {"proof_context_view", "agent_proof_view"}:
        from core.easycrypt.session_prover_workspace_view import (  # type: ignore
            build_prover_workspace_view_from_context,
        )
        return build_prover_workspace_view_from_context(
            view,
            proof_context_payload=proof_context_payload or agent_view_payload,
        )

    data = _json.loads(_json.dumps(view))
    evidence = data.get("evidence")
    raw_items = evidence.get("raw") if isinstance(evidence, dict) else None
    if isinstance(raw_items, list):
        slim = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            kept = {
                key: item[key]
                for key in ("id", "format", "source_name", "source_event_id")
                if key in item
            }
            kept["preview_omitted"] = True
            slim.append(kept)
        evidence["raw"] = slim
    return data


def _build_start_agent_view(session, args, briefing: dict) -> dict:
    from core.easycrypt.session_agent_view import (  # type: ignore
        build_proof_context_view,
        record_proof_context_view,
    )

    view = build_proof_context_view(
        session.dir,
        live_tool_name="start",
        include_goal_text=True,
    )
    start_payload = {
        "file": str(Path(args.file).resolve()) if getattr(args, "file", None) else None,
        "lemma": getattr(args, "lemma", None),
        "include_dirs": list(getattr(args, "include_dirs", []) or []),
        "discarded_tactic_count": int(
            briefing.get("discarded_tactic_count", 0) or 0,
        ),
        "pre_restart_checkpoint_path": (
            briefing.get("pre_restart_checkpoint_path")
        ),
        "restart_count": int(briefing.get("restart_count", 0) or 0),
    }
    if not start_payload["restart_count"]:
        try:
            meta = json.loads((session.dir / "session_meta.json").read_text())
            start_payload["restart_count"] = int(meta.get("restart_count", 0) or 0)
        except Exception:
            pass
    view["start"] = start_payload
    notes = list(view.get("notes") or [])
    if start_payload["discarded_tactic_count"]:
        notes.append({
            "code": "start.discarded_prior_tactics",
            "message": (
                "Session restart discarded committed tactics; see "
                "start.pre_restart_checkpoint_path."
            ),
        })
    else:
        notes.append({
            "code": "start.initialized",
            "message": "Session initialized; inspect actions for the next step.",
        })
    view["notes"] = notes
    try:
        record_proof_context_view(session, view)
    except Exception:
        pass
    return view


def _format_restart_notice(session, briefing) -> str:
    """Build the [RESTART-NOTICE] block emitted when -start discards
    committed tactics. Includes the saved-prefix path and a replay
    command so the agent can recover if the restart was premature."""
    cnt = briefing["discarded_tactic_count"]
    cp = briefing.get("pre_restart_checkpoint_path") or "(save failed)"
    replay = briefing.get("replay_chain", "")
    return (
        f"[RESTART-NOTICE] {cnt} committed tactic(s) discarded by "
        f"this -start.\n"
        f"\n"
        f"Mid-proof restart is a destructive recovery action. It is "
        f"appropriate only when you intentionally want to discard the "
        f"current frontier and replay from a saved prefix; ordinary "
        f"backtracking should use -prev, -checkpoint, or -replay.\n"
        f"\n"
        f"When restart may be the right move:\n"
        f"  - Your thinking identifies a specifically different plan "
        f"    (e.g. 'route through pr_CCP_OCCP as an intermediate')\n"
        f"  - Your direct byequiv is leaving 4+ residual subgoals\n"
        f"    that need hand-crafted invariants\n"
        f"  - You're about to drop to procedure-level while-loop\n"
        f"    invariants that no narrative pivot is targeting\n"
        f"  - You've recognized the bridge you chose is too big\n"
        f"    (manager validation of the full plan fails sim-family closers)\n"
        f"\n"
        f"When a cheaper move suffices:\n"
        f"  - `-prev` N times rewinds N specific tactics while\n"
        f"    keeping the prefix committed\n"
        f"  - `-show-proof` prints the accepted tactic list\n"
        f"  - `-status` / `-goal-info` re-read the current state\n"
        f"\n"
        f"Saved prefix to:\n  {cp}\n"
        f"To replay the prefix on this fresh session (if you decide "
        f"the restart was premature):\n"
        f"  python3 core/easycrypt/session_cli.py -d "
        f"{session.dir.name} -chain --keep-on-fail -c "
        f"'{replay[:300]}{'...' if len(replay) > 300 else ''}'\n"
    )


def _print_extract_error(file_path, lemma_name, exc) -> None:
    """Surface a richer diagnostic when -lemma extraction fails: lists
    sibling lemmas, flags name-in-section vs name-in-text-only, etc.
    Avoids the bare "not found" + agent guessing."""
    from core.easycrypt.session_common import list_lemmas_in_file  # type: ignore
    sys.stderr.write(f"Error: {exc}\n")
    info = list_lemmas_in_file(file_path)
    top = info.get("top_level", [])
    sec = info.get("in_sections", [])
    try:
        raw_text = file_path.read_text(encoding="utf-8")
        in_raw = lemma_name in raw_text
    except Exception:
        in_raw = False
    if lemma_name in sec:
        sys.stderr.write(
            f"  Note: '{lemma_name}' is present in the file inside "
            f"a section but was not matched by the extraction "
            f"regex. Check for unusual spacing or declaration "
            f"keywords.\n",
        )
    elif in_raw:
        sys.stderr.write(
            f"  Note: '{lemma_name}' appears in the file text but "
            f"was not matched as a lemma/equiv/hoare/phoare declaration. "
            f"Check for typos or unusual formatting.\n",
        )
    if sec:
        sys.stderr.write(
            f"  Lemmas found inside sections ({len(sec)} total):\n",
        )
        for n in sec[:20]:
            sys.stderr.write(f"    {n}\n")
        if len(sec) > 20:
            sys.stderr.write(f"    ... and {len(sec) - 20} more\n")
    if top:
        sys.stderr.write(f"  Top-level lemmas ({len(top)} total):\n")
        for n in top[:20]:
            sys.stderr.write(f"    {n}\n")
        if len(top) > 20:
            sys.stderr.write(f"    ... and {len(top) - 20} more\n")


# ─── -status ─────────────────────────────────────────────────────────────

def handle_status(session, args) -> int:
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import (  # type: ignore
        record_tool_view,
        tool_view_from_projection,
    )

    projection = read_proof_state_projection(
        session.dir,
        live_tool_name="status",
    )
    proof_state = projection_to_goal_info(projection)
    notes = [
        {
            "code": "status.summary",
            "message": "Status is a compact projection summary.",
        }
    ]
    if projection.consistency.notes:
        notes.extend({
            "code": "projection.consistency.note",
            "message": note,
        } for note in projection.consistency.notes[:5])
    errors = []
    if not projection.events.ok:
        errors.append({
            "code": "status.event_contract",
            "message": "event contract is not valid",
        })
    if not projection.consistency.ok:
        errors.append({
            "code": "status.consistency",
            "message": "proof-state projection is inconsistent",
        })
    status_view = tool_view_from_projection(
        tool="status",
        proof_state=proof_state,
        guidance={"recommendations": []},
        evidence={
            "event": [{
                "id": "event.proof_state_projection",
                "producer": "session_projection",
                "status": proof_state.get("status"),
                "event_contract": proof_state.get("event_contract"),
                "latest_transition": proof_state.get("latest_transition"),
            }],
        },
        notes=notes,
        errors=errors,
    )
    try:
        record_tool_view(session, status_view)
    except Exception:
        pass

    tactic_count = projection.history.tactic_count
    has_qed = projection.history.has_qed
    complete = projection.status in ("candidate_closed", "verified")
    goal_type = "complete" if complete else (projection.goal.goal_type or "unknown")
    sys.stdout.write(f"[status] {tactic_count} tactics accepted\n")
    sys.stdout.write(f"[status] Goal type: {goal_type}\n")
    sys.stdout.write(
        f"[status] Proof "
        f"{'COMPLETE' if complete or has_qed else 'incomplete'}\n",
    )
    ckpts = list(session.dir.glob("checkpoint_*.json"))
    if ckpts:
        sys.stdout.write(
            f"[status] Checkpoints: "
            f"{', '.join(c.stem.replace('checkpoint_', '') for c in ckpts)}\n",
        )
    return 0


# ─── -agent-view ────────────────────────────────────────────────────────

def handle_agent_view(session, args) -> int:
    from core.easycrypt.session_agent_view import (  # type: ignore
        build_proof_context_view,
        record_proof_context_view,
    )

    view = build_proof_context_view(
        session.dir,
        live_tool_name="agent-view",
        include_goal_text=True,
    )
    proof_context_payload = {}
    try:
        proof_context_payload = record_proof_context_view(session, view)
    except Exception:
        pass
    workspace_view = _stdout_structured_view(
        view,
        proof_context_payload=proof_context_payload,
    )
    from core.easycrypt.session_prover_workspace_view import (  # type: ignore
        record_prover_workspace_view,
    )
    try:
        record_prover_workspace_view(session, workspace_view)
    except Exception:
        pass
    sys.stdout.write(
        _json.dumps(
            workspace_view,
            indent=2,
        )
        + "\n"
    )
    return 0


# ─── -episode-view ──────────────────────────────────────────────────────

def handle_episode_view(session, args) -> int:
    from core.easycrypt.session_episode_timeline import (  # type: ignore
        build_session_episode_timeline,
        record_session_episode_timeline,
    )

    timeline = build_session_episode_timeline(session.dir)
    try:
        record_session_episode_timeline(session, timeline)
    except Exception:
        pass
    sys.stdout.write(_json.dumps(timeline, indent=2, sort_keys=True) + "\n")
    return 0


# ─── -checkpoint ─────────────────────────────────────────────────────────

def handle_checkpoint(session, args) -> int:
    if not session.history.exists() or session.history.stat().st_size == 0:
        sys.stderr.write("No proof in progress. Nothing to checkpoint.\n")
        return 1
    tactics = [
        l for l in session.history.read_text(
            encoding="utf-8",
        ).splitlines() if l.strip()
    ]
    goal_summary = ""
    if session.curr.exists():
        state = session.read_state()
        raw = state.raw_for_goal_tools
        if state.proof_candidate_closed:
            goal_summary = "complete"
        else:
            try:
                from core.easycrypt.analysis.ec_goal_parser import parse_goal  # type: ignore
                info = parse_goal(raw)
                goal_summary = (
                    "complete"
                    if info.num_remaining == 0
                    else (info.goal_type or "unknown")
                )
            except Exception:
                goal_summary = "unknown"
    ckpt = {
        "name": args.checkpoint_name,
        "timestamp": _dt.now().isoformat(),
        "tactics": tactics,
        "goal_summary": goal_summary,
    }
    ckpt_path = session.dir / f"checkpoint_{args.checkpoint_name}.json"
    ckpt_path.write_text(_json.dumps(ckpt, indent=2), encoding="utf-8")
    sys.stdout.write(
        f"[checkpoint] Saved '{args.checkpoint_name}' "
        f"({len(tactics)} tactics, {goal_summary})\n",
    )
    return 0


# ─── -replay ─────────────────────────────────────────────────────────────

def handle_replay(session, args) -> int:
    """Restore a checkpoint by clearing history and re-applying tactics
    one at a time. Stops at the first error."""
    from core.easycrypt.session_common import trim_after_last_prompt  # type: ignore

    ckpt_path = session.dir / f"checkpoint_{args.replay_name}.json"
    if not ckpt_path.exists():
        sys.stderr.write(f"Checkpoint '{args.replay_name}' not found.\n")
        return 1
    ckpt = _json.loads(ckpt_path.read_text(encoding="utf-8"))
    tactics = ckpt.get("tactics", [])
    if not tactics:
        sys.stderr.write("Checkpoint has no tactics.\n")
        return 1
    # Clear history + steps + commit_meta.log to keep them aligned
    session.history.write_text("")
    session.steps.write_text("")
    meta_path = session.dir / "commit_meta.log"
    if meta_path.exists():
        meta_path.write_text("")
    sys.stdout.write(
        f"[replay] Replaying {len(tactics)} tactics from "
        f"'{args.replay_name}'...\n",
    )
    for i, tac in enumerate(tactics):
        prev_error_lines = set()
        if session.curr.exists():
            prev_state = session.read_state()
            prev_error_lines = {
                ln for ln in prev_state.raw_current.splitlines()
                if re.match(r"^\s*\[(error|critical|fatal)", ln)
            }
        session.append_block(tac, deltas_only=False)
        state = session.read_state()
        curr_error_lines = {
            ln for ln in state.raw_current.splitlines()
            if re.match(r"^\s*\[(error|critical|fatal)", ln)
        }
        if curr_error_lines - prev_error_lines:
            sys.stdout.write(
                f"[replay] ERROR at tactic {i + 1}/{len(tactics)}: "
                f"{tac}\n",
            )
            return 1
    sys.stdout.write(
        f"[replay] Restored {len(tactics)} tactics from "
        f"'{args.replay_name}'.\n",
    )
    state = session.read_state()
    snippet = state.raw_for_goal_tools or state.active_output
    if not snippet:
        snippet = "\n".join(state.raw_current.splitlines()[-15:])
    snippet = trim_after_last_prompt(snippet)
    sys.stdout.write(snippet + "\n")
    return 0
