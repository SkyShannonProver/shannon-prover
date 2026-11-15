"""Failure-linked hypothesis-scope diagnosis vertical slice."""

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
    HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
    HYPOTHESIS_SCOPE_FACT_STRATEGY_CONTRACT,
    HYPOTHESIS_SCOPE_SMT_HINT_STRATEGY_CONTRACT,
)
from .analysis import analyze_hypothesis_scope_diagnosis
from .realization import OUT_OF_SCOPE_HYPOTHESIS_CODEC
from .surface_lowering import lower_hypothesis_scope_diagnosis
from .syntax import is_hypothesis_scope_candidate


def hypothesis_scope_diagnosis_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M11", "M15"),
            experiment_id="hypothesis-scope-diagnosis-v1",
        ),
        correctness_contract=(
            "after one unchanged rejected smt(...) or rewrite ... in H, "
            "explain only when EasyCrypt names the failing reference (the "
            "located smt hint, or the first rejected rewrite-item prefix), "
            "that name does not resolve in the operation's own lookup scope "
            "(Ax.lookup_opt for an smt hint, the context before H for a "
            "rewrite proof term), it is a hypothesis of the checked goal, "
            "and, for rewrite, it is declared after H; an smt action is "
            "only the same call without that hint, accepted natively and "
            "certified by exact preflight at the original state"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, committed prefix, rejected "
            "tactic, native failing-reference position, native scope facts, "
            "optional native-accepted smt candidate, and any compound "
            "accepted prefix it was checked after"
        ),
        native_semantic_dependencies=(
            "NativeOutOfScopeHypothesisDescriptor",
        ),
        shannon_delta_contract=(
            "state the native scope facts about the agent's own written "
            "name; for smt, optionally drop exactly that hint from the "
            "agent's call; never add, rename, reorder or replace a "
            "reference, move a hypothesis, or suggest another tactic"
        ),
        lexical_prefilter_contract=(
            "one bounded smt(...) or rewrite ... in H sentence schedules a "
            "native diagnosis; lexical text never establishes which "
            "reference failed or any scope fact"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryHandoff",
            "RecoveryClaim",
            "RecoveryPreservationWitness",
            "RecoveryActionRealization",
            "AttemptRealization",
        ),
        certification_policy="exact_tactic_preflight_or_diagnostic_only",
        strategy_contracts=(
            HYPOTHESIS_SCOPE_FACT_STRATEGY_CONTRACT,
            HYPOTHESIS_SCOPE_SMT_HINT_STRATEGY_CONTRACT,
        ),
    )


def hypothesis_scope_diagnosis_feature() -> FeatureDefinition:

    return FeatureDefinition(
        spec=hypothesis_scope_diagnosis_feature_spec(),
        execution_gate=failed_commit_gate(
            gate_id="owned_current_hypothesis_scope_failure",
            prefilter=is_hypothesis_scope_candidate,
            not_prefiltered_reason="hypothesis_scope_not_prefiltered",
            eligible_reason="candidate_hypothesis_scope_failure",
            accepts_recovery_handoff=True,
        ),
        native_semantic_request_producers=(attempt_diagnostic_producer(
            producer_id="hypothesis_scope_diagnosis.native_diagnostic",
            request_prefix="hypothesis-scope-attempt",
            prefilter=is_hypothesis_scope_candidate,
        ),),
        analysis_producers=(analyze_hypothesis_scope_diagnosis,),
        surface_lowerers=(lower_hypothesis_scope_diagnosis,),
        realization_codecs=(OUT_OF_SCOPE_HYPOTHESIS_CODEC,),
    )
