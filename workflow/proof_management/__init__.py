"""Manager-owned proof state services.

The package is the landing zone for proof-node management responsibilities
that used to live directly inside ``ProofNodeManager``.  The public manager
facade remains agent-facing; these services own specific internal state.
"""

from .checkpoint_store import ProofCheckpointManager
from .checkpoints import CheckpointIndex, CheckpointOption
from .event_store import ProofEventManager, ProofEventStoreError
from .events import ProofEvent
from .lineage import (
    LemmaLineageStore,
    lineage_briefing_from_events,
    lineage_briefing_markdown,
)
from .node_bootstrap import ProofNodeLifecycleManager
from .health import backend_failure_health_event, timeout_health_event
from .intent_admission import (
    IntentAdmission,
    IntentAdmissionController,
    IntentPreflightDecision,
)
from .protocol_repair import (
    ALLOWED_AGENT_INTENTS,
    AgentIntent,
    AgentIntentName,
    parse_agent_intent,
    view_allows_qed,
    view_requires_qed_before_finish,
)
from .projection import ProofProjectionPipeline, ProofProjectionResult
from .recovery_handlers import (
    ProofRecoveryIntentHandler,
    RecoveryTurnPlan,
)
from .repl_session import ReplBackendError, ReplBackendTimeout, ReplSessionManager
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
    agent_observation_from_command,
    backend_action_record,
    content_observation_from_payload,
    extract_json_object,
    timeout_backend_action_record,
)
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
from .turn_spine import CommittedTurnSpine
from .types import (
    ManagedTurn,
    NodeHealthEvent,
    NodeProgressSummary,
    ProofStateSnapshot,
    TurnDirective,
)

__all__ = [
    "ALLOWED_AGENT_INTENTS",
    "AgentIntent",
    "AgentIntentName",
    "CheckpointIndex",
    "CheckpointOption",
    "CommittedTurnSpine",
    "IntentAdmission",
    "IntentAdmissionController",
    "IntentPreflightDecision",
    "LemmaLineageStore",
    "ManagedTurn",
    "NodeHealthEvent",
    "NodeProgressSummary",
    "ProofCheckpointManager",
    "ProofEvent",
    "ProofEventManager",
    "ProofEventStoreError",
    "ProofNodeLifecycleManager",
    "ProofProjectionPipeline",
    "ProofProjectionResult",
    "ProofRecoveryIntentHandler",
    "ProofStateSnapshot",
    "ProofTurnExecutor",
    "RecoveryTurnPlan",
    "ReplBackendError",
    "ReplBackendTimeout",
    "ReplSessionManager",
    "ResumeRouteCandidate",
    "RouteFamilyEvidence",
    "TurnDirective",
    "agent_observation_from_command",
    "backend_action_record",
    "backend_failure_health_event",
    "build_resume_diversity_index",
    "content_observation_from_payload",
    "clean_manager_actions",
    "extract_json_object",
    "intent_effect",
    "intent_payload_surface",
    "infer_route_family",
    "latest_observation_for_view",
    "lineage_briefing_from_events",
    "lineage_briefing_markdown",
    "parse_agent_intent",
    "render_observation_view",
    "resume_diversity_candidate_summary",
    "resume_diversity_handoff_note",
    "resume_diversity_markdown",
    "resume_route_candidate_from_manifest",
    "route_family_score_adjustment",
    "selection_menu_action",
    "snapshot_surface",
    "timeout_backend_action_record",
    "timeout_health_event",
    "view_allows_qed",
    "view_requires_qed_before_finish",
    "view_with_latest_observation",
]
