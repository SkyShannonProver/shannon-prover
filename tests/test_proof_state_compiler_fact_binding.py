"""Shared fact IR and proof-slot binding contracts."""

from core.easycrypt.proof_state_compiler.contracts import (
    ApplicationSignature,
    ArgumentSlot,
    EvidenceRef,
    ProofFact,
)
from core.easycrypt.proof_state_compiler.middle_end.proof_slot_binding import (
    bind_available_proof_slots,
)
from core.easycrypt.proof_state_compiler.syntax.formulas import (
    parse_proof_judgment,
    parse_top_level_relation,
)


def _evidence(identity: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=identity,
        source_kind="fixture",
        source_ref=identity,
        source_sha256=(identity[0] if identity else "a") * 64,
    )


def _fact(name: str, formula: str, origin: str, marker: str) -> ProofFact:
    evidence = _evidence(marker)
    return ProofFact(
        fact_id=f"fact:{name}:{marker}",
        name=name,
        judgment=parse_proof_judgment(formula),
        origin=origin,
        evidence_refs=(evidence,),
    )


def _signature() -> ApplicationSignature:
    evidence = _evidence("a")
    return ApplicationSignature(
        resource_id="resource:T",
        slots=(ArgumentSlot(
            slot_id="proof:1",
            name="premise_1",
            kind="proof",
            binding_mode="deferred_obligation",
            expected="hoare[ M.f : true ==> true ]",
            explicit=True,
            evidence_refs=(evidence,),
        ),),
        evidence_refs=(evidence,),
    )


def test_top_level_relation_ignores_probability_event_internals() -> None:
    relation = parse_top_level_relation(
        "Pr[G.main() @ &m : x = y] <= Pr[H.main() @ &m : res] + 1%r"
    )
    assert relation is not None
    assert relation.operator == "<="
    assert relation.left == "Pr[G.main() @ &m : x = y]"


def test_top_level_relation_does_not_misread_implication_or_module_bound() -> None:
    assert parse_top_level_relation("P => Q") is None
    assert parse_top_level_relation("P ==> Q") is None
    assert parse_top_level_relation("M <: T") is None


def test_current_context_fact_wins_over_lexical_source_candidate() -> None:
    facts = (
        _fact(
            "source_fact",
            "hoare[ M.f : true ==> true ]",
            "source_declaration",
            "b",
        ),
        _fact(
            "Hlocal",
            "hoare[ M.f : P ==> Q ]",
            "current_context",
            "c",
        ),
    )

    matches = bind_available_proof_slots(
        _signature(),
        instantiated_expectations={},
        facts=facts,
    )

    assert matches.as_dict() == {"proof:1": "Hlocal"}


def test_equal_strength_fact_ambiguity_remains_unresolved() -> None:
    facts = (
        _fact(
            "H1",
            "hoare[ M.f : true ==> true ]",
            "current_context",
            "d",
        ),
        _fact(
            "H2",
            "hoare[ M.f : true ==> true ]",
            "current_context",
            "e",
        ),
    )

    matches = bind_available_proof_slots(
        _signature(),
        instantiated_expectations={},
        facts=facts,
    )

    assert matches.resolved_values == ()

def test_conflicting_same_name_fact_ambiguity_remains_unresolved() -> None:
    facts = (
        _fact(
            "H",
            "hoare[ M.f : P ==> Q ]",
            "current_context",
            "d",
        ),
        _fact(
            "H",
            "hoare[ M.f : R ==> S ]",
            "current_context",
            "e",
        ),
    )

    matches = bind_available_proof_slots(
        _signature(),
        instantiated_expectations={},
        facts=facts,
    )

    assert matches.resolved_values == ()
