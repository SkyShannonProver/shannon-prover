"""Long-lived agent prompt helpers and raw-view preview utilities.

Normal per-turn presentation no longer lives here.  The canonical turn route is
``ProverWorkspaceView`` -> ``SurfaceModel`` -> ``SurfaceTurnModel`` -> markdown
or web card (see ``workflow.surface_turn_model``).  This module only keeps the
long-lived MCP/runtime prompt, the size guard for legal raw workspace JSON, and
the committed-proof snippet writer used by ``NodeMemory``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from workflow.view_neutrality import view_neutrality_strict
from workflow.proof_management.common import _drop_empty
from workflow.context_intents import (
    CONTEXT_TOPIC_INTENTS,
    INTENT_CLASS_CONTEXT_TOPIC,
    intents_by_class,
    is_context_topic_intent,
)
from workflow.surface_profiles import (
    allowed_intents_for_surface_profile,
    effective_allowed_intents,
    effective_inspect_topics,
    probe_disabled,
    resolve_surface_profile,
)
from workflow.proof_management import ALLOWED_AGENT_INTENTS


_INTERPRET_FACT_FORK = """## How to read what the manager returns

Every result the manager hands back is a STATIC-ANALYSIS FACT about the state your
tactics have walked into — the RESULT of where you have walked, never a verdict on
whether the proof is winnable and never an instruction for the next move. The
manager reports where you ARE; the move stays yours.

Read a reported MISMATCH (a lemma is about procedure `P` but the frontier calls
`Q`; two sides' heads differ; an argument or hypothesis you need is absent) as a
FORK, not a wall. It can mean any of:
- you have NOT reached the point where it matches yet — reshape the frontier and
  it appears;
- you took a WRONG TURN earlier — a rewind recovers the match;
- you DROPPED OR MISSED a parameter / hypothesis earlier — supply it and retry;
- you OVERSHOT — you collapsed a level you still needed (e.g. inlined `P` away).
The view states the fact; YOU decide which reading holds from your own proof
history — it never tells you which. "Does not apply HERE" is never "the goal is
unprovable." The manager never supplies the semantic content (the coupling, the
invariant, the route) — that is always yours."""


_INTERPRET_SIGNALS_PROBE = """Weigh each kind of signal for what it is:
- VERIFIED FACTS (`pr_bridge_routes`, an accepted `probe_tactic`, a daemon-confirmed
  `call` skeleton): "this type-checks / is accepted ON THE CURRENT GOAL" — NOT
  "this closes the proof / reaches `qed` / is the best route / is the correct
  invariant." A revisable starting point.
- DIAGNOSES (`diagnose`, `route_health`): ranked, FALLIBLE hypotheses about
  WHERE a failure lives. A diagnosis is a place to look, not a proven cause.
- OPTIONS (`candidate_moves`, `navigation`, `structural_transitions`): a menu of
  moves valid for THIS view only. Read `use_when` / `limitations` / `anti_routes`,
  then pick by your own plan — or ignore them."""


_INTERPRET_SIGNALS_NO_PROBE = """Weigh each kind of signal for what it is:
- VERIFIED FACTS (`pr_bridge_routes`, a daemon-confirmed `call` skeleton): "this
  type-checks / is accepted ON THE CURRENT GOAL" — NOT "this closes the proof /
  reaches `qed` / is the best route / is the correct invariant." A revisable
  starting point.
- DIAGNOSES (`diagnose`, `route_health`): ranked, FALLIBLE hypotheses about
  WHERE a failure lives. A diagnosis is a place to look, not a proven cause.
- OPTIONS (`candidate_moves`, `navigation`, `structural_transitions`): a menu of
  moves valid for THIS view only. Read `use_when` / `limitations` / `anti_routes`,
  then pick by your own plan — or ignore them."""


def _manager_interpret_section(current_intents: list[str]) -> str:
    # Proof-disposition coaching (how to READ manager returns). Gated to rungs with
    # inspection/probing; the L1 goal-projection baseline gets none of it — it is a
    # raw baseline, and the manager still enforces every contract regardless.
    if (CONTEXT_TOPIC_INTENTS | {"probe_tactic", "lookup_symbol"}) & set(current_intents):
        # Switch-aware: drop the `probe_tactic` example when probe is OFF.
        signals = (
            _INTERPRET_SIGNALS_NO_PROBE if probe_disabled() else _INTERPRET_SIGNALS_PROBE
        )
        return _INTERPRET_FACT_FORK + "\n\n" + signals
    return ""


_ADMIT_GATE = """A final proof must contain no committed `admit.` tactics. The
manager scans the committed proof and blocks `qed.` / `finish` while any
committed `admit.` remains. If you previously used `admit.`, undo it and prove
that subgoal before completing the lemma. Helper lemmas shown in source/context
snippets may themselves contain `admit.`; those are declarations you may still
cite as already-established facts."""


_MCP_TOOL_LINES = {
    "commit_tactic": "`commit_tactic` — apply a tactic, changing the proof state. The one state-changing move.",
    "probe_tactic": "`probe_tactic` — run a tactic speculatively: the manager reports accept/reject and the resulting goal WITHOUT changing state. Reach for it whenever you would otherwise commit just to see what happens.",
    "lookup_symbol": "`lookup_symbol` — get the exact declaration / signature of a named lemma or operator before you apply it.",
    "undo_last_step": "`undo_last_step` — undo only the most recent committed tactic.",
    "undo_to_checkpoint": "`undo_to_checkpoint` — open a menu of committed tactics and rewind to before one; copy one `submit` object from the menu (some call-scope rewinds need confirmation).",
    "fresh_restart": "`fresh_restart` — erase the whole committed branch in this node (confirmation required); not a multi-step undo.",
    "finish": "`finish` — declare the proof complete, or — while goals remain — give up (see “Don’t stop on your own” below).",
}


_MCP_TOOL_ORDER = [
    "commit_tactic", "probe_tactic", "lookup_symbol",
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
    # Switch-aware: when probe is OFF it is never unlocked, so the escalation-lever
    # descriptions must not name `probe_tactic` / `probe`.
    off = probe_disabled()
    schema_levers = (
        "context topic intents and `lookup_symbol`" if off
        else "`probe_tactic`, context topic intents, and `lookup_symbol`"
    )
    unlock_levers = (
        "context topics / lookup"
        if off else "probe / context topics / lookup"
    )
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
        shown = ", ".join(f"`{topic}`" for topic in context_topics[:12])
        more = "" if len(context_topics) <= 12 else f", ... (+{len(context_topics) - 12})"
        lines.insert(
            1 if "commit_tactic" in current else 0,
            (
                f"{shown}{more} — read-only context topic intents. Submit the "
                "topic name directly, with only that topic's extra payload fields."
            ),
        )
    return "\n".join(f"- {ln}" for ln in lines)


def _play_well_section(current_intents: list[str]) -> str:
    # Proof-disposition coaching (how to PLAY) + the final-admit gate.
    # Gated to inspection/probing rungs; the L1 goal-projection baseline gets none.
    if not ((CONTEXT_TOPIC_INTENTS | {"probe_tactic", "lookup_symbol"}) & set(current_intents)):
        return ""
    if "probe_tactic" in current_intents:
        brave = (
            "So be brave: PROBE, COMMIT, and UNDO freely. Every time you act, "
            "EasyCrypt's core shows you the ground truth of the resulting state — "
            "and that truth is exactly what lets you analyze the fork above. You "
            "can SEE the goal, so do not sit and simulate it in your head: when you "
            "catch yourself reasoning \"would this apply / does this write that "
            "field / what would this produce,\" STOP and probe it — one reversible "
            "round answers it. Probing and committing are cheap and undoable "
            "(`undo_last_step`, `undo_to_checkpoint`); head-simulation is slow and "
            "usually wrong. Getting stuck thinking hard at one spot is the failure "
            "mode; an accepted probe, a committed step you can rewind, or a fresh "
            "read of the goal beats another minute of speculation."
        )
    else:
        brave = (
            "So be brave: COMMIT and UNDO freely. Every time you act, EasyCrypt's "
            "core shows you the ground truth of the resulting state — and that "
            "truth is exactly what lets you analyze the fork above. You can SEE the "
            "goal, so do not sit and simulate it in your head; commit a concrete "
            "step and read the result. A wrong step is cheap — `undo_last_step` "
            "reverts it; head-simulation is slow and usually wrong. Getting stuck "
            "thinking hard at one spot is the failure mode; a committed step you "
            "can undo, or a fresh read of the goal, beats another minute of "
            "speculation."
        )
    return "## How to play well\n\n" + brave + "\n\n" + _ADMIT_GATE


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

    The trailing ``{profile_safe_prompt}`` block is the full turn-0 bootstrap
    (lemma source + sibling lemmas; ~14-20k tokens). When ``compact`` is set
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
    allowed_intents = ", ".join(f"`{name}`" for name in current_intents)
    profile = resolve_surface_profile(surface_profile)
    profile_safe_prompt = _profile_safe_original_prompt(prompt, surface_profile)
    intent_example = _intent_example_for_profile(current_intents, profile)
    keep_going_actions = _keep_going_actions_for_profile(current_intents)
    refresh_hint = _refresh_hint_for_profile(current_intents)
    mcp_tools = _mcp_tools_section(current_intents)
    adaptive_section = _adaptive_mode_section(surface_profile)
    # Proof-disposition coaching (interpret + play). Empty on the L1 baseline.
    coaching = "\n\n".join(
        s for s in (
            _manager_interpret_section(current_intents),
            _play_well_section(current_intents),
        ) if s
    )
    coaching = f"{coaching}\n\n" if coaching else ""
    if compact:
        # Fresh-context reopening: drop the heavy turn-0 bootstrap. The EC session
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

Each manager response gives the current authoritative `ProverWorkspaceView`.
Use MCP tools to interact with the manager; all proof interaction goes through
the structured MCP tool `submit_proof_intent`, one intent object per turn, e.g.:

```json
{intent_example}
```

Always include a `payload` object (an empty object for menu/request intents like
`finish` and `fresh_restart`). The arguments are structured data, so long tactic
strings need no shell escaping or scratch files. Your full step-numbered committed
proof is always written to `LEGAL_PROOF_SO_FAR` (see Runtime details); read it to
reference a step for `amend_and_replay` / `undo_to_checkpoint`, or to re-orient —
instead of re-deriving work you already committed.

## Your MCP tools

The current `intent` must be one of: {allowed_intents}. This run grants:

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
each prompt — read that file whenever you need it: to reference a step number for
`amend_and_replay` / `undo_to_checkpoint`, or to re-orient on what you have already
committed (e.g. after a context refresh or a fresh-context respawn).

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
    actions this surface actually grants (L1 has no probe/inspect/lookup)."""
    if (CONTEXT_TOPIC_INTENTS | {"probe_tactic", "lookup_symbol"}) & set(current_intents):
        # Switch-aware: with probe OFF the manager rejects probes, so name a
        # commit affordance instead of "probe a candidate".
        candidate_action = (
            "commit a candidate" if probe_disabled() else "probe a candidate"
        )
        return (
            f"Try another tactic, {candidate_action}, request a context topic or look up a lemma, "
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


def _route_health_guidance_for_profile(profile: Any) -> str:
    if view_neutrality_strict():
        # route_health is stripped from the view under neutrality, so prompt
        # guidance about how to read it is moot. See docs/design/compiler_view_boundary.md.
        return ""
    has_route_health = (
        profile is None
        or getattr(profile, "stage", "") == "full"
        or getattr(profile, "stage", "") == "l4_checked_action_surface"
    )
    if not has_route_health:
        return ""
    return (
        "When the view contains `candidate_moves.route_health`, read it as "
        "the manager's current route diagnosis. It may point to a possible "
        "boundary gap, a frontier placement problem, or a `conseq`/surgery "
        "sequence. Route-health is advisory for this current view only: use "
        "the recommended inspect/probe/rewind action when it matches the "
        "goal. If it lists `useful_inspections`, read them only as context "
        "before deciding whether an earlier boundary should be revisited. "
        "Do not treat route-health as an invariant recipe, proof script, or "
        "historical truth."
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
    if "probe_tactic" not in (effective_allowed_intents(profile) or frozenset()):
        head = head.replace("If the first probe shows", "If the first attempt shows")
        head = head.replace("probe shows", "attempt shows")
    return head + "\n\n" + _profile_safe_protocol(profile)


def _profile_safe_protocol(profile: Any) -> str:
    # The allowed-intent list lives once, in the runtime wrapper above; this
    # protocol carries the inspect-topic list, visible fields, and the qed/report
    # close-out (so the intent set is stated exactly once, not three times).
    topics_line = ""
    effective_topics = effective_inspect_topics(profile)
    if effective_topics is not None:
        rendered = ", ".join(f"`{topic}`" for topic in sorted(effective_topics))
        topics_line = (
            "Profile-visible context topic intents: "
            f"{rendered or '`<none>`'}.\n\n"
        )
    preview = ""
    # Switch-aware: gate on the EFFECTIVE intents (which strip `probe_tactic` when
    # the probe lever is OFF), not the raw allowed-intents, so a probe-OFF run does
    # not advertise a `probe_tactic` affordance the manager will reject.
    if "probe_tactic" in (effective_allowed_intents(profile) or frozenset()):
        preview = (
            "Use `probe_tactic` for reversible tactic checks when a shown "
            "candidate needs validation before a commit.\n\n"
        )
    visible_fields = _profile_visible_field_sentence(profile)
    return f"""## Profile-Safe Proof Protocol

This surface profile is part of the interface ladder. Treat panels, intents,
and topics absent from the current surface as unavailable.

{topics_line}{preview}Read the current `ProverWorkspaceView` as the authority for the current state.
Profile-visible fields for this run: {visible_fields}. Choose exactly one next
proof intent, submit it via `submit_proof_intent`, then read the refreshed view
before deciding again.

Do not invent lemmas or axioms; use only declarations visible in source,
planner context, the current workspace view, or exact symbol lookup.

When the refreshed view says `candidate_closed_pending_qed` or offers `qed.`
as a candidate move, submit:
`{{"intent":"commit_tactic","payload":{{"tactic":"qed."}}}}`.
Only after `qed.` is accepted and the next view shows the lemma is saved should
you output `PROOF TACTICS:` followed by the accepted tactic sequence, then a
concise `PROVER REPORT:` JSON block with useful observations, missing guidance,
and blockers if any."""


def _profile_visible_field_sentence(profile: Any) -> str:
    if getattr(profile, "stage", "") == "l1_goal_projection":
        fields = (
            "`current_goal`, `proof_status`, `last_result`, and "
            "`latest_observation`"
        )
    else:
        fields = (
            "`current_goal`, `proof_status`, `program_frontier`, "
            "`application_context`, `facts_and_diagnostics`, `candidate_moves`, "
            "and profile-visible `inspect_lookup_handles`"
        )
    return fields


def _md_proof_so_far(panel: Any) -> str:
    """Render the persistent, step-numbered committed proof so the agent can orient
    (especially a respawned agent) and reference a step for `amend_and_replay`,
    instead of re-deriving work it already committed."""
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


def _workspace_view_preview(view: dict[str, Any]) -> dict[str, Any]:
    """Presentation-only size guard for the inline view: pass the (already
    surface-profiled) view THROUGH, transforming only the size-heavy fields so the
    inline output stays under tool limits — truncate the giant goal, compact the
    navigation, cap the handle list. It does NOT re-select fields.

    WHICH content the agent sees is selected by the SurfaceModel ->
    SurfaceTurnModel pipeline.  This preview helper is only a size guard for the
    raw audit JSON.  It must not re-select panels, actions, or display order."""
    if not isinstance(view, dict):
        return {}
    preview = dict(view)  # pass everything the profile produced straight through

    current_goal = view.get("current_goal")
    if isinstance(current_goal, dict):
        current_goal_preview = dict(current_goal)
        lines = current_goal_preview.get("lines")
        if isinstance(lines, list):
            joined = "\n".join(str(line) for line in lines)
            # The goal is THE thing the agent acts on — show it WHOLE inline. The
            # cap is very high (30k) so every real proof goal renders in full; only a
            # pathological goal (a destructive `inline *` that exploded it into
            # thousands of lines) trips it. Truncating low (3000) and pointing the
            # agent at `latest_workspace_view.json` was actively harmful: it (a) hid
            # the giant goal that IS the undo signal, and (b) drove the agent to read
            # that file via shell, which the bridge-escape watchdog false-killed (the
            # filename contains "workspace_view"). So: full goal inline, and an
            # oversize goal nudges undo instead of a file read.
            lines_preview = _truncate_text(joined, 30000)
            current_goal_preview["lines_preview"] = lines_preview
            current_goal_preview["line_count"] = len(lines)
            current_goal_preview.pop("lines", None)
            if lines_preview != joined:
                current_goal_preview["full_view_text_fully_shown"] = current_goal.get("text_fully_shown")
                current_goal_preview["full_view_truncated"] = current_goal.get("truncated")
                current_goal_preview["text_fully_shown"] = False
                current_goal_preview["truncated"] = True
                current_goal_preview["truncation_scope"] = "inline_preview"
                current_goal_preview["oversize_consider_undo"] = True
        preview["current_goal"] = current_goal_preview

    handles = view.get("inspect_lookup_handles")
    if isinstance(handles, list):
        preview["inspect_lookup_handles"] = handles[:12]

    candidate_moves = view.get("candidate_moves")
    if isinstance(candidate_moves, list):
        moves_preview = []
        for move in candidate_moves[:8]:
            if isinstance(move, dict):
                moves_preview.append(_drop_empty({
                    "label": move.get("label") or move.get("name"),
                    "move": move.get("move"),
                    "applicability": move.get("applicability"),
                    "effect": _truncate_text(str(move.get("effect") or ""), 180),
                    "limitations": _truncate_text(str(move.get("limitations") or ""), 180),
                }))
            else:
                moves_preview.append(move)
        preview["candidate_moves"] = moves_preview
    elif candidate_moves is not None:
        preview["candidate_moves"] = _candidate_moves_preview(candidate_moves)

    return preview


def _candidate_moves_preview(candidate_moves: Any) -> Any:
    if not isinstance(candidate_moves, dict):
        return candidate_moves
    route_health: list[dict[str, Any]] = []
    for item in candidate_moves.get("route_health", [])[:2]:
        if not isinstance(item, dict):
            continue
        route_health.append(_drop_empty({
            "signal": item.get("signal"),
            "confidence": item.get("confidence"),
            "message": _truncate_text(str(item.get("message") or ""), 260),
            "evidence": item.get("evidence"),
            "observed_gap": item.get("observed_gap"),
            "observed_risk": item.get("observed_risk"),
            "related_surface": item.get("related_surface"),
            "concept_diff": item.get("concept_diff"),
            "recommended_next": item.get("recommended_next"),
            "primary_next_action": item.get("primary_next_action"),
            "repair_checkpoint": item.get("repair_checkpoint"),
            "useful_inspections": item.get("useful_inspections"),
            "anti_routes": item.get("anti_routes"),
            "after_rewind_next": item.get("after_rewind_next"),
        }))

    structural_transitions: list[dict[str, Any]] = []
    for item in candidate_moves.get("structural_transitions", [])[:3]:
        if not isinstance(item, dict):
            continue
        structural_transitions.append(_compact_transition_surface(item))

    navigation: list[dict[str, Any]] = []
    for item in candidate_moves.get("navigation", [])[:3]:
        if not isinstance(item, dict):
            continue
        fast_track = item.get("fast_track_probe")
        if isinstance(fast_track, dict):
            fast_track_preview = _drop_empty({
                "tactic": _truncate_text(str(fast_track.get("tactic") or ""), 260),
                "preconditions": fast_track.get("preconditions"),
                "expected_next_shape": _truncate_text(
                    str(fast_track.get("expected_next_shape") or ""),
                    220,
                ),
            })
        else:
            fast_track_preview = fast_track
        navigation.append(_drop_empty({
            "id": item.get("id"),
            "episode": item.get("episode"),
            "route": item.get("route"),
            "confidence": item.get("confidence"),
            "confidence_reason": _truncate_text(
                str(item.get("confidence_reason") or ""),
                220,
            ),
            "valid_for": item.get("valid_for"),
            "why_now": _truncate_text(str(item.get("why_now") or ""), 260),
            "fast_track_probe": fast_track_preview,
            "anti_routes": item.get("anti_routes"),
            "repair_if_fails": item.get("repair_if_fails"),
            "lemma_pack": item.get("lemma_pack"),
        }))

    moves: list[dict[str, Any]] = []
    for move in candidate_moves.get("moves", [])[:6]:
        if not isinstance(move, dict):
            continue
        moves.append(_drop_empty({
            "title": move.get("title") or move.get("label") or move.get("name"),
            "category": move.get("category"),
            "tactic": _truncate_text(str(move.get("tactic") or ""), 220),
            "tactic_shape": _truncate_text(
                str(move.get("tactic_shape") or ""),
                220,
            ),
            "symbol_hint": move.get("symbol_hint"),
            "lookup_before_use": move.get("lookup_before_use"),
            "applicability": _truncate_text(
                str(move.get("applicability") or ""),
                180,
            ),
            "effect": _truncate_text(str(move.get("effect") or ""), 180),
            "limitations": _truncate_text(
                str(move.get("limitations") or ""),
                180,
            ),
        }))

    probe_alternatives: list[dict[str, Any]] = []
    for item in candidate_moves.get("probe_alternatives", [])[:6]:
        if not isinstance(item, dict):
            continue
        goal_summary = item.get("goal_after_probe_summary")
        if isinstance(goal_summary, dict):
            compact_goal_summary = _drop_empty({
                "remaining_goals": goal_summary.get("remaining_goals"),
                "first_lines": [
                    _truncate_text(str(line), 160)
                    for line in goal_summary.get("first_lines", [])[:3]
                ],
                "char_count": goal_summary.get("char_count"),
                "truncated": goal_summary.get("truncated"),
            })
        else:
            compact_goal_summary = {}
        probe_alternatives.append(_drop_empty({
            "tactic": _truncate_text(str(item.get("tactic") or ""), 260),
            "probe_result": item.get("probe_result"),
            "status": item.get("status"),
            "how_to_use": _truncate_text(
                str(item.get("how_to_use") or ""),
                220,
            ),
            "structural_transition": _compact_transition_surface(
                item.get("structural_transition")
            ),
            "closing_decision": _compact_transition_surface(
                item.get("closing_decision")
            ),
            "goal_after_probe_summary": compact_goal_summary,
            "error_summary": _truncate_text(
                str(item.get("error_summary") or ""),
                220,
            ),
        }))

    return _drop_empty({
        "route_health": route_health,
        "structural_transitions": structural_transitions,
        "navigation": navigation,
        "probe_alternatives": probe_alternatives,
        "moves": moves,
        "limitations": candidate_moves.get("limitations", [])[:3],
    })


def _compact_transition_surface(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return _drop_empty({
        "id": item.get("id"),
        "kind": item.get("kind"),
        "status": item.get("status"),
        "tactic": _truncate_text(str(item.get("tactic") or ""), 260),
        "phase": item.get("phase"),
        "valid_for": item.get("valid_for"),
        "why_here": _truncate_text(str(item.get("why_here") or ""), 260),
        "decision": _truncate_text(str(item.get("decision") or ""), 240),
        "recommended_next": item.get("recommended_next"),
        "after_commit": _truncate_text(str(item.get("after_commit") or ""), 260),
        "if_wrong_after_commit": _truncate_text(
            str(item.get("if_wrong_after_commit") or ""),
            220,
        ),
    })


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + "\n... [truncated]"


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
    if intent == "probe_tactic":
        observations = [
            action.get("agent_observation")
            for action in actions
            if isinstance(action.get("agent_observation"), dict)
        ]
        if any(
            observation.get("kind") == "accepted_structural_transition"
            for observation in observations
            if isinstance(observation, dict)
        ):
            return (
                "Accepted structural transition probe. Decide whether to enter "
                "this phase using `last_result.structural_transition`; do not "
                "solve the speculative preview in your mental model, and do "
                "not call `undo_last_step` to undo a read-only probe."
            )
        if any(
            observation.get("kind") == "accepted_closing_probe"
            for observation in observations
            if isinstance(observation, dict)
        ):
            return (
                "Accepted closing/checking probe. Commit the exact tactic only "
                "if you want to try closing or checking this obligation."
            )
        return (
            "Read-only tactic probe. Use any goal-after-probe text as a "
            "preview only; there is no probe step to undo."
        )
    if intent == "probe_replay_suffix_chunk":
        return (
            "Read-only replay chunk probe. The manager checked an old route "
            "chunk in a scratch verifier session; there is no committed replay "
            "step to undo."
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
        "probe_tactic": "tactic probe",
        "commit_tactic": "tactic commit",
        "probe_replay_suffix_chunk": "replay chunk probe",
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

