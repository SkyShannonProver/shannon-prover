r"""Pure-view `up_to_bad_call` enrichment — already-handled gates + episode dedup
(audit 2026-06-09, SPEC-C #5/#6).

The 12-agent replay audit found the pure-view path fired counterfactually INSIDE
already-handled up-to-bad territory (7 resume FPs whose offered template carried
`!UFCMA.bad1{2}`; 14 scratch wrong-domain views inside the agent's own 2-clause
call obligations) and repeated the same banner over up to 24 consecutive views.
These tests pin the three silencing gates and the per-session episode dedup,
AND the must-keep fires (the true-positive shapes from the same bundles).
"""
from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import core.easycrypt.session_prover_workspace_view as _wv  # noqa: E402
from core.easycrypt.session_prover_workspace_view import (  # noqa: E402
    _UP_TO_BAD_EPISODE_LATCH,
    _UP_TO_BAD_REARM_CONSUMED,
    _enrich_decision_context,
    _enrich_up_to_bad_call,
)


def _enrich(dc: dict, lines: list[str], session_dir: str | None = None) -> dict:
    _enrich_decision_context(
        dc,
        state={"goal_window": {"lines": lines}},
        frontier={},
        proof_ir={},
        evidence={},
        debug_refs={"session_dir": session_dir} if session_dir else None,
    )
    return dc


# ---- goal shapes (verbatim from the step4_1 bundles) ------------------------------

# step4_1 scratch Tree_0_0 t7 (KEEP-FIRE): pre carries `bad1 \/ inv ...`, post the
# forged relation-break disjunction. No call committed yet, offer is the bare
# restatement template (positive mention only).
_KEEP_GOAL = [
    "pre =",
    "  UFCMA.bad1{2} \\/",
    "  inv SplitC2.I1.RO.m{1} RO.m{2} Mem.log{1} Mem.log{2} UFCMA.log{2}",
    "",
    "post = forged{1} => forged{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2}",
    "[472|check]>",
]
_KEEP_OFFER = {
    "proof_options": [
        {
            "title": "Invariant-call route",
            "tactic_shape": (
                "call (_: r{1} => forged{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2})."
            ),
        }
    ]
}

# step4_1 scratch Tree_0_1 t18-41 (the pre-fix FALSE NEGATIVE): nested-paren post.
_NESTED_FN_GOAL = [
    "post = forged{1} => (forged{2} \\/ UFCMA.bad2{2}) \\/ UFCMA.bad1{2}",
    "[472|check]>",
]

# step4_1 resume Tree_0_0 t5 (counterfactual FP): the offered template's invariant
# already GUARDS the bad (`!UFCMA.bad1{2} => ...`) — obligation (1) of the
# prefix's own 2-clause call.
_HANDLED_OFFER = {
    "proof_options": [
        {
            "title": "Invariant-call route",
            "tactic_shape": (
                "call (_: (!UFCMA.bad1{2} => true /\\ (glob A){1} = (glob A){2} /\\ "
                "inv RO.m{1} RO.m{2} Mem.log{1} Mem.log{2} UFCMA.log{2}) /\\ "
                "(glob A){2} = (glob A){m})."
            ),
        }
    ]
}

# step4_1 scratch Tree_0_0_r2 t21 (wrong-domain FP): the goal is INSIDE the
# obligations of the agent's own 2-clause call — pre carries `!UFCMA.bad1{2}` as a
# top-level negated conjunct (inside a parenthesized group), post is the
# negated-guard obligation shape.
_WRONG_DOMAIN_GOAL = [
    "pre =",
    "  (c{2} = witness<:ciphertext> /\\",
    "   c{1} = witness<:ciphertext> /\\",
    "   !UFCMA.bad1{2} /\\",
    "   p{1} = p{2} /\\",
    "   inv SplitC2.I1.RO.m{1} RO.m{2} Mem.log{1} Mem.log{2} UFCMA.log{2}) /\\",
    "  check_plaintext BNR.lenc{1} p{1}",
    "",
    "post =",
    "  !UFCMA.bad1{2} =>",
    "  c{1} = c{2} /\\",
    "  inv SplitC2.I1.RO.m{1} RO.m{2} Mem.log{1} Mem.log{2} UFCMA.log{2}",
    "[389|check]>",
]

# The genuine negated-GUARD shape (must KEEP firing — a guard is not a conjunct).
_NEG_GUARD_GOAL = [
    "equiv[ G1.O ~ G2.O :",
    "  ={glob A} ==>",
    "  !(UFCMA.bad1 \\/ UFCMA.bad2){2} => ={res}",
    "]",
]


def setup_function(_fn) -> None:
    _UP_TO_BAD_EPISODE_LATCH.clear()
    _UP_TO_BAD_REARM_CONSUMED.clear()


# ---- must-keep fires ----------------------------------------------------------------


def test_keep_fire_scratch_t7_shape_with_positive_mention_offer() -> None:
    # A POSITIVE bad mention in the offered template (the bare restatement of the
    # post — exactly the wrong one-clause form the mechanism exists to flag) must
    # NOT silence the fire. (step4_1 scratch Tree_0_0 t7: the must-keep TP.)
    dc = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL)
    assert "up_to_bad_call" in dc
    entry = dc["up_to_bad_call"]
    # E2 (audit 2026-06-09): _KEEP_GOAL carries BOTH bad1 and bad2, so the candidate
    # must cover both via the disjunctive up-to-bad clause — the old
    # `call (_: UFCMA.bad1, <inv>).` silently dropped bad2.
    assert entry["candidate"] == "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>)."
    assert entry["active_bad_events"] == ["UFCMA.bad1", "UFCMA.bad2"]
    assert entry["certified"] is False


def test_keep_fire_nested_paren_post_previously_false_negative() -> None:
    # step4_1 scratch Tree_0_1 t18-41: the nested `(forged \/ bad2) \/ bad1`
    # rendering harvested ∅ pre-fix and the lineage died unflagged. Must now fire.
    dc = _enrich(dict(_KEEP_OFFER), _NESTED_FN_GOAL)
    assert "up_to_bad_call" in dc
    assert dc["up_to_bad_call"]["active_bad_events"] == ["UFCMA.bad1", "UFCMA.bad2"]


def test_keep_fire_on_negated_guard_goal() -> None:
    # `!(B1 \/ B2){2} => ={res}` is the genuine UNHANDLED up-to-bad shape (the bad
    # appears as a negated guard ANTECEDENT, not a conjunct) — gate (b) must not
    # swallow it.
    dc = _enrich(
        {"proof_options": [{"title": "Invariant-call",
                            "tactic": "call (_: ={glob UFCMA})."}]},
        _NEG_GUARD_GOAL,
    )
    assert "up_to_bad_call" in dc


def test_fire_text_has_no_false_committed_call_premise() -> None:
    # SPEC-C #5: on the offer-triggered path the banner must not claim "your
    # `call (_: inv)` is lockstep" — there may be no committed call at all.
    dc = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL)
    text = dc["up_to_bad_call"]["text"]
    assert "your `call (_: inv)`" not in text
    assert "on offer here is lockstep" in text


# ---- gate (a): offered template already handles the bad ------------------------------


def test_gate_a_negated_mention_in_offer_silences() -> None:
    # step4_1 resume Tree_0_0 t5: the offered invariant template literally carries
    # `!UFCMA.bad1{2}` — the frontier is inside handled up-to-bad territory.
    dc = _enrich(dict(_HANDLED_OFFER), _KEEP_GOAL)
    assert "up_to_bad_call" not in dc


# ---- gate (a2): offered single-clause lockstep call already CARRIES every bad --------
# (E1 audit 2026-06-09): the offered invariant asserts the bad as a TOP-LEVEL CONJUNCT.

from core.easycrypt.session_prover_workspace_view import (  # noqa: E402
    _offer_already_handles_bad,
)

# step4_1 resume Tree_0_0 t34's REAL offered "Invariant-call route": a single-clause
# lockstep call whose invariant has `UFCMA.bad1{2}` as a top-level conjunct.
_T34_CARRIED_OFFER_TEXT = (
    "Invariant-call route call (_: UFCMA.bad1{2} /\\ (UFCMA.bad1{2} \\/ inv "
    "SplitC2.I1.RO.m{1} RO.m{2} SplitC2.I2.RO.m{1} SplitC2.I2.RO.m{2} Mem.log{1} "
    "Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} "
    "BNR.ndec{2} UFCMA.log{2}))).   Use this as route-selection context."
)


def test_gate_a2_carried_top_conjunct_in_lockstep_offer_silences() -> None:
    # The agent is already tracking `UFCMA.bad1` inside the offered call invariant
    # (top-level conjunct) — nothing to flag.
    assert _offer_already_handles_bad([_T34_CARRIED_OFFER_TEXT], {"UFCMA.bad1"}) is True


def test_gate_a2_does_not_silence_post_restatement_disjunction() -> None:
    # The wrong one-clause form the mechanism EXISTS to flag (step4_1 scratch t29):
    # the offered invariant only RESTATES the up-to-bad post inside an
    # implication-consequent disjunction (`r{1} => forged{2} \/ bad2 \/ bad1`), never
    # as a top conjunct — a POSITIVE mention that must NOT silence the fire.
    restate = (
        "Invariant-call route call (_: r{1} => forged{2} \\/ UFCMA.bad2{2} \\/ "
        "UFCMA.bad1{2}).   Use this as route-selection context."
    )
    assert (
        _offer_already_handles_bad([restate], {"UFCMA.bad1", "UFCMA.bad2"}) is False
    )


def test_gate_a2_requires_every_bad_carried() -> None:
    # Partial coverage does not silence: the t34 offer carries only `UFCMA.bad1`, so a
    # two-bad active set `{bad1, bad2}` is NOT already-handled (gate (a2) needs ALL).
    assert (
        _offer_already_handles_bad(
            [_T34_CARRIED_OFFER_TEXT], {"UFCMA.bad1", "UFCMA.bad2"}
        )
        is False
    )


# ---- gate (b): goal-level negated-bad conjunct ---------------------------------------


def test_gate_b_negated_conjunct_in_pre_silences_wrong_domain_view() -> None:
    # step4_1 scratch Tree_0_0_r2 t21 (one of the 14 wrong-domain views): the pre
    # carries `!UFCMA.bad1{2}` as a top-level negated conjunct inside a
    # parenthesized group — obligation (1) of the agent's own 2-clause call.
    # The offer here is the obligation-shaped template WITHOUT a negated mention
    # in normalized form being required; the goal alone must gate it.
    dc = _enrich(dict(_KEEP_OFFER), _WRONG_DOMAIN_GOAL)
    assert "up_to_bad_call" not in dc


# ---- gate (c): committed history already has the 2-clause call -----------------------


def test_gate_c_committed_two_clause_call_silences(tmp_path: Path) -> None:
    # step4_1 resume t7-t10: prefix L17 already committed
    # `call (_: UFCMA.bad1, inv ...)`; later phoare `call (_: UFCMA.bad1).` calls
    # must not mask it. The same goal/offer WITHOUT that history fires.
    (tmp_path / "history.ec").write_text(
        "byequiv (_: ={glob A} ==> res{1} => res{2} \\/ UFCMA.bad1{2}).\n"
        "proc.\n"
        "call (_: UFCMA.bad1, inv RO.m{1} RO.m{2} UFCMA.log{2}).\n"
        + "call (_: UFCMA.bad1).\n" * 6,
        encoding="utf-8",
    )
    dc = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=str(tmp_path))
    assert "up_to_bad_call" not in dc


def test_gate_c_lockstep_history_does_not_silence(tmp_path: Path) -> None:
    # A committed LOCKSTEP call is precisely the incoherence — it must not gate.
    (tmp_path / "history.ec").write_text(
        "byequiv (_: ={glob A} ==> res{1} => res{2} \\/ UFCMA.bad1{2}).\n"
        "proc.\n"
        "call (_: inv RO.m{1} RO.m{2} UFCMA.log{2}).\n",
        encoding="utf-8",
    )
    dc = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=str(tmp_path))
    assert "up_to_bad_call" in dc


# ---- episode dedup --------------------------------------------------------------------


def test_dedup_same_fact_fires_once_per_episode(tmp_path: Path) -> None:
    # scratch Tree_0_0 t7-t30: 24 consecutive identical banners pre-fix. Same
    # (bad-set, candidate) fact on consecutive views of one session -> one fire.
    sd = str(tmp_path)
    first = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd)
    assert "up_to_bad_call" in first
    second = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd)
    assert "up_to_bad_call" not in second


def test_dedup_refires_after_episode_ends(tmp_path: Path) -> None:
    # After the frontier stops carrying any harvested bad (episode over), the same
    # fact may legitimately fire again ("frontier/call 变化后重发").
    sd = str(tmp_path)
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd)
    no_bad_goal = ["post = ={res, glob M}"]
    _enrich(dict(_KEEP_OFFER), no_bad_goal, session_dir=sd)  # episode ends
    again = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd)
    assert "up_to_bad_call" in again


def test_dedup_fires_again_when_fact_changes(tmp_path: Path) -> None:
    # A different bad-set (frontier moved to a seq-mid goal carrying only bad1) is
    # a NEW fact and fires without an intervening no-bad view.
    sd = str(tmp_path)
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd)
    seq_mid_goal = [
        "pre =",
        "  (UFCMA.bad1{2} \\/",
        "   inv SplitC2.I1.RO.m{1} RO.m{2} Mem.log{1} Mem.log{2} UFCMA.log{2})",
        "",
        "post = true",
    ]
    dc = _enrich(dict(_KEEP_OFFER), seq_mid_goal, session_dir=sd)
    assert "up_to_bad_call" in dc
    assert dc["up_to_bad_call"]["active_bad_events"] == ["UFCMA.bad1"]


# ---- E3 re-arm on a newly-committed non-uptobad call (audit 2026-06-09) ----------
# The generic frontier re-arm never ends step4_1 scratch Tree_0_0's episode (the goal
# carries bad1,bad2 for its whole life), so the fact latched at t3/t4 could never
# re-surface at the decisive t29 where the agent commits the WRONG one-segment
# `call (_: forged => ... \/ bad)` and gives up. E3 adds a call-event re-arm: a new
# committed relational `call (_: ...)` that is STILL not the 2-clause up-to-bad form
# re-arms the fact ONCE (one re-fire per such call event; gates (a)/(b)/(c) priority).

# scratch Tree_0_0 t29 verbatim: the wrong one-segment lockstep call (no top comma).
_T29_WRONG_CALL = (
    "call (_: forged{1} => forged{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2})."
)
# The 2-clause up-to-bad form carrying the bad (gate (c) territory — must NOT re-arm).
_TWO_CLAUSE_CALL = (
    "call (_: UFCMA.bad1, inv SplitC2.I1.RO.m{1} RO.m{2} UFCMA.log{2})."
)


def _write_history(tmp_path: Path, tactics: list[str]) -> str:
    (tmp_path / "history.ec").write_text(
        "\n".join(tactics) + "\n", encoding="utf-8"
    )
    return str(tmp_path)


def test_e3_rearm_on_new_non_uptobad_call_within_same_episode(tmp_path: Path) -> None:
    # First fire latches the fact. The goal still carries the bad (episode NOT over),
    # so the generic re-arm would keep it silent forever. Committing a NEW non-uptobad
    # `call (_:` (the t29 wrong one-segment form) re-arms the SAME fact once.
    sd = _write_history(tmp_path, ["proc.", "wp."])  # no relational call yet
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd)
    # Same fact, same episode -> suppressed.
    assert "up_to_bad_call" not in _enrich(
        dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd
    )
    # The agent commits the WRONG one-segment call (t29). The fact may re-fire ONCE.
    _write_history(tmp_path, ["proc.", "wp.", _T29_WRONG_CALL])
    refire = _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd)
    assert "up_to_bad_call" in refire, "E3 re-arm must re-surface at the t29 wrong call"


def test_e3_rearm_fires_at_most_once_per_call_event(tmp_path: Path) -> None:
    # No return to the 24-view banner spam: with the non-uptobad call already in
    # history, the sequence is initial fire -> exactly ONE re-arm fire -> silent on
    # every later view (the same committed call signature re-arms at most once).
    sd = _write_history(tmp_path, [_T29_WRONG_CALL])
    fires = []
    for i in range(26):
        if "up_to_bad_call" in _enrich(
            dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd
        ):
            fires.append(i)
    # Fire #0 = initial episode fire; fire #1 = the single re-arm on the committed
    # non-uptobad call; nothing after (history/call signature never changes again).
    assert fires == [0, 1], f"expected initial + one re-arm, got {fires}"


def test_e3_no_rearm_when_committed_call_is_two_clause_uptobad(tmp_path: Path) -> None:
    # Gate (c) priority: when the committed relational call IS the 2-clause up-to-bad
    # form carrying the bad, the frontier is handled — the enrichment returns at gate
    # (c) and never reaches the re-arm (the resume Tree_0_0 lineage stays silent).
    sd = _write_history(tmp_path, [_TWO_CLAUSE_CALL])
    assert "up_to_bad_call" not in _enrich(
        dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd
    )
    # Even after the latch is set by an earlier fire on a fresh scope, committing a
    # 2-clause up-to-bad call must not re-arm (gate (c) silences it).
    s2 = tmp_path / "s2"
    s2.mkdir()
    sd2 = _write_history(s2, ["wp."])
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd2)
    _write_history(s2, ["wp.", _TWO_CLAUSE_CALL])
    assert "up_to_bad_call" not in _enrich(
        dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=sd2
    )


def test_dedup_off_without_session_identity() -> None:
    # No session_dir -> the enrichment stays a pure projection (unit-test /
    # detached-projection determinism): identical consecutive calls both fire.
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL)
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL)


def test_dedup_scopes_are_independent(tmp_path: Path) -> None:
    # Two trees (sessions) in one process must not suppress each other.
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=str(a))
    assert "up_to_bad_call" in _enrich(dict(_KEEP_OFFER), _KEEP_GOAL, session_dir=str(b))


# ---- contract -------------------------------------------------------------------------


def test_enrichment_never_raises_on_malformed_input() -> None:
    # never-raise / flag-only: garbage state must not break view building.
    dc: dict = {"proof_options": [{"tactic_shape": "call (_: x)."}]}
    _enrich_decision_context(
        dc,
        state={"goal_window": {"lines": [None, 42, {"x": 1}]}},  # type: ignore[list-item]
        frontier={},
        proof_ir={},
        evidence={},
        debug_refs={"session_dir": 13},  # type: ignore[dict-item]
    )
    # silent (no fire) and no exception is the whole contract here
    assert "up_to_bad_call" not in dc or isinstance(dc["up_to_bad_call"], dict)


def test_no_fire_without_call_offer() -> None:
    dc = _enrich({"proof_options": []}, _KEEP_GOAL)
    assert "up_to_bad_call" not in dc


# ---- E3 real-bundle replay (audit 2026-06-09) ------------------------------------
# Drives the ACTUAL step4_1 scratch Tree_0_0 bundle (each saved view + reconstructed
# committed history) through the pure-view enrichment and pins: the fact re-fires at
# the decisive t29 (the wrong one-segment call commit) and does NOT spam between the
# initial fire and t29 (no return to the 24-view banner). Skips when the sibling
# worktree bundle is not on disk (this worktree is `wt_feat_panel`; the run lives in
# `wt_step41_l4`), so the suite stays green on a clone without that artifact.

_SCRATCH_T00 = (
    ROOT
    / "wt_step41_l4/agent_view_runs"
    / "step4_1/2026-06-08_2246_step4_1__e88725b7-dirty/views/Tree_0_0"
)


def _bundle_goal_lines(view: dict) -> list[str]:
    cg = view.get("current_goal") or {}
    return [str(x) for x in (cg.get("lines") or [])] if isinstance(cg, dict) else []


def _bundle_dc_proxy(view: dict) -> dict:
    cm = view.get("candidate_moves")
    moves = cm.get("moves") if isinstance(cm, dict) else None
    opts = []
    for mv in moves or []:
        if isinstance(mv, dict):
            opts.append(
                {
                    "title": str(mv.get("title") or ""),
                    "tactic": str(mv.get("tactic_shape") or mv.get("tactic") or ""),
                    "guidance": str(mv.get("how_to_complete") or ""),
                    "applicability": str(mv.get("applicability") or ""),
                }
            )
    # Hypothetical lockstep call offer so the on-offer gate is satisfied even where the
    # saved L4 surface did not project a call move (matches the audit replay harness).
    opts.append({"title": "Invariant-call", "tactic": "call (_: ={glob X})."})
    return {"proof_options": opts}


@pytest.mark.skipif(
    not _SCRATCH_T00.exists(), reason="step4_1 scratch bundle not on disk"
)
def test_e3_real_bundle_scratch_t00_refires_at_t29() -> None:
    _wv._UP_TO_BAD_EPISODE_LATCH.clear()
    _wv._UP_TO_BAD_REARM_CONSUMED.clear()
    scope = tempfile.mkdtemp()
    hist = Path(scope) / "history.ec"
    committed: list[str] = []
    fires: list[int] = []
    for f in sorted(glob.glob(str(_SCRATCH_T00 / "turn_*.json"))):
        n = int(os.path.basename(f).split("_")[1].split(".")[0])
        view = json.loads(Path(f).read_text())
        mrf = _SCRATCH_T00 / "manager_results" / os.path.basename(f)
        mr = json.loads(mrf.read_text()) if mrf.exists() else {}
        hi = mr.get("handled_intent") or {}
        intent = str(hi.get("intent") or "")
        tac = str((hi.get("payload") or {}).get("tactic") or "")
        ok = mr.get("ok")
        # Append a committed, non-errored tactic BEFORE enriching this turn's view, so
        # the t29 call event is visible on the turn the agent reads its consequence.
        if intent == "commit_tactic" and ok and tac:
            committed.append(tac)
            hist.write_text("\n".join(committed) + "\n", encoding="utf-8")
        dc = _bundle_dc_proxy(view)
        _enrich_up_to_bad_call(
            dc,
            state={"goal_window": {"lines": _bundle_goal_lines(view)}},
            debug_refs={"session_dir": scope},
        )
        if "up_to_bad_call" in dc:
            fires.append(n)
    # The decisive give-up turn must see the fact re-surface.
    assert 29 in fires, f"E3 re-arm did not re-fire at t29; fires={fires}"
    # No banner spam between the initial episode fires and t29 (no 24-view repeat).
    spam = sorted(set(range(5, 29)) & set(fires))
    assert not spam, f"E3 re-armed into banner spam at {spam}; fires={fires}"


# ---- E1 real-bundle replay: step4_1 resume Tree_0_0 t34 stays NEUTRAL in the -------
#      HISTORY path (committed-history union active), not just the pure-view path. ----

_RESUME_T00 = (
    ROOT
    / "wt_step41_l4/agent_view_runs"
    / "step4_1/2026-06-09_0018_step4_1__e88725b7-dirty/views/Tree_0_0"
)
_RESUME_BOOT = (
    _RESUME_T00.parent / "_bootstrap" / "manager_bootstrap_0_0.json"
)


def _replay_prefix(boot: Path) -> list[str]:
    if not boot.exists():
        return []
    try:
        d = json.loads(boot.read_text())
    except Exception:
        return []
    tacs: list[str] = []
    for a in d.get("manager_actions") or []:
        if not str(a.get("label", "")).startswith("replay_prefix"):
            continue
        obs = a.get("agent_observation") or {}
        t = obs.get("tactic") or a.get("tactic")
        if t:
            tacs.append(str(t))
    return tacs


@pytest.mark.skipif(
    not _RESUME_T00.exists(), reason="step4_1 resume bundle not on disk"
)
def test_E1_real_bundle_resume_t34_neutral_history_path() -> None:
    # With the E1 harvest re-split fix the t34 pre block now harvests {UFCMA.bad1};
    # the widened gate (a2) must keep t34 NEUTRAL even with the committed-history union
    # active (debug_refs carries a reconstructed `history.ec` = bootstrap replay_prefix
    # + accepted commits). t34 must not appear in the fire set; the whole Tree_0_0
    # stays quiet here.
    _wv._UP_TO_BAD_EPISODE_LATCH.clear()
    _wv._UP_TO_BAD_REARM_CONSUMED.clear()
    scope = tempfile.mkdtemp()
    hist = Path(scope) / "history.ec"
    committed: list[str] = _replay_prefix(_RESUME_BOOT)
    if committed:
        hist.write_text("\n".join(committed) + "\n", encoding="utf-8")
    fires: list[int] = []
    for f in sorted(glob.glob(str(_RESUME_T00 / "turn_*.json"))):
        n = int(os.path.basename(f).split("_")[1].split(".")[0])
        view = json.loads(Path(f).read_text())
        mrf = _RESUME_T00 / "manager_results" / os.path.basename(f)
        mr = json.loads(mrf.read_text()) if mrf.exists() else {}
        hi = mr.get("handled_intent") or {}
        intent = str(hi.get("intent") or "")
        tac = str((hi.get("payload") or {}).get("tactic") or "")
        if intent == "commit_tactic" and mr.get("ok") and tac:
            committed.append(tac)
            hist.write_text("\n".join(committed) + "\n", encoding="utf-8")
        lines = _bundle_goal_lines(view)
        if not lines:
            continue
        dc = _bundle_dc_proxy(view)
        _enrich_up_to_bad_call(
            dc,
            state={"goal_window": {"lines": lines}},
            debug_refs={"session_dir": scope},
        )
        if "up_to_bad_call" in dc:
            fires.append(n)
    assert 34 not in fires, f"t34 fired in the history path; fires={fires}"
