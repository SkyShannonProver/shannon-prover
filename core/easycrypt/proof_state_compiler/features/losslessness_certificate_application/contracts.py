"""Feature-local identity and strategy contracts for frozen M05."""

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    EvidenceRef,
    ProofResource,
    ROUTE_SELECTING,
    StrategyContract,
)


LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID = (
    "losslessness_certificate_application"
)
LOSSLESSNESS_CERTIFICATE_NATIVE_PRODUCER_ID = (
    "losslessness_certificate_application.native_application"
)
LOSSLESSNESS_CERTIFICATE_ANALYSIS_PRODUCER_ID = (
    "losslessness_certificate_application.native_binding"
)
LOSSLESSNESS_CERTIFICATE_APPLICATION_CERTIFICATION_POLICY = (
    "exact_tactic_preflight"
)
LOSSLESSNESS_CERTIFICATE_APPLICATION_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=ROUTE_SELECTING,
    rationale=(
        "proactive exposure selects a losslessness-certificate reduction "
        "before an explicit agent commitment"
    ),
    introduced_choice="losslessness_certificate_application",
)


@dataclass(frozen=True)
class LosslessnessApplicationSketch:
    """One bounded lexical candidate awaiting native EasyCrypt authority."""

    resource: ProofResource
    target_procedure: str
    application_term: str
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if not self.target_procedure or not self.application_term:
            raise ValueError("M05 candidate sketch is incomplete")
        if not self.evidence_refs:
            raise ValueError("M05 candidate sketch requires evidence")
