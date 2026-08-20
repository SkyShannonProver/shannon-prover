"""Feature-neutral P3 dependency contracts for native EasyCrypt semantics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import (
    ProvenanceRef,
    StateRef,
)


NATIVE_PROOF_TERM_ELABORATION = "proof_term_elaboration"
NATIVE_ATTEMPT_DIAGNOSTIC = "attempt_diagnostic"
NATIVE_TACTIC_PREFIX_DIAGNOSTIC = "tactic_prefix_diagnostic"
NATIVE_SELECTED_APPLICATION_BINDING_SET = "selected_application_binding_set"
NATIVE_SEMANTIC_QUERY_KINDS = frozenset({
    NATIVE_PROOF_TERM_ELABORATION,
    NATIVE_ATTEMPT_DIAGNOSTIC,
    NATIVE_TACTIC_PREFIX_DIAGNOSTIC,
    NATIVE_SELECTED_APPLICATION_BINDING_SET,
})
NATIVE_PRODUCTION_READY = "ready"
NATIVE_PRODUCTION_NOT_APPLICABLE = "not_applicable"
NATIVE_PRODUCTION_ABSTAINED = "abstained"
NATIVE_PRODUCTION_DISPOSITIONS = frozenset({
    NATIVE_PRODUCTION_READY,
    NATIVE_PRODUCTION_NOT_APPLICABLE,
    NATIVE_PRODUCTION_ABSTAINED,
})
MAX_NATIVE_CONSUMER_REQUESTS = 32
MAX_NATIVE_EXECUTION_UNITS = 8
MAX_NATIVE_BINDING_CANDIDATE_CHECKS = 4096
_PROOF_TERM_OPERATIONS = frozenset({"apply", "exact", "call", "conseq"})
_ATTEMPT_OPERATIONS = frozenset({
    "apply", "exact", "call", "conseq", "transitivity", "change", "eager",
    "rewrite", "intro_pattern",
})
NATIVE_TACTIC_PREFIX_EFFECTS = frozenset({
    "accepted_changed",
    "accepted_no_progress",
    "rejected",
})


def _valid_qualified_symbol(value: str) -> bool:
    return bool(value) and all(
        part
        and (part[0].isalpha() or part[0] == "_")
        and all(char.isalnum() or char in "_'" for char in part)
        for part in value.split(".")
    )


@dataclass(frozen=True)
class NativePlanningBudget:
    """One immutable native-work allocation shared by all active features.

    Consumer requests bound candidate materialization and fan-out bookkeeping.
    Execution units bound actual EasyCrypt boundary crossings after identical
    requests have been coalesced.  The two limits are deliberately distinct.
    """

    max_consumer_requests: int = MAX_NATIVE_CONSUMER_REQUESTS
    max_execution_units: int = MAX_NATIVE_EXECUTION_UNITS
    used_consumer_requests: int = 0
    used_execution_units: int = 0

    def __post_init__(self) -> None:
        values = (
            self.max_consumer_requests,
            self.max_execution_units,
            self.used_consumer_requests,
            self.used_execution_units,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("native planning budget values must be non-negative integers")
        if self.max_consumer_requests < 1 or self.max_execution_units < 1:
            raise ValueError("native planning budget requires positive limits")
        if self.max_consumer_requests > MAX_NATIVE_CONSUMER_REQUESTS:
            raise ValueError("native planning consumer limit exceeds the shared cap")
        if self.max_execution_units > MAX_NATIVE_EXECUTION_UNITS:
            raise ValueError("native planning execution limit exceeds the runtime cap")
        if self.used_consumer_requests > self.max_consumer_requests:
            raise ValueError("native planning consumer budget is overdrawn")
        if self.used_execution_units > self.max_execution_units:
            raise ValueError("native planning execution budget is overdrawn")

    @property
    def remaining_consumer_requests(self) -> int:
        return self.max_consumer_requests - self.used_consumer_requests

    @property
    def remaining_execution_units(self) -> int:
        return self.max_execution_units - self.used_execution_units

    def consume(self, plan: "NativeSemanticPlan") -> "NativePlanningBudget":
        if plan.budget != self:
            raise ValueError("native plan was not produced from this budget")
        return NativePlanningBudget(
            max_consumer_requests=self.max_consumer_requests,
            max_execution_units=self.max_execution_units,
            used_consumer_requests=(
                self.used_consumer_requests + len(plan.requests)
            ),
            used_execution_units=(
                self.used_execution_units + len(plan.execution_units)
            ),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "max_consumer_requests": self.max_consumer_requests,
            "max_execution_units": self.max_execution_units,
            "used_consumer_requests": self.used_consumer_requests,
            "used_execution_units": self.used_execution_units,
            "remaining_consumer_requests": self.remaining_consumer_requests,
            "remaining_execution_units": self.remaining_execution_units,
        }


@dataclass(frozen=True)
class NativeModuleTermDescriptor:
    """One EasyCrypt-owned module term used in a semantic boundary."""

    term: str
    top_kind: str
    top_identity: str
    arguments: tuple["NativeModuleTermDescriptor", ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.term
            or self.top_kind not in {"local", "concrete"}
            or not self.top_identity
        ):
            raise ValueError("native module term descriptor is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "term": self.term,
            "top_kind": self.top_kind,
            "top_identity": self.top_identity,
            "arguments": [item.to_payload() for item in self.arguments],
        }


@dataclass(frozen=True)
class NativeFormulaBoundaryDescriptor:
    """A typed, presentation-safe boundary selected by EasyCrypt."""

    role: str
    procedure_identity: str
    module: NativeModuleTermDescriptor

    def __post_init__(self) -> None:
        if (
            self.role != "relation_left_probability"
            or not self.procedure_identity
        ):
            raise ValueError("native formula boundary descriptor is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "role": self.role,
            "procedure_identity": self.procedure_identity,
            "module": self.module.to_payload(),
        }


@dataclass(frozen=True)
class NativeFormulaDescriptor:
    """Shallow typed formula/judgment descriptor owned by EasyCrypt."""

    kind: str
    text: str
    type_text: str
    procedure: str = ""
    comparison: str = ""
    lossless: bool | None = None
    boundary: NativeFormulaBoundaryDescriptor | None = None

    def __post_init__(self) -> None:
        if not self.kind or not self.text or not self.type_text:
            raise ValueError("native formula descriptor is incomplete")
        if self.lossless is not None and type(self.lossless) is not bool:
            raise ValueError("native formula lossless marker is invalid")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "kind": self.kind,
            "text": self.text,
            "type": self.type_text,
        }
        if self.procedure:
            payload["procedure"] = self.procedure
        if self.comparison:
            payload["comparison"] = self.comparison
        if self.lossless is not None:
            payload["lossless"] = self.lossless
        if self.boundary is not None:
            payload["boundary"] = self.boundary.to_payload()
        return payload


@dataclass(frozen=True)
class NativeResolvedHead:
    kind: str
    identity: str
    type_arguments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {"global", "local"} or not self.identity:
            raise ValueError("native resolved head is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "identity": self.identity,
            "type_arguments": list(self.type_arguments),
        }


@dataclass(frozen=True)
class NativeInputArgument:
    position: int
    syntax_kind: str
    explicit_hole: bool
    source_spelling: str = ""

    def __post_init__(self) -> None:
        if self.position < 1 or self.syntax_kind not in {
            "hole", "formula", "memory", "module", "proof", "proof_tactic"
        }:
            raise ValueError("native input argument is invalid")
        if self.explicit_hole is not (self.syntax_kind == "hole"):
            raise ValueError("native input hole marker is invalid")
        if self.source_spelling and (
            not _valid_qualified_symbol(self.source_spelling)
            or self.syntax_kind not in {"formula", "module"}
        ):
            raise ValueError("native input argument spelling is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "position": self.position,
            "syntax_kind": self.syntax_kind,
            "explicit_hole": self.explicit_hole,
            "source_spelling": self.source_spelling,
        }


@dataclass(frozen=True)
class NativeProofTermArgument:
    position: int
    kind: str
    hole: bool
    expected_name: str = ""
    expected_type: str = ""
    expected_formula: NativeFormulaDescriptor | None = None
    resolved_identity: str = ""
    resolved_formula: NativeFormulaDescriptor | None = None
    resolved_proof_head: NativeResolvedHead | None = None

    def __post_init__(self) -> None:
        if self.position < 1 or self.kind not in {
            "formula", "memory", "module", "proof"
        }:
            raise ValueError("native proof-term argument is invalid")
        if self.hole and self.kind != "proof":
            raise ValueError("native non-proof argument cannot remain a hole")
        if self.kind == "proof" and self.expected_formula is None:
            raise ValueError("native proof argument requires expected formula")
        if self.kind != "proof" and not self.expected_type:
            raise ValueError("native forall argument requires expected type")
        if self.kind == "formula" and (
            self.resolved_formula is None
            or self.resolved_identity
            or self.resolved_proof_head is not None
        ):
            raise ValueError("native formula argument value is invalid")
        if self.kind in {"memory", "module"} and (
            not self.resolved_identity
            or self.resolved_formula is not None
            or self.resolved_proof_head is not None
        ):
            raise ValueError(f"native {self.kind} argument value is invalid")
        if self.kind == "proof" and (
            (self.hole and self.resolved_proof_head is not None)
            or (not self.hole and self.resolved_proof_head is None)
            or (not self.hole and self.resolved_formula is not None)
            or self.resolved_identity
        ):
            raise ValueError("native proof argument value is invalid")

    def to_payload(self) -> dict[str, object]:
        actual: dict[str, object] = {"kind": self.kind, "hole": self.hole}
        if self.resolved_identity:
            actual["identity"] = self.resolved_identity
        if self.resolved_formula is not None:
            actual["formula"] = self.resolved_formula.to_payload()
        if self.resolved_proof_head is not None:
            actual["head"] = self.resolved_proof_head.to_payload()
        expected: dict[str, object] = {
            "kind": self.kind,
            "name": self.expected_name,
        }
        if self.expected_type:
            expected["type"] = self.expected_type
        if self.expected_formula is not None:
            expected["formula"] = self.expected_formula.to_payload()
        return {
            "position": self.position,
            "actual": actual,
            "expected": expected,
        }


@dataclass(frozen=True)
class NativeResidualProofPremise:
    argument_position: int
    formula: NativeFormulaDescriptor

    def __post_init__(self) -> None:
        if self.argument_position < 1:
            raise ValueError("native residual premise position is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "argument_position": self.argument_position,
            "formula": self.formula.to_payload(),
        }


@dataclass(frozen=True)
class NativeProofTermDescriptor:
    """Feature-neutral typed result of one bounded proof-term elaboration."""

    resolved_head: NativeResolvedHead
    input_mode: str
    input_arguments: tuple[NativeInputArgument, ...]
    explicit_hole_count: int
    implicit_argument_count: int
    arguments: tuple[NativeProofTermArgument, ...]
    can_concretize: bool
    residual_proof_premises: tuple[NativeResidualProofPremise, ...]
    result: NativeFormulaDescriptor
    result_convertible_to_current_goal: bool

    def __post_init__(self) -> None:
        if self.input_mode not in {"explicit", "implicit"}:
            raise ValueError("native proof-term input mode is invalid")
        if tuple(item.position for item in self.input_arguments) != tuple(
            range(1, len(self.input_arguments) + 1)
        ):
            raise ValueError("native input argument order is invalid")
        if self.explicit_hole_count != sum(
            item.explicit_hole for item in self.input_arguments
        ):
            raise ValueError("native explicit hole count is invalid")
        if self.implicit_argument_count < 0 or len(self.arguments) != (
            len(self.input_arguments) + self.implicit_argument_count
        ):
            raise ValueError("native elaborated argument count is invalid")
        if tuple(item.position for item in self.arguments) != tuple(
            range(1, len(self.arguments) + 1)
        ):
            raise ValueError("native elaborated argument order is invalid")
        residual_positions = {
            item.argument_position for item in self.residual_proof_premises
        }
        proof_holes = {
            item.position for item in self.arguments
            if item.kind == "proof" and item.hole
        }
        if residual_positions != proof_holes:
            raise ValueError("native residual premises disagree with proof holes")
        if self.can_concretize is not True:
            raise ValueError("native descriptor must be concretized")
        if type(self.result_convertible_to_current_goal) is not bool:
            raise TypeError(
                "native result/current-goal convertibility must be a bool"
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "resolved_head": self.resolved_head.to_payload(),
            "input_mode": self.input_mode,
            "input_arguments": [
                item.to_payload() for item in self.input_arguments
            ],
            "explicit_hole_count": self.explicit_hole_count,
            "implicit_argument_count": self.implicit_argument_count,
            "arguments": [item.to_payload() for item in self.arguments],
            "can_concretize": self.can_concretize,
            "residual_proof_premises": [
                item.to_payload() for item in self.residual_proof_premises
            ],
            "result": self.result.to_payload(),
            "result_convertible_to_current_goal": (
                self.result_convertible_to_current_goal
            ),
        }


@dataclass(frozen=True)
class NativeCheckedApplication:
    """One same-resource application accepted in the exact native state."""

    application_term: str
    candidate_tactic: str
    tactic_effect: str
    descriptor: NativeProofTermDescriptor

    def __post_init__(self) -> None:
        if (
            not self.application_term
            or self.application_term != self.application_term.strip()
            or self.tactic_effect != "accepted_changed"
            or not self.candidate_tactic.endswith(".")
        ):
            raise ValueError("native checked application is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "application_term": self.application_term,
            "candidate_tactic": self.candidate_tactic,
            "tactic_effect": self.tactic_effect,
            "descriptor": self.descriptor.to_payload(),
        }


@dataclass(frozen=True)
class NativeSelectedApplicationBindingSetDescriptor:
    """Bounded native search for arguments of one agent-selected theorem.

    The search population is a compiler-declared spelling inventory.  Native
    EasyCrypt owns module typing, restrictions, result/goal matching, and
    tactic preflight.  A complete small checked set may be shown to the agent;
    incomplete or oversized sets never expose an arbitrary prefix.
    """

    operation: str
    selected_resource: str
    resolved_head: NativeResolvedHead
    module_slot_count: int
    candidate_module_term_count: int
    candidate_check_count: int
    typed_binding_count: int
    checked_completion_count: int
    population_complete: bool
    checked_completions: tuple[NativeCheckedApplication, ...]
    reason: str = ""

    def __post_init__(self) -> None:
        if (
            self.operation not in {"apply", "exact"}
            or not self.selected_resource
            or self.module_slot_count < 1
            or self.candidate_module_term_count < 1
            or not 1 <= self.candidate_check_count <= (
                MAX_NATIVE_BINDING_CANDIDATE_CHECKS
            )
            or self.typed_binding_count < 0
            or self.checked_completion_count < 0
            or self.checked_completion_count > self.typed_binding_count
        ):
            raise ValueError("native selected-application binding set is invalid")
        if self.population_complete == bool(self.reason):
            raise ValueError("native binding-set completeness/reason is invalid")
        if not self.population_complete and (
            self.checked_completion_count or self.checked_completions
        ):
            raise ValueError("incomplete native binding set exposed a prefix")
        if self.population_complete and self.checked_completion_count <= 4:
            if len(self.checked_completions) != self.checked_completion_count:
                raise ValueError("small native binding set lost completions")
        elif self.checked_completions:
            raise ValueError("oversized native binding set exposed a prefix")
        terms = tuple(item.application_term for item in self.checked_completions)
        if terms != tuple(sorted(set(terms))):
            raise ValueError("native binding-set completions are not canonical")
        resource_tail = self.selected_resource.rsplit(".", 1)[-1]
        if self.resolved_head.identity.rsplit(".", 1)[-1] != resource_tail:
            raise ValueError("native binding set resolved another theorem")
        expected_prefix = self.operation + " ("
        if any(
            not item.candidate_tactic.startswith(expected_prefix)
            or item.candidate_tactic
            != f"{self.operation} ({item.application_term})."
            for item in self.checked_completions
        ):
            raise ValueError("native binding set changed the operation")
        if self.operation in {"apply", "exact"} and any(
            not item.descriptor.result_convertible_to_current_goal
            for item in self.checked_completions
        ):
            raise ValueError(
                "direct application binding does not match the current goal"
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "selected_resource": self.selected_resource,
            "resolved_head": self.resolved_head.to_payload(),
            "module_slot_count": self.module_slot_count,
            "candidate_module_term_count": self.candidate_module_term_count,
            "candidate_check_count": self.candidate_check_count,
            "typed_binding_count": self.typed_binding_count,
            "checked_completion_count": self.checked_completion_count,
            "population_complete": self.population_complete,
            "checked_completions": [
                item.to_payload() for item in self.checked_completions
            ],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class NativeApplicationSlotDescriptor:
    """One ordered argument slot exposed by an EasyCrypt proof-term head."""

    position: int
    kind: str
    name: str = ""
    type_text: str = ""
    formula: NativeFormulaDescriptor | None = None

    def __post_init__(self) -> None:
        if self.position < 1 or self.kind not in {
            "formula", "memory", "module", "proof"
        }:
            raise ValueError("native application slot is invalid")
        if self.kind == "proof":
            if (self.formula is None) == (not self.type_text):
                raise ValueError("native proof slot requires one typed shape")
            if self.type_text and self.type_text != "bool":
                raise ValueError("native proof slot has a non-proposition type")
        elif not self.type_text or self.formula is not None:
            raise ValueError("native forall slot requires one typed expectation")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "position": self.position,
            "kind": self.kind,
            "name": self.name,
        }
        if self.type_text:
            payload["type"] = self.type_text
        if self.formula is not None:
            payload["formula"] = self.formula.to_payload()
        return payload


@dataclass(frozen=True)
class NativeApplicationHeadDescriptor:
    """Typed shape of a selected proof-term head before concretization.

    This descriptor is deliberately weaker than ``NativeProofTermDescriptor``:
    it identifies the head and its ordered slots, but chooses no argument
    values and claims no application is valid.
    """

    resolved_head: NativeResolvedHead
    input_mode: str
    input_arguments: tuple[NativeInputArgument, ...]
    slots: tuple[NativeApplicationSlotDescriptor, ...]
    result: NativeFormulaDescriptor

    def __post_init__(self) -> None:
        if self.input_mode not in {"explicit", "implicit"}:
            raise ValueError("native application-head input mode is invalid")
        if tuple(item.position for item in self.input_arguments) != tuple(
            range(1, len(self.input_arguments) + 1)
        ):
            raise ValueError("native application-head input order is invalid")
        if tuple(item.position for item in self.slots) != tuple(
            range(1, len(self.slots) + 1)
        ):
            raise ValueError("native application-head slot order is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "resolved_head": self.resolved_head.to_payload(),
            "input_mode": self.input_mode,
            "input_arguments": [
                item.to_payload() for item in self.input_arguments
            ],
            "slots": [item.to_payload() for item in self.slots],
            "result": self.result.to_payload(),
        }


@dataclass(frozen=True)
class NativeProofTermElaborationQuery:
    operation: str
    application_term: str

    def __post_init__(self) -> None:
        if self.operation not in _PROOF_TERM_OPERATIONS:
            raise ValueError("unsupported native proof-term operation")
        if (
            not self.application_term
            or self.application_term != self.application_term.strip()
        ):
            raise ValueError("native proof-term query requires exact application")

    @property
    def query_kind(self) -> str:
        return NATIVE_PROOF_TERM_ELABORATION

    def to_payload(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "application_term": self.application_term,
        }


@dataclass(frozen=True)
class NativeSelectedApplicationBindingSetQuery:
    """One bounded spelling pool for a selected proof-term operation."""

    operation: str
    selected_resource: str
    module_candidates: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.operation not in {"apply", "exact"}:
            raise ValueError("native binding-set operation is invalid")
        if not _valid_qualified_symbol(self.selected_resource):
            raise ValueError("native binding set requires an exact resource")
        if (
            not self.module_candidates
            or len(self.module_candidates) > 96
            or self.module_candidates != tuple(sorted(set(
                self.module_candidates
            )))
            or any(
                not item
                or item != item.strip()
                or len(item) > 512
                or any(char in item for char in "\n\r;")
                for item in self.module_candidates
            )
        ):
            raise ValueError("native binding-set module inventory is invalid")

    @property
    def query_kind(self) -> str:
        return NATIVE_SELECTED_APPLICATION_BINDING_SET

    def to_payload(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "selected_resource": self.selected_resource,
            "module_candidates": list(self.module_candidates),
        }


@dataclass(frozen=True)
class NativeAttemptDiagnosticQuery:
    rejected_tactic: str
    observed_outcome_kind: str

    def __post_init__(self) -> None:
        if (
            not self.rejected_tactic
            or self.rejected_tactic != self.rejected_tactic.strip()
        ):
            raise ValueError("native attempt diagnostic requires exact tactic")
        if self.observed_outcome_kind not in {"rejected", "no_progress"}:
            raise ValueError("native attempt diagnostic requires manager outcome")

    @property
    def query_kind(self) -> str:
        return NATIVE_ATTEMPT_DIAGNOSTIC

    def to_payload(self) -> dict[str, object]:
        return {
            "rejected_tactic": self.rejected_tactic,
            "observed_outcome_kind": self.observed_outcome_kind,
        }


@dataclass(frozen=True)
class NativeTacticPrefixDiagnosticQuery:
    """One complete, bounded population of source-preserving prefixes."""

    rejected_tactic: str
    candidate_prefixes: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            type(self.rejected_tactic) is not str
            or not self.rejected_tactic
            or self.rejected_tactic != self.rejected_tactic.strip()
            or not self.rejected_tactic.endswith(".")
        ):
            raise ValueError("native tactic-prefix query requires exact tactic")
        if (
            type(self.candidate_prefixes) is not tuple
            or not self.candidate_prefixes
            or len(self.candidate_prefixes) > 8
            or any(
                type(item) is not str
                or not item
                or item != item.strip()
                or not item.endswith(".")
                or item == self.rejected_tactic
                for item in self.candidate_prefixes
            )
            or len(self.candidate_prefixes) != len(set(self.candidate_prefixes))
        ):
            raise ValueError("native tactic-prefix population is invalid")

    @property
    def query_kind(self) -> str:
        return NATIVE_TACTIC_PREFIX_DIAGNOSTIC

    def to_payload(self) -> dict[str, object]:
        return {
            "rejected_tactic": self.rejected_tactic,
            "candidate_prefixes": list(self.candidate_prefixes),
        }


NativeSemanticQuery = (
    NativeProofTermElaborationQuery
    | NativeSelectedApplicationBindingSetQuery
    | NativeAttemptDiagnosticQuery
    | NativeTacticPrefixDiagnosticQuery
)


@dataclass(frozen=True)
class NativeRelationBridgeDescriptor:
    """Native-established realization of one agent-written intermediate."""

    source_operation: str
    relation_family: str
    intermediate_text: str
    intermediate_type_text: str
    candidate_tactic: str
    failure_kind: str
    source_target_present: bool
    source_target_convertible_to_current_goal: bool
    source_target_right_convertible_to_current_right: bool

    def __post_init__(self) -> None:
        if (
            self.source_operation not in {"transitivity", "change"}
            or self.relation_family not in {"real_le", "int_le"}
            or not self.intermediate_text
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
            or self.intermediate_type_text != expected_type
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

    def to_payload(self) -> dict[str, object]:
        return {
            "source_operation": self.source_operation,
            "relation_family": self.relation_family,
            "intermediate_text": self.intermediate_text,
            "intermediate_type": self.intermediate_type_text,
            "candidate_tactic": self.candidate_tactic,
            "failure_kind": self.failure_kind,
            "source_target_present": self.source_target_present,
            "source_target_convertible_to_current_goal": (
                self.source_target_convertible_to_current_goal
            ),
            "source_target_right_convertible_to_current_right": (
                self.source_target_right_convertible_to_current_right
            ),
        }


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

    def to_payload(self) -> dict[str, str]:
        return {
            "certificate_family": self.certificate_family,
            "left_relation": self.left_relation,
            "right_relation": self.right_relation,
            "candidate_tactic": self.candidate_tactic,
        }


@dataclass(frozen=True)
class NativeRelationBridgeChoiceDescriptor:
    """Native-established alternatives when one strict bridge is ambiguous."""

    source_operation: str
    relation_family: str
    goal_left_text: str
    intermediate_text: str
    goal_right_text: str
    intermediate_type_text: str
    failure_kind: str
    choices: tuple[NativeRelationBridgeChoice, ...]

    def __post_init__(self) -> None:
        if (
            self.source_operation != "transitivity"
            or self.relation_family != "real_lt"
            or not self.goal_left_text
            or not self.intermediate_text
            or not self.goal_right_text
            or self.intermediate_type_text != "real"
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

    def to_payload(self) -> dict[str, object]:
        return {
            "source_operation": self.source_operation,
            "relation_family": self.relation_family,
            "goal_left_text": self.goal_left_text,
            "intermediate_text": self.intermediate_text,
            "goal_right_text": self.goal_right_text,
            "intermediate_type": self.intermediate_type_text,
            "failure_kind": self.failure_kind,
            "choices": [item.to_payload() for item in self.choices],
        }


@dataclass(frozen=True)
class NativePhlTransitivityBoundaryDescriptor:
    """Native PHL transitivity form/current-goal boundary mismatch."""

    source_operation: str
    attempted_form: str
    current_goal_form: str
    side: str
    failure_kind: str

    def __post_init__(self) -> None:
        if (
            self.source_operation != "transitivity"
            or self.attempted_form not in {"function", "statement"}
            or self.current_goal_form not in {"function", "statement"}
            or self.attempted_form == self.current_goal_form
            or self.side not in {"", "left", "right"}
            or (
                self.attempted_form == "function" and self.side
            )
            or (
                self.attempted_form == "statement" and not self.side
            )
            or self.failure_kind != "phl_transitivity_boundary_mismatch"
        ):
            raise ValueError("native PHL transitivity boundary is incomplete")

    def to_payload(self) -> dict[str, str]:
        return {
            "source_operation": self.source_operation,
            "attempted_form": self.attempted_form,
            "current_goal_form": self.current_goal_form,
            "side": self.side,
            "failure_kind": self.failure_kind,
        }


@dataclass(frozen=True)
class NativeEagerWhileCandidateDescriptor:
    """One agent-supplied invariant accepted by native eager preflight."""

    invariant_text: str
    candidate_tactic: str

    def __post_init__(self) -> None:
        if (
            not self.invariant_text
            or self.candidate_tactic
            != f"eager while ({self.invariant_text})."
        ):
            raise ValueError("native eager-while candidate is not canonical")

    def to_payload(self) -> dict[str, str]:
        return {
            "invariant_text": self.invariant_text,
            "candidate_tactic": self.candidate_tactic,
        }


@dataclass(frozen=True)
class NativeEagerWhileDialectDescriptor:
    """Native classification of one selected eager-while failure."""

    source_operation: str
    eager_subform: str
    attempted_shape: str
    failure_kind: str
    candidates: tuple[NativeEagerWhileCandidateDescriptor, ...]

    def __post_init__(self) -> None:
        if (
            self.source_operation != "eager"
            or self.eager_subform != "while"
            or self.attempted_shape not in {
                "explicit_statement_contract", "invariant"
            }
            or self.failure_kind not in {
                "eager_while_dialect_mismatch",
                "eager_while_guard_mismatch",
            }
            or len(self.candidates) > 2
            or len(self.candidates) != len(set(self.candidates))
        ):
            raise ValueError("native eager-while dialect descriptor is incomplete")
        if self.failure_kind == "eager_while_dialect_mismatch" and (
            self.attempted_shape != "explicit_statement_contract"
        ):
            raise ValueError("native eager dialect mismatch has the wrong shape")
        if self.failure_kind == "eager_while_guard_mismatch" and (
            self.attempted_shape != "invariant" or self.candidates
        ):
            raise ValueError("native eager guard mismatch carried candidates")

    def to_payload(self) -> dict[str, object]:
        return {
            "source_operation": self.source_operation,
            "eager_subform": self.eager_subform,
            "attempted_shape": self.attempted_shape,
            "failure_kind": self.failure_kind,
            "candidates": [item.to_payload() for item in self.candidates],
        }


@dataclass(frozen=True)
class NativePureTailRewriteDescriptor:
    """Unique native realization of an agent-selected rewrite target.

    The descriptor does not choose a lemma, direction, occurrence, witness, or
    proof route.  It only records that the exact left-to-right rewrite already
    attempted by the agent fails at the conclusion and succeeds at exactly one
    named hypothesis in the unchanged current state.
    """

    source_operation: str
    selected_resource: str
    target_kind: str
    target_name: str
    candidate_tactic: str
    failure_kind: str
    accepted_target_count: int

    def __post_init__(self) -> None:
        if (
            self.source_operation != "rewrite"
            or not self.selected_resource
            or self.target_kind != "hypothesis"
            or not self.target_name
            or self.candidate_tactic
            != f"rewrite {self.selected_resource} in {self.target_name}."
            or self.failure_kind != "rewrite_target_mismatch"
            or self.accepted_target_count != 1
        ):
            raise ValueError("native pure-tail rewrite descriptor is incomplete")

    def to_payload(self) -> dict[str, object]:
        return {
            "source_operation": self.source_operation,
            "selected_resource": self.selected_resource,
            "target_kind": self.target_kind,
            "target_name": self.target_name,
            "candidate_tactic": self.candidate_tactic,
            "failure_kind": self.failure_kind,
            "accepted_target_count": self.accepted_target_count,
        }


@dataclass(frozen=True)
class NativeIntroPatternRepairDescriptor:
    """Unique native repair of one agent-selected nested intro pattern.

    EasyCrypt has parsed both tactics and accepted the candidate in the exact
    unchanged state.  Shannon records only the already selected binder names
    and their order; it does not choose a hypothesis, decomposition, or proof
    route.
    """

    source_operation: str
    surface_operation: str
    attempted_pattern_kind: str
    binder_names: tuple[str, ...]
    candidate_tactic: str
    failure_kind: str
    selected_pattern_count: int

    def __post_init__(self) -> None:
        if (
            self.source_operation != "intro_pattern"
            or self.surface_operation != "move"
            or self.attempted_pattern_kind != "nested_case"
            or len(self.binder_names) < 2
            or len(self.binder_names) > 32
            or len(self.binder_names) != len(set(self.binder_names))
            or any(not name for name in self.binder_names)
            or not self.candidate_tactic.endswith(".")
            or self.failure_kind != "intro_pattern_structure_mismatch"
            or self.selected_pattern_count != 1
        ):
            raise ValueError("native intro-pattern repair descriptor is incomplete")

    def to_payload(self) -> dict[str, object]:
        return {
            "source_operation": self.source_operation,
            "surface_operation": self.surface_operation,
            "attempted_pattern_kind": self.attempted_pattern_kind,
            "binder_names": list(self.binder_names),
            "candidate_tactic": self.candidate_tactic,
            "failure_kind": self.failure_kind,
            "selected_pattern_count": self.selected_pattern_count,
        }


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

    def to_payload(self) -> dict[str, object]:
        return {
            "source_operation": self.source_operation,
            "selected_resource": self.selected_resource,
            "module_argument_position": self.module_argument_position,
            "module_term_text": self.module_term_text,
            "candidate_application_term": self.candidate_application_term,
            "candidate_tactic": self.candidate_tactic,
            "candidate_argument_kinds": list(self.candidate_argument_kinds),
            "failure_kind": self.failure_kind,
            "resolved_candidate_count": self.resolved_candidate_count,
        }


@dataclass(frozen=True)
class NativeTacticPrefixDiagnosticDescriptor:
    """Feature-neutral native results for one lexical prefix population."""

    rejected_tactic: str
    candidate_prefixes: tuple[str, ...]
    prefix_effects: tuple[str, ...]
    accepted_prefixes: tuple[str, ...]
    boundary_tactic: str
    native_failure_kind: str
    native_error_message: str
    boundary_failure_kind: str
    boundary_error_message: str
    goal_kind: str
    boundary_attempt: NativeAttemptedOperationDescriptor | None = None

    def __post_init__(self) -> None:
        candidates_valid = bool(
            type(self.candidate_prefixes) is tuple
            and self.candidate_prefixes
            and len(self.candidate_prefixes) <= 8
            and all(
                type(item) is str
                and item
                and item == item.strip()
                and item.endswith(".")
                for item in self.candidate_prefixes
            )
            and len(self.candidate_prefixes)
            == len(set(self.candidate_prefixes))
        )
        accepted_valid = bool(
            type(self.accepted_prefixes) is tuple
            and all(
                type(item) is str and item in self.candidate_prefixes
                for item in self.accepted_prefixes
            )
            and len(self.accepted_prefixes)
            == len(set(self.accepted_prefixes))
        )
        effects_valid = bool(
            type(self.prefix_effects) is tuple
            and len(self.prefix_effects) == len(self.candidate_prefixes)
            and all(
                item in NATIVE_TACTIC_PREFIX_EFFECTS
                for item in self.prefix_effects
            )
        )
        expected_accepted = tuple(
            candidate
            for candidate, effect in zip(
                self.candidate_prefixes, self.prefix_effects
            )
            if effect != "rejected"
        )
        contiguous_effect = ""
        for effect in self.prefix_effects:
            if effect == "rejected":
                break
            contiguous_effect = effect
        handoff_valid = self.boundary_attempt is None or bool(
            contiguous_effect in {
                "accepted_no_progress", "accepted_changed"
            }
            and self.accepted_prefixes
            == self.candidate_prefixes[:len(self.accepted_prefixes)]
            and self.boundary_tactic
            and isinstance(
                self.boundary_attempt, NativeAttemptedOperationDescriptor
            )
            and self.boundary_attempt.rejected_tactic == self.boundary_tactic
            and self.boundary_attempt.attempt_outcome == "rejected"
            and self.boundary_attempt.native_diagnostic_status == "blocker"
        )
        if (
            type(self.rejected_tactic) is not str
            or not self.rejected_tactic
            or self.rejected_tactic != self.rejected_tactic.strip()
            or not self.rejected_tactic.endswith(".")
            or not candidates_valid
            or not accepted_valid
            or not effects_valid
            or self.accepted_prefixes != expected_accepted
            or type(self.boundary_tactic) is not str
            or (
                self.boundary_tactic
                and (
                    self.boundary_tactic != self.boundary_tactic.strip()
                    or not self.boundary_tactic.endswith(".")
                )
            )
            or not handoff_valid
            or type(self.native_failure_kind) is not str
            or not self.native_failure_kind
            or type(self.native_error_message) is not str
            or not self.native_error_message
            or type(self.boundary_failure_kind) is not str
            or not self.boundary_failure_kind
            or type(self.boundary_error_message) is not str
            or not self.boundary_error_message
            or type(self.goal_kind) is not str
            or not self.goal_kind
        ):
            raise ValueError("native tactic-prefix descriptor is invalid")

    def to_payload(self) -> dict[str, object]:
        return {
            "rejected_tactic": self.rejected_tactic,
            "candidate_prefixes": list(self.candidate_prefixes),
            "prefix_effects": list(self.prefix_effects),
            "accepted_prefixes": list(self.accepted_prefixes),
            "boundary_tactic": self.boundary_tactic,
            "boundary_attempt": (
                None
                if self.boundary_attempt is None
                else self.boundary_attempt.to_payload()
            ),
            "native_failure_kind": self.native_failure_kind,
            "native_error_message": self.native_error_message,
            "boundary_failure_kind": self.boundary_failure_kind,
            "boundary_error_message": self.boundary_error_message,
            "goal_kind": self.goal_kind,
        }


@dataclass(frozen=True)
class NativeAttemptedOperationDescriptor:
    """Native parse and applicability result for one exact rejected tactic."""

    operation_family: str
    rejected_tactic: str
    exact_resource: str
    argument_kinds: tuple[str, ...]
    side: str
    positions: tuple[int, ...]
    native_diagnostic_status: str
    native_failure_kind: str
    native_error_message: str
    attempt_outcome: str
    goal_kind: str
    application_head: NativeApplicationHeadDescriptor | None = None
    proof_term: NativeProofTermDescriptor | None = None
    relation_bridge: NativeRelationBridgeDescriptor | None = None
    relation_bridge_choice: NativeRelationBridgeChoiceDescriptor | None = None
    phl_transitivity_boundary: (
        NativePhlTransitivityBoundaryDescriptor | None
    ) = None
    eager_while_dialect: NativeEagerWhileDialectDescriptor | None = None
    pure_tail_rewrite: NativePureTailRewriteDescriptor | None = None
    intro_pattern_realization: NativeIntroPatternRepairDescriptor | None = None
    application_syntax_repair: (
        NativeApplicationSyntaxRepairDescriptor | None
    ) = None

    def __post_init__(self) -> None:
        if self.operation_family not in _ATTEMPT_OPERATIONS:
            raise ValueError("native attempted operation family is invalid")
        if not self.rejected_tactic:
            raise ValueError("native attempted operation requires exact tactic")
        if any(not item for item in self.argument_kinds):
            raise ValueError("native attempted operation argument kind is invalid")
        if self.side not in {"", "left", "right"}:
            raise ValueError("native attempted operation side is invalid")
        if any(type(item) is not int or item < 0 for item in self.positions):
            raise ValueError("native attempted operation position is invalid")
        if self.attempt_outcome not in {"accepted", "rejected", "no_progress"}:
            raise ValueError("native attempted operation outcome is invalid")
        if self.native_diagnostic_status not in {
            "blocker", "no_blocker", "indeterminate"
        }:
            raise ValueError("native attempted diagnostic status is invalid")
        if not self.goal_kind:
            raise ValueError("native attempted operation requires goal kind")
        if (
            self.attempt_outcome == "rejected"
            and self.native_diagnostic_status == "no_blocker"
        ):
            raise ValueError("rejected native attempt requires a diagnostic")
        if (
            self.attempt_outcome == "accepted"
            and self.native_diagnostic_status != "no_blocker"
        ):
            raise ValueError("accepted native attempt cannot carry a diagnostic")
        if self.native_diagnostic_status == "no_blocker" and (
            self.native_failure_kind or self.native_error_message
        ):
            raise ValueError("no-blocker native attempt carried an error")
        if (
            self.native_diagnostic_status != "no_blocker"
            and not self.native_failure_kind
        ):
            raise ValueError("native attempt diagnostic is empty")
        if (
            self.native_diagnostic_status == "indeterminate"
            and self.native_failure_kind != "native_assertion"
        ):
            raise ValueError("native indeterminate diagnostic kind is invalid")
        if bool(self.native_failure_kind) is not bool(self.native_error_message):
            raise ValueError("native attempt error is incomplete")
        if self.proof_term is not None and self.operation_family not in {
            "apply", "exact", "call", "conseq"
        }:
            raise ValueError("only proof-term operations carry proof descriptors")
        if self.application_head is not None and not self.exact_resource:
            raise ValueError("native application head requires a named resource")
        if (
            self.proof_term is not None
            and self.application_head is not None
            and self.proof_term.resolved_head != self.application_head.resolved_head
        ):
            raise ValueError("native application and head descriptors disagree")
        if self.relation_bridge is not None and (
            self.operation_family != self.relation_bridge.source_operation
            or self.exact_resource
            or self.proof_term is not None
            or self.application_head is not None
        ):
            raise ValueError("native relation bridge changed attempted identity")
        if self.relation_bridge_choice is not None and (
            self.operation_family
            != self.relation_bridge_choice.source_operation
            or self.exact_resource
            or self.proof_term is not None
            or self.application_head is not None
            or self.relation_bridge is not None
        ):
            raise ValueError("native relation choice changed attempted identity")
        if self.phl_transitivity_boundary is not None and (
            self.operation_family
            != self.phl_transitivity_boundary.source_operation
            or self.exact_resource
            or self.proof_term is not None
            or self.application_head is not None
            or self.relation_bridge is not None
            or self.relation_bridge_choice is not None
            or self.side != self.phl_transitivity_boundary.side
        ):
            raise ValueError("native PHL boundary changed attempted identity")
        if self.eager_while_dialect is not None and (
            self.operation_family
            != self.eager_while_dialect.source_operation
            or self.exact_resource
            or self.proof_term is not None
            or self.application_head is not None
            or self.relation_bridge is not None
            or self.relation_bridge_choice is not None
            or self.phl_transitivity_boundary is not None
            or self.side
            or self.positions
        ):
            raise ValueError("native eager dialect changed attempted identity")
        if self.pure_tail_rewrite is not None and (
            self.operation_family != self.pure_tail_rewrite.source_operation
            or self.operation_family != "rewrite"
            or self.exact_resource
            != self.pure_tail_rewrite.selected_resource
            or self.proof_term is not None
            or self.application_head is not None
            or self.relation_bridge is not None
            or self.relation_bridge_choice is not None
            or self.phl_transitivity_boundary is not None
            or self.eager_while_dialect is not None
            or self.side
            or self.positions
        ):
            raise ValueError("native pure-tail rewrite changed attempted identity")
        if self.intro_pattern_realization is not None and (
            self.operation_family
            != self.intro_pattern_realization.source_operation
            or self.operation_family != "intro_pattern"
            or self.exact_resource
            or self.proof_term is not None
            or self.application_head is not None
            or self.relation_bridge is not None
            or self.relation_bridge_choice is not None
            or self.phl_transitivity_boundary is not None
            or self.eager_while_dialect is not None
            or self.pure_tail_rewrite is not None
            or self.application_syntax_repair is not None
            or self.side
            or self.positions
        ):
            raise ValueError("native intro-pattern repair changed attempted identity")
        syntax = self.application_syntax_repair
        if syntax is not None and (
            self.operation_family != syntax.source_operation
            or self.exact_resource != syntax.selected_resource
            or self.native_failure_kind != syntax.failure_kind
            or self.application_head is None
            or not self.application_head.slots
            or self.application_head.slots[0].kind != "module"
            or tuple(
                item.syntax_kind for item in self.application_head.input_arguments
            )
            != syntax.candidate_argument_kinds
            or self.proof_term is not None
            or self.relation_bridge is not None
            or self.relation_bridge_choice is not None
            or self.phl_transitivity_boundary is not None
            or self.eager_while_dialect is not None
            or self.pure_tail_rewrite is not None
            or self.intro_pattern_realization is not None
            or self.argument_kinds
            or self.side
            or self.positions
        ):
            raise ValueError(
                "native application syntax repair changed attempted identity"
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "operation_family": self.operation_family,
            "rejected_tactic": self.rejected_tactic,
            "exact_resource": self.exact_resource,
            "argument_kinds": list(self.argument_kinds),
            "side": self.side,
            "positions": list(self.positions),
            "native_diagnostic_status": self.native_diagnostic_status,
            "native_failure_kind": self.native_failure_kind,
            "native_error_message": self.native_error_message,
            "attempt_outcome": self.attempt_outcome,
            "goal_kind": self.goal_kind,
            "application_head": (
                None
                if self.application_head is None
                else self.application_head.to_payload()
            ),
            "proof_term": (
                None if self.proof_term is None else self.proof_term.to_payload()
            ),
            "relation_bridge": (
                None
                if self.relation_bridge is None
                else self.relation_bridge.to_payload()
            ),
            "relation_bridge_choice": (
                None
                if self.relation_bridge_choice is None
                else self.relation_bridge_choice.to_payload()
            ),
            "phl_transitivity_boundary": (
                None
                if self.phl_transitivity_boundary is None
                else self.phl_transitivity_boundary.to_payload()
            ),
            "eager_while_dialect": (
                None
                if self.eager_while_dialect is None
                else self.eager_while_dialect.to_payload()
            ),
            "pure_tail_rewrite": (
                None
                if self.pure_tail_rewrite is None
                else self.pure_tail_rewrite.to_payload()
            ),
            "intro_pattern_realization": (
                None
                if self.intro_pattern_realization is None
                else self.intro_pattern_realization.to_payload()
            ),
            "application_syntax_repair": (
                None
                if self.application_syntax_repair is None
                else self.application_syntax_repair.to_payload()
            ),
        }


NativeSemanticDescriptor = (
    NativeProofTermDescriptor
    | NativeSelectedApplicationBindingSetDescriptor
    | NativeAttemptedOperationDescriptor
    | NativeTacticPrefixDiagnosticDescriptor
)


def _semantic_unit_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class NativeSemanticRequest:
    """One bounded semantic fact requested by an active P3 feature slice."""

    state_ref: StateRef
    request_id: str
    producer_id: str
    query: NativeSemanticQuery
    evidence_refs: tuple[EvidenceRef, ...]
    feature_id: str = ""
    evaluation_prefix: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id or not self.producer_id:
            raise ValueError("native semantic request requires identity")
        if self.feature_id != self.feature_id.strip():
            raise ValueError("native semantic request feature identity is invalid")
        if (
            type(self.evaluation_prefix) is not tuple
            or any(
                type(item) is not str
                or not item
                or item != item.strip()
                or not item.endswith(".")
                or "\n" in item
                or "\r" in item
                for item in self.evaluation_prefix
            )
        ):
            raise ValueError("native semantic evaluation prefix is invalid")
        if not isinstance(self.query, (
            NativeProofTermElaborationQuery,
            NativeSelectedApplicationBindingSetQuery,
            NativeAttemptDiagnosticQuery,
            NativeTacticPrefixDiagnosticQuery,
        )):
            raise TypeError("native semantic request requires a typed query")
        if not self.evidence_refs:
            raise ValueError("native semantic request requires evidence")

    @property
    def query_kind(self) -> str:
        return self.query.query_kind

    def semantic_payload(self) -> dict[str, object]:
        return {
            "state": self.state_ref.identity_payload(),
            "evaluation_prefix": list(self.evaluation_prefix),
            "query_kind": self.query_kind,
            "payload": self.query.to_payload(),
        }

    @property
    def semantic_unit_sha256(self) -> str:
        return _semantic_unit_sha256(self.semantic_payload())

    def runtime_payload(self, *, request_id: str | None = None) -> dict[str, object]:
        return {
            "request_id": request_id or self.request_id,
            "evaluation_prefix": list(self.evaluation_prefix),
            "query_kind": self.query_kind,
            "payload": self.query.to_payload(),
        }

    def identity_payload(self) -> dict[str, object]:
        return {
            "state": self.state_ref.identity_payload(),
            "request_id": self.request_id,
            "feature_id": self.feature_id,
            "producer_id": self.producer_id,
            "evaluation_prefix": list(self.evaluation_prefix),
            "query_kind": self.query_kind,
            "payload": self.query.to_payload(),
        }

    @property
    def identity_sha256(self) -> str:
        encoded = json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class NativeSemanticRequestProduction:
    """One producer's complete, non-truncated planning result."""

    producer_id: str
    disposition: str
    requests: tuple[NativeSemanticRequest, ...] = ()
    reason: str = ""
    considered_candidate_count: int = 0

    def __post_init__(self) -> None:
        if not self.producer_id:
            raise ValueError("native semantic production requires producer identity")
        if self.disposition not in NATIVE_PRODUCTION_DISPOSITIONS:
            raise ValueError("native semantic production disposition is invalid")
        if (
            type(self.considered_candidate_count) is not int
            or self.considered_candidate_count < 0
        ):
            raise ValueError("native semantic candidate count is invalid")
        if any(request.producer_id != self.producer_id for request in self.requests):
            raise ValueError("native semantic production crosses producer ownership")
        if self.disposition == NATIVE_PRODUCTION_READY:
            if not self.requests or self.reason:
                raise ValueError("ready native production payload is invalid")
            if self.considered_candidate_count < len(self.requests):
                raise ValueError("native production omitted considered candidates")
        elif self.requests:
            raise ValueError("non-ready native production cannot carry requests")
        elif self.disposition == NATIVE_PRODUCTION_ABSTAINED and not self.reason:
            raise ValueError("native abstention requires a typed reason")
        elif self.disposition == NATIVE_PRODUCTION_NOT_APPLICABLE and self.reason:
            raise ValueError("not-applicable native production cannot carry a reason")

    @classmethod
    def ready(
        cls,
        producer_id: str,
        requests: tuple[NativeSemanticRequest, ...],
        *,
        considered_candidate_count: int | None = None,
    ) -> "NativeSemanticRequestProduction":
        return cls(
            producer_id=producer_id,
            disposition=NATIVE_PRODUCTION_READY,
            requests=requests,
            considered_candidate_count=(
                len(requests)
                if considered_candidate_count is None
                else considered_candidate_count
            ),
        )

    @classmethod
    def not_applicable(
        cls, producer_id: str
    ) -> "NativeSemanticRequestProduction":
        return cls(
            producer_id=producer_id,
            disposition=NATIVE_PRODUCTION_NOT_APPLICABLE,
        )

    @classmethod
    def abstained(
        cls,
        producer_id: str,
        *,
        reason: str,
        considered_candidate_count: int,
    ) -> "NativeSemanticRequestProduction":
        return cls(
            producer_id=producer_id,
            disposition=NATIVE_PRODUCTION_ABSTAINED,
            reason=reason,
            considered_candidate_count=considered_candidate_count,
        )


@dataclass(frozen=True)
class NativeSemanticPlanningDecision:
    """Auditable disposition for one feature-owned native producer."""

    feature_id: str
    producer_id: str
    disposition: str
    reason: str
    considered_candidate_count: int
    proposed_request_ids: tuple[str, ...]
    unresolved_request_count: int
    unresolved_execution_unit_count: int

    def __post_init__(self) -> None:
        if not self.feature_id or not self.producer_id:
            raise ValueError("native planning decision requires ownership")
        if self.disposition not in NATIVE_PRODUCTION_DISPOSITIONS:
            raise ValueError("native planning decision disposition is invalid")
        if any(not request_id for request_id in self.proposed_request_ids):
            raise ValueError("native planning request identity is empty")
        if len(self.proposed_request_ids) != len(set(self.proposed_request_ids)):
            raise ValueError("native planning request population is duplicated")
        if self.proposed_request_ids != tuple(sorted(self.proposed_request_ids)):
            raise ValueError("native planning request population is not canonical")
        counts = (
            self.considered_candidate_count,
            self.unresolved_request_count,
            self.unresolved_execution_unit_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("native planning decision count is invalid")
        if self.disposition == NATIVE_PRODUCTION_ABSTAINED and not self.reason:
            raise ValueError("native planning abstention requires a reason")
        if self.disposition != NATIVE_PRODUCTION_ABSTAINED and self.reason:
            raise ValueError("non-abstaining native decision cannot carry a reason")

    @property
    def proposed_request_count(self) -> int:
        """Derived telemetry; population identity is owned by request IDs."""

        return len(self.proposed_request_ids)

    @property
    def proposed_population_sha256(self) -> str:
        """Order-independent identity of the exact proposed request set."""

        return frozen_json_sha256(freeze_json_object({
            "request_ids": list(self.proposed_request_ids),
        }))

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_id": self.feature_id,
            "producer_id": self.producer_id,
            "disposition": self.disposition,
            "reason": self.reason,
            "considered_candidate_count": self.considered_candidate_count,
            "proposed_request_count": self.proposed_request_count,
            "proposed_request_ids": list(self.proposed_request_ids),
            "proposed_population_sha256": self.proposed_population_sha256,
            "unresolved_request_count": self.unresolved_request_count,
            "unresolved_execution_unit_count": (
                self.unresolved_execution_unit_count
            ),
        }


NATIVE_PLANNING_STAGES = ("pre_resource", "post_resource")


@dataclass(frozen=True)
class NativeSemanticPlanningStage:
    """One compiler-derived planning result for an exact state and budget."""

    state_ref: StateRef
    stage: str
    budget_before: NativePlanningBudget
    budget_after: NativePlanningBudget
    decisions: tuple[NativeSemanticPlanningDecision, ...]
    evidence_ref: EvidenceRef

    def __post_init__(self) -> None:
        if self.stage not in NATIVE_PLANNING_STAGES:
            raise ValueError("native planning stage is invalid")
        if self.budget_before.max_consumer_requests != (
            self.budget_after.max_consumer_requests
        ) or self.budget_before.max_execution_units != (
            self.budget_after.max_execution_units
        ):
            raise ValueError("native planning stage changed its allocation")
        if (
            self.budget_after.used_consumer_requests
            < self.budget_before.used_consumer_requests
            or self.budget_after.used_execution_units
            < self.budget_before.used_execution_units
        ):
            raise ValueError("native planning stage moved its budget backwards")
        keys = tuple((item.feature_id, item.producer_id) for item in self.decisions)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("native planning stage decisions are not canonical")

    @classmethod
    def from_plan(
        cls,
        *,
        stage: str,
        plan: "NativeSemanticPlan",
        budget_after: NativePlanningBudget,
    ) -> "NativeSemanticPlanningStage":
        payload = freeze_json_object({
            "stage": stage,
            "state_ref": plan.state_ref.identity_payload(),
            "budget_before": plan.budget.to_dict(),
            "budget_after": budget_after.to_dict(),
            "decisions": [item.to_dict() for item in plan.decisions],
        })
        digest = frozen_json_sha256(payload)
        return cls(
            state_ref=plan.state_ref,
            stage=stage,
            budget_before=plan.budget,
            budget_after=budget_after,
            decisions=plan.decisions,
            evidence_ref=EvidenceRef(
                evidence_id=f"native-planning:{stage}:{digest[:20]}",
                source_kind="compiler_native_planning",
                source_ref=f"compiler://native-planning/{stage}/{digest}",
                source_sha256=digest,
            ),
        )


@dataclass(frozen=True)
class NativeSemanticPlanningReport:
    """Both bounded native-planning stages supplied to the final P2/P3 pass."""

    state_ref: StateRef
    stages: tuple[NativeSemanticPlanningStage, ...] = ()

    def __post_init__(self) -> None:
        if any(item.state_ref != self.state_ref for item in self.stages):
            raise ValueError("native planning report crosses StateRef")
        names = tuple(item.stage for item in self.stages)
        expected = tuple(
            name for name in NATIVE_PLANNING_STAGES if name in set(names)
        )
        if names != expected or len(names) != len(set(names)):
            raise ValueError("native planning report stages are not canonical")

    def decisions_for(
        self,
        *,
        feature_id: str,
        producer_id: str,
    ) -> tuple[tuple[NativeSemanticPlanningStage, NativeSemanticPlanningDecision], ...]:
        return tuple(
            (stage, decision)
            for stage in self.stages
            for decision in stage.decisions
            if decision.feature_id == feature_id
            and decision.producer_id == producer_id
        )


@dataclass(frozen=True)
class NativeSemanticPlan:
    """All active-feature native dependencies for one exact StateRef."""

    state_ref: StateRef
    requests: tuple[NativeSemanticRequest, ...]
    execution_units: tuple["NativeSemanticExecutionUnit", ...]
    budget: NativePlanningBudget = field(default_factory=NativePlanningBudget)
    decisions: tuple[NativeSemanticPlanningDecision, ...] = ()

    def __post_init__(self) -> None:
        if len(self.requests) > self.budget.remaining_consumer_requests:
            raise ValueError("native semantic plan exceeds its consumer allocation")
        if len(self.execution_units) > self.budget.remaining_execution_units:
            raise ValueError("native semantic plan exceeds its execution allocation")
        request_ids = [request.request_id for request in self.requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("native semantic plan has duplicate request IDs")
        if any(request.state_ref != self.state_ref for request in self.requests):
            raise ValueError("native semantic plan crosses StateRef")
        covered = tuple(
            request.request_id
            for unit in self.execution_units
            for request in unit.requests
        )
        if sorted(covered) != sorted(request_ids):
            raise ValueError("native semantic execution units do not cover requests")
        unit_ids = tuple(unit.unit_id for unit in self.execution_units)
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("native semantic plan has duplicate execution units")


@dataclass(frozen=True)
class NativeSemanticExecutionUnit:
    """One coalesced native boundary crossing with one or more consumers."""

    unit_id: str
    state_ref: StateRef
    query: NativeSemanticQuery
    requests: tuple[NativeSemanticRequest, ...]

    def __post_init__(self) -> None:
        if not self.unit_id or not self.requests:
            raise ValueError("native semantic execution unit is incomplete")
        if any(request.state_ref != self.state_ref for request in self.requests):
            raise ValueError("native semantic execution unit crosses StateRef")
        if any(request.query != self.query for request in self.requests):
            raise ValueError("native semantic execution unit mixes payloads")
        if any(
            request.evaluation_prefix != self.requests[0].evaluation_prefix
            for request in self.requests
        ):
            raise ValueError("native semantic execution unit mixes proof contexts")
        if any(request.semantic_unit_sha256 != self.unit_id for request in self.requests):
            raise ValueError("native semantic unit identity drifted")

    def runtime_payload(self) -> dict[str, object]:
        return self.requests[0].runtime_payload(request_id=self.unit_id)

    @property
    def query_kind(self) -> str:
        return self.query.query_kind

@dataclass(frozen=True)
class NativeSemanticObservation:
    """One event-bound native result returned by the manager runtime."""

    state_ref: StateRef
    request_id: str
    feature_id: str
    producer_id: str
    request_identity_sha256: str
    batch_id: str
    batch_index: int
    batch_size: int
    batch_cache_state: str
    batch_build_elapsed_ms: int
    batch_execution_elapsed_ms: int
    batch_elapsed_ms: int
    query: NativeSemanticQuery
    evaluation_prefix: tuple[str, ...]
    status: str
    result_formula: str
    descriptor: NativeSemanticDescriptor | None
    structured_error: FrozenJsonObject
    runtime_identity_sha256: str
    companion_identity_sha256: str
    elapsed_ms: int
    provenance: ProvenanceRef

    def __post_init__(self) -> None:
        if not self.request_id or not self.producer_id:
            raise ValueError("native semantic observation requires identity")
        if self.feature_id != self.feature_id.strip():
            raise ValueError("native semantic observation feature identity is invalid")
        if (
            not self.batch_id
            or self.batch_size < 1
            or self.batch_size > 8
            or self.batch_index < 0
            or self.batch_index >= self.batch_size
            or self.batch_cache_state not in {"cold", "warm"}
            or self.batch_build_elapsed_ms < 0
            or self.batch_execution_elapsed_ms < 0
            or self.batch_elapsed_ms < (
                self.batch_build_elapsed_ms + self.batch_execution_elapsed_ms
            )
        ):
            raise ValueError("native semantic observation batch identity is invalid")
        if not isinstance(self.query, (
            NativeProofTermElaborationQuery,
            NativeSelectedApplicationBindingSetQuery,
            NativeAttemptDiagnosticQuery,
            NativeTacticPrefixDiagnosticQuery,
        )):
            raise TypeError("native semantic observation requires typed query")
        if (
            type(self.evaluation_prefix) is not tuple
            or any(
                type(item) is not str
                or not item
                or item != item.strip()
                or not item.endswith(".")
                for item in self.evaluation_prefix
            )
        ):
            raise ValueError("native semantic observation context is invalid")
        for value in (
            self.request_identity_sha256,
            self.runtime_identity_sha256,
            self.companion_identity_sha256,
        ):
            if (
                len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError("native semantic observation identity is invalid")
        if self.status not in {"accepted", "rejected"}:
            raise ValueError("native semantic observation status is invalid")
        if self.status == "accepted":
            if self.descriptor is None or self.structured_error:
                raise ValueError("accepted native observation payload is invalid")
            if self.query_kind == NATIVE_PROOF_TERM_ELABORATION and (
                not self.result_formula
                or not isinstance(self.descriptor, NativeProofTermDescriptor)
            ):
                raise ValueError("accepted proof-term observation is invalid")
            expected_descriptor_type = {
                NATIVE_SELECTED_APPLICATION_BINDING_SET: (
                    NativeSelectedApplicationBindingSetDescriptor
                ),
                NATIVE_ATTEMPT_DIAGNOSTIC: NativeAttemptedOperationDescriptor,
                NATIVE_TACTIC_PREFIX_DIAGNOSTIC: (
                    NativeTacticPrefixDiagnosticDescriptor
                ),
            }.get(self.query_kind)
            if self.query_kind != NATIVE_PROOF_TERM_ELABORATION and (
                self.result_formula
                or expected_descriptor_type is None
                or not isinstance(self.descriptor, expected_descriptor_type)
            ):
                raise ValueError("accepted diagnostic observation is invalid")
        elif self.result_formula or self.descriptor is not None or not self.structured_error:
            raise ValueError("rejected native observation payload is invalid")
        if self.elapsed_ms < 0:
            raise ValueError("native semantic elapsed time is invalid")
        if not self.provenance.authoritative or (
            self.provenance.authority != "native.semantic.batch.produced"
        ):
            raise ValueError("native semantic observation requires event authority")

    @property
    def query_kind(self) -> str:
        return self.query.query_kind

    @property
    def semantic_unit_sha256(self) -> str:
        """Identity of the coalesced native member that produced this fact.

        ``request_id`` identifies this feature consumer. Multiple consumer
        requests may fan out from one native execution unit, so artifact joins
        must use this unit identity rather than equating the two IDs.
        """

        return _semantic_unit_sha256({
            "state": self.state_ref.identity_payload(),
            "evaluation_prefix": list(self.evaluation_prefix),
            "query_kind": self.query_kind,
            "payload": self.query.to_payload(),
        })

    @classmethod
    def accepted(
        cls,
        *,
        request: NativeSemanticRequest,
        batch_id: str,
        batch_index: int,
        batch_size: int,
        batch_cache_state: str = "warm",
        batch_build_elapsed_ms: int = 0,
        batch_execution_elapsed_ms: int = 0,
        batch_elapsed_ms: int,
        result_formula: str,
        descriptor: NativeSemanticDescriptor,
        runtime_identity_sha256: str,
        companion_identity_sha256: str,
        elapsed_ms: int,
        provenance: ProvenanceRef,
    ) -> "NativeSemanticObservation":
        return cls(
            state_ref=request.state_ref,
            request_id=request.request_id,
            feature_id=request.feature_id,
            producer_id=request.producer_id,
            request_identity_sha256=request.identity_sha256,
            batch_id=batch_id,
            batch_index=batch_index,
            batch_size=batch_size,
            batch_cache_state=batch_cache_state,
            batch_build_elapsed_ms=batch_build_elapsed_ms,
            batch_execution_elapsed_ms=batch_execution_elapsed_ms,
            batch_elapsed_ms=batch_elapsed_ms,
            query=request.query,
            evaluation_prefix=request.evaluation_prefix,
            status="accepted",
            result_formula=result_formula,
            descriptor=descriptor,
            structured_error=freeze_json_object({}),
            runtime_identity_sha256=runtime_identity_sha256,
            companion_identity_sha256=companion_identity_sha256,
            elapsed_ms=elapsed_ms,
            provenance=provenance,
        )

    @classmethod
    def rejected(
        cls,
        *,
        request: NativeSemanticRequest,
        batch_id: str,
        batch_index: int,
        batch_size: int,
        batch_cache_state: str = "warm",
        batch_build_elapsed_ms: int = 0,
        batch_execution_elapsed_ms: int = 0,
        batch_elapsed_ms: int,
        structured_error: dict[str, object],
        runtime_identity_sha256: str,
        companion_identity_sha256: str,
        elapsed_ms: int,
        provenance: ProvenanceRef,
    ) -> "NativeSemanticObservation":
        return cls(
            state_ref=request.state_ref,
            request_id=request.request_id,
            feature_id=request.feature_id,
            producer_id=request.producer_id,
            request_identity_sha256=request.identity_sha256,
            batch_id=batch_id,
            batch_index=batch_index,
            batch_size=batch_size,
            batch_cache_state=batch_cache_state,
            batch_build_elapsed_ms=batch_build_elapsed_ms,
            batch_execution_elapsed_ms=batch_execution_elapsed_ms,
            batch_elapsed_ms=batch_elapsed_ms,
            query=request.query,
            evaluation_prefix=request.evaluation_prefix,
            status="rejected",
            result_formula="",
            descriptor=None,
            structured_error=freeze_json_object(structured_error),
            runtime_identity_sha256=runtime_identity_sha256,
            companion_identity_sha256=companion_identity_sha256,
            elapsed_ms=elapsed_ms,
            provenance=provenance,
        )
