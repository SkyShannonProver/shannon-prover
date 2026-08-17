"""Evidence-gated feature registrations for the common compiler pipeline."""

from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionDecision,
    FeatureExecutionEligibility,
    FeatureExecutionGate,
    FeatureExecutionPlan,
    ONCE_PER_TURN_OCCURRENCE,
    REPEATABLE,
    STATE_REFRESH_EXECUTION_GATE,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureCatalog,
    FeatureDefinition,
    FeatureSpec,
)
__all__ = [
    "ExperimentGate",
    "FeatureExecutionDecision",
    "FeatureExecutionEligibility",
    "FeatureExecutionGate",
    "FeatureExecutionPlan",
    "ONCE_PER_TURN_OCCURRENCE",
    "REPEATABLE",
    "FeatureCatalog",
    "FeatureDefinition",
    "FeatureSpec",
    "STATE_REFRESH_EXECUTION_GATE",
]
