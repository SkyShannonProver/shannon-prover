"""Shared resource-discovery protocol and deterministic aggregation."""

from __future__ import annotations

from typing import Protocol

from core.easycrypt.proof_state_compiler.contracts.environment import (
    CompilationEnvironment,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    CompilerInvocationContext,
)
from core.easycrypt.proof_state_compiler.contracts.projected_state import (
    ProjectedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import (
    ProofIR,
    ProofResource,
)


class ResourceDiscoverer(Protocol):
    def __call__(
        self,
        state: ProjectedProofState,
        environment: CompilationEnvironment,
        base_ir: ProofIR,
        invocation: CompilerInvocationContext,
    ) -> tuple[ProofResource, ...]: ...


def discover_resources(
    state: ProjectedProofState,
    environment: CompilationEnvironment,
    base_ir: ProofIR,
    discoverers: tuple[ResourceDiscoverer, ...],
    invocation: CompilerInvocationContext,
) -> tuple[ProofResource, ...]:
    resources = tuple(
        resource
        for discoverer in discoverers
        for resource in discoverer(state, environment, base_ir, invocation)
    )
    identities = [resource.resource_id for resource in resources]
    if len(identities) != len(set(identities)):
        raise ValueError("P2 resource discoverers produced duplicate resource IDs")
    return resources
