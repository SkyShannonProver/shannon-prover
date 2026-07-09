"""Tests for scripts/run_queue.sh — the sequential run-queue launcher.

Covers the contract that replaced the hand-rolled pgrep-polling chain
launchers: strict sequential execution, null-glob-safe session-dir wipe
(zero/one/many matches), and the explicit PID-wait path.
"""

import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_queue.sh"


def run_queue(tmp_path, lines, *args, queue_name="queue.txt"):
    queue = tmp_path / queue_name
    queue.write_text("\n".join(lines) + "\n")
    proc = subprocess.run(
        ["bash", str(SCRIPT), "--worktree", str(tmp_path), *args, str(queue)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    log = tmp_path / f"{queue_name}.out"
    return proc, log.read_text() if log.exists() else ""


def test_sequential_execution_order(tmp_path):
    lines = [
        "# comment line",
        "",
        "echo start1 >> order.txt; sleep 0.3; echo end1 >> order.txt",
        "echo start2 >> order.txt",
    ]
    proc, log = run_queue(tmp_path, lines)
    assert proc.returncode == 0, proc.stderr
    order = (tmp_path / "order.txt").read_text().split()
    assert order == ["start1", "end1", "start2"]
    assert "step 1/2 START" in log and "step 2/2 EXIT rc=0" in log
    assert "queue done: overall_rc=0" in log


@pytest.mark.parametrize("n_dirs", [0, 1, 3])
def test_session_wipe_zero_one_many(tmp_path, n_dirs):
    for i in range(n_dirs):
        d = tmp_path / f".ec_session_prover_tree_0_{i}"
        d.mkdir()
        (d / "stale.txt").write_text("stale")
    survivor = tmp_path / ".ec_session_other"
    survivor.mkdir()

    proc, log = run_queue(tmp_path, ["true"])
    # Zero matches must not abort the queue (the zsh null-glob trap).
    assert proc.returncode == 0, proc.stderr
    assert not list(tmp_path.glob(".ec_session_prover_tree_*"))
    assert survivor.is_dir()
    assert "wiped stale .ec_session_prover_tree_*" in log


def test_wipe_runs_between_steps(tmp_path):
    lines = [
        "mkdir .ec_session_prover_tree_made_by_step1",
        "test ! -d .ec_session_prover_tree_made_by_step1 && touch step2_saw_clean",
    ]
    proc, _ = run_queue(tmp_path, lines)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "step2_saw_clean").exists()


def test_no_wipe_flag(tmp_path):
    stale = tmp_path / ".ec_session_prover_tree_keep"
    stale.mkdir()
    proc, _ = run_queue(tmp_path, ["true"], "--no-wipe")
    assert proc.returncode == 0, proc.stderr
    assert stale.is_dir()


def spawn_detached_sleeper(seconds):
    """Start a sleep that is NOT our child (orphaned to launchd/init).

    A plain Popen child would become a zombie after exit until we reap it,
    and `kill -0` succeeds on zombies — the queue would (correctly) keep
    waiting while the test held the zombie. Real pre-existing runs are
    reaped by their own shells, so model that.
    """
    out = subprocess.run(
        ["bash", "-c", f"sleep {seconds} >/dev/null 2>&1 & echo $!"],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(out.stdout.strip())


def test_wait_pid_blocks_until_exit(tmp_path):
    pid = spawn_detached_sleeper(2)
    t0 = time.monotonic()
    proc, log = run_queue(
        tmp_path,
        ["touch ran_after_wait"],
        "--wait-pid", str(pid), "--poll", "1",
    )
    elapsed = time.monotonic() - t0
    assert proc.returncode == 0, proc.stderr
    assert elapsed >= 1.5, "queue returned before the waited PID exited"
    assert (tmp_path / "ran_after_wait").exists()
    assert f"waiting for pre-existing pid {pid}" in log
    assert f"pid {pid} has exited" in log


def test_wait_pidfile(tmp_path):
    pid = spawn_detached_sleeper(1.5)
    pidfile = tmp_path / "run.pid"
    pidfile.write_text(f"{pid}\n")
    proc, log = run_queue(
        tmp_path,
        ["touch ran_after_wait"],
        "--wait-pidfile", str(pidfile), "--poll", "1",
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "ran_after_wait").exists()
    assert f"pid {pid} has exited" in log


def test_wait_pid_already_exited_returns_promptly(tmp_path):
    dead = subprocess.Popen(["true"])
    dead.wait()
    t0 = time.monotonic()
    proc, _ = run_queue(
        tmp_path, ["touch ran"], "--wait-pid", str(dead.pid), "--poll", "30"
    )
    assert proc.returncode == 0, proc.stderr
    assert time.monotonic() - t0 < 10
    assert (tmp_path / "ran").exists()


def test_failure_logged_and_queue_continues(tmp_path):
    proc, log = run_queue(tmp_path, ["exit 3", "touch second_ran"])
    assert proc.returncode == 1
    assert (tmp_path / "second_ran").exists()
    assert "step 1/2 EXIT rc=3" in log
    assert "queue done: overall_rc=1" in log


def test_stop_on_error_aborts(tmp_path):
    proc, log = run_queue(
        tmp_path, ["exit 3", "touch second_ran"], "--stop-on-error"
    )
    assert proc.returncode == 3
    assert not (tmp_path / "second_ran").exists()
    assert "queue ABORTED at step 1/2" in log


def test_per_step_env_override_and_own_redirect(tmp_path):
    lines = [
        "WHY3EC_SOCKET=/tmp/why3ec_test_a.sock sh -c 'echo $WHY3EC_SOCKET' > step1.log 2>&1",
    ]
    proc, log = run_queue(tmp_path, lines)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "step1.log").read_text().strip() == "/tmp/why3ec_test_a.sock"
    # Redirected step output must not leak into the queue log.
    assert "/tmp/why3ec_test_a.sock" not in log.replace(
        "WHY3EC_SOCKET=/tmp/why3ec_test_a.sock", ""
    )


def test_empty_queue_is_an_error(tmp_path):
    proc, _ = run_queue(tmp_path, ["# only a comment"])
    assert proc.returncode == 2
    assert "no runnable lines" in proc.stderr


def test_bad_pid_rejected(tmp_path):
    proc, _ = run_queue(tmp_path, ["true"], "--wait-pid", "not-a-pid")
    assert proc.returncode == 2
    assert "numeric" in proc.stderr
