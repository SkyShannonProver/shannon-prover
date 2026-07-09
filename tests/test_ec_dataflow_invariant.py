"""Tests for dataflow-backed invariant skeleton generation."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_dataflow_invariant import (  # noqa: E402
    build_invariant_skeleton,
)


def test_dataflow_invariant_adds_common_code_reads() -> None:
    skeleton = build_invariant_skeleton(
        {
            "post": "={Mem.log} /\\ StLSke.gs{1} = RO.m{2}",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "c <@ L.enc(k, p);",
                "vars_read": ["k", "p"],
                "vars_written": ["c"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "c <@ R.enc(k, p);",
                "vars_read": ["k", "p"],
                "vars_written": ["c"],
            }],
        },
        "pRHL",
    )

    assert skeleton["shared_equalities"] == ["Mem.log"]
    assert skeleton["dataflow_equalities"] == ["k", "p"]
    assert skeleton["suggested_invariant"] == (
        "={Mem.log, k, p} /\\ StLSke.gs{1} = RO.m{2}"
    )
    assert skeleton["native_reference"]["easycrypt_modules"] == [
        "EcPV.s_read",
        "EcPV.s_write",
        "EcPV.PV.fv",
        "EcPhlTrans.t_equivS_trans_eq",
    ]


def test_backward_liveness_promotes_reads_for_live_writes() -> None:
    skeleton = build_invariant_skeleton(
        {
            "post": "={res}",
            "left_statements": [{
                "pos": 1,
                "type": "ASSIGN",
                "text": "x <- k;",
                "vars_read": ["k"],
                "vars_written": ["x"],
            }, {
                "pos": 2,
                "type": "ASSIGN",
                "text": "res <- x;",
                "vars_read": ["x"],
                "vars_written": ["res"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "ASSIGN",
                "text": "x <- k;",
                "vars_read": ["k"],
                "vars_written": ["x"],
            }, {
                "pos": 2,
                "type": "ASSIGN",
                "text": "res <- x;",
                "vars_read": ["x"],
                "vars_written": ["res"],
            }],
        },
        "pRHL",
    )

    left_steps = skeleton["backward_liveness"]["left"]
    assert left_steps[1]["live_after"] == ["res"]
    assert left_steps[1]["live_before"] == ["x"]
    assert left_steps[0]["live_before"] == ["k"]
    assert skeleton["dataflow_equalities"] == ["k", "x"]


def test_dataflow_invariant_keeps_one_sided_reads_out_of_equalities() -> None:
    skeleton = build_invariant_skeleton(
        {
            "post": "={res}",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "res <@ L.f(k, left_only);",
                "vars_read": ["k", "left_only"],
                "vars_written": ["res"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "res <@ R.f(k);",
                "vars_read": ["k"],
                "vars_written": ["res"],
            }],
        },
        "pRHL",
    )

    assert skeleton["dataflow_equalities"] == ["k"]
    assert "left_only" not in skeleton["suggested_invariant"]


def test_dataflow_invariant_carries_live_pre_relations() -> None:
    skeleton = build_invariant_skeleton(
        {
            "pre": (
                "pre = k{1} = Mem.k{1} /\\ "
                "Mem.k{1} = Block.k{2} /\\ unrelated{1} = ghost{2}"
            ),
            "post": "post = ={n, result} /\\ c0{1} = c{2}",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "t <@ L.mac(k, n, c0);",
                "vars_read": ["k", "n", "c0"],
                "vars_written": ["t"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "t <@ R.mac(Block.k, n, c);",
                "vars_read": ["Block.k", "n", "c"],
                "vars_written": ["t"],
            }],
        },
        "pRHL",
    )

    assert "k{1} = Mem.k{1}" in skeleton["carried_precondition_atoms"]
    assert "Mem.k{1} = Block.k{2}" in skeleton["carried_precondition_atoms"]
    assert "unrelated{1} = ghost{2}" not in skeleton["carried_precondition_atoms"]
    assert "k{1} = Mem.k{1}" in skeleton["suggested_invariant"]


def test_dataflow_invariant_exposes_equality_closure_provenance() -> None:
    skeleton = build_invariant_skeleton(
        {
            "pre": (
                "pre = local_k{1} = Mem.k{1} /\\ "
                "Mem.k{1} = Game.k{2} /\\ Game.k{2} = ghost{2} /\\ "
                "dead{1} = other{2}"
            ),
            "post": "post = tag{1} = tag{2}",
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "tag <@ L.mac(local_k, msg);",
                "vars_read": ["local_k", "msg"],
                "vars_written": ["tag"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "tag <@ R.mac(Game.k, msg);",
                "vars_read": ["Game.k", "msg"],
                "vars_written": ["tag"],
            }],
        },
        "pRHL",
    )

    carried = skeleton["carried_precondition_atoms"]
    assert "local_k{1} = Mem.k{1}" in carried
    assert "Mem.k{1} = Game.k{2}" in carried
    assert "Game.k{2} = ghost{2}" in carried
    assert "dead{1} = other{2}" not in carried
    closure = skeleton["carried_precondition_closure"]
    assert closure["kind"] == "precondition_equality_liveness_closure"
    assert [
        item["text"] for item in closure["closure_steps"]
    ][:3] == [
        "local_k{1} = Mem.k{1}",
        "Mem.k{1} = Game.k{2}",
        "Game.k{2} = ghost{2}",
    ]
    assert "EasyCrypt still type-checks" in closure["strategy_boundary"]


def test_dataflow_invariant_drops_initial_state_and_callee_proc_name() -> None:
    """Regression for the step4_badi misleading call-invariant candidate.

    The skeleton must not (a) treat a callee procedure name picked up by read
    extraction (``b <@ Game(A).main()`` -> ``main``) as a shared equality, nor
    (b) bake the *initial* program state (``lbad1 = []``, ``badi = false``) into
    the suggested invariant.  Both made the surfaced ``call (_: ...)`` candidate
    read like a complete-but-wrong invariant.
    """
    skeleton = build_invariant_skeleton(
        {
            "pre": (
                "pre = UFCMA_li.badi{2} = false /\\ "
                "UFCMA_l.lbad1{2} = [] /\\ UFCMA_l.lbad1{1} = []"
            ),
            "post": (
                "post = (let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in "
                "tt.`1 = tt.`2) => UFCMA_li.badi{2}"
            ),
            "left_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "b <@ Game(A).main();",
                "vars_read": ["main"],
                "vars_written": ["b"],
            }],
            "right_statements": [{
                "pos": 1,
                "type": "CALL",
                "text": "b <@ Game(A).main();",
                "vars_read": ["main"],
                "vars_written": ["b"],
            }],
        },
        "pRHL",
    )

    suggested = skeleton["suggested_invariant"]
    # (a) the callee procedure name never becomes an equality-frame variable
    assert "main" in skeleton["excluded_procedure_names"]
    assert "={main}" not in suggested
    assert "main" not in suggested
    # (b) initial-state facts are dropped, not surfaced as invariant conjuncts
    dropped = skeleton["dropped_initial_value_atoms"]
    assert "UFCMA_l.lbad1{2} = []" in dropped
    assert "UFCMA_li.badi{2} = false" in dropped
    assert "= []" not in suggested
    assert "= false" not in suggested
    # the genuine postcondition-to-preserve is still surfaced
    assert "UFCMA_li.badi{2}" in suggested


def main() -> int:
    test_dataflow_invariant_adds_common_code_reads()
    test_backward_liveness_promotes_reads_for_live_writes()
    test_dataflow_invariant_keeps_one_sided_reads_out_of_equalities()
    test_dataflow_invariant_carries_live_pre_relations()
    test_dataflow_invariant_exposes_equality_closure_provenance()
    test_dataflow_invariant_drops_initial_state_and_callee_proc_name()
    print("PASS test_ec_dataflow_invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
