"""L4-only finish self-diagnosis nudge.

When an L4 agent submits `finish` while committed admits remain, the admit gate
pushes back ONCE with a structured 4-case self-diagnosis prompt, then honors
`finish` on insist (monotonic per-node counter). This nudge is L4-ONLY:

  * L1 (`l1_goal_projection`) has neither `checkpoints` nor `undo_to_checkpoint`,
    so it must keep the flat hard block — never the rewind-pointing 4-case prompt.
  * `qed` with admits stays a flat hard block on every profile (it is an invalid
    completion claim, not a give-up).

The `_give_up_gate` must not re-block a finish the admit gate already honored.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from tests.helpers.builders import intent, make_manager  # noqa: E402
from workflow.proof_node_manager import ProofNodeManager  # noqa: E402


def _manager(surface_profile: str) -> ProofNodeManager:
    m = make_manager(
        lemma_name="step4_badi",
        surface_profile=surface_profile,
    )
    # Stand in for history.ec carrying a replayed prefix with admits.
    m._current_committed_tactics = lambda: [  # type: ignore[method-assign]
        "proc.", "sp.", "admit.", "wp.", "admit.",
    ]
    return m


_intent = intent


# ---------------------------------------------------------------- L4 nudge ----

def test_l4_finish_with_admits_first_time_gets_4case_diagnose():
    m = _manager("l4_checked_action_surface")
    gate = m._committed_admit_gate(_intent("finish"))
    assert gate is not None and gate.ok is False
    p = gate.repair_prompt
    # The 4-case self-diagnosis, not the flat hard block.
    for tag in ("(a)", "(b)", "(c)", "(d)"):
        assert tag in p, f"missing case {tag}"
    assert "checkpoints" in p and "undo_to_checkpoint" in p  # rewind route in (a)
    assert m._finish_with_admit_count == 1


def test_l4_finish_with_admits_second_time_is_honored():
    m = _manager("l4_checked_action_surface")
    assert m._committed_admit_gate(_intent("finish")) is not None  # 1st: pushback
    # 2nd finish: the agent insisted -> honor (gate passes through).
    assert m._committed_admit_gate(_intent("finish")) is None
    assert m._finish_with_admit_count == 1  # not incremented past the threshold


def test_l4_qed_with_admits_stays_hard_blocked():
    m = _manager("l4_checked_action_surface")
    gate = m._committed_admit_gate(_intent("commit_tactic", "qed."))
    assert gate is not None and gate.ok is False
    assert "(a)" not in gate.repair_prompt  # flat block, not the 4-case nudge
    assert "un-discharged `admit.` tactic" in gate.repair_prompt
    assert getattr(m, "_finish_with_admit_count", 0) == 0  # qed never trips it


def test_l4_preview_profile_also_nudges():
    m = _manager("l4_preview_diagnostic")
    gate = m._committed_admit_gate(_intent("finish"))
    assert gate is not None and "(a)" in gate.repair_prompt


# ------------------------------------------------------------- L1 excluded ----

def test_l1_finish_with_admits_keeps_flat_hard_block():
    m = _manager("l1_goal_projection")
    gate = m._committed_admit_gate(_intent("finish"))
    assert gate is not None and gate.ok is False
    # L1 must NOT get the rewind-pointing 4-case prompt.
    assert "(a)" not in gate.repair_prompt
    assert "checkpoints" not in gate.repair_prompt
    assert "un-discharged `admit.` tactic" in gate.repair_prompt
    assert getattr(m, "_finish_with_admit_count", 0) == 0


def test_l1_finish_with_admits_never_honored_via_counter():
    """L1 stays hard-blocked no matter how many times finish is submitted."""
    m = _manager("l1_goal_projection")
    for _ in range(3):
        gate = m._committed_admit_gate(_intent("finish"))
        assert gate is not None  # still blocked; no counter escape on L1


# ---------------------------------------------- give-up gate non-interference -

def test_give_up_gate_does_not_reblock_honored_finish():
    m = _manager("l4_checked_action_surface")
    # latest_view stands in for an OPEN proof (what would trip _give_up_gate).
    m.latest_view = {"proof_status": {"status": "open", "remaining_goals": 2}}
    assert m._committed_admit_gate(_intent("finish")) is not None  # 1st pushback
    assert m._committed_admit_gate(_intent("finish")) is None       # honored
    # _give_up_gate must now pass through (the agent already self-diagnosed).
    assert m._give_up_gate(_intent("finish")) is None


def test_give_up_gate_unaffected_without_admits():
    """No committed admits -> counter stays 0 -> give-up gate behaves normally."""
    m = _manager("l4_checked_action_surface")
    m._current_committed_tactics = lambda: ["proc.", "sp.", "wp."]  # no admits
    m.latest_view = {"proof_status": {"status": "open", "remaining_goals": 1}}
    assert m._committed_admit_gate(_intent("finish")) is None  # no admits, no nudge
    # give-up gate still engages on a genuinely-open give-up.
    assert m._give_up_gate(_intent("finish")) is not None
