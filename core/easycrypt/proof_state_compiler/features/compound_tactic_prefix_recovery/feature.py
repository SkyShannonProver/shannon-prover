"""Commitment-relative compound-tactic accepted-prefix diagnostic slice."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID = (
    "compound_tactic_prefix_recovery"
)
COMPOUND_TACTIC_PREFIX_RECOVERY_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected and ordered the compound tactic; native "
        "EasyCrypt reports the longest contiguous accepted source prefix "
        "without asking the agent to commit that prefix alone"
    ),
    required_commitment="exact_rejected_compound_tactic_and_source_order",
)


def compound_tactic_prefix_recovery_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M18",),
            experiment_id="compound-tactic-accepted-prefix-diagnostic-v2",
        ),
        correctness_contract=(
            "after one unchanged native-confirmed compound-tactic rejection, "
            "preserve the exact source and order; report only the longest "
            "contiguous EasyCrypt-accepted proper top-level prefix, its "
            "proof-state effect, first rejected extension, and that "
            "extension's native error; hand a native-typed extension to the "
            "ordinary recovery owner for either a no-progress or a "
            "state-changing prefix; bind all consumer-native work to the "
            "exact accepted prefix, and recompose any checked repair with "
            "that prefix before original-StateRef certification; never "
            "direct or perform a standalone prefix commit; when no typed "
            "suffix consumer forms a P3 action or diagnostic, retain the "
            "source feature as the sole factual boundary-diagnostic owner"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, committed prefix, complete "
            "bounded lexical stage population, native full-attempt rejection, "
            "per-prefix acceptance and proof-state effect, native full-attempt "
            "error, and native-typed first-rejected-prefix error"
        ),
        native_semantic_dependencies=(
            "NativeTacticPrefixDiagnosticDescriptor",
        ),
        shannon_delta_contract=(
            "explain the accepted/rejected boundary inside the agent's exact "
            "compound tactic; route its exact native-typed suffix through the "
            "existing recovery owner in a scratch context derived from the "
            "accepted prefix, then recompose only a unique checked repair; "
            "otherwise fall back to the native accepted/rejected boundary; "
            "do not commit, invent, reorder, rewrite, or replay any tactic token"
        ),
        lexical_prefilter_contract=(
            "balanced top-level semicolons enumerate at most eight proper "
            "source prefixes; lexical text never establishes parsing, "
            "acceptance, progress, or failure localization"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryHandoff",
            "RecoveryClaim",
            "NativeTacticPrefixDiagnosticDescriptor",
        ),
        certification_policy="none_diagnostic_only",
        strategy_contracts=(
            COMPOUND_TACTIC_PREFIX_RECOVERY_STRATEGY_CONTRACT,
        ),
    )


def compound_tactic_prefix_recovery_feature() -> FeatureDefinition:
    from .analysis import analyze_compound_tactic_prefix_recovery
    from .execution import COMPOUND_TACTIC_PREFIX_RECOVERY_EXECUTION_GATE
    from .native_attempt import plan_native_compound_prefix_attempt
    from .surface_lowering import lower_compound_tactic_prefix_recovery

    return FeatureDefinition(
        spec=compound_tactic_prefix_recovery_feature_spec(),
        execution_gate=COMPOUND_TACTIC_PREFIX_RECOVERY_EXECUTION_GATE,
        native_semantic_request_producers=(
            plan_native_compound_prefix_attempt,
        ),
        analysis_producers=(analyze_compound_tactic_prefix_recovery,),
        surface_lowerers=(lower_compound_tactic_prefix_recovery,),
    )
