"""P4 backend: candidate lowering, admission, and final ActionSurface."""

from core.easycrypt.proof_state_compiler.backend.presentation import (
    RenderedCompilerMarkdown,
    action_surface_payload,
    render_action_surface,
    render_action_surface_payload,
)
from core.easycrypt.proof_state_compiler.backend.admission import (
    AdmissionManifest,
    AdmissionResult,
    admit_action_surface,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    CompilerTrigger,
    DeliveryRule,
)
from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
    SurfaceLowerer,
    build_candidate_surface,
)

__all__ = [
    "AdmissionManifest",
    "AdmissionResult",
    "CompilerTrigger",
    "DeliveryRule",
    "RenderedCompilerMarkdown",
    "SurfaceContribution",
    "SurfaceLowerer",
    "action_surface_payload",
    "admit_action_surface",
    "build_candidate_surface",
    "render_action_surface",
    "render_action_surface_payload",
]
