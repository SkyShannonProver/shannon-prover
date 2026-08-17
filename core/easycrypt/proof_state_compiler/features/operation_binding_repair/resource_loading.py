"""Bounded exact declaration dependency for the attempted resource."""

from __future__ import annotations

import hashlib

from core.easycrypt.proof_state_compiler.contracts import (
    CompilationEnvironment,
    CompilerInvocationContext,
    DeclarationLoadRequest,
    ProjectedProofState,
    ProofIR,
)


OPERATION_BINDING_REPAIR_LOAD_PRODUCER_ID = (
    "operation_binding_repair.declaration_dependency"
)


def request_attempted_resource_declaration(
    _state: ProjectedProofState,
    _environment: CompilationEnvironment,
    base_ir: ProofIR,
    _invocation: CompilerInvocationContext,
) -> tuple[DeclarationLoadRequest, ...]:
    attempted = base_ir.attempted_operation
    if attempted is None or not attempted.resource:
        return ()
    symbols = tuple(dict.fromkeys((
        attempted.resource,
        attempted.resource_basename,
    )))
    digest = hashlib.sha256(
        (
            OPERATION_BINDING_REPAIR_LOAD_PRODUCER_ID
            + "\0symbol_declarations\0"
            + "|".join(symbols)
        ).encode("utf-8")
    ).hexdigest()[:20]
    return (DeclarationLoadRequest(
        request_id=f"attempted-resource:{digest}",
        producer_id=OPERATION_BINDING_REPAIR_LOAD_PRODUCER_ID,
        query_kind="symbol_declarations",
        scope="",
        declaration_kinds=("lemma", "axiom"),
        member_name_terms=(),
        max_results=len(symbols),
        evidence_refs=attempted.evidence_refs,
        symbols=symbols,
    ),)
