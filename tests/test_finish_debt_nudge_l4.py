"""Uniform finish/qed safety while committed admits remain.

The first compiler-information A/B has one profile-independent completion
gate.  L4 no longer gets a finish nudge or a second-submission escape hatch;
that behavioral treatment would confound the information-only comparison.
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


# --------------------------------------------------------- uniform hard gate ----

def test_l4_finish_with_admits_gets_flat_hard_block():
    m = _manager("l4_proof_state_compiler_v2_operation_binding_repair")
    gate = m._committed_admit_gate(_intent("finish"))
    assert gate is not None and gate.ok is False
    p = gate.repair_prompt
    assert "(a)" not in p
    assert "checkpoints" not in p
    assert "un-discharged `admit.` tactic" in p
    assert getattr(m, "_finish_with_admit_count", 0) == 0


def test_l4_finish_with_admits_never_escapes_on_repetition():
    m = _manager("l4_proof_state_compiler_v2_operation_binding_repair")
    for _ in range(3):
        gate = m._committed_admit_gate(_intent("finish"))
        assert gate is not None and gate.ok is False


def test_l4_qed_with_admits_stays_hard_blocked():
    m = _manager("l4_proof_state_compiler_v2_operation_binding_repair")
    gate = m._committed_admit_gate(_intent("commit_tactic", "qed."))
    assert gate is not None and gate.ok is False
    assert "(a)" not in gate.repair_prompt  # flat block, not the 4-case nudge
    assert "un-discharged `admit.` tactic" in gate.repair_prompt
    assert getattr(m, "_finish_with_admit_count", 0) == 0  # qed never trips it


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

def test_admit_gate_precedes_open_proof_give_up_gate():
    m = _manager("l4_proof_state_compiler_v2_operation_binding_repair")
    # The hard admit gate owns this invalid completion attempt before the
    # ordinary open-proof give-up policy is relevant.
    m.latest_view = {"proof_status": {"status": "open", "remaining_goals": 2}}
    for _ in range(3):
        assert m._committed_admit_gate(_intent("finish")) is not None


def test_give_up_gate_unaffected_without_admits():
    """No committed admits -> counter stays 0 -> give-up gate behaves normally."""
    m = _manager("l4_proof_state_compiler_v2_operation_binding_repair")
    m._current_committed_tactics = lambda: ["proc.", "sp.", "wp."]  # no admits
    m.latest_view = {"proof_status": {"status": "open", "remaining_goals": 1}}
    assert m._committed_admit_gate(_intent("finish")) is None  # no admits, no nudge
    # give-up gate still engages on a genuinely-open give-up.
    assert m._give_up_gate(_intent("finish")) is not None
