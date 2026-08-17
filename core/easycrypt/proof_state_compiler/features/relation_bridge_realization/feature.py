"""Argument-preserving real relation realization rows."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


RELATION_BRIDGE_REALIZATION_FEATURE_ID = "relation_bridge_realization"
RELATION_BRIDGE_REALIZATION_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the correction preserves the native-identified intermediate supplied "
        "by the failed intent and changes only its certified realization"
    ),
    required_commitment="agent_supplied_relation_intermediate",
)


def relation_bridge_realization_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=RELATION_BRIDGE_REALIZATION_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M16-RELATION-BRIDGE-REALIZATION",),
            experiment_id="relation-bridge-realization-v1",
        ),
        correctness_contract=(
            "claim one failed transitivity/change intent only when native "
            "EasyCrypt identifies either one exact real/int-<= realization or "
            "all three accepted real-< bridge choices"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, native relation descriptor, "
            "preservation witness, and unchanged-state tactic preflight"
        ),
        native_semantic_dependencies=(
            "NativeRelationBridgeDescriptor[real_le]",
            "NativeRelationBridgeDescriptor[int_le]",
            "NativeRelationBridgeChoiceDescriptor[real_lt]",
        ),
        shannon_delta_contract=(
            "preserve the agent-supplied intermediate and select only the "
            "registered real-<= ler_trans realization, or present every "
            "native-accepted real-< bridge without ranking; never discover a midpoint"
        ),
        lexical_prefilter_contract=(
            "transitivity/change spelling only schedules one native diagnostic; "
            "it does not establish a relation, type, or conversion"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryClaim",
            "RecoveryPreservationWitness",
            "RecoveryActionRealization",
            "NativeRelationBridgeDescriptor",
            "NativeRelationBridgeChoiceDescriptor",
        ),
        certification_policy="exact_tactic_preflight",
        strategy_contracts=(RELATION_BRIDGE_REALIZATION_STRATEGY_CONTRACT,),
    )

def relation_bridge_realization_feature() -> FeatureDefinition:
    from .analysis import analyze_relation_bridge_realization
    from .execution import RELATION_BRIDGE_FAILURE_EXECUTION_GATE
    from .native_attempt import plan_native_relation_bridge_attempt
    from .surface_lowering import lower_relation_bridge_realization

    return FeatureDefinition(
        spec=relation_bridge_realization_feature_spec(),
        execution_gate=RELATION_BRIDGE_FAILURE_EXECUTION_GATE,
        native_semantic_request_producers=(plan_native_relation_bridge_attempt,),
        analysis_producers=(analyze_relation_bridge_realization,),
        surface_lowerers=(lower_relation_bridge_realization,),
    )
