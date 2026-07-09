"""Worker stderr capture — a hard prover-worker death (no `result` event) must
leave a forensic trail.

The tree worker is spawned with stderr=PIPE, but the supervisor previously read
only stdout, so the pipe was never drained: a hard-death traceback (OOM /
SIGKILL / uncaught exception) was lost when the proc was reaped — which is why
the CBC_upto 2026-06-25 worker deaths could not be pinned to a physical cause —
AND a worker writing >~64KB to stderr would deadlock on a full pipe. The tracker
now drains stderr every poll into a bounded tail and persists it on exit.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.progress import _TreeProverTracker  # noqa: E402


def _run_until_finished(tracker, *, max_iters=500, sleep=0.01):
    for _ in range(max_iters):
        tracker.poll_lines()
        if tracker.finished:
            return True
        time.sleep(sleep)
    return False


def _tracker(proc, node_mem: Path) -> "_TreeProverTracker":
    return _TreeProverTracker(
        proc, "Tree-0.0", str(node_mem.parent),
        allowed_node_memory_dirs=[str(node_mem)],
    )


def test_stderr_persisted_with_exit_code_on_hard_death(tmp_path):
    """A worker that writes a traceback to stderr and dies non-zero leaves its
    stderr tail + exit code in node_memory/<tree>/worker_stderr.log."""
    nm = tmp_path / "node_memory" / "Tree_0_0"
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.stderr.write('Traceback (most recent call last):\\n"
         "FATAL boom in the worker\\n'); sys.stderr.flush(); sys.exit(139)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    tr = _tracker(proc, nm)
    assert _run_until_finished(tr), "worker should finish, not hang"
    log = nm / "worker_stderr.log"
    assert log.exists(), "worker_stderr.log must be written on exit"
    txt = log.read_text(encoding="utf-8")
    assert "FATAL boom in the worker" in txt        # the captured stderr
    assert "returncode=139" in txt                   # the exit code (death cause)
    assert "Tree-0.0" in txt                          # the node it belongs to


def test_large_stderr_does_not_deadlock_and_tail_is_kept(tmp_path):
    """A worker writing >64KB to stderr must NOT block on a full pipe (the drain
    keeps it flowing); the bounded tail keeps the END of the output."""
    nm = tmp_path / "node_memory" / "Tree_0_0"
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.stderr.write('X'*(256*1024)); "
         "sys.stderr.write('\\nTAILMARKER_END\\n'); sys.exit(0)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    tr = _tracker(proc, nm)
    assert _run_until_finished(tr), "256KB-stderr worker must not deadlock"
    txt = (nm / "worker_stderr.log").read_text(encoding="utf-8")
    assert "TAILMARKER_END" in txt                   # bounded tail keeps the end
    # tail is bounded (we don't store unbounded stderr)
    assert len(tr._stderr_tail) <= _TreeProverTracker._STDERR_TAIL_MAX


def test_clean_worker_still_persists_an_empty_log(tmp_path):
    """Always-persist: even a clean worker that wrote nothing to stderr leaves a
    log (header + empty body), so its absence unambiguously means 'never ran'."""
    nm = tmp_path / "node_memory" / "Tree_0_0"
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    tr = _tracker(proc, nm)
    assert _run_until_finished(tr)
    log = nm / "worker_stderr.log"
    assert log.exists()
    assert "returncode=0" in log.read_text(encoding="utf-8")
