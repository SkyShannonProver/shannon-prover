"""Agent-facing prover prompt construction (the prompt surface).

Extracted from ``workflow/agents/prover.py`` (backlog #7, audit §3.4): the functions
that build the long-lived prover prompt, the child (Layer-3) prompt, and the
session/route handoff sections the agent reads. ``prover.py`` keeps orchestration,
session lifecycle, why3/EC-daemon management, verification, and ``run()``. One-way
import: ``prover.py`` -> ``prover_prompt.py`` (no cycle).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from workflow.proof_tool.easycrypt_source_resource import (
    SOURCE_RESOURCE_MANIFEST_ENV,
)

from workflow.proof_state_compiler.current_turn_presentation import (
    compose_current_surface_turn,
    render_current_surface_turn_markdown,
    require_current_workspace_view,
)
from workflow.proof_state_compiler.profile_registry import (
    normalize_runtime_surface_profile_id,
)


MANAGED_HANDOFF_START = "<!-- shannon-managed-handoff:start -->"
MANAGED_HANDOFF_END = "<!-- shannon-managed-handoff:end -->"


def managed_handoff_block(prompt: str) -> str:
    """Return the marked provisional handoff, or ``""`` when absent."""

    start = prompt.find(MANAGED_HANDOFF_START)
    end = prompt.find(MANAGED_HANDOFF_END)
    if start < 0 and end < 0:
        return ""
    if start < 0 or end < start:
        raise ValueError("prover prompt has malformed managed handoff markers")
    end += len(MANAGED_HANDOFF_END)
    if prompt.find(MANAGED_HANDOFF_START, start + 1) >= 0:
        raise ValueError("prover prompt has duplicate managed handoff start markers")
    if prompt.find(MANAGED_HANDOFF_END, end) >= 0:
        raise ValueError("prover prompt has duplicate managed handoff end markers")
    return prompt[start:end]


def bind_authoritative_managed_handoff(
    prompt: str,
    initial_followup: str,
) -> str:
    """Replace the provisional handoff with the manager-bound turn-0 surface.

    The orchestrator can render goal facts before worker adoption, but it does
    not own live mutation authority and therefore cannot render runnable
    actions.  The worker calls this only after ``ProofNodeManager`` adoption
    and turn-0 composition.  Prompts without markers are retained for unit and
    transitional callers; malformed marker pairs fail closed.
    """

    block = managed_handoff_block(prompt)
    if not block:
        return prompt
    surface = str(initial_followup or "").strip()
    legal_anchor = "\n\n### Legal Node Memory Anchor"
    if legal_anchor in surface:
        surface = surface.split(legal_anchor, 1)[0].rstrip()
    if not surface:
        raise ValueError("authoritative manager handoff is empty")
    replacement = (
        f"{MANAGED_HANDOFF_START}\n"
        "### Initial proof surface\n\n"
        "This is the authoritative manager-bound turn-0 surface. It is the "
        "same current-turn rendering persisted as "
        "`LEGAL_LATEST_FOLLOWUP`.\n\n"
        f"{surface}\n"
        f"{MANAGED_HANDOFF_END}"
    )
    return prompt.replace(block, replacement, 1)


def _session_dir_for_tag(session_tag: str) -> str:
    return f".ec_session_{session_tag}"


def _agent_visible_workspace_view(
    view: dict[str, Any],
    surface_profile: str | None,
) -> dict[str, Any]:
    """Validate the current lean view before including it in a handoff."""

    return require_current_workspace_view(
        view,
        profile_id=normalize_runtime_surface_profile_id(surface_profile),
        label="prover prompt current handoff workspace view",
    )


def _render_managed_session_handoff(
    session_dir: str,
    managed_session: dict[str, Any] | None,
    *,
    surface_profile: str | None = None,
) -> str:
    view = (
        managed_session.get("workspace_view")
        if isinstance(managed_session, dict) else None
    )
    if isinstance(view, dict):
        view = _agent_visible_workspace_view(view, surface_profile)
    if isinstance(view, dict) and view:
        turn = compose_current_surface_turn(
            view,
            normalize_runtime_surface_profile_id(surface_profile),
            handled_intent={},
        )
        view_md = render_current_surface_turn_markdown(turn)
    else:
        view_md = ""
    missing_view_note = ""
    if not isinstance(view, dict) or not view:
        missing_view_note = (
            "\nThe expected manager handoff view is missing from this prompt. "
            "Record which manager context is missing before choosing tactics.\n"
        )
    return f"""{MANAGED_HANDOFF_START}
{missing_view_note}
### Initial proof surface

The manager-produced agent-facing view at handoff — the same markdown surface you
get on every later turn. If this handoff is truncated later, recover it from
`LEGAL_LATEST_FOLLOWUP`; the raw workspace JSON is audit-only.

{view_md}
{MANAGED_HANDOFF_END}
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
    return prompt


def _source_access_prompt(*, eval_mode: bool) -> str:
    if not eval_mode:
        return (
            "Read the target file on demand for definitions, modules, axioms, "
            "and sibling lemmas."
        )
    import os as _os

    if _os.environ.get(SOURCE_RESOURCE_MANIFEST_ENV, "").strip():
        return (
            "Use only the manager-owned source-navigation tools described in "
            "the runtime contract; provider-native filesystem, shell, and "
            "generic resource access are disabled. Proof-state interaction "
            "remains exclusively through `submit_proof_intent`."
        )
    return (
        "The proof-stripped source is backend input, not an agent-facing "
        "filesystem resource. Do not call shell, filesystem, MCP resource, or "
        "source-reading tools. Use only the manager-owned proof tool and the "
        "exact declarations/resource anchors it advertises."
    )


def _build_prover_prompt(
    file_path: str,
    lemma_name: str,
    include_dir: str,
    session_tag: Optional[str] = None,
    managed_session: dict[str, Any] | None = None,
    surface_profile: str | None = None,
) -> str:
    """Build the task prompt for the selected managed prover agent."""

    # Sanitize lemma name for shell safety (e.g., ExpPsample_Exp' has a quote)
    safe_lemma = lemma_name.replace("'", "_prime")
    session_tag = session_tag or f"prover_{safe_lemma}"
    session_dir = _session_dir_for_tag(session_tag)

    import os as _os
    eval_mode = _os.environ.get("EVAL_TARGET_LEMMA", "").strip() == lemma_name
    source_access = _source_access_prompt(eval_mode=eval_mode)
    context_section = f"""
## Target Source
Target file: `{file_path}`

{source_access} The initial prompt does not embed source text, lemma-name indexes,
cross-file summaries, research context, or structural diffs.
"""

    # Eval mode banner: surfaces the no-retrieval rule inside the prompt itself.
    # The repository policy has the full directive; this is the prompt reminder.
    eval_banner = ""
    if eval_mode:
        eval_banner = (
            f"[EVAL MODE] Measuring real proof construction, not retrieval: do "
            f"not read cached or prior proof material for `{lemma_name}`. "
            f"Sibling lemmas in the target .ec are fine. "
            f"Full rule: repository 'Eval mode' policy.\n\n"
        )

    context_preamble = (
        "The target file path is below. Use the current manager view for proof "
        "state."
        if eval_mode
        else (
            "The target file path is below. Use the current manager view for "
            "proof state, and read source text only when a step needs exact "
            "declarations."
        )
    )

    managed_session_section = _render_managed_session_handoff(
        session_dir,
        managed_session,
        surface_profile=surface_profile,
    )

    prompt = f"""{eval_banner}You are proving EasyCrypt lemma `{lemma_name}` in `{file_path}`.

{context_preamble}
{context_section}
{managed_session_section}
"""
    return _scrub_session_cli_from_agent_prompt(prompt)


def _build_child_prover_prompt(
    file_path: str,
    lemma_name: str,
    include_dir: str,
    session_tag: str,
    *,
    layer_move_action: dict | None = None,
    managed_session: dict[str, Any] | None = None,
    surface_profile: str | None = None,
    outer_proof_handoff: dict[str, Any] | None = None,
) -> str:
    """Build a child prompt without a second proof-state presentation path.

    Tree topology may assign an abstraction direction, but all current proof
    facts, actions, failures, and replay affordances come from the manager's
    current-turn handoff below.
    """
    session_dir = _session_dir_for_tag(session_tag)

    import os as _os
    eval_mode = _os.environ.get("EVAL_TARGET_LEMMA", "").strip() == lemma_name
    source_access = _source_access_prompt(eval_mode=eval_mode)
    context_section = f"""
## Target Source
Target file: `{file_path}`

{source_access} The child prompt does not embed source text, lemma-name indexes,
cross-file summaries, research context, or structural diffs.
"""

    layer_move_action_directive = ""
    if layer_move_action:
        current_layer = layer_move_action.get("current_layer") or "unknown"
        move = layer_move_action.get("move") or "same"
        move_label = layer_move_action.get("move_label") or move
        layer_move_action_directive = f"""
## Tree branch assignment

The orchestrator assigned this child the **{move_label}** (`{move}`) branch from
the `{current_layer}` abstraction layer. This label distinguishes tree-search
topology only. It carries no goal facts, tactic candidates, proof route, or
verdict; use the manager surface below as the sole proof-state authority.

If the authoritative surface makes that direction inapplicable, follow the
proof state rather than forcing the branch label.
"""
    managed_session_section = _render_managed_session_handoff(
        session_dir,
        managed_session,
        surface_profile=surface_profile,
    )
    outer_handoff_section = _render_outer_proof_handoff(outer_proof_handoff)

    prompt = f"""You are proving EasyCrypt lemma `{lemma_name}` in `{file_path}`.

Continue from the manager-owned proof state below. Use the persistent proof
controls for commit/undo/rewind/restart/finish; use only state-dependent
information actions advertised by the current surface.
{context_section}{layer_move_action_directive}{outer_handoff_section}
## Current Proof State

{managed_session_section}

The view above is the authoritative current state; read it before choosing your
next tactic.
"""
    return _scrub_session_cli_from_agent_prompt(prompt)


def _render_outer_proof_handoff(context: dict[str, Any] | None) -> str:
    """Confirm the replay; detailed guidance lives in the durable anchor."""

    if not isinstance(context, dict) or context.get("kind") != "outer_proof_handoff":
        return ""
    count = int(context.get("accepted_command_count") or 0)
    commands_hash = str(context.get("accepted_commands_sha256") or "")[:64]
    return f"""
## Same-run outer proof handoff

The manager has replayed {count} complete EasyCrypt command(s) authored by the
outer proof constructor (command-sequence hash `{commands_hash}`). Its bounded
strategy, rejected boundary, candidate suffix, and resource anchors are in the
durable continuation brief supplied by the runtime. They are untrusted
guidance; the exact current goal below is the sole proof-state authority.
"""
