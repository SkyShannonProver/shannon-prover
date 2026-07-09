from __future__ import annotations

import json
from pathlib import Path

from workflow.surface_composer import compose_surface_model
from workflow.surface_action_preflight import (
    action_preflight_key,
    derived_preflight_candidates,
    preflight_result_for_action,
    surface_preflight_candidates,
)
from workflow.surface_model import surface_model_to_dict
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

    assert "from workflow.surface_tactic_forms import tactic_form_names_for_state" in composer
    assert "from workflow.surface_tactic_forms import" in eligibility
    assert "def eligible_tactic_form_names" in owner
    assert "def tactic_form_names_for_state" in owner
    assert "def tactic_form_names_for_state" not in eligibility
    assert "_PROGRAM_TACTIC_FORMS" not in eligibility


def test_panel_action_policy_has_one_contract_owner() -> None:
    eligibility = (ROOT / "workflow" / "surface_action_eligibility.py").read_text(encoding="utf-8")
    owner = (ROOT / "workflow" / "surface_action_policy.py").read_text(encoding="utf-8")

    assert "def panel_allowed_intents" in owner
    assert "PANEL_INTENTS" in owner
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
        "decision_context": {"up_to_bad_call": {
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


def test_tactic_form_single_choice_still_renders_as_choice_action() -> None:
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
    actions = [a for a in model["actions"] if a["intent"] == "tactic_forms"]
    assert len(actions) == 1
    assert actions[0]["payload"] == {"name": "<name>"}
    assert actions[0]["choices"] == {"name": ["rewrite"]}


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
    assert facts["call_site_raw_evidence"]["role"] == "audit_only"
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


def test_operator_lemmas_surface_uses_goal_derived_choices_without_preflight() -> None:
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
    ops = [
        op
        for action in hit_model["actions"]
        if action["intent"] == "operator_lemmas"
        for op in action["choices"]["operator"]
    ]
    assert ops == ["(^)"]


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
    assert "%/" in facts["integer_arithmetic_shapes"]
    assert "%%" in facts["integer_arithmetic_shapes"]
    assert facts["integer_arithmetic_split_candidates"][0].startswith(
        "block_size <= size p from size (drop block_size p)"
    )
    assert "size p %% block_size <> 0" in facts["integer_arithmetic_b2i_guards"]
    assert any(
        "divzMDl" in family and "divz_small" in family
        for family in facts["integer_arithmetic_lemma_families"]
    )

    tactic_choices = [
        name
        for action in model["actions"]
        if action["intent"] == "tactic_forms"
        for name in action["choices"]["name"]
    ]
    assert {"rewrite", "case"} <= set(tactic_choices)

    operator_choices = [
        op
        for action in model["actions"]
        if action["intent"] == "operator_lemmas"
        for op in action["choices"]["operator"]
    ]
    assert "(%/)" in operator_choices
    assert "(%%)" in operator_choices


def test_pure_panel_surfaces_named_memory_decorations_as_short_fact() -> None:
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

    assert "memory_decorated_terms" in facts
    assert "p{m}" in facts["memory_decorated_terms"]
    assert "introduced memory: &m" in facts["memory_decorated_terms"]
    assert "ambient_memory_translation" not in facts


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
    assert [fact["key"] for fact in panel_facts[:8]] == [
        "implication_premises",
        "conclusion_obligations",
        "iter_successor_shape",
        "memory_decorated_terms",
        "integer_arithmetic_shapes",
        "integer_arithmetic_split_candidates",
        "integer_arithmetic_b2i_guards",
        "integer_arithmetic_lemma_families",
    ]
    assert facts["implication_premises"][0].startswith("iter equality premise:")
    assert facts["implication_premises"][1].startswith("nonempty-list premise:")
    assert any("iter equality obligation" in item for item in facts["conclusion_obligations"])
    assert any("size/drop inequality obligation" in item for item in facts["conclusion_obligations"])
    assert facts["memory_decorated_terms"].startswith("terms: p{m}")
    assert "count has top-level + 1" in facts["iter_successor_shape"][0]
    assert facts["integer_arithmetic_split_candidates"] == [
        "block_size <= size p{m} from size (drop block_size p{m})"
    ]
    assert "needs:" not in " ".join(facts["integer_arithmetic_lemma_families"])


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
                    }],
                },
            },
        },
    )
    assert context_only["eligible"] is False
    assert verified["eligible"] is True

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
            "schema_version": 1,
            "results": [{
                "intent": "pr_bridge_routes",
                "payload": {},
                "key": action_preflight_key("pr_bridge_routes", {}),
                "eligible": True,
                "reason": "preflight found a daemon-verified pr_bridge_routes option",
            }],
        },
    }
    actionable_model = surface_model_to_dict(compose_surface_model(actionable, PROFILE))
    assert "pr_bridge_routes" in {
        action["intent"] for action in actionable_model.get("actions", [])
    }


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


def test_choice_preflight_expands_inv_bridge_and_call_subgoal_inputs() -> None:
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
            {"intent": "bridge_probe", "payload": {"claim": "<claim>"}},
            {"intent": "call_subgoals", "payload": {"invariant": "<invariant>"}},
        ]},
    }

    candidates = surface_preflight_candidates(view)
    by_intent = {}
    for item in candidates:
        by_intent.setdefault(item["intent"], []).append(item["payload"])
    assert {"lemma": "equ_cc"} in by_intent["inv_from_lemma"]
    assert {
        "claim": "Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]"
    } in by_intent["bridge_probe"]
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


def test_inv_bridge_and_call_subgoal_preflight_classifiers() -> None:
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
    bridge_rejected = preflight_result_for_action(
        "bridge_probe",
        {"claim": "Pr[A] = Pr[B]"},
        {
            "label": "inspect_bridge_probe",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Bridge Probe",
                    "items": [{
                        "candidate": "Decompose this bridge into smaller Pr equalities.",
                        "verification": "not daemon-verified against the current goal",
                    }],
                },
            },
        },
    )
    bridge_verified = preflight_result_for_action(
        "bridge_probe",
        {"claim": "Pr[A] = Pr[B]"},
        {
            "label": "inspect_bridge_probe",
            "exit_code": 0,
            "agent_observation": {
                "content": {
                    "title": "Bridge Probe",
                    "items": [{
                        "candidate": "have -> : Pr[A] = Pr[B]. byequiv=>//.",
                        "verification": "daemon-verified against the current goal",
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
    assert bridge_rejected["eligible"] is False
    assert bridge_verified["eligible"] is True
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


def test_inv_bridge_and_call_subgoals_surface_only_after_preflight() -> None:
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

    bridge_base = {
        "kind": "prover_workspace_view",
        "proof_status": {"current_layer": "pr", "goal_type": "probability"},
        "current_goal": {
            "lines": ["Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]"]
        },
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "bridge_probe", "payload": {"claim": "<claim>"}},
            {"intent": "goal_info", "payload": {}},
        ]},
    }
    bridge_without = surface_model_to_dict(compose_surface_model(bridge_base, PROFILE))
    assert "bridge_probe" not in {
        action["intent"] for action in bridge_without.get("actions", [])
    }
    bridge_hits = {
        **bridge_base,
        "surface_action_preflight": {
            "schema_version": 1,
            "results": [{
                "intent": "bridge_probe",
                "payload": {"claim": "Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]"},
                "key": action_preflight_key(
                    "bridge_probe",
                    {"claim": "Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]"},
                ),
                "eligible": True,
                "reason": "preflight found a daemon-verified bridge_probe option",
            }],
        },
    }
    bridge_model = surface_model_to_dict(compose_surface_model(bridge_hits, PROFILE))
    assert "bridge_probe" in {
        action["intent"] for action in bridge_model.get("actions", [])
    }


def test_surface_actions_carry_state_eligibility_metadata() -> None:
    model = surface_model_to_dict(
        compose_surface_model(_assignment_recover_view(), "l4_checked_action_surface")
    )
    for action in model["actions"]:
        assert action["eligibility_reason"]
        assert action["state_scope"]
