"""Commitment-relative pure-tail recovery vertical slice."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


PURE_TAIL_RECOVERY_FEATURE_ID = "pure_tail_recovery"
PURE_TAIL_RECOVERY_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected the rewrite lemma and direction; native "
        "EasyCrypt identifies one unique current hypothesis target"
    ),
    required_commitment="attempted_rewrite_lemma_and_direction",
)


def pure_tail_recovery_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=PURE_TAIL_RECOVERY_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M14",),
            experiment_id="pure-tail-rewrite-target-recovery-v1",
        ),
        correctness_contract=(
            "after one unchanged failed plain rewrite, preserve the exact lemma "
            "and left-to-right direction; act only when native EasyCrypt accepts "
            "the rewrite at exactly one current named hypothesis"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, committed prefix, selected "
            "rewrite resource, native unique-target descriptor, and exact "
            "unchanged-state tactic preflight"
        ),
        native_semantic_dependencies=("NativePureTailRewriteDescriptor",),
        shannon_delta_contract=(
            "move only the already selected rewrite from the conclusion to one "
            "native-unique hypothesis target; do not add lemmas, reverse the "
            "rewrite, choose an occurrence, split a case, or discharge a goal"
        ),
        lexical_prefilter_contract=(
            "one plain named rewrite bounds a native diagnostic request; lexical "
            "text never establishes applicability or target identity"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryClaim",
            "RecoveryActionRealization",
            "AttemptRealization",
        ),
        certification_policy="exact_tactic_preflight",
        strategy_contracts=(PURE_TAIL_RECOVERY_STRATEGY_CONTRACT,),
    )


def pure_tail_recovery_feature() -> FeatureDefinition:
    from core.easycrypt.proof_state_compiler.features.failed_commit import (
        attempt_diagnostic_producer,
        failed_commit_gate,
    )
    from .analysis import analyze_pure_tail_recovery
    from .realization import PURE_TAIL_REWRITE_CODEC
    from .surface_lowering import lower_pure_tail_recovery
    from .syntax import selected_plain_rewrite

    def plain_rewrite(tactic: str) -> bool:
        return selected_plain_rewrite(tactic) is not None

    return FeatureDefinition(
        spec=pure_tail_recovery_feature_spec(),
        execution_gate=failed_commit_gate(
            gate_id="owned_current_pure_tail_failure",
            prefilter=plain_rewrite,
            not_prefiltered_reason="plain_rewrite_not_prefiltered",
            eligible_reason="candidate_selected_rewrite_failure",
            accepts_recovery_handoff=True,
        ),
        native_semantic_request_producers=(attempt_diagnostic_producer(
            producer_id="pure_tail_recovery.rewrite_target.native_diagnostic",
            request_prefix="pure-tail-rewrite-attempt",
            prefilter=plain_rewrite,
        ),),
        analysis_producers=(analyze_pure_tail_recovery,),
        surface_lowerers=(lower_pure_tail_recovery,),
        realization_codecs=(PURE_TAIL_REWRITE_CODEC,),
    )
