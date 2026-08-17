"""P1-P2 frontend: authoritative projection and shared ProofIR assembly."""

from core.easycrypt.proof_state_compiler.frontend.proof_ir_builder import (
    build_proof_ir,
)
from core.easycrypt.proof_state_compiler.frontend.declaration_stream import (
    DeclarationInput,
    declaration_inputs,
)
from core.easycrypt.proof_state_compiler.frontend.resource_discovery import (
    ResourceDiscoverer,
)
from core.easycrypt.proof_state_compiler.frontend.resource_loading import (
    ResourceLoadRequestProducer,
    plan_resource_loads,
)
from core.easycrypt.proof_state_compiler.frontend.state_projector import (
    AuthoritativeSnapshotInput,
    RuntimeSnapshotInput,
    project_authoritative_state,
)
from core.easycrypt.proof_state_compiler.frontend.attempted_operation import (
    parse_attempted_operation,
)

__all__ = [
    "AuthoritativeSnapshotInput",
    "RuntimeSnapshotInput",
    "DeclarationInput",
    "ResourceDiscoverer",
    "ResourceLoadRequestProducer",
    "build_proof_ir",
    "declaration_inputs",
    "project_authoritative_state",
    "plan_resource_loads",
    "parse_attempted_operation",
]
