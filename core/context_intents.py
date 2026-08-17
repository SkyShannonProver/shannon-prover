"""Canonical current proof intents.

The fresh compiler runtime exposes proof mutation/control plus compiler output;
the retired inspect-topic and symbol-lookup protocols are intentionally absent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


INTENT_CLASS_PROOF_MUTATION = "proof_mutation"
INTENT_CLASS_PROOF_CONTROL = "proof_control"


@dataclass(frozen=True)
class IntentSpec:
    """Agent-facing intent contract metadata.

    Public surfaces attach this metadata so renderers do not infer categories
    from names.
    """

    name: str
    intent_class: str
    read_only: bool
    payload_fields: tuple[str, ...] = ()
    description: str = ""
    advertised: bool = True
    persistent_control: bool = False
    control_interaction: str = ""
    control_requires_input: tuple[str, ...] = ()
    display_label: str = ""
    may_mutate_proof_state: bool = False
    required_payload_fields: tuple[str, ...] = ()


_BASE_INTENT_SPECS: dict[str, IntentSpec] = {
    "commit_tactic": IntentSpec(
        "commit_tactic",
        INTENT_CLASS_PROOF_MUTATION,
        False,
        ("tactic",),
        "apply a tactic to the committed EasyCrypt proof state",
        persistent_control=True,
        control_interaction="input",
        control_requires_input=("tactic",),
        display_label="Commit tactic",
        may_mutate_proof_state=True,
        required_payload_fields=("tactic",),
    ),
    "undo_last_step": IntentSpec(
        "undo_last_step",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        (),
        "undo the last committed tactic",
        persistent_control=True,
        control_interaction="direct",
        display_label="Undo last",
        may_mutate_proof_state=True,
    ),
    "undo_to_checkpoint": IntentSpec(
        "undo_to_checkpoint",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        ("checkpoint_id", "confirm", "confirmation_id", "restore_id"),
        "open or execute a semantic rewind menu",
        persistent_control=True,
        control_interaction="menu",
        display_label="Rewind",
        may_mutate_proof_state=True,
    ),
    "fresh_restart": IntentSpec(
        "fresh_restart",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        ("confirm", "confirmation_id"),
        "erase this node's committed branch after confirmation",
        persistent_control=True,
        control_interaction="confirmation",
        display_label="Restart",
        may_mutate_proof_state=True,
    ),
    "amend_and_replay": IntentSpec(
        "amend_and_replay",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        ("index", "tactic"),
        "replace one committed tactic and replay the remaining verified prefix",
        persistent_control=True,
        control_interaction="menu",
        control_requires_input=("index", "tactic"),
        display_label="Amend & replay",
        may_mutate_proof_state=True,
        required_payload_fields=("index", "tactic"),
    ),
    "finish": IntentSpec(
        "finish",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        (),
        "ask the manager to finish or report why the proof is not finishable",
        persistent_control=True,
        control_interaction="menu",
        display_label="Finish",
    ),
}


INTENT_REGISTRY: dict[str, IntentSpec] = dict(_BASE_INTENT_SPECS)

MANAGER_INTENTS = frozenset(
    name for name, spec in INTENT_REGISTRY.items() if spec.advertised
)
PROTOCOL_INTENTS = frozenset(INTENT_REGISTRY)
READ_ONLY_INTENTS = frozenset(
    name for name, spec in INTENT_REGISTRY.items() if spec.read_only
)
NONEMPTY_STRING_PAYLOAD_FIELDS = frozenset({
    "tactic",
    "checkpoint_id",
    "restore_id",
    "confirmation_id",
})


def persistent_control_specs() -> tuple[IntentSpec, ...]:
    """Return the canonical always-available proof-control catalog.

    Protocol parsing, profile gating, prompts, and human controls all consume
    this order. State-dependent proof actions and read-only context requests do
    not belong in this catalog.
    """
    return tuple(
        spec for spec in INTENT_REGISTRY.values()
        if spec.persistent_control
    )


def persistent_control_names() -> frozenset[str]:
    return frozenset(spec.name for spec in persistent_control_specs())


def persistent_control_catalog() -> tuple[dict[str, Any], ...]:
    """Serializable proof-control metadata for agent and human clients."""
    return tuple(
        {
            "intent": spec.name,
            "label": spec.display_label or spec.name,
            "description": spec.description,
            "interaction": spec.control_interaction,
            "requires_input": list(spec.control_requires_input),
        }
        for spec in persistent_control_specs()
    )


def control_menu_intents() -> frozenset[str]:
    """Intents whose unconfirmed/underspecified result may be a typed menu."""
    return frozenset(
        spec.name
        for spec in INTENT_REGISTRY.values()
        if spec.control_interaction in {"menu", "confirmation"}
    )


def intent_spec(intent: Any) -> IntentSpec | None:
    name = str(intent or "").strip()
    return INTENT_REGISTRY.get(name)


def intent_class(intent: Any) -> str:
    spec = intent_spec(intent)
    return spec.intent_class if spec else "unknown"


def intent_is_read_only(intent: Any) -> bool:
    spec = intent_spec(intent)
    return bool(spec and spec.read_only)


def intent_may_mutate_proof_state(intent: Any) -> bool:
    spec = intent_spec(intent)
    return bool(spec and spec.may_mutate_proof_state)


def intent_payload_fields(intent: Any) -> tuple[str, ...]:
    spec = intent_spec(intent)
    return spec.payload_fields if spec else ()


def canonicalize_intent_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical scalar representation used by the live protocol."""

    canonical = dict(payload)
    for field_name in NONEMPTY_STRING_PAYLOAD_FIELDS:
        value = canonical.get(field_name)
        if isinstance(value, str):
            canonical[field_name] = value.strip()
    return canonical


def intent_payload_contract_error(
    intent: Any,
    payload: dict[str, Any],
    *,
    require_required_fields: bool = True,
) -> str:
    """Validate the shared exact field/type contract for one intent payload.

    State-dependent control variants remain manager-owned.  Compiler-emitted
    actions and the manager parser share this lower-level shape contract so a
    compiler action cannot be rendered as exact while being protocol-invalid.
    """

    spec = intent_spec(intent)
    if spec is None:
        return "unknown_or_missing_intent"
    unexpected = sorted(set(payload) - set(spec.payload_fields))
    if unexpected:
        return "unexpected_payload_fields"
    for field_name, value in payload.items():
        if field_name in NONEMPTY_STRING_PAYLOAD_FIELDS:
            if type(value) is not str or not value.strip():
                return f"payload_field_{field_name}_must_be_nonempty_string"
        elif field_name == "confirm":
            if type(value) is not bool:
                return "payload_field_confirm_must_be_bool"
        elif field_name == "index":
            if type(value) is not int or value < 1:
                return "payload_field_index_must_be_positive_int"
        else:
            return f"unsupported_payload_field_{field_name}"
    if require_required_fields and any(
        field not in payload for field in spec.required_payload_fields
    ):
        return "missing_required_payload_fields"
    return ""


def intents_by_class(
    intents: set[str] | frozenset[str] | list[str] | tuple[str, ...],
    intent_cls: str,
) -> list[str]:
    return sorted(
        name for name in intents
        if intent_class(name) == intent_cls
    )


def add_intent_contract(request: dict[str, Any]) -> dict[str, Any]:
    """Attach the public intent taxonomy to an intent-shaped request object."""
    if not isinstance(request, dict):
        return {}
    out = dict(request)
    raw_intent = str(out.get("intent") or "").strip()
    spec = intent_spec(raw_intent)
    if spec is None:
        return out
    out["intent_class"] = spec.intent_class
    out["read_only"] = spec.read_only
    if spec.payload_fields:
        out["payload_fields"] = list(spec.payload_fields)
    elif "payload_fields" in out:
        out.pop("payload_fields", None)
    return out
