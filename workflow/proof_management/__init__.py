"""Manager-owned proof state services.

The package is the landing zone for proof-node management responsibilities
that used to live directly inside ``ProofNodeManager``.  The public manager
facade remains agent-facing; these services own specific internal state.
"""

from .checkpoint_store import ProofCheckpointManager
from .checkpoints import CheckpointIndex, CheckpointOption
from .event_store import ProofEventManager
from .events import ProofEvent
from .evidence import EvidenceBundle
from .lineage import (
    LemmaLineageStore,
    lineage_briefing_from_events,
    lineage_briefing_markdown,
)
from .escalation_policy import EscalationPolicy
from .lifecycle import ProofNodeLifecycleManager
from .loop_monitor import LoopMonitor
from .surface_producer import ManagerSurfaceProducer
from .memory_store import (
    NegativeMemory,
    ProofMemoryManager,
    RepairEpisode,
    RoutePiece,
    RouteMemorySnapshot,
    RouteMemory,
)
from .node_state import ProofNodeState, ProofNodeStateManager
from .health import backend_failure_health_event, timeout_health_event
from .intent_preflight import (
    IntentPreflightDecision,
    preflight_intent,
    probe_undo_boundary_observation,
)
from .protocol_repair import (
    ALLOWED_AGENT_INTENTS,
    AgentIntent,
    AgentIntentName,
    parse_agent_intent,
    view_allows_qed,
    view_requires_qed_before_finish,
)
from .probe_alternatives import (
    ProofProbeAlternativeManager,
    probe_alternative_entry,
    snapshot_probe_key,
    workspace_view_with_probe_alternatives,
)
from .projection import ProofProjectionPipeline, ProofProjectionResult
from .recovery_handlers import (
    ProofRecoveryIntentHandler,
    RecoveryTurnPlan,
)
from .repl_session import ReplBackendError, ReplBackendTimeout, ReplSessionManager
from .repair_notes import RewindNote, normalize_rewind_note, rewind_note_summary
from .route_diversity import (
    ResumeRouteCandidate,
    build_resume_diversity_index,
    resume_diversity_candidate_summary,
    resume_diversity_handoff_note,
    resume_diversity_markdown,
    resume_route_candidate_from_manifest,
)
from .route_family import (
    RouteFamilyEvidence,
    infer_route_family,
    route_family_score_adjustment,
)
from .backend_actions import (
    accepted_probe_preview_effects,
    agent_observation_from_command,
    command_summary,
    content_observation_from_payload,
    extract_json_object,
    timeout_command_summary,
    workspace_view_from_payload,
)
from .renderer import ProofViewRenderer
from .turn_executor import ProofTurnExecutor
from .turn_view import (
    clean_manager_actions,
    intent_effect,
    intent_payload_surface,
    latest_observation_for_view,
    render_observation_view,
    selection_menu_action,
    snapshot_surface,
    view_with_latest_observation,
)
from .types import ManagedTurn, NodeHealthEvent, NodeProgressSummary, ProofStateSnapshot

__all__ = [
    "ALLOWED_AGENT_INTENTS",
    "AgentIntent",
    "AgentIntentName",
    "CheckpointIndex",
    "CheckpointOption",
    "EscalationPolicy",
    "EvidenceBundle",
    "IntentPreflightDecision",
    "LemmaLineageStore",
    "LoopMonitor",
    "ManagedTurn",
    "ManagerSurfaceProducer",
    "NodeHealthEvent",
    "NodeProgressSummary",
    "NegativeMemory",
    "ProofCheckpointManager",
    "ProofEvent",
    "ProofEventManager",
    "ProofMemoryManager",
    "ProofNodeLifecycleManager",
    "ProofNodeState",
    "ProofNodeStateManager",
    "ProofProjectionPipeline",
    "ProofProjectionResult",
    "ProofProbeAlternativeManager",
    "ProofRecoveryIntentHandler",
    "ProofStateSnapshot",
    "ProofTurnExecutor",
    "ProofViewRenderer",
    "RepairEpisode",
    "RouteMemory",
    "RoutePiece",
    "RouteMemorySnapshot",
    "RecoveryTurnPlan",
    "ReplBackendError",
    "ReplBackendTimeout",
    "ReplSessionManager",
    "RewindNote",
    "ResumeRouteCandidate",
    "RouteFamilyEvidence",
    "accepted_probe_preview_effects",
    "agent_observation_from_command",
    "backend_failure_health_event",
    "build_resume_diversity_index",
    "command_summary",
    "content_observation_from_payload",
    "clean_manager_actions",
    "extract_json_object",
    "intent_effect",
    "intent_payload_surface",
    "infer_route_family",
    "latest_observation_for_view",
    "lineage_briefing_from_events",
    "lineage_briefing_markdown",
    "normalize_rewind_note",
    "parse_agent_intent",
    "preflight_intent",
    "probe_alternative_entry",
    "probe_undo_boundary_observation",
    "render_observation_view",
    "resume_diversity_candidate_summary",
    "resume_diversity_handoff_note",
    "resume_diversity_markdown",
    "resume_route_candidate_from_manifest",
    "rewind_note_summary",
    "route_family_score_adjustment",
    "selection_menu_action",
    "snapshot_probe_key",
    "snapshot_surface",
    "timeout_command_summary",
    "timeout_health_event",
    "view_allows_qed",
    "view_requires_qed_before_finish",
    "view_with_latest_observation",
    "workspace_view_with_probe_alternatives",
    "workspace_view_from_payload",
]
