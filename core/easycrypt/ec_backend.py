"""EasyCrypt execution of one managed commit.

``Session.append_block`` appends a transaction to the session journal and asks
EasyCrypt to judge it, on the daemon when it can take the commit and otherwise
with ``BatchBackend``, which replays the whole journal in a fresh process.
Either way the result is a ``CommitOutcome``; the session decides from it what
to roll back and record.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.easycrypt.ec_diagnostics import error_text
from core.easycrypt.ec_proc import emacs_command, why3_socket_from_env
from core.easycrypt.ec_env import get_ec_env

# A batch run still going after this long is killed and reported as an error;
# -verify gives a whole compile the same bound.
BATCH_TIMEOUT_SECONDS = 600.0


@dataclass(frozen=True)
class CommitOutcome:
    """EasyCrypt's verdict on one appended transaction, and where it ran.

    ``backend`` is ``"daemon"`` or ``"batch"`` and ``route`` says why that
    backend ran (the ``ec.routing`` reason); ``detail`` names the failure
    behind a batch fallback. ``error`` is EasyCrypt's rejection, empty when
    it accepted the transaction. ``prev.out`` holds the state before the
    transaction and ``current.out`` the output of the backend that ran.
    """

    backend: str
    route: str
    error: str = ""
    detail: str = ""

    @property
    def accepted(self) -> bool:
        return not self.error


class BatchBackend:
    """Spawn-per-call EasyCrypt over the frozen ``context.ec`` of a session.

    ``run`` feeds context plus one input file to a fresh ``easycrypt -emacs``
    and writes everything it prints to ``output_path``.
    """

    def __init__(self, session_dir: Path) -> None:
        self._dir = Path(session_dir)

    def run(
        self, input_path: Path, output_path: Path, include_dirs: list,
        timeout: float = BATCH_TIMEOUT_SECONDS,
    ) -> int:
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
            # EC writes to an unlinked scratch file that is copied to
            # output_path only once it has exited. If this process is killed
            # first (the manager's own timeout), the orphaned EC can never
            # write into a session file that a later command has rewritten.
            with open(tmp_path, "rb") as inp, tempfile.TemporaryFile() as scratch:
                try:
                    proc = subprocess.Popen(
                        cmd, stdin=inp, stdout=scratch,
                        stderr=subprocess.STDOUT, env=ec_env,
                    )
                except FileNotFoundError:
                    raise RuntimeError("easycrypt not found on PATH; please install or adjust PATH.")
                timed_out = False
                try:
                    returncode = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    returncode = proc.wait()
                    timed_out = True
                except BaseException:
                    proc.kill()
                    proc.wait()
                    raise
                scratch.seek(0)
                output = scratch.read()
            if timed_out:
                output += (
                    f"\n[error] EasyCrypt batch run timed out after {timeout:g}s\n"
                ).encode("utf-8")
            output_path.write_bytes(output)
            return returncode
        finally:
            os.unlink(tmp_path)

    def commit(
        self,
        *,
        history: Path,
        curr: Path,
        include_dirs: list,
        route: str,
        detail: str = "",
    ) -> CommitOutcome:
        """Replay the journal, its latest transaction included, into ``curr``.

        The session already holds the state before the transaction, so one
        run is enough. EasyCrypt in ``-emacs`` mode continues after an error
        and may print a later goal or closure, so the verdict comes from the
        whole replay rather than the state it ends in.
        """
        returncode = self.run(history, curr, include_dirs)
        errors = []
        diagnostic = error_text(curr.read_text(encoding="utf-8", errors="replace"))
        if diagnostic:
            errors.append(diagnostic)
        if returncode:
            errors.append(f"[error] EasyCrypt batch exited with status {returncode}")
        return CommitOutcome("batch", route, "\n".join(errors), detail)
