from __future__ import annotations

from workflow.proof_management.analyzers.frame_obligation import FrameObligationAnalyzer
from workflow.proof_management.node_state import ProofNodeState


def _state(
    view: dict,
    *,
    tactics: list[str] | None = None,
) -> ProofNodeState:
    return ProofNodeState(
        node_id="Tree-unit",
        base_workspace_view=view,
        committed_tactics=list(tactics or []),
    )


def _goal(*lines: str) -> dict:
    return {
        "proof_status": {"view_focus": "relational_program"},
        "current_goal": {"lines": list(lines)},
    }


def test_frame_obligation_analyzer_reports_dropped_frame_fact() -> None:
    analyzer = FrameObligationAnalyzer()
    surface = analyzer.analyze(
        state=_state(
            _goal(
                "Current goal",
                "(glob A){1} = (glob A){2}",
            ),
            tactics=[
                "byequiv (_ : ={glob A} ==> post)=> //.",
                "proc.",
                "seq 5 3 : (UFCMA.bad1{1} => event_bound).",
                "sp 4 2.",
            ],
        )
    )

    assert surface["kind"] == "frame_obligation_ledger"
    required = {item["fact"] for item in surface["required_later"]}
    assert "={glob A}" in required
    dropped = surface["possibly_dropped"][0]
    assert dropped["fact"] == "={glob A}"
    assert dropped["boundary"] == "seq #3"
    assert dropped["related_checkpoint"]["submit"]["intent"] == "undo_to_checkpoint"


def test_frame_obligation_analyzer_ignores_top_level_only_frame_fact() -> None:
    analyzer = FrameObligationAnalyzer()

    assert analyzer.analyze(
        state=_state(
            _goal(
                "Current goal",
                "UFCMA.bad1{1} => event_bound",
            ),
            tactics=[
                "byequiv (_ : ={glob A} ==> post)=> //.",
                "proc.",
                "seq 5 3 : (UFCMA.bad1{1} => event_bound).",
                "sp 4 2.",
            ],
        )
    ) == {}


def test_frame_obligation_analyzer_suppresses_carried_frame_fact() -> None:
    analyzer = FrameObligationAnalyzer()

    assert analyzer.analyze(
        state=_state(
            _goal(
                "Current goal",
                "(glob A){1} = (glob A){2}",
            ),
            tactics=[
                "byequiv (_ : ={glob A} ==> post)=> //.",
                "proc.",
                "seq 5 3 : (={glob A} /\\ UFCMA.bad1{1} => event_bound).",
                "sp 4 2.",
            ],
        )
    ) == {}


def test_frame_obligation_analyzer_ignores_prior_proof_segment_boundaries() -> None:
    analyzer = FrameObligationAnalyzer()

    assert analyzer.analyze(
        state=_state(
            _goal(
                "Current goal",
                "equiv[M.f ~ N.g : ={glob A} ==> ={res}]",
            ),
            tactics=[
                "congr.",
                "call (_: Mem.k{1} = IndBlock.k{2}).",
                "proc; inline *; sim.",
                "have H : equiv[M.f ~ N.g : ={glob A} ==> ={res}].",
            ],
        )
    ) == {}


def test_frame_obligation_analyzer_glob_subsumes_field_no_false_drop() -> None:
    """A carried `={glob OCC}` covers the field `={OCC.gs}` (subsumption), so the field must
    NOT be reported as dropped. Regression for the CCP_OCCP false `={OCC.gs} dropped` alarm
    that recommended a wrong rewind even though `={glob OCC}` was carried."""
    analyzer = FrameObligationAnalyzer()
    assert analyzer.analyze(
        state=_state(
            _goal("Current goal", "={OCC.gs}"),
            tactics=[
                "byequiv (_ : ={glob OCC} ==> post)=> //.",
                "proc.",
                "seq 5 3 : (={glob OCC} /\\ UFCMA.bad1{1} => event_bound).",
                "sp 4 2.",
            ],
        )
    ) == {}


def test_frame_obligation_analyzer_clone_alias_no_false_drop() -> None:
    """`RO.m` and its clone-qualified `ROIN.RO.m` are the same field, so a carried
    `={ROIN.RO.m}` covers a required `={RO.m}`. Regression for the step4_badi false
    `={RO.m} dropped` alarm (RO.m vs ROIN.RO.m name-normalization mismatch)."""
    analyzer = FrameObligationAnalyzer()
    assert analyzer.analyze(
        state=_state(
            _goal("Current goal", "={RO.m}"),
            tactics=[
                "byequiv (_ : ={glob A} ==> post)=> //.",
                "proc.",
                "seq 5 3 : (={ROIN.RO.m} /\\ UFCMA.bad1{1} => event_bound).",
                "sp 4 2.",
            ],
        )
    ) == {}


def test_frame_obligation_analyzer_unrelated_leaf_name_still_dropped() -> None:
    """The alias rule must NOT over-match fields that merely share a leaf name: required
    `={X.m}` is NOT covered by a carried `={Y.m}` (different modules), so a REAL drop is
    still reported — the lenience fixes false positives without blinding the ledger."""
    analyzer = FrameObligationAnalyzer()
    surface = analyzer.analyze(
        state=_state(
            _goal("Current goal", "={X.m}"),
            tactics=[
                "byequiv (_ : ={glob A} ==> post)=> //.",
                "proc.",
                "seq 5 3 : (={Y.m} /\\ UFCMA.bad1{1} => event_bound).",
                "sp 4 2.",
            ],
        )
    )
    assert surface.get("kind") == "frame_obligation_ledger"
    assert any(d["fact"] == "={X.m}" for d in surface["possibly_dropped"])


def test_frame_obligation_analyzer_pre_transitivity_suppresses_false_drop() -> None:
    """A `={glob A}` DERIVABLE from the PRE by transitivity through a middle memory
    (`(glob A){1}=(glob A){m} ∧ (glob A){2}=(glob A){m}` ⊢ `={glob A}`) is NOT dropped — it
    is provable, just not re-asserted at the `call (_: true)` boundary. Regression for the
    cpa_ddh0 false `={glob A} dropped → undo_to_checkpoint` that would rewind a sound proof."""
    analyzer = FrameObligationAnalyzer()
    assert analyzer.analyze(
        state=_state(
            _goal(
                "Current goal",
                "pre =",
                "  (glob A){1} = (glob A){m} /\\",
                "  (glob A){2} = (glob A){m}",
                "CPA(E, A).main ~ DDH(A).main",
                "post = (glob A){1} = (glob A){2}",
            ),
            tactics=[
                "byequiv (_ : ={glob A} ==> post)=> //.",
                "proc.",
                "call (_: true).",
                "sp 4 2.",
            ],
        )
    ) == {}


def test_frame_obligation_analyzer_one_transitivity_half_still_drops() -> None:
    """The suppression needs BOTH halves: only `(glob A){1}=(glob A){m}` in the pre does NOT
    prove `={glob A}`, so a real drop is still reported (no over-suppression)."""
    analyzer = FrameObligationAnalyzer()
    surface = analyzer.analyze(
        state=_state(
            _goal(
                "Current goal",
                "pre = (glob A){1} = (glob A){m}",
                "post = (glob A){1} = (glob A){2}",
            ),
            tactics=[
                "byequiv (_ : ={glob A} ==> post)=> //.",
                "proc.",
                "seq 5 3 : (other{1} => bound).",
                "sp 4 2.",
            ],
        )
    )
    assert surface.get("kind") == "frame_obligation_ledger"
    assert any(d["fact"] == "={glob A}" for d in surface["possibly_dropped"])
