r"""Mechanism CATCH — local-patch / no-progress loop detector (flag-only).

Failure this addresses (lemma ``step4_1``): after the undischargeable lockstep
``call``, the agent ground a death-spiral of LOCAL PATCHES that is a MACRO-CYCLE,
NOT a single frozen goal. ~10-11 DISTINCT rendered fingerprints rotate with period
~11 and the whole block repeats ~7 times until timeout, never re-issuing the
``call``. The open ``remaining`` count is NOT frozen — it oscillates 7->6->5->4->3
every cycle — but the frontier FLOOR (the fewest open goals reached) hits 3 by
~turn 24 and stays flat for ~60 turns: zero NET progress. Each patch was ACCEPTED
by EC, yet the floor never moved again.

Signal (RECURRENCE SEMANTICS — rewritten after the 2026-06-09 six-sequence audit):
    Over a sliding window of recent turns for a node, compute a goal RENDER
    FINGERPRINT = hash of ``(pre, post, remaining_count, phase)`` as rendered in
    the workspace view. A fingerprint scores a HIT only when it is REACHED BY AN
    ACCEPTED, NON-ERRORED ``commit_tactic`` — and a hit after the first one counts
    only if, since the previous hit, at least one accepted commit landed on a
    DIFFERENT fingerprint (the agent genuinely LEFT this goal and came back).
    Raise ``local_patch_loop`` when the current turn is such an accepted
    re-arrival and the fingerprint has accumulated >= K (K=3) hits within the
    window, with no structural-restructure intent (``call`` / ``byequiv`` /
    ``equiv`` / ``transitivity`` — NOT ``conseq``, which keeps the same game pair)
    between the hits, and no frontier-floor improvement between returns (the
    floor-between-arrivals gate below).

    Turns that CANNOT change proof state NEVER count — neither as a hit nor as
    "leaving": read-only ``inspect_context``/``lookup_symbol`` echoes, REJECTED or
    errored commits, text-equal auto-reverted commits, repair/unhealthy turns
    (intent=None), undo checkpoint-selection menus, and gated ``qed.``/``finish``.
    (The audited pre-rewrite code counted ANY turn whose view re-rendered the same
    fingerprint, so "1 accepted commit creating the goal + 2 state-frozen turns"
    satisfied K=3 — the dominant false-positive shape: 73/74 banners across six
    audited sequences were that artifact.)

HARD-SILENCE GUARDS:
  - TERMINAL/CLOSED frontier: the goal shows ``No more goals``, or
    ``proof_status.status == candidate_closed_pending_qed``, or
    ``current_layer == closed_candidate`` — there is nothing to loop on (the
    right lever there is the final-admit gate / qed, not restructuring).
  - UNKNOWN frontier: fewer than 2 non-None ``remaining`` samples in the window —
    we cannot distinguish progress from stall, so we stay silent (unknown != unchanged).
  - UNDO COOLDOWN: the undo/restart turn itself and the immediately following
    turn never fire. A view RESTORED by undo is the agent's own deliberate
    navigation, not a relapse (and it is not an accepted commit, so it can never
    score a hit either).

FLOOR-BETWEEN-ARRIVALS gate: for the excursions between consecutive accepted
arrivals at this fingerprint, compute each excursion's frontier FLOOR (the lowest
non-None ``remaining`` reached). Stay silent if the LATEST excursion reached a
strictly lower floor than every earlier one — the agent is still converting each
round-trip into net progress. Fire only when the floor between returns has
stopped improving. Because the gate compares per-excursion MINIMA between
arrivals at the SAME fingerprint, a legitimate ``remaining`` RISE from a
structural split (``seq`` / ``case`` / ``rcondt``) never reads as "no progress" —
rises simply never enter the comparison (the audited window-half floor split
misread exactly that shape, step4_badi scratch t23).

CRITICAL design choices:
  - Keyed on the RENDERED ``(pre,post,remaining,phase)`` fingerprint, NOT on the
    persisted ``goal_hash`` (empirically empty for ~85/86 turns in the failure
    trace, so a goal_hash-keyed detector silently no-ops).
  - The monotonic REPL prompt/counter line is stripped before hashing (Defect 1),
    otherwise every turn's hash is unique and the detector is dead on real traces.
  - This module's ``detect_patch_loop`` is a PURE function of ``history``: it
    fires on EVERY accepted re-arrival while the loop persists. The "one fire per
    loop EPISODE" suppression + re-arm latch lives in ``ProofNodeManager``: on a
    fire it captures the loop-set as the fingerprints REACHED BY ACCEPTED COMMITS
    in the window, and re-arms only after >= R (R=2) accepted commits land OUTSIDE
    that set (parking on one new frozen fingerprint via rejected turns is NOT an
    escape), or a game-pair restructure, or an undo/restart intent (full
    production vocabulary: ``undo_last_step`` / ``request_restart`` /
    ``undo_to_checkpoint`` / ``fresh_restart``).
  - On the real step4_1 resume trace (Tree_0_0, 85 turns of macro-cycle), the
    banner fires EXACTLY ONCE, inside the 2nd-4th macro-cycle round (t27-t49):
    the first fingerprint to accumulate 3 ACCEPTED, separated arrivals inside one
    window. (The pre-rewrite code fired at t27 via a rejected-commit filler hit.)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

# decision_context key + banner text. Validators grep for both.
DECISION_CONTEXT_KEY = "local_patch_loop"

# Intents/tactic heads that RESTRUCTURE THE GAME PAIR (re-issuing these is the
# lever, not a patch — they reset the loop). Comparison is on the tactic head.
#
# NOTE on `conseq`: a `conseq` reshapes the goal's pre/post but keeps the SAME two
# games, so on its own it is a LOCAL patch, not a game-pair restructure — the
# step4_1 death-spiral used `conseq (_: _ ==> bad1)` as one of its repeated patches.
# We therefore do NOT treat `conseq` as loop-resetting. Only tactics that swap the
# games themselves (`call` re-issue, `byequiv`/`equiv`, `transitivity`) reset it.
_RESTRUCTURE_HEADS = ("call", "byequiv", "equiv", "transitivity")

# The FULL production vocabulary of rewind/restart intents. Used for BOTH the
# detector's undo cooldown and the manager's episode-latch re-arm. The audited
# code listed only the first two; real runs rewound via `undo_to_checkpoint` and
# `fresh_restart`, so true rewinds never re-armed while (worse) the restored view
# could still score a recurrence. NOTE: widening this list is only safe BECAUSE
# hits now require accepted re-arrival — the badi-resume counterfactual showed
# that widening it under the old any-turn-counts semantics took 4 fires to 9,
# all landing on an agent already mid-recovery.
_REARM_INTENTS = (
    "undo_last_step",
    "request_restart",
    "undo_to_checkpoint",
    "fresh_restart",
)

DEFAULT_K = 3
# Window must span >= K ACCEPTED arrivals of one member of the REAL step4_1
# MACRO-CYCLE. Each rendered fingerprint is re-reached about once per ~11-turn
# cycle, so 3 separated accepted arrivals span ~22 turns; 24 covers that with a
# small margin. Cranking it higher only inflates the false-positive surface of
# the PURE detector without firing any sooner; the manager's episode latch (not
# the window) is what bounds re-fires.
DEFAULT_WINDOW = 24

# ---- Episode ESCALATION (2026-06-09 round-2 reaudit, E6 residual / FN) ----
# On the real step4_1 resume trace the single latched banner fired at t34 and
# the agent then ground the SAME macro-cycle for ~50 more turns to timeout with
# zero further signal (47 pure re-fires all latch-suppressed). If the episode
# persists (no genuine escape re-arms the latch) for this many further turns,
# the manager surfaces EXACTLY ONE stronger escalation banner, then stays
# silent for the rest of the episode (hard cap: 2 banners per episode).
# Tuned on the six audited bundles: 22 puts the escalation at t56 on the
# step4_1 resume Tree_0_0 trace (target window t54-t65, death-grind till t85);
# every other audited tree has no latched fire at all, so 0 escalations there.
DEFAULT_ESCALATE_AFTER = 22

# ---- Rejected-thrash signal (2026-06-09 round-2 reaudit, known blind spot) --
# step4_badi scratch Tree_0_1_r2 t33-t39: an accepted `skip; smt().` created a
# goal, then THREE consecutive rejected commits (`sim.` / `auto; smt().` /
# `auto => />; smt(...)`) parked on that same fingerprint, and at t39 the agent
# abandoned the tree — the only stuck-to-abandonment texture in that run, and
# the rewritten CATCH recurrence semantics are CATEGORICALLY silent on it
# (rejected commits can never score a hit). `detect_rejected_thrash` is the
# narrow bypass: >= THRASH_K consecutive rejected/errored `commit_tactic` turns
# on ONE fingerprint, no accepted commit in between, non-terminal frontier, and
# no game-pair-restructure attempt inside the run (an agent whose REJECTED
# attempts are `call ...`/`byequiv ...` is already switching routes — the
# step4_1 scratch t25-t29 texture — and must not be nagged).
DEFAULT_THRASH_K = 3

# REPL bookkeeping prompt/counter line, e.g. ``[521|check]>`` -> ``[531|check]>``.
# This index advances by a few units EVERY committed turn even when the goal is
# byte-identical, so leaving it in the fingerprint makes every turn's hash unique
# and the loop detector silently no-ops on real EC traces (Defect 1). It carries
# no goal content, so we drop it before hashing. The tight anchored regex matches
# ONLY a line that is exactly the prompt token (digits|word followed by ``>``),
# so real goal content (hypotheses, program, pre/post) is never stripped.
_REPL_PROMPT_RE = re.compile(r"^\[\d+\|\w+\]>$")

# Terminal / closed-candidate markers (hard-silence guard). On such views the
# proof has no open frontier to loop on — the audited code fired its single most
# self-contradictory banner ("This is a patch loop, not progress") on a view
# whose goal read exactly `No more goals` (step4_badi scratch r2_r2 t4 / resume
# Tree_0_1 t4).
_TERMINAL_GOAL_TEXT = "No more goals"
_TERMINAL_STATUS = "candidate_closed_pending_qed"
_TERMINAL_LAYER = "closed_candidate"


def _is_volatile_line(line: str) -> bool:
    """True for purely-monotonic REPL bookkeeping lines that carry no goal content
    and so must be normalised out of the fingerprint (see ``_REPL_PROMPT_RE``)."""
    return bool(_REPL_PROMPT_RE.match(line.strip()))


def render_fingerprint(view: dict[str, Any]) -> str:
    """A stable hash of the rendered ``(pre, post, remaining, phase)`` of a view.

    Pulls the agent-rendered substrate (NOT goal_hash): the current goal lines, the
    remaining-goal count, and the phase/layer label. Whitespace within lines is
    normalised so cosmetic reflow does not perturb the key, but the structural
    content does.

    The view exposes no standalone structured ``pre``/``post`` fields — they live
    only inside ``current_goal.lines`` (the ``pre = ...`` / ``post = ...`` lines) —
    so the fingerprint is built from ``lines`` with the volatile REPL prompt/counter
    line(s) stripped first. ``remaining`` and ``phase`` come from the structured
    ``proof_status`` fields directly."""
    cg = view.get("current_goal") if isinstance(view.get("current_goal"), dict) else {}
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    lines = cg.get("lines") if isinstance(cg.get("lines"), list) else []
    # Strip the monotonic REPL prompt/counter line(s) BEFORE hashing so a frozen
    # goal yields a STABLE fingerprint across turns (Defect 1).
    kept = [ln for ln in lines if not _is_volatile_line(str(ln))]
    body = "\n".join(" ".join(str(ln).split()) for ln in kept)
    remaining = ps.get("remaining_goals")
    phase = (
        ps.get("current_layer")
        or ps.get("view_focus")
        or cg.get("view_focus")
        or ""
    )
    payload = f"REM={remaining}␟PHASE={phase}␟BODY={body}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def remaining_of(view: dict[str, Any]) -> int | None:
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    r = ps.get("remaining_goals")
    return r if isinstance(r, int) else None


def is_terminal_view(view: dict[str, Any]) -> bool:
    """True when the view shows a CLOSED/terminal frontier: ``No more goals`` in
    the goal text, ``proof_status.status == candidate_closed_pending_qed``, or
    ``current_layer == closed_candidate``. The patch-loop banner is hard-silenced
    on such views (there is no open frontier to loop on; the lever there is
    the final-admit gate / qed, not restructuring)."""
    cg = view.get("current_goal") if isinstance(view.get("current_goal"), dict) else {}
    ps = view.get("proof_status") if isinstance(view.get("proof_status"), dict) else {}
    lines = cg.get("lines") if isinstance(cg.get("lines"), list) else []
    if any(_TERMINAL_GOAL_TEXT in str(ln) for ln in lines):
        return True
    if str(ps.get("status") or "") == _TERMINAL_STATUS:
        return True
    if str(ps.get("current_layer") or "") == _TERMINAL_LAYER:
        return True
    return False


@dataclass
class TurnRecord:
    """The minimal per-turn substrate the detector needs. Built by callers from the
    workspace view + the manager turn outcome (see ``record_from``)."""

    fingerprint: str
    remaining: int | None
    intent: str          # e.g. "commit_tactic" or a context topic
    tactic: str          # the tactic string for a commit/probe, else ""
    accepted: bool       # committed AND not errored/rejected
    errored: bool        # EC error / no-op / reject signal
    terminal: bool = False  # view shows a closed/terminal frontier (hard silence)


def record_from(
    view: dict[str, Any],
    *,
    intent: str,
    tactic: str = "",
    ok: bool = False,
    errored: bool = False,
) -> TurnRecord:
    """Build a ``TurnRecord`` from a rendered view + the turn outcome.

    ``accepted`` is True only for a ``commit_tactic`` whose manager outcome was
    ok AND not errored — a REJECTED commit, a text-equal auto-revert (surfaced
    as ``error_summary``), a gated ``qed.``/``finish``, a repair turn
    (intent=None) and every read-only intent are all NOT accepted, so they can
    never score a recurrence hit nor count as "leaving" a goal."""
    accepted = (intent == "commit_tactic") and bool(ok) and not bool(errored)
    return TurnRecord(
        fingerprint=render_fingerprint(view),
        remaining=remaining_of(view),
        intent=str(intent or ""),
        tactic=str(tactic or ""),
        accepted=accepted,
        errored=bool(errored),
        terminal=is_terminal_view(view),
    )


def _tactic_head(tactic: str) -> str:
    t = tactic.strip().lower().lstrip("+-*").strip()
    return t.split("(")[0].split()[0].rstrip(".;") if t.split() else ""


def _accepted_arrival_hits(recent: list[TurnRecord], target: str) -> list[int]:
    """Indices (within ``recent``) of ACCEPTED arrivals at ``target``, counting a
    re-arrival only after the agent genuinely LEFT — i.e. at least one accepted
    commit landed on a DIFFERENT fingerprint since the previous counted hit.
    Non-state-changing turns (read-only / rejected / errored / repair / undo)
    neither score a hit nor count as leaving. Consecutive accepted commits that
    keep landing on the same fingerprint collapse into the one arrival."""
    hits: list[int] = []
    departed = True  # the first accepted arrival always counts (creation)
    for i, r in enumerate(recent):
        if not r.accepted or not r.fingerprint:
            continue
        if r.fingerprint == target:
            if departed:
                hits.append(i)
                departed = False
        else:
            departed = True
    return hits


def detect_patch_loop(
    history: list[TurnRecord],
    *,
    k: int = DEFAULT_K,
    window: int = DEFAULT_WINDOW,
) -> dict[str, Any] | None:
    r"""Return a neutral ``decision_context`` banner, or ``None`` if no loop.

    PURE function of ``history`` (no latch) — may return a banner on every
    accepted re-arrival while the loop persists; the "one fire per EPISODE"
    suppression lives in ``ProofNodeManager``. ``history`` is oldest->newest.
    Fires when, within the trailing ``window``:
      - the CURRENT turn is an ACCEPTED, non-errored ``commit_tactic`` that
        re-arrives at a fingerprint with >= ``k`` accepted-arrival hits, each
        pair of consecutive hits separated by at least one accepted commit on a
        DIFFERENT fingerprint (the agent genuinely left and came back) — turns
        that cannot change proof state (read-only echoes, rejected/errored or
        text-equal commits, repair turns, undo menus, gated qed/finish) never
        count as hits nor as leaving, AND
      - NO restructuring intent (call/byequiv/equiv/transitivity — NOT conseq,
        which keeps the same game pair) appeared between the hits, AND
      - the frontier FLOOR between returns has stopped improving: per-excursion
        minima of ``remaining`` between consecutive arrivals are not strictly
        decreasing into the latest excursion, AND
      - none of the hard-silence guards apply: the current view is not
        terminal/closed (``No more goals`` / candidate_closed_pending_qed /
        closed_candidate), the window holds >= 2 non-None ``remaining`` samples,
        and neither this turn nor the previous one is an undo/restart intent
        (undo cooldown).
    """
    if not history:
        return None
    recent = history[-window:]
    cur = recent[-1]
    target = cur.fingerprint
    if not target:
        return None

    # --- Undo cooldown: the undo/restart turn and the turn right after it never
    # fire. The restored view is deliberate navigation, not a relapse.
    if cur.intent in _REARM_INTENTS:
        return None
    if len(recent) >= 2 and recent[-2].intent in _REARM_INTENTS:
        return None

    # --- Terminal-state guard: a closed/terminal frontier cannot be a patch loop.
    if cur.terminal:
        return None

    # --- Unknown-frontier guard: with < 2 non-None remaining samples in the
    # window we cannot tell progress from stall — hard silence (unknown != unchanged).
    win_rems = [r.remaining for r in recent if r.remaining is not None]
    if len(win_rems) < 2:
        return None

    # --- Recurrence: only accepted re-arrivals count, and only the current turn
    # being one can fire (so the banner lands ON the relapse commit, never on a
    # read-only echo / undo / repair turn).
    hits = _accepted_arrival_hits(recent, target)
    if len(hits) < k or hits[-1] != len(recent) - 1:
        return None

    # --- No restructuring intent between the hits: re-issuing the game-pair
    # lever resets the loop (the latch also re-arms on it, see the manager).
    span = recent[hits[0] : hits[-1] + 1]
    for r in span:
        head = _tactic_head(r.tactic)
        if r.intent == "commit_tactic" and head in _RESTRUCTURE_HEADS:
            return None  # a restructure happened — not a frozen patch loop

    # --- FLOOR-BETWEEN-ARRIVALS gate. For each excursion between consecutive
    # accepted arrivals at this fingerprint, take the excursion's frontier FLOOR
    # (min non-None `remaining`). Silent while the LATEST excursion still reached
    # a strictly lower floor than every earlier one (each round-trip converts
    # into net progress); fire once the floor between returns stops improving.
    # Comparing per-excursion minima between arrivals at the SAME fingerprint
    # means a legitimate `remaining` RISE from a structural split (seq/case/
    # rcondt) never reads as "no progress" — rises never enter the comparison.
    gap_floors: list[int | None] = []
    for a, b in zip(hits, hits[1:]):
        rems = [r.remaining for r in recent[a : b + 1] if r.remaining is not None]
        gap_floors.append(min(rems) if rems else None)
    prior = [g for g in gap_floors[:-1] if g is not None]
    latest = gap_floors[-1]
    if latest is not None and prior and latest < min(prior):
        return None  # floor still shrinking between returns — real convergence

    n = len(hits)
    rem_now = cur.remaining
    # Unknown is NOT "unchanged": never render a claim about an unknown count.
    rem_disp: int | str = rem_now if rem_now is not None else "unknown"
    return {
        "key": DECISION_CONTEXT_KEY,
        # DEFAULT NEUTRAL text. The bare detector is DOMAIN-AGNOSTIC: it knows only
        # that the frontier floor has not moved between returns, NOT what structural
        # tactic produced it. A call/up-to-bad-specific tail ("re-issue your `call`
        # in up-to-bad form") would be WRONG-DOMAIN on a non-up-to-bad loop. The
        # manager swaps in the call-aware tail ONLY when the `up_to_bad_call`
        # signal is independently active for the same frontier (see
        # LoopMonitor.inject + `patch_loop_banner_text`).
        "text": patch_loop_banner_text(n, call_aware=False),
        "recurrences": n,
        "remaining": rem_disp,
        "fingerprint": target,
        "certified": False,
        "guarantee": (
            "UNCERTIFIED observation — a no-progress-cycle signal from the rendered "
            "goal fingerprint, NOT a verdict and NOT a gate. You may keep going; "
            "this only flags that the frontier has not moved."
        ),
    }


def patch_loop_banner_text(n: int, *, call_aware: bool) -> str:
    r"""The ``local_patch_loop`` banner text.

    ``n`` is the number of ACCEPTED arrivals at this goal fingerprint (creation +
    accepted re-arrivals after genuinely leaving) — never inflated by read-only /
    rejected / repair / undo turns, which cannot score hits under the rewritten
    recurrence semantics. The text asserts exactly what the detector verified:
    accepted round-trips back to the same rendered goal with no floor improvement
    between returns. It does NOT claim "net open goals unchanged" (the count may
    legitimately oscillate, or be unknown).

    WORDING (round-2 audit, F3): N counts the CREATION arrival too, so the text
    spells the breakdown out — "reached ... N times (first arrival + N-1
    returns)" — instead of the audited "arrived back ... N times — each return
    ..." phrasing, which read as if all N were returns (off-by-one against what
    the detector actually counted). Detector semantics are unchanged.

    Two forms share one stem so the only difference is the closing lever clause:
      - NEUTRAL (``call_aware=False``): the domain-agnostic banner — the lever is
        "the structural tactic that produced this frontier". This is what the bare
        ``detect_patch_loop`` emits and what a non-up-to-bad loop must carry: NO
        call/up-to-bad text.
      - CALL-AWARE (``call_aware=True``): adds the ``(e.g. re-issue your `call` in
        up-to-bad form)`` parenthetical, surfaced by the manager ONLY when the
        ``up_to_bad_call`` signal is independently active at this frontier.
    """
    lever = (
        "reconsider the structural tactic that produced this frontier "
        "(e.g. re-issue your `call` in up-to-bad form) rather than another "
        "local patch."
        if call_aware else
        "reconsider the structural tactic that produced this frontier rather "
        "than another local patch."
    )
    returns = max(n - 1, 0)
    return (
        f"Your accepted commits have reached this identical goal {n} times "
        f"(first arrival + {returns} return{'s' if returns != 1 else ''}, each "
        f"after working elsewhere) without restructuring, and the open-goal "
        f"floor between returns has stopped improving. This is "
        f"a patch loop, not progress. The lever is upstream — {lever}"
    )


def patch_loop_escalation_text(turns_since: int, accepted_since: int) -> str:
    r"""The ONE-per-episode ESCALATION banner (manager-surfaced; see
    ``LoopMonitor.inject``). Emitted only after the
    latched ``local_patch_loop`` banner already fired and the SAME episode then
    persisted — no genuine escape (>= 2 accepted commits outside the loop-set),
    no game-pair restructure, no undo/restart — for ``DEFAULT_ESCALATE_AFTER``
    further turns. Stronger than the first banner but still flag-only: it
    reports the measured idle span and recommends the rewind lever explicitly;
    it never gates anything.
    """
    return (
        f"Escalation — {turns_since} turns have passed since the patch-loop "
        f"banner above this goal first fired, with {accepted_since} accepted "
        f"commit{'s' if accepted_since != 1 else ''} since then, and the proof "
        f"is still cycling inside the same goal set: no escape, no restructure, "
        f"no rewind. At this point further local patches at this frontier have "
        f"a long measured record of not closing it. The strongest available "
        f"lever is `undo_to_checkpoint` back to BEFORE the structural tactic "
        f"that produced this frontier (`inspect_context` with topic "
        f"`checkpoints` lists the committed cut points with ready-to-submit "
        f"payloads), then re-cut it differently — or switch to a different "
        f"structural route entirely."
    )


def rejected_thrash_banner_text(n: int) -> str:
    r"""The ``rejected_thrash`` banner text — NEUTRAL and deliberately DISTINCT
    from the patch-loop wording: this signal is about consecutive REJECTED
    attempts parked on one goal (no state ever changed), not about accepted
    round-trips. It points at the followup's own Already-tried list and offers
    the two real levers (different family / rewind) without prescribing either.
    """
    return (
        f"Your last {n} attempted commits were all rejected at this same goal — "
        f"the proof state has not changed. The Already-tried list in this "
        f"followup shows the tactic families already exhausted at this exact "
        f"state; consider a genuinely different tactic family, or rewind "
        f"(`undo_to_checkpoint` / `undo_last_step`) and reshape the goal "
        f"upstream instead of retrying variants here."
    )


def detect_rejected_thrash(
    history: list[TurnRecord],
    *,
    k: int = DEFAULT_THRASH_K,
) -> dict[str, Any] | None:
    r"""Return a neutral ``rejected_thrash`` banner dict, or ``None``.

    Fires when the CURRENT turn is the ``k``-th consecutive REJECTED/errored
    ``commit_tactic`` parked on ONE fingerprint:

      - the current turn is a ``commit_tactic`` with ``errored`` set and not
        accepted (a real EC reject/error — gated ``qed.``/``finish`` deflections
        have ``errored=False`` and never count),
      - walking backwards, the trailing run collects STRICTLY CONSECUTIVE
        rejected commits on the SAME fingerprint; ANYTHING else breaks it — an
        accepted commit, a different fingerprint, a probe, an undo/restart, a
        repair turn, AND read-only ``inspect_context``/``lookup_symbol`` turns
        (an agent that inspects between rejections is gathering information,
        not blind-retrying — the inspect-interleaved friction textures from a
        held-out MAC corpus run, e.g. c1/Tree_0_0_0 t5-t9 and c1/Tree_0_0
        t55-t59, must stay silent),
      - the run length is EXACTLY ``k`` — this is the built-in episode latch:
        the banner lands once on the k-th rejection and the 4th/5th/... stay
        silent; only a run genuinely broken (accepted commit / new goal /
        rewind / inspect) and re-formed can fire again,
      - the view is not terminal/closed,
      - NO rejected attempt in the run has a game-pair-restructure head
        (``call`` / ``byequiv`` / ``equiv`` / ``transitivity``): an agent whose
        rejected attempts are restructure tactics is already switching routes
        (step4_1 scratch t25-t29), which is the opposite of thrash, and
      - at least TWO attempts in the run share the same tactic HEAD — true
        thrash retries VARIANTS of one family (badi r2 t35/t36 both `auto…`,
        badi Tree_0_1 t12/t14 both `move=> …; smt(…)`), whereas a run of
        all-distinct heads (`wp.` / `if.` / `sp.` — a held-out MAC corpus
        run's c2/Tree_0_2 t7-t9, c0/Tree_0_1_0_0 t8-t10) is an agent stepping
        through DIFFERENT program-structure levers and must stay silent.

    Empirically tuned on the six audited bundles (2026-06-09 round 2): the one
    true positive is step4_badi scratch Tree_0_1_r2 t36 (three consecutive
    rejects after the t33 `skip; smt().` arrival, tree abandoned at t39).
    """
    if not history:
        return None
    cur = history[-1]
    if cur.intent != "commit_tactic" or cur.accepted or not cur.errored:
        return None
    if cur.terminal or not cur.fingerprint:
        return None
    run: list[TurnRecord] = [cur]
    for r in reversed(history[:-1]):
        if (
            r.fingerprint != cur.fingerprint
            or r.intent != "commit_tactic"
            or r.accepted
            or not r.errored
        ):
            break  # anything but a same-goal rejected commit breaks the run
        run.append(r)
    # EXACTLY k — one banner per thrash episode, no manager latch needed.
    if len(run) != k:
        return None
    heads = [_tactic_head(r.tactic) for r in run]
    for head in heads:
        if head in _RESTRUCTURE_HEADS:
            return None  # rejected RESTRUCTURE attempts = switching routes, not thrash
    if len(set(heads)) == len(heads):
        return None  # all-distinct heads = stepping through different levers
    return {
        "key": DECISION_CONTEXT_KEY,
        "kind": "rejected_thrash",
        "text": rejected_thrash_banner_text(k),
        "rejections": k,
        "fingerprint": cur.fingerprint,
        "certified": False,
        "guarantee": (
            "UNCERTIFIED observation — a consecutive-rejections signal from the "
            "rendered goal fingerprint, NOT a verdict and NOT a gate. You may "
            "keep going; this only flags that the recent attempts here were all "
            "rejected."
        ),
    }
