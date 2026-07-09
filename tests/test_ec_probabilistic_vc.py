"""Tests for probabilistic VC/loss-accounting classification."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_probabilistic_vc import (  # noqa: E402
    PROBABILISTIC_VC_KIND,
    build_probabilistic_vc_frontend,
    probabilistic_vc_event_terms,
)


def test_pr_loss_accounting_classifies_bad_event_bound() -> None:
    goal = (
        "`| Pr[G0.main() @ &m : res] - Pr[G1.main() @ &m : res] | <= "
        "Pr[BadGame.main() @ &m : BadGame.bad] + eps"
    )

    frontend = build_probabilistic_vc_frontend(
        parsed={"goal_type": "probability", "prob_form": "adv_diff_ineq"},
        goal_type="probability",
        program_ir={},
        goal_text=goal,
        procedure_frontend={},
    )

    assert PROBABILISTIC_VC_KIND == "easycrypt_probabilistic_vc_frontend"
    assert frontend["available"] is True
    kinds = {item["kind"] for item in frontend["obligations"]}
    assert "pr_loss_accounting" in kinds
    assert "bad_event_reduction" in kinds
    assert frontend["strategy"] == "bad-event reduction"
    assert "have-chain" in frontend["expected_rule_families"]


def test_loop_bad_event_bound_uses_procedure_frontend_signals() -> None:
    frontend = build_probabilistic_vc_frontend(
        parsed={
            "goal_type": "pRHL",
            "post": (
                "post = Compute.bad{2} = "
                "(DoubleQuery.bad{1} \\/ mem DoubleQuery.qs s){1}"
            ),
        },
        goal_type="pRHL",
        program_ir={"statements": [{"kind": "WHILE"}, {"kind": "IF"}]},
        goal_text="while (i < n) { ... }",
        procedure_frontend={
            "loop_frontiers": [{"kind": "WHILE", "statement_path": "1"}],
            "branch_guards": [{"kind": "IF", "statement_path": "1.1"}],
            "sample_frontiers": [{"kind": "SAMPLE", "statement_path": "1.2"}],
        },
    )

    assert frontend["available"] is True
    kinds = {item["kind"] for item in frontend["obligations"]}
    assert "bad_event_reduction" in kinds
    assert "loop_bad_event_bound" in kinds
    assert "branch_event_split" in kinds
    assert "sampling_loss_or_coupling" in kinds
    assert frontend["strategy"] == "loop bad-event loss accounting"
    assert frontend["program_signals"]["loop_count"] == 1


def test_phoare_seq_bound_is_classified_without_bad_event_terms() -> None:
    frontend = build_probabilistic_vc_frontend(
        parsed={
            "goal_type": "phoare",
            "post": "(G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog",
            "suggested_tactics": [
                "seq 23 : ((G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog) 1%r 1%r 0%r _.",
                "rnd.",
            ],
        },
        goal_type="phoare",
        program_ir={"statements": [{"kind": "SAMPLE"}]},
        goal_text=(
            "phoare[ G4.main : true ==> "
            "(G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog ] <= "
            "(PKE_.qD%r / order%r)"
        ),
        procedure_frontend={
            "sample_frontiers": [{"kind": "SAMPLE", "statement_path": "23"}],
        },
    )

    assert frontend["available"] is True
    kinds = {item["kind"] for item in frontend["obligations"]}
    assert "phoare_seq_bound" in kinds
    assert "sampling_loss_or_coupling" in kinds
    assert frontend["strategy"] == "bounded phoare VC generation"


def test_event_terms_include_uniq_failure_shape() -> None:
    terms = probabilistic_vc_event_terms("! uniq qs /\\ not_failure /\\ win_event")

    assert "! uniq qs" in terms
    assert "not_failure" in terms
    assert "win_event" in terms
