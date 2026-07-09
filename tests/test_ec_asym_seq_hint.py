"""Unit tests for ``ec_asym_seq_hint.synthesize_invariants``.

These tests exercise the synthesis logic against synthetic ``AlignResult``
fixtures so we can pin behavior without needing a live EasyCrypt session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_asym_seq_hint import (  # noqa: E402
    AsymSeqProposal,
    synthesize_invariants,
)


@dataclass
class _Stmt:
    pos: int
    text: str = ""
    stmt_type: str = "ASSIGN"
    distribution: str = ""
    procedure: str = ""
    vars_written: set = field(default_factory=set)
    vars_read: set = field(default_factory=set)
    pos_path: str = ""


@dataclass
class _Match:
    left_pos: int
    right_pos: int
    match_type: str = "CALL"
    label: str = ""
    confidence: str = "exact"


@dataclass
class _Result:
    left: list
    right: list
    matches: list
    unmatched_left: list = field(default_factory=list)
    unmatched_right: list = field(default_factory=list)
    swaps: list = field(default_factory=list)
    blocked_swaps: list = field(default_factory=list)
    pre: str = ""
    post: str = ""


def _preferred(result) -> AsymSeqProposal | None:
    proposals = synthesize_invariants(result)
    return proposals[0] if proposals else None


def test_symmetric_returns_none() -> None:
    """When LHS and RHS have equal stmt counts, no proposal."""
    res = _Result(
        left=[_Stmt(1, vars_written={"x"})],
        right=[_Stmt(1, vars_written={"x"})],
        matches=[_Match(1, 1)],
    )
    assert _preferred(res) is None


def test_no_matches_returns_none() -> None:
    res = _Result(
        left=[_Stmt(1), _Stmt(2)],
        right=[_Stmt(1)],
        matches=[],
    )
    assert _preferred(res) is None


def test_same_name_matches_emit_eq_clause() -> None:
    """When matched stmts write the same variable on both sides, the
    invariant uses the ``={var}`` shape."""
    res = _Result(
        left=[
            _Stmt(1, vars_written={"k"}),
            _Stmt(2, vars_written={"t"}),
            _Stmt(3, vars_written={"result"}),
            _Stmt(4),
            _Stmt(5),
        ],
        right=[
            _Stmt(1, vars_written={"k"}),
            _Stmt(2, vars_written={"t"}),
            _Stmt(3, vars_written={"result"}),
        ],
        matches=[
            _Match(1, 1),
            _Match(2, 2),
            _Match(3, 3),
        ],
    )
    proposal = _preferred(res)
    assert proposal is not None
    assert proposal.left_n == 5
    assert proposal.right_m == 3
    assert proposal.matched_pair_count == 3
    # Single combined ={k, result, t} clause, alphabetically sorted.
    assert proposal.invariant == "={k, result, t}"
    assert proposal.to_tactic() == "seq 5 3 : (={k, result, t})."


def test_multiple_split_candidates_surface_structure() -> None:
    """The generator should not hard-code a single full-prefix split.

    The old full-prefix proposal remains first for compatibility, but call
    and control-flow boundaries are exposed as separate candidates so the
    daemon/cost model can choose locally.
    """
    res = _Result(
        left=[
            _Stmt(1, stmt_type="CALL", procedure="M.f", vars_written={"x"}),
            _Stmt(2, stmt_type="IF"),
            _Stmt(3, vars_written={"z"}),
        ],
        right=[
            _Stmt(1, stmt_type="CALL", procedure="M.f", vars_written={"x"}),
            _Stmt(2, stmt_type="IF"),
        ],
        matches=[
            _Match(1, 1, match_type="CALL"),
            _Match(2, 2, match_type="IF"),
        ],
    )
    proposals = synthesize_invariants(res)
    assert proposals
    assert proposals[0].origin == "full_prefix_alignment"
    origins = {proposal.origin for proposal in proposals}
    assert "first_call_boundary" in origins
    assert any(proposal.to_tactic() == "seq 1 1 : (={x})." for proposal in proposals)


def test_seq_proposal_reports_live_fact_coverage() -> None:
    res = _Result(
        left=[
            _Stmt(1, stmt_type="CALL", vars_written={"c1"}, vars_read={"n", "p1"}),
            _Stmt(2, vars_written={"flag"}),
        ],
        right=[
            _Stmt(1, stmt_type="CALL", vars_written={"c1"}, vars_read={"n", "p1"}),
        ],
        matches=[_Match(1, 1, match_type="CALL")],
        post="post = c1{1} = c1{2} /\\ badi{2}",
    )

    proposal = [
        item for item in synthesize_invariants(res)
        if item.origin == "first_call_boundary"
    ][0]

    assert proposal.preserved_vars == ("c1",)
    assert "n" in proposal.prefix_read_vars
    assert "p1" in proposal.prefix_read_vars
    assert "badi" in proposal.missing_live_post_vars
    assert proposal.coverage == "partial_visible_live_coverage"
    assert "prefix reads not carried" in proposal.coverage_note()


def test_renamed_match_emits_asym_clause() -> None:
    """When matched stmts write differently-named locals (LHS ``c0``
    vs RHS ``c`` after oracle inlining), emit ``c0{1} = c{2}``."""
    res = _Result(
        left=[
            _Stmt(1, vars_written={"c0"}),
            _Stmt(2),
            _Stmt(3),
            _Stmt(4),
            _Stmt(5),
        ],
        right=[
            _Stmt(1, vars_written={"c"}),
            _Stmt(2),
            _Stmt(3),
        ],
        matches=[_Match(1, 1)],
    )
    proposal = _preferred(res)
    assert proposal is not None
    assert "c0{1} = c{2}" in proposal.invariant


def test_mixed_same_and_renamed_clauses() -> None:
    """Common case for ChaChaPoly step1 dec: shared ``n, a, t`` plus a
    renamed ``c0`` ↔ ``c`` pair. Synthesis emits both pieces joined by
    ``/\\``."""
    res = _Result(
        left=[
            _Stmt(1, vars_written={"n", "a", "c0", "t"}),
            _Stmt(2),
            _Stmt(3),
            _Stmt(4),
            _Stmt(5),
        ],
        right=[
            _Stmt(1, vars_written={"n", "a", "c", "t"}),
            _Stmt(2),
            _Stmt(3),
        ],
        matches=[_Match(1, 1)],
    )
    proposal = _preferred(res)
    assert proposal is not None
    # ={a, n, t} for shared, c0{1} = c{2} for the rename.
    assert "={a, n, t}" in proposal.invariant
    assert "c0{1} = c{2}" in proposal.invariant
    assert " /\\ " in proposal.invariant


def test_unsafe_var_names_filtered() -> None:
    """Names with operators, leading digits, or whitespace must be
    filtered out — they would produce syntactically invalid EC."""
    res = _Result(
        left=[
            _Stmt(1, vars_written={"x", "1bad", "x+y", "x y"}),
            _Stmt(2),
            _Stmt(3),
        ],
        right=[
            _Stmt(1, vars_written={"x", "1bad", "x+y", "x y"}),
        ],
        matches=[_Match(1, 1)],
    )
    proposal = _preferred(res)
    assert proposal is not None
    assert proposal.invariant == "={x}"


def test_qualified_name_allowed() -> None:
    """Qualified names like ``Mem.k`` are valid EC identifiers and
    must be preserved."""
    res = _Result(
        left=[
            _Stmt(1, vars_written={"Mem.k"}),
            _Stmt(2),
            _Stmt(3),
        ],
        right=[
            _Stmt(1, vars_written={"Mem.k"}),
        ],
        matches=[_Match(1, 1)],
    )
    proposal = _preferred(res)
    assert proposal is not None
    assert "Mem.k" in proposal.invariant


def test_no_writes_falls_back_to_true() -> None:
    """If matched statements have no written vars (e.g. structural
    matches), invariant degrades to ``true``. No proposal is emitted
    because there are no contributing matches with vars_written."""
    res = _Result(
        left=[_Stmt(1), _Stmt(2)],
        right=[_Stmt(1)],
        matches=[_Match(1, 1)],
    )
    proposal = _preferred(res)
    # Match exists but contributes nothing → invariant is empty.
    # synthesize returns proposal with invariant="true" only when at
    # least one match contributed; matches with no vars_written are
    # skipped before counting.
    assert proposal is None


def test_proposal_to_tactic_format() -> None:
    p = AsymSeqProposal(
        left_n=5, right_m=3, invariant="={n, a, t}", matched_pair_count=2,
    )
    assert p.to_tactic() == "seq 5 3 : (={n, a, t})."


def main() -> int:
    tests = [
        test_symmetric_returns_none,
        test_no_matches_returns_none,
        test_same_name_matches_emit_eq_clause,
        test_multiple_split_candidates_surface_structure,
        test_seq_proposal_reports_live_fact_coverage,
        test_renamed_match_emits_asym_clause,
        test_mixed_same_and_renamed_clauses,
        test_unsafe_var_names_filtered,
        test_qualified_name_allowed,
        test_no_writes_falls_back_to_true,
        test_proposal_to_tactic_format,
    ]
    for t in tests:
        t()
    print("PASS test_ec_asym_seq_hint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
