from __future__ import annotations

from workflow.proof_management.route_family import (
    infer_route_family,
    route_family_score_adjustment,
)


def test_route_family_detects_top_level_seq_route() -> None:
    family = infer_route_family(["byequiv=>//.", "proc.", "sp.", "seq 1 1 : P."])

    assert family.family == "top_level_seq_route"
    adjustment, reason = route_family_score_adjustment(family)
    assert adjustment > 0
    assert "top_level_seq_route" in reason


def test_route_family_uses_only_the_committed_tactic_spine() -> None:
    family = infer_route_family(["proc.", "wp."])

    assert family.family == "linear_prefix_route"


def test_route_family_detects_procedure_local_route() -> None:
    family = infer_route_family([
        "proc.",
        "inline*.",
        "inline*.",
        "wp.",
        "rcondt{1} 1.",
        "while{1} (true) (n-i).",
    ])

    assert family.family == "procedure_local_route"
    adjustment, _ = route_family_score_adjustment(family)
    assert adjustment < 0
