"""Consume native EasyCrypt descriptors for the frozen M05 application."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    NativePlanningBudget,
    ProofCoordinate,
    ProofIR,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.candidate_discovery import (
    discover_unique_losslessness_application,
    plan_losslessness_native_application,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.contracts import (
    LOSSLESSNESS_CERTIFICATE_ANALYSIS_PRODUCER_ID,
    LOSSLESSNESS_CERTIFICATE_NATIVE_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.middle_end.native_application import (
    native_application_contribution,
    single_module_losslessness_certificate_matches,
)


def analyze_native_losslessness_application(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    """Admit binding facts only from one exact accepted native descriptor."""

    sketch = discover_unique_losslessness_application(proof_ir, coordinate)
    requests = plan_losslessness_native_application(
        proof_ir,
        coordinate,
        invocation,
        NativePlanningBudget(),
    ).requests
    if sketch is None or len(requests) != 1:
        return AnalysisContribution()
    request = requests[0]
    observations = tuple(
        item
        for item in proof_ir.native_semantic_observations
        if item.producer_id == LOSSLESSNESS_CERTIFICATE_NATIVE_PRODUCER_ID
        and item.request_id == request.request_id
    )
    if (
        len(observations) != 1
        or observations[0].status != "accepted"
        or observations[0].descriptor is None
    ):
        return AnalysisContribution()
    observation = observations[0]
    descriptor = observation.descriptor
    if not single_module_losslessness_certificate_matches(
        descriptor,
        resource_symbol=sketch.resource.symbol,
        target_procedure=sketch.target_procedure,
    ):
        return AnalysisContribution()
    return native_application_contribution(
        resource=sketch.resource,
        observation=observation,
        producer_id=LOSSLESSNESS_CERTIFICATE_ANALYSIS_PRODUCER_ID,
        identity_namespace="native-losslessness",
        evidence_refs=sketch.evidence_refs,
    )
