from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

# Agent-facing observations must never mention any resume/floor/prefix concept.
_RESUME_LEAK_RE = re.compile(
    r"crosses_resume_floor|resume_start|resume_local|resume handoff|"
    r"verified.*prefix|resume floor|resume boundary",
    re.IGNORECASE,
)

from workflow.proof_management import (  # noqa: E402
    ProofStateSnapshot,
    ReplBackendError,
    ReplBackendTimeout,
    ReplSessionManager,
)
from workflow.proof_node_manager import (  # noqa: E402
    ProofNodeManager,
)
from workflow.proof_management.backend_actions import (  # noqa: E402
    agent_observation_from_command,
    backend_action_record as _backend_action_record,
)
from workflow.proof_management import AgentIntent, parse_agent_intent  # noqa: E402
from tests.helpers.builders import make_manager  # noqa: E402


def _control_items(observation: dict) -> list[dict]:
    return observation["control_menu"]["items"]


def _control_notice(observation: dict) -> str:
    return observation["control_menu"]["notice"]


def _current_workspace_view(**overrides) -> dict:
    """Complete v3 workspace fixture for paths that enter manager projection."""

    view = {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal",
            "remaining_goals_known": True,
        },
        "current_goal": {"lines": []},
        "view_hash": "v" * 40,
    }
    proof_status = dict(view["proof_status"])
    status_overrides = overrides.pop("proof_status", {})
    proof_status.update(status_overrides)
    if proof_status.get("status") in {
        "session_closed_pending_verification",
        "goals_discharged_pending_qed",
        "closed",
        "complete",
        "verified",
    } and "goal_identity_required" not in status_overrides:
        proof_status["goal_identity_required"] = False
        proof_status.pop("goal_hash", None)
    view.update(overrides)
    view["proof_status"] = proof_status
    return view


def _write_managed_session_meta(
    project_root: Path,
    session_dir: str = ".ec_session_unit",
) -> None:
    path = project_root / session_dir
    path.mkdir(parents=True, exist_ok=True)
    (path / "session_meta.json").write_text(
        json.dumps({
            "file": "eval/examples/SchnorrPK.ec",
            "lemma": "dummy",
        }),
        encoding="utf-8",
    )


def _current_bootstrap(
    *,
    workspace_view: dict,
    snapshot: dict | None = None,
    replay_prefix: list[str] | None = None,
    session_dir: str = ".ec_session_unit",
) -> dict:
    current_snapshot = {
        "node_id": "Tree-unit",
        "session_tag": "unit",
        "session_dir": session_dir,
        "session_epoch": 0,
        "state_version": 0,
        "goal_hash": "goal",
        "goal_identity_required": True,
        "workspace_view_artifact": "",
        "execution_refs": {},
    }
    current_snapshot.update(snapshot or {})
    if snapshot is not None and "goal_identity_required" not in snapshot:
        current_snapshot["goal_identity_required"] = bool(
            current_snapshot["goal_hash"]
        )
    prefix = list(replay_prefix or [])
    return {
        "schema_version": 3,
        "kind": "proof_node_manager_bootstrap",
        "node_id": "Tree-unit",
        "session_tag": "unit",
        "session_dir": session_dir,
        "file": "eval/examples/SchnorrPK.ec",
        "lemma": "dummy",
        "include_dirs": ["eval/examples", "easycrypt-src/theories"],
        "replay_prefix_count": len(prefix),
        "replay_prefix": prefix,
        "replay_prefix_requested_count": len(prefix),
        "manager_actions": [],
        "snapshot": current_snapshot,
        "workspace_view": workspace_view,
    }


def test_repl_captures_tactic_preflight_boundary_before_backend_process(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The event offset must be sampled before the CLI can append this call's events."""
    import workflow.proof_management.repl_session as repl_module

    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="freshness",
        node_id="Tree-freshness",
        project_root=tmp_path,
    )
    order: list[str] = []
    boundary = object()

    def capture(session_dir, cmd):
        order.append("capture")
        assert session_dir == tmp_path / ".ec_session_freshness"
        assert cmd[-3:] == ["-try", "-c", "move=> &m x."]
        return boundary

    def run(*_args, **_kwargs):
        order.append("run")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    def record(label, cmd, result, duration_ms, **kwargs):
        order.append("record")
        assert kwargs["tactic_preflight_boundary"] is boundary
        return {"label": label, "exit_code": result.returncode}

    monkeypatch.setattr(repl_module, "capture_tactic_preflight_invocation", capture)
    monkeypatch.setattr(repl_module.subprocess, "run", run)
    monkeypatch.setattr(repl_module, "backend_action_record", record)
    monkeypatch.setattr(manager, "_env", lambda: {})

    actions: list[dict] = []
    manager._run_backend(
        "exact_tactic_preflight",
        ["-try", "-c", "move=> &m x."],
        actions=actions,
        timeout=10,
    )

    assert order == ["capture", "run", "record"]
    assert actions == [{"label": "exact_tactic_preflight", "exit_code": 0}]


def test_read_only_tactic_preflight_uses_exact_try_without_refresh(
    tmp_path: Path,
) -> None:
    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="try-unit",
        node_id="Tree-try-unit",
        project_root=tmp_path,
    )
    calls: list[tuple[str, list[str], int]] = []

    def run(
        label: str,
        args: list[str],
        *,
        actions: list[dict],
        timeout: int,
    ) -> None:
        calls.append((label, list(args), timeout))
        actions.append({"label": label, "exit_code": 0})

    manager._run_backend = run  # type: ignore[method-assign]

    result = manager.read_only_tactic_preflight("move=> &m x.", timeout=17)

    assert calls == [(
        "exact_tactic_preflight",
        ["-try", "-c", "move=> &m x."],
        17,
    )]
    assert result == {
        "label": "exact_tactic_preflight",
        "exit_code": 0,
    }
    assert manager.state_version == 0


def test_repl_captures_tactic_execution_boundary_before_backend_process(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import workflow.proof_management.repl_session as repl_module

    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="tactic-boundary",
        node_id="Tree-tactic-boundary",
        project_root=tmp_path,
    )
    order: list[str] = []
    boundary = object()

    def capture(session_dir, cmd):
        order.append("capture")
        assert session_dir == tmp_path / ".ec_session_tactic-boundary"
        assert cmd[-4:] == ["-tactic-exec", "commit", "-c", "wp."]
        return boundary

    def run(*_args, **_kwargs):
        order.append("run")
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

    def record(label, cmd, result, duration_ms, **kwargs):
        order.append("record")
        assert kwargs["tactic_execution_boundary"] is boundary
        return {"label": label, "exit_code": result.returncode}

    monkeypatch.setattr(
        repl_module,
        "capture_tactic_execution_invocation",
        capture,
    )
    monkeypatch.setattr(repl_module.subprocess, "run", run)
    monkeypatch.setattr(repl_module, "backend_action_record", record)
    monkeypatch.setattr(manager, "_env", lambda: {})

    actions: list[dict] = []
    manager._run_backend(
        "commit_tactic",
        ["-tactic-exec", "commit", "-c", "wp."],
        actions=actions,
        timeout=10,
    )

    assert order == ["capture", "run", "record"]
    assert actions == [{"label": "commit_tactic", "exit_code": 0}]


@pytest.mark.parametrize("retired_flag", ["-next", "-prev", "-chain"])
def test_repl_rejects_retired_tactic_mutation_flags(
    tmp_path: Path,
    retired_flag: str,
) -> None:
    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="retired-tactic-flag",
        node_id="Tree-retired-tactic-flag",
        project_root=tmp_path,
    )
    args = [retired_flag]
    if retired_flag != "-prev":
        args.extend(["-c", "wp."])

    with pytest.raises(ValueError, match="only through -tactic-exec"):
        manager._run_backend(
            "retired_tactic_action",
            args,
            actions=[],
            timeout=10,
        )


def test_repl_fails_closed_on_zero_exit_backend_contract_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import workflow.proof_management.repl_session as repl_module

    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="contract",
        node_id="Tree-contract",
        project_root=tmp_path,
    )
    monkeypatch.setattr(
        repl_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="raw poison", stderr="",
        ),
    )
    monkeypatch.setattr(
        repl_module,
        "backend_action_record",
        lambda *_args, **_kwargs: {
            "label": "exact_tactic_preflight",
            "exit_code": 0,
            "outcome_kind": "backend_error",
            "contract_error": "missing current tactic preflight",
        },
    )
    monkeypatch.setattr(manager, "_env", lambda: {})

    actions: list[dict] = []
    with pytest.raises(ReplBackendError):
        manager._run_backend(
            "exact_tactic_preflight",
            ["-try", "-c", "move=> &m x."],
            actions=actions,
            timeout=10,
        )
    assert actions[-1]["contract_error"] == "missing current tactic preflight"


def test_agent_intent_schema_is_proof_level_only() -> None:
    parsed = parse_agent_intent(
        '{"intent": "commit_tactic", "payload": {"tactic": "byequiv=>//."}}'
    )

    assert parsed.ok is True
    assert parsed.intent is not None
    data = parsed.intent.to_dict()
    assert data == {
        "intent": "commit_tactic",
        "payload": {"tactic": "byequiv=>//."},
    }
    for forbidden in (
        "node_id",
        "view_hash",
        "goal_hash",
        "state_version",
        "request_id",
        "reason",
    ):
        assert forbidden not in data


def test_malformed_intent_repairs_without_killing_node() -> None:
    manager = make_manager()
    manager.latest_view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["x = y"]},
    }

    turn = manager.handle_agent_message("I will try smt() next.")

    assert turn.ok is False
    assert turn.workspace_view["current_goal"]["lines"] == ["x = y"]
    assert "exactly one JSON object" in turn.repair_prompt
    assert turn.health_event is None


def test_repeated_malformed_intent_stays_recoverable() -> None:
    # Regression: three consecutive empty/malformed intents (observed near the
    # finish line of several L4 runs) must NOT brick the node. A malformed intent
    # is a recoverable no-op — the manager re-issues the latest view with a
    # corrective nudge and never emits a terminal `agent_protocol_stuck` health
    # event, so the runtime bridge keeps re-prompting instead of wedging.
    manager = make_manager()
    manager.latest_view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["x = y"]},
    }

    turns = [
        manager.handle_agent_message("bad one"),
        manager.handle_agent_message(""),  # empty {} intent
        manager.handle_agent_message("{}"),
    ]

    for turn in turns:
        assert turn.ok is False
        # Node stays live across every malformed turn — no terminal health event.
        assert turn.health_event is None
        # The latest workspace view is re-issued so the agent can recover.
        assert turn.workspace_view["current_goal"]["lines"] == ["x = y"]
        assert "JSON" in turn.repair_prompt

    # The corrective nudge escalates once a streak forms: the later turns name the
    # streak and frame it as a recoverable no-op, the first does not.
    assert "no valid proof intent" not in turns[0].repair_prompt
    assert "no valid proof intent" in turns[-1].repair_prompt
    assert "recoverable no-op" in turns[-1].repair_prompt


def test_valid_intent_resets_malformed_streak() -> None:
    # A valid intent after malformed ones clears the streak so a later malformed
    # intent starts over with the plain (non-escalated) nudge — preserving the
    # exact behavior for valid intents.
    manager = make_manager()
    manager.latest_view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["x = y"]},
    }

    manager.handle_agent_message("bad one")
    manager.handle_agent_message("bad two")
    assert manager.malformed_count == 2

    # A valid proof-control intent resets the streak counter.
    manager.handle_agent_message(
        '{"intent": "finish", "payload": {}}'
    )
    assert manager.malformed_count == 0

    # The next malformed intent is back to the plain, first-strike nudge.
    turn = manager.handle_agent_message("bad again")
    assert turn.health_event is None
    assert "no valid proof intent" not in turn.repair_prompt


def test_adopt_bootstrap_seeds_latest_view_without_restart() -> None:
    manager = make_manager()

    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["Current goal", "x = y"]},
        ),
        snapshot={
            "session_epoch": 4,
            "state_version": 7,
            "goal_hash": "goal",
        },
    ))
    turn = manager.handle_agent_message("not json")

    assert turn.ok is False
    assert turn.workspace_view["current_goal"]["lines"] == ["Current goal", "x = y"]
    assert manager.repl.state_version == 7
    assert manager.repl.session_epoch == 4


def test_backend_timeout_returns_latest_view_with_health_event() -> None:
    manager = make_manager()
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["Current goal", "x = y"]},
        ),
        snapshot={
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "goal",
        },
    ))

    def timeout(_intent):
        raise ReplBackendTimeout({
            "label": "commit_tactic",
            "timed_out": True,
            "timeout_seconds": 180,
            "mutates_proof_state": True,
        })

    manager.repl.handle_intent = timeout  # type: ignore[method-assign]
    turn = manager.handle_agent_message(
        '{"intent": "commit_tactic", "payload": {"tactic": "inline *."}}'
    )

    assert turn.ok is False
    assert turn.workspace_view["current_goal"]["lines"] == ["Current goal", "x = y"]
    assert turn.health_event is not None
    assert turn.health_event.status == "manager_action_timeout"
    assert "proof state may be uncertain" in turn.health_event.message
    assert turn.manager_actions[0]["timed_out"] is True


def test_admit_is_not_preflight_clarified() -> None:
    # `admit` is not intercepted by preflight. The manager instead gates
    # finish/qed while committed admits remain.
    from workflow.proof_management.intent_preflight import preflight_intent

    view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "proof_status": {"status": "open"},
    }
    decision = preflight_intent(
        intent=AgentIntent(intent="commit_tactic", payload={"tactic": "admit."}),
        latest_view=view,
        surface_profile=None,
    )
    assert decision.should_handle is False, "admit must not be intercepted"
    assert decision.audit_kind != "agent_intent.admit_clarification"


def test_qed_tactic_requires_closed_candidate_view() -> None:
    manager = make_manager()
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["Current goal", "x = y"]},
            proof_status={"status": "open"},
        ),
        snapshot={
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "goal",
        },
    ))
    backend_calls: list[str] = []

    def handled(_intent):
        backend_calls.append("called")
        raise AssertionError("qed must not reach backend while goal is open")

    manager.repl.handle_intent = handled  # type: ignore[method-assign]

    turn = manager.handle_agent_message(
        '{"intent": "commit_tactic", "payload": {"tactic": "qed."}}'
    )

    assert turn.ok is False
    assert turn.health_event is None
    assert backend_calls == []
    assert turn.manager_actions[0]["label"] == "qed_clarification"
    assert "did not execute `qed.`" in turn.workspace_view["last_result"]["result"]
    assert "goals_discharged_pending_qed" in turn.repair_prompt


def test_qed_tactic_allowed_when_view_is_closed_candidate() -> None:
    manager = make_manager()
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["No more goals"]},
            proof_status={"status": "goals_discharged_pending_qed"},
        ),
        snapshot={
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "",
            "goal_identity_required": False,
        },
    ))
    backend_calls: list[str] = []

    def handled(intent):
        backend_calls.append(intent.payload["tactic"])
        return (
            ProofStateSnapshot(
                node_id="Tree-unit",
                session_tag="unit",
                session_dir=".ec_session_unit",
                session_epoch=1,
                state_version=4,
                goal_hash="",
                goal_identity_required=False,
                raw_workspace_view=_current_workspace_view(
                    current_goal={"lines": ["No more goals"]},
                    proof_status={"status": "session_closed_pending_verification"},
                ),
            ),
            [{"label": "commit_tactic", "agent_observation": {"result": "ok"}}],
        )

    manager.repl.handle_intent = handled  # type: ignore[method-assign]

    turn = manager.handle_agent_message(
        '{"intent": "commit_tactic", "payload": {"tactic": "qed."}}'
    )

    assert turn.ok is True
    assert backend_calls == ["qed."]


def test_finish_requires_qed_when_candidate_is_pending_save() -> None:
    manager = make_manager()
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["No more goals", "[25|check]>"]},
            proof_status={"status": "goals_discharged_pending_qed"},
        ),
        snapshot={
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "",
            "goal_identity_required": False,
        },
    ))
    backend_calls: list[str] = []

    def handled(_intent):
        backend_calls.append("called")
        raise AssertionError("finish must not reach backend while qed is pending")

    manager.repl.handle_intent = handled  # type: ignore[method-assign]

    turn = manager.handle_agent_message('{"intent": "finish", "payload": {}}')

    assert turn.ok is False
    assert turn.health_event is None
    assert backend_calls == []
    assert turn.manager_actions[0]["label"] == "finish_requires_qed"
    assert turn.manager_actions[0]["mutates_proof_state"] is False
    menu = turn.workspace_view["last_result"]["control_menu"]
    assert menu["items"][0]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "qed."},
    }
    assert turn.manager_actions[0]["needs_attention"] is True
    last = turn.workspace_view["last_result"]
    assert last["intent"] == "finish"
    assert last["kind"] == "finish_requires_qed"
    assert last["outcome_kind"] == "control_menu"
    assert "manager_action" not in last
    assert "next_intent" not in last


def test_finish_allowed_after_qed_is_saved() -> None:
    manager = make_manager()
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(
            current_goal={
                "lines": [
                    "No active goal: proof candidate was closed and `qed.` was saved.",
                ],
            },
            proof_status={"status": "session_closed_pending_verification"},
        ),
        snapshot={
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "",
            "goal_identity_required": False,
        },
    ))
    backend_calls: list[str] = []

    def handled(intent):
        backend_calls.append(intent.intent)
        return (
            ProofStateSnapshot(
                node_id="Tree-unit",
                session_tag="unit",
                session_dir=".ec_session_unit",
                session_epoch=1,
                state_version=4,
                goal_hash="",
                goal_identity_required=False,
                raw_workspace_view=_current_workspace_view(
                    current_goal={"lines": ["saved"]},
                    proof_status={"status": "session_closed_pending_verification"},
                ),
            ),
            [{"label": "finish", "agent_observation": {"result": "finished"}}],
        )

    manager.repl.handle_intent = handled  # type: ignore[method-assign]

    turn = manager.handle_agent_message('{"intent": "finish", "payload": {}}')

    assert turn.ok is True
    assert backend_calls == ["finish"]


def test_repl_finish_action_has_explicit_terminal_observation(tmp_path: Path) -> None:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
        project_root=tmp_path,
    )
    snapshot = ProofStateSnapshot(
        node_id="Tree-unit",
        session_tag="unit",
        session_dir=".ec_session_unit",
        session_epoch=1,
        state_version=4,
        goal_hash="",
        goal_identity_required=False,
        raw_workspace_view=_current_workspace_view(
            current_goal={},
            proof_status={"status": "session_closed_pending_verification"},
        ),
    )
    repl._snapshot_from_managed_goal_view = (  # type: ignore[method-assign]
        lambda *, actions: snapshot
    )

    returned, actions = repl.handle_intent(AgentIntent("finish", {}))

    assert returned is snapshot
    finish = actions[0]
    assert finish["label"] == "finish"
    assert finish["outcome_kind"] == "accepted"
    assert finish["proof_state_effect"] == "unchanged"
    assert finish["agent_observation"]["kind"] == "finish_accepted"
    assert "Finish accepted" in finish["agent_observation"]["result"]


def test_repl_start_replays_prefix_with_step_actions(tmp_path: Path) -> None:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
        project_root=tmp_path,
    )
    _write_managed_session_meta(tmp_path)
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(label, args, *, actions, timeout):  # noqa: ANN001
        calls.append((label, list(args)))
        if label == "managed_goal_view":
            return _current_workspace_view(
                current_goal={"lines": ["g"]},
            )
        return '{"ok": true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]

    repl.start(replay_prefix=["byequiv=>//.", "proc."])

    assert calls[1] == (
        "replay_prefix_step_1",
        ["-tactic-exec", "commit", "-c", "byequiv=>//."],
    )
    assert calls[2] == (
        "replay_prefix_step_2",
        ["-tactic-exec", "commit", "-c", "proc."],
    )


def test_fresh_restart_intent_restarts_current_node_with_force_restart(
    tmp_path: Path,
) -> None:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
        project_root=tmp_path,
    )
    _write_managed_session_meta(tmp_path)
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(label, args, *, actions, timeout):  # noqa: ANN001
        calls.append((label, list(args)))
        actions.append({"label": label, "exit_code": 0})
        if label == "managed_goal_view":
            return _current_workspace_view(
                current_goal={"lines": ["fresh"]},
            )
        return '{"ok": true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]

    snapshot, actions = repl.handle_intent(AgentIntent("fresh_restart", {}))

    restart_args = dict(calls)["fresh_restart"]
    assert restart_args[:2] == ["-start", "--force-restart"]
    assert restart_args[-2:] == ["-lemma", "dummy"]
    assert "replay_prefix" not in dict(calls)
    assert snapshot.session_epoch == 1
    assert snapshot.raw_workspace_view["current_goal"]["lines"] == ["fresh"]
    assert actions[0]["label"] == "fresh_restart"


def _manager_with_view(tmp_path: Path) -> ProofNodeManager:
    manager = make_manager()
    manager.repl.session_dir = str(tmp_path / "session")
    Path(manager.repl.session_dir).mkdir(parents=True, exist_ok=True)
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(
            current_goal={"lines": ["Current goal", "x = y"]},
            proof_status={"status": "open"},
        ),
        snapshot={
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "goal",
        },
        session_dir=manager.repl.session_dir,
    ))
    return manager


def _record_route_event_facts(
    manager: ProofNodeManager,
    events: list[dict[str, object]],
) -> None:
    for event in events:
        if event.get("rejected") is True:
            verdict = {
                "outcome_kind": "rejected",
                "proof_state_effect": "unchanged",
                "needs_attention": True,
                "accepted": False,
                "rejected": True,
                "changed": False,
            }
        elif event.get("accepted") is True:
            changed = event.get("changed") is True
            verdict = {
                "outcome_kind": "accepted",
                "proof_state_effect": "changed" if changed else "unchanged",
                "needs_attention": False,
                "accepted": True,
                "rejected": False,
                "changed": changed,
            }
        else:
            verdict = {
                "outcome_kind": "unknown",
                "proof_state_effect": "unknown",
                "needs_attention": False,
                "accepted": False,
                "rejected": False,
                "changed": False,
            }
        current = {**verdict, **event}
        manager.events.record_route_event(current)


def test_parser_accepts_negotiated_rewind_and_restart_intents() -> None:
    for text in (
        '{"intent":"amend_and_replay","payload":{}}',
        '{"intent":"amend_and_replay","payload":{"index":2,"tactic":"wp."}}',
        '{"intent":"undo_to_checkpoint","payload":{}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_0123456789abcdef"}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_0123456789abcdef","confirm":true,"confirmation_id":"abc"}}',
        '{"intent":"undo_to_checkpoint","payload":{"restore_id":"restore_abc"}}',
        '{"intent":"fresh_restart","payload":{}}',
        '{"intent":"fresh_restart","payload":{"confirm":true,"confirmation_id":"abc"}}',
    ):
        parsed = parse_agent_intent(text)
        assert parsed.ok is True


def test_amend_and_replay_menu_survives_manager_contract(tmp_path: Path) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text("proc.\nwp.\n", encoding="utf-8")

    turn = manager.handle_agent_message(
        '{"intent":"amend_and_replay","payload":{}}'
    )

    assert turn.ok is True
    assert turn.manager_actions[0]["proof_state_effect"] == "unchanged"
    assert turn.manager_actions[0]["outcome_kind"] == "control_menu"
    last = turn.workspace_view["last_result"]
    assert last["kind"] == "amend_selection"
    assert _control_notice(last) == (
        "Choose a committed tactic and provide a concrete replacement. "
        "No proof state changed."
    )
    assert [item["committed_tactic"] for item in _control_items(last)] == [
        "proc.",
        "wp.",
    ]
    second = _control_items(last)[1]
    assert second["requires_input"] == ["tactic"]
    assert second["submit"] == {
        "intent": "amend_and_replay",
        "payload": {"index": 2},
    }


def test_fresh_restart_menu_does_not_call_backend_or_surface_mutation_metadata(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)

    def fail_backend(_intent):
        raise AssertionError("fresh_restart menu must not call backend")

    manager.repl.handle_intent = fail_backend  # type: ignore[method-assign]
    turn = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')

    assert turn.ok is True
    assert turn.manager_actions[0]["proof_state_effect"] == "unchanged"
    assert turn.manager_actions[0]["outcome_kind"] == "control_menu"
    last = turn.workspace_view["last_result"]
    assert last["kind"] == "fresh_restart_confirmation"
    assert "Fresh restart erases" in _control_notice(last)
    assert "result" not in last
    assert "mutates_proof_state" not in last
    assert "proof state was not changed" not in str(last).lower()
    assert _control_items(last)[-1]["submit"]["intent"] == "fresh_restart"
    assert _control_items(last)[-1]["submit"]["payload"]["confirm"] is True
    # Menu order after 82d92bfa3 dropped the "Continue current branch"
    # option: lighter undo choices first, destructive restart last.
    assert _control_items(last)[0]["submit"] == {
        "intent": "undo_last_step",
        "payload": {},
    }
    assert _control_items(last)[1]["submit"] == {
        "intent": "undo_to_checkpoint",
        "payload": {},
    }


def test_request_restart_is_unknown_intent_and_does_not_mutate(tmp_path: Path) -> None:
    manager = _manager_with_view(tmp_path)

    def fail_backend(_intent):
        raise AssertionError("unknown request_restart must not call backend")

    manager.repl.handle_intent = fail_backend  # type: ignore[method-assign]
    turn = manager.handle_agent_message('{"intent":"request_restart","payload":{}}')

    assert turn.ok is False
    assert turn.manager_actions == []
    assert turn.repair_prompt
    assert "exactly one JSON object" in turn.repair_prompt
    assert manager.malformed_count == 1


def test_invalid_fresh_restart_confirmation_returns_menu_without_mutation(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)

    def fail_fresh_restart():
        raise AssertionError("invalid confirmation must not restart")

    manager.repl.fresh_restart = fail_fresh_restart  # type: ignore[method-assign]
    turn = manager.handle_agent_message(
        '{"intent":"fresh_restart","payload":{"confirm":true,"confirmation_id":"bad"}}'
    )

    assert turn.ok is True
    assert turn.workspace_view["last_result"]["kind"] == "fresh_restart_confirmation"


def test_repeated_bare_fresh_restart_only_shows_menu_without_mutation(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)

    def fail_fresh_restart():
        raise AssertionError("bare fresh_restart must not restart")

    manager.repl.fresh_restart = fail_fresh_restart  # type: ignore[method-assign]

    first = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')
    second = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')

    assert first.ok is True
    assert second.ok is True
    assert first.workspace_view["last_result"]["kind"] == "fresh_restart_confirmation"
    assert second.workspace_view["last_result"]["kind"] == "fresh_restart_confirmation"


def test_confirmed_fresh_restart_calls_backend_after_menu(tmp_path: Path) -> None:
    manager = _manager_with_view(tmp_path)
    menu = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')
    confirmation_id = _control_items(menu.workspace_view["last_result"])[-1]["submit"][
        "payload"
    ]["confirmation_id"]
    calls: list[str] = []

    def fake_restart():
        calls.append("fresh_restart")
        snapshot = ProofStateSnapshot(
            node_id="Tree-unit",
            session_tag="unit",
            session_dir=manager.repl.session_dir,
            session_epoch=2,
            state_version=4,
            goal_hash="fresh",
            goal_identity_required=True,
            raw_workspace_view=_current_workspace_view(
                current_goal={"lines": ["fresh"]},
                proof_status={"status": "open"},
            ),
        )
        return snapshot, [{"label": "fresh_restart", "exit_code": 0}]

    manager.repl.fresh_restart = fake_restart  # type: ignore[method-assign]
    turn = manager.handle_agent_message(json.dumps({
        "intent": "fresh_restart",
        "payload": {"confirm": True, "confirmation_id": confirmation_id},
    }))

    assert calls == ["fresh_restart"]
    assert turn.ok is True
    assert turn.workspace_view["last_result"]["kind"] == "fresh_restart_confirmed"
    assert turn.workspace_view["current_goal"]["lines"] == ["fresh"]


def test_resume_checkpoint_menu_offers_prefix_steps_as_ordinary(
    tmp_path: Path,
) -> None:
    # Transparent resume: the agent perceives one continuous proof it owns. The
    # replayed-prefix steps (here idx 1..3) surface as ORDINARY checkpoints with
    # NO "Return to resume start" / "verified replay prefix" framing, and the
    # whole menu is free of any resume/floor/prefix concept.
    manager = _manager_with_view(tmp_path)
    manager._replay_prefix_count = 3
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "\n".join([
            "byphoare (_: true ==> _) => //.",
            "proc.",
            "seq 24 : (G3.a \\in G3.cilog).",
            "seq 1 : (has (fun ci => ci.`1 = g ^ G1.u) G3.cilog /\\ size G3.cilog <= PKE_.qD) (PKE_.qD%r / order%r) ((PKE_.qD%r / order%r) ^ 2) 1%r 0%r.",
            "by rnd; skip; smt(dt_ll).",
        ])
        + "\n",
        encoding="utf-8",
    )

    turn = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')

    last = turn.workspace_view["last_result"]
    options = _control_items(last)
    # No resume-start option, no resume concept anywhere in the agent-facing menu.
    assert all(item.get("label") != "Return to resume start" for item in options)
    assert not _RESUME_LEAK_RE.search(json.dumps(last)), last
    # The in-prefix seq boundary at idx 3 is an ordinary rewindable checkpoint.
    seq_option = next(item for item in options if item["tactic_index"] == 3)
    assert seq_option["submit"]["payload"]["checkpoint_id"].startswith("cp_3_")
    assert seq_option["submit"]["intent"] == "undo_to_checkpoint"


def test_product_budget_seq_checkpoint_gets_semantic_label(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "proc.\n"
        "seq 1 : (has (fun ci => ci.`1 = g ^ G1.u) G3.cilog /\\ size G3.cilog <= PKE_.qD) (PKE_.qD%r / order%r) ((PKE_.qD%r / order%r) ^ 2) 1%r 0%r.\n"
        "rnd; skip.\n",
        encoding="utf-8",
    )

    turn = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')

    product = next(
        option
        for option in _control_items(turn.workspace_view["last_result"])
        if option["tactic_index"] == 2
    )
    assert product["label"] == "Before product-budget seq cut #2"
    assert product["after_rewind_next"] == (
        "Choose the continuation from the restored goal."
    )
    assert product["repair_use_when"] == (
        "Use this to reconsider this committed sequence cut."
    )


def test_resume_fresh_restart_blocks_agent_destructive_restart(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    manager._replay_prefix_count = 2
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text("a.\nb.\nc.\n", encoding="utf-8")
    menu = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')
    last = menu.workspace_view["last_result"]
    assert all(
        option["submit"]["intent"] != "fresh_restart"
        for option in _control_items(last)
    )
    assert any(
        option["submit"]["intent"] == "undo_to_checkpoint"
        for option in _control_items(last)
    )

    calls: list[str] = []

    def fail_restart():
        calls.append("fresh_restart")
        raise AssertionError("resume restart is agent-disabled")

    manager.repl.fresh_restart = fail_restart  # type: ignore[method-assign]
    turn = manager.handle_agent_message(json.dumps({
        "intent": "fresh_restart",
            "payload": {
                "confirm": True,
                "confirmation_id": "agent-copied-or-stale",
            },
    }))

    assert calls == []
    last = turn.workspace_view["last_result"]
    assert last["kind"] == "fresh_restart_confirmation"
    assert "Fresh restart inside this node is disabled" in _control_notice(last)
    # The notice (and whole observation) carries no resume/prefix framing.
    assert not _RESUME_LEAK_RE.search(json.dumps(last)), last
    assert all(
        option["submit"]["intent"] != "fresh_restart"
        for option in _control_items(last)
    )
    assert manager._replay_prefix_count == 2


def test_undo_to_checkpoint_menu_surfaces_committed_tactics(tmp_path: Path) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "\n".join([
            "byequiv=>//.",
            "proc.",
            "inline *.",
            "wp.",
            "call (_: ={glob A}).",
            "sp.",
        ])
        + "\n",
        encoding="utf-8",
    )

    turn = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')

    last = turn.workspace_view["last_result"]
    assert last["kind"] == "checkpoint_selection"
    assert _control_notice(last) == "Choose the committed tactic you want to rewind before."
    assert "result" not in last
    assert "mutates_proof_state" not in last
    option = _control_items(last)[0]
    assert option["semantic_id"] == "after_call_opened"
    assert option["committed_tactic"] == "sp."
    assert option["tactic_index"] == 6
    assert option["repair_use_when"] == (
        "Use this to reconsider this committed structural step."
    )
    assert option["after_rewind_next"] == (
        "Choose the continuation from the restored goal."
    )
    assert option["effect_if_selected"] == (
        "This will undo committed tactic #6 and every committed tactic after it in this node."
    )
    assert option["submit"]["intent"] == "undo_to_checkpoint"
    call_option = next(
        item for item in _control_items(last)
        if item["committed_tactic"].startswith("call (_:")
    )
    assert "call invariant introduction point" in call_option["why_checkpoint"]
    assert call_option["repair_use_when"] == (
        "Use this to reconsider this committed call invariant."
    )
    assert call_option["after_rewind_next"] == (
        "Choose the continuation from the restored goal."
    )


def test_checkpoint_menu_keeps_outer_structural_boundaries(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "\n".join([
            "byequiv=>//.",
            "proc.",
            "seq 5 3: (outer_event).",
            "sp 4 2.",
            "call (_: inv0).",
            "inline init0.",
            "sp 1 1.",
            "wp.",
            "call (_: inv1).",
            "inline init1.",
            "sp 1 1.",
            "call (_: inv2).",
            "inline init2.",
            "sp 1 1.",
            "call (_: inv3).",
            "proc.",
            "sp.",
            "if.",
            "smt().",
            "wp.",
            "inline enc.",
            "wp; sp.",
            "inline set_bad1.",
            "sp.",
            "inline cc.",
            "sp.",
            "inline EncRnd.cc.",
            "seq 1 1: (inner_midpoint).",
            "while (loop_inv).",
            "auto; smt().",
            "sp.",
            "wp.",
            "rnd.",
            "wp.",
            "rnd.",
            "skip => />.",
            "rewrite /check_plaintext.",
            "smt().",
            "move=> H.",
            "smt().",
            "inline *.",
            "wp; auto => />.",
            "smt().",
        ])
        + "\n",
        encoding="utf-8",
    )

    turn = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')

    options = _control_items(turn.workspace_view["last_result"])
    indices = {item["tactic_index"] for item in options}
    assert {5, 9, 12, 15, 28, 29}.issubset(indices)
    assert len(options) <= 12
    outer = next(item for item in options if item["tactic_index"] == 5)
    assert outer["label"] == "Before call invariant #5"
    assert outer["undo_scope"] == "structural_boundary"


def test_outer_call_rewind_requires_confirmation_and_restore_anchor(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    tactics = [
        "byequiv=>//.",
        "call (_: outer_inv).",
        "wp.",
        "call (_: inner_inv).",
        "wp.",
        "smt().",
    ]
    history.write_text("\n".join(tactics) + "\n", encoding="utf-8")
    checkpoint_id = "cp_2_" + hashlib.sha1(
        "\n".join(tactics).encode("utf-8")
    ).hexdigest()[:16]

    rewinds: list[int] = []

    def fake_rewind(tactic_index: int):  # noqa: ANN001
        rewinds.append(tactic_index)
        history.write_text(
            "\n".join(tactics[: max(0, tactic_index - 1)]) + "\n",
            encoding="utf-8",
        )
        return (
            _route_snapshot(manager, "Current goal\nafter rewind"),
            [{"label": "undo_to_checkpoint", "exit_code": 0}],
        )

    manager.repl.rewind_before_tactic = fake_rewind  # type: ignore[method-assign]

    turn = manager.handle_agent_message(json.dumps({
        "intent": "undo_to_checkpoint",
        "payload": {"checkpoint_id": checkpoint_id},
    }))

    last = turn.workspace_view["last_result"]
    assert last["kind"] == "checkpoint_rewind_confirmation"
    assert rewinds == []
    assert history.read_text(encoding="utf-8").splitlines() == tactics
    confirm_payload = _control_items(last)[0]["submit"]["payload"]
    assert confirm_payload["checkpoint_id"] == checkpoint_id
    assert confirm_payload["confirm"] is True

    turn = manager.handle_agent_message(json.dumps({
        "intent": "undo_to_checkpoint",
        "payload": confirm_payload,
    }))

    assert rewinds == [2]
    assert turn.workspace_view["last_result"]["kind"] == "checkpoint_rewind"
    menu = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')
    restore_option = _control_items(menu.workspace_view["last_result"])[0]
    assert restore_option["semantic_id"] == "restore_before_last_rewind"

    def fake_restore(restored_tactics, *, label="restore_pre_rewind"):  # noqa: ANN001
        history.write_text("\n".join(restored_tactics) + "\n", encoding="utf-8")
        return (
            _route_snapshot(manager, "Current goal\nrestored"),
            [{"label": label, "exit_code": 0}],
        )

    manager.repl.restore_committed_tactics = fake_restore  # type: ignore[method-assign]
    restored = manager.handle_agent_message(json.dumps(restore_option["submit"]))

    assert restored.workspace_view["last_result"]["kind"] == "checkpoint_restore"
    assert history.read_text(encoding="utf-8").splitlines() == tactics



def test_selected_checkpoint_rewinds_by_replaying_prefix(tmp_path: Path) -> None:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
        project_root=tmp_path,
    )
    repl.session_dir = "session"
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    _write_managed_session_meta(tmp_path, "session")
    (session_dir / "history.ec").write_text("a.\nb.\nc.\nd.\ne.\n", encoding="utf-8")
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(label, args, *, actions, timeout):  # noqa: ANN001
        calls.append((label, list(args)))
        actions.append({"label": label, "exit_code": 0})
        if label == "managed_goal_view":
            return _current_workspace_view(
                current_goal={"lines": ["g"]},
            )
        return '{"ok":true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]
    snapshot, actions = repl.rewind_before_tactic(3)

    assert [label for label, _args in calls] == [
        "undo_to_checkpoint",
        "replay_prefix_step_1",
        "replay_prefix_step_2",
        "managed_goal_view",
    ]
    assert calls[0][1][:2] == ["-start", "--force-restart"]
    assert calls[1][1] == ["-tactic-exec", "commit", "-c", "a."]
    assert calls[2][1] == ["-tactic-exec", "commit", "-c", "b."]
    assert snapshot.raw_workspace_view["current_goal"]["lines"] == ["g"]
    assert len([a for a in actions if a["label"] == "undo_to_checkpoint"]) == 1


def test_stale_checkpoint_id_returns_fresh_menu_without_mutation(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text("a.\nb.\n", encoding="utf-8")

    def fail_rewind(_idx):
        raise AssertionError("stale checkpoint must not rewind")

    manager.repl.rewind_before_tactic = fail_rewind  # type: ignore[method-assign]
    turn = manager.handle_agent_message(
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_0123456789abcdef"}}'
    )

    last = turn.workspace_view["last_result"]
    assert last["kind"] == "checkpoint_selection"
    # Panel-defect #2: a stale-HISTORY id (valid index, drifted hash) is rejected
    # WITHOUT mutating, and the result is now EXPLICIT — it says nothing was
    # rewound and hands back the refreshed id for the same committed tactic, rather
    # than a terse notice that reads as a silent no-op.
    notice = _control_notice(last)
    assert "NOTHING was rewound" in notice or "nothing was rewound" in notice.lower()
    assert "cp_1_" in notice  # refreshed id for the same committed tactic #1


def _route_snapshot(
    manager: ProofNodeManager,
    goal_text: str,
    *,
    goal_hash: str = "route",
) -> ProofStateSnapshot:
    return ProofStateSnapshot(
        node_id=manager.node_id,
        session_tag=manager.session_tag,
        session_dir=manager.repl.session_dir,
        session_epoch=1,
        state_version=4,
        goal_hash=goal_hash,
        goal_identity_required=True,
        raw_workspace_view=_current_workspace_view(
            proof_status={
                "status": "open",
                "remaining_goals": 8,
                "goal_type": "pRHL",
                "view_focus": "seq_cut",
                "current_layer": "procedure_body",
            },
            current_goal={
                "lines": goal_text.splitlines(),
                "char_count": len(goal_text),
            },
        ),
    )


def test_exact_same_goal_rejection_is_suppressed_before_backend() -> None:
    manager = make_manager()
    manager.latest_snapshot = _route_snapshot(manager, "x = y", goal_hash="same")
    manager.latest_view = _current_workspace_view(
        current_goal={"lines": ["x = y"]},
    )
    manager._rejection_goal_hash = "same"
    manager._current_goal_rejections = [{
        "intent": "commit_tactic",
        "payload": {"tactic": "rewrite H."},
        "outcome_kind": "rejected",
    }]

    turn = manager._exact_rejected_submission_gate(AgentIntent(
        intent="commit_tactic",
        payload={"tactic": "rewrite H."},
    ))

    assert turn is not None
    assert turn.ok is False
    assert turn.manager_actions[0]["label"] == "exact_rejection_memory"
    assert "already rejected" in turn.repair_prompt
