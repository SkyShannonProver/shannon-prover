"""Pre-commit file transaction for a managed EasyCrypt session.

Extracted from ``session_runtime.Session`` (a cut of the Session god-object
decomposition). ``append_block`` SPECULATIVELY appends the candidate tactic to
``history.ec`` and runs EC; the append must be undone in two cases — EC accepted
the tactic but it produced no goal change (no-progress auto-revert), or the
daemon REJECTED it. Both undo the SAME multi-file transaction, which was
previously DUPLICATED inline in ``Session._apply_no_progress_rollback`` and the
daemon-reject branch of ``Session._try_daemon_path``.

This owns that snapshot+restore over ``{history, steps, curr}``, keyed on
``prev.hist`` (the pre-append ``history`` snapshot) and ``prev.out`` (the
pre-tactic ``curr`` — which is ALSO the prior post-commit state; the two
meanings coincide by construction, so one file serves both). Daemon-cache
invalidation is deliberately NOT here: it is REPL lifecycle owned by the
Session, and each caller invalidates after restoring (EC has no undo).
"""
from __future__ import annotations

from pathlib import Path


class RollbackJournal:
    """Snapshot/restore of the speculative pre-commit append.

    Holds the session-dir Paths it transacts over. Those Paths are fixed for the
    life of a session (assigned once in ``Session.__init__``), so capturing them
    at construction is safe — only the file CONTENTS change between commits.
    """

    def __init__(
        self,
        history: Path,
        steps: Path,
        curr: Path,
        prev: Path,
        prev_hist: Path,
    ) -> None:
        self._history = history
        self._steps = steps
        self._curr = curr
        self._prev = prev
        self._prev_hist = prev_hist

    def snapshot_pre_commit(self, line_count: int) -> None:
        """Snapshot ``history.ec`` -> ``prev.hist`` before the speculative
        append, bounded to the first ``line_count`` lines (the bound guards
        against a concurrent append racing this read). ``prev.out`` is NOT
        snapshotted here — it already holds the prior post-commit state, which
        IS this commit's pre-tactic state.
        """
        if line_count <= 0:
            self._prev_hist.write_text("")
        else:
            with self._history.open("rb") as hin, self._prev_hist.open("wb") as pout:
                for i, line in enumerate(hin, start=1):
                    if i > line_count:
                        break
                    pout.write(line)

    def restore_pre_commit(self) -> None:
        """Undo the speculative append: ``history`` <- ``prev.hist``, pop the
        last ``steps.log`` line, ``curr`` <- ``prev``. Each guard mirrors the
        original inline rollback (a file that doesn't exist yet is skipped).

        The ``curr`` <- ``prev`` restore is load-bearing on the daemon-reject
        path: without it, the daemon's post_raw (mostly just the next prompt —
        error text gets stripped) makes STATE-DIFF compare a full ``prev``
        against a near-empty ``curr`` and report a PHONY ``verdict=PROGRESS`` —
        false progress that makes the agent believe a rejected tactic worked
        (reproduced 2026-04-29: a named call hitting "cannot infer all
        placeholders" emitted ``subgoals 5->1`` after the history rolled back).
        Hedged: this same curr<-prev / false-PROGRESS mechanism may also be what
        drove Run 13's ~12-min toxic loop, rather than the earlier fingerprint /
        regression framings. The caller invalidates the daemon afterward (EC has
        no undo).
        """
        if self._prev_hist.exists():
            self._history.write_bytes(self._prev_hist.read_bytes())
        if self._steps.exists():
            step_lines = self._steps.read_text(encoding="utf-8").splitlines()
            if step_lines:
                self._steps.write_text(
                    "\n".join(step_lines[:-1])
                    + ("\n" if step_lines[:-1] else "")
                )
        if self._prev.exists():
            self._curr.write_bytes(self._prev.read_bytes())
