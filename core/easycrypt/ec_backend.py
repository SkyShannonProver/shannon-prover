"""EC commit execution results (and, eventually, the daemon/batch ECBackend).

Step 1 of the ECBackend extraction (part of the ``session_runtime.Session``
decomposition): this is the typed result that carries the daemon-vs-batch
routing outcome back to ``append_block`` — replacing the out-of-band
``Session._daemon_rejection_error`` instance attribute (a lazily-created side
channel set deep inside ``_try_daemon_path`` and read+cleared in
``append_block``).

The execution itself (``_try_daemon_path`` / ``_run_ec`` / the routing decision)
moves into a real ``ECBackend`` collaborator in a LATER phase — gated on
``SessionFileStore``, because the daemon-reject path is a transactional rollback
over the session dir's ``{history, steps, prev, curr, prev_hist}`` files and
cannot be cleanly lifted until that on-disk transaction has an owner.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.easycrypt.ec_proc import emacs_command, why3_socket_from_env
from core.easycrypt.session_common import get_ec_env

if TYPE_CHECKING:
    from core.easycrypt.session_rollback import RollbackJournal


@dataclass(frozen=True)
class ECResult:
    """Outcome of a single EC commit attempt.

    * ``took_daemon`` — the commit was handled by the daemon fast-path (whether
      ACCEPTED or REJECTED); ``False`` means ``append_block`` must fall back to
      the batch subprocess path.
    * ``reason`` — the fixed routing-reason string (one of the ``_route`` reasons,
      e.g. ``daemon_accept`` / ``daemon_reject`` / ``disabled`` / ``no_meta``);
      surfaced as the ``ec.routing`` audit event and pinned by
      ``test_ec_routing_characterization``.
    * ``rejection_error`` — the daemon's EC error text on a daemon REJECT (the
      ``[error]…`` line ``append_block`` ORs into ``has_new_error``); empty on
      accept / fallback. Travels inline here instead of via a side-channel attr.
    """
    took_daemon: bool
    reason: str
    rejection_error: str = ""


@dataclass(frozen=True)
class DaemonCommitOutcome:
    """Result of the daemon ROUND-TRIP body (post-RPC). Internal to the
    ECBackend<->Session boundary; ``Session._try_daemon_path`` collapses it back
    into an ``ECResult``.

    * ``accepted`` — daemon ACCEPTED the tactic. Read here with the REJECT test's
      default-True semantics: a missing ``accepted`` key counts as accepted for
      the reject decision. (Session reads the daemon-USED audit flag separately
      with default-False — the two are deliberately ASYMMETRIC and kept so.)
    * ``rejection_error`` — synthesized ``[error] …`` line on reject, "" on
      accept. Rides home inline; NEVER written into curr.out (invariant C).
    * ``write_failed`` — the prev/curr write raised. Kept as a FIELD (not an
      exception) so Session routes the distinct ``write_fail`` reason on this
      expected branch, exactly as the inline code did.
    """
    accepted: bool
    rejection_error: str = ""
    write_failed: bool = False


class ECBackend:
    """Batch (spawn-per-call) EasyCrypt execution.

    Step 2 of the Session -> ECBackend extraction: owns the ``run_batch`` path —
    a fresh ``easycrypt -emacs`` subprocess per call over (frozen ``context.ec``
    + the history/tactic input file). The daemon fast-path AND the
    daemon-vs-batch ROUTING move here in a later phase, gated on the eventual
    ``SessionFileStore`` (the daemon-reject path is a transactional rollback over
    the session dir's files). For now ``Session`` keeps a thin ``_run_ec``
    delegating shim so its external/test callers stay intact.
    """

    def __init__(self, session_dir: Path) -> None:
        self._dir = Path(session_dir)

    def run_batch(
        self, input_path: Path, output_path: Path, include_dirs: list,
    ) -> None:
        # Connect to the external why3server if available (avoids the sandbox
        # nice() issue); emacs_command adds -server only when the socket exists.
        cmd = emacs_command(include_dirs, why3_socket_from_env())
        # Build combined input: frozen context + history/tactic commands
        context_file = self._dir / "context.ec"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ec") as tmp:
            tmp_path = tmp.name
            if context_file.exists() and context_file.stat().st_size > 0:
                tmp.write(context_file.read_bytes())
                if not context_file.read_bytes().endswith(b"\n"):
                    tmp.write(b"\n")
            tmp.write(input_path.read_bytes())
        try:
            ec_env = get_ec_env()
            with open(tmp_path, "rb") as inp, output_path.open("wb") as out:
                try:
                    subprocess.run(cmd, stdin=inp, stdout=out, stderr=subprocess.STDOUT, check=False, env=ec_env)
                except FileNotFoundError:
                    raise RuntimeError("easycrypt not found on PATH; please install or adjust PATH.")
        finally:
            os.unlink(tmp_path)

    def commit_via_daemon(
        self,
        *,
        result: dict,
        pre_bytes: bytes,
        prev: Path,
        rollback: "RollbackJournal",
        write_curr_compressed: Callable[[str], None],
        invalidate: Callable[[], None],
    ) -> DaemonCommitOutcome:
        """The daemon round-trip BODY, run after Session has gated availability
        and called ``try_commit_latest`` (both STAY on Session — they own the
        shared daemon handle + 7 of the 8 routing reasons).

        Happy path: write the pre-state to ``prev`` and the daemon's compressed
        post_raw to ``curr`` (via the injected ``write_curr_compressed``). A write
        failure returns ``write_failed=True`` so Session routes ``write_fail`` and
        falls back to batch.

        Daemon REJECT: roll back the speculative append via ``rollback``
        (history<-prev.hist, pop steps, curr<-prev), synthesize the ``[error]``
        line from the daemon result, invalidate the daemon cache (EC has no undo),
        and return the error inline in ``rejection_error``. The reject branch
        writes ``curr`` ZERO times after the rollback — the error must NOT land in
        curr.out (invariant C; it would become the next commit's prev_raw).

        Post-condition (accept): ``curr`` holds the compressed post_raw before
        return, so Session's force-flush probe can read it back.
        """
        try:
            prev.write_bytes(pre_bytes)
            # Compress the daemon's raw EC output to just the current state
            # section (avoids leaking context-processing errors into curr).
            write_curr_compressed(result.get("post_raw", "") or "")
        except Exception:
            return DaemonCommitOutcome(accepted=False, write_failed=True)
        # Daemon-side rejection => roll back the speculative history append that
        # append_block did before calling us. Otherwise the rejected tactic sits
        # in history.ec and every subsequent daemon sync re-replays + re-fails,
        # silent to the agent (replay audit: a named call missing universal
        # params returned `[critical] cannot infer all placeholders`; keeping it
        # in history degenerated goal_type to `ambient`).
        if not bool(result.get("accepted", True)):
            _rejection = ""
            try:
                # The curr<-prev restore is load-bearing — see
                # RollbackJournal.restore_pre_commit (else the daemon post_raw
                # makes STATE-DIFF report a phony verdict=PROGRESS; 2026-04-29).
                rollback.restore_pre_commit()
                # Surface the daemon's error so has_new_error fires in
                # append_block. `raw` carries the full EC error line incl. the
                # lemma name — needed by [AUTO-SIG] which gates on
                # `name in new_err_text`; don't use `kind` (it strips that).
                err = result.get("error") or {}
                err_msg = ""
                if isinstance(err, dict):
                    err_msg = (err.get("raw")
                               or err.get("message")
                               or err.get("excerpt")
                               or "")
                if not err_msg:
                    raw = result.get("post_raw", "") or ""
                    for ln in raw.splitlines():
                        if re.match(r"^\s*\[(error|critical|fatal)", ln):
                            err_msg = ln.strip()
                            break
                # Do NOT write the error into curr.out: it would become the next
                # commit's prev_raw (Session syncs prev<-curr post-commit) and a
                # stale `[error] X` line pollutes downstream hooks like
                # explain_no_progress (substring-matches goal_raw for a named
                # procedure). Audit 2026-04-29: a dice reject left
                # `[error] unknown procedure: ChaCha.enc` in curr; the next
                # `inline ChaCha.enc.` got a bogus "appears in the goal" hint.
                # The error rides home in rejection_error instead.
                if err_msg:
                    if not err_msg.startswith("["):
                        err_msg = f"[error] {err_msg}"
                    _rejection = err_msg
                else:
                    _rejection = "[error] daemon rejection"
                invalidate()
            except Exception:
                pass
            return DaemonCommitOutcome(accepted=False, rejection_error=_rejection)
        return DaemonCommitOutcome(accepted=True)
