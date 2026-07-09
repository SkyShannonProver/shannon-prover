r"""CORRECT mechanism — the history-aware sticky-fact hook in PivotStrategyPhase.

`_up_to_bad_call_coherence` scans the committed-tactic history for a `byequiv`/
`equiv`/`conseq` post that admits a top-level `\/ bad` disjunct (sticky up-to-bad
fact), then flags a subsequently-committed LOCKSTEP `call (_: inv)` as incoherent.
Precision: silent when the committed post is pure-equivalence, when bad appears only
in implication position, or when the call is already the 2-clause up-to-bad form.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_hook_phases import PivotStrategyPhase  # noqa: E402


class _StubSession:
    def __init__(self, tmp: Path, tactics: list[str]) -> None:
        self.dir = tmp
        hist = tmp / "history.txt"
        hist.write_text("\n".join(tactics) + "\n", encoding="utf-8")
        self.history = str(hist)


def _phase(tmp: Path, tactics: list[str]) -> PivotStrategyPhase:
    ph = PivotStrategyPhase.__new__(PivotStrategyPhase)
    ph.session = _StubSession(tmp, tactics)
    return ph


# A current call-frontier goal whose own post is just the lockstep relation (the
# up-to-bad disjunct lives upstream in the committed byequiv — the sticky fact).
_FRONTIER_GOAL = "equiv[ G1.O ~ G2.O : !UFCMA.bad1{2} ==> ={res} ]"


def test_hook_fires_on_sticky_byequiv_then_lockstep_call(tmp_path: Path) -> None:
    tactics = [
        "byequiv (_: ={glob A} ==> res{1} => res{2} \\/ UFCMA.bad1{2} \\/ UFCMA.bad2{2}).",
        "proc.",
        "call (_: ={glob UFCMA} /\\ ={UFCMA.log}).",  # lockstep — incoherent here
    ]
    ph = _phase(tmp_path, tactics)
    out = ph._up_to_bad_call_coherence(_FRONTIER_GOAL)
    assert out is not None
    line, rec = out
    assert "[UP-TO-BAD CALL COHERENCE" in line
    assert rec["decision_context_key"] == "up_to_bad_call"
    assert "UFCMA.bad1" in rec["active_bad_events"]
    assert rec["committable"] is False


def test_hook_silent_on_pure_equiv_byequiv(tmp_path: Path) -> None:
    # step1/step3-style: pure-equivalence post, lockstep call is correct.
    tactics = [
        "byequiv (_: ={glob A, x} ==> ={res, glob M}).",
        "proc.",
        "call (_: ={glob M}).",
    ]
    ph = _phase(tmp_path, tactics)
    assert ph._up_to_bad_call_coherence("equiv[ M.f ~ M.g : ={x} ==> ={res} ]") is None


def test_hook_silent_when_call_already_uptobad(tmp_path: Path) -> None:
    tactics = [
        "byequiv (_: ={glob A} ==> res{1} => res{2} \\/ UFCMA.bad1{2}).",
        "proc.",
        "call (_: UFCMA.bad1, ={UFCMA.log}).",  # already 2-clause
    ]
    ph = _phase(tmp_path, tactics)
    assert ph._up_to_bad_call_coherence(_FRONTIER_GOAL) is None


def test_hook_silent_when_no_call_committed(tmp_path: Path) -> None:
    tactics = ["byequiv (_: ={glob A} ==> res{1} => res{2} \\/ UFCMA.bad1{2}).", "proc."]
    ph = _phase(tmp_path, tactics)
    assert ph._up_to_bad_call_coherence(_FRONTIER_GOAL) is None


# ============================================================================== #
# Audit 2026-06-09 (SPEC-C #2/#3): call selection + projection-annotated harvest. #
# The step4_1 resume Tree_0_1 prefix — byequiv with the nested `(...){2}` post,   #
# three lockstep calls, then a LEMMA-application `call (equ_cc ...)` — was a      #
# double false negative: (a) the byequiv post harvested ∅ (projection group not   #
# peeled), (b) even with names the temporally-last `call (equ_cc ...)` masked the #
# lockstep calls. Both fixed; pinned here on the verbatim prefix shape.           #
# ============================================================================== #

_TREE01_LOCKSTEP_CALL = (
    "call (_: inv SplitC2.I1.RO.m{1} RO.m{2} SplitC2.I2.RO.m{1} SplitC2.I2.RO.m{2} "
    "Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} "
    "BNR.ndec{1} BNR.ndec{2} UFCMA.log{2})."
)

_TREE01_PREFIX = [
    "apply (ler_trans (Pr[UFCMA(RO).distinguish() @ &m : (res \\/ UFCMA.bad2) \\/ UFCMA.bad1])).",
    "byequiv (_: ={glob A} ==> (res{1} => ((res \\/ UFCMA.bad2) \\/ UFCMA.bad1){2})).",
    "proc.",
    _TREE01_LOCKSTEP_CALL,
    _TREE01_LOCKSTEP_CALL,
    _TREE01_LOCKSTEP_CALL,
    "exlim n{2}, SplitC2.I1.RO.m{1}, SplitC2.I2.RO.m{1} => n0 mr0 ms0.",
    "call (equ_cc n0 mr0 ms0).",
]

# A downstream pure-logic subgoal — carries NO disjunct of its own; the up-to-bad
# fact must come from the STICKY committed byequiv.
_LOGIC_SUBGOAL = "forall (x : int), 0 <= x => poly_out x = poly_out x"


def test_hook_fires_on_tree01_prefix_despite_equ_cc_masking(tmp_path: Path) -> None:
    ph = _phase(tmp_path, _TREE01_PREFIX)
    out = ph._up_to_bad_call_coherence(_LOGIC_SUBGOAL)
    assert out is not None, (
        "the lemma-application `call (equ_cc ...)` masked the lockstep calls "
        "(pre-fix latest-call scan) or the nested byequiv post harvested ∅"
    )
    line, rec = out
    assert "[UP-TO-BAD CALL COHERENCE" in line
    assert set(rec["active_bad_events"]) == {"UFCMA.bad1", "UFCMA.bad2"}
    # The candidate is assembled from the LOCKSTEP call's invariant, never from a
    # lemma argument or a phoare flag. E2 (audit 2026-06-09): with BOTH bad1 and
    # bad2 active the bad clause is their disjunction so the call covers both —
    # the old `call (_: UFCMA.bad1, inv ...)` silently dropped bad2.
    assert rec["action"].startswith("call (_: (UFCMA.bad1 \\/ UFCMA.bad2), inv ")


def test_hook_silent_on_tree00_prefix_two_clause_behind_phoare(tmp_path: Path) -> None:
    # step4_1 resume Tree_0_0 prefix shape: the relational call is ALREADY the
    # 2-clause up-to-bad form; six later one-sided `call (_: UFCMA.bad1).` phoare
    # preservation calls must neither mask it nor be promoted to a lockstep call
    # (pre-fix: is_lockstep_call('call (_: UFCMA.bad1).') was True and the hook
    # assembled the absurd `call (_: UFCMA.bad2, UFCMA.bad1).`).
    tactics = [
        "byequiv (_: ={glob A} ==> res{1} => res{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2}).",
        "proc.",
        "call (_: UFCMA.bad1, inv RO.m{1} RO.m{2} UFCMA.log{2}).",
    ] + ["call (_: UFCMA.bad1)."] * 6
    ph = _phase(tmp_path, tactics)
    assert ph._up_to_bad_call_coherence(_LOGIC_SUBGOAL) is None


# ============================================================================== #
# Audit 2026-06-09 (SPEC-C #4): the coherence emit must NOT be shadowed by the    #
# `_try_relational_invariant` early returns (cands-empty / no-predicates /        #
# non-pRHL goal). Pre-fix the ONLY emit point sat at the tail of the resolved-    #
# carrier success path, so exactly the frontiers with no carrier never surfaced.  #
# ============================================================================== #


def test_coherence_emitted_from_try_relational_invariant_no_carrier(
    tmp_path: Path,
) -> None:
    # tmp session dir has no .ec sources -> no named predicates resolve -> the
    # pre-fix code returned the bare shape palette (or None) and the coherence
    # signal died in the early return. It must now ride along / surface alone.
    ph = _phase(tmp_path, _TREE01_PREFIX)
    prhl_goal = (
        "&1 (left ) : {p : plaintext}\n&2 (right) : {p : plaintext}\n"
        "pre = ={p}\npost = ={res}"
    )
    res = ph._try_relational_invariant(prhl_goal, None)
    assert res is not None
    assert "[UP-TO-BAD CALL COHERENCE" in res.text
    assert any(r.get("kind") == "up_to_bad_call" for r in res.recommendations)


def test_coherence_emitted_from_try_relational_invariant_non_prhl_goal(
    tmp_path: Path,
) -> None:
    # A pure-logic subgoal (not pRHL-shaped) used to return None before the
    # coherence check could run; the sticky fact must still surface.
    ph = _phase(tmp_path, _TREE01_PREFIX)
    res = ph._try_relational_invariant(_LOGIC_SUBGOAL, None)
    assert res is not None
    assert "[UP-TO-BAD CALL COHERENCE" in res.text


def test_try_relational_invariant_still_none_when_nothing_to_say(
    tmp_path: Path,
) -> None:
    # No carrier AND no coherence fact (pure-equivalence byequiv): stays None —
    # the early-return fix must not invent output where there is none.
    ph = _phase(tmp_path, [
        "byequiv (_: ={glob A, x} ==> ={res, glob M}).",
        "proc.",
        "call (_: ={glob M}).",
    ])
    assert ph._try_relational_invariant(_LOGIC_SUBGOAL, None) is None
