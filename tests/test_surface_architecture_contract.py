import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_cards_consume_surface_turn_without_raw_workspace_inference() -> None:
    source = (ROOT / "playground/static/index.html").read_text()

    assert "renderSurfaceTurn(" in source
    assert "surface_turn.proof_surface" in source
    for legacy_marker in (
        "candidate_moves",
        "decision_context",
        "inspect_lookup_handles",
        "renderFollowupCards",
        "ephemeralResponse",
        "pendingMenuIntent",
    ):
        assert legacy_marker not in source


def test_web_read_only_drawer_renders_only_the_typed_overlay_panel() -> None:
    source = (ROOT / "playground/static/index.html").read_text()
    drawer = source.split("function renderReadOnlyInline(turn){", 1)[1].split(
        "function renderSurfaceTurn(turn){", 1
    )[0]

    assert "renderSurfacePanel(panel)" in drawer
    assert "renderSurfaceCards(overlay)" not in drawer
    assert "overlay.status" not in drawer


def test_agent_and_playground_share_the_surface_turn_renderer() -> None:
    runtime = (ROOT / "workflow/proof_node_runtime.py").read_text()
    playground = (ROOT / "playground/node_boot.py").read_text()

    for source in (runtime, playground):
        assert "compose_surface_turn" in source
        assert "render_surface_turn_markdown" in source


def test_core_does_not_import_presentation_workflow() -> None:
    offenders: list[str] = []
    for path in (ROOT / "core").rglob("*.py"):
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        imports_workflow = any(
            (
                isinstance(node, ast.ImportFrom)
                and str(node.module or "").split(".", 1)[0] == "workflow"
            )
            or (
                isinstance(node, ast.Import)
                and any(alias.name.split(".", 1)[0] == "workflow" for alias in node.names)
            )
            for node in ast.walk(tree)
        )
        if imports_workflow:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_tactic_reference_taxonomy_has_one_owner() -> None:
    owner = (ROOT / "workflow/surface_tactic_forms.py").read_text()
    eligibility = (ROOT / "workflow/surface_action_eligibility.py").read_text()

    assert "def eligible_tactic_form_names(" in owner
    assert "REFERENCE_WORTHY_TACTIC_FORMS" not in owner
    assert "def surface_tactic_form_names(" not in owner
    assert "def _supplemental_tactic_form_names(" not in owner
    assert "eligible_tactic_form_names" in eligibility
    assert "def _project_reference_action(" not in eligibility


def test_tactic_references_do_not_advertise_retired_backend_interfaces() -> None:
    source = (ROOT / "core/easycrypt/search/ec_tactic_forms.py").read_text()

    for retired in ("lemma_index", "-sig", "-tactic-forms"):
        assert retired not in source


def test_pure_tail_does_not_own_exact_loaded_conclusion_matching() -> None:
    lemma_index = (ROOT / "core/easycrypt/analysis/ec_lemma_index.py").read_text()
    pure_tail = (
        ROOT / "workflow/proof_management/analyzers/pure_tail.py"
    ).read_text()

    assert "def mechanical_goal_candidates(" in lemma_index
    assert "def _conclusion_lemma_routes(" not in pure_tail
    assert "def _local_lemma_declarations(" not in pure_tail


def test_normal_surface_path_uses_direct_typed_intents() -> None:
    producers = (
        ROOT / "core/easycrypt/session_prover_workspace_view.py",
        ROOT / "core/easycrypt/analysis/probability_budget.py",
        ROOT / "workflow/proof_management/analyzers/route_health.py",
    )
    for path in producers:
        assert '"intent": "inspect_context"' not in path.read_text()

    presentation = (
        ROOT / "workflow/surface_profiles.py",
        ROOT / "workflow/surface_composer.py",
        ROOT / "workflow/surface_action_preflight.py",
    )
    for path in presentation:
        assert "direct_context_request" not in path.read_text()

    workspace_manager = (
        ROOT / "core/easycrypt/session_workspace_view_manager.py"
    ).read_text()
    assert "def _semantic_handle(" not in workspace_manager
    assert '"kind": kind' not in workspace_manager

    workspace_projection = (
        ROOT / "core/easycrypt/session_prover_workspace_view.py"
    ).read_text()
    assert "def _inspect_topic_from_context_handle(" not in workspace_projection
    dedupe = workspace_projection.split(
        "def _dedupe_manager_handles(", 1
    )[1].split("def _phase_panel(", 1)[0]
    assert 'payload["topic"]' not in dedupe


def test_structural_panels_read_typed_facts_not_candidate_prose() -> None:
    source = (ROOT / "workflow/surface_structural_facts.py").read_text()

    assert "candidate_moves" not in source
    assert "re.compile" not in source
    assert "checked_structural_sources" in source
    assert "application_context" in source


def test_state_eligibility_has_one_owner() -> None:
    producer = (ROOT / "core/easycrypt/session_prover_workspace_view.py").read_text()

    for legacy_gate in (
        "_CALL_FRONTIER_TOPICS",
        "_PR_BRIDGE_TOPICS",
        "_goal_is_pr_bridge_candidate",
        "_goal_has_live_bridge_target",
        "offer_call_frontier",
        "offer_pr_bridge",
        "offer_equiv_bridge",
        "offer_program_surgery",
    ):
        assert legacy_gate not in producer
    roster = producer.split("def _prhl_surgery_tactic_handles(", 1)[1].split(
        "def _manager_handle(", 1
    )[0]
    assert "goal_text" not in roster

    manager = (ROOT / "workflow/proof_node_manager.py").read_text()
    assert "preflight_candidate_state_eligibility" in manager

    composer = (ROOT / "workflow/surface_composer.py").read_text()
    assert "def _call_context_preflight_eligible(" not in composer
    assert "has_displayable_call_surface" in composer


def test_structural_fact_provenance_uses_typed_sources() -> None:
    panels = (ROOT / "workflow/surface_panels.py").read_text()
    structural = (ROOT / "workflow/surface_structural_facts.py").read_text()

    assert 'source_refs=("program_frontier", "candidate_moves")' not in panels
    assert "candidate_moves" not in structural
    assert "re.compile" not in structural


def test_web_action_grouping_uses_typed_intent_class_only() -> None:
    source = (ROOT / "playground/static/index.html").read_text()
    function = source.split("function intentClassOf(a){", 1)[1].split(
        "function intentClassLabel", 1
    )[0]

    assert "a.intent_class" in function
    assert "a.intent===" not in function
    assert "includes(a.intent)" not in function


def test_web_ready_proof_actions_use_the_surface_action_label() -> None:
    source = (ROOT / "playground/static/index.html").read_text()
    function = source.split("function askTopic(a){", 1)[1].split(
        "function surfaceGoalHtml", 1
    )[0]

    assert "a.read_only===false && a.label" in function
    assert "return a.label" in function


def test_preflighted_executable_routes_do_not_recover_legacy_candidate_prose() -> None:
    preflight = (ROOT / "workflow/surface_action_preflight.py").read_text()
    composer = (ROOT / "workflow/surface_composer.py").read_text()
    eligibility = (ROOT / "workflow/surface_action_eligibility.py").read_text()

    assert "def preflight_candidate_evidence(" in preflight
    assert "def matching_preflight_submission(" in preflight
    assert "candidate_moves" not in composer
    assert "candidate_moves" not in eligibility
