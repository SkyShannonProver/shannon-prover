"""Feature-neutral composition of one native compound-boundary handoff."""

from __future__ import annotations

from dataclasses import replace

from core.easycrypt.proof_state_compiler.contracts.analyzed_state import (
    AnalyzedProofState,
)
from core.easycrypt.proof_state_compiler.contracts.candidate_surface import (
    ActionCandidate,
    DiagnosticCandidate,
)
from core.easycrypt.proof_state_compiler.contracts.correction import (
    CorrectionPresentation,
    DO_YOU_MEAN,
)
from core.easycrypt.proof_state_compiler.contracts.failure import RecoveryHandoff
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.contracts.digest import (
    canonical_json,
    text_sha256,
)
from core.easycrypt.proof_state_compiler.compound_boundary_text import (
    compound_boundary_summary,
)


RECOVERY_HANDOFF_INTERNAL_PRESENTATION_BOUND_EXCEEDED = (
    "recovery_handoff_internal_presentation_bound_exceeded"
)


def present_recovery_handoff(
    state: AnalyzedProofState,
    actions: tuple[ActionCandidate, ...],
    diagnostics: tuple[DiagnosticCandidate, ...],
) -> tuple[
    tuple[ActionCandidate, ...],
    tuple[DiagnosticCandidate, ...],
    tuple[str, ...],
]:
    """Attach boundary context and recompose a selected suffix recovery.

    Compound recovery discovers the exact suffix; it does not know which
    proof-domain feature will own that suffix.  This P4 composition therefore
    runs only after ownership resolution and decorates the one selected
    feature result without producer-specific or operation-family dispatch.
    Generic producer identity is retained only as delivery authorization.  A
    state-changing prefix is never exposed as a suffix-only action: the exact
    repaired suffix is recomposed with the native-accepted prefix before the
    manager certifies the complete tactic at the original ``StateRef``.
    """

    attempted = state.attempted_operation
    handoff = None if attempted is None else attempted.recovery_handoff
    ownership = state.recovery_ownership
    if handoff is None or not ownership.owns(
        ownership.owner_feature_id,
        attempted.recovery_key,
    ):
        return actions, diagnostics, ()
    owner = ownership.owner_feature_id
    trigger_id = attempted.trigger_id
    presented_actions = []
    internal_presentation_bound_exceeded = False
    for item in actions:
        if (
            item.feature_id == owner
            and item.trigger_id == trigger_id
            and item.feature_id != handoff.source_feature_id
        ):
            presented, exceeded = _present_action(item, state, handoff)
            internal_presentation_bound_exceeded |= exceeded
        else:
            presented = item
        if presented is not None:
            presented_actions.append(presented)
    presented_diagnostics = []
    for item in diagnostics:
        if (
            item.feature_id == owner
            and item.trigger_id == trigger_id
            and item.feature_id != handoff.source_feature_id
        ):
            presented, exceeded = _present_diagnostic(item, handoff)
            internal_presentation_bound_exceeded |= exceeded
        else:
            presented = item
        if presented is not None:
            presented_diagnostics.append(presented)
    audit_reasons = (
        (RECOVERY_HANDOFF_INTERNAL_PRESENTATION_BOUND_EXCEEDED,)
        if internal_presentation_bound_exceeded
        else ()
    )
    return (
        tuple(presented_actions),
        tuple(presented_diagnostics),
        audit_reasons,
    )


def recovery_handoff_message(handoff: RecoveryHandoff) -> str:
    """Return the shared exact-state explanation for agent presentation."""

    return compound_boundary_summary(
        accepted_prefix=handoff.accepted_prefix_tactic,
        accepted_effect=handoff.accepted_prefix_effect,
        accepted_stage_count=handoff.accepted_prefix_stage_count,
        rejected_extension=handoff.derived_rejected_tactic,
        native_error=handoff.native_error_message,
        parse_error=handoff.native_failure_kind == "parse_error",
    )


def _present_action(
    item: ActionCandidate,
    state: AnalyzedProofState,
    handoff: RecoveryHandoff,
) -> tuple[ActionCandidate | None, bool]:
    base = recovery_handoff_message(handoff)
    existing = item.correction
    presented_item = item
    if handoff.prefix_changes_state or handoff.later_stages:
        # The action is the agent's tactic with only the failing stage
        # replaced: a state-changing prefix and every later stage stay.
        suffix_tactic = str(item.payload.to_dict().get("tactic") or "").strip()
        complete_tactic = compose_recovery_handoff_action(
            (
                handoff.accepted_prefix_tactic
                if handoff.prefix_changes_state else ""
            ),
            suffix_tactic,
            handoff.later_stages,
        )
        if complete_tactic is None:
            return None, False
        identity_material = canonical_json({
            "source_candidate_id": item.candidate_id,
            "handoff": handoff.to_payload(),
            "complete_tactic": complete_tactic,
        })
        presented_item = replace(
            item,
            candidate_id="compound-boundary-action:" + text_sha256(
                identity_material
            )[:20],
            payload=freeze_json_object({"tactic": complete_tactic}),
        )
    reason = (
        base + "\n\n" + existing.reason
        if existing is not None
        else base
    )
    try:
        correction = CorrectionPresentation(
            presentation_kind=DO_YOU_MEAN,
            reason_code=(
                existing.reason_code
                if existing is not None
                else "native_compound_boundary_recovery"
            ),
            reason=reason,
        )
    except ValueError:
        # The native strings exceeded the broad internal schema bound.
        # Agent delivery budgets are enforced later over the final Markdown.
        return None, True
    witness_id = presented_item.recovery_witness_id
    if not witness_id and state.recovery_ownership.preservation_witness:
        witness_id = (
            state.recovery_ownership.preservation_witness.witness_id
        )
    if not witness_id:
        return None, False
    return (
        replace(
            presented_item,
            recovery_witness_id=witness_id,
            correction=correction,
            delivery_dependency_feature_ids=_delivery_dependencies(
                presented_item.feature_id,
                presented_item.delivery_dependency_feature_ids,
                handoff,
            ),
        ),
        False,
    )


def compose_recovery_handoff_action(
    accepted_prefix_tactic: str,
    repaired_suffix_tactic: str,
    later_stages: str = "",
) -> str | None:
    """Join exact tactics without interpreting any tactic family.

    ``accepted_prefix_tactic`` is empty when the accepted prefix is a no-op
    and stays out of the action. ``later_stages`` are the agent's stages
    after the failing one (no final dot), kept so that the action changes
    only the failing stage. The agent's own spelling, line breaks included,
    is kept; only the joining ``; `` is normalized.
    """

    tactics = (
        (accepted_prefix_tactic,) if accepted_prefix_tactic else ()
    ) + (repaired_suffix_tactic,)
    if any(
        not value
        or value != value.strip()
        or not value.endswith(".")
        for value in tactics
    ) or later_stages != later_stages.strip() or later_stages.endswith("."):
        return None
    suffix = repaired_suffix_tactic[:-1].strip()
    if not suffix:
        return None
    parts = [
        *((accepted_prefix_tactic[:-1].rstrip(),) if accepted_prefix_tactic else ()),
        suffix,
        *((later_stages,) if later_stages else ()),
    ]
    if any(not part for part in parts):
        return None
    return "; ".join(parts) + "."


def recovery_handoff_action_suffix(
    handoff: RecoveryHandoff | None,
    presented_tactic: str,
) -> str | None:
    """Recover the exact feature-owned suffix from one presented action."""

    if handoff is None:
        return presented_tactic
    if not presented_tactic.endswith("."):
        return None
    body = presented_tactic[:-1]
    prefix_tactic = (
        handoff.accepted_prefix_tactic if handoff.prefix_changes_state else ""
    )
    if prefix_tactic:
        marker = prefix_tactic[:-1].rstrip() + "; "
        if not body.startswith(marker):
            return None
        body = body[len(marker):]
    later = handoff.later_stages
    if later:
        ending = "; " + later
        if not body.endswith(ending):
            return None
        body = body[:-len(ending)]
    suffix = body + "."
    if not body or compose_recovery_handoff_action(
        prefix_tactic,
        suffix,
        later,
    ) != presented_tactic:
        return None
    return suffix


def _present_diagnostic(
    item: DiagnosticCandidate,
    handoff: RecoveryHandoff,
) -> tuple[DiagnosticCandidate | None, bool]:
    base = recovery_handoff_message(handoff)
    diagnostic = item.diagnostic
    primary = base + "\n\n" + diagnostic.primary
    try:
        composed = replace(diagnostic, primary=primary)
    except ValueError:
        return None, True
    return (
        replace(
            item,
            diagnostic=composed,
            delivery_dependency_feature_ids=_delivery_dependencies(
                item.feature_id,
                item.delivery_dependency_feature_ids,
                handoff,
            ),
        ),
        False,
    )


def _delivery_dependencies(
    owner_feature_id: str,
    existing: tuple[str, ...],
    handoff: RecoveryHandoff,
) -> tuple[str, ...]:
    """Return upstream treatment dependencies without creating another owner."""

    return tuple(sorted(
        (set(existing) | {handoff.source_feature_id})
        - {owner_feature_id}
    ))
