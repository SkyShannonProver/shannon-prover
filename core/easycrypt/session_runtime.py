#!/usr/bin/env python3
"""Runtime implementation for EasyCrypt proof sessions.

This module owns the concrete Session class and runtime helpers.
session_cli.py is kept as the argparse/dispatch entry point.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.easycrypt.session_common import (
    trim_after_last_prompt as _trim_after_last_prompt,
)
from core.easycrypt.session_display import (
    compress_current_state,
    format_try_chain,
    format_try_single,
)

from core.easycrypt.session_no_progress import detect_no_progress  # no-progress detection (extracted)
from core.easycrypt.session_tactic_precheck import precheck_tactic  # tactic precheck (extracted)
from core.easycrypt.ec_backend import ECBackend, ECResult  # EC execution (extracted)
from core.easycrypt.session_rollback import RollbackJournal  # pre-commit file txn (extracted)

from core.easycrypt.session_display import reorder_display as _reorder_display

from core.easycrypt.session_events import append_error_event as _append_error_event
from core.easycrypt.session_events import append_event as _append_event
from core.easycrypt.session_events import events_path as _events_path


@dataclass(frozen=True)
class UndoStepResult:
    """Concrete outcome of one requested history rewind."""

    output: str
    status: str
    undone_tactic: str
    remaining_steps: int

    @property
    def state_changed(self) -> bool:
        return self.status == "ok"


class Session:
    def __init__(self, session_dir: Path, include_dirs: list[str] | None = None):
        self.dir = session_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._ec_backend = ECBackend(self.dir)  # batch EC execution (daemon path TBD)
        self._include_file = self.dir / "include_dirs.txt"
        # Merge: CLI args override, but also load persisted dirs from previous invocations
        persisted = []
        if self._include_file.exists():
            persisted = [d for d in self._include_file.read_text().splitlines() if d.strip()]
        if include_dirs:
            self._include_dirs = include_dirs
        else:
            self._include_dirs = persisted
        # Files
        self.keep = self.dir / ".keep"
        self.history = self.dir / "history.ec"
        self.steps = self.dir / "steps.log"
        self.curr = self.dir / "current.out"
        self.prev = self.dir / "prev.out"
        self.delta = self.dir / "delta.out"
        self.prev_hist = self.dir / "prev.hist"
        self.context_file = self.dir / "context.ec"
        # The pre-commit snapshot/restore transaction over these files (extracted).
        self._rollback = RollbackJournal(
            self.history, self.steps, self.curr, self.prev, self.prev_hist,
        )
        self.events = _events_path(self.dir)
        # Touch essential files if missing
        self.keep.touch(exist_ok=True)
        for p in [self.history, self.curr, self.prev]:
            if not p.exists():
                p.write_text("")
        # Daemon backend: lazy-initialized on the first managed commit when
        # session_meta.json supplies (file, lemma). Gracefully falls back
        # to the subprocess path on any failure. See daemon_backend.py.
        self._daemon_backend = None  # type: ignore[assignment]
        # Set by _try_daemon_path when the latest commit went through the
        # daemon. It is audit metadata and may also be consulted by explicit
        # read-only inspections that require a synchronized daemon.
        self._last_commit_via_daemon = False
        # Why the last commit routed daemon-vs-batch (one of the _route()
        # reasons) — surfaced as an `ec.routing` event for audit visibility.
        self._last_routing_reason = ""

    def emit_event(
        self, event_type: str, payload: dict | None = None,
        *, source: str = "session_cli",
    ) -> bool:
        """Append a structured session event without affecting proof flow."""
        return bool(_append_event(
            self.dir, event_type, payload or {}, source=source,
        ))

    def emit_error_event(
        self, event_type: str, exc: BaseException,
        payload: dict | None = None, *, source: str = "session_cli",
    ) -> bool:
        return bool(_append_error_event(
            self.dir, event_type, exc, payload or {}, source=source,
        ))

    def _get_daemon_meta(self):
        """Return (file_path, lemma_name) from session_meta.json, or
        (None, None) if the session wasn't started with both -f and
        -lemma (whole-file sessions fall back to subprocess)."""
        meta_path = self.dir / "session_meta.json"
        if not meta_path.exists():
            return None, None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None, None
        fpath = meta.get("file")
        lname = meta.get("lemma")
        if not fpath or not lname:
            return None, None
        return fpath, lname

    def _apply_no_progress_rollback(self) -> None:
        """Restore the session to its pre-tactic state after a tactic
        was accepted by EC but produced no goal change.

        Called by `append_block` when the hook registry's mutation
        aggregate has `request_rollback=True` (set by
        `tactic_no_effect_trigger`). The rollback restores
        history.ec from prev_hist, pops the last step from
        steps.log, restores curr.out from prev.out, and invalidates
        the daemon cache. Without the daemon invalidation, the
        in-memory EC state would be ahead of the file state and
        downstream tactics would be applied on top of a phantom
        committed tactic.
        """
        self._rollback.restore_pre_commit()
        # EC has no undo; the daemon session must be dropped and
        # replayed on the next commit. Invalidate the cache.
        self._invalidate_daemon()

    def _route(
        self, reason: str, took_daemon: bool, *, rejection_error: str = "",
    ) -> "ECResult":
        """Record WHY the latest commit routed daemon-vs-batch (one of the fixed
        reason strings) and return the routing outcome. The reason is surfaced by
        ``append_block`` as an ``ec.routing`` audit event; the daemon-reject error
        (if any) travels inline in the result rather than via a side-channel attr.
        ``_last_routing_reason`` is kept as a Session attr for an external test
        reader (``test_ec_routing_characterization``)."""
        self._last_routing_reason = reason
        return ECResult(
            took_daemon=took_daemon, reason=reason, rejection_error=rejection_error,
        )

    def _try_daemon_path(self) -> "ECResult":
        """Replace the two ``_run_ec`` calls with a daemon round-trip
        when possible. Writes daemon's pre-commit goal raw to ``prev``
        and post-commit raw to ``curr`` so downstream diff / parsing /
        hooks run unchanged. Returns an ``ECResult``: ``took_daemon`` is True when
        the daemon handled the commit (accept OR reject), False when the caller
        must fall back to the batch subprocess; a daemon reject's EC error rides
        back inline in ``rejection_error``."""
        try:
            from core.easycrypt.daemon_backend import DaemonBackend, is_disabled, _split_tactics
        except Exception:
            return self._route("import_fail", False)
        if is_disabled():
            return self._route("disabled", False)
        fpath, lname = self._get_daemon_meta()
        if not fpath or not lname:
            return self._route("no_meta", False)
        try:
            fp = Path(fpath)
            if not fp.exists():
                return self._route("file_gone", False)
        except Exception:
            return self._route("file_gone", False)
        if self._daemon_backend is None:
            try:
                self._daemon_backend = DaemonBackend(self.dir, self._include_dirs)
            except Exception:
                return self._route("construct_fail", False)
        try:
            hist_text = self.history.read_text(encoding="utf-8")
        except Exception:
            return self._route("history_read_fail", False)
        tactics = _split_tactics(hist_text)
        if not tactics:
            return self._route("empty_tactics", False)
        # Pre-commit goal state for no-progress diffing. In subprocess
        # mode `_run_ec(prev_hist, prev)` recomputes it by re-running
        # EC on the history-minus-last-tactic. In daemon mode we can
        # skip that round-trip entirely: at the end of the PRIOR
        # append_block, ``self.prev`` was set to the prior ``self.curr``
        # (post-commit state), which is exactly the pre-commit state
        # for this tactic. For the first commit after start, ``self.prev``
        # is empty and ``self.curr`` holds the post-context state from
        # ``-start`` — use that.
        try:
            pre_bytes = self.prev.read_bytes() if self.prev.exists() else b""
            if not pre_bytes.strip() and self.curr.exists():
                pre_bytes = self.curr.read_bytes()
        except Exception:
            pre_bytes = b""
        try:
            result = self._daemon_backend.try_commit_latest(fp, lname, tactics)
        except Exception:
            return self._route("commit_exception", False)
        if result is None:
            return self._route("commit_none", False)
        # --- round-trip body delegated to ECBackend: it writes prev + the
        #     compressed post_raw to curr; on a daemon REJECT it rolls back via
        #     the journal, synthesizes the [error] line, and invalidates the
        #     daemon cache. The daemon HANDLE, the routing record, and the
        #     accept-path force-flush stay here on Session. ---
        outcome = self._ec_backend.commit_via_daemon(
            result=result,
            pre_bytes=pre_bytes,
            prev=self.prev,
            rollback=self._rollback,
            write_curr_compressed=self._write_curr_compressed,
            invalidate=self._invalidate_daemon,
        )
        if outcome.write_failed:
            return self._route("write_fail", False)
        if not outcome.accepted:
            self._last_commit_via_daemon = False
            return self._route(
                "daemon_reject", True, rejection_error=outcome.rejection_error,
            )
        # Force-flush: some tactic combos (e.g. `rewrite X; smt(...)` that
        # close one subgoal and transition goal type) leave EC's post-commit
        # output at just `[N|check]>` without a `Current goal` / `No more
        # goals` header. Probe the daemon for fresh state so the agent sees the
        # real current goal. ChaChaPoly step3 (2026-04-24): agent burned ~40s
        # in a qed/auto/trivial/smt loop because curr.out held `[380|check]>`
        # for three tactics before EC flushed. NOTE: the default-False read of
        # `accepted` here is intentional and ASYMMETRIC with the backend's
        # reject test (default-True) — preserved verbatim.
        try:
            if bool(result.get("accepted", False)):
                _state_after = self.read_state()
                if _state_after.num_remaining < 0:
                    fresh = self._daemon_backend.get_goal_raw()
                    if fresh:
                        # daemon's get_goal output includes a synthetic
                        # `locate Int.` echo plus the real state — compress
                        # to extract just the state section.
                        self._write_curr_compressed(fresh)
        except Exception:
            pass
        self._last_commit_via_daemon = bool(result.get("accepted", False))
        return self._route("daemon_accept", True)

    def _invalidate_daemon(self) -> None:
        """Close any daemon session associated with this session dir.
        Called on start and undo where EC state must be rebuilt."""
        self._last_commit_via_daemon = False
        if self._daemon_backend is not None:
            try:
                self._daemon_backend.invalidate()
            except Exception:
                pass
            self._daemon_backend = None
            return
        # Daemon may still hold a session even if this Session instance
        # was just constructed (fresh CLI invocation). Try lightweight
        # invalidate via a temporary backend so the close is issued.
        try:
            from core.easycrypt.daemon_backend import DaemonBackend
            DaemonBackend(self.dir, self._include_dirs).invalidate()
        except Exception:
            pass

    def try_speculative(self, tactic: str) -> str:
        """Run one or more tactics against the current daemon-backed
        session state WITHOUT committing any of them. Returns a
        human-readable report.

        Single-tactic input (one ``.``-terminated statement): uses
        ``daemon.try_tactic`` — fast, reports accepted + error (or
        goal_after).

        Multi-tactic input (two or more ``.``-terminated statements):
        uses ``daemon.try_chain`` — sends them in sequence within one
        ephemeral EC; stops at first failure. Reports per-step
        acceptance + final state. Use for verifying UNFOLD plans
        (``proc. call <pivot>. auto.``) without commit-and-rollback.

        Requires ``session_meta.json`` to have both ``file`` and
        ``lemma``. Committed history must replay cleanly (no failed
        tactics in it)."""
        try:
            from core.easycrypt.daemon_backend import DaemonBackend, _split_tactics, is_disabled
        except Exception as e:
            return (f"[TRY] error: daemon_backend import failed: {e}\n"
                    "       -try requires the EC daemon.\n")
        if is_disabled():
            return ("[TRY] EC_DAEMON_DISABLE is set; -try requires the daemon.\n"
                    "       Unset the env var and retry.\n")
        fpath, lname = self._get_daemon_meta()
        if not fpath or not lname:
            return ("[TRY] error: session_meta.json is missing file/lemma; "
                    "re-run `-start -f <file> -lemma <name>` first.\n"
                    "       -try is daemon-only and needs both to open a session.\n")
        fp = Path(fpath)
        if not fp.exists():
            return f"[TRY] error: file not found: {fpath}\n"

        if self._daemon_backend is None:
            self._daemon_backend = DaemonBackend(self.dir, self._include_dirs)
        try:
            hist_text = self.history.read_text(encoding="utf-8")
        except Exception:
            hist_text = ""
        tactics = _split_tactics(hist_text)

        if not self._daemon_backend._sync_to(fp, lname, tactics):
            detail = getattr(self._daemon_backend, "last_error", "") or "unknown"
            return ("[TRY] error: could not sync daemon to committed "
                    "history (daemon spawn / session open / replay failed). "
                    "If a committed tactic fails on replay, -try is "
                    "unavailable until that tactic is removed through the "
                    "manager undo control.\n"
                    f"[TRY] sync_detail: {detail}\n")
        cli = self._daemon_backend._ensure_daemon()
        if cli is None:
            return "[TRY] error: daemon connection lost.\n"

        # Split into 1+ tactics. _split_tactics handles ``.``-boundary
        # parsing (same function used for history.ec). If the caller
        # passes one tactic without a trailing dot, add one.
        raw_in = tactic.strip()
        if not raw_in:
            return "[TRY] error: empty tactic.\n"
        if not raw_in.endswith("."):
            raw_in = raw_in + "."
        tactic_list = [t.strip() for t in _split_tactics(raw_in) if t.strip()]
        if not tactic_list:
            return "[TRY] error: no parseable tactic (check the trailing '.').\n"

        # Snapshot the goal state BEFORE the speculative call so we can
        # run the same no-progress detection that ``append_block`` runs
        # on commit. Without this, ``-try`` would say "accepted" for a
        # tactic that a managed commit would auto-revert as no-effect — and the
        # agent would chase the inconsistency. See ``detect_no_progress``.
        try:
            prev_raw_for_progress = self.read_state().raw_current
        except Exception:
            prev_raw_for_progress = ""

        try:
            from core.easycrypt.ec_daemon_client import ECDaemonConnectionLost
        except Exception:  # pragma: no cover - import shim
            ECDaemonConnectionLost = ()  # type: ignore[assignment]

        def _run_probe(client: Any) -> tuple[str, Any]:
            if len(tactic_list) == 1:
                return "single", client.try_tactic(
                    self._daemon_backend._session_id, tactic_list[0])
            return "chain", client.try_chain(
                self._daemon_backend._session_id, tactic_list)

        verb = "try_tactic" if len(tactic_list) == 1 else "try_chain"
        try:
            kind, r = _run_probe(cli)
        except ECDaemonConnectionLost:
            # The daemon dropped the connection mid-probe — its EC subprocess
            # most likely crashed (a heavy smt/auto on a large goal). `-try` is
            # speculative (it never mutates committed state), so recovery is
            # safe: respawn a fresh daemon, replay the committed history, and
            # retry the probe ONCE. Bounding to a single retry avoids looping
            # when the tactic itself is what crashes EC.
            self._daemon_backend._force_fresh_daemon()
            if not self._daemon_backend._sync_to(fp, lname, tactics):
                return ("[TRY] error: the daemon dropped the connection "
                        "mid-probe and the session could not be re-synced. The "
                        "probe was NOT evaluated and the committed proof state "
                        "is unchanged — retry, or use a lighter tactic (the "
                        "goal may be too heavy for smt/auto).\n")
            cli = self._daemon_backend._ensure_daemon()
            if cli is None:
                return ("[TRY] error: the daemon dropped the connection "
                        "mid-probe and could not be respawned. The committed "
                        "proof state is unchanged.\n")
            try:
                kind, r = _run_probe(cli)
            except Exception:
                return ("[TRY] error: this tactic repeatedly drops the "
                        "EasyCrypt backend connection on the current goal (the "
                        "daemon crashed again after a fresh respawn + replay) — "
                        "it is almost certainly too heavy (e.g. a broad "
                        "smt/auto on a large goal). The probe was NOT evaluated "
                        "and the committed proof state is unchanged; try a "
                        "lighter or more targeted tactic.\n")
        except Exception as e:
            return f"[TRY] error: daemon {verb} failed: {e}\n"

        if kind == "single":
            return self._format_try_single(
                tactic_list[0], r, file_path=self._session_file_path(),
                prev_raw=prev_raw_for_progress,
            )
        return self._format_try_chain(
            tactic_list, r, file_path=self._session_file_path(),
            prev_raw=prev_raw_for_progress,
        )


    def _session_file_path(self) -> Optional[str]:
        """Return the target file path stored in this session's metadata."""
        try:
            meta_path = self.dir / "session_meta.json"
            if not meta_path.exists():
                return None
            with open(meta_path, "r") as f:
                data = json.load(f)
            fp = data.get("file")
            return fp if isinstance(fp, str) and fp else None
        except Exception:
            return None

    @staticmethod
    def _format_try_single(
        tactic: str, r: dict, file_path: Optional[str] = None,
        prev_raw: str = "",
    ) -> str:
        return format_try_single(tactic, r, file_path, prev_raw)

    @staticmethod
    def _format_try_chain(
        tactics: list, chain: dict, file_path: Optional[str] = None,
        prev_raw: str = "",
    ) -> str:
        return format_try_chain(tactics, chain, file_path, prev_raw)

    @staticmethod
    def _compress_current_state(text: str) -> str:
        return compress_current_state(text)

    def _write_curr_compressed(self, raw: bytes | str) -> None:
        """Write the compressed current state to ``self.curr``.

        Takes raw EC output (bytes or str), compresses to just the current
        state section via ``_compress_current_state``, and writes it. Used
        in place of ``self.curr.write_text(raw)`` / ``self.curr.write_bytes(raw)``
        everywhere the prior code dumped the full replay transcript.
        """
        if isinstance(raw, bytes):
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                # Binary-safe fallback — if decode fails, just write raw.
                self.curr.write_bytes(raw)
                return
        else:
            text = raw or ""
        self.curr.write_text(
            Session._compress_current_state(text), encoding="utf-8"
        )

    def _compress_curr_inplace(self) -> None:
        """Re-read ``self.curr`` and rewrite it with only the current state
        section. Use after subprocess-path ``_run_ec(_, self.curr)`` calls
        which dump the full EC transcript (including context-processing
        errors) to the file.
        """
        try:
            if not self.curr.exists():
                return
            raw = self.curr.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        try:
            self.curr.write_text(
                Session._compress_current_state(raw), encoding="utf-8"
            )
        except Exception:
            pass

    def start(self) -> dict:
        # Close any daemon session tied to this dir BEFORE we wipe the
        # dir (the state file is about to disappear under rmtree).
        self._invalidate_daemon()
        # Briefing: if the session already has committed tactics, save them
        # as a pre-restart checkpoint and return a report so the prover
        # (which IS going through with the restart — this is their call) can
        # replay the prefix if they change their mind, or at least knows
        # exactly what they discarded. Motivation: ChaChaPoly Run 4 step2_1
        # triggered -start as a "restart clean" move after transient
        # goal-info confusion, losing 28 committed tactics of real progress
        # silently. The prover should be able to restart, but also be
        # equipped to replay if they realize the restart was a mistake.
        committed_tactics: list[str] = []
        if self.dir.exists() and self.history.exists():
            try:
                committed_tactics = [
                    line.strip()
                    for line in self.history.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except Exception:
                committed_tactics = []

        # Save a pre-restart checkpoint before wiping — BEFORE shutil.rmtree
        # erases everything. Stored OUTSIDE the session dir so rmtree won't
        # eat it (parent-dir sibling file).
        pre_restart_path = None
        if committed_tactics:
            pre_restart_path = self.dir.parent / f"{self.dir.name}.pre_restart.txt"
            try:
                pre_restart_path.write_text(
                    "\n".join(committed_tactics) + "\n", encoding="utf-8"
                )
            except Exception:
                pre_restart_path = None

        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.keep.touch()
        # Fresh files
        self.context_file = self.dir / "context.ec"
        for p in [self.history, self.steps, self.curr, self.prev, self.delta, self.prev_hist, self.context_file]:
            if p:
                p.write_text("")
        self._include_file.write_text("\n".join(self._include_dirs) + "\n" if self._include_dirs else "")

        # Return briefing: number discarded, checkpoint path, ready-to-paste
        # replay chain. Lets the caller surface a clear restart-notice.
        briefing = {
            "discarded_tactic_count": len(committed_tactics),
            "pre_restart_checkpoint_path": (
                str(pre_restart_path) if pre_restart_path and pre_restart_path.exists() else None
            ),
            "replay_chain": (
                " ".join(committed_tactics) if committed_tactics else ""
            ),
        }
        return briefing

    def load_context(self, file_path: Path):
        """Store an .ec file as frozen context. It is prepended to every EC run
        but never touched by append_block/step_up."""
        self.context_file = self.dir / "context.ec"
        text = file_path.read_text(encoding="utf-8")
        self.context_file.write_text(text)
        self.emit_event("session.loaded_context", {
            "file": str(file_path.resolve()),
            "context_file": str(self.context_file.resolve()),
            "bytes": len(text.encode("utf-8")),
            "lines": len(text.splitlines()),
        })

    def _run_ec(self, input_path: Path, output_path: Path, include_dirs: list[str] | None = None):
        """Batch (spawn-per-call) EC execution. Thin delegate to ``ECBackend``;
        kept as a ``Session`` method because external callers (session_commands,
        proof replay and the undo path) and tests patch/call
        ``Session._run_ec`` directly."""
        self._ec_backend.run_batch(
            input_path, output_path, include_dirs or self._include_dirs,
        )

    @staticmethod
    def _count_lines(p: Path) -> int:
        try:
            return sum(1 for _ in p.open("rb"))
        except FileNotFoundError:
            return 0

    def _reconstruct_steps_if_missing(self):
        if self.steps.exists() and self.steps.stat().st_size > 0:
            return
        # Build steps.log by counting contiguous lines ending with '.' as a command boundary
        steps = []
        count = 0
        dot_re = re.compile(rb"\.[\t ]*$")
        with self.history.open("rb") as f:
            for line in f:
                count += 1
                if dot_re.search(line):
                    steps.append(count)
                    count = 0
        if count:
            steps.append(count)
        with self.steps.open("w", encoding="utf-8") as s:
            for n in steps:
                s.write(f"{n}\n")

    def append_block(self, block_text: str, deltas_only: bool = False) -> str:
        _pc = precheck_tactic(block_text, self.emit_event)
        if _pc.refusal is not None:
            return _pc.refusal
        block_text = _pc.block_text
        trimmed = _pc.trimmed  # downstream events/display/qed-detect use this form

        # Prepare previous history snapshot (before append)
        total_before = self._count_lines(self.history)
        self._rollback.snapshot_pre_commit(total_before)
        self.emit_event("tactic.submitted", {
            "tactic": block_text,
            "deltas_only": deltas_only,
            "history_lines_before": total_before,
            "line_count": len(block_text.splitlines()),
        })

        # Append block and record step length
        block_lines = block_text.splitlines()
        # Ensure trailing newline
        if not block_text.endswith("\n"):
            block_text += "\n"
        self.history.write_text(self.history.read_text() + block_text)
        with self.steps.open("a", encoding="utf-8") as s:
            s.write(f"{len(block_lines)}\n")
        # Run EC: prefer the daemon fast-path (persistent EC process,
        # ~50-100 ms per commit). Falls back to spawn-per-call
        # subprocesses on any daemon failure or when session_meta.json
        # lacks (file, lemma). Disable entirely with EC_DAEMON_DISABLE=1.
        _ec = self._try_daemon_path()
        took_daemon = _ec.took_daemon
        # Surface the daemon-vs-batch routing decision (and WHY) as an audit
        # event — previously a fully silent boolean (#3 Step 5, visibility).
        self.emit_event("ec.routing", {
            "backend": "daemon" if took_daemon else "batch",
            "reason": _ec.reason,
        })
        if not took_daemon:
            self._run_ec(self.prev_hist, self.prev)
            self._run_ec(self.history, self.curr)
            # Strip context-processing transcript from current.out so
            # agents reading the file see the current goal state, not a
            # noisy replay log. See `_compress_current_state` docstring.
            self._compress_curr_inplace()

        # ── Goal-state diff detection (ARCH-001) ──
        # Compare goal output (including hypotheses) before and after tactic.
        # If identical, the tactic was accepted but had no effect — the session
        # will auto-rollback (see below) to keep the invariant that
        # "committed history only contains state-changing tactics".
        # Note: `have _: X by tac.` with anonymous `_` genuinely produces no visible
        # change (EC discards the hypothesis). This is correctly flagged as NO_PROGRESS
        # since `have _` is a no-op. Use named hypotheses (`have H: ...`) instead.
        no_progress = False
        prev_raw = self.prev.read_text(encoding="utf-8", errors="replace")
        curr_raw = self.curr.read_text(encoding="utf-8", errors="replace")
        # Only check if there's no new error (errors change output even if goal unchanged).
        # Match EC's severity prefixes: [error, [critical, [fatal. Earlier we only
        # matched [error, which missed "[critical] nothing to rewrite" from conditional
        # rewrites with unmatched preconditions — those fell through to NO_PROGRESS and
        # got auto-committed as ghost tactics.
        _error_prefix_re = re.compile(r"^\s*\[(error|critical|fatal)")
        _prev_lines_set = set(prev_raw.splitlines())
        _curr_lines = curr_raw.splitlines()
        _new_error_lines = [
            ln.strip()
            for ln in _curr_lines
            if ln not in _prev_lines_set
            if _error_prefix_re.match(ln)
        ]
        has_new_error = any(
            _error_prefix_re.match(ln) for ln in _new_error_lines
        )
        # Daemon-side rejection delivers the error via instance state
        # rather than curr.out (writing it to curr would pollute next
        # commit's prev_raw and break downstream goal-substring checks).
        # Append the rejection error to curr_raw in memory for the typed
        # execution result, while leaving on-disk current.out untouched.
        rejection_err = _ec.rejection_error
        if rejection_err:
            has_new_error = True
            if rejection_err.strip():
                _new_error_lines.append(rejection_err.strip())
            curr_raw = curr_raw + "\n" + rejection_err + "\n"
        # Keep the rejection error around for the typed rejection display.
        _rejection_for_display = rejection_err
        # No-progress detection: shared with -try via Session.detect_no_progress
        # (single source of truth — see step3 Run 9 Tree-0.0 incident notes
        # in detect_no_progress' docstring).
        no_progress, _np_reason = detect_no_progress(
            prev_raw, curr_raw, has_new_error,
        )

        # ── Goal count tracking ──
        # Delegate EC prompt / close-marker parsing to session_state so
        # commit-time events and inspection tools agree on closed-proof
        # shapes such as `No more goals` → `+ added lemma` → prompt.
        try:
            from core.easycrypt.session_state import infer_goal_count  # type: ignore
            prev_count, _ = infer_goal_count(prev_raw)
            curr_count, no_more = infer_goal_count(curr_raw)
        except Exception:
            prev_count, _ = (-1, False)
            curr_count, no_more = (-1, False)

        display = []
        rollback_requested = False

        # Block-ends-with-qed signal: when the just-applied block ends with
        # `qed.` and EC accepted it without error, we treat the proof as
        # closed even when EC's response landed in async-check mode
        # ([N|check]> with no goal text). Without this, smt-heavy qed
        # closures (where EC delegates to why3 asynchronously) silently
        # fail the [ALL_GOALS_CLOSED] detection — the proof structure IS
        # closed but the SMT verification is pending. Source of truth for
        # SMT correctness is the post-extract full-file `easycrypt <file>`
        # check; we only need a reliable in-loop "the prover finished" signal.
        # Observed: step1 Run 8 (2026-04-27) — Tree-0.0 closed at 60:38
        # with `qed.`, but EC went to [365|check]> with no goal text.
        # goal-count inference returned (-1, False), no [ALL_GOALS_CLOSED]
        # emitted, no completion candidate was selected, and the orchestrator
        # never picked
        # the winner and let everyone run to 70min timeout. The 53-tactic
        # proof was correct (verified standalone) but discovered only by
        # the extraction-time history.ec scan, not the loop signal.
        _trim_lower = trimmed.lower().rstrip(".")
        _block_ends_with_qed = (
            _trim_lower.endswith("qed")
            or _trim_lower.endswith("qed;")
        )
        _async_check_close = (
            _block_ends_with_qed
            and not has_new_error
            and prev_count >= 1
            and curr_count == -1
        )

        # Accepted no-op tactics are reverted as a session invariant. This is
        # proof control, not compiler guidance, so it lives directly in the
        # commit transaction rather than in the retired hook/panel system.
        if no_progress and not has_new_error:
            rollback_requested = True
            self._apply_no_progress_rollback()

        try:
            history_lines_after = self._count_lines(self.history)
        except Exception:
            history_lines_after = total_before
        history_committed = history_lines_after > total_before
        event_no_more = bool(no_more)
        event_curr_count = curr_count
        candidate_closed = bool(
            (not has_new_error)
            and (event_no_more or _async_check_close or event_curr_count == 0)
        )
        if has_new_error:
            tactic_status = "error"
        elif rollback_requested:
            tactic_status = "no_progress_reverted"
        elif not history_committed:
            tactic_status = "not_committed"
        else:
            tactic_status = "ok"
        event_error_lines = _new_error_lines if tactic_status == "error" else []
        latest_error = event_error_lines[-1] if event_error_lines else ""
        self.emit_event("goal.changed", {
            "tactic": trimmed,
            "goals_before": prev_count,
            "goals_after": event_curr_count,
            "no_more_goals": event_no_more,
            "async_check_close": bool(_async_check_close),
            "no_progress": bool(no_progress),
            "no_progress_reason": _np_reason,
            "candidate_closed": candidate_closed,
        })
        self.emit_event("tactic.result", {
            "tactic": trimmed,
            "status": tactic_status,
            "goals_before": prev_count,
            "goals_after": event_curr_count,
            "has_new_error": bool(has_new_error),
            "no_progress": bool(no_progress),
            "no_progress_reason": _np_reason,
            "rollback_requested": rollback_requested,
            "history_committed": history_committed,
            "history_lines_before": total_before,
            "history_lines_after": history_lines_after,
            "candidate_closed": candidate_closed,
            "daemon_used": bool(getattr(self, "_last_commit_via_daemon", False)),
            "daemon_rejection": bool(_rejection_for_display),
            "error_lines": event_error_lines,
            "latest_error": latest_error,
        })
        if candidate_closed:
            self.emit_event("proof.candidate_closed", {
                "tactic": trimmed,
                "goals_before": prev_count,
                "goals_after": event_curr_count,
                "no_more_goals": event_no_more,
                "async_check_close": bool(_async_check_close),
            })

        if deltas_only:
            # Compute delta as the suffix of current after the longest common prefix
            prev_text = self.prev.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            curr_text = self.curr.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            lcp = 0
            max_lcp = min(len(prev_text), len(curr_text))
            while lcp < max_lcp and prev_text[lcp] == curr_text[lcp]:
                lcp += 1
            delta_text = "".join(curr_text[lcp:])
            # Trim anything printed after the last prompt to avoid trailing noise
            delta_text = _trim_after_last_prompt(delta_text)
            self.delta.write_text(delta_text)
            # Update prev snapshot to current for next calls
            self.prev.write_bytes(self.curr.read_bytes())
            display.append("Delta:\n")
            display.append(delta_text)
            return "".join(_reorder_display(display))
        else:
            # Extract the current state snippet from the shared state reader.
            state = self.read_state()
            snippet = (
                state.raw_for_goal_tools
                or state.active_output
                or state.raw_current
            )
            if snippet and not snippet.endswith("\n"):
                snippet += "\n"
            # Trim anything printed after the last prompt to avoid trailing noise
            snippet = _trim_after_last_prompt(snippet)
            self.delta.write_text(snippet)
            # Update prev snapshot to current for next calls
            self.prev.write_bytes(self.curr.read_bytes())
            display.append("State:\n")
            display.append(snippet)
            return "".join(_reorder_display(display))

    def read_state(self):
        """Return the structured current session state."""
        from core.easycrypt.session_state import read_session_state  # type: ignore
        return read_session_state(self.dir, self.curr, self.prev)

    def get_active_goal_output(self) -> str:
        """Return only the output from the last tactic (delta), not the full session.

        session.curr contains ALL output from processing context + history.
        This includes stale goals from context lemma proofs. The delta
        (curr minus prev) contains only the active goal from the last tactic.
        """
        return self.read_state().active_output

    def get_active_goal_block(self) -> tuple[str, int]:
        """Extract the active goal block and remaining count from session.curr.

        Uses the highest [N|check]> number to find the most recently created
        goal — this is always from the last tactic, never from stale context
        processing (which has low numbers like [11]).

        Returns (goal_text, n_remaining) where goal_text is the full block
        from "Current goal" to "[N|check]>" for the active goal.
        """
        if not self.curr.exists():
            return "", 0
        state = self.read_state()
        return state.active_goal_block, state.num_remaining

    def _empty_undo_result(self) -> UndoStepResult:
        msg = "No steps to undo.\n"
        self.delta.write_text(msg)
        self.emit_event("tactic.undone", {
            "status": "empty",
            "undone_tactic": "",
            "remaining_steps": 0,
        })
        return UndoStepResult(
            output=msg,
            status="empty",
            undone_tactic="",
            remaining_steps=0,
        )

    def step_up(self) -> UndoStepResult:
        self._reconstruct_steps_if_missing()
        if not self.steps.exists() or self.steps.stat().st_size == 0:
            return self._empty_undo_result()

        # Read steps and drop last entry
        with self.steps.open("r", encoding="utf-8") as s:
            entries = [int(x.strip()) for x in s if x.strip()]
        if not entries:
            return self._empty_undo_result()
        last = entries.pop()

        # Capture the text of the command being undone (last block)
        hist_lines = self.history.read_text(encoding="utf-8", errors="replace").splitlines()
        if last > 0 and hist_lines:
            block_lines = hist_lines[-last:]
        else:
            block_lines = []
        undone_block = "\n".join(block_lines) + ("\n" if block_lines else "")

        # Trim history by 'last' lines
        total = self._count_lines(self.history)
        keep = max(0, total - last)
        if keep == 0:
            self.history.write_text("")
        else:
            with self.history.open("rb") as hin, tempfile.NamedTemporaryFile(delete=False) as tmp:
                name = tmp.name
                for i, line in enumerate(hin, start=1):
                    if i > keep:
                        break
                    tmp.write(line)
            shutil.move(name, self.history)

        # Write back remaining steps
        with self.steps.open("w", encoding="utf-8") as s:
            for n in entries:
                s.write(f"{n}\n")

        # Determine the new last active command block (if any)
        now_last_cmd = ""
        if entries:
            now_len = entries[-1]
            lines_hist = self.history.read_text(encoding="utf-8", errors="replace").splitlines()
            if now_len > 0 and len(lines_hist) >= now_len:
                now_last_cmd = "\n".join(lines_hist[-now_len:]) + "\n"

        # Undo rewinds history; EC has no undo, so any daemon session
        # we own is now ahead of the authoritative history. Drop it so
        # the next commit will reopen+replay from the trimmed history.
        self._invalidate_daemon()
        # Run EC on new current history
        self._run_ec(self.history, self.curr)
        # Strip context-processing transcript from current.out so agents
        # reading the file see the current goal state, not the replay log.
        self._compress_curr_inplace()
        self.prev.write_bytes(self.curr.read_bytes())

        state = self.read_state()
        snippet = state.raw_for_goal_tools or state.active_output
        if not snippet:
            snippet = "\n".join(state.raw_current.splitlines()[-80:])
        if snippet and not snippet.endswith("\n"):
            snippet += "\n"
        # Trim anything printed after the last prompt to avoid trailing noise
        snippet = _trim_after_last_prompt(snippet)
        msg_parts = ["Command (undone):\n", undone_block]
        if now_last_cmd:
            msg_parts.extend(["Command (now last):\n", now_last_cmd])
        msg_parts.extend([
            "\n=== CURRENT GOAL (after undo) ===\n",
            snippet,
            "=== Read the goal above before choosing your next tactic. ===\n",
        ])
        msg = "".join(msg_parts)
        self.delta.write_text(msg)
        self.emit_event("tactic.undone", {
            "status": "ok",
            "undone_tactic": undone_block.strip(),
            "remaining_steps": len(entries),
            "history_lines_after": self._count_lines(self.history),
        })
        return UndoStepResult(
            output=msg,
            status="ok",
            undone_tactic=undone_block.strip(),
            remaining_steps=len(entries),
        )
