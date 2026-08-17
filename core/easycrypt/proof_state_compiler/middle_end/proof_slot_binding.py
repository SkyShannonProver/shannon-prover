"""Shared matching of named facts to instantiated proof slots."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.proof_ir import (
    ApplicationSignature,
    ProofFact,
    ProofJudgment,
)
from core.easycrypt.proof_state_compiler.syntax.formulas import (
    normalize_formula,
    parse_proof_judgment,
)


@dataclass(frozen=True)
class ProofSlotMatches:
    resolved_values: tuple[tuple[str, str], ...] = ()
    matched_facts: tuple[ProofFact, ...] = ()

    def as_dict(self) -> dict[str, str]:
        return dict(self.resolved_values)

    @property
    def evidence_refs(self) -> tuple[EvidenceRef, ...]:
        return tuple(dict.fromkeys(
            evidence
            for fact in self.matched_facts
            for evidence in fact.evidence_refs
        ))


def bind_available_proof_slots(
    signature: ApplicationSignature,
    *,
    instantiated_expectations: dict[str, str],
    facts: tuple[ProofFact, ...],
) -> ProofSlotMatches:
    """Resolve only unique, structurally compatible named proof facts.

    This is candidate construction, not a verifier claim.  Source-declaration
    facts remain lexical candidates and every resulting action still requires
    exact-state EasyCrypt preflight.
    """

    resolved: list[tuple[str, str]] = []
    matched: list[ProofFact] = []
    for slot in signature.slots:
        if slot.kind != "proof":
            continue
        expected = instantiated_expectations.get(slot.slot_id, slot.expected)
        expected_judgment = parse_proof_judgment(expected)
        ranked = [
            (_fact_score(expected_judgment, fact), fact)
            for fact in facts
        ]
        ranked = [(score, fact) for score, fact in ranked if score > 0]
        if not ranked:
            continue
        best = max(score for score, _ in ranked)
        best_facts = [fact for score, fact in ranked if score == best]
        distinct = {
            (fact.name, normalize_formula(fact.judgment.text)): fact
            for fact in best_facts
        }
        if len(distinct) != 1:
            continue
        fact = next(iter(distinct.values()))
        resolved.append((slot.slot_id, fact.name))
        matched.append(fact)
    return ProofSlotMatches(tuple(resolved), tuple(matched))


def _fact_score(expected: ProofJudgment, fact: ProofFact) -> int:
    observed = fact.judgment
    origin = 200 if fact.origin == "current_context" else 100
    if normalize_formula(expected.text) == normalize_formula(observed.text):
        return origin + 40
    if (
        expected.kind in {"equiv", "hoare", "phoare", "lossless"}
        and expected.kind == observed.kind
        and expected.subject
        and normalize_formula(expected.subject)
        == normalize_formula(observed.subject)
    ):
        return origin + 20
    return 0
