"""Tests for the ProofContextView -> ProverWorkspaceView manager."""
from __future__ import annotations

import sys
from pathlib import Path


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_workspace_view_manager import (  # type: ignore  # noqa: E402
    WorkspaceViewManager,
    build_workspace_view_plan,
)
from core.easycrypt.session_prover_workspace_view import (  # type: ignore  # noqa: E402
    _first_instruction_alignment,
    _frontier_exposes_call,
    _leading_statement,
    build_prover_workspace_view_from_context,
)
from core.easycrypt.search.ec_tactic_forms import format_forms, get_forms, list_all  # type: ignore  # noqa: E402
from workflow.surface_profiles import (  # type: ignore  # noqa: E402
    apply_workspace_view_surface_profile,
)
from workflow.surface_composer import compose_surface_model  # type: ignore  # noqa: E402
from workflow.surface_panels import (  # type: ignore  # noqa: E402
    _extract_swap_offsets,
    _render_surgery_skeleton,
)
from workflow.surface_action_preflight import action_preflight_key  # noqa: E402


def _context_view(
    *,
    goal_type: str,
    goal_text: str,
    layer: str,
    resources: dict | None = None,
    actions: list[dict] | None = None,
    candidate_menu: list[dict] | None = None,
) -> dict:
    return {
        "kind": "proof_context_view",
        "ok": True,
        "proof_state": {
            "status": "open",
            "candidate_ready": False,
            "final_ready": False,
            "goal": {
                "goal_type": goal_type,
                "num_remaining": 1,
                "num_remaining_determined": True,
                "active_goal_hash": "hash",
                "fact_source": "pretty_goal_text",
                "authority": "pretty_text_fallback",
                "ec_ground_truth": False,
            },
        },
        "current_goal": {
            "goal_type": goal_type,
            "active_goal_hash": "hash",
            "active_goal_preview": goal_text.splitlines()[0],
            "active_goal_text": goal_text,
        },
        "proof_ir": {
            "current_layer": layer,
            "goal_kind": goal_type,
            "candidate_menu": candidate_menu or [],
            "phase": {
                "name": layer,
                "prefer": [],
                "avoid": [],
                "resource_summary": resources or {},
            },
        },
        "actions": actions or [],
        "safe_next_actions": [],
        "guidance": {"recommendations": [], "stale_recommendation_count": 0},
        "debug_refs": {"session_dir": "/tmp/session"},
        "errors": [],
        "notes": [],
    }


def _call_panel_facts(view: dict) -> dict:
    v = dict(view)
    v.setdefault("proof_status", {"current_layer": "call_site"})
    v.setdefault("program_frontier", {"current_frontier_scope": {"frontier": {
        "kind": "left_call",
        "left": {"head": "call", "statement": "x <@ M.f()"},
    }}})
    v.setdefault("call_site_surface", {"live_call_sites": [{
        "side": "left",
        "path": "1",
        "procedure": "M.f",
        "is_frontier_call": True,
        "requires_cut_to_frontier": False,
    }]})
    v.setdefault("inspect_lookup_handles", {"ask_manager_for": [{
        "intent": "call_site_options",
        "payload": {},
    }]})
    v["surface_action_preflight"] = {
        "schema_version": 1,
        "results": [{
            "intent": "call_site_options",
            "payload": {},
            "key": action_preflight_key("call_site_options", {}),
            "eligible": True,
            "reason": "preflight found a runnable call-site option",
        }],
    }
    model = compose_surface_model(v, "l4_checked_action_surface").to_dict()
    panel = model.get("primary_panel") or {}
    return {item["key"]: item.get("value") for item in panel.get("facts", [])}


def test_manager_uses_compact_budget_for_ambient_goal() -> None:
    goal = "\n".join([f"line {idx}" for idx in range(8)])
    plan = build_workspace_view_plan(
        _context_view(goal_type="ambient", goal_text=goal, layer="ambient_logic")
    )

    assert plan.goal_family == "ambient_logic"
    assert plan.budget.goal_window_lines == 400
    assert plan.budget.goal_window_chars == 30000
    assert "pure goal shape" in plan.focus


def test_ambient_residual_with_memory_tags_is_not_relational_program() -> None:
    """Panel re-audit RTF_FixC: a pure-logic residual that EC reduced to an ambient
    goal still carries memory-tagged variables (`F.m{1}`/`F.m{2}`) but has NO
    two-column program frontier. The weak `{1}`+`{2}` text fallback in
    `_classify_goal_family` must NOT drag it into `relational_program` (which would
    offer the relational call/sp/wp/swap/conseq surgery menu on a `smt`/`rewrite`
    leaf). It must classify as `ambient_logic` so the menu/budget/display agree with
    the already-pure-logic renderer. (Corpus items 048/068/069/077/078/079.)"""
    goal = (
        "oget F.m{1}.[x{2} <- (r1L, r2L)].[x{2}] = oget F.m{2}.[x{2}]"
    )
    plan = build_workspace_view_plan(
        _context_view(goal_type="ambient", goal_text=goal, layer="ambient_logic")
    )
    assert plan.goal_family == "ambient_logic"
    assert "pure goal shape" in plan.focus


def test_two_column_program_leaf_stays_relational_program() -> None:
    """Protect-list mirror of the RTF_FixC fix: a LIVE two-column relational program
    frontier (corpus item 042 — `r1 <$ dseed (1) r1 <$ dseed`, layer
    `procedure_body`) genuinely needs the relational surgery menu and MUST keep
    `relational_program`. The ambient-residual gate only fires when the layer/goal
    is itself ambient, never on a program-body frontier carrying `{1}`/`{2}`."""
    goal = "\n".join([
        "r1 <$ dseed                (1)  r1 <$ dseed",
        "pre =",
        "  P.seed{1} = P.seed{2} /\\ P.logP{1} = P.logP{2}",
    ])
    plan = build_workspace_view_plan(
        _context_view(goal_type="pRHL", goal_text=goal, layer="procedure_body")
    )
    assert plan.goal_family == "relational_program"


def test_manager_classifies_probability_goal_with_pr_focus() -> None:
    view = _context_view(
        goal_type="pr",
        goal_text="Pr[G.main() @ &m : res] = Pr[H.main() @ &m : res]",
        layer="pr",
        resources={
            "has_pr_normal_form": True,
            "pr_rewrite_candidates": 2,
        },
    )
    plan = build_workspace_view_plan(view)

    assert plan.goal_family == "probability"
    assert plan.budget.goal_window_lines == 500
    assert plan.budget.goal_window_chars == 30000
    assert "typed bridge/path resources" in plan.focus
    assert "pr_rewrite_candidates" in plan.frontier_resource_keys
    assert any("typed Pr paths" in item for item in plan.inspect_order)


def test_probability_view_surfaces_canonical_inspect_topics() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="pr",
            goal_text="Pr[M.main() @ &m : res] = Pr[N.main() @ &m : res]",
            layer="pr",
        )
    )

    topics = [
        handle.get("intent")
        for handle in slim["inspect_lookup_handles"].get("ask_manager_for", [])
    ]

    assert "goal_info" not in topics
    # Canonical bridge topics expose the goal layer (pr_ vs equiv_) and the
    # verified-route vs context-lemmas status; the verified Pr route precedes
    # the context-only equiv lemmas.
    assert "pr_bridge_routes" in topics
    assert "equiv_bridge_lemmas" in topics
    assert topics.index("pr_bridge_routes") < topics.index("equiv_bridge_lemmas")
    # Broad lemma_index is retired from the normal surface; source reading and
    # lookup_symbol cover file-level declaration discovery.
    assert "lemma_hints" not in topics
    assert "lemma_index" not in topics
    assert "pivot_context" not in topics
    # old names fully renamed away from the agent-facing menu
    assert "bridge_options" not in topics
    assert "bridge_lemmas" not in topics
    assert "goal_patterns" not in topics


def test_prhl_module_projects_typed_procedure_entry_transition() -> None:
    context = _context_view(
        goal_type="equiv",
        goal_text="pre = true\nL.f ~ R.f\npost = ={res}",
        layer="prhl_module",
        candidate_menu=[{
            "id": "proc_open",
            "tactic": "proc.",
            "effect": "`proc` exposes call sites before lower-level proof passes.",
        }],
    )
    context["proof_ir"]["phase"]["legality"] = {
        "proc_open": {
            "status": "preferred",
            "reason": "`proc` exposes call sites before lower-level proof passes.",
        },
    }

    slim = build_prover_workspace_view_from_context(context)

    assert slim["program_frontier"]["procedure_entry_transition"] == {
        "kind": "module_procedure_entry",
        "current_layer": "prhl_module",
        "transition": "proc_open",
        "status": "preferred",
        "tactic": "proc.",
        "effect": "`proc` exposes call sites before lower-level proof passes.",
        "authority": "proof-state analysis phase legality",
    }


def test_non_module_layer_does_not_project_procedure_entry_transition() -> None:
    context = _context_view(
        goal_type="pRHL",
        goal_text="&1: {x:int}\npre = true\nx <- 0\npost = true",
        layer="procedure_body",
        candidate_menu=[{"id": "proc_open", "tactic": "proc."}],
    )
    context["proof_ir"]["phase"]["legality"] = {
        "proc_open": {"status": "preferred"},
    }

    slim = build_prover_workspace_view_from_context(context)

    assert "procedure_entry_transition" not in slim.get("program_frontier", {})


def test_workspace_projection_preserves_parser_confirmed_true_postcondition() -> None:
    context = _context_view(
        goal_type="hoare",
        goal_text="pre = P\nx <@ M.f()\npost = true",
        layer="procedure_body",
    )
    context["proof_state"]["goal"]["post"] = "true"
    context["proof_state"]["goal"]["trivial_postcondition"] = True

    slim = build_prover_workspace_view_from_context(context)

    assert slim["current_goal"]["trivial_postcondition"] is True


def test_probability_view_omits_bridge_topics_when_single_pr() -> None:
    # A single `Pr[P] = const` goal (e.g. PIR_correct) is a direct computation,
    # not a Pr/equiv bridge: the bridge inspect handles return "no matching
    # context". The goal-class menu is gated on >= 2 `Pr[...]` terms, so on a
    # one-Pr goal pr_bridge_routes / equiv_bridge_lemmas are NOT offered (vs the
    # two-Pr goal above, where they are). Generic probability handles still surface.
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="pr",
            goal_text="0 <= i0 < N => Pr[PIR.main(i0) @ &m : res = a i0] = 1%r",
            layer="pr",
        )
    )
    topics = [
        (handle.get("payload") or {}).get("topic")
        for handle in slim["inspect_lookup_handles"].get("ask_manager_for", [])
    ]
    assert "pr_bridge_routes" not in topics
    assert "equiv_bridge_lemmas" not in topics
    assert "goal_info" not in topics
    assert "lemma_index" not in topics


def test_sanitize_agent_view_stamps_committable_move_provenance() -> None:
    """A committable candidate move is stamped with honest provenance markers by
    the runtime panel-policy gate, so the agent is never misled about how the
    option arose or what it guarantees (decided 2026-05-28: provenance attach)."""
    view = WorkspaceViewManager().sanitize_agent_view({
        "kind": "prover_workspace_view",
        "proof_status": {"status": "open"},
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "candidate_moves": {
            "moves": [{
                "title": "Concrete tactic candidate",
                "category": "commit",
                "tactic": "congr.",
                "source": "try",
                "evidence": [
                    "Daemon probe accepted this tactic and it would leave 2 subgoal(s)."
                ],
            }]
        },
    })

    move = view["candidate_moves"]["moves"][0]
    # The runtime gate stamps honest provenance on every committable option.
    assert "verified" in move
    assert "guarantee" in move
    assert "derivation" in move


def test_tactic_forms_cover_mid_prhl_surgery_tools() -> None:
    for name in ("wp", "swap", "rcondt", "rcondf", "conseq", "rnd", "eager", "sim"):
        assert name in list_all()
        forms = get_forms(name)
        assert forms is not None
        rendered = format_forms(forms, mode="pRHL")
        assert f"`{name}` tactic" in rendered
    assert "wp -11 -11" in format_forms(get_forms("wp"), mode="pRHL")  # type: ignore[arg-type]
    assert "rcondt{2}" in format_forms(get_forms("rcondt"), mode="pRHL")  # type: ignore[arg-type]
    assert "cannot infer equalities" in format_forms(get_forms("sim"), mode="pRHL")  # type: ignore[arg-type]


def test_tactic_forms_cover_probability_budget_tools() -> None:
    for name in ("fel", "phoare_split", "phoare"):
        assert name in list_all()
        forms = get_forms(name)
        assert forms is not None
        rendered = format_forms(forms, mode="phoare")
        assert "probability budget" in rendered
    for name in ("seq", "call"):
        assert name in list_all()
        assert get_forms(name) is not None
    assert "phoare split !" in format_forms(get_forms("phoare_split"), mode="phoare")  # type: ignore[arg-type]
    assert "seq K : Q B" in format_forms(get_forms("seq"), mode="phoare")  # type: ignore[arg-type]
    assert "call (_: PRE ==> POST)" in format_forms(get_forms("call"), mode="phoare")  # type: ignore[arg-type]


def test_workspace_view_surfaces_relational_frontier_without_raw_ir() -> None:
    view = _context_view(
        goal_type="equiv",
        goal_text="\n".join([
            "equiv [ G8.main ~ CPA.main :",
            "  ={glob A} ==> ={res}",
            "]",
            "&1 (left) : {i : int}",
            "&2 (right) : {i : int}",
        ]),
        layer="call_site",
        resources={
            "frontier_call_sites": 1,
            "live_callable_lemmas": 2,
            "asymmetric_instrumentation_regions": [
                {"side": "left", "writes": ["bad", "lbad1"]},
            ],
        },
    )

    slim = build_prover_workspace_view_from_context(view)
    rendered = str(slim)

    assert slim["current_goal"]["view_focus"] == "relational_program"
    assert "goal_family" not in slim["current_goal"]
    assert slim["current_goal"]["text_fully_shown"] is True
    assert slim["current_goal"]["truncated"] is False
    assert slim["current_goal"]["lines"][0].startswith("equiv [")
    assert "text" not in slim["current_goal"]
    assert "goal_hash" not in slim["current_goal"]
    assert slim["program_frontier"]["view_focus"] == "relational_program"
    assert "family" not in slim["program_frontier"]
    assert slim["program_frontier"]["focus"]["frontier_call_sites"] == 1
    assert (
        slim["program_frontier"]["focus"]["asymmetric_instrumentation_regions"][0]["side"]
        == "left"
    )
    assert "candidate_menu" not in rendered
    assert "proof_ir" not in slim
    handles = slim["inspect_lookup_handles"]["ask_manager_for"]
    assert all("cost" not in handle for handle in handles)
    by_topic = {handle["intent"]: handle for handle in handles}
    assert "call_subgoals" in by_topic
    assert "manager_note" in slim["inspect_lookup_handles"]
    assert "status" not in by_topic["call_subgoals"]
    assert slim["inspect_lookup_handles"]["effect"].startswith(
        "All handles here are read-only manager requests"
    )
    assert "obligations" in by_topic["call_subgoals"]["returns"]


def test_workspace_view_manager_preserves_panel_order_and_latest_observation() -> None:
    manager = WorkspaceViewManager()

    view = manager.project(
        {
            "schema_version": 1,
            "kind": "prover_workspace_view",
            "ok": True,
            "decision_context": {"proof_options": []},
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "proof_frontier": {"focus": {"live_call_sites": 0}},
            "proof_position": {"status": "open"},
            "recent_diagnostics": {"notes": [{"message": "existing"}]},
            "want_more_context": {"view_fields": ["current_goal.lines"]},
        },
        state_version=7,
        session_epoch=2,
        latest_observation={
            "intent": "commit_tactic",
            "tactic": "inline{1} 2.",
            "status": "rejected",
            "proof_state": "unchanged",
            "error_summary": "invalid position",
        },
    )

    keys = list(view)
    # Goal-dynamic order (panel_policy.panel_order_for): stable situation header,
    # then the synthesized options lead the decision cluster, then the structural
    # surfaces (program_frontier here — no call/seq layer), then support + menu.
    assert keys[:8] == [
        "last_result",
        "current_goal",
        "proof_status",
        "candidate_moves",
        "program_frontier",
        "application_context",
        "facts_and_diagnostics",
        "inspect_lookup_handles",
    ]
    assert keys[-4:] == [
        "schema_version",
        "based_on_state_version",
        "session_epoch",
        "view_hash",
    ]
    observation = view["last_result"]
    assert observation["tactic"] == "inline{1} 2."
    assert "status" not in observation
    assert observation["result"].startswith("EasyCrypt rejected this proof step")
    assert (
        observation["proof_state"]
        == "The committed EasyCrypt proof state was not changed."
    )
    assert observation["error_summary"] == "invalid position"
    assert manager.lint_agent_view(view) == []

    coded = manager.project(
        {
            "schema_version": 1,
            "kind": "prover_workspace_view",
            "current_goal": {"lines": ["Current goal", "x = y"]},
            "recent_diagnostics": {
                "notes": [
                    {
                        "code": "internal.note",
                        "message": "human text",
                    },
                    {
                        "message": "keep this note",
                    },
                ],
            },
        },
        latest_observation={
            "content": {
                "notes": [{
                    "code": "internal.note",
                    "message": "human text",
                }],
            },
        },
    )
    assert coded["last_result"]["content"]["notes"] == [
        {"message": "human text"}
    ]
    assert coded["facts_and_diagnostics"]["notes"] == [{"message": "keep this note"}]

    display = manager.agent_display_view(view)
    assert list(display)[:8] == [
        "last_result",
        "current_goal",
        "proof_status",
        "candidate_moves",
        "program_frontier",
        "application_context",
        "facts_and_diagnostics",
        "inspect_lookup_handles",
    ]
    for hidden in (
        "ok",
        "kind",
        "schema_version",
        "based_on_state_version",
        "session_epoch",
        "view_hash",
    ):
        assert hidden not in display


def test_agent_display_view_does_not_synthesize_empty_diagnostics() -> None:
    manager = WorkspaceViewManager()
    display = manager.agent_display_view({
        "last_result": {},
        "proof_status": {"status": "open"},
        "current_goal": {"lines": ["Current goal"]},
        "surface_profile": {"name": "l1_goal_projection", "stage": "l1_goal_projection"},
    })

    assert "facts_and_diagnostics" not in display


def test_agent_view_lint_rejects_cost_style_wording() -> None:
    manager = WorkspaceViewManager()

    issues = manager.lint_agent_view({
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "recent_diagnostics": {
            "notes": [{
                "message": (
                    "`inline *` is a high-cost global pass here because it "
                    "can hide live handles."
                ),
            }],
        },
    })

    assert any("cost-style wording" in issue for issue in issues)


def test_workspace_view_keeps_large_raw_goal_fully_shown_when_under_budget() -> None:
    goal = "\n".join([f"stmt {idx};" for idx in range(180)])
    slim = build_prover_workspace_view_from_context(
        _context_view(goal_type="equiv", goal_text=goal, layer="call_site")
    )

    current_goal = slim["current_goal"]
    # completeness is shown by the status flags + the full lines; the machine
    # size COUNTS (line_count/shown_lines/...) are stripped from the agent view.
    assert current_goal["text_fully_shown"] is True
    assert current_goal["truncated"] is False
    assert current_goal["lines"] == goal.splitlines()
    assert "text" not in current_goal
    assert "line_count" not in current_goal and "shown_lines" not in current_goal
    assert "current_session_fallback" not in slim["inspect_lookup_handles"]
    assert "files" not in slim["inspect_lookup_handles"]


def test_workspace_view_does_not_label_strategy_hint_as_command() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
            layer="procedure_body",
            candidate_menu=[{
                "id": "proof_ir.call_shape.strategy",
                "action_type": "strategy_hint",
                "tactic": "call (_: Inv).",
                "tactic_family": "call_invariant_skeleton",
                "why": "This invariant shape still needs instantiation.",
            }],
        )
    )

    option = slim["candidate_moves"]["moves"][0]
    assert option["category"] == "strategy"
    assert (
        option["applicability"]
        == "Use this as route-selection context; it is not a tactic to run as-is."
    )
    assert option["tactic_shape"] == "call (_: Inv)."
    assert "tactic" not in option
    assert "command" not in option
    assert "id" not in option
    assert "epistemic_status" not in option
    assert "confidence" not in option


def test_workspace_view_explains_invariant_template_without_bare_enum() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
            layer="call_site",
            candidate_menu=[{
                "id": "proof_ir.call_inv.strategy",
                "action_type": "strategy_hint",
                "tactic": "call (_: Inv).",
                "tactic_family": "call_invariant_skeleton",
                "requires_instantiation": True,
                "why": "Invariant-call route is available.",
            }],
        )
    )

    # A fill-in template (`requires_instantiation`) is guidance the agent must
    # complete, not a state-derived fact — it is no longer surfaced in
    # candidate_moves (the compiler pushes facts, not proof guidance).
    assert not slim["candidate_moves"].get("moves")


def test_workspace_view_adds_call_invariant_inputs_for_visible_call_frontier() -> None:
    goal_text = "\n".join([
        "Current goal",
        "&1 (left ) : {b3 : bool, k : key}",
        "&2 (right) : {b1 : bool}",
        "pre = (glob A){2} = (glob A){m}",
        "SplitC2.I1.RO.m <- empty<:nonce * C.counter, poly_in>",
        "SplitC2.I2.RO.m <- empty<:nonce * C.counter, poly_out>",
        "SplitC1.I2.RO.m <- empty<:nonce * C.counter, extra_block>",
        "SplitD.ROF.RO.m <- empty<:nonce * C.counter, block>",
        "k <$ dkey",
        "Mem.log <- empty<:ciphertext, plaintext>",
        "Mem.lc <- []",
        "BNR.lenc <- []",
        "BNR.ndec <- 0",
        "b3 <@ A(LeftO).main()",
        "b1 <@ A(RightO).main()",
        "post = b3{1} = b1{2}",
    ])
    view = _context_view(
        goal_type="equiv",
        goal_text=goal_text,
        layer="call_site",
        actions=[{
            "category": "strategy",
            "source": "AUTO-DIFF",
            "command": "call (_: Inv).",
            "why": "program-difference analysis found an invariant-call shape.",
            "requires_instantiation": True,
            "metadata": {"proof_ir_tactic_family": "call_invariant_skeleton"},
        }],
    )
    view["proof_ir"]["resources"] = {
        "call_sites": [
            {
                "side": "right",
                "order": 5,
                "statement_path": "5",
                "procedure": "A.main",
                "statement": "b1 <@ A(RightO).main()",
                "is_frontier_call": True,
            },
            {
                "side": "left",
                "order": 12,
                "statement_path": "12",
                "procedure": "A.main",
                "statement": "b3 <@ A(LeftO).main()",
                "is_frontier_call": True,
            },
        ],
        "name_resolution": {
            "items": [
                {
                    "name": "equ_cc",
                    "handle_kind": "call_equiv",
                    "fact_source": "source_scan",
                    "declaration": (
                        "local equiv equ_cc n0 mr0 ms0: "
                        "ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair("
                        "SplitC2.RO_Pair(ROin, ROout), SplitC1.I2.RO), ROF))).enc "
                        "~ EncRnd.cc : "
                        "arg{2}.`1 = n0 /\\ "
                        "(forall n c, (n,c) \\in ROF.m => n \\in BNR.lenc){1} /\\ "
                        "mr0 = ROin.m{1} /\\ "
                        "ms0 = ROout.m{1} ==> ={res}."
                    ),
                    "lhs_proc": (
                        "ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair("
                        "SplitC2.RO_Pair(ROin, ROout), SplitC1.I2.RO), ROF))).enc"
                    ),
                    "rhs_proc": "EncRnd.cc",
                }
            ]
        },
    }
    view["evidence"] = {
        "context": [
            {
                "lemma": "equ_cc",
                "call_template": (
                    "ecall (equ_cc <nonce_var>{1} "
                    "<ROin_map>{1} <ROout_map>{1})."
                ),
                "semantic_delta": (
                    "A split random-oracle encryption route can match EncRnd "
                    "when the selected call-equivalence precondition is met."
                ),
            }
        ]
    }

    slim = build_prover_workspace_view_from_context(view)
    inputs = slim["application_context"]

    assert "call (_: ...)" in inputs["how_to_use"]
    assert inputs["visible_call_frontier"]["left"]["statement"] == "b3 <@ A(LeftO).main()"
    assert inputs["visible_call_frontier"]["right"]["statement"] == "b1 <@ A(RightO).main()"
    assert inputs["selected_handles"][0]["name"] == "equ_cc"
    assert "candidate_fact_shapes" not in inputs
    assert "caution" not in inputs
    assert any(
        "ROF.m" in item["atom"]
        for item in inputs["declaration_requirements"]
        if item["category"] == "external state fact"
    )
    assert inputs["declaration_requirements"][0]["source_lemma"] == "equ_cc"
    assert any(
        "ROin.m" in item["atom"]
        for item in inputs["declaration_requirements"]
        if item["category"] == "base relation input"
    )
    assert inputs["visible_but_not_required"] == [
        {
            "state": "SplitC1.I2.RO.m",
            "why_visible": "It is initialized before the visible call frontier.",
            "why_not_added_by_default": (
                "The selected call-equivalence precondition facts do not name "
                "this state. Add it to an invariant only if a call-subgoal "
                "preview creates an obligation for it."
            ),
        }
    ]
    assert inputs["inspect_if_unsure"]["intent"] == "call_subgoals"
    assert inputs["inspect_if_unsure"]["payload"] == {}
    assert "extra conjuncts" in inputs["inspect_if_unsure"]["why"]


def test_frontier_exposes_call_survives_filtered_placeholder_skeleton() -> None:
    """Regression (facts-only producer cut): the call-invariant write-map gate keys
    off the FACTUAL call frontier via `_frontier_exposes_call`, not the candidate_menu.
    An un-filled `call (_: <adversary invariant>)` skeleton is GUIDANCE and is dropped
    from candidate_menu at the producer — but the real call frontier (call_sites) still
    exists, so the gate must still fire. Reading the now-call-item-free menu alone
    would suppress the write-map exactly in the placeholder-only adversary case where
    the agent most needs it.
    """
    # candidate_menu carries NO `call (_:` item and no skeleton family (the placeholder
    # was filtered as guidance) — the regression precondition.
    menu_without_call = {"candidate_menu": [{"tactic": "proc."}, {"tactic": "inline *."}]}
    frontier_with_call = {"call_sites": [{"side": "right", "statement": "b <@ A(O).main()"}]}
    assert _frontier_exposes_call(frontier_with_call, "", menu_without_call) is True

    # No call signal anywhere -> stays suppressed (the fix must not over-surface).
    assert _frontier_exposes_call({}, "post = a{1} = b{2}", menu_without_call) is False


def test_swap_offset_harvest_blanks_route_dependent_offset() -> None:
    """HINT_UNIQUENESS_POLICY V1 regression: the signed swap OFFSET is route-dependent
    (≥11 EC-valid offsets at the schnorr_shvzk frontier; only the route picks one), so it
    must NEVER be surfaced as a lone value. The harvest surfaces the source-position FRAME
    with the offset BLANKED (`<offset>`), mirroring `_extract_seq_positions` blanking the
    coupling. Items 111/117 saw `swap{2} 12 -2` when the route needed `-5`."""
    view = {"program_frontier": {"checked_structural_sources": {
        "swap_sources": [
            {"form": "swap{1} 3 <offset>.", "side": "1", "source_position": "3"},
            {"form": "swap [1..3] <offset>.", "source_position": "1..3"},
        ],
    }}}
    frames = _extract_swap_offsets(view)
    # source-position frame is surfaced (the "a swap is available here" signal survives),
    # but the offset value is blanked, never the lone signed number.
    assert frames == [
        "`swap{1} 3 <offset>.` -- checked static-realignment source; the offset is not selected.",
        "`swap [1..3] <offset>.` -- checked static-realignment source; the offset is not selected.",
    ]
    # the lone signed offset must NOT leak in any form
    assert all("swap{1} 3 2" not in f and "[1..3] 2" not in f for f in frames)
    # CRITICAL: two DIFFERENT offsets at the SAME source collapse to ONE frame — the
    # producer no longer leaks which arbitrary offset candidate_moves happened to compute.
    same_source = {"program_frontier": {"checked_structural_sources": {
        "swap_sources": [
            {"form": "swap{2} 12 <offset>.", "side": "2", "source_position": "12"},
        ],
    }}}
    collapsed = _extract_swap_offsets(same_source)
    assert len(collapsed) == 1
    assert all("-2" not in f and "-5" not in f for f in collapsed)
    # Legacy tactic prose is not a fact source. No typed facts means no frames.
    assert _extract_swap_offsets({"candidate_moves": {"moves": [{"tactic": "auto."}]}}) == []
    assert _extract_swap_offsets({
        "candidate_moves": {"moves": [{"tactic": "swap{1} 3 2."}]}
    }) == []
    assert _extract_swap_offsets({}) == []
    # wired into the surgery skeleton under `swap_offsets`
    skel = _render_surgery_skeleton(view)
    assert skel is not None and "swap_offsets" in skel
    assert any("swap{1} 3 <offset>" in s for s in skel["swap_offsets"])
    preblanked = _render_surgery_skeleton({
        "program_frontier": {"checked_structural_sources": {
            "swap_sources": [{
                "form": "swap{2} 12 <offset>.",
                "side": "2",
                "source_position": "12",
            }],
        }}
    })
    assert preblanked is not None
    assert preblanked["swap_offsets"] == [
        "`swap{2} 12 <offset>.` -- checked static-realignment source; the offset is not selected.",
    ]


def test_call_focus_surfaces_precise_context_not_low_precision_write_map() -> None:
    """The call panel surfaces decision-relevant call-frontier facts only.

    Module aliases, the abstract-adversary `glob` boundary, and the `inline*`
    preview are useful current-frontier facts.  The static write-map is too
    broad unless intersected with current required frame obligations, so it
    stays out of the presentation surface.
    """
    view = {
        "application_context": {
            "call_frontier_structure": {
                "module_aliases": [{"alias": "M0", "resolves_to": "MAC20"},
                                   {"alias": "M1", "resolves_to": "MAC2"}],
                "abstract_adversaries": [{"name": "A"}],
            },
            "inline_preview": {
                "call": "y <@ H.f(m)",
                "modules": [{"module": "H", "kind": "abstract", "inline": "stops (abstract adversary)"}],
                "inline_stops_at": ["H"], "call_at": ["H"],
            },
            "write_map": {"fields": [
                {"field": "H.f", "written_by": [], "status": "read-only here (safe `={H.f}`)"},
                {"field": "M.log", "written_by": ["HH", "M"], "status": "mutated"},
            ]},
        },
    }
    focus = _call_panel_facts(view)
    assert any("MAC20" in s for s in focus.get("module_aliases") or [])
    glob = focus.get("abstract_adversary_glob") or ""
    assert "`A`" in glob and "={glob" in glob          # the step4_badi drop-={glob A} fact
    assert "STOPS at" in (focus.get("inline_preview") or "")
    assert "frame_write_summary" not in focus
    assert "frame_write_map" not in focus
    # graceful: no application_context -> none of the new keys (never a placeholder)
    bare = _call_panel_facts({})
    for k in ("module_aliases", "abstract_adversary_glob", "inline_preview", "frame_write_map", "frame_write_summary"):
        assert k not in bare


def test_call_focus_hides_incomplete_inline_preview_tail() -> None:
    view = {
        "application_context": {
            "inline_preview": {
                "call": "c2 <@ ChaCha(...).enc(k, n, p2)",
            },
        },
    }

    focus = _call_panel_facts(view)

    assert "inline_preview" not in focus


def test_workspace_view_marks_unresolved_lemma_as_lookup_hint() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
            layer="call_site",
            candidate_menu=[{
                "action_type": "strategy_hint",
                "tactic": "call poly_mac1.",
                "tactic_family": "call_named_equiv",
                "why": "Route landmark for the current call site.",
                "cost_factors": {
                    "name_resolution_status": "source_scope_check_required",
                },
            }],
        )
    )

    option = slim["candidate_moves"]["moves"][0]
    assert option["category"] == "strategy"
    assert option["tactic_shape"] == "call poly_mac1."
    assert "tactic" not in option
    assert option["symbol_hint"] == "poly_mac1"
    assert option["lookup_before_use"] == {
        "intent": "lookup_symbol",
        "payload": {"symbol": "poly_mac1"},
    }
    assert "route landmark" in option["limitations"][0]


def test_workspace_view_treats_named_call_strategy_as_landmark_until_checked() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
            layer="call_site",
            candidate_menu=[{
                "action_type": "strategy_hint",
                "tactic": "call chacha_enc1.",
                "tactic_family": "call_named_equiv",
                "why": "A nearby helper name is relevant to the current route.",
            }],
        )
    )

    option = slim["candidate_moves"]["moves"][0]

    assert option["tactic_shape"] == "call chacha_enc1."
    assert "tactic" not in option
    assert option["symbol_hint"] == "chacha_enc1"
    assert option["lookup_before_use"] == {
        "intent": "lookup_symbol",
        "payload": {"symbol": "chacha_enc1"},
    }
    assert option["runnable_status"].startswith("Not established as a live call tactic")
    assert "route landmark" in option["limitations"][0]


def test_workspace_view_explains_rnd_template_inputs() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
            layer="procedure_body",
            candidate_menu=[{
                "id": "proof_ir.rnd.strategy",
                "action_type": "strategy_hint",
                "tactic": "rnd (fun x => x + <offset>) (fun x => x - <offset>).",
                "tactic_family": "sampling_coupling",
                "requires_instantiation": True,
                "why": "Sampling statements are visible.",
            }],
        )
    )

    # A fill-in template (`requires_instantiation`) is guidance, not a fact — no
    # longer surfaced in candidate_moves.
    assert not slim["candidate_moves"].get("moves")


def test_workspace_view_explains_splitwhile_template_inputs() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
            layer="procedure_body",
            candidate_menu=[{
                "id": "proof_ir.splitwhile.strategy",
                "action_type": "strategy_hint",
                "tactic": "splitwhile{1} 2: (<split of 5 <= r>).",
                "tactic_family": "splitwhile",
                "requires_instantiation": True,
                "why": "A loop frontier is visible.",
            }],
        )
    )

    # A fill-in template (`requires_instantiation`) is guidance, not a fact — no
    # longer surfaced in candidate_moves.
    assert not slim["candidate_moves"].get("moves")


def test_workspace_view_lints_unreviewed_enum_values_with_path() -> None:
    manager = WorkspaceViewManager()
    issues = manager.lint_agent_view({
        "current_goal": {"lines": ["x = y"]},
        "candidate_moves": {
            "moves": [{
                "applicability": "needs_instantiation",
            }],
        },
    })

    assert issues == [
        "unreviewed enum-like value in agent view: "
        "candidate_moves.moves[0].applicability = 'needs_instantiation'"
    ]


def test_workspace_view_keeps_legacy_auto_pivot_as_inspect_handle_not_move() -> None:
    # The move list is sourced from the factual `candidate_menu`; a legacy
    # AUTO-PIVOT lookup (a heuristic kb-hint recommendation) is not a menu move,
    # it surfaces only as an inspect/lookup handle. A manager-preflighted proc
    # candidate in the menu renders as a ready move.
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ G8.main ~ CPA.main : ={glob A} ==> ={res} ]",
            layer="prhl_module",
            candidate_menu=[{
                "id": "proof_ir.proc_open.preflight",
                "action_type": "runnable_tactic",
                "tactic": "proc.",
                "tactic_family": "proc_open",
                "epistemic_status": "easycrypt_preflight_accepted",
                "verified": True,
            }],
            actions=[
                {
                    "id": "diagnostic.auto_pivot.foo.inspect",
                    "category": "inspect",
                    "source": "AUTO-PIVOT",
                    "command": (
                        "python3 core/easycrypt/session_cli.py -d SESSION "
                        "-where CCP_OCCP"
                    ),
                    "state_changed": False,
                    "why": "Unverified pivot lookup.",
                    "epistemic_status": "unverified_pivot_not_frontier_verified",
                    "metadata": {
                        "unverified_pivot_hint": True,
                        "scheduler_role": "unverified_pivot_background",
                    },
                },
            ],
        )
    )

    option = slim["candidate_moves"]["moves"][0]
    assert "id" not in option
    assert "command" not in option
    assert "confidence" not in option
    assert option["tactic"] == "proc."
    assert option["source"] == "proof-state analysis"
    assert option["evidence"] == ["EasyCrypt verified this against the current goal."]
    handles = slim["inspect_lookup_handles"]["lookup_candidates"]
    assert len(handles) == 1
    assert handles[0]["symbol"] == "CCP_OCCP"
    assert "id" not in handles[0]
    assert "command" not in handles[0]
    assert "confidence" not in handles[0]


def test_workspace_view_drops_empty_strategy_options() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="ambient",
            goal_text="x = y",
            layer="ambient_logic",
            actions=[{
                "category": "strategy",
                "source": "ProofIR",
            }],
        )
    )

    assert "moves" not in slim.get("candidate_moves", {})


def test_workspace_view_humanizes_internal_route_sources() -> None:
    # An internal AUTO-DIFF recommendation must never leak its raw source enum
    # into the agent view, whatever panel it lands in.
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="equiv",
            goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
            layer="call_site",
            actions=[{
                "category": "strategy",
                "source": "AUTO-DIFF",
                "command": "call H.",
                "why": "AUTO-DIFF found this call shape while comparing programs.",
            }],
        )
    )

    text = str(slim)
    assert "AUTO-DIFF" not in text
    assert WorkspaceViewManager().lint_agent_view(slim) == []


def test_ambient_residual_uses_close_tools_not_call_tools() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="ambient",
            goal_text="x + y = y + x",
            layer="procedure_body",
        )
    )

    assert slim["current_goal"]["view_focus"] == "ambient_logic"
    by_topic = {
        handle["intent"]: handle
        for handle in slim["inspect_lookup_handles"]["ask_manager_for"]
    }
    # Broad lemma_index is hidden; tactic forms remain state-selected.
    assert "tactic_forms" in by_topic
    assert "lemma_index" not in by_topic
    assert "goal_info" not in by_topic
    assert "lemma_hints" not in by_topic
    assert "suggest_close" not in by_topic
    assert "call_site_options" not in by_topic
    assert "call_subgoals" not in by_topic


def test_workspace_view_filters_low_level_tool_names_from_inspect_handles() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="pr",
            goal_text="Pr[M.main() @ &m : res] = Pr[N.main() @ &m : res]",
            layer="pr",
            actions=[
                {
                    "category": "inspect",
                    "source": "AUTO-PIVOT",
                    "epistemic_status": "unverified_pivot_not_frontier_verified",
                    "tool": "try",
                    "why": "Probe candidate context should stay out of inspect handles.",
                },
                {
                    "category": "inspect",
                    "source": "AUTO-PIVOT",
                    "epistemic_status": "unverified_pivot_not_frontier_verified",
                    "tool": "inspect_context",
                    "why": (
                        "If pursuing this bridge, inspect it with "
                        "`-where pr_CCP_OCCP` before guessing arguments."
                    ),
                },
            ],
        )
    )

    handles = slim["inspect_lookup_handles"]
    topics = [
        (handle.get("payload") or {}).get("topic")
        for handle in handles.get("ask_manager_for", [])
    ]
    assert "try" not in topics
    assert "inspect_context" not in topics
    lookup_symbols = {
        handle.get("symbol") for handle in handles.get("lookup_candidates", [])
    }
    assert "pr_CCP_OCCP" in lookup_symbols
    assert WorkspaceViewManager().lint_agent_view(slim) == []


def test_workspace_view_manager_normalizes_legacy_inspect_handle_topics() -> None:
    manager = WorkspaceViewManager()

    slim = manager.project({
        "schema_version": 2,
        "kind": "prover_workspace_view",
        "ok": True,
        "current_goal": {"lines": ["Current goal", "x = y"]},
        "proof_status": {"status": "open"},
        "inspect_lookup_handles": {
            "ask_manager_for": [
                {
                    "intent": "inspect_context",
                    "payload": {"topic": "try"},
                    "use_when": "Probe-shaped context mentions `-where pr_CCP_OCCP`.",
                },
                {
                    "intent": "inspect_context",
                    "payload": {"topic": "inspect_context"},
                    "use_when": "Wrapper handle mentions `-sig equ_cc`.",
                },
                {
                    "intent": "inspect_context",
                    "topic": "-goal-info",
                    "use_when": "Need parsed goal shape.",
                },
            ],
        },
    })

    handles = slim["inspect_lookup_handles"]
    topics = [
        (handle.get("payload") or {}).get("topic")
        for handle in handles.get("ask_manager_for", [])
    ]
    assert topics == []
    lookup_symbols = {
        handle.get("symbol") for handle in handles.get("lookup_candidates", [])
    }
    assert {"pr_CCP_OCCP", "equ_cc"} <= lookup_symbols
    assert manager.lint_agent_view(slim) == []


def test_workspace_view_maps_native_search_handle_to_rewrite_candidates() -> None:
    slim = build_prover_workspace_view_from_context(
        _context_view(
            goal_type="pr",
            goal_text="Pr[M.main() @ &m : res] <= Pr[N.main() @ &m : res]",
            layer="pr",
            actions=[{
                "category": "inspect",
                "source": "ProofIR",
                "tool": "search",
                "command": (
                    "python3 core/easycrypt/session_cli.py -d SESSION "
                    "-search-skeleton 'mu predU'"
                ),
                "why": (
                    "Goal is a Pr additive/union-style bound; EC native "
                    "search can retrieve probability union/split lemmas."
                ),
                "metadata": {
                    "proof_ir_tactic_family": "native_ast_search",
                },
            }],
        )
    )

    topics = [
        handle.get("intent")
        for handle in slim["inspect_lookup_handles"].get("ask_manager_for", [])
    ]
    assert "rewrite_candidates" in topics
    assert "search" not in topics
    assert WorkspaceViewManager().lint_agent_view(slim) == []


def test_agent_view_lint_rejects_low_level_inspect_topics() -> None:
    manager = WorkspaceViewManager()

    issues = manager.lint_agent_view({
        "inspect_lookup_handles": {
            "ask_manager_for": [
                {
                    "intent": "inspect_context",
                    "payload": {"topic": "try"},
                },
            ],
        },
    })

    assert issues == [
        "low-level inspect topic leaked into agent view: "
        "inspect_lookup_handles.ask_manager_for[0].payload.topic = 'try'"
    ]


def test_synchronized_prhl_frontier_does_not_say_missing_right_side() -> None:
    view = _context_view(
        goal_type="equiv",
        goal_text="\n".join([
            "&1 (left ) : {j : int} [programs are in sync]",
            "&2 (right) : {j : int}",
            "",
            "pre = true",
            "(1------)  while (j < N) {",
        ]),
        layer="procedure_body",
    )
    view["proof_ir"]["resources"] = {
        "handles": {
            "procedure_body_frontend": {
                "structured_regions": [
                    {
                        "kind": "straight_line_prefix",
                        "side": "left",
                        "statement_order": 1,
                        "statement_path": "1",
                        "statement": "j <- 0",
                    },
                    {
                        "kind": "loop_frontier",
                        "side": "left",
                        "statement_order": 2,
                        "statement_path": "2",
                        "condition": "j < N",
                    },
                ],
            },
        },
    }

    slim = build_prover_workspace_view_from_context(view)
    rows = slim["program_frontier"]["frontier_alignment"]["rows"]
    first = slim["program_frontier"]["frontier_alignment"]["first_instruction_alignment"]
    rendered = str(rows)

    assert rows[0]["role"] == "synchronized setup"
    assert rows[1]["role"] == "synchronized loop frontier"
    # (2026-06-05) the first-instruction head is the SYNTACTIC first statement — the
    # leading setup assignment — not the loop reached after absorbing it. Reporting
    # the loop here meant skipping the leading statements; reporting the assignment
    # tells the agent the real next step (sp/wp the head before the loop frontier).
    assert first["left_head"] == "assignment"
    # (FIX#2, deep audit Tier-B) the programs carry the `[programs are in sync]` marker, so
    # the frontier is SYNCHRONIZED — not a deficient relational "one-sided" frontier. The
    # old "one-sided_frontier" label pushed "a one-sided tactic before a symmetric tactic",
    # the opposite of the correct symmetric route.
    assert first["branch_alignment"] == "synchronized_frontier"
    assert "single residual program column" in rows[0]["right"]
    assert "one column" in rows[1]["proof_read"]
    assert "no matching right-side" not in rendered


def test_workspace_view_shows_first_instruction_branch_alignment() -> None:
    view = _context_view(
        goal_type="equiv",
        goal_text="equiv [ M1.f ~ M2.f : ={x} ==> ={res} ]",
        layer="procedure_body",
    )
    view["proof_ir"]["resources"] = {
        "handles": {
            "procedure_body_frontend": {
                "structured_regions": [
                    {
                        "kind": "branch_frontier",
                        "ordinal": 1,
                        "left": {
                            "side": "left",
                            "statement_order": 1,
                            "statement_path": "1",
                            "statement": "if (x < y) {",
                        },
                        "right": {
                            "side": "right",
                            "statement_order": 1,
                            "statement_path": "1",
                            "statement": "if (x < y) {",
                        },
                    },
                ],
            },
        },
    }

    slim = build_prover_workspace_view_from_context(view)
    first = slim["program_frontier"]["frontier_alignment"]["first_instruction_alignment"]

    assert first["left_head"] == "if"
    assert first["right_head"] == "if"
    assert first["branch_alignment"] == "both_sides_at_if"
    assert "`if` is a plausible next" in first["proof_read"]


def test_workspace_view_projects_frontier_alignment_from_proof_ir() -> None:
    view = _context_view(
        goal_type="equiv",
        # The call statement is rendered at the active frontier (FIX-B keeps only call
        # sites whose statement is verbatim in the goal — a live frontier call is).
        goal_text="\n".join([
            "equiv [ M1.f ~ M2.f : ={glob A} ==> ={res} ]",
            "c <@ O.enc(n, p);",
            "~",
            "c <@ O.enc(n, p);",
        ]),
        layer="call_site",
    )
    view["proof_ir"]["resources"] = {
        "handles": {
            "procedure_body_frontend": {
                "structured_regions": [
                    {
                        "kind": "aligned_call_frontier",
                        "ordinal": 1,
                        "left": {
                            "side": "left",
                            "statement_order": 7,
                            "statement_path": "7",
                            "kind": "CALL",
                            "statement": "c <@ O.enc(n, p);",
                            "procedure_tail": "O.enc",
                            "is_frontier_call": True,
                            "vars_written": ["c"],
                            "vars_read": ["n", "p"],
                        },
                        "right": {
                            "side": "right",
                            "statement_order": 5,
                            "statement_path": "5",
                            "kind": "CALL",
                            "statement": "c <@ O.enc(n, p);",
                            "procedure_tail": "O.enc",
                            "is_frontier_call": True,
                            "vars_written": ["c"],
                            "vars_read": ["n", "p"],
                        },
                        "same_concrete_procedure": True,
                        "shared_written_vars": ["c"],
                    },
                ],
            },
        },
    }

    slim = build_prover_workspace_view_from_context(view)
    alignment = slim["program_frontier"]["frontier_alignment"]
    region = alignment["rows"][0]

    assert "left_right_regions" not in slim["program_frontier"]
    assert alignment["summary"].startswith("Frontier alignment:")
    assert alignment["first_instruction_alignment"]["left_head"] == "call"
    assert alignment["first_instruction_alignment"]["branch_alignment"] == "both_sides_at_call"
    assert region["role"] == "aligned call frontier"
    assert region["left"] == "c <@ O.enc(n, p);"
    assert region["right"] == "c <@ O.enc(n, p);"
    assert region["location"]["left_path"] == "7"
    assert region["location"]["right_path"] == "5"
    assert "same procedure name: `O.enc`" in region["observations"]
    assert "shared written vars: c" in region["observations"]
    assert "named equiv call" in region["proof_read"]
    assert slim["program_frontier"]["call_sites"] == [
        {
            "side": "left",
            "statement_order": 7,
            "statement_path": "7",
            "procedure": "O.enc",
            "statement": "c <@ O.enc(n, p);",
            "frontier": True,
        },
        {
            "side": "right",
            "statement_order": 5,
            "statement_path": "5",
            "procedure": "O.enc",
            "statement": "c <@ O.enc(n, p);",
            "frontier": True,
        },
    ]


def test_frontier_alignment_separates_post_call_residual_suffix() -> None:
    view = _context_view(
        goal_type="equiv",
        # The live call + its residual suffix are rendered at the frontier (FIX-B keeps a
        # call site only when its statement is verbatim in the goal).
        goal_text="\n".join([
            "equiv [ M1.f ~ M2.f : ={glob A} ==> ={res} ]",
            "p <- None<:plaintext>",
            "p <@ O.dec(c)",
            "BNR.ndec <- BNR.ndec + 1",
        ]),
        layer="call_site",
    )
    view["proof_ir"]["resources"] = {
        "handles": {
            "procedure_body_frontend": {
                "structured_regions": [
                    {
                        "kind": "wrapper_or_init",
                        "side": "left",
                        "statement_order": 1,
                        "statement_path": "1",
                        "statement": "p <- None<:plaintext>",
                    },
                    {
                        "kind": "wrapper_or_init",
                        "side": "right",
                        "statement_order": 1,
                        "statement_path": "1",
                        "statement": "p <- None<:plaintext>",
                    },
                    {
                        "kind": "aligned_call_frontier",
                        "ordinal": 2,
                        "left": {
                            "side": "left",
                            "statement_order": 2,
                            "statement_path": "2.1",
                            "kind": "CALL",
                            "statement": "p <@ O.dec(c)",
                            "procedure_tail": "O.dec",
                            "is_frontier_call": True,
                        },
                        "right": {
                            "side": "right",
                            "statement_order": 2,
                            "statement_path": "2.1",
                            "kind": "CALL",
                            "statement": "p <@ O.dec(c)",
                            "procedure_tail": "O.dec",
                            "is_frontier_call": True,
                        },
                    },
                    {
                        "kind": "wrapper_or_init",
                        "side": "left",
                        "statement_order": 3,
                        "statement_path": "2.2",
                        "statement": "BNR.ndec <- BNR.ndec + 1",
                    },
                    {
                        "kind": "wrapper_or_init",
                        "side": "right",
                        "statement_order": 3,
                        "statement_path": "2.2",
                        "statement": "BNR.ndec <- BNR.ndec + 1",
                    },
                ],
            },
        },
    }

    slim = build_prover_workspace_view_from_context(view)
    alignment = slim["program_frontier"]["frontier_alignment"]
    rows = alignment["rows"]

    assert [row["role"] for row in rows[:3]] == [
        "setup / initialization",
        "aligned call frontier",
        "residual after call",
    ]
    assert "p <- None" in rows[0]["left"]
    assert "BNR.ndec" not in rows[0]["left"]
    assert "BNR.ndec <- BNR.ndec + 1" in rows[2]["left"]
    assert "after the live call frontier" in rows[2]["proof_read"]
    # (2026-06-05) the first-instruction head is the SYNTACTIC first statement
    # (`p <- None`), not the call that follows it: the agent must `sp`/`wp` the
    # leading assignment before it can cross the call. (The call frontier itself is
    # still reported in the rows / call_sites; this is the *first* instruction.)
    assert alignment["first_instruction_alignment"]["branch_alignment"] == (
        "both_sides_at_assignment"
    )
    assert "residual statements remain after a call frontier" in alignment["summary"]


def test_workspace_view_merges_raw_call_sites_into_frontier() -> None:
    view = _context_view(
        goal_type="equiv",
        # Both call statements are rendered at the frontier so FIX-B keeps them (it drops
        # only call sites whose statement is absent from the goal — consumed/hypothesis).
        goal_text="\n".join([
            "equiv [ M1.f ~ M2.f : ={glob A} ==> ={res} ]",
            "b3 <@ A(LeftO).main()",
            "~",
            "b1 <@ A(RightO).main()",
        ]),
        layer="call_site",
    )
    view["proof_ir"]["resources"] = {
        "call_sites": [
            {
                "side": "left",
                "order": 12,
                "statement_path": "12",
                "procedure": "A.main",
                "statement": "b3 <@ A(LeftO).main()",
                "is_frontier_call": True,
            },
            {
                "side": "right",
                "order": 5,
                "statement_path": "5",
                "procedure": "A.main",
                "statement": "b1 <@ A(RightO).main()",
                "is_frontier_call": True,
            },
        ],
        "handles": {
            "procedure_body_frontend": {
                "structured_regions": [
                    {
                        "kind": "call_site",
                        "side": "right",
                        "statement_order": 5,
                        "statement_path": "5",
                        "procedure": "A.main",
                        "statement": "b1 <@ A(RightO).main()",
                    },
                ],
            },
        },
    }

    slim = build_prover_workspace_view_from_context(view)
    call_sites = slim["program_frontier"]["call_sites"]

    assert [site["side"] for site in call_sites] == ["right", "left"]
    assert call_sites[1]["statement_path"] == "12"
    assert call_sites[1]["statement"] == "b3 <@ A(LeftO).main()"


def test_manager_owns_phase_resource_selection() -> None:
    view = _context_view(
        goal_type="ambient",
        goal_text="x = y",
        layer="ambient_logic",
        resources={
            "native_ast_search_hits": 2,
            "frontier_call_sites": 1,
            "asymmetric_instrumentation_regions": [{"side": "left"}],
        },
    )
    plan = build_workspace_view_plan(view)
    slim = build_prover_workspace_view_from_context(view)

    assert plan.goal_family == "ambient_logic"
    assert plan.phase_summary.startswith("Ambient logic layer")
    assert plan.phase_resource_keys == (
        "native_ast_search_queries",
        "native_ast_search_hits",
        "unfoldable_goal_heads",
        "unfoldable_goal_head_count",
    )
    assert slim["facts_and_diagnostics"] == {}


def test_workspace_view_compacts_unfoldable_goal_heads() -> None:
    view = _context_view(
        goal_type="ambient",
        goal_text="check_plaintext x",
        layer="ambient_logic",
        resources={
            "unfoldable_goal_heads": [{
                "name": "check_plaintext",
                "declaration_kind": "op",
                "unfold_tactic": "rewrite /check_plaintext.",
                "smt_argument_role": "not_a_lemma_hint",
                "source_path": "/very/long/path/context.ec",
                "note": "verbose internal note",
            }],
            "unfoldable_goal_head_count": 1,
        },
    )

    slim = build_prover_workspace_view_from_context(view)
    heads = slim["facts_and_diagnostics"]["facts"]["unfoldable_goal_heads"]

    assert heads == [{
        "name": "check_plaintext",
        "declaration_kind": "op",
        "unfold_tactic": "rewrite /check_plaintext.",
        "smt_argument_role": "not_a_lemma_hint",
    }]


def test_workspace_view_keeps_unfoldable_facts_structured_under_budget() -> None:
    view = _context_view(
        goal_type="ambient",
        goal_text="f0 x /\\ f1 x /\\ f2 x /\\ f3 x /\\ f4 x",
        layer="ambient_logic",
        resources={
            "unfoldable_goal_heads": [
                {
                    "name": f"Very.Long.Qualified.f{idx}",
                    "unqualified_name": f"f{idx}",
                    "declaration_kind": "op",
                    "unfold_tactic": f"rewrite /Very.Long.Qualified.f{idx}.",
                    "smt_argument_role": "not_a_lemma_hint",
                    "source_path": "/very/long/path/context.ec",
                    "note": "verbose internal note",
                }
                for idx in range(8)
            ],
            "unfoldable_goal_head_count": 8,
        },
    )

    slim = build_prover_workspace_view_from_context(view)
    heads = slim["facts_and_diagnostics"]["facts"]["unfoldable_goal_heads"]

    assert isinstance(heads, list)
    assert heads[0]["name"] == "Very.Long.Qualified.f0"
    assert "source_path" not in heads[0]
    assert len(heads) <= 4


def test_workspace_view_promotes_branch_guard_local_hints() -> None:
    goal = "\n".join([
        "pre = x{1} = (n{1}, C.ofintd 0) /\\ ! (n{1} \\in BNR.lenc{1})",
        "if (SplitD.test x) {",
        "  t <$ dpoly_out",
        "}",
    ])
    view = _context_view(
        goal_type="pRHL",
        goal_text=goal,
        layer="procedure_body",
        resources={
            "unfoldable_goal_heads": [{
                "name": "SplitD.test",
                "unqualified_name": "test",
                "declaration_kind": "op",
                "unfold_tactic": "rewrite /SplitD.test.",
                "smt_argument_role": "not_a_lemma_hint",
            }],
        },
    )

    slim = build_prover_workspace_view_from_context(view)
    hints = slim["program_frontier"]["local_goal_hints"]

    assert hints["branch_guard_definitions"][0]["symbol"] == "SplitD.test"
    assert hints["branch_guard_definitions"][0]["unfold_tactic"] == (
        "rewrite /SplitD.test."
    )
    rewrite_symbols = {
        item["symbol"] for item in hints["local_rewrite_facts"]
    }
    assert {"C.ofintdK", "C.toint_ofintd"} <= rewrite_symbols
    assert hints["local_rewrite_facts"][0]["lookup_before_use"] == {
        "intent": "lookup_symbol",
        "payload": {"symbol": "C.ofintdK"},
    }


def test_manager_classifies_seq_cut_from_coverage_resources() -> None:
    view = _context_view(
        goal_type="equiv",
        goal_text="equiv [ M.f ~ N.f : ={x} ==> ={res} ]",
        layer="procedure_body",
        resources={
            "seq_cut_coverage": {"covered": 3, "total": 5},
            "missing_live_facts": ["={bad}"],
            "preserved_vars": ["i", "s"],
        },
        actions=[{
            "id": "proof_ir.program_seq_cut",
            "title": "Program seq cut",
            "tactic": "seq 4 4.",
        }],
    )

    plan = build_workspace_view_plan(view)

    assert plan.goal_family == "seq_cut"
    assert "cut coverage" in plan.focus
    assert "missing_live_facts" in plan.frontier_resource_keys
    # only the epistemic guardrail remains in frontier_checks (the route-
    # preference "read coverage before committing" prose was removed).
    assert any("not evidence" in check for check in plan.frontier_checks)

    slim = build_prover_workspace_view_from_context(view)
    model = compose_surface_model(
        slim,
        "l4_checked_action_surface",
    ).to_dict()
    surfaced_intents = {
        action["intent"] for action in model.get("actions", [])
    }
    # This seq_cut goal exposes no call frontier (no call site, no `<@`, no call
    # action), so the call-frontier inspect handles are NOT offered — clicking
    # them would only return an empty "no call route" result. The old broad
    # goal_info base is hidden; tactic_forms still surface through the composer.
    assert "call_subgoals" not in surfaced_intents
    assert "call_site_options" not in surfaced_intents
    assert "goal_info" not in surfaced_intents


def test_first_instruction_head_is_syntactic_not_a_buried_call() -> None:
    # Panel-audit root cause (2026-06-05): on an eager/reorder frontier the analyzer
    # flattens the loop, so the rows are "setup" (the top-level prefix) then a "call
    # frontier" whose call is actually buried inside the loop body. The first-
    # instruction head must read the SYNTACTIC first statement (the setup head), not
    # that buried call — reporting "call" made the panel claim "both_sides_at_call"
    # and steer toward a call tactic that can never fire at a `while`/assignment head.
    rows = [
        {"role": "setup / initialization",
         "left": "2 setup statement(s): k <- 0; m <- nth witness l k",
         "right": "2 setup statement(s): k <- 0; m <- nth witness l i"},
        {"role": "call frontier", "left": "y <@ H.f(m)", "right": "y <@ H.f(m)"},
    ]
    fia = _first_instruction_alignment(rows)
    assert fia["left_head"] == "assignment" and fia["right_head"] == "assignment"
    assert fia["left_first"] == "k <- 0"
    assert fia["branch_alignment"] == "both_sides_at_assignment"
    assert "call" not in fia["branch_alignment"]            # NOT the buried call

    # a genuine call frontier with no leading setup still reads as a call
    rows2 = [{"role": "call frontier", "left": "y <@ O.f(x)", "right": "y <@ O.f(x)"}]
    assert _first_instruction_alignment(rows2)["left_head"] == "call"


def test_leading_statement_extracts_syntactic_head() -> None:
    assert _leading_statement("2 setup statement(s): k <- 0; m <- nth l k") == "k <- 0"
    assert _leading_statement("y <@ H.f(m)") == "y <@ H.f(m)"
    # a structural head spans a block — keep it whole (do not split on inner `;`)
    assert _leading_statement("while (k < n) { a; b }").startswith("while")


def test_seq_tactic_forms_are_isolated_by_proof_mode() -> None:
    # PBound audit (2026-06-05): a bd-hoare goal must expose the phoare 4-bound
    # layout, while pRHL-only syntax must not leak across the mode boundary.
    from core.easycrypt.search.ec_tactic_forms import get_forms, format_forms  # type: ignore
    seq = get_forms("seq")
    ph = format_forms(seq, mode="phoare")
    pr = format_forms(seq, mode="pRHL")
    assert "seq N : (R) P1 P2 P3 P4" in ph
    assert "seq K L : (INVARIANT)" not in ph
    assert "seq K L : (INVARIANT)" in pr
    assert "seq N : (R) P1 P2 P3 P4" not in pr


def test_statement_head_treats_no_frontier_placeholder_as_no_head() -> None:
    # regression-audit MINOR (2026-06-05): a one-sided frontier whose absent side is
    # the placeholder "no left-side setup before this frontier" must read as a no-head
    # (-> one-sided_frontier), not a `statement` head (-> frontier_heads_differ).
    from core.easycrypt.session_prover_workspace_view import _statement_head, _first_instruction_alignment  # type: ignore
    assert _statement_head("no left-side setup before this frontier") == ""
    rows = [{"role": "call frontier",
             "left": "no left-side setup before this frontier", "right": "x <$ d"}]
    assert _first_instruction_alignment(rows)["branch_alignment"] == "one-sided_frontier"
