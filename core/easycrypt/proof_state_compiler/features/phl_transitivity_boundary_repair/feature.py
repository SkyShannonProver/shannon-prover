"""Feature definition for PHL transitivity form/current-goal repair."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID = (
    "phl_transitivity_boundary_repair"
)
PHL_TRANSITIVITY_BOUNDARY_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the diagnostic explains the native boundary required by the written "
        "PHL transitivity form and leaves boundary, side, and intermediate "
        "selection to the agent"
    ),
    required_commitment="agent_supplied_phl_transitivity_form",
)


def phl_transitivity_boundary_repair_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M22-PHL-TRANSITIVITY-BOUNDARY",),
            experiment_id="phl-transitivity-boundary-v1",
        ),
        correctness_contract=(
            "diagnose only a native-parsed PHL function/statement transitivity "
            "form used at the opposite native equiv goal boundary"
        ),
        provenance_contract=(
            "exact failed occurrence, StateRef, native PHL form and current "
            "equiv goal kind, with one recovery owner"
        ),
        native_semantic_dependencies=(
            "NativePhlTransitivityBoundaryDescriptor",
        ),
        shannon_delta_contract=(
            "state the required PHL boundary and bounded alternatives without "
            "choosing a function, statement, or side"
        ),
        lexical_prefilter_contract=(
            "bounded transitivity spelling schedules native parsing only"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryClaim",
            "RecoveryPreservationWitness",
            "NativePhlTransitivityBoundaryDescriptor",
        ),
        certification_policy="none_diagnostic_only",
        strategy_contracts=(
            PHL_TRANSITIVITY_BOUNDARY_REPAIR_STRATEGY_CONTRACT,
        ),
    )


def phl_transitivity_boundary_repair_feature() -> FeatureDefinition:
    from .analysis import analyze_phl_transitivity_boundary
    from .execution import PHL_TRANSITIVITY_BOUNDARY_EXECUTION_GATE
    from .native_attempt import plan_native_phl_transitivity_attempt
    from .surface_lowering import lower_phl_transitivity_boundary

    return FeatureDefinition(
        spec=phl_transitivity_boundary_repair_feature_spec(),
        execution_gate=PHL_TRANSITIVITY_BOUNDARY_EXECUTION_GATE,
        native_semantic_request_producers=(plan_native_phl_transitivity_attempt,),
        analysis_producers=(analyze_phl_transitivity_boundary,),
        surface_lowerers=(lower_phl_transitivity_boundary,),
    )
