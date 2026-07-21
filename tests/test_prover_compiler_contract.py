#!/usr/bin/env python3
"""The managed-prover handoff must state the compiler/agent contract + trust
boundary: what the compiler mechanically provides, that "applies" is not a
correctness claim, and that backtrack-and-adjust on an invariant is sanctioned.

Eval-safe: the contract is generic (no benchmark identifiers).

Run: python3 -m pytest tests/test_prover_compiler_contract.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.agents.prover_prompt import _render_managed_session_handoff  # noqa: E402
from workflow.agent_prompt_render import render_long_lived_agent_prompt  # noqa: E402


def _handoff() -> str:
    return _render_managed_session_handoff(
        "", {"workspace_view": {"current_goal": {"lines": ["pr A = pr B"]}}})


def _full_prompt() -> str:
    # The runtime wrapper carries the interpret/play contract; the static handoff
    # carries the compiler resources. The agent sees the two combined.
    return render_long_lived_agent_prompt(
        _handoff(), host="h", port=1, token="t",
        node_memory_dir=Path("/tmp/nm"), max_turns=10,
        surface_profile="l4_checked_action_surface")


def test_handoff_describes_what_the_compiler_provides() -> None:
    # The static handoff carries the same typed proof surface used on live
    # turns. State-dependent context actions are composed at runtime instead
    # of being advertised as a fixed prompt menu.
    out = _handoff()
    assert "### Initial proof surface" in out
    assert "raw workspace JSON is audit-only" in out
    assert "lemma_index" not in out


def test_handoff_states_the_trust_boundary() -> None:
    out = _full_prompt()
    assert "current authoritative proof surface rendered" in out
    assert "from `SurfaceTurnModel`" in out
    assert "raw full workspace JSON is an audit/replay artifact" in out


def test_handoff_contract_is_eval_safe() -> None:
    out = _handoff()
    for bad in ("ChaChaPoly", "inv_cpa", "poly_mac1", "I_stateless", "UFCMA"):
        assert bad not in out, f"benchmark identifier {bad!r} leaked into the contract"
