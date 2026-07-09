#!/usr/bin/env python3
"""Minimal Python client for ec_daemon.

Usage:

    from ec_daemon_client import ECDaemonClient
    with ECDaemonClient() as cli:
        goal = cli.open_session("my_sess", "/path/file.ec", ["-I", "..."], "lemma_foo")
        r = cli.commit("my_sess", "proc.")
        t = cli.try_tactic("my_sess", "apply some_lemma.")
        cli.close_session("my_sess")

Each call is synchronous. Connections are pooled lazily; each call
opens+closes a socket (simple, cheap locally).
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any, Optional

SOCKET_PATH_DEFAULT = "/tmp/ec_daemon.sock"


class ECDaemonError(RuntimeError):
    pass


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
    def __init__(self, socket_path: str = SOCKET_PATH_DEFAULT):
        self.socket_path = socket_path

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
        raise ECDaemonError(resp.get("error", "unknown"))

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

    def commit(self, session_id: str, tactic: str, timeout: float = 120.0) -> dict:
        return self._call("commit", session_id=session_id,
                          params={"tactic": tactic}, timeout=timeout)

    def try_tactic(self, session_id: str, tactic: str,
                   timeout: float = 120.0) -> dict:
        return self._call("try_tactic", session_id=session_id,
                          params={"tactic": tactic}, timeout=timeout)

    def batch_try(self, session_id: str, tactics: list[str],
                  timeout: float = 600.0) -> list[dict]:
        return self._call("batch_try", session_id=session_id,
                          params={"tactics": tactics}, timeout=timeout)

    def try_chain(self, session_id: str, tactics: list[str],
                  timeout: float = 600.0) -> dict:
        """Run ``tactics`` as a sequence in one ephemeral EC. Stops at
        the first failure. Returns
        ``{accepted, final_closed, final_goal, steps, failed_at, error}``.
        Unlike ``batch_try`` (which tries each tactic independently),
        this runs them as a chain: step N sees the state after step N-1."""
        return self._call("try_chain", session_id=session_id,
                          params={"tactics": tactics}, timeout=timeout)

    def bridge_probe(self, session_id: str, bridge_stmt: str,
                     timeout: float = 600.0) -> dict:
        """Test bridge economics: is ``bridge_stmt`` (an equality
        claim suitable for ``have -> :``, typically ``Pr[A] = Pr[B]``)
        closeable by a short sim-family closer? Returns
        ``{accepted, closed_by, bridge_size, error}``.

        Use BEFORE committing a ``have ->`` — if the probe says
        ``too_big``, decompose at an intermediate checkpoint (find a
        ``pr_*`` lemma that breaks the bridge into smaller pieces)
        instead of forcing a one-shot ``have ->`` that'll require a
        hand-crafted ``while`` invariant."""
        return self._call("bridge_probe", session_id=session_id,
                          params={"bridge_stmt": bridge_stmt,
                                  "timeout": timeout},
                          timeout=timeout + 30)

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
