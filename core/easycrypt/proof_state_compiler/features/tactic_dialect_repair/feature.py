"""Feature definition for selected tactic-dialect repair."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


TACTIC_DIALECT_REPAIR_FEATURE_ID = "tactic_dialect_repair"
TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected eager while; the feature preserves its "
        "submitted invariant candidates and changes only native tactic dialect"
    ),
    required_commitment="agent_supplied_eager_while_operation",
)


def tactic_dialect_repair_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=TACTIC_DIALECT_REPAIR_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M13", "M22"),
            experiment_id="selected-eager-while-dialect-v1",
        ),
        correctness_contract=(
            "repair only an explicitly failed eager-while form when native "
            "EasyCrypt establishes the current boundary and every exposed "
            "candidate passes unchanged-state preflight"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, native eager descriptor, "
            "preserved submitted formula, and one recovery owner"
        ),
        native_semantic_dependencies=("NativeEagerWhileDialectDescriptor",),
        shannon_delta_contract=(
            "explain the invariant-only form, expose one checked submitted "
            "invariant, or list every bounded checked submitted candidate; "
            "never choose eager or invent an invariant"
        ),
        lexical_prefilter_contract=(
            "bounded eager-while spelling schedules native diagnosis only"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryClaim",
            "RecoveryPreservationWitness",
            "RecoveryActionRealization",
            "AttemptRealization",
        ),
        certification_policy="exact_tactic_preflight_or_diagnostic_only",
        strategy_contracts=(TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,),
    )


def tactic_dialect_repair_feature() -> FeatureDefinition:
    from core.easycrypt.proof_state_compiler.features.failed_commit import (
        attempt_diagnostic_producer,
        failed_commit_gate,
    )
    from .analysis import analyze_eager_while_dialect
    from .realization import EAGER_WHILE_DIALECT_CODEC
    from .surface_lowering import lower_tactic_dialect_repair
    from .syntax import is_candidate_eager_while

    return FeatureDefinition(
        spec=tactic_dialect_repair_feature_spec(),
        execution_gate=failed_commit_gate(
            gate_id="owned_current_tactic_dialect_failure",
            prefilter=is_candidate_eager_while,
            not_prefiltered_reason="eager_while_not_prefiltered",
            eligible_reason="candidate_selected_eager_while_failure",
            accepts_recovery_handoff=True,
        ),
        native_semantic_request_producers=(attempt_diagnostic_producer(
            producer_id="tactic_dialect_repair.eager_while.native_diagnostic",
            request_prefix="eager-while-dialect",
            prefilter=is_candidate_eager_while,
        ),),
        analysis_producers=(analyze_eager_while_dialect,),
        surface_lowerers=(lower_tactic_dialect_repair,),
        realization_codecs=(EAGER_WHILE_DIALECT_CODEC,),
    )
