#!/usr/bin/env python3
"""Persistent EasyCrypt daemon: keeps one ``easycrypt -emacs`` subprocess
per session alive across tactic submissions, enabling fast speculative
execution (try tactic → rollback) without the 5-15s per-call re-spawn +
history-replay overhead session_cli currently pays.

Transport: Unix socket at ``/tmp/ec_daemon.sock``. Framing:
    newline-delimited JSON objects, one request/response per line.

Multi-prover: a daemon holds N concurrent sessions, one EC subprocess
each (indexed by session_id string). Different sessions can execute
concurrently (separate threads); same session serializes via a
per-session lock. This supports tree-mode provers (prover_tree_0_0,
prover_tree_0_1, ...) running in parallel.

Protocol (minimal JSON-RPC-ish):
    {method: str, session_id: str, params: dict}
    → {status: "ok"|"error", result: ..., error: ...}

Methods:
    open_session(file_path, include_dirs, lemma_name): create EC
        subprocess, load context.ec from the matching session_dir, step
        into the lemma's proof, return current goal state.
    commit(tactic): advance permanently, append to history, return new
        goal state.
    try_tactic(tactic): execute, capture outcome, auto-undo. Return
        {accepted, error, goal_state_preview}. Session state unchanged.
    batch_try([tactic1, ...]): each tactic tried independently, all
        undone. Returns list of per-tactic results.
    get_goal(): current goal state.
    undo(): revert last committed tactic (for -prev equivalent).
    list_sessions(): active session ids.
    close_session(): terminate EC subprocess.
    shutdown(): stop daemon.

Errors: if EC hits an error line (e.g. ``[error-N-M]cannot ...``), the
response's ``error`` field carries:
    {kind: "unification_fail"|"no_progress"|"unknown_lemma"|
           "type_error"|"other",
     raw: str, location: dict?}

Rollback semantics: ``try_tactic`` always runs ``undo.`` after the
tactic, regardless of whether the tactic succeeded. If EC considers a
failing tactic as "no state change", the undo becomes a no-op; if EC
did advance state briefly before reporting an error, the undo brings it
back. Either way, history is unchanged.

Scope for this initial version: single-host, trust all local clients,
no auth. Persistence across daemon restart is NOT supported — a
restart wipes all sessions (clients reopen).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Ensure the project root is importable: the daemon is spawned directly as
# `python core/easycrypt/ec_daemon.py` (daemon_backend._spawn_daemon), so only
# this file's own dir lands on sys.path — without the project root the
# package-absolute imports below would not resolve. (No-op when imported as a
# package, where the root is already on the path.)
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from core.easycrypt.ec_lifecycle import (  # noqa: E402
    PROMPT_RE,
    ECSessionLifecycle,
    split_ec_commands as _split_ec_commands,
)


logger = logging.getLogger("ec_daemon")

SOCKET_PATH_DEFAULT = "/tmp/ec_daemon.sock"
# EC error line shape: ``[error-<a>-<b>]<reason>``. The a/b are
# character-offset hints; the reason text varies.
ERROR_LINE_RE = re.compile(r"\[(error|critical|fatal)(-[0-9\-]+)?\](.*)")


class _EphemeralEC(ECSessionLifecycle):
    """Spawn-fresh ephemeral EC for read-only speculative probing (#3 step 3b).

    Each probe gets its own isolated pipe — the committed ``self.proc`` is never
    touched (the reason ECDaemon spawns fresh). It replays the setup + committed
    prefix via the base lifecycle, runs the speculative tactic(s), and is torn
    down. The only ephemeral-specific knob is the diagnostic label; the daemon's
    ``_parse_error`` is passed to ``replay_prefix`` as the setup gate."""

    _label = "ephemeral EC"




# ---------------------------------------------------------------------------
# EC subprocess wrapper
# ---------------------------------------------------------------------------


@dataclass
class GoalState:
    """Snapshot of EC's output for the current goal."""

    raw: str                # full output block since last prompt
    remaining: int = 0       # remaining subgoal count (from "Current goal (remaining: N)")
    is_closed: bool = False  # "No more goals" seen
    last_prompt: str = ""    # e.g. "[12|check]"


@dataclass
class TacticOutcome:
    """Result of sending one tactic to EC."""

    accepted: bool
    raw_output: str               # full output since command
    goal_after: GoalState
    error: Optional[dict] = None  # {kind, raw, location?}
    # When the tactic is accepted but produces no state change, EC
    # stays at the same prompt/goal. Callers may treat that as a
    # "no_progress" error depending on their policy.
    no_progress: bool = False


@dataclass
class ChainOutcome:
    """Result of running a sequence of tactics speculatively (ephemeral
    EC). ``accepted`` iff every tactic in the chain was accepted by EC;
    ``final_closed`` iff the final state has ``No more goals``.
    ``steps`` has per-tactic TacticOutcomes up to (and including) the
    first failure, after which no further tactics were sent."""

    accepted: bool
    final_closed: bool
    final_goal: GoalState
    steps: list[TacticOutcome]
    failed_at: Optional[int] = None
    error: Optional[dict] = None


class ECSubprocess(ECSessionLifecycle):
    """One persistent ``easycrypt -emacs`` process.

    The lifecycle is: spawn → prime with context.ec → enter proof for
    the target lemma → advance with tactics. The object is owned by
    one session and is NOT thread-safe on its own; the daemon wraps it
    with a per-session lock.
    """

    # Recognize EC prompts to know when it's done producing output.
    # EC prompts on its own line. Our read loop detects the prompt and
    # stops reading for that turn.
    _RESPONSE_TIMEOUT_DEFAULT = 60.0  # seconds

    def __init__(self, include_dirs: list[str], why3_socket: Optional[str] = None):
        super().__init__(include_dirs, why3_socket)
        # Last known open-goal count (EC `(remaining: N)`); -1 = unknown. Used by
        # `execute` to treat a `case`/split that ADDS a subgoal as progress even
        # when the prompt-tail text is unchanged (panel-defect #3).
        self._last_remaining = -1
        self.file_path: Optional[Path] = None
        self.lemma_name: Optional[str] = None
        # Number of tactics committed via ``execute``. Used for
        # diagnostics and checkpoint recovery.
        self.committed_count: int = 0
        # Setup prefix (``require``/``clone``/imports/the lemma
        # declaration + ``proof.``) replayed into ephemeral EC
        # processes for speculative ``try_tactic``. Cached at
        # ``load_context_and_enter_proof`` time.
        self._setup_commands: list[str] = []
        # History of committed tactics (the proof body so far). Used
        # as replay input for ephemeral EC.
        self._committed_tactics: list[str] = []
        # A warm ephemeral EC kept at the committed state for fast read-only
        # batch probing (run-then-``undo``, ~0.02 s/probe vs ~1.4 s spawn-fresh).
        # Lazily built, invalidated on every commit. See ``batch_try``.
        self._warm = None

    # -----------------------------------------------------------------
    # Process lifecycle
    # -----------------------------------------------------------------

    def _resolve_env(self) -> dict[str, str]:
        """Spawn environment for the base ``spawn()``. The daemon is often
        auto-spawned by a process whose ambient PATH lacks the EasyCrypt opam
        switch; load it so spawn doesn't ``FileNotFoundError`` (the unified argv
        + banner drain live in the base)."""
        return self._get_ec_env()

    @staticmethod
    def _get_ec_env() -> dict[str, str]:
        """Load EC env from opam. Mirrors session_cli._get_ec_env.

        The daemon is often auto-spawned by a Python process whose
        ambient PATH does not include the EasyCrypt opam switch. If we
        return the ambient env unchanged, daemon open_session fails with
        ``FileNotFoundError: easycrypt`` and session_cli silently falls
        back to the slow subprocess replay path for every tactic.
        """
        try:
            from core.easycrypt.ec_env import get_ec_env  # type: ignore
            return get_ec_env()
        except ImportError:
            pass
        try:
            from core.easycrypt.ec_env import get_ec_env  # type: ignore
            return get_ec_env()
        except ImportError:
            pass
        env = dict(os.environ)
        for cmd in (["opam", "env", "--switch=easycrypt"], ["opam", "env"]):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().splitlines():
                        m = re.match(r"(\w+)='([^']*)'", line)
                        if m:
                            env[m.group(1)] = m.group(2)
                    return env
            except Exception:
                continue
        return env

    def close(self) -> None:
        """Terminate the EC subprocess (and invalidate any warm prober)."""
        self._invalidate_warm()
        self.teardown(
            grace=5.0,
            abandon_msg=(
                "EC subprocess pid=%s did not exit after SIGKILL; "
                "abandoning it to avoid blocking the session."
            ),
        )

    # -----------------------------------------------------------------
    # Session bootstrap
    # -----------------------------------------------------------------

    def load_context_and_enter_proof(
        self,
        file_path: Path,
        lemma_name: str,
    ) -> GoalState:
        """Load ``file_path`` into EC, step to the lemma's proof body,
        and return the initial goal state.

        Implementation: ``lemma_extract`` gives us the minimal snippet
        ending in ``proof.`` Each complete statement (a region that
        ends with a ``.`` at line end) triggers one EC response in
        ``-emacs`` mode. We must send **one statement at a time** and
        drain one prompt per statement — batching would leave residual
        prompts in the buffer that later ``execute`` calls would
        consume instead of their own output.
        """
        self.file_path = file_path
        self.lemma_name = lemma_name
        self._invalidate_warm()   # new proof context; any warm prober is stale
        from core.easycrypt.lemma_extract import extract_lemma  # type: ignore
        extracted = extract_lemma(file_path, lemma_name, open_proof=True)
        commands = [c for c in _split_ec_commands(extracted) if c.strip()]
        self._setup_commands = list(commands)
        final_output = b""
        for cmd in commands:
            self._send(cmd)
            final_output = self._read_until_prompt(timeout=120.0)
            err = self._parse_error(
                final_output.decode("utf-8", errors="replace")
            )
            if err is not None:
                raise RuntimeError(
                    f"EC rejected setup command {cmd!r} for lemma "
                    f"{lemma_name!r}: {err}"
                )
        entered = self._parse_goal_state(
            final_output.decode("utf-8", errors="replace")
        )
        # Seed the open-goal count so the first committed tactic's progress check
        # (panel-defect #3) has a valid baseline.
        self._last_remaining = entered.remaining
        return entered

    # -----------------------------------------------------------------
    # Tactic execution
    # -----------------------------------------------------------------

    def execute(self, tactic: str) -> TacticOutcome:
        """Send one tactic, return the outcome. Tactic is appended to
        history if accepted. Callers should hold the session lock.
        """
        if not tactic.endswith("."):
            tactic = tactic.rstrip() + "."
        before_prompt = self._last_prompt_text
        before_remaining = self._last_remaining
        self._send(tactic)
        raw = self._read_until_prompt().decode("utf-8", errors="replace")
        goal = self._parse_goal_state(raw)
        err = self._parse_error(raw)
        if err is None:
            self.committed_count += 1
            self._committed_tactics.append(
                tactic if tactic.endswith("\n") else tactic
            )
            self._invalidate_warm()   # committed state moved; warm prober is stale
            # Panel-defect #3 (docs/reports/insights/l4_panel_defects_equiv_step4.md):
            # a `case`/split that ADDS a subgoal (and a hypothesis) is genuine
            # progress even if the prompt-tail text is unchanged. Treat an increase
            # in EC's open-goal count (`remaining`) as progress. A truly idempotent
            # tactic leaves the count unchanged and is still flagged.
            goal_count_increased = (
                before_remaining >= 0
                and goal.remaining > before_remaining
            )
            no_progress = (
                self._last_prompt_text == before_prompt
                and not goal.is_closed
                and not goal_count_increased
            )
            self._last_remaining = goal.remaining
            return TacticOutcome(
                accepted=True,
                raw_output=raw,
                goal_after=goal,
                error=None,
                no_progress=no_progress,
            )
        return TacticOutcome(
            accepted=False,
            raw_output=raw,
            goal_after=goal,
            error=err,
            no_progress=False,
        )

    # -----------------------------------------------------------------
    # Warm read-only batch probing (run-then-undo)
    # -----------------------------------------------------------------

    @staticmethod
    def _warm_enabled() -> bool:
        return os.environ.get("EC_WARM_PROBE", "1").strip().lower() not in (
            "0", "false", "no", "off")

    def _invalidate_warm(self) -> None:
        if self._warm is not None:
            try:
                self._warm.close()
            except Exception:
                pass
            self._warm = None

    def _ensure_warm(self):
        """A live warm prober at the committed state, built lazily. Returns
        ``None`` (caller falls back to spawn-fresh) if disabled, not in a proof,
        or the build fails."""
        if not self._warm_enabled():
            return None
        if self._warm is not None and self._warm.alive:
            return self._warm
        self._invalidate_warm()
        if not self.file_path or not self.lemma_name:
            return None
        try:
            from core.easycrypt.ec_warm_prober import WarmProber  # type: ignore
        except Exception:
            try:
                from core.easycrypt.ec_warm_prober import WarmProber
            except Exception:
                return None
        try:
            wp = WarmProber(self.include_dirs, self.why3_socket,
                            env=self._get_ec_env())
            ok = wp.open(self.file_path, self.lemma_name,
                         committed_tactics=list(self._committed_tactics),
                         setup_commands=list(self._setup_commands))
        except Exception:
            return None
        if ok and wp.alive:
            self._warm = wp
            return wp
        try:
            wp.close()
        except Exception:
            pass
        return None

    def _probe_to_outcome(self, res) -> "TacticOutcome":
        """Convert a warm ``ProbeResult`` to a ``TacticOutcome`` using EC's OWN
        parsers on the probe's raw output, so warm and spawn-fresh agree exactly
        on accepted / goal / error; ``advanced`` gives no_progress."""
        raw = res.raw or ""
        err = self._parse_error(raw)
        goal = self._parse_goal_state(raw)
        # Panel-defect #3: a `case`/split that adds a subgoal is progress even if
        # `advanced` were ever computed as False; if the probe's open-goal count
        # exceeds the committed count, never flag no_progress. (`advanced` already
        # catches the counter move; this is defense-in-depth and keeps the warm and
        # committed paths agreeing on count-based progress.)
        goal_count_increased = (
            self._last_remaining >= 0
            and goal.remaining > self._last_remaining
        )
        no_progress = (
            (err is None)
            and (not res.advanced)
            and (not goal.is_closed)
            and (not goal_count_increased)
        )
        return TacticOutcome(
            accepted=(err is None), raw_output=raw, goal_after=goal,
            error=err, no_progress=no_progress)

    def batch_try(self, tactics: list[str],
                  timeout: float = 180.0) -> "list[TacticOutcome]":
        """Probe each tactic read-only and independently. Uses a warm ephemeral
        (run-then-undo; ~0.02 s/probe after a one-time ~1.4 s warm-up) when
        available, falling back to spawn-fresh ``try_tactic`` per tactic if the
        warm build fails or the prober drifts mid-batch. Result order matches
        ``tactics``; callers hold the session lock."""
        wp = self._ensure_warm()
        out: "list[TacticOutcome]" = []
        for tac in tactics:
            done = False
            if wp is not None and wp.alive:
                try:
                    res = wp.probe(tac, timeout=timeout)
                except Exception:
                    res = None
                if res is not None and wp.alive:
                    out.append(self._probe_to_outcome(res))
                    done = True
                else:
                    self._invalidate_warm()   # drift -> spawn-fresh for the rest
                    wp = None
            if not done:
                out.append(self._try_tactic_fresh(tac, timeout=timeout))
        return out

    # Note: EC in ``-emacs`` mode does NOT accept ``undo.`` / ``Undo.``
    # — those produce parse errors. ``abort.`` exits proof mode but
    # can't be re-entered for the same lemma. Consequently, there's
    # no primitive in EC's toplevel that rolls the current proof back
    # one tactic. For speculative execution we fall back to
    # "ephemeral EC": spawn a fresh subprocess, replay setup + all
    # committed tactics, run the speculative tactic, terminate. See
    # ``try_tactic`` below.

    def try_tactic(self, tactic: str,
                   timeout: float = 180.0) -> TacticOutcome:
        """Speculatively try a tactic read-only (never touches the committed
        ``self.proc``). Uses the warm prober — run-then-``undo``, ~0.02 s after a
        one-time warm-up, the warm process reused across probes until the next
        commit — when available, falling back to a fresh ephemeral EC otherwise.
        ``EC_WARM_PROBE=0`` forces spawn-fresh. So EVERY read-only probe site
        (single or batched, in any producer) gets the warm speedup with no
        per-caller change; the committed ``execute`` path is untouched."""
        if self._warm_enabled():
            wp = self._ensure_warm()
            if wp is not None and wp.alive:
                try:
                    res = wp.probe(tactic, timeout=timeout)
                except Exception:
                    res = None
                if res is not None and wp.alive:
                    return self._probe_to_outcome(res)
                self._invalidate_warm()   # drift -> this probe spawns fresh
        return self._try_tactic_fresh(tactic, timeout=timeout)

    def _spawn_ephemeral_replayed(self, timeout: float):
        """Shared skeleton of the fresh-probe paths: spawn an ephemeral EC
        (fully isolated from ``self.proc``), replay setup + committed
        tactics, and hand back ``(eph, fail)``. Callers own teardown and
        keep their distinct send/parse/return logic."""
        eph = _EphemeralEC(
            self.include_dirs, self.why3_socket, env=self._get_ec_env(),
        )
        try:
            eph.spawn()   # spawn + drain banner
            fail = eph.replay_prefix(
                self._setup_commands, self._committed_tactics,
                is_setup_error=self._parse_error, committed_timeout=timeout,
            )
        except BaseException:
            # Callers only own teardown once they hold the handle; a spawn or
            # replay crash must not leak the ephemeral EC process.
            eph.teardown()
            raise
        return eph, fail

    def _try_tactic_fresh(self, tactic: str,
                          timeout: float = 180.0) -> TacticOutcome:
        """Execute a tactic speculatively without touching the main
        EC process.

        Implementation: spawn a fresh ``easycrypt -emacs`` subprocess,
        replay the cached setup commands + all committed tactics, then
        send ``tactic``. Capture the result. Kill the ephemeral process.

        Cost: O(len(setup) + len(committed_tactics)) per call. For a
        mid-proof session after ~20 tactics the replay runs in 2-5
        seconds. For long proofs this is a real cost but still faster
        than the prover finding out the hard way (5-10 minutes of
        self-correction, per Run 20 data).
        """
        eph, fail = self._spawn_ephemeral_replayed(timeout)
        try:
            if fail is not None:
                return TacticOutcome(
                    accepted=False,
                    raw_output=fail.raw,
                    goal_after=GoalState(raw=""),
                    error={
                        "kind": "ephemeral_setup_failed",
                        "raw": f"setup cmd {fail.setup_cmd!r} failed: {fail.err}",
                    },
                )
            # Try the tactic
            tac = tactic
            if not tac.endswith("."):
                tac = tac.rstrip() + "."
            eph._send(tac)
            raw_bytes = eph._read_until_prompt(timeout=timeout)
            raw = raw_bytes.decode("utf-8", errors="replace")
            goal = self._parse_goal_state(raw)
            err = self._parse_error(raw)
            if err is None:
                return TacticOutcome(
                    accepted=True, raw_output=raw,
                    goal_after=goal, error=None,
                )
            return TacticOutcome(
                accepted=False, raw_output=raw,
                goal_after=goal, error=err,
            )
        finally:
            eph.teardown()

    # ------------------------------------------------------------------
    # Bridge economics — test if a `have ->` rewrite is "atomic"
    # ------------------------------------------------------------------

    # Ordered by cost/complexity. The earliest closer that succeeds
    # tells us the bridge size. If NONE succeed, the bridge is too big
    # and the prover should decompose it further (usually by finding an
    # intermediate `pr_*` lemma to break it at).
    # Closers are used as ``have -> : <stmt> <closer>.`` — single
    # EC statement. The ``by ...`` syntax must be inlined (no
    # intermediate dot) or EC fires two statements and we miss the
    # second one's error in our single read-until-prompt. Each entry
    # is ``(closer_tail, size_label)`` where closer_tail is everything
    # after ``Pr[A]=Pr[B]`` up to (but not including) the terminating
    # period — so the full tactic is ``have -> : <stmt> <tail>.``.
    _BRIDGE_CLOSER_LADDER: list[tuple[str, str]] = [
        # Trivial reflexive / identity closers:
        ("by done",                                          "atomic"),
        ("by trivial",                                       "atomic"),
        # Sim-family closers — no hand-crafted hints needed:
        ("by byequiv => //=; sim",                           "atomic"),
        ("by byequiv => //=; proc; sim",                     "atomic"),
        ("by byequiv => //=; proc; inline *; sim",           "small"),
        ("by byequiv => //=; proc; inline *; wp; sim",       "small"),
        ("by byequiv => //=; proc; inline *; wp; auto => />", "medium"),
        ("by byequiv => //=; proc; inline *; wp; sim />",    "medium"),
    ]

    def bridge_probe(self, bridge_stmt: str,
                     timeout: float = 120.0) -> dict:
        """Test if ``bridge_stmt`` (an equality claim you'd put after
        ``have -> :``, typically ``Pr[A] = Pr[B]``) is closeable via
        a short sim-family closer. This is how you check *bridge
        economics* before committing: a have-> that closes with
        ``sim`` or ``byequiv+sim`` is an "atomic bridge"; one that
        needs a hand-crafted ``while`` invariant is "too big" and
        should be decomposed at an intermediate checkpoint.

        Implementation: for each closer in
        ``_BRIDGE_CLOSER_LADDER``, spawn an ephemeral EC, replay
        setup + committed tactics, run
        ``have -> : <bridge_stmt>. <closer>`` and see if EC closes.
        Return the smallest closer that works, or an error if none do.

        Returns:
            {
              "accepted": bool,  # True iff any ladder step closed
              "closed_by": str | None,  # the exact closer that worked
              "bridge_size": "atomic" | "small" | "medium" | "too_big",
              "error": dict | None,  # error from final (deepest) attempt
                                       # if all failed — tells caller WHY
                                       # the bridge is too big
            }
        """
        stmt = bridge_stmt.strip().rstrip(".")  # no trailing dot

        # Ladder: try cheapest closer first.
        # NOTE: we check ``outcome.accepted`` (did the whole chain run
        # without EC erroring), NOT ``final_closed``. `have -> : X by
        # closer.` is atomic: if the closer doesn't discharge X, EC
        # throws. If it does, the have-> succeeds and the MAIN goal
        # continues open (that's the whole point of have->; the main
        # goal remains, just with the rewrite applied). So final_closed
        # would always be False here — accepted is the right signal.
        #
        # IMPORTANT: the whole ``have -> : <stmt> <tail>.`` must be
        # ONE EC statement (no dot in the middle). If split into two,
        # EC prompts after the first and the lifecycle reader
        # stops before seeing the closer's error — we'd report
        # ``accepted=True`` falsely. So we splice with a single space
        # and append exactly one trailing period.
        last_err: Optional[dict] = None
        for closer, size in self._BRIDGE_CLOSER_LADDER:
            combined = f"have -> : {stmt} {closer}."
            # Use try_chain on a single-element list so existing
            # ephemeral-EC scaffolding handles replay + kill.
            outcome = self.try_chain([combined], timeout=timeout)
            if outcome.accepted:
                return {
                    "accepted": True,
                    "closed_by": closer,
                    "bridge_size": size,
                    "error": None,
                }
            # Track the error for the report if we exhaust the ladder.
            if outcome.error is not None:
                last_err = outcome.error
            elif outcome.steps and outcome.steps[-1].error is not None:
                last_err = outcome.steps[-1].error

        return {
            "accepted": False,
            "closed_by": None,
            "bridge_size": "too_big",
            "error": last_err or {
                "kind": "bridge_too_big",
                "raw": "no sim-family closer on the ladder closed the "
                       "bridge; decompose it at an intermediate checkpoint "
                       "(look for a pr_* lemma that breaks the gap into "
                       "two smaller bridges).",
            },
        }

    def try_chain(self, tactics: list[str],
                  timeout: float = 180.0) -> ChainOutcome:
        """Speculatively run a tactic sequence read-only (never touches the
        committed ``self.proc``). Uses the warm prober — run the chain, then ONE
        undo-to-base; ~0.02 s/step after a one-time warm-up — when available,
        falling back to a fresh ephemeral EC otherwise. ``EC_WARM_PROBE=0`` forces
        spawn-fresh."""
        if not tactics:
            return ChainOutcome(
                accepted=False, final_closed=False,
                final_goal=GoalState(raw=""),
                steps=[], failed_at=None,
                error={"kind": "empty_chain", "raw": "no tactics provided"},
            )
        if self._warm_enabled():
            wp = self._ensure_warm()
            if wp is not None and wp.alive:
                try:
                    raws, ok = wp.probe_chain(tactics, timeout=timeout)
                except Exception:
                    raws, ok = None, False
                if ok and wp.alive and raws is not None:
                    return self._chain_to_outcome(raws)
                self._invalidate_warm()
        return self._try_chain_fresh(tactics, timeout=timeout)

    def _chain_to_outcome(self, step_raws: "list[str]") -> ChainOutcome:
        """Build a ChainOutcome from the warm path's per-step raw outputs, with
        EC's own parsers + break-at-first-failure — identical to the fresh path."""
        steps: list[TacticOutcome] = []
        failed_at: Optional[int] = None
        chain_error: Optional[dict] = None
        final_raw = ""
        for idx, raw in enumerate(step_raws):
            final_raw = raw
            goal = self._parse_goal_state(raw)
            err = self._parse_error(raw)
            steps.append(TacticOutcome(
                accepted=(err is None), raw_output=raw,
                goal_after=goal, error=err))
            if err is not None:
                failed_at = idx
                chain_error = err
                break
            if goal.is_closed:
                break
        final_goal = (self._parse_goal_state(final_raw) if final_raw
                      else GoalState(raw=""))
        return ChainOutcome(
            accepted=(failed_at is None), final_closed=final_goal.is_closed,
            final_goal=final_goal, steps=steps, failed_at=failed_at,
            error=chain_error)

    def _try_chain_fresh(self, tactics: list[str],
                         timeout: float = 180.0) -> ChainOutcome:
        """Execute a sequence of tactics speculatively. Spawns one
        ephemeral EC, replays setup + committed tactics, then sends
        each tactic in ``tactics`` one at a time. Stops at the first
        failure (or at EOF). Returns a ``ChainOutcome`` with per-step
        ``TacticOutcome`` records plus aggregate ``accepted`` /
        ``final_closed`` flags. Session state is not touched.

        This is the primitive multi-hop search builds on: verify an
        UNFOLD plan (``proc.`` → ``call <pivot>.`` → ``auto.``) without
        actually committing any of it.
        """
        eph, fail = self._spawn_ephemeral_replayed(timeout)
        try:
            if fail is not None:
                return ChainOutcome(
                    accepted=False, final_closed=False,
                    final_goal=GoalState(raw=""),
                    steps=[], failed_at=None,
                    error={
                        "kind": "ephemeral_setup_failed",
                        "raw": f"setup cmd {fail.setup_cmd!r} failed: {fail.err}",
                    },
                )

            steps: list[TacticOutcome] = []
            failed_at: Optional[int] = None
            chain_error: Optional[dict] = None
            final_raw = ""
            for idx, tac in enumerate(tactics):
                t_norm = tac.strip()
                if not t_norm.endswith("."):
                    t_norm = t_norm + "."
                eph._send(t_norm)
                raw_bytes = eph._read_until_prompt(timeout=timeout)
                raw = raw_bytes.decode("utf-8", errors="replace")
                final_raw = raw
                goal = self._parse_goal_state(raw)
                err = self._parse_error(raw)
                step_outcome = TacticOutcome(
                    accepted=(err is None),
                    raw_output=raw,
                    goal_after=goal,
                    error=err,
                )
                steps.append(step_outcome)
                if err is not None:
                    failed_at = idx
                    chain_error = err
                    break
                if goal.is_closed:
                    # Optimization: no point sending more tactics
                    # into a closed proof state — they'd fail with
                    # "no more goals" and just confuse the report.
                    break

            final_goal = self._parse_goal_state(final_raw) if final_raw else GoalState(raw="")
            return ChainOutcome(
                accepted=(failed_at is None),
                final_closed=final_goal.is_closed,
                final_goal=final_goal,
                steps=steps,
                failed_at=failed_at,
                error=chain_error,
            )
        finally:
            eph.teardown()

    # -----------------------------------------------------------------
    # Output parsing
    # -----------------------------------------------------------------

    @staticmethod
    def _parse_goal_state(raw: str) -> GoalState:
        """Extract a ``GoalState`` from EC's raw output for a tactic."""
        is_closed = "No more goals" in raw
        remaining = 0
        m = re.search(r"Current goal\s*\(remaining:\s*(\d+)\)", raw)
        if m:
            remaining = int(m.group(1))
        elif re.search(r"\bCurrent goal\b", raw) and not is_closed:
            remaining = 1
        pm = None
        for m in PROMPT_RE.finditer(raw.encode("utf-8")):
            pm = m
        last_prompt = ""
        if pm:
            last_prompt = raw.encode("utf-8")[pm.start():pm.end()].decode(
                "utf-8", errors="replace"
            )
        return GoalState(
            raw=raw, remaining=remaining,
            is_closed=is_closed, last_prompt=last_prompt,
        )

    @staticmethod
    def _parse_error(raw: str) -> Optional[dict]:
        """If ``raw`` contains a tactic failure, return structured
        metadata. Returns None when EC accepted the tactic cleanly.

        Classification:
          unification_fail : matches "cannot unify" / "not convertible"
          no_progress       : ``no progress`` substring (a few EC tactics
                              emit this as an error instead of just
                              leaving state unchanged)
          unknown_lemma     : ``unknown lemma``, ``cannot find lemma``,
                              ``unknown procedure``
          type_error        : ``type error``, ``unbound``, ``mismatch``
          other             : anything else under [error/critical/fatal]
        """
        m_err = ERROR_LINE_RE.search(raw)
        if not m_err:
            return None
        reason = m_err.group(3).strip()
        low = reason.lower()
        if "cannot unify" in low or "not convertible" in low:
            kind = "unification_fail"
        elif "no progress" in low:
            kind = "no_progress"
        elif ("unknown lemma" in low or "cannot find lemma" in low
              or "unknown procedure" in low or "unknown module" in low):
            kind = "unknown_lemma"
        elif ("type error" in low or "unbound" in low
              or "mismatch" in low):
            kind = "type_error"
        else:
            kind = "other"
        return {"kind": kind, "raw": reason[:500],
                "severity": m_err.group(1)}


# ---------------------------------------------------------------------------
# Session manager (multi-session)
# ---------------------------------------------------------------------------


class SessionManager:
    """Registry of active EC sessions. Each session has its own
    ECSubprocess + lock. Cross-session operations parallelize; same
    session serializes.
    """

    def __init__(self):
        self._sessions: dict[str, ECSubprocess] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()
        # Wall-clock of the last registry/with_session touch per session.
        # Drives the idle-TTL reaper (worker-death survival means nobody
        # explicitly closes a crashed node's session; the reaper bounds
        # the leak of idle EC processes).
        self._last_used: dict[str, float] = {}

    def open(
        self,
        session_id: str,
        file_path: Path,
        include_dirs: list[str],
        lemma_name: str,
        why3_socket: Optional[str] = None,
    ) -> GoalState:
        with self._registry_lock:
            if session_id in self._sessions:
                raise ValueError(
                    f"session {session_id!r} already open; close it first"
                )
            ec = ECSubprocess(include_dirs=include_dirs,
                              why3_socket=why3_socket)
            self._sessions[session_id] = ec
            self._locks[session_id] = threading.Lock()
            self._last_used[session_id] = time.time()
        # Hold the session lock while bootstrapping.
        with self._locks[session_id]:
            ec.spawn()
            goal = ec.load_context_and_enter_proof(file_path, lemma_name)
        return goal

    def close(self, session_id: str) -> None:
        with self._registry_lock:
            ec = self._sessions.pop(session_id, None)
            self._locks.pop(session_id, None)
            self._last_used.pop(session_id, None)
        if ec is not None:
            ec.close()

    def adopt(self, old_id: str, new_id: str) -> bool:
        """Rename a live session ``old_id`` -> ``new_id`` (registry-only).

        The EC process, its lock, and all in-memory proof state move
        unchanged; only the registry key changes. This is the daemon half
        of worker-death attach: a respawned proof node (new session dir,
        hence new session id) adopts the dead node's still-live EC session
        instead of replaying the committed prefix.

        Raises ``KeyError`` when ``old_id`` is not open and ``ValueError``
        when ``new_id`` is already taken. ``old_id == new_id`` is a no-op.
        """
        with self._registry_lock:
            if old_id == new_id:
                if old_id not in self._sessions:
                    raise KeyError(f"session {old_id!r} not open")
                self._last_used[old_id] = time.time()
                return True
            if old_id not in self._sessions:
                raise KeyError(f"session {old_id!r} not open")
            if new_id in self._sessions:
                raise ValueError(
                    f"session {new_id!r} already open; close it first"
                )
            self._sessions[new_id] = self._sessions.pop(old_id)
            self._locks[new_id] = self._locks.pop(old_id)
            self._last_used[new_id] = time.time()
            self._last_used.pop(old_id, None)
        return True

    def info(self, session_id: str) -> dict:
        """Lightweight registry metadata for one session (no EC I/O)."""
        with self._registry_lock:
            ec = self._sessions.get(session_id)
            last_used = self._last_used.get(session_id)
        if ec is None:
            return {"exists": False}
        proc = ec.proc
        return {
            "exists": True,
            "file_path": str(ec.file_path) if ec.file_path else None,
            "lemma_name": ec.lemma_name,
            "committed_count": int(ec.committed_count),
            "ec_alive": bool(proc is not None and proc.poll() is None),
            "idle_seconds": (
                max(0.0, time.time() - last_used)
                if isinstance(last_used, float) else None
            ),
        }

    def touch(self, session_id: str) -> None:
        with self._registry_lock:
            if session_id in self._sessions:
                self._last_used[session_id] = time.time()

    def reap_idle(self, ttl_seconds: float) -> list[str]:
        """Close sessions idle for more than ``ttl_seconds``. Returns the
        reaped ids. ``ttl_seconds <= 0`` disables reaping."""
        if ttl_seconds <= 0:
            return []
        cutoff = time.time() - ttl_seconds
        with self._registry_lock:
            stale = [
                sid for sid, used in self._last_used.items()
                if used < cutoff and sid in self._sessions
            ]
        for sid in stale:
            logger.info("reaping idle session %s (ttl=%ss)", sid, ttl_seconds)
            self.close(sid)
        return stale

    def close_all(self) -> None:
        with self._registry_lock:
            ids = list(self._sessions.keys())
        for sid in ids:
            self.close(sid)

    def list(self) -> list[str]:
        with self._registry_lock:
            return list(self._sessions.keys())

    def with_session(self, session_id: str):
        """Context manager returning (ec, lock-held). Usage:

            with mgr.with_session(sid) as ec:
                ec.execute(...)
        """
        return _SessionCtx(self, session_id)


class _SessionCtx:
    def __init__(self, mgr: SessionManager, session_id: str):
        self.mgr = mgr
        self.sid = session_id
        self._lock: Optional[threading.Lock] = None

    def __enter__(self) -> ECSubprocess:
        with self.mgr._registry_lock:
            ec = self.mgr._sessions.get(self.sid)
            lock = self.mgr._locks.get(self.sid)
            if ec is not None:
                self.mgr._last_used[self.sid] = time.time()
        if ec is None or lock is None:
            raise KeyError(f"session {self.sid!r} not open")
        lock.acquire()
        self._lock = lock
        return ec

    def __exit__(self, *a):
        if self._lock is not None:
            self._lock.release()


# ---------------------------------------------------------------------------
# Unix socket server (JSON line-framed)
# ---------------------------------------------------------------------------


class DaemonServer:
    def __init__(self, socket_path: str, mgr: SessionManager):
        self.socket_path = socket_path
        self.mgr = mgr
        self._shutdown = threading.Event()
        self._listen_sock: Optional[socket.socket] = None

    def serve_forever(self) -> None:
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(self.socket_path)
        sock.listen(16)
        sock.settimeout(0.5)
        self._listen_sock = sock
        logger.info("ec_daemon listening on %s", self.socket_path)
        self._start_session_reaper()
        try:
            while not self._shutdown.is_set():
                try:
                    conn, _ = sock.accept()
                except socket.timeout:
                    continue
                t = threading.Thread(
                    target=self._handle_connection,
                    args=(conn,),
                    daemon=True,
                )
                t.start()
        finally:
            sock.close()
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass

    def shutdown(self) -> None:
        logger.info("shutting down ec_daemon")
        self._shutdown.set()
        self.mgr.close_all()

    def _start_session_reaper(self) -> None:
        """Background idle-session reaper.

        Worker-death survival (the attach path) means a crashed node's
        EC session deliberately stays open with nobody connected. The
        reaper bounds the resulting leak: sessions untouched for
        ``EC_DAEMON_SESSION_TTL_SECONDS`` (default 6h; <=0 disables)
        are closed. The default is generous on purpose — a live prover
        run touches its session every commit/probe, so only genuinely
        abandoned sessions age past the TTL.
        """
        try:
            ttl = float(
                os.environ.get("EC_DAEMON_SESSION_TTL_SECONDS", "21600")
            )
        except ValueError:
            ttl = 21600.0
        if ttl <= 0:
            return

        def _loop() -> None:
            while not self._shutdown.wait(60.0):
                try:
                    self.mgr.reap_idle(ttl)
                except Exception as e:  # never kill the reaper thread
                    logger.warning("session reaper error: %s", e)

        threading.Thread(target=_loop, daemon=True, name="session-reaper").start()

    def _handle_connection(self, conn: socket.socket) -> None:
        """One connection can carry multiple requests (newline-framed)."""
        try:
            buf = b""
            while not self._shutdown.is_set():
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    resp = self._dispatch(line)
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
        except Exception as e:
            logger.exception("connection handler error: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _dispatch(self, line: bytes) -> dict:
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            return _err_resp(f"JSON parse error: {e}")
        method = req.get("method")
        sid = req.get("session_id", "")
        params = req.get("params", {}) or {}
        handler = _METHOD_TABLE.get(method)
        if handler is None:
            return _err_resp(f"unknown method: {method!r}")
        try:
            return handler(self, sid, params)
        except Exception as e:
            logger.exception("handler error for %s: %s", method, e)
            return _err_resp(f"{type(e).__name__}: {e}")


def _ok_resp(result: Any) -> dict:
    return {"status": "ok", "result": result}


def _err_resp(msg: str) -> dict:
    return {"status": "error", "error": msg}


def _goal_to_dict(g: GoalState) -> dict:
    return {
        "raw": g.raw,
        "remaining": g.remaining,
        "is_closed": g.is_closed,
        "last_prompt": g.last_prompt,
    }


def _outcome_to_dict(o: TacticOutcome) -> dict:
    return {
        "accepted": o.accepted,
        "no_progress": o.no_progress,
        "raw_output": o.raw_output,
        "goal_after": _goal_to_dict(o.goal_after),
        "error": o.error,
    }


# ---------------------------------------------------------------------------
# Method handlers
# ---------------------------------------------------------------------------


def _h_open(srv: DaemonServer, sid: str, p: dict) -> dict:
    file_path = Path(p["file_path"]).resolve()
    include_dirs = p.get("include_dirs", []) or []
    lemma_name = p["lemma_name"]
    why3 = p.get("why3_socket")
    goal = srv.mgr.open(sid, file_path, include_dirs, lemma_name, why3)
    return _ok_resp(_goal_to_dict(goal))


def _h_close(srv: DaemonServer, sid: str, p: dict) -> dict:
    srv.mgr.close(sid)
    return _ok_resp(True)


def _h_list(srv: DaemonServer, sid: str, p: dict) -> dict:
    return _ok_resp(srv.mgr.list())


def _h_commit(srv: DaemonServer, sid: str, p: dict) -> dict:
    tactic = p["tactic"]
    with srv.mgr.with_session(sid) as ec:
        outcome = ec.execute(tactic)
    return _ok_resp(_outcome_to_dict(outcome))


def _h_try(srv: DaemonServer, sid: str, p: dict) -> dict:
    tactic = p["tactic"]
    with srv.mgr.with_session(sid) as ec:
        outcome = ec.try_tactic(tactic)
    return _ok_resp(_outcome_to_dict(outcome))


def _h_batch_try(srv: DaemonServer, sid: str, p: dict) -> dict:
    tactics = p["tactics"]
    with srv.mgr.with_session(sid) as ec:
        outcomes = ec.batch_try(tactics)
    return _ok_resp([_outcome_to_dict(o) for o in outcomes])


def _h_try_chain(srv: DaemonServer, sid: str, p: dict) -> dict:
    tactics = p["tactics"]
    with srv.mgr.with_session(sid) as ec:
        chain = ec.try_chain(tactics)
    return _ok_resp({
        "accepted": chain.accepted,
        "final_closed": chain.final_closed,
        "final_goal": _goal_to_dict(chain.final_goal),
        "steps": [_outcome_to_dict(s) for s in chain.steps],
        "failed_at": chain.failed_at,
        "error": chain.error,
    })


def _h_bridge_probe(srv: DaemonServer, sid: str, p: dict) -> dict:
    bridge_stmt = p["bridge_stmt"]
    timeout = float(p.get("timeout", 120.0))
    with srv.mgr.with_session(sid) as ec:
        result = ec.bridge_probe(bridge_stmt, timeout=timeout)
    return _ok_resp(result)


def _h_adopt(srv: DaemonServer, sid: str, p: dict) -> dict:
    """Rename live session ``session_id`` -> ``params.new_session_id``.

    Used by the worker-death attach path: a respawned proof node adopts
    the dead node's still-live EC session under its own session id so
    no committed-prefix replay is needed."""
    new_sid = p["new_session_id"]
    srv.mgr.adopt(sid, new_sid)
    return _ok_resp(True)


def _h_info(srv: DaemonServer, sid: str, p: dict) -> dict:
    return _ok_resp(srv.mgr.info(sid))


def _h_shutdown(srv: DaemonServer, sid: str, p: dict) -> dict:
    srv.shutdown()
    return _ok_resp(True)


def _h_goal(srv: DaemonServer, sid: str, p: dict) -> dict:
    """Return the latest goal state from the main EC (no tactic run)."""
    with srv.mgr.with_session(sid) as ec:
        # We don't have a dedicated "get goal" command in EC's -emacs
        # protocol; the goal emitted after the last commit is
        # already the current state. Re-send a no-op comment-only
        # line? Better: just return what we have. For now, we issue
        # a trivial non-effect query — ``pragma Goals.`` or send an
        # empty line. Neither is guaranteed universal. As a safe
        # option we simply re-send the last committed tactic output
        # from internal cache... but we don't cache raw. So for now,
        # re-send a no-op: ``locate Int.`` which always works and
        # leaves state unchanged, then parse the goal out of the
        # next prompt's output. This is a temporary stopgap; a
        # better primitive can be added later.
        ec._send("locate Int.")
        raw = ec._read_until_prompt().decode("utf-8", errors="replace")
    return _ok_resp({"raw": raw})


_METHOD_TABLE = {
    "open_session": _h_open,
    "close_session": _h_close,
    "list_sessions": _h_list,
    "commit": _h_commit,
    "try_tactic": _h_try,
    "batch_try": _h_batch_try,
    "try_chain": _h_try_chain,
    "bridge_probe": _h_bridge_probe,
    "get_goal": _h_goal,
    "adopt_session": _h_adopt,
    "session_info": _h_info,
    "shutdown": _h_shutdown,
}


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Persistent EasyCrypt daemon")
    ap.add_argument("--socket", default=SOCKET_PATH_DEFAULT,
                    help="Unix socket path")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    mgr = SessionManager()
    srv = DaemonServer(args.socket, mgr)

    # PID file so a supervisor can force-kill an unresponsive daemon (and its
    # easycrypt -emacs children, since we are a session leader) instead of
    # leaking it to PID 1 — see prover._hard_kill_ec_daemon. The daemon is a
    # session leader (spawned start_new_session=True), so killing this pid's
    # process group reaps the whole EC child set.
    pid_path = args.socket + ".pid"
    try:
        with open(pid_path, "w", encoding="utf-8") as _pf:
            _pf.write(str(os.getpid()))
    except OSError:
        pid_path = None

    def _cleanup() -> None:
        # Reap EC children on ANY clean exit path (normal return, SystemExit,
        # SIGINT/SIGTERM via _sig) so they are not orphaned. close_all is
        # idempotent. Only an uncatchable SIGKILL/OOM skips this — that is the
        # case _hard_kill_ec_daemon's process-group kill exists to cover.
        try:
            mgr.close_all()
        except Exception:
            pass
        if pid_path:
            try:
                os.unlink(pid_path)
            except OSError:
                pass

    import atexit
    atexit.register(_cleanup)

    def _sig(*_a):
        srv.shutdown()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
