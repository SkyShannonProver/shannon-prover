"""Long-lived agent prompt helpers.

Normal per-turn presentation no longer lives here.  The canonical turn route is
``ProverWorkspaceView`` -> ``SurfaceModel`` -> ``SurfaceTurnModel`` -> markdown
or web card (see ``workflow.surface_turn_model``). This module only keeps the
long-lived MCP/runtime prompt, manager-outcome summaries, and the committed-proof
snippet writer used by ``NodeMemory``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from workflow.proof_management.common import _drop_empty
from workflow.context_intents import (
    CONTEXT_TOPIC_INTENTS,
    INTENT_CLASS_CONTEXT_TOPIC,
    intents_by_class,
    is_context_topic_intent,
)
from workflow.surface_profiles import allowed_intents_for_surface_profile, resolve_surface_profile
from workflow.proof_management import ALLOWED_AGENT_INTENTS


_INTERPRET_SURFACE = """## How to read the manager surface

The rendered `SurfaceModel` contains current-state mechanical evidence and
loaded declarations, not a proof strategy. Use the actions shown on that
surface for optional read-only context; semantic choices such as invariants,
cuts, couplings, and the overall proof route remain yours."""


def _manager_interpret_section(current_intents: list[str]) -> str:
    # Proof-disposition coaching (how to READ manager returns). Gated to rungs with
    # inspection; the L1 goal-projection baseline gets none of it — it is a
    # raw baseline, and the manager still enforces every contract regardless.
    if (CONTEXT_TOPIC_INTENTS | {"lookup_symbol"}) & set(current_intents):
        return _INTERPRET_SURFACE
    return ""


_MCP_TOOL_LINES = {
    "commit_tactic": "`commit_tactic` — apply a tactic, changing the proof state. The one state-changing move.",
    "lookup_symbol": "`lookup_symbol` — get the exact declaration / signature of a named lemma or operator before you apply it.",
    "undo_last_step": "`undo_last_step` — undo only the most recent committed tactic.",
    "undo_to_checkpoint": "`undo_to_checkpoint` — open a menu of committed tactics and rewind to before one; copy one `submit` object from the menu (some call-scope rewinds need confirmation).",
    "fresh_restart": "`fresh_restart` — erase the whole committed branch in this node (confirmation required); not a multi-step undo.",
    "finish": "`finish` — declare the proof complete, or — while goals remain — give up (see “Don’t stop on your own” below).",
}


_MCP_TOOL_ORDER = [
    "commit_tactic", "lookup_symbol",
    "undo_last_step", "undo_to_checkpoint", "fresh_restart",
    "finish",
]


def _adaptive_mode_section(surface_profile: str | None) -> str:
    """Explanation injected only for an adaptive profile: the agent starts cheap
    (goal-only) and the richer intents are *escalation levers* — reach for one
    only when genuinely stuck, or it instantly upgrades to the full surface."""
    profile = resolve_surface_profile(surface_profile)
    if profile is None or not profile.escalate_to:
        return ""
    schema_levers = "context topic intents and `lookup_symbol`"
    unlock_levers = "context topics / lookup"
    return (
        "## Adaptive surface — prove it yourself; the manager unlocks tools when you stall\n\n"
        "You begin in the **goal-only fast path**: you see just the current goal, and "
        "your working intents are `commit_tactic` / `undo_last_step` / `finish` / "
        "`fresh_restart`. Figure out the proof **yourself**, from your own EasyCrypt "
        "knowledge, and commit. Most steps should stay here — this is the cheap path.\n\n"
        f"The tool schema also lists {schema_levers}, but **you cannot use them on "
        "demand.** The MANAGER decides "
        "when to unlock the richer checked-action surface — automatically, once it "
        "judges you objectively STUCK (your committed state has not advanced for "
        "several turns). If you reach for one of those intents before then, it is "
        "REJECTED with a note that you are not yet judged stuck.\n\n"
        "⚠️ So do NOT fish for the tools. Commit your best **genuine** attempt each "
        "turn. A wrong attempt is not wasted — repeated no-progress steps are exactly "
        f"what makes the manager unlock {unlock_levers} and the decision "
        "panels for you. When that happens the new panels and intents simply start "
        "working in your next turn.\n"
    )


def _mcp_tools_section(current_intents: list[str]) -> str:
    current = set(current_intents)
    lines = [
        _MCP_TOOL_LINES[i] for i in _MCP_TOOL_ORDER
        if i in current and i in _MCP_TOOL_LINES
    ]
    context_topics = intents_by_class(current, INTENT_CLASS_CONTEXT_TOPIC)
    if context_topics:
        lines.insert(
            1 if "commit_tactic" in current else 0,
            (
                "State-dependent read-only context actions — submit only a "
                "concrete intent/payload displayed on the current surface."
            ),
        )
    return "\n".join(f"- {ln}" for ln in lines)


def render_long_lived_agent_prompt(
    prompt: str,
    *,
    host: str,
    port: int,
    token: str,
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
    _ = (host, port, token)
    current_intents = sorted(
        allowed_intents_for_surface_profile(surface_profile) & ALLOWED_AGENT_INTENTS
    )
    profile = resolve_surface_profile(surface_profile)
    profile_safe_prompt = _profile_safe_original_prompt(prompt, surface_profile)
    intent_example = _intent_example_for_profile(current_intents, profile)
    keep_going_actions = _keep_going_actions_for_profile(current_intents)
    refresh_hint = _refresh_hint_for_profile(current_intents)
    mcp_tools = _mcp_tools_section(current_intents)
    adaptive_section = _adaptive_mode_section(surface_profile)
    coaching = _manager_interpret_section(current_intents)
    coaching = f"{coaching}\n\n" if coaching else ""
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
            "and the profile-visible reference panels.\n\n---\n\n"
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
the structured MCP tool `submit_proof_intent`, one intent object per turn, e.g.:

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
{adaptive_section}
{coaching}## Runtime details

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

If Claude context is compacted, a tool result is truncated, or you are unsure what
the latest manager response was, read `LEGAL_LATEST_FOLLOWUP` first and
`LEGAL_PROOF_SO_FAR` if you need committed-history context; if they are not in
your context, {refresh_hint} instead of using shell directory discovery. If
`submit_proof_intent` is unavailable, do not inspect private transport or
implementation files — report `TOOL_BOUNDARY_MISSING` in your final
`PROVER REPORT:` so the orchestrator can restart or repair the node.

**Don't stop on your own.** Every turn MUST end with a `submit_proof_intent` call;
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


def _intent_example_for_profile(
    current_intents: list[str],
    profile: Any,
) -> str:
    if "commit_tactic" in current_intents:
        return '{"intent": "commit_tactic", "payload": {"tactic": "TAC."}}'
    if "finish" in current_intents:
        return '{"intent": "finish", "payload": {}}'
    return '{"intent": "commit_tactic", "payload": {"tactic": "TAC."}}'


def _keep_going_actions_for_profile(current_intents: list[str]) -> str:
    """Profile-accurate list of "what to try instead of stopping" — only names
    actions this surface actually grants (L1 has no inspect/lookup)."""
    if (CONTEXT_TOPIC_INTENTS | {"lookup_symbol"}) & set(current_intents):
        return (
            "Try another tactic, commit a candidate, request a context topic or look up a lemma, "
            "decompose the goal, or rewind and re-approach"
        )
    return (
        "Try a different tactic, undo a wrong step, or restart the branch and "
        "re-approach"
    )


def _refresh_hint_for_profile(current_intents: list[str]) -> str:
    """How to recover the current goal when context is lost.

    The recovery target is the compact agent-readable followup, not the raw
    audit workspace JSON.
    """
    return (
        "re-read `LEGAL_LATEST_FOLLOWUP` and, if needed, `LEGAL_PROOF_SO_FAR`, "
        "then submit your next proof intent"
    )


def _profile_safe_original_prompt(prompt: str, surface_profile: str | None) -> str:
    profile = resolve_surface_profile(surface_profile)
    if profile is None or profile.stage == "full":
        return prompt
    if profile.stage == "l1_goal_projection":
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
        return head.rstrip() + "\n\n" + _profile_safe_protocol(profile)
    cut_markers = [
        "\n## What you can reason about vs what you need EC for",
        "\n## Prove from the branch point",
        "\n### Mode 1: Choose the next proof intent",
    ]
    cut_points = [prompt.find(marker) for marker in cut_markers]
    cut_points = [point for point in cut_points if point >= 0]
    head = prompt[: min(cut_points)].rstrip() if cut_points else prompt.rstrip()
    return head + "\n\n" + _profile_safe_protocol(profile)


def _profile_safe_protocol(profile: Any) -> str:
    _ = profile
    return f"""## Profile-Safe Proof Protocol

This surface profile is part of the interface ladder. Treat panels, intents,
and topics absent from the current surface as unavailable.

Read the rendered `SurfaceTurnModel` as the authority for the current state.
Choose exactly one next proof intent, submit it via `submit_proof_intent`, then
read the refreshed surface before deciding again. Read-only actions are
state-dependent: use only a concrete intent/payload shown on the current
`SurfaceModel`.

Do not invent lemmas or axioms; use only declarations visible in source,
the current proof surface, or exact symbol lookup.

When the refreshed surface says `candidate_closed_pending_qed`, submit:
`{{"intent":"commit_tactic","payload":{{"tactic":"qed."}}}}`.
Only after `qed.` is accepted and the next view shows the lemma is saved should
you output `PROOF TACTICS:` followed by the accepted tactic sequence, then a
concise `PROVER REPORT:` JSON block with useful observations, missing guidance,
and blockers if any."""


def _md_proof_so_far(panel: Any) -> str:
    """Render the persistent, step-numbered proof for recovery orientation."""
    if not isinstance(panel, dict):
        return ""
    steps = panel.get("steps")
    if not isinstance(steps, list) or not steps:
        return ""
    rows: list[str] = []
    for entry in steps:
        if not isinstance(entry, dict):
            continue
        step = entry.get("step")
        tactic = str(entry.get("tactic") or "")
        rows.append(f"{step}. {tactic}" if step is not None else f"   {tactic}")
    count = panel.get("committed_count")
    return (
        f"### Proof so far ({count} committed — step-numbered, your own work)\n"
        "```\n" + "\n".join(rows) + "\n```"
    )


def _agent_safe_action_summaries(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("label") == "agent_view":
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


def _turn_interpretation(
    handled_intent: dict[str, Any] | None,
    actions: list[dict[str, Any]],
) -> str:
    intent = str((handled_intent or {}).get("intent") or "")
    if intent == "lookup_symbol" or is_context_topic_intent(intent):
        return (
            "Read-only context. Accepted/rejected tactic or call text inside "
            "a preview is route-selection information, not the current "
            "proof-state error."
        )
    if intent == "commit_tactic":
        if any(_action_changed_proof_state(action) for action in actions):
            return "Committed tactic accepted; the EasyCrypt proof state changed."
        return (
            "Commit attempt did not change the committed EasyCrypt proof "
            "state; use the returned result and latest view before trying "
            "the next proof intent."
        )
    if intent == "commit_replay_suffix_chunk":
        return (
            "Replay chunk commit was handled by the manager; the latest view "
            "is authoritative for the replayed route suffix."
        )
    if intent == "undo_last_step":
        return "Undo request was handled by the manager; the latest view is authoritative."
    if intent == "undo_to_checkpoint":
        payload = (handled_intent or {}).get("payload")
        # Panel-defect #2: never claim a "rewind was handled" when the request
        # actually degraded to a menu re-prompt (stale/unreachable target) and
        # NOTHING changed. Distinguish a real rewind (proof state changed) from a
        # menu by inspecting the actions, so the agent gets an honest signal
        # instead of a frozen-identical observation that reads as a no-op.
        state_changed = any(_action_changed_proof_state(action) for action in actions)
        menu_shown = any(
            isinstance(action, dict)
            and str(action.get("label") or "") in {
                "checkpoint_selection", "checkpoint_rewind_confirmation",
            }
            for action in actions
        )
        if isinstance(payload, dict) and payload.get("restore_id"):
            return "Checkpoint restore was handled by the manager; the latest view is authoritative."
        if isinstance(payload, dict) and (payload.get("confirm") or payload.get("checkpoint_id")):
            if state_changed:
                return "Checkpoint rewind executed; the EasyCrypt proof state changed (see the latest view)."
            if menu_shown:
                return (
                    "The requested rewind did NOT execute — the manager returned "
                    "a checkpoint menu (the target was stale or not reachable from "
                    "this scope; read the menu's notice). No proof state changed."
                )
            return "Checkpoint rewind request was handled by the manager; the latest view is authoritative."
        return "Checkpoint choices were shown; choose one submit object or continue proving."
    if intent == "fresh_restart":
        payload = (handled_intent or {}).get("payload")
        if isinstance(payload, dict) and payload.get("confirm"):
            return "Fresh restart was confirmed; the latest view is the new branch start."
        return "Fresh restart confirmation was shown; choose an option before erasing this branch."
    if intent == "finish":
        if any(
            str(action.get("label") or "") == "finish_requires_qed"
            for action in actions
            if isinstance(action, dict)
        ):
            return "Finish was rejected because the closed candidate still needs `qed.`."
        if any(
            str(action.get("label") or "") == "give_up_gate"
            for action in actions
            if isinstance(action, dict)
        ):
            return ("Finish was deflected: the proof is still open. Make another "
                    "genuine attempt before giving up (see the manager's message).")
        return "Finish request was handled by the manager."
    return "Manager handled the previous message and refreshed the latest view."


def _friendly_manager_action(label: object) -> str:
    normalized = str(label or "").strip()
    return {
        "commit_tactic": "tactic commit",
        "commit_replay_suffix_chunk": "replay chunk commit",
        "inspect_call_subgoals": "call-obligation preview",
        "lookup_symbol": "symbol lookup",
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


def _action_changed_proof_state(action: dict[str, Any]) -> bool:
    if not bool(action.get("mutates_proof_state")):
        return False
    if action.get("exit_code") != 0:
        return False
    observation = action.get("agent_observation")
    if isinstance(observation, dict):
        proof_state = str(observation.get("proof_state") or "").lower()
        if "not changed" in proof_state or "unchanged" in proof_state:
            return False
        result = str(observation.get("result") or "").lower()
        if "rejected" in result or "did not execute" in result:
            return False
    return True
