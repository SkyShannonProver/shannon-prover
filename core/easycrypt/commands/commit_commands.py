"""Canonical manager tactic execution and exact read-only preflight."""
from __future__ import annotations

import re
import sys

from core.easycrypt.session_no_progress import detect_no_progress
def handle_tactic_exec(session, args) -> int:
    """Canonical Proof Interaction Manager wrapper.

    This entry point names the manager-level state-changing execution mode directly.
    """
    mode = str(getattr(args, "tactic_exec", "") or "")
    if mode == "commit":
        return handle_commit(session, args)
    if mode == "commit_chain":
        return handle_commit_chain(session, args)
    if mode == "undo":
        return handle_undo(session, args)
    sys.stderr.write(
        "Unknown -tactic-exec mode. Use commit, commit_chain, or undo.\n",
    )
    return 2


def handle_commit(session, args) -> int:
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
        sys.stderr.write("No tactic provided for -tactic-exec commit.\n")
        return 2
    delta = session.append_block(data, deltas_only=args.deltas_only)
    transition = _latest_transition_info(session, "commit")
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
    _finalize_tactic_execution(
        session,
        command="commit",
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


def handle_undo(session, args) -> int:
    """Pop the most recent committed tactic from history."""
    undo = session.step_up()
    output = undo.output
    changed = undo.state_changed
    _finalize_tactic_execution(
        session,
        command="undo",
        execution_mode="undo",
        status="undone" if changed else "no_progress",
        attempted_tactics=[],
        accepted_count=0,
        failure_reason="" if changed else output.strip(),
        raw_output=output,
        ok=changed,
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
    _record_try_preflight_artifact(session, result, report)
    sys.stdout.write(report)
    return 0


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


def _record_try_preflight_artifact(
    session,
    result: dict,
    report: str,
) -> dict:
    from core.easycrypt.session_projection import (  # type: ignore
        projection_to_proof_status,
        read_proof_state_projection,
    )
    from core.easycrypt.session_tactic_preflight import (  # type: ignore
        build_tactic_preflight_artifact,
        record_tactic_preflight_artifact,
    )

    projection = read_proof_state_projection(session.dir, live_tool_name="try")
    proof_state = projection_to_proof_status(projection)

    artifact = build_tactic_preflight_artifact(
        proof_state=proof_state,
        result=result,
        raw_report=report,
    )
    record_tactic_preflight_artifact(session, artifact)
    return artifact


_CHAIN_ERR_RE = re.compile(r"\[(error|critical|fatal)")


def handle_commit_chain(session, args) -> int:
    """Apply tactics one-by-one with auto-detection of errors / no-progress.

    Reads tactic source from --from-file or -c, splits on `.<whitespace>`
    (preserves dots inside identifiers), and applies each via
    `session.append_block`. Stops at the first failed step:
    - `--keep-on-fail`: rolls back the failed step only, preserves the
      successful prefix
    - default: rolls back EVERYTHING (failed step + accepted prefix)

    """
    chain_input = None
    if args.from_file is not None:
        chain_input = open(args.from_file).read()
    elif args.command is not None:
        chain_input = args.command
    if chain_input is None:
        sys.stderr.write(
            "Usage: -tactic-exec commit_chain -c 'tac1. tac2. tac3.'\n"
            "   or: -tactic-exec commit_chain --from-file tactics.txt\n",
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

    accepted = 0
    for i, tac in enumerate(tactics):
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
        # [section closing] artifact suppression
        if has_error and new_errors:
            non_section = {
                e for e in new_errors
                if "cannot process [section closing]" not in e
            }
            if not non_section:
                has_error = False
        # [theory closing] suppression on qed
        is_qed = tac.strip().rstrip(".").strip().lower() == "qed"
        if has_error and new_errors and is_qed:
            non_theory = {
                e for e in new_errors
                if "cannot process [theory closing]" not in e
            }
            if not non_theory:
                has_error = False

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
            return _handle_commit_chain_failure(
                session, args, tactics, tac, accepted, i,
                has_error, new_errors, auto_reverted,
                tactic_committed,
            )
        accepted += 1

    _finalize_tactic_execution(
        session,
        command="commit_chain",
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


def _handle_commit_chain_failure(
        session, args, tactics, tac, accepted, i,
        has_error, new_errors, auto_reverted, tactic_committed) -> int:
    """Roll back after a failed chain step. Returns exit code 1.

    Failure diagnostics live in the structured tactic-execution artifact
    (status/failed_tactic/failure_reason below); there is no separate
    stdout rendering.
    """
    if args.keep_on_fail and accepted > 0:
        # Preserve successful prefix; pop only the failed tactic
        # (skip step_up if append_block already rolled back).
        if tactic_committed:
            session.step_up()
    else:
        # Roll back failed step + accepted prefix. If append_block
        # already rolled back the failed tactic, only roll back the
        # prefix.
        rollback_n = accepted + (1 if tactic_committed else 0)
        for _ in range(rollback_n):
            session.step_up()
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
        command="commit_chain",
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


def _finalize_tactic_execution(
    session,
    *,
    command: str,
    live_tool_name: str | None = None,
    execution_mode: str,
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
) -> dict:
    """Finalize one proof interaction in the canonical manager order.

    Handler code above executes EasyCrypt/session runtime and passes the raw
    outcome here.  The manager then normalizes and records artifacts in order:
    CommitResponse -> managed goal envelope -> TacticExecutionResult.
    """
    active_tool_name = live_tool_name or command
    from core.easycrypt.session_commit_response import (  # type: ignore
        build_commit_response,
        record_commit_response,
    )

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
        live_tool_name=active_tool_name,
        ok=ok,
    )
    payload = record_commit_response(session, response)
    if emit_artifact_stdout:
        sys.stdout.write(
            "[COMMIT-RESPONSE] structured response recorded: "
            f"{payload.get('artifact')}\n",
        )
    workspace_view, workspace_payload = _record_prover_workspace_view(
        session,
        live_tool_name=active_tool_name,
    )
    _record_tactic_execution_result(
        session,
        mode=execution_mode,
        command=command,
        response=response,
        commit_payload=payload,
        workspace_view=workspace_view,
        workspace_payload=workspace_payload,
        raw_output=raw_output,
        chain_steps=chain_steps or [],
        emit_stdout=emit_execution_stdout,
    )
    return payload


def _record_prover_workspace_view(
    session,
    *,
    live_tool_name: str,
) -> tuple[dict, dict]:
    from core.easycrypt.session_managed_goal_view import (  # type: ignore
        build_managed_goal_view,
        record_managed_goal_view,
    )

    workspace_view = build_managed_goal_view(
        session.dir,
        live_tool_name=live_tool_name,
    )
    workspace_payload = record_managed_goal_view(session, workspace_view)
    return workspace_view, workspace_payload


def _record_tactic_execution_result(
    session,
    *,
    mode: str,
    command: str,
    response: dict,
    commit_payload: dict,
    workspace_view: dict,
    workspace_payload: dict,
    raw_output: str = "",
    chain_steps: list[dict] | None = None,
    emit_stdout: bool = True,
) -> dict:
    from core.easycrypt.session_tactic_execution_result import (  # type: ignore
        build_tactic_execution_result,
        format_tactic_execution_result,
        record_tactic_execution_result,
        write_tactic_raw_result_artifact,
    )

    raw_payload = {}
    if raw_output:
        raw_payload = write_tactic_raw_result_artifact(
            session.dir,
            command=command,
            raw_result=raw_output,
        )
    result = build_tactic_execution_result(
        mode=mode,
        command=command,
        commit_response=response,
        commit_response_payload=commit_payload,
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
