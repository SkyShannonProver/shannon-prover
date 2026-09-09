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
import re
import select
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

from core.easycrypt.ec_proc import spawn_emacs_pipe
from core.easycrypt.lemma_decls import mask_comments

logger = logging.getLogger("ec_lifecycle")

# The ``-emacs`` prompt is ``[<step>|<mode>]>``; it appears at end-of-line and
# marks the end of EC's output for one command. Canonical definition —
# ``ec_daemon`` imports it from here.
PROMPT_RE = re.compile(rb"\[\d+\|[a-zA-Z]+\]>")


def split_ec_commands(text: str) -> list[str]:
    """Split EC source text into a list of complete statements.

    An EC statement ends at a ``.`` that's at end-of-line, outside of
    a string literal and outside block comments. This matches what
    EC's toplevel treats as one command in ``-emacs`` mode.

    The splitter is intentionally conservative: unusual constructs
    (strings with dots, nested comments) are handled by tracking the
    paren-brace-bracket depth and comment nesting. Blank lines and
    comment-only lines are included with the next command so offsets
    stay consistent.
    """
    out: list[str] = []
    cur: list[str] = []
    in_block_comment = 0  # depth of (* ... *)
    in_string = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        cur.append(ch)
        # Handle line comment "(* *)"-style only. EC has no // line comments,
        # but we can still flag newline ending.
        if in_block_comment > 0:
            if ch == '(' and nxt == '*':
                in_block_comment += 1
                cur.append(nxt)
                i += 2
                continue
            if ch == '*' and nxt == ')':
                in_block_comment -= 1
                cur.append(nxt)
                i += 2
                continue
            i += 1
            continue
        if in_string:
            if ch == '"' and (i == 0 or text[i - 1] != "\\"):
                in_string = False
            i += 1
            continue
        if ch == '(' and nxt == '*':
            in_block_comment = 1
            cur.append(nxt)
            i += 2
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == '.':
            # Is this end-of-statement? It is iff followed by whitespace
            # or EOF — not a qualifier like ``M.proc`` where the next char
            # is alphanumeric.
            if not nxt or nxt in " \t\n\r":
                # Flush current buffer as one statement (include the dot
                # and trailing newline if present).
                # Gobble following whitespace up to but not including the
                # next non-whitespace char.
                j = i + 1
                while j < n and text[j] in " \t":
                    cur.append(text[j])
                    j += 1
                # Include a single trailing newline if present.
                if j < n and text[j] == "\n":
                    cur.append("\n")
                    j += 1
                out.append("".join(cur))
                cur = []
                i = j
                continue
        i += 1
    tail = "".join(cur).strip()
    if tail:
        out.append(tail)
    return out


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
    one prompt per send, so no bytes are ever left buffered)."""

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
        self._last_prompt_text = ""

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
        self.proc = spawn_emacs_pipe(
            self.include_dirs, self.why3_socket, env=self._resolve_env(),
        )
        self._read_until_prompt(timeout=self._drain_timeout)

    # -- I/O primitives ---------------------------------------------------------
    def _read_until_prompt(self, timeout: float = _RESPONSE_TIMEOUT_DEFAULT) -> bytes:
        """Read stdout until a ``[N|mode]>`` prompt; return the block since the
        previous prompt. Buffer-preserving: any bytes past the prompt stay in
        ``self._buffer`` for the next read."""
        assert self.proc is not None and self.proc.stdout is not None
        deadline = time.monotonic() + timeout
        out = bytearray()
        fileno = self.proc.stdout.fileno()
        while True:
            m = PROMPT_RE.search(self._buffer)
            if m:
                out.extend(self._buffer[: m.end()])
                self._buffer = self._buffer[m.end():]
                self._last_prompt_text = out[-80:].decode("utf-8", errors="replace")
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

    def _send(self, line: str) -> None:
        """Write a command line to EC (newline-terminated)."""
        assert self.proc is not None and self.proc.stdin is not None
        if not line.endswith("\n"):
            line += "\n"
        try:
            self.proc.stdin.write(line.encode("utf-8"))
            self.proc.stdin.flush()
        except BrokenPipeError as e:
            raise RuntimeError(f"{self._label} subprocess stdin broken: {e}") from e

    def send_and_drain(self, text: str, *, timeout: float,
                       is_error: Callable[[str], object]) -> str:
        """Drain every native sentence in one logical transaction.

        Stop at the first native rejection and return that response; otherwise
        return the final sentence's response (the current goal, not an earlier
        intermediate goal). The caller owns rollback of a partially run block.
        """
        raw = ""
        for command in split_ec_commands(text):
            if not mask_comments(command).strip():
                continue  # A comment-only tail produces no native response.
            self._send(command)
            raw = self._read_until_prompt(timeout=timeout).decode("utf-8", errors="replace")
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
