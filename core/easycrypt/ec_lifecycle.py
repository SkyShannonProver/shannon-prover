"""Single owner of the EasyCrypt ``-emacs`` pipe-process lifecycle (#3 step 3).

One sequence — ``spawn -> drain banner -> send/read-until-prompt -> replay
prefix -> bounded teardown`` — shared by every EC process the daemon runs:

  * the persistent committed process (``ECSubprocess``),
  * the spawn-fresh ephemeral speculative probes (``_try_tactic_fresh`` /
    ``_try_chain_fresh``),
  * the warm run-then-``undo`` prober (``WarmProber``).

Each of those adds only its own proof/probe semantics on top of this base; the
spawn argv, banner drain, prompt reader, command send, replay loop and the
bounded (give-up-not-block) teardown all live here, in one place. The argv
itself is owned by ``ec_proc.spawn_emacs_pipe``; the bounded-wait teardown
discipline (audit §8 #6) and the why3-socket pass-through are preserved exactly.
"""
from __future__ import annotations

import logging
import os
import select
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

from core.easycrypt.ec_prompt import PROMPT_BYTES_RE
from core.easycrypt.ec_proc import spawn_emacs_pipe
from core.easycrypt.proof_text import split_ec_commands, strip_comments

logger = logging.getLogger("ec_lifecycle")

class ECProtocolDesync(RuntimeError):
    """The EC pipe can no longer pair a command with its own reply.

    Raised for every use of a process after a read timed out, the process
    closed its output or exited, a write failed, or a reply was left unread.
    The late or extra prompt is still in the pipe, so the next read would
    return the previous command's reply. The only recovery is a new process.
    """


@dataclass
class ReplayFail:
    """First setup or committed block rejected while replaying into fresh EC."""

    setup_cmd: str
    err: dict
    raw: str


class ECSessionLifecycle:
    """Owns one ``easycrypt -emacs`` subprocess's pipe lifecycle.

    Subclasses add proof/probe semantics; the per-strategy knobs are the class
    attributes below (``_label`` for diagnostics, ``_teardown_grace`` for the
    SIGTERM->SIGKILL wait budget) plus ``_resolve_env`` (how to obtain the spawn
    environment). The reader preserves ``self._buffer`` across reads — correct
    for the persistent process and equivalent for ephemerals (which read exactly
    one prompt per send, so no bytes are ever left buffered).

    Any failed read or write leaves the process desynchronized: it refuses
    further I/O with ``ECProtocolDesync`` until it is respawned, and the owner
    must replace it (``desynchronized`` reports this)."""

    _label = "EC"
    _drain_timeout = 30.0
    _teardown_grace = 3.0
    _RESPONSE_TIMEOUT_DEFAULT = 60.0

    def __init__(self, include_dirs, why3_socket: Optional[str] = None, env=None):
        self.include_dirs = list(include_dirs)
        self.why3_socket = why3_socket
        self._env = env
        self.proc: Optional[subprocess.Popen] = None
        self._buffer = b""
        self._desync: Optional[str] = None

    # -- spawn environment -----------------------------------------------------
    def _resolve_env(self):
        if self._env is not None:
            return self._env
        from core.easycrypt.ec_env import get_ec_env

        return get_ec_env()

    # -- spawn + banner drain ---------------------------------------------------
    def spawn(self) -> None:
        """Start the EC subprocess (unified argv via ``ec_proc``) and drain the
        startup banner up to the first prompt. ``why3_socket`` is passed through
        unchanged — never re-defaulted — so concurrent arms never share a socket.
        """
        self._buffer = b""
        self._desync = None
        self.proc = spawn_emacs_pipe(
            self.include_dirs, self.why3_socket, env=self._resolve_env(),
        )
        self._read_until_prompt(timeout=self._drain_timeout)

    # -- synchronization --------------------------------------------------------
    @property
    def desynchronized(self) -> bool:
        return self._desync is not None

    def _mark_desynchronized(self, reason: str) -> None:
        if self._desync is None:
            self._desync = reason
            logger.warning("%s pipe desynchronized: %s", self._label, reason)

    def _require_synchronized(self) -> None:
        if self._desync is not None:
            raise ECProtocolDesync(
                f"{self._label} pipe is out of step with its commands "
                f"({self._desync}); the process must be replaced"
            )

    def interrupt(self) -> None:
        """Kill the EC process but keep the handle, so a reader blocked on the
        pipe in another thread sees end-of-file and returns; the owner still
        tears the process down."""
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass

    # -- I/O primitives ---------------------------------------------------------
    def _read_until_prompt(self, timeout: float = _RESPONSE_TIMEOUT_DEFAULT) -> bytes:
        """Read stdout until a ``[N|mode]>`` prompt; return the block since the
        previous prompt. Buffer-preserving: any bytes past the prompt stay in
        ``self._buffer`` for the next read. A failed read desynchronizes the
        process: the reply it missed may still arrive."""
        self._require_synchronized()
        try:
            return self._read_prompt_block(timeout)
        except BaseException as exc:
            self._mark_desynchronized(f"read failed: {type(exc).__name__}: {exc}")
            raise

    def _read_prompt_block(self, timeout: float) -> bytes:
        assert self.proc is not None and self.proc.stdout is not None
        deadline = time.monotonic() + timeout
        out = bytearray()
        fileno = self.proc.stdout.fileno()
        while True:
            m = PROMPT_BYTES_RE.search(self._buffer)
            if m:
                out.extend(self._buffer[: m.end()])
                self._buffer = self._buffer[m.end():]
                return bytes(out)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"{self._label} did not emit prompt within {timeout}s; "
                    f"buffer tail={self._buffer[-200:]!r}"
                )
            ready, _, _ = select.select([fileno], [], [], min(remaining, 1.0))
            if not ready:
                if self.proc.poll() is not None:
                    raise RuntimeError(
                        f"{self._label} subprocess exited (code={self.proc.returncode}) "
                        f"while awaiting prompt. Output so far: "
                        f"{(bytes(out) + self._buffer)[-500:]!r}"
                    )
                continue
            chunk = os.read(fileno, 8192)
            if not chunk:
                raise RuntimeError(
                    f"{self._label} subprocess closed stdout unexpectedly. Output: "
                    f"{(bytes(out) + self._buffer)[-500:]!r}"
                )
            self._buffer += chunk

    def _collect_ready_output(self) -> None:
        """Buffer output that has already arrived, without waiting."""
        if self.proc is None or self.proc.stdout is None:
            return
        fileno = self.proc.stdout.fileno()
        while select.select([fileno], [], [], 0)[0]:
            chunk = os.read(fileno, 8192)
            if not chunk:
                return
            self._buffer += chunk

    def _send(self, line: str) -> None:
        """Write a command line to EC (newline-terminated).

        A prompt that has arrived by now answers no pending command, so the
        reply to this one would be read as the previous one's."""
        self._require_synchronized()
        self._collect_ready_output()
        if PROMPT_BYTES_RE.search(self._buffer):
            self._mark_desynchronized(
                f"unread reply before send: {self._buffer[-200:]!r}"
            )
        self._require_synchronized()
        assert self.proc is not None and self.proc.stdin is not None
        if not line.endswith("\n"):
            line += "\n"
        try:
            self.proc.stdin.write(line.encode("utf-8"))
            self.proc.stdin.flush()
        except BaseException as e:
            self._mark_desynchronized(f"write failed: {type(e).__name__}: {e}")
            if isinstance(e, BrokenPipeError):
                raise RuntimeError(f"{self._label} subprocess stdin broken: {e}") from e
            raise

    def send_and_drain(self, text: str, *, timeout: float,
                       is_error: Callable[[str], object],
                       whole_transaction: bool = False) -> str:
        """Drain every native sentence in one logical transaction.

        Stop at the first native rejection and return that response; otherwise
        return the final sentence's response (the current goal, not an earlier
        intermediate goal). The caller owns rollback of a partially run block.
        ``timeout`` bounds each sentence, or with ``whole_transaction`` the
        transaction as a whole.
        """
        deadline = time.monotonic() + timeout if whole_transaction else None
        raw = ""
        for command in split_ec_commands(text):
            if not strip_comments(command).strip():
                continue  # A comment-only tail produces no native response.
            self._send(command)
            wait = timeout if deadline is None else max(0.0, deadline - time.monotonic())
            raw = self._read_until_prompt(timeout=wait).decode("utf-8", errors="replace")
            if is_error(raw):
                break
        if not raw:
            raise ValueError("empty EasyCrypt transaction")
        return raw

    # -- replay prefix ----------------------------------------------------------
    def replay_prefix(
        self,
        setup_commands: list[str],
        committed_tactics: list[str],
        *,
        is_setup_error: Callable[[str], Optional[dict]],
        setup_timeout: float = 120.0,
        committed_timeout: float = 180.0,
    ) -> Optional[ReplayFail]:
        """Replay the setup prefix (error-gated by ``is_setup_error``) then the
        committed tactics into this freshly-spawned process. Returns ``None`` on
        success or a ``ReplayFail`` for the first rejected setup/commit block.
        Historical acceptance does not authorize ignoring a replay rejection.
        """
        for blocks, timeout in ((setup_commands, setup_timeout), (committed_tactics, committed_timeout)):
            for block in blocks:
                raw = self.send_and_drain(block, timeout=timeout, is_error=is_setup_error)
                err = is_setup_error(raw)
                if err is not None:
                    return ReplayFail(block, err, raw)
        return None

    # -- teardown ---------------------------------------------------------------
    def teardown(self, *, grace: Optional[float] = None, abandon_msg: Optional[str] = None) -> None:
        """Close stdin, SIGTERM, bounded-wait, then SIGKILL + a second bounded
        wait, then abandon with a warning. The waits are BOUNDED on purpose: an
        uninterruptible (D-state) EC child cannot be reaped anyway, and this runs
        under the per-session lock, so an unbounded wait would wedge every RPC
        for that session (audit §8 #6)."""
        if self.proc is None:
            return
        grace = self._teardown_grace if grace is None else grace
        if abandon_msg is None:
            abandon_msg = (
                f"{self._label} subprocess pid=%s did not exit after SIGKILL; "
                "abandoning it to release the session lock."
            )
        proc = self.proc
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                logger.warning(abandon_msg, getattr(proc, "pid", "?"))
        self.proc = None
