"""Agent-facing prover prompt construction (the prompt surface).

Extracted from ``workflow/agents/prover.py`` (backlog #7, audit §3.4): the functions
that build the long-lived prover prompt, the child (Layer-3) prompt, and the
session/route handoff sections the agent reads. ``prover.py`` keeps orchestration,
session lifecycle, why3/EC-daemon management, verification, and ``run()``. One-way
import: ``prover.py`` -> ``prover_prompt.py`` (no cycle).
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from core.easycrypt.session_workspace_view_manager import WorkspaceViewManager


def _session_dir_for_tag(session_tag: str) -> str:
    return f".ec_session_{session_tag}"


def _agent_visible_workspace_view(view: dict[str, Any]) -> dict[str, Any]:
    """Return the prompt-facing view with debug CLI fallbacks removed."""
    return WorkspaceViewManager().agent_display_view(view)


def _render_managed_session_handoff(
    session_dir: str,
    managed_session: dict[str, Any] | None,
    *,
    replay_prefix: list[str] | None = None,
) -> str:
    replay_prefix = [t for t in (replay_prefix or []) if str(t).strip()]
    view = (
        managed_session.get("workspace_view")
        if isinstance(managed_session, dict) else None
    )
    if isinstance(view, dict):
        view = _agent_visible_workspace_view(view)
    # Render the handoff through the same SurfaceTurnModel contract used by live
    # manager turns. Raw workspace JSON remains an audit/replay artifact; the
    # agent-facing recovery file is the latest followup surface.
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown

    view_md = (
        render_surface_turn_markdown(
            compose_surface_turn(view, view.get("surface_profile"), handled_intent={})
        )
        if isinstance(view, dict) and view else
        ""
    )
    prefix_lines = ""
    if replay_prefix:
        rendered = "\n".join(f"- `{t}`" for t in replay_prefix)
        prefix_lines = f"""
### Manager-replayed prefix

The manager already replayed this accepted prefix before handing you the
session. Use it as episode context only; do not run it again.

{rendered}
"""
    missing_view_note = ""
    if not isinstance(view, dict) or not view:
        missing_view_note = (
            "\nThe expected manager handoff view is missing from this prompt. "
            "Record which manager context is missing before choosing tactics.\n"
        )
    return f"""{prefix_lines}{missing_view_note}
### Initial proof surface

The manager-produced agent-facing view at handoff — the same markdown surface you
get on every later turn. If this handoff is truncated later, recover it from
`LEGAL_LATEST_FOLLOWUP`; the raw workspace JSON is audit-only.

{view_md}
"""


def _render_route_replay_handoff(
    managed_session: dict[str, Any] | None,
) -> str:
    """Spawn-prompt banner for unconsumed route-memory replay chunks.

    A Layer-3 crash-respawn child inherits the dead node's route memory
    (verifier-checked tactic chunks saved when a route was rewound). The
    chunks already surface inside the workspace view's `route_replay_memory`
    panel, but a collapsed panel is easy to miss at turn 0 — observed
    2026-06-11 on upto_X1_X2, where a respawned child re-derived ~90 saved
    tactics manually over ~25 minutes. This renders an explicit prompt
    section: how many chunks exist, where the frontier is, and that
    `commit_replay_suffix_chunk` is preferred over manual re-derivation.
    Returns "" when the view carries no replayable chunk.
    """
    view = (
        managed_session.get("workspace_view")
        if isinstance(managed_session, dict) else None
    )
    surface = view.get("route_replay_memory") if isinstance(view, dict) else None
    if not isinstance(surface, dict):
        return ""
    items = [
        item for item in list(surface.get("items") or [])
        if isinstance(item, dict)
    ]
    chunk_count = 0
    remaining_tactics = 0
    frontier_lines: list[str] = []
    for item in items:
        chunks = [
            chunk for chunk in list(item.get("available_chunks") or [])
            if isinstance(chunk, dict)
            and isinstance(chunk.get("submit_commit"), dict)
        ]
        if not chunks:
            continue
        chunk_count += len(chunks)
        progress = (
            item.get("progress")
            if isinstance(item.get("progress"), dict) else {}
        )
        try:
            remaining_tactics += int(progress.get("remaining_old_tactics") or 0)
        except (TypeError, ValueError):
            pass
        head = chunks[0]
        first_tactic = str(head.get("first_tactic") or "").strip()
        if len(first_tactic) > 120:
            first_tactic = first_tactic[:117].rstrip() + "..."
        frontier_lines.append(
            f"- next chunk `{head.get('chunk_id')}` "
            f"({head.get('tactic_count')} tactic(s), kind "
            f"`{head.get('kind') or 'route_suffix'}`) starts at "
            f"`{first_tactic}`"
        )
    if chunk_count <= 0:
        return ""
    tactic_note = (
        f" covering ~{remaining_tactics} not-yet-recommitted tactic(s)"
        if remaining_tactics > 0 else ""
    )
    frontier = "\n".join(frontier_lines)
    return f"""
## Saved route memory: replay it, do not re-derive it

This node's earlier route was rewound and the discarded suffix was saved as
verifier-checked replay chunks. {chunk_count} chunk(s){tactic_note} are
available RIGHT NOW from the current proof state (see the
`route_replay_memory` panel in the view for the full menu):

{frontier}

Before deriving tactics manually, consume this memory chunk-by-chunk:

1. `{{"intent": "commit_replay_suffix_chunk", "payload": {{"chunk_id": "..."}}}}`
   — commits the checked chunk and refreshes the view (the next chunk then
   appears in the panel).

Re-deriving these tactics by hand wastes the whole budget the previous
attempt already spent. Only abandon a chunk when the manager rejects it or the
goal has genuinely diverged from the saved route.
"""


def _scrub_session_cli_from_agent_prompt(prompt: str) -> str:
    """Remove low-level session_cli recipes from agent-facing prompts.

    Direct session_cli use remains available as an audited debug signal through
    the process tools, but it should not be presented as the intended proof
    interaction surface.
    """
    prompt = re.sub(
        r"```bash\n(?:[^\n]*session_cli\.py[^\n]*\n)+```",
        (
            "```text\n"
            "Manager request: use the current ProverWorkspaceView action; "
            "if more state is needed, record the missing manager context.\n"
            "```"
        ),
        prompt,
        flags=re.MULTILINE,
    )
    prompt = re.sub(
        r"(?im)^.*session_cli\.py.*\n?",
        "",
        prompt,
    )
    prompt = prompt.replace("session_cli", "manager")
    prompt = prompt.replace("`-agent-view`", "the manager handoff view")
    prompt = prompt.replace("`-episode-view`", "`episode_view`")
    prompt = prompt.replace("`-goal-info`", "the current goal panel")
    prompt = prompt.replace("`-diagnose`", "`diagnose`")
    prompt = prompt.replace("`-try`", "a manager check")
    prompt = prompt.replace("`-next`", "`commit`")
    prompt = prompt.replace("`-chain`", "`commit_chain`")
    prompt = prompt.replace("`-prev`", "`undo`")
    prompt = prompt.replace("-try", "manager check")
    prompt = prompt.replace("-next", "commit")
    prompt = prompt.replace("-chain", "commit_chain")
    prompt = prompt.replace("-prev", "undo")
    prompt = prompt.replace("-agent-view", "manager handoff view")
    prompt = prompt.replace("-goal-info", "current goal panel")
    prompt = prompt.replace("-episode-view", "episode_view")
    prompt = prompt.replace("-diagnose", "diagnose")
    prompt = prompt.replace("next action", "proof option")
    prompt = prompt.replace("Next action", "Proof option")
    prompt = prompt.replace("Lookup first:", "Possible context:")
    prompt = prompt.replace(
        "after Pr handles are exhausted",
        "when comparing Pr-rewrite and direct-equivalence routes",
    )
    return prompt


def _build_prover_prompt(
    file_path: str,
    lemma_name: str,
    include_dir: str,
    session_tag: Optional[str] = None,
    managed_session: dict[str, Any] | None = None,
) -> str:
    """Build the task prompt for the Claude Code subagent."""

    # Sanitize lemma name for shell safety (e.g., ExpPsample_Exp' has a quote)
    safe_lemma = lemma_name.replace("'", "_prime")
    session_tag = session_tag or f"prover_{safe_lemma}"
    session_dir = _session_dir_for_tag(session_tag)

    context_section = f"""
## Target Source
Target file: `{file_path}`

Read the target file on demand for definitions, modules, axioms, and sibling
lemmas. The initial prompt does not embed source text, lemma-name indexes,
cross-file summaries, research context, or structural diffs.
"""

    # Eval mode banner: surfaces the no-retrieval rule inside the prompt itself.
    # CLAUDE.md has the full directive; this is the in-prompt reminder.
    eval_banner = ""
    import os as _os
    if _os.environ.get("EVAL_TARGET_LEMMA", "").strip() == lemma_name:
        eval_banner = (
            f"[EVAL MODE] Measuring real proof construction, not retrieval: do "
            f"not read any cached/prior proof of `{lemma_name}` (traces, "
            f"proof-bank). Sibling lemmas in the target .ec are fine. "
            f"Full rule: CLAUDE.md 'Eval mode'.\n\n"
        )

    context_preamble = (
        "The target file path is below. Use the current manager view for proof "
        "state, and read source text only when a step needs exact declarations."
    )

    managed_session_section = _render_managed_session_handoff(
        session_dir,
        managed_session,
    )

    prompt = f"""{eval_banner}You are proving EasyCrypt lemma `{lemma_name}` in `{file_path}`.

{context_preamble}
{context_section}
{managed_session_section}
"""
    return _scrub_session_cli_from_agent_prompt(prompt)


def _child_repair_context() -> str:
    return (
        "- Read the latest proof surface to refresh the authoritative state; "
        "use only concrete read-only actions displayed on that surface."
    )


def _render_child_proof_ir_slice(layer_move_action: dict | None) -> str:
    if not isinstance(layer_move_action, dict):
        return ""
    proof_slice = layer_move_action.get("proof_ir_slice")
    if not isinstance(proof_slice, dict) or not proof_slice:
        return ""
    lines = [
        "## ProofIR Slice for This Child",
        "",
        (
            f"- layer: `{proof_slice.get('current_layer', 'unknown')}`; "
            f"goal kind: `{proof_slice.get('goal_kind', 'unknown')}`; "
            f"assigned move: `{proof_slice.get('move', 'same')}`"
        ),
    ]
    liveness = proof_slice.get("liveness") or {}
    if isinstance(liveness, dict) and liveness:
        pieces = []
        for key in (
            "live_call_site_count",
            "frontier_call_site_count",
            "live_callable_lemma_count",
            "callable_now_lemma_count",
            "non_frontier_callable_lemma_count",
        ):
            if key in liveness:
                pieces.append(f"{key}={liveness[key]}")
        if pieces:
            lines.append("- resources: " + ", ".join(pieces))

    plans = proof_slice.get("program_action_plans") or []
    if plans:
        lines.extend(["", "Program action plan candidates:"])
        for plan in plans[:3]:
            if not isinstance(plan, dict):
                continue
            headline = str(plan.get("procedure_tail") or plan.get("kind") or "plan")
            lines.append(f"- `{headline}`")
            for action in (plan.get("phase_order") or [])[:4]:
                if not isinstance(action, dict):
                    continue
                hint = (
                    action.get("tactic_hint")
                    or action.get("tactic_template")
                    or action.get("kind")
                    or ""
                )
                reason = action.get("reason") or ""
                lines.append(f"  - {action.get('kind', '?')}: `{hint}`")
                if reason:
                    lines.append(f"    reason: {reason}")

    candidates = proof_slice.get("candidate_menu") or []
    if candidates:
        lines.extend(["", "Current-layer candidates:"])
        for item in candidates[:4]:
            if not isinstance(item, dict):
                continue
            tactic = item.get("tactic") or item.get("id") or "candidate"
            why = item.get("why") or ""
            lines.append(
                f"- `{tactic}` [{item.get('tactic_family', '?')}]: {why}"
            )

    callables = proof_slice.get("callable_lemmas") or []
    if callables:
        lines.extend(["", "Live callable lemma handles:"])
        for handle in callables[:4]:
            if not isinstance(handle, dict):
                continue
            lines.append(
                f"- `{handle.get('lemma', '?')}` for "
                f"`{handle.get('procedure', '?')}` "
                f"({handle.get('frontier_status', '?')}): "
                f"{handle.get('repair_hint', '')}"
            )

    pr_plan = proof_slice.get("pr_path_plan") or {}
    if isinstance(pr_plan, dict):
        rec = pr_plan.get("recommended_path") or {}
        if isinstance(rec, dict) and rec:
            lemmas = ", ".join(str(x) for x in (rec.get("lemmas") or [])[:5])
            lines.extend([
                "",
                (
                    f"Pr path plan: relation `{rec.get('relation', '')}`, "
                    f"hops={rec.get('hop_count', 0)}, lemmas: {lemmas}"
                ),
            ])

    diagnostics = proof_slice.get("diagnostics") or []
    if diagnostics:
        lines.extend(["", "Diagnostics to respect:"])
        for diag in diagnostics[:3]:
            if not isinstance(diag, dict):
                continue
            lines.append(
                f"- `{diag.get('code', 'proof_ir.diagnostic')}`: "
                f"{diag.get('message', '')}"
            )
    lines.extend([
        "",
        (
            "Use this slice as compiler analysis, not as a forced script: "
            "replay the prefix, read the actual current goal, then choose "
            "tactics that respect the live resources and phase ordering."
        ),
    ])
    return "\n".join(lines) + "\n"


def _probability_budget_failure_directive(
    negative_signal: list[str],
    parent_goal_state: str,
    repair_context: str,
) -> str:
    if not negative_signal:
        return ""
    first = str(negative_signal[0] or "").strip()
    lower = first.lower()
    context = f"{first}\n{parent_goal_state}".lower()
    probability_context = (
        "bound" in context
        and "[<=]" in context
        and ("/" in context and ("*" in context or "^" in context))
    )
    if not probability_context:
        return ""
    if re.search(r"\bcall\s*\(\s*_:\s*true\s*\)\s*\.", lower):
        label = "direct `call (_: true).` under a product/one-sided bound"
    elif re.match(r"\s*seq\s+\d+\b", lower):
        if "size " in lower and ("*" in lower or "^" in lower or "/" in lower):
            label = "product-budget-on-side-fact `seq`"
        elif "1%r" in lower and (r"\in" in lower or " in " in lower):
            label = "event-preserving `seq` candidate that needs ledger classification"
        else:
            label = "recorded probability-budget `seq` shape"
    else:
        return ""
    return f"""
The parent branch tried {label} under a product/one-sided probability bound and
it did not work out. This is information about what was tried, not a ban.

The useful FACT is structural: under a product or one-sided bound, WHERE the
budget is allocated across a `seq`/`call` boundary decides whether a step keeps
the bound — a direct `call (_: true).` for a one-sided bound, or putting the
whole product budget on a deterministic side fact (e.g. a size bound), typically
loses it, whereas an event-preserving `seq ... event 1%r` or
`call (_: PRE /\\ event ==> event)` can be a sound boundary move.

Read the current goal and decide for yourself; EasyCrypt is the authority on
whether any step is sound, not this note.
{repair_context}
"""


def _build_child_prover_prompt(
    file_path: str,
    lemma_name: str,
    include_dir: str,
    session_tag: str,
    replay_prefix: list[str],
    negative_signal: list[str],
    parent_goal_state: str = "",
    discoveries: list[str] = None,
    blocked_openers: list[str] = None,
    layer_move_action: dict | None = None,
    managed_session: dict[str, Any] | None = None,
) -> str:
    """Build a prompt for a child prover that starts from a branch point.

    The child replays the prefix to reach the branch point, then explores
    a different approach. It receives the parent's goal state, accumulated
    discoveries from other provers, and a negative signal.

    `blocked_openers` lists first-structural-tactics the parent branch
    already tried from this branch point — the child MUST NOT repeat them.
    This forces genuine diversity at spawn time (empirically, today's
    children reconverge on the parent's opener in almost all cases).
    """
    session_dir = _session_dir_for_tag(session_tag)

    # Format negative signal
    neg_lines = []
    for tac in negative_signal:
        neg_lines.append(f"  - `{tac}`")
    neg_text = "\n".join(neg_lines) if neg_lines else (
        "  (no concrete failed tactic was recorded; this child is a "
        "same-frontier/layer-move explorer)"
    )

    # Get the first structural tactic that failed (for targeted advice)
    first_failed = negative_signal[0].split()[0].rstrip(".;") if negative_signal else ""

    repair_context = _child_repair_context()

    context_section = f"""
## Target Source
Target file: `{file_path}`

Read the target file on demand for definitions, modules, axioms, and sibling
lemmas. The child prompt does not embed source text, lemma-name indexes,
cross-file summaries, research context, or structural diffs.
"""

    # Generic layer-move action. This is the main "compiler-like" branch
    # mechanism: a child is assigned a proof-layer experiment (move up, stay,
    # or move down) while still being allowed to reject it after replay if the
    # concrete EC state makes another action more appropriate.
    layer_move_action_directive = ""
    if layer_move_action:
        current_layer = layer_move_action.get("current_layer") or "unknown"
        move = layer_move_action.get("move") or "same"
        move_label = layer_move_action.get("move_label") or move
        focus = layer_move_action.get("focus") or []
        first_failed_tactic = (
            layer_move_action.get("first_failed_tactic") or ""
        )
        failed_experiment = layer_move_action.get("failed_experiment")
        focus_lines = "\n".join(f"  - {item}" for item in focus[:4])
        memory_lines = ""
        if isinstance(failed_experiment, dict):
            samples = failed_experiment.get("sample_tactics") or []
            sample_lines = "\n".join(f"  - `{t}`" for t in samples[:3])
            memory_lines = f"""

Recent sibling memory: `{failed_experiment.get('experiment_kind', '?')}` hit `{failed_experiment.get('failure_shape', '?')}` on `{failed_experiment.get('subject', '?')}` {failed_experiment.get('count', '?')} times. Do not spend this child retrying that same experiment shape.
{sample_lines}
"""
        layer_move_action_directive = f"""
## Layer-move action

This child was spawned to explore one tree-search direction: **{move_label}** from the current `{current_layer}` proof layer — a non-binding search hint, not a proof fact, a verdict, or an instruction.

Read the actual goal and follow it. If the goal calls for a different move — including a tactic the parent tried — take it; EasyCrypt is the authority, not this hint. Note any mismatch in the PROVER REPORT rather than forcing this direction.

Focus for this branch:
{focus_lines if focus_lines else '  - choose a materially different proof-layer move from the parent'}
{f'''
Parent's first failed tactic at this branch was:
```
{first_failed_tactic}
```
''' if first_failed_tactic else ''}{memory_lines}
"""
        layer_move_action_directive += _render_child_proof_ir_slice(
            layer_move_action,
        )

    # A': render openers-already-tried as a NEUTRAL FACT, not a prohibition.
    # The parent branch committed these openers from this point and none reached
    # qed. Surfacing them nudges this child toward a different angle (children
    # otherwise converge on the parent's strategy), but it is information, not a
    # ban: a tactic that failed for the parent on a FORM/feedback reason or on a
    # different sub-state can still be correct here, and EC — not this list — is
    # the authority. (A hard ban here once steered an eager-while child on a
    # held-out MAC corpus run away from the provably-correct `eager while`
    # because the parent's failures were parse-errors, not "eager is wrong".)
    blocked_directive = ""
    if blocked_openers:
        blocked_list = ", ".join(f"`{t}`" for t in blocked_openers)
        blocked_directive = f"""
## Openers the parent already tried at this branch point

The parent branch committed these openers from this exact point and none reached
`qed`: {blocked_list}. This is neutral information about what has been explored —
NOT a prohibition.

- For DIVERSITY, prefer a structurally different opener so this child explores a
  new angle instead of re-deriving the parent's path.
- But EasyCrypt is the authority, not this list. If reading the goal shows that
  one of these openers (or a variant) is actually the right move, use it — a
  tactic that failed for the parent for a FORM/feedback reason, or on a different
  sub-state, can still be correct here. Do not read "the parent tried it" as "it
  is wrong."

When the goal is genuinely ambiguous, a materially different strategy is the
better use of this child. Always end your turn with a `submit_proof_intent` call
(use `finish` only if you have truly run out of distinct strategies).
"""

    probability_failure_directive = _probability_budget_failure_directive(
        negative_signal,
        parent_goal_state,
        repair_context,
    )
    if probability_failure_directive:
        failure_directive = probability_failure_directive
    elif negative_signal:
        failure_directive = f"""
The parent reached a dead end with `{first_failed}` (and similar tactics) from
this frontier. That is information about what has been tried, not a ban: if
reading the goal shows it is the correct move, EasyCrypt decides — use it.
Otherwise a materially different path from this frontier is likely the more
productive use of this child.
{repair_context}
"""
    else:
        failure_directive = """
No tactic is banned solely because this section is empty. Use the layer-move
action and the parent goal state to explore a materially different path from
the same frontier.
"""
    managed_session_section = _render_managed_session_handoff(
        session_dir,
        managed_session,
        replay_prefix=replay_prefix,
    )
    route_replay_section = _render_route_replay_handoff(managed_session)

    prompt = f"""You are proving EasyCrypt lemma `{lemma_name}` in `{file_path}`.

Below is your proof of this lemma in progress: the committed steps are your own
work so far, and the view shows the goal you are at now. Continue from the
current goal. The whole proof is yours — nothing in the committed history is
off-limits: if an earlier step turns out to be a dead end, rewind to any
checkpoint in the menu and redo it.
{context_section}{layer_move_action_directive}{blocked_directive}
## Current Proof State

{managed_session_section}

The view above is the authoritative current state; read it before choosing your
next tactic.
{route_replay_section}
{f'''
## Current Goal
Your proof currently sits at this goal:
```
{parent_goal_state[-1500:]}
```
Use this to understand the proof state WITHOUT re-reading it from EC.
''' if parent_goal_state else ''}
{f'''
## Useful facts for this lemma
{chr(10).join(f"- {d}" for d in (discoveries or []))}
Consider using these in your proof.
''' if discoveries else ''}
{f'''
## Lines already ruled out from here — DO NOT repeat
These tactics have already been tried from the current point and do not work;
take a different line:
{neg_text}
{failure_directive}
''' if (neg_text and neg_text.strip()) else ''}"""
    return _scrub_session_cli_from_agent_prompt(prompt)
