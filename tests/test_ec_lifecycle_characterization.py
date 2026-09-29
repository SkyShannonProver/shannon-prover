"""Characterization of the EC ephemeral spawn -> drain -> replay -> teardown
sequence, locked with a pipe-backed FAKE EasyCrypt before the ECSessionLifecycle
refactor (re-audit #3 / docs/refactor_ec_lifecycle_blueprint.md).

The three ephemeral sites (ECSubprocess._try_tactic_fresh, ._try_chain_fresh,
WarmProber.open) currently COPY-PASTE the replay-prefix loop and the bounded
teardown block. Step 1 of #3 extracts those into shared helpers; these goldens
pin the observable control sequence (the lines sent to EC + the teardown
reaping order) so the dedup can be proven behavior-identical without standing up
real EasyCrypt. Real-EC semantic equivalence stays guarded by
test_ec_warm_batch_integration etc.

The fake is INTERACTIVE: it emits a `[N|check]>` prompt at spawn (banner) and one
per stdin write, so the genuine `_eph_read_until_prompt` select()+os.read() loop
runs against a real OS pipe.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import core.easycrypt.ec_daemon as ecd  # noqa: E402
import core.easycrypt.ec_warm_prober as ecw  # noqa: E402
import core.easycrypt.ec_lifecycle as ecl  # noqa: E402


class _FakeECStdout:
    """Only needs fileno() — `_eph_read_until_prompt` reads the raw fd directly."""

    def __init__(self, fd: int):
        self._fd = fd

    def fileno(self) -> int:
        return self._fd


class _FakeECStdin:
    def __init__(self, parent: "_FakeECPipe"):
        self._p = parent
        self.closed = False

    def write(self, data):
        self._p.sent.append(
            data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        )
        self._p._emit_prompt()  # one EC prompt per command, request/response style

    def flush(self):
        pass

    def close(self):
        self.closed = True
        self._p.calls.append("stdin.close")


class _FakeECPipe:
    """Pipe-backed interactive fake `easycrypt -emacs` subprocess.

    Records `sent` (the ordered replay/probe lines) and `calls` (the teardown
    reaping order). `wait_timeouts` makes the first N wait() calls raise
    TimeoutExpired, to drive the bounded SIGKILL/abandon teardown path.
    """

    def __init__(self, *, wait_timeouts: int = 0, goal_text: str = ""):
        self._r, self._w = os.pipe()
        self.stdout = _FakeECStdout(self._r)
        self.stdin = _FakeECStdin(self)
        self.sent: list[str] = []
        self.calls: list = []
        self.returncode = None
        self.pid = 4242
        self._n = 0
        self._goal_text = goal_text
        self._wait_timeouts_remaining = wait_timeouts
        # banner + the prompt the initial drain reads
        os.write(self._w, b"EasyCrypt banner line\n" + self._prompt())

    def _prompt(self) -> bytes:
        p = b"[%d|check]>" % self._n
        self._n += 1
        return p

    def _emit_prompt(self):
        body = (self._goal_text.encode() + b"\n") if self._goal_text else b""
        os.write(self._w, body + self._prompt())

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.calls.append(("wait", timeout))
        if self._wait_timeouts_remaining > 0:
            self._wait_timeouts_remaining -= 1
            raise subprocess.TimeoutExpired(cmd="ec", timeout=timeout)
        if self.returncode is None:
            self.returncode = -15
        return self.returncode

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")
        if self.returncode is None:
            self.returncode = -9

    def close_fds(self):
        for fd in (self._r, self._w):
            try:
                os.close(fd)
            except OSError:
                pass


@pytest.fixture
def fake_spawn(monkeypatch):
    """Patch the shared EasyCrypt spawn owner to mint _FakeECPipe instances."""
    fakes: list[_FakeECPipe] = []
    cfg: dict = {}

    def _spawn(include_dirs, why3_socket, env=None):
        f = _FakeECPipe(**cfg)
        f.spawn_args = (include_dirs, why3_socket, env)
        fakes.append(f)
        return f

    monkeypatch.setattr(ecl, "spawn_emacs_pipe", _spawn, raising=True)
    yield fakes, cfg
    for f in fakes:
        f.close_fds()


def _ec(setup, committed):
    ec = ecd.ECSubprocess(include_dirs=["."], why3_socket=None)
    ec._setup_commands = list(setup)
    ec._committed_tactics = list(committed)
    return ec


SETUP = ["require import AllCore.", "lemma L : true.", "proof."]
COMMITTED = ["move=> x.", "trivial."]


def test_charact_try_tactic_fresh_replay_sequence(fake_spawn):
    """GOLDEN: one spawn, one drain, replay = setup ++ committed ++ normalized
    probe, clean teardown (stdin.close -> terminate -> wait(3.0), no kill)."""
    fakes, _ = fake_spawn
    ec = _ec(SETUP, COMMITTED)

    outcome = ec._try_tactic_fresh("smt()")

    assert len(fakes) == 1
    f = fakes[0]
    # unified argv triple was used (include_dirs, why3_socket, env)
    assert f.spawn_args[0] == ["."] and f.spawn_args[1] is None
    # replay sequence (trailing dot normalized onto the probe)
    assert f.sent == [
        "require import AllCore.\n", "lemma L : true.\n", "proof.\n",
        "move=> x.\n", "trivial.\n", "smt().\n",
    ]
    # bounded teardown, clean path
    assert f.calls == ["stdin.close", "terminate", ("wait", 3.0)]
    assert outcome.accepted is True


def test_charact_teardown_bounded_kill_path(fake_spawn):
    """GOLDEN: when the first wait() times out, teardown escalates to kill +
    a second bounded wait (the §8#6 hardening)."""
    fakes, cfg = fake_spawn
    cfg["wait_timeouts"] = 1
    ec = _ec(SETUP, COMMITTED)

    ec._try_tactic_fresh("smt()")

    f = fakes[0]
    assert f.calls == [
        "stdin.close", "terminate", ("wait", 3.0), "kill", ("wait", 3.0),
    ]


def test_charact_teardown_abandon_path(fake_spawn):
    """GOLDEN: when BOTH waits time out, teardown abandons (no unbounded wait) —
    the loop must not wedge the session lock."""
    fakes, cfg = fake_spawn
    cfg["wait_timeouts"] = 2
    ec = _ec(SETUP, COMMITTED)

    ec._try_tactic_fresh("smt()")

    f = fakes[0]
    assert f.calls == [
        "stdin.close", "terminate", ("wait", 3.0), "kill", ("wait", 3.0),
    ]


# The drain-then-(setup ++ committed) prefix every ephemeral site must replay
# identically — the precondition for extracting one shared _replay_prefix helper.
PREFIX = [
    "require import AllCore.\n", "lemma L : true.\n", "proof.\n",
    "move=> x.\n", "trivial.\n",
]


def test_charact_try_chain_fresh_replay_sequence(fake_spawn):
    """GOLDEN: chain replays the SAME setup++committed prefix, then sends each
    chain tactic; bounded teardown (identical to _try_tactic_fresh)."""
    fakes, _ = fake_spawn
    ec = _ec(SETUP, COMMITTED)

    outcome = ec._try_chain_fresh(["rewrite /=.", "done."])

    f = fakes[0]
    assert f.sent[:5] == PREFIX           # shared prefix
    assert f.sent[5:6] == ["rewrite /=.\n"]  # first chain step always sent
    assert f.calls == ["stdin.close", "terminate", ("wait", 3.0)]
    assert outcome.accepted is True


def test_charact_warm_open_replay_sequence(fake_spawn):
    """GOLDEN: WarmProber.open replays the SAME merged setup++committed prefix.
    After the Step-2 fix, close() uses the shared bounded teardown (no longer the
    divergent bare kill()), so the warm child is reaped like the daemon paths."""
    fakes, _ = fake_spawn
    warm = ecw.WarmProber(include_dirs=["."], why3_socket=None)

    ok = warm.open("dummy.ec", "L", committed_tactics=COMMITTED, setup_commands=SETUP)

    assert ok is True
    f = fakes[0]
    assert f.sent == PREFIX               # merged loop sends setup ++ committed
    assert f.calls == []                  # open() leaves the warm process alive
    warm.close()
    # bounded teardown (clean path): stdin.close -> terminate -> wait(3.0)
    assert f.calls == ["stdin.close", "terminate", ("wait", 3.0)]


def test_charact_three_sites_share_identical_replay_prefix(fake_spawn):
    """GOLDEN (the key Step-1 precondition): all three ephemeral sites emit the
    IDENTICAL drain-then-(setup ++ committed) replay prefix."""
    fakes, _ = fake_spawn

    _ec(SETUP, COMMITTED)._try_tactic_fresh("smt()")
    _ec(SETUP, COMMITTED)._try_chain_fresh(["auto."])
    ecw.WarmProber(["."], None).open(
        "dummy.ec", "L", committed_tactics=COMMITTED, setup_commands=SETUP)

    tactic_pre, chain_pre, warm_pre = (fakes[0].sent[:5], fakes[1].sent[:5], fakes[2].sent[:5])
    assert tactic_pre == chain_pre == warm_pre == PREFIX


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
