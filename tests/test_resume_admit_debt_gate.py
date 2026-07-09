"""Task #1: committed-admit gate must survive resume.

The gate reads admits straight from the committed proof (`history.ec`), the
resume-surviving source of truth, so it blocks on resume and clears once a
rewind drops the admit.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from tests.helpers.builders import intent, make_manager  # noqa: E402
from workflow.proof_node_manager import ProofNodeManager  # noqa: E402


def _manager() -> ProofNodeManager:
    return make_manager(lemma_name="step4_badi")


_intent = intent


def test_resumed_node_is_gated_by_committed_admits():
    m = _manager()

    # Stand in for history.ec carrying the replayed prefix with admits.
    m._current_committed_tactics = lambda: [  # type: ignore[method-assign]
        "proc.", "sp.", "admit.", "wp.", "admit.", "skip.",
    ]

    for intent in (_intent("finish"), _intent("commit_tactic", "qed.")):
        gate = m._committed_admit_gate(intent)
        assert gate is not None, f"{intent.intent} must be gated on resume"
        assert gate.ok is False
        assert "2 un-discharged `admit.` tactic" in gate.repair_prompt


def test_gate_clears_after_rewind_drops_admit_from_history():
    """A rewind truncates history.ec; once no admit remains the gate passes."""
    m = _manager()
    m._current_committed_tactics = lambda: ["proc.", "sp.", "wp.", "skip."]
    assert m._committed_admit_gate(_intent("finish")) is None
    assert m._committed_admit_gate(_intent("commit_tactic", "qed.")) is None


def test_non_finish_qed_intents_are_never_gated():
    m = _manager()
    m._current_committed_tactics = lambda: ["admit.", "admit."]
    assert m._committed_admit_gate(_intent("commit_tactic", "sp.")) is None
    assert m._committed_admit_gate(_intent("inspect_context")) is None
    assert m._committed_admit_gate(_intent("undo_last_step")) is None


def test_committed_admit_labels_carry_step_and_tactic():
    m = _manager()
    m._current_committed_tactics = lambda: ["proc.", "admit.", "wp."]
    admits = m._committed_admits()
    assert len(admits) == 1
    assert "step 2" in admits[0]
    assert "admit." in admits[0]
