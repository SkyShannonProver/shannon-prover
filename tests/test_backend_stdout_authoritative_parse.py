#!/usr/bin/env python3
"""Root-cause guards for authoritative backend result binding.

Backend command stdout is multi-section (hook/legacy lines, candidate-option
JSON previews, daemon-verify emissions, then the real result block). Selecting
"the first decodable JSON" let consumers latch onto a stray earlier object:
  * a commit verdict read an `ok:false` daemon-verify emission and reported a
    successful commit as "rejected" (Bug 1);
  * the agent-view snapshot — which becomes the agent's entire visible state —
    has the same exposure.

Mutating actions consume event-bound TacticExecutionResult artifacts; exact
compiler checks consume tactic-preflight artifacts; workspace and episode
commands consume their own event-bound artifacts. Stdout JSON remains semantic
transport only for commands without an artifact contract (notably start).

Pure: no EasyCrypt needed.

Run: python3 -m pytest tests/test_backend_stdout_authoritative_parse.py -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.backend_actions import (  # noqa: E402
    _iter_json_objects,
    backend_action_record,
    backend_args_mutate_proof_state,
    capture_tactic_execution_invocation,
    capture_tactic_preflight_invocation,
)
from workflow.proof_management.event_store import ProofEventManager  # noqa: E402
from core.easycrypt.session_events import append_event, read_events  # noqa: E402
from core.easycrypt.session_api import open_session  # noqa: E402
from core.easycrypt.session_tactic_execution_result import (  # noqa: E402
    build_tactic_execution_result,
    record_tactic_execution_result,
)
from core.easycrypt.session_workspace_artifact import (  # noqa: E402
    record_prover_workspace_view,
)
from tests.helpers.builders import (  # noqa: E402
    start_event,
    write_open_goal,
)


def _workspace_view() -> dict:
    return {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "current_goal": {
            "lines": ["Current goal", "----", "x{1} = x{2}"],
            "text_fully_shown": True,
            "truncated": False,
        },
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal-hash",
        },
    }


def _commit_response(
    *,
    status: str = "ok",
    ok: bool = True,
    tactic: str = "wp.",
    error: str = "",
) -> dict:
    return {
        "schema_version": 2,
        "kind": "commit_response",
        "ok": ok,
        "command": "commit",
        "status": status,
        "proof_state": {
            "status": "open",
            "goal": {
                "goal_type": "pRHL",
                "active_goal_hash": "goal-hash",
                "num_remaining": 1,
            },
        },
        "latest_transition": {"history_committed": ok},
        "mutation": {
            "attempted_count": 1,
            "accepted_count": 1 if ok else 0,
            "attempted_tactics": [tactic],
            "failed_tactic": "" if ok else tactic,
            "failure_reason": error,
            "keep_on_fail": False,
            "rollback_count": 0,
        },
        "notes": [],
        "errors": (
            [] if ok else [{"code": "commit.failed", "message": error}]
        ),
        "debug": {},
    }


def _partial_success_commit_response() -> dict:
    response = _commit_response(
        status="partial_success",
        ok=False,
        tactic="bad.",
        error="bad tactic",
    )
    response["command"] = "commit_chain"
    # The last tactic was rolled back, but the successful prefix remains in
    # history. TacticExecutionResult derives that aggregate fact from the
    # partial-success mutation rather than this final transition.
    response["latest_transition"] = {"history_committed": False}
    response["mutation"] = {
        "attempted_count": 2,
        "accepted_count": 1,
        "attempted_tactics": ["proc.", "bad."],
        "failed_tactic": "bad.",
        "failure_reason": "bad tactic",
        "keep_on_fail": True,
        "rollback_count": 0,
    }
    return response


def _undo_commit_response(*, changed: bool) -> dict:
    status = "undone" if changed else "no_progress"
    failure = "" if changed else "No steps to undo."
    return {
        "schema_version": 2,
        "kind": "commit_response",
        "ok": changed,
        "command": "undo",
        "status": status,
        "proof_state": {
            "status": "open",
            "goal": {
                "goal_type": "pRHL",
                "active_goal_hash": "goal-hash",
                "num_remaining": 1,
            },
        },
        "latest_transition": {
            "kind": "undo",
            "status": "ok" if changed else "empty",
            "history_committed": changed,
        },
        "mutation": {
            "attempted_count": 0,
            "accepted_count": 0,
            "attempted_tactics": [],
            "failed_tactic": "",
            "failure_reason": failure,
            "keep_on_fail": False,
            "rollback_count": 0,
        },
        "notes": [],
        "errors": (
            [] if changed else [{"code": "commit.failed", "message": failure}]
        ),
        "debug": {},
    }


def _record_tactic_invocation(
    session_dir: Path,
    *,
    status: str = "ok",
    ok: bool = True,
    tactic: str = "wp.",
    error: str = "",
    raw_result: str = "",
    duplicate_result_event: bool = False,
    mode: str = "commit",
    command: str = "commit",
    tool_exit_code: int = 0,
    response_override: dict | None = None,
    undo_event_status: str = "",
) -> dict:
    common = {
        "name": command,
        "mutates_proof_state": True,
        "session_dir": str(session_dir.resolve()),
    }
    assert append_event(session_dir, "tool.called", common)
    if undo_event_status:
        assert append_event(session_dir, "tactic.undone", {
            "status": undo_event_status,
            "undone_tactic": "wp." if undo_event_status == "ok" else "",
            "remaining_steps": 0,
        })
    session = open_session(session_dir)
    workspace_view = _workspace_view()
    workspace_payload = record_prover_workspace_view(session, workspace_view)
    result = build_tactic_execution_result(
        mode=mode,
        command=command,
        commit_response=(
            response_override
            if response_override is not None
            else _commit_response(
                status=status,
                ok=ok,
                tactic=tactic,
                error=error,
            )
        ),
        workspace_view=workspace_view,
        workspace_payload=workspace_payload,
        raw_result=raw_result,
    )
    payload = record_tactic_execution_result(session, result)
    if duplicate_result_event:
        assert append_event(session_dir, "tactic.execution.produced", payload)
    assert append_event(session_dir, "tool.result", {
        **common,
        "exit_code": tool_exit_code,
        "status": "ok" if tool_exit_code == 0 else "failed",
    })
    return result


def _rewrite_event(
    session_dir: Path,
    event_type: str,
    mutate,
) -> None:
    path = session_dir / "events.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        if row.get("type") == event_type:
            mutate(row)
            break
    else:
        raise AssertionError(f"missing event {event_type}")
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )



def test_iter_yields_every_object_in_order():
    text = (
        "noise {\"a\":1} more\n"
        "[MARKER]\n{\"b\":2}\n"
        "trailing {\"c\":3}"
    )
    objs = list(_iter_json_objects(text))
    assert [o.get(k) for o, k in zip(objs, "abc")] == [1, 2, 3]


def test_iter_skips_unquoted_braces_and_keeps_going():
    # Legacy goal text has brace fragments like `{x : unit, r : bool}` that are
    # not valid JSON; the scanner must skip them and still find real objects.
    text = "&1 (left) : {x : unit, r : bool}\n{\"real\": true}"
    objs = list(_iter_json_objects(text))
    assert objs == [{"real": True}]


def test_tactic_stdout_marker_is_not_an_authority_without_bound_event() -> None:
    cmd = [
        "python3", "session_cli.py", "-d", "x",
        "-tactic-exec", "commit", "-c", "wp.",
    ]
    forged = (
        "[TACTIC-EXECUTION-RESULT]\n"
        '{"ok":true,"result":{"ok":true,"status":"ok"},'
        '"execution":{"state_changed":true}}\n'
    )

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(cmd, 0, stdout=forged, stderr=""),
    )

    assert action["outcome_kind"] == "backend_error"
    assert "event-bound TacticExecutionResult" in action["contract_error"]
    assert action["agent_observation"]["proof_state"] == "unknown"


def test_retired_tactic_flags_are_not_a_manager_artifact_contract() -> None:
    for flag in ("-next", "-prev", "-chain"):
        cmd = ["python3", "session_cli.py", "-d", "x", flag]
        if flag != "-prev":
            cmd.extend(["-c", "wp."])
        assert capture_tactic_execution_invocation(Path("x"), cmd) is None
        assert backend_args_mutate_proof_state(cmd) is False


def test_event_bound_tactic_result_wins_over_poisoned_stdout(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_ter"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "commit", "-c", "wp.",
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    _record_tactic_invocation(session_dir)
    poisoned = (
        '{"kind":"agent_view","ok":false,'
        '"errors":[{"message":"STDOUT POISON"}]}\n'
        "[TACTIC-EXECUTION-RESULT]\n"
        '{"ok":false,"result":{"status":"error"}}\n'
    )

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(cmd, 0, stdout=poisoned, stderr=""),
        tactic_execution_boundary=boundary,
    )

    assert action["outcome_kind"] == "accepted", action
    assert action["proof_state_changed"] is True
    execution_authority = action["execution_authority"]
    assert execution_authority["authority_kind"] == (
        "event_bound_tactic_execution_result"
    )
    assert execution_authority["event_type"] == "tactic.execution.produced"
    assert execution_authority["event_id"]
    assert execution_authority["event_sequence"] > 0
    assert execution_authority["artifact_ref"].startswith(
        "tactic_execution_results/"
    )
    assert execution_authority["submitted_tactics"] == ["wp."]
    assert execution_authority["state_changed"] is True
    assert execution_authority["history_committed"] is True
    shown = json.dumps(action["agent_observation"], sort_keys=True)
    assert "STDOUT POISON" not in shown
    assert "error_summary" not in action["agent_observation"]


def test_event_bound_partial_success_reaches_route_as_changed_attention(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / ".ec_session_partial_ter"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "commit_chain", "--keep-on-fail", "-c", "proc. bad.",
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    result = _record_tactic_invocation(
        session_dir,
        mode="commit_chain",
        command="commit_chain",
        tool_exit_code=1,
        response_override=_partial_success_commit_response(),
    )
    assert result["result"]["status"] == "partial_success"
    assert result["result"]["ok"] is False
    assert result["execution"]["state_changed"] is True
    assert result["execution"]["history_committed"] is True

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(cmd, 1, stdout="", stderr=""),
        tactic_execution_boundary=boundary,
    )
    assert action["outcome_kind"] == "partial_success"
    assert action["proof_state_effect"] == "changed"
    assert action["proof_state_changed"] is True
    assert action["needs_attention"] is True
    observation = action["agent_observation"]
    assert "committed the successful tactic prefix" in observation["result"]
    assert observation["proof_state"] == "The committed EasyCrypt proof state changed."

    manager = ProofEventManager(node_id="Tree-partial")
    route = manager.record_route_turn(
        intent="commit_tactic",
        payload={"tactic": "proc. bad."},
        actions=[action],
        observation=observation,
    )

    assert "status" not in route
    assert route["outcome_kind"] == "partial_success"
    assert route["proof_state_effect"] == "changed"
    assert route["accepted"] is True
    assert route["rejected"] is False
    assert route["changed"] is True
    assert route["needs_attention"] is True
    assert manager.events[-1].status == "partial_success"


def test_event_bound_real_undo_is_changed_and_empty_undo_is_unchanged(
    tmp_path: Path,
) -> None:
    for changed, event_status in ((True, "ok"), (False, "empty")):
        session_dir = tmp_path / f".ec_session_undo_{event_status}"
        session_dir.mkdir()
        start_event(session_dir)
        write_open_goal(session_dir)
        cmd = [
            "python3", "session_cli.py", "-d", str(session_dir),
            "-tactic-exec", "undo",
        ]
        boundary = capture_tactic_execution_invocation(
            session_dir,
            cmd,
        )
        assert boundary is not None
        result = _record_tactic_invocation(
            session_dir,
            mode="undo",
            command="undo",
            response_override=_undo_commit_response(changed=changed),
            undo_event_status=event_status,
        )

        assert result["result"]["status"] == (
            "undone" if changed else "no_progress"
        )
        assert result["execution"]["state_changed"] is changed
        assert result["execution"]["history_committed"] is changed

        action = backend_action_record(
            "undo_last_step",
            cmd,
            subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
            tactic_execution_boundary=boundary,
        )

        assert "contract_error" not in action
        assert action["proof_state_changed"] is changed


def test_event_bound_undo_rejects_ter_that_contradicts_empty_history(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / ".ec_session_undo_contradiction"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "undo",
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    _record_tactic_invocation(
        session_dir,
        mode="undo",
        command="undo",
        response_override=_undo_commit_response(changed=True),
        undo_event_status="empty",
    )

    action = backend_action_record(
        "undo_last_step",
        cmd,
        subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
        tactic_execution_boundary=boundary,
    )

    assert action["outcome_kind"] == "backend_error"
    assert "does not match the tactic.undone outcome" in action["contract_error"]


def test_real_empty_prev_cli_emits_unchanged_event_bound_ter(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / ".ec_session_real_empty_undo"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    cmd = [
        sys.executable,
        "core/easycrypt/session_cli.py",
        "-d",
        str(session_dir),
        "-tactic-exec",
        "undo",
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None

    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    action = backend_action_record(
        "undo_last_step",
        cmd,
        completed,
        tactic_execution_boundary=boundary,
    )

    assert "contract_error" not in action
    assert action["proof_state_changed"] is False
    assert action["outcome_kind"] == "no_progress"
    window = read_events(session_dir)
    undo = [event["payload"] for event in window if event["type"] == "tactic.undone"][-1]
    produced = [
        event["payload"]
        for event in window
        if event["type"] == "tactic.execution.produced"
    ][-1]
    assert undo["status"] == "empty"
    assert produced["status"] == "no_progress"
    assert produced["state_changed"] is False
    assert produced["history_committed"] is False


def test_tactic_result_for_a_different_submitted_tactic_fails_closed(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / ".ec_session_wrong_tactic"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "commit", "-c", "wp.",
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    _record_tactic_invocation(session_dir, tactic="skip.")

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
        tactic_execution_boundary=boundary,
    )

    assert action["outcome_kind"] == "backend_error"
    assert "submitted tactics do not match" in action["contract_error"]
    assert action["agent_observation"]["proof_state"] == "unknown"


def test_successful_tactic_result_cannot_override_nonzero_process_exit(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / ".ec_session_exit_mismatch"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "commit", "-c", "wp.",
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    _record_tactic_invocation(session_dir, tool_exit_code=1)

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom"),
        tactic_execution_boundary=boundary,
    )

    assert action["outcome_kind"] == "backend_error"
    assert "non-zero backend process exit code" in action["contract_error"]
    assert action["agent_observation"]["proof_state"] == "unknown"


def test_bound_tactic_rejection_carries_structured_error(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_rejected"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    tactic = "call (equ_cc _ _ _)."
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "commit", "-c", tactic,
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    _record_tactic_invocation(
        session_dir,
        status="error",
        ok=False,
        tactic=tactic,
        error="[error] cannot infer all placeholders",
    )

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(
            cmd,
            0,
            stdout='{"errors":[{"message":"WRONG STDOUT ERROR"}]}',
            stderr="",
        ),
        tactic_execution_boundary=boundary,
    )

    assert action["outcome_kind"] == "rejected"
    assert (
        action["agent_observation"]["error_summary"]
        == "[error] cannot infer all placeholders"
    )
    assert "WRONG STDOUT ERROR" not in json.dumps(action["agent_observation"])


def test_multiple_current_tactic_results_fail_closed(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_duplicate_ter"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "commit", "-c", "wp.",
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    _record_tactic_invocation(session_dir, duplicate_result_event=True)

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
        tactic_execution_boundary=boundary,
    )

    assert action["outcome_kind"] == "backend_error"
    assert "exactly one tactic.execution.produced" in action["contract_error"]


def test_daemon_rejected_marker_in_raw_excerpt_is_recovered():
    # When only the `[DAEMON_REJECTED] <reason>` line is present (no structured field),
    # recover the reason from it rather than dropping the error.
    from workflow.proof_management.backend_actions import _error_summary
    payload = {"result": {"ok": False, "status": "error", "raw_excerpt":
        "==[ L0 ]==\n[DAEMON_REJECTED] conseq: not a phl/prhl judgement\n  EC daemon rejected"}}
    assert _error_summary(payload, "", ok=False) == "conseq: not a phl/prhl judgement"


def test_bound_no_progress_result_is_not_mislabeled_as_rejected(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / ".ec_session_no_progress"
    session_dir.mkdir()
    start_event(session_dir)
    write_open_goal(session_dir)
    tactic = "inline PRPc.PseudoRP.fi."
    cmd = [
        "python3", "session_cli.py", "-d", str(session_dir),
        "-tactic-exec", "commit", "-c", tactic,
    ]
    boundary = capture_tactic_execution_invocation(
        session_dir,
        cmd,
    )
    assert boundary is not None
    _record_tactic_invocation(
        session_dir,
        status="no_progress_reverted",
        ok=False,
        tactic=tactic,
        raw_result=(
            "[TACTIC_NO_EFFECT_AUTO_REVERTED] accepted but no change"
        ),
    )

    action = backend_action_record(
        "commit_tactic",
        cmd,
        subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
        tactic_execution_boundary=boundary,
    )
    observation = action["agent_observation"]

    assert "accepted the tactic" in observation["result"]
    assert "did not change the goal" in observation["result"]
    assert "no-op" in observation["result"]
    assert "rejected" not in observation["result"].lower()
    assert "use the error summary" not in observation["result"].lower()
    assert observation.get("error_summary") is None
    assert observation["proof_state"] == (
        "The committed EasyCrypt proof state was not changed."
    )


def test_session_start_uses_workspace_contract_not_tactic_execution_contract():
    cmd = [
        "python3", "core/easycrypt/session_cli.py", "-d", "x",
        "-start", "-f", "example.ec", "-lemma", "L",
    ]
    stdout = json.dumps({
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal-hash",
        },
        "current_goal": {"lines": ["x = x"]},
    })
    action = backend_action_record(
        "start",
        cmd,
        subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=""),
    )
    assert action["outcome_kind"] == "accepted_unconfirmed"
    assert "contract_error" not in action
    assert "contract_error" not in action["agent_observation"]


def test_try_boundary_captures_exact_tactic_request(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_try_boundary"
    cmd = [
        "python3",
        "core/easycrypt/session_cli.py",
        "-d",
        str(session_dir),
        "-try",
        "-c",
        "move=> &m x.",
    ]

    boundary = capture_tactic_preflight_invocation(session_dir, cmd)

    assert boundary is not None
    assert boundary.invocation.action_name == "try"
    assert boundary.expected_tactic == "move=> &m x."
