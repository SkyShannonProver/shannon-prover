"""Manager-authored per-turn followup rendering for the prover agent.

Turns one completed manager turn into the agent-facing followup markdown and
persists it through ``NodeMemory``; read-only over the current-turn
presentation owned by the proof-state compiler.
"""
from __future__ import annotations

import json
from typing import Any

from workflow.node.agent_prompt_render import (
    _agent_safe_action_summaries,
    _drop_empty,
)
from workflow.node.node_memory import NodeMemory
from workflow.proof_management import (
    ManagedTurn,
)
from workflow.proof_state_compiler.current_turn_presentation import (
    compose_current_surface_turn,
    current_proof_surface_from_turn,
    render_current_surface_turn_markdown,
    require_current_workspace_view,
)
from workflow.proof_state_compiler.profile_registry import (
    normalize_runtime_surface_profile_id,
)
from workflow.proof_tool.proof_tool_contract import (
    PROOF_TOOL_IDENTITY,
)


def _read_latest_view(memory: "NodeMemory | None") -> dict[str, Any]:
    if memory is None:
        return {}
    try:
        return json.loads(memory.latest_view.read_text(encoding="utf-8"))
    except Exception:
        return {}


def render_manager_followup(
    turn: ManagedTurn,
    turn_index: int,
    handled_intent: dict[str, Any] | None,
    memory: NodeMemory | None = None,
    full_view: dict[str, Any] | None = None,
    surface_profile: str | None = None,
) -> str:
    surface_profile = normalize_runtime_surface_profile_id(surface_profile)
    canonical_view = (
        require_current_workspace_view(
            turn.workspace_view,
            profile_id=surface_profile,
            label="managed current turn workspace view",
        )
        if isinstance(turn.workspace_view, dict)
        else {}
    )
    audit_view = (
        require_current_workspace_view(
            full_view,
            profile_id=surface_profile,
            label="managed current full workspace view",
        )
        if isinstance(full_view, dict) and full_view
        else None
    )
    health_event = (
        turn.health_event.to_dict()
        if getattr(turn, "health_event", None) is not None
        else {}
    )
    actions = _agent_safe_action_summaries(turn.manager_actions)
    result_payload = _drop_empty({
        "turn": turn_index,
        "handled_intent": handled_intent,
        "ok": bool(turn.ok),
        "repair_prompt": turn.repair_prompt,
        "health_event": health_event,
        "manager_actions": actions,
        "manager_observations": dict(turn.manager_observations),
        "view_refreshed": bool(canonical_view),
    })

    prior_view = _read_latest_view(memory)
    prior_surface = current_proof_surface_from_turn(
        prior_view.get("surface_turn") if isinstance(prior_view, dict) else {}
    )
    surface_turn = compose_current_surface_turn(
        canonical_view,
        surface_profile,
        base_surface=prior_surface,
        handled_intent=handled_intent,
        ok=bool(turn.ok),
        repair_prompt=turn.repair_prompt,
        manager_actions=turn.manager_actions,
        health_event=health_event,
        compiler_markdown=turn.compiler_markdown,
    )
    result_payload["surface_turn_hash"] = surface_turn.get("surface_turn_hash")
    target_view = (
        dict(audit_view)
        if isinstance(audit_view, dict)
        else dict(canonical_view)
    )
    target_view["surface_turn"] = surface_turn

    if memory is None:
        return render_current_surface_turn_markdown(
            surface_turn,
            submit_line=(
                "Submit exactly one proof intent for the next turn "
                f"(`{PROOF_TOOL_IDENTITY.tool}`: one `intent` + `payload`).\n"
            ),
        )

    submit_line = (
        "Submit exactly ONE proof intent via the "
        f"`{PROOF_TOOL_IDENTITY.tool}` MCP tool "
        "(only `intent` + `payload`; no node ids, hashes, request ids, or reasoning "
        "fields).\n\n"
    )
    anchor_block = (
        "The current goal above is your complete surface. "
        "The raw workspace JSON is the manager's audit file, not part of "
        "your surface — you do not need to open it.\n"
    )
    followup = render_current_surface_turn_markdown(
        surface_turn,
        submit_line=submit_line,
        anchor_block=anchor_block,
    )
    memory.write_latest_followup(
        turn_index=turn_index,
        result_payload=result_payload,
        workspace_view=target_view,
        followup_text=followup,
        committed_tactics=turn.committed_tactics,
    )
    return followup
