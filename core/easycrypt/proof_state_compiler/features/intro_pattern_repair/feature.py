"""Commitment-relative structured intro-pattern repair vertical slice."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


INTRO_PATTERN_REPAIR_FEATURE_ID = "intro_pattern_repair"
INTRO_PATTERN_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected the destruct operation and exact binder "
        "names/order; native EasyCrypt only realizes that commitment in its "
        "canonical deep-flatten intro dialect"
    ),
    required_commitment="selected_destruct_source_and_ordered_binders",
)


def intro_pattern_repair_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=INTRO_PATTERN_REPAIR_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M15",),
            experiment_id="structured-intro-pattern-recovery-v1",
        ),
        correctness_contract=(
            "after one unchanged rejected structured destruct, preserve the "
            "exact tactic, selected source, binder names, binder order, and "
            "continuation; act only when EasyCrypt accepts exactly one "
            "canonical deep-flatten realization in the unchanged state"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, committed prefix, rejected "
            "tactic, native parsed intro tree, ordered binders, and exact "
            "unchanged-state candidate preflight"
        ),
        native_semantic_dependencies=("NativeIntroPatternRepairDescriptor",),
        shannon_delta_contract=(
            "replace one already selected nested intro-pattern tree with "
            "EasyCrypt's deep-flatten spelling; do not select a hypothesis, "
            "invent, remove, rename, or reorder binders, change the tactic "
            "core, or alter its continuation"
        ),
        lexical_prefilter_contract=(
            "one bounded move/case tactic with a nested bracket tree bounds a "
            "native query; lexical text never establishes decomposition, "
            "binder correspondence, or applicability"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryClaim",
            "RecoveryActionRealization",
            "NativeIntroPatternRepairDescriptor",
        ),
        certification_policy="exact_tactic_preflight",
        strategy_contracts=(INTRO_PATTERN_REPAIR_STRATEGY_CONTRACT,),
    )


def intro_pattern_repair_feature() -> FeatureDefinition:
    from .analysis import analyze_intro_pattern_repair
    from .execution import INTRO_PATTERN_REPAIR_EXECUTION_GATE
    from .native_attempt import plan_native_intro_pattern_attempt
    from .surface_lowering import lower_intro_pattern_repair

    return FeatureDefinition(
        spec=intro_pattern_repair_feature_spec(),
        execution_gate=INTRO_PATTERN_REPAIR_EXECUTION_GATE,
        native_semantic_request_producers=(plan_native_intro_pattern_attempt,),
        analysis_producers=(analyze_intro_pattern_repair,),
        surface_lowerers=(lower_intro_pattern_repair,),
    )
