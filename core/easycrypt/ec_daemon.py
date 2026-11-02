#!/usr/bin/env python3
"""Persistent EasyCrypt daemon: keeps one ``easycrypt -emacs`` subprocess
per session alive across tactic submissions, enabling fast speculative
execution (try tactic → rollback) without the 5-15s per-call re-spawn +
history-replay overhead session_cli currently pays.

Transport: Unix socket at ``ec_daemon_client.default_socket_path()``
(``EC_DAEMON_SOCKET``, else a per-checkout ``/tmp/ec_daemon_<hash>.sock``).
Framing: newline-delimited JSON objects, one request/response per line.

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
        subprocess, load ``file_path`` up to the lemma's ``proof.`` (via
        ``lemma_extract``), return current goal state.
    commit(tactic, timeout): advance permanently, append to history, return
        new goal state. A rejected transaction leaves the session at its
        pre-commit level (sentences it ran are undone) or, when that cannot
        be shown, discards the session. A transaction EasyCrypt does not
        finish within ``timeout`` seconds is rejected with ``timed_out`` and
        the session is discarded.
    rewind(keep, keep_identity, held_identity): return the committed
        process to the level recorded after its first ``keep`` committed
        transactions with EasyCrypt's ``undo <level>.``, without re-running
        anything. It refuses (and changes nothing) when the identities do
        not describe what the session holds or the undone range contains a
        command whose effect ``undo`` does not revert; see ``rewind``.
    try_tactic(tactic) / try_chain(tactics): run read-only and return
        the outcome; the committed session is never touched.
    get_goal(): current goal state.
    adopt_session(new_session_id) / session_info(): rename a live session,
        report its liveness and committed count.
    list_sessions(): active session ids.
    close_session(): terminate EC subprocess.
    shutdown(): stop daemon.

Errors: if EC hits an error line (e.g. ``[error-N-M]cannot ...``), the
response's ``error`` field carries ``ec_diagnostics.parse_error``'s
    {kind: "unification_fail"|"no_progress"|"unknown_lemma"|
           "type_error"|"other",
     raw: str, severity: str}

Read-only probes: ``try_tactic`` / ``try_chain`` run on a separate warm
process stopped at the committed state and rolled back with the
step-numbered ``undo <N>.`` (``ec_warm_prober``), or, when that is disabled
or drifts, on a fresh ephemeral EC that replays setup + committed tactics.

Scope for this initial version: single-host, trust all local clients,
no auth. Persistence across daemon restart is NOT supported — a
restart wipes all sessions (clients reopen).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import signal
import socket
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

from core.easycrypt.committed_history import committed_prefix_identity  # noqa: E402
from core.easycrypt.ec_lifecycle import ECSessionLifecycle  # noqa: E402
from core.easycrypt.ec_prompt import PROMPT_RE  # noqa: E402
from core.easycrypt.proof_text import (  # noqa: E402
    split_ec_commands,
    strip_comments,
    undo_unsafe_sentence,
)
from core.easycrypt.ec_env import get_ec_env  # noqa: E402
from core.easycrypt.ec_daemon_client import default_socket_path  # noqa: E402
from core.easycrypt.ec_diagnostics import parse_error  # noqa: E402


logger = logging.getLogger("ec_daemon")

# The interleaved warm handoff still imports the splitter under this name.
_split_ec_commands = split_ec_commands


def _with_final_dot(tactic: str) -> str:
    """End ``tactic`` with a dot unless its code (not a comment) already does."""
    if strip_comments(tactic).rstrip().endswith("."):
        return tactic
    return tactic.rstrip() + "."


def _prompt_level(raw: str) -> Optional[tuple[int, str]]:
    """``(level, mode)`` of the last ``[level|mode]>`` prompt in ``raw``."""
    found = None
    for match in PROMPT_RE.finditer(raw or ""):
        found = (int(match.group(1)), match.group(2))
    return found


@dataclass(frozen=True)
class _Level:
    """EasyCrypt's undo level after setup or after one committed transaction.

    ``undoable`` says whether ``undo`` can take this transaction back: it ran
    no command whose effect ``undo`` does not revert, and it raised the level.
    ``open_goal`` says whether EasyCrypt's reply showed an open goal.
    """

    level: int
    mode: str
    undoable: bool = True
    open_goal: bool = False


class RewindRefused(RuntimeError):
    """The session cannot be rewound by ``undo``; nothing was sent to EC."""


class SetupRejected(RuntimeError):
    """EasyCrypt rejected a command of the lemma's context. Opening the same
    source again fails the same way."""


def _shows_open_goal(goal: "GoalState") -> bool:
    return bool(not goal.is_closed and goal.remaining >= 1)


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
    error: Optional[dict] = None  # {kind, raw, severity?}


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
        # The client's transaction texts exactly as submitted, so a rewind can
        # check the client's committed-prefix identity against what this
        # process actually ran.
        self._committed_requests: list[str] = []
        # Undo levels: one after setup, then one per committed transaction.
        # Empty when the setup level is unknown; rewinds are then refused.
        self._levels: list[_Level] = []
        # The level and mode of the last prompt read from the process.
        self._prompt: Optional[tuple[int, str]] = None
        # A warm ephemeral EC kept at the committed state for fast read-only
        # batch probing (run-then-``undo``, ~0.02 s/probe vs ~1.4 s spawn-fresh).
        # Lazily built, invalidated on every commit. See ``try_tactic``.
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
        """Return the single repository-managed EasyCrypt environment."""

        return get_ec_env()

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
        commands = [c for c in split_ec_commands(extracted) if c.strip()]
        self._setup_commands = list(commands)
        final_output = b""
        for cmd in commands:
            self._send(cmd)
            final_output = self._read_until_prompt(timeout=120.0)
            err = self._parse_error(
                final_output.decode("utf-8", errors="replace")
            )
            if err is not None:
                raise SetupRejected(
                    f"EC rejected setup command {cmd!r} for lemma "
                    f"{lemma_name!r}: {err}"
                )
        text = final_output.decode("utf-8", errors="replace")
        self._prompt = _prompt_level(text)
        goal = self._parse_goal_state(text)
        self._levels = (
            [_Level(*self._prompt, open_goal=_shows_open_goal(goal))]
            if self._prompt is not None else []
        )
        return goal

    # -----------------------------------------------------------------
    # Tactic execution
    # -----------------------------------------------------------------

    def execute(self, tactic: str, timeout: Optional[float] = None) -> TacticOutcome:
        """Send one tactic, return the outcome. Tactic is appended to
        history if accepted. Callers should hold the session lock.

        ``timeout`` (default ``_RESPONSE_TIMEOUT_DEFAULT``) bounds the whole
        transaction. When it runs out, ``TimeoutError`` propagates and the
        process is desynchronized.
        """
        request = tactic
        tactic = _with_final_dot(tactic)
        before = self._prompt
        # A manager transaction may contain several EC sentences. Drain one
        # response per sentence, exactly as bootstrap does; otherwise a later
        # call can consume an earlier sentence's buffered prompt. Commit to the
        # journal only if the entire transaction succeeds.
        raw = self.send_and_drain(
            tactic,
            timeout=self._RESPONSE_TIMEOUT_DEFAULT if timeout is None else timeout,
            is_error=self._parse_error,
            whole_transaction=True,
        )
        self._prompt = _prompt_level(raw)
        goal = self._parse_goal_state(raw)
        err = self._parse_error(raw)
        if err is None:
            self.committed_count += 1
            self._committed_tactics.append(tactic)
            self._committed_requests.append(request)
            self._record_level(request, goal)
            self._invalidate_warm()   # committed state moved; warm prober is stale
            return TacticOutcome(
                accepted=True,
                raw_output=raw,
                goal_after=goal,
                error=None,
            )
        self._restore_after_rejection(request, before)
        return TacticOutcome(
            accepted=False,
            raw_output=raw,
            goal_after=goal,
            error=err,
        )

    # -----------------------------------------------------------------
    # Undo levels and rewind
    # -----------------------------------------------------------------

    def _record_level(self, request: str, goal: "GoalState") -> None:
        """Record the level an accepted transaction left the process at."""
        if not self._levels or len(self._levels) != len(self._committed_requests):
            # The setup level is unknown or an earlier entry is missing.
            self._levels = []
            return
        if self._prompt is None:
            self._levels = []
            return
        level, mode = self._prompt
        undoable = (
            level > self._levels[-1].level and not undo_unsafe_sentence(request)
        )
        self._levels.append(_Level(level, mode, undoable, _shows_open_goal(goal)))

    def _restore_after_rejection(
        self,
        request: str,
        before: Optional[tuple[int, str]],
    ) -> None:
        """Leave the process at its pre-commit level after a rejection.

        EasyCrypt does not push a level for a failed sentence, but sentences
        before it in the same transaction did run. They are undone here. A
        rejected transaction that ran a command ``undo`` cannot revert, or a
        level that cannot be accounted for, desynchronizes the process, so
        the session is discarded and the client reopens it.
        """
        after = self._prompt
        if before is not None and after == before:
            if undo_unsafe_sentence(request):
                self._mark_desynchronized(
                    "rejected transaction ran a command undo cannot revert"
                )
            return
        if (
            before is None
            or after is None
            or after[0] < before[0]
            or undo_unsafe_sentence(request)
        ):
            self._mark_desynchronized(
                f"rejected transaction left level {after} after {before}"
            )
            return
        try:
            raw = self.send_and_drain(
                f"undo {before[0]}.",
                timeout=self._RESPONSE_TIMEOUT_DEFAULT,
                is_error=self._parse_error,
            )
        except Exception as exc:  # the pipe is already marked desynchronized
            self._mark_desynchronized(f"undo after rejection failed: {exc}")
            return
        self._prompt = _prompt_level(raw)
        if self._prompt != before or self._parse_error(raw) is not None:
            self._mark_desynchronized(
                f"undo after rejection reached {self._prompt}, expected {before}"
            )

    def rewind(
        self,
        keep: int,
        *,
        keep_identity: str,
        held_identity: Optional[str] = None,
        require_open_goal: bool = False,
    ) -> dict:
        """Return to the level recorded after the first ``keep`` transactions.

        ``keep_identity`` must be the committed-prefix identity of those
        transactions and ``held_identity``, when given, that of everything
        this process committed; both are checked against the texts it
        actually ran. Every undone transaction must be undoable and the
        recorded levels must rise strictly; with ``require_open_goal`` the
        target level must have shown an open goal. Raises ``RewindRefused``
        before sending anything when a check fails. Sends ``undo <level>.``
        and requires EasyCrypt's prompt to report exactly that level and
        mode; otherwise the process is desynchronized and the session is
        discarded.

        Kept transactions are not re-run: the restored scope is the one
        EasyCrypt built when it accepted them.
        """
        held = len(self._committed_requests)
        if (
            held_identity is not None
            and committed_prefix_identity(self._committed_requests) != held_identity
        ):
            raise RewindRefused("held_identity_mismatch")
        if type(keep) is not int or keep < 0 or keep > held:
            raise RewindRefused("keep_out_of_range")
        if committed_prefix_identity(self._committed_requests[:keep]) != keep_identity:
            raise RewindRefused("keep_identity_mismatch")
        if len(self._levels) != held + 1:
            raise RewindRefused("undo_levels_unknown")
        target = self._levels[keep]
        if require_open_goal and not target.open_goal:
            raise RewindRefused("target_state_has_no_open_goal")
        for index in range(keep + 1, held + 1):
            entry = self._levels[index]
            if not entry.undoable or entry.level <= self._levels[index - 1].level:
                raise RewindRefused(f"transaction_{index}_not_undoable")
        if keep == held:
            return {"kept": keep, "undone": 0, "raw": "", "level": target.level}
        raw = self.send_and_drain(
            f"undo {target.level}.",
            timeout=self._RESPONSE_TIMEOUT_DEFAULT,
            is_error=self._parse_error,
        )
        self._prompt = _prompt_level(raw)
        if (
            self._prompt != (target.level, target.mode)
            or self._parse_error(raw) is not None
        ):
            self._mark_desynchronized(
                f"undo {target.level} reached {self._prompt}"
            )
            raise RuntimeError(
                f"undo {target.level} reached {self._prompt}; session discarded"
            )
        del self._committed_tactics[keep:]
        del self._committed_requests[keep:]
        del self._levels[keep + 1:]
        self.committed_count = keep
        self._invalidate_warm()   # committed state moved; warm prober is stale
        return {
            "kept": keep,
            "undone": held - keep,
            "raw": raw,
            "level": target.level,
        }

    def reprint_goal(self) -> str:
        """Make EasyCrypt print the current state with a query that does not
        change it (``locate Int.``). The query raises the level by one;
        recorded levels stay valid because ``undo`` pops to an absolute
        level."""
        self._send("locate Int.")
        raw = self._read_until_prompt().decode("utf-8", errors="replace")
        self._prompt = _prompt_level(raw) or self._prompt
        return raw

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
        on accepted / goal / error."""
        raw = res.raw or ""
        err = self._parse_error(raw)
        goal = self._parse_goal_state(raw)
        return TacticOutcome(
            accepted=(err is None), raw_output=raw, goal_after=goal, error=err)

    # Note: EC in ``-emacs`` mode rejects a bare ``undo.`` / ``Undo.`` as a
    # parse error, and ``abort.`` cannot re-enter the same lemma. The
    # level-numbered ``undo <N>.`` does work: the warm prober uses it after
    # every probe and ``rewind`` uses it on the committed process. Probes never
    # run on the committed process; without the warm prober a probe spawns an
    # ephemeral EC, replays setup + all committed tactics, runs the speculative
    # tactic and terminates. See ``try_tactic``.

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
            tac = _with_final_dot(tactic)
            raw = eph.send_and_drain(tac, timeout=timeout, is_error=self._parse_error)
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
                t_norm = _with_final_dot(tac.strip())
                raw = eph.send_and_drain(t_norm, timeout=timeout, is_error=self._parse_error)
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
        last_prompt = ""
        for m in PROMPT_RE.finditer(raw):
            last_prompt = m.group(0)
        return GoalState(
            raw=raw, remaining=remaining,
            is_closed=is_closed, last_prompt=last_prompt,
        )

    _parse_error = staticmethod(parse_error)


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
        ec = ECSubprocess(include_dirs=include_dirs,
                          why3_socket=why3_socket)
        # The id is reserved at once, but its lock is held from before
        # registration until bootstrap ends, so no request can reach a
        # half-initialised EC; a failed bootstrap unregisters and stops it.
        lock = threading.Lock()
        with lock:
            with self._registry_lock:
                if session_id in self._sessions:
                    raise ValueError(
                        f"session {session_id!r} already open; close it first"
                    )
                self._sessions[session_id] = ec
                self._locks[session_id] = lock
                self._last_used[session_id] = time.time()
            try:
                ec.spawn()
                return ec.load_context_and_enter_proof(file_path, lemma_name)
            except BaseException:
                self._discard(ec)
                raise

    def _discard(self, ec: ECSubprocess) -> None:
        """Unregister ``ec`` under whatever id it now has and stop it. The
        caller holds its session lock, so no request is using the pipe."""
        with self._registry_lock:
            for sid in [k for k, v in self._sessions.items() if v is ec]:
                self._sessions.pop(sid, None)
                self._locks.pop(sid, None)
                self._last_used.pop(sid, None)
        ec.close()

    def _is_registered(self, ec: ECSubprocess) -> bool:
        with self._registry_lock:
            return any(v is ec for v in self._sessions.values())

    def close(self, session_id: str) -> None:
        with self._registry_lock:
            ec = self._sessions.pop(session_id, None)
            lock = self._locks.pop(session_id, None)
            self._last_used.pop(session_id, None)
        if ec is None:
            return
        if lock is None:
            ec.close()
            return
        # A request still running on this session owns the pipe. Kill EC so it
        # fails at once instead of finishing its sentence, and tear down only
        # after it has let go of the lock.
        if not lock.acquire(blocking=False):
            ec.interrupt()
            lock.acquire()
        try:
            ec.close()
        finally:
            lock.release()

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
        self._ec: Optional[ECSubprocess] = None

    def __enter__(self) -> ECSubprocess:
        with self.mgr._registry_lock:
            ec = self.mgr._sessions.get(self.sid)
            lock = self.mgr._locks.get(self.sid)
            if ec is not None:
                self.mgr._last_used[self.sid] = time.time()
        if ec is None or lock is None:
            raise KeyError(f"session {self.sid!r} not open")
        lock.acquire()
        # The previous holder may have discarded or closed this session.
        if not self.mgr._is_registered(ec):
            lock.release()
            raise KeyError(f"session {self.sid!r} not open")
        self._lock = lock
        self._ec = ec
        return ec

    def __exit__(self, *a):
        if self._lock is None:
            return
        try:
            # A timed-out or failed exchange leaves a late reply in the pipe;
            # drop the session so the client reopens and replays it.
            if getattr(self._ec, "desynchronized", False):
                self.mgr._discard(self._ec)
        finally:
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


def _err_resp(msg: str, kind: Optional[str] = None) -> dict:
    response = {"status": "error", "error": msg}
    if kind:
        response["kind"] = kind
    return response


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
    try:
        goal = srv.mgr.open(sid, file_path, include_dirs, lemma_name, why3)
    except SetupRejected as exc:
        # Say so as a class: the client stops reopening the same source.
        return _err_resp(f"{type(exc).__name__}: {exc}", kind="setup_rejected")
    return _ok_resp(_goal_to_dict(goal))


def _h_close(srv: DaemonServer, sid: str, p: dict) -> dict:
    srv.mgr.close(sid)
    return _ok_resp(True)


def _h_list(srv: DaemonServer, sid: str, p: dict) -> dict:
    return _ok_resp(srv.mgr.list())


# A client's limit for one transaction is capped at a batch run's
# (``ec_backend.BATCH_TIMEOUT_SECONDS``).
_MAX_COMMIT_TIMEOUT_SECONDS = 600.0


def _commit_timeout(value: Any) -> float:
    """The client's limit for one transaction, capped. A request without a
    usable limit (an older client) keeps ``_RESPONSE_TIMEOUT_DEFAULT``."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        return ECSubprocess._RESPONSE_TIMEOUT_DEFAULT
    return min(float(value), _MAX_COMMIT_TIMEOUT_SECONDS)


def _h_commit(srv: DaemonServer, sid: str, p: dict) -> dict:
    """Commit ``params.tactic``, giving EasyCrypt ``params.timeout`` seconds.

    A transaction EasyCrypt does not finish in time is a verdict, not an
    error: ``{"accepted": False, "timed_out": True, ...}``. The process still
    owes the late reply, so leaving the session context discards it and the
    client reopens and replays."""
    tactic = p["tactic"]
    timeout = _commit_timeout(p.get("timeout"))
    with srv.mgr.with_session(sid) as ec:
        try:
            outcome = ec.execute(tactic, timeout=timeout)
        except TimeoutError:
            ec._mark_desynchronized(f"transaction timed out after {timeout:g}s")
            message = f"EasyCrypt did not finish this transaction within {timeout:g} s"
            return _ok_resp({
                "accepted": False,
                "timed_out": True,
                "timeout": timeout,
                "raw_output": "",
                "goal_after": _goal_to_dict(GoalState(raw="")),
                "error": {"kind": "timeout", "raw": message},
            })
    return _ok_resp(_outcome_to_dict(outcome))


def _h_rewind(srv: DaemonServer, sid: str, p: dict) -> dict:
    """Undo the committed process back to ``params.keep`` transactions.

    A refusal is a structured ``{"rewound": False, "reason": ...}`` reply and
    leaves the session untouched; a failed ``undo`` discards the session and
    is reported as an error."""
    keep = p["keep"]
    with srv.mgr.with_session(sid) as ec:
        try:
            result = ec.rewind(
                keep,
                keep_identity=str(p["keep_identity"]),
                held_identity=p.get("held_identity"),
                require_open_goal=bool(p.get("require_open_goal")),
            )
        except RewindRefused as refused:
            return _ok_resp({"rewound": False, "reason": str(refused)})
    goal = ECSubprocess._parse_goal_state(result["raw"])
    return _ok_resp({
        "rewound": True,
        "kept": result["kept"],
        "undone": result["undone"],
        "raw_output": result["raw"],
        "goal_after": _goal_to_dict(goal),
        "level": result["level"],
    })


def _h_try(srv: DaemonServer, sid: str, p: dict) -> dict:
    tactic = p["tactic"]
    with srv.mgr.with_session(sid) as ec:
        outcome = ec.try_tactic(tactic)
    return _ok_resp(_outcome_to_dict(outcome))


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
        # EC's -emacs protocol has no "print goal" command; a query that
        # leaves the state unchanged makes it print the current goal.
        raw = ec.reprint_goal()
    return _ok_resp({"raw": raw})


_METHOD_TABLE = {
    "open_session": _h_open,
    "close_session": _h_close,
    "list_sessions": _h_list,
    "commit": _h_commit,
    "rewind": _h_rewind,
    "try_tactic": _h_try,
    "try_chain": _h_try_chain,
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
    ap.add_argument("--socket", default=default_socket_path(),
                    help="Unix socket path (default: EC_DAEMON_SOCKET env or "
                         "the per-checkout /tmp path)")
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
    # leaking it to PID 1 — see ec_services._hard_kill_ec_daemon. The daemon is a
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
