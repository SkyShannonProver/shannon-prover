from __future__ import annotations

import json

from workflow.surface_composer import compose_surface_model
from workflow.surface_model import surface_model_to_dict
from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown


PROFILE = "l4_checked_action_surface"


def _base_view() -> dict:
    return {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "procedure_body",
            "current_layer": "procedure_body",
            "goal_type": "pRHL",
        },
        "current_goal": {"lines": ["Current goal", "x = y"], "line_count": 2},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": "apply"}},
            {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
            {"intent": "operator_lemmas", "payload": {"operator": "size"}},
            {"intent": "inspect_context", "payload": {"topic": "goal_info"}},
            {"intent": "probe_tactic", "payload": {"tactic": "smt()."}},
        ]},
    }


def _surface_hash(view: dict) -> str:
    return surface_model_to_dict(compose_surface_model(view, PROFILE))["surface_model_hash"]


def test_read_only_tactic_forms_is_overlay_and_preserves_base_surface() -> None:
    base = _base_view()
    readonly = {
        **base,
        "last_result": {
            "intent": "tactic_forms",
            "payload": {"name": "apply"},
            "result": "Read-only context returned.",
            "proof_state": "unchanged",
            "content": {
                "title": "Tactic Form Reference",
                "preview": "=== apply tactic -- argument forms ===\nForm 1: apply LEMMA.",
            },
        },
    }

    turn = compose_surface_turn(
        readonly,
        PROFILE,
        base_view=base,
        handled_intent={"intent": "tactic_forms", "payload": {"name": "apply"}},
    )

    assert turn["presentation_kind"] == "read_only_overlay"
    assert turn["base_surface_updates"] is False
    assert turn["proof_surface"]["surface_model_hash"] == _surface_hash(base)
    assert turn["overlay_surface"]["phase"] == "context_result"
    overlay_keys = {
        fact["key"] for fact in turn["overlay_surface"]["primary_panel"]["facts"]
    }
    assert "request" not in overlay_keys
    assert "read_only_note" not in overlay_keys

    md = render_surface_turn_markdown(turn)
    assert "apply tactic -- argument forms" in md
    assert "## Continue from unchanged proof state" not in md
    assert "## Read-only result" in md
    assert md.index("## 🎯 Current Goal") < md.index("### Need more? submit one read-only request")
    assert md.index("### Need more? submit one read-only request") < md.index("## Read-only result")
    assert md.index("## Read-only result") < md.index("apply tactic -- argument forms")
    assert '"intent": "tactic_forms", "payload": {"name": "<name>"}' in md
    assert "\n\n---\n\n### Need more? submit one read-only request" in md
    assert "Read-only note" not in md
    assert "committed proof state unchanged" not in md


def test_read_only_markdown_keeps_proof_facts_before_overlay_result() -> None:
    base = {
        **_base_view(),
        "decision_context": {"up_to_bad_call": {
            "active_bad_events": ["UFCMA.bad1", "UFCMA.bad2"],
        }},
    }
    readonly = {
        **_base_view(),
        "last_result": {
            "intent": "tactic_forms",
            "payload": {"name": "conseq"},
            "result": "Read-only context returned.",
            "proof_state": "unchanged",
            "content": {
                "title": "Tactic Form Reference",
                "preview": "=== conseq tactic -- argument forms ===",
            },
        },
    }

    turn = compose_surface_turn(
        readonly,
        PROFILE,
        base_view=base,
        handled_intent={"intent": "tactic_forms", "payload": {"name": "conseq"}},
    )
    md = render_surface_turn_markdown(turn)

    assert md.index("Up-to-bad call compatibility") < md.index("## Read-only result")
    assert md.index("## Read-only result") < md.index("conseq tactic")


def test_markdown_fact_values_preserve_easycrypt_fragments() -> None:
    view = {
        **_base_view(),
        "decision_context": {"up_to_bad_call": {
            "active_bad_events": ["UFCMA.bad1", "UFCMA.bad2"],
        }},
    }
    turn = compose_surface_turn(view, PROFILE)

    md = render_surface_turn_markdown(turn)

    assert "`!(UFCMA.bad1 \\/ UFCMA.bad2)`" in md
    assert "`call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>).`" in md
    assert "- `active_bad_events`:\n  - UFCMA.bad1\n  - UFCMA.bad2" in md
    assert '["UFCMA.bad1"' not in md


def test_markdown_fact_list_preserves_inline_code_prose() -> None:
    turn = {
        "presentation_kind": "proof_state",
        "proof_surface": {
            "schema_version": 1,
            "goal": {"text": "Current goal\nx = y"},
            "status": {"remaining_goals": 1, "surface_phase": "deep_surgery"},
            "primary_panel": {
                "title": "Surgery -- align or decompose the two sides",
                "display_policy": {},
                "facts": [{
                    "label": "Where",
                    "value": [
                        "guarded `if` at left/right side 2, program position 7: "
                        "`rcondt{2} 7` or `rcondf{2} 7` -- guard `size Mem.lc <= qdec`"
                    ],
                }],
            },
            "actions": [],
        },
    }

    md = render_surface_turn_markdown(turn)

    assert "- guarded `if` at left/right side 2" in md
    assert "- ``guarded" not in md


def test_markdown_renders_whole_program_structure_values() -> None:
    view = {
        **_base_view(),
        "current_goal": {"goal_type": "pRHL", "lines": ["Current goal", "pre", "post"]},
        "program_frontier": {
            "current_frontier_scope": {
                "setup": {
                    "left": {"paths": ["1"], "summary": "k <- 0"},
                    "right": {
                        "paths": ["1", "2"],
                        "summary": "2 setup statement(s): k <- 0; m <- nth witness l i",
                    },
                },
                "frontier": {
                    "left": {
                        "head": "while",
                        "path": "2",
                        "statement": "while (k < size l) {",
                    },
                    "right": {
                        "head": "if",
                        "path": "3",
                        "statement": "if (m \\notin M.log) {",
                    },
                },
                "lookahead_after_frontier": [
                    {
                        "side": "left",
                        "path": "2.2.1",
                        "statement": "y <@ H.f(m)",
                        "procedure": "H.f",
                    },
                    {
                        "side": "right",
                        "path": "3.1",
                        "statement": "y <@ H.f(m)",
                        "procedure": "H.f",
                    },
                ],
            },
        },
    }

    md = render_surface_turn_markdown(compose_surface_turn(view, PROFILE))

    assert "Whole-program structure" in md
    assert "`left_regions`" in md and "setup-block(1) | while | call H.f" in md
    assert "`right_regions`" in md and "setup-block(2) | guarded if | call H.f" in md
    assert "mechanical top-level region sequence around the current frontier" not in md


def test_markdown_fact_list_of_dicts_is_not_json_blob() -> None:
    turn = {
        "presentation_kind": "read_only_overlay",
        "proof_surface": surface_model_to_dict(compose_surface_model(_base_view(), PROFILE)),
        "overlay_surface": {
            "schema_version": 1,
            "phase": "context_result",
            "goal": {"text": "Current goal\nx = y"},
            "status": {"remaining_goals": 1},
            "primary_panel": {
                "title": "Requested Context",
                "facts": [{
                    "label": "Items",
                    "value": [{
                        "candidate": "call (_: inv_cpa ‹ROin.m | ROout.m›{1}).",
                        "why": "type-matched menu; not literal syntax",
                    }],
                }],
            },
            "actions": [],
        },
    }

    md = render_surface_turn_markdown(turn)

    assert '{"candidate"' not in md
    assert "- `candidate`: `call (_: inv_cpa ‹ROin.m | ROout.m›{1}).`" in md
    assert "  `why`: type-matched menu" in md


def test_rejected_commit_updates_base_presentation_and_leads_before_goal() -> None:
    rejected = {
        **_base_view(),
        "last_result": {
            "intent": "commit_tactic",
            "tactic": "rewrite.",
            "result": "EasyCrypt rejected the committed tactic.",
            "error_summary": "[error] cannot rewrite the program head",
            "proof_state": "not changed",
        },
        "program_frontier": {
            "frontier_alignment": {
                "first_instruction_alignment": {
                    "left_head": "assignment",
                    "right_head": None,
                    "branch_alignment": "single_program_frontier",
                }
            }
        },
    }

    turn = compose_surface_turn(
        rejected,
        PROFILE,
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "rewrite."}},
        ok=True,
        manager_actions=[{"mutates_proof_state": True, "exit_code": 1}],
    )

    assert turn["presentation_kind"] == "proof_state"
    assert turn["base_surface_updates"] is True
    assert "overlay_surface" not in turn
    assert "control_menu" not in turn
    assert turn["turn_outcome"]["lead_before_goal"] is True
    md = render_surface_turn_markdown(turn)
    assert md.index("EasyCrypt rejected") < md.index("## 🎯 Current Goal")


def test_no_progress_commit_is_not_proof_state_changed_and_leads_before_goal() -> None:
    no_progress = {
        **_base_view(),
        "last_result": {
            "intent": "commit_tactic",
            "tactic": "rewrite /gen_CTR_encrypt_bytes /=.",
            "result": (
                "NO PROGRESS -- EasyCrypt ACCEPTED this commit but it did not "
                "change the goal, so nothing was committed (it auto-reverts)."
            ),
            "proof_state": "The committed EasyCrypt proof state was not changed.",
        },
    }

    turn = compose_surface_turn(
        no_progress,
        PROFILE,
        handled_intent={
            "intent": "commit_tactic",
            "payload": {"tactic": "rewrite /gen_CTR_encrypt_bytes /=."},
        },
        ok=True,
        manager_actions=[
            {
                "mutates_proof_state": True,
                "exit_code": 0,
                "agent_observation": no_progress["last_result"],
            }
        ],
    )

    assert turn["presentation_kind"] == "proof_state"
    assert turn["proof_state_changed"] is False
    assert turn["turn_outcome"]["proof_state_changed"] is False
    assert turn["turn_outcome"]["lead_before_goal"] is True
    md = render_surface_turn_markdown(turn)
    assert md.index("NO PROGRESS") < md.index("## 🎯 Current Goal")


def test_probe_disabled_reject_renders_repair_not_probe_preview() -> None:
    view = {
        **_base_view(),
        "last_result": {},
    }
    repair = (
        "`probe_tactic` is not an available proof intent on this surface. "
        "Commit directly with `commit_tactic`."
    )

    turn = compose_surface_turn(
        view,
        PROFILE,
        handled_intent={
            "intent": "probe_tactic",
            "payload": {"tactic": "byequiv => //."},
        },
        ok=False,
        repair_prompt=repair,
        manager_actions=[{"label": "probe_disabled_reject"}],
    )

    assert turn["presentation_kind"] == "proof_state"
    assert turn["base_surface_updates"] is False
    assert turn["turn_outcome"]["result_line"] == repair
    md = render_surface_turn_markdown(turn)
    assert repair in md
    assert "Probe returned" not in md
    assert "Probe preview" not in md


def test_bare_undo_to_checkpoint_is_typed_control_menu_without_base_update() -> None:
    base = _base_view()
    menu_view = {
        **base,
        "last_result": {
            "intent": "undo_to_checkpoint",
            "kind": "checkpoint_menu",
            "notice": "Choose a rewind target.",
            "checkpoint_options": [
                {
                    "label": "before_call_route",
                    "why_checkpoint": "rewind to the call route boundary",
                    "submit": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": "before_call_route"},
                    },
                }
            ],
        },
    }

    turn = compose_surface_turn(
        menu_view,
        PROFILE,
        base_view=base,
        handled_intent={"intent": "undo_to_checkpoint", "payload": {}},
    )

    assert turn["presentation_kind"] == "control_menu"
    assert turn["base_surface_updates"] is False
    assert turn["proof_surface"]["surface_model_hash"] == _surface_hash(base)
    menu = turn["control_menu"]
    assert menu["title"] == "Rewind targets"
    assert menu["items"][0]["submit"] == {
        "intent": "undo_to_checkpoint",
        "payload": {"checkpoint_id": "before_call_route"},
    }


def test_confirmed_rewind_updates_base_surface() -> None:
    view = {
        **_base_view(),
        "last_result": {
            "intent": "undo_to_checkpoint",
            "kind": "checkpoint_rewind",
            "result": "rewound to checkpoint",
            "proof_state": "changed",
        },
    }

    turn = compose_surface_turn(
        view,
        PROFILE,
        handled_intent={
            "intent": "undo_to_checkpoint",
            "payload": {"checkpoint_id": "before_call_route"},
        },
        manager_actions=[{"mutates_proof_state": True, "exit_code": 0}],
    )

    assert turn["presentation_kind"] == "proof_state"
    assert turn["base_surface_updates"] is True
    assert "control_menu" not in turn


def test_legacy_wrapper_and_probe_are_absent_from_surface_turn_actions() -> None:
    turn = compose_surface_turn(_base_view(), PROFILE)
    actions_blob = json.dumps(turn["proof_surface"].get("actions", []))
    assert "inspect_context" not in actions_blob
    assert "probe_tactic" not in actions_blob
