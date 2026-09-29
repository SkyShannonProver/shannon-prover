#!/usr/bin/env python3
"""Regression test for DaemonBackend self-healing against a poisoned daemon.

A daemon spawned in a checkout/worktree that is later deleted keeps its socket
alive but forks every EC subprocess with a dead cwd, so EC crashes with
``Unix_error(ENOENT, "getcwd")``. The socket-file staleness probe in
``_ensure_daemon`` cannot see this (the listener is alive), so before the fix a
standalone backend that reached such a daemon silently lost every
daemon-verified producer (bridge_options / call_site_options /
rewrite_candidates) at deep proof states.

Two defenses are tested:
  1. ``_default_socket`` keys the socket on the live checkout, so a daemon's
     cwd always equals a checkout that exists (no cross-checkout sharing).
  2. If a poisoned daemon is reached anyway, ``_sync_to`` detects the poison
     error, discards the daemon, respawns a fresh one (whose cwd is the live
     checkout), and retries the open once.

Requires `easycrypt` on PATH via the opam switch (like test_ec_daemon.py).
Run with: python3 tests/test_daemon_backend_poison_recovery.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
EC_DIR = REPO_ROOT / "core" / "easycrypt"

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)
from core.easycrypt.daemon_backend import DaemonBackend, _default_socket, _is_poison_error  # noqa: E402
from core.easycrypt.ec_daemon_client import ECDaemonClient  # noqa: E402

MINIMAL_EC = """require import AllCore.

lemma foo (x : int) : x = x.
proof.
admit.
qed.
"""


def test_default_socket_is_per_checkout():
    """Two different checkouts (cwds) must map to different default sockets,
    and EC_DAEMON_SOCKET must override."""
    saved = os.environ.pop("EC_DAEMON_SOCKET", None)
    try:
        cwd = os.getcwd()
        d1 = tempfile.mkdtemp()
        d2 = tempfile.mkdtemp()
        try:
            os.chdir(d1)
            s1 = _default_socket()
            os.chdir(d2)
            s2 = _default_socket()
        finally:
            os.chdir(cwd)
        assert s1 != s2, f"distinct checkouts shared a socket: {s1}"
        assert s1.startswith("/tmp/ec_daemon_") and s1.endswith(".sock")
        os.environ["EC_DAEMON_SOCKET"] = "/tmp/explicit_override.sock"
        assert _default_socket() == "/tmp/explicit_override.sock"
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)
        print("  ✓ default_socket_is_per_checkout")
    finally:
        os.environ.pop("EC_DAEMON_SOCKET", None)
        if saved is not None:
            os.environ["EC_DAEMON_SOCKET"] = saved


def test_is_poison_error_markers():
    assert _is_poison_error(Exception('Unix_error(ENOENT, "getcwd", "")'))
    assert _is_poison_error(Exception("EC subprocess closed stdout unexpectedly"))
    assert _is_poison_error(Exception("Fatal error: exception ..."))
    assert not _is_poison_error(Exception("unknown lemma foo"))
    assert not _is_poison_error(Exception("apply: cannot unify"))
    print("  ✓ is_poison_error_markers")


def _spawn_poisoned_daemon(sock: str) -> tuple[subprocess.Popen, str]:
    """Spawn a daemon whose cwd is a directory we then delete, so every EC it
    forks inherits a dead cwd. Returns (proc, deleted_dir)."""
    poison_cwd = tempfile.mkdtemp(prefix="poison_cwd_")
    try:
        os.unlink(sock)
    except FileNotFoundError:
        pass
    proc = subprocess.Popen(
        [sys.executable, str(EC_DIR / "ec_daemon.py"),
         "--socket", sock, "--log-level", "WARNING"],
        cwd=poison_cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(60):
        if os.path.exists(sock):
            break
        time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError("poison daemon did not create socket")
    # Poison it: delete the daemon's cwd. The live socket survives.
    shutil.rmtree(poison_cwd, ignore_errors=True)
    return proc, poison_cwd


def test_sync_recovers_from_poisoned_daemon():
    """A poisoned daemon is reachable on the socket; DaemonBackend must detect
    the poison, respawn a fresh daemon, and commit successfully."""
    sock = f"/tmp/ec_daemon_test_{uuid.uuid4().hex[:8]}.sock"
    proc, poison_cwd = _spawn_poisoned_daemon(sock)
    session_dir = Path(tempfile.mkdtemp(prefix="poison_sess_"))
    # EC file lives outside the deleted cwd so it survives + has an abs path.
    fd, ec_name = tempfile.mkstemp(suffix=".ec")
    os.close(fd)
    ec_file = Path(ec_name)
    ec_file.write_text(MINIMAL_EC)
    respawn_pid = None
    try:
        # Sanity: the daemon really is poisoned — a direct open crashes EC.
        poisoned = False
        try:
            cli = ECDaemonClient(sock)
            cli.open_session("probe", str(ec_file),
                             ["easycrypt-src/theories"], "foo")
        except Exception as exc:  # noqa: BLE001
            poisoned = _is_poison_error(exc)
        assert poisoned, "expected the deleted-cwd daemon to crash EC on open"

        # The fix: backend detects poison, respawns, retries, and commits.
        be = DaemonBackend(session_dir, ["easycrypt-src/theories"],
                           socket_path=sock)
        out = be.try_commit_latest(ec_file, "foo", ["trivial."])
        assert out is not None, f"recovery failed: last_error={be.last_error!r}"
        assert out["accepted"], f"commit not accepted: {out}"
        assert out["goal_after"].get("is_closed"), out

        # A fresh daemon now owns the socket; its cwd is the live checkout.
        new_cli = ECDaemonClient(sock)
        sessions = new_cli.list_sessions()
        assert isinstance(sessions, list)
        try:
            new_cli.shutdown()
        except Exception:
            pass
        print("  ✓ sync_recovers_from_poisoned_daemon")
    finally:
        # Kill the orphaned poisoned daemon and any respawn.
        for p in (proc,):
            try:
                p.kill()
                p.wait(timeout=3)
            except Exception:
                pass
        # Any daemon still bound to the socket (the respawn): shut it down.
        try:
            ECDaemonClient(sock).shutdown()
        except Exception:
            pass
        for path in (sock, sock + ".spawn_lock"):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            except Exception:
                pass
        ec_file.unlink(missing_ok=True)
        shutil.rmtree(session_dir, ignore_errors=True)
        shutil.rmtree(poison_cwd, ignore_errors=True)
        _ = respawn_pid


TESTS = [
    test_default_socket_is_per_checkout,
    test_is_poison_error_markers,
    test_sync_recovers_from_poisoned_daemon,
]


def main():
    print("Running daemon_backend poison-recovery tests")
    print("  (requires `easycrypt` on PATH via opam switch)")
    print()
    failed = 0
    for fn in TESTS:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {fn.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    print()
    print(f"{len(TESTS) - failed}/{len(TESTS)} tests passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
