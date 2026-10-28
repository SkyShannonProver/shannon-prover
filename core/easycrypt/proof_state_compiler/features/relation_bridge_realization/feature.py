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
            "AttemptRealization",
        ),
        certification_policy="exact_tactic_preflight",
        strategy_contracts=(RELATION_BRIDGE_REALIZATION_STRATEGY_CONTRACT,),
    )

def relation_bridge_realization_feature() -> FeatureDefinition:
    from core.easycrypt.proof_state_compiler.features.failed_commit import (
        attempt_diagnostic_producer,
        failed_commit_gate,
    )
    from .analysis import analyze_relation_bridge_realization
    from .realization import RELATION_BRIDGE_CODECS
    from .surface_lowering import lower_relation_bridge_realization
    from .syntax import relation_bridge_intent_family

    def relation_intent(tactic: str) -> bool:
        return relation_bridge_intent_family(tactic) is not None

    return FeatureDefinition(
        spec=relation_bridge_realization_feature_spec(),
        execution_gate=failed_commit_gate(
            gate_id="owned_current_relation_failure",
            prefilter=relation_intent,
            not_prefiltered_reason="relation_intent_not_prefiltered",
            eligible_reason="candidate_relation_bridge_failure",
            accepts_recovery_handoff=True,
        ),
        native_semantic_request_producers=(attempt_diagnostic_producer(
            producer_id="relation_bridge_realization.attempt.native_diagnostic",
            request_prefix="relation-bridge-attempt",
            prefilter=relation_intent,
        ),),
        analysis_producers=(analyze_relation_bridge_realization,),
        surface_lowerers=(lower_relation_bridge_realization,),
        realization_codecs=RELATION_BRIDGE_CODECS,
    )
