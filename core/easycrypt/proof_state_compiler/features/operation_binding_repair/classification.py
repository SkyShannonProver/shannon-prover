"""Feature-local B1/B2/B4 classification over native attempt descriptors."""

from core.easycrypt.proof_state_compiler.contracts import AttemptedOperationIR


_B1_NATIVE_FAILURES = frozenset({
    "lookup_failure",
    "proof_term_lookup_failure",
    "proof_term_native_user_error",
})
_B2_NATIVE_FAILURES = frozenset({
    "application_module_argument_syntax",
    "cannot_infer_module",
    "invalid_module_argument",
})
_B4_NATIVE_FAILURES = frozenset({
    "wrong_argument_kind",
    "not_functional",
    "formula_type_mismatch",
    "invalid_formula_argument",
    "proof_argument_mismatch",
})
_CALL_APPLICABILITY_FAILURE = "call_applicability_failure"


def classify_operation_binding_failure(
    attempted: AttemptedOperationIR | None,
) -> str | None:
    if attempted is None or attempted.operation_family not in {
        "apply", "exact", "call", "conseq"
    } or not attempted.exact_resource:
        return None
    kind = attempted.native_failure_kind
    head = attempted.application_head_descriptor
    if attempted.native_diagnostic_status == "no_blocker":
        return None
    if attempted.native_diagnostic_status == "indeterminate":
        if head is None:
            return None
        remaining = head.slots[len(head.input_arguments):]
        if any(slot.kind == "module" for slot in remaining):
            return "B2"
        return "B4" if remaining else None
    if kind in _B1_NATIVE_FAILURES:
        return "B1"
    if kind in _B2_NATIVE_FAILURES:
        return "B2"
    if kind in _B4_NATIVE_FAILURES:
        return "B4"
    # EasyCrypt's call tactic owns a broader applicability check than proof
    # term elaboration, so its execution boundary deliberately reports one
    # opaque call-specific blocker.  Two explicit holes are the historical
    # bounded sketch.  A bare selected head is equally bounded only when the
    # native head descriptor proves that its first remaining slot is a module;
    # resource discovery must still establish the supported losslessness
    # certificate shape before exact unchanged-state preflight admits repair.
    if (
        kind == _CALL_APPLICABILITY_FAILURE
        and attempted.operation_family == "call"
    ):
        if attempted.parsed_arguments == ("hole", "hole"):
            return "B2"
        remaining = (
            () if head is None
            else head.slots[len(head.input_arguments):]
        )
        if (
            not attempted.parsed_arguments
            and remaining
            and remaining[0].kind == "module"
        ):
            return "B2"
    # EasyCrypt represents some head lookup and placeholder failures as an
    # opaque TCEUser.  We never classify its printed message.  The native head
    # result supplies the discriminant instead: no resolved head is B1; a
    # resolved under-supplied module slot is B2; other under-supplied slots are
    # B4.  Exact preflight still owns whether any correction is admissible.
    if kind == "native_user_error" and head is None:
        return "B1"
    if kind == "native_user_error" and head is not None:
        remaining = head.slots[len(head.input_arguments):]
        if any(slot.kind == "module" for slot in remaining):
            return "B2"
        if remaining:
            return "B4"
    return None
