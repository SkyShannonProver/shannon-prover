"""CLI handlers for commit-pipeline commands: -next, -prev, -try,
-bridge-probe, -chain, -write-back.

These all interact with the session's tactic-history (history.ec /
steps.log) and the daemon. Each handler mirrors the inline block it
replaced in `session_cli.main()` — the move is mechanical, no
behavior change. main() now dispatches via 2-line one-liners.

Why split this out (Phase 4 cleanup, 2026-04-30): main() had grown
to 53 inline `if args.X:` branches totaling ~1600 body lines; chain
alone was ~300. Putting these in their own module shrinks main()
toward pure dispatch and groups handlers by purpose for navigability.
"""
from __future__ import annotations

import json
import json as _json
import os
import re
import sys
from datetime import datetime as _dt
from pathlib import Path

from core.easycrypt.session_no_progress import detect_no_progress


# ─── -next ───────────────────────────────────────────────────────────────

def handle_tactic_exec(session, args) -> int:
    """Canonical Proof Interaction Manager wrapper.

    Existing flags remain compatibility shims; this entry point names the
    manager-level execution mode directly.
    """
    mode = str(getattr(args, "tactic_exec", "") or "")
    if mode == "probe":
        return handle_try(session, args)
    if mode == "commit":
        return handle_next(session, args)
    if mode == "commit_chain":
        return handle_chain(session, args)
    if mode == "undo":
        return handle_prev(session, args)
    sys.stderr.write(
        "Unknown -tactic-exec mode. Use probe, commit, commit_chain, or undo.\n",
    )
    return 2


def handle_next(session, args) -> int:
    """Apply ONE tactic block to the session. Read from --from-file,
    -c, or stdin in that priority. Calls Session.append_block which
    runs the full hook pipeline (registry + Phases + mutations)."""
    if args.from_file is not None:
        data = open(args.from_file).read()
    elif args.command is not None:
        data = args.command
    else:
        data = sys.stdin.read()
    if not data.strip():
        sys.stderr.write("No input provided on stdin for -next.\n")
        return 2
    delta = session.append_block(data, deltas_only=args.deltas_only)
    transition = _latest_transition_info(session, "next")
    status = str(transition.get("status") or "ok")
    command_ok = (
        status == "ok"
        and transition.get("history_committed") is not False
    )
    failed_tactic = "" if command_ok else data.strip()
    failure_reason = ""
    if not command_ok:
        failure_reason = (
            str(transition.get("latest_error") or "").strip()
            or str(transition.get("no_progress_reason") or "").strip()
            or "tactic had no effect or was not committed"
        )
    _write_legacy_output(delta)
    _finalize_tactic_execution(
        session,
        command="next",
        execution_mode="commit",
        status=status,
        attempted_tactics=[data.strip()],
        accepted_count=1 if command_ok else 0,
        failed_tactic=failed_tactic,
        failure_reason=failure_reason,
        raw_output=delta,
        ok=command_ok,
        emit_artifact_stdout=False,
    )
    return 0


# ─── -prev ───────────────────────────────────────────────────────────────

def handle_prev(session, args) -> int:
    """Pop the most recent committed tactic from history."""
    legacy = session.step_up()
    _write_legacy_output(legacy)
    _finalize_tactic_execution(
        session,
        command="prev",
        execution_mode="undo",
        status="undone",
        attempted_tactics=[],
        accepted_count=0,
        raw_output=legacy,
        ok=True,
        emit_artifact_stdout=False,
    )
    return 0


# ─── -try ────────────────────────────────────────────────────────────────

def handle_try(session, args) -> int:
    """Speculative tactic application — applies via daemon ephemerally,
    reports accepted/error/no-progress, does not commit."""
    if args.from_file is not None:
        tactic = open(args.from_file).read()
    elif args.command is not None:
        tactic = args.command
    else:
        tactic = sys.stdin.read()
    if not tactic.strip():
        sys.stderr.write(
            "No tactic provided for -try (use -c or stdin).\n",
        )
        return 2
    report = session.try_speculative(tactic)
    result = _parse_try_report(report, tactic)
    accepted = result.get("accepted")
    session.emit_event("tactic.try_result", {
        "name": "try",
        "kind": "speculative_tactic",
        "accepted": accepted,
        "mutates_proof_state": False,
        "tactic": str(result.get("tactic") or tactic).strip(),
        "status": "error" if report.startswith("[TRY] error") else "ok",
        "goal_after_closed": result.get("goal_after_closed"),
        "goal_after_remaining": result.get("goal_after_remaining"),
        "error_kind": result.get("error_kind"),
        "no_progress_predicted": result.get("no_progress_predicted"),
        "report": report,
    })
    view = _build_try_tool_view(session, result, report)
    if view is None:
        sys.stdout.write(report)
        return 0
    _write_legacy_output(report)
    _record_try_outcome(
        session,
        tactic=str(result.get("tactic") or tactic).strip(),
        accepted=result.get("accepted"),
        is_chain=bool(result.get("is_chain")),
        no_progress=bool(result.get("no_progress_predicted")),
        tool_error=bool(result.get("tool_error")),
        raw_output=report,
    )
    return 0


def _record_try_outcome(
    session,
    *,
    tactic: str,
    accepted: bool | None,
    is_chain: bool = False,
    no_progress: bool = False,
    tool_error: bool = False,
    raw_output: str = "",
) -> None:
    """Finalize a speculative probe as a TacticExecutionResult.

    Probes don't mutate proof state, but their ToolView carries the
    just-verified runnable rec (daemon_probe_accepted). Re-emitting an
    ProofContextView here puts that rec inside the freshness window at the
    pre-commit goal — without this, the rec is only visible to a
    post-commit result on a *different* goal hash, where freshness classifies
    it as stale_goal_hash. The TacticExecutionResult emitted here is the one
    whose `workspace.view.suggested_next_steps.primary` can carry the verified commit
    candidate before the proof state moves to a different goal hash.
    """
    if tool_error:
        status = "probe_error"
    elif accepted is True and not no_progress:
        status = "probe_accepted"
    elif accepted is True and no_progress:
        status = "probe_no_progress"
    elif accepted is False:
        status = "probe_rejected"
    else:
        status = "probe_unknown"
    command = "try-chain" if is_chain else "try"
    try:
        _finalize_tactic_execution(
            session,
            command=command,
            live_tool_name="try",
            execution_mode="probe",
            status=status,
            attempted_tactics=[tactic] if tactic else [],
            accepted_count=0,
            raw_output=raw_output,
            ok=(accepted is True) and not tool_error,
            emit_artifact_stdout=False,
            emit_execution_stdout=True,
        )
    except Exception:
        pass


def _parse_try_report(report: str, tactic: str) -> dict:
    tactic_text = tactic.strip()
    m_tac = re.search(r"^\[TRY\] tactic:\s*(.+?)\s*$", report, re.MULTILINE)
    if m_tac:
        tactic_text = m_tac.group(1).strip()

    accepted = None
    m = re.search(r"^\[TRY\] accepted:\s+(True|False)\s*$", report, re.MULTILINE)
    if m:
        accepted = (m.group(1) == "True")
    chain_m = re.search(
        r"^\[TRY-CHAIN\] all_accepted:\s+(True|False)\s*$",
        report, re.MULTILINE,
    )
    if chain_m:
        accepted = (chain_m.group(1) == "True")

    goal_after_closed = bool(re.search(
        r"^\[TRY\] goal_after:\s+all goals closed\.\s*$",
        report,
        re.MULTILINE,
    ))
    chain_closed = re.search(
        r"^\[TRY-CHAIN\] final_closed:\s+(True|False)\s*$",
        report,
        re.MULTILINE,
    )
    if chain_closed:
        goal_after_closed = (chain_closed.group(1) == "True")

    remaining = None
    m_remaining = re.search(
        r"^\[TRY\] goal_after:\s+(\d+) subgoal\(s\) remaining\s*$",
        report,
        re.MULTILINE,
    )
    if not m_remaining:
        m_remaining = re.search(
            r"^\[TRY-CHAIN\] goal_after:\s+(\d+) subgoal\(s\) remaining\s*$",
            report,
            re.MULTILINE,
        )
    if m_remaining:
        remaining = int(m_remaining.group(1))
    elif goal_after_closed:
        remaining = 0

    m_error = re.search(r"^\[TRY\] error_kind:\s*(.+?)\s*$", report, re.MULTILINE)
    tool_error = bool(re.search(r"^\[TRY\] error:", report, re.MULTILINE))
    no_progress = "PRODUCES NO PROGRESS" in report
    return {
        "tactic": tactic_text,
        "accepted": accepted,
        "goal_after_closed": goal_after_closed,
        "goal_after_remaining": remaining,
        "error_kind": m_error.group(1).strip() if m_error else "",
        "tool_error": tool_error,
        "no_progress_predicted": no_progress,
        "is_chain": bool(chain_m),
    }


def _build_try_tool_view(session, result: dict, report: str) -> dict | None:
    try:
        from core.easycrypt.session_projection import (  # type: ignore
            projection_to_goal_info,
            read_proof_state_projection,
        )
        from core.easycrypt.session_tool_view import (  # type: ignore
            Recommendation,
            record_tool_view,
            tool_view_from_projection,
        )
    except Exception:
        try:
            from core.easycrypt.session_projection import (  # type: ignore
                projection_to_goal_info,
                read_proof_state_projection,
            )
            from core.easycrypt.session_tool_view import (  # type: ignore
                Recommendation,
                record_tool_view,
                tool_view_from_projection,
            )
        except Exception:
            return None

    try:
        projection = read_proof_state_projection(session.dir, live_tool_name="try")
        proof_state = projection_to_goal_info(projection)
    except Exception:
        proof_state = {}

    recommendations = _try_recommendations(result, Recommendation)
    evidence = _try_evidence(result, proof_state)
    errors = []
    if result.get("tool_error"):
        errors.append({
            "code": "try.tool_error",
            "message": "Speculative probe could not run; inspect debug.legacy_report.",
            "severity": "error",
        })
    notes = [{
        "code": "try.state_unchanged",
        "message": "Speculative probe did not mutate the committed proof state.",
    }]
    view = tool_view_from_projection(
        tool="try",
        proof_state=proof_state,
        recommendations=recommendations,
        evidence=evidence,
        notes=notes,
        errors=errors,
        debug={
            "legacy_report": report,
            "parsed_result": dict(result),
        },
        ok=not errors,
    )
    try:
        record_tool_view(session, view)
    except Exception:
        pass
    return view


def _stdout_tool_view(view: dict) -> dict:
    """Return the prover-facing stdout form of a ToolView.

    Tool artifacts keep bulky compatibility/debug fields for postmortem
    inspection. Stdout is what the live prover reads after every command, so
    keep it structured and avoid reintroducing legacy transcript text there.
    """
    data = _json.loads(_json.dumps(view))
    debug = data.get("debug")
    parsed_result = {}
    if isinstance(debug, dict):
        parsed = debug.get("parsed_result")
        if isinstance(parsed, dict):
            parsed_result = dict(parsed)
        debug.pop("legacy_report", None)
    if data.get("tool") == "try":
        return _stdout_try_tool_view(data, parsed_result)
    return data


def _stdout_try_tool_view(data: dict, parsed_result: dict) -> dict:
    """Put the probe verdict before bulky proof-state fields.

    Claude previews only the first chunk of large outputs.  The first bytes of
    a `-try` stdout view must therefore answer the operational question:
    accepted/rejected, tactic, mutates state, and what to do next.  Full
    ToolView/proof-state data remains present later in the same object and in
    the persisted ToolView artifact.
    """
    accepted = parsed_result.get("accepted")
    no_progress = bool(parsed_result.get("no_progress_predicted"))
    tactic = str(parsed_result.get("tactic") or "")
    probe_result = {
        "accepted": accepted,
        "status": (
            "probe_accepted"
            if accepted is True and not no_progress else
            "probe_no_progress"
            if accepted is True and no_progress else
            "probe_rejected"
            if accepted is False else
            "probe_unknown"
        ),
        "tactic": tactic,
        "mutates_proof_state": False,
        "goal_after_closed": parsed_result.get("goal_after_closed"),
        "goal_after_remaining": parsed_result.get("goal_after_remaining"),
        "error_kind": str(parsed_result.get("error_kind") or ""),
    }
    out = {
        "schema_version": data.get("schema_version"),
        "tool": data.get("tool"),
        "ok": data.get("ok"),
        "probe_result": probe_result,
    }
    if accepted is True and not no_progress and tactic:
        out["next"] = {
            "primary_action": "commit_probe_result",
            "tool": "next",
            "tactic": tactic,
            "state_changed": True,
            "epistemic_status": "daemon_probe_accepted",
        }
    elif tactic:
        out["next"] = {
            "primary_action": "do_not_commit_probe_result",
            "tool": "",
            "tactic": tactic,
            "state_changed": False,
        }
    for key in (
        "guidance",
        "evidence",
        "notes",
        "errors",
        "proof_state",
        "debug",
    ):
        if key in data:
            out[key] = data[key]
    for key, value in data.items():
        if key not in out:
            out[key] = value
    return out


def _try_recommendations(result: dict, recommendation_cls) -> list:
    tactic = str(result.get("tactic") or "").strip()
    if not tactic:
        return []
    accepted = result.get("accepted")
    no_progress = bool(result.get("no_progress_predicted"))
    if accepted is True and not no_progress:
        closed = bool(result.get("goal_after_closed"))
        remaining = result.get("goal_after_remaining")
        why = "Daemon probe accepted this tactic without mutating proof state."
        if closed:
            why = (
                "Daemon probe accepted this tactic and it would close all "
                "goals; commit it to make the proof state advance."
            )
        elif isinstance(remaining, int):
            why = (
                "Daemon probe accepted this tactic and it would leave "
                f"{remaining} subgoal(s); commit it if that is the intended "
                "decomposition."
            )
        return [recommendation_cls(
            id="try.commit_accepted_tactic",
            kind="tactic_candidate",
            producer="try",
            action=tactic,
            action_type="runnable_tactic",
            why=why,
            confidence="verified",
            preconditions=[
                "proof_state.status == open",
                "current goal unchanged since the probe",
            ],
            evidence_refs=[
                "probe.try.result",
                "epistemic.try.daemon_probe_accepted",
            ],
            metadata={
                "epistemic_status": "daemon_probe_accepted",
                "state_changed": False,
                "probe_mutates_proof_state": False,
                "recommended_commit_tool": "next",
                "goal_after_closed": closed,
                "goal_after_remaining": remaining,
                "cost": "cheap",
            },
        )]

    if accepted is False or no_progress:
        status = (
            "daemon_probe_no_progress"
            if no_progress else "daemon_probe_rejected"
        )
        why = (
            "Daemon probe accepted this tactic but predicted no progress; "
            "committing would be auto-reverted."
            if no_progress else
            "Daemon probe rejected this tactic; do not commit it in the "
            "current proof state."
        )
        return [recommendation_cls(
            id="try.avoid_rejected_tactic",
            kind="avoid_tactic",
            producer="try",
            action=tactic,
            action_type="avoid_action",
            why=why,
            confidence="high",
            preconditions=["current goal unchanged since the probe"],
            evidence_refs=[
                "probe.try.result",
                f"epistemic.try.{status}",
            ],
            metadata={
                "epistemic_status": status,
                "state_changed": False,
                "probe_mutates_proof_state": False,
                "error_kind": str(result.get("error_kind") or ""),
                "cost": "free",
            },
        )]
    return []


def _try_evidence(result: dict, proof_state: dict) -> dict:
    goal = proof_state.get("goal") if isinstance(proof_state.get("goal"), dict) else {}
    accepted = result.get("accepted")
    if accepted is True and not result.get("no_progress_predicted"):
        status = "daemon_probe_accepted"
        meaning = "The EasyCrypt daemon accepted this tactic on the current state."
        not_meaning = "The tactic has not been committed to history.ec."
    elif result.get("no_progress_predicted"):
        status = "daemon_probe_no_progress"
        meaning = (
            "The daemon accepted the tactic, but session no-progress checks "
            "predict commit would auto-revert."
        )
        not_meaning = "This is not a useful commit candidate."
    elif accepted is False:
        status = "daemon_probe_rejected"
        meaning = "The EasyCrypt daemon rejected this tactic on the current state."
        not_meaning = "This does not rule out related tactics after edits."
    else:
        status = "daemon_probe_indeterminate"
        meaning = "The speculative probe did not produce a boolean verdict."
        not_meaning = "No proof-state mutation occurred."
    return {
        "probe": [{
            "id": "probe.try.result",
            "producer": "daemon.try_tactic",
            "accepted": accepted,
            "mutates_proof_state": False,
            "tactic": str(result.get("tactic") or ""),
            "goal_after_closed": result.get("goal_after_closed"),
            "goal_after_remaining": result.get("goal_after_remaining"),
            "error_kind": str(result.get("error_kind") or ""),
            "no_progress_predicted": bool(result.get("no_progress_predicted")),
            "active_goal_hash": str(goal.get("active_goal_hash") or ""),
        }],
        "epistemic": [{
            "id": f"epistemic.try.{status}",
            "status": status,
            "meaning": meaning,
            "not_meaning": not_meaning,
        }],
        "event": [{
            "id": "event.proof_state_projection",
            "producer": "session_projection",
            "status": str(proof_state.get("status") or ""),
            "event_contract": proof_state.get("event_contract"),
            "latest_transition": proof_state.get("latest_transition"),
        }],
    }


# ─── -bridge-probe ───────────────────────────────────────────────────────

def handle_bridge_probe(session, args) -> int:
    """Speculative `have -> : <stmt>.` probe to test whether a Pr-level
    bridge can close via sim/byequiv ladder."""
    if args.from_file is not None:
        stmt = open(args.from_file).read()
    elif args.command is not None:
        stmt = args.command
    else:
        stmt = sys.stdin.read()
    if not stmt.strip():
        sys.stderr.write(
            "No bridge statement provided for -bridge-probe "
            "(use -c 'Pr[A] = Pr[B]' or stdin).\n",
        )
        return 2
    report = session.bridge_probe(stmt)
    _record_bridge_probe_tool_view(session, stmt, report)
    sys.stdout.write(report)
    return 0


def _record_bridge_probe_tool_view(session, stmt: str, report: str) -> None:
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_goal_info,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tool_view import record_tool_view, tool_view_from_projection  # type: ignore
    try:
        projection = read_proof_state_projection(
            session.dir,
            live_tool_name="bridge-probe",
        )
        accepted = "[BRIDGE-PROBE] accepted:  True" in report
        recommendations = _bridge_probe_recommendations(stmt, report)
        view = tool_view_from_projection(
            tool="bridge-probe",
            proof_state=projection_to_goal_info(projection),
            recommendations=recommendations,
            evidence={
                "probe": [{
                    "id": "probe.bridge_probe",
                    "producer": "daemon.bridge_probe",
                    "accepted": accepted,
                    "candidate": _bridge_probe_candidate(stmt),
                    "bridge_size": _bridge_probe_field(report, "bridge_size"),
                    "closed_by": _bridge_probe_field(report, "closed_by"),
                }],
                "epistemic": [{
                    "id": "epistemic.bridge_probe",
                    "status": (
                        "daemon_probe_accepted"
                        if accepted else "daemon_probe_rejected"
                    ),
                    "meaning": (
                        "The daemon tested the bridge against the current "
                        "history without mutating proof state."
                    ),
                    "not_meaning": (
                        "The tactic has already been committed to history."
                    ),
                }],
                "raw": [{
                    "id": "raw.bridge_probe_text",
                    "format": "legacy_text",
                    "preview": report[:1000],
                }],
            },
            notes=[] if recommendations else [report.strip()],
            debug={"legacy_text": report[:4000]},
        )
        record_tool_view(session, view)
    except Exception:
        pass


def _bridge_probe_recommendations(stmt: str, report: str) -> list[dict]:
    normalized_stmt = stmt.strip().rstrip(".")
    if not normalized_stmt:
        return []
    accepted = "[BRIDGE-PROBE] accepted:  True" in report
    closed_by = _bridge_probe_field(report, "closed_by")
    if accepted and closed_by:
        return [{
            "id": "bridge_probe.commit.0",
            "kind": "bridge_probe_commit",
            "producer": "bridge-probe",
            "action": f"have -> : {normalized_stmt}. {closed_by}",
            "why": (
                "The daemon bridge probe accepted this bridge and closer "
                "against the current history."
            ),
            "action_type": "runnable_tactic",
            "confidence": "verified",
            "preconditions": [
                "proof_state.status == open",
                "history has not changed since the bridge probe",
            ],
            "source_refs": [],
            "evidence_refs": ["probe.bridge_probe", "raw.bridge_probe_text"],
            "metadata": {
                "epistemic_status": "daemon_probe_accepted",
                "state_changed": True,
                "bridge_size": _bridge_probe_field(report, "bridge_size"),
            },
        }]
    if "[BRIDGE-PROBE] VERDICT: TOO BIG" in report:
        return [
            {
                "id": "bridge_probe.decompose.0",
                "kind": "bridge_probe_strategy",
                "producer": "bridge-probe",
                "action": (
                    "Decompose this bridge into smaller Pr equalities or add "
                    "a hand-crafted invariant/rnd hint before committing."
                ),
                "why": (
                    "The daemon could not close the full bridge with the "
                    "sim/byequiv ladder."
                ),
                "action_type": "strategy_hint",
                "confidence": "high",
                "preconditions": ["proof_state.status == open"],
                "source_refs": [],
                "evidence_refs": ["probe.bridge_probe", "raw.bridge_probe_text"],
                "metadata": {
                    "epistemic_status": "daemon_probe_rejected",
                    "state_changed": False,
                    "bridge_size": _bridge_probe_field(report, "bridge_size"),
                },
            },
            {
                "id": "bridge_probe.avoid.0",
                "kind": "bridge_probe_avoid",
                "producer": "bridge-probe",
                "action": (
                    f"Do not commit `have -> : {normalized_stmt}.` as one "
                    "unhinted bridge."
                ),
                "why": "The bridge probe rejected the unhinted full bridge.",
                "action_type": "avoid_action",
                "confidence": "high",
                "preconditions": ["proof_state.status == open"],
                "source_refs": [],
                "evidence_refs": ["probe.bridge_probe", "raw.bridge_probe_text"],
                "metadata": {
                    "epistemic_status": "daemon_probe_rejected",
                    "state_changed": False,
                },
            },
        ]
    return []


def _bridge_probe_candidate(stmt: str) -> str:
    normalized = stmt.strip().rstrip(".")
    return f"have -> : {normalized}." if normalized else ""


def _bridge_probe_field(report: str, field: str) -> str:
    prefix = f"[BRIDGE-PROBE] {field}:"
    for line in report.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


# ─── -chain ──────────────────────────────────────────────────────────────

# Tactics that warrant an auto-checkpoint before applying. transitivity
# can spawn multiple subgoal branches whose ordering matters; eager
# variants reshape the proof tree in non-trivial ways.
_CHAIN_RISKY_TACTICS = re.compile(
    r"^\s*(?:transitivity|eager\s+call|eager\s+proc|eager\s+seq)\b",
    re.IGNORECASE,
)

# Markers in append_block's delta that the chain handler should re-emit
# explicitly (the `-next` handler prints the full delta verbatim; chain
# extracts named blocks because the chain flow already prints its own
# `OK` / goal state). See session_cli.py 5002 (history) for context.
_CHAIN_BLOCK_RE = re.compile(
    r"\[(?:AUTO-[A-Z][A-Z_-]*|STATE-DIFF|GOAL_CLOSED|"
    r"TACTIC_NO_EFFECT_AUTO_REVERTED)\]"
    r".*?(?=\n\[(?:AUTO-[A-Z]|STATE-DIFF|GOAL_CLOSED|"
    r"TACTIC_NO_EFFECT_AUTO_REVERTED|goal:)|\Z)",
    re.DOTALL,
)

_CHAIN_ERR_RE = re.compile(r"\[(error|critical|fatal)")


def handle_chain(session, args) -> int:
    """Apply tactics one-by-one with auto-detection of errors / no-progress.

    Reads tactic source from --from-file or -c, splits on `.<whitespace>`
    (preserves dots inside identifiers), and applies each via
    `session.append_block`. Stops at the first failed step:
    - `--keep-on-fail`: rolls back the failed step only, preserves the
      successful prefix
    - default: rolls back EVERYTHING (failed step + accepted prefix)

    Sets `session._chain_skip_verify = True` for the duration so
    daemon-verified hook blocks (AUTO-PIVOT-VERIFIED, AUTO-CALL-READY,
    etc.) skip their daemon probes — at 5+ candidates × ~200ms each
    × 75 steps that's 35+ min vs ~3 min when skipped. Agent gets these
    blocks back on the next single `-next`.
    """
    chain_input = None
    if args.from_file is not None:
        chain_input = open(args.from_file).read()
    elif args.command is not None:
        chain_input = args.command
    if chain_input is None:
        sys.stderr.write(
            "Usage: -chain -c 'tac1. tac2. tac3.'\n"
            "   or: -chain --from-file tactics.txt\n",
        )
        return 2
    if not session.curr.exists():
        sys.stderr.write("No current goal state. Run -start first.\n")
        return 1

    # Split on '.<whitespace>' to preserve identifier dots (G1.bad, etc.)
    tactics: list[str] = []
    for part in re.split(r"\.\s", chain_input.strip()):
        part = part.strip().rstrip(".")
        if part:
            tactics.append(part + ".")
    if not tactics:
        sys.stderr.write(
            "No tactics found. Each tactic must end with '.'\n",
        )
        return 2

    _legacy_stdout_write(f"[chain] {len(tactics)} tactics to apply\n")
    session._chain_skip_verify = True

    accepted = 0
    for i, tac in enumerate(tactics):
        _legacy_stdout_write(f"\n[{i + 1}/{len(tactics)}] {tac}\n")
        if _CHAIN_RISKY_TACTICS.match(tac) and accepted > 0:
            _auto_checkpoint(session, tac)

        prev_text_raw = ""
        if session.curr.exists():
            prev_text_raw = session.read_state().raw_current

        # Ground truth: history.ec line count. append_block can roll
        # back via TWO paths (no-progress auto-revert + daemon-rejection),
        # only the first emits a marker. Comparing line counts is the
        # single accurate signal — both shrink history to the
        # pre-append state.
        hist_lines_before = session._count_lines(session.history)
        delta = session.append_block(tac, deltas_only=False)

        for auto in _CHAIN_BLOCK_RE.findall(delta):
            _legacy_stdout_write("\n" + auto.rstrip() + "\n")

        hist_lines_after = session._count_lines(session.history)
        tactic_committed = hist_lines_after > hist_lines_before
        auto_reverted = "[TACTIC_NO_EFFECT_AUTO_REVERTED]" in delta

        curr_state = session.read_state()
        curr_text = curr_state.raw_current
        prev_errors = (
            set(l for l in prev_text_raw.split("\n")
                if _CHAIN_ERR_RE.search(l))
            if prev_text_raw else set()
        )
        curr_errors = set(l for l in curr_text.split("\n")
                          if _CHAIN_ERR_RE.search(l))
        new_errors = curr_errors - prev_errors
        has_error = len(new_errors) > 0

        # Detect "all closed" via the shared session-state reader so chain
        # mode agrees with events and inspection tools on prompt shapes like
        # `No more goals` -> `+ added lemma` -> prompt.
        no_more = curr_state.proof_candidate_closed

        # Strict-mode SMT replay errors — downgrade when proof closed
        if no_more and has_error and new_errors:
            non_strict = {
                e for e in new_errors
                if not ("cannot prove goal" in e and "strict" in e.lower())
            }
            if not non_strict:
                has_error = False
                _legacy_stdout_write(
                    "  [STRICT_WARNING] smt accepted but may not "
                    "replay in strict mode. Goals remaining: "
                    f"{'0 (all closed)' if no_more else 'unchanged'}.\n",
                )
        # [section closing] artifact suppression
        if has_error and new_errors:
            non_section = {
                e for e in new_errors
                if "cannot process [section closing]" not in e
            }
            if not non_section:
                has_error = False
                _legacy_stdout_write(
                    "  [POST-QED] 'section closing' artifact "
                    "suppressed (benign EC post-proof artifact, "
                    "proof valid).\n",
                )
        # [theory closing] suppression on qed
        is_qed = tac.strip().rstrip(".").strip().lower() == "qed"
        if has_error and new_errors and is_qed:
            non_theory = {
                e for e in new_errors
                if "cannot process [theory closing]" not in e
            }
            if not non_theory:
                has_error = False
                _legacy_stdout_write(
                    "  [POST-QED] 'theory closing' artifact "
                    "suppressed (benign EC post-proof artifact, "
                    "proof valid).\n",
                )

        stale, _stale_reason = detect_no_progress(
            prev_text_raw,
            curr_text,
            has_error,
        )
        stale = stale and not no_more

        # Failure detection: error OR stale OR not-committed-to-history.
        # `not tactic_committed` catches silent daemon rollbacks (no
        # marker fires), preventing chain from over-rollback past a
        # real prefix.
        if has_error or stale or not tactic_committed:
            return _handle_chain_failure(
                session, args, tactics, tac, accepted, i,
                has_error, new_errors, auto_reverted,
                tactic_committed,
            )
        accepted += 1
        last_lines = (
            curr_state.raw_for_goal_tools or curr_state.active_output
        ).strip().split("\n")[-20:]
        goal_lines = [
            l for l in last_lines if "post =" in l or "check]>" in l
        ]
        if goal_lines:
            _legacy_stdout_write(f"  OK  {goal_lines[-1].strip()}\n")
        else:
            _legacy_stdout_write("  OK\n")

    _legacy_stdout_write(f"\n[chain] All {accepted} tactics accepted.\n")
    goal_block, n_remaining = session.get_active_goal_block()
    goal_status = session._auto_goal_header()
    if n_remaining > 1:
        _legacy_stdout_write(
            f"\n{goal_status.rstrip()} ({n_remaining} remaining)\n",
        )
    else:
        _legacy_stdout_write(f"\n{goal_status}")
    if goal_block:
        _legacy_stdout_write(f"\nFinal goal state:\n{goal_block}\n")
    _finalize_tactic_execution(
        session,
        command="chain",
        execution_mode="commit_chain",
        status="ok",
        attempted_tactics=tactics,
        accepted_count=accepted,
        keep_on_fail=bool(args.keep_on_fail),
        raw_output=f"[chain] All {accepted} tactics accepted.",
        chain_steps=[
            {"index": idx + 1, "tactic": tactic, "status": "accepted"}
            for idx, tactic in enumerate(tactics)
        ],
        ok=True,
        emit_artifact_stdout=False,
    )
    return 0


def _auto_checkpoint(session, tac: str) -> None:
    """Save a checkpoint before a risky tactic (transitivity / eager
    variants) so the agent can rewind cleanly if the path doesn't
    pan out."""
    ckpt_name = f"auto_before_{tac.split()[0].strip()}"
    ckpt_tactics = [
        l for l in session.history.read_text(
            encoding="utf-8",
        ).splitlines()
        if l.strip()
    ]
    ckpt = {
        "name": ckpt_name,
        "timestamp": _dt.now().isoformat(),
        "tactics": ckpt_tactics,
        "auto": True,
    }
    ckpt_path = session.dir / f"checkpoint_{ckpt_name}.json"
    ckpt_path.write_text(_json.dumps(ckpt, indent=2), encoding="utf-8")
    _legacy_stdout_write(
        f"  [auto-checkpoint] Saved '{ckpt_name}' "
        f"({len(ckpt_tactics)} tactics)\n",
    )


def _handle_chain_failure(
        session, args, tactics, tac, accepted, i,
        has_error, new_errors, auto_reverted, tactic_committed) -> int:
    """Print failure diagnostics + roll back. Returns exit code 1."""
    if has_error:
        err_msg = (
            list(new_errors)[0] if new_errors else "unknown error"
        )
        _legacy_stdout_write(f"  FAILED: {err_msg.strip()}\n")
        # Classify the error so SYNTAX vs STRUCTURE is correctly
        # attributed and the prover doesn't abandon a correct
        # structural path on a signature error. Lazy import — avoids
        # circular dependency at module load.
        from core.easycrypt.session_common import classify_and_format  # type: ignore
        cls_block = classify_and_format(
            err_msg,
            tactic_text=tac,
            file_path=session._session_file_path(),
        )
        if cls_block:
            _legacy_stdout_write(cls_block)
    elif auto_reverted or not tactic_committed:
        _legacy_stdout_write(
            "  AUTO-REVERTED: tactic had no effect, session "
            "rolled back\n",
        )
    else:
        _legacy_stdout_write(
            "  STALE: tactic had no effect (goal unchanged)\n",
        )

    if args.keep_on_fail and accepted > 0:
        # Preserve successful prefix; pop only the failed tactic
        # (skip step_up if append_block already rolled back).
        if tactic_committed:
            session.step_up()
        _legacy_stdout_write(
            f"\n[chain] Stopped after {accepted}/{len(tactics)} "
            f"tactics. Partial success kept (--keep-on-fail): state "
            f"after {accepted} accepted tactic(s) is preserved.\n"
            f"  Failed tactic rolled back: {tac!r}\n"
            f"  Remaining tactics NOT applied: "
            f"{[t for t in tactics[i + 1:]]}\n",
        )
        goal_block, n_remaining = session.get_active_goal_block()
        goal_status = session._auto_goal_header()
        if n_remaining > 1:
            _legacy_stdout_write(
                f"\n{goal_status.rstrip()} ({n_remaining} remaining)\n",
            )
        else:
            _legacy_stdout_write(f"\n{goal_status}")
        if goal_block:
            _legacy_stdout_write(
                f"\nCheckpoint goal state:\n{goal_block}\n",
            )
        _legacy_stdout_write(
            "[chain] Session is at checkpoint. Continue with "
            "-next -c '<tactic>'.\n",
        )
    else:
        # Roll back failed step + accepted prefix. If append_block
        # already rolled back the failed tactic, only roll back the
        # prefix.
        rollback_n = accepted + (1 if tactic_committed else 0)
        for _ in range(rollback_n):
            session.step_up()
        _legacy_stdout_write(
            f"\n[chain] Stopped after {accepted}/{len(tactics)} "
            f"tactics. All {rollback_n} tactic(s) rolled back.\n",
        )
        goal_block, n_remaining = session.get_active_goal_block()
        goal_status = session._auto_goal_header()
        _legacy_stdout_write(f"\n{goal_status}")
        if goal_block:
            _legacy_stdout_write(
                f"\nGoal state at failure point:\n{goal_block}\n",
            )
    status = "partial_success" if args.keep_on_fail and accepted > 0 else "failed"
    failure_reason = (
        list(new_errors)[0].strip()
        if has_error and new_errors else
        "tactic had no effect or was not committed"
    )
    if args.keep_on_fail and accepted > 0:
        rollback_count = 1 if tactic_committed else 0
    else:
        rollback_count = accepted + (1 if tactic_committed else 0)
    _finalize_tactic_execution(
        session,
        command="chain",
        execution_mode="commit_chain",
        status=status,
        attempted_tactics=tactics[:i + 1],
        accepted_count=accepted if args.keep_on_fail else 0,
        failed_tactic=tac,
        failure_reason=failure_reason,
        keep_on_fail=bool(args.keep_on_fail),
        rollback_count=rollback_count,
        raw_output=failure_reason,
        chain_steps=[
            {
                "index": idx + 1,
                "tactic": tactic,
                "status": (
                    "accepted"
                    if idx < accepted and args.keep_on_fail else
                    "rolled_back"
                    if idx < accepted else
                    "failed"
                ),
            }
            for idx, tactic in enumerate(tactics[:i + 1])
        ],
        ok=False,
        emit_artifact_stdout=False,
    )
    return 1


def _record_proof_context_view(
    session,
    action_name: str,
    *,
    emit_stdout: bool = True,
) -> tuple[dict, dict] | None:
    """Build and persist the post-execution ProofContextView.

    The command's own ``tool.result`` event is emitted by ``session_cli`` after
    the handler returns, so this snapshot is intentionally "post EasyCrypt
    result, pre tool.result". ``session_projection`` ignores the live trailing
    ``tool.called`` for the same action to avoid a false pending-tool contract
    error.
    """
    try:
        from core.easycrypt.session_agent_view import (  # type: ignore
            build_proof_context_view,
            record_proof_context_view,
        )
    except Exception:
        try:
            from core.easycrypt.session_agent_view import (  # type: ignore
                build_proof_context_view,
                record_proof_context_view,
            )
        except Exception:
            return None
    try:
        view = build_proof_context_view(
            session.dir,
            live_tool_name=action_name,
            include_goal_text=True,
            max_recommendations=8,
            max_stale_recommendations=8,
        )
        payload = record_proof_context_view(
            session,
            view,
            source="session_cli.post_commit",
        )
        if emit_stdout:
            sys.stdout.write(
                "\n[PROOF-CONTEXT-VIEW] post-commit snapshot recorded: "
                f"{payload.get('artifact')}\n",
            )
        return view, payload
    except Exception:
        return None


def _finalize_tactic_execution(
    session,
    *,
    command: str,
    live_tool_name: str | None = None,
    execution_mode: str | None = None,
    status: str,
    attempted_tactics: list[str],
    accepted_count: int,
    failed_tactic: str = "",
    failure_reason: str = "",
    keep_on_fail: bool = False,
    rollback_count: int = 0,
    raw_output: str = "",
    chain_steps: list[dict] | None = None,
    ok: bool | None = None,
    emit_artifact_stdout: bool = True,
    emit_execution_stdout: bool = True,
) -> dict | None:
    """Finalize one proof interaction in the canonical manager order.

    Handler code above executes EasyCrypt/session runtime and passes the raw
    outcome here.  The manager then normalizes and records artifacts in order:
    CommitResponse -> ProofContextView -> ProverWorkspaceView ->
    TacticExecutionResult.  Legacy CommandSummary artifacts are historical
    readers only and are not produced by the live manager path.
    """
    active_tool_name = live_tool_name or command
    try:
        from core.easycrypt.session_commit_response import (  # type: ignore
            build_commit_response,
            record_commit_response,
        )
    except Exception:
        try:
            from core.easycrypt.session_commit_response import (  # type: ignore
                build_commit_response,
                record_commit_response,
            )
        except Exception:
            return None
    try:
        response = build_commit_response(
            session.dir,
            command=command,
            status=status,
            attempted_tactics=attempted_tactics,
            accepted_count=accepted_count,
            failed_tactic=failed_tactic,
            failure_reason=failure_reason,
            keep_on_fail=keep_on_fail,
            rollback_count=rollback_count,
            agent_view_payload={},
            live_tool_name=active_tool_name,
            ok=ok,
        )
        payload = record_commit_response(session, response)
        if emit_artifact_stdout:
            sys.stdout.write(
                "[COMMIT-RESPONSE] structured response recorded: "
                f"{payload.get('artifact')}\n",
            )
        proof_context_view, proof_context_payload = (
            _record_proof_context_view(
                session,
                active_tool_name,
                emit_stdout=False,
            ) or ({}, {})
        )
        workspace_view, workspace_payload = _record_prover_workspace_view(
            session,
            proof_context_view=proof_context_view,
            proof_context_payload=proof_context_payload,
        )
        _record_tactic_execution_result(
            session,
            mode=execution_mode or command,
            command=command,
            response=response,
            commit_payload=payload,
            proof_context_payload=proof_context_payload,
            workspace_view=workspace_view,
            workspace_payload=workspace_payload,
            raw_output=raw_output,
            chain_steps=chain_steps or [],
            emit_stdout=emit_execution_stdout,
        )
        return payload
    except Exception:
        return None


def _record_prover_workspace_view(
    session,
    *,
    proof_context_view: dict,
    proof_context_payload: dict,
) -> tuple[dict, dict]:
    try:
        from core.easycrypt.session_prover_workspace_view import (  # type: ignore
            build_prover_workspace_view_from_context,
            record_prover_workspace_view,
        )
    except Exception:
        try:
            from core.easycrypt.session_prover_workspace_view import (  # type: ignore
                build_prover_workspace_view_from_context,
                record_prover_workspace_view,
            )
        except Exception:
            return {}, {}
    try:
        workspace_view = build_prover_workspace_view_from_context(
            proof_context_view,
            proof_context_payload=proof_context_payload,
            max_alternatives=3,
            max_evidence=5,
        )
    except Exception:
        return {}, {}
    try:
        workspace_payload = record_prover_workspace_view(session, workspace_view)
    except Exception:
        workspace_payload = {}
    return workspace_view, workspace_payload


def _record_tactic_execution_result(
    session,
    *,
    mode: str,
    command: str,
    response: dict,
    commit_payload: dict,
    proof_context_payload: dict,
    workspace_view: dict,
    workspace_payload: dict,
    raw_output: str = "",
    chain_steps: list[dict] | None = None,
    emit_stdout: bool = True,
) -> dict | None:
    try:
        from core.easycrypt.session_tactic_execution_result import (  # type: ignore
            build_tactic_execution_result,
            format_tactic_execution_result,
            record_tactic_execution_result,
            write_tactic_raw_result_artifact,
        )
    except Exception:
        try:
            from core.easycrypt.session_tactic_execution_result import (  # type: ignore
                build_tactic_execution_result,
                format_tactic_execution_result,
                record_tactic_execution_result,
                write_tactic_raw_result_artifact,
            )
        except Exception:
            return None
    try:
        raw_payload = {}
        if raw_output:
            try:
                raw_payload = write_tactic_raw_result_artifact(
                    session.dir,
                    command=command,
                    raw_result=raw_output,
                )
            except Exception:
                raw_payload = {}
        result = build_tactic_execution_result(
            session.dir,
            mode=mode,
            command=command,
            commit_response=response,
            commit_response_payload=commit_payload,
            proof_context_payload=proof_context_payload,
            workspace_view=workspace_view,
            workspace_payload=workspace_payload,
            raw_result=raw_output,
            raw_result_payload=raw_payload,
            chain_steps=chain_steps or [],
        )
        payload = record_tactic_execution_result(session, result)
        if emit_stdout:
            sys.stdout.write(format_tactic_execution_result(result))
        return payload
    except Exception:
        return None


def _latest_transition_info(session, action_name: str) -> dict:
    from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore
    try:
        projection = read_proof_state_projection(
            session.dir,
            live_tool_name=action_name,
        )
        return projection.latest_transition.to_dict()
    except Exception:
        return {}


def _write_legacy_output(text: str) -> None:
    if not text:
        return
    mode = _legacy_display_mode()
    if mode in {"off", "hide", "hidden", "none"}:
        return
    if mode == "compact":
        compact = _compact_legacy_output(text)
        if compact:
            sys.stdout.write("\n[LEGACY-OUTPUT compact]\n")
            sys.stdout.write(compact)
            if not compact.endswith("\n"):
                sys.stdout.write("\n")
        return
    sys.stdout.write("\n[LEGACY-OUTPUT]\n")
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _legacy_stdout_write(text: str) -> None:
    if not text:
        return
    mode = _legacy_display_mode()
    if mode in {"off", "hide", "hidden", "none"}:
        return
    sys.stdout.write(text)


def _legacy_display_mode() -> str:
    # Commit stdout hides legacy blocks by default (deliberately stricter than
    # the canonical "full" default used by the inspect/session surfaces).
    from core.easycrypt.session_tool_view import legacy_display_mode
    return legacy_display_mode(default="hidden")


def _compact_legacy_output(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    important_prefixes = (
        "[ALL_GOALS_CLOSED]",
        "[GOAL_CLOSED]",
        "[DAEMON_REJECTED]",
        "[TACTIC_NO_EFFECT_AUTO_REVERTED]",
        "[STATE-DIFF]",
        "[CLASS:",
        "[error]",
        "[critical]",
        "[fatal]",
    )
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if (
            stripped.startswith(important_prefixes)
            or stripped.startswith("Current goal")
            or stripped.startswith("No more goals")
            or "remaining:" in stripped
            or stripped.startswith("pre =")
            or stripped.startswith("post =")
        ):
            kept.append(line)
    if not kept:
        kept = lines[-12:]
    return "\n".join(kept[:80])


# ─── -write-back ─────────────────────────────────────────────────────────

def handle_write_back(session, args) -> int:
    """Write the session's accepted proof back into the source .ec file,
    replacing the body between `proof.` and `qed.` of the target lemma.
    Preserves comment lines from the original body (notably
    `(* COMPLETE THIS … *)` markers).

    Resolves `file_path` from `--file` or session_meta.json; resolves
    `lemma_name` from `--lemma` or session_meta.json. Both are
    required.
    """
    file_path = None
    if args.file:
        file_path = Path(args.file)
    else:
        meta_path = session.dir / "session_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                if meta.get("file"):
                    file_path = Path(meta["file"])
            except Exception:
                pass
    if file_path is None or not file_path.exists():
        sys.stderr.write(
            "[write-back] No source file found. Use -f <file.ec> "
            "or start the session with -f.\n",
        )
        return 1

    lemma_name = args.lemma
    if not lemma_name:
        meta_path = session.dir / "session_meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                lemma_name = meta.get("lemma")
            except Exception:
                pass
    if not lemma_name:
        sys.stderr.write(
            "[write-back] No lemma name. Use -lemma <name> or start "
            "the session with -lemma.\n",
        )
        return 1

    if not session.history.exists() or session.history.stat().st_size == 0:
        sys.stderr.write(
            "[write-back] Session history is empty. Prove the "
            "lemma first.\n",
        )
        return 1

    hist_text = session.history.read_text(
        encoding="utf-8", errors="replace",
    )
    hist_lines = hist_text.splitlines()
    has_qed = any(
        l.strip().lower().rstrip(".").strip() == "qed"
        for l in hist_lines
    )
    if not has_qed:
        sys.stderr.write(
            "[write-back] WARNING: session history has no 'qed.' — "
            "proof may be incomplete.\n"
            "  Proceeding anyway. Add 'qed.' to history or re-run "
            "with a complete proof.\n",
        )

    # Strip leading proof. / trailing qed. — session history may or
    # may not include the wrapper lines.
    tactic_lines = list(hist_lines)
    if tactic_lines and re.match(r"^\s*proof\s*\.\s*$", tactic_lines[0]):
        tactic_lines = tactic_lines[1:]
    if tactic_lines and re.match(r"^\s*qed\s*\.\s*$", tactic_lines[-1]):
        tactic_lines = tactic_lines[:-1]

    src_text = file_path.read_text(encoding="utf-8")
    src_lines = src_text.splitlines(keepends=True)

    lemma_pat = re.compile(
        r"^\s*(local\s+)?(lemma|equiv|hoare)\s+"
        + re.escape(lemma_name) + r"\b",
    )
    lemma_line_idx = None
    for i, line in enumerate(src_lines):
        if lemma_pat.match(line):
            lemma_line_idx = i
            break
    if lemma_line_idx is None:
        sys.stderr.write(
            f"[write-back] Could not find lemma '{lemma_name}' in "
            f"{file_path.name}.\n",
        )
        return 1

    # Lemma signature can span multiple lines; find next `proof.`
    proof_line_idx = None
    for i in range(lemma_line_idx + 1, len(src_lines)):
        if re.match(r"^\s*proof\s*\.\s*$", src_lines[i]):
            proof_line_idx = i
            break
    if proof_line_idx is None:
        sys.stderr.write(
            f"[write-back] Could not find 'proof.' after lemma "
            f"'{lemma_name}' in {file_path.name}.\n",
        )
        return 1

    qed_line_idx = None
    for i in range(proof_line_idx + 1, len(src_lines)):
        if re.match(r"^\s*qed\s*\.\s*$", src_lines[i]):
            qed_line_idx = i
            break
    if qed_line_idx is None:
        sys.stderr.write(
            f"[write-back] Could not find 'qed.' after 'proof.' "
            f"for lemma '{lemma_name}' in {file_path.name}.\n",
        )
        return 1

    orig_body_lines = src_lines[proof_line_idx + 1: qed_line_idx]
    preserved_comments = [
        l for l in orig_body_lines
        if re.match(r"^\s*\(\*", l.rstrip("\n"))
    ]

    # Detect indentation: 2-space default, or match what's already in
    # the file body.
    body_indent = "  "
    for bl in orig_body_lines:
        stripped = bl.rstrip("\n")
        if stripped.strip() and not stripped.strip().startswith("(*"):
            m = re.match(r"^(\s+)", stripped)
            if m:
                body_indent = m.group(1)
            break

    new_body_parts: list[str] = []
    for c in preserved_comments:
        new_body_parts.append(c if c.endswith("\n") else c + "\n")
    for tl in tactic_lines:
        stripped_tl = tl.strip()
        if stripped_tl:
            new_body_parts.append(body_indent + stripped_tl + "\n")
        else:
            new_body_parts.append("\n")
    new_body = "".join(new_body_parts)

    new_text = (
        "".join(src_lines[: proof_line_idx + 1])
        + new_body
        + "".join(src_lines[qed_line_idx:])
    )
    file_path.write_text(new_text, encoding="utf-8")

    old_body_count = len([l for l in orig_body_lines if l.strip()])
    new_body_count = len([l for l in new_body_parts if l.strip()])
    sys.stdout.write(
        f"[write-back] Wrote proof of '{lemma_name}' to {file_path}\n"
        f"  Replaced lines {proof_line_idx + 2}–{qed_line_idx} "
        f"({old_body_count} non-blank) with {new_body_count} "
        f"tactic line(s)\n"
        f"  Proof status: "
        f"{'complete (qed present in history)' if has_qed else 'WARNING: incomplete (no qed in history)'}\n",
    )
    if preserved_comments:
        sys.stdout.write(
            f"  Preserved {len(preserved_comments)} comment "
            f"line(s) from original proof block\n",
        )
    return 0
