"""Discover losslessness declarations through the shared frontend parser."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    CompilationEnvironment,
    CompilerInvocationContext,
    ProofIR,
    ProofResource,
    ProjectedProofState,
)
from core.easycrypt.proof_state_compiler.frontend.declaration_stream import (
    declaration_inputs,
)
from core.easycrypt.proof_state_compiler.frontend.losslessness_declaration import (
    parse_losslessness_declaration,
)


def discover_losslessness_resources(
    _state: ProjectedProofState,
    environment: CompilationEnvironment,
    _base_ir: ProofIR,
    _invocation: CompilerInvocationContext,
) -> tuple[ProofResource, ...]:
    return tuple(
        resource
        for item in declaration_inputs(environment)
        for resource in (parse_losslessness_declaration(item),)
        if resource is not None
    )
