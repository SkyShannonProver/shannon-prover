from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.surface_composer import compose_surface_model
from workflow.surface_action_preflight import (
    action_preflight_key,
    derived_preflight_candidates,
    matching_preflight_submission,
    preflight_result_for_action,
    surface_preflight_candidates,
)
from workflow.surface_action_eligibility import (
    action_eligibility,
    preflight_candidate_state_eligibility,
)
from workflow.surface_model import PanelAction, surface_model_to_dict
from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown


PROFILE = "l4_checked_action_surface"
ROOT = Path(__file__).resolve().parents[1]


def _assignment_recover_view() -> dict:
    return {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "view_focus": "procedure_body",
            "current_layer": "recovery",
            "goal_type": "pRHL",
        },
        "current_goal": {"lines_preview": "x <- e\npost", "line_count": 2},
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
        "inspect_lookup_handles": {
            "ask_manager_for": [
                {"intent": "tactic_forms", "payload": {"name": "call"}},
                {"intent": "tactic_forms", "payload": {"name": "sp"}},
                {"intent": "tactic_forms", "payload": {"name": "while"}},
                {"intent": "tactic_forms", "payload": {"name": "wp"}},
                {"intent": "probe_tactic", "payload": {"tactic": "sp."}},
            ]
        },
    }


def test_tactic_form_choices_have_one_contract_owner() -> None:
    composer = (ROOT / "workflow" / "surface_composer.py").read_text(encoding="utf-8")
    eligibility = (ROOT / "workflow" / "surface_action_eligibility.py").read_text(encoding="utf-8")
    owner = (ROOT / "workflow" / "surface_tactic_forms.py").read_text(encoding="utf-8")
    panels = (ROOT / "workflow" / "surface_panels.py").read_text(encoding="utf-8")

    assert "from workflow.surface_tactic_forms import compose_tactic_form_actions" in composer
    assert "from workflow.surface_tactic_forms import eligible_tactic_form_names" in eligibility
    assert "def eligible_tactic_form_names" in owner
    assert "def compose_tactic_form_actions" in owner
    assert "def tactic_form_names_for_state" not in owner
    assert "_PROGRAM_TACTIC_FORMS" not in eligibility
    assert "def _plain_actions" not in composer
    assert "def _pure_actions" not in panels
    assert "def _deep_actions" not in panels


def test_panel_action_policy_has_one_contract_owner() -> None:
    composer = (ROOT / "workflow" / "surface_composer.py").read_text(encoding="utf-8")
    eligibility = (ROOT / "workflow" / "surface_action_eligibility.py").read_text(encoding="utf-8")
    owner = (ROOT / "workflow" / "surface_action_policy.py").read_text(encoding="utf-8")
    panels = (ROOT / "workflow" / "surface_panels.py").read_text(encoding="utf-8")

    assert "def panel_allowed_intents" in owner
    assert "PANEL_INTENTS" in owner
    assert "filter_surface_actions" in composer
    assert "filter_surface_facts" in composer
    assert "filter_surface_actions" not in panels
    assert "filter_surface_facts" not in panels
    assert "panel_allowed_intents" in eligibility
    assert "_PANEL_INTENTS" not in eligibility


def test_recover_surface_assignment_head_only_surfaces_assignment_families() -> None:
    model = surface_model_to_dict(
        compose_surface_model(_assignment_recover_view(), "l4_checked_action_surface")
    )
    panel = model["primary_panel"]
    assert panel["panel_id"] == "recovery"
    blob = json.dumps(panel, ensure_ascii=False)
    assert "head if" not in blob
    assert "head while" not in blob
    assert "head call" not in blob
    assert "head sample" not in blob
    assert "sp" in blob and "wp" in blob
    assert len(model["actions"]) == 1
    action = model["actions"][0]
    assert action["intent"] == "tactic_forms"
    assert action["payload"] == {"name": "<name>"}
    assert action["choices"] == {"name": ["sp", "wp"]}
    assert "probe_tactic" not in json.dumps(model)


def test_recover_surface_markdown_uses_model_not_legacy_head_table() -> None:
    view = _assignment_recover_view()
    turn = compose_surface_turn(
        view,
        PROFILE,
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "rewrite."}},
        ok=False,
    )
    md = render_surface_turn_markdown(turn)
    assert "Recover -- last committed tactic" in md
    assert md.index("EasyCrypt rejected") < md.index("Current Goal")
    assert md.index("Current Goal") < md.index("Recover --")
    assert "head if" not in md
    assert "head while" not in md
    assert "head call" not in md
    assert "head sample" not in md
    assert "name choices: `sp`, `wp`" in md
    assert '"intent": "tactic_forms", "payload": {"name": "<name>"}' in md
    assert '"name": "while"' not in md
    assert "probe_tactic" not in md


def test_surface_actions_are_registered_direct_intents() -> None:
    view = _assignment_recover_view()
    view["inspect_lookup_handles"]["ask_manager_for"].append({
        "intent": "inspect_context",
        "payload": {"topic": "operator_lemmas", "operator": "size"},
    })
    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    for action in model["actions"]:
        assert action["intent"] != "inspect_context"
        assert action["intent_class"] in {"context_topic", "symbol_lookup"}
        assert isinstance(action["payload"], dict)


def test_l1_goal_only_surface_has_no_context_actions_or_panel() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "procedure_body", "goal_type": "phoare"},
        "current_goal": {"lines": ["Current goal", "x <- 0", "post"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "goal_info", "payload": {}},
            {"intent": "operator_lemmas", "payload": {"operator": "OPERATOR"}},
            {"intent": "tactic_forms", "payload": {"name": "wp"}},
        ]},
    }

    model = surface_model_to_dict(
        compose_surface_model(view, "l1_goal_projection", goal_only=True)
    )

    assert model["phase"] == "goal_only"
    assert model.get("actions", []) == []
    assert "primary_panel" not in model


def test_read_only_context_result_is_surface_model_primary_panel() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "current_layer": "procedure_body"},
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "last_result": {
            "intent": "tactic_forms",
            "payload": {"name": "rewrite"},
            "result": "Read-only context returned.",
            "proof_state": "unchanged",
            "content": {
                "title": "Tactic Form Reference",
                "preview": "=== `rewrite` tactic -- argument forms ===\nForm 1: rewrite LEMMA.",
            },
        },
    }
    model = surface_model_to_dict(compose_surface_model(view, "l4_checked_action_surface"))
    assert model["phase"] == "context_result"
    panel = model["primary_panel"]
    assert panel["panel_id"] == "context_result"
    assert panel["display_policy"]["lead_before_goal"] is True
    assert panel["display_policy"]["compact_goal"] is True
    keys = {fact["key"] for fact in panel["facts"]}
    assert "request" not in keys
    assert "read_only_note" not in keys
    blob = json.dumps(panel, ensure_ascii=False)
    assert "rewrite LEMMA" in blob

    turn = compose_surface_turn(
        view,
        PROFILE,
        base_view={"current_goal": {"lines": ["Current goal", "x = y"]}},
        handled_intent={"intent": "tactic_forms", "payload": {"name": "rewrite"}},
    )
    md = render_surface_turn_markdown(turn)
    assert md.index("Current Goal") < md.index("Requested: `tactic_forms`")
    assert "Read-only result" in md
    assert "Continue from unchanged proof state" not in md
    assert "rewrite LEMMA" in md
    assert "```text\n=== `rewrite` tactic" in md
    assert "Read-only note" not in md
    assert "committed proof state unchanged" not in md


def test_read_only_context_result_does_not_include_proof_state_decision_context() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"status": "open", "current_layer": "procedure_body"},
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "application_context": {"up_to_bad_call": {
            "active_bad_events": ["UFCMA.bad1", "UFCMA.bad2"],
        }},
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

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    assert model["phase"] == "context_result"
    blob = json.dumps(model["primary_panel"], ensure_ascii=False)
    assert "conseq tactic" in blob
    assert "Up-to-bad call compatibility" not in blob
    assert "up_to_bad_call_compatibility" not in blob


def test_surface_actions_collapse_repeated_choice_variants_once() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {"lines": ["x = y"]},
        "last_result": {
            "intent": "commit_tactic",
            "tactic": "rewrite.",
            "result": "EasyCrypt rejected the committed tactic.",
            "proof_state": "not changed",
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": name}}
            for _ in range(4)
            for name in ("smt", "rewrite", "apply", "case")
        ]},
    }
    model = surface_model_to_dict(compose_surface_model(view, "l4_checked_action_surface"))
    actions = [a for a in model["actions"] if a["intent"] == "tactic_forms"]
    assert len(actions) == 1
    assert actions[0]["payload"] == {"name": "<name>"}
    assert actions[0]["choices"] == {"name": ["rewrite", "apply"]}


def test_common_pure_tactic_form_is_not_a_persistent_reference_action() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {"lines": ["x = y"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
        ]},
    }
    model = surface_model_to_dict(compose_surface_model(view, "l4_checked_action_surface"))
    assert "tactic_forms" not in {
        action["intent"] for action in model.get("actions", [])
    }


def test_recover_surface_never_advertises_unsupported_tactic_form_choices() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {"lines": ["x = y"]},
        "last_result": {
            "intent": "commit_tactic",
            "tactic": "rewrite.",
            "result": "EasyCrypt rejected the committed tactic.",
            "proof_state": "not changed",
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }
    model = surface_model_to_dict(compose_surface_model(view, "l4_checked_action_surface"))
    actions = [a for a in model["actions"] if a["intent"] == "tactic_forms"]
    assert len(actions) == 1
    assert actions[0]["choices"] == {"name": ["rewrite", "apply"]}
    applicable = next(
        fact for fact in model["primary_panel"]["facts"]
        if fact["key"] == "applicable_tactic_families"
    )
    assert "case" not in applicable["value"]
    assert "smt" in applicable["value"]


def test_call_site_options_requires_live_current_frontier() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "procedure_body",
            "goal_type": "phoare",
        },
        "current_goal": {"lines": ["c <- []", "i <- 1", "while (p <> []) {", "z <@ OCC(I).cc(k,n,i)"]},
        "program_frontier": {
            "focus": {"frontier_call_sites": 0},
            "frontier_alignment": {
                "first_instruction_alignment": {
                    "left_head": "assignment",
                    "right_head": None,
                    "branch_alignment": "single_program_frontier",
                }
            },
        },
        "call_site_surface": {
            "called_proc_body": ["future body context only"],
            "items": [{"why": "the call invariant must be preserved"}],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_site_options", "payload": {}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }
    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    assert model["phase"] != "call_site"
    assert "call_site_options" not in {action["intent"] for action in model.get("actions", [])}
    assert "goal_info" not in {action["intent"] for action in model.get("actions", [])}


def test_call_site_options_ignores_buried_call_when_head_is_while() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "call_site",
            "view_focus": "call_site",
            "goal_type": "phoare",
        },
        "current_goal": {
            "lines": [
                "while (p <> []) {",
                "  z <@ OCC(I).cc(k,n,i)",
                "}",
            ]
        },
        "program_frontier": {
            "focus": {"frontier_call_sites": 1},
            "frontier_alignment": {
                "first_instruction_alignment": {
                    "left_head": "while",
                    "right_head": None,
                    "branch_alignment": "single_program_frontier",
                }
            },
        },
        "call_site_surface": {
            "frontier_live_named_handles": [{"symbol": "cc_spec"}],
            "named_call_templates": [{"symbol": "cc_spec", "tactic_shape": "call cc_spec."}],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_site_options", "payload": {}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }
    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    assert "call_site_options" not in {action["intent"] for action in model.get("actions", [])}
    assert "goal_info" not in {action["intent"] for action in model.get("actions", [])}


def test_call_site_options_surfaces_on_live_call_frontier() -> None:
    from workflow.surface_action_preflight import action_preflight_key

    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "call_site",
            "view_focus": "call_site",
            "goal_type": "pRHL",
        },
        "current_goal": {"lines": ["x <@ H.f(a)", "post"]},
        "program_frontier": {
            "focus": {"frontier_call_sites": 1},
            "frontier_alignment": {
                "first_instruction_alignment": {
                    "left_head": "call",
                    "right_head": "call",
                    "branch_alignment": "aligned",
                }
            },
        },
        "call_site_surface": {
            "callable_now": [{"symbol": "Hf", "callable_now": True}],
            "frontier_live_named_handles": [{"symbol": "Hf"}],
        },
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [
                {
                    "intent": "call_site_options",
                    "payload": {},
                    "key": action_preflight_key("call_site_options", {}),
                    "eligible": True,
                    "reason": "preflight found a runnable call-site option",
                },
                {
                    "intent": "call_subgoals",
                    "payload": {"invariant": "={glob H}"},
                    "key": action_preflight_key("call_subgoals", {"invariant": "={glob H}"}),
                    "eligible": True,
                    "reason": "preflight found a concrete call_subgoals obligation preview",
                },
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_site_options", "payload": {}},
            {"intent": "call_subgoals", "payload": {"invariant": "<invariant>"}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }
    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    assert model["phase"] == "call_site"
    actions = {action["intent"]: action for action in model["actions"]}
    assert "call_site_options" in actions
    assert actions["call_site_options"]["state_scope"] == "surface_action_preflight"
    assert "call_subgoals" in actions
    assert actions["call_subgoals"]["choices"]["invariant"] == ["={glob H}"]


def test_call_site_panel_collapses_raw_evidence_into_display_fact() -> None:
    from workflow.surface_action_preflight import action_preflight_key

    handle = {
        "symbol": "equ_cc",
        "source": "source_equiv_declaration",
        "procedures": ["ChaCha(...).enc", "EncRnd.cc"],
        "frontier_live": True,
        "callable_now": True,
        "call_candidate_kind": "direct_current_call",
        "matched_call_sites": [
            {"side": "left", "statement_path": "6", "procedure": "ChaCha.enc"},
            {"side": "right", "statement_path": "4", "procedure": "EncRnd.cc"},
        ],
    }
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "call_site",
            "view_focus": "call_site",
            "goal_type": "pRHL",
        },
        "current_goal": {"lines": ["left call", "right call"]},
        "program_frontier": {"focus": {"frontier_call_sites": 2}},
        "call_site_surface": {
            "named_handles": [handle],
            "frontier_live_named_handles": [handle],
            "callable_now": [handle],
        },
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [{
                "intent": "call_site_options",
                "payload": {},
                "key": action_preflight_key("call_site_options", {}),
                "eligible": True,
                "reason": "preflight found a runnable call-site option",
            }],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_site_options", "payload": {}},
        ]},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    panel = model["primary_panel"]
    facts = {fact["key"]: fact for fact in panel.get("facts", [])}

    assert panel["panel_id"] == "call_site"
    assert facts["direct_current_call"]["role"] == "primary"
    assert facts["direct_current_call"]["value"]["candidates"] == [{
        "symbol": "equ_cc",
        "frontier": ["left:6 `ChaCha.enc`", "right:4 `EncRnd.cc`"],
        "procedures": ["ChaCha(...).enc", "EncRnd.cc"],
        "source": "source_equiv_declaration",
        "call_candidate_kind": "direct_current_call",
    }]
    assert "call_site_raw_evidence" not in facts
    assert "named_handles" not in facts
    assert "frontier_live_named_handles" not in facts
    assert "callable_now" not in facts

    md = render_surface_turn_markdown({
        "presentation_kind": "proof_state",
        "proof_surface": model,
    })
    assert "Direct current call" in md
    assert "equ_cc" in md
    assert "Named handles" not in md
    assert "Frontier-live named handles" not in md
    assert "Callable now" not in md
    assert "Call-site raw evidence" not in md


def test_call_site_options_static_facts_do_not_surface_without_preflight() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "current_layer": "call_site",
            "view_focus": "call_site",
            "goal_type": "pRHL",
        },
        "current_goal": {"lines": ["x <@ H.f(a)", "post"]},
        "program_frontier": {
            "focus": {"frontier_call_sites": 1},
            "frontier_alignment": {
                "first_instruction_alignment": {
                    "left_head": "call",
                    "right_head": "call",
                    "branch_alignment": "aligned",
                }
            },
        },
        "call_site_surface": {
            "callable_now": [{"symbol": "Hf", "callable_now": True}],
            "frontier_live_named_handles": [{"symbol": "Hf"}],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_site_options", "payload": {}},
            {"intent": "call_subgoals", "payload": {"invariant": "<invariant>"}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }
    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    actions = {action["intent"] for action in model.get("actions", [])}
    assert model["phase"] != "call_site"
    assert "call_site_options" not in actions
    assert "call_subgoals" not in actions


def test_call_site_preflight_requires_runnable_result() -> None:
    inert = preflight_result_for_action(
        "call_site_options",
        {},
        {
            "label": "inspect_call_site_options",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Call-Site Context",
                    "items": [{
                        "why": (
                            "the call invariant must be preserved through every "
                            "oracle/state this procedure touches"
                        ),
                    }],
                },
            },
        },
    )
    runnable = preflight_result_for_action(
        "call_site_options",
        {},
        {
            "label": "inspect_call_site_options",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Call-Site Context",
                    "items": [{
                        "candidate": "call H.",
                        "verification": "daemon-verified against the current goal",
                        "submit": {
                            "intent": "commit_tactic",
                            "payload": {"tactic": "call H."},
                        },
                    }],
                },
            },
        },
    )

    assert inert["eligible"] is False
    assert runnable["eligible"] is True


def test_operator_lemmas_is_not_dynamically_preflighted() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "procedure_body", "goal_type": "pRHL"},
        "current_goal": {"lines": ["----", "nth w (l1 ++ l2) i"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "OPERATOR"}},
        ]},
    }

    candidates = surface_preflight_candidates(view)
    assert "operator_lemmas" not in {item["intent"] for item in candidates}


def test_preflight_state_gate_rejects_future_call_context() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "procedure_body", "goal_type": "pRHL"},
        "current_goal": {"lines": ["x <- 0", "later: y <@ M.f()"]},
        "program_frontier": {"current_frontier_scope": {"frontier": {
            "kind": "assignment",
            "left": {"head": "assignment", "statement": "x <- 0"},
        }}},
        "call_site_surface": {
            "live_call_sites": [{
                "procedure": "M.f",
                "is_frontier_call": False,
                "requires_cut_to_frontier": True,
            }],
        },
    }

    assert not preflight_candidate_state_eligibility(
        view, "call_site_options", {}
    ).eligible
    assert not preflight_candidate_state_eligibility(
        view, "call_invariant_skeleton", {}
    ).eligible


def test_preflight_state_gate_allows_current_call_frontier() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "call_site", "goal_type": "pRHL"},
        "current_goal": {"lines": ["x <@ M.f()", "post"]},
        "program_frontier": {"current_frontier_scope": {"frontier": {
            "kind": "call",
            "left": {"head": "call", "statement": "x <@ M.f()"},
        }}},
    }

    assert preflight_candidate_state_eligibility(
        view, "call_site_options", {}
    ).eligible


def test_preflight_state_gate_requires_concrete_context_for_call_subgoals() -> None:
    generic_call = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "call_site", "goal_type": "pRHL"},
        "current_goal": {"lines": ["x <@ M.f()", "post"]},
        "program_frontier": {"current_frontier_scope": {"frontier": {
            "kind": "call",
            "left": {"head": "call", "statement": "x <@ M.f()"},
        }}},
    }
    concrete = {
        **generic_call,
        "call_site_surface": {
            "frontier_live_named_handles": [{"symbol": "equiv_f"}],
        },
    }

    assert not preflight_candidate_state_eligibility(
        generic_call, "call_subgoals", {"invariant": "I"}
    ).eligible
    assert preflight_candidate_state_eligibility(
        concrete, "call_subgoals", {"invariant": "I"}
    ).eligible


def test_operator_lemmas_is_not_a_persistent_surface_action() -> None:
    base = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": ["----", "a ^ b = c ^ d"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "OPERATOR"}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }

    hit_model = surface_model_to_dict(compose_surface_model(base, PROFILE))
    assert "operator_lemmas" not in {
        action["intent"] for action in hit_model.get("actions", [])
    }


def test_operator_lemmas_is_hidden_at_program_frontier() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "procedure_body", "goal_type": "pRHL"},
        "current_goal": {"lines": [
            "&1: {x : int}",
            "&2: {x : int}",
            "----",
            "x <- x + 1   (1)  x <- x + 1",
        ]},
        "program_frontier": {"current_frontier_scope": {"frontier": {
            "kind": "assignment",
            "left": {"head": "assignment", "statement": "x <- x + 1"},
            "right": {"head": "assignment", "statement": "x <- x + 1"},
        }}},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "OPERATOR"}},
        ]},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    assert "operator_lemmas" not in {
        action["intent"] for action in model.get("actions", [])
    }


def test_pure_integer_residual_surfaces_mechanical_split_and_div_mod_choices() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    goal_lines = [
        "p: message",
        "hp: p <> []",
        "hd: block_size <> 0",
        "------------------------------------------------------------",
        "size p %/ block_size + b2i (size p %% block_size <> 0) =",
        "size (drop block_size p) %/ block_size +",
        "b2i (size (drop block_size p) %% block_size <> 0) + 1",
    ]
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": goal_lines},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "OPERATOR"}},
            {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
        ]},
    }
    view["pure_tail_surface"] = pure_tail_surface(view)

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {
        fact["key"]: fact.get("value")
        for fact in model["primary_panel"].get("facts", [])
    }
    assert "integer_arithmetic_surface" not in facts
    assert "integer_arithmetic_shapes" not in facts
    assert facts["integer_arithmetic_split_candidates"][0].startswith(
        "block_size <= size p from size (drop block_size p)"
    )
    assert "size p %% block_size <> 0" in facts["integer_arithmetic_b2i_guards"]
    assert any(
        "divzMDl" in family and "divz_small" in family
        for family in facts["integer_arithmetic_lemma_families"]
    )

    assert not model.get("actions")


def test_pure_panel_does_not_repeat_memory_decorations_from_goal() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    goal_lines = [
        "&m: {i : int, p : message}",
        "------------------------------------------------------------",
        "p{m} <> [] => size (drop block_size p{m}) < size p{m}",
    ]
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": goal_lines},
        "inspect_lookup_handles": {"ask_manager_for": []},
    }
    view["pure_tail_surface"] = pure_tail_surface(view)

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {
        fact["key"]: fact.get("value")
        for fact in model["primary_panel"].get("facts", [])
    }

    assert "memory_decorated_terms" not in facts
    assert "ambient_memory_translation" not in facts


def test_pure_panel_renders_typed_distribution_facts_without_tactic_recipe() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "remaining_goals": 2,
            "current_layer": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {
            "lines": [
                "Current goal",
                "----",
                "mu1 [0..bound - 1] k = inv bound%r",
            ],
        },
        "pure_tail_surface": {
            "state": "ambient_pure_tail",
            "distribution_certificates": [{
                "lemma": "dinter1E",
                "certificate_kind": "finite_interval_point_mass",
                "distribution": "[0..bound - 1]",
                "point": "k",
                "instantiated_identity": (
                    "mu1 (dinter 0 (bound - 1)) k = "
                    "if 0 <= k <= bound - 1 then 1%r / bound%r else 0%r"
                ),
                "interval_cardinality": "bound",
                "loaded_supporting_facts": [{
                    "lemma": "bound_pos",
                    "fact": "0 < bound",
                }],
            }],
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {
        fact["key"]: fact
        for fact in model["primary_panel"].get("facts", [])
    }
    certificate = facts["distribution_certificates"]

    assert certificate["actionability"] == "high"
    assert certificate["value"]["matches"][0]["lemma"] == "dinter1E"
    assert certificate["value"]["loaded_cardinality_facts"][0]["lemma"] == "bound_pos"
    assert "rewrite dinter1E" not in json.dumps(certificate)

    turn = compose_surface_turn(
        view,
        PROFILE,
        handled_intent={"intent": "commit_tactic", "payload": {"tactic": "rnd."}},
        ok=True,
    )
    markdown = render_surface_turn_markdown(turn)
    assert "dinter1E" in markdown
    assert "bound_pos: 0 < bound" in markdown


def test_fact_eligibility_rejects_unregistered_panel_fact_keys() -> None:
    from workflow.surface_fact_eligibility import (
        fact_eligibility,
        validate_surface_fact_contract,
    )
    from workflow.surface_model import PanelFact

    unknown = fact_eligibility(
        {},
        "pure_logic",
        PanelFact("future_guess", "Future guess", "some text"),
    )
    known = fact_eligibility(
        {},
        "pure_logic",
        PanelFact("local_hypothesis_graph", "Local order chains", ["H1", "H2"]),
    )

    assert unknown.eligible is False
    assert "presentation contract" in unknown.reason
    assert known.eligible is True
    with pytest.raises(ValueError, match="future_guess"):
        validate_surface_fact_contract(
            "pure_logic",
            [PanelFact("future_guess", "Future guess", "some text")],
        )


def test_filtered_empty_primary_panel_is_not_rendered() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "remaining_goals_known": True,
            "current_layer": "relational_program",
            "goal_type": "pRHL",
        },
        "current_goal": {
            "goal_type": "pRHL",
            "lines": ["Current goal", "pre = true", "post = true"],
        },
        "program_frontier": {"current_frontier_scope": {}},
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))

    assert model.get("primary_panel") is None


def test_relational_program_surfaces_only_typed_exact_named_routes() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "remaining_goals_known": True,
            "current_layer": "relational_program",
            "goal_type": "equiv",
        },
        "current_goal": {
            "goal_type": "equiv",
            "lines": ["Current goal", "pre = true", "Proc1.f ~ Proc2.f", "post = true"],
        },
        "application_context": {
            "loaded_named_routes": [{
                "route_kind": "exact",
                "symbol": "CBC_Oracle_enc_eq",
                "matched_form": "exact/(CBC_Oracle_enc_eq P P' I Hf).",
                "verification_status": "ProofIR name and current-goal shape match",
            }],
        },
        "program_frontier": {"current_frontier_scope": {}},
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))

    panel = model["primary_panel"]
    assert panel["panel_id"] == "relational_program"
    fact = panel["facts"][0]
    assert fact["key"] == "loaded_named_routes"
    assert fact["value"][0]["symbol"] == "CBC_Oracle_enc_eq"
    assert "proc." not in json.dumps(panel)


def test_relational_program_does_not_surface_generic_candidate_move_as_route() -> None:
    view = {
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "relational_program",
            "goal_type": "equiv",
        },
        "current_goal": {
            "goal_type": "equiv",
            "lines": ["Current goal", "Proc1.f ~ Proc2.f"],
        },
        "candidate_moves": {"moves": [{
            "category": "strategy",
            "tactic_shape": "apply GuessedLemma.",
            "source": "proof-state analysis",
        }]},
        "program_frontier": {"current_frontier_scope": {}},
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))

    assert model.get("primary_panel") is None


def test_opener_surfaces_loaded_probability_rewrite_matches_not_generic_forms() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "probability"},
        "current_goal": {
            "goal_type": "probability",
            "lines": ["Pr[Sample.simple(s) @ &1 : res = a] = Pr[Sample.double(t, s) @ &2 : res = a]"],
        },
        "application_context": {
            "mechanical_goal_candidates": [
                {
                    "lemma": "pr_sample_simple",
                    "match_kind": "loaded_rewrite_head",
                    "shared_symbols": ["Pr", "simple"],
                },
                {
                    "lemma": "pr_sample_double",
                    "match_kind": "loaded_rewrite_head",
                    "shared_symbols": ["Pr", "double"],
                    "required_premises": ["forall x, x \\in t => x \\in s"],
                },
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {item["key"]: item for item in model["primary_panel"]["facts"]}

    assert "mechanical_goal_candidates" in facts
    assert "tactic_affordances" not in facts
    assert {name for group in facts["mechanical_goal_candidates"]["value"] for name in group["lemmas"]} == {
        "pr_sample_simple",
        "pr_sample_double",
    }


def test_opener_prefers_exact_loaded_pr_endpoint_fact_over_generic_tactic_table() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "probability"},
        "current_goal": {
            "goal_type": "probability",
            "lines": ["Pr[Game0.main() @ &m : res] <= eps"],
        },
        "application_context": {
            "pr_endpoint_matches": [{
                "lemma": "Bridge",
                "lhs_game": "Game0.main()",
                "rhs_game": "Game1.main()",
                "required_premises": ["initialisation q"],
                "exact_endpoint_matches": [{
                    "lemma_side": "lhs",
                    "rewrite_direction": "lhs_to_rhs",
                    "other_endpoint": "Game1.main()",
                }],
                "authority": "source_scan_fallback",
            }],
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {
        fact["key"]: fact
        for fact in model["primary_panel"]["facts"]
    }

    assert "pr_endpoint_matches" in facts
    assert "tactic_affordances" not in facts
    assert all(
        action["intent"] != "tactic_forms"
        for action in model.get("actions", [])
    )
    detail = facts["pr_endpoint_matches"]["details"][0]
    assert detail["lemma"] == "Bridge"
    assert detail["required_premises"] == ["initialisation q"]
    assert detail["rewrite_direction"] == "lhs_to_rhs"


def test_pure_panel_surfaces_only_decision_relevant_mechanical_shape_facts() -> None:
    from workflow.proof_management.analyzers.pure_tail import pure_tail_surface

    goal_lines = [
        "&m: {i : int, c : byte list, p : message}",
        "------------------------------------------------------------",
        "r = iter (size p{m} %/ block_size + b2i (size p{m} %% block_size <> 0)) f x =>",
        "p{m} <> [] =>",
        "r = iter (size (drop block_size p{m}) %/ block_size +",
        "          b2i (size (drop block_size p{m}) %% block_size <> 0) + 1) f y /\\",
        "size (drop block_size p{m}) < size p{m}",
    ]
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": goal_lines},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "OPERATOR"}},
            {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
        ]},
    }
    view["pure_tail_surface"] = pure_tail_surface(view)

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    panel_facts = model["primary_panel"].get("facts", [])
    facts = {fact["key"]: fact.get("value") for fact in panel_facts}

    assert "goal_operators" not in facts
    assert [fact["key"] for fact in panel_facts[:4]] == [
        "iter_successor_shape",
        "integer_arithmetic_split_candidates",
        "integer_arithmetic_b2i_guards",
        "integer_arithmetic_lemma_families",
    ]
    assert "implication_premises" not in facts
    assert "conclusion_obligations" not in facts
    assert "memory_decorated_terms" not in facts
    assert "integer_arithmetic_shapes" not in facts
    assert "count has top-level + 1" in facts["iter_successor_shape"][0]
    assert facts["integer_arithmetic_split_candidates"] == [
        "block_size <= size p{m} from size (drop block_size p{m})"
    ]
    assert "needs:" not in " ".join(facts["integer_arithmetic_lemma_families"])


def test_pure_panel_groups_structural_lemma_families_without_losing_names() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "ambient"},
        "current_goal": {"goal_type": "ambient", "lines": ["m.[k <- v].[k] = Some v"]},
        "pure_tail_surface": {
            "mechanical_goal_candidates": [
                {
                    "lemma": "get_setE",
                    "match_kind": "loaded_structural_fingerprint",
                    "shared_structures": ["map update followed by lookup"],
                },
                {
                    "lemma": "get_set_sameE",
                    "match_kind": "loaded_structural_fingerprint",
                    "shared_structures": ["map update followed by lookup"],
                },
                {
                    "lemma": "PolyCancel",
                    "match_kind": "loaded_structural_fingerprint",
                    "shared_structures": ["add/sub cancellation equality"],
                    "shared_types": ["poly_out"],
                },
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    fact = next(
        item for item in model["primary_panel"]["facts"]
        if item["key"] == "mechanical_goal_candidates"
    )

    assert len(fact["value"]) == 2
    assert fact["value"][0]["lemmas"] == ["get_setE", "get_set_sameE"]
    assert fact["value"][1]["lemmas"] == ["PolyCancel"]
    assert all("declaration" not in item for item in fact["value"])
    md = render_surface_turn_markdown(compose_surface_turn(view, PROFILE))
    assert "get_setE" in md
    assert "get_set_sameE" in md
    assert "PolyCancel" in md


def test_loaded_mechanical_matches_suppress_redundant_broad_reference_actions() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "ambient"},
        "current_goal": {"goal_type": "ambient", "lines": ["m.[k <- v].[k] = Some v"]},
        "pure_tail_surface": {
            "mechanical_goal_candidates": [{
                "lemma": "get_set_sameE",
                "match_kind": "loaded_structural_fingerprint",
                "shared_structures": ["map update followed by lookup"],
            }],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {
                "intent": "operator_lemmas",
                "payload": {"operator": "(_.[_ <- _].[_])"},
                "requires_input": ["operator"],
                "choices": {"operator": ["(_.[_ <- _].[_])"]},
            },
            {
                "intent": "tactic_forms",
                "payload": {"name": "rewrite"},
                "requires_input": ["name"],
                "choices": {"name": ["rewrite"]},
            },
        ]},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))

    assert model.get("actions", []) == []


def test_pure_panel_renders_composed_list_and_map_transport_facts() -> None:
    view = {
        "proof_status": {"status": "open", "goal_type": "ambient"},
        "current_goal": {"goal_type": "ambient", "lines": ["pure goal"]},
        "pure_tail_surface": {
            "list_normalization_surface": {
                "prefix_successor_chains": [{
                    "shape": "mapped take-prefix successor",
                    "mapper": "encode",
                    "index": "k",
                    "source_list": "xs",
                    "side_condition": "0 <= k < size xs",
                    "side_condition_status": "visible",
                    "lemma_chain": [
                        {"lemma": "take_nth"},
                        {"lemma": "map_rcons"},
                        {"lemma": "cats1"},
                    ],
                }],
            },
            "map_update_transport_surface": {
                "shape": "pointwise finite-map key transport",
                "pointwise_relation": "forall x, left.[x] = right.[encode x]",
                "key_transform": "encode",
                "update_key_pair": {"source": "next", "transformed": "encode next"},
                "lookup_normalization_lemma": "get_setE",
                "left_inverse_lemma": "decode_encode",
                "effect": "get/set normalization plus loaded inverse evidence",
            },
            "mechanical_goal_candidates": [{
                "lemma": "decode_encode",
                "match_kind": "loaded_left_inverse_support",
                "transform": "encode",
                "inverse": "decode",
            }],
        },
        "inspect_lookup_handles": {"ask_manager_for": []},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {item["key"]: item for item in model["primary_panel"]["facts"]}

    assert facts["list_normalization_routes"]["value"][0]["loaded_chain"] == [
        "take_nth", "map_rcons", "cats1",
    ]
    assert facts["map_update_transport"]["value"]["loaded_support"] == [
        "get_setE", "decode_encode",
    ]
    assert "mechanical_goal_candidates" not in facts


def test_dynamic_route_actions_require_displayable_preflight() -> None:
    context_only = preflight_result_for_action(
        "pr_bridge_routes",
        {},
        {
            "label": "inspect_pr_bridge_routes",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Verified Pr Bridge Routes",
                    "items": [{"why": "bridge candidates require a matching Pr shape"}],
                },
            },
        },
    )
    verified = preflight_result_for_action(
        "pr_bridge_routes",
        {},
        {
            "label": "inspect_pr_bridge_routes",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Verified Pr Bridge Routes",
                    "items": [{
                        "candidate": "byequiv (_: ={glob G} ==> ={res}).",
                        "verification": "daemon-verified against the current goal",
                        "submit": {
                            "intent": "commit_tactic",
                            "payload": {
                                "tactic": "byequiv (_: ={glob G} ==> ={res})."
                            },
                        },
                    }],
                },
            },
        },
    )
    assert context_only["eligible"] is False
    assert verified["eligible"] is True
    assert verified["result_kind"] == "ready_to_submit_candidates"
    assert verified["candidate_count"] == 1
    assert verified["ready_submission_count"] == 1

    base = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "pr", "goal_type": "probability"},
        "current_goal": {"lines": ["Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "pr_bridge_routes", "payload": {}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }

    without_preflight = surface_model_to_dict(compose_surface_model(base, PROFILE))
    assert "pr_bridge_routes" not in {
        action["intent"] for action in without_preflight.get("actions", [])
    }

    inert = {
        **base,
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [{
                "intent": "pr_bridge_routes",
                "payload": {},
                "key": action_preflight_key("pr_bridge_routes", {}),
                "eligible": False,
                "reason": "preflight returned context but no runnable/verified pr_bridge_routes option",
            }],
        },
    }
    inert_model = surface_model_to_dict(compose_surface_model(inert, PROFILE))
    assert "pr_bridge_routes" not in {
        action["intent"] for action in inert_model.get("actions", [])
    }

    actionable = {
        **base,
        "surface_action_preflight": {
            "schema_version": 2,
            "results": [verified],
        },
    }
    actionable_model = surface_model_to_dict(compose_surface_model(actionable, PROFILE))
    actions = actionable_model.get("actions", [])
    assert "pr_bridge_routes" not in {action["intent"] for action in actions}
    assert [action for action in actions if action["intent"] == "commit_tactic"] == [{
        "intent": "commit_tactic",
        "payload": {"tactic": "byequiv (_: ={glob G} ==> ={res})."},
        "label": "Commit verified Pr bridge route 1",
        "intent_class": "proof_mutation",
        "read_only": False,
        "description": "byequiv (_: ={glob G} ==> ={res}).",
        "source_refs": ["surface_action_preflight.results"],
        "eligibility_reason": (
            "exact manager-preflighted submission from pr_bridge_routes"
        ),
        "state_scope": "surface_action_preflight",
    }]
    facts = {
        fact["key"]: fact
        for fact in actionable_model["primary_panel"]["facts"]
    }
    assert facts["verified_pr_bridge_routes"]["summary"].startswith(
        "Manager read-only preflight found 1 current-state route"
    )
    assert facts["verified_pr_bridge_routes"]["audit_payload"][0]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "byequiv (_: ={glob G} ==> ={res})."},
    }

    md = render_surface_turn_markdown({
        "presentation_kind": "proof_state",
        "proof_surface": actionable_model,
    })
    assert "### Ready proof action" in md
    assert md.count("byequiv (_: ={glob G} ==> ={res}).") == 1


def test_preflight_retains_multiple_typed_routes_and_rejects_invented_submit() -> None:
    summary = {
        "label": "inspect_pr_bridge_routes",
        "exit_code": 0,
        "agent_observation": {
            "content": {
                "title": "Verified Pr Bridge Routes",
                "items": [
                    {
                        "candidate": "rewrite H1.",
                        "why": "first verified route",
                        "verification": "daemon-verified against the current goal",
                        "submit": {
                            "intent": "commit_tactic",
                            "payload": {"tactic": "rewrite H1."},
                        },
                    },
                    {
                        "candidate": "rewrite H2.",
                        "why": "second verified route",
                        "verification": "daemon-verified against the current goal",
                        "submit": {
                            "intent": "commit_tactic",
                            "payload": {"tactic": "rewrite H2."},
                        },
                    },
                    {
                        "candidate": "rewrite H2.",
                        "verification": "daemon-verified against the current goal",
                        "submit": {
                            "intent": "commit_tactic",
                            "payload": {"tactic": "rewrite H2."},
                        },
                    },
                ],
            },
        },
    }
    result = preflight_result_for_action("pr_bridge_routes", {}, summary)
    assert result["candidate_count"] == 2
    assert [item["candidate"] for item in result["candidates"]] == [
        "rewrite H1.", "rewrite H2.",
    ]

    view = {
        "proof_status": {"goal_type": "probability"},
        "current_goal": {"lines": ["Pr[G.main() @ &m : res] <= 1%r"]},
        "surface_action_preflight": {
            "schema_version": 2,
            "results": [result],
        },
    }
    assert matching_preflight_submission(
        view, "commit_tactic", {"tactic": "rewrite H2."}
    )["source_intent"] == "pr_bridge_routes"
    assert not matching_preflight_submission(
        view, "commit_tactic", {"tactic": "rewrite INVENTED."}
    )
    invented = PanelAction(
        intent="commit_tactic",
        payload={"tactic": "rewrite INVENTED."},
        intent_class="proof_mutation",
        read_only=False,
    )
    assert action_eligibility(view, "opener", "opener", invented).eligible is False


def test_remaining_context_preflights_require_displayable_content() -> None:
    bridge_empty = preflight_result_for_action(
        "equiv_bridge_lemmas",
        {},
        {
            "label": "inspect_equiv_bridge_lemmas",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Equiv Bridge Lemma Context",
                    "notes": [{"code": "bridge_lemmas.no_candidate"}],
                },
            },
        },
    )
    bridge_hit = preflight_result_for_action(
        "equiv_bridge_lemmas",
        {},
        {
            "label": "inspect_equiv_bridge_lemmas",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Equiv Bridge Lemma Context",
                    "items": [{"candidate": "exact equ_cc.", "why": "bridge chain"}],
                },
            },
        },
    )
    lemma_empty = preflight_result_for_action(
        "lemma_hints",
        {},
        {
            "label": "inspect_lemma_hints",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Lemma Hint Context",
                    "notes": [{"code": "lemma_hints.no_match"}],
                },
            },
        },
    )
    lemma_hit = preflight_result_for_action(
        "lemma_hints",
        {},
        {
            "label": "inspect_lemma_hints",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Lemma Hint Context",
                    "items": [{
                        "candidate": '{"intent":"lookup_symbol","payload":{"symbol":"size_ge0"}}',
                        "why": "matched current goal operator",
                    }],
                },
            },
        },
    )
    gap_empty = preflight_result_for_action(
        "subgoal_gap",
        {},
        {
            "label": "inspect_subgoal_gap",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Subgoal Gap",
                    "notes": [{"code": "subgoal_gap.no_missing_marker"}],
                },
            },
        },
    )
    gap_hit = preflight_result_for_action(
        "subgoal_gap",
        {},
        {
            "label": "inspect_subgoal_gap",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Subgoal Gap",
                    "items": [{
                        "candidate": "Strengthen the invariant/precondition.",
                        "why": "subgoal-gap found 2 missing conjunct marker(s).",
                    }],
                },
            },
        },
    )

    assert bridge_empty["eligible"] is False
    assert bridge_hit["eligible"] is True
    assert lemma_empty["eligible"] is False
    assert lemma_hit["eligible"] is True
    assert gap_empty["eligible"] is False
    assert gap_hit["eligible"] is True


def test_remaining_dynamic_actions_surface_only_after_preflight() -> None:
    base = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "procedure_body", "goal_type": "pRHL"},
        "current_goal": {"lines": ["x <- 0", "post"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "equiv_bridge_lemmas", "payload": {}},
            {"intent": "lemma_hints", "payload": {}},
            {"intent": "subgoal_gap", "payload": {}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }
    candidates = surface_preflight_candidates(base)
    assert {item["intent"] for item in candidates} == {
        "equiv_bridge_lemmas",
        "lemma_hints",
        "subgoal_gap",
    }

    without_preflight = surface_model_to_dict(compose_surface_model(base, PROFILE))
    assert {
        "equiv_bridge_lemmas",
        "lemma_hints",
        "subgoal_gap",
    }.isdisjoint({action["intent"] for action in without_preflight.get("actions", [])})

    with_hits = {
        **base,
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [
                {
                    "intent": intent,
                    "payload": {},
                    "key": action_preflight_key(intent, {}),
                    "eligible": True,
                    "reason": f"preflight found concrete {intent} context",
                }
                for intent in (
                    "equiv_bridge_lemmas",
                    "lemma_hints",
                    "subgoal_gap",
                )
            ],
        },
    }
    hit_model = surface_model_to_dict(compose_surface_model(with_hits, PROFILE))
    intents = {action["intent"] for action in hit_model.get("actions", [])}
    assert {"equiv_bridge_lemmas", "lemma_hints", "subgoal_gap"} <= intents


def test_choice_preflight_expands_inv_and_call_subgoal_inputs() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "call_site", "goal_type": "pRHL"},
        "current_goal": {
            "lines": ["Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]"]
        },
        "call_site_surface": {
            "frontier_live_named_handles": [
                {"symbol": "equ_cc", "kind": "equiv_lemma", "tactic_shape": "call equ_cc."}
            ],
            "named_call_templates": [
                {"tactic_shape": "call (_: ={glob M} /\\ k{1} = k{2})."}
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "inv_from_lemma", "payload": {"lemma": "LEMMA"}},
            {"intent": "call_subgoals", "payload": {"invariant": "<invariant>"}},
        ]},
    }

    candidates = surface_preflight_candidates(view)
    by_intent = {}
    for item in candidates:
        by_intent.setdefault(item["intent"], []).append(item["payload"])
    assert {"lemma": "equ_cc"} in by_intent["inv_from_lemma"]
    assert {
        "invariant": "={glob M} /\\ k{1} = k{2}"
    } in by_intent["call_subgoals"]


def test_call_subgoal_choices_ignore_explanatory_prose() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "call_site", "goal_type": "pRHL"},
        "current_goal": {"lines": ["x <@ H.f(a)", "post"]},
        "call_site_surface": {
            "items": [
                {
                    "why": "read-only here (clone-owned / preserved -> safe `={C.ofintd}`)",
                },
                {
                    "candidate": "Mechanical write-map: DON'T re-derive it in your head",
                    "note": "contains no call invariant",
                },
                {
                    "tactic_shape": "call (_: ={glob M} /\\ k{1} = k{2}).",
                },
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_subgoals", "payload": {"invariant": "<invariant>"}},
        ]},
    }

    candidates = surface_preflight_candidates(view)
    payloads = [
        item["payload"]["invariant"]
        for item in candidates
        if item["intent"] == "call_subgoals"
    ]
    assert payloads == ["={glob M} /\\ k{1} = k{2}"]


def test_inv_and_call_subgoal_preflight_classifiers() -> None:
    inv_empty = preflight_result_for_action(
        "inv_from_lemma",
        {"lemma": "bad"},
        {
            "label": "inspect_inv_from_lemma",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Invariant from Lemma",
                    "notes": [{"code": "inv_from_lemma.no_template"}],
                },
            },
        },
    )
    inv_hit = preflight_result_for_action(
        "inv_from_lemma",
        {"lemma": "equ_cc"},
        {
            "label": "inspect_inv_from_lemma",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Invariant from Lemma",
                    "items": [{
                        "candidate": "call (_: ={glob M} /\\ k{1} = k{2}).",
                        "why": "extracted from lemma precondition",
                    }],
                },
            },
        },
    )
    call_rejected = preflight_result_for_action(
        "call_subgoals",
        {"invariant": "={glob M}"},
        {
            "label": "inspect_call_subgoals",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Call Obligation Preview",
                    "preview": "`call (_: ...).` was rejected by daemon.",
                },
            },
        },
    )
    call_hit = preflight_result_for_action(
        "call_subgoals",
        {"invariant": "={glob M}"},
        {
            "label": "inspect_call_subgoals",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Call Obligation Preview",
                    "preview": (
                        "Speculative `call (_: ...).` accepted by daemon. "
                        "2 subgoal(s) will be queued post-commit.\n"
                        "Active subgoal preview (first 20 lines):"
                    ),
                },
            },
        },
    )

    assert inv_empty["eligible"] is False
    assert inv_hit["eligible"] is True
    assert call_rejected["eligible"] is False
    assert call_hit["eligible"] is True


def test_call_subgoals_can_derive_from_invariant_preflight_result() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "call_site", "goal_type": "pRHL"},
        "current_goal": {"lines": ["x <@ H.f(a)", "post"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "call_invariant_skeleton", "payload": {}},
            {"intent": "call_subgoals", "payload": {"invariant": "<invariant>"}},
        ]},
    }
    skeleton_summary = {
        "label": "inspect_call_invariant_skeleton",
        "exit_code": 0,
        "agent_observation": {
            "content": {
                "title": "Call-Invariant Glob Skeleton",
                "items": [{
                    "candidate": "call (_: ={glob M} /\\ k{1} = k{2}).",
                }],
            },
        },
    }
    skeleton_preflight = preflight_result_for_action(
        "call_invariant_skeleton",
        {},
        skeleton_summary,
    )

    derived = derived_preflight_candidates(view, [{
        "intent": "call_invariant_skeleton",
        "payload": {},
        "summary": skeleton_summary,
        "preflight_result": skeleton_preflight,
    }])

    assert derived == [{
        "intent": "call_subgoals",
        "payload": {"invariant": "={glob M} /\\ k{1} = k{2}"},
    }]


def test_call_invariant_skeleton_preflight_rejects_menu_placeholders() -> None:
    summary = {
        "label": "inspect_call_invariant_skeleton",
        "exit_code": 0,
        "agent_observation": {
            "content": {
                "title": "Call-Invariant Glob Skeleton",
                "items": [{
                    "candidate": "call (_: inv_cpa ‹ROin.m | ROout.m›{1} Mem.log{1} Mem.log{2}).",
                    "why": "type-matched menu; not literal EasyCrypt syntax",
                }],
            },
        },
    }

    result = preflight_result_for_action(
        "call_invariant_skeleton",
        {},
        summary,
    )

    assert result["eligible"] is False
    assert "incomplete" in result["reason"]


def test_inv_and_call_subgoals_surface_only_after_preflight() -> None:
    call_base = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "call_site", "goal_type": "pRHL"},
        "current_goal": {"lines": ["x <@ H.f(a)", "post"]},
        "call_site_surface": {
            "frontier_live_named_handles": [
                {"symbol": "equ_cc", "kind": "equiv_lemma", "tactic_shape": "call equ_cc."}
            ],
            "named_call_templates": [
                {"tactic_shape": "call (_: ={glob M})."}
            ],
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "inv_from_lemma", "payload": {"lemma": "LEMMA"}},
            {"intent": "call_subgoals", "payload": {"invariant": "<invariant>"}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }

    without_preflight = surface_model_to_dict(compose_surface_model(call_base, PROFILE))
    assert {"inv_from_lemma", "call_subgoals"}.isdisjoint({
        action["intent"] for action in without_preflight.get("actions", [])
    })

    call_hits = {
        **call_base,
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [
                {
                    "intent": "inv_from_lemma",
                    "payload": {"lemma": "equ_cc"},
                    "key": action_preflight_key("inv_from_lemma", {"lemma": "equ_cc"}),
                    "eligible": True,
                    "reason": "preflight found concrete inv_from_lemma context",
                },
                {
                    "intent": "call_subgoals",
                    "payload": {"invariant": "={glob M}"},
                    "key": action_preflight_key("call_subgoals", {"invariant": "={glob M}"}),
                    "eligible": True,
                    "reason": "preflight found a concrete call_subgoals obligation preview",
                },
            ],
        },
    }
    call_model = surface_model_to_dict(compose_surface_model(call_hits, PROFILE))
    call_intents = {action["intent"] for action in call_model.get("actions", [])}
    assert {"inv_from_lemma", "call_subgoals"} <= call_intents

def test_surface_actions_carry_state_eligibility_metadata() -> None:
    model = surface_model_to_dict(
        compose_surface_model(_assignment_recover_view(), "l4_checked_action_surface")
    )
    for action in model["actions"]:
        assert action["eligibility_reason"]
        assert action["state_scope"]


def test_trivial_pure_goal_has_no_lookup_or_tactic_reference_menu() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {"lines": ["Current goal", "-----", "true"]},
        "pure_tail_surface": {"goal_operators": ["true"]},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "operator_lemmas", "payload": {"operator": "true"}},
            {"intent": "tactic_forms", "payload": {"name": "rewrite"}},
        ]},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    assert {action["intent"] for action in model.get("actions", [])}.isdisjoint({
        "operator_lemmas", "tactic_forms",
    })


def test_opener_surfaces_loaded_pr_bound_route_set_without_generic_tactic_table() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "opener",
            "goal_type": "probability",
        },
        "current_goal": {"lines": [
            "Pr[G0.main() @ &m : res] <=",
            "Pr[G1.main() @ &m : res] + Pr[G2.main() @ &m : bad]",
        ]},
        "application_context": {
            "pr_bound_routes": [
                {
                    "lemma": "reduction",
                    "route_role": "outer_bound_decomposition",
                    "exact_goal_endpoints": ["G0.main", "G1.main", "G2.main"],
                    "required_premises": ["0 <= eps"],
                    "authority": "source_scan_fallback",
                },
                {
                    "lemma": "Bound_G2",
                    "route_role": "exact_visible_term_bound",
                    "exact_goal_endpoints": ["G2.main"],
                    "authority": "source_scan_fallback",
                },
            ],
        },
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {
        item["key"]: item.get("value")
        for item in model["primary_panel"]["facts"]
    }

    assert "pr_bound_routes" in facts
    assert "tactic_affordances" not in facts
    assert {item["lemma"] for item in facts["pr_bound_routes"]} == {
        "reduction", "Bound_G2",
    }


def test_pure_panel_surfaces_compact_list_normalization_routes() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "ambient_logic",
            "goal_type": "ambient",
        },
        "current_goal": {"lines": [
            "hlo: size prefix <= i",
            "hhi: i < size prefix + size xs",
            "----",
            "nth witness (map f xs) (i - size prefix) = rhs",
        ]},
        "pure_tail_surface": {
            "list_normalization_surface": {
                "lemma_families": [{
                    "shape": "nth over map",
                    "lemma_names": ["nth_map"],
                    "side_condition": "0 <= index < size source_list",
                }],
                "nth_map_terms": [{
                    "source_list": "xs",
                    "index": "i - size prefix",
                    "side_condition": "0 <= i - size prefix < size xs",
                    "side_condition_status": "derivable_from_visible_linear_bounds",
                    "supporting_hypotheses": ["hlo", "hhi"],
                }],
            },
        },
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {
        item["key"]: item.get("value")
        for item in model["primary_panel"]["facts"]
    }

    routes = facts["list_normalization_routes"]
    assert routes[0]["loaded_family"] == ["nth_map"]
    assert routes[1]["side_condition_status"] == (
        "derivable_from_visible_linear_bounds"
    )
    assert routes[1]["supporting_hypotheses"] == ["hlo", "hhi"]


def test_single_program_surfaces_live_losslessness_certificate_without_recipe() -> None:
    view = {
        "kind": "prover_workspace_view",
        "proof_status": {
            "status": "open",
            "remaining_goals": 1,
            "current_layer": "procedure_body",
            "goal_type": "phoare",
        },
        "current_goal": {"lines": [
            "Current goal",
            "Ofll: islossless O.f",
            "----",
            "(1) D2(O).O.init()",
            "(2) b <@ Adv_MAC_to_F(A, D2(O).O).guess()",
        ]},
        "program_frontier": {"current_frontier_scope": {
            "setup": {"left": {"paths": ["1"], "summary": "D2(O).O.init()"}},
            "frontier": {
                "kind": "left_call",
                "left": {
                    "side": "left",
                    "path": "2",
                    "head": "call",
                    "statement": "b <@ Adv_MAC_to_F(A, D2(O).O).guess()",
                },
            },
        }},
        "call_site_surface": {"one_sided_call_surface": {
            "state": "one_sided_call_frontier",
            "visible_lossless_handles": [{
                "symbol": "Alossless_F",
                "certificate_kind": "losslessness",
                "procedure": "Adv_MAC_to_F(A,D2(O).O).guess",
                "declared_procedure": "Adv_MAC_to_F(A,O).guess",
                "parameter_bindings": {"O": "D2(O).O"},
                "required_premises": ["islossless D2(O).O.f"],
                "match_kind": "module_parameter_instantiation",
                "verification_status": "loaded declaration shape match",
            }],
        }},
        "inspect_lookup_handles": {"ask_manager_for": [{
            "intent": "tactic_forms",
            "payload": {"name": "inline"},
        }]},
    }

    model = surface_model_to_dict(compose_surface_model(view, PROFILE))
    facts = {
        item["key"]: item
        for item in model["primary_panel"]["facts"]
    }
    certificate = facts["one_sided_losslessness_certificates"]

    assert certificate["actionability"] == "high"
    assert certificate["value"]["candidates"][0]["lemma"] == "Alossless_F"
    assert certificate["value"]["candidates"][0]["module_bindings"] == {
        "O": "D2(O).O"
    }
    assert "call (" not in json.dumps(certificate)
    tactic_action = next(
        action for action in model["actions"] if action["intent"] == "tactic_forms"
    )
    assert set(tactic_action["choices"]["name"]) == {"call", "inline"}
