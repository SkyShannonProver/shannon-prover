"""Commitment-relative structured intro-pattern repair vertical slice."""

from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)
from core.easycrypt.proof_state_compiler.features.failed_commit import (
    attempt_diagnostic_producer,
    failed_commit_gate,
)
from .ids import (
    INTRO_PATTERN_REPAIR_FEATURE_ID,
    INTRO_PATTERN_REPAIR_STRATEGY_CONTRACT,
)
from .analysis import analyze_intro_pattern_repair
from .realization import INTRO_PATTERN_REALIZATION_CODEC
from .surface_lowering import lower_intro_pattern_repair
from .syntax import is_nested_intro_pattern_candidate


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
            "AttemptRealization",
        ),
        certification_policy="exact_tactic_preflight",
        strategy_contracts=(INTRO_PATTERN_REPAIR_STRATEGY_CONTRACT,),
    )


def intro_pattern_repair_feature() -> FeatureDefinition:

    return FeatureDefinition(
        spec=intro_pattern_repair_feature_spec(),
        execution_gate=failed_commit_gate(
            gate_id="owned_current_intro_pattern_failure",
            prefilter=is_nested_intro_pattern_candidate,
            not_prefiltered_reason="intro_pattern_not_prefiltered",
            eligible_reason="candidate_structured_intro_failure",
            accepts_recovery_handoff=True,
        ),
        native_semantic_request_producers=(attempt_diagnostic_producer(
            producer_id="intro_pattern_repair.native_diagnostic",
            request_prefix="intro-pattern-attempt",
            prefilter=is_nested_intro_pattern_candidate,
        ),),
        analysis_producers=(analyze_intro_pattern_repair,),
        surface_lowerers=(lower_intro_pattern_repair,),
        realization_codecs=(INTRO_PATTERN_REALIZATION_CODEC,),
    )
