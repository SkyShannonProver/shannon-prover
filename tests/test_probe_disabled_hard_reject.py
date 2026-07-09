"""No-probe agent surface must be authoritative, not menu-only.

`probe_disabled()` removes probe from the offered intent menu/schema, but a model
may still submit `probe_tactic` from habit or stale context. Before this gate the
manager ran the probe anyway, so a no-probe run could silently become probe-ON.
The manager must HARD-REJECT a submitted probe when the lever is unavailable —
without executing it — and tell the agent to commit directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import workflow.surface_profiles as sp  # noqa: E402
from tests.helpers.builders import make_manager  # noqa: E402
from workflow.proof_node_manager import ProofNodeManager  # noqa: E402
from workflow.proof_management.protocol_repair import parse_agent_intent  # noqa: E402


def _manager() -> ProofNodeManager:
    return make_manager(lemma_name="step4_badi")


def _probe_intent(name: str = "probe_tactic"):
    if name == "probe_tactic":
        raw = '{"intent": "probe_tactic", "payload": {"tactic": "auto."}}'
    else:
        raw = '{"intent": "probe_replay_suffix_chunk", "payload": {}}'
    return parse_agent_intent(raw).intent


def test_probe_rejected_without_running_when_disabled(monkeypatch):
    monkeypatch.delenv("SHANNON_ENABLE_PROBE", raising=False)
    monkeypatch.delenv("SHANNON_DISABLE_PROBE", raising=False)
    assert sp.probe_disabled() is True
    m = _manager()
    # the gate must fire and NOT reach the repl (no EC session needed)
    turn = m._probe_disabled_gate(_probe_intent("probe_tactic"))
    assert turn is not None, "probe must be hard-rejected when disabled"
    assert turn.ok is False
    assert "not an available proof intent" in (turn.repair_prompt or "").lower()
    assert "commit_tactic" in (turn.repair_prompt or "")
    labels = [a.get("label") for a in (turn.manager_actions or [])]
    assert "probe_disabled_reject" in labels
    # also covers the replay-chunk probe variant
    assert m._probe_disabled_gate(_probe_intent("probe_replay_suffix_chunk")) is not None


def test_probe_gate_is_noop_when_enabled(monkeypatch):
    monkeypatch.setenv("SHANNON_ENABLE_PROBE", "1")
    monkeypatch.delenv("SHANNON_DISABLE_PROBE", raising=False)
    assert sp.probe_disabled() is False
    m = _manager()
    # gate must NOT fire when probe is on — probe proceeds normally
    assert m._probe_disabled_gate(_probe_intent("probe_tactic")) is None


def test_non_probe_intents_never_gated(monkeypatch):
    monkeypatch.delenv("SHANNON_ENABLE_PROBE", raising=False)
    monkeypatch.delenv("SHANNON_DISABLE_PROBE", raising=False)
    m = _manager()
    for raw in (
        '{"intent": "commit_tactic", "payload": {"tactic": "auto."}}',
        '{"intent": "undo_last_step", "payload": {}}',
        '{"intent": "inspect_context", "payload": {"topic": "goal_info"}}',
    ):
        intent = parse_agent_intent(raw).intent
        assert m._probe_disabled_gate(intent) is None, raw
