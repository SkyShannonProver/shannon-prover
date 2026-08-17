"""Read-only structured adapters over the installed EasyCrypt native library."""

from core.easycrypt.native_semantics.companion import NativeCompanionIdentity
from core.easycrypt.native_semantics.semantic_adapter import (
    NATIVE_SEMANTIC_PROTOCOL_VERSION,
    NativeSemanticBatchRequest,
    NativeSemanticBatchResult,
    NativeSemanticQuery,
    NativeSemanticResult,
    run_native_semantic_batch,
    validate_attempt_descriptor,
    validate_pure_tail_rewrite_descriptor,
    validate_intro_pattern_realization_descriptor,
    validate_application_syntax_repair_descriptor,
    validate_application_head_descriptor,
    validate_native_query_payload,
    validate_proof_term_descriptor,
    validate_selected_application_binding_set_descriptor,
    validate_tactic_prefix_descriptor,
)
from core.easycrypt.native_semantics.state_projection_adapter import (
    NativeStateProjectionRequest,
    NativeStateProjectionResult,
    run_native_state_projection,
    validate_native_projection,
)

__all__ = [
    "NATIVE_SEMANTIC_PROTOCOL_VERSION",
    "NativeCompanionIdentity",
    "NativeSemanticBatchRequest",
    "NativeSemanticBatchResult",
    "NativeSemanticQuery",
    "NativeSemanticResult",
    "run_native_semantic_batch",
    "validate_attempt_descriptor",
    "validate_pure_tail_rewrite_descriptor",
    "validate_intro_pattern_realization_descriptor",
    "validate_application_syntax_repair_descriptor",
    "validate_application_head_descriptor",
    "validate_native_query_payload",
    "validate_proof_term_descriptor",
    "validate_selected_application_binding_set_descriptor",
    "validate_tactic_prefix_descriptor",
    "NativeStateProjectionRequest",
    "NativeStateProjectionResult",
    "run_native_state_projection",
    "validate_native_projection",
]
