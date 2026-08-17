"""P2 dependency-discovery protocol for verifier-resolved declarations."""

from __future__ import annotations

from typing import Protocol

from core.easycrypt.proof_state_compiler.contracts.environment import (
    CompilationEnvironment,
    DeclarationLoadRequest,
    ResourceLoadPlan,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    CompilerInvocationContext,
)
from core.easycrypt.proof_state_compiler.contracts.projected_state import (
    ProjectedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import ProofIR


class ResourceLoadRequestProducer(Protocol):
    def __call__(
        self,
        state: ProjectedProofState,
        environment: CompilationEnvironment,
        base_ir: ProofIR,
        invocation: CompilerInvocationContext,
    ) -> tuple[DeclarationLoadRequest, ...]: ...


def plan_resource_loads(
    state: ProjectedProofState,
    environment: CompilationEnvironment,
    base_ir: ProofIR,
    producers: tuple[ResourceLoadRequestProducer, ...],
    invocation: CompilerInvocationContext,
) -> ResourceLoadPlan:
    requests = tuple(
        request
        for producer in producers
        for request in producer(state, environment, base_ir, invocation)
    )
    return ResourceLoadPlan(state_ref=state.state_ref, requests=requests)
