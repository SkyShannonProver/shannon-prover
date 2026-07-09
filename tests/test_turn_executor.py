from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow.proof_management import AgentIntent
from workflow.proof_management.repl_session import ReplBackendError
from workflow.proof_management.turn_executor import ProofTurnExecutor


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


class _FakeProbeAlternatives:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(
        self,
        intent: AgentIntent,
        snapshot: _Snapshot,
        observation: dict[str, Any],
    ) -> None:
        self.records.append({
            "intent": intent.intent,
            "snapshot": snapshot.to_dict(),
            "observation": dict(observation),
        })


def _executor(tmp_path: Path) -> tuple[ProofTurnExecutor, dict[str, Any], _FakeEvents, _FakeLineage, _FakeProbeAlternatives]:
    state: dict[str, Any] = {
        "snapshot": _Snapshot(),
        "view": {"last_result": {"result": "old"}},
    }
    events = _FakeEvents()
    lineage = _FakeLineage()
    probes = _FakeProbeAlternatives()

    def project(snapshot: _Snapshot, observation: dict[str, Any] | None) -> dict[str, Any]:
        view = {
            "proof_status": {"status": "open"},
            "last_result": observation or {"result": "projected"},
        }
        state["snapshot"] = snapshot
        state["view"] = view
        return view

    executor = ProofTurnExecutor(
        node_id="Tree-unit",
        repl=_FakeRepl(),
        events=events,
        lineage=lineage,  # type: ignore[arg-type]
        probe_alternatives=probes,  # type: ignore[arg-type]
        latest_snapshot=lambda: state.get("snapshot"),
        latest_view=lambda: dict(state.get("view") or {}),
        set_latest_view=lambda view: state.update({"view": dict(view)}),
        project=project,  # type: ignore[arg-type]
        audit=events.audit,
        run_dir=lambda: tmp_path,
        surface_profile="unit",
    )
    return executor, state, events, lineage, probes


def test_turn_executor_renders_menu_turn_without_backend_mutation(
    tmp_path: Path,
) -> None:
    executor, state, events, _, _ = _executor(tmp_path)

    turn = executor.menu_turn(
        AgentIntent("undo_to_checkpoint", {}),
        {"kind": "checkpoint_selection", "result": "choose"},
        label="checkpoint_selection",
        audit_kind="checkpoint_selection.requested",
    )

    assert turn.ok
    assert turn.manager_actions[0]["proof_state_effect"] == "selection_menu_only"
    assert state["view"]["last_result"]["kind"] == "checkpoint_selection"
    assert events.audits[-1]["kind"] == "checkpoint_selection.requested"


def test_turn_executor_records_successful_repl_turn(
    tmp_path: Path,
) -> None:
    executor, _, events, lineage, probes = _executor(tmp_path)
    snapshot = _Snapshot()

    turn = executor.repl_call(
        AgentIntent("probe_tactic", {"tactic": "wp."}),
        lambda: (
            snapshot,
            [
                {
                    "label": "probe_tactic",
                    "agent_observation": {"result": "accepted"},
                }
            ],
        ),
    )

    assert turn.ok
    assert turn.workspace_view["last_result"]["result"] == "accepted"
    assert events.route_turns[0]["intent"] == "probe_tactic"
    assert lineage.turns[0]["node_id"] == "Tree-unit"
    assert probes.records[0]["intent"] == "probe_tactic"
    assert events.audits[-1]["kind"] == "agent_intent.handled"


def test_turn_executor_surfaces_backend_failure_without_projection(
    tmp_path: Path,
) -> None:
    executor, state, events, _, _ = _executor(tmp_path)

    turn = executor.repl_call(
        AgentIntent("inspect_context", {"topic": "goal_info"}),
        lambda: (_ for _ in ()).throw(
            ReplBackendError({
                "label": "agent_view",
                "exit_code": 1,
                "agent_observation": {"error_summary": "view failed"},
            })
        ),
    )

    assert not turn.ok
    assert turn.repair_prompt
    assert state["view"]["last_result"]["intent"] == "inspect_context"
    assert events.audits[-1]["kind"] == "manager_action.backend_failure"
