r"""Mechanism CATCH — local-patch / no-progress loop detector.

Contract (REWRITTEN per the 2026-06-09 six-sequence panel audit):
  - A fingerprint scores a recurrence HIT only when it is REACHED BY AN ACCEPTED,
    non-errored ``commit_tactic``, and a later hit counts only after the agent
    GENUINELY LEFT — at least one accepted commit on a DIFFERENT fingerprint
    between consecutive hits. Turns that cannot change proof state (read-only
    inspect/lookup echoes, REJECTED/errored commits, text-equal auto-reverts,
    repair turns, undo menus, gated qed/finish) count NEITHER as hits NOR as
    leaving. (The audited pre-rewrite code counted ANY re-render of the same
    fingerprint: "1 accepted commit + 2 state-frozen turns" met K=3 — the
    dominant false-positive shape, 73/74 banners across six audited sequences.)
  - FIRES only on the K-th (K=3) accepted re-arrival, with no restructuring
    intent between hits and no frontier-floor improvement between returns.
  - HARD SILENCE on terminal/closed views (``No more goals`` /
    candidate_closed_pending_qed / closed_candidate), on windows with < 2
    non-None ``remaining`` samples, and on the undo/restart turn + the turn
    right after (undo cooldown).
  - Keyed on the rendered fingerprint, NOT goal_hash; the monotonic REPL prompt
    line is stripped (Defect 1).
  - One banner per loop EPISODE via the manager latch; re-arm only after >= 2
    ACCEPTED commits land outside the captured loop-set, a game-pair
    restructure, or an undo/restart intent (full vocabulary incl.
    ``undo_to_checkpoint`` / ``fresh_restart``).
"""
from __future__ import annotations

import glob
import json
import os

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from tests.helpers.builders import (  # noqa: E402
    drive_osc_loop,
    loop_goal_view,
    next_loop_prompt,
)
from workflow.patch_loop_detector import (  # noqa: E402
    DECISION_CONTEXT_KEY,
    TurnRecord,
    detect_patch_loop,
    record_from,
    render_fingerprint,
)

# The synthetic views carry the monotonic `[NNN|check]>` REPL prompt line
# (advancing per call — see tests.helpers.builders) so the synthetic loop tests
# exercise Defect 1: a fingerprint that did NOT strip this line would change
# every turn and the loop would never be detected.


def _goal_view(label: str, remaining: int | None, *, layer: str = "call_site") -> dict:
    """A synthetic rendered view whose fingerprint is determined by (label,
    remaining, layer). Distinct labels model genuinely different goals."""
    return loop_goal_view(label, remaining, layer=layer)


def _frozen_view(remaining: int = 5) -> dict:
    """The step4_1-shaped recurring goal (legacy fixture name kept for the
    fingerprint tests)."""
    return _goal_view("!UFCMA.bad1{2}", remaining)


def _commit(view: dict, tactic: str, *, ok: bool = True, errored: bool = False) -> TurnRecord:
    return record_from(view, intent="commit_tactic", tactic=tactic, ok=ok, errored=errored)


def _readonly(view: dict, intent: str = "inspect_context") -> TurnRecord:
    return record_from(view, intent=intent, tactic="", ok=True, errored=False)


def _osc_loop(n_arrivals: int = 3, *, loop_label: str = "LOOP-A",
              away_label: str = "AWAY-B", loop_rem: int = 5,
              away_rem: int = 4) -> list[TurnRecord]:
    """The REAL loop shape the detector targets: accepted commits ARRIVE at the
    loop goal, genuinely LEAVE via an accepted commit to a different goal, and
    arrive back — ``n_arrivals`` times, ending ON an arrival."""
    return drive_osc_loop(
        _commit,
        make_loop_view=lambda: _goal_view(loop_label, loop_rem),
        make_away_view=lambda: _goal_view(away_label, away_rem),
        arrivals=n_arrivals,
    )


def test_render_fingerprint_stable_and_distinguishing() -> None:
    # Two views with the SAME goal but DIFFERENT monotonic `[NNN|check]>` prompt
    # lines must yield the SAME fingerprint (Defect 1: the prompt is stripped).
    a = render_fingerprint(_frozen_view(5))
    b = render_fingerprint(_frozen_view(5))
    assert a == b
    # A different remaining count changes the fingerprint.
    assert render_fingerprint(_frozen_view(4)) != a


def test_render_fingerprint_ignores_repl_prompt_line() -> None:
    # Direct Defect-1 guard: identical goal, only the `[NNN|check]>` index advances.
    base_lines = [
        "Current goal (remaining: 5)",
        "pre = UFCMA.bad1 /\\ size Mem.lc <= qdec",
        "post = UFCMA.bad1",
    ]
    v1 = {
        "current_goal": {"lines": base_lines + ["[521|check]>"]},
        "proof_status": {"remaining_goals": 5, "current_layer": "procedure_body"},
    }
    v2 = {
        "current_goal": {"lines": base_lines + ["[540|check]>"]},
        "proof_status": {"remaining_goals": 5, "current_layer": "procedure_body"},
    }
    assert render_fingerprint(v1) == render_fingerprint(v2)
    # But real goal content must still distinguish.
    v3 = {
        "current_goal": {"lines": base_lines[:-1] + ["post = false", "[540|check]>"]},
        "proof_status": {"remaining_goals": 5, "current_layer": "procedure_body"},
    }
    assert render_fingerprint(v3) != render_fingerprint(v1)


# --------------------------------------------------------------------------- #
# Core recurrence semantics: accepted re-arrival after a genuine departure.    #
# --------------------------------------------------------------------------- #


def test_CATCH_fires_on_accepted_rearrival_macrocycle() -> None:
    # The step4_1 shape: accepted commits keep ARRIVING BACK at the same goal
    # after genuinely working elsewhere (A -> B -> A -> B -> A), no restructure,
    # floor between returns flat. Fires on the 3rd accepted arrival.
    history = _osc_loop(3)
    flag = detect_patch_loop(history, k=3)
    assert flag is not None
    assert flag["key"] == DECISION_CONTEXT_KEY == "local_patch_loop"
    assert flag["certified"] is False
    assert flag["recurrences"] == 3
    assert flag["remaining"] == 5
    assert "patch loop, not progress" in flag["text"]
    # The audited-false claim is gone for good; N is the accepted-arrival count.
    assert "via accepted local tactics" not in flag["text"]
    assert "net open goals unchanged" not in flag["text"]
    # Round-2 F3 wording: N includes the CREATION arrival, so the text spells
    # the breakdown out instead of reading as if all N were returns.
    assert "reached this identical goal 3 times" in flag["text"]
    assert "(first arrival + 2 returns, each after working elsewhere)" in flag["text"]
    assert "arrived back" not in flag["text"]
    # The BARE detector is domain-agnostic: NEUTRAL banner, no call/up-to-bad text.
    assert "re-issue your `call`" not in flag["text"]
    assert "reconsider the structural tactic that produced this frontier" in flag["text"]


def test_CATCH_fires_only_on_the_arrival_turn_itself() -> None:
    # Even with >= 3 accepted arrivals in the window, the detector only fires
    # when the CURRENT turn is the accepted re-arrival — never on a read-only
    # echo of the looped goal (the audited code fired on inspect/lookup turns).
    history = _osc_loop(3)
    assert detect_patch_loop(history, k=3) is not None
    history.append(_readonly(_goal_view("LOOP-A", 5)))
    assert detect_patch_loop(history, k=3) is None
    history.append(_readonly(_goal_view("LOOP-A", 5), intent="lookup_symbol"))
    assert detect_patch_loop(history, k=3) is None


def test_CATCH_silent_without_genuine_departure() -> None:
    # Accepted commits that keep landing on the SAME fingerprint without ever
    # leaving collapse into ONE arrival — never K. (Replaces the old
    # "truly frozen loop" fire expectation: the audit established that an
    # accepted commit which re-renders an identical view is a text-equal no-op
    # auto-reverted by the manager — production cannot legitimately produce
    # this shape via accepted state-changing commits, and the old any-re-render
    # hit counting was the dominant false-positive engine.)
    frozen = [
        _commit(_frozen_view(5), "smt()."),
        _commit(_frozen_view(5), "smt()."),
        _commit(_frozen_view(5), "smt()."),
        _commit(_frozen_view(5), "smt()."),
    ]
    assert detect_patch_loop(frozen, k=3) is None


def test_CATCH_does_not_fire_when_remaining_decreases() -> None:
    # Remaining strictly shrinks 5 -> 4 -> 3: a legitimately converging proof.
    # (Distinct remaining => distinct fingerprints, < k arrivals anywhere.)
    history = [
        _commit(_frozen_view(5), "auto."),
        _commit(_frozen_view(4), "auto."),
        _commit(_frozen_view(3), "auto."),
    ]
    assert detect_patch_loop(history, k=3) is None


def test_CATCH_does_not_fire_with_restructure_between() -> None:
    # The oscillating loop would fire — but a `call` (game-pair restructure)
    # between the arrivals resets it. Must NOT fire.
    history = [
        _commit(_goal_view("LOOP-A", 5), "smt()."),
        _commit(_goal_view("AWAY-B", 4), "call (_: UFCMA.bad1, ={UFCMA.log})."),
        _commit(_goal_view("LOOP-A", 5), "smt()."),
        _commit(_goal_view("AWAY-B", 4), "auto."),
        _commit(_goal_view("LOOP-A", 5), "smt()."),
    ]
    assert detect_patch_loop(history, k=3) is None


def test_CATCH_does_not_fire_below_k() -> None:
    assert detect_patch_loop(_osc_loop(2), k=3) is None


def test_CATCH_requires_an_accepted_commit_not_just_probes() -> None:
    # Same fingerprint recurs >=3 but every turn is a read-only probe/inspect:
    # this is a stall signal, not a *patch* loop. Must NOT fire.
    v = _frozen_view(5)
    probe = record_from(v, intent="probe_tactic", tactic="auto.", ok=False, errored=True)
    history = [probe, probe, probe]
    assert detect_patch_loop(history, k=3) is None


# --------------------------------------------------------------------------- #
# The six audited state-frozen filler shapes — none may score a hit.           #
# (1 accepted commit + 2 such turns was the dominant FP: e.g. UFCMA_genCC      #
# Tree_0_1 t48 = commit + lookup(enc) + lookup(genpoly1305).)                  #
# --------------------------------------------------------------------------- #


def _one_commit_plus(fillers: list[TurnRecord]) -> list[TurnRecord]:
    """The audited degenerate shape: one accepted commit CREATES the goal, then
    state-frozen turns re-render it (here: k-1 = 2 fillers)."""
    return [_commit(_goal_view("STUCK", 6), "sp.")] + fillers


def test_no_hit_from_readonly_echoes() -> None:
    v = lambda: _goal_view("STUCK", 6)  # noqa: E731
    hist = _one_commit_plus([
        _readonly(v(), "inspect_context"),
        _readonly(v(), "lookup_symbol"),
    ])
    assert detect_patch_loop(hist, k=3) is None


def test_no_hit_from_rejected_commits() -> None:
    # UFCMA Tree_0_1_r2 t4 shape: accepted `have H0 := ...` then two commits
    # rejected with `[error] unknown lemma H0` re-rendering the same goal.
    v = lambda: _goal_view("STUCK", 6)  # noqa: E731
    hist = _one_commit_plus([
        _commit(v(), "apply H0.", ok=False, errored=True),
        _commit(v(), "apply H0.", ok=False, errored=True),
    ])
    assert detect_patch_loop(hist, k=3) is None


def test_no_hit_from_text_equal_autoreverts() -> None:
    # step4_1 resume Tree_0_1 t11 shape: EC "accepted" but text-equal -> the
    # manager auto-reverts and surfaces error_summary='text-equal' (ok=True,
    # errored=True) — NOT an accepted arrival.
    v = lambda: _goal_view("STUCK", 6)  # noqa: E731
    hist = _one_commit_plus([
        _commit(v(), "move=> _; split.", ok=True, errored=True),
        _commit(v(), "move=> _; split.", ok=True, errored=True),
    ])
    assert detect_patch_loop(hist, k=3) is None


def test_no_hit_from_repair_turns() -> None:
    # step4_1 resume Tree_0_1_r2 t48 shape: malformed replies -> repair turns
    # with intent=None / ok=False re-rendering the goal.
    v = lambda: _goal_view("STUCK", 6)  # noqa: E731
    repair = lambda: record_from(v(), intent="", tactic="", ok=False, errored=False)  # noqa: E731
    hist = _one_commit_plus([repair(), repair()])
    assert detect_patch_loop(hist, k=3) is None


def test_no_hit_from_gated_qed_finish() -> None:
    # badi resume Tree_0_1 t5 shape: `qed.` deflected by the scaffold-debt gate
    # (ok=False), `finish` deflected by the give-up gate — state untouched.
    v = lambda: _goal_view("STUCK", 6)  # noqa: E731
    hist = _one_commit_plus([
        _commit(v(), "qed.", ok=False, errored=False),
        record_from(v(), intent="finish", tactic="", ok=False, errored=False),
    ])
    assert detect_patch_loop(hist, k=3) is None


def test_fillers_do_not_count_as_leaving_either() -> None:
    # Rejected/read-only turns on OTHER fingerprints are not departures: two
    # accepted arrivals separated only by such turns still collapse below k
    # even with a third accepted same-fp commit (no accepted commit ever landed
    # on a different fingerprint).
    A = lambda: _goal_view("LOOP-A", 5)  # noqa: E731
    B = lambda: _goal_view("AWAY-B", 4)  # noqa: E731
    hist = [
        _commit(A(), "smt()."),
        _commit(B(), "auto.", ok=False, errored=True),  # rejected — not a departure
        _readonly(B()),                                  # echo — not a departure
        _commit(A(), "smt()."),                          # same arrival, no departure
        _commit(A(), "smt()."),
    ]
    assert detect_patch_loop(hist, k=3) is None


# --------------------------------------------------------------------------- #
# Undo: restored views never count as hits; undo cooldown.                     #
# --------------------------------------------------------------------------- #


def test_undo_restored_view_never_scores_a_hit() -> None:
    # PIN of step4_1 resume Tree_0_1 t17: accepted commit created fp X (t9);
    # two text-equal rejects re-rendered it (t10/t11); an undo_last_step then
    # RESTORED the same view — the audited code counted that as the 4th
    # recurrence AND let the undo re-arm the latch in the same turn, firing at
    # the exact moment the agent was deliberately backtracking. Must be silent
    # on the undo turn AND the turn right after (cooldown).
    X = lambda: _goal_view("poly_out", 11)  # noqa: E731
    hist = [
        _commit(X(), "move=> _; split."),
        _commit(X(), "move=> _; split.", ok=True, errored=True),   # text-equal
        _commit(X(), "move=> _; split.", ok=False, errored=True),  # rejected
        record_from(X(), intent="undo_last_step", tactic="", ok=True, errored=False),
    ]
    assert detect_patch_loop(hist, k=3) is None
    # ... and even with enough real arrivals in the window, the undo turn and
    # its successor are cooled down.
    loop = _osc_loop(3)
    assert detect_patch_loop(loop, k=3) is not None
    cooled = loop + [record_from(
        _goal_view("LOOP-A", 5), intent="undo_to_checkpoint", tactic="",
        ok=True, errored=False)]
    assert detect_patch_loop(cooled, k=3) is None  # the undo turn itself
    cooled.append(_readonly(_goal_view("LOOP-A", 5)))
    assert detect_patch_loop(cooled, k=3) is None  # the turn right after


def test_undo_cooldown_covers_all_four_rewind_intents() -> None:
    loop = _osc_loop(3)
    for intent in ("undo_last_step", "request_restart", "undo_to_checkpoint",
                   "fresh_restart"):
        hist = loop + [record_from(
            _goal_view("LOOP-A", 5), intent=intent, tactic="", ok=True, errored=False)]
        assert detect_patch_loop(hist, k=3) is None, intent


# --------------------------------------------------------------------------- #
# Hard-silence guards: terminal/closed views; unknown frontier.                #
# --------------------------------------------------------------------------- #


def _terminal_view(kind: str) -> dict:
    prompt = next_loop_prompt()
    v = {
        "current_goal": {"lines": ["No more goals", f"[{prompt}|check]>"]},
        "proof_status": {"remaining_goals": None, "remaining_goals_known": False},
    }
    if kind == "status":
        v["current_goal"]["lines"] = ["weird rendering", f"[{prompt}|check]>"]
        v["proof_status"]["status"] = "candidate_closed_pending_qed"
    elif kind == "layer":
        v["current_goal"]["lines"] = ["weird rendering", f"[{prompt}|check]>"]
        v["proof_status"]["current_layer"] = "closed_candidate"
    return v


def test_terminal_guard_hard_silences_closed_views() -> None:
    # PIN of step4_badi scratch r2_r2 t4 / resume Tree_0_1 t4: the audited code
    # told an agent staring at `No more goals` that it was in "a patch loop,
    # not progress". Terminal views are hard-silenced even if (synthetically)
    # reached by accepted arrivals with departures.
    for kind in ("goal", "status", "layer"):
        hist = []
        for i in range(3):
            if i:
                hist.append(_commit(_goal_view("AWAY", 4), "auto."))
            hist.append(_commit(_terminal_view(kind), "smt()."))
        # give the window >= 2 non-None remaining samples so ONLY the terminal
        # guard is what silences it.
        hist.insert(0, _commit(_goal_view("PRE", 5), "sp."))
        assert detect_patch_loop(hist, k=3) is None, kind


def test_unknown_frontier_guard_fewer_than_two_samples() -> None:
    # PIN of badi resume Tree_0_1 t4 gate bypass: win_rems=[1] (single non-None
    # sample) slipped through the old half-split gate. < 2 non-None samples in
    # the window now hard-silences.
    hist = [_commit(_goal_view("ONLY-SAMPLE", 1), "trivial.")]
    for i in range(3):
        if i:
            hist.append(_commit(_goal_view("AWAY", None), "auto."))
        hist.append(_commit(_goal_view("LOOP-A", None), "smt()."))
    assert detect_patch_loop(hist, k=3) is None


def test_unknown_remaining_renders_unknown_not_unchanged() -> None:
    # When the loop is real but the CURRENT remaining is None, the banner must
    # not claim anything was "unchanged" (unknown != unchanged).
    hist = []
    for i in range(3):
        if i:
            hist.append(_commit(_goal_view("AWAY-B", 4 + i), "auto."))
        hist.append(_commit(_goal_view("LOOP-A", None), "smt()."))
    flag = detect_patch_loop(hist, k=3)
    assert flag is not None
    assert flag["remaining"] == "unknown"
    assert "unchanged" not in flag["text"]
    assert "unchanged" not in str(flag["remaining"])


# --------------------------------------------------------------------------- #
# Floor-between-arrivals gate.                                                 #
# --------------------------------------------------------------------------- #


def test_floor_gate_silent_while_floor_improves_between_returns() -> None:
    # Each excursion between arrivals reaches a strictly LOWER floor (4 then 3):
    # the agent converts every round-trip into net progress -> silent.
    hist = [
        _commit(_goal_view("LOOP-A", 5), "smt()."),
        _commit(_goal_view("MID", 4), "auto."),
        _commit(_goal_view("LOOP-A", 5), "smt()."),
        _commit(_goal_view("LOW", 3), "auto."),
        _commit(_goal_view("LOOP-A", 5), "smt()."),
    ]
    assert detect_patch_loop(hist, k=3) is None
    # Flat floors (4 then 4) -> the round-trips stopped paying -> fires.
    hist2 = [
        _commit(_goal_view("LOOP-A", 5), "smt()."),
        _commit(_goal_view("MID", 4), "auto."),
        _commit(_goal_view("LOOP-A", 5), "smt()."),
        _commit(_goal_view("MID", 4), "auto."),
        _commit(_goal_view("LOOP-A", 5), "smt()."),
    ]
    assert detect_patch_loop(hist2, k=3) is not None


def test_floor_gate_ignores_legal_remaining_rises() -> None:
    # PIN of step4_badi scratch Tree_0_1_r2 t23: a legal `seq`/`case`/`rcondt`
    # split RAISES remaining; the old window-half floor split read the rise as
    # "no net progress" and fired. The new gate compares per-excursion MINIMA
    # between same-fp arrivals, so rises never enter the comparison: here every
    # excursion rises to 9 but the floors still improve (7 then 6) -> silent.
    hist = [
        _commit(_goal_view("LOOP-A", 8), "smt()."),
        _commit(_goal_view("SPLIT-UP", 9), "case (b)."),     # legal expansion
        _commit(_goal_view("WORK", 7), "auto."),
        _commit(_goal_view("LOOP-A", 8), "smt()."),
        _commit(_goal_view("SPLIT-UP2", 9), "rcondt{1} 2."),  # legal expansion
        _commit(_goal_view("WORK2", 6), "auto."),
        _commit(_goal_view("LOOP-A", 8), "smt()."),
    ]
    assert detect_patch_loop(hist, k=3) is None


# --------------------------------------------------------------------------- #
# REAL-DATA regression: the step4_1 resume Tree_0_0 trace (86 per-turn views). #
# The macro-cycle: ~10 distinct fingerprints rotate with period ~10-11, every  #
# member re-reached by an ACCEPTED commit once per cycle. Under the rewritten  #
# semantics the first fingerprint to accumulate 3 separated accepted arrivals  #
# inside one window is `a65452cb` (the rem=3 cycle-floor goal, arrivals at     #
# t12/t24/t34) -> single latched fire at turn 34, inside the SPEC target range #
# t27-t49. (The audited pre-rewrite code fired at t27 via a rejected-commit    #
# filler hit on `fff72630` — hits 15/16(rejected)/27.)                         #
# --------------------------------------------------------------------------- #

_FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__), "fixtures", "step4_1_patch_loop_views"
)
# The LoopMonitor window for the step4_1 loop (see LoopMonitor / _MANAGER_WINDOW).
_MANAGER_WINDOW = 24
# The single latched fire on the real trace under the rewritten semantics.
_REAL_FIRE_TURN = 34
_REAL_FIRE_FP = "a65452cb126112b5"


def _load_real_turns() -> list[dict]:
    paths = sorted(glob.glob(os.path.join(_FIXTURE_DIR, "turn_*.json")))
    assert paths, f"missing real-data fixture under {_FIXTURE_DIR}"
    return [json.load(open(p)) for p in paths]


def _record_real_turn(view: dict) -> TurnRecord:
    """Build a TurnRecord from a real view exactly as the manager would: intent,
    tactic, ok and errored come from the view's `last_result` (the action that
    produced this view)."""
    lr = view.get("last_result") or {}
    intent = lr.get("intent") or ""
    tactic = lr.get("tactic") or (lr.get("payload") or {}).get("tactic") or ""
    result_text = (lr.get("result") or "").lower()
    errored = "rejected" in result_text or "error" in result_text
    ok = intent == "commit_tactic" and not errored
    return record_from(view, intent=intent, tactic=tactic, ok=ok, errored=errored)


def test_REAL_step4_1_trace_fires_patch_loop() -> None:
    # Replay the real 86-turn trace through detect_patch_loop with the manager's
    # window. The cycle-floor goal `a65452cb` (remaining: 3) is re-reached by an
    # accepted commit once per macro-cycle (t12/t24/t34); its 3rd separated
    # accepted arrival inside one window must FIRE at turn 34 (t27-t49 per spec).
    turns = _load_real_turns()
    assert len(turns) == 86

    # Sanity: the fixture really does preserve the volatile `[NNN|check]>` prompt
    # and the recurring goal — turns 60/70/80 differ ONLY in that prompt index, so
    # the stripped fingerprint collapses them to one while the RAW lines differ.
    import re as _re

    prompt_re = _re.compile(r"^\[\d+\|\w+\]>$")
    for n in (60, 70, 80):
        lines = turns[n]["current_goal"]["lines"]
        assert any(prompt_re.match(str(l).strip()) for l in lines), n
    assert (
        render_fingerprint(turns[60])
        == render_fingerprint(turns[70])
        == render_fingerprint(turns[80])
    )
    # A genuinely different goal stays distinct.
    assert render_fingerprint(turns[65]) != render_fingerprint(turns[80])

    history: list[TurnRecord] = []
    first_fire = None
    for n, view in enumerate(turns):
        history.append(_record_real_turn(view))
        flag = detect_patch_loop(history, window=_MANAGER_WINDOW)
        if flag is not None and first_fire is None:
            first_fire = (n, flag)

    assert first_fire is not None, "detector DEAD on real step4_1 trace"
    fire_turn, flag = first_fire
    assert fire_turn == _REAL_FIRE_TURN
    assert 27 <= fire_turn <= 49  # SPEC-B target range (macro-cycle rounds 2-4)
    assert flag["fingerprint"] == _REAL_FIRE_FP
    assert flag["key"] == DECISION_CONTEXT_KEY == "local_patch_loop"
    assert flag["recurrences"] >= 3
    assert flag["remaining"] == 3
    assert flag["certified"] is False
    assert isinstance(flag["fingerprint"], str) and flag["fingerprint"]


def test_REAL_step4_1_audited_FP_turn27_now_silent() -> None:
    # The audited pre-rewrite headline fire at t27 (fp fff72630, hits
    # 15/16/27 with t16 a REJECTED commit) violated even the old docstring:
    # the rejected filler hit is exactly what the rewrite removes. Turn 27
    # must now be silent on both the pure and manager paths.
    turns = _load_real_turns()
    history: list[TurnRecord] = []
    for view in turns[:28]:
        history.append(_record_real_turn(view))
    assert detect_patch_loop(history, window=_MANAGER_WINDOW) is None


def test_REAL_step4_1_trace_is_DEAD_under_old_logic() -> None:
    # Pin the defect: with the OLD window (8), the loop period (~10-11) exceeds the
    # window so < k accepted arrivals ever co-occur and the detector NEVER fires —
    # exactly the audit's "0 fires" finding. (Defect 1 is pinned separately by the
    # render_fingerprint tests above.) This documents WHY window=8 was dead and
    # would catch a regression that shrank the window back below the loop period.
    turns = _load_real_turns()
    history: list[TurnRecord] = []
    fired = False
    for view in turns:
        history.append(_record_real_turn(view))
        if detect_patch_loop(history, window=8) is not None:
            fired = True
            break
    assert not fired, "window=8 should be too small to span 3 accepted arrivals"


# --------------------------------------------------------------------------- #
# LoopMonitor EPISODE-LATCH harness. `detect_patch_loop` is a PURE function and  #
# re-fires on every later accepted re-arrival; LoopMonitor collapses one loop     #
# episode to ONE banner. These exercise the exact LoopMonitor.inject path (the    #
# stateful surface ProofNodeManager delegates to per turn).                       #
# --------------------------------------------------------------------------- #


class _Intent:
    def __init__(self, intent: str, tactic: str) -> None:
        self.intent = intent
        self.payload = {"tactic": tactic} if tactic else {}


class _ManagedTurn:
    def __init__(self, view: dict, intent: str, tactic: str, ok: bool, errored: bool):
        self.workspace_view = view
        self.intent = _Intent(intent, tactic)
        self.ok = ok
        self.manager_actions = (
            [{"error_summary": "rejected"}] if errored else [{"label": "ok"}]
        )


def _fresh_manager():
    """A fresh LoopMonitor (the unit under test) sized to the step4_1 window; its
    defaults (armed, empty episode-set, rearm_after=2) match the old shell."""
    from workflow.proof_management import LoopMonitor

    return LoopMonitor(window=_MANAGER_WINDOW)


def _drive(mgr, view: dict, intent: str, tactic: str, ok: bool, errored: bool):
    """Push one turn through the LoopMonitor inject path; return the banner or None."""
    result = _ManagedTurn(dict(view), intent, tactic, ok, errored)
    mgr.inject(result)
    dc = result.workspace_view.get("decision_context") or {}
    return dc.get("local_patch_loop")


def _drive_real(mgr, view: dict):
    lr = view.get("last_result") or {}
    intent = lr.get("intent") or ""
    tactic = lr.get("tactic") or (lr.get("payload") or {}).get("tactic") or ""
    result_text = (lr.get("result") or "").lower()
    errored = "rejected" in result_text or "error" in result_text
    ok = intent == "commit_tactic" and not errored
    return _drive(mgr, view, intent, tactic, ok, errored)


def _drive_osc_loop(mgr, loop_label: str, away_label: str, *, arrivals: int = 3,
                    loop_rem: int = 5, away_rem: int = 4):
    """Drive the genuine arrive-leave-arrive loop through the manager; return
    the banners that surfaced."""
    flags = drive_osc_loop(
        lambda view, tactic: _drive(mgr, view, "commit_tactic", tactic, True, False),
        make_loop_view=lambda: _goal_view(loop_label, loop_rem),
        make_away_view=lambda: _goal_view(away_label, away_rem),
        arrivals=arrivals,
    )
    return [f for f in flags if f is not None]


def test_REAL_step4_1_via_manager_inject_path() -> None:
    # Exercise the exact LoopMonitor.inject path (what the manager delegates to
    # per turn), not just the bare detector, so a wiring regression is also caught.
    mgr = _fresh_manager()
    turns = _load_real_turns()
    fired_at = None
    for n, view in enumerate(turns):
        flag = _drive_real(mgr, view)
        if flag is not None and fired_at is None:
            fired_at = (n, flag)

    assert fired_at is not None, "manager inject path DEAD on real step4_1 trace"
    n, flag = fired_at
    assert n == _REAL_FIRE_TURN
    assert flag["fingerprint"] == _REAL_FIRE_FP
    assert flag["recurrences"] >= 3
    assert flag["certified"] is False


def test_REAL_step4_1_fires_exactly_once_per_episode() -> None:
    # HEADLINE regression lock: through the manager episode latch the real
    # 86-turn trace must surface the PATCH-LOOP banner on EXACTLY ONE turn —
    # turn 34, fingerprint a65452cb, inside the SPEC range t27-t49 — even though
    # the PURE detector re-fires on ~48 accepted re-arrivals.
    #
    # Round-2 (F1) NOTE: the same persisting episode now also earns EXACTLY ONE
    # *escalation* banner (kind="escalation") ~22 turns later (t56, inside the
    # F1 spec window t54-t65). That is a distinct, intentional second banner —
    # the patch-loop first-fire uniqueness at t34 is unchanged and still pinned
    # below; the escalation is separated out so it is not mistaken for a
    # spurious patch-loop re-fire.
    mgr = _fresh_manager()
    turns = _load_real_turns()
    fires = [
        (n, flag) for n, view in enumerate(turns) if (flag := _drive_real(mgr, view))
    ]
    loop_fires = [(n, f) for n, f in fires if (f.get("kind") or "loop") != "escalation"]
    esc_fires = [(n, f) for n, f in fires if f.get("kind") == "escalation"]

    # patch-loop first-fire: EXACTLY ONE, at t34 (unchanged headline pin).
    assert len(loop_fires) == 1, \
        f"expected exactly 1 patch-loop fire, got {[n for n, _ in loop_fires]}"
    n, flag = loop_fires[0]
    assert n == _REAL_FIRE_TURN
    assert 27 <= n <= 49
    assert flag["fingerprint"] == _REAL_FIRE_FP
    assert flag["recurrences"] >= 3
    assert flag["remaining"] == 3

    # F1 escalation: EXACTLY ONE, inside the spec window t54-t65 (observed t56).
    assert len(esc_fires) == 1, \
        f"expected exactly 1 escalation, got {[n for n, _ in esc_fires]}"
    esc_n, _ = esc_fires[0]
    assert 54 <= esc_n <= 65


def test_REAL_step4_1_fires_exactly_once_FAILS_under_always_fire_logic() -> None:
    # Pin the defect this latch closes: WITHOUT the episode latch the pure
    # detector fires on every later accepted re-arrival of every cycle member
    # (~48 turns on this trace), not 1. The "exactly once" invariant is provided
    # by the manager latch, NOT the detector.
    turns = _load_real_turns()
    history: list[TurnRecord] = []
    pure_fires = 0
    for view in turns:
        history.append(_record_real_turn(view))
        if detect_patch_loop(history, window=_MANAGER_WINDOW) is not None:
            pure_fires += 1
    assert pure_fires > 1


def test_REAL_step4_1_suppressed_after_first_fire() -> None:
    # Turns 35-85 carry NO *patch-loop* banner — the macro-cycle keeps rotating
    # inside the captured accepted loop-set, and the lone turn-77 `conseq` blip
    # is a 1-turn excursion (escape needs >= 2 accepted out-of-set commits).
    #
    # Round-2 (F1) NOTE: the ONLY banner allowed in t35-85 is the single
    # intentional *escalation* (kind="escalation") at t56 — the persisting
    # episode's second-and-final banner. Patch-loop suppression after the first
    # fire is unchanged; we just permit that one escalation instead of asserting
    # blanket None.
    mgr = _fresh_manager()
    turns = _load_real_turns()
    banners = [_drive_real(mgr, view) for view in turns]
    assert banners[_REAL_FIRE_TURN] is not None
    assert (banners[_REAL_FIRE_TURN].get("kind") or "loop") != "escalation"
    escalations = []
    for n in range(_REAL_FIRE_TURN + 1, 86):
        b = banners[n]
        if b is None:
            continue
        # No patch-loop re-fire is permitted; only the lone escalation may show.
        assert b.get("kind") == "escalation", \
            f"spurious patch-loop re-fire at turn {n}: {b.get('kind')}"
        escalations.append(n)
    assert len(escalations) == 1, f"expected exactly 1 escalation, got {escalations}"
    assert 54 <= escalations[0] <= 65
    assert banners[78] is None  # explicit post-blip guard (no patch-loop here)


def test_rearm_blip_does_not_refire() -> None:
    # A genuine loop fires once. ONE accepted off-loop-set commit followed by a
    # return must NOT re-arm (escape_run 1 < R=2); TWO consecutive accepted
    # off-loop-set commits DO re-arm, and a NEW re-formed loop fires again.
    mgr = _fresh_manager()
    assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
    # one accepted off-loop-set commit, then back into the captured loop:
    _drive(mgr, _goal_view("BLIP", 6), "commit_tactic", "conseq (_: _ ==> true).", True, False)
    refire = _drive_osc_loop(mgr, "LOOP-A", "AWAY-B")
    assert not refire, "1-commit blip must NOT re-arm (R=2)"

    mgr2 = _fresh_manager()
    assert len(_drive_osc_loop(mgr2, "LOOP-A", "AWAY-B")) == 1
    # TWO consecutive accepted off-loop-set commits -> genuine escape -> re-arm.
    _drive(mgr2, _goal_view("ESC-1", 6), "commit_tactic", "conseq (_: _ ==> true).", True, False)
    _drive(mgr2, _goal_view("ESC-2", 7), "commit_tactic", "sp.", True, False)
    refire2 = _drive_osc_loop(mgr2, "LOOP-C", "AWAY-D")
    assert refire2, "2-commit escape must re-arm -> new episode fires"


def test_rearm_requires_accepted_commits_not_parked_rejections() -> None:
    # PIN of step4_badi scratch t13 (double fire on one thrash): after a fire,
    # ONE accepted commit lands on a new frozen fingerprint and the agent then
    # THRASHES with rejected commits parked on that same fingerprint. The
    # audited any-turn escape counter hit R=2 there and re-armed mid-thrash;
    # rejected turns must NOT advance the escape run.
    #
    # Round-2 (F2) NOTE: those parked rejected commits are exactly the
    # rejected-thrash texture (>= 3 consecutive rejected commit_tactic on the
    # same fingerprint), so the *new* `rejected_thrash` signal intentionally
    # fires on the 3rd consecutive rejection. The original intent of THIS test —
    # the parked rejections must NOT re-arm or re-fire the PATCH-LOOP episode
    # latch — is fully preserved and pinned below; we only stop asserting a
    # blanket None and instead separate out the intentional rejected_thrash.
    mgr = _fresh_manager()
    assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
    flags = [
        _drive(mgr, _goal_view("FROZEN-NEW", 4), "commit_tactic", "auto.", True, False),
        _drive(mgr, _goal_view("FROZEN-NEW", 4), "commit_tactic", "smt(size_ge0).", False, True),
        _drive(mgr, _goal_view("FROZEN-NEW", 4), "commit_tactic", "smt(size_ge0 size_eq0).", False, True),
        _drive(mgr, _goal_view("FROZEN-NEW", 4), "commit_tactic", "auto; smt().", False, True),
    ]
    # No PATCH-LOOP banner may surface from the parked rejections (the latch
    # must not re-arm on rejected turns) — the only allowed banner is the
    # intentional F2 rejected_thrash on the 3rd consecutive rejection.
    for i, f in enumerate(flags):
        if f is None:
            continue
        assert f.get("kind") == "rejected_thrash", \
            f"unexpected non-thrash banner at flag[{i}]: {f.get('kind')}"
    assert not mgr._armed, "loop episode latch must stay disarmed"
    # the latch is still disarmed: returning into the old loop stays silent.
    assert not _drive_osc_loop(mgr, "LOOP-A", "AWAY-B")


def test_rearm_on_restructure_then_refire() -> None:
    # A loop fires once; a game-pair restructure (`call`) re-arms the latch
    # immediately; a NEW re-formed loop fires again.
    mgr = _fresh_manager()
    assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
    _drive(mgr, _goal_view("POST-CALL", 6), "commit_tactic",
           "call (_: UFCMA.bad1, ={log}).", True, False)
    assert _drive_osc_loop(mgr, "LOOP-C", "AWAY-D"), "`call` restructure must re-arm"


def test_rearm_on_all_rewind_intents_with_cooldown() -> None:
    # All four production rewind/restart intents re-arm the latch — including
    # `undo_to_checkpoint` and `fresh_restart`, which the audited code missed
    # (real runs rewound exclusively via undo_to_checkpoint: badi scratch
    # T0_0 t31, T0_1 t15/t40, T0_1_r2 t39). The undo turn itself and the next
    # turn are cooled down; a genuinely NEW loop afterwards fires.
    for intent in ("undo_last_step", "request_restart", "undo_to_checkpoint",
                   "fresh_restart"):
        mgr = _fresh_manager()
        assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
        f = _drive(mgr, _goal_view("LOOP-A", 5), intent, "", True, False)
        assert f is None, f"{intent} turn itself must not carry a banner"
        assert mgr._armed, f"{intent} must re-arm the latch"
        f = _drive(mgr, _goal_view("LOOP-A", 5), "inspect_context", "", True, False)
        assert f is None, "turn right after the rewind is cooled down"
        assert _drive_osc_loop(mgr, "LOOP-C", "AWAY-D"), \
            f"new loop after {intent} re-arm must fire"


def test_rearm_vocab_does_not_rebanner_recovering_agent() -> None:
    # PIN of the badi-resume counterfactual (4 -> 9 fires when ONLY the vocab
    # was widened on the old semantics): after a fire, a recovery sequence of
    # undo_to_checkpoint / fresh_restart / inspect turns that keeps re-rendering
    # the SAME frozen fingerprint must produce ZERO further banners — re-arming
    # is fine, but a hit needs an accepted re-arrival, which recovery turns
    # cannot provide.
    mgr = _fresh_manager()
    assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
    frozen = lambda: _goal_view("LOOP-A", 5)  # noqa: E731
    recovery = [
        ("undo_to_checkpoint", "", True, False),
        ("inspect_context", "", True, False),
        ("fresh_restart", "", True, False),
        ("inspect_context", "", True, False),
        ("commit_tactic", "smt().", False, True),   # rejected retry
        ("undo_to_checkpoint", "", True, False),
        ("inspect_context", "", True, False),
    ]
    flags = [_drive(mgr, frozen(), *args) for args in recovery]
    assert all(f is None for f in flags), "recovery turns must never be re-banner'd"


# --------------------------------------------------------------------------- #
# Banner coupling. The bare detector emits the NEUTRAL banner; the manager      #
# swaps in the call-aware tail ONLY when the up-to-bad-call signal is           #
# independently active for the same frontier. Anchored on the REAL shapes:      #
#   - step4_badi smt(size_ge0) thrash frontier (bare `=> badi` post): NEUTRAL.   #
#   - step4_1 up-to-bad frontier (post `\/ bad` + offered call): call-aware.     #
# --------------------------------------------------------------------------- #

_BADI_PROMPT = [600]


def _badi_view(remaining: int, marker: str) -> dict:
    """A step4_badi-shaped frontier: post is the BARE consequent `=> badi{2}`
    (NO `\\/` — not up-to-bad), with a multi-glob lockstep `call (_: ...)`
    OFFERED. `up_to_bad_names` returns ∅ on this, so the manager must keep the
    banner NEUTRAL even though a call move is on offer. ``marker`` varies the
    goal so the loop can genuinely leave and return."""
    _BADI_PROMPT[0] += 3
    return {
        "current_goal": {
            "lines": [
                f"Current goal (remaining: {remaining})",
                "",
                f"pre = ={{glob A}} /\\ i0{{2}} = nth0 /\\ {marker}",
                "",
                "forged <@ M.f()  (1---)  x <- 0",
                "",
                "post =",
                "  (let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) =>",
                "  UFCMA_li.badi{2}",
                f"[{_BADI_PROMPT[0]}|check]>",
            ],
            "view_focus": "call_site",
        },
        "proof_status": {"remaining_goals": remaining, "current_layer": "call_site"},
        "decision_context": {
            "proof_options": [
                {
                    "title": "Invariant-call",
                    "tactic": (
                        "call (_: ={glob BNR, glob ROIN.RO, UFCMA.cbad1, "
                        "Mem.log})."
                    ),
                }
            ]
        },
    }


def test_patch_loop_banner_neutral_without_up_to_bad() -> None:
    # step4_badi smt(size_ge0)-thrash shape: a genuine arrive-leave-arrive loop
    # on a frontier whose post is the BARE `=> badi` consequent (NOT up-to-bad),
    # even with a call OFFERED. The banner must be NEUTRAL — no "re-issue your
    # `call`" / up-to-bad text.
    mgr = _fresh_manager()
    seq = []
    for i in range(3):
        if i:
            seq.append(_drive(mgr, _badi_view(3, "ELSEWHERE"), "commit_tactic",
                              "auto.", True, False))
        seq.append(_drive(mgr, _badi_view(4, "THE-LOOP-GOAL"), "commit_tactic",
                          "smt(size_ge0).", True, False))
    fires = [f for f in seq if f is not None]
    assert len(fires) == 1, "the step4_badi-shaped loop must fire exactly once"
    flag = fires[0]
    assert "patch loop, not progress" in flag["text"]
    # NEUTRAL: no call / up-to-bad text.
    assert "re-issue your `call`" not in flag["text"]
    assert "up-to-bad" not in flag["text"]
    assert "reconsider the structural tactic that produced this frontier" in flag["text"]


def test_patch_loop_banner_call_aware_with_up_to_bad() -> None:
    # step4_1 up-to-bad frontier: the same genuine loop, but the view's
    # decision_context carries `up_to_bad_call` (as the pure-view enrichment
    # writes on this real shape). The manager then appends the call-aware tail.
    mgr = _fresh_manager()

    def s41_view(label: str, remaining: int) -> dict:
        v = _goal_view(label, remaining)
        v["decision_context"] = {
            "up_to_bad_call": {
                "active_bad_events": ["UFCMA.bad1", "UFCMA.bad2"],
                "certified": False,
                "text": "Upstream postcondition admits `\\/ UFCMA.bad1`; ...",
            }
        }
        return v

    seq = []
    for i in range(3):
        if i:
            seq.append(_drive(mgr, s41_view("AWAY", 4), "commit_tactic",
                              "auto.", True, False))
        seq.append(_drive(mgr, s41_view("LOOP", 5), "commit_tactic",
                          "conseq (_: _ ==> UFCMA.bad1).", True, False))
    fires = [f for f in seq if f is not None]
    assert len(fires) == 1
    flag = fires[0]
    assert "patch loop, not progress" in flag["text"]
    # CALL-AWARE: the up-to-bad call tail is present.
    assert "re-issue your `call` in up-to-bad form" in flag["text"]


def test_patch_loop_banner_call_aware_via_frontier_fallback() -> None:
    # Even if the enrichment key is NOT on the view, the manager's independent
    # frontier check (`_up_to_bad_frontier`) detects the up-to-bad shape + offered
    # lockstep call and still surfaces the call-aware tail.
    mgr = _fresh_manager()
    _S41_PROMPT = [700]

    def s41_shape_view(marker: str, remaining: int) -> dict:
        _S41_PROMPT[0] += 3
        return {
            "current_goal": {
                "lines": [
                    f"Current goal (remaining: {remaining})",
                    "",
                    f"pre = ={{glob A}} /\\ {marker}",
                    "",
                    "forged <@ M.f()  (1---)  x <- 0",
                    "",
                    "post = forged{1} => forged{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2}",
                    f"[{_S41_PROMPT[0]}|check]>",
                ],
                "view_focus": "call_site",
            },
            "proof_status": {"remaining_goals": remaining, "current_layer": "call_site"},
            "decision_context": {
                "proof_options": [
                    {"title": "Invariant-call", "tactic": "call (_: ={glob UFCMA} /\\ ={UFCMA.log})."}
                ]
            },
        }

    seq = []
    for i in range(3):
        if i:
            seq.append(_drive(mgr, s41_shape_view("AWAY", 4), "commit_tactic",
                              "auto.", True, False))
        seq.append(_drive(mgr, s41_shape_view("LOOP", 5), "commit_tactic",
                          "conseq (_: _ ==> b).", True, False))
    fires = [f for f in seq if f is not None]
    assert len(fires) == 1
    assert "re-issue your `call` in up-to-bad form" in fires[0]["text"]


# --------------------------------------------------------------------------- #
# Round-2 F2 — `rejected_thrash` (kind on the same key). The narrow bypass for #
# the badi-scratch Tree_0_1_r2 t33-t39 stuck-to-abandonment texture: >= 3      #
# STRICTLY CONSECUTIVE rejected commits parked on one fingerprint, with a      #
# repeated tactic head, no restructure attempt, non-terminal. Empirically      #
# tuned on all six audited bundles (see _fix_catch2fix_replay.py): fires =     #
# badi scratch r2 t36 (the must-fire) + Tree_0_1 t14 + a held-out MAC corpus   #
# run's c0/Tree_0_1_1 t35; UFCMA / badi resume / both step4_1 runs: zero.      #
# --------------------------------------------------------------------------- #

from workflow.patch_loop_detector import detect_rejected_thrash  # noqa: E402


def _rej(view: dict, tactic: str) -> TurnRecord:
    return _commit(view, tactic, ok=False, errored=True)


def _badi_r2_thrash_run() -> list[TurnRecord]:
    """The REAL must-fire shape (badi scratch Tree_0_1_r2 t33-t36): accepted
    `skip; smt().` creates the goal, then sim. / auto; smt(). / auto => />;
    smt(...) are rejected in three consecutive turns on the same fingerprint
    (heads sim/auto/auto — `auto` repeats)."""
    G = lambda: _goal_view("BADI-R2-GOAL", 6)  # noqa: E731
    return [
        _commit(G(), "skip; smt()."),
        _rej(G(), "sim."),
        _rej(G(), "auto; smt()."),
        _rej(G(), "auto => />; smt(domE get_setE mem_set)."),
    ]


def test_thrash_fires_on_third_consecutive_reject_badi_shape() -> None:
    hist = _badi_r2_thrash_run()
    flag = detect_rejected_thrash(hist)
    assert flag is not None
    assert flag["key"] == DECISION_CONTEXT_KEY  # same panel key (render survival)
    assert flag["kind"] == "rejected_thrash"
    assert flag["rejections"] == 3
    assert flag["certified"] is False
    assert "NOT a verdict and NOT a gate" in flag["guarantee"]
    # Neutral text, DISTINCT from the patch-loop wording.
    text = flag["text"]
    assert "rejected at this same goal" in text
    assert "Already-tried" in text
    assert "different tactic family" in text
    assert "patch loop" not in text
    assert "re-issue your `call`" not in text


def test_thrash_silent_below_k_ufcma_pair() -> None:
    # UFCMA t3/t4: two consecutive rejects are below threshold.
    hist = _badi_r2_thrash_run()[:-1]
    assert detect_rejected_thrash(hist) is None


def test_thrash_exactly_k_is_the_episode_latch() -> None:
    # Fires ONLY on the 3rd rejection; the 4th/5th stay silent (run length 4/5
    # \!= 3) — one banner per thrash episode with no manager state.
    hist = _badi_r2_thrash_run()
    assert detect_rejected_thrash(hist) is not None
    hist.append(_rej(_goal_view("BADI-R2-GOAL", 6), "auto; smt(size_ge0)."))
    assert detect_rejected_thrash(hist) is None
    hist.append(_rej(_goal_view("BADI-R2-GOAL", 6), "auto."))
    assert detect_rejected_thrash(hist) is None


def test_thrash_rearms_after_a_genuine_break() -> None:
    # An accepted commit breaks the run; a re-formed 3-run can fire again
    # (a NEW thrash episode).
    hist = _badi_r2_thrash_run()
    assert detect_rejected_thrash(hist) is not None
    hist.append(_commit(_goal_view("NEW-GOAL", 5), "wp."))
    for t in ("smt(a).", "smt(a b).", "smt(a b c)."):
        hist.append(_rej(_goal_view("NEW-GOAL", 5), t))
    assert detect_rejected_thrash(hist) is not None


def test_thrash_inspect_breaks_the_run() -> None:
    # Inspect-interleaved friction from a held-out MAC corpus run
    # (c1/Tree_0_0_0 t5-t9, c1/Tree_0_0 t55-t59): an agent that inspects
    # between rejections is gathering information, not blind-retrying.
    # Read-only turns BREAK the run.
    G = lambda: _goal_view("MAC-GOAL", 7)  # noqa: E731
    hist = [
        _commit(G(), "case: (c \\in Mem.log) => Hcm."),
        _rej(G(), "split; first exact Hd1. split."),
        _readonly(G()),
        _rej(G(), "split; first exact Hd1."),
        _readonly(G()),
        _rej(G(), "split; move=> Hro."),
    ]
    assert detect_rejected_thrash(hist) is None


def test_thrash_accepted_and_probe_and_gated_qed_break_the_run() -> None:
    G = lambda: _goal_view("GOAL-X", 7)  # noqa: E731
    base = [_rej(G(), "smt(a)."), _rej(G(), "smt(b).")]
    # accepted commit between -> the third reject starts a NEW run of 1
    hist = base + [_commit(G(), "wp."), _rej(G(), "smt(c).")]
    assert detect_rejected_thrash(hist) is None
    # rejected PROBE between -> breaks too (probing = reversible exploration)
    probe = record_from(G(), intent="probe_tactic", tactic="auto.",
                        ok=False, errored=True)
    hist = base + [probe, _rej(G(), "smt(c).")]
    assert detect_rejected_thrash(hist) is None
    # gated qed (ok=False, errored=False — NOT an EC reject) neither counts
    # as a rejection nor extends the run
    gated = _commit(G(), "qed.", ok=False, errored=False)
    hist = base + [gated, _rej(G(), "smt(c).")]
    assert detect_rejected_thrash(hist) is None
    assert detect_rejected_thrash(base + [gated]) is None


def test_thrash_all_distinct_heads_stays_silent() -> None:
    # A held-out MAC corpus run's c2/Tree_0_2 t7-t9 (`wp.` / `if.` / `sp.`)
    # and c0/Tree_0_1_0_0 t8-t10 (`move=> />.` / `wp.` / `if.`): stepping
    # through DIFFERENT program-structure levers is not thrash.
    G = lambda: _goal_view("MAC-T02", 8)  # noqa: E731
    hist = [_rej(G(), "wp."), _rej(G(), "if."), _rej(G(), "sp.")]
    assert detect_rejected_thrash(hist) is None
    # ... whereas a repeated head among the three fires (badi Tree_0_1
    # t12-t14: move=>/smt/move=> with the move=> head repeating).
    hist2 = [
        _rej(G(), "move=> &1 &2 /=; smt(size_ge0)."),
        _rej(G(), "smt(size_ge0 size_eq0)."),
        _rej(G(), "move=> &1 &2; smt(size_ge0 size_eq0)."),
    ]
    assert detect_rejected_thrash(hist2) is not None


def test_thrash_restructure_attempts_stay_silent() -> None:
    # step4_1 scratch t25-t29 texture: rejected `call`/`byequiv` attempts mean
    # the agent is already switching routes — the opposite of thrash.
    G = lambda: _goal_view("S41-SCRATCH", 4)  # noqa: E731
    hist = [
        _rej(G(), "call (_: UFCMA.bad1, ={log})."),
        _rej(G(), "call (_: UFCMA.bad1, inv RO.m{1} RO.m{2})."),
        _rej(G(), "call (_: true)."),
    ]
    assert detect_rejected_thrash(hist) is None
    # even ONE restructure attempt inside an otherwise-thrashy run silences
    hist2 = [
        _rej(G(), "smt(a)."),
        _rej(G(), "byequiv => //."),
        _rej(G(), "smt(a b)."),
    ]
    assert detect_rejected_thrash(hist2) is None


def test_thrash_hard_silent_on_terminal_views() -> None:
    hist = [
        _rej(_terminal_view("goal"), "qed."),
        _rej(_terminal_view("goal"), "qed."),
        _rej(_terminal_view("goal"), "qed."),
    ]
    assert detect_rejected_thrash(hist) is None


def test_thrash_via_manager_inject_path_and_loop_latch_untouched() -> None:
    # The manager surfaces the thrash banner under the SAME `local_patch_loop`
    # key (kind=rejected_thrash) — the only key that survives sanitize and
    # renders in the followup — and the patch-loop episode latch state is not
    # consumed by it.
    mgr = _fresh_manager()
    G = lambda: _goal_view("BADI-R2-GOAL", 6)  # noqa: E731
    flags = [
        _drive(mgr, G(), "commit_tactic", "skip; smt().", True, False),
        _drive(mgr, G(), "commit_tactic", "sim.", False, True),
        _drive(mgr, G(), "commit_tactic", "auto; smt().", False, True),
        _drive(mgr, G(), "commit_tactic", "auto => />; smt(domE).", False, True),
    ]
    assert flags[:3] == [None, None, None]
    assert flags[3] is not None and flags[3]["kind"] == "rejected_thrash"
    assert mgr._armed, "thrash must NOT consume the loop episode latch"
    # the 4th rejection stays silent (episode latch via the EXACTLY-k rule)
    f = _drive(mgr, G(), "commit_tactic", "auto.", False, True)
    assert f is None


def test_REAL_step4_1_trace_zero_thrash_fires() -> None:
    # Regression lock from the six-bundle replay: the step4_1 resume Tree_0_0
    # macro-cycle (rejects interleaved with accepted patches) produces ZERO
    # rejected-thrash fires.
    turns = _load_real_turns()
    history: list[TurnRecord] = []
    fires = []
    for n, view in enumerate(turns):
        history.append(_record_real_turn(view))
        if detect_rejected_thrash(history) is not None:
            fires.append(n)
    assert fires == [], f"unexpected thrash fires on real trace: {fires}"


# --------------------------------------------------------------------------- #
# Round-2 F1 — episode ESCALATION. After the latched fire, if the SAME episode #
# persists (the latch never re-arms) for >= 22 further turns, the manager      #
# surfaces EXACTLY ONE stronger banner (kind=escalation), then the episode is  #
# permanently silent (cap: 2 banners per episode). Real-trace target: fire t34 #
# -> escalation t56 (spec window t54-t65), grind ran to t85.                   #
# --------------------------------------------------------------------------- #


def _drive_in_episode_turns(mgr, n: int) -> list:
    """Drive `n` turns that keep the episode alive: accepted commits cycling
    INSIDE the captured loop-set (LOOP-A / AWAY-B) — they reset the escape run
    and never re-arm, exactly the real macro-cycle shape."""
    flags = []
    for i in range(n):
        label, rem = (("LOOP-A", 5) if i % 2 == 0 else ("AWAY-B", 4))
        flags.append(_drive(mgr, _goal_view(label, rem), "commit_tactic",
                            "smt().", True, False))
    return flags


def test_escalation_fires_once_after_22_persisting_turns() -> None:
    mgr = _fresh_manager()
    assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
    flags = _drive_in_episode_turns(mgr, 21)
    assert all(f is None for f in flags), "below threshold: silent"
    esc = _drive_in_episode_turns(mgr, 1)[0]
    assert esc is not None and esc["kind"] == "escalation"
    assert esc["key"] == "local_patch_loop"
    assert esc["certified"] is False
    assert esc["turns_since_first_banner"] == 22
    # all 22 in-episode turns were accepted commits
    assert esc["accepted_since_first_banner"] == 22
    text = esc["text"]
    assert "22 turns" in text
    assert "undo_to_checkpoint" in text
    assert "structural" in text
    assert "NOT a verdict and NOT a gate" in esc["guarantee"]
    # ... and the episode is now PERMANENTLY silent (cap 2 banners/episode).
    more = _drive_in_episode_turns(mgr, 30)
    assert all(f is None for f in more), "post-escalation episode must stay silent"


def test_escalation_resets_when_episode_ends() -> None:
    # An undo re-arms the latch -> episode over -> NO escalation accrues; a NEW
    # loop episode later gets its own fresh fire + escalation budget.
    mgr = _fresh_manager()
    assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
    _drive_in_episode_turns(mgr, 10)
    _drive(mgr, _goal_view("LOOP-A", 5), "undo_to_checkpoint", "", True, False)
    assert mgr._armed
    assert mgr._turns_since_fire == 0
    assert not mgr._escalated
    # a NEW re-formed loop fires (banner 1 of the new episode) ...
    assert len(_drive_osc_loop(mgr, "LOOP-C", "AWAY-D")) == 1
    # ... and escalates after 22 more persisting turns (banner 2)
    flags = []
    for i in range(22):
        label, rem = (("LOOP-C", 5) if i % 2 == 0 else ("AWAY-D", 4))
        flags.append(_drive(mgr, _goal_view(label, rem), "commit_tactic",
                            "smt().", True, False))
    fires = [f for f in flags if f is not None]
    assert len(fires) == 1 and fires[0]["kind"] == "escalation"


def test_escalation_never_lands_on_terminal_view() -> None:
    # If the threshold turn happens to render a terminal view, the escalation
    # is deferred to the next non-terminal turn, never claimed over
    # `No more goals`.
    mgr = _fresh_manager()
    assert len(_drive_osc_loop(mgr, "LOOP-A", "AWAY-B")) == 1
    _drive_in_episode_turns(mgr, 21)
    f = _drive(mgr, _terminal_view("goal"), "inspect_context", "", True, False)
    assert f is None, "terminal view must not carry the escalation"
    f = _drive_in_episode_turns(mgr, 1)[0]
    assert f is not None and f["kind"] == "escalation"


def test_REAL_step4_1_escalation_at_t56_and_nothing_else() -> None:
    # HEADLINE round-2 regression lock on the real 86-turn trace: the latched
    # fire at t34, ONE escalation at t56 (= 22 persisting turns later, inside
    # the spec window t54-t65), zero rejected-thrash banners, nothing after.
    mgr = _fresh_manager()
    turns = _load_real_turns()
    fires = []
    for n, view in enumerate(turns):
        flag = _drive_real(mgr, view)
        if flag is not None:
            fires.append((n, flag.get("kind") or "loop", flag))
    assert [(n, k) for n, k, _ in fires] == [(34, "loop"), (56, "escalation")]
    esc = fires[1][2]
    assert 54 <= fires[1][0] <= 65
    assert esc["turns_since_first_banner"] == 22
    assert esc["accepted_since_first_banner"] >= 1
    assert "undo_to_checkpoint" in esc["text"]
