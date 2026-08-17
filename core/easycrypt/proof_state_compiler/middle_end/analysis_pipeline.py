"""Aggregate registered P3 producers into one shared analyzed state."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    AnalyzedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.proof_ir import ProofIR
from core.easycrypt.proof_state_compiler.contracts.delivery import CompilerInvocationContext
from core.easycrypt.proof_state_compiler.derived_provenance import derived_provenance
from core.easycrypt.proof_state_compiler.middle_end.binding_analysis import (
    aggregate_applications,
    aggregate_bindings,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
    AnalysisProducer,
)
from core.easycrypt.proof_state_compiler.middle_end.coordinate import analyze_coordinate
from core.easycrypt.proof_state_compiler.middle_end.resource_analysis import (
    aggregate_resource_assessments,
)
from core.easycrypt.proof_state_compiler.middle_end.recovery_ownership import (
    complete_recovery_claims,
    resolve_recovery_ownership,
)


def analyze_proof_ir(
    proof_ir: ProofIR,
    producers: tuple[AnalysisProducer, ...] = (),
    invocation: CompilerInvocationContext | None = None,
) -> AnalyzedProofState:
    if invocation is None:
        from core.easycrypt.proof_state_compiler.contracts.delivery import (
            compiler_invocation_context,
        )
        invocation = compiler_invocation_context(
            proof_ir.state_ref,
            source_event_id=proof_ir.provenance.source_event_id,
        )
    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("P3 invocation context is stale")
    coordinate = analyze_coordinate(proof_ir)
    contributions = tuple(
        producer(proof_ir, coordinate, invocation) for producer in producers
    )
    applications = aggregate_applications(contributions)
    handoff = (
        None
        if proof_ir.attempted_operation is None
        else proof_ir.attempted_operation.recovery_handoff
    )
    recovery_claims = complete_recovery_claims(proof_ir, tuple(
        claim
        for contribution in contributions
        if handoff is None or _formed_recovery_result(contribution)
        for claim in contribution.recovery_claims
    ))
    return AnalyzedProofState(
        state_ref=proof_ir.state_ref,
        provenance=derived_provenance(
            "p3.analysis", proof_ir.state_ref, proof_ir.provenance
        ),
        coordinate=coordinate,
        attempted_operation=proof_ir.attempted_operation,
        resources=aggregate_resource_assessments(contributions),
        bindings=aggregate_bindings(contributions),
        applications=applications,
        application_applicabilities=tuple(
            item
            for contribution in contributions
            for item in contribution.application_applicabilities
        ),
        scope=tuple(
            item for contribution in contributions for item in contribution.scope
        ),
        boundary_contracts=tuple(
            item
            for contribution in contributions
            for item in contribution.boundary_contracts
        ),
        transforms=tuple(
            item for contribution in contributions for item in contribution.transforms
        ),
        diagnostics=tuple(
            item for contribution in contributions for item in contribution.diagnostics
        ),
        recovery_action_realizations=tuple(
            item
            for contribution in contributions
            for item in contribution.recovery_action_realizations
        ),
        recovery_claims=recovery_claims,
        recovery_ownership=resolve_recovery_ownership(
            proof_ir,
            invocation,
            recovery_claims,
        ),
    )


def _formed_recovery_result(contribution: AnalysisContribution) -> bool:
    """A delegated compound suffix owns the handoff only with a P3 result."""

    return bool(
        contribution.applications
        or contribution.diagnostics
        or contribution.recovery_action_realizations
    )
