#!/usr/bin/env python3
"""Runtime implementation for EasyCrypt proof sessions.

This module owns the concrete Session class and runtime helpers.
session_cli.py is kept as the argparse/dispatch entry point.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.easycrypt.session.session_common import (
    trim_after_last_prompt as _trim_after_last_prompt,
)
from core.easycrypt.session.session_display import (
    TryResult,
    compress_current_state,
    try_tool_error,
)

from core.easycrypt.session.session_no_progress import detect_no_progress  # no-progress detection (extracted)
from core.easycrypt.session.session_tactic_precheck import precheck_tactic  # tactic precheck (extracted)
from core.easycrypt.ec_backend import BatchBackend, CommitOutcome
from core.easycrypt.session.session_rollback import RollbackJournal  # pre-commit file txn (extracted)

from core.easycrypt.session.session_events import append_error_event as _append_error_event
from core.easycrypt.session.session_events import append_event as _append_event
from core.easycrypt.session.session_events import events_path as _events_path


@dataclass(frozen=True)
class UndoStepResult:
    """Concrete outcome of one requested history rewind.

    ``status`` is ``ok`` (history rewound), ``empty`` (nothing to undo) or
    ``unavailable`` (a multi-step rewind the daemon could not perform by
    ``undo``; nothing changed and ``reason`` says why, so the manager uses
    its restart+replay path). ``backend`` names how the state was rebuilt:
    ``daemon_undo`` or ``batch_replay``.
    """

    output: str
    status: str
    undone_tactic: str
    remaining_steps: int
    undone_count: int = 0
    backend: str = ""
    reason: str = ""

    @property
    def state_changed(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True)
class CommitResult:
    """Outcome of one ``append_block``, as its ``tactic.result`` event records it.

    ``status`` is ``ok``, ``error``, ``no_progress_reverted``,
    ``not_committed`` or ``refused``; only ``ok`` leaves the transaction in
    the journal. ``output`` is the state (or refusal) text shown for it.
    """

    status: str
    history_committed: bool
    latest_error: str
    no_progress_reason: str
    output: str


@dataclass(frozen=True)
class _Fallback:
    """Why the daemon did not judge a commit, so the batch backend must."""

    route: str
    detail: str = ""


def _exception_detail(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


class Session:
    def __init__(
        self,
        session_dir: Path,
        include_dirs: list[str] | None = None,
        *,
        batch: BatchBackend | None = None,
    ):
        self.dir = session_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._batch = batch or BatchBackend(self.dir)
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
        # to the batch backend on any failure. See daemon_backend.py.
        self._daemon_backend = None  # type: ignore[assignment]

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

    def _roll_back(self) -> None:
        """Undo the appended transaction: ``history.ec``, ``steps.log`` and
        ``current.out`` return to their pre-commit state.

        The daemon must then hold exactly the restored journal. A rejected
        transaction already left it there (the daemon undoes the sentences a
        rejected transaction ran); an accepted no-op is taken back with
        EasyCrypt's ``undo``. When neither can be shown the daemon session is
        dropped, and the next commit reopens and replays it; it is dropped
        even when the restore fails.
        """
        restored = False
        try:
            self._rollback.restore_pre_commit()
            restored = True
        finally:
            if not restored or self._daemon_undo_to_journal() is None:
                self._invalidate_daemon()

    def _journal_transactions(self) -> list[str] | None:
        """The committed transactions, or ``None`` when ``history.ec`` holds
        commands that ``steps.log`` cannot split into transactions (a rewind
        must not mistake an unreadable journal for an empty one)."""
        from core.easycrypt.committed_history import (
            read_committed_commands,
            read_committed_transactions,
        )

        try:
            transactions = read_committed_transactions(self.dir)
            if not transactions and read_committed_commands(self.dir):
                return None
        except Exception:
            return None
        return transactions

    def _daemon_for_meta(self):
        """``(DaemonBackend, file, lemma)`` when the session can use the
        daemon, else ``None``."""
        from core.easycrypt.daemon_backend import DaemonBackend, is_disabled

        if is_disabled():
            return None
        fpath, lname = self._get_daemon_meta()
        if not fpath or not lname or not Path(fpath).exists():
            return None
        if self._daemon_backend is None:
            self._daemon_backend = DaemonBackend(self.dir, self._include_dirs)
        return self._daemon_backend, Path(fpath), lname

    def _daemon_undo_to(
        self,
        transactions: list[str],
        *,
        require_open_goal: bool = False,
    ):
        """Bring the daemon back to ``transactions`` by ``undo`` only.

        Returns ``(DaemonRewind, "")`` when the daemon now holds exactly
        ``transactions``, else ``(None, reason)``. Never reopens or replays.
        """
        try:
            target = self._daemon_for_meta()
            if target is None:
                return None, "daemon unavailable for this session"
            backend, file_path, lemma = target
            reply = backend.rewind_to(
                file_path,
                lemma,
                list(transactions),
                require_open_goal=require_open_goal,
            )
        except Exception as exc:
            return None, _exception_detail(exc)
        if reply is None:
            return None, str(backend.last_error or "daemon rewind unavailable")
        return reply, ""

    def _daemon_undo_to_journal(self):
        transactions = self._journal_transactions()
        if transactions is None:
            return None
        return self._daemon_undo_to(transactions)[0]

    def _write_curr_from_daemon(self, raw: str) -> None:
        """Write the daemon's state reply as ``current.out``, re-printing the
        goal when the reply carries only a prompt (as after a commit)."""
        self._write_curr_compressed(raw)
        try:
            if self.read_state().num_remaining < 0 and self._daemon_backend:
                fresh = self._daemon_backend.get_goal_raw()
                if fresh:
                    self._write_curr_compressed(fresh)
        except Exception:
            pass

    def _pre_commit_bytes(self) -> bytes:
        """The state the journal's latest transaction starts from.

        The prior commit left its post-commit state in ``prev.out``
        (``_commit_display``); right after -start ``prev.out`` is empty and
        ``current.out`` holds the opened goal.
        """
        try:
            pre_bytes = self.prev.read_bytes() if self.prev.exists() else b""
            if not pre_bytes.strip() and self.curr.exists():
                pre_bytes = self.curr.read_bytes()
        except Exception:
            pre_bytes = b""
        return pre_bytes

    def _execute(self) -> CommitOutcome:
        """Have EasyCrypt judge the journal's latest transaction.

        The daemon judges it when it can; otherwise the batch backend replays
        the journal. The route is recorded as an ``ec.routing`` event before
        a batch run starts. Either way ``prev.out`` receives the pre-commit
        state, against which the session counts goals and detects no-ops.
        """
        pre_bytes = self._pre_commit_bytes()
        attempt = self._commit_on_daemon(pre_bytes)
        if isinstance(attempt, CommitOutcome):
            self._emit_routing("daemon", attempt.route)
            return attempt
        self._emit_routing("batch", attempt.route, attempt.detail)
        self.prev.write_bytes(pre_bytes)
        return self._batch.commit(
            history=self.history,
            curr=self.curr,
            include_dirs=self._include_dirs,
            route=attempt.route,
            detail=attempt.detail,
        )

    def _emit_routing(self, backend: str, route: str, detail: str = "") -> None:
        routing_event = {"backend": backend, "reason": route}
        if detail:
            routing_event["detail"] = detail[:400]
        self.emit_event("ec.routing", routing_event)

    def _commit_on_daemon(self, pre_bytes: bytes) -> CommitOutcome | _Fallback:
        """Commit the journal's latest transaction on the daemon.

        Writes ``pre_bytes`` to ``prev.out`` and the daemon's reply,
        compressed, to ``current.out``; a rejection is left for the caller to
        roll back. Returns the fallback route when the daemon cannot judge
        the commit.
        """
        try:
            from core.easycrypt.daemon_backend import DaemonBackend, is_disabled
            from core.easycrypt.committed_history import read_committed_transactions
        except Exception as exc:
            return _Fallback("import_fail", _exception_detail(exc))
        if is_disabled():
            return _Fallback("disabled")
        fpath, lname = self._get_daemon_meta()
        if not fpath or not lname:
            return _Fallback("no_meta")
        try:
            fp = Path(fpath)
            if not fp.exists():
                return _Fallback("file_gone")
        except Exception as exc:
            return _Fallback("file_gone", _exception_detail(exc))
        if self._daemon_backend is None:
            try:
                self._daemon_backend = DaemonBackend(self.dir, self._include_dirs)
            except Exception as exc:
                return _Fallback("construct_fail", _exception_detail(exc))
        try:
            tactics = read_committed_transactions(self.dir)
        except Exception as exc:
            return _Fallback("history_read_fail", _exception_detail(exc))
        # steps.log, not command splitting, owns the atomic submission. Splitting
        # the new block makes its first commands look like already accepted
        # history and can turn a native rejection into a batch fallback.
        if not tactics:
            return _Fallback("empty_tactics")
        try:
            reply = self._daemon_backend.commit_latest(fp, lname, tactics)
        except Exception as exc:
            return _Fallback("commit_exception", _exception_detail(exc))
        finally:
            self._emit_daemon_unavailable()
        if reply is None:
            return _Fallback(
                "commit_none",
                str(getattr(self._daemon_backend, "last_error", "") or ""),
            )
        try:
            self.prev.write_bytes(pre_bytes)
            # Keep only the current state section of the daemon's output
            # (avoids leaking context-processing errors into curr). A
            # rejection's error stays out of current.out: it would become
            # the next commit's prev.out.
            self._write_curr_compressed(reply.post_raw)
        except Exception:
            return _Fallback("write_fail")
        if not reply.accepted:
            return CommitOutcome("daemon", "daemon_reject", reply.error)
        # Force-flush: some tactic combos (e.g. `rewrite X; smt(...)` that
        # close one subgoal and transition goal type) leave EC's post-commit
        # output at just `[N|check]>` without a `Current goal` / `No more
        # goals` header. Probe the daemon for fresh state so the agent sees the
        # real current goal.
        try:
            if self.read_state().num_remaining < 0:
                fresh = self._daemon_backend.get_goal_raw()
                if fresh:
                    # daemon's get_goal output includes a synthetic
                    # `locate Int.` echo plus the real state — compress
                    # to extract just the state section.
                    self._write_curr_compressed(fresh)
        except Exception:
            pass
        return CommitOutcome("daemon", "daemon_accept")

    def _emit_daemon_unavailable(self) -> None:
        """Record each daemon failure the backend just started to skip the
        daemon for."""
        notices = getattr(self._daemon_backend, "unavailable_notices", None)
        if not notices:
            return
        for notice in list(notices):
            self.emit_event("ec.daemon_unavailable", notice)
        notices.clear()

    def _invalidate_daemon(self) -> None:
        """Close any daemon session associated with this session dir.
        Called on start, and when an undo or rollback could not be mirrored
        on the daemon by ``undo``, so the next commit reopens and replays."""
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

    def try_speculative(self, tactic: str) -> TryResult:
        """Check one or more tactics against the committed state WITHOUT
        committing any of them.

        One ``.``-terminated statement runs as the daemon's ``try_tactic``
        and is also checked for progress, as a commit would be. Several run
        in sequence as ``try_chain``, which stops at the first failure; use it
        for multi-step plans (``proc. call <pivot>. auto.``) without
        commit-and-rollback.

        Requires ``session_meta.json`` to have both ``file`` and
        ``lemma``. Committed history must replay cleanly (no failed
        tactics in it)."""
        try:
            from core.easycrypt.daemon_backend import DaemonBackend, is_disabled
            from core.easycrypt.committed_history import read_committed_transactions
        except Exception as e:
            return try_tool_error(
                tactic,
                f"[TRY] error: daemon_backend import failed: {e}\n"
                "       -try requires the EC daemon.\n",
            )
        if is_disabled():
            return TryResult(
                tactic=tactic.strip(),
                report=("[TRY] EC_DAEMON_DISABLE is set; -try requires the daemon.\n"
                        "       Unset the env var and retry.\n"),
            )
        fpath, lname = self._get_daemon_meta()
        if not fpath or not lname:
            return try_tool_error(
                tactic,
                "[TRY] error: session_meta.json is missing file/lemma; "
                "re-run `-start -f <file> -lemma <name>` first.\n"
                "       -try is daemon-only and needs both to open a session.\n",
            )
        fp = Path(fpath)
        if not fp.exists():
            return try_tool_error(tactic, f"[TRY] error: file not found: {fpath}\n")

        if self._daemon_backend is None:
            self._daemon_backend = DaemonBackend(self.dir, self._include_dirs)
        committed = read_committed_transactions(self.dir)
        try:
            prev_raw = self.read_state().raw_current
        except Exception:
            prev_raw = ""
        try:
            return self._daemon_backend.try_tactics(
                fp, lname, committed, tactic, prev_raw,
            )
        finally:
            self._emit_daemon_unavailable()

    def _write_curr_compressed(self, raw: bytes | str) -> None:
        """Write the compressed current state to ``self.curr``.

        Takes raw EC output (bytes or str), compresses to just the current
        state section via ``compress_current_state``, and writes it. Used
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
        self.curr.write_text(compress_current_state(text), encoding="utf-8")

    def _compress_curr_inplace(self) -> None:
        """Re-read ``self.curr`` and rewrite it with only the current state
        section. Use after a batch run, which dumps the full EC transcript
        (including context-processing output) to the file.
        """
        try:
            if not self.curr.exists():
                return
            raw = self.curr.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        try:
            self.curr.write_text(compress_current_state(raw), encoding="utf-8")
        except Exception:
            pass

    def replay_current(self) -> None:
        """Replay the journal in a fresh EasyCrypt and keep its latest state
        in ``current.out``."""
        self._batch.run(self.history, self.curr, self._include_dirs)
        self._compress_curr_inplace()

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
        # One entry per EasyCrypt command, not per physical line: a command
        # may span lines and one line may hold several commands.
        from core.easycrypt.committed_history import read_committed_tactics

        committed_tactics = read_committed_tactics(self.dir)

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

    def append_block(self, block_text: str, deltas_only: bool = False) -> CommitResult:
        """Commit one tactic transaction: precheck it, append it to the
        journal, have EasyCrypt judge it, roll back a rejection or an
        accepted no-op, and record the transition."""
        precheck = precheck_tactic(block_text, self.emit_event)
        if precheck.refusal is not None:
            return CommitResult("refused", False, "", "", precheck.refusal)
        block_text = precheck.block_text
        trimmed = precheck.trimmed  # downstream events/display/qed-detect use this form

        total_before = self._count_lines(self.history)
        self._rollback.snapshot_pre_commit(total_before)
        self.emit_event("tactic.submitted", {
            "tactic": block_text,
            "deltas_only": deltas_only,
            "history_lines_before": total_before,
            "line_count": len(block_text.splitlines()),
        })
        block_lines = block_text.splitlines()
        if not block_text.endswith("\n"):
            block_text += "\n"
        self.history.write_text(self.history.read_text() + block_text)
        with self.steps.open("a", encoding="utf-8") as s:
            s.write(f"{len(block_lines)}\n")

        outcome = self._execute()
        if not outcome.accepted:
            self._roll_back()
        if outcome.backend == "batch":
            # A batch run prints the whole replay. Keep the latest state only,
            # also when the rollback copied that replay back from prev.out.
            self._compress_curr_inplace()

        prev_raw = self.prev.read_text(encoding="utf-8", errors="replace")
        curr_raw = self.curr.read_text(encoding="utf-8", errors="replace")
        has_new_error = not outcome.accepted
        error_lines: list[str] = []
        if has_new_error:
            if outcome.error.strip():
                error_lines.append(outcome.error.strip())
            # Goal counting reads the rejection after the restored state, as
            # it appears in the transition record.
            curr_raw = curr_raw + "\n" + outcome.error + "\n"
        # An accepted tactic that leaves the goal unchanged is reverted, so
        # committed history only contains state-changing tactics. `have _: X
        # by tac.` with an anonymous `_` is such a no-op: EC discards it.
        no_progress, no_progress_reason = detect_no_progress(
            prev_raw, curr_raw, has_new_error,
        )

        # Delegate EC prompt / close-marker parsing to session_state so
        # commit-time events and inspection tools agree on closed-proof
        # shapes such as `No more goals` → `+ added lemma` → prompt.
        try:
            from core.easycrypt.session.session_state import infer_goal_count  # type: ignore
            prev_count, _ = infer_goal_count(prev_raw)
            curr_count, no_more = infer_goal_count(curr_raw)
        except Exception:
            prev_count, _ = (-1, False)
            curr_count, no_more = (-1, False)

        # An accepted `qed.` whose reply is only an async-check prompt
        # (`[N|check]>` with no goal text, while why3 finishes the SMT calls)
        # still closes the proof. Offline verification of the extracted proof
        # remains the authority for SMT correctness; this is only the in-loop
        # signal that the prover finished.
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

        if no_progress:
            self._roll_back()

        try:
            history_lines_after = self._count_lines(self.history)
        except Exception:
            history_lines_after = total_before
        history_committed = history_lines_after > total_before
        event_no_more = bool(no_more)
        candidate_closed = bool(
            (not has_new_error)
            and (event_no_more or _async_check_close or curr_count == 0)
        )
        if has_new_error:
            tactic_status = "error"
        elif no_progress:
            tactic_status = "no_progress_reverted"
        elif not history_committed:
            tactic_status = "not_committed"
        else:
            tactic_status = "ok"
        latest_error = error_lines[-1] if error_lines else ""
        self.emit_event("goal.changed", {
            "tactic": trimmed,
            "goals_before": prev_count,
            "goals_after": curr_count,
            "no_more_goals": event_no_more,
            "async_check_close": bool(_async_check_close),
            "no_progress": bool(no_progress),
            "no_progress_reason": no_progress_reason,
            "candidate_closed": candidate_closed,
        })
        self.emit_event("tactic.result", {
            "tactic": trimmed,
            "status": tactic_status,
            "goals_before": prev_count,
            "goals_after": curr_count,
            "has_new_error": bool(has_new_error),
            "no_progress": bool(no_progress),
            "no_progress_reason": no_progress_reason,
            "rollback_requested": bool(no_progress),
            "history_committed": history_committed,
            "history_lines_before": total_before,
            "history_lines_after": history_lines_after,
            "candidate_closed": candidate_closed,
            "daemon_used": (
                outcome.backend == "daemon" and outcome.accepted and not no_progress
            ),
            "daemon_rejection": has_new_error,
            "error_lines": error_lines,
            "latest_error": latest_error,
        })
        if candidate_closed:
            self.emit_event("proof.candidate_closed", {
                "tactic": trimmed,
                "goals_before": prev_count,
                "goals_after": curr_count,
                "no_more_goals": event_no_more,
                "async_check_close": bool(_async_check_close),
            })
        return CommitResult(
            status=tactic_status,
            history_committed=history_committed,
            latest_error=latest_error,
            no_progress_reason=no_progress_reason,
            output=self._commit_display(deltas_only),
        )

    def _commit_display(self, deltas_only: bool) -> str:
        """Record and return the text shown for a commit, then make the
        post-commit state the next commit's pre-commit state."""
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
            self.prev.write_bytes(self.curr.read_bytes())
            return "Delta:\n" + delta_text
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
        self.prev.write_bytes(self.curr.read_bytes())
        return "State:\n" + snippet


    def read_state(self):
        """Return the structured current session state."""
        from core.easycrypt.session.session_state import read_session_state  # type: ignore
        return read_session_state(self.dir, self.curr, self.prev)

    def _empty_undo_result(self, remaining: int = 0) -> UndoStepResult:
        msg = "No steps to undo.\n"
        self.delta.write_text(msg)
        self.emit_event("tactic.undone", {
            "status": "empty",
            "undone_tactic": "",
            "remaining_steps": remaining,
        })
        return UndoStepResult(
            output=msg,
            status="empty",
            undone_tactic="",
            remaining_steps=remaining,
        )

    def step_up(self) -> UndoStepResult:
        """Undo the latest committed transaction.

        The daemon takes it back with EasyCrypt's ``undo <level>.`` and its
        reply becomes ``current.out``. When the daemon cannot (no live
        session in step with the journal, or the transaction ran a command
        ``undo`` does not revert), the daemon session is dropped and the
        trimmed journal is replayed in a fresh EasyCrypt instead.
        """
        self._reconstruct_steps_if_missing()
        if not self.steps.exists() or self.steps.stat().st_size == 0:
            return self._empty_undo_result()

        # Read steps and drop last entry
        with self.steps.open("r", encoding="utf-8") as s:
            entries = [int(x.strip()) for x in s if x.strip()]
        if not entries:
            return self._empty_undo_result()
        transactions = self._journal_transactions()
        daemon_reply = None
        if transactions is not None and len(transactions) == len(entries):
            daemon_reply, _reason = self._daemon_undo_to(transactions[:-1])
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

        if daemon_reply is not None and daemon_reply.undone == 1 and daemon_reply.post_raw:
            backend = "daemon_undo"
            self._write_curr_from_daemon(daemon_reply.post_raw)
        else:
            # The daemon could not mirror the undo: drop its session so the
            # next commit reopens and replays the trimmed history.
            backend = "batch_replay"
            self._invalidate_daemon()
            self.replay_current()
        self.prev.write_bytes(self.curr.read_bytes())
        msg = self._undo_message(undone_block, now_last_cmd)
        self.emit_event("tactic.undone", {
            "status": "ok",
            "undone_tactic": undone_block.strip(),
            "remaining_steps": len(entries),
            "history_lines_after": self._count_lines(self.history),
            "undone_count": 1,
            "backend": backend,
        })
        return UndoStepResult(
            output=msg,
            status="ok",
            undone_tactic=undone_block.strip(),
            remaining_steps=len(entries),
            undone_count=1,
            backend=backend,
        )

    def _undo_message(self, undone_block: str, now_last_cmd: str) -> str:
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
        return msg

    def rewind_to_command_count(self, keep_commands: int) -> UndoStepResult:
        """Rewind the journal to its first ``keep_commands`` commands by
        undoing the daemon's committed process, in one EasyCrypt command.

        This is the manager's checkpoint rewind (and the rewind half of
        restore and amend). It changes nothing and reports ``unavailable``
        unless ``keep_commands`` ends a committed transaction and the daemon
        holds the journal and can undo every dropped transaction; the manager
        then restarts and replays instead. Kept transactions are not re-run.
        """
        transactions = self._journal_transactions()
        if transactions is None:
            return self._unavailable_undo_result("committed journal unreadable", 0)
        commands_so_far = 0
        boundaries = {0: 0}
        from core.easycrypt.committed_history import flatten_committed_transactions

        for index, transaction in enumerate(transactions, start=1):
            commands_so_far += len(flatten_committed_transactions([transaction]))
            boundaries[commands_so_far] = index
        if keep_commands == commands_so_far:
            return self._empty_undo_result(remaining=len(transactions))
        if keep_commands < 0 or keep_commands > commands_so_far:
            return self._unavailable_undo_result(
                f"keep_commands {keep_commands} outside 0..{commands_so_far}",
                len(transactions),
            )
        keep = boundaries.get(keep_commands)
        if keep is None:
            return self._unavailable_undo_result(
                f"command {keep_commands} does not end a committed transaction",
                len(transactions),
            )
        try:
            entries = [
                int(x.strip())
                for x in self.steps.read_text(encoding="utf-8").splitlines()
                if x.strip()
            ]
            lines = self.history.read_text(encoding="utf-8").splitlines(keepends=True)
        except (OSError, ValueError) as exc:
            return self._unavailable_undo_result(
                f"journal unreadable: {_exception_detail(exc)}", len(transactions)
            )
        if len(entries) != len(transactions) or sum(entries) != len(lines):
            return self._unavailable_undo_result(
                "steps.log does not split history.ec", len(transactions)
            )
        from core.easycrypt.proof_text import undo_unsafe_sentence

        # The daemon refuses to undo across such a command; one in the kept
        # prefix is refused here too, because restart+replay re-commits that
        # prefix command by command, where a lone ``pragma`` is reverted as a
        # no-op. Falling back keeps this rewind identical to that path.
        unsafe = next(
            (found for found in map(undo_unsafe_sentence, transactions) if found),
            "",
        )
        if unsafe:
            return self._unavailable_undo_result(
                f"journal contains `{unsafe[:80]}`, which undo cannot revert",
                len(transactions),
            )
        # The target must show an open goal: a rewind to a goals-closed state
        # emits ``tactic.undone`` where restart+replay re-emits the closing
        # commit's close events, which a later ``qed`` needs as authority.
        reply, reason = self._daemon_undo_to(
            transactions[:keep], require_open_goal=True,
        )
        if reply is None or reply.undone != len(transactions) - keep or not reply.post_raw:
            return self._unavailable_undo_result(
                reason or "daemon did not undo the requested transactions",
                len(transactions),
            )
        kept_lines = sum(entries[:keep])
        self.history.write_text("".join(lines[:kept_lines]), encoding="utf-8")
        self.steps.write_text(
            "".join(f"{n}\n" for n in entries[:keep]), encoding="utf-8"
        )
        self._write_curr_from_daemon(reply.post_raw)
        self.prev.write_bytes(self.curr.read_bytes())
        undone_block = "\n".join(transactions[keep:]) + "\n"
        now_last_cmd = transactions[keep - 1] + "\n" if keep else ""
        msg = self._undo_message(undone_block, now_last_cmd)
        self.emit_event("tactic.undone", {
            "status": "ok",
            "undone_tactic": undone_block.strip(),
            "remaining_steps": keep,
            "history_lines_after": self._count_lines(self.history),
            "undone_count": len(transactions) - keep,
            "backend": "daemon_undo",
        })
        return UndoStepResult(
            output=msg,
            status="ok",
            undone_tactic=undone_block.strip(),
            remaining_steps=keep,
            undone_count=len(transactions) - keep,
            backend="daemon_undo",
        )

    def _unavailable_undo_result(self, reason: str, remaining: int) -> UndoStepResult:
        msg = f"Rewind by undo unavailable: {reason}\n"
        self.emit_event("tactic.undone", {
            "status": "unavailable",
            "undone_tactic": "",
            "remaining_steps": remaining,
            "reason": reason[:400],
        })
        return UndoStepResult(
            output=msg,
            status="unavailable",
            undone_tactic="",
            remaining_steps=remaining,
            reason=reason,
        )
