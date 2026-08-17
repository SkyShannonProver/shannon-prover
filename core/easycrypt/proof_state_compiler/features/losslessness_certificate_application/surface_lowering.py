"""Lower one unambiguous losslessness application to a generic action."""

from core.easycrypt.proof_state_compiler.backend.surface_lowering import (
    SurfaceContribution,
)
from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    AnalyzedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    CompilerInvocationContext,
)
from core.easycrypt.proof_state_compiler.backend.application_lowering import (
    lower_application_action,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.contracts import (
    LOSSLESSNESS_CERTIFICATE_APPLICATION_CERTIFICATION_POLICY,
    LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,
    LOSSLESSNESS_CERTIFICATE_APPLICATION_STRATEGY_CONTRACT,
    LOSSLESSNESS_CERTIFICATE_ANALYSIS_PRODUCER_ID,
)


def lower_losslessness_certificate_action(
    state: AnalyzedProofState,
    _invocation: CompilerInvocationContext,
) -> SurfaceContribution:
    applications = tuple(
        item
        for item in state.applications
        if item.producer_id == LOSSLESSNESS_CERTIFICATE_ANALYSIS_PRODUCER_ID
    )
    if len(applications) != 1:
        return SurfaceContribution()
    application = applications[0]
    return SurfaceContribution(actions=(lower_application_action(
        application,
        feature_id=LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,
        certification_policy=(
            LOSSLESSNESS_CERTIFICATE_APPLICATION_CERTIFICATION_POLICY
        ),
        strategy_contract=(
            LOSSLESSNESS_CERTIFICATE_APPLICATION_STRATEGY_CONTRACT
        ),
    ),))
