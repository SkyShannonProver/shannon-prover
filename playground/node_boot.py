"""Bootstrap and drive ONE standalone Shannon Prover proof node.

A human playground is a drop-in replacement for the agent: the same JSON intents
go through the same `ProofNodeManager.handle_agent_message` loop, and we render
the same followup the agent reads. No tree supervisor / worker subprocess / MCP
transport is needed — those only add process isolation in the real run.

Construction (verified against the real orchestrator path):
    manager = ProofNodeManager(...); bootstrap = manager.bootstrap(replay_prefix=[])
    turn    = manager.handle_agent_message('{"intent": ..., "payload": ...}')
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import uuid
from pathlib import Path
from typing import Any

from workflow.proof_node_manager import ProofNodeManager
from workflow.proof_management.types import ManagedTurn
from workflow.proof_management import ALLOWED_AGENT_INTENTS
from workflow.agent_prompt_render import render_long_lived_agent_prompt
from workflow.agents.prover_prompt import _build_prover_prompt
from workflow.proof_node_mcp_server import (
    SERVER_NAME,
    SERVER_VERSION,
    _intent_schema_description,
    _payload_description,
    _submit_tool_description,
)
from workflow.surface_profiles import ensure_supported_surface_profile
from workflow.surface_profiles import schema_intents_for_surface_profile
from core.easycrypt.session_workspace_view_manager import WorkspaceViewManager
from workflow.proof_node_runtime import _render_manager_followup
from workflow.surface_decision_context import merge_surface_decision_context
from workflow.surface_turn_model import (
    compose_surface_turn,
    proof_surface_from_turn,
    render_surface_turn_markdown,
)

# Repo root = parent of this `playground/` package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DISPLAY_MAX_TURNS = 1000

def _next_tag(lemma: str) -> str:
    """A unique, filesystem-safe session tag (uuid suffix) so every session gets a
    FRESH EasyCrypt session dir — never reusing a leftover mid-proof one (which the
    backend refuses to ``-start`` over)."""
    safe = "".join(c if c.isalnum() else "_" for c in lemma)[:40]
    return f"playground_{safe}_{uuid.uuid4().hex[:8]}"

def _render_mcp_tool_context(profile: str, node_memory_dir: Path) -> str:
    allowed = sorted(
        schema_intents_for_surface_profile(profile) & ALLOWED_AGENT_INTENTS
    )
    schema = {
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "tools": [
            {
                "name": "submit_proof_intent",
                "description": _submit_tool_description(allowed, node_memory_dir),
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": allowed,
                            "description": _intent_schema_description(allowed),
                        },
                        "payload": {
                            "type": "object",
                            "description": _payload_description(allowed),
                            "additionalProperties": True,
                        },
                    },
                    "required": ["intent"],
                },
            }
        ],
    }
    return json.dumps(schema, indent=2, ensure_ascii=False)


_RUNTIME_TASK_MARKER = (
    "The original prover prompt follows — your specific lemma, the file, "
    "and the profile-visible reference panels.\n\n---\n\n"
)


def _split_runtime_prompt(runtime_prompt: str) -> tuple[str, str]:
    if _RUNTIME_TASK_MARKER not in runtime_prompt:
        return runtime_prompt, ""
    runtime_contract, task_context = runtime_prompt.split(_RUNTIME_TASK_MARKER, 1)
    return runtime_contract.rstrip(), _RUNTIME_TASK_MARKER + task_context


def _strip_initial_workspace_view(prompt: str) -> str:
    marker = "\n### Initial ProverWorkspaceView\n"
    if marker not in prompt:
        return prompt
    before, _ = prompt.split(marker, 1)
    missing_note = (
        "\nThe expected manager handoff view is missing from this prompt. "
        "Record which manager context is missing before choosing tactics.\n"
    )
    return before.replace(missing_note, "").rstrip() + "\n"


def _planner_context_for_instructions(
    *,
    file: str,
    lemma: str,
    include_dir: str,
    profile: str,
    session_tag: str,
):
    """Use the default planner for L4-style instruction preview.

    L1 is intentionally planner-free. Other profiles should show the same
    planner-backed task context a normal prover handoff receives, while still
    excluding the first-turn workspace view.
    """
    if profile == "l1_goal_projection":
        return None
    from workflow.agents.proof_planner import run as run_planner
    from workflow.schemas.config import RunConfig

    planner_dir = PROJECT_ROOT / "playground" / "node_memory" / session_tag / "planner"
    planner_dir.mkdir(parents=True, exist_ok=True)
    eval_target = os.environ.get("EVAL_TARGET_LEMMA", "").strip()
    config = RunConfig(
        file=file,
        lemma=lemma,
        include_dir=include_dir,
        output_dir=str(planner_dir),
        eval_mode=(eval_target == lemma),
        surface_profile=profile,
    )
    # The planner emits human progress logs to stdout. In the web playground this
    # endpoint may be called after the launching terminal has gone away; progress
    # logging must not turn into a user-visible "Broken pipe" render failure.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return run_planner(config, planner_dir)


def render_instructions(
    *,
    file: str,
    lemma: str,
    include_dir: str,
    profile: str,
    session_tag: str | None = None,
) -> str:
    ensure_supported_surface_profile(profile)
    session_tag = session_tag or f"instructions_{''.join(c if c.isalnum() else '_' for c in lemma)[:40]}"
    plan = _planner_context_for_instructions(
        file=file,
        lemma=lemma,
        include_dir=include_dir,
        profile=profile,
        session_tag=session_tag,
    )
    task_prompt = _build_prover_prompt(
        file,
        lemma,
        include_dir,
        session_tag=session_tag,
        plan=plan,
        managed_session=None,
    )
    task_prompt = _strip_initial_workspace_view(task_prompt)
    node_memory_dir = PROJECT_ROOT / "playground" / "node_memory" / session_tag
    runtime_prompt = render_long_lived_agent_prompt(
        task_prompt,
        host="127.0.0.1",
        port=0,
        token="<redacted>",
        node_memory_dir=node_memory_dir,
        max_turns=DISPLAY_MAX_TURNS,
        surface_profile=profile,
    )
    runtime_contract, task_context = _split_runtime_prompt(runtime_prompt)
    return "\n\n".join([
        "# Agent Instructions",
        (
            "This is the state-independent instruction context for the selected "
            "file, lemma, and surface profile. It excludes the first-turn "
            "ProverWorkspaceView / proof panel, so it can be rendered before "
            "starting a proof daemon. L4-style profiles use the default planner "
            "context here; L1 remains planner-free. Hidden Claude Code "
            "host/system messages are not available to the playground process."
        ),
        "## Runtime Contract (Generated)",
        runtime_contract,
        "## Per-Node MCP Tool Metadata (Generated)",
        _render_mcp_tool_context(profile, node_memory_dir),
        "## Task Context (Generated)",
        task_context,
    ])


def _render_initial_prompt(
    *,
    file: str,
    lemma: str,
    include_dir: str,
    session_tag: str,
    profile: str,
    bootstrap: dict[str, Any],
) -> str:
    _ = bootstrap
    return render_instructions(
        file=file,
        lemma=lemma,
        include_dir=include_dir,
        session_tag=session_tag,
        profile=profile,
    )


class Node:
    """Handle for one live proof node."""

    def __init__(
        self,
        manager: ProofNodeManager,
        bootstrap: dict[str, Any],
        profile: str,
        *,
        initial_prompt: str,
    ):
        self.manager = manager
        self.bootstrap = bootstrap
        self.profile = profile
        self.initial_prompt = initial_prompt
        self.initial_prompt_profile = profile
        self.turn_index = 0


def bootstrap_node(
    file: str,
    lemma: str,
    profile: str,
    *,
    include_dir: str,
    work_dir: Path | None = None,
) -> Node:
    """Build ONE live proof node with EasyCrypt loaded at ``lemma``.

    Requires the opam ``easycrypt`` switch reachable (PATH, or via the backend's
    ``opam env`` shell-out). Structural tactics (proc/inline/call/wp/rewrite) work
    out of the box; ``smt()``/``auto`` need why3server, which EasyCrypt starts
    automatically when the process is NOT under an OS sandbox that blocks nice().
    """
    ensure_supported_surface_profile(profile)
    tag = _next_tag(lemma)
    manager = ProofNodeManager(
        file_path=file,
        lemma_name=lemma,
        include_dir=include_dir,
        session_tag=tag,
        node_id=tag,
        run_dir=work_dir,                 # None is fine; only disables the on-disk audit twin
        project_root=PROJECT_ROOT,
        surface_profile=profile,          # l1_goal_projection | l4_checked_action_surface | adaptive
    )
    bootstrap = manager.bootstrap(replay_prefix=[])
    if not bootstrap.get("workspace_view"):
        _safe_dispose(manager)
        raise RuntimeError(
            f"Bootstrap produced no view for {lemma} in {file} — check the file loads "
            f"(require/import + include_dir) and the lemma name is exact."
        )
    initial_prompt = _render_initial_prompt(
        file=file,
        lemma=lemma,
        include_dir=include_dir,
        session_tag=tag,
        profile=profile,
        bootstrap=bootstrap,
    )
    return Node(manager, bootstrap, profile, initial_prompt=initial_prompt)


def drive(node: Node, intent_json: str) -> ManagedTurn:
    """One human turn. ``intent_json`` e.g. '{"intent":"commit_tactic","payload":{"tactic":"proc."}}'."""
    node.turn_index += 1
    return node.manager.handle_agent_message(intent_json)


def render_followup(
    node: Node,
    turn_or_view: Any,
    profile: str,
    *,
    base_view: Any | None = None,
    full_view: Any | None = None,
) -> str:
    """Render the markdown the agent would read, honoring the surface profile.

    Pass the bootstrap dict (initial view) or a ManagedTurn (per-turn followup).
    """
    goal_only = profile == "l1_goal_projection"
    if isinstance(turn_or_view, ManagedTurn):
        handled = turn_or_view.intent.to_dict() if turn_or_view.intent else None
        return _render_manager_followup(
            turn_or_view,
            node.turn_index,
            handled,
            memory=None,
            full_view=full_view if full_view is not None else getattr(node.manager, "latest_full_view", None),
            surface_profile=profile,
            base_view=workspace_view_of(base_view),
        )
    surface_turn = surface_turn_of(
        turn_or_view,
        profile,
        base_view=base_view,
        full_view=full_view,
    )
    return render_surface_turn_markdown(surface_turn, goal_only=goal_only)


def workspace_view_of(turn_or_view: Any) -> dict[str, Any]:
    """The structured ProverWorkspaceView (the off-surface 'audit view')."""
    if isinstance(turn_or_view, ManagedTurn):
        return turn_or_view.workspace_view or {}
    if isinstance(turn_or_view, dict):
        return turn_or_view.get("workspace_view", turn_or_view)
    return {}


def surface_turn_of(
    turn_or_view: Any,
    profile: str,
    *,
    base_view: Any | None = None,
    full_view: Any | None = None,
) -> dict[str, Any]:
    """The typed per-turn presentation contract used by the web card.

    ``turn_or_view`` may be the bootstrap dict, a raw workspace view, or a
    ManagedTurn.  ``base_view`` is the last committed/base proof state used when
    the current turn is read-only or a control-menu response.
    """
    goal_only = profile == "l1_goal_projection"
    view_manager = WorkspaceViewManager()
    raw = workspace_view_of(turn_or_view)
    try:
        view = view_manager.agent_display_view(raw)
    except Exception:
        view = dict(raw) if isinstance(raw, dict) else {}
    raw_full = workspace_view_of(full_view)
    try:
        profiled_full = view_manager.agent_display_view(raw_full) if raw_full else {}
    except Exception:
        profiled_full = dict(raw_full) if isinstance(raw_full, dict) else {}
    view, profiled_full, decision_context = merge_surface_decision_context(
        view,
        profiled_full,
    )
    raw_base = workspace_view_of(base_view)
    try:
        profiled_base = view_manager.agent_display_view(raw_base) if raw_base else {}
    except Exception:
        profiled_base = dict(raw_base) if isinstance(raw_base, dict) else {}
    if decision_context and isinstance(profiled_base, dict):
        profiled_base["decision_context"] = dict(decision_context)
    base_surface = {}
    if isinstance(raw_base, dict):
        base_surface = proof_surface_from_turn(raw_base.get("surface_turn") or {})
    if not base_surface and isinstance(base_view, dict):
        base_surface = proof_surface_from_turn(base_view.get("surface_turn") or {})
    handled: dict[str, Any] | None = None
    ok = True
    repair_prompt = ""
    manager_actions = None
    health_event = {}
    if isinstance(turn_or_view, ManagedTurn):
        handled = turn_or_view.intent.to_dict() if turn_or_view.intent else {}
        ok = bool(turn_or_view.ok)
        repair_prompt = str(turn_or_view.repair_prompt or "")
        manager_actions = turn_or_view.manager_actions
        if getattr(turn_or_view, "health_event", None) is not None:
            health_event = turn_or_view.health_event.to_dict()
    return compose_surface_turn(
        view,
        profile,
        base_view=profiled_base,
        base_surface=base_surface,
        handled_intent=handled,
        ok=ok,
        repair_prompt=repair_prompt,
        manager_actions=manager_actions,
        health_event=health_event,
        goal_only=goal_only,
    )


def dispose(node: Node) -> None:
    _safe_dispose(getattr(node, "manager", None))


def _safe_dispose(manager: Any) -> None:
    """Best-effort shutdown of the manager's EasyCrypt session."""
    if manager is None:
        return
    for target in (manager, getattr(manager, "repl", None)):
        if target is None:
            continue
        for meth in ("shutdown", "close", "stop"):
            fn = getattr(target, meth, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
                return
