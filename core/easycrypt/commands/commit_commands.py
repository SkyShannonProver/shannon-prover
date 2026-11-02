"""Canonical manager tactic execution and exact read-only preflight."""
from __future__ import annotations

import sys

from core.easycrypt.proof_text import split_tactic_chain


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
    -c, or stdin in that priority. ``Session.append_block`` judges and
    records it; its verdict is the command's result."""
    if args.from_file is not None:
        data = open(args.from_file).read()
    elif args.command is not None:
        data = args.command
    else:
        data = sys.stdin.read()
    if not data.strip():
        sys.stderr.write("No tactic provided for -tactic-exec commit.\n")
        return 2
    result = session.append_block(data, deltas_only=args.deltas_only)
    command_ok = result.status == "ok"
    _finalize_tactic_execution(
        session,
        command="commit",
        execution_mode="commit",
        status=result.status,
        attempted_tactics=[data.strip()],
        accepted_count=1 if command_ok else 0,
        failed_tactic="" if command_ok else data.strip(),
        failure_reason="" if command_ok else _failure_reason(result),
        raw_output=result.output,
        ok=command_ok,
        emit_artifact_stdout=False,
    )
    return 0


def _failure_reason(result) -> str:
    """Why a commit left nothing in history, for the execution record."""
    return (
        result.latest_error.strip()
        or result.no_progress_reason.strip()
        or "tactic had no effect or was not committed"
    )


def handle_undo(session, args) -> int:
    """Pop the most recent committed transaction from history, or, with
    ``--keep-commands N``, rewind to the first ``N`` committed commands by
    undoing the daemon. A rewind that cannot be done by undo changes nothing
    and is reported as ``no_progress`` with the reason."""
    keep_commands = getattr(args, "keep_commands", None)
    if keep_commands is None:
        undo = session.step_up()
    else:
        undo = session.rewind_to_command_count(int(keep_commands))
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
    result = session.try_speculative(tactic)
    session.emit_event("tactic.try_result", {
        "name": "try",
        "kind": "speculative_tactic",
        "accepted": result.accepted,
        "mutates_proof_state": False,
        "tactic": result.tactic.strip(),
        "status": "error" if result.tool_error else "ok",
        "goal_after_closed": result.goal_after_closed,
        "goal_after_remaining": result.goal_after_remaining,
        "error_kind": result.error_kind,
        "no_progress_predicted": result.no_progress_predicted,
        "report": result.report,
    })
    _record_try_preflight_artifact(session, result)
    sys.stdout.write(result.report)
    return 0


def _record_try_preflight_artifact(session, result) -> dict:
    from core.easycrypt.session.session_projection import (  # type: ignore
        projection_to_proof_status,
        read_proof_state_projection,
    )
    from core.easycrypt.session.session_tactic_preflight import (  # type: ignore
        build_tactic_preflight_artifact,
        record_tactic_preflight_artifact,
    )

    projection = read_proof_state_projection(session.dir, live_tool_name="try")
    proof_state = projection_to_proof_status(projection)

    artifact = build_tactic_preflight_artifact(
        proof_state=proof_state,
        result=result,
    )
    record_tactic_preflight_artifact(session, artifact)
    return artifact


def handle_commit_chain(session, args) -> int:
    """Commit tactics one by one, stopping at the first that does not commit.

    Reads tactic source from --from-file or -c, splits it at EasyCrypt
    sentence ends (``split_tactic_chain``, which the manager uses to bind
    the request), and applies each via `session.append_block`, whose
    verdict decides the step. Stops at the first failed step:
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

    tactics = split_tactic_chain(chain_input)
    if not tactics:
        sys.stderr.write(
            "No tactics found. Each tactic must end with '.'\n",
        )
        return 2

    accepted = 0
    for i, tac in enumerate(tactics):
        result = session.append_block(tac, deltas_only=False)
        if result.status != "ok":
            return _handle_commit_chain_failure(
                session, args, tactics, tac, accepted, i, result,
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
        session, args, tactics, tac, accepted, i, result) -> int:
    """Roll back after a failed chain step. Returns exit code 1.

    Failure diagnostics live in the structured tactic-execution artifact
    (status/failed_tactic/failure_reason below); there is no separate
    stdout rendering.
    """
    tactic_committed = result.history_committed
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
    failure_reason = _failure_reason(result)
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
    from core.easycrypt.session.session_commit_response import (  # type: ignore
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
    from core.easycrypt.session.session_managed_goal_view import (  # type: ignore
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
    from core.easycrypt.session.session_tactic_execution_result import (  # type: ignore
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
