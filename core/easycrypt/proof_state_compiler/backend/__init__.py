"""P4 backend: candidate lowering, admission, and final ActionSurface."""

from core.easycrypt.proof_state_compiler.backend.presentation import (
    action_surface_payload,
    render_action_surface_payload,
)
from core.easycrypt.proof_state_compiler.backend.admission import (
    AdmissionManifest,
    AdmissionResult,
    admit_action_surface,
)
from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)

__all__ = [
    "AdmissionManifest",
    "AdmissionResult",
    "SurfaceContribution",
    "action_surface_payload",
    "admit_action_surface",
    "render_action_surface_payload",
]
