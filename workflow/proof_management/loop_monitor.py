"""Local-patch / no-progress loop detection (the manager's "mechanism CATCH").

Extracted from ``ProofNodeManager`` (audit §8 #8): the manager used to hold ~10
``_patch_loop_*`` fields, three trace-tuned magic numbers, and the ~230-line
``_inject_patch_loop_signal`` directly. This concentrates that one stateful
concern — an episode-latched detector that surfaces a neutral ``local_patch_loop``
banner — in a single owner.

The detector is FLAG-ONLY: it writes a neutral entry into the turn view's
``decision_context``; it never gates a turn and never raises (any internal failure
is swallowed so the banner simply does not appear).

Window sizing (``window=24``): the real step4_1 MACRO-CYCLE has ~10-11 distinct
fingerprints (period ~11); each member is re-reached by an accepted commit about
once per cycle, so K(=3) separated arrivals of one member span ~22 turns — a
24-turn window covers that with margin. ``detect_patch_loop`` is a PURE function
that would re-fire on every later accepted re-arrival inside the window; the
EPISODE LATCH (``_armed``) bounds it to ONE fire per loop episode.

Episode latch + re-arm (``rearm_after=2``): on first fire we disarm and capture
the loop-set (the fingerprints reached by ACCEPTED commits in the window;
state-frozen turns — rejected / read-only / repair — re-render a member's view
but are not themselves loop states). We re-arm only after a GENUINE escape: >= R
accepted commits land OUTSIDE the captured loop-set without an accepted return in
between (so a lone 1-turn excursion does not re-arm, and neither does parking on
one new frozen fingerprint via rejected turns — the audited any-turn counter
double-fired exactly there), OR a game-pair restructure (``_RESTRUCTURE_HEADS``),
OR an undo/restart intent (``_REARM_INTENTS``).

Episode escalation (``escalate_after=22``): while the latch stays disarmed — the
episode persists, no escape / restructure / undo re-armed it — count the turns
since the fire; at >= the threshold surface EXACTLY ONE stronger banner, then stay
silent for the rest of the episode (hard cap 2 banners/episode). 22 was tuned on
the real step4_1 resume Tree_0_0 trace (fire t34 -> escalation t56).
"""
from __future__ import annotations

from typing import Any, Optional

from workflow.proof_management.types import ManagedTurn


class LoopMonitor:
    """Owns the patch-loop episode latch + escalation for one proof node."""

    def __init__(
        self,
        *,
        window: int = 24,
        rearm_after: int = 2,
        escalate_after: int = 22,
    ) -> None:
        # In-proc ring of recent per-turn render fingerprints (NOT goal_hash, which
        # was empirically empty); `detect_patch_loop` reads it for a no-progress
        # MACRO-CYCLE of accepted local patches.
        self._history: list[Any] = []
        self._window = window
        # Episode latch state.
        self._armed = True
        self._episode_fps: set[str] = set()
        self._escape_run = 0
        self._rearm_after = rearm_after
        # Episode escalation state.
        self._escalate_after = escalate_after
        self._turns_since_fire = 0
        self._accepted_since_fire = 0
        self._escalated = False

    def inject(self, result: ManagedTurn, *, full_view: Optional[dict] = None) -> None:
        """Record this turn and, if warranted, surface a ``local_patch_loop`` banner.

        Writes the banner into the returned view's ``decision_context`` (and, when
        provided, the stored full/audit ``full_view`` — #12 step 3 dual-view
        fidelity). Flag-only; never gates the turn, never raises.

        EPISODE LATCH: collapses one loop episode to a SINGLE banner (see module
        docstring). BANNER COUPLING: ``detect_patch_loop`` returns the neutral text;
        the call-specific tail is added only when the up-to-bad-call signal is
        independently active for this turn/frontier. EPISODE ESCALATION: one
        stronger banner if the same episode persists past the threshold.
        REJECTED-THRASH bypass: ``detect_rejected_thrash`` fires once on the k-th
        (k=3) consecutive rejected commit parked on one fingerprint.
        """
        try:
            from workflow.patch_loop_detector import (
                _REARM_INTENTS, _RESTRUCTURE_HEADS, _tactic_head,
                detect_patch_loop, detect_rejected_thrash,
                patch_loop_banner_text, patch_loop_escalation_text,
                record_from)
            view = getattr(result, "workspace_view", None)
            if not isinstance(view, dict):
                return
            # The stored full (audit) view, so the banner reaches it too (#12
            # step 3 — completes the dual-view fidelity for the one stateful
            # surface). None on the bare test shells that lack a lifecycle.
            full = full_view
            intent_obj = getattr(result, "intent", None)
            intent_name = getattr(intent_obj, "intent", "") if intent_obj else ""
            payload = getattr(intent_obj, "payload", {}) if intent_obj else {}
            tactic = str((payload or {}).get("tactic") or "")
            # An EC error / no-op / reject signal on any of this turn's actions —
            # checked at both the top level and the nested live-action shape.
            errored = False
            for a in (result.manager_actions or []):
                if not isinstance(a, dict):
                    continue
                if a.get("error_summary"):
                    errored = True
                    break
                obs = a.get("agent_observation")
                if isinstance(obs, dict) and obs.get("error_summary"):
                    errored = True
                    break
            rec = record_from(
                view,
                intent=intent_name,
                tactic=tactic,
                ok=bool(result.ok),
                errored=errored,
            )
            self._history.append(rec)
            # Bound the ring so memory stays flat on long runs.
            if len(self._history) > 4 * self._window:
                self._history = self._history[
                    -2 * self._window:
                ]

            # --- Episode RE-ARM gate (run BEFORE detection so a real escape this
            # turn can re-arm the latch for a re-formed loop). Only ACCEPTED
            # commits move the escape counter: a state-frozen turn (rejected /
            # read-only / repair) neither escapes nor returns, and parking on one
            # new frozen fingerprint via rejected turns must NOT count as escape
            # (the audited any-turn counter double-fired exactly there). ---
            if self._episode_fps and rec.accepted:
                if rec.fingerprint not in self._episode_fps:
                    self._escape_run += 1
                else:
                    self._escape_run = 0
            escaped = self._escape_run >= self._rearm_after
            head = _tactic_head(rec.tactic)
            restructure = (
                rec.intent in ("commit_tactic", "probe_tactic")
                and head in _RESTRUCTURE_HEADS
            )
            # Full production rewind/restart vocabulary (incl. undo_to_checkpoint
            # and fresh_restart). Safe to re-arm here: the detector's own undo
            # cooldown keeps this turn and the next silent, and a hit needs an
            # accepted re-arrival — an agent mid-recovery cannot be re-banner'd.
            undo = rec.intent in _REARM_INTENTS
            if escaped or restructure or undo:
                self._armed = True
                self._episode_fps = set()
                self._escape_run = 0
                # The episode ended -> escalation tracking resets with it.
                self._turns_since_fire = 0
                self._accepted_since_fire = 0
                self._escalated = False
            elif not self._armed:
                # Episode persists: account this turn toward the escalation
                # threshold (every managed turn counts — the agent is burning
                # turns either way) and track accepted commits since the fire.
                self._turns_since_fire += 1
                if rec.accepted:
                    self._accepted_since_fire += 1

            def _dc() -> dict:
                d = view.get("decision_context")
                if not isinstance(d, dict):
                    d = {}
                    view["decision_context"] = d
                return d

            def _set_loop_banner(entry: dict, *, default: bool = False) -> None:
                # Write the banner to BOTH the agent-facing lean view and the
                # stored full (audit) view (set-key, idempotent). Reads (e.g.
                # call_aware) stay on the lean view via _dc().
                for v in (view, full):
                    if not isinstance(v, dict):
                        continue
                    d = v.get("decision_context")
                    if not isinstance(d, dict):
                        d = {}
                        v["decision_context"] = d
                    if default:
                        d.setdefault("local_patch_loop", entry)
                    else:
                        d["local_patch_loop"] = entry

            flag = detect_patch_loop(
                self._history, window=self._window
            )
            if flag is not None and self._armed:
                # FIRE ONCE for this episode: disarm and capture the rotating
                # loop-set (the fingerprints reached by ACCEPTED commits in the
                # window) so subsequent cycling turns are suppressed until a
                # genuine escape/restructure/undo re-arms the latch.
                self._armed = False
                self._episode_fps = {
                    r.fingerprint
                    for r in self._history[-self._window:]
                    if getattr(r, "accepted", False) and r.fingerprint
                }
                self._escape_run = 0
                self._turns_since_fire = 0
                self._accepted_since_fire = 0
                self._escalated = False
                dc = _dc()
                # Choose the neutral vs call-aware banner tail. The up-to-bad-call
                # signal is active for this frontier iff its enrichment already
                # wrote `up_to_bad_call` into this view's decision_context, OR the
                # up-to-bad goal shape + an offered lockstep call is independently
                # detectable here.
                call_aware = "up_to_bad_call" in dc or self._up_to_bad_frontier(view)
                if call_aware:
                    flag = dict(flag)
                    flag["text"] = patch_loop_banner_text(
                        int(flag.get("recurrences") or 0), call_aware=True
                    )
                _set_loop_banner(flag)
                return

            # --- EPISODE ESCALATION: one stronger banner if the SAME episode
            # persisted for >= `_escalate_after` further turns with no genuine
            # escape. Never on a terminal view (nothing to escalate) and never on
            # an undo/restart turn (those re-armed above anyway).
            if (
                not self._armed
                and not self._escalated
                and self._turns_since_fire >= self._escalate_after
                and not rec.terminal
            ):
                self._escalated = True
                _set_loop_banner({
                    "key": "local_patch_loop",
                    "kind": "escalation",
                    "text": patch_loop_escalation_text(
                        self._turns_since_fire,
                        self._accepted_since_fire,
                    ),
                    "turns_since_first_banner": self._turns_since_fire,
                    "accepted_since_first_banner":
                        self._accepted_since_fire,
                    "certified": False,
                    "guarantee": (
                        "UNCERTIFIED observation — a persistence signal from the "
                        "rendered goal fingerprints, NOT a verdict and NOT a "
                        "gate. You may keep going; this only flags how long this "
                        "loop episode has now lasted."
                    ),
                })
                return

            # --- REJECTED-THRASH bypass: fires once on the k-th consecutive
            # rejected commit parked on one fingerprint (the EXACTLY-k rule in
            # the detector is its own episode latch).
            thrash = detect_rejected_thrash(self._history)
            if thrash is not None:
                _set_loop_banner(thrash, default=True)
        except Exception:
            pass

    def _up_to_bad_frontier(self, view: dict[str, Any]) -> bool:
        r"""True when THIS turn's frontier independently shows the up-to-bad shape AND
        an offered lockstep ``call (_: inv)`` — the same condition the pure-view
        ``up_to_bad_call`` enrichment fires on. Used as a fallback so the call-aware
        patch-loop tail can appear even if the enrichment key is not on this exact
        view object (e.g. a view assembled by a path that did not run it).

        The call offer is read from the structures a LIVE agent view actually
        carries: ``candidate_moves.moves`` (the factual menu — offered templates
        live in ``tactic``/``tactic_shape``) first, with the internal
        ``decision_context.proof_options`` shape kept as a fallback for
        manager-internal views.

        The same three already-handled gates (a)/(b)/(c) the pure-view enrichment
        applies are enforced here too, so the call-aware tail appears iff the
        enrichment would itself fire (2026-06-09 round-3 re-audit D7: harvesting a
        bad-name from an already-up-to-bad committed call is correct, but emitting
        "re-issue your call in up-to-bad form" then points at the wrong lever;
        gate-a/c silence it back to NEUTRAL).

        Pure/best-effort: any failure returns False so the NEUTRAL banner stands.
        """
        try:
            from core.easycrypt.session_prover_workspace_view import (
                _up_to_bad_names_in_goal, _committed_history_uptobad_names,
                _offered_call_option_texts, _offer_already_handles_bad,
                _goal_negated_bad_conjuncts, _committed_call_already_uptobad)
        except Exception:
            return False
        try:
            cg = view.get("current_goal") if isinstance(view.get("current_goal"), dict) else {}
            lines = [str(x) for x in (cg.get("lines") if isinstance(cg.get("lines"), list) else [])]
            scope = ""
            dr = view.get("debug_refs")
            if isinstance(dr, dict):
                scope = str(dr.get("session_dir") or "")
            # Same data source as the enrichment: goal-local harvest UNION the
            # committed-history coherence harvest.
            bad_names = set(_up_to_bad_names_in_goal(lines))
            if scope:
                bad_names |= set(_committed_history_uptobad_names(scope))
            if not bad_names:
                return False
            # Gather the offered call-invariant templates (menu moves first, the
            # internal proof_options shape as fallback) — the texts gate (a) reads.
            offer_texts: list[str] = []
            cm = (
                view.get("candidate_moves")
                if isinstance(view.get("candidate_moves"), dict) else {}
            )
            moves = cm.get("moves") if isinstance(cm.get("moves"), list) else []
            for move in moves:
                if not isinstance(move, dict):
                    continue
                text = " ".join(
                    str(move.get(key) or "")
                    for key in (
                        "title", "tactic", "tactic_shape", "guidance",
                        "applicability",
                    )
                )
                if "call (_:" in text or "Invariant-call" in text:
                    offer_texts.append(text)
            dc = view.get("decision_context")
            if isinstance(dc, dict):
                offer_texts.extend(_offered_call_option_texts(dc))
            if not offer_texts:
                return False
            # Already-handled gates (a)/(b)/(c): any one means the frontier is
            # INSIDE handled up-to-bad territory and the call-aware tail is
            # wrong-domain. Mirror `_enrich_up_to_bad_call` exactly.
            if _offer_already_handles_bad(offer_texts, bad_names):
                return False
            if bad_names & _goal_negated_bad_conjuncts(lines):
                return False
            if _committed_call_already_uptobad(scope, bad_names):
                return False
            return True
        except Exception:
            return False
