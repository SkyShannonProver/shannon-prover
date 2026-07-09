"""Process-lifecycle helpers for cleanly tearing down the prover process tree.

The prover run tree is:

    eval_suite.run / project_driver        (operator-facing entry)
        -> orchestrator   (subprocess)
            -> prover.run  (in-process)
                -> tree worker(s)          (Popen, start_new_session=True)
                    -> claude -p           (same process group as the worker)
                        -> MCP stdio server

Worker subtrees, ``why3server``, and the EasyCrypt daemon are all torn down by
Python ``finally``/``atexit`` blocks (e.g. ``run_tree_prover``'s finally calls
``_terminate_process_tree`` for every node; ``prover.run``'s finally shuts down
the daemon + why3server). The catch: those blocks only run on a *normal* exit,
an exception, or ``SIGINT`` (Ctrl-C → ``KeyboardInterrupt``). They are skipped by

  * the default ``SIGTERM`` action (plain ``kill <pid>``), and
  * a single-PID ``SIGKILL`` (``Popen.kill()``).

When a finally block is skipped, the detached worker groups, ``why3server``, and
``easycrypt -emacs`` children are reparented to PID 1 and survive the run — the
"dozens of orphaned why3server / ec_daemon" symptom. These helpers close that:

  * :func:`install_terminal_signal_handlers` turns ``SIGTERM`` into a normal
    ``KeyboardInterrupt`` so the existing cleanup paths run on ``kill <pid>``.
  * :func:`terminate_subprocess_tree` stops a spawned child by its process
    *group* with a grace window, so the child's OWN finally blocks (which reap
    its detached grandchildren) get to run before we escalate to ``SIGKILL``.

Note: we deliberately do NOT install a ``SIGHUP`` handler. Long runs are started
under ``nohup`` (which sets ``SIGHUP`` to ignore so a closed terminal does not
kill them); re-handling ``SIGHUP`` here would undo that.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Optional

_HANDLERS_INSTALLED = False

# Env var naming the file where the orchestrator records each tree worker's
# process-group id, so a supervisor that had to SIGKILL a *wedged* orchestrator
# (its own cleanup finally never ran) can still reap the detached worker groups.
WORKER_PGID_MANIFEST_ENV = "SHANNON_WORKER_PGID_MANIFEST"


def install_terminal_signal_handlers() -> bool:
    """Translate ``SIGTERM`` into ``KeyboardInterrupt`` in the main thread.

    With this installed, ``kill <pid>`` on a long-running entry point (driver,
    suite, orchestrator) unwinds the same ``finally``/``except KeyboardInterrupt``
    cleanup paths that Ctrl-C already triggers, instead of terminating abruptly
    and orphaning the worker/why3server/daemon subtree.

    Idempotent. Main-thread only — returns ``False`` (leaving the default
    disposition) off the main thread or on platforms where the signal cannot be
    installed, so callers/tests never crash for trying.
    """
    global _HANDLERS_INSTALLED
    if _HANDLERS_INSTALLED:
        return True

    def _raise_keyboard_interrupt(signum, _frame):  # pragma: no cover - trivial
        raise KeyboardInterrupt(f"received signal {signum}")

    try:
        signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    except (ValueError, OSError):
        # ValueError: not the main thread. OSError: unsupported platform.
        return False

    _HANDLERS_INSTALLED = True
    return True


def terminate_subprocess_tree(
    proc: subprocess.Popen,
    *,
    grace_seconds: float = 30.0,
) -> None:
    """Cooperatively stop a child started with ``start_new_session=True``.

    Sends ``SIGTERM`` to the child's process *group* — so the child's own
    signal handler / ``finally`` blocks run and reap ITS detached grandchildren
    (tree workers, claude, MCP, why3server, daemon) — waits up to
    ``grace_seconds`` for it to exit, then escalates to ``SIGKILL`` of the group.

    Falls back to signalling the single PID where process groups are
    unavailable (non-POSIX, or the child was not a session leader). Safe to call
    on an already-exited process (no-op).

    This is the entry-to-orchestrator analogue of
    ``workflow.progress._terminate_process_tree`` (which the orchestrator uses
    internally to reap its tree workers); kept here so the operator-facing
    drivers do not have to import the heavy ``progress`` module.
    """
    if proc.poll() is not None:
        return

    pgid: Optional[int] = None
    try:
        pgid = os.getpgid(proc.pid)
    except (AttributeError, ProcessLookupError, PermissionError, OSError):
        pgid = None

    def _signal_group_or_proc(sig: int) -> None:
        if pgid is not None:
            try:
                os.killpg(pgid, sig)
                return
            except ProcessLookupError:
                return
            except (PermissionError, OSError):
                pass
        try:
            proc.send_signal(sig)
        except (ProcessLookupError, OSError):
            pass

    _signal_group_or_proc(signal.SIGTERM)
    try:
        proc.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass

    _signal_group_or_proc(signal.SIGKILL)
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        return


def terminate_pgid_bounded(pid: int, *, grace_seconds: float = 3.0) -> None:
    """Tear down a detached session-leader process we hold only a PID for.

    For a child we do NOT have a ``Popen`` handle on — e.g. the EasyCrypt daemon,
    known only by the PID in its ``<socket>.pid`` file — this signals its process
    *group* with ``SIGTERM`` (so it reaps the ``easycrypt -emacs`` / ``why3server``
    children it leads), polls up to ``grace_seconds`` via ``os.kill(pid, 0)``,
    then escalates to ``SIGKILL``. The poll is BOUNDED so a wedged daemon cannot
    block run-level cleanup. Use :func:`terminate_subprocess_tree` instead when a
    ``Popen`` handle is available.
    """
    try:
        pgid: Optional[int] = os.getpgid(pid)
    except (ProcessLookupError, OSError):
        pgid = None

    def _sig(sig: int) -> None:
        try:
            if pgid is not None:
                os.killpg(pgid, sig)
            else:
                os.kill(pid, sig)
        except (ProcessLookupError, OSError):
            pass

    _sig(signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return  # exited within the grace window
        time.sleep(0.1)
    _sig(signal.SIGKILL)  # still alive after grace


def record_worker_pgid(manifest_path: Optional[str], pid: int) -> None:
    """Append a spawned worker's process-group id to the manifest (best-effort).

    Called by the orchestrator as each tree worker is spawned. The manifest is
    the backstop for the one case the in-process cleanup cannot cover: the
    orchestrator itself getting SIGKILL'd / OOM-killed before its reaping
    ``finally`` runs. No-op when no manifest path is configured.
    """
    if not manifest_path:
        return
    try:
        pgid = os.getpgid(pid)
    except (AttributeError, ProcessLookupError, OSError):
        pgid = pid
    try:
        with open(manifest_path, "a", encoding="utf-8") as fh:
            fh.write(f"{pgid}\n")
    except OSError:
        pass


def reap_worker_pgid_manifest(
    manifest_path: Optional[str],
    *,
    grace_seconds: float = 8.0,
) -> int:
    """Kill every process group listed in a worker-PGID manifest, then delete it.

    Backstop reaping for when a supervisor had to SIGKILL a wedged orchestrator
    whose own ``finally`` never reaped its detached worker groups. SIGTERM each
    recorded group, wait ``grace_seconds``, SIGKILL survivors. A group that is
    already gone is skipped (its leader pid no longer resolves), which keeps the
    common case — orchestrator exited cleanly and self-reaped — a safe no-op.
    Returns the number of groups that were still alive when first signalled.

    Call this ONLY after the orchestrator has exited (cleanly or killed): a live
    group whose leader pid was recycled is the only PID-reuse risk, and it is
    bounded by signalling only groups whose leader still resolves at call time.
    """
    if not manifest_path or not os.path.exists(manifest_path):
        return 0
    pgids: list[int] = []
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        pgids.append(int(line))
                    except ValueError:
                        pass
    except OSError:
        pgids = []

    def _alive(pgid: int) -> bool:
        try:
            os.killpg(pgid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False

    live = [p for p in dict.fromkeys(pgids) if _alive(p)]
    for pgid in live:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
    if live:
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if not any(_alive(p) for p in live):
                break
            time.sleep(0.2)
        for pgid in live:
            if _alive(pgid):
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
    try:
        os.unlink(manifest_path)
    except OSError:
        pass
    return len(live)
