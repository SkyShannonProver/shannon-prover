from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from workflow.proof_management.checkpoint_store import ProofCheckpointManager
from workflow.proof_management.protocol_repair import AgentIntent
from workflow.proof_management.recovery_handlers import ProofRecoveryIntentHandler

# Agent-facing observations must never mention any resume/floor/prefix concept.
_RESUME_LEAK_RE = re.compile(
    r"crosses_resume_floor|resume_start|resume_local|resume handoff|"
    r"verified.*prefix|resume floor|resume boundary",
    re.IGNORECASE,
)


def _history_hash(tactics: list[str]) -> str:
    return hashlib.sha1("\n".join(tactics).encode("utf-8")).hexdigest()


def _confirmation_id(*parts: object) -> str:
    return hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


class _FakeRepl:
    def __init__(self) -> None:
        self.state_version = 7
        self.fresh_started = False
        self.rewound_before: int | None = None
        self.restored_tactics: list[str] = []
        self.amended_prefix: list[str] = []

    def fresh_restart(self) -> tuple[str, list[dict[str, Any]]]:
        self.fresh_started = True
        return "snapshot", [{"label": "fresh_restart", "exit_code": 0}]

    def rewind_before_tactic(self, tactic_index: int) -> tuple[str, list[dict[str, Any]]]:
        self.rewound_before = tactic_index
        return "snapshot", [{"label": "undo_to_checkpoint", "exit_code": 0}]

    def restore_committed_tactics(
        self,
        tactics: list[str],
        label: str = "restore_committed_tactics",
    ) -> tuple[str, list[dict[str, Any]]]:
        self.restored_tactics = list(tactics)
        return "snapshot", [{"label": label, "exit_code": 0}]

    def restart_with_edited_prefix(
        self,
        edited_tactics: list[str],
        label: str = "restart_replay_edit",
    ) -> tuple[str, list[dict[str, Any]]]:
        self.amended_prefix = list(edited_tactics)
        return "snapshot", [{"label": label, "exit_code": 0}]

def _handler(
    tmp_path: Path,
    *,
    tactics: list[str],
    replay_prefix_count: int = 0,
) -> tuple[
    ProofRecoveryIntentHandler,
    ProofCheckpointManager,
    _FakeRepl,
]:
    checkpoints = ProofCheckpointManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    repl = _FakeRepl()
    replay_prefix = {"cleared": False}
    handler = ProofRecoveryIntentHandler(
        node_id="Tree-unit",
        checkpoints=checkpoints,
        repl=repl,
        committed_tactics=lambda: list(tactics),
        replay_prefix_count=lambda: replay_prefix_count,
        resumed_lineage=lambda: replay_prefix_count > 0,
        clear_replay_prefix=lambda: replay_prefix.update({"cleared": True}),
    )
    return handler, checkpoints, repl


def _handler_with_prefix_flag(
    tmp_path: Path,
    *,
    tactics: list[str],
    replay_prefix_count: int,
) -> tuple[ProofRecoveryIntentHandler, _FakeRepl, dict[str, Any]]:
    checkpoints = ProofCheckpointManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    repl = _FakeRepl()
    replay_prefix = {"cleared": False}
    handler = ProofRecoveryIntentHandler(
        node_id="Tree-unit",
        checkpoints=checkpoints,
        repl=repl,
        committed_tactics=lambda: list(tactics),
        replay_prefix_count=lambda: replay_prefix_count,
        resumed_lineage=lambda: replay_prefix_count > 0,
        clear_replay_prefix=lambda: replay_prefix.update({"cleared": True}),
    )
    return handler, repl, replay_prefix


def test_rewind_into_replayed_prefix_clears_prefix_transparently(
    tmp_path: Path,
) -> None:
    # Resumed node: prefix is tactics 1..4; the upstream call at idx 2 is the
    # blocker.  Rewinding before idx 2 lands inside the replayed prefix, so the
    # internal replay-prefix protection must be lifted (clear callback fires).
    # This is fully transparent to the agent: its observation carries NO resume
    # flag; only the INTERNAL audit note (audit_extra, debug-only) records it.
    tactics = ["proc.", "call (_: inv).", "wp.", "auto.", "seq 1: (m).", "sp."]
    handler, repl, replay_prefix = _handler_with_prefix_flag(
        tmp_path, tactics=tactics, replay_prefix_count=4,
    )
    checkpoint_id = next(
        item["checkpoint_id"]
        for item in handler.checkpoints.menu_options(
            tactics, replay_prefix_count=4
        )
        if item["checkpoint_id"].startswith("cp_2_")
    )

    plan = handler.handle_undo_to_checkpoint(
        AgentIntent(
            intent="undo_to_checkpoint",
            payload={"checkpoint_id": checkpoint_id},
        ),
    )

    assert plan.kind == "repl_call"
    # Internal audit note (debug, never shown to the agent) may record it.
    assert plan.audit_extra["checkpoint"]["crosses_resume_floor"] is True
    assert plan.audit_extra["checkpoint"]["prior_replay_prefix_count"] == 4
    # Agent-facing observation carries NO resume/floor/prefix concept.
    assert "crosses_resume_floor" not in plan.observation
    assert not _RESUME_LEAK_RE.search(json.dumps(plan.observation)), plan.observation
    # The prefix is only cleared once the rewind actually executes.
    assert replay_prefix["cleared"] is False
    assert plan.call is not None
    plan.call()
    assert repl.rewound_before == 2
    # Internal protection lifted so the run continues correctly.
    assert replay_prefix["cleared"] is True


def test_rewind_above_prefix_does_not_clear_prefix(tmp_path: Path) -> None:
    # Rewinding to a checkpoint ABOVE the replayed prefix (post-resume work) must
    # NOT lift the internal protection: the prefix stays intact and is not
    # cleared. No resume framing leaks either way.
    tactics = ["proc.", "call (_: inv).", "wp.", "auto.", "seq 1: (m).", "sp."]
    handler, repl, replay_prefix = _handler_with_prefix_flag(
        tmp_path, tactics=tactics, replay_prefix_count=4,
    )
    checkpoint_id = next(
        item["checkpoint_id"]
        for item in handler.checkpoints.menu_options(
            tactics, replay_prefix_count=4
        )
        if item["checkpoint_id"].startswith("cp_6_")
    )

    plan = handler.handle_undo_to_checkpoint(
        AgentIntent(
            intent="undo_to_checkpoint",
            payload={"checkpoint_id": checkpoint_id},
        ),
    )

    assert "crosses_resume_floor" not in plan.audit_extra["checkpoint"]
    assert "crosses_resume_floor" not in plan.observation
    assert not _RESUME_LEAK_RE.search(json.dumps(plan.observation)), plan.observation
    assert plan.call is not None
    plan.call()
    assert repl.rewound_before == 6
    assert replay_prefix["cleared"] is False


def test_recovery_handler_builds_checkpoint_selection_plan(tmp_path: Path) -> None:
    handler, _, _ = _handler(tmp_path, tactics=["proc.", "wp."])

    plan = handler.checkpoint_selection_plan(
        AgentIntent(intent="undo_to_checkpoint", payload={}),
    )

    assert plan.kind == "menu"
    assert plan.label == "checkpoint_selection"
    assert plan.audit_kind == "checkpoint_selection.requested"
    assert plan.observation["kind"] == "checkpoint_selection"
    assert plan.observation["control_menu"]["items"][0]["submit"]["intent"] == (
        "undo_to_checkpoint"
    )


def test_recovery_handler_rewinds_checkpoint_and_saves_restore_anchor(
    tmp_path: Path,
) -> None:
    tactics = ["proc.", "wp.", "auto."]
    handler, checkpoints, repl = _handler(tmp_path, tactics=tactics)
    checkpoint = next(
        item for item in checkpoints.menu_options(tactics)
        if item["checkpoint_id"].startswith("cp_2_")
    )

    plan = handler.handle_undo_to_checkpoint(
        AgentIntent(
            intent="undo_to_checkpoint",
            payload={"checkpoint_id": checkpoint["checkpoint_id"]},
        ),
    )

    assert plan.kind == "repl_call"
    assert plan.observation["kind"] == "checkpoint_rewind"
    assert plan.audit_extra["proof_state_operation"] == "rewind_before_checkpoint"
    assert checkpoints.pre_rewind_restore_anchor["from_checkpoint_id"] == (
        checkpoint["checkpoint_id"]
    )

    assert plan.call is not None
    snapshot, actions = plan.call()
    assert snapshot == "snapshot"
    assert actions[0]["label"] == "undo_to_checkpoint"
    assert repl.rewound_before == 2


def test_recovery_handler_confirms_fresh_restart_as_recovery_plan(
    tmp_path: Path,
) -> None:
    handler, checkpoints, repl = _handler(tmp_path, tactics=["proc."])

    menu = handler.handle_fresh_restart(
        AgentIntent(intent="fresh_restart", payload={}),
    )
    assert menu.kind == "menu"
    assert menu.label == "fresh_restart_confirmation"
    token = checkpoints.fresh_restart_confirmation_id

    plan = handler.handle_fresh_restart(
        AgentIntent(
            intent="fresh_restart",
            payload={"confirm": True, "confirmation_id": token},
        ),
    )

    assert plan.kind == "repl_call"
    assert plan.observation["kind"] == "fresh_restart_confirmed"
    assert plan.audit_extra["proof_state_operation"] == "fresh_restart_confirmed"
    assert plan.call is not None
    snapshot, actions = plan.call()
    assert snapshot == "snapshot"
    assert actions[0]["label"] == "fresh_restart"
    assert repl.fresh_started


# ── amend_and_replay: edit one committed step, replay the rest ────────────────

def test_amend_and_replay_edits_step_and_replays(tmp_path: Path) -> None:
    handler, _checkpoints, repl = _handler(
        tmp_path,
        tactics=["byequiv (_: ={glob A}).", "proc.", "auto.", "smt()."],
    )
    plan = handler.handle_amend_and_replay(
        AgentIntent(
            intent="amend_and_replay",
            payload={"index": 1, "tactic": "byequiv (_: ={glob A, arg})."},
        )
    )
    assert plan.kind == "repl_call"
    assert plan.call is not None
    snapshot, _actions = plan.call()
    assert snapshot == "snapshot"
    # step 1 replaced; steps 2-4 kept verbatim for replay
    assert repl.amended_prefix == [
        "byequiv (_: ={glob A, arg}).", "proc.", "auto.", "smt()."]
    assert plan.observation["amended_step"] == 1
    assert plan.observation["original_tactic"] == "byequiv (_: ={glob A})."
    assert plan.audit_extra["proof_state_operation"] == "amend_and_replay"
    assert "proof_state_effect" not in plan.audit_extra
    # never leaks resume/prefix internals
    assert not _RESUME_LEAK_RE.search(json.dumps(plan.observation))


def test_amend_and_replay_edits_middle_step(tmp_path: Path) -> None:
    handler, _c, repl = _handler(tmp_path, tactics=["a.", "b.", "c.", "d."])
    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={"index": 3, "tactic": "C2."})
    )
    plan.call()
    assert repl.amended_prefix == ["a.", "b.", "C2.", "d."]


def test_amend_and_replay_empty_payload_returns_typed_step_menu(tmp_path: Path) -> None:
    handler, _c, repl = _handler(tmp_path, tactics=["a.", "b."])

    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={})
    )

    assert plan.kind == "menu"
    assert plan.label == "amend_selection"
    menu = plan.observation["control_menu"]
    assert menu["title"] == "Amend & replay"
    assert [item["submit"] for item in menu["items"]] == [
        {
            "intent": "amend_and_replay",
            "payload": {"index": 1},
        },
        {
            "intent": "amend_and_replay",
            "payload": {"index": 2},
        },
    ]
    assert menu["items"][0]["requires_input"] == ["tactic"]
    assert repl.amended_prefix == []


def test_amend_and_replay_rejects_placeholder_without_mutating_state(
    tmp_path: Path,
) -> None:
    handler, _c, repl = _handler(tmp_path, tactics=["a.", "b."])

    plan = handler.handle_amend_and_replay(
        AgentIntent(
            intent="amend_and_replay",
            payload={"index": 1, "tactic": "<replacement tactic>"},
        )
    )

    assert plan.kind == "menu"
    assert "concrete replacement" in plan.observation["control_menu"]["notice"]
    assert repl.amended_prefix == []


def test_amend_and_replay_rejects_unchanged_tactic_without_replay(
    tmp_path: Path,
) -> None:
    handler, _c, repl = _handler(tmp_path, tactics=["a.", "b."])

    plan = handler.handle_amend_and_replay(
        AgentIntent(
            intent="amend_and_replay",
            payload={"index": 1, "tactic": "a."},
        )
    )

    assert plan.kind == "menu"
    assert "must differ" in plan.observation["control_menu"]["notice"]
    assert repl.amended_prefix == []


def test_amend_and_replay_rejects_out_of_range_index(tmp_path: Path) -> None:
    handler, _c, repl = _handler(tmp_path, tactics=["a.", "b."])
    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={"index": 9, "tactic": "x."})
    )
    assert plan.kind == "menu"
    assert plan.label == "amend_selection"
    assert all(
        item["submit"]["intent"] == "amend_and_replay"
        for item in plan.observation["control_menu"]["items"]
    )
    assert repl.amended_prefix == []


def test_amend_and_replay_requires_a_corrected_tactic(tmp_path: Path) -> None:
    handler, _c, repl = _handler(tmp_path, tactics=["a.", "b."])
    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={"index": 1})
    )
    assert plan.kind == "menu"
    assert plan.label == "amend_selection"
    assert repl.amended_prefix == []


def test_amend_and_replay_disabled_on_resumed_node(tmp_path: Path) -> None:
    # a resumed node (replay_prefix_count>0) must NOT amend (mirror fresh_restart)
    handler, _c, repl = _handler(
        tmp_path, tactics=["a.", "b."], replay_prefix_count=2)
    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={"index": 1, "tactic": "x."})
    )
    assert plan.kind == "menu"
    assert plan.label == "amend_selection"
    assert plan.observation["control_menu"]["items"] == []
    assert "resumed node" in plan.observation["control_menu"]["notice"]
    assert repl.amended_prefix == []


def _resumable_handler(
    tmp_path: Path,
    *,
    tactics: list[str],
    replay_prefix_count: int,
    resumed_lineage: bool,
) -> tuple[ProofRecoveryIntentHandler, _FakeRepl, dict[str, Any]]:
    """Handler whose resume FLOOR (count) is mutable and whose resume LINEAGE
    flag is durable — mirrors the manager wiring so a rewind-below-floor can
    clear the count without lifting the lineage marker."""
    checkpoints = ProofCheckpointManager(
        node_id="Tree-unit",
        run_dir=tmp_path,
        history_hash=_history_hash,
        confirmation_id=_confirmation_id,
    )
    repl = _FakeRepl()
    state = {"count": replay_prefix_count, "resumed": resumed_lineage}

    def _clear() -> None:
        # Real clear_replay_prefix semantics: drop the transient floor, KEEP
        # the durable lineage marker.
        state["count"] = 0

    handler = ProofRecoveryIntentHandler(
        node_id="Tree-unit",
        checkpoints=checkpoints,
        repl=repl,
        committed_tactics=lambda: list(tactics),
        replay_prefix_count=lambda: state["count"],
        resumed_lineage=lambda: state["resumed"],
        clear_replay_prefix=_clear,
    )
    return handler, repl, state


def test_amend_disabled_when_resume_floor_cleared_but_lineage_durable(
    tmp_path: Path,
) -> None:
    # Regression (CBC_upto Tree-0.0.r2, 2026-06-25): a resumed node whose resume
    # FLOOR has been cleared by a rewind-below-floor must STILL refuse amend —
    # the durable lineage marker, not the transient count, gates it.
    handler, repl, state = _resumable_handler(
        tmp_path,
        tactics=["a.", "b.", "c."],
        replay_prefix_count=0,  # floor already cleared by an earlier rewind
        resumed_lineage=True,   # but the node is still resumed lineage
    )
    assert state["count"] == 0
    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={"index": 1, "tactic": "x."})
    )
    assert plan.kind != "repl_call"
    assert repl.amended_prefix == []


def test_rewind_into_prefix_then_amend_stays_disabled(tmp_path: Path) -> None:
    # End-to-end of the defeated guard: resumed node (floor=4), the agent rewinds
    # BELOW the floor (clearing the count), then tries amend. Pre-fix the cleared
    # count re-enabled amend; the durable lineage marker keeps it forbidden.
    tactics = ["proc.", "call (_: inv).", "wp.", "auto.", "seq 1: (m).", "sp."]
    handler, repl, state = _resumable_handler(
        tmp_path, tactics=tactics, replay_prefix_count=4, resumed_lineage=True,
    )
    checkpoint_id = next(
        item["checkpoint_id"]
        for item in handler.checkpoints.menu_options(tactics, replay_prefix_count=4)
        if item["checkpoint_id"].startswith("cp_2_")
    )

    rewind = handler.handle_undo_to_checkpoint(
        AgentIntent(
            intent="undo_to_checkpoint",
            payload={"checkpoint_id": checkpoint_id},
        ),
    )
    assert rewind.call is not None
    rewind.call()                       # crosses the resume floor -> clears count
    assert state["count"] == 0          # transient floor gone
    assert state["resumed"] is True     # durable lineage marker survives

    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={"index": 1, "tactic": "x."})
    )
    assert plan.kind != "repl_call"     # still routed to the rewind menu
    assert repl.amended_prefix == []    # nothing amended/replayed


def test_amend_allowed_on_genuine_from_scratch_node(tmp_path: Path) -> None:
    # Guard rails: a non-resumed root (no lineage, no floor) keeps amend.
    handler, repl, _state = _resumable_handler(
        tmp_path, tactics=["a.", "b.", "c."],
        replay_prefix_count=0, resumed_lineage=False,
    )
    plan = handler.handle_amend_and_replay(
        AgentIntent(intent="amend_and_replay", payload={"index": 2, "tactic": "B2."})
    )
    assert plan.kind == "repl_call"
    plan.call()
    assert repl.amended_prefix == ["a.", "B2.", "c."]
