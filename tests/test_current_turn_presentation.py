from __future__ import annotations

from workflow.proof_state_compiler.current_turn_presentation import (
    compose_current_surface_turn,
    render_current_surface_turn_markdown,
    require_current_workspace_view,
)
from workflow.proof_node_runtime import ProofNodeRuntime
from core.easycrypt.proof_state_compiler.backend.presentation import (
    render_action_surface_payload,
)


def _view(**overrides) -> dict:
    view = {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "remaining_goals_known": True,
            "goal_identity_required": True,
            "goal_hash": "goal-hash",
        },
        "last_result": {},
        "current_goal": {
            "lines": ["Current goal", "x : int", "---", "x = x"],
            "line_count": 4,
            "truncated": False,
        },
        "view_hash": "view-hash",
    }
    view.update(overrides)
    return view


def _compiler_markdown(*, actions: list[dict] | None = None) -> str:
    return render_action_surface_payload({
        "schema_version": 1,
        "resources": [],
        "bindings": [],
        "actions": list(actions or []),
        "diagnostics": [],
    }).text


def test_current_view_contract_needs_no_legacy_carrier_panels() -> None:
    view = require_current_workspace_view(
        _view(),
        profile_id="l1_goal_projection",
        label="test current view",
    )

    assert set(view) == {
        "schema_version",
        "kind",
        "ok",
        "proof_status",
        "last_result",
        "current_goal",
        "view_hash",
    }


def test_current_goal_markdown_matches_current_contract() -> None:
    current = compose_current_surface_turn(
        _view(),
        "l1_goal_projection",
    )
    assert render_current_surface_turn_markdown(current) == (
        "## 🎯 Current Goal\n"
        "```\n"
        "Current goal\n"
        "x : int\n"
        "---\n"
        "x = x\n"
        "```"
    )


def test_empty_current_compiler_arms_are_byte_identical_to_l1() -> None:
    l1 = render_current_surface_turn_markdown(
        compose_current_surface_turn(_view(), "l1_goal_projection")
    )
    treatment = render_current_surface_turn_markdown(
        compose_current_surface_turn(
            _view(),
            "l4_proof_state_compiler_v2_operation_binding_repair",
            compiler_markdown="",
        )
    )
    audit = render_current_surface_turn_markdown(
        compose_current_surface_turn(
            _view(),
            "l4_proof_state_compiler_v2_operation_binding_repair_audit",
            compiler_markdown="",
        )
    )

    assert treatment == l1
    assert audit == l1


def test_current_recovery_action_uses_generic_delivery_renderer() -> None:
    turn = compose_current_surface_turn(
        _view(),
        "l4_proof_state_compiler_v2_operation_binding_repair",
        compiler_markdown=_compiler_markdown(actions=[{
                "intent": "commit_tactic",
                "payload": {"tactic": "call (L (<: M) _)."},
                "unresolved_premises": ["islossless M.f"],
                "presentation_kind": "failure_linked_repair",
                "checked_local_effect": {"remaining_goals": 1},
            }]),
    )

    markdown = render_current_surface_turn_markdown(turn)

    assert "## Checked repair for the attempted operation" in markdown
    assert '"intent":"commit_tactic"' in markdown
    assert "call (L (<: M) _)." in markdown
    assert "islossless M.f" in markdown
    assert "1 goal(s) remain" in markdown


def test_current_turn_embeds_compiler_markdown_byte_for_byte() -> None:
    compiler = _compiler_markdown(actions=[{
        "intent": "commit_tactic",
        "payload": {"tactic": "trivial."},
        "presentation_kind": "failure_linked_repair",
        "checked_local_effect": {"closed": True},
    }])
    turn = compose_current_surface_turn(
        _view(),
        "l4_proof_state_compiler_v2_operation_binding_repair",
        compiler_markdown=compiler,
    )

    rendered = render_current_surface_turn_markdown(turn)

    assert rendered.count(compiler) == 1


def test_finish_outcome_projects_only_authoritative_agent_observation() -> None:
    recalculation_trap = compose_current_surface_turn(
        _view(last_result={"intent": "finish", "result": "finished"}),
        "l1_goal_projection",
        handled_intent={"intent": "finish", "payload": {}},
        ok=True,
        manager_actions=[{
            "label": "finish",
            "exit_code": 0,
            "needs_attention": False,
            "agent_observation": {"result": "finished"},
        }],
    )
    assert recalculation_trap["turn_outcome"]["finish_accepted"] is False

    authoritative = compose_current_surface_turn(
        _view(last_result={"intent": "finish", "result": "finished"}),
        "l1_goal_projection",
        handled_intent={"intent": "finish", "payload": {}},
        ok=True,
        manager_actions=[{
            "label": "finish",
            "exit_code": 0,
            "agent_observation": {
                "kind": "finish_accepted",
                "result": "Finish accepted.",
            },
        }],
    )
    assert authoritative["turn_outcome"]["finish_accepted"] is True


def test_current_control_menu_preserves_prior_goal_surface() -> None:
    base = compose_current_surface_turn(_view(), "l1_goal_projection")
    menu_view = _view(
        current_goal={"lines": ["same goal"], "line_count": 1},
        last_result={
            "intent": "undo_to_checkpoint",
            "control_menu": {
                "title": "Rewind targets",
                "items": [{
                    "label": "Before call",
                    "submit": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": "before_call"},
                    },
                }],
            },
        },
    )
    turn = compose_current_surface_turn(
        menu_view,
        "l1_goal_projection",
        base_surface=base["proof_surface"],
        handled_intent={"intent": "undo_to_checkpoint", "payload": {}},
    )

    markdown = render_current_surface_turn_markdown(turn)

    assert turn["presentation_kind"] == "control_menu"
    assert turn["base_surface_updates"] is False
    assert "## Rewind targets" in markdown
    assert "Before call" in markdown
    assert "x = x" in markdown
    assert "same goal" not in markdown


def test_current_runtime_bootstrap_uses_current_presenter(tmp_path) -> None:
    bootstrap = {
        "schema_version": 3,
        "kind": "proof_node_manager_bootstrap",
        "node_id": "Tree-current",
        "session_tag": "current",
        "session_dir": ".ec_session_current",
        "file": "target.ec",
        "lemma": "target",
        "include_dirs": ["."],
        "replay_prefix_count": 0,
        "replay_prefix": [],
        "replay_prefix_requested_count": 0,
        "manager_actions": [],
        "snapshot": {
            "node_id": "Tree-current",
            "session_tag": "current",
            "session_dir": ".ec_session_current",
            "session_epoch": 0,
            "state_version": 0,
            "goal_hash": "goal-hash",
            "goal_identity_required": True,
            "workspace_view_artifact": "",
            "execution_refs": {},
        },
        "workspace_view": _view(),
    }
    runtime = ProofNodeRuntime(
        prompt="Target prompt",
        bootstrap=bootstrap,
        file_path="target.ec",
        lemma_name="target",
        include_dir=".",
        session_tag="current",
        node_id="Tree-current",
        run_dir=tmp_path,
        model="test",
        surface_profile="l1_goal_projection",
        project_root=tmp_path,
        emit=lambda _event: None,
    )

    initial = runtime.memory.initial_followup.read_text(encoding="utf-8")
    stored = runtime.memory.initial_view.read_text(encoding="utf-8")

    assert "## 🎯 Current Goal" in initial
    assert "x = x" in initial
    assert "program_frontier" not in initial
    assert "CurrentGoalEnvelope -> CurrentSurfaceTurn" in stored
