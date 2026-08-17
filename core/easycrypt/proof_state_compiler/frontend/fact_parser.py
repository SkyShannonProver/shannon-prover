"""Build source-declaration facts until native global lookup replaces it."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts.environment import (
    CompilationEnvironment,
)
from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.proof_ir import ProofFact
from core.easycrypt.proof_state_compiler.frontend.declaration_stream import (
    declaration_inputs,
)
from core.easycrypt.proof_state_compiler.syntax.formulas import (
    normalize_formula,
    parse_proof_judgment,
)
from core.easycrypt.proof_state_compiler.frontend.resource_syntax import (
    top_level_colon,
)


def parse_source_declaration_facts(
    environment: CompilationEnvironment,
) -> tuple[ProofFact, ...]:
    facts = list(_source_declaration_facts(environment))
    # Source files can contain repeated section-local declarations with the
    # same printable name and proposition.  They denote one candidate term for
    # proof-slot binding; conflicting propositions remain separate.
    deduplicated: dict[tuple[str, str, str], ProofFact] = {}
    for fact in facts:
        key = (fact.origin, fact.name, normalize_formula(fact.judgment.text))
        deduplicated.setdefault(key, fact)
    return tuple(deduplicated.values())


def _source_declaration_facts(
    environment: CompilationEnvironment,
) -> tuple[ProofFact, ...]:
    values = []
    for item in declaration_inputs(environment):
        colon = top_level_colon(item.declaration)
        if colon < 0:
            continue
        proposition = normalize_formula(
            item.declaration[colon + 1:].rstrip(".").strip()
        )
        if proposition:
            values.append(_fact(
                item.symbol,
                proposition,
                "source_declaration",
                item.evidence,
            ))
    return tuple(values)


def _fact(
    name: str,
    proposition: str,
    origin: str,
    evidence: EvidenceRef,
) -> ProofFact:
    digest = hashlib.sha256(
        f"{origin}\0{name}\0{normalize_formula(proposition)}\0"
        f"{evidence.source_sha256}".encode()
    ).hexdigest()[:20]
    return ProofFact(
        fact_id=f"proof-fact:{digest}",
        name=name,
        judgment=parse_proof_judgment(proposition),
        origin=origin,
        evidence_refs=(evidence,),
    )
