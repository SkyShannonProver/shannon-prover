"""Tests for Pr obligation planning."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_pr_obligations import (  # noqa: E402
    build_pr_normal_form,
    build_pr_obligation_plan,
    native_ast_pr_arithmetic_shape,
)
from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # noqa: E402


def test_pr_normal_form_classifies_union_bound_without_congr_tactic() -> None:
    normal = build_pr_normal_form(
        {"prob_form": "ineq"},
        "probability",
        "Pr[G.main() @ &m : res] <= Pr[H.main() @ &m : res] + eps",
    )

    assert normal["available"] is True
    assert normal["normalization_kind"] == "union_bound_or_additive_inequality"
    assert normal["recommended_tactic"] == ""


def test_pr_obligation_plan_prefers_arithmetic_chain_when_present() -> None:
    plan = build_pr_obligation_plan(
        parsed={"goal_type": "probability", "prob_form": "adv_ineq"},
        goal_type="probability",
        goal_text=(
            "`|Pr[G0.main() @ &m : res] - Pr[G1.main() @ &m : res]| <= "
            "Pr[BAD.main() @ &m : bad] + eps"
        ),
        pr_path_plan={
            "arithmetic_plan": {
                "available": True,
                "shape": "absolute_pr_difference_bound",
                "recommended_chain": ["reduction", "bad_bound"],
            },
        },
        semantic_pr_bound_candidates=[{"lemma": "bad_bound", "score": 8}],
        native_ast_search={
            "suggested_queries": [{"query": "mu predU"}],
        },
    )

    assert plan["available"] is True
    assert plan["primary_strategy"] == "use_pr_arithmetic_chain"
    assert [item["kind"] for item in plan["obligations"]][:2] == [
        "pr_union_bound_plan",
        "pr_arithmetic_chain",
    ]
    assert plan["summary"]["has_semantic_bound_lookup"] is True


def test_native_ast_pr_arithmetic_shape_classifies_additive_inequality() -> None:
    assert native_ast_pr_arithmetic_shape(
        {"prob_form": "ineq"},
        "probability",
        "Pr[G.main() @ &m : res] <= Pr[H.main() @ &m : res] + eps",
    ) == "additive_pr_inequality"


def test_native_ast_pr_arithmetic_shape_keeps_single_pr_inequality() -> None:
    assert native_ast_pr_arithmetic_shape(
        {"prob_form": "ineq"},
        "probability",
        "Pr[G.main() @ &m : bad] <= eps",
    ) == "probability_inequality"


def test_proof_ir_exposes_pr_obligation_plan_resource() -> None:
    goal = "Pr[G.main() @ &m : res] <= Pr[H.main() @ &m : res] + eps"
    ir = build_proof_ir(
        proof_state={},
        current_goal={
            "goal_type": "probability",
            "active_goal_preview": goal,
            "parsed_goal": {
                "goal_type": "probability",
                "prob_form": "ineq",
                "raw_text": goal,
            },
        },
    )

    plan = ir["resources"]["handles"]["pr_obligation_plan"]
    assert plan["available"] is True
    assert plan["primary_strategy"] == "decompose_pr_union_bound"
    assert ir["phase"]["resource_summary"]["has_pr_obligation_plan"] is True
