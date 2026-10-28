"""Native relation-bridge realizations of one written intermediate.

Owned by this slice.  The companion's ``relation_bridge_realization``
realizers emit the payloads (one certificate, or the strict-goal choices);
this module types them, and its codecs check that each realizes the attempt
it arrived with.
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

RELATION_BRIDGE_KIND = "relation_bridge_realization.bridge"
RELATION_BRIDGE_CHOICE_KIND = "relation_bridge_realization.choice"
_BRIDGE_FIELDS = frozenset({
    "source_operation",
    "relation_family",
    "intermediate_text",
    "intermediate_type",
    "candidate_tactic",
    "source_target_present",
    "source_target_convertible_to_current_goal",
    "source_target_right_convertible_to_current_right",
})
_CHOICE_FIELDS = frozenset({
    "source_operation",
    "relation_family",
    "goal_left_text",
    "intermediate_text",
    "goal_right_text",
    "intermediate_type",
    "choices",
})


@dataclass(frozen=True)
class NativeRelationBridgeDescriptor:
    """Native-established realization of one agent-written intermediate."""

    source_operation: str
    relation_family: str
    intermediate_text: str
    intermediate_type: str
    candidate_tactic: str
    failure_kind: str
    source_target_present: bool
    source_target_convertible_to_current_goal: bool
    source_target_right_convertible_to_current_right: bool

    def __post_init__(self) -> None:
        if (
            self.source_operation not in {"transitivity", "change"}
            or self.relation_family not in {"real_le", "int_le"}
            or type(self.intermediate_text) is not str
            or not self.intermediate_text
            or type(self.candidate_tactic) is not str
            or not self.candidate_tactic.endswith(".")
            or not self.failure_kind
        ):
            raise ValueError("native relation-bridge descriptor is incomplete")
        expected_type, certificate_family = {
            "real_le": ("real", "ler_trans"),
            "int_le": ("int", "Int.lez_trans"),
        }[self.relation_family]
        expected_failure = {
            "transitivity": "formula_transitivity_surface_mismatch",
            "change": "change_target_not_convertible",
        }[self.source_operation]
        if (
            self.failure_kind != expected_failure
            or self.intermediate_type != expected_type
            or self.candidate_tactic
            != (
                f"apply ({certificate_family} {self.intermediate_text}); "
                "first last."
            )
            or (
                self.relation_family == "int_le"
                and self.source_operation != "transitivity"
            )
        ):
            raise ValueError("native relation-bridge certificate is invalid")
        booleans = (
            self.source_target_present,
            self.source_target_convertible_to_current_goal,
            self.source_target_right_convertible_to_current_right,
        )
        if any(type(value) is not bool for value in booleans):
            raise TypeError("native relation-bridge flags must be booleans")
        if self.source_operation == "transitivity" and any(booleans):
            raise ValueError("transitivity sketch cannot claim a change target")
        if self.source_operation == "change" and (
            not self.source_target_present
            or self.source_target_convertible_to_current_goal
            or not self.source_target_right_convertible_to_current_right
        ):
            raise ValueError("change bridge requires one non-convertible target")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativeRelationBridgeDescriptor":
        payload = realization_fields(realization, _BRIDGE_FIELDS)
        return cls(
            source_operation=payload["source_operation"],
            relation_family=payload["relation_family"],
            intermediate_text=payload["intermediate_text"],
            intermediate_type=payload["intermediate_type"],
            candidate_tactic=payload["candidate_tactic"],
            failure_kind=realization.failure_kind,
            source_target_present=payload["source_target_present"],
            source_target_convertible_to_current_goal=(
                payload["source_target_convertible_to_current_goal"]
            ),
            source_target_right_convertible_to_current_right=(
                payload["source_target_right_convertible_to_current_right"]
            ),
        )


@dataclass(frozen=True)
class NativeRelationBridgeChoice:
    """One native-checked interpretation of a preserved strict bridge."""

    certificate_family: str
    left_relation: str
    right_relation: str
    candidate_tactic: str

    def __post_init__(self) -> None:
        if (
            self.certificate_family not in {
                "ler_lt_trans", "ltr_le_trans", "ltr_trans"
            }
            or self.left_relation not in {"<", "<="}
            or self.right_relation not in {"<", "<="}
            or not self.candidate_tactic.endswith(".")
        ):
            raise ValueError("native relation-bridge choice is incomplete")


@dataclass(frozen=True)
class NativeRelationBridgeChoiceDescriptor:
    """Native-established alternatives when one strict bridge is ambiguous."""

    source_operation: str
    relation_family: str
    goal_left_text: str
    intermediate_text: str
    goal_right_text: str
    intermediate_type: str
    failure_kind: str
    choices: tuple[NativeRelationBridgeChoice, ...]

    def __post_init__(self) -> None:
        if any(type(value) is not str or not value for value in (
            self.goal_left_text, self.intermediate_text, self.goal_right_text,
        )):
            raise ValueError("native relation-choice text is incomplete")
        if (
            self.source_operation != "transitivity"
            or self.relation_family != "real_lt"
            or self.intermediate_type != "real"
            or self.failure_kind != "formula_transitivity_surface_mismatch"
        ):
            raise ValueError(
                "native relation-bridge choice descriptor is incomplete"
            )
        expected = (
            ("ler_lt_trans", "<=", "<"),
            ("ltr_le_trans", "<", "<="),
            ("ltr_trans", "<", "<"),
        )
        observed = tuple(
            (item.certificate_family, item.left_relation, item.right_relation)
            for item in self.choices
        )
        if observed != expected or any(
            item.candidate_tactic
            != (
                f"apply ({item.certificate_family} "
                f"{self.intermediate_text}); first last."
            )
            for item in self.choices
        ):
            raise ValueError("native strict relation choices are not canonical")

    @classmethod
    def from_realization(
        cls, realization: AttemptRealization
    ) -> "NativeRelationBridgeChoiceDescriptor":
        payload = realization_fields(realization, _CHOICE_FIELDS)
        choices = payload["choices"]
        if type(choices) is not list or any(
            type(item) is not dict or set(item) != {
                "certificate_family",
                "left_relation",
                "right_relation",
                "candidate_tactic",
            }
            for item in choices
        ):
            raise ValueError("native relation choice fields are invalid")
        return cls(
            source_operation=payload["source_operation"],
            relation_family=payload["relation_family"],
            goal_left_text=payload["goal_left_text"],
            intermediate_text=payload["intermediate_text"],
            goal_right_text=payload["goal_right_text"],
            intermediate_type=payload["intermediate_type"],
            failure_kind=realization.failure_kind,
            choices=tuple(
                NativeRelationBridgeChoice(
                    certificate_family=item["certificate_family"],
                    left_relation=item["left_relation"],
                    right_relation=item["right_relation"],
                    candidate_tactic=item["candidate_tactic"],
                )
                for item in choices
            ),
        )


def _without_resource(attempt: NativeAttemptedOperationDescriptor) -> bool:
    return (
        not attempt.exact_resource
        and attempt.proof_term is None
        and attempt.application_head is None
    )


def _read_bridge(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativeRelationBridgeDescriptor:
    descriptor = NativeRelationBridgeDescriptor.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != descriptor.source_operation
        or not _without_resource(attempt)
    ):
        raise ValueError("native relation bridge does not realize its attempt")
    return descriptor


def _read_choice(
    attempt: NativeAttemptedOperationDescriptor,
) -> NativeRelationBridgeChoiceDescriptor:
    descriptor = NativeRelationBridgeChoiceDescriptor.from_realization(
        attempt.realization
    )
    if (
        attempt.operation_family != descriptor.source_operation
        or not _without_resource(attempt)
    ):
        raise ValueError("native relation choice does not realize its attempt")
    return descriptor


RELATION_BRIDGE_CODECS = (
    RealizationCodec(RELATION_BRIDGE_KIND, _read_bridge),
    RealizationCodec(RELATION_BRIDGE_CHOICE_KIND, _read_choice),
)


def relation_bridge_of(
    attempt: CarriesRealization | None,
) -> NativeRelationBridgeDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, RELATION_BRIDGE_KIND)
    if realization is None:
        return None
    return NativeRelationBridgeDescriptor.from_realization(realization)


def relation_bridge_choice_of(
    attempt: CarriesRealization | None,
) -> NativeRelationBridgeChoiceDescriptor | None:
    """The typed realization if ``attempt`` carries this slice's kind."""

    realization = attempt_realization(attempt, RELATION_BRIDGE_CHOICE_KIND)
    if realization is None:
        return None
    return NativeRelationBridgeChoiceDescriptor.from_realization(realization)
