from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow.proof_management.protocol_repair import AgentIntent
from workflow.proof_management.repl_session import ReplBackendError
from workflow.proof_management.turn_executor import ProofTurnExecutor
from workflow.proof_management.node_state import NodeTurnState


class _Snapshot:
    state_version = 3
    goal_hash = "goal"

    def to_dict(self) -> dict[str, Any]:
        return {"state_version": self.state_version, "goal_hash": self.goal_hash}


class _FakeRepl:
    state_version = 3


class _FakeEvents:
    def __init__(self) -> None:
        self.audits: list[dict[str, Any]] = []
        self.route_turns: list[dict[str, Any]] = []

    def audit(self, record: dict[str, Any]) -> None:
        self.audits.append(dict(record))

    def record_route_turn(
        self,
        *,
        intent: str,
        payload: dict[str, Any],
        actions: list[dict[str, Any]],
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "intent": intent,
            "payload": dict(payload),
            "actions": list(actions),
            "observation": dict(observation),
        }
        self.route_turns.append(record)
        return record


class _FakeLineage:
    def __init__(self) -> None:
        self.run_dir: Path | None = None
        self.turns: list[dict[str, Any]] = []

    def record_proof_turn(
        self,
        *,
        node_id: str,
        route_event: dict[str, Any],
    ) -> None:
        self.turns.append({"node_id": node_id, "route_event": route_event})


def _executor(
    tmp_path: Path,
) -> tuple[ProofTurnExecutor, NodeTurnState, _FakeEvents, _FakeLineage]:
    state = NodeTurnState(
        latest_snapshot=_Snapshot(),  # type: ignore[arg-type]
        latest_view={"last_result": {"result": "old"}},
    )
    events = _FakeEvents()
    lineage = _FakeLineage()

    def project(snapshot: _Snapshot, observation: dict[str, Any] | None) -> dict[str, Any]:
        view = {
            "proof_status": {"status": "open"},
            "last_result": observation or {"result": "projected"},
        }
        state.latest_snapshot = snapshot  # type: ignore[assignment]
        state.latest_view = view
        return view

    executor = ProofTurnExecutor(
        node_id="Tree-unit",
        state=state,
        repl=_FakeRepl(),  # type: ignore[arg-type]
        events=events,  # type: ignore[arg-type]
        lineage=lineage,  # type: ignore[arg-type]
        project=project,  # type: ignore[arg-type]
        audit=events.audit,
        surface_profile="unit",
    )
    return executor, state, events, lineage


def test_turn_executor_renders_menu_turn_without_backend_mutation(
    tmp_path: Path,
) -> None:
    executor, state, events, _ = _executor(tmp_path)

    turn = executor.menu_turn(
        AgentIntent("undo_to_checkpoint", {}),
        {"kind": "checkpoint_selection", "result": "choose"},
        label="checkpoint_selection",
        audit_kind="checkpoint_selection.requested",
    )

    assert turn.ok
    assert turn.manager_actions[0]["proof_state_effect"] == "unchanged"
    assert turn.manager_actions[0]["outcome_kind"] == "control_menu"
    assert state.latest_view["last_result"]["kind"] == "checkpoint_selection"
    assert events.audits[-1]["kind"] == "checkpoint_selection.requested"


def test_turn_executor_records_successful_repl_turn(
    tmp_path: Path,
) -> None:
    executor, _, events, lineage = _executor(tmp_path)
    snapshot = _Snapshot()

    turn = executor.repl_call(
        AgentIntent("commit_tactic", {"tactic": "wp."}),
        lambda: (
            snapshot,
            [
                {
                    "label": "commit_tactic",
                    "agent_observation": {"result": "accepted"},
                }
            ],
        ),
    )

    assert turn.ok
    assert turn.workspace_view["last_result"]["result"] == "accepted"
    assert events.route_turns[0]["intent"] == "commit_tactic"
    assert lineage.turns[0]["node_id"] == "Tree-unit"
    assert events.audits[-1]["kind"] == "agent_intent.handled"


def test_turn_executor_surfaces_backend_failure_without_projection(
    tmp_path: Path,
) -> None:
    executor, state, events, _ = _executor(tmp_path)

    turn = executor.repl_call(
        AgentIntent("commit_tactic", {"tactic": "wp."}),
        lambda: (_ for _ in ()).throw(
            ReplBackendError({
                "label": "commit_tactic",
                "exit_code": 1,
                "agent_observation": {"error_summary": "view failed"},
            })
        ),
    )

    assert not turn.ok
    assert turn.repair_prompt
    assert state.latest_view["last_result"]["intent"] == "commit_tactic"
    assert events.audits[-1]["kind"] == "manager_action.backend_failure"
