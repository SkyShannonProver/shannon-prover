"""Parse losslessness declarations into shared proof-resource IR."""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.contracts import (
    ApplicationSignature,
    ArgumentSlot,
    ProofJudgment,
    ProofResource,
)
from core.easycrypt.proof_state_compiler.frontend.declaration_stream import (
    DeclarationInput,
)
from core.easycrypt.proof_state_compiler.frontend.resource_syntax import (
    consume_leading_forall_module_parameters,
    module_parameter_specs,
    split_top_level_implications,
    top_level_colon,
)
from core.easycrypt.proof_state_compiler.syntax.module_terms import (
    ModuleTermParseError,
    parse_procedure_term,
)


def parse_losslessness_declaration(
    item: DeclarationInput,
) -> ProofResource | None:
    """Return one lexical certificate sketch, or abstain on another shape.

    Native EasyCrypt elaboration/preflight remains the semantic authority for
    every argument and application.
    """

    symbol = item.symbol
    declaration = item.declaration
    evidence = item.evidence
    colon = top_level_colon(declaration)
    if colon < 0:
        return None
    header = declaration[:colon]
    proposition = declaration[colon + 1:].strip()
    if proposition.endswith("."):
        proposition = proposition[:-1].rstrip()
    required_modules = module_parameter_specs(header)
    normalized = consume_leading_forall_module_parameters(proposition)
    if normalized is None:
        return None
    normalized_modules, proposition = normalized
    required_modules += normalized_modules
    module_names = tuple(name for name, _restriction in required_modules)
    if len(module_names) != len(set(module_names)):
        return None
    clauses = split_top_level_implications(proposition)
    if len(clauses) < 2:
        return None
    procedures = [_lossless_procedure(clause) for clause in clauses]
    if any(not procedure for procedure in procedures):
        return None
    try:
        for procedure in procedures:
            parse_procedure_term(procedure)
    except ModuleTermParseError:
        return None

    resource_id = f"{symbol}@{evidence.source_ref}"
    slots = tuple(
        ArgumentSlot(
            slot_id=f"module:{name}",
            name=name,
            kind="module",
            binding_mode="required",
            expected=f"{name} <: {restriction}",
            explicit=True,
            evidence_refs=(evidence,),
        )
        for name, restriction in required_modules
    ) + tuple(
        ArgumentSlot(
            slot_id=f"proof:{index}",
            name=f"premise_{index}",
            kind="proof",
            binding_mode="deferred_obligation",
            expected=f"islossless {procedure}",
            explicit=True,
            evidence_refs=(evidence,),
        )
        for index, procedure in enumerate(procedures[:-1], start=1)
    )
    return ProofResource(
        resource_id=resource_id,
        symbol=symbol,
        resource_kind="procedure_certificate",
        declaration=declaration,
        application_signature=ApplicationSignature(
            resource_id=resource_id,
            slots=slots,
            evidence_refs=(evidence,),
        ),
        premises=tuple(
            ProofJudgment(
                kind="lossless",
                text=f"islossless {procedure}",
                procedure=procedure,
            )
            for procedure in procedures[:-1]
        ),
        conclusion=ProofJudgment(
            kind="lossless",
            text=f"islossless {procedures[-1]}",
            procedure=procedures[-1],
        ),
        evidence_refs=(evidence,),
    )


def _lossless_procedure(clause: str) -> str:
    value = clause.strip()
    while value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    match = re.fullmatch(r"islossless\s+(.+)", value)
    return match.group(1).strip() if match else ""
