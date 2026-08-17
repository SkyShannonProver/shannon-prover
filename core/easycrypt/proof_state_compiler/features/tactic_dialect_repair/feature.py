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
            "NativeEagerWhileDialectDescriptor",
        ),
        certification_policy="exact_tactic_preflight_or_diagnostic_only",
        strategy_contracts=(TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT,),
    )


def tactic_dialect_repair_feature() -> FeatureDefinition:
    from .analysis import analyze_eager_while_dialect
    from .execution import TACTIC_DIALECT_REPAIR_EXECUTION_GATE
    from .native_attempt import plan_native_eager_while_attempt
    from .surface_lowering import lower_tactic_dialect_repair

    return FeatureDefinition(
        spec=tactic_dialect_repair_feature_spec(),
        execution_gate=TACTIC_DIALECT_REPAIR_EXECUTION_GATE,
        native_semantic_request_producers=(plan_native_eager_while_attempt,),
        analysis_producers=(analyze_eager_while_dialect,),
        surface_lowerers=(lower_tactic_dialect_repair,),
    )
