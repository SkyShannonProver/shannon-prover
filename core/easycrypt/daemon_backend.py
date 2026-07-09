#!/usr/bin/env python3
"""Daemon-backed fast path for session_cli.

When available, each ``-next`` call routes through a persistent
``ec_daemon`` process instead of spawning a fresh ``easycrypt``
subprocess. The daemon carries EC state in memory so every commit
after the first costs ~50-100 ms instead of 1-2 s.

Design invariants
-----------------

- **Disk is truth.** ``history.ec`` is the only source of committed
  tactic state. Daemon is a volatile accelerator that can be dropped
  and rebuilt from ``history.ec`` at any time without losing
  correctness.

- **Zero-impact fallback.** Any daemon error returns ``None`` and the
  caller stays on the subprocess path. No exceptions escape to break
  the prover flow.

- **Lemma-scoped.** The daemon requires ``(file_path, lemma_name)``
  (from ``session_meta.json``). Whole-file sessions fall back to
  subprocess.

- **Auto-spawn.** The daemon process is started lazily if the socket
  is missing.

Usage from ``session_cli.Session.append_block``::

    dbe = DaemonBackend(session_dir, include_dirs)
    result = dbe.try_commit_latest(file_path, lemma_name, all_tactics)
    if result is not None:
        curr_file.write_text(result["post_raw"])
        prev_file.write_text(result["pre_raw"])
    else:
        # fall back to the slow _run_ec path

See ``DaemonBackend.invalidate`` for the ``-prev``/``-start`` path.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from core.env_loader import env_bool
from core.easycrypt.ec_daemon_client import ECDaemonClient


def _default_socket() -> str:
    """Per-checkout daemon socket path.

    A daemon's working directory is the checkout it was spawned in. The old
    single global ``/tmp/ec_daemon.sock`` let a daemon spawned in one
    checkout/worktree serve another; when the first checkout was later deleted,
    the daemon's cwd vanished and EC crashed with
    ``Unix_error(ENOENT, "getcwd")`` — surfacing to callers as
    ``daemon unavailable`` / ``could not sync daemon to committed history`` and
    silently disabling all daemon-verified producers (bridge_options,
    call_site_options, rewrite_candidates) at deep proof states. Keying the
    socket on the current checkout keeps a reused daemon's cwd equal to the
    live checkout, so ``getcwd`` always succeeds. The managed prover overrides
    this with a per-run ``EC_DAEMON_SOCKET``.
    """
    override = os.environ.get("EC_DAEMON_SOCKET", "").strip()
    if override:
        return override
    key = hashlib.sha1(os.path.realpath(os.getcwd()).encode()).hexdigest()[:12]
    return f"/tmp/ec_daemon_{key}.sock"


def session_id_for_dir(session_dir: "Path | str") -> str:
    """The daemon session id for a session dir: ``scli_`` + first 12 hex chars of
    sha1(resolved dir path). Single source of truth — ``DaemonBackend`` and the
    workflow-side ``daemon_attach`` both derive the id here (no hand-mirroring)."""
    h = hashlib.sha1(str(Path(session_dir).resolve()).encode()).hexdigest()[:12]
    return f"scli_{h}"


SOCKET_DEFAULT = _default_socket()


def _resolve_why3_socket() -> Optional[str]:
    """Return the path to the persistent why3 socket if it is currently
    listening, else ``None``.

    The orchestrator (``workflow.agents.prover._ensure_why3server``) starts
    one why3 server per run on ``/tmp/why3ec.sock`` and reuses it for
    every EC subprocess via ``-server``. The subprocess path in
    ``session_runtime._run_ec`` already wires this up. This helper exists
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
    socket_path = os.environ.get("WHY3EC_SOCKET", "/tmp/why3ec.sock")
    if os.path.exists(socket_path):
        return socket_path
    return None


def _split_tactics(history_text: str) -> list[str]:
    """Split ``history.ec`` content into individual ``.``-terminated
    statements. Reuses ``ec_daemon._split_ec_commands``."""
    from core.easycrypt.ec_daemon import _split_ec_commands
    return [c.strip() for c in _split_ec_commands(history_text) if c.strip()]


def is_disabled() -> bool:
    """Honor the ``EC_DAEMON_DISABLE=1`` kill switch."""
    return env_bool("EC_DAEMON_DISABLE", default=False)


_POISON_MARKERS = (
    "getcwd",            # EC: Unix_error(ENOENT, "getcwd", "") — cwd deleted
    "closed stdout",     # daemon: EC subprocess died mid-handshake
    "closed stderr",
    "fatal error",       # EC OCaml fatal exception
    "unix_error",
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

    # -----------------------------------------------------------------
    # State (how many tactics the daemon has replayed)
    # -----------------------------------------------------------------

    def _load_state(self) -> dict:
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_state(self, state: dict) -> None:
        try:
            self._state_path.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def invalidate(self) -> None:
        """Close the daemon session (best effort) and drop state file.
        Call on ``-start`` / ``-prev`` / any operation that rewinds
        or resets committed history."""
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

        Replay audit 2026-04-29: this exact stale-socket case caused
        all 5 verified-clean lemma replays to show 0 emits across
        every daemon-dependent block (AUTO-PIVOT-VERIFIED,
        AUTO-PIVOT-CALL-READY, AUTO-CALL-SUGGEST,
        AUTO-BRIDGE-SUGGEST, AUTO-REWRITE-PROBE). The socket file
        was a week old; `os.path.exists()` returned True so we
        skipped spawning, then connect/list_sessions failed silently.
        """
        if self._client is not None:
            try:
                self._client.list_sessions()
                return self._client
            except Exception:
                self._client = None
        # Probe-and-respawn on stale socket: socket file present but
        # nothing listening. connect_ex returns 0 on success, errno
        # otherwise (typically ECONNREFUSED for orphan socket files).
        if os.path.exists(self.socket_path):
            try:
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                probe.settimeout(2)
                rc = probe.connect_ex(self.socket_path)
                probe.close()
            except Exception:
                rc = -1
            if rc != 0:
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
        if not os.path.exists(self.socket_path):
            if not self._spawn_daemon():
                return None
        cli = ECDaemonClient(self.socket_path)
        try:
            cli.list_sessions()
        except Exception:
            return None
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

    def _sync_to(self, file_path: Path, lemma_name: str,
                 target_tactics: list[str]) -> bool:
        """Ensure the daemon session has exactly ``target_tactics``
        committed. Re-opens and replays from scratch if needed.
        Returns ``True`` on success."""
        self.last_error = ""
        cli = self._ensure_daemon()
        if cli is None:
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
                # Daemon went past our target — EC has no undo, so
                # we must reopen and replay.
                need_reopen = True

        if need_reopen:
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
                        return False
                else:
                    self.last_error = (
                        f"open_session failed for {file_path.name}:{lemma_name}: {exc}"
                    )
                    return False
            cached_count = 0

        # Commit any missing tactics from ``cached_count`` up to target.
        if cached_count < len(target_tactics):
            new_tactics = target_tactics[cached_count:]
            for tac in new_tactics:
                try:
                    r = cli.commit(self._session_id, tac)
                except Exception as exc:
                    self.last_error = f"replay commit raised for {tac!r}: {exc}"
                    self._client = None
                    return False
                if not r.get("accepted"):
                    # Committed history should replay cleanly; if not,
                    # something is off — surrender to subprocess.
                    error = r.get("error") or r.get("raw_output") or ""
                    self.last_error = (
                        f"replay rejected committed tactic {tac!r}: "
                        f"{str(error).strip()[:500]}"
                    )
                    return False

        self._save_state({
            "session_id": self._session_id,
            "committed_count": len(target_tactics),
            "file_path": str(file_path.resolve()),
            "lemma_name": lemma_name,
            "socket_path": self.socket_path,
        })
        return True

    def try_commit_latest(self, file_path: Path, lemma_name: str,
                          all_tactics: list[str]) -> Optional[dict]:
        """Sync daemon to ``all_tactics[:-1]``, commit
        ``all_tactics[-1]``. Returns a dict with ``post_raw`` /
        ``accepted`` / ``goal_after`` / ``error`` / ``no_progress``,
        or ``None`` on any failure.

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
            r = cli.commit(self._session_id, all_tactics[-1])
        except Exception:
            self._client = None
            return None

        accepted = bool(r.get("accepted", False))
        if accepted:
            state = self._load_state()
            state["committed_count"] = len(all_tactics)
            self._save_state(state)
        return {
            "post_raw": r.get("raw_output", "") or "",
            "accepted": accepted,
            "goal_after": r.get("goal_after", {}),
            "error": r.get("error"),
            "no_progress": bool(r.get("no_progress", False)),
        }

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
            return None
        if not isinstance(r, dict):
            return None
        return r.get("raw") or None
