"""On-demand `inspect_context checkpoints` rewind menu.

The structural rewind menu was previously surfaced ONLY in the failure-recovery
focus (right after a rejected commit). An agent at a closed-candidate / admit-
discharge state that diagnosed an upstream cut/invariant as the blocker and
wanted to rewind to re-cut had no way to discover the checkpoint targets — the
`checkpoints` topic 404'd — so it gave up instead of rewinding (observed live).
This makes the structural checkpoints (each with a ready-to-submit
`undo_to_checkpoint` payload) requestable in ANY state, wherever
`undo_to_checkpoint` is an allowed intent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from tests.helpers.builders import make_manager  # noqa: E402
from workflow.proof_node_manager import ProofNodeManager  # noqa: E402
from workflow.proof_management.protocol_repair import parse_agent_intent  # noqa: E402
from workflow.surface_profiles import (  # noqa: E402
    effective_inspect_topics,
    resolve_surface_profile,
    surface_profile_allows_intent,
)


def _manager() -> ProofNodeManager:
    return make_manager(lemma_name="step4_badi")


PREFIX = ["proc.", "seq 6 6 : (inv).", "call (_: inv).", "wp.", "admit.", "skip."]


def test_checkpoints_topic_allowed_wherever_undo_is():
    """For L2/L3/L4 the `checkpoints` inspect topic accompanies undo_to_checkpoint (the
    agent reads the menu to get an id). L1 ALSO offers undo_to_checkpoint, but by INDEX
    off the proof_so_far panel — so it has the intent WITHOUT the checkpoints topic
    (L1 has no inspect channel at all)."""
    def _allows(prof: str, intent: str) -> bool:
        r = surface_profile_allows_intent(prof, intent)
        return r[0] if isinstance(r, tuple) else bool(r)

    for prof in ("l2_semantic_ir", "l3_flow_navigation",
                 "l4_preview_diagnostic", "l4_checked_action_surface"):
        assert _allows(prof, "undo_to_checkpoint"), prof
        topics = effective_inspect_topics(resolve_surface_profile(prof)) or frozenset()
        assert "checkpoints" in topics, f"{prof} offers undo but not checkpoints"
    # L1: undo_to_checkpoint offered (index-addressed, no menu) but NO checkpoints topic.
    assert _allows("l1_goal_projection", "undo_to_checkpoint")
    topics_l1 = effective_inspect_topics(
        resolve_surface_profile("l1_goal_projection")
    ) or frozenset()
    assert "checkpoints" not in topics_l1


def test_inspect_checkpoints_returns_menu_with_undo_payloads():
    m = _manager()
    m._current_committed_tactics = lambda: list(PREFIX)  # type: ignore[method-assign]
    intent = parse_agent_intent(
        '{"intent": "inspect_context", "payload": {"topic": "checkpoints"}}'
    ).intent
    turn = m._handle_inspect_checkpoints(intent)
    assert turn.ok is True
    menu = (turn.workspace_view or {}).get("checkpoint_menu") or {}
    items = menu.get("checkpoints") or []
    assert items, "expected at least one structural checkpoint"
    # every item carries a ready-to-submit undo_to_checkpoint payload
    for it in items:
        sub = it.get("submit") or {}
        assert sub.get("intent") == "undo_to_checkpoint"
        assert (sub.get("payload") or {}).get("checkpoint_id")
    assert "undo_to_checkpoint" in menu.get("note", "")


def test_surfaced_checkpoint_ids_pass_the_undo_handler_validation():
    """Menu<->action round-trip: every checkpoint_id the menu emits must satisfy
    the EXACT validation handle_undo_to_checkpoint applies (parse + digest match
    + index bounds), so the discovery menu and the rewind action agree on the id
    format. Locks the L2 invariant against future hash/format drift."""
    from workflow.proof_management.checkpoint_surface import (
        parse_checkpoint_id,
        structural_checkpoints_surface,
    )
    from workflow.proof_management.repl_session import history_hash

    tactics = list(PREFIX)
    digest16 = history_hash(tactics)[:16]
    items = structural_checkpoints_surface(tactics, replay_prefix_count=0)
    assert items
    for it in items:
        cid = (it.get("submit") or {}).get("payload", {}).get("checkpoint_id")
        parsed = parse_checkpoint_id(cid)
        assert parsed is not None, f"unparseable id {cid!r}"
        idx, dg = parsed
        assert dg == digest16, "menu digest != undo-handler digest (format drift)"
        assert 1 <= idx <= len(tactics)


def test_checkpoint_menu_is_rendered_only_by_surface_turn_control_menu():
    """Rewind choices are now a SurfaceTurnModel ControlMenu from a bare
    undo_to_checkpoint turn. A normal proof-state turn must not keep a parallel
    checkpoint-menu contract."""
    from workflow.proof_management.checkpoint_surface import (
        structural_checkpoints_surface,
    )
    from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown

    items = structural_checkpoints_surface(list(PREFIX), replay_prefix_count=0)
    assert items
    view = {
        "current_goal": {"lines": ["the current goal"]},
        "pure_tail_surface": {"goal_operators": ["x"]},
        "checkpoint_menu": {"checkpoints": items, "note": "rewind note"},
    }
    md = render_surface_turn_markdown(
        compose_surface_turn(view, "l4_checked_action_surface")
    )
    assert "Rewind targets" not in md

    menu_view = {
        "current_goal": {"lines": ["the current goal"]},
        "last_result": {
            "intent": "undo_to_checkpoint",
            "notice": "rewind note",
            "checkpoint_options": items,
        },
    }
    turn = compose_surface_turn(
        menu_view,
        "l4_checked_action_surface",
        base_view={"current_goal": {"lines": ["the current goal"]}},
        handled_intent={"intent": "undo_to_checkpoint", "payload": {}},
    )
    md_menu = render_surface_turn_markdown(turn)
    assert "Rewind targets" in md_menu
    assert "undo_to_checkpoint" in md_menu
    assert "checkpoint_id" in md_menu
    # a normal view WITHOUT a checkpoint_menu renders unchanged (no menu, no crash)
    md2 = render_surface_turn_markdown(
        compose_surface_turn(
            {"current_goal": {"lines": ["g"]}, "pure_tail_surface": {}},
            "l4_checked_action_surface",
        )
    )
    assert "Rewind targets" not in md2


def test_inspect_checkpoints_empty_history_is_ok_not_error():
    m = _manager()
    m._current_committed_tactics = lambda: []  # type: ignore[method-assign]
    intent = parse_agent_intent(
        '{"intent": "inspect_context", "payload": {"topic": "checkpoints"}}'
    ).intent
    turn = m._handle_inspect_checkpoints(intent)
    assert turn.ok is False
    menu = (turn.workspace_view or {}).get("checkpoint_menu") or {}
    assert menu.get("checkpoints") == []
