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
    # The static handoff no longer inlines a fixed compiler-topic menu
    # (CLAUDE.md: intent/topic menus are runtime-generated). It carries the
    # rendered view surface plus a runtime-generated request menu with
    # copyable submit shapes; the compiler-resource description (verified
    # facts such as `pr_bridge_routes` / the call-invariant skeleton) lives
    # in the runtime wrapper the agent sees combined with the handoff.
    out = _handoff()
    assert "### Initial ProverWorkspaceView" in out
    assert 'submit `{"intent"' in out, (
        "handoff lost the runtime-generated request menu (no copyable "
        "submit shape)"
    )
    assert "lemma_index" not in out
    full = _full_prompt()
    for topic in ("pr_bridge_routes", "call_invariant_skeleton"):
        assert topic in full, (
            f"compiler help `{topic}` not described anywhere on the combined "
            "agent surface (handoff + runtime wrapper)"
        )


def test_handoff_states_the_trust_boundary() -> None:
    out = _full_prompt()
    # The manager result is a static-analysis fact, not a verdict.
    assert "STATIC-ANALYSIS FACT" in out
    # "accepted on the current goal" is only a type-check, not a claim that it
    # closes the proof or is the correct invariant.
    assert "accepted ON THE CURRENT GOAL" in out
    assert "is the best route" in out
    assert "is the correct" in out
    # backtrack-and-adjust is sanctioned: committing and undoing are normal play.
    assert "COMMIT and UNDO freely" in out


def test_handoff_contract_is_eval_safe() -> None:
    out = _handoff()
    for bad in ("ChaChaPoly", "inv_cpa", "poly_mac1", "I_stateless", "UFCMA"):
        assert bad not in out, f"benchmark identifier {bad!r} leaked into the contract"
