"""Failure-linked localization of the first failing smt call of a tactic."""

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
    SMT_FAILURE_LOCALIZATION_FEATURE_ID,
    SMT_FAILURE_LOCALIZATION_STRATEGY_CONTRACT,
)
from .analysis import analyze_smt_failure_localization
from .realization import SMT_FAILURE_LOCALIZATION_CODEC
from .surface_lowering import lower_smt_failure_localization
from .syntax import is_direct_smt_failure_candidate


def smt_failure_localization_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=SMT_FAILURE_LOCALIZATION_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M15-SMT-FAILURE-LOCALIZATION",),
            experiment_id="smt-failure-localization-v1",
        ),
        correctness_contract=(
            "after one unchanged rejected tactic, or the failing part of a "
            "recovery handoff in its temporary state, report only EasyCrypt's "
            "first failing smt call: its exact source text located by "
            "EasyCrypt's report-mode notice, the number of goals report mode "
            "finds it failing on, and the native kind of the first failed "
            "goal when EasyCrypt's own run re-derives that goal; claim only "
            "when the strict run fails at the same smt call number with the "
            "uncatchable strict smt error and with the error EasyCrypt "
            "reported for the commit; never name a tactic, hint, lemma or "
            "next step"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, committed prefix, rejected "
            "tactic, report-mode notice, report and strict smt call numbers, "
            "strict native error, and any recovery handoff"
        ),
        native_semantic_dependencies=("NativeSmtFailureLocalization",),
        shannon_delta_contract=(
            "run the agent's exact tactic in EasyCrypt's report and strict "
            "modes at the same proof, join the first report notice to the "
            "strict failure by smt call number, quote the located call and "
            "count same-call failures; re-derive the first failed goal only "
            "through EasyCrypt runs of the stages that reach the call; do "
            "not alter, repair, reorder or commit any tactic"
        ),
        lexical_prefilter_contract=(
            "one sentence that mentions smt, is not one lone smt call, and "
            "is not a top-level ';' sequence outside a by/first/last/expect "
            "body bounds a direct native request; a sequence or a "
            "multi-sentence commit is reached only through a recovery "
            "handoff; lexical text never locates a call or establishes a "
            "failure"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryHandoff",
            "RecoveryClaim",
            "AttemptRealization",
        ),
        certification_policy="none_diagnostic_only",
        strategy_contracts=(SMT_FAILURE_LOCALIZATION_STRATEGY_CONTRACT,),
    )


def smt_failure_localization_feature() -> FeatureDefinition:
    return FeatureDefinition(
        spec=smt_failure_localization_feature_spec(),
        execution_gate=failed_commit_gate(
            gate_id="owned_current_smt_failure",
            prefilter=is_direct_smt_failure_candidate,
            not_prefiltered_reason="smt_failure_not_prefiltered",
            eligible_reason="candidate_smt_call_failure",
            accepts_recovery_handoff=True,
        ),
        native_semantic_request_producers=(attempt_diagnostic_producer(
            producer_id="smt_failure_localization.native_diagnostic",
            request_prefix="smt-failure-attempt",
            prefilter=is_direct_smt_failure_candidate,
        ),),
        analysis_producers=(analyze_smt_failure_localization,),
        surface_lowerers=(lower_smt_failure_localization,),
        realization_codecs=(SMT_FAILURE_LOCALIZATION_CODEC,),
    )
