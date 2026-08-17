"""Feature-neutral compiler service telemetry."""

from __future__ import annotations

import json
import re
from typing import Any

from core.easycrypt.proof_state_compiler.backend import (
    AdmissionResult,
    action_surface_payload,
)
from core.easycrypt.proof_state_compiler.contracts import (
    CompilationBundle,
    CertificationResult,
    CompilerInvocationContext,
    CompilerTrigger,
    AGENT_SELECTED_OPERATION,
    CURRENT_STATE_FAILURE,
    DeclarationLoadRequest,
    NativeSemanticObservation,
    NativeSemanticPlan,
    NativeSemanticRequest,
    EXPLICIT_CONTEXT_REQUEST,
    STATE_REFRESH,
    TRIGGER_KINDS,
)
from core.easycrypt.proof_state_compiler.contracts.delivery_policy import (
    ResolvedDeliveryPlan,
)
from core.easycrypt.proof_state_compiler.features.execution import (
    FeatureExecutionPlan,
)
from workflow.proof_state_compiler.activation import ActivationPlan


DELIVERY_TELEMETRY_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _native_descriptor_summary(
    observation: NativeSemanticObservation,
) -> dict[str, Any]:
    descriptor = (
        observation.descriptor.to_payload()
        if observation.descriptor is not None
        else {}
    )
    head = descriptor.get("resolved_head")
    arguments = descriptor.get("arguments")
    residuals = descriptor.get("residual_proof_premises")
    summary = {
        "descriptor_present": bool(descriptor),
        "operation_family": str(descriptor.get("operation_family") or ""),
        "native_failure_kind": str(
            descriptor.get("native_failure_kind") or ""
        ),
        "resolved_head": dict(head) if isinstance(head, dict) else {},
        "argument_count": len(arguments) if isinstance(arguments, list) else 0,
        "residual_proof_premise_count": (
            len(residuals) if isinstance(residuals, list) else 0
        ),
    }
    if all(
        field in descriptor
        for field in (
            "candidate_module_term_count",
            "candidate_check_count",
            "typed_binding_count",
            "checked_completion_count",
            "population_complete",
        )
    ):
        summary["selected_application_binding_set"] = {
            "candidate_module_term_count": descriptor[
                "candidate_module_term_count"
            ],
            "candidate_check_count": descriptor[
                "candidate_check_count"
            ],
            "typed_binding_count": descriptor["typed_binding_count"],
            "checked_completion_count": descriptor[
                "checked_completion_count"
            ],
            "population_complete": descriptor["population_complete"],
            "reason": str(descriptor.get("reason") or ""),
        }
    return summary


def _native_batch_summaries(
    observations: tuple[NativeSemanticObservation, ...],
) -> list[dict[str, Any]]:
    batches: dict[str, list[NativeSemanticObservation]] = {}
    for item in observations:
        batches.setdefault(item.batch_id, []).append(item)
    summaries = []
    for batch_id, members in batches.items():
        ordered = sorted(members, key=lambda item: (
            item.batch_index, item.request_id
        ))
        first = ordered[0]
        units: dict[int, list[NativeSemanticObservation]] = {}
        for item in ordered:
            units.setdefault(item.batch_index, []).append(item)
        if tuple(sorted(units)) != tuple(range(first.batch_size)) or any(
            item.batch_size != first.batch_size for item in ordered
        ):
            raise ValueError("native semantic batch telemetry is inconsistent")
        if any(
            item.batch_elapsed_ms != first.batch_elapsed_ms
            or item.batch_cache_state != first.batch_cache_state
            or item.batch_build_elapsed_ms != first.batch_build_elapsed_ms
            or item.batch_execution_elapsed_ms
            != first.batch_execution_elapsed_ms
            or item.state_ref != first.state_ref
            or item.runtime_identity_sha256 != first.runtime_identity_sha256
            or item.companion_identity_sha256
            != first.companion_identity_sha256
            or item.provenance != first.provenance
            for item in ordered[1:]
        ):
            raise ValueError("native semantic batch authority drifted")
        summaries.append({
            "batch_id": batch_id,
            "execution_unit_count": len(units),
            "consumer_request_count": len(ordered),
            "request_ids": [item.request_id for item in ordered],
            "accepted": sum(item.status == "accepted" for item in ordered),
            "rejected": sum(item.status == "rejected" for item in ordered),
            "cache_state": first.batch_cache_state,
            "build_elapsed_ms": first.batch_build_elapsed_ms,
            "execution_elapsed_ms": first.batch_execution_elapsed_ms,
            "elapsed_ms": first.batch_elapsed_ms,
            "source_event_id": first.provenance.source_event_id,
            "artifact_ref": first.provenance.artifact_ref,
        })
    return summaries


def validate_delivery_telemetry(value: object) -> tuple[str, ...]:
    """Validate the serialized trigger-occurrence contract used by audits."""

    errors: list[str] = []
    if not isinstance(value, dict):
        return ("delivery telemetry must be an object",)
    if type(value.get("schema_version")) is not int or value.get(
        "schema_version"
    ) != DELIVERY_TELEMETRY_SCHEMA_VERSION:
        errors.append("delivery telemetry has an unsupported schema_version")
    refresh = value.get("state_refresh_trigger")
    if not isinstance(refresh, dict):
        errors.append("delivery telemetry requires state_refresh_trigger")
        refresh = {}
    if refresh.get("trigger_kind") != STATE_REFRESH:
        errors.append("delivery state_refresh_trigger has the wrong kind")
    for field in ("trigger_id", "source_event_id"):
        if not isinstance(refresh.get(field), str) or not refresh.get(field):
            errors.append(f"delivery state_refresh_trigger requires {field}")
    available = value.get("available_triggers")
    if not isinstance(available, list) or not available or len(available) > 2:
        errors.append("delivery requires one or two available_triggers")
        available = []
    ids: list[str] = []
    for index, item in enumerate(available):
        if not isinstance(item, dict):
            errors.append(f"delivery trigger {index} must be an object")
            continue
        trigger_id = item.get("trigger_id")
        source_event_id = item.get("source_event_id")
        trigger_kind = item.get("trigger_kind")
        anchor_id = item.get("commitment_anchor_id")
        anchor_kind = item.get("commitment_anchor_kind")
        anchor_event_id = item.get("commitment_anchor_source_event_id")
        if not isinstance(trigger_id, str) or not trigger_id:
            errors.append(f"delivery trigger {index} requires trigger_id")
        else:
            ids.append(trigger_id)
        if not isinstance(source_event_id, str) or not source_event_id:
            errors.append(f"delivery trigger {index} requires source_event_id")
        if trigger_kind not in TRIGGER_KINDS:
            errors.append(f"delivery trigger {index} has an invalid trigger_kind")
        if trigger_kind in {STATE_REFRESH, EXPLICIT_CONTEXT_REQUEST}:
            if any(value not in (None, "") for value in (
                anchor_id,
                anchor_kind,
                anchor_event_id,
            )):
                errors.append(
                    f"delivery trigger {index} cannot carry a commitment anchor"
                )
        elif trigger_kind in {AGENT_SELECTED_OPERATION, CURRENT_STATE_FAILURE}:
            for field, field_value in (
                ("commitment_anchor_id", anchor_id),
                ("commitment_anchor_kind", anchor_kind),
                ("commitment_anchor_source_event_id", anchor_event_id),
            ):
                if not isinstance(field_value, str) or not field_value:
                    errors.append(f"delivery trigger {index} requires {field}")
            if anchor_event_id != source_event_id:
                errors.append(
                    f"delivery trigger {index} anchor crosses event authority"
                )
    if len(ids) != len(set(ids)):
        errors.append("delivery available_triggers contain duplicate IDs")
    if available and isinstance(available[0], dict) and any(
        available[0].get(field) != refresh.get(field)
        for field in ("trigger_id", "trigger_kind", "source_event_id")
    ):
        errors.append("delivery refresh trigger is not the leading available trigger")
    presented = value.get("presented_delivery_ids")
    if not isinstance(presented, list) or any(
        not isinstance(item, str) or not item for item in presented
    ):
        errors.append("delivery presented_delivery_ids must be non-empty strings")
    elif len(presented) != len(set(presented)):
        errors.append("delivery presented_delivery_ids contain duplicates")
    context_sha256 = value.get("invocation_context_sha256")
    if not isinstance(context_sha256, str) or not _SHA256_RE.fullmatch(
        context_sha256
    ):
        errors.append("delivery invocation_context_sha256 must be lowercase SHA-256")
    for field in ("lifetime_ledger_size", "lifetime_suppressed"):
        field_value = value.get(field)
        if type(field_value) is not int or field_value < 0:
            errors.append(f"delivery {field} must be a non-negative integer")
    return tuple(errors)


def compilation_telemetry(
    bundle: CompilationBundle,
    certifications: tuple[CertificationResult, ...],
    admission: AdmissionResult,
    *,
    environment_id: str,
    activation_plan: ActivationPlan,
    compiler_feature_ids: tuple[str, ...],
    feature_execution_plan: FeatureExecutionPlan,
    feature_execution_lifetime_size: int,
    manifest_id: str,
    certification_feature_ids: tuple[str, ...],
    admitted_feature_ids: tuple[str, ...],
    admitted_strategy_classes: tuple[str, ...],
    delivery_plan: ResolvedDeliveryPlan,
    planned_resource_loads: tuple[DeclarationLoadRequest, ...],
    resource_load_report: tuple[dict[str, Any], ...],
    loaded_declarations: tuple[Any, ...],
    planned_native_semantics: tuple[NativeSemanticRequest, ...],
    native_semantic_plans: tuple[NativeSemanticPlan, ...],
    native_semantic_observations: tuple[NativeSemanticObservation, ...],
    timings_ms: dict[str, int],
    exact_observation_cache: dict[str, Any],
    certification_cache: dict[str, Any],
    resource_cache: dict[str, Any],
    certification_work_performed: bool,
    state_refresh_trigger: CompilerTrigger,
    invocation_context: CompilerInvocationContext,
    delivery_lifetime_size: int,
) -> dict[str, Any]:
    if state_refresh_trigger != invocation_context.state_refresh:
        raise ValueError(
            "telemetry state refresh diverges from compiler invocation context"
        )
    if delivery_plan.profile_id != manifest_id:
        raise ValueError("telemetry delivery plan diverges from manifest")
    if tuple(compiler_feature_ids) != feature_execution_plan.eligible_feature_ids:
        raise ValueError("telemetry compiler features diverge from execution plan")
    if (
        type(feature_execution_lifetime_size) is not int
        or feature_execution_lifetime_size < 0
    ):
        raise ValueError("telemetry execution lifetime size is invalid")
    available_trigger_ids = {
        item.trigger_id for item in invocation_context.triggers
    }
    if any(
        item.trigger_id and item.trigger_id not in available_trigger_ids
        for item in admission.decisions
    ):
        raise ValueError(
            "admission decision trigger is absent from invocation context"
        )
    candidate = bundle.candidate_surface
    all_candidates = tuple(
        item
        for collection in (
            candidate.resource_references,
            candidate.binding_references,
            candidate.actions,
            candidate.diagnostics,
        )
        for item in collection
    )
    candidates_by_id = {
        item.candidate_id: item for item in all_candidates
    }
    presentation_payload = action_surface_payload(admission.action_surface)
    presentation_payload_bytes = len(json.dumps(
        presentation_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8"))
    delivery = {
        "schema_version": DELIVERY_TELEMETRY_SCHEMA_VERSION,
        "state_refresh_trigger": {
            "trigger_id": state_refresh_trigger.trigger_id,
            "trigger_kind": state_refresh_trigger.trigger_kind,
            "source_event_id": state_refresh_trigger.source_event_id,
        },
        "available_triggers": [
            {
                "trigger_id": item.trigger_id,
                "trigger_kind": item.trigger_kind,
                "source_event_id": item.source_event_id,
                "commitment_anchor_id": (
                    item.commitment_anchor.anchor_id
                    if item.commitment_anchor is not None
                    else ""
                ),
                "commitment_anchor_kind": (
                    item.commitment_anchor.anchor_kind
                    if item.commitment_anchor is not None
                    else ""
                ),
                "commitment_anchor_source_event_id": (
                    item.commitment_anchor.source_event_id
                    if item.commitment_anchor is not None
                    else ""
                ),
            }
            for item in invocation_context.triggers
        ],
        "invocation_context_sha256": invocation_context.identity_sha256,
        "presented_delivery_ids": list(admission.presented_delivery_ids),
        "lifetime_ledger_size": delivery_lifetime_size,
        "lifetime_suppressed": sum(
            item.reason == "delivery_lifetime_suppressed"
            for item in admission.decisions
        ),
    }
    delivery_errors = validate_delivery_telemetry(delivery)
    if delivery_errors:
        raise ValueError(
            "delivery telemetry contract: " + "; ".join(delivery_errors)
        )
    native_state = bundle.projected_state.native_state
    attempted_operation = bundle.proof_ir.attempted_operation
    native_batches = _native_batch_summaries(native_semantic_observations)
    return {
        "environment_id": environment_id,
        "exact_observation_cache": dict(exact_observation_cache),
        "certification_cache": dict(certification_cache),
        "resource_cache": dict(resource_cache),
        "activation_plan": {
            **activation_plan.to_dict(),
            "plan_sha256": activation_plan.plan_sha256,
        },
        "execution": {
            "status": "executed",
            **feature_execution_plan.to_dict(),
            "lifetime_ledger_size": feature_execution_lifetime_size,
        },
        "compiler_feature_ids": list(compiler_feature_ids),
        "manifest_id": manifest_id,
        "manifest": {
            "certification_feature_ids": list(certification_feature_ids),
            "admitted_feature_ids": list(admitted_feature_ids),
            "admitted_strategy_classes": list(admitted_strategy_classes),
            "delivery_plan": {
                **delivery_plan.to_dict(),
                "plan_sha256": delivery_plan.plan_sha256,
            },
        },
        "delivery": delivery,
        "attempted_operation": (
            {
                "attempt_id": attempted_operation.attempt_id,
                "occurrence_identity": (
                    attempted_operation.occurrence_identity
                ),
                "trigger_id": attempted_operation.trigger_id,
                "operation_family": attempted_operation.operation_family,
                "exact_resource": attempted_operation.exact_resource,
                "rejected_tactic": attempted_operation.rejected_tactic,
                "native_diagnostic_status": (
                    attempted_operation.native_diagnostic_status
                ),
                "native_failure_kind": (
                    attempted_operation.native_failure_kind
                ),
            }
            if attempted_operation is not None
            else {}
        ),
        "resource_loading": {
            "active_feature_ids": list(compiler_feature_ids),
            "planned_request_count": len(planned_resource_loads),
            "planned_requests": [request.runtime_payload()
                                 for request in planned_resource_loads],
            "request_count": len(resource_load_report),
            "loaded_declaration_count": sum(
                int(item.get("loaded_count") or 0)
                for item in resource_load_report
            ),
            "available_declaration_count": len(loaded_declarations),
            "reused_declaration_count": int(
                resource_cache.get("reused_declaration_count") or 0
            ),
            "elapsed_ms": sum(
                int(item.get("elapsed_ms") or 0)
                for item in resource_load_report
            ),
            "reports": [dict(item) for item in resource_load_report],
            "declarations": [{
                "symbol": str(item.symbol),
                "declaration_sha256": str(item.declaration_sha256),
                "declaration_head": str(item.declaration)[:240],
            } for item in loaded_declarations],
        },
        "native_semantics": {
            "active_feature_ids": list(compiler_feature_ids),
            "planned_request_count": len(planned_native_semantics),
            "planned_requests": [
                request.identity_payload()
                for request in planned_native_semantics
            ],
            "planning": {
                "stage_count": len(native_semantic_plans),
                "initial_budget": (
                    native_semantic_plans[0].budget.to_dict()
                    if native_semantic_plans
                    else {}
                ),
                "final_budget": (
                    native_semantic_plans[-1].budget.consume(
                        native_semantic_plans[-1]
                    ).to_dict()
                    if native_semantic_plans
                    else {}
                ),
                "decisions": [
                    {
                        "stage": stage_index,
                        **decision.to_dict(),
                    }
                    for stage_index, plan in enumerate(
                        native_semantic_plans, start=1
                    )
                    for decision in plan.decisions
                ],
            },
            "observation_count": len(native_semantic_observations),
            "batch_count": len(native_batches),
            "accepted": sum(
                item.status == "accepted"
                for item in native_semantic_observations
            ),
            "rejected": sum(
                item.status == "rejected"
                for item in native_semantic_observations
            ),
            "elapsed_ms": sum(item["elapsed_ms"] for item in native_batches),
            "batches": native_batches,
            "observations": [{
                "request_id": item.request_id,
                "feature_id": item.feature_id,
                "producer_id": item.producer_id,
                "request_identity_sha256": item.request_identity_sha256,
                "evaluation_prefix": list(item.evaluation_prefix),
                "batch_id": item.batch_id,
                "batch_index": item.batch_index,
                "batch_size": item.batch_size,
                "member_elapsed_ms": item.elapsed_ms,
                "status": item.status,
                "runtime_identity_sha256": item.runtime_identity_sha256,
                "companion_identity_sha256": item.companion_identity_sha256,
                "source_event_id": item.provenance.source_event_id,
                "artifact_ref": item.provenance.artifact_ref,
                **_native_descriptor_summary(item),
            } for item in native_semantic_observations],
        },
        "native_state": (
            {
                "present": True,
                "complete": native_state.complete,
                "truncation_reasons": list(native_state.truncation_reasons),
                "open_goal_count": native_state.open_goal_count,
                "runtime_identity_sha256": (
                    native_state.runtime_identity_sha256
                ),
                "companion_identity_sha256": (
                    native_state.companion_identity_sha256
                ),
                "source_event_id": native_state.provenance.source_event_id,
                "artifact_ref": native_state.provenance.artifact_ref,
                "elapsed_ms": native_state.elapsed_ms,
            }
            if native_state is not None
            else {
                "present": False,
                "complete": False,
                "truncation_reasons": [],
                "open_goal_count": 0,
                "runtime_identity_sha256": "",
                "companion_identity_sha256": "",
                "source_event_id": "",
                "artifact_ref": "",
                "elapsed_ms": 0,
            }
        ),
        "timings_ms": dict(timings_ms),
        "state": {
            "session_id": bundle.state_ref.session_id,
            "state_version": bundle.state_ref.state_version,
            "goal_identity": bundle.state_ref.goal_identity,
            "committed_prefix_identity": (
                bundle.state_ref.committed_prefix_identity
            ),
        },
        "candidate_counts": {
            "resources": len(candidate.resource_references),
            "bindings": len(candidate.binding_references),
            "actions": len(candidate.actions),
            "diagnostics": len(candidate.diagnostics),
            "audit_reasons": list(candidate.audit_reasons),
            "delivery_dependencies": {
                item.candidate_id: list(getattr(
                    item, "delivery_dependency_feature_ids", ()
                ))
                for item in all_candidates
                if getattr(item, "delivery_dependency_feature_ids", ())
            },
            "recovery_ownership": {
                "status": bundle.analyzed_state.recovery_ownership.status,
                "owner_feature_id": (
                    bundle.analyzed_state.recovery_ownership.owner_feature_id
                ),
                "claimant_feature_ids": list(
                    bundle.analyzed_state.recovery_ownership.claimant_feature_ids
                ),
                "audit_reason": (
                    bundle.analyzed_state.recovery_ownership.audit_reason
                ),
            },
            "by_strategy_class": {
                strategy_class: sum(
                    item.strategy_contract.strategy_class == strategy_class
                    for item in all_candidates
                )
                for strategy_class in sorted({
                    item.strategy_contract.strategy_class
                    for item in all_candidates
                })
            },
        },
        "certifications": {
            "total": len(certifications),
            "accepted": sum(item.accepted for item in certifications),
            "performed": (
                len(certifications) if certification_work_performed else 0
            ),
            "performed_accepted": (
                sum(item.accepted for item in certifications)
                if certification_work_performed
                else 0
            ),
            "reused": (
                0 if certification_work_performed else len(certifications)
            ),
            "records": [{
                "candidate_id": item.candidate_id,
                "policy": item.policy,
                "accepted": item.accepted,
                "verification_ref": item.verification_ref,
                "reuse": (
                    {
                        "material_state_sha256": (
                            item.reuse.material_state_sha256
                        ),
                        "origin_state_version": (
                            item.reuse.origin_state_ref.state_version
                        ),
                        "origin_input_event_id": (
                            item.reuse.origin_input_provenance.source_event_id
                        ),
                        "current_input_event_id": (
                            item.reuse.current_input_provenance.source_event_id
                        ),
                    }
                    if item.reuse is not None
                    else None
                ),
            } for item in certifications],
        },
        "admission": {
            "admitted": sum(item.admitted for item in admission.decisions),
            "rejected": sum(not item.admitted for item in admission.decisions),
            "reasons": [item.reason for item in admission.decisions],
            "compiler_markdown_bytes": admission.markdown_bytes,
            "compiler_markdown_characters": (
                admission.presentation.characters
            ),
            "compiler_markdown_sha256": admission.presentation.sha256,
            "presentation_payload_bytes": presentation_payload_bytes,
            # The bounded admitted surface is part of this authoritative
            # completion event.  This lets bulk experiment/audit readers
            # attribute non-action facts and diagnostics without treating a
            # rendered workspace file or stdout as semantic fallback.
            "agent_surface": presentation_payload,
            "presented_actions": [{
                "feature_id": item.feature_id,
                "strategy_class": item.strategy_contract.strategy_class,
                "delivery_kind": item.delivery.presentation_kind,
                "delivery_lifetime": item.delivery.lifetime,
                "intent": item.intent,
                "payload": item.payload.to_dict(),
            } for item in admission.action_surface.actions],
            "decisions": [{
                "candidate_id": item.candidate_id,
                "feature_id": item.feature_id,
                "strategy_class": candidates_by_id[
                    item.candidate_id
                ].strategy_contract.strategy_class,
                "trigger_id": item.trigger_id,
                "delivery_id": item.delivery_id,
                "admitted": item.admitted,
                "reason": item.reason,
                "candidate_markdown_bytes": item.candidate_markdown_bytes,
                "effective_max_markdown_bytes": item.effective_max_markdown_bytes,
                "surface_markdown_bytes": item.surface_markdown_bytes,
                "surface_max_markdown_bytes": item.surface_max_markdown_bytes,
            } for item in admission.decisions],
        },
        "candidate_features": [
            {
                "candidate_id": item.candidate_id,
                "feature_id": item.feature_id,
                "strategy_class": item.strategy_contract.strategy_class,
                "trigger_id": item.trigger_id,
            }
            for item in all_candidates
        ],
    }
