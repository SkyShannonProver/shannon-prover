"""Native-backed realization of one selected application's module grammar.

This is a B2 subtype of ``operation_binding_repair``.  The rejected tactic
already commits to ``call``, one exact resource, one concrete first module
term, and an exact remaining suffix.  The only permitted realization inserts
EasyCrypt's ``(<: M)`` module grammar around that term.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts import (
    CompilerInvocationContext,
    EvidenceRef,
    NativeApplicationSyntaxRepairDescriptor,
    NativePlanningBudget,
    NativeProofTermDescriptor,
    NativeProofTermElaborationQuery,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    ProofCoordinate,
    ProofIR,
    ProofResource,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.classification import (
    classify_operation_binding_failure,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.contracts import (
    OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.middle_end.native_application import (
    native_application_contribution,
    resolved_head_matches_resource,
)


APPLICATION_MODULE_SYNTAX_NATIVE_PRODUCER_ID = (
    "operation_binding_repair.application_module_syntax.native_elaboration"
)


@dataclass(frozen=True)
class ApplicationModuleSyntaxRealization:
    """The one feature-local source-to-candidate punctuation transform."""

    selected_resource: str
    module_term_text: str
    suffix_text: str
    candidate_application_term: str
    candidate_tactic: str


@dataclass(frozen=True)
class ApplicationModuleSyntaxRepairSketch:
    """One source-verified native realization awaiting full elaboration."""

    resource: ProofResource
    descriptor: NativeApplicationSyntaxRepairDescriptor
    realization: ApplicationModuleSyntaxRealization
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        if (
            self.resource.symbol != self.descriptor.selected_resource
            or self.realization.selected_resource != self.resource.symbol
            or not self.evidence_refs
        ):
            raise ValueError("application module syntax sketch is incomplete")


def realize_application_module_syntax(
    rejected_tactic: str,
) -> ApplicationModuleSyntaxRealization | None:
    """Reconstruct the only allowed punctuation edit from exact source text.

    This is deliberately lexical.  It grants no type or module authority; it
    only proves that the native candidate preserved the selected resource,
    module-term tokens, remaining suffix, and order.
    """

    text = str(rejected_tactic or "")
    if (
        not 0 < len(text) <= 4096
        or text != text.strip()
        or not text.startswith("call ")
        or not text.endswith(".")
        or any(token in text for token in (
            ";", "\n", "\r", '"', "(*", "*)", "|",
        ))
    ):
        return None
    term = text[len("call "):-1].strip()
    application = _outer_parenthesized_body(term)
    if application is None:
        return None
    separator = _first_top_level_space(application)
    if separator is None:
        return None
    resource = application[:separator].strip()
    arguments = application[separator:].strip()
    if not resource or not arguments:
        return None
    first = _first_application_argument(arguments)
    if first is None:
        return None
    module_term, suffix, was_parenthesized = first
    if (
        not module_term
        or "<:" in module_term
        or not _balanced_delimiters(module_term)
        or not _balanced_delimiters(suffix)
        or (
            not was_parenthesized
            and suffix.startswith(("(", "."))
        )
    ):
        return None
    candidate_application = (
        f"{resource} (<: {module_term})"
        + ("" if not suffix else f" {suffix}")
    )
    return ApplicationModuleSyntaxRealization(
        selected_resource=resource,
        module_term_text=module_term,
        suffix_text=suffix,
        candidate_application_term=candidate_application,
        candidate_tactic=f"call ({candidate_application}).",
    )


def discover_unique_application_module_syntax_repair(
    proof_ir: ProofIR,
) -> ApplicationModuleSyntaxRepairSketch | None:
    """Join one native grammar descriptor to its exact source transform."""

    attempted = proof_ir.attempted_operation
    if attempted is None:
        return None
    syntax = attempted.application_syntax_repair_descriptor
    head = attempted.application_head_descriptor
    realization = realize_application_module_syntax(
        attempted.rejected_tactic
    )
    if (
        syntax is None
        or realization is None
        or classify_operation_binding_failure(attempted) != "B2"
        or attempted.operation != "call"
        or attempted.resource != syntax.selected_resource
        or attempted.resource != realization.selected_resource
        or syntax.module_term_text != realization.module_term_text
        or syntax.candidate_application_term
        != realization.candidate_application_term
        or syntax.candidate_tactic != realization.candidate_tactic
        or syntax.module_argument_position != 1
        or syntax.resolved_candidate_count != 1
        or attempted.parsed_arguments
        or bool(attempted.side)
        or bool(attempted.positions)
        or head is None
        or not resolved_head_matches_resource(
            head.resolved_head.identity,
            attempted.resource,
        )
        or not head.slots
        or head.slots[0].kind != "module"
        or tuple(item.syntax_kind for item in head.input_arguments)
        != syntax.candidate_argument_kinds
        or not head.input_arguments
        or head.input_arguments[0].syntax_kind != "module"
        or head.input_arguments[0].explicit_hole
    ):
        return None
    resources = tuple(
        resource
        for resource in proof_ir.resources
        if resource.symbol == attempted.resource
    )
    if len(resources) != 1:
        return None
    resource = resources[0]
    evidence = tuple(dict.fromkeys(
        attempted.evidence_refs + resource.evidence_refs
    ))
    return ApplicationModuleSyntaxRepairSketch(
        resource=resource,
        descriptor=syntax,
        realization=realization,
        evidence_refs=evidence,
    )


def plan_native_application_module_syntax_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    _budget: NativePlanningBudget,
) -> NativeSemanticRequestProduction:
    if invocation.state_ref != proof_ir.state_ref:
        raise ValueError("application module syntax planning crossed StateRef")
    sketch = discover_unique_application_module_syntax_repair(proof_ir)
    if sketch is None:
        return NativeSemanticRequestProduction.not_applicable(
            APPLICATION_MODULE_SYNTAX_NATIVE_PRODUCER_ID
        )
    digest = hashlib.sha256(
        (
            sketch.resource.resource_id
            + "\0"
            + sketch.realization.candidate_application_term
        ).encode("utf-8")
    ).hexdigest()[:20]
    return NativeSemanticRequestProduction.ready(
        APPLICATION_MODULE_SYNTAX_NATIVE_PRODUCER_ID,
        (NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=f"operation-binding-module-syntax:{digest}",
            producer_id=APPLICATION_MODULE_SYNTAX_NATIVE_PRODUCER_ID,
            query=NativeProofTermElaborationQuery(
                operation="call",
                application_term=(
                    sketch.realization.candidate_application_term
                ),
            ),
            evidence_refs=sketch.evidence_refs,
        ),),
    )


def analyze_native_application_module_syntax_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    sketch = discover_unique_application_module_syntax_repair(proof_ir)
    requests = plan_native_application_module_syntax_repair(
        proof_ir,
        coordinate,
        invocation,
        NativePlanningBudget(),
    ).requests
    if sketch is None or len(requests) != 1:
        return AnalysisContribution()
    request = requests[0]
    observations = tuple(
        item
        for item in proof_ir.native_semantic_observations
        if item.producer_id == APPLICATION_MODULE_SYNTAX_NATIVE_PRODUCER_ID
        and item.request_id == request.request_id
    )
    if len(observations) != 1:
        return AnalysisContribution()
    observation = observations[0]
    descriptor = observation.descriptor
    syntax = sketch.descriptor
    if (
        observation.status != "accepted"
        or not isinstance(descriptor, NativeProofTermDescriptor)
        or not descriptor.can_concretize
        or observation.query.application_term
        != sketch.realization.candidate_application_term
        or not resolved_head_matches_resource(
            descriptor.resolved_head.identity,
            sketch.resource.symbol,
        )
        or tuple(item.syntax_kind for item in descriptor.input_arguments)
        != syntax.candidate_argument_kinds
        or not descriptor.input_arguments
        or descriptor.input_arguments[0].syntax_kind != "module"
        or descriptor.input_arguments[0].explicit_hole
        or not descriptor.arguments
        or descriptor.arguments[0].kind != "module"
        or descriptor.arguments[0].hole
        or not descriptor.arguments[0].resolved_identity
    ):
        return AnalysisContribution()
    return native_application_contribution(
        resource=sketch.resource,
        observation=observation,
        producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
        identity_namespace="native-b2-application-module-syntax",
        evidence_refs=sketch.evidence_refs,
        trigger_id=proof_ir.attempted_operation.trigger_id,
    )


def _outer_parenthesized_body(value: str) -> str | None:
    if len(value) < 2 or value[0] != "(" or value[-1] != ")":
        return None
    depth = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0 or (depth == 0 and index != len(value) - 1):
                return None
    return value[1:-1].strip() if depth == 0 else None


def _first_top_level_space(value: str) -> int | None:
    depth = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return None
        elif character.isspace() and depth == 0:
            return index
    return None


def _first_application_argument(
    value: str,
) -> tuple[str, str, bool] | None:
    text = value.strip()
    if not text:
        return None
    if text[0] == "(":
        depth = 0
        for index, character in enumerate(text):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth < 0:
                    return None
                if depth == 0:
                    return (
                        text[1:index].strip(),
                        text[index + 1:].strip(),
                        True,
                    )
        return None
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return None
        elif character.isspace() and depth == 0:
            return text[:index].strip(), text[index:].strip(), False
    return (text, "", False) if depth == 0 else None


def _balanced_delimiters(value: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for character in value:
        if character in "([{":
            stack.append(character)
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                return False
    return not stack
