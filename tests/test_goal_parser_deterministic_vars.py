"""Statement vars_read/vars_written must export in deterministic order.

swap_align Statements carry variable names as SETS; ec_goal_parser's
_parse_prhl is the boundary that serializes them into the parsed-goal
dicts every downstream consumer reads (dataflow invariant eq-sets,
call-invariant candidate tactic_shapes, preflight content hashes). A
plain list(set) there is PYTHONHASHSEED-ordered, which made generated
invariants like ``={dt, m0, m1, y}`` flip variable order between
otherwise-identical runs (observed via replay_audit on the cpa_ddh0
bundle). The boundary must emit sorted() lists.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import core.easycrypt.analysis.swap_align as swap_align  # noqa: E402
from core.easycrypt.analysis.ec_goal_parser import GoalInfo, _parse_prhl  # noqa: E402
from core.easycrypt.analysis.swap_align import AlignResult, Statement  # noqa: E402

# Enough names that a hash-ordered list(set) matching sorted() by luck is
# effectively impossible (and across three statements, astronomically so).
_NAMES = ["dt", "m0", "m1", "y", "b", "b0", "gx", "gy", "gz", "sk", "pk", "c"]


def _stub_result() -> AlignResult:
    stmts = [
        Statement(
            pos=i + 1,
            text=f"x{i} <@ M.f();",
            stmt_type="CALL",
            distribution="",
            procedure="M.f",
            vars_written=set(_NAMES[i:i + 4]),
            vars_read=set(_NAMES) - {"c"},
            pos_path=str(i + 1),
        )
        for i in range(3)
    ]
    return AlignResult(
        left=stmts, right=list(stmts), matches=[],
        unmatched_left=[], unmatched_right=[], swaps=[],
        pre="true", post="={res}",
    )


def test_parse_prhl_exports_sorted_var_lists(monkeypatch) -> None:
    monkeypatch.setattr(
        swap_align, "parse_prhl_goal", lambda raw_text, context_file=None: _stub_result()
    )
    info = GoalInfo(goal_type="pRHL", raw_text="")
    _parse_prhl(info, "pre = true\npost = ={res}")
    assert info.left_stmts and info.right_stmts
    for side in (info.left_stmts, info.right_stmts):
        for stmt in side:
            assert stmt["vars_read"] == sorted(stmt["vars_read"]), stmt
            assert stmt["vars_written"] == sorted(stmt["vars_written"]), stmt
    # the concrete flip observed in the wild: these four must serialize
    # identically in every process
    assert info.left_stmts[0]["vars_read"][:4] == ["b", "b0", "dt", "gx"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
