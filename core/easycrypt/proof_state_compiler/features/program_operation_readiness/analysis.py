"""P3 structural legality for the one visible program operation frontier."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    EXPLANATION_ONLY,
    StructuredDiagnostic,
    CompilerInvocationContext,
    ProofCoordinate,
    ProofIR,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness.contracts import (
    ProgramOperationReadiness,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
PROGRAM_OPERATION_READINESS_PRODUCER_ID = "program_operation_readiness.analysis"
_OPERATION_BY_KIND = {"call": "call", "sample": "rnd", "while": "while"}


def analyze_program_operation_readiness(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    forward = coordinate.forward_frontier
    active = coordinate.tactic_active_boundary
    if coordinate.status != "known" or forward is None or active is None:
        return AnalysisContribution()
    operation = _OPERATION_BY_KIND.get(forward.kind)
    if operation is None:
        return AnalysisContribution()
    boundary = f"({active.position}) {active.text}"
    active_operation = _OPERATION_BY_KIND.get(active.kind)
    if active_operation == operation:
        readiness = ProgramOperationReadiness(
            operation=operation,
            status="legal",
            tactic_active_boundary=boundary,
            evidence_refs=coordinate.evidence_refs,
        )
        message = (
            f"{readiness.operation} is structurally legal at tactic-active "
            f"boundary {readiness.tactic_active_boundary}."
        )
    else:
        blocker = (
            f"tactic-active boundary is {active.kind} statement "
            f"{boundary}"
        )
        readiness = ProgramOperationReadiness(
            operation=operation,
            status="blocked",
            tactic_active_boundary=boundary,
            blocker=blocker,
            evidence_refs=coordinate.evidence_refs,
        )
        message = (
            f"{readiness.operation} is structurally blocked: "
            f"{readiness.blocker}."
        )
    return AnalysisContribution(diagnostics=(StructuredDiagnostic(
        producer_id=PROGRAM_OPERATION_READINESS_PRODUCER_ID,
        code="program_operation_readiness",
        primary=message,
        notes=(),
        help="",
        applicability=EXPLANATION_ONLY,
        evidence_refs=readiness.evidence_refs,
    ),))
