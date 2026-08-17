"""Authority-free vocabulary shared by core and workflow action evidence.

These values describe evidence.  They never carry a submit payload, proof-state
identity, producer, or live execution authority. The exact tactic-preflight
artifact and compiler delivery contracts remain separate, boundary-local
value objects.
"""
from __future__ import annotations


ACTION_EVIDENCE_SCHEMA_VERSION = 1

ACTION_LIFECYCLES = frozenset({
    "observation",
    "candidate",
    "ready_for_preflight",
    "executable_current_state",
})
ACTION_TYPES = frozenset({
    "runnable_tactic",
    "tactic_candidate",
    "inspection_action",
    "strategy_hint",
    "avoid_action",
    "warning",
})
BINDING_STATUSES = frozenset({
    "not_applicable",
    "incomplete",
    "complete",
})
PREREQUISITE_DISPOSITIONS = frozenset({
    "satisfied",
    "deferred_as_obligation",
    "unresolved",
})
VALIDATION_STATUSES = frozenset({
    "not_checked",
    "schema_checked",
    "daemon_accepted_on_exact_state",
    "daemon_rejected_on_exact_state",
})
NO_PROGRESS_STATUSES = frozenset({
    "not_checked",
    "progress",
    "no_progress",
})
EFFECT_KINDS = frozenset({
    "context_only",
    "proof_state_transition",
    "unknown",
})
RESIDUAL_OBLIGATION_KINDS = frozenset({
    "none",
    "closed",
    "proof_obligations",
    "unknown",
})

# Strict field vocabularies let conversion tests detect semantic drift while
# preserving separate objects and authority boundaries.
CORE_RUNNABLE_EVIDENCE_FIELDS = frozenset({
    "schema_version",
    "lifecycle",
    "action_type",
    "exact_submit",
    "binding_status",
    "resolved_bindings",
    "prerequisites",
    "validation_status",
    "no_progress_status",
    "effect_kind",
    "previewed_effect",
    "residual_obligations",
    "unresolved_dependencies",
    "strategic_non_guarantee",
    "source_refs",
    "evidence_refs",
})

WORKFLOW_PROOF_OPTION_EVIDENCE_FIELDS = frozenset({
    *CORE_RUNNABLE_EVIDENCE_FIELDS,
    "current_state_preflight",
})


def vocabulary_error(value: object, allowed: frozenset[str], field: str) -> str:
    """Return an error for an unknown vocabulary value, else an empty string."""

    if not isinstance(value, str) or value not in allowed:
        return f"{field} must be one of {', '.join(sorted(allowed))}"
    return ""
