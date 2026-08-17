from __future__ import annotations

import hashlib

import pytest

from core.easycrypt.proof_state_compiler.backend.presentation import (
    PresentationContractError,
    render_action_surface_payload,
)


def _payload() -> dict:
    return {
        "schema_version": 1,
        "resources": [],
        "bindings": [],
        "actions": [{
            "intent": "commit_tactic",
            "payload": {"tactic": "trivial."},
            "presentation_kind": "failure_linked_repair",
            "checked_local_effect": {"closed": True},
        }],
        "diagnostics": [],
    }


def test_renderer_returns_exact_markdown_measurements_outside_payload() -> None:
    payload = _payload()

    rendered = render_action_surface_payload(payload)

    assert rendered.text == (
        "## Checked repair for the attempted operation\n\n"
        "EasyCrypt checked this exact local action:\n"
        "```json\n"
        '{"intent":"commit_tactic","payload":{"tactic":"trivial."}}\n'
        "```\n\n"
        "Checked local effect: this action closes the goal."
    )
    assert rendered.utf8_bytes == len(rendered.text.encode("utf-8"))
    assert rendered.characters == len(rendered.text)
    assert rendered.sha256 == hashlib.sha256(
        rendered.text.encode("utf-8")
    ).hexdigest()
    assert "utf8_bytes" not in payload
    assert "sha256" not in payload


def test_renderer_rejects_unknown_fields_instead_of_exposing_them() -> None:
    payload = _payload()
    payload["actions"][0]["internal_evidence"] = "must not reach the agent"

    with pytest.raises(PresentationContractError):
        render_action_surface_payload(payload)


@pytest.mark.parametrize(
    ("intent", "action_payload"),
    (
        (
            "commit_tactic",
            {"tactic": "trivial.", "internal_evidence": "must not leak"},
        ),
        ("commit_tactic", {"tactic": "   "}),
        ("finish", {}),
    ),
)
def test_renderer_rejects_manager_invalid_compiler_actions(
    intent: str,
    action_payload: dict,
) -> None:
    payload = _payload()
    payload["actions"][0]["intent"] = intent
    payload["actions"][0]["payload"] = action_payload

    with pytest.raises(PresentationContractError):
        render_action_surface_payload(payload)


def test_binding_template_rejects_uncontracted_native_details() -> None:
    payload = _payload()
    payload["actions"] = []
    payload["bindings"] = [{
        "resource_id": "native:binding:1",
        "unresolved": [],
        "resolved": {"future_internal_field": "must not leak"},
    }]

    with pytest.raises(PresentationContractError):
        render_action_surface_payload(payload)


def test_diagnostic_terminal_renders_after_notes_shape_and_help() -> None:
    payload = _payload()
    payload["actions"] = []
    payload["diagnostics"] = [{
        "primary": "Structural diagnosis.",
        "notes": ["Checked detail."],
        "placeholder_shape": "apply T (<value>).",
        "help": "Mechanical explanation.",
        "terminal": "The compiler selected neither continuation.",
    }]

    rendered = render_action_surface_payload(payload)

    assert rendered.text == (
        "## Compiler diagnostic\n\n"
        "Structural diagnosis.\n\n"
        "- Checked detail.\n\n"
        "Typed application shape:\n"
        "```easycrypt\n"
        "apply T (<value>).\n"
        "```\n\n"
        "Help: Mechanical explanation.\n\n"
        "The compiler selected neither continuation."
    )
    assert rendered.text.endswith(
        "The compiler selected neither continuation."
    )
