"""P3 middle end: coordinate, resource, and binding analyses."""

from core.easycrypt.proof_state_compiler.middle_end.analysis_pipeline import analyze_proof_ir
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
    AnalysisProducer,
)
from core.easycrypt.proof_state_compiler.middle_end.native_dependencies import (
    NativeSemanticProducerBinding,
    NativeSemanticRequestProducer,
    plan_native_semantics,
)

__all__ = [
    "AnalysisContribution",
    "AnalysisProducer",
    "NativeSemanticProducerBinding",
    "NativeSemanticRequestProducer",
    "analyze_proof_ir",
    "plan_native_semantics",
]
