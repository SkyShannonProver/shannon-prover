"""Static hygiene tests for prover-facing compiler text."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation.prover_view_text_lint import (  # noqa: E402
    lint_prover_facing_payload,
)


def _codes(payload: dict, view_type: str = "agent_view") -> set[str]:
    return {
        issue.code
        for issue in lint_prover_facing_payload(payload, view_type=view_type)
    }


def test_lint_rejects_internal_disjoint_tag_leak() -> None:
    payload = {
        "guidance": {
            "recommendations": [{
                "id": "pivot",
                "action": "-where pr_bridge",
                "why": "Use [DISJOINT] later.",
                "confidence": "medium",
            }],
        },
    }

    assert "internal_analysis_tag_leak" in _codes(payload)


def test_lint_rejects_not_callable_without_repair() -> None:
    payload = {
        "guidance": {
            "recommendations": [{
                "id": "call.bad",
                "action": "call H0.",
                "action_type": "strategy_hint",
                "why": "H0 is not callable.",
                "confidence": "medium",
            }],
        },
    }

    codes = _codes(payload)

    assert "not_callable_without_reason_or_repair" in codes
    assert "negative_guidance_without_repair" in codes


def test_lint_accepts_balanced_frontier_guidance() -> None:
    payload = {
        "guidance": {
            "recommendations": [{
                "id": "call.h0",
                "action": "call H0.",
                "action_type": "strategy_hint",
                "why": (
                    "H0 is not callable at the current frontier because the "
                    "adversary call has not generated oracle obligations yet."
                ),
                "preconditions": [
                    "Use `call (_: <adversary invariant>).` first; then probe `call H0.` in the oracle subgoal.",
                ],
                "confidence": "medium",
                "metadata": {},
            }],
        },
    }

    assert _codes(payload) == set()


def test_lint_rejects_avoid_without_positive_route() -> None:
    payload = {
        "guidance": {
            "recommendations": [{
                "id": "try.no_progress",
                "action": "simplify.",
                "action_type": "avoid_action",
                "why": "Daemon probe predicted no progress.",
                "confidence": "high",
            }],
        },
    }

    assert "negative_guidance_without_repair" in _codes(payload)


def test_lint_rejects_conflicting_same_action_guidance() -> None:
    payload = {
        "guidance": {
            "recommendations": [{
                "id": "try.commit",
                "action": "inline *.",
                "action_type": "probe_tactic",
                "why": "Probe this tactic.",
                "confidence": "medium",
            }, {
                "id": "proof_ir.avoid",
                "action": "inline *.",
                "action_type": "avoid_action",
                "why": "Avoid at this phase because live handles remain; use a named call first.",
                "confidence": "medium",
            }],
        },
    }

    assert "conflicting_guidance_for_same_action" in _codes(payload)


def test_lint_requires_phase_prefer_when_phase_avoid_exists() -> None:
    payload = {
        "proof_ir": {
            "phase": {
                "name": "call_site",
                "prefer": [],
                "avoid": ["inline * before live handles"],
            },
        },
    }

    assert "phase_avoid_without_positive_prefer" in _codes(payload)




def main() -> int:
    test_lint_rejects_internal_disjoint_tag_leak()
    test_lint_rejects_not_callable_without_repair()
    test_lint_accepts_balanced_frontier_guidance()
    test_lint_rejects_avoid_without_positive_route()
    test_lint_rejects_conflicting_same_action_guidance()
    test_lint_requires_phase_prefer_when_phase_avoid_exists()
    test_plain_text_lint_rejects_internal_tag()
    print("PASS test_prover_view_text_lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
