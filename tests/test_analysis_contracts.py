"""Tests for analysis compiler contract documentation."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "core" / "easycrypt" / "analysis" / "CONTRACTS.md"
README = ROOT / "core" / "easycrypt" / "analysis" / "README.md"
SCHEMAS = ROOT / "core" / "easycrypt" / "analysis" / "SCHEMAS.md"
EXTENDING = ROOT / "core" / "easycrypt" / "analysis" / "EXTENDING.md"
LEMMA_AUTHORING = ROOT / "core" / "easycrypt" / "analysis" / "LEMMA_AUTHORING.md"
TESTING = ROOT / "TESTING.md"


def test_analysis_contracts_document_core_layer_boundaries() -> None:
    text = CONTRACTS.read_text(encoding="utf-8")

    for heading in [
        "## Raw Goal Frontend",
        "## Canonical Frontends",
        "## Resource And Symbol Layer",
        "## Middle-End Planners",
        "## Native Search Bridge",
        "## Action Rendering Layer",
        "## ProofIR Facade",
        "## Backend And Tool Boundary",
        "## Stable Fact Shapes",
    ]:
        assert heading in text

    required_modules = [
        "session_projection.py",
        "ec_goal_parser.py",
        "ec_native_state.py",
        "ec_pr_canonical.py",
        "ec_program_ir.py",
        "ec_lemma_index.py",
        "ec_name_resolution.py",
        "ec_pr_obligations.py",
        "ec_pr_path_planner.py",
        "ec_pr_bridge_frontend.py",
        "ec_native_ast_search.py",
        "ec_action_contracts.py",
        "ec_equiv_closers.py",
        "ec_pr_actions.py",
        "ec_procedure_actions.py",
        "ec_proof_ir.py",
        "session_cli.py",
    ]
    for module in required_modules:
        assert module in text


def test_analysis_contracts_pin_negative_obligations() -> None:
    text = CONTRACTS.read_text(encoding="utf-8")

    for phrase in [
        "choose project lemmas",
        "select a project-local lemma name",
        "require lemma names to begin with",
        "turn a search hit directly into `apply` or `rewrite`",
        "discover new semantic facts",
        "become the home for new parser/resource/action logic",
        "accept `admit.`",
        "treat `-goal-json` / `-program-json` adapter artifacts as EC-native",
    ]:
        assert phrase in text


def test_analysis_readme_links_contracts() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "[`CONTRACTS.md`](CONTRACTS.md)" in readme
    assert "[`SCHEMAS.md`](SCHEMAS.md)" in readme
    assert "[`EXTENDING.md`](EXTENDING.md)" in readme
    assert "[`LEMMA_AUTHORING.md`](LEMMA_AUTHORING.md)" in readme


def test_extending_guide_points_future_agents_to_passes() -> None:
    text = EXTENDING.read_text(encoding="utf-8")
    contracts = CONTRACTS.read_text(encoding="utf-8")

    assert "Do Not Add To ProofIR Unless" in text
    for phrase in [
        "canonical frontend",
        "resource/symbol pass",
        "planner/obligation pass",
        "action renderer",
        "ProofIR facade",
    ]:
        assert phrase in text
    assert "EXTENDING.md" in contracts


def test_testing_guide_links_contracts_from_smoke_matrix() -> None:
    testing = TESTING.read_text(encoding="utf-8")

    assert "core/easycrypt/analysis/CONTRACTS.md" in testing
    assert "core/easycrypt/analysis/SCHEMAS.md" in testing
    assert "core/easycrypt/analysis/LEMMA_AUTHORING.md" in testing


def test_schema_inventory_names_core_fact_shapes() -> None:
    text = SCHEMAS.read_text(encoding="utf-8")

    for heading in [
        "## `GoalStateFact`",
        "## `PrTerm`",
        "## `ProgramIR`",
        "## `SemanticLemmaCandidate`",
        "## `NameResolutionFact`",
        "## `InstantiationBinding`",
        "## `PrObligation`",
        "## `PrPathPlan`",
        "## `PrBridgeCandidate`",
        "## `EquivExactCloser`",
        "## `NativeSearchFact`",
        "## `ActionCandidate`",
        "## `ProofIR`",
    ]:
        assert heading in text

    for phrase in [
        "A fact that came from search or static analysis is evidence",
        "`inspection_action` must not mutate proof state",
        "`strategy_hint` may be non-tactic prose",
        "`probe_tactic` means probeable, not proven",
        "fallback or unresolved source/name facts must not become",
    ]:
        assert phrase in text


def test_lemma_authoring_rules_pin_supported_and_unsupported_shapes() -> None:
    text = LEMMA_AUTHORING.read_text(encoding="utf-8")

    for heading in [
        "## Pr Equality Rewrite Lemmas",
        "## Pr Inequality And Bound Lemmas",
        "## Additive And Union Bounds",
        "## Advantage And Arithmetic Chain Lemmas",
        "## Procedure Equivalence Lemmas",
        "## Module Parameters And Instantiation",
        "## Unsupported Or Weakly Supported Shapes",
    ]:
        assert heading in text

    for phrase in [
        "Names like `step2_1`,",
        "These are authoring rules, not naming rules",
        "Put the relevant `Pr[...]` terms in the theorem statement",
        "does not promise to recover resources hidden only inside an",
        "proof-local `have`",
    ]:
        assert phrase in text
