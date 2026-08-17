"""Authority/parity sentinels for the native P1 -> P2 frontend."""

from __future__ import annotations

from pathlib import Path

from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts import (
    TargetRef,
    TransitionRef,
    empty_compilation_environment,
)
from tests.proof_state_compiler_test_support import (
    instruction,
    native_state,
    program,
    typed_node,
)


ROOT = Path(__file__).resolve().parents[1]


def _state_ref() -> StateRef:
    return StateRef(
        session_id="native-frontend-test",
        state_version=3,
        goal_identity="native-frontend-goal",
        goal_identity_required=True,
        committed_prefix_identity="7" * 64,
    )


def _snapshot(lines: tuple[str, ...], native) -> AuthoritativeSnapshotInput:
    state_ref = _state_ref()
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="native.frontend.fixture",
            authority="compiler.input.produced",
            source_sha256="a" * 64,
            artifact_ref="compiler_inputs/native-frontend.json",
            source_event_id="native-frontend-input",
            source_event_sequence=3,
            authoritative=True,
        ),
        target=TargetRef("eval/native_frontend.ec", "native_frontend"),
        transition=TransitionRef(
            "inspected", state_ref, "compiler_inputs/native-frontend.json"
        ),
        goal_lines=lines,
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native,
    )


def _compile(lines: tuple[str, ...], native):
    return ProofStateCompiler().compile(
        _snapshot(lines, native),
        empty_compilation_environment(),
    )


def test_pretty_text_program_and_local_lookalikes_have_no_semantic_authority() -> None:
    state_ref = _state_ref()
    bundle = _compile(
        (
            "Hfake: islossless Fake.f",
            "(1) x <@ Fake.f();",
            "--------",
            "Pr[Fake.main() @ &m : res] <= 1%r",
        ),
        native_state(state_ref, formula=typed_node("true", "true")),
    )

    assert bundle.proof_ir.goal.kind == "formula"
    assert bundle.proof_ir.goal.formula == "true"
    assert bundle.proof_ir.statements == ()
    assert bundle.proof_ir.facts == ()
    assert bundle.analyzed_state.coordinate.status == "unknown"


def test_native_program_structure_drives_coordinate_when_text_has_no_program() -> None:
    state_ref = _state_ref()
    call = instruction(
        "call",
        "x <@ Real.f()",
        side="single",
        position=1,
        procedure="Top.Real./f",
    )
    bundle = _compile(
        ("Current goal", "--------", "true"),
        native_state(
            state_ref,
            judgment_kind="hoare_statement",
            formula=typed_node(
                "hoare_statement",
                "hoare[statement : true ==> true]",
                children=(typed_node("true", "true"),) * 2,
                child_roles=("precondition", "postcondition"),
            ),
            programs=(program("single", (call,)),),
        ),
    )

    statement = bundle.proof_ir.statements[0]
    assert statement.procedure == "Top.Real./f"
    assert statement.structural_path == ("single", "1")
    assert bundle.analyzed_state.coordinate.forward_frontier == statement


def test_exceptional_postcondition_retains_all_branches_in_typed_ir() -> None:
    state_ref = _state_ref()
    normal = typed_node("true", "true")
    exception = typed_node("equality", "x = 0")
    postcondition = typed_node(
        "exceptional_postcondition",
        "normal => true; exception Top.Error => x = 0",
        children=(normal, exception),
        child_roles=("normal_postcondition", "exception_postcondition"),
        exception_paths=["Top.Error"],
    )
    formula = typed_node(
        "hoare_statement",
        "hoare[statement : true ==> true raises Top.Error => x = 0]",
        children=(typed_node("true", "true"), postcondition),
        child_roles=("precondition", "postcondition"),
    )

    bundle = _compile(
        ("Current goal", "--------", formula["text"]),
        native_state(
            state_ref,
            judgment_kind="hoare_statement",
            formula=formula,
        ),
    )

    assert bundle.proof_ir.goal.postcondition == "true"
    retained = bundle.proof_ir.goal.formula_ir.children[1]
    assert retained.kind == "exceptional_postcondition"
    assert retained.children[1].text == "x = 0"
    assert tuple(retained.properties["exception_paths"]) == ("Top.Error",)


def test_native_probability_relation_is_structural_not_text_scanning() -> None:
    state_ref = _state_ref()
    left = typed_node("probability", "Pr[G.main() @ &m : res]", type_text="real")
    right = typed_node("operator_application", "1%r", type_text="real")
    bundle = _compile(
        ("Current goal", "--------", "text without a relation"),
        native_state(
            state_ref,
            formula=typed_node(
                "operator_application",
                "Pr[G.main() @ &m : res] <= 1%r",
                children=(left, right),
                operator="Top.RealOrder.le",
                relation_operator="<=",
            ),
        ),
    )

    assert bundle.proof_ir.goal.kind == "probability"
    assert bundle.proof_ir.goal.relation is not None
    assert bundle.proof_ir.goal.relation.operator == "<="
    assert bundle.proof_ir.goal.relation.left == left["text"]


def test_native_local_hypothesis_is_the_only_current_fact_source() -> None:
    state_ref = _state_ref()
    equality = typed_node(
        "equality",
        "x = 0",
        children=(
            typed_node("local", "x", type_text="int"),
            typed_node("integer", "0", type_text="int"),
        ),
    )
    bundle = _compile(
        ("Htext: false", "--------", "true"),
        native_state(
            state_ref,
            locals_value=(
                {"index": 0, "name": "Hnative", "kind": "hypothesis", "formula": equality},
                {"index": 1, "name": "x", "kind": "variable", "type": "int", "definition": None},
            ),
        ),
    )

    assert [fact.name for fact in bundle.proof_ir.facts] == ["Hnative"]
    fact = bundle.proof_ir.facts[0]
    assert fact.judgment.relation is not None
    assert fact.judgment.relation.operator == "="
    assert fact.evidence_refs[0].source_kind == "native_typed_state"


def test_incomplete_native_projection_abstains_without_text_fallback() -> None:
    bundle = _compile(
        (
            "Hfake: true",
            "(1) x <@ Fake.f();",
            "--------",
            "Pr[Fake.main() @ &m : res] <= 1%r",
        ),
        native_state(_state_ref(), complete=False),
    )

    assert bundle.proof_ir.goal.status == "unknown"
    assert bundle.proof_ir.statements == ()
    assert bundle.proof_ir.facts == ()
    assert bundle.candidate_surface.empty


def test_v2_pretty_text_semantic_parsers_are_deleted() -> None:
    frontend = ROOT / "core/easycrypt/proof_state_compiler/frontend"
    assert not (frontend / "goal_parser.py").exists()
    assert not (frontend / "program_parser.py").exists()
