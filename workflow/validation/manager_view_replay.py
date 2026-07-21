"""Replay proof intents through ProofNodeManager and save each workspace view.

This is the manager-boundary calibration tool for agent-view regressions.  It
does not launch a live prover agent.  It starts one managed proof node, submits
one proof intent at a time, and records the refreshed ProverWorkspaceView after
each turn.

Examples:

  python3 -m workflow.validation.manager_view_replay replay \
    --proof-bank-lemma schnorr_proof_of_knowledge_completeness --max-steps 10

  python3 -m workflow.validation.manager_view_replay replay \
    --file eval/examples/SchnorrPK.ec --lemma schnorr_proof_of_knowledge_completeness \
    --tactic 'move=> Rhw.' --tactic 'byphoare (_: arg = (h, w'\\'' ) ==> _) => //.'

To replay against a DIFFERENT checkout/worktree's manager+view code, run this
script BY FILE PATH (so ``--project-root`` can be placed first on ``sys.path``).
Do NOT use ``python3 -m`` from another checkout: that imports the ``workflow``
package from the current working directory and ``--project-root`` is then
silently ignored.

  python3 /path/to/other/checkout/workflow/validation/manager_view_replay.py replay \
    --project-root /path/to/other/checkout \
    --proof-bank-lemma schnorr_proof_of_knowledge_completeness --max-steps 10

  python3 /path/to/other/checkout/workflow/validation/manager_view_replay.py compare \
    --left artifacts/manager_view_replay_old \
    --right artifacts/manager_view_replay_current

Replaying a REAL agent run's recorded behavior (so inspect / lookup /
undo intents are replayed too, not just committed tactics) and validating that
the replay reproduces what the agent actually saw:

  # Reconstruct + validate on the SAME commit the run executed on:
  python3 workflow/validation/manager_view_replay.py replay \
    --from-run workflow/runs/2026-05-29_1035_step1/iteration_1 \
    --reconcile --out-dir artifacts/mvr_from_run_same_commit
  # reconcile: N/N turns identical  => reconstruction is faithful.

  # Then re-run --from-run on another checkout (by file path + --project-root)
  # and `compare` the two output dirs: remaining diffs are code, not behavior.
"""
from __future__ import annotations

import argparse
import atexit
import difflib
import hashlib
import inspect
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PROJECT_ROOT))

from workflow.validation.replay_artifacts import dig as _dig
from workflow.context_intents import is_context_topic_intent, normalize_context_topic


@dataclass(frozen=True)
class StepSpec:
    intent: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "payload": dict(self.payload)}

    @property
    def label(self) -> str:
        if self.intent == "commit_tactic":
            return _compact(str(self.payload.get("tactic") or ""), 100)
        if self.intent == "inspect_context":
            return f"inspect:{self.payload.get('topic') or 'goal_info'}"
        if is_context_topic_intent(self.intent):
            return f"context:{self.intent}"
        if self.intent == "lookup_symbol":
            return f"lookup:{self.payload.get('symbol') or ''}"
        return self.intent


def replay(args: argparse.Namespace) -> int:
    project_root = _project_root(args)
    _prefer_project_root_for_imports(project_root)
    from workflow.proof_node_manager import ProofNodeManager

    # Import the view manager from the code-under-test (after the sys.path
    # preference above) so the saved agent surface reflects THIS checkout's
    # projection/ordering, not the script's own copy.
    try:  # Package import path.
        from core.easycrypt.session_workspace_view_manager import (  # type: ignore
            WorkspaceViewManager,
        )
    except Exception:  # Script/session_cli import path.
        sys.path.insert(0, str(project_root / "core" / "easycrypt"))
        from session_workspace_view_manager import WorkspaceViewManager  # type: ignore

    workspace_view_manager = WorkspaceViewManager()

    # Optional: render the EXACT agent-facing inline-read (the followup markdown the
    # prover actually reads) per turn, using the code-under-test renderer + a real
    # NodeMemory. This is the "simulate the CURRENT inline read" path for panel audits.
    render_followup = None
    NodeMemoryCls = None
    if getattr(args, "write_followups", False):
        from workflow.proof_node_runtime import (  # type: ignore
            _render_manager_followup as render_followup,
            NodeMemory as NodeMemoryCls,
        )

    def agent_surface(view: dict[str, Any]) -> dict[str, Any]:
        """Project a raw workspace view into the real agent-facing surface.

        ``agent_display_view`` strips ``AGENT_HIDDEN_METADATA_FIELDS`` and
        applies ``order_agent_view`` -- i.e. exactly what the prover agent
        sees -- so the saved artifact is what we actually want to diff.
        """
        return workspace_view_manager.agent_display_view(view)

    # ``--from-run`` reconstructs the agent's actual recorded intent stream and
    # auto-derives the target.  It is its own step source; explicit
    # --tactic/--step/--proof-bank are ignored when it is set.
    run_meta: dict[str, Any] = {}
    run_steps: list[StepSpec] | None = None
    if args.from_run:
        run_steps, run_meta = _steps_from_run(
            args.from_run, args.from_run_node, project_root=project_root
        )
        if not args.file and run_meta.get("file"):
            args.file = run_meta["file"]
        if not args.lemma and run_meta.get("lemma"):
            args.lemma = run_meta["lemma"]
        if not args.include_dir and run_meta.get("include_dir"):
            args.include_dir = run_meta["include_dir"]
        if not args.surface_profile and run_meta.get("surface_profile"):
            args.surface_profile = run_meta["surface_profile"]
        if len(run_meta.get("include_dirs") or []) > 1:
            print(
                f"--from-run: the run used {len(run_meta['include_dirs'])} include "
                f"dirs but the manager takes one; using {args.include_dir!r}. Pass "
                "--include-dir if the session fails to open.",
                flush=True,
            )
        print(
            f"--from-run: replaying {run_meta.get('intent_count', len(run_steps))} "
            f"intents from node {run_meta.get('node', '?')}",
            flush=True,
        )

    target = _resolve_target(args, project_root=project_root)
    steps = run_steps if run_steps is not None else _resolve_steps(
        args, target, project_root=project_root
    )
    if args.max_steps:
        steps = steps[: args.max_steps]
    if not steps:
        raise SystemExit("no proof steps supplied or found")

    out_dir = Path(args.out_dir).resolve()
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "workspace_views").mkdir(parents=True, exist_ok=True)
    (out_dir / "raw_views").mkdir(exist_ok=True)
    (out_dir / "manager_results").mkdir(exist_ok=True)
    (out_dir / "diffs").mkdir(exist_ok=True)

    session_tag = args.session_tag or _safe_slug(
        f"manager_view_replay_{target['lemma']}_{int(time.time())}"
    )
    manager = _make_manager(
        ProofNodeManager,
        file_path=str(target["file"]),
        lemma_name=str(target["lemma"]),
        include_dir=str(target.get("include_dir") or ""),
        session_tag=session_tag,
        node_id=args.node_id or "manager-view-replay",
        run_dir=out_dir,
        project_root=project_root,
        surface_profile=args.surface_profile or None,
    )
    # Point the session (and therefore any scratch/lock files, e.g.
    # ``<session_dir>.cli.lock``) under out_dir rather than the repo root.
    # This late override is safe because manager readers consult
    # ``repl.session_dir`` lazily -- the node_state committed-tactic reader is a
    # lambda and the projection pipeline reads it per turn -- so it is picked up
    # on the first bootstrap/turn below.
    manager.repl.session_dir = str(out_dir / ".ec_session")

    followup_memory = None
    if render_followup is not None and NodeMemoryCls is not None:
        followup_memory = NodeMemoryCls(
            out_dir, manager.node_id, surface_profile=args.surface_profile or None
        )

    cleanup = _ReplayCleanup(manager, out_dir)
    atexit.register(cleanup.close)

    started = time.perf_counter()
    bootstrap = manager.bootstrap()
    initial_raw_view = dict(bootstrap.get("workspace_view") or manager.latest_view)
    initial_view = agent_surface(initial_raw_view)
    _write_json(out_dir / "bootstrap.json", _jsonable(bootstrap))
    _write_json(out_dir / "workspace_views" / "turn_000_bootstrap.json", initial_view)
    _write_json(out_dir / "raw_views" / "turn_000_bootstrap.json", initial_raw_view)

    report_steps: list[dict[str, Any]] = []
    previous_view = initial_view
    for index, step in enumerate(steps, start=1):
        intent = step.to_dict()
        turn_start = time.perf_counter()
        turn = manager.handle_agent_message(
            json.dumps(intent, separators=(",", ":"), sort_keys=False)
        )
        elapsed_ms = int((time.perf_counter() - turn_start) * 1000)
        post_raw_view = dict(turn.workspace_view or {})
        post_view = agent_surface(post_raw_view)

        if getattr(args, "write_followups", False):
            # Independent ground-truth: snapshot the literal EC daemon goal output
            # (current.out) AFTER this turn, untouched by any view projection.
            (out_dir / "ec_raw").mkdir(exist_ok=True)
            curr_out = Path(manager.repl.session_dir) / "current.out"
            _write_text(
                out_dir / "ec_raw" / f"turn_{index:03d}.txt",
                curr_out.read_text(encoding="utf-8", errors="replace")
                if curr_out.exists() else "(current.out missing)\n",
            )

        if followup_memory is not None and render_followup is not None:
            # Mirror the real worker call: render the current-code inline-read into
            # out_dir/node_memory/<node>/followups/, with the run's surface profile.
            try:
                render_followup(
                    turn,
                    index,
                    intent,
                    followup_memory,
                    full_view=getattr(manager, "latest_full_view", None),
                    surface_profile=args.surface_profile or None,
                )
            except Exception as exc:  # never let rendering abort the replay
                _write_text(
                    out_dir / "followup_render_errors.log",
                    f"turn {index}: {type(exc).__name__}: {exc}\n",
                )

        stem = f"turn_{index:03d}_{step.intent}"
        view_path = out_dir / "workspace_views" / f"{stem}.json"
        raw_view_path = out_dir / "raw_views" / f"{stem}.json"
        result_path = out_dir / "manager_results" / f"{stem}.json"
        diff_path = out_dir / "diffs" / f"{stem}_pre_to_post.diff"
        _write_json(view_path, post_view)
        _write_json(raw_view_path, post_raw_view)
        _write_json(
            result_path,
            {
                "turn": index,
                "intent": intent,
                "ok": bool(turn.ok),
                "elapsed_ms": elapsed_ms,
                "repair_prompt": turn.repair_prompt,
                "health_event": (
                    turn.health_event.to_dict() if turn.health_event else {}
                ),
                "manager_actions": _jsonable(turn.manager_actions),
                "snapshot": turn.snapshot.to_dict() if turn.snapshot else {},
            },
        )
        _write_text(
            diff_path,
            _diff_json(
                previous_view,
                post_view,
                fromfile=f"turn_{index - 1:03d}",
                tofile=stem,
                ignore_volatile=not args.strict_diff,
            ),
        )
        accepted = _turn_acceptance(turn.manager_actions)
        report_steps.append({
            "turn": index,
            "intent": intent,
            "ok": bool(turn.ok),
            "accepted": accepted,
            "elapsed_ms": elapsed_ms,
            "view": str(view_path),
            "manager_result": str(result_path),
            "pre_to_post_diff": str(diff_path),
            "label": step.label,
        })
        status = "ok" if turn.ok else "failed"
        accepted_text = "" if accepted is None else f" accepted={accepted}"
        print(
            f"{index:03d} {step.intent:<15} {status:<7}"
            f"{accepted_text:<15} {elapsed_ms:>6}ms {step.label}",
            flush=True,
        )
        previous_view = post_view
        if (not turn.ok or turn.health_event is not None) and not args.continue_on_failure:
            break

    report = {
        "kind": "manager_view_replay_report",
        "file": str(target["file"]),
        "lemma": target["lemma"],
        "include_dir": target.get("include_dir") or "",
        "surface_profile": args.surface_profile or "",
        "steps_requested": len(steps),
        "steps_completed": len(report_steps),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "steps": report_steps,
    }
    _write_json(out_dir / "report.json", report)
    print(f"\nreport: {out_dir / 'report.json'}", flush=True)

    rc = 0 if all(step["ok"] for step in report_steps) else 1
    if args.reconcile:
        if not args.from_run:
            raise SystemExit("--reconcile requires --from-run")
        node_views_dir = Path(run_meta.get("node_views_dir") or "")
        if not node_views_dir.exists():
            raise SystemExit(
                f"--reconcile: run views dir not found: {node_views_dir!r} "
                "(is --from-run pointed at a real run?)"
            )
        reconcile = _reconcile_views(out_dir, node_views_dir, strict=args.strict_diff)
        _write_json(out_dir / "reconcile_report.json", reconcile)
        # Denominator is turns_total (every turn the live run recorded), so a
        # replay that stopped early cannot read as a clean "N/N identical".
        detail = []
        if reconcile["mismatched"]:
            detail.append(f"{reconcile['mismatched']} differ")
        if reconcile["missing"]:
            detail.append(f"{reconcile['missing']} not reproduced")
        suffix = f" ({', '.join(detail)})" if detail else ""
        print(
            f"reconcile: {reconcile['identical']}/{reconcile['turns_total']} "
            f"turns identical to the live run{suffix}; report: "
            f"{out_dir / 'reconcile_report.json'}",
            flush=True,
        )
        if args.fail_on_reconcile_diff and reconcile["mismatched"]:
            rc = 1
    cleanup.close()
    return rc


def compare(args: argparse.Namespace) -> int:
    left = Path(args.left).resolve()
    right = Path(args.right).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else right / "view_diffs"
    out_dir.mkdir(parents=True, exist_ok=True)
    left_views = _view_files(left)
    right_views = _view_files(right)
    names = sorted(set(left_views) | set(right_views))
    rows: list[dict[str, Any]] = []
    mismatch_count = 0
    for name in names:
        lpath = left_views.get(name)
        rpath = right_views.get(name)
        diff_text = ""
        proof_diverged = False
        if lpath is None or rpath is None:
            mismatch_count += 1
            diff_text = f"missing: left={bool(lpath)} right={bool(rpath)}\n"
        else:
            left_view = _read_json(lpath)
            right_view = _read_json(rpath)
            # Anchor on proof state: if the two sides reached a different goal
            # for this turn, a downstream view diff is a PROOF divergence, not a
            # rendering change.  Flag it so reviewers do not misread it.
            proof_diverged = _goal_signature(left_view) != _goal_signature(right_view)
            diff_text = _diff_json(
                left_view,
                right_view,
                fromfile=str(lpath),
                tofile=str(rpath),
                ignore_volatile=not args.strict,
            )
            if proof_diverged:
                diff_text = (
                    "# proof_diverged: current_goal.lines differ for this turn; "
                    "view differences below may be proof-state, not rendering.\n"
                ) + diff_text
            if diff_text:
                mismatch_count += 1
        diff_path = out_dir / f"{Path(name).stem}.diff"
        _write_text(diff_path, diff_text)
        rows.append({
            "view": name,
            "left": str(lpath) if lpath else "",
            "right": str(rpath) if rpath else "",
            "diff": str(diff_path),
            "different": bool(diff_text),
            "proof_diverged": proof_diverged,
        })
    report = {
        "kind": "manager_view_replay_compare",
        "left": str(left),
        "right": str(right),
        "strict": bool(args.strict),
        "views_compared": len(names),
        "mismatches": mismatch_count,
        "views": rows,
    }
    _write_json(out_dir / "compare_report.json", report)
    print(f"compared: {len(names)} view(s); mismatches: {mismatch_count}")
    print(f"report: {out_dir / 'compare_report.json'}")
    return 1 if mismatch_count and args.fail_on_diff else 0


class _ReplayCleanup:
    def __init__(self, manager: Any, out_dir: Path) -> None:
        self._manager = manager
        self._out_dir = Path(out_dir)
        self._closed = False

    def close(self) -> bool:
        if self._closed:
            return False
        self._closed = True
        released = False
        error = ""
        try:
            repl = getattr(self._manager, "repl", None)
            close = getattr(repl, "close", None)
            if callable(close):
                released = bool(close())
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        try:
            _write_json(
                self._out_dir / "cleanup_report.json",
                {
                    "kind": "manager_view_replay_cleanup",
                    "daemon_session_closed": released,
                    "error": error,
                },
            )
        except Exception:
            pass
        return released


def _resolve_target(args: argparse.Namespace, *, project_root: Path) -> dict[str, Any]:
    target: dict[str, Any] = {}
    if args.proof_bank_lemma:
        target.update(
            _proof_bank_entry(
                Path(args.proof_bank),
                args.proof_bank_lemma,
                project_root=project_root,
            )
        )
    if args.file:
        target["file"] = args.file
    if args.lemma:
        target["lemma"] = args.lemma
    if args.include_dir:
        target["include_dir"] = args.include_dir
    if not target.get("file") or not target.get("lemma"):
        raise SystemExit("need --file and --lemma, or --proof-bank-lemma")
    file = Path(str(target["file"]))
    if not file.is_absolute():
        file = project_root / file
    target["file"] = file.resolve()
    target.setdefault("include_dir", "")
    return target


def _make_manager(manager_cls: Any, **kwargs: Any) -> Any:
    params = set(inspect.signature(manager_cls).parameters)
    clean = {key: value for key, value in kwargs.items() if key in params}
    if "surface_profile" not in params and "ablation_profile" in params:
        clean["ablation_profile"] = kwargs.get("surface_profile")
    return manager_cls(**clean)


def _resolve_steps(
    args: argparse.Namespace,
    target: dict[str, Any],
    *,
    project_root: Path,
) -> list[StepSpec]:
    explicit: list[StepSpec] = []
    for raw in args.step or []:
        explicit.append(_step_from_text(raw, default_intent=args.intent))
    for raw in args.tactic or []:
        explicit.append(StepSpec(args.intent, {"tactic": raw}))
    if args.tactics_file:
        explicit.extend(_steps_from_tactics_file(Path(args.tactics_file), args.intent))
    if explicit:
        return explicit
    if args.proof_bank_lemma:
        entry = _proof_bank_entry(
            Path(args.proof_bank),
            args.proof_bank_lemma,
            project_root=project_root,
        )
        tactics = [str(t) for t in list(entry.get("tactics") or []) if str(t).strip()]
        return [StepSpec(args.intent, {"tactic": tactic}) for tactic in tactics]
    if not args.no_source_proof:
        return [
            StepSpec(args.intent, {"tactic": tactic})
            for tactic in _source_proof_tactics(
                Path(target["file"]),
                str(target["lemma"]),
            )
        ]
    return []


def _step_from_text(raw: str, *, default_intent: str) -> StepSpec:
    text = str(raw or "").strip()
    if not text:
        raise SystemExit("empty --step")
    if text.startswith("{"):
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise SystemExit("--step JSON must be an object")
        return StepSpec(str(obj.get("intent") or default_intent), dict(obj.get("payload") or {}))
    for prefix, intent, key in (
        ("commit:", "commit_tactic", "tactic"),
        ("lookup:", "lookup_symbol", "symbol"),
    ):
        if text.startswith(prefix):
            return StepSpec(intent, {key: text[len(prefix):].strip()})
    if text.startswith("inspect:"):
        topic = normalize_context_topic(text[len("inspect:"):].strip() or "goal_info")
        return StepSpec(topic, {})
    return StepSpec(default_intent, {"tactic": text})


def _steps_from_tactics_file(path: Path, default_intent: str) -> list[StepSpec]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("[") or stripped.startswith("{"):
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            obj = obj.get("steps") or obj.get("tactics") or []
        if not isinstance(obj, list):
            raise SystemExit(f"{path} must contain a JSON list or steps/tactics object")
        steps: list[StepSpec] = []
        for item in obj:
            if isinstance(item, str):
                steps.append(StepSpec(default_intent, {"tactic": item}))
            elif isinstance(item, dict):
                steps.append(StepSpec(str(item.get("intent") or default_intent), dict(item.get("payload") or {})))
            else:
                raise SystemExit(f"unsupported tactic item in {path}: {item!r}")
        return steps
    return [
        _step_from_text(line, default_intent=default_intent)
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _proof_bank_entry(path: Path, lemma: str, *, project_root: Path) -> dict[str, Any]:
    if not path.is_absolute():
        path = project_root / path
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        entry = json.loads(raw)
        if entry.get("lemma") == lemma:
            return dict(entry)
    raise SystemExit(f"lemma {lemma!r} not found in proof bank {path}")


def _source_proof_tactics(file: Path, lemma: str) -> list[str]:
    from workflow.validation.proof_view_replay import (
        _split_human_tactics,
        iter_proof_spans,
    )

    spans = [span for span in iter_proof_spans(file) if span.name == lemma]
    if not spans:
        raise SystemExit(f"lemma {lemma!r} not found in {file}")
    return _split_human_tactics(spans[0].body)


def _steps_from_run(
    run_dir_arg: str,
    node_arg: str,
    *,
    project_root: Path,
) -> tuple[list[StepSpec], dict[str, Any]]:
    """Reconstruct the exact ordered intent stream the agent submitted in a run.

    The source-proof / proof-bank step sources only know committed tactics.  A
    real managed run, however, records every intent (inspect / lookup /
    undo / commit) in each node's ``timeline.jsonl`` + ``manager_results/``.
    Replaying that full stream makes the captured view at each turn match the
    agent's real decision surface, including read-only context overlays.

    Returns ``(steps, meta)`` where ``meta`` carries the auto-derived target
    (``file``/``lemma``/``include_dir``/``surface_profile``) and the node's saved
    ``workspace_views`` dir (``node_views_dir``) used by ``--reconcile``.
    """
    from workflow.validation import agent_view_timeline_report as avt

    iteration_dir, node_dir = _resolve_run_node(
        run_dir_arg, node_arg, project_root=project_root, avt=avt
    )
    node_id = avt._node_id_from_dir(node_dir)

    entries = [
        item
        for item in avt._read_jsonl(node_dir / "timeline.jsonl")
        if isinstance(item, dict) and item.get("kind") == "manager_turn"
    ]
    entries.sort(key=lambda item: avt._int(item.get("turn")))
    steps: list[StepSpec] = []
    for entry in entries:
        turn = avt._int(entry.get("turn"))
        if turn <= 0:
            continue
        # Prefer the authoritative handled_intent recorded by the manager; fall
        # back to the timeline entry's intent.
        result = avt._read_json(node_dir / "manager_results" / f"turn_{turn:03d}.json")
        intent = result.get("handled_intent") if isinstance(result, dict) else None
        if not isinstance(intent, dict) or not intent.get("intent"):
            intent = entry.get("intent")
        if not isinstance(intent, dict) or not intent.get("intent"):
            continue
        steps.append(StepSpec(str(intent.get("intent")), dict(intent.get("payload") or {})))

    meta = _run_target_meta(iteration_dir, node_id, node_dir, avt=avt)
    meta["node"] = node_id
    meta["node_views_dir"] = str((node_dir / "workspace_views").resolve())
    meta["intent_count"] = len(steps)
    return steps, meta


def _resolve_run_node(
    run_dir_arg: str,
    node_arg: str,
    *,
    project_root: Path,
    avt: Any,
) -> tuple[Path, Path]:
    p = Path(run_dir_arg).expanduser()
    if not p.exists() and not p.is_absolute():
        p = project_root / run_dir_arg
    p = p.resolve()
    if (p / "node_memory").is_dir():
        iteration_dir = p
    elif (p / "timeline.jsonl").exists():
        # ``p`` is itself a node_memory/<node> dir.
        return p.parent.parent, p
    else:
        raise SystemExit(
            f"--from-run: {p} is neither an iteration dir (no node_memory/) nor a "
            "node dir (no timeline.jsonl)"
        )
    node_dirs = avt._node_memory_dirs(iteration_dir)
    if not node_dirs:
        raise SystemExit(f"--from-run: no node_memory nodes under {iteration_dir}")
    if node_arg:
        wanted = _norm_node(node_arg)
        for node_dir in node_dirs:
            if wanted in {
                _norm_node(avt._node_id_from_dir(node_dir)),
                _norm_node(node_dir.name),
            }:
                return iteration_dir, node_dir
        have = [avt._node_id_from_dir(d) for d in node_dirs]
        raise SystemExit(f"--from-run-node {node_arg!r} not found; have {have}")
    if len(node_dirs) == 1:
        return iteration_dir, node_dirs[0]
    chosen = _prefer_root_node(node_dirs, avt)
    print(
        f"--from-run: multiple nodes {[avt._node_id_from_dir(d) for d in node_dirs]}; "
        f"using {avt._node_id_from_dir(chosen)} (pass --from-run-node to choose). "
        "Non-root nodes resume mid-proof and may diverge from a fresh bootstrap.",
        flush=True,
    )
    return iteration_dir, chosen


def _norm_node(text: str) -> str:
    return (
        str(text)
        .replace("Tree-", "")
        .replace("Tree_", "")
        .replace("-", ".")
        .replace("_", ".")
        .strip(".")
    )


def _prefer_root_node(node_dirs: list[Path], avt: Any) -> Path:
    """Prefer a node that started from the lemma bootstrap (no replayed prefix)."""
    for node_dir in node_dirs:
        for entry in avt._read_jsonl(node_dir / "timeline.jsonl"):
            if isinstance(entry, dict) and entry.get("kind") == "bootstrap":
                if avt._int(entry.get("replay_prefix_count")) == 0:
                    return node_dir
                break
    return node_dirs[0]


def _run_target_meta(
    iteration_dir: Path,
    node_id: str,
    node_dir: Path,
    *,
    avt: Any,
) -> dict[str, Any]:
    record = avt._read_json(avt._bootstrap_file_for_node(iteration_dir, node_id))
    if not record:
        for item in avt._read_jsonl(iteration_dir / "manager_session_bootstrap.jsonl"):
            if isinstance(item, dict) and str(item.get("node") or "") == node_id:
                record = item
                break
    meta: dict[str, Any] = {}
    if not isinstance(record, dict):
        record = {}
    file = str(record.get("file") or "")
    lemma = str(record.get("lemma") or "")
    if file:
        meta["file"] = file
    if lemma:
        meta["lemma"] = lemma
    include_dirs = record.get("include_dirs")
    if isinstance(include_dirs, list) and include_dirs:
        meta["include_dirs"] = [str(d) for d in include_dirs]
        # The manager adds the file's own directory automatically and accepts one
        # extra include dir; prefer the first recorded dir that is not the file
        # directory.
        file_dir = str(Path(file).resolve().parent) if file else ""
        extra = [str(d) for d in include_dirs if str(Path(str(d)).resolve()) != file_dir]
        meta["include_dir"] = extra[0] if extra else str(include_dirs[0])
    profile = _profile_name(_dig(record, "workspace_view", "surface_profile"))
    if not profile:
        first_view = avt._read_json(node_dir / "workspace_views" / "turn_001.json")
        profile = _profile_name(first_view.get("surface_profile") if isinstance(first_view, dict) else "")
    if profile:
        meta["surface_profile"] = profile
    return meta


def _profile_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("surface_profile") or value.get("name") or "")
    return str(value or "")


def _project_root(args: argparse.Namespace) -> Path:
    raw = str(getattr(args, "project_root", "") or "").strip()
    root = Path(raw).expanduser() if raw else SCRIPT_PROJECT_ROOT
    return root.resolve()


def _prefer_project_root_for_imports(project_root: Path) -> None:
    _guard_workflow_already_imported(project_root)
    root = str(project_root)
    if root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    ec_dir = str(project_root / "core" / "easycrypt")
    if ec_dir in sys.path:
        sys.path.remove(ec_dir)
    sys.path.insert(0, ec_dir)


def _guard_workflow_already_imported(project_root: Path) -> None:
    """Fail loudly if ``--project-root`` cannot actually take effect.

    If the ``workflow`` package is already imported from a DIFFERENT root than
    the requested ``project_root`` (the classic ``python3 -m`` footgun), then
    prepending ``project_root`` to ``sys.path`` does nothing -- Python keeps the
    cached module -- and the replay would silently exercise the wrong checkout's
    code.  Refuse rather than produce a misleading artifact.
    """
    module = sys.modules.get("workflow")
    module_paths = list(getattr(module, "__path__", []) or []) if module is not None else []
    if not module_paths:
        return
    expected = (project_root / "workflow").resolve()
    for raw in module_paths:
        try:
            if Path(raw).resolve() == expected:
                return
        except Exception:
            continue
    raise SystemExit(
        "--project-root cannot override an already-imported `workflow` package "
        f"(imported from {module_paths!r}, requested {str(expected)!r}); run this "
        "script BY FILE PATH (python3 "
        f"{project_root / 'workflow' / 'validation' / 'manager_view_replay.py'} ...), "
        "not via `python3 -m`."
    )


def _turn_acceptance(actions: Any) -> bool | None:
    if not isinstance(actions, list):
        return None
    for action in actions:
        if not isinstance(action, dict) or action.get("label") == "agent_view":
            continue
        observation = action.get("agent_observation")
        if isinstance(observation, dict):
            if "accepted" in observation:
                return bool(observation.get("accepted"))
            status = str(observation.get("status") or "").lower()
            if status in {"preflight_accepted", "accepted", "ok"}:
                return True
            if status in {"preflight_rejected", "rejected", "error", "failed"}:
                return False
        if action.get("exit_code") not in (None, 0):
            return False
    return None


# Volatility split:
#   * agent_display_view (applied at save time) already removes agent-hidden
#     metadata such as view_hash / session_epoch / based_on_state_version /
#     schema_version, so those no longer need to be ignored here.
#   * _VOLATILE_KEYS handles the remaining CROSS-RUN/PATH noise: per-run node
#     identity, on-disk session paths/tags, and the ``*_artifact`` path keys.
# Everything else (panel content AND order) is meant to be compared faithfully.
_VOLATILE_KEYS = {
    "artifact",
    "context_artifact",
    "full_context_artifact",
    "node_id",
    "proof_context_view_artifact",
    "session_dir",
    "session_tag",
    "workspace_view_artifact",
}


def _normalize_for_compare(value: Any, *, ignore_volatile: bool) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if ignore_volatile and key in _VOLATILE_KEYS:
                continue
            out[key] = _normalize_for_compare(item, ignore_volatile=ignore_volatile)
        return out
    if isinstance(value, list):
        return [
            _normalize_for_compare(item, ignore_volatile=ignore_volatile)
            for item in value
        ]
    return value


def _diff_json(
    left: Any,
    right: Any,
    *,
    fromfile: str,
    tofile: str,
    ignore_volatile: bool,
) -> str:
    left_norm = _normalize_for_compare(left, ignore_volatile=ignore_volatile)
    right_norm = _normalize_for_compare(right, ignore_volatile=ignore_volatile)
    left_lines = _json_lines(left_norm)
    right_lines = _json_lines(right_norm)
    return "".join(
        difflib.unified_diff(
            left_lines,
            right_lines,
            fromfile=fromfile,
            tofile=tofile,
        )
    )


def _view_files(root: Path) -> dict[str, Path]:
    # Prefer the current ``workspace_views/`` layout; fall back to the legacy
    # ``views/`` directory (older artifacts), then to the root itself.
    view_dir = root / "workspace_views"
    if not view_dir.exists():
        view_dir = root / "views"
    if not view_dir.exists():
        view_dir = root
    return {path.name: path for path in sorted(view_dir.glob("turn_*.json"))}


def _reconcile_views(out_dir: Path, node_views_dir: Path, *, strict: bool) -> dict[str, Any]:
    """Diff freshly-replayed views against the run's own saved agent views.

    Run this with ``--project-root`` at the SAME commit the run executed on: if
    every turn is identical, the report->replay reconstruction is faithful and a
    later CROSS-COMMIT diff is attributable to code, not to a flawed
    reconstruction.  Mismatches localize nondeterminism (e.g. async SMT) or
    reconstruction gaps (e.g. a non-root node that resumed mid-proof).
    """
    fresh = _turn_indexed_views(out_dir / "workspace_views")
    live = _turn_indexed_views(node_views_dir)
    diff_dir = out_dir / "reconcile_diffs"
    diff_dir.mkdir(parents=True, exist_ok=True)
    turns = sorted(set(fresh) | set(live))
    both = [turn for turn in turns if turn in fresh and turn in live]
    rows: list[dict[str, Any]] = []
    identical = 0
    for turn in turns:
        fpath = fresh.get(turn)
        lpath = live.get(turn)
        if fpath is None or lpath is None:
            rows.append({
                "turn": turn,
                "identical": False,
                "fresh_view": str(fpath) if fpath else "",
                "live_view": str(lpath) if lpath else "",
                "note": "missing on one side",
            })
            continue
        live_view = _read_json(lpath)
        fresh_view = _read_json(fpath)
        goal_diverged = _goal_signature(live_view) != _goal_signature(fresh_view)
        diff_text = _diff_json(
            live_view,
            fresh_view,
            fromfile=f"live/{lpath.name}",
            tofile=f"replay/{fpath.name}",
            ignore_volatile=not strict,
        )
        same = not diff_text
        diff_path = ""
        if same:
            identical += 1
        else:
            diff_path = str(diff_dir / f"turn_{turn:03d}.diff")
            _write_text(Path(diff_path), diff_text)
        rows.append({
            "turn": turn,
            "identical": same,
            "goal_diverged": goal_diverged,
            "fresh_view": str(fpath),
            "live_view": str(lpath),
            "diff": diff_path,
        })
    return {
        "kind": "manager_view_replay_reconcile",
        "node_views_dir": str(node_views_dir),
        "turns_compared": len(both),
        "turns_total": len(turns),
        # Turns present on only one side (e.g. the replay stopped early or was
        # capped by --max-steps); these were never reproduced and count as
        # mismatched, not as silent passes.
        "missing": len(turns) - len(both),
        "identical": identical,
        "mismatched": len(turns) - identical,
        "views": rows,
    }


def _turn_indexed_views(view_dir: Path) -> dict[int, Path]:
    """Map turn number -> view path.  Handles both the replay layout
    (``turn_001_commit_tactic.json``) and the live-run layout
    (``turn_001.json``); the bootstrap view (turn 0) is skipped."""
    out: dict[int, Path] = {}
    if not view_dir.exists():
        return out
    for path in sorted(view_dir.glob("turn_*.json")):
        match = re.match(r"turn_0*(\d+)", path.name)
        if not match:
            continue
        turn = int(match.group(1))
        if turn == 0:
            continue
        out.setdefault(turn, path)
    return out


def _json_lines(obj: Any) -> list[str]:
    # sort_keys=False is deliberate: the saved views are already in canonical
    # panel order (order_agent_view), so preserving key order here makes the
    # diff sensitive to panel/key REORDERING -- the #1 regression this tool must
    # catch.  Sorting keys would alphabetize and make the diff order-blind.
    return [
        line + "\n"
        for line in json.dumps(obj, indent=2, sort_keys=False, ensure_ascii=False).splitlines()
    ]


def _goal_signature(view: Any) -> str:
    """sha1 of the joined ``current_goal.lines`` (proof-state anchor)."""
    lines = []
    if isinstance(view, dict):
        current_goal = view.get("current_goal")
        if isinstance(current_goal, dict) and isinstance(current_goal.get("lines"), list):
            lines = [str(line) for line in current_goal["lines"]]
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    return value


def _safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "manager_view_replay"


def _compact(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_replay = sub.add_parser("replay")
    p_replay.add_argument("--file", default="")
    p_replay.add_argument("--lemma", default="")
    p_replay.add_argument("--include-dir", default="")
    p_replay.add_argument("--proof-bank", default="workflow/proof_bank.jsonl")
    p_replay.add_argument("--proof-bank-lemma", default="")
    p_replay.add_argument(
        "--project-root",
        default="",
        help=(
            "Checkout/worktree whose manager/view code should run. For a different "
            "worktree, execute this script by file path so that checkout can be "
            "placed first on sys.path."
        ),
    )
    p_replay.add_argument("--tactic", action="append", default=[])
    p_replay.add_argument(
        "--step",
        action="append",
        default=[],
        help=(
            "One step. Plain text is a tactic; prefixes commit:, inspect:, "
            "lookup: choose the intent; JSON intent objects also work."
        ),
    )
    p_replay.add_argument("--tactics-file", default="")
    p_replay.add_argument(
        "--from-run",
        default="",
        help=(
            "Replay the agent's ACTUAL recorded intent stream from a managed run "
            "(an iteration dir such as .../iteration_1, or a node_memory/<node> "
            "dir). Includes inspect/lookup/undo, not just committed "
            "tactics, and auto-derives --file/--lemma/--include-dir/"
            "--surface-profile from the run unless given explicitly."
        ),
    )
    p_replay.add_argument(
        "--from-run-node",
        default="",
        help=(
            "Which run node to replay (e.g. Tree-0.0). Defaults to the single "
            "node, else a root node that started from the lemma bootstrap."
        ),
    )
    p_replay.add_argument(
        "--reconcile",
        action="store_true",
        help=(
            "After replay, diff each fresh view against the run's own saved agent "
            "view (requires --from-run). Run with --project-root at the SAME "
            "commit the run executed on to validate reconstruction fidelity."
        ),
    )
    p_replay.add_argument(
        "--fail-on-reconcile-diff",
        action="store_true",
        help="Exit non-zero if any reconciled turn differs from the live run.",
    )
    p_replay.add_argument(
        "--intent",
        choices=["commit_tactic"],
        default="commit_tactic",
        help="Default intent for plain tactics.",
    )
    p_replay.add_argument("--max-steps", type=int, default=0)
    p_replay.add_argument("--out-dir", default="artifacts/manager_view_replay")
    p_replay.add_argument("--clean", action="store_true")
    p_replay.add_argument("--continue-on-failure", action="store_true")
    p_replay.add_argument("--strict-diff", action="store_true")
    p_replay.add_argument("--surface-profile", default="")
    p_replay.add_argument("--session-tag", default="")
    p_replay.add_argument("--node-id", default="")
    p_replay.add_argument("--no-source-proof", action="store_true")
    p_replay.add_argument(
        "--write-followups",
        action="store_true",
        help=(
            "Also render the EXACT current-code agent-facing inline-read (the "
            "followup markdown the prover reads) per turn into "
            "out_dir/node_memory/<node>/followups/turn_NNN.md, plus an ec_raw/ "
            "snapshot of the literal EC goal. For panel audits."
        ),
    )
    p_replay.set_defaults(func=replay)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("--left", required=True)
    p_compare.add_argument("--right", required=True)
    p_compare.add_argument("--out-dir", default="")
    p_compare.add_argument("--strict", action="store_true")
    p_compare.add_argument("--fail-on-diff", action="store_true")
    p_compare.set_defaults(func=compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
