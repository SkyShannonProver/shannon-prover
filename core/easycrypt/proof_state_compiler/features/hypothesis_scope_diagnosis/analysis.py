"""Own one native-established out-of-scope hypothesis reference.

The analysis states facts only.  Every fact was established by EasyCrypt in
the proof where the failing operation ran: the current goal, or the temporary
goal of a compound's accepted prefix.  It names no replacement, ordering or
proof route.  The one exception is an smt call EasyCrypt accepts without the
failing hint: that exact tactic may be offered as a certified action.
"""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    EXPLANATION_ONLY,
    CompilerInvocationContext,
    ProofCoordinate,
    ProofIR,
    RecoveryActionRealization,
    StructuredDiagnostic,
    exact_operation_resource_witness,
    native_argument_realization_witness,
    recovery_claim_for,
)
from core.easycrypt.proof_state_compiler.contracts.digest import text_sha256
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_goal_reference,
)
from .ids import HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID
from .realization import (
    NativeOutOfScopeHypothesisDescriptor,
    out_of_scope_hypothesis_of,
)


HYPOTHESIS_SCOPE_ANALYSIS_PRODUCER_ID = "hypothesis_scope_diagnosis.analysis"


def hypothesis_scope_facts(
    descriptor: NativeOutOfScopeHypothesisDescriptor,
    goal: str,
) -> str:
    """The native facts, in the words the agent sees."""

    name = descriptor.written_name
    if descriptor.source_operation == "smt":
        return (
            f"`{name}` is a hypothesis of {goal}, not a global lemma. "
            "`smt(...)` hints name global lemmas, axioms or theories; the "
            "goal's hypotheses are already given to smt."
        )
    target = descriptor.target_name
    return (
        f"`{name}` is a hypothesis of {goal}, declared after `{target}`; "
        f"`rewrite … in {target}` resolves names in the context before "
        f"`{target}`."
    )


def analyze_hypothesis_scope_diagnosis(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    descriptor = (
        None if attempted is None else out_of_scope_hypothesis_of(attempted)
    )
    if (
        attempted is None
        or descriptor is None
        or attempted.operation_family != descriptor.source_operation
        or attempted.exact_resource != descriptor.written_name
        or attempted.native_diagnostic_status != "blocker"
        or attempted.native_failure_kind != descriptor.failure_kind
    ):
        return AnalysisContribution()
    goal = checked_goal_reference(attempted.recovery_handoff)
    facts = hypothesis_scope_facts(descriptor, goal)
    if descriptor.candidate_tactic:
        return _smt_hint_action(attempted, descriptor, facts)
    diagnostic = StructuredDiagnostic(
        producer_id=HYPOTHESIS_SCOPE_ANALYSIS_PRODUCER_ID,
        code=descriptor.failure_kind,
        primary=facts,
        notes=(),
        help="",
        applicability=EXPLANATION_ONLY,
        evidence_refs=attempted.evidence_refs,
        trigger_id=attempted.trigger_id,
    )
    return AnalysisContribution(
        diagnostics=(diagnostic,),
        recovery_claims=(recovery_claim_for(
            attempted,
            feature_id=HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
            allowed_output_kinds=("diagnostic",),
            preservation_witness=exact_operation_resource_witness(
                attempted.operation_family, ""
            ),
        ),),
    )


def _smt_hint_action(attempted, descriptor, facts) -> AnalysisContribution:
    witness = native_argument_realization_witness(
        source_operation_family="smt",
        target_operation_family="smt",
        committed_argument="\0".join(descriptor.remaining_hints),
        native_family="smt_hints_without_goal_hypothesis",
        exact_tactic=descriptor.candidate_tactic,
    )
    realization = RecoveryActionRealization(
        realization_id="hypothesis-scope-smt-hint:" + text_sha256(
            attempted.recovery_key + "\0" + witness.witness_id
        )[:20],
        feature_id=HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        trigger_id=attempted.trigger_id,
        witness=witness,
        exact_tactic=descriptor.candidate_tactic,
        reason_code=descriptor.failure_kind,
        reason=(
            facts + " EasyCrypt accepts the same `smt` call without the "
            f"`{descriptor.written_name}` hint."
        ),
        evidence_refs=attempted.evidence_refs,
    )
    return AnalysisContribution(
        recovery_action_realizations=(realization,),
        recovery_claims=(recovery_claim_for(
            attempted,
            feature_id=HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID,
            allowed_output_kinds=("action",),
            preservation_witness=witness,
        ),),
    )
