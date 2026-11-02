#!/usr/bin/env python3
"""Daemon-backed fast path for session_cli.

When available, each managed commit routes through a persistent
``ec_daemon`` process instead of spawning a fresh ``easycrypt``
subprocess. The daemon carries EC state in memory so every commit
after the first costs ~50-100 ms instead of 1-2 s.

Design invariants
-----------------

- **Journal-bound acceleration.** ``history.ec`` plus ``steps.log`` preserve
  committed manager transactions. Daemon state is volatile and can be rebuilt
  from that journal; current semantic outcomes still require native execution.

- **Zero-impact fallback.** Any daemon error returns ``None`` and the
  caller stays on the subprocess path. No exceptions escape to break
  the prover flow. A transaction EasyCrypt does not finish within the step
  limit is not an error but a rejection: the batch path would run it again.

- **Lemma-scoped.** The daemon requires ``(file_path, lemma_name)``
  (from ``session_meta.json``). Whole-file sessions fall back to
  subprocess.

- **Auto-spawn.** The daemon process is started lazily if the socket
  is missing.

Usage from ``session_runtime.Session._commit_on_daemon``::

    dbe = DaemonBackend(session_dir, include_dirs)
    reply = dbe.commit_latest(file_path, lemma_name, all_transactions)
    if reply is None:
        ...  # fall back to the batch backend
    else:
        ...  # reply has post_raw and the rejection error, if any; Session
             # writes prev.out from its own pre-commit state

Some daemon failures repeat on every commit until something changes: the
daemon cannot be spawned, a committed transaction does not replay, or
EasyCrypt rejects the lemma's context. The backend remembers each in
``<session_dir>/daemon_unavailable.json``, keyed by what failed (the socket,
the committed prefix identity, the source content), and skips the daemon
while the key still matches and the entry is fresh. A skip is an ordinary
fallback (``None``), never a verdict. The entries survive ``invalidate``;
``-start`` removes the session directory and them with it.

``try_tactics`` checks tactics on the committed state without committing
them. When the journal shrinks (an undo, a rewind, a rolled-back rejection or
no-op), ``rewind_to`` takes the daemon back with EasyCrypt's ``undo <level>.``
instead of reopening and replaying; ``invalidate`` drops the session when
that is not possible (and on start).
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from core.env_loader import env_bool
from core.easycrypt.committed_history import committed_prefix_identity
from core.easycrypt.ec_daemon_client import (
    ECDaemonClient,
    ECDaemonConnectionLost,
    step_timeout_seconds,
)
from core.easycrypt.proof_text import split_ec_commands
from core.easycrypt.session.session_display import (
    TryResult,
    chain_try_result,
    single_try_result,
    try_tool_error,
)


def _default_socket() -> str:
    """Resolve through the one shared default (env override, else
    per-checkout path) — see ``ec_daemon_client.default_socket_path``."""
    from core.easycrypt.ec_daemon_client import default_socket_path

    return default_socket_path()


def session_id_for_dir(session_dir: "Path | str") -> str:
    """The daemon session id for a session dir: ``scli_`` + first 12 hex chars of
    sha1(resolved dir path). Single source of truth — ``DaemonBackend`` and the
    workflow-side ``daemon_attach`` both derive the id here (no hand-mirroring)."""
    h = hashlib.sha1(str(Path(session_dir).resolve()).encode()).hexdigest()[:12]
    return f"scli_{h}"


def _resolve_why3_socket() -> Optional[str]:
    """Return the path to the persistent why3 socket if it is currently
    listening, else ``None``.

    The prover (``workflow.agents.ec_services._ensure_why3server``) starts
    one why3 server per run on the ``WHY3EC_SOCKET`` path
    (``ec_proc.why3_socket_from_env``) and reuses it for every EC
    subprocess via ``-server``. The batch path in
    ``ec_backend.BatchBackend.run`` already wires this up. This helper exists
    so the daemon-backed path passes the same socket through to
    ``cli.open_session``; without it the daemon-spawned EC tries to
    spawn its own why3 server, which the OS sandbox blocks via
    ``nice()``, and EC silently fails on any SMT-dependent clone.

    A connect-probe is intentionally NOT done here — it would block the
    fast-path commit. ``ec_daemon._h_open`` accepts ``None``
    gracefully (omits the ``-server`` flag); a stale socket on disk that
    EC then refuses is no worse than the prior bug of always omitting
    the flag.
    """
    from core.easycrypt.ec_proc import why3_socket_from_env

    socket_path = why3_socket_from_env()
    if os.path.exists(socket_path):
        return socket_path
    return None


def is_disabled() -> bool:
    """Honor the ``EC_DAEMON_DISABLE=1`` kill switch."""
    return env_bool("EC_DAEMON_DISABLE", default=False)


# How long a known daemon failure is honoured before the daemon is tried
# again. A spawn failure belongs to the environment. Replay and open failures
# are keyed by the content that failed, but smt under load can fail once.
SPAWN_FAILURE_TTL_SECONDS = 300.0
CONTENT_FAILURE_TTL_SECONDS = 600.0


def _source_sha256(file_path: Path) -> str:
    try:
        return hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
    except OSError:
        return ""


@dataclass(frozen=True)
class DaemonCommit:
    """The daemon's verdict on the latest transaction.

    ``post_raw`` is EasyCrypt's output for the transaction and ``error`` its
    rejection, empty when the daemon accepted and committed it.
    """

    post_raw: str
    error: str = ""

    @property
    def accepted(self) -> bool:
        return not self.error


@dataclass(frozen=True)
class DaemonRewind:
    """The daemon now holds exactly the requested journal prefix.

    ``post_raw`` is EasyCrypt's reply to ``undo <level>.`` (it prints the
    restored goal), empty when nothing had to be undone. ``undone`` counts
    the transactions taken back.
    """

    post_raw: str
    undone: int = 0


def _rejection(error: object, post_raw: str) -> str:
    """The ``[error] …`` line for a rejected commit, never empty.

    ``raw`` carries the full EC error text incl. the lemma name; ``kind``
    strips it. Without a structured error the first error line of the
    reply stands in.
    """
    message = ""
    if isinstance(error, dict):
        message = (error.get("raw")
                   or error.get("message")
                   or error.get("excerpt")
                   or "")
    if not message:
        for line in post_raw.splitlines():
            if re.match(r"^\s*\[(error|critical|fatal)", line):
                message = line.strip()
                break
    if not message:
        return "[error] daemon rejection"
    return message if message.startswith("[") else f"[error] {message}"


_POISON_MARKERS = (
    "getcwd",            # EC: Unix_error(ENOENT, "getcwd", "") — cwd deleted
    "closed stdout",     # daemon: EC subprocess died mid-handshake
    "closed stderr",
    "fatal error",       # EC OCaml fatal exception
    "unix_error",
)

_STALE_SOCKET_ERRNOS = frozenset({
    errno.ECONNREFUSED,
    errno.ENOENT,
})


def _socket_probe_error(errno_value: int, socket_path: str) -> str:
    """Describe a failed Unix-socket probe without treating it as stale.

    A permission failure means the caller cannot establish whether the
    listener is healthy.  It must therefore fail closed without unlinking a
    possibly live daemon socket.  Unknown probe failures follow the same
    conservative rule.
    """

    try:
        detail = os.strerror(errno_value)
    except (OverflowError, ValueError):
        detail = "unknown socket error"
    if errno_value in {errno.EACCES, errno.EPERM}:
        kind = "daemon socket access denied"
    else:
        kind = "daemon socket probe failed"
    return (
        f"{kind}: {socket_path}: {detail} "
        f"(errno={errno_value})"
    )


def _is_poison_error(exc: object) -> bool:
    """A live daemon whose working directory was deleted (e.g. spawned in a
    worktree that was later removed) crashes every EC subprocess it forks with
    ``Unix_error(ENOENT, "getcwd")``. The socket stays alive, so the stale-file
    probe in ``_ensure_daemon`` cannot detect it — only the open/commit error
    text reveals it. Per-checkout sockets (``_default_socket``) prevent this
    cross-checkout case; this detector is the runtime safety net for any
    residual poison (incl. a daemon spawned before the per-checkout fix)."""
    s = str(exc).lower()
    return any(m in s for m in _POISON_MARKERS)


class DaemonBackend:
    """Client-side shim that keeps a session_cli session in sync with
    an ``ec_daemon`` session. State cached at
    ``<session_dir>/daemon_state.json``.
    """

    def __init__(self, session_dir: Path, include_dirs: list[str],
                 socket_path: Optional[str] = None):
        self.dir = Path(session_dir)
        self.include_dirs = list(include_dirs)
        # Resolve the default at construction (not import) time: the managed
        # prover sets EC_DAEMON_SOCKET lazily before first use, and the
        # per-checkout key reflects the live cwd. An explicit socket_path wins.
        self.socket_path = socket_path or _default_socket()
        self._session_id = session_id_for_dir(self.dir)
        self._state_path = self.dir / "daemon_state.json"
        self._client: Optional[ECDaemonClient] = None
        self.last_error = ""
        self._failures_path = self.dir / "daemon_unavailable.json"
        self._failures: Optional[dict] = None
        # Failures this backend started to honour, for the session to record
        # (one ``ec.daemon_unavailable`` event each).
        self.unavailable_notices: list[dict] = []

    # -----------------------------------------------------------------
    # State (which committed prefix the daemon has replayed)
    # -----------------------------------------------------------------

    def _load_state(self) -> dict:
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text())
            except Exception as exc:
                # A corrupt state file silently degrades every commit into a
                # full-history replay ("slow, not wrong") — leave a breadcrumb.
                self.last_error = (
                    f"daemon state unreadable ({self._state_path}): "
                    f"{type(exc).__name__}: {exc}; replaying full history"
                )
                return {}
        return {}

    def _save_state(self, state: dict) -> None:
        try:
            self._state_path.write_text(json.dumps(state, indent=2))
        except Exception as exc:
            self.last_error = (
                f"daemon state unwritable ({self._state_path}): "
                f"{type(exc).__name__}: {exc}"
            )

    def _forget_state(self) -> None:
        """Drop the cached replay state so the next sync reopens and replays.

        Called whenever a request failed without a reply: the daemon may still
        have run it, so the state no longer describes the daemon's EC."""
        try:
            self._state_path.unlink(missing_ok=True)
        except OSError as exc:
            self.last_error = (
                f"daemon state not removable ({self._state_path}): "
                f"{type(exc).__name__}: {exc}"
            )

    # -----------------------------------------------------------------
    # Known failures (see the module docstring)
    # -----------------------------------------------------------------

    def _known_failures(self) -> dict:
        if self._failures is None:
            try:
                loaded = json.loads(self._failures_path.read_text())
            except (OSError, ValueError):
                loaded = {}
            self._failures = loaded if isinstance(loaded, dict) else {}
        return self._failures

    def _write_failures(self) -> None:
        try:
            if self._failures:
                self._failures_path.write_text(json.dumps(self._failures, indent=2))
            else:
                self._failures_path.unlink(missing_ok=True)
        except OSError:
            pass  # forgetting a known failure only costs a retry

    def _remember_failure(self, kind: str, ttl: float, reason: str, **key) -> None:
        until = time.time() + ttl
        self._known_failures()[kind] = {**key, "reason": reason, "until": until}
        self._write_failures()
        notice = {
            "kind": kind,
            "reason": reason[:400],
            "ttl_seconds": ttl,
            "expires_at": datetime.fromtimestamp(until, timezone.utc).isoformat(
                timespec="seconds"
            ),
        }
        if "prefix_count" in key:
            notice["prefix_count"] = key["prefix_count"]
        self.unavailable_notices.append(notice)

    def _honoured_failure(self, kind: str, matches: Callable[[dict], bool]) -> str:
        """``last_error`` for a fresh ``kind`` failure whose key ``matches``,
        else ``""``. An expired or no longer matching entry is dropped."""
        failures = self._known_failures()
        entry = failures.get(kind)
        if entry is None:
            return ""
        left = -1.0
        if isinstance(entry, dict) and isinstance(entry.get("until"), (int, float)):
            left = float(entry["until"]) - time.time()
        if left > 0 and matches(entry):
            return (
                f"negative cache: {entry.get('reason') or kind} "
                f"(skipping the daemon for another {left:.0f} s)"
            )
        del failures[kind]
        self._write_failures()
        return ""

    def _honoured_content_failure(self, file_path: Path, lemma_name: str,
                                  target_tactics: list[str]) -> str:
        """A known replay failure in ``target_tactics`` or rejection of this
        lemma's context, as ``last_error``; else ``""``."""
        source = str(Path(file_path).resolve())

        def same_lemma(entry: dict) -> bool:
            return entry.get("file_path") == source and entry.get("lemma_name") == lemma_name

        def same_prefix(entry: dict) -> bool:
            count = entry.get("prefix_count")
            return (
                same_lemma(entry)
                and type(count) is int
                and 0 < count <= len(target_tactics)
                and committed_prefix_identity(target_tactics[:count])
                == entry.get("prefix_sha256")
            )

        def same_source(entry: dict) -> bool:
            return same_lemma(entry) and entry.get("source_sha256") == _source_sha256(
                Path(file_path)
            )

        return (
            self._honoured_failure("replay", same_prefix)
            or self._honoured_failure("open", same_source)
        )

    def _remember_replay_failure(self, file_path: Path, lemma_name: str,
                                 prefix: list[str]) -> None:
        self._remember_failure(
            "replay", CONTENT_FAILURE_TTL_SECONDS, self.last_error,
            file_path=str(Path(file_path).resolve()),
            lemma_name=lemma_name,
            prefix_count=len(prefix),
            prefix_sha256=committed_prefix_identity(prefix),
        )

    def _remember_open_failure(self, exc: Exception, file_path: Path,
                               lemma_name: str) -> None:
        """Remember an open that EasyCrypt refused (the daemon says so with
        ``kind``); other open failures may not repeat."""
        if getattr(exc, "kind", None) != "setup_rejected":
            return
        self._remember_failure(
            "open", CONTENT_FAILURE_TTL_SECONDS, self.last_error,
            file_path=str(Path(file_path).resolve()),
            lemma_name=lemma_name,
            source_sha256=_source_sha256(Path(file_path)),
        )

    def invalidate(self) -> None:
        """Close the daemon session (best effort) and drop state file.
        Call on start, and whenever the journal changed in a way
        ``rewind_to`` could not mirror on the daemon."""
        cli = self._client
        if cli is None and os.path.exists(self.socket_path):
            cli = ECDaemonClient(self.socket_path)
        if cli is not None:
            try:
                cli.close_session(self._session_id)
            except Exception:
                pass
        self._client = None
        try:
            self._state_path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass

    # -----------------------------------------------------------------
    # Daemon connection
    # -----------------------------------------------------------------

    def _ensure_daemon(self) -> Optional[ECDaemonClient]:
        """Return a usable client, or ``None`` on failure. Lazy-spawns
        the daemon if the socket is missing OR if the existing socket
        is stale (file present but no listener — happens when a
        previous daemon crashed without cleanup, leaving the socket
        path on disk).

        Checking only ``os.path.exists()`` would skip the spawn for a
        stale socket file, and every later connect/list_sessions would then
        fail silently.
        """
        if self._client is not None:
            try:
                self._client.list_sessions()
                return self._client
            except Exception:
                self._client = None
        # Probe-and-respawn on a *confirmed* stale socket: socket file present
        # but nothing listening.  ``connect_ex`` also returns nonzero for
        # permission and policy failures.  Those do not prove staleness and
        # must never cause a potentially live socket to be unlinked.
        if os.path.exists(self.socket_path):
            probe = None
            try:
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                probe.settimeout(2)
                rc = probe.connect_ex(self.socket_path)
            except OSError as exc:
                rc = exc.errno if exc.errno is not None else -1
            except Exception:
                rc = -1
            finally:
                if probe is not None:
                    try:
                        probe.close()
                    except Exception:
                        pass
            if rc in _STALE_SOCKET_ERRNOS:
                # Stale: drop the file so _spawn_daemon's existence
                # check doesn't short-circuit. Also drop the spawn
                # lock — it may be from a long-dead process.
                for p in (self.socket_path, self.socket_path + ".spawn_lock"):
                    try:
                        os.unlink(p)
                    except FileNotFoundError:
                        pass
                    except Exception:
                        pass
            elif rc != 0:
                self.last_error = _socket_probe_error(rc, self.socket_path)
                return None
        if not os.path.exists(self.socket_path):
            honoured = self._honoured_failure(
                "spawn", lambda entry: entry.get("socket_path") == self.socket_path,
            )
            if honoured:
                self.last_error = honoured
                return None
            if not self._spawn_daemon():
                self.last_error = f"daemon spawn failed: {self.socket_path}"
                self._remember_failure(
                    "spawn", SPAWN_FAILURE_TTL_SECONDS, self.last_error,
                    socket_path=self.socket_path,
                )
                return None
        cli = ECDaemonClient(self.socket_path)
        try:
            cli.list_sessions()
        except Exception as exc:
            self.last_error = (
                f"daemon handshake failed at {self.socket_path}: "
                f"{type(exc).__name__}: {exc}"
            )
            return None
        if "spawn" in self._known_failures():
            # A daemon answers there now; a later spawn may work as well.
            del self._known_failures()["spawn"]
            self._write_failures()
        self._client = cli
        return cli

    def _spawn_daemon(self) -> bool:
        """Spawn the daemon detached. Wait up to 10 s for its socket
        to appear. Returns ``True`` on success.

        Multiple concurrent session_cli processes can all reach the
        "socket absent → spawn" path at the same time. Without a lock
        we end up with N orphan daemons: only one wins the ``bind()``
        race on the socket, the other N−1 silently crash but their
        Python process leaks as zombies. Use a POSIX file lock on
        ``<socket>.lock`` to serialize the spawn decision; whoever
        wins the lock actually spawns, the others just wait for the
        socket to appear."""
        import fcntl  # POSIX only — daemon is Unix-socket-only anyway
        script = Path(__file__).parent / "ec_daemon.py"
        if not script.exists():
            return False
        lock_path = self.socket_path + ".spawn_lock"
        try:
            lock_fd = os.open(
                lock_path, os.O_WRONLY | os.O_CREAT, 0o600,
            )
        except Exception:
            lock_fd = None
        try:
            if lock_fd is not None:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX)
                except Exception:
                    pass
            # After acquiring the lock, re-check: another process may
            # have spawned the daemon while we were waiting.
            if os.path.exists(self.socket_path):
                return True
            try:
                subprocess.Popen(
                    [sys.executable, str(script),
                     "--socket", self.socket_path,
                     "--log-level", "WARNING"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                return False
            for _ in range(100):
                if os.path.exists(self.socket_path):
                    return True
                time.sleep(0.1)
            return False
        finally:
            if lock_fd is not None:
                # Unlink while still holding the exclusive lock: waiters on
                # this inode re-check the socket under their lock, and later
                # spawners create a fresh lock file. Without the unlink every
                # successful spawn left a permanent .spawn_lock behind (three
                # of them were sitting in the repo root from July).
                try:
                    os.unlink(lock_path)
                except OSError:
                    pass
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                except Exception:
                    pass

    def _force_fresh_daemon(self) -> Optional[ECDaemonClient]:
        """Discard a live-but-poisoned daemon and spawn a fresh one.

        Unlinking the socket path orphans the poisoned daemon (it keeps its
        now-pathless listening fd but receives no new connections) and lets
        ``_spawn_daemon`` bind a fresh daemon at the same path — whose cwd is
        the live checkout, so ``getcwd`` succeeds. Returns the new client or
        ``None``."""
        self._client = None
        for p in (self.socket_path, self.socket_path + ".spawn_lock"):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
            except Exception:
                pass
        return self._ensure_daemon()

    # -----------------------------------------------------------------
    # Sync + commit
    # -----------------------------------------------------------------

    def _rewind_session(self, cli: ECDaemonClient, state: dict,
                        target_tactics: list[str], *,
                        require_open_goal: bool = False,
                        ) -> Optional[DaemonRewind]:
        """Undo the live session back to ``target_tactics``, a proper prefix
        of what the state file says it holds.

        The daemon checks both committed-prefix identities against the texts
        it ran, and refuses without touching EC when they disagree or an
        undone transaction cannot be undone. ``None`` means the session does
        not hold ``target_tactics`` now (``last_error`` says why)."""
        try:
            reply = cli.rewind(
                self._session_id,
                len(target_tactics),
                keep_identity=committed_prefix_identity(target_tactics),
                held_identity=state.get("committed_prefix_sha256"),
                require_open_goal=require_open_goal,
            )
        except Exception as exc:
            # A failed undo discards the daemon session; without a reply the
            # daemon's state is unknown either way.
            self.last_error = f"daemon rewind failed: {type(exc).__name__}: {exc}"
            if isinstance(exc, ECDaemonConnectionLost):
                self._client = None
            self._forget_state()
            return None
        if not isinstance(reply, dict) or reply.get("rewound") is not True:
            reason = reply.get("reason") if isinstance(reply, dict) else reply
            self.last_error = f"daemon rewind refused: {reason}"
            return None
        updated = dict(state)
        updated["committed_count"] = len(target_tactics)
        updated["committed_prefix_sha256"] = committed_prefix_identity(
            target_tactics
        )
        self._save_state(updated)
        return DaemonRewind(
            post_raw=str(reply.get("raw_output") or ""),
            undone=int(reply.get("undone") or 0),
        )

    def rewind_to(self, file_path: Path, lemma_name: str,
                  target_tactics: list[str], *,
                  require_open_goal: bool = False) -> Optional[DaemonRewind]:
        """Bring the live daemon session back to ``target_tactics`` by undo only.

        Succeeds when the session holds ``target_tactics`` (nothing to do) or
        a longer history that starts with it (one ``undo <level>.``). With
        ``require_open_goal`` the daemon also refuses a target state that
        showed no open goal. Never opens, replays or commits: ``None`` means
        the caller must use its restart/replay path, and ``last_error`` says
        why."""
        self.last_error = ""
        if is_disabled():
            self.last_error = "daemon disabled"
            return None
        state = self._load_state()
        if (
            not state
            or state.get("file_path") != str(Path(file_path).resolve())
            or state.get("lemma_name") != lemma_name
        ):
            self.last_error = "daemon state does not describe this session"
            return None
        cached_count = state.get("committed_count")
        if type(cached_count) is not int or cached_count < len(target_tactics):
            self.last_error = "daemon holds fewer transactions than the target"
            return None
        if self._client is None and not os.path.exists(self.socket_path):
            self.last_error = "daemon socket missing"
            return None
        cli = self._ensure_daemon()
        if cli is None:
            return None
        try:
            sessions = cli.list_sessions()
        except Exception as exc:
            self.last_error = f"list_sessions failed: {exc}"
            self._client = None
            return None
        if self._session_id not in sessions:
            self.last_error = "daemon session is gone"
            return None
        if cached_count == len(target_tactics):
            if state.get("committed_prefix_sha256") == committed_prefix_identity(
                target_tactics
            ):
                return DaemonRewind(post_raw="", undone=0)
            self.last_error = "daemon holds a different history of the same length"
            return None
        return self._rewind_session(
            cli, state, target_tactics, require_open_goal=require_open_goal,
        )

    def _sync_to(self, file_path: Path, lemma_name: str,
                 target_tactics: list[str]) -> bool:
        """Ensure the daemon session has exactly ``target_tactics``
        committed. Undoes back to a shorter target, extends a held prefix,
        and otherwise re-opens and replays from scratch.
        Returns ``True`` on success.

        The state file names the replayed prefix by its identity, not only
        its length: a session is extended only when what it holds is the
        start of ``target_tactics``, and the daemon checks that identity
        again before undoing to a shorter target. A known failure for this
        journal or context returns ``False`` at once."""
        self.last_error = self._honoured_content_failure(
            file_path, lemma_name, target_tactics,
        )
        if self.last_error:
            return False
        cli = self._ensure_daemon()
        if cli is None:
            if not self.last_error:
                self.last_error = "daemon connection unavailable"
            return False

        state = self._load_state()
        cached_count = state.get("committed_count", 0)
        cached_file = state.get("file_path")
        cached_lemma = state.get("lemma_name")

        need_reopen = (
            cached_file != str(file_path.resolve())
            or cached_lemma != lemma_name
        )

        if not need_reopen:
            try:
                sessions = cli.list_sessions()
            except Exception as exc:
                self.last_error = f"list_sessions failed: {exc}"
                self._client = None
                return False
            if self._session_id not in sessions:
                need_reopen = True
            elif cached_count > len(target_tactics):
                # The journal shrank under the daemon. Undo back to it; reopen
                # and replay only when the daemon refuses or the undo fails.
                if self._rewind_session(cli, state, target_tactics) is None:
                    need_reopen = True
                else:
                    cached_count = len(target_tactics)
            elif state.get("committed_prefix_sha256") != committed_prefix_identity(
                target_tactics[:cached_count]
            ):
                # Same length, different tactics: the history changed under
                # the daemon (or the state predates prefix identities).
                need_reopen = True

        if need_reopen:
            # Until the replay below completes, no count describes the session.
            self._forget_state()
            try:
                cli.close_session(self._session_id)
            except Exception:
                pass
            try:
                cli.open_session(
                    self._session_id, str(file_path),
                    self.include_dirs, lemma_name,
                    why3_socket=_resolve_why3_socket(),
                )
            except Exception as exc:
                # A poisoned daemon (dead cwd) crashes every EC it forks. The
                # socket is alive, so _ensure_daemon's stale-file probe passed
                # and handed us this daemon. Discard it, spawn a fresh one, and
                # retry the open once before surrendering to the subprocess.
                if _is_poison_error(exc):
                    cli = self._force_fresh_daemon()
                    if cli is None:
                        self.last_error = (
                            f"daemon respawn failed after poison for "
                            f"{file_path.name}:{lemma_name}: {exc}"
                        )
                        return False
                    try:
                        cli.open_session(
                            self._session_id, str(file_path),
                            self.include_dirs, lemma_name,
                            why3_socket=_resolve_why3_socket(),
                        )
                    except Exception as exc2:
                        self.last_error = (
                            f"open_session failed after respawn for "
                            f"{file_path.name}:{lemma_name}: {exc2}"
                        )
                        self._remember_open_failure(exc2, file_path, lemma_name)
                        return False
                else:
                    self.last_error = (
                        f"open_session failed for {file_path.name}:{lemma_name}: {exc}"
                    )
                    self._remember_open_failure(exc, file_path, lemma_name)
                    return False
            cached_count = 0

        # Commit any missing tactics from ``cached_count`` up to target. A
        # replayed transaction gets the same limit as when it was committed.
        if cached_count < len(target_tactics):
            new_tactics = target_tactics[cached_count:]
            step_timeout = step_timeout_seconds()
            for index, tac in enumerate(new_tactics, start=cached_count):
                # A partial replay leaves the daemon between the cached count
                # and the target, so a failure forgets the count.
                try:
                    r = cli.commit(self._session_id, tac, timeout=step_timeout)
                except Exception as exc:
                    self.last_error = f"replay commit raised for {tac!r}: {exc}"
                    self._client = None
                    self._forget_state()
                    return False
                if r.get("timed_out") is True:
                    self.last_error = (
                        f"replay timed out on committed tactic {tac!r}: "
                        f"{_rejection(r.get('error'), '')}"
                    )
                    self._forget_state()
                    self._remember_replay_failure(
                        file_path, lemma_name, target_tactics[:index + 1],
                    )
                    return False
                if not r.get("accepted"):
                    # Committed history should replay cleanly; if not,
                    # something is off — surrender to subprocess.
                    error = r.get("error") or r.get("raw_output") or ""
                    self.last_error = (
                        f"replay rejected committed tactic {tac!r}: "
                        f"{str(error).strip()[:500]}"
                    )
                    self._forget_state()
                    self._remember_replay_failure(
                        file_path, lemma_name, target_tactics[:index + 1],
                    )
                    return False

        self._save_state({
            "session_id": self._session_id,
            "committed_count": len(target_tactics),
            "committed_prefix_sha256": committed_prefix_identity(target_tactics),
            "file_path": str(file_path.resolve()),
            "lemma_name": lemma_name,
            "socket_path": self.socket_path,
        })
        return True

    def commit_latest(self, file_path: Path, lemma_name: str,
                      all_tactics: list[str]) -> Optional[DaemonCommit]:
        """Sync daemon to ``all_tactics[:-1]``, commit
        ``all_tactics[-1]``. Returns the daemon's verdict, or ``None``
        when the daemon could not judge the commit (``last_error`` says
        why). A transaction EasyCrypt does not finish within
        ``step_timeout_seconds()`` is a rejection.

        The caller supplies its own pre-commit state (typically
        ``self.prev`` / ``self.curr`` from the prior turn) for
        no-progress diffing — the daemon's ``get_goal`` produces
        differently-formatted output that doesn't compare cleanly
        against commit outputs."""
        if is_disabled():
            return None
        if not all_tactics or not file_path or not lemma_name:
            return None

        if not self._sync_to(file_path, lemma_name, all_tactics[:-1]):
            return None
        cli = self._ensure_daemon()
        if cli is None:
            return None

        try:
            r = cli.commit(
                self._session_id, all_tactics[-1], timeout=step_timeout_seconds(),
            )
        except Exception as exc:
            self.last_error = f"daemon commit RPC failed: {type(exc).__name__}: {exc}"
            self._client = None
            self._forget_state()
            return None

        post_raw = r.get("raw_output", "") or ""
        if r.get("timed_out") is True:
            # A batch run would only spend the same time on the same tactic
            # again. The daemon dropped the session it stopped, so the caller
            # rolls the transaction back and the next commit reopens and
            # replays a journal without it.
            self._forget_state()
            return DaemonCommit(post_raw, _rejection(r.get("error"), post_raw))
        if not bool(r.get("accepted", False)):
            return DaemonCommit(post_raw, _rejection(r.get("error"), post_raw))
        state = self._load_state()
        state["committed_count"] = len(all_tactics)
        state["committed_prefix_sha256"] = committed_prefix_identity(all_tactics)
        self._save_state(state)
        return DaemonCommit(post_raw)

    def try_tactics(self, file_path: Path, lemma_name: str,
                    committed: list[str], request: str,
                    prev_raw: str = "") -> TryResult:
        """Check ``request`` on the committed state without committing it.

        The request is split at EasyCrypt sentence ends; one tactic runs as
        ``try_tactic``, several as ``try_chain``, which stops at the first
        failure. ``prev_raw`` is the current state, against which an
        accepted single tactic is checked for progress. Committed history
        must replay cleanly first.
        """
        if not self._sync_to(file_path, lemma_name, committed):
            detail = self.last_error or "unknown"
            return try_tool_error(
                request,
                "[TRY] error: could not sync daemon to committed "
                "history (daemon spawn / session open / replay failed). "
                "If a committed tactic fails on replay, -try is "
                "unavailable until that tactic is removed through the "
                "manager undo control.\n"
                f"[TRY] sync_detail: {detail}\n",
            )
        cli = self._ensure_daemon()
        if cli is None:
            return try_tool_error(request, "[TRY] error: daemon connection lost.\n")

        # A probe without a final dot gets one.
        raw_in = request.strip()
        if not raw_in:
            return try_tool_error(request, "[TRY] error: empty tactic.\n")
        if not raw_in.endswith("."):
            raw_in = raw_in + "."
        tactic_list = [t.strip() for t in split_ec_commands(raw_in) if t.strip()]
        if not tactic_list:
            return try_tool_error(
                request,
                "[TRY] error: no parseable tactic (check the trailing '.').\n",
            )

        single = len(tactic_list) == 1

        def _run_probe(client: ECDaemonClient) -> dict:
            if single:
                return client.try_tactic(self._session_id, tactic_list[0])
            return client.try_chain(self._session_id, tactic_list)

        verb = "try_tactic" if single else "try_chain"
        try:
            reply = _run_probe(cli)
        except ECDaemonConnectionLost:
            # The daemon dropped the connection mid-probe — its EC subprocess
            # most likely crashed (a heavy smt/auto on a large goal). A probe
            # never mutates committed state, so recovery is safe: respawn a
            # fresh daemon, replay the committed history, and retry the probe
            # ONCE. Bounding to a single retry avoids looping when the tactic
            # itself is what crashes EC.
            self._force_fresh_daemon()
            if not self._sync_to(file_path, lemma_name, committed):
                return try_tool_error(
                    request,
                    "[TRY] error: the daemon dropped the connection "
                    "mid-probe and the session could not be re-synced. The "
                    "probe was NOT evaluated and the committed proof state "
                    "is unchanged — retry, or use a lighter tactic (the "
                    "goal may be too heavy for smt/auto).\n",
                )
            cli = self._ensure_daemon()
            if cli is None:
                return try_tool_error(
                    request,
                    "[TRY] error: the daemon dropped the connection "
                    "mid-probe and could not be respawned. The committed "
                    "proof state is unchanged.\n",
                )
            try:
                reply = _run_probe(cli)
            except Exception:
                return try_tool_error(
                    request,
                    "[TRY] error: this tactic repeatedly drops the "
                    "EasyCrypt backend connection on the current goal (the "
                    "daemon crashed again after a fresh respawn + replay) — "
                    "it is almost certainly too heavy (e.g. a broad "
                    "smt/auto on a large goal). The probe was NOT evaluated "
                    "and the committed proof state is unchanged; try a "
                    "lighter or more targeted tactic.\n",
                )
        except Exception as e:
            return try_tool_error(request, f"[TRY] error: daemon {verb} failed: {e}\n")
        if single:
            return single_try_result(tactic_list[0], reply, prev_raw)
        return chain_try_result(request, tactic_list, reply)

    def get_goal_raw(self) -> Optional[str]:
        """Force EC to re-emit the current goal state, returning the raw
        output.

        Some tactic combinations (especially chains like
        ``rewrite X; smt(...)`` that simultaneously close one subgoal and
        transition goal type) leave EC's output buffer at just ``[N|check]>``
        with no ``Current goal`` header — the state is internally correct
        but hasn't flushed. Calling this sends a harmless probe
        (``locate Int.`` via daemon's ``get_goal``) so EC prints the
        current state in its next output block.

        Returns ``None`` on any daemon error. Does NOT commit — the probe
        leaves session state unchanged.
        """
        if is_disabled():
            return None
        cli = self._ensure_daemon()
        if cli is None:
            return None
        try:
            r = cli.get_goal(self._session_id)
        except Exception:
            self._client = None
            self._forget_state()
            return None
        if not isinstance(r, dict):
            return None
        return r.get("raw") or None
