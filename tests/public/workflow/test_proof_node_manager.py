from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

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
    TurnDirective,
)
from workflow.node.proof_node_manager import (  # noqa: E402
    ProofNodeManager,
)
from workflow.proof_management.backend_request import BackendRequest  # noqa: E402
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

    def capture(session_dir, request):
        order.append("capture")
        assert session_dir == tmp_path / ".ec_session_freshness"
        assert request == BackendRequest.try_tactic("move=> &m x.")
        return boundary

    def run(*_args, **_kwargs):
        order.append("run")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    def record(request, argv, result, duration_ms, **kwargs):
        order.append("record")
        assert argv[-3:] == ["-try", "-c", "move=> &m x."]
        assert kwargs["tactic_preflight_boundary"] is boundary
        return {"label": request.label, "exit_code": result.returncode}

    monkeypatch.setattr(repl_module, "capture_tactic_preflight_invocation", capture)
    monkeypatch.setattr(repl_module, "run_in_process_group", run)
    monkeypatch.setattr(repl_module, "backend_action_record", record)
    monkeypatch.setattr(manager, "_env", lambda: {})

    actions: list[dict] = []
    manager._run_backend(
        BackendRequest.try_tactic("move=> &m x."),
        actions=actions,
        timeout=10,
    )

    assert order == ["capture", "run", "record"]
    assert actions == [{"label": "exact_tactic_preflight", "exit_code": 0}]


def test_repl_turn_deadline_clamps_every_backend_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import workflow.proof_management.repl_session as repl_module

    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="deadline-clamp",
        node_id="Tree-deadline-clamp",
        project_root=tmp_path,
    )
    observed: list[float] = []
    monkeypatch.setattr(repl_module.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        repl_module,
        "run_in_process_group",
        lambda *_args, **kwargs: (
            observed.append(float(kwargs["timeout"]))
            or subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr="",
            )
        ),
    )
    monkeypatch.setattr(
        repl_module,
        "backend_action_record",
        lambda request, *_args, **_kwargs: {
            "label": request.label, "exit_code": 0,
        },
    )
    monkeypatch.setattr(manager, "_env", lambda: {})

    with manager.turn_deadline(104.5):
        manager._run_backend(
            BackendRequest.managed_goal_view(),
            actions=[],
            timeout=30,
        )

    assert observed == [4.5]


def test_repl_turn_deadline_does_not_start_backend_after_expiry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import workflow.proof_management.repl_session as repl_module

    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="deadline-expired",
        node_id="Tree-deadline-expired",
        project_root=tmp_path,
    )
    monkeypatch.setattr(repl_module.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        repl_module,
        "run_in_process_group",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("expired deadline must not start a backend process")
        ),
    )
    actions: list[dict] = []

    with manager.turn_deadline(99.0), pytest.raises(ReplBackendTimeout):
        manager._run_backend(
            BackendRequest.managed_goal_view(),
            actions=actions,
            timeout=30,
        )

    assert actions[-1]["deadline_expired_before_start"] is True
    assert actions[-1]["absolute_deadline"] == 99.0


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

    def capture(session_dir, request):
        order.append("capture")
        assert session_dir == tmp_path / ".ec_session_tactic-boundary"
        assert request == BackendRequest.commit("commit_tactic", "wp.")
        return boundary

    def run(*_args, **_kwargs):
        order.append("run")
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="",
        )

    def record(request, argv, result, duration_ms, **kwargs):
        order.append("record")
        assert argv[-4:] == ["-tactic-exec", "commit", "-c", "wp."]
        assert kwargs["tactic_execution_boundary"] is boundary
        return {"label": request.label, "exit_code": result.returncode}

    monkeypatch.setattr(
        repl_module,
        "capture_tactic_execution_invocation",
        capture,
    )
    monkeypatch.setattr(repl_module, "run_in_process_group", run)
    monkeypatch.setattr(repl_module, "backend_action_record", record)
    monkeypatch.setattr(manager, "_env", lambda: {})

    actions: list[dict] = []
    manager._run_backend(
        BackendRequest.commit("commit_tactic", "wp."),
        actions=actions,
        timeout=10,
    )

    assert order == ["capture", "run", "record"]
    assert actions == [{"label": "commit_tactic", "exit_code": 0}]


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
        repl_module,
        "run_in_process_group",
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
            BackendRequest.try_tactic("move=> &m x."),
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


def test_raw_tool_arguments_reach_the_same_manager_repair_owner() -> None:
    manager = make_manager()
    manager.latest_view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["x = y"]},
    }

    turn = manager.handle_tool_arguments({"payload": {"tactic": "smt()."}})

    assert turn.ok is False
    assert turn.intent is None
    assert turn.health_event is None
    assert "exactly one JSON object" in turn.repair_prompt
    assert manager.malformed_count == 1


@pytest.mark.parametrize("raw_arguments", [None, [], "commit_tactic", 7])
def test_non_object_tool_arguments_reach_manager_owned_repair(
    raw_arguments,
) -> None:
    manager = make_manager()
    manager.latest_view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["x = y"]},
    }

    turn = manager.handle_tool_arguments(raw_arguments)

    assert turn.ok is False
    assert turn.intent is None
    assert turn.health_event is None
    assert "exactly one JSON object" in turn.repair_prompt
    assert manager.malformed_count == 1


def test_expired_manager_deadline_fails_closed_before_execution() -> None:
    manager = make_manager()
    manager.repl.handle_intent = (  # type: ignore[method-assign]
        lambda _intent: (_ for _ in ()).throw(
            AssertionError("expired turn must not reach the REPL")
        )
    )

    turn = manager.handle_tool_arguments(
        {"intent": "commit_tactic", "payload": {"tactic": "trivial."}},
        deadline=time.time() - 1,
    )

    assert turn.ok is False
    assert turn.health_event is not None
    assert turn.health_event.status == "manager_turn_deadline_exceeded"
    assert turn.directive is TurnDirective.NODE_UNHEALTHY


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


def test_resume_bootstrap_seeds_restore_anchor_and_route_events(
    tmp_path: Path,
) -> None:
    from workflow.proof_management import ProofProjectionResult
    from workflow.proof_management.events import (
        RESUME_ROUTE_EVENT_SCHEMA_VERSION,
    )

    manager = make_manager(run_dir=tmp_path)
    prefix = ["proc.", "wp."]
    anchor = {
        "restore_id": "restore_current",
        "tactics": ["proc.", "wp.", "sp."],
        "from_checkpoint_id": "cp_current",
        "from_tactic_index": 3,
    }
    route_event = {
        "kind": "resume_route_event",
        "schema_version": RESUME_ROUTE_EVENT_SCHEMA_VERSION,
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "outcome_kind": "accepted",
        "proof_state_effect": "changed",
        "needs_attention": False,
        "accepted": True,
        "rejected": False,
        "changed": True,
    }

    def start(*, replay_prefix, replay_transactions=None, daemon_attach=None):
        manager.repl.committed_history = lambda: list(replay_prefix)
        manager.repl.adopt_versions(len(replay_prefix), 1)
        return (
            ProofStateSnapshot(
                node_id="Tree-unit",
                session_tag="unit",
                session_dir=manager.repl.session_dir,
                session_epoch=1,
                state_version=len(replay_prefix),
                goal_hash="goal",
                goal_identity_required=True,
            ),
            [],
        )

    view = _current_workspace_view()
    manager.repl.start = start  # type: ignore[method-assign]
    manager.projection.project = lambda snapshot, **_kwargs: (  # type: ignore[method-assign]
        ProofProjectionResult(
            view=dict(view), full_view=dict(view),
        )
    )
    manager.bootstrap(
        replay_prefix=prefix,
        resume_context={
            "resume_prefix_count": len(prefix),
            "replay_transactions": list(prefix),
            "checkpoint_payload": {
                "schema_version": 1,
                "kind": "proof_checkpoint_state",
                "node_id": "Tree-unit",
                "pre_rewind_restore_anchor": anchor,
            },
            "route_event_facts": [route_event],
        },
    )

    assert manager.checkpoints.restore_anchor("restore_current") == anchor
    assert [
        {key: item[key] for key in route_event}
        for item in manager.events.route_event_facts
    ] == [route_event]
    # The worker that serves the agent adopts the bootstrap in a fresh
    # manager; both facts must be durable for it.
    worker = make_manager(run_dir=tmp_path)
    assert worker.checkpoints.restore_anchor("restore_current") == anchor
    assert len(worker.events.route_event_facts) == 1


def test_compiler_read_only_violation_marks_the_node_unhealthy() -> None:
    from workflow.proof_state_compiler.service import CompilerReadOnlyViolation

    class _MutatingCompiler:
        def compile_current_state(self, *, turn_evidence=None):
            raise CompilerReadOnlyViolation(
                "compiler service changed committed proof history"
            )

    manager = make_manager()
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(),
        snapshot={"session_epoch": 1, "state_version": 3, "goal_hash": "goal"},
    ))
    manager.compiler.service = _MutatingCompiler()

    turn = manager.handle_agent_message("not json")

    assert turn.ok is False
    assert turn.directive is TurnDirective.NODE_UNHEALTHY
    assert turn.health_event is not None
    assert turn.health_event.status == "compiler_read_only_violation"
    assert "changed committed proof history" in turn.health_event.message


@pytest.mark.parametrize("method", ["certify", "compiler_input"])
def test_compiler_surface_read_only_check_is_bound_to_every_call(
    tmp_path: Path,
    method: str,
) -> None:
    from workflow.proof_state_compiler.service import CompilerReadOnlyViolation

    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="read-only-unit",
        node_id="Tree-read-only-unit",
        project_root=tmp_path,
    )
    history: list[str] = ["proc."]
    manager.committed_history = lambda: list(history)  # type: ignore[method-assign]

    def run(request, *, actions: list[dict], **_kwargs):
        label, args = request.label, list(request.args)
        # A backend call that leaves the session changed and then fails: the
        # mutation must surface, not the ordinary failure behind it.
        history.append("wp.")
        actions.append({"label": label, "exit_code": 1})
        raise ReplBackendError(actions[-1])

    manager._run_backend = run  # type: ignore[method-assign]

    with pytest.raises(
        CompilerReadOnlyViolation, match="changed committed proof history"
    ):
        if method == "certify":
            manager.certify_exact_tactic("wp.")
        else:
            manager.read_compiler_input_v2()


def test_compiler_input_source_is_project_relative_not_cwd_relative(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from workflow.proof_management.backend_actions import (
        AuthoritativeViewResolution,
    )

    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "Target.ec").write_text("", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    manager = ReplSessionManager(
        file_path="src/Target.ec",
        lemma_name="target",
        include_dir="easycrypt-src/theories",
        session_tag="input-unit",
        node_id="Tree-input-unit",
        project_root=project,
    )
    manager.committed_history = lambda: []  # type: ignore[method-assign]

    def run(request, *, actions, authoritative_resolutions, **_kwargs):
        label, args = request.label, list(request.args)
        actions.append({"label": label, "exit_code": 0})
        authoritative_resolutions.append(AuthoritativeViewResolution(
            required=True,
            event_id="event-1",
            event_sequence=1,
            event_payload={"snapshot_id": "snapshot-1"},
        ))
        return {
            "ok": True,
            "snapshot_id": "snapshot-1",
            # The backend reports the resolved file; the manager keeps the
            # project-relative spelling.
            "target": {
                "lemma": "target",
                "source_file": str((project / "src" / "Target.ec").resolve()),
            },
            "state": {"state_version": 0},
        }

    manager._run_backend = run  # type: ignore[method-assign]

    result = manager.read_compiler_input_v2()

    assert result["snapshot"]["snapshot_id"] == "snapshot-1"


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
    assert turn.directive is TurnDirective.NODE_UNHEALTHY


def test_admit_is_not_preflight_clarified() -> None:
    # `admit` is not intercepted by preflight. The manager instead gates
    # finish/qed while committed admits remain.
    manager = make_manager()
    view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "proof_status": {"status": "open"},
    }
    admission = manager.admission.admit_intent(
        AgentIntent(intent="commit_tactic", payload={"tactic": "admit."}),
        latest_view=view,
        latest_snapshot=None,
    )
    assert admission.preflight.should_handle is False, "admit must not be intercepted"
    assert admission.preflight.audit_kind != "agent_intent.admit_clarification"


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
        manager.repl.adopt_versions(4, 1)
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
    assert backend_calls == []
    assert turn.directive is TurnDirective.STOP_REQUESTED


def test_manager_finish_action_has_explicit_serving_directive() -> None:
    manager = make_manager()
    manager.latest_view = _current_workspace_view(
        current_goal={},
        proof_status={"status": "session_closed_pending_verification"},
    )
    turn = manager.handle_tool_arguments({"intent": "finish", "payload": {}})

    finish = turn.manager_actions[0]
    assert finish["label"] == "finish"
    assert finish["outcome_kind"] == "accepted"
    assert finish["proof_state_effect"] == "unchanged"
    assert finish["agent_observation"]["kind"] == "finish_accepted"
    assert "Finish accepted" in finish["agent_observation"]["result"]
    assert turn.directive is TurnDirective.STOP_REQUESTED


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

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        label, args = request.label, list(request.args)
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


def test_fresh_restart_restarts_current_node_with_force_restart(
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

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        label, args = request.label, list(request.args)
        calls.append((label, list(args)))
        actions.append({"label": label, "exit_code": 0})
        if label == "managed_goal_view":
            return _current_workspace_view(
                current_goal={"lines": ["fresh"]},
            )
        return '{"ok": true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]

    snapshot, actions = repl.fresh_restart()

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
        manager.repl.adopt_versions(4, 2)
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


_START_ACK_ACTION = {
    # What backend_action_record makes of the bare `-start` acknowledgement.
    "exit_code": 0,
    "mutates_proof_state": True,
    "outcome_kind": "accepted_unconfirmed",
    "proof_state_effect": "unknown",
    "proof_state_changed": False,
    "needs_attention": False,
}


def _recovery_snapshot(manager: ProofNodeManager) -> ProofStateSnapshot:
    manager.repl.adopt_versions(4, 2)
    return ProofStateSnapshot(
        node_id="Tree-unit",
        session_tag="unit",
        session_dir=manager.repl.session_dir,
        session_epoch=2,
        state_version=4,
        goal_hash="restored",
        goal_identity_required=True,
        raw_workspace_view=_current_workspace_view(
            current_goal={"lines": ["restored"]},
            proof_status={"status": "open"},
        ),
    )


def test_recovery_turn_outcome_is_the_recovery_not_the_start_ack(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    menu = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')
    confirmation_id = _control_items(menu.workspace_view["last_result"])[-1][
        "submit"
    ]["payload"]["confirmation_id"]
    manager.repl.fresh_restart = lambda: (  # type: ignore[method-assign]
        _recovery_snapshot(manager),
        [{"label": "fresh_restart", **_START_ACK_ACTION}],
    )

    turn = manager.handle_agent_message(json.dumps({
        "intent": "fresh_restart",
        "payload": {"confirm": True, "confirmation_id": confirmation_id},
    }))

    last = turn.workspace_view["last_result"]
    assert last["outcome_kind"] == "accepted"
    assert last["proof_state_effect"] == "changed"
    assert manager.events.route_event_facts[-1]["outcome_kind"] == "accepted"


def test_amend_replay_stop_is_reported_as_partial_with_its_step(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text("proc.\nwp.\nauto.\n", encoding="utf-8")
    stop = {
        "label": "replay_prefix_stopped_at_divergence",
        "exit_code": 0,
        "mutates_proof_state": False,
        "replay_stopped_at_step": 2,
        "replay_kept_count": 1,
        "replay_requested_count": 3,
        "stopped_tactic": "wp.",
        "agent_observation": {
            "label": "replay_prefix_stopped_at_divergence",
            "result": (
                "Replay stopped at step 2: after the edit, `wp.` no longer "
                "applies."
            ),
        },
    }
    manager.repl.restart_with_edited_prefix = (  # type: ignore[method-assign]
        lambda _edited: (
            _recovery_snapshot(manager),
            [
                {"label": "restart_replay_edit", **_START_ACK_ACTION},
                {"label": "replay_prefix_step_1", "exit_code": 0},
                stop,
            ],
        )
    )

    turn = manager.handle_agent_message(json.dumps({
        "intent": "amend_and_replay",
        "payload": {"index": 1, "tactic": "proc; inline *."},
    }))

    last = turn.workspace_view["last_result"]
    assert last["outcome_kind"] == "partial_success"
    assert last["proof_state_effect"] == "changed"
    assert last["needs_attention"] is True
    assert last["replay_stopped_at_step"] == 2
    assert last["replay_kept_count"] == 1
    assert last["message"].startswith("Replaced committed step 1")
    assert last["result"].endswith("`wp.` no longer applies.")
    assert manager.events.route_event_facts[-1]["outcome_kind"] == (
        "partial_success"
    )


def test_resume_checkpoint_menu_offers_prefix_steps_as_ordinary(
    tmp_path: Path,
) -> None:
    # Transparent resume: the agent perceives one continuous proof it owns. The
    # replayed-prefix steps (here idx 1..3) surface as ORDINARY checkpoints with
    # NO "Return to resume start" / "verified replay prefix" framing, and the
    # whole menu is free of any resume/floor/prefix concept.
    manager = _manager_with_view(tmp_path)
    manager.state.replay_prefix_count = 3
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


def test_product_budget_seq_needs_a_real_budget_marker() -> None:
    from workflow.proof_management.tactic_utils import is_product_budget_seq

    # The `seq` head itself is not a query budget.
    assert not is_product_budget_seq("seq 2 : (has p xs).")
    assert not is_product_budget_seq("seq 3 : (bad = false /\\ ={glob A}).")
    assert is_product_budget_seq("seq 2 : (has p xs /\\ size xs <= qH).")
    assert is_product_budget_seq("seq 2 : (size log <= PKE_.qD /\\ bad).")
    assert is_product_budget_seq("seq 1 : (has p xs) (1%r / order%r).")


def test_resume_fresh_restart_blocks_agent_destructive_restart(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    manager.state.replay_prefix_count = 2
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
    assert manager.state.replay_prefix_count == 2


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



def _rewind_repl(tmp_path: Path) -> tuple[ReplSessionManager, Path]:
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
    return repl, session_dir


def test_selected_checkpoint_rewinds_in_place_by_one_undo(tmp_path: Path) -> None:
    # F2: a rewind is one undo of the live session; the kept commands are not
    # replayed, so the turn has no replay_prefix_step_* actions.
    repl, session_dir = _rewind_repl(tmp_path)
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        label, args = request.label, list(request.args)
        calls.append((label, list(args)))
        action = {"label": label, "exit_code": 0}
        if request.kind == "undo":
            keep = int(args[args.index("--keep-commands") + 1])
            lines = (session_dir / "history.ec").read_text().splitlines()
            (session_dir / "history.ec").write_text(
                "".join(line + "\n" for line in lines[:keep])
            )
            action.update(proof_state_changed=True, outcome_kind="accepted")
        actions.append(action)
        if label == "managed_goal_view":
            return _current_workspace_view(
                current_goal={"lines": ["g"]},
            )
        return '{"ok":true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]
    epoch = repl.session_epoch
    snapshot, actions = repl.rewind_before_tactic(3)

    assert [label for label, _args in calls] == [
        "undo_to_checkpoint",
        "managed_goal_view",
    ]
    assert calls[0][1] == ["-tactic-exec", "undo", "--keep-commands", "2"]
    assert repl.committed_history() == ["a.", "b."]
    assert snapshot.raw_workspace_view["current_goal"]["lines"] == ["g"]
    assert snapshot.session_epoch == epoch + 1
    assert not [a for a in actions if a["label"].startswith("replay_prefix_step_")]


def test_refused_undo_falls_back_to_restart_and_replay(tmp_path: Path) -> None:
    repl, _session_dir = _rewind_repl(tmp_path)
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(request, *, actions, timeout):  # noqa: ANN001
        label, args = request.label, list(request.args)
        calls.append((label, list(args)))
        action = {"label": label, "exit_code": 0}
        if request.kind == "undo":
            # The session reports the rewind unavailable and changes nothing.
            action.update(
                proof_state_changed=False,
                outcome_kind="no_progress",
                needs_attention=True,
                execution_authority={"structured_error": "pragma in range"},
            )
        actions.append(action)
        if label == "managed_goal_view":
            return _current_workspace_view(
                current_goal={"lines": ["g"]},
            )
        return '{"ok":true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]
    snapshot, actions = repl.rewind_before_tactic(3)

    assert [label for label, _args in calls] == [
        "undo_to_checkpoint",
        "undo_to_checkpoint",
        "replay_prefix_step_1",
        "replay_prefix_step_2",
        "managed_goal_view",
    ]
    assert calls[0][1] == ["-tactic-exec", "undo", "--keep-commands", "2"]
    assert calls[1][1][:2] == ["-start", "--force-restart"]
    assert calls[2][1] == ["-tactic-exec", "commit", "-c", "a."]
    assert calls[3][1] == ["-tactic-exec", "commit", "-c", "b."]
    assert snapshot.raw_workspace_view["current_goal"]["lines"] == ["g"]
    fallback = actions[0]
    assert fallback["label"] == "daemon_undo_fallback"
    assert fallback["needs_attention"] is False
    assert fallback["proof_state_changed"] is False
    assert fallback["daemon_undo"]["reason"] == "pragma in range"
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
    manager.admission.observe_projection(
        manager.latest_snapshot,
        {
            "intent": "commit_tactic",
            "payload": {"tactic": "rewrite H."},
            "outcome_kind": "rejected",
            "proof_state_effect": "unchanged",
        },
    )

    decision = manager.admission.admit_intent(
        AgentIntent(
            intent="commit_tactic",
            payload={"tactic": "rewrite H."},
        ),
        latest_view=manager.latest_view,
        latest_snapshot=manager.latest_snapshot,
    )
    turn = decision.turn

    assert turn is not None
    assert turn.ok is False
    assert turn.manager_actions[0]["label"] == "exact_rejection_memory"
    assert "already rejected" in turn.repair_prompt


def test_manager_services_share_one_node_state_and_their_collaborators() -> None:
    """Wiring: every service gets the facade's own objects, not copies or
    getters, so a write by one service is what the next one reads."""

    manager = make_manager()

    for service in (manager.lifecycle, manager.turns, manager.recovery):
        assert service.state is manager.state
    for service in (
        manager.lifecycle,
        manager.turns,
        manager.recovery,
        manager.admission,
        manager.compiler,
    ):
        assert service.repl is manager.repl
    assert manager.lifecycle.checkpoints is manager.checkpoints
    assert manager.recovery.checkpoints is manager.checkpoints
    for service in (manager.lifecycle, manager.turns, manager.admission):
        assert service.events is manager.events
    for service in (manager.lifecycle, manager.turns):
        assert service.lineage is manager.lineage
    assert manager.compiler.service is manager.compiler_service
    assert manager.compiler.repl.session_path == manager.session_path


def test_adopted_resume_lineage_reaches_recovery_and_survives_a_floor_clear(
    tmp_path: Path,
) -> None:
    manager = make_manager()
    manager.repl.session_dir = str(tmp_path / "session")
    Path(manager.repl.session_dir).mkdir(parents=True, exist_ok=True)
    (Path(manager.repl.session_dir) / "history.ec").write_text(
        "a.\nb.\n", encoding="utf-8"
    )
    manager.adopt_bootstrap(_current_bootstrap(
        workspace_view=_current_workspace_view(),
        snapshot={"session_epoch": 1, "state_version": 3, "goal_hash": "goal"},
        replay_prefix=["a.", "b."],
        session_dir=manager.repl.session_dir,
    ))
    amend = AgentIntent("amend_and_replay", {"index": 1, "tactic": "x."})

    assert manager.state.replay_prefix_count == 2
    assert manager.recovery.handle_amend_and_replay(amend).kind == "menu"

    # A rewind below the resume floor lifts the floor through the shared
    # state; the lineage marker it leaves keeps amend refused.
    manager.state.clear_replay_prefix()

    assert manager.state.replay_prefix_count == 0
    assert manager.state.resumed_from_prefix is True
    assert manager.recovery.handle_amend_and_replay(amend).kind == "menu"
    # Control: the same request on a from-scratch node is executed.
    manager.state.resumed_from_prefix = False
    assert manager.recovery.handle_amend_and_replay(amend).kind == "repl_call"


def test_executor_view_writes_are_the_facade_latest_view(tmp_path: Path) -> None:
    manager = _manager_with_view(tmp_path)

    turn = manager.handle_agent_message(
        '{"intent":"undo_to_checkpoint","payload":{}}'
    )

    assert manager.latest_view is manager.state.latest_view
    assert manager.latest_view == turn.workspace_view
    assert manager.latest_view["last_result"]["kind"] == "checkpoint_selection"
