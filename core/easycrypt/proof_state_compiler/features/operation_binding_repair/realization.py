"""Native grammar realization of one selected call application.

Owned by this slice.  The companion's ``operation_binding_repair`` realizer
emits the payload; this module types it, and its codec checks that it
realizes the attempt it arrived with.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    CarriesRealization,
    AttemptRealization,
    NativeAttemptedOperationDescriptor,
    RealizationCodec,
    attempt_realization,
    realization_fields,
)

APPLICATION_SYNTAX_REPAIR_KIND = "operation_binding_repair.module_argument_syntax"
_FIELDS = frozenset({
    "source_operation",
    "selected_resource",
    "module_argument_position",
    "module_term_text",
    "candidate_application_term",
    "candidate_tactic",
    "candidate_argument_kinds",
    "resolved_candidate_count",
})


@dataclass(frozen=True)
class NativeApplicationSyntaxRepairDescriptor:
    """One native-resolved grammar realization of a selected application.

    The descriptor carries the native candidate, but feature-local admission
    must still reconstruct the exact source-to-candidate punctuation transform
    from the rejected tactic before using it.
    """

    source_operation: str
    selected_resource: str
    module_argument_position: int
    module_term_text: str
    candidate_application_term: str
    candidate_tactic: str
    candidate_argument_kinds: tuple[str, ...]
    failure_kind: str
    resolved_candidate_count: int

    def __post_init__(self) -> None:
        if any(type(value) is not str for value in (
            self.selected_resource,
            self.module_term_text,
            self.candidate_application_term,
            self.candidate_tactic,
        )) or any(
            type(item) is not str for item in self.candidate_argument_kinds
        ):
            raise ValueError("native application syntax repair is not text")
        marker = f"(<: {self.module_term_text})"
        if (
            self.source_operation != "call"
            or not self.selected_resource
            or self.module_argument_position != 1
            or not self.module_term_text
            or not self.candidate_application_term.startswith(
                self.selected_resource + " "
            )
            or marker not in self.candidate_application_term
            or self.candidate_tactic
            != f"call ({self.candidate_application_term})."
            or not self.candidate_argument_kinds
            or self.candidate_argument_kinds[0] != "module"
            or any(not item for item in self.candidate_argument_kinds)
            or self.failure_kind != "application_module_argument_syntax"
            or self.resolved_candidate_count != 1
            or any(
                token in self.candidate_tactic
                for token in (";", "\n", "\r", '"', "(*", "*)", "|")
            )
        ):
            raise ValueError("native application syntax repair is incomplete")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativeApplicationSyntaxRepairDescriptor":
        payload = realization_fields(realization, _FIELDS)
        argument_kinds = payload["candidate_argument_kinds"]
        if type(argument_kinds) is not list:
            raise ValueError("native application syntax arguments are invalid")
        return cls(
            source_operation=payload["source_operation"],
            selected_resource=payload["selected_resource"],
            module_argument_position=payload["module_argument_position"],
            module_term_text=payload["module_term_text"],
            candidate_application_term=payload["candidate_application_term"],
            candidate_tactic=payload["candidate_tactic"],
            candidate_argument_kinds=tuple(argument_kinds),
            failure_kind=realization.failure_kind,
            resolved_candidate_count=payload["resolved_candidate_count"],
        )


def _read(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativeApplicationSyntaxRepairDescriptor:
    descriptor = NativeApplicationSyntaxRepairDescriptor.from_realization(
        attempt.realization
    )
    # The realizer rebuilt the attempted call from EasyCrypt's own parse of
    # the punctuated candidate: same resource, native head, nothing else.
    if (
        attempt.operation_family != "call"
        or attempt.exact_resource != descriptor.selected_resource
        or attempt.proof_term is not None
        or attempt.application_head is None
        or not attempt.application_head.slots
        or attempt.application_head.slots[0].kind != "module"
        or tuple(
            item.syntax_kind
            for item in attempt.application_head.input_arguments
        ) != descriptor.candidate_argument_kinds
        or attempt.argument_kinds
        or attempt.side
        or attempt.positions
    ):
        raise ValueError(
            "native application syntax repair changed attempted identity"
        )
    return descriptor


APPLICATION_SYNTAX_REPAIR_CODEC = RealizationCodec(
    APPLICATION_SYNTAX_REPAIR_KIND, _read
)


def application_syntax_repair_of(
    attempt: CarriesRealization | None,
) -> NativeApplicationSyntaxRepairDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, APPLICATION_SYNTAX_REPAIR_KIND)
    if realization is None:
        return None
    return NativeApplicationSyntaxRepairDescriptor.from_realization(realization)
