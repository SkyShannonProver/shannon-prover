"""Compiler-profile registry projection and manager-facing service factory."""

from __future__ import annotations

from typing import Any

from core.easycrypt.proof_state_compiler.features.catalog import (
    production_feature_catalog,
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
    PRODUCTION_COMPILER_PROFILES as COMPILER_PROFILES,  # noqa: F401  (public name)
    PRODUCTION_PROFILE_IDS,
    runtime_profile_registration,
)


def compiler_assembly_for_profile(profile: str | None) -> CompilerAssembly | None:
    """Resolve one known compiler profile without feature-specific branches."""

    normalized = str(profile or "")
    try:
        registration = runtime_profile_registration(normalized)
    except ValueError:
        return None
    specification = registration.compiler_profile
    if registration.profile_id in PRODUCTION_PROFILE_IDS:
        feature_catalog = production_feature_catalog()
    else:
        from workflow.proof_state_compiler.research.proof_state_compiler_research_feature_catalog import (
            research_feature_catalog,
        )

        feature_catalog = research_feature_catalog()
    assembly = assemble_compiler_profile(
        specification,
        feature_catalog,
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
