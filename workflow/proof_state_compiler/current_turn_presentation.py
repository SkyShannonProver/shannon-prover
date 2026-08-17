"""Public composition facade for the current turn-presentation backend."""

from workflow.proof_state_compiler.current_turn_composer import (
    compose_current_surface_turn,
)
from workflow.proof_state_compiler.current_turn_contract import (
    current_proof_surface_from_turn,
    require_current_workspace_view,
)
from workflow.proof_state_compiler.current_turn_markdown import (
    render_current_surface_turn_markdown,
)


__all__ = (
    "compose_current_surface_turn",
    "current_proof_surface_from_turn",
    "render_current_surface_turn_markdown",
    "require_current_workspace_view",
)
