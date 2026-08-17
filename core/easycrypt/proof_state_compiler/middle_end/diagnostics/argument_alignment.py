"""Bounded argument-layout diagnostics from one native theorem head.

This module never proposes a binding.  It reports only the ordered slots that
EasyCrypt exposed and the syntactic argument kinds that EasyCrypt parsed from
the agent's selected application.  Applicability and exact correction remain
separate, stronger results.
"""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    EXPLANATION_ONLY,
    AttemptedOperationIR,
    NativeApplicationSlotDescriptor,
    NativeInputArgument,
    StructuredDiagnostic,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_state_reference,
)


def structured_application_argument_alignment_diagnostic(
    attempted: AttemptedOperationIR,
    *,
    producer_id: str,
) -> StructuredDiagnostic | None:
    """Explain an unresolved selected application without choosing a repair.

    The caller must already have failed to establish either a unique checked
    completion or a stronger current-state applicability result.  Consequently
    this diagnostic leads with that fact and treats the slot layout as
    explanatory evidence only; it is never a placeholder promise.
    """

    head = attempted.application_head_descriptor
    if (
        head is None
        or not producer_id
        or not attempted.exact_resource
        or attempted.operation_family
        not in {"apply", "exact", "call", "conseq"}
        or not head.slots
        or not head.input_arguments
        or not application_arguments_misaligned(
            head.slots, head.input_arguments
        )
    ):
        return None
    expected = _expected_arguments(head.slots)
    supplied = _supplied_arguments_list(head.input_arguments)
    mismatch = _first_mismatch(head.slots, head.input_arguments)
    if not expected or not supplied or not mismatch:
        return None
    label = attempted.exact_resource
    handoff = attempted.recovery_handoff
    state_context = checked_state_reference(handoff)
    standalone_result = (
        "\n\nThe proof state is unchanged. The compiler preserved your "
        "argument order and selected no replacement theorem."
        if handoff is None
        else ""
    )
    try:
        return StructuredDiagnostic(
            producer_id=producer_id,
            code="selected_application_argument_layout",
            primary=(
                f"`{label}` expects arguments in this order:\n\n"
                + expected
                + "\n\nYou supplied:\n\n"
                + supplied
                + "\n\n"
                + mismatch
                + "\n\nThe compiler preserved your concrete argument in its "
                "original position and did not reinterpret it as a different "
                "theorem argument. This "
                f"`{attempted.operation_family}` application did not succeed "
                f"in {state_context}."
                + standalone_result
            ),
            notes=(),
            help="",
            applicability=EXPLANATION_ONLY,
            evidence_refs=attempted.evidence_refs,
            trigger_id=attempted.trigger_id,
        )
    except ValueError:
        # Exact native terms are omitted rather than truncated into misleading
        # fragments.  If the bounded representation still does not fit, the
        # diagnostic is not agent-facing.
        return None


def application_arguments_misaligned(
    slots: tuple[NativeApplicationSlotDescriptor, ...],
    arguments: tuple[NativeInputArgument, ...],
) -> bool:
    """Return whether concrete input contradicts its current ordered slot.

    An explicit hole is compatible with every slot because it selects no
    value.  Missing trailing arguments are likewise an inference request, not
    an alignment mismatch.  Extra arguments or a concrete syntactic kind that
    cannot inhabit its current slot are mismatches.
    """

    for argument in arguments:
        if argument.position > len(slots):
            return True
        if argument.syntax_kind == "hole":
            continue
        slot = slots[argument.position - 1]
        if slot.kind == "proof":
            if argument.syntax_kind not in {"proof", "proof_tactic"}:
                return True
        elif argument.syntax_kind != slot.kind:
            return True
    return False


def _expected_arguments(
    slots: tuple[NativeApplicationSlotDescriptor, ...],
) -> str:
    rows = []
    for slot in slots[:4]:
        detail = _slot_expectation(slot)
        if not detail:
            return ""
        rows.append(f"{slot.position}. {detail}")
    if len(slots) > len(rows):
        rows.append(f"{len(rows) + 1}. plus {len(slots) - len(rows)} more")
    return "\n".join(rows)


def _slot_expectation(slot: NativeApplicationSlotDescriptor) -> str:
    if slot.kind == "proof" and slot.formula is not None:
        formula = _bounded_exact_text(slot.formula.text)
        return f"a proof of `{formula}`" if formula else ""
    type_text = _bounded_exact_text(slot.type_text)
    if not type_text:
        return ""
    if slot.kind == "module":
        name = _bounded_exact_text(slot.name)
        return (
            f"`{name}` with module type `{type_text}`"
            if name
            else f"a module with type `{type_text}`"
        )
    name = _bounded_exact_text(slot.name)
    return (
        f"`{name}` with {slot.kind} type `{type_text}`"
        if name
        else f"a {slot.kind} with type `{type_text}`"
    )


def _supplied_arguments_list(
    arguments: tuple[NativeInputArgument, ...],
) -> str:
    rows = []
    for argument in arguments[:4]:
        spelling = _bounded_exact_text(argument.source_spelling)
        if not spelling:
            return ""
        rows.append(
            f"{argument.position}. {argument.syntax_kind} `{spelling}`"
        )
    if len(arguments) > len(rows):
        rows.append(
            f"{len(rows) + 1}. plus {len(arguments) - len(rows)} more"
        )
    return "\n".join(rows)


def _first_mismatch(
    slots: tuple[NativeApplicationSlotDescriptor, ...],
    arguments: tuple[NativeInputArgument, ...],
) -> str:
    for argument in arguments:
        if argument.position > len(slots):
            return (
                f"Argument {argument.position} has no corresponding theorem "
                "slot."
            )
        if argument.syntax_kind == "hole":
            continue
        slot = slots[argument.position - 1]
        compatible = (
            argument.syntax_kind in {"proof", "proof_tactic"}
            if slot.kind == "proof"
            else argument.syntax_kind == slot.kind
        )
        if not compatible:
            return (
                f"Argument {argument.position} is a "
                f"{argument.syntax_kind}, but slot {slot.position} requires "
                f"a {slot.kind}."
            )
    return ""


def _bounded_exact_text(value: str, *, max_bytes: int = 120) -> str:
    value = value.strip()
    if (
        not value
        or "\n" in value
        or "\r" in value
        or len(value.encode("utf-8")) > max_bytes
    ):
        return ""
    return value
