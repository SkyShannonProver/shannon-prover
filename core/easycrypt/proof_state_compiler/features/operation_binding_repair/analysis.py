"""P3 B1/B2/B4 operation-binding repair over shared attempted-operation IR."""

from __future__ import annotations

from dataclasses import replace

from core.easycrypt.proof_state_compiler.contracts import (
    CHOICE_REQUIRED,
    EXPLANATION_ONLY,
    ApplicationApplicability,
    CompilerInvocationContext,
    EvidenceRef,
    NativeApplicationSlotDescriptor,
    NativeModuleTermDescriptor,
    ProofCoordinate,
    ProofIR,
    RecoveryClaim,
    StructuredDiagnostic,
    exact_operation_resource_witness,
)
from core.easycrypt.proof_state_compiler.middle_end.contributions import (
    AnalysisContribution,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.feature import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.contracts import (
    OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.classification import (
    classify_operation_binding_failure,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.namespace_repair import (
    analyze_native_namespace_repair,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.losslessness_module_repair import (
    analyze_native_losslessness_module_repair,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.losslessness_call_repair import (
    analyze_native_losslessness_call_repair,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.application_module_syntax_repair import (
    analyze_native_application_module_syntax_repair,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.probability_multislot_repair import (
    PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID,
    analyze_native_probability_multislot_repair,
    matched_native_probability_multislot_observations,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.selected_application_binding_set import (
    matched_native_selected_application_binding_set,
)
from core.easycrypt.proof_state_compiler.middle_end.application_applicability import (
    assess_current_state_application,
)
from core.easycrypt.proof_state_compiler.middle_end.diagnostics import (
    structured_application_argument_alignment_diagnostic,
    structured_application_diagnostic,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    checked_entire_goal_reference,
    checked_goal_reference,
    checked_state_reference,
)
from core.easycrypt.proof_state_compiler.middle_end.native_application import (
    native_application_descriptor_contribution,
)


def analyze_operation_binding_repair(
    proof_ir: ProofIR,
    _coordinate: ProofCoordinate,
    _invocation: CompilerInvocationContext,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    failure_class = classify_operation_binding_failure(attempted)
    if attempted is None or failure_class is None:
        return AnalysisContribution()
    claim = RecoveryClaim(
        feature_id=OPERATION_BINDING_REPAIR_FEATURE_ID,
        recovery_key=attempted.recovery_key,
        attempt_id=attempted.attempt_id,
        occurrence_identity=attempted.occurrence_identity,
        trigger_id=attempted.trigger_id,
        operation_family=attempted.operation_family,
        selected_resource=attempted.exact_resource,
        resource_match_kind=(
            "basename" if failure_class == "B1" else "exact"
        ),
        allowed_output_kinds=("action", "diagnostic"),
        preservation_witness=exact_operation_resource_witness(
            attempted.operation_family,
            attempted.exact_resource,
        ),
        evidence_refs=attempted.evidence_refs,
    )
    contribution = AnalysisContribution()
    selected_binding_contribution = AnalysisContribution()
    selected_binding_diagnostic = None
    if failure_class == "B2":
        (
            selected_binding_contribution,
            selected_binding_diagnostic,
        ) = _analyze_selected_application_binding_set(proof_ir)
    probability_applicability = None
    if attempted.operation == "apply" and failure_class in {"B2", "B4"}:
        matches = matched_native_probability_multislot_observations(proof_ir)
        probability_applicability = assess_current_state_application(
            state_ref=proof_ir.state_ref,
            operation=attempted.operation,
            selected_resource=attempted.resource,
            planning_report=proof_ir.native_semantic_planning_report,
            native_observations=proof_ir.native_semantic_observations,
            feature_id=OPERATION_BINDING_REPAIR_FEATURE_ID,
            native_producer_id=(
                PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID
            ),
            matched_request_ids=tuple(
                observation.request_id for _sketch, observation in matches
            ),
        )
    if attempted.native_diagnostic_status != "indeterminate":
        contribution = (
            analyze_native_namespace_repair(proof_ir, _coordinate, _invocation)
            if failure_class == "B1"
            else _bind_application_shape_repair(
                proof_ir,
                _coordinate,
                _invocation,
                probability_applicability=probability_applicability,
                selected_binding_contribution=(
                    selected_binding_contribution
                ),
            )
        )
    applicability_items = (
        ()
        if probability_applicability is None
        else (probability_applicability,)
    )
    if (
        len(contribution.applications) == 1
        and selected_binding_diagnostic is None
    ):
        return _attach_recovery_claim(replace(
            contribution,
            application_applicabilities=applicability_items,
        ), claim)
    if failure_class not in {"B2", "B4"}:
        return _attach_recovery_claim(contribution, claim)
    diagnostic = selected_binding_diagnostic
    if diagnostic is None and not contribution.applications:
        diagnostic = structured_application_diagnostic(
            producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
            trigger_id=attempted.trigger_id,
            operation=attempted.operation,
            selected_resource=attempted.resource,
            native_failure_kind=attempted.native_failure_kind,
            applicability=probability_applicability,
            recovery_handoff=attempted.recovery_handoff,
            phase_boundary_mismatch=_phase_boundary_mismatch(proof_ir),
            evidence_refs=attempted.evidence_refs,
        )
    if diagnostic is None and not contribution.applications:
        diagnostic = structured_application_argument_alignment_diagnostic(
            attempted,
            producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
        )
    return _attach_recovery_claim(replace(
        AnalysisContribution(),
        application_applicabilities=applicability_items,
        diagnostics=() if diagnostic is None else (diagnostic,),
    ), claim)


def _attach_recovery_claim(
    contribution: AnalysisContribution,
    claim: RecoveryClaim,
) -> AnalysisContribution:
    """Attach the semantic claim and narrow its allowed visible result kind."""

    output_kinds = tuple(sorted({
        *({"action"} if contribution.applications else set()),
        *({"action"} if contribution.recovery_action_realizations else set()),
        *({"diagnostic"} if contribution.diagnostics else set()),
    }))
    if not output_kinds:
        return replace(contribution, recovery_claims=(claim,))
    return replace(
        contribution,
        recovery_claims=(replace(
            claim,
            allowed_output_kinds=output_kinds,
        ),),
    )


def _analyze_selected_application_binding_set(
    proof_ir: ProofIR,
) -> tuple[AnalysisContribution, StructuredDiagnostic | None]:
    """Classify one complete native same-resource binding set.

    The native adapter has already resolved the selected bare head,
    type-checked every module spelling combination, matched its result to the
    exact direct or temporary post-prefix goal, and preflighted the exact
    tactic. P3 owns only
    the visible outcome:
    one action, the complete small choice set, or the fact that none applied.
    """

    attempted = proof_ir.attempted_operation
    matched = matched_native_selected_application_binding_set(proof_ir)
    if (
        attempted is None
        or attempted.native_diagnostic_status != "blocker"
        or matched is None
    ):
        return AnalysisContribution(), None
    observation, descriptor = matched
    if not descriptor.population_complete:
        return AnalysisContribution(), None
    native_evidence = EvidenceRef(
        evidence_id=(
            "native-selected-application-binding-set:"
            + observation.provenance.source_event_id
        ),
        source_kind="native_selected_application_binding_set",
        source_ref=observation.provenance.artifact_ref,
        source_sha256=observation.provenance.source_sha256,
    )
    evidence = tuple(dict.fromkeys(
        attempted.evidence_refs + (native_evidence,)
    ))
    if descriptor.checked_completion_count == 1:
        resources = tuple(
            item for item in proof_ir.resources
            if item.symbol == attempted.resource
        )
        if len(resources) != 1 or len(descriptor.checked_completions) != 1:
            return AnalysisContribution(), None
        completion = descriptor.checked_completions[0]
        contribution = native_application_descriptor_contribution(
            resource=resources[0],
            descriptor=completion.descriptor,
            operation=descriptor.operation,
            application_term=completion.application_term,
            producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
            identity_namespace="native-selected-application-binding-set",
            evidence_refs=tuple(dict.fromkeys(
                evidence + resources[0].evidence_refs
            )),
            trigger_id=attempted.trigger_id,
        )
        return contribution, None
    resource_label = attempted.resource
    if descriptor.checked_completion_count == 0:
        head = attempted.application_head_descriptor
        requirement = (
            None
            if head is None
            else _module_argument_requirement(
                resource_label,
                head.slots,
                descriptor.module_slot_count,
            )
        )
        if requirement is None:
            return AnalysisContribution(), None
        operation = descriptor.operation
        handoff = attempted.recovery_handoff
        state_context = checked_state_reference(handoff)
        goal_context = checked_goal_reference(handoff)
        entire_goal_context = checked_entire_goal_reference(handoff)
        operation_rule = (
            "`apply H` can succeed only when the conclusion of the "
            "instantiated `H` matches—or can be unified with—"
            f"{entire_goal_context}."
            if operation == "apply"
            else (
                "`exact H` can succeed only when the instantiated `H` "
                f"proves {goal_context}."
            )
        )
        standalone_result = (
            "\n\nThe proof state is unchanged. The compiler found no "
            f"replacement `{operation}` that EasyCrypt accepts in this "
            "proof state."
            if handoff is None
            else ""
        )
        diagnostic = StructuredDiagnostic(
            producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
            code="selected_application_not_applicable",
            primary=(
                requirement
                + "\n\nSupplying these arguments only instantiates the "
                "theorem.\n\n"
                + "For the module candidates checked here, no completed "
                "instance makes this "
                f"`{operation}` succeed in {state_context}."
                + "\n\n"
                + operation_rule
                + standalone_result
            ),
            notes=(),
            help="",
            applicability=EXPLANATION_ONLY,
            evidence_refs=evidence,
            trigger_id=attempted.trigger_id,
        )
        return AnalysisContribution(), diagnostic
    if descriptor.checked_completions:
        help_text = (
            "EasyCrypt checked these exact same-resource alternatives for "
            "the failing stage:\n"
            + "\n".join(
                f"- `{item.candidate_tactic}`"
                for item in descriptor.checked_completions
            )
            + "\nChoose one only if it fits the proof route you want; the "
            "compiler selected none."
        )
    else:
        help_text = (
            "EasyCrypt found multiple checked same-resource bindings, but the "
            "complete set exceeds the bounded diagnostic surface. The "
            "compiler selected and displayed none."
        )
    try:
        state_context = checked_state_reference(attempted.recovery_handoff)
        diagnostic = StructuredDiagnostic(
            producer_id=OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID,
            code="selected_application_binding_choice_required",
            primary=(
                f"`{resource_label}` has multiple checked bindings in "
                f"{state_context}; no binding is uniquely determined."
            ),
            notes=(),
            help=help_text,
            applicability=CHOICE_REQUIRED,
            evidence_refs=evidence,
            trigger_id=attempted.trigger_id,
        )
    except ValueError:
        return AnalysisContribution(), None
    return AnalysisContribution(), diagnostic


def _module_argument_requirement(
    resource_label: str,
    slots: tuple[NativeApplicationSlotDescriptor, ...],
    expected_count: int,
) -> str | None:
    """Render only the exact ordered module slots searched by this feature."""

    module_slots = tuple(item for item in slots if item.kind == "module")
    if len(module_slots) != expected_count or not module_slots:
        return None
    rows = []
    for index, slot in enumerate(module_slots, start=1):
        if (
            not slot.name
            or not slot.type_text
            or any(char in slot.name + slot.type_text for char in "`\n\r")
            or len(slot.name.encode("utf-8")) > 80
            or len(slot.type_text.encode("utf-8")) > 160
        ):
            return None
        rows.append(
            f"{index}. `{slot.name}` with module type `{slot.type_text}`"
        )
    count = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
    }.get(len(module_slots), str(len(module_slots)))
    return (
        f"`{resource_label}` requires {count} module "
        f"argument{'s' if len(module_slots) != 1 else ''}, in this order:\n\n"
        + "\n".join(rows)
    )


def _phase_boundary_mismatch(proof_ir: ProofIR) -> tuple[str, str] | None:
    """Return one native-structural boundary mismatch, never text-derived."""

    attempted = proof_ir.attempted_operation
    goal = proof_ir.goal
    head = (
        None if attempted is None else attempted.application_head_descriptor
    )
    result_boundary = (
        None if head is None else head.result.boundary
    )
    formula = goal.formula_ir
    if (
        attempted is None
        or result_boundary is None
        or formula is None
        or goal.relation is None
        or formula.kind != "operator_application"
        or len(formula.children) != 2
        or formula.children[0].kind != "probability"
    ):
        return None
    current_properties = formula.children[0].properties.to_dict()
    current_procedure = current_properties.get("procedure")
    current_module = current_properties.get("procedure_module")
    if (
        not isinstance(current_procedure, str)
        or not current_procedure
        or not isinstance(current_module, dict)
        or current_procedure == result_boundary.procedure_identity
    ):
        return None
    differences = _module_term_differences(
        current_module, result_boundary.module
    )
    if differences is None or len(differences) != 1:
        return None
    current_label, result_label = differences[0]
    if not current_label or not result_label or current_label == result_label:
        return None
    return current_label, result_label


def _module_term_differences(
    current: dict[str, object],
    result: NativeModuleTermDescriptor,
) -> tuple[tuple[str, str], ...] | None:
    current_term = current.get("term")
    current_kind = current.get("top_kind")
    current_identity = current.get("top_identity")
    current_arguments = current.get("arguments")
    if (
        not isinstance(current_term, str)
        or not current_term
        or current_kind not in {"local", "concrete"}
        or not isinstance(current_identity, str)
        or not current_identity
        or not isinstance(current_arguments, list)
        or any(not isinstance(item, dict) for item in current_arguments)
    ):
        return None
    if (
        current_kind != result.top_kind
        or current_identity != result.top_identity
        or len(current_arguments) != len(result.arguments)
    ):
        return ((current_term, result.term),)
    differences: list[tuple[str, str]] = []
    for current_argument, result_argument in zip(
        current_arguments, result.arguments
    ):
        nested = _module_term_differences(current_argument, result_argument)
        if nested is None:
            return None
        differences.extend(nested)
    return tuple(differences)


def _bind_application_shape_repair(
    proof_ir: ProofIR,
    coordinate: ProofCoordinate,
    invocation: CompilerInvocationContext,
    *,
    probability_applicability: ApplicationApplicability | None,
    selected_binding_contribution: AnalysisContribution,
) -> AnalysisContribution:
    attempted = proof_ir.attempted_operation
    assert attempted is not None
    failure_class = classify_operation_binding_failure(attempted)
    alternatives = []
    if len(selected_binding_contribution.applications) == 1:
        alternatives.append(selected_binding_contribution)
    if failure_class == "B2":
        syntax = analyze_native_application_module_syntax_repair(
            proof_ir,
            coordinate,
            invocation,
        )
        if len(syntax.applications) == 1:
            alternatives.append(syntax)
        if attempted.operation == "apply":
            losslessness = analyze_native_losslessness_module_repair(
                proof_ir,
                coordinate,
                invocation,
            )
        elif attempted.operation == "call":
            losslessness = analyze_native_losslessness_call_repair(
                proof_ir,
                coordinate,
                invocation,
            )
        else:
            losslessness = AnalysisContribution()
        if len(losslessness.applications) == 1:
            alternatives.append(losslessness)

    if (
        attempted.operation == "apply"
        and probability_applicability is not None
        and probability_applicability.unique_checked_completion
    ):
        probability = analyze_native_probability_multislot_repair(
            proof_ir,
            coordinate,
            invocation,
        )
        if len(probability.applications) == 1:
            alternatives.append(probability)
    if len(alternatives) != 1:
        return AnalysisContribution()
    contribution = alternatives[0]
    application = contribution.applications[0]
    evidence = tuple(dict.fromkeys(
        attempted.evidence_refs + application.evidence_refs
    ))
    application = replace(application, evidence_refs=evidence)
    return AnalysisContribution(
        resources=contribution.resources,
        bindings=contribution.bindings,
        applications=(application,),
    )
