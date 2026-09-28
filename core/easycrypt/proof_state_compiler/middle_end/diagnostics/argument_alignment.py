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
        # With implicit arguments on, EasyCrypt inserts inferred formula
        # arguments before the written ones of an implicit-mode
        # `apply`/`exact`, so written positions are not slot positions.
        # Module, memory and proof binders are never implicit.
        or (
            attempted.operation_family in {"apply", "exact"}
            and head.input_mode == "implicit"
            and head.implicits_enabled
            and any(slot.kind == "formula" for slot in head.slots)
        )
        # EasyCrypt unfolds the result into further products, so the listed
        # slots are not all the arguments it takes.
        or head.unfolds_to_more_slots
        or not _rejection_agrees_with_layout(
            head.slots,
            head.input_arguments,
            attempted.native_failure_kind,
        )
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
    """Return whether concrete input certainly contradicts its ordered slot.

    An explicit hole is compatible with every slot because it selects no
    value.  Missing trailing arguments are likewise an inference request, not
    an alignment mismatch.  EasyCrypt's parser reports every plain term
    argument as a formula, even a hypothesis name, a lemma application or a
    module name that the elaborator then uses as a proof or module, so formula
    syntax is a mismatch only at the argument EasyCrypt itself rejected
    (``rejected``).  The slots are read without unfolding definitions while
    EasyCrypt unfolds to find further products, so an argument beyond them is
    a mismatch only when EasyCrypt rejected it too.  An explicit proof, module
    or memory argument in another kind of slot always is.
    """

    return any(
        not _may_inhabit(argument, slots) for argument in arguments
    )


def _may_inhabit(
    argument: NativeInputArgument,
    slots: tuple[NativeApplicationSlotDescriptor, ...],
) -> bool:
    if argument.position > len(slots):
        return not argument.rejected
    if argument.syntax_kind == "hole":
        return True
    if argument.syntax_kind == "formula":
        return not argument.rejected
    return _syntax_fits(argument, slots[argument.position - 1])


def _syntax_fits(
    argument: NativeInputArgument,
    slot: NativeApplicationSlotDescriptor,
) -> bool:
    if argument.syntax_kind in {"hole", "formula"}:
        return argument.syntax_kind == "hole" or slot.kind == "formula"
    if slot.kind == "proof":
        return argument.syntax_kind in {"proof", "proof_tactic"}
    return argument.syntax_kind == slot.kind


def _rejection_agrees_with_layout(
    slots: tuple[NativeApplicationSlotDescriptor, ...],
    arguments: tuple[NativeInputArgument, ...],
    native_failure_kind: str,
) -> bool:
    """A native rejection must be explainable by the slot layout shown.

    EasyCrypt rejects an argument either for its kind within the products or
    because no product is left.  A rejected argument whose syntax fits its
    slot, or a failure kind that names the other reason, means the written
    positions do not line up with these slots, so nothing is said.
    """

    rejected = tuple(argument for argument in arguments if argument.rejected)
    if not rejected:
        return True
    (argument,) = rejected
    beyond = argument.position > len(slots)
    # Products coincide with the slots up to the first rejected argument, so
    # a rejection further out means EasyCrypt found products not listed.
    if argument.position > len(slots) + 1:
        return False
    if native_failure_kind == "not_functional" and not beyond:
        return False
    if native_failure_kind == "wrong_argument_kind" and beyond:
        return False
    return beyond or not _syntax_fits(argument, slots[argument.position - 1])


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
        # The parser kind of a plain name is not its role (see above), so
        # names are listed without a kind label.
        rows.append(f"{argument.position}. `{spelling}`")
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
        if _may_inhabit(argument, slots):
            continue
        if argument.position > len(slots):
            return (
                f"Argument {argument.position} has no corresponding theorem "
                "slot."
            )
        slot = slots[argument.position - 1]
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
