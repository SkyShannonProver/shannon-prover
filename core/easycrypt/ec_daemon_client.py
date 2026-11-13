#!/usr/bin/env python3
"""Minimal Python client for ec_daemon.

Usage:

    from core.easycrypt.ec_daemon_client import ECDaemonClient
    with ECDaemonClient() as cli:
        goal = cli.open_session("my_sess", "/path/file.ec", ["/path/theories"], "lemma_foo")
        r = cli.commit("my_sess", "proc.")
        t = cli.try_tactic("my_sess", "apply some_lemma.")
        cli.close_session("my_sess")

``include_dirs`` is a list of directories; the daemon adds the ``-I`` flags.
Each call is synchronous and opens and closes its own socket; there is no
connection pool.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import socket
from pathlib import Path
from typing import Any, Optional


# EasyCrypt's limit on one committed or replayed transaction on the daemon.
# This default is the one owner of the value: the manager passes it to
# session_cli in ``STEP_TIMEOUT_ENV`` and gives the whole commit call a margin
# on top of it (``repl_session.COMMIT_CALL_TIMEOUT_SECONDS``), so direct
# ``session_cli`` use behaves alike.
STEP_TIMEOUT_ENV = "SHANNON_EC_STEP_TIMEOUT"
DEFAULT_STEP_TIMEOUT_SECONDS = 170.0
# The client waits this much longer than the step limit: on a timeout the
# daemon stops EasyCrypt and drops the session before it replies.
_COMMIT_REPLY_SLACK_SECONDS = 15.0


def step_timeout_seconds() -> float:
    """The per-transaction limit from ``STEP_TIMEOUT_ENV``, else the default.

    A value that is not a positive finite number is ignored."""
    raw = os.environ.get(STEP_TIMEOUT_ENV, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_STEP_TIMEOUT_SECONDS
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_STEP_TIMEOUT_SECONDS
    return value


def default_socket_path() -> str:
    """THE one home of the EC-daemon socket default.

    Order: explicit ``EC_DAEMON_SOCKET`` env (the managed prover sets a
    per-run path), else a per-checkout ``/tmp`` path keyed on the current
    working directory. A per-checkout key keeps a reused daemon's cwd equal to
    the live checkout — the old single global ``/tmp/ec_daemon.sock`` let a
    daemon spawned in a later-deleted worktree serve another checkout and
    crash every EC child with ``Unix_error(ENOENT, "getcwd")``.

    Every layer (daemon argparse, this client, DaemonBackend, run-level
    shutdown) must resolve the default through here; five divergent defaults
    were how two processes ended up talking past each other.
    """
    override = os.environ.get("EC_DAEMON_SOCKET", "").strip()
    if override:
        return override
    key = hashlib.sha1(os.path.realpath(os.getcwd()).encode()).hexdigest()[:12]
    return f"/tmp/ec_daemon_{key}.sock"


class ECDaemonError(RuntimeError):
    """A structured error reply. ``kind`` names a failure the daemon reports
    as a class (``"setup_rejected"``), else it is ``None``."""

    def __init__(self, message: object = "", kind: Optional[str] = None) -> None:
        super().__init__(message)
        self.kind = kind


class ECDaemonConnectionLost(ECDaemonError):
    """The daemon dropped the connection without returning a complete response.

    Its request handler crashed mid-RPC — almost always because the EC
    subprocess backing the session died (a heavy ``smt``/``auto`` under resource
    pressure on a large goal). Distinct from a *structured* RPC error so callers
    can RECOVER (respawn the daemon, replay committed history, retry the probe
    once) instead of surfacing a raw socket error to the agent. Subclasses
    ``ECDaemonError`` so existing ``except ECDaemonError`` handlers still catch it.
    """


class ECDaemonClient:
    def __init__(self, socket_path: str = ""):
        self.socket_path = socket_path or default_socket_path()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    # -----------------------------------------------------------------

    def _call(self, method: str, session_id: str = "",
              params: Optional[dict] = None,
              timeout: float = 300.0) -> Any:
        req = {"method": method, "session_id": session_id,
               "params": params or {}}
        payload = (json.dumps(req) + "\n").encode("utf-8")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(self.socket_path)
            sock.sendall(payload)
            # Read until one newline-terminated response
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    # EOF before a full response: the daemon's handler crashed
                    # mid-RPC (its EC subprocess most likely died). Recoverable.
                    raise ECDaemonConnectionLost(
                        f"daemon closed connection mid-response; got {buf!r}"
                    )
                buf += chunk
            line, _ = buf.split(b"\n", 1)
            resp = json.loads(line)
        except (ConnectionError, FileNotFoundError) as e:
            # The daemon is gone (refused / reset / socket vanished) — same
            # recoverable class as a mid-response EOF.
            raise ECDaemonConnectionLost(
                f"daemon connection failed: {e}") from e
        finally:
            sock.close()
        if resp.get("status") == "ok":
            return resp.get("result")
        raise ECDaemonError(resp.get("error", "unknown"), kind=resp.get("kind"))

    # -----------------------------------------------------------------
    # High-level API

    def open_session(self, session_id: str, file_path: str,
                     include_dirs: list[str], lemma_name: str,
                     why3_socket: Optional[str] = None) -> dict:
        return self._call(
            "open_session",
            session_id=session_id,
            params={
                "file_path": str(Path(file_path).resolve()),
                "include_dirs": include_dirs,
                "lemma_name": lemma_name,
                "why3_socket": why3_socket,
            },
            timeout=180.0,
        )

    def close_session(self, session_id: str) -> bool:
        return self._call("close_session", session_id=session_id)

    def list_sessions(self) -> list[str]:
        return self._call("list_sessions")

    def commit(self, session_id: str, tactic: str,
               timeout: Optional[float] = None) -> dict:
        """Commit ``tactic``; EasyCrypt gets ``timeout`` seconds for it
        (default ``step_timeout_seconds()``).

        When EasyCrypt does not finish in time the reply is
        ``{"accepted": False, "timed_out": True, ...}`` and the daemon has
        dropped the session. A daemon that predates the limit ignores it."""
        limit = step_timeout_seconds() if timeout is None else float(timeout)
        return self._call(
            "commit", session_id=session_id,
            params={"tactic": tactic, "timeout": limit},
            timeout=limit + _COMMIT_REPLY_SLACK_SECONDS,
        )

    def rewind(self, session_id: str, keep: int, *, keep_identity: str,
               held_identity: Optional[str] = None,
               require_open_goal: bool = False,
               timeout: float = 120.0) -> dict:
        """Undo the session back to its first ``keep`` committed transactions.

        Returns ``{"rewound": False, "reason"}`` when the daemon refuses
        (nothing changed), else ``{"rewound": True, "kept", "undone",
        "raw_output", "goal_after", "level"}``."""
        return self._call(
            "rewind",
            session_id=session_id,
            params={
                "keep": int(keep),
                "keep_identity": keep_identity,
                "held_identity": held_identity,
                "require_open_goal": bool(require_open_goal),
            },
            timeout=timeout,
        )

    def try_tactic(self, session_id: str, tactic: str,
                   timeout: float = 120.0) -> dict:
        return self._call("try_tactic", session_id=session_id,
                          params={"tactic": tactic}, timeout=timeout)

    def try_chain(self, session_id: str, tactics: list[str],
                  timeout: float = 600.0) -> dict:
        """Run ``tactics`` as a sequence in one ephemeral EC. Stops at
        the first failure. Returns
        ``{accepted, final_closed, final_goal, steps, failed_at, error}``.
        Step N sees the state after step N-1."""
        return self._call("try_chain", session_id=session_id,
                          params={"tactics": tactics}, timeout=timeout)

    def get_goal(self, session_id: str) -> dict:
        return self._call("get_goal", session_id=session_id)

    def adopt_session(self, old_session_id: str, new_session_id: str) -> bool:
        """Rename a live session ``old_session_id`` -> ``new_session_id``.

        The EC process and its in-memory proof state move unchanged; only
        the registry key changes. Worker-death attach uses this so a
        respawned node (new session dir => new derived session id) takes
        over the dead node's live session instead of replaying."""
        return self._call("adopt_session", session_id=old_session_id,
                          params={"new_session_id": new_session_id})

    def session_info(self, session_id: str) -> dict:
        """Registry metadata: {exists, file_path, lemma_name,
        committed_count, ec_alive, idle_seconds}."""
        return self._call("session_info", session_id=session_id)

    def shutdown(self) -> bool:
        return self._call("shutdown")
