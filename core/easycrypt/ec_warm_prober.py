"""Warm ephemeral EC prober — fast read-only tactic probing via run-then-undo.

A daemon read-only probe (``ECDaemon.try_tactic``) spawns a fresh ``easycrypt
-emacs`` subprocess, replays the setup commands + every committed tactic, runs
ONE tactic, and kills the process. That costs ~1.4 s/probe — dominated by theory
loading, NOT the tactic — and it grows with proof depth (O(setup + committed)).

This module keeps ONE warm ephemeral process stopped at the committed state and
probes each tactic by running it and rolling back with ``undo <N>.`` — the
step-numbered ProofGeneral backtrack. (Note: the bare ``undo.`` / ``Undo.``
parse-error in ``-emacs`` mode, which is why ``ECDaemon`` concluded there was no
in-place rollback and fell back to spawn-fresh; the step-numbered form works.)
The ``-emacs`` prompt ``[N|check]`` exposes the step number N; after a probe the
counter is at N+1 (or the goal changed), and ``undo <base>.`` returns it to the
committed base step. Measured: ~0.02 s/probe after a one-time ~1.4 s warm-up —
~70x faster per probe, and it does not grow with proof depth.

Isolation/safety: the warm process is a DEDICATED ephemeral, never the daemon's
committed ``self.proc`` — so a probe can never corrupt the real proof state (the
reason ``ECDaemon`` spawned fresh). On any *drift* (a probe whose ``undo`` does
not return to the base step) or process failure, the prober marks itself dead via
``alive`` so the caller falls back to spawn-fresh. It is invalidated whenever the
committed state changes (a new commit → re-``open`` to replay the new prefix).

STANDALONE: this is not yet wired into ``ECDaemon``. It isolates the mechanism +
its safety tests so it can be validated across tactic types (smt, multi-subgoal,
goal-closing, long runs) before integration. See ``tests/test_ec_warm_prober.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.easycrypt.ec_lifecycle import split_ec_commands as _split_ec_commands
from core.easycrypt.ec_lifecycle import ECSessionLifecycle

# The `-emacs` prompt is `[<step>|<mode>]>`; the step number is the rollback key.
_STEP_RE = re.compile(r"\[(\d+)\|")
# Error/critical markers EC emits in `-emacs` mode (e.g. `[error-4-6]parse error`).
_ERROR_RE = re.compile(r"\[(?:error|critical)\b")


def _last_step(raw: str) -> Optional[int]:
    found = _STEP_RE.findall(raw or "")
    return int(found[-1]) if found else None


def _goal_text(raw: str) -> str:
    """Best-effort goal text from a chunk of EC output (the lines that are not
    blank and not a prompt token)."""
    out = [s for s in (line.strip() for line in (raw or "").splitlines())
           if s and not s.startswith("[")]
    return " ".join(out[-6:])[:400]


def _error_text(raw: str) -> str:
    m = re.search(r"\[(?:error|critical)[^\n]*", raw or "")
    if m:
        return m.group(0)[:200]
    for line in reversed((raw or "").splitlines()):
        s = line.strip()
        if s and not s.startswith("["):
            return s[:200]
    return ""


@dataclass
class ProbeResult:
    """Outcome of one warm probe. ``advanced`` iff the proof state changed (the
    step counter moved or the goal closed) — the authoritative "did it apply"
    signal, and what decides whether a rollback is needed. ``accepted`` is a
    best-effort flag for standalone use (a caller with EC's own error parser
    should re-derive accepted/goal/no_progress from ``raw`` instead). ``raw`` is
    the full EC output the probe produced, before the rollback."""
    accepted: bool
    advanced: bool = False
    error: str = ""
    goal_after: str = ""
    raw: str = ""


class WarmProber(ECSessionLifecycle):
    """Reusable warm EC process for fast read-only probing (run-then-``undo``).

    Lifecycle: ``open(file, lemma, committed)`` pays the one-time replay, then
    ``probe(tactic)`` is ~0.02 s each. ``alive`` is False after a drift / death /
    ``close()``; the caller must then re-``open`` or fall back to spawn-fresh.
    Inherits the shared EC pipe lifecycle (spawn/drain/read/send/teardown) and
    adds only the run-then-``undo`` semantics on top.
    """

    _label = "warm EC"

    def __init__(self, include_dirs, why3_socket: Optional[str] = None, env=None):
        super().__init__(include_dirs, why3_socket, env=env)
        self._base_step: Optional[int] = None
        self._base_goal: str = ""
        self._dead = True

    # ── lifecycle ────────────────────────────────────────────────────────────

    @property
    def alive(self) -> bool:
        return (self.proc is not None and not self._dead
                and self.proc.poll() is None)

    @property
    def base_step(self) -> Optional[int]:
        return self._base_step

    @property
    def base_goal(self) -> str:
        return self._base_goal

    def open(self, file_path, lemma_name: str, committed_tactics=(),
             setup_commands=None, timeout: float = 120.0) -> bool:
        """Spawn the warm process, replay setup + committed tactics once, and
        record the committed base step. Returns ``alive``.

        ``setup_commands`` lets a caller that already has the replay prefix (e.g.
        ``ECSubprocess._setup_commands``) pass it directly, so the warm process
        replays EXACTLY the committed process's setup; when ``None`` it is
        re-derived with ``extract_lemma``."""
        self.close()
        try:
            if setup_commands is None:
                from core.easycrypt.lemma_extract import extract_lemma  # type: ignore
                setup_commands = _split_ec_commands(
                    extract_lemma(Path(file_path), lemma_name, open_proof=True))
            self.spawn()   # spawn + drain banner (shared lifecycle base)
            setup = [c for c in setup_commands if c and c.strip()]
            last = ""
            for cmd_line in [*setup, *committed_tactics]:
                last = self._send_recv(cmd_line, timeout)
                if _ERROR_RE.search(last):
                    self.close()
                    return False
            step = _last_step(last) if last else _last_step(self._send_recv("pragma noop.", timeout))
            if step is None:
                self.close()
                return False
            self._base_step = step
            self._base_goal = _goal_text(last)
            self._dead = False
            return True
        except Exception:
            self.close()
            return False

    def close(self) -> None:
        # Bounded teardown (SIGTERM -> wait -> SIGKILL -> bounded wait -> abandon),
        # the same give-up-not-block sequence as the daemon/ephemeral paths, via
        # the shared lifecycle base (audit §8 #6 / #3).
        self.teardown(
            grace=3.0,
            abandon_msg=(
                "warm EC subprocess pid=%s did not exit after SIGKILL; "
                "abandoning it to release the warm prober."
            ),
        )
        self._dead = True
        self._base_step = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    # ── probing ──────────────────────────────────────────────────────────────

    def _send_recv(self, line: str, timeout: float) -> str:
        """Send one command and read its full response. Warm probes are
        send-then-read; the base ``_send`` is the bare write."""
        super()._send(line)
        return self._read_until_prompt(timeout=timeout).decode(
            "utf-8", errors="replace")

    def probe(self, tactic: str, timeout: float = 120.0) -> ProbeResult:
        """Run ``tactic`` read-only and roll back to the base step. Marks the
        prober dead on any drift / failure (then ``alive`` is False)."""
        if not self.alive:
            raise RuntimeError("WarmProber is not alive; re-open or fall back")
        try:
            raw = self._send_recv(tactic, timeout)
        except Exception as exc:
            self._dead = True
            return ProbeResult(accepted=False, error=f"{type(exc).__name__}: {exc}")
        step = _last_step(raw)
        # advanced = the proof state changed (counter moved or the goal closed,
        # which drops the `[N|check]` prompt). A rejected or no-progress tactic
        # leaves the step where it was. advanced decides whether to roll back.
        advanced = step is None or step != self._base_step
        accepted = advanced and not _ERROR_RE.search(raw)
        goal_after = _goal_text(raw) if accepted else ""
        if advanced:
            try:
                back = self._send_recv(f"undo {self._base_step}.", timeout)
            except Exception as exc:
                self._dead = True
                return ProbeResult(accepted=accepted, advanced=advanced,
                                   error=f"undo failed: {type(exc).__name__}: {exc}",
                                   goal_after=goal_after, raw=raw)
            if _last_step(back) != self._base_step:
                self._dead = True   # drift: could not restore the base step
        return ProbeResult(
            accepted=accepted, advanced=advanced,
            error="" if accepted else _error_text(raw),
            goal_after=goal_after, raw=raw)

    def probe_chain(self, tactics, timeout: float = 120.0):
        """Run ``tactics`` as a sequence on the warm process (each step sees the
        prior step's state), capturing the raw EC output per step until the goal
        closes or the list is exhausted, then roll the WHOLE chain back to the
        committed base step. Returns ``(step_raws, ok)``; ``ok`` is False (and the
        prober is marked dead) if the rollback could not restore the base step.

        It deliberately does NOT stop early on an apparent error — the caller (a
        consumer with EC's own parsers) decides the first failure from the
        per-step raws, so this only needs to never *truncate before* the failure;
        any steps it ran past a failure are cheap (~0.02 s, all undone) and are
        ignored by the caller's break-at-first-failure logic."""
        if not self.alive:
            raise RuntimeError("WarmProber is not alive; re-open or fall back")
        raws: list[str] = []
        advanced_any = False
        for tac in tactics:
            try:
                raw = self._send_recv(tac, timeout)
            except Exception:
                self._dead = True
                return raws, False
            raws.append(raw)
            step = _last_step(raw)
            if step is None or "No more goals" in raw:   # goal closed -> stop
                advanced_any = True
                break
            if step != self._base_step:
                advanced_any = True
        if advanced_any:
            try:
                back = self._send_recv(f"undo {self._base_step}.", timeout)
            except Exception:
                self._dead = True
                return raws, False
            if _last_step(back) != self._base_step:
                self._dead = True
                return raws, False
        return raws, True
