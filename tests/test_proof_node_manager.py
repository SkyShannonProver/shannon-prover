from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


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
from workflow.proof_management.analyzers.recovery import (  # noqa: E402
    recovery_diagnosis_surface as _recovery_diagnosis_surface,
    workspace_view_with_recovery_consistent_route_health as _workspace_view_with_recovery_consistent_route_health,
)
from workflow.proof_management.backend_actions import (  # noqa: E402
    command_summary as _command_summary,
    content_observation_from_payload as _content_observation_from_payload,
)
from workflow.proof_management.recovery import (  # noqa: E402
    annotate_route_health_items as _annotate_route_health_items,
)
from workflow.proof_management import AgentIntent, parse_agent_intent  # noqa: E402
from workflow.surface_profiles import apply_workspace_view_surface_profile  # noqa: E402
from tests.helpers.builders import make_manager  # noqa: E402


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

    # A valid (read-only) intent resets the streak counter.
    manager.handle_agent_message(
        '{"intent": "inspect_context", "payload": {"topic": "goal_info"}}'
    )
    assert manager.malformed_count == 0

    # The next malformed intent is back to the plain, first-strike nudge.
    turn = manager.handle_agent_message("bad again")
    assert turn.health_event is None
    assert "no valid proof intent" not in turn.repair_prompt


def test_adopt_bootstrap_seeds_latest_view_without_restart() -> None:
    manager = make_manager()

    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "current_goal": {"lines": ["Current goal", "x = y"]},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 4,
            "state_version": 7,
            "goal_hash": "abc",
        },
    })
    turn = manager.handle_agent_message("not json")

    assert turn.ok is False
    assert turn.workspace_view["current_goal"]["lines"] == ["Current goal", "x = y"]
    assert manager.repl.state_version == 7
    assert manager.repl.session_epoch == 4


def test_backend_timeout_returns_latest_view_with_health_event() -> None:
    manager = make_manager()
    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "current_goal": {"lines": ["Current goal", "x = y"]},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "abc",
        },
    })

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


def test_readonly_backend_failure_returns_manager_result_not_exception() -> None:
    manager = make_manager()
    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "current_goal": {"lines": ["Current goal", "x = y"]},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "abc",
        },
    })
    action = _command_summary(
        "inspect_tactic_forms",
        [
            "python3",
            "core/easycrypt/session_cli.py",
            "-tactic-forms",
            "unknown",
        ],
        subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="No tactic-form reference for `unknown`.",
        ),
    )

    def backend_failure(_intent):
        raise ReplBackendError(action)

    manager.repl.handle_intent = backend_failure  # type: ignore[method-assign]
    turn = manager.handle_agent_message(
        '{"intent": "inspect_context", '
        '"payload": {"topic": "tactic_forms", "name": "unknown"}}'
    )

    assert turn.ok is False
    assert turn.health_event is None
    assert turn.manager_actions == [action]
    assert "could not complete" in turn.repair_prompt
    assert turn.workspace_view["current_goal"]["lines"] == ["Current goal", "x = y"]
    assert turn.workspace_view["last_result"]["intent"] == "inspect_context"
    assert turn.workspace_view["last_result"]["payload"] == {
        "topic": "tactic_forms",
        "name": "unknown",
    }
    assert "No tactic-form reference" in turn.workspace_view["last_result"]["error_summary"]


def test_admit_is_not_preflight_clarified() -> None:
    # `admit` is not intercepted by preflight. The manager instead gates
    # finish/qed while committed admits remain.
    from workflow.proof_management.intent_preflight import preflight_intent

    view = {
        "kind": "prover_workspace_view",
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "proof_position": {"status": "open"},
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
    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "schema_version": 1,
            "ok": True,
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "proof_status": {"status": "open"},
            "proof_frontier": {},
            "recent_diagnostics": {},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "abc",
        },
    })
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
    assert "closed proof candidate" in turn.repair_prompt


def test_qed_tactic_allowed_when_view_is_closed_candidate() -> None:
    manager = make_manager()
    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "schema_version": 1,
            "ok": True,
            "current_goal": {"lines": ["No more goals"]},
            "proof_status": {"status": "candidate_closed_pending_qed"},
            "proof_frontier": {},
            "recent_diagnostics": {},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "closed",
        },
    })
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
                goal_hash="closed",
                raw_workspace_view={
                    "kind": "prover_workspace_view",
                    "schema_version": 1,
                    "ok": True,
                    "current_goal": {"lines": ["No more goals"]},
                    "proof_status": {"status": "candidate_closed"},
                },
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
    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "schema_version": 1,
            "ok": True,
            "current_goal": {"lines": ["No more goals", "[25|check]>"]},
            "proof_status": {"status": "candidate_closed_pending_qed"},
            "candidate_moves": {
                "moves": [{
                    "title": "Concrete tactic candidate",
                    "category": "commit",
                    "tactic": "qed.",
                }],
            },
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "pending-qed",
        },
    })
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
    assert "commit_tactic" in turn.repair_prompt
    assert "qed." in turn.repair_prompt
    last = turn.workspace_view["last_result"]
    assert last["intent"] == "finish"
    assert last["manager_action"] == "finish_requires_qed"
    assert last["next_intent"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "qed."},
    }


def test_finish_allowed_after_qed_is_saved() -> None:
    manager = make_manager()
    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "schema_version": 1,
            "ok": True,
            "current_goal": {
                "lines": [
                    "No active goal: proof candidate was closed and `qed.` was saved.",
                ],
            },
            "proof_status": {"status": "candidate_closed"},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "saved",
        },
    })
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
                goal_hash="saved",
                raw_workspace_view={
                    "kind": "prover_workspace_view",
                    "schema_version": 1,
                    "ok": True,
                    "current_goal": {"lines": ["saved"]},
                    "proof_status": {"status": "candidate_closed"},
                },
            ),
            [{"label": "finish", "agent_observation": {"result": "finished"}}],
        )

    manager.repl.handle_intent = handled  # type: ignore[method-assign]

    turn = manager.handle_agent_message('{"intent": "finish", "payload": {}}')

    assert turn.ok is True
    assert backend_calls == ["finish"]


def test_inspect_observation_does_not_surface_cost_field() -> None:
    content = _content_observation_from_payload(
        "inspect_call_site_options",
        {
            "topic": "call_site_options",
            "status": "available",
            "observations": [{
                "producer": "AUTO-CALL-SUGGEST",
                "kind": "call_site_context",
                "effect": "context only; proof state unchanged",
                "cost": "cheap",
                "status": "available",
                "why": "context available",
            }],
            "tool_view": {
                "notes": [{
                    "code": "auto_call_suggest.context_only",
                    "message": "route context",
                }]
            },
        },
        "",
    )

    assert content["title"] == "Call-Site Context"
    assert "topic" not in content
    assert "result" not in content
    assert "kind" not in content["items"][0]
    assert "producer" not in content["items"][0]
    assert "confidence" not in content["items"][0]
    assert "cost" not in content["items"][0]
    assert "status" not in content["items"][0]
    assert content["notes"][0] == {"message": "route context"}


def test_inspect_observation_preserves_manager_owned_submit_intent() -> None:
    content = _content_observation_from_payload(
        "inspect_pr_bridge_routes",
        {
            "topic": "pr_bridge_routes",
            "status": "available",
            "tool_view": {
                "guidance": {
                    "recommendations": [{
                        "id": "bridge_options.verified.0",
                        "action": "rewrite H.",
                        "why": "verified route",
                        "confidence": "verified",
                        "metadata": {
                            "effect": "commits a verified Pr bridge route",
                            "submit": {
                                "intent": "commit_tactic",
                                "payload": {"tactic": "rewrite H."},
                            },
                        },
                    }],
                },
            },
        },
        "",
    )

    assert content["title"] == "Verified Pr Bridge Routes"
    assert content["items"][0]["candidate"] == "rewrite H."
    assert content["items"][0]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "rewrite H."},
    }
    assert content["items"][0]["verification"] == (
        "daemon-verified against the current goal"
    )


def test_call_subgoals_preview_is_explicitly_speculative_readonly() -> None:
    content = _content_observation_from_payload(
        "inspect_call_subgoals",
        {},
        (
            "=== Call subgoal preview ===\n"
            "Speculative `call (_: ...).` was rejected by daemon.\n"
            "Current goal remains unchanged."
        ),
    )

    assert content["title"] == "Call Obligation Preview"
    assert "preview_scope" not in content
    assert "preview_status" not in content
    assert "proof_state" not in content
    assert "how_to_read" not in content
    assert content["result"] == (
        "The previewed call did not typecheck against the daemon; no tactic "
        "was committed."
    )
    assert "was rejected by daemon" in content["preview"]


def test_inspect_context_topics_map_to_manager_backend_tools() -> None:
    manager = make_manager()

    assert manager.repl._inspect_args({"topic": "align"}) == ["-align"]
    assert manager.repl._inspect_args({"topic": "lemma_hints"}) == ["-lemma-hints"]
    # equiv_bridge_lemmas is the canonical name; bridge_lemmas is a back-compat alias.
    assert manager.repl._inspect_args({"topic": "equiv_bridge_lemmas"}) == ["-bridge-lemmas"]
    assert manager.repl._inspect_args({"topic": "bridge_lemmas"}) == ["-bridge-lemmas"]
    assert manager.repl._inspect_args({"topic": "inv_from_lemma", "lemma": "H"}) == [
        "-inv-from-lemma",
        "H",
    ]
    assert manager.repl._inspect_args({"topic": "tactic_forms", "name": "call"}) == [
        "-tactic-forms",
        "call",
    ]
    # operator_lemmas -> live EC `search OP.` over the loaded ctx (project-local lemmas);
    # --max raised so the needed lemma isn't silently truncated past the default 30.
    assert manager.repl._inspect_args({"topic": "operator_lemmas", "operator": "big"}) == [
        "-search-skeleton",
        "big",
        "--max",
        "200",
    ]
    # op may be a tighter term skeleton (passes through verbatim to EC search).
    assert manager.repl._inspect_args(
        {"topic": "operator_lemmas", "operator": "(big _ _ (_ :: _))"}
    ) == ["-search-skeleton", "(big _ _ (_ :: _))", "--max", "200"]
    # no operator -> safe fallback, never a crash
    assert manager.repl._inspect_args({"topic": "operator_lemmas"}) == ["-goal-info"]
    assert manager.repl._inspect_args({"topic": "pivot_context"}) == [
        "-pivot-inspect",
        "context",
    ]
    assert manager.repl._inspect_args({"topic": "verified_pivot_options"}) == [
        "-pivot-inspect",
        "verified",
    ]
    assert manager.repl._inspect_args({"topic": "call_site_options"}) == [
        "-pivot-inspect",
        "call-site",
    ]
    # pr_bridge_routes is the canonical name; bridge_options is a back-compat alias.
    assert manager.repl._inspect_args({"topic": "pr_bridge_routes"}) == [
        "-pivot-inspect",
        "bridge",
    ]
    assert manager.repl._inspect_args({"topic": "bridge_options"}) == [
        "-pivot-inspect",
        "bridge",
    ]
    assert manager.repl._inspect_args({"topic": "rewrite_candidates"}) == [
        "-pivot-inspect",
        "rewrite",
    ]
    assert manager.repl._inspect_args({"topic": "call_invariant_skeleton"}) == [
        "-pivot-inspect",
        "call-invariant-skeleton",
    ]
    assert manager.repl._inspect_args({
        "topic": "call_subgoals",
        "invariant": "={glob M}",
    }) == ["-call-subgoals", "-c", "={glob M}"]
    assert manager.repl._inspect_args({"topic": "suggest_close"}) == [
        "-suggest-close",
    ]


def test_goal_info_tool_view_surfaces_structured_content_without_preview() -> None:
    payload = {
        "schema_version": 1,
        "tool": "goal-info",
        "ok": True,
        "proof_state": {
            "status": "open",
            "goal": {
                "state_kind": "open",
                "goal_type": "ambient",
                "num_remaining": 1,
                "num_remaining_determined": True,
                "proof_candidate_closed": False,
                "active_goal_hash": "abc123",
                "authority": "pretty_text_fallback",
                "ec_ground_truth": False,
            },
            "history": {
                "tactic_count": 5,
                "has_qed": False,
                "latest_tactic": "have -> : " + "x = y " * 100,
            },
            "latest_transition": {
                "kind": "state_changed_same_goal_count",
                "status": "ok",
                "goals_before": 1,
                "goals_after": 1,
                "candidate_closed": False,
                "no_progress": False,
                "tactic": "have -> : " + "x = y " * 100,
            },
        },
        "guidance": {
            "goal_info": {
                "goal_type": "ambient",
                "ambient_shape": "simple_eq",
                "num_remaining": 1,
                "num_remaining_determined": True,
            },
        },
    }

    content = _content_observation_from_payload(
        "inspect_goal_info",
        payload,
        json.dumps(payload),
    )

    assert content["title"] == "Parsed Goal Information"
    assert content["goal_info"] == payload["guidance"]["goal_info"]
    assert content["goal_state"]["active_goal_hash"] == "abc123"
    assert content["history"]["tactic_count"] == 5
    assert content["latest_transition"]["kind"] == "state_changed_same_goal_count"
    assert len(content["history"]["latest_tactic"]) <= 320
    assert "preview" not in content


def test_repl_start_replays_prefix_with_step_actions() -> None:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
    )
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(label, args, *, actions, timeout):  # noqa: ANN001
        calls.append((label, list(args)))
        if label == "agent_view":
            return '{"workspace": {"kind": "prover_workspace_view", "current_goal": {"lines": ["g"]}}}'
        return '{"ok": true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]

    repl.start(replay_prefix=["byequiv=>//.", "proc."])

    assert calls[1] == (
        "replay_prefix_step_1",
        ["-next", "-c", "byequiv=>//."],
    )
    assert calls[2] == (
        "replay_prefix_step_2",
        ["-next", "-c", "proc."],
    )


def test_fresh_restart_intent_restarts_current_node_with_force_restart() -> None:
    repl = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="unit",
        node_id="Tree-unit",
    )
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(label, args, *, actions, timeout):  # noqa: ANN001
        calls.append((label, list(args)))
        actions.append({"label": label, "exit_code": 0})
        if label == "agent_view":
            return '{"kind": "prover_workspace_view", "current_goal": {"lines": ["fresh"]}}'
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
    manager.adopt_bootstrap({
        "workspace_view": {
            "kind": "prover_workspace_view",
            "schema_version": 1,
            "ok": True,
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "proof_status": {"status": "open"},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": manager.repl.session_dir,
            "session_epoch": 1,
            "state_version": 3,
            "goal_hash": "abc",
        },
    })
    return manager


def _record_route_event_facts(
    manager: ProofNodeManager,
    events: list[dict[str, object]],
) -> None:
    for event in events:
        manager.events.record_route_event(dict(event))


def test_parser_accepts_negotiated_rewind_and_restart_intents() -> None:
    for text in (
        '{"intent":"undo_to_checkpoint","payload":{}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_0123456789abcdef"}}',
        '{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_1_0123456789abcdef","confirm":true,"confirmation_id":"abc"}}',
        '{"intent":"undo_to_checkpoint","payload":{"restore_id":"restore_abc"}}',
        '{"intent":"fresh_restart","payload":{}}',
        '{"intent":"fresh_restart","payload":{"confirm":true,"confirmation_id":"abc"}}',
    ):
        parsed = parse_agent_intent(text)
        assert parsed.ok is True


def test_fresh_restart_menu_does_not_call_backend_or_surface_mutation_metadata(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)

    def fail_backend(_intent):
        raise AssertionError("fresh_restart menu must not call backend")

    manager.repl.handle_intent = fail_backend  # type: ignore[method-assign]
    turn = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')

    assert turn.ok is True
    assert turn.manager_actions[0]["proof_state_effect"] == "selection_menu_only"
    last = turn.workspace_view["last_result"]
    assert last["kind"] == "fresh_restart_confirmation"
    assert "Fresh restart is destructive" in last["message"]
    assert "result" not in last
    assert "mutates_proof_state" not in last
    assert "proof state was not changed" not in str(last).lower()
    assert last["options"][-1]["submit"]["intent"] == "fresh_restart"
    assert last["options"][-1]["submit"]["payload"]["confirm"] is True
    # Menu order after 82d92bfa3 dropped the "Continue current branch"
    # option: lighter undo choices first, destructive restart last.
    assert last["options"][0]["submit"] == {
        "intent": "undo_last_step",
        "payload": {},
    }
    assert last["options"][1]["submit"] == {
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
    confirmation_id = menu.workspace_view["last_result"]["options"][-1]["submit"][
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
            raw_workspace_view={
                "kind": "prover_workspace_view",
                "current_goal": {"lines": ["fresh"]},
                "proof_status": {"status": "open"},
            },
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
    options = last["checkpoint_options"]
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
        for option in turn.workspace_view["last_result"]["checkpoint_options"]
        if option["tactic_index"] == 2
    )
    assert product["label"] == "Before product-budget seq cut #2"
    assert "stronger midpoint assertion" in product["after_rewind_next"]
    assert "budget" in product["repair_use_when"]


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
        for option in last["options"]
    )
    assert any(
        option["submit"]["intent"] == "undo_to_checkpoint"
        for option in last["options"]
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
            "erase_to_target_lemma": True,
        },
    }))

    assert calls == []
    last = turn.workspace_view["last_result"]
    assert last["kind"] == "fresh_restart_confirmation"
    assert "Fresh restart inside this node is disabled" in last["notice"]
    # The notice (and whole observation) carries no resume/prefix framing.
    assert not _RESUME_LEAK_RE.search(json.dumps(last)), last
    assert all(
        option["submit"]["intent"] != "fresh_restart"
        for option in last["options"]
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
    assert last["message"] == "Choose the committed tactic you want to rewind before."
    assert "result" not in last
    assert "mutates_proof_state" not in last
    option = last["checkpoint_options"][0]
    assert option["semantic_id"] == "after_call_opened"
    assert option["committed_tactic"] == "sp."
    assert option["tactic_index"] == 6
    assert "frontier" in option["repair_use_when"]
    assert "sp" in option["after_rewind_next"]
    assert option["effect_if_selected"] == (
        "This will undo committed tactic #6 and every committed tactic after it in this node."
    )
    assert option["submit"]["intent"] == "undo_to_checkpoint"
    call_option = next(
        item for item in last["checkpoint_options"]
        if item["committed_tactic"].startswith("call (_:")
    )
    assert "call invariant introduction point" in call_option["why_checkpoint"]
    assert "Prefer this over fresh restart" in call_option["repair_use_when"]
    assert "call_subgoals" in call_option["after_rewind_next"]


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

    options = turn.workspace_view["last_result"]["checkpoint_options"]
    indices = {item["tactic_index"] for item in options}
    assert {5, 9, 12, 15, 28, 29}.issubset(indices)
    assert len(options) <= 12
    outer = next(item for item in options if item["tactic_index"] == 5)
    assert outer["label"] == "Before call invariant #5"
    assert outer["undo_scope"] == "structural_boundary"


def test_call_local_structural_checkpoints_are_surface_and_menu(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "call (_: inv0).\n"
        "wp.\n"
        "smt().\n",
        encoding="utf-8",
    )

    view = manager._project(_route_snapshot(manager, "Current goal\nx = y"))

    checkpoints = view["structural_checkpoints"]["items"]
    by_semantic = {
        semantic_id
        for item in checkpoints
        for semantic_id in item.get("semantic_ids", [item.get("semantic_id")])
    }
    assert "before_call_route" in by_semantic
    assert "after_call_opened" in by_semantic
    assert "before_call_obligation_work" in by_semantic
    assert checkpoints[0]["semantic_id"] == "before_call_obligation_work"

    turn = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')
    options = turn.workspace_view["last_result"]["checkpoint_options"]
    assert options[0]["semantic_id"] == "before_call_obligation_work"
    assert any("after_call_opened" in item.get("semantic_ids", []) for item in options)
    assert any("before_call_route" in item.get("semantic_ids", []) for item in options)
    noisy_fields = {
        "discarded_tactic_count",
        "kept_tactic_count",
        "crosses_resume_boundary",
        "discarded_replay_prefix_count",
        "rollback_class",
        "rollback_group",
        "confirmation_required",
    }
    assert noisy_fields.isdisjoint(options[0])


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
    confirm_payload = last["checkpoint"]["submit"]["payload"]
    assert confirm_payload["checkpoint_id"] == checkpoint_id
    assert confirm_payload["confirm"] is True

    turn = manager.handle_agent_message(json.dumps({
        "intent": "undo_to_checkpoint",
        "payload": confirm_payload,
    }))

    assert rewinds == [2]
    assert turn.workspace_view["last_result"]["kind"] == "checkpoint_rewind"
    assert any(
        item.get("semantic_id") == "restore_before_last_rewind"
        for item in turn.workspace_view["structural_checkpoints"]["items"]
    )

    menu = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')
    restore_option = menu.workspace_view["last_result"]["checkpoint_options"][0]
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


def test_route_replay_memory_surfaces_suffix_after_checkpoint_rewind(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    manager.run_dir = tmp_path / "run"
    history = Path(manager.repl.session_dir) / "history.ec"
    tactics = [
        "byequiv=>//.",
        "proc.",
        "seq 5 3 : (old_midpoint).",
        "sp 4 2.",
        "wp.",
        "smt().",
    ]
    history.write_text("\n".join(tactics) + "\n", encoding="utf-8")
    manager._project(_route_snapshot(manager, "Current goal\nbefore rewind"))
    checkpoint_id = "cp_3_" + hashlib.sha1(
        "\n".join(tactics).encode("utf-8")
    ).hexdigest()[:16]

    def fake_rewind(tactic_index: int):  # noqa: ANN001
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

    assert manager.proof_memory.route_memories
    memory_file = manager.run_dir / "route_memory" / "Tree-unit_route_replay_memory.json"
    assert memory_file.exists()
    assert "rewind_route_memory" not in turn.workspace_view
    surface = turn.workspace_view["route_replay_memory"]
    chunk = surface["items"][0]["available_chunks"][0]
    assert chunk["first_tactic"] == "seq 5 3 : (old_midpoint)."
    assert chunk["submit_commit"]["intent"] == "commit_replay_suffix_chunk"
    assert "submit_probe" not in chunk
    assert surface["kind"] == "route_replay_memory"
    assert surface["repair_episodes"]


def test_route_replay_memory_replays_suffix_after_rewritten_boundary(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    old_tactics = [
        "byequiv=>//.",
        "proc.",
        "seq 5 3 : (old_midpoint).",
        "sp 4 2.",
        "call (_: old_inv).",
        "wp.",
    ]
    manager.proof_memory.record_checkpoint_rewind(
        tactics=old_tactics,
        checkpoint_id="cp_old",
        tactic_index=3,
        state_version=manager.repl.state_version,
    )
    current_tactics = [
        "byequiv=>//.",
        "proc.",
        "seq 5 3 : (={glob A} /\\ new_midpoint).",
        "sp 4 2.",
    ]
    history.write_text("\n".join(current_tactics) + "\n", encoding="utf-8")

    view = manager._project(_route_snapshot(manager, "Current goal\nx = y"))
    assert "rewind_route_memory" not in view
    surface = view["route_replay_memory"]
    item = surface["items"][0]
    assert item["progress"]["rewrite_anchor"]["relation"] == (
        "same_structural_boundary_head_rewritten"
    )
    chunk = item["available_chunks"][0]
    assert chunk["first_tactic"] == "call (_: old_inv)."
    assert chunk["last_tactic"] == "wp."

    verified: list[tuple[list[str], list[str]]] = []

    def fake_verify(prefix_tactics, chunk_tactics):  # noqa: ANN001
        verified.append((list(prefix_tactics), list(chunk_tactics)))
        return {
            "ok": True,
            "accepted_count": len(chunk_tactics),
            "accepted_tactics": list(chunk_tactics),
            "actions": [{"label": "scratch_replay", "exit_code": 0}],
        }

    def fake_restore(restored_tactics, *, label="restore_pre_rewind"):  # noqa: ANN001
        history.write_text("\n".join(restored_tactics) + "\n", encoding="utf-8")
        return (
            _route_snapshot(manager, "Current goal\nafter replay"),
            [{"label": label, "exit_code": 0}],
        )

    manager.repl.verify_tactic_chunk_from_prefix = fake_verify  # type: ignore[method-assign]
    manager.repl.restore_committed_tactics = fake_restore  # type: ignore[method-assign]

    committed = manager.handle_agent_message(json.dumps({
        "intent": "commit_replay_suffix_chunk",
        "payload": {"chunk_id": chunk["chunk_id"]},
    }))

    assert committed.workspace_view["last_result"]["kind"] == "replay_suffix_commit"
    assert verified[0][0] == current_tactics
    assert verified[0][1] == ["call (_: old_inv).", "wp."]
    assert history.read_text(encoding="utf-8").splitlines() == [
        *current_tactics,
        "call (_: old_inv).",
        "wp.",
    ]


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
    (session_dir / "history.ec").write_text("a.\nb.\nc.\nd.\ne.\n", encoding="utf-8")
    calls: list[tuple[str, list[str]]] = []

    def fake_backend(label, args, *, actions, timeout):  # noqa: ANN001
        calls.append((label, list(args)))
        actions.append({"label": label, "exit_code": 0})
        if label == "agent_view":
            return '{"kind":"prover_workspace_view","current_goal":{"lines":["g"]}}'
        return '{"ok":true}'

    repl._run_backend = fake_backend  # type: ignore[method-assign]
    snapshot, actions = repl.rewind_before_tactic(3)

    assert [label for label, _args in calls] == [
        "undo_to_checkpoint",
        "replay_prefix_step_1",
        "replay_prefix_step_2",
        "agent_view",
    ]
    assert calls[0][1][:2] == ["-start", "--force-restart"]
    assert calls[1][1] == ["-next", "-c", "a."]
    assert calls[2][1] == ["-next", "-c", "b."]
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
    notice = last["notice"]
    assert "NOTHING was rewound" in notice or "nothing was rewound" in notice.lower()
    assert "cp_1_" in notice  # refreshed id for the same committed tactic #1


def _route_snapshot(manager: ProofNodeManager, goal_text: str) -> ProofStateSnapshot:
    return ProofStateSnapshot(
        node_id=manager.node_id,
        session_tag=manager.session_tag,
        session_dir=manager.repl.session_dir,
        session_epoch=1,
        state_version=4,
        goal_hash="route",
        raw_workspace_view={
            "kind": "prover_workspace_view",
            "schema_version": 1,
            "ok": True,
            "proof_status": {
                "status": "open",
                "remaining_goals": 8,
                "goal_type": "pRHL",
                "view_focus": "seq_cut",
                "current_layer": "procedure_body",
            },
            "current_goal": {
                "lines": goal_text.splitlines(),
                "char_count": len(goal_text),
            },
            "candidate_moves": {"moves": []},
        },
    )


def test_route_health_reports_boundary_gap_and_context_lookup(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Target.ec"
    source.write_text(
        """
op inv_lbad1 xs lenc log mem lc cbad ndec =
  size xs <= size (make_lbad1 log mem lenc) /\\ cbad <= qenc.
local lemma inv_lbad1_i xs lenc log mem lc cbad ndec:
  size xs <= cbad => make_lbad1 xs log mem lc ndec = xs.
proof. admit. qed.
""",
        encoding="utf-8",
    )
    manager = _manager_with_view(tmp_path)
    manager.repl.file_path = str(source)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "call (_: ={UFCMA_l.lbad1, UFCMA.log, Mem.lc}).\n",
        encoding="utf-8",
    )
    _record_route_event_facts(manager, [
        {
            "intent": "commit_tactic",
            "tactic": "sim.",
            "tactic_head": "sim",
            "rejected": True,
            "error_summary": "cannot infer the set of equalities",
        },
        {
            "intent": "commit_tactic",
            "tactic": "smt().",
            "tactic_head": "smt",
            "rejected": True,
            "error_summary": "SMT failed",
        },
    ])
    goal = """
Current goal
pre = UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2}
post = size UFCMA_l.lbad1{2} <= nth0 =>
       UFCMA_li.cbadi{2} = 0 /\
       nth (w1,w2) (make_lbad1 UFCMA_l.lbad1{1} UFCMA.log{1}
                    Mem.log{1} Mem.lc{1}) nth0 = (w1,w2)
"""

    view = manager._project(_route_snapshot(manager, goal))

    health = view["candidate_moves"]["route_health"]
    debt = health[0]
    assert debt["signal"] == "possible_boundary_gap"
    assert debt["recovery_class"] == "boundary_repair_evidence"
    assert debt["checkpoint_policy"] == "boundary_checkpoint_visible"
    assert all(item["signal"] != "prhl_surgery_sequence_needed" for item in health)
    assert debt["recommended_next"] == debt["repair_checkpoint"]["submit"]
    assert "candidate_ingredients" not in debt
    concept_diff = debt["concept_diff"]
    assert concept_diff["residual_cluster"] == "bad-event index/list structure"
    assert "ufcma_l.lbad1" in concept_diff["boundary_mentions"]
    assert "ufcma_li.cbadi" in concept_diff["residual_terms_not_obvious_in_boundary"]
    assert "recipe" in concept_diff["how_to_read"]
    assert any(
        item["intent"] == "lookup_symbol"
        and item["payload"]["symbol"] == "inv_lbad1_i"
        and "context only" in item["why"]
        for item in debt["useful_inspections"]
    )
    assert debt["repair_checkpoint"]["label"] == "Before call invariant #3"
    assert debt["repair_checkpoint"]["submit"]["intent"] == "undo_to_checkpoint"
    diagnosis = view["recovery_diagnosis_surface"]
    assert diagnosis["recovery_class"] == "boundary_repair_evidence"
    assert diagnosis["related_checkpoints"][0]["label"] == "Before call invariant #3"
    assert "submit" not in diagnosis["related_checkpoints"][0]


def test_route_health_does_not_report_boundary_gap_without_repeated_symptoms(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "call (_: ={UFCMA_l.lbad1, UFCMA.log, Mem.lc}).\n",
        encoding="utf-8",
    )
    goal = """
Current goal
post = size UFCMA_l.lbad1{2} <= nth0 =>
       UFCMA_li.cbadi{2} = 0 /\
       nth (w1,w2) (make_lbad1 UFCMA_l.lbad1{1} UFCMA.log{1}
                    Mem.log{1} Mem.lc{1}) nth0 = (w1,w2)
"""

    view = manager._project(_route_snapshot(manager, goal))

    signals = [
        item["signal"]
        for item in view.get("candidate_moves", {}).get("route_health", [])
    ]
    assert "possible_boundary_gap" not in signals


def test_route_health_reports_step3_style_boundary_gap(tmp_path: Path) -> None:
    source = tmp_path / "Step3.ec"
    source.write_text(
        """
op inv_cpa roin roout log1 log2 lc1 lc2 lenc1 lenc2 ndec1 ndec2 =
  (forall n c, (n,c) \\in ROF.m => n \\in BNR.lenc) /\\ Mem.log = Mem.log.
""",
        encoding="utf-8",
    )
    manager = _manager_with_view(tmp_path)
    manager.repl.file_path = str(source)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\nproc.\ncall (_: ={Mem.log, Mem.lc}).\n",
        encoding="utf-8",
    )
    _record_route_event_facts(manager, [
        {
            "intent": "commit_tactic",
            "tactic": "sim.",
            "tactic_head": "sim",
            "rejected": True,
            "error_summary": "cannot infer the set of equalities",
        },
        {
            "intent": "commit_tactic",
            "tactic": "smt().",
            "tactic_head": "smt",
            "rejected": True,
            "error_summary": "SMT failed",
        },
    ])
    goal = """
Current goal
post = inv_cpa ROin.m{1} ROout.m{1} Mem.log{1} Mem.log{2}
       Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2}
       BNR.ndec{1} BNR.ndec{2} /\
       forall n c, (n,c) \\in ROF.m{1} => n \\in BNR.lenc{1}
"""

    view = manager._project(_route_snapshot(manager, goal))

    debt = view["candidate_moves"]["route_health"][0]
    assert debt["signal"] == "possible_boundary_gap"
    assert debt["recovery_class"] == "boundary_repair_evidence"
    assert debt["recommended_next"] == debt["repair_checkpoint"]["submit"]
    assert debt["concept_diff"]["residual_cluster"] == "oracle/log CPA invariant structure"
    assert "bnr.lenc" in debt["concept_diff"]["residual_terms_not_obvious_in_boundary"]
    assert any(
        item["intent"] == "lookup_symbol"
        and item["payload"]["symbol"] == "inv_cpa"
        for item in debt["useful_inspections"]
    )


def test_route_health_reports_lost_named_call_boundary(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "call (_: inv_cpa ROin.m ROout.m).\n"
        "proc.\n"
        "inline *.\n"
        "wp.\n",
        encoding="utf-8",
    )
    goal = """
Current goal
pre = inv_cpa ROin.m{1} ROout.m{1} Mem.log{1} Mem.log{2}
post = r14{1} = t{2} /\\ poly1305_eval r4{1} (topol a{2} c1{2}) = t{2}
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["program_frontier"] = {
        "authority": "proof-state analysis",
        "call_sites": [],
    }
    snapshot.raw_workspace_view["candidate_moves"] = {
        "moves": [
            {
                "title": "Named-call context",
                "category": "strategy",
                "tactic_shape": "ecall (equ_cc <nonce> <ROin> <ROout>).",
                "applicability": (
                    "Use as route context; current frontier determines "
                    "whether this named oracle-equivalence applies."
                ),
            }
        ]
    }

    view = manager._project(snapshot)

    health = view["candidate_moves"]["route_health"]
    loss = health[0]
    assert loss["signal"] == "lost_call_abstraction_boundary"
    assert loss["recovery_class"] == "call_frontier_recovery_evidence"
    assert loss["checkpoint_policy"] == "call_site_boundary_visible"
    assert loss["route_candidate"]["symbol"] == "equ_cc"
    assert loss["repair_checkpoint"]["label"] == "Before inline expansion #5"
    assert loss["repair_checkpoint"]["tactic_index"] == 5
    assert loss["recommended_next"] == loss["repair_checkpoint"]["submit"]
    assert "no live procedure call site" in loss["evidence"][1]
    assert any(
        item["intent"] == "lookup_symbol"
        and item["payload"]["symbol"] == "equ_cc"
        for item in loss["useful_inspections"]
    )
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")
    upgrade_loss = upgrade["candidate_moves"]["route_health"][0]
    assert upgrade_loss["signal"] == "lost_call_abstraction_boundary"
    assert upgrade["recovery_diagnosis_surface"]["recovery_class"] == (
        "call_frontier_recovery_evidence"
    )
    assert any(
        item["intent"] == "call_site_options"
        for item in upgrade_loss["useful_inspections"]
    )
    assert any(
        item["intent"] == "lookup_symbol"
        and item["payload"]["symbol"] == "equ_cc"
        for item in upgrade_loss["useful_inspections"]
    )


def test_call_opened_procedure_equivalence_is_not_lost_boundary_or_pure_tail(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "inline *.\n"
        "wp.\n"
        "call (_: Mem.k{1} = IndBlock.k{2}).\n",
        encoding="utf-8",
    )
    goal = """
Current goal (remaining: 4)

pre = arg{1} = arg{2} /\\ Mem.k{1} = IndBlock.k{2}

    RealOrcls(GenChaChaPoly(OpCCinit.OCC(I_stateless))).enc ~ D(A, IndBlock).O.enc

post = res{1} = res{2} /\\ Mem.k{1} = IndBlock.k{2}
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["program_frontier"] = {
        "authority": "proof-state analysis",
        "call_sites": [],
    }
    snapshot.raw_workspace_view["candidate_moves"] = {
        "moves": [
            {
                "title": "Named-call context",
                "category": "strategy",
                "tactic_shape": "call poly_mac1.",
                "applicability": (
                    "This named-call shape came from program comparison."
                ),
            }
        ]
    }

    view = manager._project(snapshot)
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    signals = [
        item["signal"]
        for item in upgrade.get("candidate_moves", {}).get("route_health", [])
    ]
    assert "lost_call_abstraction_boundary" not in signals
    assert "pure_tail_surface" not in upgrade


def test_route_health_keeps_named_call_context_when_call_site_is_live(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\nproc.\ninline *.\n",
        encoding="utf-8",
    )
    goal = """
Current goal
&1 (left) : { c2 <@ ChaCha(CCRO).enc(k, n, p2) }
&2 (right): { c1 <@ EncRnd.cc(n, p1) }
post = ={c1, c2}
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["program_frontier"] = {
        "call_sites": [
            {"side": "left", "procedure": "ChaCha.enc"},
            {"side": "right", "procedure": "EncRnd.cc"},
        ]
    }
    snapshot.raw_workspace_view["candidate_moves"] = {
        "moves": [
            {
                "title": "Named-call route",
                "category": "strategy",
                "tactic_shape": "ecall (equ_cc n{1} ROin.m{1} ROout.m{1}).",
            }
        ]
    }

    view = manager._project(snapshot)

    signals = [
        item["signal"]
        for item in view.get("candidate_moves", {}).get("route_health", [])
    ]
    assert "lost_call_abstraction_boundary" not in signals


def test_l4_call_site_surface_exposes_neutral_current_state(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    goal = """
Current goal
&1 (left) : { c2 <@ Wrapper.enc(n, p) }
&2 (right): { c1 <@ EncRnd.cc(n, p) }
post = ={c1, c2}
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["program_frontier"] = {
        "call_sites": [
            {
                "id": "left.1",
                "side": "left",
                "procedure": "Wrapper.enc",
                "requires_cut_to_frontier": True,
                "is_frontier_call": False,
            },
            {
                "id": "right.1",
                "side": "right",
                "procedure": "EncRnd.cc",
                "is_frontier_call": True,
            },
        ],
        "frontier_alignment": {
            "rows": [
                {
                    "role": "residual after call",
                    "left": "BNR.ndec <- BNR.ndec + 1",
                    "right": "BNR.ndec <- BNR.ndec + 1",
                    "proof_read": "These statements remain after the live call frontier.",
                }
            ]
        },
    }
    snapshot.raw_workspace_view["application_context"] = {
        "selected_handles": [
            {
                "name": "wrapper_equiv",
                "kind": "call-equivalence handle",
                "why_relevant": "visible call handle context",
            }
        ]
    }
    snapshot.raw_workspace_view["candidate_moves"] = {
        "moves": [
            {
                "title": "Named-call context",
                "category": "strategy",
                "tactic": "call old_equiv.",
                "applicability": "This named-call shape came from program comparison.",
            }
        ]
    }
    view = manager._project(snapshot)
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    surface = upgrade["call_site_surface"]
    assert [item["procedure"] for item in surface["live_call_sites"]] == [
        "Wrapper.enc",
        "EncRnd.cc",
    ]
    assert surface["named_handles"][0]["symbol"] == "wrapper_equiv"
    assert surface["frontier_blockers"][0]["kind"] == "requires_cut_to_frontier"
    assert any(
        item["kind"] == "residual_after_call_site"
        for item in surface["frontier_blockers"]
    )
    assert surface["residual_frontier"]["state"] == "residual_after_call"
    assert "old_equiv" in {item["symbol"] for item in surface["named_handles"]}
    old_equiv = next(
        item for item in surface["named_handles"]
        if item["symbol"] == "old_equiv"
    )
    assert "tactic_shape" not in old_equiv
    assert "preview_effects" not in surface
    assert "old_equiv" not in json.dumps(upgrade.get("candidate_moves", {}))
    assert "should" not in json.dumps(surface).lower()


def test_l4_call_site_surface_exposes_one_sided_call_certificate_evidence(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    goal = """
Current goal
Hdec: forall ge k c,
        hoare[ E.dec :
                (glob E) = ge /\\ k = k /\\ c = c ==>
                (glob E) = ge /\\ res = dec k c ]
------------------------------------------------------------------------
&1 (left ) : {p0 : ptxt option, ek : eK, c0 : ctxt}
&2 (right) : {b : bool}
p0 <@ E.dec(ek, c0)        (1)
post = p0{1} <> None<:ptxt>
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["program_frontier"] = {
        "call_sites": [
            {
                "side": "left",
                "side_index": 1,
                "procedure": "E.dec",
                "statement": "p0 <@ E.dec(ek, c0)",
            }
        ],
        "frontier_alignment": {
            "first_instruction_alignment": {
                "left_first": "p0 <@ E.dec(ek, c0)",
                "right_first": "no matching right-side call at this frontier",
                "branch_alignment": "one-sided_frontier",
            }
        },
    }
    snapshot.raw_workspace_view["application_context"] = {
        "selected_handles": [
            {
                "name": "E_dec_ll",
                "kind": "lossless lemma",
                "why_relevant": "losslessness certificate for E.dec",
            }
        ]
    }

    view = manager._project(snapshot)
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    surface = upgrade["call_site_surface"]["one_sided_call_surface"]
    assert surface["state"] == "one_sided_call_frontier"
    assert surface["one_sided_sites"][0]["procedure"] == "E.dec"
    assert surface["visible_hoare_handles"][0]["symbol"] == "Hdec"
    assert surface["visible_hoare_handles"][0]["procedure"] == "E.dec"
    assert surface["visible_lossless_handles"][0]["symbol"] == "E_dec_ll"
    assert surface["packaging_evidence"]["kind"] == (
        "one_sided_call_certificate_shape"
    )
    assert surface["packaging_evidence"]["confidence"] == "high"
    assert "phoare[PROC : PRE ==> POST] = 1%r" in json.dumps(surface)
    assert "should" not in json.dumps(surface).lower()


def test_l4_one_sided_call_surface_absent_for_paired_call_frontier(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    goal = """
Current goal
Hdec: hoare[ E.dec : true ==> res = None<:ptxt> ]
------------------------------------------------------------------------
&1 (left ) : {p0 : ptxt option, ek : eK, c0 : ctxt}
&2 (right) : {p1 : ptxt option, ek : eK, c0 : ctxt}
p0 <@ E.dec(ek, c0)        (1)
p1 <@ E.dec(ek, c0)        (2)
post = p0{1} = p1{2}
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["program_frontier"] = {
        "call_sites": [
            {
                "side": "left",
                "side_index": 1,
                "procedure": "E.dec",
                "statement": "p0 <@ E.dec(ek, c0)",
            },
            {
                "side": "right",
                "side_index": 2,
                "procedure": "E.dec",
                "statement": "p1 <@ E.dec(ek, c0)",
            },
        ]
    }
    snapshot.raw_workspace_view["application_context"] = {
        "selected_handles": [{"name": "E_dec_ll", "kind": "lossless lemma"}]
    }

    view = manager._project(snapshot)
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    assert "one_sided_call_surface" not in upgrade["call_site_surface"]


def test_seq_local_structural_checkpoints_are_surface_and_menu(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "seq 1 1: (={x}).\n"
        "wp.\n"
        "smt().\n",
        encoding="utf-8",
    )
    snapshot = _route_snapshot(manager, "Current goal\npost = ={x}")

    view = manager._project(snapshot)

    checkpoints = view["structural_checkpoints"]["items"]
    by_semantic = {
        semantic_id
        for item in checkpoints
        for semantic_id in item.get("semantic_ids", [item.get("semantic_id")])
    }
    assert "before_seq_cut" in by_semantic
    assert "after_seq_opened" in by_semantic
    assert "before_branch_work" in by_semantic
    assert any(item["undo_scope"] == "branch_local" for item in checkpoints)
    assert checkpoints[0]["semantic_id"] == "before_branch_work"

    turn = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')
    options = turn.workspace_view["last_result"]["checkpoint_options"]
    assert options[0]["semantic_id"] == "before_branch_work"
    assert any("after_seq_opened" in item.get("semantic_ids", []) for item in options)
    assert any(item["undo_scope"] == "branch_local" for item in options)


def test_l4_frame_obligation_ledger_reports_dropped_frame_fact(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv (_ : ={glob A} ==> post)=> //.\n"
        "proc.\n"
        "seq 5 3 : (UFCMA.bad1{1} => event_bound).\n"
        "sp 4 2.\n",
        encoding="utf-8",
    )
    goal = """
Current goal
(glob A){1} = (glob A){2}
"""

    view = manager._project(_route_snapshot(manager, goal))
    preview = apply_workspace_view_surface_profile(view, "l4_preview_diagnostic")
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    assert "frame_obligation_ledger" not in preview
    ledger = upgrade["frame_obligation_ledger"]
    required = {item["fact"] for item in ledger["required_later"]}
    assert "={glob A}" in required
    dropped = ledger["possibly_dropped"][0]
    assert dropped["fact"] == "={glob A}"
    assert dropped["boundary"] == "seq #3"
    assert dropped["related_checkpoint"]["submit"]["intent"] == "undo_to_checkpoint"
    assert "should" not in json.dumps(ledger).lower()


def test_l4_frame_obligation_ledger_ignores_top_level_only_frame_fact(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv (_ : ={glob A} ==> post)=> //.\n"
        "proc.\n"
        "seq 5 3 : (UFCMA.bad1{1} => event_bound).\n"
        "sp 4 2.\n",
        encoding="utf-8",
    )
    goal = """
Current goal
UFCMA.bad1{1} => event_bound
"""

    view = manager._project(_route_snapshot(manager, goal))
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    assert "frame_obligation_ledger" not in upgrade


def test_l4_frame_obligation_ledger_suppresses_carried_frame_fact(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv (_ : ={glob A} ==> post)=> //.\n"
        "proc.\n"
        "seq 5 3 : (={glob A} /\\ UFCMA.bad1{1} => event_bound).\n"
        "sp 4 2.\n",
        encoding="utf-8",
    )
    goal = """
Current goal
(glob A){1} = (glob A){2}
"""

    view = manager._project(_route_snapshot(manager, goal))
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    assert "frame_obligation_ledger" not in upgrade


def test_l4_frame_obligation_ledger_ignores_local_equalities_from_step3_tail(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "call (_: inv_cpa RO1.m{1} RO2.m{1} Mem.log{1} Mem.log{2}).\n"
        "seq 1 1 : (n{1} = n{2} /\\ a{1} = a{2} /\\ p{1} = p{2}).\n"
        "skip.\n",
        encoding="utf-8",
    )
    goal = """
Current goal
pre =
  n{1} = n{2} /\\
  a{1} = a{2} /\\
  p{1} = p{2}
"""

    view = manager._project(_route_snapshot(manager, goal))
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    assert "frame_obligation_ledger" not in upgrade


def test_l4_frame_obligation_ledger_ignores_prior_proof_segment_boundaries(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "congr.\n"
        "call (_: Mem.k{1} = IndBlock.k{2}).\n"
        "proc; inline *; sim.\n"
        "have H : equiv[M.f ~ N.g : ={glob A} ==> ={res}].\n",
        encoding="utf-8",
    )
    goal = """
Current goal
equiv[M.f ~ N.g : ={glob A} ==> ={res}]
"""

    view = manager._project(_route_snapshot(manager, goal))
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    assert "frame_obligation_ledger" not in upgrade


def test_seq_cut_surface_prefers_rewound_seq_boundary(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "seq 5 3: (old_midpoint).\n"
        "sp 4 2.\n"
        "call (_: old_inv).\n"
        "inline init.\n"
        "sp 1 1.\n"
        "call (_: old_inv).\n"
        "inline init2.\n"
        "sp 1 1.\n"
        "call (_: old_inv).\n"
        "inline init3.\n"
        "sp 1 1.\n"
        "call (_: old_inv).\n"
        "proc.\n"
        "sp.\n"
        "if.\n"
        "smt().\n"
        "wp.\n"
        "inline enc.\n"
        "wp; sp.\n"
        "inline set_bad1.\n"
        "sp.\n"
        "inline cc.\n"
        "sp.\n"
        "inline EncRnd.cc.\n"
        "sp.\n",
        encoding="utf-8",
    )
    goal = """
Current goal (remaining: 8)
pre = true
while (p2 <> []) { z <$ dblock }
post = true
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["proof_status"]["view_focus"] = "relational_program"
    latest_observation = {
        "intent": "undo_to_checkpoint",
        "payload": {"checkpoint_id": "cp_28_49264619fd80d1b8"},
        "kind": "checkpoint_rewind",
        "message": "Rewound this branch to before committed tactic #28.",
        "tactic_index": 28,
        "committed_tactic": "seq 1 1 : (={glob A} /\\ inv_tail).",
        "undone_tactic_count": 74,
    }

    view = manager._project(snapshot, latest_observation=latest_observation)
    surface = view["seq_cut_surface"]

    assert surface["state"] == "before_rewound_seq_cut"
    assert surface["seq_candidate_id"] == "cp_28_49264619fd80d1b8"
    assert surface["cut_position"]["tactic"] == "seq 1 1 : (={glob A} /\\ inv_tail)."
    assert surface["restored_boundary"]["boundary_status"] == (
        "not_committed_in_current_state"
    )
    residual = surface["residual_frontier"]
    assert residual["latest_committed_seq_tactic_index"] == 3
    assert residual["rewound_seq_tactic_index"] == 28
    assert "latest_seq_tactic_index" not in residual
    health = view["candidate_moves"]["route_health"][0]
    assert health["signal"] == "seq_boundary_restored"
    assert health["recovery_class"] == "seq_midpoint_repair_evidence"
    assert view["recovery_diagnosis_surface"]["recovery_class"] == (
        "seq_midpoint_repair_evidence"
    )
    assert "should" not in json.dumps(surface).lower()


def test_recovery_diagnosis_reports_seq_midpoint_repair_for_branch_mismatch(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "seq 1 1: (={p}).\n"
        "wp.\n"
        "auto.\n",
        encoding="utf-8",
    )
    _record_route_event_facts(manager, [{
        "intent": "commit_tactic",
        "tactic": "smt().",
        "tactic_head": "smt",
        "rejected": True,
        "error_summary": "SMT failed",
    }])
    goal = r"""
Current goal
forall &1 &2,
  p{1} = p{2} =>
  (forall n0 c0, (n0, c0) \in ROF.m{1} => n0 \in BNR.lenc{1})
"""

    view = manager._project(_route_snapshot(manager, goal))

    health = view["candidate_moves"]["route_health"][0]
    assert health["signal"] == "seq_cut_mismatch"
    assert health["recovery_class"] == "seq_midpoint_repair_evidence"
    assert health["recommended_next"] == health["repair_checkpoint"]["submit"]
    diagnosis = view["recovery_diagnosis_surface"]
    assert diagnosis["recovery_class"] == "seq_midpoint_repair_evidence"
    assert diagnosis["checkpoint_policy"] == "seq_local_checkpoint_visible"
    assert diagnosis["related_checkpoints"]


def test_l4_pure_tail_surface_reports_map_projection_memory_gap(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "seq 1 1: (={p}).\n"
        "wp.\n"
        "rnd.\n"
        "skip.\n",
        encoding="utf-8",
    )
    goal = r"""
Current goal
forall &1 &2,
  p{1} = p{2} =>
  (forall n0 c0,
     (n0, c0) \in ROF.m{1}.[(p{2}.`1, c1{2}) <- r{1}] =>
     n0 \in n{1} :: BNR.lenc{1})
"""

    view = manager._project(_route_snapshot(manager, goal))
    preview = apply_workspace_view_surface_profile(view, "l4_preview_diagnostic")
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    assert "pure_tail_surface" not in preview
    assert "recovery_diagnosis_surface" not in preview
    surface = upgrade["pure_tail_surface"]
    families = {
        item["family"]
        for item in surface["obligation_families"]
    }
    assert "map_update_projection" in families
    assert "constructor_projection" in families
    assert "map_membership_preservation" in families
    assert surface["ambient_memory_translation"]["visible_decorations"]
    assert surface["gap_analysis"][0]["signal"] == (
        "map_key_membership_head_alignment"
    )
    reversible = surface["gap_analysis"][0]["reversible_to"][0]
    assert "before_branch_work" in reversible.get(
        "semantic_ids",
        [reversible.get("semantic_id")],
    )
    assert reversible["undo_scope"] == "branch_local"
    reversible_ids = {
        item.get("semantic_id")
        for item in surface["gap_analysis"][0]["reversible_to"]
    } | {
        semantic_id
        for item in surface["gap_analysis"][0]["reversible_to"]
        for semantic_id in (item.get("semantic_ids") or [])
    }
    assert "before_seq_cut" in reversible_ids
    route_health = upgrade["candidate_moves"]["route_health"][0]
    assert route_health["signal"] == "pure_tail_alignment_gap"
    assert route_health["recovery_class"] == "local_pure_surgery_available"
    assert route_health["related_checkpoints"][0]["semantic_id"] == "before_branch_work"
    assert "repair_checkpoint" not in route_health
    assert "recommended_next" not in route_health
    diagnosis = upgrade["recovery_diagnosis_surface"]
    assert diagnosis["recovery_class"] == "local_pure_surgery_available"
    assert diagnosis["checkpoint_policy"] == "current_state_local_work_visible"
    assert any(
        item["kind"] == "pure_tail_obligation_families"
        for item in diagnosis["available_local_work"]
    )
    assert "submit" not in json.dumps(diagnosis.get("related_checkpoints", []))
    assert "should" not in json.dumps(surface).lower()


def test_l4_pure_tail_gap_suppresses_stale_call_boundary_signal(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "call (_: inv_cpa ROin.m ROout.m).\n"
        "proc.\n"
        "sp 4 0; inline{1} *.\n"
        "seq 1 1: (={p}).\n"
        "wp.\n"
        "rnd.\n"
        "skip.\n",
        encoding="utf-8",
    )
    goal = r"""
Current goal
forall &1 &2,
  p{1} = p{2} =>
  (forall n0 c0,
     (n0, c0) \in ROF.m{1}.[(p{2}.`1, c1{2}) <- r{1}] =>
     n0 \in n{1} :: BNR.lenc{1})
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["proof_status"] = {
        "goal_type": "ambient",
        "current_layer": "ambient_logic",
        "view_focus": "pure_tail",
    }
    snapshot.raw_workspace_view["program_frontier"] = {
        "authority": "proof-state analysis",
        "call_sites": [],
    }
    snapshot.raw_workspace_view["candidate_moves"] = {
        "moves": [
            {
                "title": "Named-call context",
                "category": "strategy",
                "tactic_shape": "ecall (equ_cc <nonce> <ROin> <ROout>).",
                "applicability": (
                    "Use as route context; current frontier determines "
                    "whether this named oracle-equivalence applies."
                ),
            }
        ]
    }

    view = manager._project(snapshot)
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")

    signals = [
        item["signal"]
        for item in upgrade["candidate_moves"]["route_health"]
    ]
    assert signals[0] == "pure_tail_alignment_gap"
    assert "lost_call_abstraction_boundary" not in signals
    assert upgrade["recovery_diagnosis_surface"]["recovery_class"] == (
        "local_pure_surgery_available"
    )
    assert not upgrade["candidate_moves"].get("moves")
    assert "call_site_surface" not in upgrade


def test_l4_pure_tail_surface_suppresses_gap_when_alignment_visible(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\nproc.\nseq 1 1: (={p}).\nwp.\n",
        encoding="utf-8",
    )
    goal = r"""
Current goal
forall &1 &2,
  p{2}.`1 = n{1} =>
  (forall n0 c0,
     (n0, c0) \in ROF.m{1}.[(p{2}.`1, c1{2}) <- r{1}] =>
     n0 \in n{1} :: BNR.lenc{1})
"""

    view = manager._project(_route_snapshot(manager, goal))
    surface = apply_workspace_view_surface_profile(
        view,
        "l4_checked_action_surface",
    )["pure_tail_surface"]

    assert not any(
        item["signal"] == "map_key_membership_head_alignment"
        for item in surface.get("gap_analysis", [])
    )


def test_l4_pure_tail_surface_reports_local_membership_and_witness_sources(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "seq 6 4: (={p}).\n"
        "wp.\n"
        "rnd.\n"
        "skip.\n",
        encoding="utf-8",
    )
    goal = r"""
Current goal
H16:
  (t1, t') \in
    UFCMA_l.lbad1{2} ++
    map (fun t'0 => (t0L, t'0))
      (map (fun c3 => c3.`4)
        (filter (fun c3 => c3.`1 = p{2}.`1) Mem.lc{2}))
exists (n1 : nonce),
  (n1 = p{2}.`1 \/ n1 \in BNR.lenc{2}) /\
  (oget UFCMA.log{2}.[p{2}.`1 <- (a{2}, c1{2}, t1)].[n1]).`3 = t1
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["proof_status"] = {
        "goal_type": "ambient",
        "current_layer": "ambient_logic",
        "view_focus": "pure_tail",
    }

    upgrade = apply_workspace_view_surface_profile(
        manager._project(snapshot),
        "l4_checked_action_surface",
    )
    surface = upgrade["pure_tail_surface"]
    membership = surface["membership_decomposition_surface"]
    witnesses = surface["existential_witness_surface"]
    lookup = surface["map_update_lookup_surface"]

    assert {
        "concat_membership",
        "map_membership",
        "filter_membership",
    } <= set(membership["source_shapes"])
    assert any(item.get("name") == "n1" for item in witnesses["binders"])
    witness_sources = {
        item["source"]
        for item in witnesses["candidate_sources"]
    }
    assert "map_update_key" in witness_sources
    assert "membership_member" in witness_sources
    assert any(
        item["case"] in {"key_case_unresolved", "same_key_visible", "update_key"}
        for item in lookup["key_cases"]
    )
    assert surface["gap_analysis"][0]["signal"] == (
        "local_membership_decomposition_available"
    )
    health = upgrade["candidate_moves"]["route_health"][0]
    assert health["signal"] == "local_membership_decomposition_available"
    assert health["recovery_class"] == "local_pure_surgery_available"
    assert "repair_checkpoint" not in health
    diagnosis = upgrade["recovery_diagnosis_surface"]
    assert diagnosis["recovery_class"] == "local_pure_surgery_available"
    assert any(
        item["kind"] == "membership_decomposition_sources"
        for item in diagnosis["available_local_work"]
    )
    assert "should" not in json.dumps(surface).lower()


def test_recovery_diagnosis_prioritizes_local_pure_surgery_when_seq_noise_exists(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\n"
        "proc.\n"
        "seq 6 4: (={p}).\n"
        "wp.\n",
        encoding="utf-8",
    )
    _record_route_event_facts(manager, [{
        "intent": "commit_tactic",
        "tactic": "smt(mem_cat mapP).",
        "tactic_head": "smt",
        "rejected": True,
        "error_summary": "SMT failed",
    }])
    goal = r"""
Current goal
H16:
  (t1, t') \in
    UFCMA_l.lbad1{2} ++
    map (fun t'0 => (t0L, t'0))
      (map (fun c3 => c3.`4)
        (filter (fun c3 => c3.`1 = p{2}.`1) Mem.lc{2}))
exists (n1 : nonce),
  (n1 = p{2}.`1 \/ n1 \in BNR.lenc{2}) /\
  (oget UFCMA.log{2}.[p{2}.`1 <- (a{2}, c1{2}, t1)].[n1]).`3 = t1
"""
    snapshot = _route_snapshot(manager, goal)
    snapshot.raw_workspace_view["proof_status"] = {
        "goal_type": "ambient",
        "current_layer": "ambient_logic",
        "view_focus": "pure_tail",
    }

    upgrade = apply_workspace_view_surface_profile(
        manager._project(snapshot),
        "l4_checked_action_surface",
    )
    signals = [
        item["signal"]
        for item in upgrade["candidate_moves"]["route_health"]
    ]
    assert "seq_cut_mismatch" in signals
    assert "local_membership_decomposition_available" in signals
    diagnosis = upgrade["recovery_diagnosis_surface"]
    assert diagnosis["recovery_class"] == "local_pure_surgery_available"
    assert diagnosis["checkpoint_policy"] == "current_state_local_work_visible"
    assert any(
        item["kind"] == "membership_decomposition_sources"
        for item in diagnosis["available_local_work"]
    )


def test_recovery_diagnosis_does_not_promote_stale_call_signal_over_pure_tail(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\nproc.\nseq 1 1: (={p}).\nwp.\nskip.\n",
        encoding="utf-8",
    )
    goal = r"""
Current goal
forall &1 &2,
  p{1} = p{2} =>
  (forall n0 c0,
     (n0, c0) \in ROF.m{1}.[(p{2}.`1, c1{2}) <- r{1}] =>
     n0 \in n{1} :: BNR.lenc{1})
"""
    view = apply_workspace_view_surface_profile(
        manager._project(_route_snapshot(manager, goal)),
        "l4_checked_action_surface",
    )
    route_health = _annotate_route_health_items([
        {
            "signal": "lost_call_abstraction_boundary",
            "confidence": "medium",
            "evidence": ["stale named call context", "current state has no live call site"],
        }
    ])

    diagnosis = _recovery_diagnosis_surface(view, route_health=route_health)

    assert diagnosis["recovery_class"] == "local_pure_surgery_available"
    assert diagnosis["checkpoint_policy"] == "current_state_local_work_visible"
    assert any(
        item["kind"] == "pure_tail_obligation_families"
        for item in diagnosis["available_local_work"]
    )


def test_global_frame_gap_blocks_local_pure_surgery_classification(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv (_ : ={glob A} ==> post)=> //.\n"
        "proc.\n"
        "call (_: ={Mem.lc, Mem.log}).\n"
        "proc.\n"
        "inline *.\n",
        encoding="utf-8",
    )
    goal = r"""
Current goal (remaining: 5)
&1 (left ) : {b : bool} [programs are in sync]
&2 (right) : {b : bool}

pre =
  Mem.lc{1} = Mem.lc{2} /\
  Mem.log{1} = Mem.log{2}

post =
  (glob A){1} = (glob A){2} /\
  Mem.lc{1} = Mem.lc{2} /\
  Mem.log{1} = Mem.log{2}
"""

    view = manager._project(_route_snapshot(manager, goal))

    health = view["candidate_moves"]["route_health"][0]
    assert health["signal"] == "frame_boundary_gap"
    assert health["recovery_class"] == "boundary_repair_evidence"
    assert health["repair_checkpoint"]["tactic_index"] == 3
    assert health["recommended_next"] == health["repair_checkpoint"]["submit"]
    diagnosis = view["recovery_diagnosis_surface"]
    assert diagnosis["recovery_class"] == "boundary_repair_evidence"
    assert diagnosis["confidence"] == "high"
    assert "={glob A}" in json.dumps(diagnosis)


def test_local_recovery_demotes_stale_structural_rewind_payload() -> None:
    view = {
        "candidate_moves": {
            "route_health": [
                {
                    "signal": "lost_call_abstraction_boundary",
                    "recovery_class": "call_frontier_recovery_evidence",
                    "recommended_next": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": "cp_outer"},
                    },
                    "primary_next_action": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": "cp_outer"},
                    },
                    "repair_checkpoint": {
                        "checkpoint_id": "cp_outer",
                        "semantic_id": "last_call_site_boundary",
                        "label": "Before broad inline #99",
                        "tactic_index": 99,
                        "why_here": "Return before a stale call boundary.",
                        "submit": {
                            "intent": "undo_to_checkpoint",
                            "payload": {"checkpoint_id": "cp_outer"},
                        },
                    },
                }
            ]
        }
    }

    out = _workspace_view_with_recovery_consistent_route_health(
        view,
        {"recovery_class": "local_pure_surgery_available"},
    )

    health = out["candidate_moves"]["route_health"][0]
    assert health["signal"] == "lost_call_abstraction_boundary"
    assert health["related_checkpoints"][0]["semantic_id"] == (
        "last_call_site_boundary"
    )
    assert "recommended_next" not in health
    assert "primary_next_action" not in health
    assert "repair_checkpoint" not in health
    assert "submit" not in json.dumps(health)


def test_structural_recovery_keeps_rewind_payload() -> None:
    view = {
        "candidate_moves": {
            "route_health": [
                {
                    "signal": "lost_call_abstraction_boundary",
                    "recovery_class": "call_frontier_recovery_evidence",
                    "recommended_next": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": "cp_outer"},
                    },
                    "repair_checkpoint": {
                        "checkpoint_id": "cp_outer",
                        "semantic_id": "last_call_site_boundary",
                        "label": "Before broad inline #99",
                        "tactic_index": 99,
                        "submit": {
                            "intent": "undo_to_checkpoint",
                            "payload": {"checkpoint_id": "cp_outer"},
                        },
                    },
                }
            ]
        }
    }

    out = _workspace_view_with_recovery_consistent_route_health(
        view,
        {"recovery_class": "call_frontier_recovery_evidence"},
    )

    health = out["candidate_moves"]["route_health"][0]
    assert health["recommended_next"]["intent"] == "undo_to_checkpoint"
    assert health["repair_checkpoint"]["submit"]["intent"] == "undo_to_checkpoint"


def test_fresh_restart_inside_seq_scope_returns_structural_recovery_menu(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\nproc.\nseq 1 1: (={x}).\nwp.\n",
        encoding="utf-8",
    )

    def fail_backend():
        raise AssertionError("bare fresh_restart inside seq scope must not restart")

    manager.repl.fresh_restart = fail_backend  # type: ignore[method-assign]
    turn = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')

    last = turn.workspace_view["last_result"]
    assert last["kind"] == "structural_recovery_menu"
    assert last["checkpoint_options"]
    assert any(
        item["undo_scope"] in {"seq_local", "branch_local"}
        for item in last["checkpoint_options"]
    )
    destructive = last["options"][-1]["submit"]
    assert destructive["intent"] == "fresh_restart"
    assert destructive["payload"]["confirm"] is True


def test_resume_fresh_restart_inside_seq_scope_has_no_destructive_option(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    manager._replay_prefix_count = 2
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\nproc.\nseq 1 1: (={x}).\nwp.\n",
        encoding="utf-8",
    )

    def fail_backend():
        raise AssertionError("resume fresh_restart inside seq scope must not restart")

    manager.repl.fresh_restart = fail_backend  # type: ignore[method-assign]
    turn = manager.handle_agent_message('{"intent":"fresh_restart","payload":{}}')

    last = turn.workspace_view["last_result"]
    assert last["kind"] == "structural_recovery_menu"
    assert last["checkpoint_options"]
    assert all(
        option["submit"]["intent"] != "fresh_restart"
        for option in last["options"]
    )


def test_route_health_reports_sim_not_ready_and_frontier_placement(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    _record_route_event_facts(manager, [
        {
            "intent": "commit_tactic",
            "tactic": "sim.",
            "tactic_head": "sim",
            "rejected": True,
            "error_summary": "cannot infer the set of equalities",
        },
        {
            "intent": "commit_tactic",
            "tactic": "while (Inv).",
            "tactic_head": "while",
            "rejected": True,
            "error_summary": "invalid last instruction",
        },
    ])
    goal = """
Current goal
left-only frontier: r <$ dpoly_in
right-only frontier: if b { x <- y }
pre = a{1} = a{2}
post = a{1} = a{2}
"""

    view = manager._project(_route_snapshot(manager, goal))

    signals = [
        item["signal"]
        for item in view["candidate_moves"]["route_health"]
    ]
    assert "frontier_placement" in signals
    assert "local_tool_not_ready" in signals
    assert "possible_boundary_gap" not in signals


def test_route_health_recommends_conseq_for_prhl_post_compression(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    goal = r"""
Current goal
pre =
  n{1} = n{2} /\
  a{1} = a{2} /\
  c0{1} = c0{2}
t0 <$ dpoly_out     t0 <$ dpoly_out
post =
  if x{1} \\notin RO.m{1} then
    forall result_L result_R, result_L = result_R =>
      n{1} = n{2} /\ a{1} = a{2} /\ c0{1} = c0{2}
  else
    let m_R = RO.m{2} in n{1} = n{2} /\ a{1} = a{2}
"""

    view = manager._project(_route_snapshot(manager, goal))

    health = view["candidate_moves"]["route_health"][0]
    assert health["signal"] == "prhl_surgery_sequence_needed"
    assert health["recovery_class"] == "residual_program_surgery_available"
    assert health["checkpoint_policy"] == "current_state_residual_work_visible"
    assert health["recommended_next"]["intent"] == "commit_tactic"
    assert health["recommended_next"]["payload"]["tactic"].startswith("conseq")
    diagnosis = view["recovery_diagnosis_surface"]
    assert diagnosis["recovery_class"] == "residual_program_surgery_available"
    assert any(
        item["kind"] == "residual_program_surgery"
        for item in diagnosis["available_local_work"]
    )


def test_structural_transition_wp_is_separate_from_route_health(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    _record_route_event_facts(manager, [{
        "intent": "inspect_context",
        "topic": "align",
        "accepted": True,
        "changed": False,
    }])
    goal = r"""
Current goal
pre = a{1} = a{2}
post =
  if x{1} \\notin RO.m{1} then
    forall result_L result_R, result_L = result_R =>
      a{1} = a{2}
  else a{1} = a{2}
"""

    view = manager._project(_route_snapshot(manager, goal))

    candidate_moves = view["candidate_moves"]
    assert [
        item["signal"]
        for item in candidate_moves.get("route_health", [])
    ] == ["prhl_surgery_sequence_needed"]
    assert view["recovery_diagnosis_surface"]["recovery_class"] == (
        "residual_program_surgery_available"
    )
    transition = candidate_moves["structural_transitions"][0]
    assert transition["id"] == "post_wp_surgery"
    assert transition["status"] == "candidate_reversible_transition"
    assert transition["recommended_next"]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "wp."},
    }


def test_structural_transition_surfaces_random_tuple_swap_under_probability_budget(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    goal = r"""
Current goal
Bound   : [<=] (PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)
pre = true
(13)  (m0, m1) <@ G4.A.choose(G1.k, g, G1.g_, e, f, h)
(14)  G1.u <$ dt
(15)  G1.u' <$ dt \ pred1 G1.u
(16)  r' <$ dt
(17)  r <$ dt
post =
  let a = g ^ G1.u in
  let a_ = G1.g_ ^ G1.u' in
  let c = g ^ r' in let d = g ^ r in (a, a_, c, d) \in G3.cilog
"""

    view = manager._project(_route_snapshot(manager, goal))

    transition = view["candidate_moves"]["structural_transitions"][0]
    assert transition["tactic"] == "swap [14..17] -1."
    assert transition["recommended_next"]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "swap [14..17] -1."},
    }
    assert transition["detected_shape"] == {
        "kind": "random_tuple_after_call_under_product_budget",
        "call_statement": 13,
        "sample_statements": [14, 15, 16, 17],
        "event_mentions": ["G1.u", "G1.u'", "r'", "r"],
    }
    preview = apply_workspace_view_surface_profile(view, "l4_preview_diagnostic")
    assert not any(
        item.get("tactic") == "swap [14..17] -1."
        for item in preview.get("candidate_moves", {}).get(
            "structural_transitions",
            [],
        )
    )
    upgrade = apply_workspace_view_surface_profile(view, "l4_checked_action_surface")
    assert any(
        item.get("tactic") == "swap [14..17] -1."
        for item in upgrade["candidate_moves"]["structural_transitions"]
    )


def test_structural_transition_does_not_repeat_wp_after_entering_post_wp(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    _record_route_event_facts(manager, [{
        "intent": "commit_tactic",
        "tactic": "wp.",
        "tactic_head": "wp",
        "accepted": True,
        "changed": True,
    }])
    goal = r"""
Current goal
pre = a{1} = a{2}
post =
  if x{1} \\notin RO.m{1} then
    forall result_L result_R, result_L = result_R =>
      a{1} = a{2}
  else a{1} = a{2}
"""

    view = manager._project(_route_snapshot(manager, goal))

    candidate_moves = view["candidate_moves"]
    assert [
        item["signal"]
        for item in candidate_moves.get("route_health", [])
    ] == ["prhl_surgery_sequence_needed"]
    assert "structural_transitions" not in candidate_moves


def test_structural_transition_stays_suppressed_after_post_wp_inline(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    _record_route_event_facts(manager, [
        {
            "intent": "commit_tactic",
            "tactic": "wp.",
            "tactic_head": "wp",
            "accepted": True,
            "changed": True,
        },
        {
            "intent": "commit_tactic",
            "tactic": "inline RO.sample ROout.set.",
            "tactic_head": "inline",
            "accepted": True,
            "changed": True,
        },
    ])
    goal = r"""
Current goal
pre = a{1} = a{2}
post =
  if x{1} \\notin RO.m{1} then
    forall result_L result_R, result_L = result_R =>
      a{1} = a{2}
  else a{1} = a{2}
"""

    view = manager._project(_route_snapshot(manager, goal))

    assert "structural_transitions" not in view["candidate_moves"]


def test_structural_transition_can_reappear_after_post_wp_phase_closes(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    _record_route_event_facts(manager, [
        {
            "intent": "commit_tactic",
            "tactic": "wp.",
            "tactic_head": "wp",
            "accepted": True,
            "changed": True,
        },
        {
            "intent": "commit_tactic",
            "tactic": "skip; smt().",
            "tactic_head": "skip",
            "accepted": True,
            "changed": True,
        },
    ])
    goal = r"""
Current goal
pre = a{1} = a{2}
post =
  if y{1} \\notin RO.m{1} then
    forall result_L result_R, result_L = result_R =>
      a{1} = a{2}
  else a{1} = a{2}
"""

    view = manager._project(_route_snapshot(manager, goal))

    transition = view["candidate_moves"]["structural_transitions"][0]
    assert transition["id"] == "post_wp_surgery"
    assert transition["recommended_next"]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "wp."},
    }


def test_route_health_binds_checkpoint_menu_to_boundary_debt(
    tmp_path: Path,
) -> None:
    manager = _manager_with_view(tmp_path)
    history = Path(manager.repl.session_dir) / "history.ec"
    history.write_text(
        "byequiv=>//.\nproc.\ncall (_: ={UFCMA_l.lbad1}).\nsp.\nwp.\n",
        encoding="utf-8",
    )
    manager.latest_view = {
        "candidate_moves": {
            "route_health": [
                {
                    "signal": "possible_boundary_gap",
                    "repair_checkpoint": {
                        "label": "Before call invariant #3",
                        "tactic_index": 3,
                        "why_here": (
                            "This call invariant likely omitted lbad1/size "
                            "facts now needed by residual goals."
                        ),
                    },
                }
            ]
        }
    }

    turn = manager.handle_agent_message('{"intent":"undo_to_checkpoint","payload":{}}')

    option = turn.workspace_view["last_result"]["checkpoint_options"][0]
    assert option["label"] == "Before call invariant #3"
    assert option["tactic_index"] == 3
    assert "omitted lbad1/size" in option["why_checkpoint"]
