"""Discover only declarations preserving the attempted resource identity."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    ApplicationSignature,
    CompilationEnvironment,
    CompilerInvocationContext,
    ProofIR,
    ProofJudgment,
    ProofResource,
    ProjectedProofState,
)
from core.easycrypt.proof_state_compiler.frontend.declaration_stream import (
    declaration_inputs,
)
from core.easycrypt.proof_state_compiler.frontend.losslessness_declaration import (
    parse_losslessness_declaration,
)
from core.easycrypt.proof_state_compiler.frontend.probability_theorem_declaration import (
    parse_probability_theorem_declaration,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.classification import (
    classify_operation_binding_failure,
)


def discover_attempted_operation_resources(
    _state: ProjectedProofState,
    environment: CompilationEnvironment,
    base_ir: ProofIR,
    _invocation: CompilerInvocationContext,
) -> tuple[ProofResource, ...]:
    attempted = base_ir.attempted_operation
    if attempted is None:
        return ()
    failure_class = classify_operation_binding_failure(attempted)
    if failure_class is None:
        return ()
    values: list[ProofResource] = []
    semantic_indices: dict[tuple, int] = {}
    seen_declarations: set[tuple[str, str]] = set()
    inputs = declaration_inputs(environment)
    native_symbols = {
        item.symbol
        for item in inputs
        if item.evidence.source_kind == "loaded_declaration"
    }
    for item in inputs:
        if failure_class == "B1":
            if item.symbol.rsplit(".", 1)[-1] != attempted.resource_basename:
                continue
        elif item.symbol != attempted.resource:
            continue
        # The verifier-resolved declaration owns an exact symbol.  A source
        # sketch of that symbol may differ only because EasyCrypt normalized
        # module restrictions or other printed syntax.  Keeping both would
        # create false ambiguity; if the native declaration cannot be parsed,
        # fail closed instead of falling back to source text.
        if (
            item.symbol in native_symbols
            and item.evidence.source_kind != "loaded_declaration"
        ):
            continue
        declaration_key = (item.symbol, " ".join(item.declaration.split()))
        if declaration_key in seen_declarations:
            continue
        seen_declarations.add(declaration_key)
        resource = (
            parse_probability_theorem_declaration(item)
            or parse_losslessness_declaration(item)
        )
        if resource is None:
            resource_id = f"{item.symbol}@{item.evidence.source_ref}"
            resource = ProofResource(
                resource_id=resource_id,
                symbol=item.symbol,
                resource_kind="declaration",
                declaration=item.declaration,
                application_signature=ApplicationSignature(
                    resource_id=resource_id,
                    slots=(),
                    evidence_refs=(item.evidence,),
                ),
                premises=(),
                conclusion=ProofJudgment(
                    kind="declaration",
                    text=item.declaration,
                    subject=item.symbol,
                ),
                evidence_refs=(item.evidence,),
            )
        semantic_key = _typed_resource_key(resource)
        previous = semantic_indices.get(semantic_key)
        if previous is None:
            semantic_indices[semantic_key] = len(values)
            values.append(resource)
        elif (
            item.evidence.source_kind == "loaded_declaration"
            and all(
                evidence.source_kind != "loaded_declaration"
                for evidence in values[previous].evidence_refs
            )
        ):
            values[previous] = resource
    return tuple(values)


def _typed_resource_key(resource: ProofResource) -> tuple:
    return (
        resource.symbol,
        resource.resource_kind,
        tuple(
            (slot.name, slot.kind, slot.binding_mode, slot.expected, slot.explicit)
            for slot in resource.application_signature.slots
        ),
        tuple(
            (item.kind, item.text, item.subject, item.procedure)
            for item in resource.premises
        ),
        (
            resource.conclusion.kind,
            resource.conclusion.text,
            resource.conclusion.subject,
            resource.conclusion.procedure,
        ),
    )
