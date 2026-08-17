"""Markdown backend for the current goal-only turn contract."""
from __future__ import annotations

import json
from typing import Any

from core.easycrypt.proof_lifecycle import (
    GOALS_DISCHARGED_PENDING_QED,
    SESSION_CLOSED_PENDING_VERIFICATION,
    VERIFIED,
)
from workflow.proof_state_compiler.current_turn_contract import as_dict


def render_current_surface_turn_markdown(
    surface_turn: dict[str, Any],
    *,
    submit_line: str = "",
    anchor_block: str = "",
) -> str:
    if not isinstance(surface_turn, dict):
        return ""
    proof = as_dict(surface_turn.get("proof_surface"))
    control = as_dict(surface_turn.get("control_menu"))
    outcome = as_dict(surface_turn.get("turn_outcome"))
    compiler_value = surface_turn.get("compiler_markdown")
    compiler_md = compiler_value if isinstance(compiler_value, str) else ""
    if outcome.get("finish_accepted"):
        # A manager-accepted finish is the terminal response for this proof
        # node. Never append the ordinary next-turn instruction after it.
        submit_line = ""
        anchor_block = ""

    if control:
        return _join_turn_sections(
            before=(_render_control_menu(control), _render_proof(proof, outcome)),
            compiler_markdown=compiler_md,
            after=(submit_line + anchor_block,),
        )

    body = _render_proof(proof, outcome)
    outcome_md = _render_turn_outcome(outcome)
    if outcome_md and outcome.get("lead_before_goal"):
        body = _join_sections(outcome_md, body)
    elif outcome_md:
        body = _join_sections(body, outcome_md)
    return _join_turn_sections(
        before=(body,),
        compiler_markdown=compiler_md,
        after=(submit_line + anchor_block,),
    )


def _render_proof(surface: dict[str, Any], outcome: dict[str, Any]) -> str:
    return _join_sections(
        _render_terminal_status(surface, outcome),
        _render_goal(surface),
    )


def _render_terminal_status(
    surface: dict[str, Any],
    outcome: dict[str, Any],
) -> str:
    status = str(as_dict(surface.get("status")).get("status") or "").strip()
    finish_accepted = bool(outcome.get("finish_accepted"))
    if not finish_accepted and status not in {
        GOALS_DISCHARGED_PENDING_QED,
        SESSION_CLOSED_PENDING_VERIFICATION,
        VERIFIED,
    }:
        return ""

    lines = ["## Proof Status"]
    if status:
        lines.append(f"**Status:** `{status}`")
    if finish_accepted:
        lines.append(
            "**Finish accepted. Stop submitting proof intents and return your "
            "concise `PROVER REPORT:`.**"
        )
    elif status == GOALS_DISCHARGED_PENDING_QED:
        lines.append(
            "**Next valid action:** commit `qed.` with `commit_tactic`."
        )
    elif status == SESSION_CLOSED_PENDING_VERIFICATION:
        lines.append(
            "**Next valid action:** submit `finish`; offline verification "
            "happens after this proof node stops."
        )
    elif status == VERIFIED:
        lines.append("**Offline verification is complete. Stop submitting intents.**")
    return "\n\n".join(lines)


def _render_goal(surface: dict[str, Any]) -> str:
    goal = as_dict(surface.get("goal"))
    text = str(goal.get("text") or "").rstrip()
    if not text:
        lines = goal.get("lines")
        text = (
            "\n".join(str(line) for line in lines)
            if isinstance(lines, list)
            else ""
        )
    if not text:
        text = "(no goal)"
    return f"## 🎯 Current Goal\n```\n{text}\n```"


def _render_control_menu(menu: dict[str, Any]) -> str:
    lines = [f"## {menu.get('title') or 'Manager menu'}"]
    notice = str(menu.get("notice") or "").strip()
    if notice:
        lines.append(notice)
    items = menu.get("items") if isinstance(menu.get("items"), list) else []
    if items:
        lines.append(
            "Choose one option. Fill any required input fields before submitting:"
        )
        for item in items:
            if not isinstance(item, dict):
                continue
            item_lines = [f"- **{item.get('label') or 'option'}**"]
            if item.get("description"):
                item_lines.append(f"  - {item['description']}")
            if item.get("tactic"):
                item_lines.append(f"  - tactic: `{item['tactic']}`")
            required = item.get("requires_input") or []
            if required:
                item_lines.append(
                    "  - required input: "
                    + ", ".join(f"`{field}`" for field in required)
                )
            submit = item.get("submit")
            if isinstance(submit, dict) and submit:
                verb = "start from" if required else "submit"
                encoded = json.dumps(
                    submit,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                item_lines.append(f"  - {verb}: `{encoded}`")
            lines.append("\n".join(item_lines))
    elif not notice:
        lines.append("No manager menu is available for this state.")
    return "\n\n".join(lines)


def _render_turn_outcome(outcome: dict[str, Any]) -> str:
    text = str(outcome.get("result_line") or "").strip()
    if not text:
        return ""
    if text.startswith("## "):
        return text
    if text.startswith("Last action: "):
        return "**Last action:** " + text[len("Last action: "):]
    if "\n" in text:
        return "```\n" + text.rstrip() + "\n```"
    return "**" + text + "**"


def _join_sections(*blocks: str) -> str:
    return "\n\n---\n\n".join(
        str(block).strip()
        for block in blocks
        if str(block or "").strip()
    )


def _join_turn_sections(
    *,
    before: tuple[str, ...],
    compiler_markdown: str,
    after: tuple[str, ...],
) -> str:
    """Compose the turn while preserving the compiler block byte-for-byte."""

    sections = [
        str(block).strip()
        for block in before
        if str(block or "").strip()
    ]
    if compiler_markdown:
        sections.append(compiler_markdown)
    sections.extend(
        str(block).strip()
        for block in after
        if str(block or "").strip()
    )
    return "\n\n---\n\n".join(sections)
