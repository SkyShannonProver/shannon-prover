r"""Wiring tests for the two verifier-grounded help mechanisms (flag-only):

  CORRECT — `up_to_bad_call` is written into a workspace view's `decision_context`
  by the pure-view enrichment when the current goal post admits a `\/ bad` disjunct
  AND a lockstep `call (_: inv)` move is on offer.

  CATCH — `local_patch_loop` is injected into the returned ManagedTurn's view by
  LoopMonitor.inject across a frozen accepted-patch loop, and is NOT injected when
  `remaining` decreases.

These exercise the actual hook points (the pure helpers have their own unit tests in
test_up_to_bad_coherence.py / test_patch_loop_detector.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_prover_workspace_view import (  # noqa: E402
    _enrich_decision_context,
)
from tests.helpers.builders import drive_osc_loop, loop_goal_view  # noqa: E402
from workflow.proof_management import AgentIntent  # noqa: E402
from workflow.proof_management.types import ManagedTurn  # noqa: E402
from workflow.proof_management import LoopMonitor  # noqa: E402


# ---- CORRECT: pure-view enrichment writes up_to_bad_call --------------------------
def _state_with_post(post_line: str) -> dict:
    return {
        "goal_window": {
            "lines": [
                "equiv[ G1.O ~ G2.O :",
                "  ={glob A} ==>",
                "  " + post_line,
                "]",
            ]
        }
    }


# A decision_context that already offers a lockstep `call (_: Inv)` move.
_DC_WITH_LOCKSTEP_CALL = {
    "proof_options": [
        {"title": "Invariant-call", "tactic": "call (_: ={glob UFCMA} /\\ ={UFCMA.log})."}
    ]
}


def test_CORRECT_enrichment_writes_up_to_bad_call_key() -> None:
    dc = dict(_DC_WITH_LOCKSTEP_CALL)
    _enrich_decision_context(
        dc,
        state=_state_with_post("!(UFCMA.bad1 \\/ UFCMA.bad2){2} => ={res}"),
        frontier={},
        proof_ir={},
        evidence={},
    )
    assert "up_to_bad_call" in dc
    entry = dc["up_to_bad_call"]
    assert entry["certified"] is False
    assert "UFCMA.bad1" in entry["active_bad_events"]
    # Audit 2026-06-09: the pure-view path fires on an OFFERED call — the old
    # phrasing "your `call (_: inv)` is lockstep" asserted a committed call that
    # may not exist (false premise on every offer-triggered banner). The offer
    # wording carries the same structural fact without the false premise.
    assert "the `call (_: inv)` on offer here is lockstep" in entry["text"]
    assert "your `call (_: inv)`" not in entry["text"]


def test_CORRECT_enrichment_silent_on_pure_equiv_post() -> None:
    dc = dict(_DC_WITH_LOCKSTEP_CALL)
    _enrich_decision_context(
        dc,
        state=_state_with_post("={res, glob M}"),  # step3 shape — pure equivalence
        frontier={},
        proof_ir={},
        evidence={},
    )
    assert "up_to_bad_call" not in dc


def test_CORRECT_enrichment_silent_without_lockstep_call_on_offer() -> None:
    # Up-to-bad post present, but no call move is offered — nothing to flag.
    dc: dict = {"proof_options": []}
    _enrich_decision_context(
        dc,
        state=_state_with_post("!(UFCMA.bad1){2} => ={res}"),
        frontier={},
        proof_ir={},
        evidence={},
    )
    assert "up_to_bad_call" not in dc


# ---- CORRECT: end-to-end #1 acceptance on the REAL step4_1 turn_008 goal ----------
import json  # noqa: E402

_REAL_TURN008_VIEW = (
    ROOT / "tests" / "fixtures" / "step4_1_turn008_up_to_bad_view.json"
)


def _state_from_real_turn008() -> dict:
    """The REAL step4_1 Tree_0_0 turn_008 rendered goal — its post is
    `forged{1} => forged{2} \\/ bad2 \\/ bad1` and it carries a parenthesized
    pre-conjunct `(bad1 \\/ inv ...)`. The two-column program block sits BETWEEN
    pre and post, which is exactly what defeated the naive whole-goal parse."""
    view = json.loads(_REAL_TURN008_VIEW.read_text())
    return {"goal_window": {"lines": view["current_goal"]["lines"]}}


def test_enrich_fires_on_real_step4_1_turn008_shape() -> None:
    # The headline #1 acceptance: feeding the REAL turn_008 goal through the pure-view
    # enrichment, with a lockstep call OFFERED, MUST produce up_to_bad_call naming
    # exactly {UFCMA.bad1, UFCMA.bad2}. (Before the fix this either missed bad1 — the
    # parenthesized pre-conjunct was not descended — or captured `forged`.)
    dc = dict(_DC_WITH_LOCKSTEP_CALL)
    assert "up_to_bad_call" not in dc  # before
    _enrich_decision_context(
        dc,
        state=_state_from_real_turn008(),
        frontier={},
        proof_ir={},
        evidence={},
    )
    assert "up_to_bad_call" in dc  # after — FIRES
    entry = dc["up_to_bad_call"]
    assert entry["active_bad_events"] == ["UFCMA.bad1", "UFCMA.bad2"]
    assert entry["certified"] is False


def test_enrich_real_step4_1_silent_without_offered_call() -> None:
    # Same real up-to-bad goal, but no call move on offer -> the enrichment is silent
    # (fire-on-offer is gated on an OFFERED lockstep call, never on goal shape alone).
    dc: dict = {"proof_options": []}
    _enrich_decision_context(
        dc,
        state=_state_from_real_turn008(),
        frontier={},
        proof_ir={},
        evidence={},
    )
    assert "up_to_bad_call" not in dc


# ---- PRECISION: end-to-end on the REAL step4_1 turn_005 (binder-strip) -------------
_REAL_TURN005_VIEW = (
    ROOT / "tests" / "fixtures" / "step4_1_turn005_up_to_bad_view.json"
)


def _state_from_real_turn005() -> dict:
    """The REAL step4_1 Tree_0_0 turn_005 rendered goal. Its post is a `&&` of a
    parenthesized `(!UFCMA.bad1{2} => ... inv ...)` conjunct and a `forall (...
    bad1_R : bool ...) ... => bad1_R \\/ inv ...`. The binder local `bad1_R` is NOT a
    bad event; only the module-qualified `UFCMA.bad1` is. (This goal LEAKED `bad1_R`
    before the binder-strip — the banner read 'diverge when UFCMA.bad1, bad1_R'.)"""
    view = json.loads(_REAL_TURN005_VIEW.read_text())
    return {"goal_window": {"lines": view["current_goal"]["lines"]}}


def test_enrich_real_step4_1_turn005_excludes_bad1_R() -> None:
    # PRECISION acceptance: feeding the REAL turn_005 goal through the pure-view
    # enrichment, with a lockstep call OFFERED, MUST name EXACTLY {UFCMA.bad1} — the
    # quantifier-bound `bad1_R` is stripped. (Before the binder-strip the banner
    # listed active_bad_events == ['UFCMA.bad1', 'bad1_R'].)
    dc = dict(_DC_WITH_LOCKSTEP_CALL)
    assert "up_to_bad_call" not in dc  # before
    _enrich_decision_context(
        dc,
        state=_state_from_real_turn005(),
        frontier={},
        proof_ir={},
        evidence={},
    )
    assert "up_to_bad_call" in dc  # after — still FIRES on the genuine bad
    entry = dc["up_to_bad_call"]
    assert entry["active_bad_events"] == ["UFCMA.bad1"], entry["active_bad_events"]
    assert "bad1_R" not in entry["active_bad_events"]
    assert entry["certified"] is False


# ---- E1: REAL step4_1 resume Tree_0_0 turn_034 stays NEUTRAL (carried-bad offer) ---
_REAL_TURN034_VIEW = (
    ROOT / "tests" / "fixtures" / "step4_1_turn034_up_to_bad_view.json"
)


def _dc_from_real_turn(view: dict) -> dict:
    """The decision_context proxy built from the view's OWN `candidate_moves` — so the
    actual t34 offer (a single-clause lockstep `call (_: UFCMA.bad1{2} /\\ (...))` that
    carries `UFCMA.bad1` as a top conjunct) is what the gates see, not a synthetic
    offer."""
    cm = view.get("candidate_moves") or {}
    opts = []
    for mv in cm.get("moves") or []:
        if isinstance(mv, dict):
            opts.append(
                {
                    "title": str(mv.get("title") or ""),
                    "tactic": str(mv.get("tactic_shape") or mv.get("tactic") or ""),
                    "guidance": "",
                    "applicability": str(mv.get("applicability") or ""),
                }
            )
    return {"proof_options": opts}


def test_E1_real_step4_1_turn034_stays_neutral_carried_bad_offer() -> None:
    # E1 acceptance: with the harvest re-split fix, the t34 pre block harvests
    # {UFCMA.bad1} (previously ∅). That alone would un-silence t34, but its offered
    # single-clause lockstep call already CARRIES bad1 as a top-level conjunct, so the
    # widened gate (a2) keeps the frontier NEUTRAL. Pinned end-to-end on the REAL view.
    view = json.loads(_REAL_TURN034_VIEW.read_text())
    lines = [str(x) for x in view["current_goal"]["lines"]]

    # (1) the harvest now sees the deeply-nested up-to-bad disjunct.
    from core.easycrypt.session_prover_workspace_view import _up_to_bad_names_in_goal

    assert _up_to_bad_names_in_goal(lines) == {"UFCMA.bad1"}

    # (2) the pure-view enrichment, with the view's OWN carried-bad offer, does NOT
    # fire (gate (a2) silences). Pure-view path: debug_refs=None.
    dc = _dc_from_real_turn(view)
    _enrich_decision_context(
        dc,
        state={"goal_window": {"lines": lines}},
        frontier={},
        proof_ir={},
        evidence={},
    )
    assert "up_to_bad_call" not in dc


# ---- CATCH: manager injects local_patch_loop -------------------------------------
def _bare_manager() -> LoopMonitor:
    """A fresh LoopMonitor (the unit `inject` / `_up_to_bad_frontier` live on now),
    window sized for the short synthetic loops these tests drive. Its defaults
    (armed, empty episode-set, rearm_after=2) match the old hand-built shell."""
    return LoopMonitor(window=8)


def _goal_view(label: str, remaining: int, *, moves: list | None = None) -> dict:
    """A rendered-view stub whose fingerprint is keyed by ``label`` + ``remaining``."""
    return loop_goal_view(label, remaining, moves=moves, with_prompt_line=False)


def _commit_turn(view: dict, tactic: str) -> ManagedTurn:
    return ManagedTurn(
        ok=True,
        workspace_view=view,
        intent=AgentIntent(intent="commit_tactic", payload={"tactic": tactic}),
        manager_actions=[{"agent_observation": {}}],  # no error_summary => accepted
    )


def _drive_osc_loop(m: LoopMonitor, *, make_loop_view, make_away_view,
                    full_view=None) -> ManagedTurn:
    """Drive a genuine arrive-leave-arrive loop (A/B/A/B/A, all ACCEPTED commits)
    through the LoopMonitor inject path; return the final (arrival) turn. Pass
    ``full_view`` to also mirror the banner into a stored audit view.

    The audited-false frozen-stutter shape (one accepted commit + same-view
    echoes) no longer fires by design — a recurrence hit now needs an accepted
    re-arrival after genuinely leaving via an accepted commit elsewhere."""
    def commit(view: dict, tactic: str) -> ManagedTurn:
        turn = _commit_turn(view, tactic)
        m.inject(turn, full_view=full_view)
        return turn

    turns = drive_osc_loop(
        commit, make_loop_view=make_loop_view, make_away_view=make_away_view,
    )
    last = turns[-1]
    assert last is not None
    return last


def test_CATCH_manager_injects_local_patch_loop() -> None:
    # Genuine macro-cycle: the agent keeps ARRIVING BACK (accepted commits) at the
    # same remaining:5 goal after working elsewhere (accepted commits on a
    # different remaining:4 goal), and the floor between returns stops improving.
    m = _bare_manager()
    last = _drive_osc_loop(
        m,
        make_loop_view=lambda: _goal_view("LOOP-A", 5),
        make_away_view=lambda: _goal_view("AWAY-B", 4),
    )
    dc = last.workspace_view.get("decision_context")
    assert isinstance(dc, dict) and "local_patch_loop" in dc
    flag = dc["local_patch_loop"]
    assert flag["certified"] is False
    assert "patch loop, not progress" in flag["text"]
    # NEUTRAL banner here: no up-to-bad shape / call offer on this frontier.
    assert "up-to-bad" not in flag["text"]


def test_CATCH_banner_reaches_both_lean_and_full_view() -> None:
    # #12 step 3: the patch-loop banner is the one STATEFUL surface; it must
    # also reach the stored full (audit) view — not just the agent-facing lean
    # view — so the committed/replayed view stays faithful to what the agent saw.
    # The manager passes its lifecycle.latest_full_view as inject(full_view=...);
    # here we hand the same dict straight to the drive helper.
    m = _bare_manager()
    full_view: dict = {}
    last = _drive_osc_loop(
        m,
        make_loop_view=lambda: _goal_view("LOOP-A", 5),
        make_away_view=lambda: _goal_view("AWAY-B", 4),
        full_view=full_view,
    )
    # agent-facing lean view (unchanged behaviour)
    assert "local_patch_loop" in last.workspace_view["decision_context"]
    # audit view now carries the identical banner
    assert "local_patch_loop" in full_view["decision_context"]
    assert (full_view["decision_context"]["local_patch_loop"]
            == last.workspace_view["decision_context"]["local_patch_loop"])


def test_CATCH_manager_silent_when_remaining_decreases() -> None:
    m = _bare_manager()
    last: ManagedTurn | None = None
    for rem in (5, 4, 3):
        last = _commit_turn(_goal_view("LOOP-A", rem), "auto.")
        m.inject(last)
    assert last is not None
    dc = last.workspace_view.get("decision_context")
    # Either no decision_context written, or it lacks the loop key.
    assert not (isinstance(dc, dict) and "local_patch_loop" in dc)


def test_CATCH_manager_never_raises_on_malformed_turn() -> None:
    m = _bare_manager()
    bad = ManagedTurn(ok=True, workspace_view={}, intent=None, manager_actions=None)  # type: ignore[arg-type]
    m.inject(bad)  # must not raise


# ---- DELIVERY: sanitize preserves the decision_context panel keys ------------------
# (2026-06-09 panel audit, governing finding: `_migrate_legacy_panels` ended with an
# unconditional pop('decision_context'), so EVERY banner died in sanitize while the
# dict-level tests above stayed green. These tests pin the repaired channel at the
# exact layer that broke.)
from core.easycrypt.session_workspace_view_manager import (  # noqa: E402
    WorkspaceViewManager,
)

_PATCH_LOOP_ENTRY = {
    "key": "local_patch_loop",
    "text": (
        "Your accepted commits have arrived back at this identical goal 3 times "
        "— each return after working elsewhere — without restructuring, and the "
        "open-goal floor between returns has stopped improving. This is a patch "
        "loop, not progress. The lever is upstream — reconsider the structural "
        "tactic that produced this frontier rather than another local patch."
    ),
    "recurrences": 3,
    "remaining": 5,
    "fingerprint": "abcdef0123456789",
    "certified": False,
    "guarantee": "UNCERTIFIED observation — NOT a verdict and NOT a gate.",
}

_UP_TO_BAD_ENTRY = {
    "text": (
        "Upstream postcondition admits `\\/ UFCMA.bad1`; the `call (_: inv)` on "
        "offer here is lockstep (no bad clause). Consider the up-to-bad form "
        "`call (_: UFCMA.bad1, <inv>)`."
    ),
    "active_bad_events": ["UFCMA.bad1"],
    "candidate": "call (_: UFCMA.bad1, <inv>).",
    "certified": False,
    "guarantee": "UNCERTIFIED suggestion — NOT a verdict and NOT a gate.",
}


def _view_with_signals() -> dict:
    return {
        "current_goal": {"lines": ["pre = true", "post = ={res}"]},
        "proof_status": {"remaining_goals": 5, "current_layer": "call_site"},
        "candidate_moves": {"moves": [{"title": "x", "tactic_shape": "auto."}]},
        "application_context": {"note": "n"},
        "decision_context": {
            "local_patch_loop": dict(_PATCH_LOOP_ENTRY),
            "up_to_bad_call": dict(_UP_TO_BAD_ENTRY),
        },
    }


def test_SANITIZE_preserves_decision_context_panel_keys() -> None:
    # The break the audit pinned: sanitize_agent_view -> _migrate_legacy_panels
    # unconditionally popped decision_context. The panel keys must now survive
    # sanitize verbatim (this is the test shape that would have caught the break:
    # it exercises the REAL sanitize path, not the pre-sanitize dict).
    clean = WorkspaceViewManager().sanitize_agent_view(_view_with_signals())
    dc = clean.get("decision_context")
    assert isinstance(dc, dict), "decision_context dropped by sanitize"
    assert dc["local_patch_loop"]["text"] == _PATCH_LOOP_ENTRY["text"]
    assert dc["up_to_bad_call"]["text"] == _UP_TO_BAD_ENTRY["text"]
    assert dc["local_patch_loop"]["certified"] is False


def test_SANITIZE_preserves_panel_keys_through_agent_display_view() -> None:
    # agent_display_view = sanitize + order + metadata hiding: the full pipeline
    # _render_manager_followup runs the turn view through.
    shown = WorkspaceViewManager().agent_display_view(_view_with_signals())
    dc = shown.get("decision_context")
    assert isinstance(dc, dict)
    assert set(dc) == {"local_patch_loop", "up_to_bad_call"}


def test_SANITIZE_still_drops_internal_decision_context_shapes() -> None:
    # Legacy-migration duty unchanged: internal decision_context keys
    # (proof_options/limitations) are still projected into candidate_moves and
    # NOT exposed; with no panel signal present, no decision_context key remains.
    view = {
        "current_goal": {"lines": ["g"]},
        "decision_context": {
            "proof_options": [{"title": "opt", "category": "strategy",
                               "tactic": "auto."}],
            "limitations": [{"reason": "r"}],
        },
    }
    clean = WorkspaceViewManager().sanitize_agent_view(view)
    assert "decision_context" not in clean
    assert isinstance(clean.get("candidate_moves"), dict)  # migrated, not lost


def test_SANITIZE_panel_keys_survive_alongside_legacy_migration() -> None:
    # A decision_context carrying BOTH internal shapes and a panel signal: the
    # internal part still migrates into candidate_moves, the signal survives.
    view = {
        "current_goal": {"lines": ["g"]},
        "decision_context": {
            "proof_options": [{"title": "opt", "category": "strategy",
                               "tactic": "auto."}],
            "up_to_bad_call": dict(_UP_TO_BAD_ENTRY),
        },
    }
    clean = WorkspaceViewManager().sanitize_agent_view(view)
    dc = clean.get("decision_context")
    assert isinstance(dc, dict) and set(dc) == {"up_to_bad_call"}
    assert isinstance(clean.get("candidate_moves"), dict)


# ---- DELIVERY: end-to-end — banner reaches the agent-read followup markdown --------
# (SPEC-A core deliverable: these tests walk the FULL production render path —
# manager inject -> _render_manager_followup -> agent_display_view -> markdown +
# the three landing points — and go RED if any link of the channel breaks again.)
from workflow.proof_node_runtime import (  # noqa: E402
    NodeMemory,
    _render_manager_followup,
)
from playground.node_boot import render_followup, surface_turn_of  # noqa: E402


def _render_e2e(turn: ManagedTurn, tmp_path, *, full_view: dict | None,
                turn_index: int = 5, intent: str = "commit_tactic") -> tuple:
    memory = NodeMemory(tmp_path, "Tree_0_0")
    followup = _render_manager_followup(
        turn,
        turn_index,
        {"intent": intent, "payload": {"tactic": "smt()."}},
        memory=memory,
        full_view=full_view,
        surface_profile=None,
    )
    return followup, memory


def test_E2E_CATCH_banner_reaches_followup_markdown_and_archives(tmp_path) -> None:
    # A manager turn that genuinely FIRES, then the FULL production render path.
    m = _bare_manager()
    last = _drive_osc_loop(
        m,
        make_loop_view=lambda: _goal_view("LOOP-A", 5),
        make_away_view=lambda: _goal_view("AWAY-B", 4),
    )
    flag = last.workspace_view["decision_context"]["local_patch_loop"]
    # Production lag shape: latest_full_view does NOT carry the injected flag
    # (the manager injects into the returned turn view after projection).
    full_view = _goal_view("LOOP-A", 5)
    followup, memory = _render_e2e(last, tmp_path, full_view=full_view)

    # Landing point 1: the agent-read followup markdown. The raw decision_context
    # signal is now rendered through SurfaceModel panel facts, not a Manager-signal
    # side channel or raw JSON dump.
    assert flag["text"] in followup
    assert "Patch-loop observation" in followup
    assert "Manager signal" not in followup
    assert '"local_patch_loop"' not in followup  # not a raw JSON dump
    # Landing point 2: latest_workspace_view.json.
    latest = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    assert latest["decision_context"]["local_patch_loop"]["text"] == flag["text"]
    # Landing point 3: the per-turn archived view + followup.
    archived = json.loads(
        (memory.workspace_views_dir / "turn_005.json").read_text(encoding="utf-8")
    )
    assert archived["decision_context"]["local_patch_loop"]["text"] == flag["text"]
    assert flag["text"] in (memory.followups_dir / "turn_005.md").read_text(
        encoding="utf-8"
    )


def test_E2E_CORRECT_banner_from_full_view_when_lean_view_lacks_it(tmp_path) -> None:
    # The CORRECT signal is written by the view renderer into the FULL view; a
    # lean surface profile may have stripped decision_context from the turn view.
    # Delivery must still happen (merged from the full/audit view).
    lean_view = _goal_view("LOOP-A", 5)
    full_view = _goal_view("LOOP-A", 5)
    full_view["decision_context"] = {"up_to_bad_call": dict(_UP_TO_BAD_ENTRY)}
    turn = _commit_turn(lean_view, "call (_: ={glob A}).")
    followup, memory = _render_e2e(turn, tmp_path, full_view=full_view)

    assert _UP_TO_BAD_ENTRY["text"] not in followup
    assert "Up-to-bad call compatibility" in followup
    assert "call (_: UFCMA.bad1, <inv>)." in followup
    assert "Manager signal" not in followup
    latest = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    assert latest["decision_context"]["up_to_bad_call"]["candidate"] == (
        _UP_TO_BAD_ENTRY["candidate"]
    )


def test_PLAYGROUND_surface_turn_merges_full_view_decision_context_for_cards() -> None:
    # The playground card must consume the same merged full-view signal as the
    # agent-read followup. Otherwise the followup can show a fact that the human
    # card silently drops.
    lean_view = _goal_view("LOOP-A", 5)
    full_view = _goal_view("LOOP-A", 5)
    full_view["decision_context"] = {"up_to_bad_call": dict(_UP_TO_BAD_ENTRY)}

    surface_turn = surface_turn_of(
        lean_view,
        "l4_checked_action_surface",
        full_view=full_view,
    )
    proof = surface_turn["proof_surface"]
    facts = {
        fact.get("key"): fact
        for fact in proof["primary_panel"].get("facts", [])
    }

    assert "up_to_bad_call_compatibility" in facts
    value = facts["up_to_bad_call_compatibility"]["value"]
    assert value["relevant_call_form_family"] == "call (_: UFCMA.bad1, <inv>)."
    assert "Manager signal" not in json.dumps(surface_turn, ensure_ascii=False)


def test_PLAYGROUND_readonly_overlay_does_not_capture_proof_state_decision_context() -> None:
    # A read-only result is an overlay.  Proof-state decision_context facts must
    # remain on the base proof surface, not be appended to the requested context
    # result panel below the buttons.
    base_view = _goal_view("LOOP-A", 5)
    readonly_view = {
        **_goal_view("LOOP-A", 5),
        "last_result": {
            "intent": "tactic_forms",
            "payload": {"name": "conseq"},
            "result": "Read-only context returned.",
            "proof_state": "unchanged",
            "content": {
                "title": "Tactic Form Reference",
                "preview": "=== conseq tactic -- argument forms ===",
            },
        },
    }
    full_view = _goal_view("LOOP-A", 5)
    full_view["decision_context"] = {"up_to_bad_call": dict(_UP_TO_BAD_ENTRY)}

    surface_turn = surface_turn_of(
        readonly_view,
        "l4_checked_action_surface",
        base_view=base_view,
        full_view=full_view,
    )

    proof_blob = json.dumps(surface_turn["proof_surface"], ensure_ascii=False)
    overlay_blob = json.dumps(surface_turn["overlay_surface"], ensure_ascii=False)
    assert "Up-to-bad call compatibility" in proof_blob
    assert "Up-to-bad call compatibility" not in overlay_blob
    assert "conseq tactic" in overlay_blob


def test_PLAYGROUND_followup_uses_same_full_view_as_cards() -> None:
    # The followup tab and card tab must be two renderers over the same
    # SurfaceTurnModel inputs. In particular, a full-view decision_context fact
    # belongs to the base proof surface, before any read-only overlay.
    base_view = _goal_view("LOOP-A", 5)
    readonly_view = {
        **_goal_view("LOOP-A", 5),
        "last_result": {
            "intent": "tactic_forms",
            "payload": {"name": "conseq"},
            "result": "Read-only context returned.",
            "proof_state": "unchanged",
            "content": {
                "title": "Tactic Form Reference",
                "preview": "=== conseq tactic -- argument forms ===",
            },
        },
    }
    full_view = _goal_view("LOOP-A", 5)
    full_view["decision_context"] = {"up_to_bad_call": dict(_UP_TO_BAD_ENTRY)}

    md = render_followup(
        object(),
        readonly_view,
        "l4_checked_action_surface",
        base_view=base_view,
        full_view=full_view,
    )

    assert md.index("Up-to-bad call compatibility") < md.index("## Read-only result")
    assert md.index("## Read-only result") < md.index("conseq tactic")


def test_E2E_empty_decision_context_renders_nothing(tmp_path) -> None:
    # No signal -> no "Manager signal" block, no decision_context key in archives.
    turn = _commit_turn(_goal_view("LOOP-A", 5), "auto.")
    followup, memory = _render_e2e(turn, tmp_path, full_view=_goal_view("LOOP-A", 5))
    assert "Manager signal" not in followup
    latest = json.loads(memory.latest_view.read_text(encoding="utf-8"))
    assert "decision_context" not in latest


def test_E2E_production_builder_emits_decision_context_key() -> None:
    # The producer-side dead-end the audit pinned: _workspace_panel returned a
    # dict WITHOUT a decision_context key, so the enrichment's write was
    # unreachable no matter what downstream did. Build a view through the REAL
    # production builder (which also runs sanitize internally) and assert the
    # signal key is on the final view.
    from core.easycrypt.session_prover_workspace_view import (
        build_prover_workspace_view_from_context,
    )
    proof_context_view = {
        "ok": True,
        "proof_state": {"status": "open", "goal": {"goal_type": "equiv"}},
        "current_goal": {
            "active_goal_text": (
                "equiv[ G1.O ~ G2.O :\n"
                "  ={glob A} ==>\n"
                "  !(UFCMA.bad1 \\/ UFCMA.bad2){2} => ={res}\n"
                "]"
            ),
            "goal_type": "equiv",
        },
        "actions": [
            {
                "category": "commit",
                "title": "Invariant-call route",
                "tactic": "call (_: ={glob A} /\\ ={UFCMA.log}).",
                "why": "lockstep call on offer",
            }
        ],
    }
    view = build_prover_workspace_view_from_context(proof_context_view)
    dc = view.get("decision_context")
    assert isinstance(dc, dict), (
        "production builder lost decision_context (dead-end write regression)"
    )
    entry = dc.get("up_to_bad_call")
    assert isinstance(entry, dict)
    assert "UFCMA.bad1" in entry.get("active_bad_events", [])
    assert entry.get("certified") is False


def test_E2E_production_builder_omits_key_when_no_signal() -> None:
    from core.easycrypt.session_prover_workspace_view import (
        build_prover_workspace_view_from_context,
    )
    proof_context_view = {
        "ok": True,
        "proof_state": {"status": "open", "goal": {"goal_type": "equiv"}},
        "current_goal": {
            "active_goal_text": "equiv[ G1.O ~ G2.O : ={glob A} ==> ={res} ]",
            "goal_type": "equiv",
        },
        "actions": [],
    }
    view = build_prover_workspace_view_from_context(proof_context_view)
    assert "decision_context" not in view


# ---- SPEC-G: committed-history coherence is wired into the per-turn main path -------
# The byequiv post that establishes the up-to-bad disjunct is committed at the lineage
# root; downstream logical subgoals no longer RENDER the `\/ bad` disjunction. The
# goal-local harvest alone is ∅ on those subgoals (the step4_1 resume Tree_0_1 FN the
# audit found). With the committed-history union the fact now surfaces — through the
# SAME single emit path + the same gates + the same dedup ledger (no second producer,
# no double-fire).
_HISTORY_BYEQUIV = (
    "byequiv (_: ={glob A} ==> (res{1} => ((res \\/ UFCMA.bad2) \\/ UFCMA.bad1){2}))."
)
# A downstream logical subgoal whose own post carries NO `\/ bad` disjunction.
_DOWNSTREAM_SUBGOAL_LINES = [
    "equiv[ G1.O ~ G2.O :",
    "  ={glob A, x} ==>",
    "  ={res, glob M}",
    "]",
]


def _write_history(session_dir: Path, tactics: list[str]) -> str:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "history.ec").write_text(
        "\n".join(tactics) + "\n", encoding="utf-8"
    )
    return str(session_dir)


def test_SPECG_history_harvest_collects_byequiv_bads(tmp_path) -> None:
    from core.easycrypt.session_prover_workspace_view import (
        _committed_history_uptobad_names,
    )
    scope = _write_history(tmp_path / "s", [_HISTORY_BYEQUIV, "proc.", "sp."])
    assert _committed_history_uptobad_names(scope) == {"UFCMA.bad1", "UFCMA.bad2"}


def test_SPECG_history_harvest_empty_without_uptobad_byequiv(tmp_path) -> None:
    from core.easycrypt.session_prover_workspace_view import (
        _committed_history_uptobad_names,
    )
    scope = _write_history(
        tmp_path / "s",
        ["byequiv (_: ={glob A, x} ==> ={res, glob M}).", "proc.", "auto."],
    )
    assert _committed_history_uptobad_names(scope) == set()


def test_SPECG_history_harvest_empty_when_no_session_dir() -> None:
    from core.easycrypt.session_prover_workspace_view import (
        _committed_history_uptobad_names,
    )
    assert _committed_history_uptobad_names("") == set()
    assert _committed_history_uptobad_names("/no/such/dir/at/all") == set()


def test_SPECG_pure_view_fires_from_history_when_goal_lacks_disjunct(tmp_path) -> None:
    # The Tree_0_1 FN shape: the current subgoal carries NO `\/ bad`, but the committed
    # byequiv in history does. The union makes the fact fire.
    from core.easycrypt.session_prover_workspace_view import (
        _UP_TO_BAD_EPISODE_LATCH,
        _enrich_decision_context,
        _up_to_bad_names_in_goal,
    )
    _UP_TO_BAD_EPISODE_LATCH.clear()
    scope = _write_history(tmp_path / "s", [_HISTORY_BYEQUIV, "proc."])
    assert _up_to_bad_names_in_goal(_DOWNSTREAM_SUBGOAL_LINES) == set()  # goal-local ∅
    dc = dict(_DC_WITH_LOCKSTEP_CALL)
    _enrich_decision_context(
        dc,
        state={"goal_window": {"lines": _DOWNSTREAM_SUBGOAL_LINES}},
        frontier={}, proof_ir={}, evidence={},
        debug_refs={"session_dir": scope},
    )
    assert "up_to_bad_call" in dc  # fires purely from the committed-history union
    entry = dc["up_to_bad_call"]
    assert set(entry["active_bad_events"]) == {"UFCMA.bad1", "UFCMA.bad2"}
    # correct2fix E1/E2: 2-clause candidate covering BOTH bads.
    assert entry["candidate"] == "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>)."
    assert entry["certified"] is False


def test_SPECG_no_history_no_goal_disjunct_stays_silent(tmp_path) -> None:
    # Control: same downstream subgoal, but the committed history has NO up-to-bad
    # byequiv -> the union is ∅ -> silent (the history wiring did not widen the
    # trigger surface on plain-equiv lineages).
    from core.easycrypt.session_prover_workspace_view import (
        _UP_TO_BAD_EPISODE_LATCH,
        _enrich_decision_context,
    )
    _UP_TO_BAD_EPISODE_LATCH.clear()
    scope = _write_history(
        tmp_path / "s",
        ["byequiv (_: ={glob A, x} ==> ={res, glob M}).", "proc."],
    )
    dc = dict(_DC_WITH_LOCKSTEP_CALL)
    _enrich_decision_context(
        dc,
        state={"goal_window": {"lines": _DOWNSTREAM_SUBGOAL_LINES}},
        frontier={}, proof_ir={}, evidence={},
        debug_refs={"session_dir": scope},
    )
    assert "up_to_bad_call" not in dc


def test_SPECG_gate_c_silences_history_when_committed_call_is_uptobad(tmp_path) -> None:
    # The Tree_0_0 resume shape: history carries the up-to-bad byequiv AND a committed
    # 2-clause `call (_: UFCMA.bad1, inv ...)` (the agent already handled it). Gate (c)
    # must SILENCE — the history union does NOT defeat the already-handled gates.
    from core.easycrypt.session_prover_workspace_view import (
        _UP_TO_BAD_EPISODE_LATCH,
        _enrich_decision_context,
    )
    _UP_TO_BAD_EPISODE_LATCH.clear()
    scope = _write_history(
        tmp_path / "s",
        [
            _HISTORY_BYEQUIV,
            "proc.",
            "call (_: UFCMA.bad1, inv RO.m{1} RO.m{2} UFCMA.log{2}).",
        ],
    )
    dc = dict(_DC_WITH_LOCKSTEP_CALL)
    _enrich_decision_context(
        dc,
        state={"goal_window": {"lines": _DOWNSTREAM_SUBGOAL_LINES}},
        frontier={}, proof_ir={}, evidence={},
        debug_refs={"session_dir": scope},
    )
    assert "up_to_bad_call" not in dc  # gate (c) wins over the history union


def test_SPECG_dedup_one_fire_per_episode_no_double_from_two_sources(tmp_path) -> None:
    # No double-fire: a fact present in BOTH the goal-local harvest AND the committed
    # history fires exactly ONCE per episode (single emit path + one dedup ledger).
    from core.easycrypt.session_prover_workspace_view import (
        _UP_TO_BAD_EPISODE_LATCH,
        _enrich_decision_context,
    )
    _UP_TO_BAD_EPISODE_LATCH.clear()
    scope = _write_history(tmp_path / "s", [_HISTORY_BYEQUIV, "proc."])
    # Goal that ALSO renders the disjunction (so both sources carry {bad1,bad2}).
    goal_both = {
        "goal_window": {
            "lines": [
                "equiv[ G1.O ~ G2.O :",
                "  ={glob A} ==>",
                "  forged{1} => forged{2} \\/ UFCMA.bad2{2} \\/ UFCMA.bad1{2}",
                "]",
            ]
        }
    }
    fires = 0
    for _ in range(4):  # 4 consecutive identical-fact views
        dc = dict(_DC_WITH_LOCKSTEP_CALL)
        _enrich_decision_context(
            dc, state=goal_both, frontier={}, proof_ir={}, evidence={},
            debug_refs={"session_dir": scope},
        )
        if "up_to_bad_call" in dc:
            fires += 1
    assert fires == 1  # episode dedup: exactly one fire across the 4 identical views


def test_SPECG_e2e_production_builder_emits_from_history_only(tmp_path) -> None:
    # End-to-end through the REAL production builder: the current goal carries NO
    # `\/ bad`, the committed `history.ec` does -> the built view's decision_context
    # carries up_to_bad_call (the Tree_0_1 FN, now delivered).
    from core.easycrypt.session_prover_workspace_view import (
        _UP_TO_BAD_EPISODE_LATCH,
        build_prover_workspace_view_from_context,
    )
    _UP_TO_BAD_EPISODE_LATCH.clear()
    scope = _write_history(tmp_path / "s", [_HISTORY_BYEQUIV, "proc."])
    proof_context_view = {
        "ok": True,
        "proof_state": {"status": "open", "goal": {"goal_type": "equiv"}},
        "current_goal": {
            "active_goal_text": "\n".join(_DOWNSTREAM_SUBGOAL_LINES),
            "goal_type": "equiv",
        },
        "actions": [
            {
                "category": "commit",
                "title": "Invariant-call route",
                "tactic": "call (_: ={glob A} /\\ ={UFCMA.log}).",
                "why": "lockstep call on offer",
            }
        ],
        "debug_refs": {"session_dir": scope},
    }
    view = build_prover_workspace_view_from_context(proof_context_view)
    dc = view.get("decision_context")
    assert isinstance(dc, dict), "history-sourced signal lost the decision_context key"
    entry = dc.get("up_to_bad_call")
    assert isinstance(entry, dict)
    assert set(entry.get("active_bad_events", [])) == {"UFCMA.bad1", "UFCMA.bad2"}


def test_SPECG_e2e_history_sourced_banner_reaches_followup_markdown(tmp_path) -> None:
    # The full delivery chain for the history-sourced fact: build the view through the
    # production builder, then render the manager followup. The verbatim banner text
    # must land in the agent-read markdown through SurfaceModel panel facts,
    # proving the mechanism-layer fact is now AGENT-VISIBLE without a side channel.
    from core.easycrypt.session_prover_workspace_view import (
        _UP_TO_BAD_EPISODE_LATCH,
        build_prover_workspace_view_from_context,
    )
    _UP_TO_BAD_EPISODE_LATCH.clear()
    scope = _write_history(tmp_path / "s", [_HISTORY_BYEQUIV, "proc."])
    proof_context_view = {
        "ok": True,
        "proof_state": {"status": "open", "goal": {"goal_type": "equiv"}},
        "current_goal": {
            "active_goal_text": "\n".join(_DOWNSTREAM_SUBGOAL_LINES),
            "goal_type": "equiv",
        },
        "actions": [
            {
                "category": "commit",
                "title": "Invariant-call route",
                "tactic": "call (_: ={glob A} /\\ ={UFCMA.log}).",
                "why": "lockstep call on offer",
            }
        ],
        "debug_refs": {"session_dir": scope},
    }
    full_view = build_prover_workspace_view_from_context(proof_context_view)
    banner_text = full_view["decision_context"]["up_to_bad_call"]["text"]
    turn = _commit_turn(_goal_view("LOOP-A", 5), "call (_: ={glob A}).")
    followup, memory = _render_e2e(turn, tmp_path / "mem", full_view=full_view)
    assert banner_text not in followup
    assert "Up-to-bad call compatibility" in followup
    assert "call (_: (UFCMA.bad1 \\/ UFCMA.bad2), <inv>)." in followup
    assert "Manager signal" not in followup
    assert '"up_to_bad_call"' not in followup  # readable block, not a JSON dump


# ---- DELIVERY: call-aware wiring reads live-shaped views ---------------------------
_REAL_TURN005_LIVE_VIEW = json.loads(_REAL_TURN005_VIEW.read_text())


def test_CALLAWARE_up_to_bad_frontier_true_on_live_candidate_moves() -> None:
    # The audited structural-False: _up_to_bad_frontier read ONLY
    # decision_context.proof_options, which live views never carry. It must read
    # the live `candidate_moves.moves[]` offer. Here the offered call is a GENUINE
    # lockstep `call (_: inv)` (invariant carries NO bad) on an up-to-bad goal with
    # no committed 2-clause call in scope -> none of gates (a)/(b)/(c) fire -> True.
    m = _bare_manager()
    view = {
        "current_goal": {
            "lines": [
                "Current goal (remaining: 5)",
                "",
                "post = forged{1} => forged{2} \\/ UFCMA.bad1{2}",
                "[700|check]>",
            ],
            "view_focus": "call_site",
        },
        "proof_status": {"remaining_goals": 5, "current_layer": "call_site"},
        "candidate_moves": {
            "moves": [
                {"title": "Invariant-call route",
                 "tactic_shape": "call (_: ={glob A} /\\ ={UFCMA.log})."}
            ]
        },
    }
    assert m._up_to_bad_frontier(view) is True


def test_CALLAWARE_up_to_bad_frontier_false_when_offer_already_handles_bad() -> None:
    # D7 regression pin (2026-06-09 round-3 re-audit): the REAL step4_1 resume
    # turn_005 view carries an up-to-bad goal AND a call offer, but the offered
    # template's invariant already negates the bad (`!UFCMA.bad1{2}` — it is
    # obligation (1) of a 2-clause call already in the prefix). The call-aware
    # tail "re-issue your call in up-to-bad form" is wrong-domain here, so the
    # frontier check must apply the SAME gate-(a) the enrichment does and return
    # False (banner stays NEUTRAL). Before the fix this leaked True via the
    # ungated harvest, flipping the flagship t34 banner to call-aware.
    m = _bare_manager()
    assert m._up_to_bad_frontier(_REAL_TURN005_LIVE_VIEW) is False


def test_CALLAWARE_up_to_bad_frontier_false_without_offer() -> None:
    m = _bare_manager()
    view = json.loads(_REAL_TURN005_VIEW.read_text())
    view.pop("candidate_moves", None)
    view.pop("decision_context", None)
    assert m._up_to_bad_frontier(view) is False


def test_CALLAWARE_up_to_bad_frontier_false_without_bad_shape() -> None:
    m = _bare_manager()
    view = _goal_view(
        "PLAIN", 5,
        moves=[{"title": "Invariant-call route",
                "tactic_shape": "call (_: ={glob A})."}],
    )
    assert m._up_to_bad_frontier(view) is False


def test_CALLAWARE_banner_tail_swaps_on_live_shaped_loop_view() -> None:
    # End-to-end variant gating: a genuine loop whose arrival views carry the
    # up-to-bad goal shape + a live candidate_moves call offer gets the
    # CALL-AWARE tail; the detection semantics themselves are untouched.
    def loop_view() -> dict:
        v = {
            "current_goal": {
                "lines": [
                    "equiv[ G1.O ~ G2.O :",
                    "  ={glob A} ==>",
                    "  !(UFCMA.bad1 \\/ UFCMA.bad2){2} => ={res}",
                    "]",
                ]
            },
            "proof_status": {
                "remaining_goals": 5, "current_layer": "call_site",
            },
            "candidate_moves": {
                "moves": [{
                    "title": "Invariant-call route",
                    "tactic_shape": "call (_: ={glob A} /\\ ={UFCMA.log}).",
                }]
            },
        }
        return v

    m = _bare_manager()
    last: ManagedTurn | None = None
    for i in range(3):
        if i:
            away = _commit_turn(_goal_view("AWAY-B", 4), "auto.")
            m.inject(away)
        last = _commit_turn(loop_view(), "smt().")
        m.inject(last)
    assert last is not None
    dc = last.workspace_view.get("decision_context")
    assert isinstance(dc, dict) and "local_patch_loop" in dc
    assert "re-issue your `call` in up-to-bad form" in dc["local_patch_loop"]["text"]
