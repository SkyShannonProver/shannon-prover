"""The one feature-neutral ActionSurface-to-Markdown contract.

P4 owns this adapter.  It first projects the typed, audit-complete
``ActionSurface`` to a closed presentation payload, then renders the exact
Markdown block whose UTF-8 size is used for delivery admission.  Workflow
receives the final text and must embed it byte-for-byte; it does not render a
second time.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.easycrypt.proof_state_compiler.contracts.action_surface import (
    ActionSurface,
    VerifiedAction,
    validate_compiler_action,
)
from core.easycrypt.proof_state_compiler.contracts.delivery import (
    CHANGED_FACT,
    COMMITMENT_RESULT,
    FAILURE_LINKED_REPAIR,
    OPTIONAL_ADVISORY,
)
from core.easycrypt.proof_state_compiler.contracts.presentation import (
    MAX_INTERNAL_PRESENTATION_BYTES,
)
from core.easycrypt.proof_state_compiler.contracts.strategy import (
    COMMITMENT_RELATIVE,
)


ACTION_SURFACE_PAYLOAD_SCHEMA_VERSION = 1

OPTIONAL_CHECKED_FACT_HEADING = "Optional checked fact available"
OPTIONAL_CHECKED_FACT_NOTICE = (
    "The compiler found a fact supporting the application below, and EasyCrypt "
    "verified that the application is valid in the current proof state.\n\n"
    "You may use it now or leave it unused. Using it selects one continuation "
    "and changes the remaining proof obligations, so decide whether it fits the "
    "proof route you want to pursue."
)

_PRESENTATION_KINDS = frozenset({
    CHANGED_FACT,
    COMMITMENT_RESULT,
    FAILURE_LINKED_REPAIR,
    OPTIONAL_ADVISORY,
})


class PresentationContractError(ValueError):
    """The closed presentation payload does not satisfy schema v1."""


@dataclass(frozen=True)
class RenderedCompilerMarkdown:
    """Exact compiler block plus measurements; never written into the payload."""

    text: str
    utf8_bytes: int
    characters: int
    sha256: str

    def __post_init__(self) -> None:
        encoded = self.text.encode("utf-8")
        if self.utf8_bytes != len(encoded):
            raise ValueError("compiler Markdown byte measurement is inconsistent")
        if self.characters != len(self.text):
            raise ValueError(
                "compiler Markdown character measurement is inconsistent"
            )
        if self.sha256 != hashlib.sha256(encoded).hexdigest():
            raise ValueError("compiler Markdown hash is inconsistent")


def action_surface_payload(surface: ActionSurface) -> dict[str, Any]:
    """Project only values consumed by the fixed Markdown contract.

    Feature IDs, evidence, verifier refs, lifetime/strategy metadata, native
    binding internals, and measurements remain on the typed/audit side.  The
    action payload is retained in full only after the shared compiler-action
    contract has restricted it to manager-valid ``commit_tactic``/``tactic``;
    the renderer displays that exact object inside a JSON fence.
    """

    if not isinstance(surface, ActionSurface):
        raise TypeError("presentation projection requires an ActionSurface")
    return {
        "schema_version": ACTION_SURFACE_PAYLOAD_SCHEMA_VERSION,
        "resources": [
            {
                "resource_id": item.resource_id,
                "label": item.label,
            }
            for item in surface.resource_references
        ],
        "bindings": [
            {
                "resource_id": item.resource_id,
                # Native binding details are intentionally audit-only until a
                # typed presentation schema explicitly admits individual fields.
                "unresolved": list(item.unresolved),
            }
            for item in surface.binding_references
        ],
        "actions": [_action_payload(item) for item in surface.actions],
        "diagnostics": [
            {
                "primary": item.diagnostic.primary,
                **(
                    {"notes": list(item.diagnostic.notes)}
                    if item.diagnostic.notes else {}
                ),
                **(
                    {"placeholder_shape": item.diagnostic.placeholder_shape}
                    if item.diagnostic.placeholder_shape else {}
                ),
                **({"help": item.diagnostic.help} if item.diagnostic.help else {}),
                **(
                    {"terminal": item.diagnostic.terminal}
                    if item.diagnostic.terminal else {}
                ),
            }
            for item in surface.diagnostics
        ],
    }


def render_action_surface(surface: ActionSurface) -> RenderedCompilerMarkdown:
    """Project and render one typed surface under the sole v1 contract."""

    return render_action_surface_payload(action_surface_payload(surface))


def render_action_surface_payload(
    payload: dict[str, Any],
) -> RenderedCompilerMarkdown:
    """Validate and deterministically render ``ActionSurfacePayload v1``."""

    _validate_payload(payload)
    blocks: list[str] = []
    blocks.extend(_render_action(item) for item in payload["actions"])
    if payload["resources"]:
        blocks.append(_render_resources(payload["resources"]))
    if payload["bindings"]:
        blocks.append(_render_bindings(payload["bindings"]))
    blocks.extend(_render_diagnostic(item) for item in payload["diagnostics"])
    text = "\n\n".join(blocks)
    encoded = text.encode("utf-8")
    return RenderedCompilerMarkdown(
        text=text,
        utf8_bytes=len(encoded),
        characters=len(text),
        sha256=hashlib.sha256(encoded).hexdigest(),
    )


def _action_payload(item: VerifiedAction) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "intent": item.intent,
        "payload": item.payload.to_dict(),
        "presentation_kind": item.delivery.presentation_kind,
        "checked_local_effect": _checked_local_effect(
            item.checked_effect.to_dict()
        ),
    }
    if item.correction is not None:
        payload["correction"] = {
            "kind": item.correction.presentation_kind,
            "reason": item.correction.reason,
        }
    if (
        item.unresolved_premises
        and item.delivery.strategy_class != COMMITMENT_RELATIVE
    ):
        payload["unresolved_premises"] = list(item.unresolved_premises)
    return payload


def _checked_local_effect(effect: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    closed = effect.get("goal_after_closed")
    remaining = effect.get("goal_after_remaining")
    if type(closed) is bool:
        compact["closed"] = closed
    if type(remaining) is int and remaining >= 0:
        compact["remaining_goals"] = remaining
    return compact


def _render_action(action: dict[str, Any]) -> str:
    blocks: list[str] = []
    correction = action.get("correction")
    if isinstance(correction, dict):
        blocks.extend(("## Do you mean?", correction["reason"]))
    else:
        presentation_kind = action["presentation_kind"]
        if presentation_kind == OPTIONAL_ADVISORY:
            blocks.extend((
                f"## {OPTIONAL_CHECKED_FACT_HEADING}",
                OPTIONAL_CHECKED_FACT_NOTICE,
            ))
        elif presentation_kind == FAILURE_LINKED_REPAIR:
            blocks.append("## Checked repair for the attempted operation")
        elif presentation_kind == COMMITMENT_RESULT:
            blocks.append("## Checked elaboration of your selected operation")
        elif presentation_kind == CHANGED_FACT:
            blocks.append("## Verified compiler action")
        else:  # pragma: no cover - schema validation owns this branch
            raise PresentationContractError("unknown action presentation kind")
    submit = {
        "intent": action["intent"],
        "payload": action["payload"],
    }
    blocks.append(
        "EasyCrypt checked this exact local action:\n"
        "```json\n"
        + json.dumps(submit, ensure_ascii=False, separators=(",", ":"))
        + "\n```"
    )
    effect = action["checked_local_effect"]
    if effect.get("closed") is True:
        blocks.append("Checked local effect: this action closes the goal.")
    elif type(effect.get("remaining_goals")) is int:
        blocks.append(
            "Checked local effect: "
            f"{effect['remaining_goals']} goal(s) remain."
        )
    premises = action.get("unresolved_premises")
    if premises:
        blocks.append(
            "Remaining premises after the action:\n"
            + "\n".join(f"- `{_escape_inline_code(item)}`" for item in premises)
        )
    return "\n\n".join(blocks)


def _render_resources(resources: list[dict[str, Any]]) -> str:
    rows = ["## Relevant resources"]
    rows.extend(
        f"- `{_escape_inline_code(item['resource_id'])}`: {item['label']}"
        for item in resources
    )
    return "\n".join(rows)


def _render_bindings(bindings: list[dict[str, Any]]) -> str:
    rows = ["## Native resource bindings"]
    for item in bindings:
        rows.append(f"- Resource: `{_escape_inline_code(item['resource_id'])}`")
        if item["unresolved"]:
            rows.append(
                "  - Remaining unresolved slots: "
                + ", ".join(
                    f"`{_escape_inline_code(value)}`"
                    for value in item["unresolved"]
                )
            )
        else:
            rows.append("  - Remaining unresolved slots: none.")
    return "\n".join(rows)


def _render_diagnostic(diagnostic: dict[str, Any]) -> str:
    blocks = ["## Compiler diagnostic", diagnostic["primary"]]
    notes = diagnostic.get("notes")
    if notes:
        blocks.append("\n".join(f"- {item}" for item in notes))
    shape = diagnostic.get("placeholder_shape")
    if shape:
        blocks.append("Typed application shape:\n```easycrypt\n" + shape + "\n```")
    help_text = diagnostic.get("help")
    if help_text:
        blocks.append("Help: " + help_text)
    terminal = diagnostic.get("terminal")
    if terminal:
        blocks.append(terminal)
    return "\n\n".join(blocks)


def _validate_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise PresentationContractError("presentation payload must be an object")
    _require_exact_keys(
        payload,
        required={
            "schema_version",
            "resources",
            "bindings",
            "actions",
            "diagnostics",
        },
        label="presentation payload",
    )
    if payload["schema_version"] != ACTION_SURFACE_PAYLOAD_SCHEMA_VERSION:
        raise PresentationContractError("unsupported presentation schema version")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_INTERNAL_PRESENTATION_BYTES:
        raise PresentationContractError(
            "presentation payload exceeds the internal safety bound"
        )
    for key in ("resources", "bindings", "actions", "diagnostics"):
        if not isinstance(payload[key], list):
            raise PresentationContractError(f"{key} must be an array")
    for item in payload["resources"]:
        _require_exact_keys(
            item,
            required={"resource_id", "label"},
            label="resource presentation",
        )
        _require_nonempty_strings(item, "resource_id", "label")
    for item in payload["bindings"]:
        _require_exact_keys(
            item,
            required={"resource_id", "unresolved"},
            label="binding presentation",
        )
        _require_nonempty_strings(item, "resource_id")
        _require_string_list(item["unresolved"], "binding unresolved slots")
    for item in payload["actions"]:
        _validate_action(item)
    for item in payload["diagnostics"]:
        _validate_diagnostic(item)


def _validate_action(item: object) -> None:
    _require_exact_keys(
        item,
        required={
            "intent",
            "payload",
            "presentation_kind",
            "checked_local_effect",
        },
        optional={"correction", "unresolved_premises"},
        label="action presentation",
    )
    _require_nonempty_strings(item, "intent", "presentation_kind")
    if item["presentation_kind"] not in _PRESENTATION_KINDS:
        raise PresentationContractError("unknown action presentation kind")
    try:
        validate_compiler_action(item["intent"], item["payload"])
    except (TypeError, ValueError) as exc:
        raise PresentationContractError(str(exc)) from exc
    effect = item["checked_local_effect"]
    _require_exact_keys(
        effect,
        required=set(),
        optional={"closed", "remaining_goals"},
        label="checked local effect",
    )
    if "closed" in effect and type(effect["closed"]) is not bool:
        raise PresentationContractError("checked closed effect must be boolean")
    if "remaining_goals" in effect and (
        type(effect["remaining_goals"]) is not int
        or effect["remaining_goals"] < 0
    ):
        raise PresentationContractError(
            "checked remaining-goal effect must be a nonnegative integer"
        )
    correction = item.get("correction")
    if correction is not None:
        _require_exact_keys(
            correction,
            required={"kind", "reason"},
            label="correction presentation",
        )
        _require_nonempty_strings(correction, "kind", "reason")
        if correction["kind"] != "do_you_mean":
            raise PresentationContractError("unknown correction presentation kind")
    if "unresolved_premises" in item:
        _require_string_list(
            item["unresolved_premises"],
            "unresolved premises",
        )


def _validate_diagnostic(item: object) -> None:
    _require_exact_keys(
        item,
        required={"primary"},
        optional={"notes", "placeholder_shape", "help", "terminal"},
        label="diagnostic presentation",
    )
    _require_nonempty_strings(item, "primary")
    if "notes" in item:
        _require_string_list(item["notes"], "diagnostic notes")
    for key in ("placeholder_shape", "help", "terminal"):
        if key in item:
            _require_nonempty_strings(item, key)


def _require_exact_keys(
    value: object,
    *,
    required: set[str],
    label: str,
    optional: set[str] | None = None,
) -> None:
    if not isinstance(value, dict):
        raise PresentationContractError(f"{label} must be an object")
    optional = optional or set()
    keys = set(value)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise PresentationContractError(f"{label} fields do not match schema v1")


def _require_nonempty_strings(value: dict[str, Any], *keys: str) -> None:
    if any(
        not isinstance(value.get(key), str) or not value[key].strip()
        for key in keys
    ):
        raise PresentationContractError(
            "presentation string fields must be nonempty strings"
        )


def _require_string_list(value: object, label: str) -> None:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise PresentationContractError(f"{label} must be a string array")


def _escape_inline_code(value: str) -> str:
    # Values are still readable/copyable while a future backtick cannot break
    # the surrounding Markdown structure.
    return value.replace("`", "\\`")
