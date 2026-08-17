"""Lower one mutually exclusive same-resource action or diagnostic."""

import hashlib
import json
from dataclasses import replace

from core.easycrypt.proof_state_compiler.backend.application_lowering import (
    lower_application_action,
)
from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts import (
    AnalyzedProofState,
    AttemptedOperationIR,
    CompilerInvocationContext,
    CorrectionPresentation,
    DiagnosticCandidate,
    DO_YOU_MEAN,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.contracts import (
    OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.feature import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
    OPERATION_BINDING_REPAIR_STRATEGY_CONTRACT,
)


OPERATION_BINDING_REPAIR_CERTIFICATION_POLICY = "exact_tactic_preflight"


def lower_operation_binding_repair(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    attempted = state.attempted_operation
    if attempted is None or not state.recovery_ownership.owns(
        OPERATION_BINDING_REPAIR_FEATURE_ID,
        attempted.recovery_key,
    ):
        return SurfaceContribution()
    applications = tuple(
        item for item in state.applications
        if item.producer_id == OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID
    )
    diagnostics = tuple(
        item for item in state.diagnostics
        if item.producer_id == OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID
        and item.trigger_id == attempted.trigger_id
    )
    if len(applications) == 1 and not diagnostics:
        application = applications[0]
        action = lower_application_action(
            application,
            feature_id=OPERATION_BINDING_REPAIR_FEATURE_ID,
            certification_policy=OPERATION_BINDING_REPAIR_CERTIFICATION_POLICY,
            strategy_contract=OPERATION_BINDING_REPAIR_STRATEGY_CONTRACT,
        )
        witness = state.recovery_ownership.preservation_witness
        if witness is None:
            return SurfaceContribution()
        return SurfaceContribution(actions=(replace(
            action,
            recovery_witness_id=witness.witness_id,
            correction=CorrectionPresentation(
                presentation_kind=DO_YOU_MEAN,
                reason_code="selected_operation_argument_realization",
                reason=_unique_realization_reason(
                    attempted,
                    application.operation,
                ),
            ),
        ),))
    if not applications and len(diagnostics) == 1:
        diagnostic = diagnostics[0]
        material = json.dumps(
            diagnostic.identity_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        candidate_id = "operation-binding-diagnostic:" + hashlib.sha256(
            (attempted.recovery_key + "\0" + material).encode("utf-8")
        ).hexdigest()[:20]
        return SurfaceContribution(diagnostics=(DiagnosticCandidate(
            candidate_id=candidate_id,
            feature_id=OPERATION_BINDING_REPAIR_FEATURE_ID,
            diagnostic=diagnostic,
            strategy_contract=OPERATION_BINDING_REPAIR_STRATEGY_CONTRACT,
        ),))
    # Action/diagnostic overlap, duplicate results, and ambiguous ownership
    # all fail closed before certification or admission.
    return SurfaceContribution()


def _unique_realization_reason(
    attempted: AttemptedOperationIR,
    operation: str,
) -> str:
    repair = (
        "EasyCrypt accepts one corrected form of your selected "
        f"`{operation}`. It keeps the operation and theorem you chose and "
        "changes only how its module arguments are written or supplied."
    )
    if attempted.recovery_handoff is not None:
        return repair
    native_error = attempted.native_error_message.strip()
    if (
        not native_error
        or len(native_error.encode("utf-8")) > 500
        or "\r" in native_error
    ):
        return (
            "Your tactic failed. The proof state is unchanged.\n\n" + repair
        )
    indented_error = native_error.replace("\n", "\n  ")
    return (
        "Your tactic failed. The proof state is unchanged.\n\n"
        "EasyCrypt reports:\n\n"
        f"  {indented_error}\n\n"
        + repair
    )
