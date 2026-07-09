"""Replay proof_bank entries through session_cli and save audit artifacts.

This is a regression/audit harness, not an agent prover. It replays known
tactic sequences step by step, captures structured events, runs selected
read-only tools at checkpoints, and verifies the final lemma.

The default runner calls session_cli handlers in-process so one Python process
can reuse the same Session object and daemon backend across steps. Pass
--subprocess to use the legacy subprocess-per-action runner. In-process replay
uses chain-style fast hooks by default; pass --full-hooks to run every
interactive guidance probe.

Example:
  python3 -m workflow.validation.proof_replay --limit 1 --audit-tools status

When run from Codex, execute this with the project's non-sandbox EasyCrypt
permission because it invokes session_cli / EasyCrypt.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SESSION_CLI = _PROJECT_ROOT / "core" / "easycrypt" / "session_cli.py"
_PROOF_BANK = _PROJECT_ROOT / "workflow" / "proof_bank.jsonl"
_DEFAULT_ARTIFACT_ROOT = _PROJECT_ROOT / "artifacts" / "replay"
_EC_DIR = _PROJECT_ROOT / "core" / "easycrypt"

from core.easycrypt.session_events import (
    candidate_closed_events,
    event_payload,
    events_of_type,
    read_event_file,
    summarize_events,
    validate_event_stream,
)
from core.easycrypt.session_projection import (
    projection_to_goal_info,
    read_proof_state_projection,
)
from core.easycrypt.session_agent_view import validate_proof_context_view
from core.easycrypt.session_command_summary import (
    command_summary_workspace_metrics,
    validate_command_summary,
)
from core.easycrypt.session_commit_response import validate_commit_response
from core.easycrypt.session_episode_timeline import (
    validate_session_episode_timeline,
)
from core.easycrypt.session_tool_view import validate_tool_view
from workflow.validation.replay_artifacts import (
    AuditReport,
    ReplaySummary,
)


def _load_proof_bank(path: Path = _PROOF_BANK) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("file") and entry.get("lemma") and entry.get("tactics"):
            entries.append(entry)
    return entries


def _safe_id(entry: dict[str, Any]) -> str:
    raw = f"{entry.get('file')}::{entry.get('lemma')}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")
    return f"{base[:90]}_{digest}"


def _include_dirs(entry: dict[str, Any], ec_path: Path) -> list[str]:
    dirs: list[str] = []
    include_dir = (entry.get("include_dir") or "").strip()
    if include_dir:
        dirs.append(include_dir)
    parent = str(ec_path.parent)
    if parent not in dirs:
        dirs.append(parent)
    return dirs


def _run(
    args: list[str],
    *,
    cwd: Path,
    timeout: float,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    t0 = time.time()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "cmd": args,
            "rc": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration_sec": round(time.time() - t0, 3),
            "timeout": False,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": args,
            "rc": 124,
            "stdout": e.stdout or "",
            "stderr": e.stderr or "",
            "duration_sec": round(time.time() - t0, 3),
            "timeout": True,
        }


def _session_cli_args(session_dir: Path, extra: list[str]) -> list[str]:
    return ["python3", str(_SESSION_CLI), "-d", str(session_dir), *extra]


def _ensure_session_api_importable():
    for path in (str(_EC_DIR), str(_PROJECT_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)
    import session_api  # type: ignore
    return session_api


def _base_cli_args(
    session_dir: Path,
    include_dirs: list[str],
) -> SimpleNamespace:
    """Build the arg namespace expected by session_cli command handlers."""
    return SimpleNamespace(
        dir=str(session_dir),
        file=None,
        lemma=None,
        include_dirs=list(include_dirs),
        command=None,
        from_file=None,
        deltas_only=False,
        keep_on_fail=False,
        against_lemma="",
        max_swap_attempts=20,
        as_json=False,
        ec_src=str(_PROJECT_ROOT / "easycrypt-src" / "theories"),
        max_results=30,
        verify_lemma=None,
        checkpoint_name=None,
        replay_name=None,
        where_name=None,
        members_scope=None,
        search=None,
        search_skeleton=None,
        sig_name=None,
        check_lemma=None,
        bad_trace_module=None,
        inv_from_lemma=None,
        tactic_forms=None,
    )


def _tool_payload(session, args, action_name: str, mutates_proof_state: bool) -> dict:
    payload = {
        "name": action_name,
        "mutates_proof_state": mutates_proof_state,
        "session_dir": str(session.dir.resolve()),
        "file": args.file,
        "lemma": args.lemma,
        "from_file": args.from_file,
        "has_command": bool(args.command),
        "as_json": bool(getattr(args, "as_json", False)),
    }
    for attr in (
        "where_name", "members_scope", "search", "search_skeleton",
        "sig_name", "check_lemma", "bad_trace_module",
        "inv_from_lemma", "tactic_forms", "verify_lemma",
        "checkpoint_name", "replay_name", "against_lemma",
    ):
        value = getattr(args, attr, None)
        if value not in (None, "", False):
            payload[attr] = value
    return payload


def _run_handler(
    session,
    args,
    *,
    action_name: str,
    handler,
    mutates_proof_state: bool,
    cmd: list[str],
) -> dict[str, Any]:
    """Run a session_cli handler in-process and capture CLI-like output.

    This preserves the command handlers, session files, and structured
    events while avoiding a new Python interpreter for every replay step.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    t0 = time.time()
    rc = 1
    timed_out = False
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        payload = _tool_payload(session, args, action_name, mutates_proof_state)
        try:
            if action_name != "start":
                session.emit_event("tool.called", payload)
            rc = handler(session, args)
            if action_name == "start":
                session.emit_event("tool.called", payload | {"logged_after": True})
            session.emit_event("tool.result", payload | {
                "exit_code": rc,
                "status": "ok" if rc == 0 else "failed",
            })
        except Exception as exc:
            session.emit_error_event("error.raised", exc, {
                "phase": "proof_replay_inprocess",
                "action": action_name,
            })
            traceback.print_exc(file=sys.stderr)
            rc = 1
    return {
        "cmd": cmd,
        "runner": "inprocess",
        "rc": rc,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "duration_sec": round(time.time() - t0, 3),
        "timeout": timed_out,
    }


def _run_start_inprocess(
    session,
    session_dir: Path,
    ec_path: Path,
    lemma: str,
    include_dirs: list[str],
) -> dict[str, Any]:
    from commands.session_commands import handle_start  # type: ignore

    args = _base_cli_args(session_dir, include_dirs)
    args.file = str(ec_path)
    args.lemma = lemma
    cmd_extra = ["-start", "-f", str(ec_path), "-lemma", lemma]
    for d in include_dirs:
        cmd_extra.extend(["-I", d])
    cmd = _session_cli_args(session_dir, cmd_extra)
    return _run_handler(
        session, args, action_name="start", handler=handle_start,
        mutates_proof_state=True, cmd=cmd,
    )


def _run_next_inprocess(
    session,
    session_dir: Path,
    include_dirs: list[str],
    tactic: str,
) -> dict[str, Any]:
    from commands.commit_commands import handle_next  # type: ignore

    args = _base_cli_args(session_dir, include_dirs)
    args.command = tactic
    return _run_handler(
        session, args, action_name="next", handler=handle_next,
        mutates_proof_state=True,
        cmd=_session_cli_args(session_dir, ["-next", "-c", tactic]),
    )


def _run_verify_inprocess(
    session,
    session_dir: Path,
    include_dirs: list[str],
    lemma: str,
    ec_path: Path,
) -> dict[str, Any]:
    from commands.inspect_commands import handle_verify_lemma  # type: ignore

    args = _base_cli_args(session_dir, include_dirs)
    args.file = str(ec_path)
    args.verify_lemma = lemma
    return _run_handler(
        session, args, action_name="verify",
        handler=handle_verify_lemma, mutates_proof_state=False,
        cmd=_session_cli_args(
            session_dir, ["-verify", lemma, "-f", str(ec_path)],
        ),
    )


def _run_audit_tool_inprocess(
    session,
    session_dir: Path,
    include_dirs: list[str],
    tool: str,
) -> dict[str, Any] | None:
    spec = _tool_handler(tool)
    if spec is None:
        return None
    action_name, handler, mutates_proof_state, tool_args = spec
    args = _base_cli_args(session_dir, include_dirs)
    return _run_handler(
        session, args, action_name=action_name, handler=handler,
        mutates_proof_state=mutates_proof_state,
        cmd=_session_cli_args(session_dir, tool_args),
    )


def _tool_handler(tool: str):
    if tool == "status":
        from commands.session_commands import handle_status  # type: ignore
        return ("status", handle_status, False, ["-status"])
    if tool == "agent-view":
        from commands.session_commands import handle_agent_view  # type: ignore
        return ("agent-view", handle_agent_view, False, ["-agent-view"])
    if tool == "episode-view":
        from commands.session_commands import handle_episode_view  # type: ignore
        return ("episode-view", handle_episode_view, False, ["-episode-view"])
    if tool == "goal-info":
        from commands.inspect_commands import handle_goal_info  # type: ignore
        return ("goal-info", handle_goal_info, False, ["-goal-info"])
    if tool == "lemma-hints":
        from search.handlers import handle_lemma_hints  # type: ignore
        return ("lemma-hints", handle_lemma_hints, False, ["-lemma-hints"])
    if tool == "suggest-close":
        from commands.speculative_commands import handle_suggest_close  # type: ignore
        return ("suggest-close", handle_suggest_close, False, ["-suggest-close"])
    if tool == "diagnose":
        from commands.inspect_commands import handle_diagnose  # type: ignore
        return ("diagnose", handle_diagnose, False, ["-diagnose"])
    if tool == "clones":
        from search.handlers import handle_clones  # type: ignore
        return ("clones", handle_clones, False, ["-clones"])
    if tool == "file-index":
        from search.handlers import handle_file_index  # type: ignore
        return ("file-index", handle_file_index, False, ["-file-index"])
    if tool == "align":
        from commands.speculative_commands import handle_align  # type: ignore
        return ("align", handle_align, False, ["-align"])
    if tool == "subgoal-gap":
        from commands.inspect_commands import handle_subgoal_gap  # type: ignore
        return ("subgoal-gap", handle_subgoal_gap, False, ["-subgoal-gap"])
    if tool == "swap-search":
        from commands.speculative_commands import handle_swap_search  # type: ignore
        return ("swap-search", handle_swap_search, False, ["-swap-search"])
    if tool == "bridge-lemmas":
        from search.handlers import handle_bridge_lemmas  # type: ignore
        return ("bridge-lemmas", handle_bridge_lemmas, False, ["-bridge-lemmas"])
    return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _copy_tree_if_exists(src: Path, dst: Path) -> None:
    if src.exists() and src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


def replay_entry(
    entry: dict[str, Any],
    *,
    artifact_root: Path,
    audit_tools: list[str],
    audit_every: int,
    timeout: float,
    keep_session: bool,
    subprocess_mode: bool = False,
    full_hooks: bool = False,
) -> dict[str, Any]:
    proof_id = _safe_id(entry)
    proof_dir = artifact_root / proof_id
    if proof_dir.exists():
        shutil.rmtree(proof_dir)
    proof_dir.mkdir(parents=True, exist_ok=True)

    session_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"proof-replay-{proof_id}"
    if session_dir.exists():
        shutil.rmtree(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    ec_path = (_PROJECT_ROOT / entry["file"]).resolve()
    include_dirs = _include_dirs(entry, ec_path)
    start_extra = ["-start", "-f", str(ec_path), "-lemma", entry["lemma"]]
    for d in include_dirs:
        start_extra.extend(["-I", d])

    commands: list[dict[str, Any]] = []
    session = None
    if subprocess_mode:
        start = _run(
            _session_cli_args(session_dir, start_extra),
            cwd=_PROJECT_ROOT, timeout=timeout,
        )
    else:
        session_api = _ensure_session_api_importable()
        session = session_api.open_session(
            session_dir, include_dirs=include_dirs,
        )
        start = _run_start_inprocess(
            session, session_dir, ec_path, entry["lemma"], include_dirs,
        )
    commands.append({"kind": "start", **start})
    (proof_dir / "start.stdout.txt").write_text(start["stdout"], encoding="utf-8")
    (proof_dir / "start.stderr.txt").write_text(start["stderr"], encoding="utf-8")
    if start["rc"] != 0:
        return _finish_replay(
            entry, proof_id, proof_dir, session_dir, commands,
            outcome="START_FAILED", keep_session=keep_session,
            subprocess_mode=subprocess_mode, full_hooks=full_hooks,
        )
    if session is not None and not full_hooks:
        # Replay validates an existing tactic list. We still run the real
        # commit path, state-diff hooks, audit tools, and final verification,
        # but skip expensive hook-internal daemon probes that only produce
        # interactive guidance. This mirrors commit_commands.handle_chain().
        session._chain_skip_verify = True

    tactics = list(entry["tactics"])
    has_qed = any(
        str(t).strip().lower().rstrip(".").strip() == "qed"
        for t in tactics
    )
    replay_tactics = [
        {"tactic": str(t), "synthetic_qed": False}
        for t in tactics
    ]
    if not has_qed:
        replay_tactics.append({"tactic": "qed.", "synthetic_qed": True})

    total_steps = len(replay_tactics)
    for idx, item in enumerate(replay_tactics, start=1):
        tactic = item["tactic"]
        if subprocess_mode:
            step = _run(
                _session_cli_args(session_dir, ["-next", "-c", tactic]),
                cwd=_PROJECT_ROOT, timeout=timeout,
            )
        else:
            assert session is not None
            step = _run_next_inprocess(
                session, session_dir, include_dirs, tactic,
            )
        commands.append({
            "kind": "next",
            "step": idx,
            "tactic": tactic,
            "synthetic_qed": item["synthetic_qed"],
            **step,
        })
        stem = (
            f"step_{idx:03d}_synthetic_qed"
            if item["synthetic_qed"] else f"step_{idx:03d}"
        )
        (proof_dir / f"{stem}.stdout.txt").write_text(step["stdout"], encoding="utf-8")
        (proof_dir / f"{stem}.stderr.txt").write_text(step["stderr"], encoding="utf-8")

        if _should_audit_step(idx, total_steps, step, audit_every):
            _run_audit_tools(
                session_dir, proof_dir, commands, idx, stem,
                audit_tools, timeout, include_dirs=include_dirs,
                session=session, subprocess_mode=subprocess_mode,
            )
        if step["rc"] != 0:
            return _finish_replay(
                entry, proof_id, proof_dir, session_dir, commands,
                outcome="TACTIC_FAILED", keep_session=keep_session,
                subprocess_mode=subprocess_mode, full_hooks=full_hooks,
            )

    if subprocess_mode:
        verify = _run(
            _session_cli_args(
                session_dir, ["-verify", entry["lemma"], "-f", str(ec_path)],
            ),
            cwd=_PROJECT_ROOT, timeout=timeout,
        )
    else:
        assert session is not None
        verify = _run_verify_inprocess(
            session, session_dir, include_dirs, entry["lemma"], ec_path,
        )
    commands.append({"kind": "verify", **verify})
    (proof_dir / "verify.stdout.txt").write_text(verify["stdout"], encoding="utf-8")
    (proof_dir / "verify.stderr.txt").write_text(verify["stderr"], encoding="utf-8")
    outcome = "PASS" if verify["rc"] == 0 else "VERIFY_FAILED"
    return _finish_replay(
        entry, proof_id, proof_dir, session_dir, commands,
        outcome=outcome, keep_session=keep_session,
        subprocess_mode=subprocess_mode, full_hooks=full_hooks,
    )


def _should_audit_step(
    idx: int, total_steps: int, step: dict[str, Any], audit_every: int,
) -> bool:
    """Audit first/last/error/closed steps plus every Nth step."""
    if idx == 1 or idx == total_steps:
        return True
    text = f"{step.get('stdout', '')}\n{step.get('stderr', '')}"
    if step.get("rc") != 0:
        return True
    markers = (
        "No more goals",
        "[ALL_GOALS_CLOSED]",
        "[GOAL_CLOSED]",
        "[TACTIC_NO_EFFECT_AUTO_REVERTED]",
        "[DAEMON_REJECTED]",
        "[error",
        "[critical",
        "[fatal",
    )
    if any(m in text for m in markers):
        return True
    return audit_every > 0 and idx % audit_every == 0


def _run_audit_tools(
    session_dir: Path,
    proof_dir: Path,
    commands: list[dict[str, Any]],
    idx: int,
    stem: str,
    audit_tools: list[str],
    timeout: float,
    *,
    include_dirs: list[str],
    session=None,
    subprocess_mode: bool = False,
) -> None:
    tool_dir = proof_dir / "tool_outputs" / stem
    for tool in audit_tools:
        if subprocess_mode:
            tool_args = _tool_args(tool)
            if tool_args is None:
                continue
            tr = _run(
                _session_cli_args(session_dir, tool_args),
                cwd=_PROJECT_ROOT, timeout=timeout,
            )
        else:
            if session is None:
                continue
            tr = _run_audit_tool_inprocess(
                session, session_dir, include_dirs, tool,
            )
            if tr is None:
                continue
        commands.append({
            "kind": "audit_tool", "step": idx, "tool": tool, **tr,
        })
        tool_dir.mkdir(parents=True, exist_ok=True)
        (tool_dir / f"{tool}.stdout.txt").write_text(
            tr["stdout"], encoding="utf-8",
        )
        (tool_dir / f"{tool}.stderr.txt").write_text(
            tr["stderr"], encoding="utf-8",
        )


def _tool_args(tool: str) -> list[str] | None:
    mapping = {
        "status": ["-status"],
        "agent-view": ["-agent-view"],
        "goal-info": ["-goal-info"],
        "lemma-hints": ["-lemma-hints"],
        "suggest-close": ["-suggest-close"],
        "diagnose": ["-diagnose"],
        "clones": ["-clones"],
        "file-index": ["-file-index"],
        "align": ["-align"],
        "subgoal-gap": ["-subgoal-gap"],
        "swap-search": ["-swap-search"],
        "bridge-lemmas": ["-bridge-lemmas"],
        "episode-view": ["-episode-view"],
    }
    return mapping.get(tool)


def _finish_replay(
    entry: dict[str, Any],
    proof_id: str,
    proof_dir: Path,
    session_dir: Path,
    commands: list[dict[str, Any]],
    *,
    outcome: str,
    keep_session: bool,
    subprocess_mode: bool,
    full_hooks: bool,
) -> dict[str, Any]:
    events = read_event_file(session_dir / "events.jsonl")
    report = _build_consistency_report(commands, events, outcome, session_dir)
    _write_json(proof_dir / "commands.json", commands)
    _write_json(proof_dir / "audit_report.json", report)
    _copy_if_exists(session_dir / "events.jsonl", proof_dir / "events.jsonl")
    _copy_if_exists(session_dir / "history.ec", proof_dir / "history.ec")
    _copy_if_exists(session_dir / "current.out", proof_dir / "current.out")
    _copy_tree_if_exists(session_dir / "tool_views", proof_dir / "tool_views")
    _copy_tree_if_exists(
        session_dir / "proof_context_views",
        proof_dir / "proof_context_views",
    )
    _copy_tree_if_exists(
        session_dir / "prover_workspace_views",
        proof_dir / "prover_workspace_views",
    )
    _copy_tree_if_exists(session_dir / "agent_views", proof_dir / "agent_views")
    _copy_tree_if_exists(
        session_dir / "commit_responses",
        proof_dir / "commit_responses",
    )
    _copy_tree_if_exists(
        session_dir / "command_summaries",
        proof_dir / "command_summaries",
    )
    _copy_tree_if_exists(
        session_dir / "episode_timelines",
        proof_dir / "episode_timelines",
    )

    audit_report = AuditReport.from_dict(report)
    summary = ReplaySummary(
        proof_id=proof_id,
        file=str(entry.get("file") or ""),
        lemma=str(entry.get("lemma") or ""),
        tactic_count=len(entry.get("tactics") or []),
        replayed_tactic_count=sum(
            1 for c in commands if c.get("kind") == "next"
        ),
        outcome=outcome,
        consistency_warnings=len(audit_report.warnings),
        event_counts=audit_report.event_counts,
        artifact_dir=str(proof_dir),
        session_dir=str(session_dir),
        runner="subprocess" if subprocess_mode else "inprocess",
        full_hooks=bool(full_hooks),
    )
    _write_json(proof_dir / "summary.json", summary.to_dict())
    _write_review(proof_dir / "review.md", summary, audit_report)
    if not keep_session:
        shutil.rmtree(session_dir, ignore_errors=True)
    return summary.to_dict()


def _normalize_tactic_for_session(text: Any) -> str:
    """Mirror the non-semantic tactic normalization in session_cli.

    The replay command records the proof-bank text, while `session_cli`
    records the text it actually submits to EasyCrypt. In particular zsh
    escaping may store `\!` for EasyCrypt's repeat operator `!`; comparing
    those byte-for-byte creates false consistency warnings.
    """
    tactic = str(text or "").strip().replace("\\!", "!")
    if tactic and not tactic.endswith("."):
        tactic += "."
    return tactic.rstrip()


def _build_consistency_report(
    commands: list[dict[str, Any]],
    events: list[dict[str, Any]],
    outcome: str,
    session_dir: Path,
) -> dict[str, Any]:
    summary = summarize_events(events)
    event_contract = validate_event_stream(events, expected_outcome=outcome)
    proof_state: dict[str, Any] = {}
    try:
        projection = read_proof_state_projection(session_dir)
        proof_state = projection_to_goal_info(projection)
    except Exception as exc:
        proof_state = {"error": str(exc)}

    next_commands = [c for c in commands if c.get("kind") == "next"]
    audit_commands = [c for c in commands if c.get("kind") == "audit_tool"]
    tactic_submitted = events_of_type(events, "tactic.submitted")
    tactic_result = events_of_type(events, "tactic.result")
    candidate_events = candidate_closed_events(events)

    warnings: list[str] = []
    if summary.tactic_submitted_count != len(next_commands):
        warnings.append(
            "tactic.submitted count does not match replayed -next commands: "
            f"{summary.tactic_submitted_count} vs {len(next_commands)}"
        )
    if summary.tactic_result_count != summary.tactic_submitted_count:
        warnings.append(
            "tactic.result count does not match tactic.submitted count: "
            f"{summary.tactic_result_count} vs "
            f"{summary.tactic_submitted_count}"
        )

    for idx, (cmd, event) in enumerate(zip(next_commands, tactic_submitted), start=1):
        cmd_tactic = _normalize_tactic_for_session(cmd.get("tactic", ""))
        event_tactic = _normalize_tactic_for_session(
            event_payload(event).get("tactic", "")
        )
        if cmd_tactic != event_tactic:
            warnings.append(
                f"step {idx}: submitted tactic mismatch between command "
                "and event"
            )
            break

    closed_text_steps = []
    for cmd in next_commands:
        text = f"{cmd.get('stdout', '')}\n{cmd.get('stderr', '')}"
        if "No more goals" in text or "[ALL_GOALS_CLOSED]" in text:
            closed_text_steps.append(cmd.get("step"))
    if closed_text_steps and not candidate_events:
        warnings.append(
            "stdout shows proof closure but no proof.candidate_closed event"
        )

    if (
        summary.result_candidate_closed_count
        and summary.result_candidate_closed_count != summary.candidate_closed_count
    ):
        warnings.append(
            "candidate_closed tactic.result count differs from "
            "proof.candidate_closed event count"
        )

    failed_next = [
        {"step": c.get("step"), "rc": c.get("rc"), "tactic": c.get("tactic")}
        for c in next_commands if c.get("rc") != 0
    ]
    if failed_next:
        warnings.append(f"{len(failed_next)} replayed tactic command(s) failed")

    verification_status = summary.verification_status
    if outcome == "PASS" and verification_status != "pass":
        warnings.append(
            "replay outcome PASS but latest verification.completed is not pass"
        )
    if outcome != "PASS" and verification_status == "pass":
        warnings.append(
            "latest verification.completed pass but replay outcome is not PASS"
        )
    if outcome == "PASS" and proof_state:
        if not proof_state.get("final_ready"):
            warnings.append(
                "replay outcome PASS but proof-state projection is not final_ready"
            )
    for issue in event_contract.issues:
        warnings.append(f"[EVENT-CONTRACT:{issue.severity.upper()}] {issue.format()}")
    tool_view_audit = _audit_tool_view_events(events)
    if not tool_view_audit["checked"]:
        tool_view_audit = _audit_tool_views(audit_commands)
    for error in tool_view_audit["errors"]:
        warnings.append(f"[TOOL-VIEW:ERROR] {error}")
    for warning in tool_view_audit["warnings"]:
        warnings.append(f"[TOOL-VIEW:WARNING] {warning}")
    agent_view_audit = _audit_agent_view_events(events)
    if not agent_view_audit["checked"]:
        agent_view_audit = _audit_agent_views(audit_commands)
    for error in agent_view_audit["errors"]:
        warnings.append(f"[AGENT-VIEW:ERROR] {error}")
    for warning in agent_view_audit["warnings"]:
        warnings.append(f"[AGENT-VIEW:WARNING] {warning}")
    commit_response_audit = _audit_commit_response_events(events)
    for error in commit_response_audit["errors"]:
        warnings.append(f"[COMMIT-RESPONSE:ERROR] {error}")
    for warning in commit_response_audit["warnings"]:
        warnings.append(f"[COMMIT-RESPONSE:WARNING] {warning}")
    command_summary_audit = _audit_command_summary_events(events)
    for error in command_summary_audit["errors"]:
        warnings.append(f"[COMMAND-SUMMARY:ERROR] {error}")
    for warning in command_summary_audit["warnings"]:
        warnings.append(f"[COMMAND-SUMMARY:WARNING] {warning}")
    episode_timeline_audit = _audit_episode_timeline_events(events)
    if not episode_timeline_audit["checked"]:
        episode_timeline_audit = _audit_episode_timelines(audit_commands)
    for error in episode_timeline_audit["errors"]:
        warnings.append(f"[EPISODE-TIMELINE:ERROR] {error}")
    for warning in episode_timeline_audit["warnings"]:
        warnings.append(f"[EPISODE-TIMELINE:WARNING] {warning}")
    diagnostic_audit = _audit_structured_diagnostics(events)
    for error in diagnostic_audit["errors"]:
        warnings.append(f"[DIAGNOSTIC:ERROR] {error}")
    for warning in diagnostic_audit["warnings"]:
        warnings.append(f"[DIAGNOSTIC:WARNING] {warning}")

    return {
        "warnings": warnings,
        "event_contract": event_contract.to_dict(),
        "proof_state": proof_state,
        "event_contract_errors": event_contract.error_count,
        "event_contract_warnings": event_contract.warning_count,
        "tool_view_checked": tool_view_audit["checked"],
        "tool_view_errors": len(tool_view_audit["errors"]),
        "tool_view_warnings": len(tool_view_audit["warnings"]),
        "agent_view_checked": agent_view_audit["checked"],
        "agent_view_errors": len(agent_view_audit["errors"]),
        "agent_view_warnings": len(agent_view_audit["warnings"]),
        "commit_response_checked": commit_response_audit["checked"],
        "commit_response_errors": len(commit_response_audit["errors"]),
        "commit_response_warnings": len(commit_response_audit["warnings"]),
        "command_summary_checked": command_summary_audit["checked"],
        "command_summary_errors": len(command_summary_audit["errors"]),
        "command_summary_warnings": len(command_summary_audit["warnings"]),
        "episode_timeline_checked": episode_timeline_audit["checked"],
        "episode_timeline_errors": len(episode_timeline_audit["errors"]),
        "episode_timeline_warnings": len(episode_timeline_audit["warnings"]),
        "structured_diagnostic_checked": diagnostic_audit["checked"],
        "structured_diagnostic_errors": len(diagnostic_audit["errors"]),
        "structured_diagnostic_warnings": len(diagnostic_audit["warnings"]),
        "event_counts": summary.event_counts,
        "command_counts": {
            "next": len(next_commands),
            "audit_tool": len(audit_commands),
            "total": len(commands),
        },
        "tactic_status_counts": summary.tactic_status_counts,
        "closed_text_steps": closed_text_steps,
        "candidate_closed_events": summary.candidate_closed_count,
        "verification_status": verification_status,
        "failed_next": failed_next,
    }


def _audit_tool_views(audit_commands: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for cmd in audit_commands:
        if cmd.get("tool") != "goal-info":
            continue
        step = cmd.get("step")
        data = _extract_first_json_object(str(cmd.get("stdout") or ""))
        if not isinstance(data, dict):
            errors.append(f"step {step}: goal-info emitted no JSON object")
            continue
        view = data.get("tool_view")
        if not isinstance(view, dict):
            errors.append(f"step {step}: goal-info JSON has no tool_view object")
            continue
        checked += 1
        validation = validate_tool_view(view)
        for err in validation.errors:
            errors.append(f"step {step}: {err}")
        for warn in validation.warnings:
            warnings.append(f"step {step}: {warn}")
        proof_state = view.get("proof_state") or {}
        guidance = view.get("guidance") or {}
        recs = guidance.get("recommendations") or []
        if (
            isinstance(proof_state, dict)
            and proof_state.get("status") in ("candidate_closed", "verified")
            and recs
        ):
            errors.append(
                f"step {step}: closed proof_state has "
                f"{len(recs)} guidance recommendation(s)"
            )
    return {"checked": checked, "errors": errors, "warnings": warnings}



def _load_artifact_object(
    artifact: Path,
    label: str,
    errors: list[str],
) -> tuple[dict[str, Any], str] | None:
    """Shared artifact-audit preamble: load JSON, require an object root, and
    return (data, canonical sha1). Missing/unreadable/non-object artifacts
    append one error under ``label`` and return None."""
    if not artifact.exists():
        errors.append(f"{label}: artifact missing: {artifact}")
        return None
    try:
        data = json.loads(artifact.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label}: artifact JSON unreadable: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{label}: artifact root is not an object")
        return None
    canonical = json.dumps(data, indent=2, sort_keys=True)
    return data, hashlib.sha1(canonical.encode("utf-8")).hexdigest()

def _audit_tool_view_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for event in events_of_type(events, "tool.view.produced"):
        payload = event_payload(event)
        tool = str(payload.get("tool") or "")
        artifact = Path(str(payload.get("artifact") or ""))
        label = f"{tool or 'unknown'}:{artifact.name or 'no-artifact'}"
        loaded = _load_artifact_object(artifact, label, errors)
        if loaded is None:
            continue
        data, digest = loaded
        checked += 1
        if payload.get("view_hash") != digest:
            errors.append(f"{label}: view_hash does not match artifact")
        validation = validate_tool_view(data)
        for err in validation.errors:
            errors.append(f"{label}: {err}")
        for warn in validation.warnings:
            warnings.append(f"{label}: {warn}")
        if data.get("tool") != tool:
            errors.append(
                f"{label}: event tool {tool!r} differs from artifact "
                f"tool {data.get('tool')!r}"
            )
        if data.get("schema_version") != payload.get("schema_version"):
            errors.append(f"{label}: schema_version mismatch")
        proof_state = data.get("proof_state") or {}
        guidance = data.get("guidance") or {}
        recs = guidance.get("recommendations") or []
        if (
            isinstance(proof_state, dict)
            and proof_state.get("status") in ("candidate_closed", "verified")
            and recs
        ):
            errors.append(
                f"{label}: closed proof_state has "
                f"{len(recs)} guidance recommendation(s)"
            )
        if isinstance(recs, list) and payload.get("recommendation_count") != len(recs):
            errors.append(f"{label}: recommendation_count mismatch")
        if bool(payload.get("ok")) != bool(data.get("ok")):
            errors.append(f"{label}: ok flag mismatch")
    return {"checked": checked, "errors": errors, "warnings": warnings}


_PROVER_WORKSPACE_FORBIDDEN_KEYS = {
    "command",
    "debug_cli_fallback",
    "next_actions",
    "next_try",
    "suggested_next_steps",
    "suggestions",
}
_PROVER_WORKSPACE_FORBIDDEN_TEXT = (
    "session_cli.py",
    "Lookup first",
    "after Pr handles are exhausted",
)


def _iter_json_keys(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _iter_json_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_json_keys(item)


def _validate_prover_workspace_view(
    data: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("kind") != "prover_workspace_view":
        errors.append(f"{label}: JSON is not a ProverWorkspaceView")
        return {"errors": errors, "warnings": warnings}

    missing = [
        key for key in (
            "last_result",
            "proof_status",
            "current_goal",
            "program_frontier",
            "application_context",
            "facts_and_diagnostics",
            "candidate_moves",
            "inspect_lookup_handles",
        )
        if not isinstance(data.get(key), dict)
    ]
    if missing:
        errors.append(
            f"{label}: ProverWorkspaceView missing {', '.join(missing)}"
        )

    keys = set(_iter_json_keys(data))
    forbidden = sorted(keys & _PROVER_WORKSPACE_FORBIDDEN_KEYS)
    if forbidden:
        errors.append(
            f"{label}: ProverWorkspaceView exposes forbidden key(s): "
            f"{', '.join(forbidden)}"
        )

    rendered = json.dumps(data, sort_keys=True)
    leaked = [text for text in _PROVER_WORKSPACE_FORBIDDEN_TEXT if text in rendered]
    if leaked:
        errors.append(
            f"{label}: ProverWorkspaceView exposes backend/imperative text: "
            f"{', '.join(leaked)}"
        )

    return {"errors": errors, "warnings": warnings}


def _audit_agent_views(commands: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for cmd in commands:
        if cmd.get("tool") != "agent-view":
            continue
        step = cmd.get("step")
        data = _extract_first_json_object(str(cmd.get("stdout") or ""))
        if not isinstance(data, dict):
            errors.append(f"step {step}: agent-view emitted no JSON object")
            continue
        kind = data.get("kind")
        if kind == "prover_workspace_view":
            checked += 1
            validation = _validate_prover_workspace_view(data, f"step {step}")
            errors.extend(validation["errors"])
            warnings.extend(validation["warnings"])
            continue
        if kind not in {"proof_context_view", "agent_proof_view"}:
            errors.append(
                f"step {step}: JSON is not a ProverWorkspaceView or "
                "ProofContextView"
            )
            continue
        checked += 1
        validation = validate_proof_context_view(data)
        for err in validation.errors:
            errors.append(f"step {step}: {err}")
        for warn in validation.warnings:
            warnings.append(f"step {step}: {warn}")
    return {"checked": checked, "errors": errors, "warnings": warnings}


def _audit_agent_view_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    workspace_events = list(events_of_type(events, "prover.workspace_view.produced"))
    agent_events = list(events_of_type(events, "agent.view.produced"))
    for event in workspace_events + agent_events:
        event_type = str(event.get("type") or "")
        payload = event_payload(event)
        artifact = Path(str(payload.get("artifact") or ""))
        label_prefix = (
            "prover-workspace-view"
            if event_type == "prover.workspace_view.produced"
            else "agent-view"
        )
        label = f"{label_prefix}:{artifact.name or 'no-artifact'}"
        loaded = _load_artifact_object(artifact, label, errors)
        if loaded is None:
            continue
        data, digest = loaded
        checked += 1
        if payload.get("view_hash") != digest:
            errors.append(f"{label}: view_hash does not match artifact")
        if event_type == "prover.workspace_view.produced":
            validation = _validate_prover_workspace_view(data, label)
            errors.extend(validation["errors"])
            warnings.extend(validation["warnings"])
            if data.get("schema_version") != payload.get("schema_version"):
                errors.append(f"{label}: schema_version mismatch")
            if data.get("kind") != payload.get("view_kind"):
                errors.append(f"{label}: view_kind mismatch")
            proof_position = data.get("proof_status") or data.get("proof_position") or {}
            if (
                isinstance(proof_position, dict)
                and payload.get("proof_status") != proof_position.get("status")
            ):
                errors.append(f"{label}: proof_status mismatch")
            if bool(payload.get("ok")) != bool(data.get("ok")):
                errors.append(f"{label}: ok flag mismatch")
            continue
        validation = validate_proof_context_view(data)
        for err in validation.errors:
            errors.append(f"{label}: {err}")
        for warn in validation.warnings:
            warnings.append(f"{label}: {warn}")
        if data.get("schema_version") != payload.get("schema_version"):
            errors.append(f"{label}: schema_version mismatch")
        proof_state = data.get("proof_state") or {}
        goal = proof_state.get("goal") if isinstance(proof_state, dict) else {}
        guidance = data.get("guidance") or {}
        recs = guidance.get("recommendations") if isinstance(guidance, dict) else []
        stale = (
            guidance.get("stale_recommendations")
            if isinstance(guidance, dict) else []
        )
        if payload.get("proof_status") != proof_state.get("status"):
            errors.append(f"{label}: proof_status mismatch")
        if payload.get("goal_hash") != goal.get("active_goal_hash"):
            errors.append(f"{label}: goal_hash mismatch")
        if isinstance(recs, list) and payload.get("recommendation_count") != len(recs):
            errors.append(f"{label}: recommendation_count mismatch")
        if (
            isinstance(stale, list)
            and payload.get("stale_recommendation_count") != len(stale)
        ):
            errors.append(f"{label}: stale_recommendation_count mismatch")
        if bool(payload.get("ok")) != bool(data.get("ok")):
            errors.append(f"{label}: ok flag mismatch")
    return {"checked": checked, "errors": errors, "warnings": warnings}


def _audit_episode_timelines(commands: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for cmd in commands:
        if cmd.get("tool") != "episode-view":
            continue
        step = cmd.get("step")
        data = _extract_first_json_object(str(cmd.get("stdout") or ""))
        if not isinstance(data, dict):
            errors.append(f"step {step}: episode-view emitted no JSON object")
            continue
        if data.get("kind") != "session_episode_timeline":
            errors.append(f"step {step}: JSON is not a SessionEpisodeTimeline")
            continue
        checked += 1
        validation = validate_session_episode_timeline(data)
        for err in validation.errors:
            errors.append(f"step {step}: {err}")
        for warn in validation.warnings:
            warnings.append(f"step {step}: {warn}")
    return {"checked": checked, "errors": errors, "warnings": warnings}


def _audit_episode_timeline_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for event in events_of_type(events, "episode.timeline.produced"):
        payload = event_payload(event)
        artifact = Path(str(payload.get("artifact") or ""))
        label = f"episode-timeline:{artifact.name or 'no-artifact'}"
        loaded = _load_artifact_object(artifact, label, errors)
        if loaded is None:
            continue
        data, digest = loaded
        checked += 1
        if payload.get("timeline_hash") != digest:
            errors.append(f"{label}: timeline_hash does not match artifact")
        validation = validate_session_episode_timeline(data)
        for err in validation.errors:
            errors.append(f"{label}: {err}")
        for warn in validation.warnings:
            warnings.append(f"{label}: {warn}")
        if data.get("schema_version") != payload.get("schema_version"):
            errors.append(f"{label}: schema_version mismatch")
        if data.get("step_count") != payload.get("step_count"):
            errors.append(f"{label}: step_count mismatch")
        rollup = data.get("rollup") if isinstance(data.get("rollup"), dict) else {}
        if payload.get("final_proof_status") != rollup.get("final_proof_status"):
            errors.append(f"{label}: final_proof_status mismatch")
        if payload.get("final_primary_action") != rollup.get("final_primary_action"):
            errors.append(f"{label}: final_primary_action mismatch")
        notes = data.get("notes") if isinstance(data.get("notes"), list) else []
        errors_list = data.get("errors") if isinstance(data.get("errors"), list) else []
        if payload.get("note_count") != len(notes):
            errors.append(f"{label}: note_count mismatch")
        if payload.get("error_count") != len(errors_list):
            errors.append(f"{label}: error_count mismatch")
        if bool(payload.get("ok")) != bool(data.get("ok")):
            errors.append(f"{label}: ok flag mismatch")
    return {"checked": checked, "errors": errors, "warnings": warnings}


def _audit_commit_response_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for event in events_of_type(events, "commit.response.produced"):
        payload = event_payload(event)
        command = str(payload.get("command") or "")
        artifact = Path(str(payload.get("artifact") or ""))
        label = f"commit-response:{command or 'unknown'}:{artifact.name or 'no-artifact'}"
        loaded = _load_artifact_object(artifact, label, errors)
        if loaded is None:
            continue
        data, digest = loaded
        checked += 1
        if payload.get("response_hash") != digest:
            errors.append(f"{label}: response_hash does not match artifact")
        validation = validate_commit_response(data)
        for err in validation.errors:
            errors.append(f"{label}: {err}")
        for warn in validation.warnings:
            warnings.append(f"{label}: {warn}")
        if data.get("schema_version") != payload.get("schema_version"):
            errors.append(f"{label}: schema_version mismatch")
        if data.get("command") != command:
            errors.append(f"{label}: command mismatch")
        if data.get("status") != payload.get("status"):
            errors.append(f"{label}: status mismatch")
        proof_state = data.get("proof_state") or {}
        mutation = data.get("mutation") or {}
        if payload.get("proof_status") != proof_state.get("status"):
            errors.append(f"{label}: proof_status mismatch")
        if payload.get("attempted_count") != mutation.get("attempted_count"):
            errors.append(f"{label}: attempted_count mismatch")
        if payload.get("accepted_count") != mutation.get("accepted_count"):
            errors.append(f"{label}: accepted_count mismatch")
        if payload.get("failed_tactic") != mutation.get("failed_tactic"):
            errors.append(f"{label}: failed_tactic mismatch")
        if bool(payload.get("ok")) != bool(data.get("ok")):
            errors.append(f"{label}: ok flag mismatch")
    return {"checked": checked, "errors": errors, "warnings": warnings}


def _audit_command_summary_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for event in events_of_type(events, "command.summary.produced"):
        payload = event_payload(event)
        command = str(payload.get("command") or "")
        artifact = Path(str(payload.get("artifact") or ""))
        label = f"command-summary:{command or 'unknown'}:{artifact.name or 'no-artifact'}"
        loaded = _load_artifact_object(artifact, label, errors)
        if loaded is None:
            continue
        data, digest = loaded
        checked += 1
        if payload.get("summary_hash") != digest:
            errors.append(f"{label}: summary_hash does not match artifact")
        validation = validate_command_summary(data)
        for err in validation.errors:
            errors.append(f"{label}: {err}")
        for warn in validation.warnings:
            warnings.append(f"{label}: {warn}")
        if data.get("schema_version") != payload.get("schema_version"):
            errors.append(f"{label}: schema_version mismatch")
        if data.get("command") != command:
            errors.append(f"{label}: command mismatch")
        if data.get("command_status") != payload.get("command_status"):
            errors.append(f"{label}: command_status mismatch")
        proof = data.get("proof") or {}
        transition = data.get("transition") or {}
        workspace_metrics = command_summary_workspace_metrics(data)
        if payload.get("proof_status") != proof.get("status"):
            errors.append(f"{label}: proof_status mismatch")
        if payload.get("goal_hash") != proof.get("goal_hash"):
            errors.append(f"{label}: goal_hash mismatch")
        _check_optional_payload_field(
            payload, proof, "goal_type", label, errors, warnings,
        )
        _check_optional_payload_field(
            payload, proof, "num_remaining", label, errors, warnings,
        )
        _check_optional_payload_field(
            payload, proof, "history_tactic_count", label, errors, warnings,
        )
        _check_optional_payload_field(
            payload, transition, "transition_kind", label, errors, warnings,
            source_key="kind",
        )
        _check_optional_payload_field(
            payload, workspace_metrics, "primary_action", label, errors, warnings,
        )
        expected_recommendations = workspace_metrics.get("recommendation_count")
        if not isinstance(expected_recommendations, int):
            expected_recommendations = 0
        if payload.get("recommendation_count") != expected_recommendations:
            errors.append(f"{label}: recommendation_count mismatch")
        if bool(payload.get("ok")) != bool(data.get("ok")):
            errors.append(f"{label}: ok flag mismatch")
    return {"checked": checked, "errors": errors, "warnings": warnings}


def _check_optional_payload_field(
    payload: dict[str, Any],
    source: dict[str, Any],
    payload_key: str,
    label: str,
    errors: list[str],
    warnings: list[str],
    *,
    source_key: str | None = None,
) -> None:
    if payload_key not in payload:
        warnings.append(f"{label}: missing optional timeline field {payload_key}")
        return
    expected = source.get(source_key or payload_key)
    if payload.get(payload_key) != expected:
        errors.append(f"{label}: {payload_key} mismatch")


def _audit_structured_diagnostics(events: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for idx, event in enumerate(events_of_type(events, "diagnostic.emitted")):
        payload = event_payload(event)
        has_structured = any(
            key in payload
            for key in (
                "kind", "recommendations", "evidence",
                "notes", "errors", "debug",
            )
        )
        if not has_structured:
            continue
        checked += 1
        label = f"diagnostic[{idx}]/{payload.get('source') or 'unknown'}"
        recs = payload.get("recommendations", [])
        if not isinstance(recs, list):
            errors.append(f"{label}: recommendations must be a list")
        else:
            for ridx, rec in enumerate(recs):
                _audit_recommendation(
                    rec, f"{label}.recommendations[{ridx}]",
                    errors, warnings,
                )
        evidence = payload.get("evidence", {})
        if not isinstance(evidence, dict):
            errors.append(f"{label}: evidence must be an object")
        else:
            for bucket, items in evidence.items():
                if not isinstance(bucket, str) or not bucket:
                    errors.append(f"{label}: evidence bucket must be non-empty")
                if not isinstance(items, list):
                    errors.append(f"{label}: evidence.{bucket} must be a list")
                    continue
                for eidx, item in enumerate(items):
                    if not isinstance(item, dict):
                        errors.append(
                            f"{label}: evidence.{bucket}[{eidx}] "
                            "must be an object"
                        )
                    elif not item.get("id"):
                        warnings.append(
                            f"{label}: evidence.{bucket}[{eidx}] "
                            "has no id"
                        )
        for field in ("notes", "errors"):
            items = payload.get(field, [])
            if not isinstance(items, list):
                errors.append(f"{label}: {field} must be a list")
                continue
            for midx, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(
                        f"{label}: {field}[{midx}] must be an object"
                    )
    return {"checked": checked, "errors": errors, "warnings": warnings}


def _audit_recommendation(
    rec: Any,
    label: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(rec, dict):
        errors.append(f"{label}: recommendation must be an object")
        return
    for key in ("id", "kind", "producer", "action", "why", "confidence"):
        if key not in rec:
            errors.append(f"{label}: missing {key}")
        elif not isinstance(rec[key], str):
            errors.append(f"{label}: {key} must be a string")
        elif key in ("id", "kind", "producer", "action") and not rec[key].strip():
            errors.append(f"{label}: {key} must be non-empty")
    if rec.get("confidence") not in (
        None, "", "low", "medium", "high", "verified",
    ):
        warnings.append(
            f"{label}: unusual confidence {rec.get('confidence')!r}"
        )
    for key in ("preconditions", "source_refs", "evidence_refs"):
        if key in rec and not isinstance(rec[key], list):
            errors.append(f"{label}: {key} must be a list")
    if "metadata" in rec and not isinstance(rec["metadata"], dict):
        errors.append(f"{label}: metadata must be an object")


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    starts = [
        text.find("{", match.start())
        for match in re.finditer(r"(?m)^\s*\{", text)
    ]
    starts = [idx for idx in starts if idx >= 0]
    if not starts:
        return None
    for start in starts:
        parsed = _extract_json_object_at(text, start)
        if parsed is not None:
            return parsed
    return None


def _extract_json_object_at(text: str, start: int) -> dict[str, Any] | None:
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:idx + 1])
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def _write_review(path: Path, summary: ReplaySummary, report: AuditReport) -> None:
    warnings = report.warnings
    lines = [
        f"# Replay Review: {summary.lemma}",
        "",
        f"- file: `{summary.file}`",
        f"- outcome: `{summary.outcome}`",
        f"- tactics: {summary.replayed_tactic_count}",
        f"- verification: `{report.verification_status}`",
        f"- candidate_closed events: {report.candidate_closed_events}",
        f"- proof-state status: `{report.proof_state.get('status', '')}`",
        f"- proof-state final_ready: {bool(report.proof_state.get('final_ready'))}",
        f"- audit tool calls: {report.audit_tool_calls}",
        f"- event contract errors: {report.event_contract_errors}",
        f"- event contract warnings: {report.event_contract_warnings}",
        f"- tool-view checked: {report.tool_view_checked}",
        f"- tool-view errors: {report.tool_view_errors}",
        f"- tool-view warnings: {report.tool_view_warnings}",
        f"- agent-view checked: {report.agent_view_checked}",
        f"- agent-view errors: {report.agent_view_errors}",
        f"- agent-view warnings: {report.agent_view_warnings}",
        f"- commit-response checked: {report.commit_response_checked}",
        f"- commit-response errors: {report.commit_response_errors}",
        f"- commit-response warnings: {report.commit_response_warnings}",
        f"- command-summary checked: {report.command_summary_checked}",
        f"- command-summary errors: {report.command_summary_errors}",
        f"- command-summary warnings: {report.command_summary_warnings}",
        f"- episode-timeline checked: {report.episode_timeline_checked}",
        f"- episode-timeline errors: {report.episode_timeline_errors}",
        f"- episode-timeline warnings: {report.episode_timeline_warnings}",
        (
            "- structured diagnostics checked: "
            f"{report.structured_diagnostic_checked}"
        ),
        (
            "- structured diagnostics errors: "
            f"{report.structured_diagnostic_errors}"
        ),
        (
            "- structured diagnostics warnings: "
            f"{report.structured_diagnostic_warnings}"
        ),
        "",
        "## Consistency",
    ]
    if warnings:
        lines.extend(f"- WARNING: {w}" for w in warnings)
    else:
        lines.append("- OK: no consistency warnings")
    lines.extend([
        "",
        "## Event Counts",
    ])
    for typ, count in sorted(report.event_counts.items()):
        lines.append(f"- `{typ}`: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0,
                    help="Replay only the first N proof bank entries.")
    ap.add_argument("--lemma", help="Replay only this lemma name.")
    ap.add_argument("--skip-lemma", action="append", default=[],
                    help="Skip this lemma name; repeatable.")
    ap.add_argument("--max-tactics", type=int, default=0,
                    help="Replay only entries with <= N tactics; 0 = no cap.")
    ap.add_argument("--artifact-root", default=str(_DEFAULT_ARTIFACT_ROOT))
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--audit-tools", default="status",
                    help=("Comma-separated read-only tools to run after each "
                          "step, e.g. status,goal-info,diagnose."))
    ap.add_argument("--audit-every", type=int, default=1,
                    help=("Run audit tools every N steps, plus first/last/"
                          "error/closed steps. Use 0 for checkpoints only."))
    ap.add_argument("--keep-session", action="store_true",
                    help="Keep /tmp proof-replay-* session directories.")
    ap.add_argument("--subprocess", action="store_true",
                    help=("Use the legacy runner that invokes session_cli.py "
                          "as a new Python subprocess for every action. "
                          "Default is the faster in-process runner."))
    ap.add_argument("--full-hooks", action="store_true",
                    help=("In in-process mode, run all interactive "
                          "commit-time hook probes. By default replay uses "
                          "the faster chain-style mode that skips expensive "
                          "guidance-only hook probes while preserving real "
                          "tactic execution and final verification."))
    ap.add_argument("--prover-ux-audit", action="store_true",
                    help=("After replay, run the prover-facing CommandSummary "
                          "UX audit and fail if it reports errors."))
    ap.add_argument("--prover-behavior-audit", action="store_true",
                    help=("After replay, run the structured prover behavior "
                          "audit for tool usage and next-action follow-through."))
    ap.add_argument("--write-prover-timeline", action="store_true",
                    help=("After replay, write prover_episode_timelines.json "
                          "for episode-level review."))
    args = ap.parse_args(argv)

    entries = _load_proof_bank()
    if args.lemma:
        entries = [e for e in entries if e.get("lemma") == args.lemma]
    if args.skip_lemma:
        skipped = set(args.skip_lemma)
        entries = [e for e in entries if e.get("lemma") not in skipped]
    if args.max_tactics and args.max_tactics > 0:
        entries = [
            e for e in entries
            if len(e.get("tactics") or []) <= args.max_tactics
        ]
    if args.limit and args.limit > 0:
        entries = entries[:args.limit]
    if not entries:
        print("proof_replay: no entries selected", file=sys.stderr)
        return 1

    audit_tools = [
        t.strip() for t in args.audit_tools.split(",") if t.strip()
    ]
    artifact_root = Path(args.artifact_root)
    summaries = []
    for entry in entries:
        print(
            f"RUN: {entry['file']}::{entry['lemma']} "
            f"({len(entry.get('tactics') or [])} tactics)",
            flush=True,
        )
        summary = replay_entry(
            entry,
            artifact_root=artifact_root,
            audit_tools=audit_tools,
            audit_every=args.audit_every,
            timeout=args.timeout,
            keep_session=args.keep_session,
            subprocess_mode=args.subprocess,
            full_hooks=args.full_hooks,
        )
        summaries.append(summary)
        print(
            f"{summary['outcome']}: {summary['file']}::{summary['lemma']} "
            f"({summary['tactic_count']} tactics) -> "
            f"{summary['artifact_dir']}",
            flush=True,
        )

    _write_json(artifact_root / "summary.json", summaries)
    if args.write_prover_timeline:
        from workflow.validation.prover_episode_timeline import (
            build_replay_root_timelines,
            write_report as write_timeline_report,
        )
        timeline_report = build_replay_root_timelines(artifact_root)
        write_timeline_report(artifact_root, timeline_report)
        print(
            "prover_episode_timeline: "
            f"{timeline_report['proof_count']} proofs, "
            f"{timeline_report['step_count']} steps"
        )
    prover_ux_ok = True
    if args.prover_ux_audit:
        from workflow.validation.prover_ux_audit import (
            audit_replay_root,
            write_report as write_ux_report,
        )
        ux_report = audit_replay_root(artifact_root)
        write_ux_report(artifact_root, ux_report)
        prover_ux_ok = bool(ux_report.get("ok"))
        print(
            "prover_ux_audit: "
            f"{ux_report['proofs_checked']} proofs, "
            f"{ux_report['command_summaries_checked']} summaries, "
            f"{ux_report['error_count']} errors, "
            f"{ux_report['warning_count']} warnings"
        )
    prover_behavior_ok = True
    if args.prover_behavior_audit:
        from workflow.validation.prover_behavior_audit import (
            audit_path as audit_behavior_path,
            write_report as write_behavior_report,
        )
        behavior_report = audit_behavior_path(artifact_root)
        write_behavior_report(artifact_root, behavior_report)
        prover_behavior_ok = bool(behavior_report.get("ok"))
        print(
            "prover_behavior_audit: "
            f"{behavior_report['proofs_checked']} proofs, "
            f"{behavior_report['command_summaries_checked']} summaries, "
            f"{behavior_report['tool_usage']['total_calls']} tool calls, "
            f"{behavior_report['error_count']} errors, "
            f"{behavior_report['warning_count']} warnings"
        )
    failed = [s for s in summaries if s["outcome"] != "PASS"]
    if failed:
        print(f"proof_replay: {len(failed)}/{len(summaries)} failed")
        return 1
    if not prover_ux_ok:
        print("proof_replay: prover UX audit failed")
        return 1
    if not prover_behavior_ok:
        print("proof_replay: prover behavior audit failed")
        return 1
    print(f"proof_replay: {len(summaries)}/{len(summaries)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
