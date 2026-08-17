"""Evidence-gated contract for intrinsic program-operation readiness."""

from core.easycrypt.proof_state_compiler.contracts import (
    INTRINSIC,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


PROGRAM_OPERATION_READINESS_FEATURE_ID = "program_operation_readiness"
PROGRAM_OPERATION_READINESS_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=INTRINSIC,
    rationale=(
        "structural legality and its current blocker are fixed by the exact "
        "tactic-active program boundary"
    ),
)


def program_operation_readiness_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=PROGRAM_OPERATION_READINESS_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M04",),
            experiment_id="program-operation-readiness-batch-v1",
        ),
        correctness_contract=(
            "emit only exact current structural legality/blocker/boundary; "
            "never recommend an operation or a route around the blocker"
        ),
        provenance_contract=(
            "current authoritative goal event and exact P2/P3 program "
            "coordinate; repeated material content is silent"
        ),
        native_semantic_dependencies=("NativeProofStateSnapshot",),
        shannon_delta_contract=(
            "classify intrinsic readiness at the one compiler-owned coordinate"
        ),
        lexical_prefilter_contract="none; program structure is native-derived",
        required_ir_capabilities=(
            "ProgramStatement",
            "ProofCoordinate",
        ),
        certification_policy="exact_structural_readiness",
        strategy_contracts=(
            PROGRAM_OPERATION_READINESS_STRATEGY_CONTRACT,
        ),
    )


def program_operation_readiness_feature() -> FeatureDefinition:
    from .analysis import analyze_program_operation_readiness
    from .surface_lowering import lower_program_operation_readiness

    return FeatureDefinition(
        spec=program_operation_readiness_feature_spec(),
        analysis_producers=(analyze_program_operation_readiness,),
        surface_lowerers=(lower_program_operation_readiness,),
    )
