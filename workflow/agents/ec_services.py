"""Run-scoped OS services for the prover: why3server + EC-daemon lifecycle.

Extracted verbatim from workflow/agents/prover.py (audit: the ~450-line
socket/process-management block fused around run()). Owns the per-run
why3server process handle and socket-path policy, the EC-daemon socket
configuration/teardown, and the opam environment + scratch-path helpers
both prover and prover_writeback consume. prover.py re-exports every name
so external callers and tests are unchanged.
"""
from __future__ import annotations

import atexit
import logging
import shutil
import signal
import socket
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("workflow.agents.prover")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AF_UNIX_SOCKET_PATH_LIMIT = 100
_EC_DAEMON_SOCKET_NAME_TEMPLATE = "ec_000000000000.sock"

# Run-scoped why3server state: one process per orchestrator run, torn down
# by _shutdown_run_why3server / atexit.
_RUN_WHY3_PROC: Optional[subprocess.Popen] = None
_RUN_WHY3_SOCKET: Optional[str] = None
_WHY3_ATEXIT_REGISTERED = False


def _is_why3server_responsive(socket_path: str, timeout: float = 1.0) -> bool:
    """Probe a Unix-domain socket to confirm why3server is actually
    accepting connections.

    The previous reuse logic checked only ``os.path.exists(socket_path)``
    plus ``pgrep -f why3server``. Both are satisfied even when the
    socket inode is stale (from a dead pid in a prior session) — the
    file lingers, and at least one why3server is on the box but
    listening on a different socket. EC's ``-server <stale_sock>``
    silently falls through to "start a new server" inside the EC
    process, which is exactly the path the OS sandbox blocks via
    ``nice()``. A connect probe distinguishes alive from stale:
    SOCK_STREAM ``connect`` only succeeds when the kernel finds the
    listener bound to that path.
    """
    import socket as _socket
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect(socket_path)
        finally:
            s.close()
        return True
    except Exception:
        return False


def _cleanup_stale_why3server(socket_path: str) -> None:
    """Kill the stale why3server bound to ``socket_path`` and remove the file.

    Narrowed from a global ``pkill -f why3server``: each run now owns exactly
    one server on a per-run socket (see :func:`_configure_run_why3_socket`) and
    tears it down at the end (see :func:`_shutdown_run_why3server`), so the
    accumulation that motivated the box-wide kill (44 orphans observed on the
    dev box 2026-05-03) no longer happens through this path. A box-wide kill is
    now actively harmful — it murders concurrent eval arms' servers, which was
    one source of the L1-vs-L4 shared-``/tmp/why3ec.sock`` timing confound. We
    therefore match only the server whose command line carries THIS socket
    path. (Box-wide orphan cleanup, if ever needed, is a manual
    ``pkill -f why3server``.)
    """
    try:
        subprocess.run(
            ["pkill", "-f", socket_path],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass
    if os.path.exists(socket_path):
        try:
            os.unlink(socket_path)
        except Exception:
            pass


def _shutdown_run_why3server() -> None:
    """Tear down the why3server this run started (idempotent).

    Terminates the tracked process by signal (it is a direct child, not a
    process-group leader), waits briefly, escalates to kill, then unlinks the
    per-run socket. Registered with ``atexit`` and also called from
    ``run()``'s finally so the server dies on normal completion, on a
    ``SIGTERM``-turned-``KeyboardInterrupt`` (see
    ``workflow.proc_lifecycle``), and on interpreter exit — never lingering for
    the next run's startup pkill to mop up.
    """
    global _RUN_WHY3_PROC, _RUN_WHY3_SOCKET
    proc = _RUN_WHY3_PROC
    sock = _RUN_WHY3_SOCKET
    _RUN_WHY3_PROC = None
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        except (ProcessLookupError, OSError):
            pass
    if sock and os.path.exists(sock):
        try:
            os.unlink(sock)
        except OSError:
            pass


def _resolve_why3server_binary(env: dict) -> Optional[str]:
    """Locate the why3server executable.

    why3server ships under the opam switch's lib dir, NOT bin —
    `${OPAM_SWITCH_PREFIX}/lib/why3/why3server`. It's not on PATH
    after `opam env`, so a bare `["why3server", ...]` Popen invocation
    fails with FileNotFoundError. (Observed on dev box 2026-05-03 —
    the original ``_ensure_why3server`` only ever succeeded on the
    "already running" branch because some prior easycrypt subprocess
    had spawned why3server itself; this code never actually started
    one. Once the persistent socket goes stale and we try to start a
    fresh server, the bare lookup fails.)
    """
    prefix = env.get("OPAM_SWITCH_PREFIX", "")
    if prefix:
        candidate = os.path.join(prefix, "lib", "why3", "why3server")
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    home = os.path.expanduser("~")
    fallback = os.path.join(home, ".opam", "easycrypt", "lib", "why3", "why3server")
    if os.path.exists(fallback) and os.access(fallback, os.X_OK):
        return fallback
    return None


def _ensure_why3server(*, force_restart: bool = False) -> Optional[str]:
    """Ensure why3server is running, responsive, and return the socket
    path.

    EasyCrypt's smt() needs why3server. In sandboxed environments, EC
    can't start it (``nice()`` syscall blocked). We pre-start it here
    and pass the socket via ``-server`` to all EC invocations.

    The check is now connect-probe based, not just file/pgrep based,
    so a stale socket from a prior session does not get reused. If
    the existing socket is unresponsive we kill all why3server
    processes and start a fresh one.

    ``force_restart=True`` skips the responsiveness probe and always
    cleans up + restarts. Use from a verify-retry path when EC has
    just reported "cannot start & connect to why3server" — that
    error means something has died since the last health check.

    Returns the socket path if a responsive server is running, None
    otherwise.
    """
    socket_path = os.environ.get("WHY3EC_SOCKET", "/tmp/why3ec.sock")

    if not force_restart and os.path.exists(socket_path):
        if _is_why3server_responsive(socket_path):
            logger.info("why3server already running on %s", socket_path)
            return socket_path
        logger.info(
            "why3server socket %s exists but is unresponsive; "
            "cleaning up before restart", socket_path,
        )
    if force_restart or os.path.exists(socket_path):
        _cleanup_stale_why3server(socket_path)

    try:
        env = _get_opam_env()
        binary = _resolve_why3server_binary(env)
        if binary is None:
            logger.warning(
                "why3server binary not found (looked under "
                "$OPAM_SWITCH_PREFIX/lib/why3/ and ~/.opam/easycrypt/lib/why3/)",
            )
            return None
        proc = subprocess.Popen(
            [binary, "--socket", socket_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        # Track this server so run()'s finally / atexit can tear it down
        # instead of leaking it (orphaned-why3server-to-PID-1 was the bulk of
        # the post-run zombie symptom). Register the atexit backstop once.
        global _RUN_WHY3_PROC, _RUN_WHY3_SOCKET, _WHY3_ATEXIT_REGISTERED
        _RUN_WHY3_PROC = proc
        _RUN_WHY3_SOCKET = socket_path
        if not _WHY3_ATEXIT_REGISTERED:
            import atexit
            atexit.register(_shutdown_run_why3server)
            _WHY3_ATEXIT_REGISTERED = True
        # Wait up to ~2s for the server to bind AND respond. Don't
        # short-circuit on "file exists" alone — bind may complete
        # before the listener accepts connections.
        import time as _time
        for _ in range(10):
            _time.sleep(0.2)
            if proc.poll() is not None:
                logger.warning(
                    "why3server exited during startup (rc=%s)", proc.poll(),
                )
                return None
            if (
                os.path.exists(socket_path)
                and _is_why3server_responsive(socket_path)
            ):
                logger.info(
                    "Started why3server on %s (pid=%d)", socket_path, proc.pid,
                )
                return socket_path
        logger.warning(
            "why3server started but never became responsive (pid=%d)",
            proc.pid,
        )
        return None
    except Exception as e:
        logger.warning("Could not start why3server: %s", e)
        return None


def _ec_daemon_socket_path() -> str:
    return os.environ.get("EC_DAEMON_SOCKET", "/tmp/ec_daemon.sock")


def _configure_run_ec_daemon_socket(run_dir: Path) -> str:
    """Use a short daemon socket for this prover run."""
    import hashlib

    digest = hashlib.sha1(str(run_dir.resolve()).encode("utf-8")).hexdigest()[:12]
    socket_name = f"ec_{digest}.sock"
    socket_root = _run_ec_daemon_socket_root(socket_name=socket_name)
    socket_root.mkdir(parents=True, exist_ok=True)
    socket_path = socket_root / socket_name
    os.environ["EC_DAEMON_SOCKET"] = str(socket_path)
    return str(socket_path)


def _configure_run_why3_socket(run_dir: Path) -> str:
    """Point this run's why3server at a per-run socket via ``WHY3EC_SOCKET``.

    Mirrors :func:`_configure_run_ec_daemon_socket`. Without this every run
    (and every concurrent eval arm) shares the default ``/tmp/why3ec.sock``;
    two arms then race for the same server, which is the documented L1-vs-L4
    timing confound. A per-run socket isolates arms and lets cleanup target
    exactly one server. ``os.environ`` propagates to tree workers (their env is
    ``os.environ.copy()``), so ``session_runtime`` / ``daemon_backend`` in the
    worker connect to the same per-run socket. The path stays short (well under
    the AF_UNIX limit), so unlike the EC daemon socket it needs no root search.
    """
    import hashlib

    digest = hashlib.sha1(str(run_dir.resolve()).encode("utf-8")).hexdigest()[:12]
    socket_path = f"/tmp/why3ec_{digest}.sock"
    os.environ["WHY3EC_SOCKET"] = socket_path
    return socket_path


def _ec_daemon_socket_responsive(socket_path: str) -> bool:
    if not os.path.exists(socket_path):
        return False
    try:
        import socket

        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(1.0)
        try:
            return probe.connect_ex(socket_path) == 0
        finally:
            probe.close()
    except Exception:
        return False


def _remove_stale_ec_daemon_socket(socket_path: str) -> None:
    for path in (socket_path, socket_path + ".spawn_lock", socket_path + ".pid"):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning(
                "Could not remove stale EasyCrypt daemon file %s: %s",
                path,
                exc,
            )


def _path_fits_af_unix_socket(path: Path) -> bool:
    return len(os.fsencode(str(path))) < _AF_UNIX_SOCKET_PATH_LIMIT


def _git_common_project_root() -> Optional[Path]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(_PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    common_dir = Path(raw)
    if not common_dir.is_absolute():
        common_dir = (_PROJECT_ROOT / common_dir).resolve()
    else:
        common_dir = common_dir.resolve()
    if common_dir.name != ".git":
        return None
    return common_dir.parent


def _fallback_ec_daemon_socket_root() -> Path:
    import hashlib

    project_key = hashlib.sha1(
        str(_PROJECT_ROOT.resolve()).encode("utf-8"),
    ).hexdigest()[:12]
    return Path("/tmp") / "shannon_ec_daemons" / project_key


def _run_ec_daemon_socket_root(
    *,
    socket_name: str = _EC_DAEMON_SOCKET_NAME_TEMPLATE,
) -> Path:
    candidates = []
    common_root = _git_common_project_root()
    if common_root is not None:
        candidates.append(common_root / "tmp" / "ec_daemons")
    candidates.append(_PROJECT_ROOT / "tmp" / "ec_daemons")
    candidates.append(_fallback_ec_daemon_socket_root())

    seen: set[str] = set()
    for root in candidates:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        if _path_fits_af_unix_socket(root / socket_name):
            return root

    fallback = _fallback_ec_daemon_socket_root()
    logger.warning(
        "Using fallback EasyCrypt daemon socket root despite long path: %s",
        fallback,
    )
    return fallback


def _shutdown_repo_ec_daemons(*, reason: str = "") -> int:
    socket_root = _run_ec_daemon_socket_root()
    if not socket_root.exists():
        return 0
    stopped = 0
    for sock in sorted(socket_root.glob("*.sock")):
        if _shutdown_ec_daemon(reason=reason, socket_path=str(sock)):
            stopped += 1
    for lock in sorted(socket_root.glob("*.sock.spawn_lock")):
        sock = Path(str(lock)[: -len(".spawn_lock")])
        if not sock.exists():
            try:
                lock.unlink()
            except Exception as exc:
                logger.warning(
                    "Could not remove orphan EasyCrypt daemon lock %s: %s",
                    lock,
                    exc,
                )
    return stopped


def _hard_kill_ec_daemon(socket_path: str) -> bool:
    """Force-kill a daemon that ignored cooperative shutdown, via its PID file.

    ``ec_daemon`` writes ``<socket>.pid`` and is a session leader (spawned
    ``start_new_session=True``), so signalling its process group also reaps the
    ``easycrypt -emacs`` children it owns — which a wedged/OOM'd daemon would
    otherwise orphan to PID 1. Only reached after the socket was confirmed
    responsive, so the PID file is current (a dead daemon leaves an
    unresponsive socket and bails earlier), making PID reuse a non-issue.
    Returns True once it has signalled and cleaned up.
    """
    pid_path = socket_path + ".pid"
    try:
        pid = int(Path(pid_path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    # Shared single-PID bounded pgid teardown (the daemon is a session leader we
    # hold only a PID for) — SIGTERM the group, bounded poll, then SIGKILL.
    from workflow.proc_lifecycle import terminate_pgid_bounded

    terminate_pgid_bounded(pid, grace_seconds=3.0)
    _remove_stale_ec_daemon_socket(socket_path)
    return True


def _shutdown_ec_daemon(
    *,
    reason: str = "",
    socket_path: Optional[str] = None,
    wait_seconds: float = 3.0,
) -> bool:
    """Stop the persistent EasyCrypt daemon for a whole prover run.

    The daemon is intentionally detached so short-lived ``session_cli.py``
    calls can share an EasyCrypt subprocess pool. A full prover run creates
    many per-node sessions; leaving that daemon alive after the run lets
    ``easycrypt -emacs`` and ``why3server`` children accumulate across smoke
    tests. Run-level cleanup keeps the fast path without cross-run leaks.
    """
    sock = socket_path or _ec_daemon_socket_path()
    if not os.path.exists(sock):
        return False
    if not _ec_daemon_socket_responsive(sock):
        logger.info("Removing stale EasyCrypt daemon socket at %s", sock)
        _remove_stale_ec_daemon_socket(sock)
        return False

    def _wait_until_stopped() -> bool:
        deadline = time.monotonic() + max(0.0, wait_seconds)
        while time.monotonic() < deadline:
            if not os.path.exists(sock) or not _ec_daemon_socket_responsive(sock):
                _remove_stale_ec_daemon_socket(sock)
                return True
            time.sleep(0.1)
        if not os.path.exists(sock) or not _ec_daemon_socket_responsive(sock):
            _remove_stale_ec_daemon_socket(sock)
            return True
        return False

    try:
        from core.easycrypt.ec_daemon_client import ECDaemonClient

        ECDaemonClient(sock).shutdown()
    except Exception as exc:
        if _wait_until_stopped():
            logger.info(
                "EasyCrypt daemon stopped during shutdown handshake (%s)",
                reason or "cleanup",
            )
            return True
        label = f" ({reason})" if reason else ""
        if _hard_kill_ec_daemon(sock):
            logger.warning(
                "Force-killed EasyCrypt daemon after failed shutdown "
                "handshake%s: %s", label, exc,
            )
            return True
        logger.warning("Failed to shut down EasyCrypt daemon%s: %s", label, exc)
        return False

    if _wait_until_stopped():
        return True
    label = f" ({reason})" if reason else ""
    if _hard_kill_ec_daemon(sock):
        logger.warning("Force-killed unresponsive EasyCrypt daemon%s", label)
        return True
    logger.warning("EasyCrypt daemon stayed responsive after shutdown%s", label)
    return False


def _get_opam_env() -> dict:
    """Get environment with opam variables set for EasyCrypt."""
    from core.easycrypt.ec_env import get_ec_env
    return get_ec_env()


def _workspace_tmp_dir() -> Path:
    """Project-local scratch root used by prover verification helpers."""
    raw = os.environ.get("SHANNON_TMP_DIR", "").strip()
    path = Path(raw).expanduser() if raw else (_PROJECT_ROOT / "artifacts" / "tmp")
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _claude_scratch_path(filename: str) -> Path:
    path = _workspace_tmp_dir() / "claude" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
