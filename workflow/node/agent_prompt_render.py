"""Long-lived agent prompt helpers.

Normal per-turn presentation no longer lives here. Every supported profile
uses the current goal-envelope presenter. This module only keeps the long-lived
MCP/runtime prompt, manager-outcome summaries, and the committed-proof snippet
writer used by ``NodeMemory``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from workflow.proof_management.common import _drop_empty
from core.context_intents import (
    persistent_control_specs,
)
from workflow.proof_state_compiler.runtime_profiles import (
    resolve_runtime_surface_profile,
)
from workflow.proof_tool.proof_tool_contract import (
    ProofToolContractManifest,
    validate_proof_tool_contract,
)


def _mcp_tools_section(current_intents: list[str]) -> str:
    current = set(current_intents)
    controls: list[str] = []
    for spec in persistent_control_specs():
        if spec.name not in current:
            continue
        required = ""
        if spec.control_requires_input:
            fields = ", ".join(f"`{field}`" for field in spec.control_requires_input)
            required = f" Required payload fields: {fields}."
        controls.append(
            f"- {spec.display_label or spec.name} (`{spec.name}`) — "
            f"{spec.description}.{required}"
        )
    sections: list[str] = []
    if controls:
        sections.append("### Proof controls\n\n" + "\n".join(controls))
    return "\n\n".join(sections)


def render_long_lived_agent_prompt(
    prompt: str,
    *,
    proof_tool_manifest: ProofToolContractManifest,
    node_memory_dir: Path,
    max_turns: int,
    surface_profile: str | None = None,
    compact: bool = False,
    compact_pointer: str = "",
) -> str:
    """Render the long-lived prover runtime/tool-protocol prompt.

    The trailing ``{profile_safe_prompt}`` block is the lean turn-0 bootstrap
    (target pointer plus the typed handoff surface). When ``compact`` is set
    (the fresh-context continuation reopening — see FIX #2 /
    docs/design/fresh_context_continuation.md §Handoff) that heavy block is
    dropped and replaced by a thin ``compact_pointer`` so the fresh session opens
    near the post-compact floor, not the degraded ceiling. The runtime/tool
    protocol block above is ALWAYS kept — the fresh session still needs it.
    """
    manifest = validate_proof_tool_contract(proof_tool_manifest)
    current_intents = list(manifest.effective_profile_intents)
    tool_name = manifest.identity.tool
    profile_safe_prompt = _profile_safe_original_prompt(
        prompt,
        surface_profile,
        tool_name=tool_name,
    )
    intent_example = _intent_example(current_intents)
    keep_going_actions = _KEEP_GOING_ACTIONS
    refresh_hint = _REFRESH_HINT
    mcp_tools = _mcp_tools_section(current_intents)
    if compact:
        # Fresh-context reopening: drop the turn-0 bootstrap. The EC session
        # already holds the proof state and the handoff (prepended by the caller)
        # supplies the frontier brief + accepted spine + dead-end ledger. A thin
        # pointer to the target lets the agent re-read source on demand via tools.
        tail = (
            "Your specific lemma context is NOT re-embedded here (your prior "
            "context already established it and the EasyCrypt session is intact). "
            "Read `LEGAL_LATEST_FOLLOWUP` first to recover the current proof "
            "surface, and `LEGAL_PROOF_SO_FAR` if you need the accepted tactic "
            "spine. Re-read the target file or sibling lemmas on demand only if a "
            "step needs them."
        )
        if compact_pointer.strip():
            tail += f"\n\n{compact_pointer.strip()}"
    else:
        tail = (
            "The original prover prompt follows — your specific lemma, the file, "
            "and the current compiler profile.\n\n---\n\n"
            f"{profile_safe_prompt}"
        )
    return f"""# Long-Lived Prover Agent Runtime

You are a long-lived prover agent for one proof node. You stay alive across
manager turns and keep your own working memory. Do not stop after one proof
intent unless the proof is complete or the manager reports a terminal node
health event.

Each manager response gives the current authoritative proof surface rendered
from `SurfaceTurnModel`.
Use MCP tools to interact with the manager; all proof interaction goes through
the structured MCP tool `{tool_name}`, one intent object per turn, e.g.:

```json
{intent_example}
```

Always include a `payload` object (an empty object for menu/request intents like
`finish` and `fresh_restart`). The arguments are structured data, so long tactic
strings need no shell escaping or scratch files. Your full step-numbered committed
proof is always written to `LEGAL_PROOF_SO_FAR` (see Runtime details); read it
only when you need to re-orient before choosing a rewind target.

## Your MCP tools

{mcp_tools}
## Runtime details

**Recovering the current state.** After each manager turn the runtime writes the
agent-readable turn surface to `LEGAL_LATEST_FOLLOWUP`; read it if context was
compacted, a tool result was truncated, or you need the latest manager response
again. The raw full workspace JSON is an audit/replay artifact, not the normal
proof surface; do not open it for ordinary proof work.

**Your committed proof.** Your full step-numbered committed proof is ALWAYS
written to `LEGAL_PROOF_SO_FAR` and refreshed every turn. It is NOT repeated in
each prompt; read it only to re-orient on accepted work before a rewind or after
a context refresh.

LEGAL_NODE_MEMORY_DIR: `{node_memory_dir}`
LEGAL_LATEST_MANAGER_RESULT: `{node_memory_dir / "latest_manager_result.json"}`
LEGAL_LATEST_FOLLOWUP: `{node_memory_dir / "latest_followup.md"}`
LEGAL_PROOF_SO_FAR: `{node_memory_dir / "proof_so_far.md"}`

If Claude context is compacted (or Codex agent context is compacted), a tool
result is truncated, or you are unsure what
the latest manager response was, read `LEGAL_LATEST_FOLLOWUP` first and
`LEGAL_PROOF_SO_FAR` if you need committed-history context; if they are not in
your context, {refresh_hint} instead of using shell directory discovery. If
`{tool_name}` is unavailable, do not inspect private transport or
implementation files — report `TOOL_BOUNDARY_MISSING` in your final
`PROVER REPORT:` so the orchestrator can restart or repair the node.

**Don't stop on your own.** Every turn MUST end with a `{tool_name}` call;
a turn that ends with only text and no call terminates your session and ABANDONS
the proof. Keep going by default — a failed tactic, a hard step, an unexpected
goal, or your own uncertainty are NOT reasons to stop. {keep_going_actions} — you
have a large budget ({max_turns} manager turns), so use it; hard proofs normally
take many attempts and several dead ends.

**Giving up.** If you genuinely want to stop, do not just end with a report — tell
the manager with `{{"intent": "finish", "payload": {{}}}}`. While goals remain the
manager treats `finish` as a give-up and will push back; honor that and continue.
Insist on `finish` only after you have exhausted DISTINCT strategies — several
structurally different approaches that fail for the same fundamental reason you can
state. "This step is hard" or "I'm not sure" is never that reason. Write your
`PROVER REPORT:` only once `finish` is accepted (proof complete or give-up honored).

{tail}
"""


def _intent_example(current_intents: list[str]) -> str:
    if "commit_tactic" not in current_intents and "finish" in current_intents:
        return '{"intent": "finish", "payload": {}}'
    return '{"intent": "commit_tactic", "payload": {"tactic": "TAC."}}'


# "What to try instead of stopping" — only names actions every surface grants
# (L1 has no inspect/lookup).
_KEEP_GOING_ACTIONS = (
    "Try a different tactic, undo a wrong step, or restart the branch and "
    "re-approach"
)

# How to recover the current goal when context is lost: the compact
# agent-readable followup, not the raw audit workspace JSON.
_REFRESH_HINT = (
    "re-read `LEGAL_LATEST_FOLLOWUP` and, if needed, `LEGAL_PROOF_SO_FAR`, "
    "then submit your next proof intent"
)


def _profile_safe_original_prompt(
    prompt: str,
    surface_profile: str | None,
    *,
    tool_name: str,
) -> str:
    profile = resolve_runtime_surface_profile(surface_profile)
    if profile is None or profile.stage == "full":
        return prompt
    if profile.base_surface == "goal_only":
        # L1 is the barest baseline by framework design: the lemma statement and
        # nothing else. The file-content context, the manager-usage section, and
        # the view-interpretation guidance all belong to the higher rungs' static
        # surface, so they are dropped here. The runtime wrapper and the appended
        # profile-safe protocol carry the interaction mechanics the agent needs.
        m = re.search(
            r"You are (?:proving|continuing a proof of) EasyCrypt lemma[^\n]*",
            prompt,
        )
        lemma_line = m.group(0) if m else ""
        guard = prompt[: m.start()].rstrip() if m else ""  # eval guard, if present
        head = ((guard + "\n\n") if guard else "") + lemma_line
        # Preserve the marked handoff so the worker can replace its provisional
        # goal-only rendering with the authoritative manager-bound turn-0
        # surface after adoption. L1 still receives only its goal projection;
        # retaining the marker does not admit any L4 fields.
        from workflow.agents.prover_prompt import managed_handoff_block

        handoff = managed_handoff_block(prompt)
        blocks = [head.rstrip()]
        if handoff:
            blocks.append(handoff)
        blocks.append(_profile_safe_protocol(tool_name=tool_name))
        return "\n\n".join(block for block in blocks if block)
    cut_markers = [
        "\n## What you can reason about vs what you need EC for",
        "\n## Prove from the branch point",
        "\n### Mode 1: Choose the next proof intent",
    ]
    cut_points = [prompt.find(marker) for marker in cut_markers]
    cut_points = [point for point in cut_points if point >= 0]
    head = prompt[: min(cut_points)].rstrip() if cut_points else prompt.rstrip()
    return head + "\n\n" + _profile_safe_protocol(tool_name=tool_name)


def _profile_safe_protocol(*, tool_name: str) -> str:
    return f"""## Profile-Safe Proof Protocol

This compiler profile is part of the experiment contract. Treat intents absent
from the current surface as unavailable.

Read the rendered `SurfaceTurnModel` as the authority for the current state.
Choose exactly one next proof intent, submit it via `{tool_name}`, then
read the refreshed surface before deciding again.

Do not invent lemmas or axioms; use only declarations visible in source or the
current proof surface.

When the refreshed surface says `goals_discharged_pending_qed`, submit:
`{{"intent":"commit_tactic","payload":{{"tactic":"qed."}}}}`.
Only after `qed.` is accepted and the next view shows the lemma is saved should
you output a concise `PROVER REPORT:` JSON block with useful observations,
missing guidance, and blockers if any. The runtime appends `PROOF TACTICS:`
from verified session history; do not read `proof_so_far.md` only to reproduce
that final tactic list."""


def render_committed_proof_markdown(tactics: tuple[str, ...] | list[str]) -> str:
    """Render one manager-bound committed tactic spine for node memory."""

    rows = [str(tactic).strip() for tactic in tactics if str(tactic).strip()]
    if not rows:
        return ""
    numbered = [f"{index}. {tactic}" for index, tactic in enumerate(rows, 1)]
    return (
        f"### Proof so far ({len(rows)} committed — step-numbered, your own work)\n"
        "```\n" + "\n".join(numbered) + "\n```"
    )


def _agent_safe_action_summaries(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("label") == "managed_goal_view":
            continue
        observation = action.get("agent_observation")
        observation = observation if isinstance(observation, dict) else {}
        summaries.append(_drop_empty({
            "action": _friendly_manager_action(action.get("label")),
            "outcome": _manager_action_outcome(action),
            "timing": _manager_action_timing(action),
            "content": _manager_action_content(observation),
            "error_summary": observation.get("error_summary"),
        }))
    return summaries


def _friendly_manager_action(label: object) -> str:
    normalized = str(label or "").strip()
    return {
        "commit_tactic": "tactic commit",
        "admit_clarification": "admit clarification",
        "qed_clarification": "qed clarification",
        "undo_last_step": "undo",
        "undo_to_checkpoint": "checkpoint rewind",
        "checkpoint_selection": "checkpoint menu",
        "fresh_restart": "fresh restart",
        "fresh_restart_confirmation": "fresh restart menu",
        "finish_requires_qed": "finish requires qed",
        "finish": "finish",
        "replay_prefix": "prefix replay",
    }.get(normalized, normalized.replace("_", " ") or "manager action")


def _manager_action_outcome(action: dict[str, Any]) -> str:
    if action.get("timed_out"):
        timeout = action.get("timeout_seconds")
        if timeout:
            return f"The manager action timed out after {timeout} seconds."
        return "The manager action timed out."
    observation = action.get("agent_observation")
    if isinstance(observation, dict):
        content = observation.get("content")
        if isinstance(content, dict):
            content_result = str(content.get("result") or "").strip()
            if content_result:
                return content_result
        result = str(observation.get("result") or "").strip()
        if result:
            return result
        message = str(observation.get("message") or "").strip()
        if message:
            return message
    if action.get("exit_code") == 0:
        return "The manager action completed."
    return "The manager action did not complete successfully."


def _manager_action_content(observation: dict[str, Any]) -> dict[str, Any]:
    content = observation.get("content")
    if not isinstance(content, dict):
        return {}
    return _drop_empty({
        key: value
        for key, value in content.items()
        if key not in {"result", "proof_state", "how_to_read", "effect"}
    })


def _manager_action_timing(action: dict[str, Any]) -> str:
    duration = action.get("duration_ms")
    if not isinstance(duration, int) or duration <= 0:
        return ""
    if duration < 1000:
        return f"{duration} ms"
    return f"{duration / 1000:.1f} s"
