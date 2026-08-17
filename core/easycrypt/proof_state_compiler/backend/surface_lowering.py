"""Aggregate generic P4 lowerers into an internal CandidateSurface."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Protocol

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    AnalyzedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    CompilerInvocationContext,
)
from core.easycrypt.proof_state_compiler.contracts.candidate_surface import (
    ActionCandidate,
    BindingReferenceCandidate,
    CandidateSurface,
    DiagnosticCandidate,
    ResourceReferenceCandidate,
)
from core.easycrypt.proof_state_compiler.derived_provenance import derived_provenance
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    single_operation_identity,
)
from core.easycrypt.proof_state_compiler.contracts.failure import (
    EXACT_OPERATION_RESOURCE_WITNESS,
    NATIVE_ARGUMENT_REALIZATION_WITNESS,
    NATIVE_TACTIC_PREFIX_WITNESS,
)
from core.easycrypt.proof_state_compiler.backend.recovery_handoff_lowering import (
    present_recovery_handoff,
    recovery_handoff_action_suffix,
)


@dataclass(frozen=True)
class SurfaceContribution:
    resource_references: tuple[ResourceReferenceCandidate, ...] = ()
    binding_references: tuple[BindingReferenceCandidate, ...] = ()
    actions: tuple[ActionCandidate, ...] = ()
    diagnostics: tuple[DiagnosticCandidate, ...] = ()


class SurfaceLowerer(Protocol):
    def __call__(
        self,
        state: AnalyzedProofState,
        invocation: CompilerInvocationContext,
    ) -> SurfaceContribution: ...


def build_candidate_surface(
    state: AnalyzedProofState,
    lowerers: tuple[SurfaceLowerer, ...] = (),
    invocation: CompilerInvocationContext | None = None,
) -> CandidateSurface:
    if invocation is None:
        from core.easycrypt.proof_state_compiler.contracts.delivery import (
            compiler_invocation_context,
        )
        invocation = compiler_invocation_context(
            state.state_ref,
            source_event_id=state.provenance.source_event_id,
        )
    if invocation.state_ref != state.state_ref:
        raise ValueError("P4 invocation context is stale")
    contributions = tuple(lowerer(state, invocation) for lowerer in lowerers)
    resources = tuple(
        item
        for contribution in contributions
        for item in contribution.resource_references
    )
    bindings = tuple(
        item
        for contribution in contributions
        for item in contribution.binding_references
    )
    actions = tuple(
        item for contribution in contributions for item in contribution.actions
    )
    diagnostics = tuple(
        item for contribution in contributions for item in contribution.diagnostics
    )
    actions, diagnostics, handoff_audit_reasons = present_recovery_handoff(
        state,
        actions,
        diagnostics,
    )
    diagnostics = tuple(
        replace(
            item,
            recovery_lifetime_scope_id=_recovery_diagnostic_lifetime_scope(
                state, item
            ),
        )
        if not item.recovery_lifetime_scope_id
        else item
        for item in diagnostics
    )
    audit_reasons: tuple[str, ...] = handoff_audit_reasons
    failure_trigger = (
        invocation.event_trigger
        if (
            invocation.event_trigger is not None
            and invocation.failure_observation is not None
        )
        else None
    )
    if failure_trigger is not None:
        ownership = state.recovery_ownership
        attempted = state.attempted_operation

        def allowed(item: object) -> bool:
            trigger_id = getattr(item, "trigger_id", "")
            if trigger_id != failure_trigger.trigger_id:
                return True
            return ownership.owns(
                getattr(item, "feature_id", ""),
                ownership.recovery_key,
            )

        resources = tuple(item for item in resources if allowed(item))
        bindings = tuple(item for item in bindings if allowed(item))
        actions = tuple(item for item in actions if allowed(item))
        diagnostics = tuple(item for item in diagnostics if allowed(item))
        recovery_candidates = tuple(
            item
            for collection in (resources, bindings, actions, diagnostics)
            for item in collection
            if getattr(item, "trigger_id", "") == failure_trigger.trigger_id
        )
        invalid_identity = bool(
            recovery_candidates
            and (
                attempted is None
                or any(
                    not _preserves_attempted_operation(
                        item, attempted, ownership
                    )
                    for item in recovery_candidates
                )
            )
        )
        if invalid_identity or len(recovery_candidates) > 1:
            resources = tuple(
                item for item in resources
                if item.trigger_id != failure_trigger.trigger_id
            )
            bindings = tuple(
                item for item in bindings
                if item.trigger_id != failure_trigger.trigger_id
            )
            actions = tuple(
                item for item in actions
                if item.trigger_id != failure_trigger.trigger_id
            )
            diagnostics = tuple(
                item for item in diagnostics
                if item.trigger_id != failure_trigger.trigger_id
            )
            audit_reasons = tuple(dict.fromkeys((
                *audit_reasons,
                (
                    "recovery_candidate_changed_operation_or_resource"
                    if invalid_identity
                    else "recovery_owner_emitted_multiple_candidates"
                ),
            )))
        elif ownership.audit_reason:
            audit_reasons = tuple(dict.fromkeys((
                *audit_reasons,
                ownership.audit_reason,
            )))
    candidate_ids = [
        item.candidate_id
        for collection in (resources, bindings, actions, diagnostics)
        for item in collection
    ]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("P4 lowerers emitted duplicate candidate IDs")
    return CandidateSurface(
        state_ref=state.state_ref,
        provenance=derived_provenance(
            "p4.candidate_surface", state.state_ref, state.provenance
        ),
        resource_references=resources,
        binding_references=bindings,
        actions=actions,
        diagnostics=diagnostics,
        audit_reasons=audit_reasons,
    )


def _recovery_diagnostic_lifetime_scope(
    state: AnalyzedProofState,
    item: DiagnosticCandidate,
) -> str:
    """Group repeated variants that add no new recovery boundary evidence."""

    attempted = state.attempted_operation
    ownership = state.recovery_ownership
    witness = ownership.preservation_witness
    if (
        attempted is None
        or witness is None
        or not ownership.owns(item.feature_id, attempted.recovery_key)
        or item.trigger_id != attempted.trigger_id
    ):
        return ""
    handoff = attempted.recovery_handoff
    material = {
        "goal_identity": state.state_ref.goal_identity,
        "committed_prefix_identity": state.state_ref.committed_prefix_identity,
        "feature_id": item.feature_id,
        "operation_family": attempted.operation_family,
        "selected_resource": attempted.exact_resource,
        "native_diagnostic_status": attempted.native_diagnostic_status,
        "native_failure_kind": attempted.native_failure_kind,
        "diagnostic_code": item.diagnostic.code,
        "diagnostic_applicability": item.diagnostic.applicability,
        "witness_kind": witness.witness_kind,
        "native_family": witness.native_family,
        # For a compound-prefix diagnostic this is the exact accepted prefix;
        # a strictly longer/different boundary receives a new scope.  The full
        # rejected compound is intentionally absent, so suffix spelling churn
        # at one goal does not create new agent-facing information.
        "realization_sha256": witness.realization_sha256,
        "boundary_prefix": (
            "" if handoff is None else handoff.accepted_prefix_tactic
        ),
        "boundary_effect": (
            "" if handoff is None else handoff.accepted_prefix_effect
        ),
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _preserves_attempted_operation(
    item: object,
    attempted: object,
    ownership: object,
) -> bool:
    """Check identity only; exact tactic certification remains EasyCrypt-owned."""

    if isinstance(item, DiagnosticCandidate):
        return "diagnostic" in ownership.allowed_output_kinds
    if not isinstance(item, ActionCandidate) or (
        "action" not in ownership.allowed_output_kinds
    ):
        return False
    witness = ownership.preservation_witness
    if witness is None:
        return False
    presented_tactic = str(
        item.payload.to_dict().get("tactic") or ""
    ).strip()
    tactic = recovery_handoff_action_suffix(
        getattr(attempted, "recovery_handoff", None),
        presented_tactic,
    )
    if tactic is None:
        return False
    if witness.witness_kind == NATIVE_ARGUMENT_REALIZATION_WITNESS:
        return bool(
            item.recovery_witness_id == witness.witness_id
            and item.correction is not None
            and tactic.startswith(witness.target_operation_family + " ")
            and hashlib.sha256(tactic.encode("utf-8")).hexdigest()
            == witness.realization_sha256
            and "\n" not in tactic
            and "\r" not in tactic
        )
    if witness.witness_kind == NATIVE_TACTIC_PREFIX_WITNESS:
        rejected = str(getattr(attempted, "rejected_tactic", "") or "")
        if (
            not tactic.endswith(".")
            or not rejected.endswith(".")
            or hashlib.sha256(rejected.encode("utf-8")).hexdigest()
            != witness.committed_argument_sha256
        ):
            return False
        prefix_body = tactic[:-1].rstrip()
        rejected_body = rejected[:-1]
        remainder = rejected_body[len(prefix_body):]
        return bool(
            item.recovery_witness_id == witness.witness_id
            and item.correction is not None
            and prefix_body
            and rejected_body.startswith(prefix_body)
            and remainder.lstrip().startswith(";")
            and hashlib.sha256(tactic.encode("utf-8")).hexdigest()
            == witness.realization_sha256
        )
    if witness.witness_kind != EXACT_OPERATION_RESOURCE_WITNESS:
        return False
    parsed = single_operation_identity(tactic)
    if parsed is None:
        return False
    operation, resource = parsed
    if operation != witness.target_operation_family:
        return False
    if ownership.resource_match_kind == "none":
        return not resource
    if ownership.resource_match_kind == "basename":
        return resource.rsplit(".", 1)[-1] == (
            ownership.selected_resource.rsplit(".", 1)[-1]
        )
    return resource == ownership.selected_resource
