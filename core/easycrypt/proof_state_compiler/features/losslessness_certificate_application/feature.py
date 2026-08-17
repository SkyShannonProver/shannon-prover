"""Registration bundle for exact losslessness-certificate application."""

from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.candidate_discovery import (
    plan_losslessness_native_application,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.contracts import (
    LOSSLESSNESS_CERTIFICATE_APPLICATION_CERTIFICATION_POLICY,
    LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,
    LOSSLESSNESS_CERTIFICATE_APPLICATION_STRATEGY_CONTRACT,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.native_binding import (
    analyze_native_losslessness_application,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.resource_discovery import (
    discover_losslessness_resources,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application.surface_lowering import (
    lower_losslessness_certificate_action,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


LOSSLESSNESS_CERTIFICATE_APPLICATION_EXPERIMENT_ID = (
    "losslessness-certificate-route-v1"
)


def losslessness_certificate_application_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,
        gate=ExperimentGate(
            status="hold",
            evidence_ledger_ids=("M05",),
            experiment_id=LOSSLESSNESS_CERTIFICATE_APPLICATION_EXPERIMENT_ID,
        ),
        correctness_contract=(
            "exact true-to-true one-sided phoare [=] 1%r goal; active tail is "
            "one call; exactly one structurally unified loaded certificate"
        ),
        provenance_contract=(
            "current authoritative goal event plus hash-checked loaded "
            "declaration; exposure requires same-state EasyCrypt preflight"
        ),
        native_semantic_dependencies=(
            "NativeProofStateSnapshot",
            "NativeProofTermDescriptor",
        ),
        shannon_delta_contract=(
            "frozen M05 eligibility, one bounded certificate/module candidate, "
            "one allowed residual proof premise, and optional delivery"
        ),
        lexical_prefilter_contract=(
            "hash-bound declaration text narrows one certificate/module "
            "candidate only; it never authorizes a slot or application"
        ),
        required_ir_capabilities=(
            "GoalIR",
            "ProgramStatement.procedure",
            "ProofFact",
            "ProofResource.procedure_certificate",
            "ApplicationSignature",
            "ArgumentSlot.module",
            "SlotResolution",
            "ApplicationCandidate",
            "NativeSemanticRequest.proof_term_elaboration",
            "NativeProofTermDescriptor",
        ),
        certification_policy=(
            LOSSLESSNESS_CERTIFICATE_APPLICATION_CERTIFICATION_POLICY
        ),
        strategy_contracts=(
            LOSSLESSNESS_CERTIFICATE_APPLICATION_STRATEGY_CONTRACT,
        ),
    )


def losslessness_certificate_application_feature() -> FeatureDefinition:
    return FeatureDefinition(
        spec=losslessness_certificate_application_feature_spec(),
        resource_discoverers=(discover_losslessness_resources,),
        native_semantic_request_producers=(
            plan_losslessness_native_application,
        ),
        analysis_producers=(analyze_native_losslessness_application,),
        surface_lowerers=(lower_losslessness_certificate_action,),
    )
