"""Agent-facing context topic intents.

Historically the agent submitted ``inspect_context`` with a ``topic`` payload.
The public surface now exposes the concrete topic names directly
(``call_subgoals``, ``operator_lemmas``, ``tactic_forms``, ...).  The manager still
accepts the wrapper for replay/back-compat, but prompts, schemas, and projected
views should show these direct intents.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


INTENT_CLASS_PROOF_MUTATION = "proof_mutation"
INTENT_CLASS_PROOF_CONTROL = "proof_control"
INTENT_CLASS_CONTEXT_TOPIC = "context_topic"
INTENT_CLASS_SYMBOL_LOOKUP = "symbol_lookup"
INTENT_CLASS_LEGACY_WRAPPER = "legacy_wrapper"


@dataclass(frozen=True)
class IntentSpec:
    """Agent-facing intent contract metadata.

    ``inspect_context`` remains parseable for replay/back-compat, but it is not
    advertised: public surfaces should expose the concrete context topic intent
    (``call_subgoals``, ``operator_lemmas``, ...) and attach this metadata so renderers
    do not infer categories from names.
    """

    name: str
    intent_class: str
    read_only: bool
    payload_fields: tuple[str, ...] = ()
    description: str = ""
    advertised: bool = True


CONTEXT_TOPIC_ALIASES: dict[str, str] = {
    "bridge_options": "pr_bridge_routes",
    "bridge_lemmas": "equiv_bridge_lemmas",
}

CONTEXT_TOPIC_INTENTS = frozenset({
    "goal_info",
    "diagnose",
    "episode_view",
    "proof_frontier",
    "workspace_view",
    "align",
    "subgoal_gap",
    "lemma_hints",
    "lemma_index",
    "equiv_bridge_lemmas",
    "suggest_close",
    "pivot_context",
    "verified_pivot_options",
    "call_site_options",
    "pr_bridge_routes",
    "call_invariant_skeleton",
    "rewrite_candidates",
    "call_subgoals",
    "tactic_forms",
    "operator_lemmas",
    "inv_from_lemma",
    "probability_budget_ledger",
    "checkpoints",
})

CONTEXT_TOPIC_PAYLOAD_FIELDS: dict[str, tuple[str, ...]] = {
    "call_subgoals": ("invariant",),
    "tactic_forms": ("name",),
    "operator_lemmas": ("operator",),
    "inv_from_lemma": ("lemma",),
}

CONTEXT_TOPIC_DESCRIPTIONS: dict[str, str] = {
    "goal_info": "parsed goal shape and names",
    "diagnose": "latest failure diagnosis for the current route",
    "call_site_options": "live call-site context for the current frontier",
    "call_subgoals": "read-only preview of obligations for a candidate call invariant",
    "operator_lemmas": "project-local and stdlib lemmas mentioning an operator or term skeleton",
    "lemma_index": "indexed lemma candidates from the loaded context",
    "tactic_forms": "valid EasyCrypt forms for one tactic family",
    "checkpoints": "semantic rewind menu for committed proof steps",
}

NON_ADVERTISED_CONTEXT_TOPICS = frozenset({
    # Backend/replay still accepts this old broad parser report, but the typed
    # SurfaceModel now carries the goal/status/frontier facts directly.  Do not
    # advertise it in MCP schemas, agent followups, or human cards.
    "goal_info",
    # Broad whole-file lemma roster.  Agents may read the current `.ec` source
    # and use state-specific lookup/search surfaces; do not surface this as a
    # normal manager affordance.
    "lemma_index",
})


_BASE_INTENT_SPECS: dict[str, IntentSpec] = {
    "commit_tactic": IntentSpec(
        "commit_tactic",
        INTENT_CLASS_PROOF_MUTATION,
        False,
        ("tactic",),
        "apply a tactic to the committed EasyCrypt proof state",
    ),
    "commit_replay_suffix_chunk": IntentSpec(
        "commit_replay_suffix_chunk",
        INTENT_CLASS_PROOF_MUTATION,
        False,
        ("chunk_id",),
        "commit a saved replay suffix chunk",
    ),
    "lookup_symbol": IntentSpec(
        "lookup_symbol",
        INTENT_CLASS_SYMBOL_LOOKUP,
        True,
        ("symbol",),
        "resolve one named symbol's declaration or definition",
    ),
    "undo_last_step": IntentSpec(
        "undo_last_step",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        (),
        "undo the last committed tactic",
    ),
    "undo_to_checkpoint": IntentSpec(
        "undo_to_checkpoint",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        ("checkpoint_id", "confirm", "confirmation_id", "restore_id"),
        "open or execute a semantic rewind menu",
    ),
    "fresh_restart": IntentSpec(
        "fresh_restart",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        ("confirm", "confirmation_id"),
        "erase this node's committed branch after confirmation",
    ),
    "amend_and_replay": IntentSpec(
        "amend_and_replay",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        ("tactic_index", "replacement"),
        "edit an earlier committed step and replay the prefix",
    ),
    "finish": IntentSpec(
        "finish",
        INTENT_CLASS_PROOF_CONTROL,
        False,
        (),
        "ask the manager to finish or report why the proof is not finishable",
    ),
    "inspect_context": IntentSpec(
        "inspect_context",
        INTENT_CLASS_LEGACY_WRAPPER,
        True,
        ("topic",),
        "legacy wrapper accepted for replay/back-compat; not a public affordance",
        advertised=False,
    ),
}


INTENT_REGISTRY: dict[str, IntentSpec] = {
    **_BASE_INTENT_SPECS,
    **{
        topic: IntentSpec(
            topic,
            INTENT_CLASS_CONTEXT_TOPIC,
            True,
            CONTEXT_TOPIC_PAYLOAD_FIELDS.get(topic, ()),
            CONTEXT_TOPIC_DESCRIPTIONS.get(topic, "read-only semantic proof context"),
            advertised=topic not in NON_ADVERTISED_CONTEXT_TOPICS,
        )
        for topic in CONTEXT_TOPIC_INTENTS
    },
}

MANAGER_INTENTS = frozenset(
    name for name, spec in INTENT_REGISTRY.items() if spec.advertised
)
PROTOCOL_INTENTS = frozenset(INTENT_REGISTRY)
READ_ONLY_INTENTS = frozenset(
    name for name, spec in INTENT_REGISTRY.items() if spec.read_only
)


def normalize_context_topic(value: Any, *, default: str = "goal_info") -> str:
    topic = str(value or default).strip().replace("-", "_")
    if not topic:
        topic = default
    return CONTEXT_TOPIC_ALIASES.get(topic, topic)


def is_context_topic_intent(intent: Any) -> bool:
    return normalize_context_topic(intent, default="") in CONTEXT_TOPIC_INTENTS


def intent_spec(intent: Any) -> IntentSpec | None:
    name = str(intent or "").strip().replace("-", "_")
    normalized = normalize_context_topic(name, default="")
    if normalized in CONTEXT_TOPIC_INTENTS:
        name = normalized
    return INTENT_REGISTRY.get(name)


def intent_class(intent: Any) -> str:
    spec = intent_spec(intent)
    return spec.intent_class if spec else "unknown"


def intent_is_read_only(intent: Any) -> bool:
    spec = intent_spec(intent)
    return bool(spec and spec.read_only)


def intent_is_retrieval(intent: Any) -> bool:
    spec = intent_spec(intent)
    return bool(
        spec
        and spec.intent_class in {
            INTENT_CLASS_CONTEXT_TOPIC,
            INTENT_CLASS_SYMBOL_LOOKUP,
            INTENT_CLASS_LEGACY_WRAPPER,
        }
    )


def intent_payload_fields(intent: Any) -> tuple[str, ...]:
    spec = intent_spec(intent)
    return spec.payload_fields if spec else ()


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
    raw_intent = str(out.get("intent") or "").strip().replace("-", "_")
    payload = out.get("payload") if isinstance(out.get("payload"), dict) else {}
    public_intent = raw_intent
    if raw_intent == "inspect_context":
        topic = normalize_context_topic(payload.get("topic"), default="")
        if topic in CONTEXT_TOPIC_INTENTS:
            public_intent = topic
    spec = intent_spec(public_intent)
    if spec is None:
        return out
    out["intent_class"] = spec.intent_class
    out["read_only"] = spec.read_only
    if public_intent and public_intent != raw_intent:
        out["public_intent"] = public_intent
    if spec.payload_fields:
        out["payload_fields"] = list(spec.payload_fields)
    elif "payload_fields" in out:
        out.pop("payload_fields", None)
    return out


def context_payload_for_intent(
    intent: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the legacy backend payload for a direct topic intent."""
    data = dict(payload) if isinstance(payload, dict) else {}
    data["topic"] = normalize_context_topic(intent)
    return data


def direct_context_request(request: dict[str, Any]) -> dict[str, Any]:
    """Convert an inspect_context request object to the public direct-intent form."""
    if not isinstance(request, dict):
        return {}
    out = dict(request)
    payload = dict(out.get("payload") or {}) if isinstance(out.get("payload"), dict) else {}
    intent = str(out.get("intent") or "").strip()
    if intent == "inspect_context":
        topic = normalize_context_topic(payload.get("topic"))
        payload.pop("topic", None)
        out["intent"] = topic
        out["payload"] = payload
    elif is_context_topic_intent(intent):
        out["intent"] = normalize_context_topic(intent)
        payload.pop("topic", None)
        out["payload"] = payload
    return add_intent_contract(out)
