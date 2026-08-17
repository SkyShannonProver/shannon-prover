"""Compiler-profile registry projection and manager-facing service factory."""

from __future__ import annotations

from typing import Any

from core.easycrypt.proof_state_compiler.features.catalog import (
    default_feature_catalog,
)
from workflow.proof_state_compiler.assembly import (
    CompilerAssembly,
    assemble_compiler_profile,
)
from workflow.proof_state_compiler.service import ProofStateCompilerService
from workflow.proof_state_compiler.delivery_policies import (
    default_delivery_policy_catalog,
)
from workflow.proof_state_compiler.profile_registry import (
    CURRENT_COMPILER_PROFILES as COMPILER_PROFILES,
)


def compiler_assembly_for_profile(profile: str | None) -> CompilerAssembly | None:
    """Resolve one known compiler profile without feature-specific branches."""

    specification = COMPILER_PROFILES.get(str(profile or ""))
    if specification is None:
        # Most surface profiles do not opt into the proof-state compiler.
        return None
    assembly = assemble_compiler_profile(
        specification,
        default_feature_catalog(),
        default_delivery_policy_catalog(),
    )
    return assembly if assembly.activation_plan.compiler_enabled else None


def compiler_service_for_profile(
    profile: str | None,
    runtime: Any,
) -> ProofStateCompilerService | None:
    """Assemble a service without leaking feature choices into the manager."""

    assembly = compiler_assembly_for_profile(profile)
    if assembly is None:
        return None
    return ProofStateCompilerService.create(
        runtime=runtime,
        assembly=assembly,
    )
