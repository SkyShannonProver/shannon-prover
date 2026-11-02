"""A batch commit runs EasyCrypt once and judges exactly as the two-run commit.

Real EasyCrypt with the daemon disabled, two in-process sessions driven
through ``Session.append_block`` side by side on the same scenarios. The
reference arm keeps the batch commit as it was: it first replays the journal
without the new transaction into ``prev.out``, then the journal with it. The
current arm runs only the second replay; ``prev.out`` holds the compressed
state the session already had, the input the daemon path always used for
goal counting and no-progress detection. Every commit result, transition
record and journal file must be the same, ``current.out`` the same after
compression, and the current arm must run EasyCrypt half as often. Skipped
without the managed toolchain.

The one visible difference is a reverted no-op: the reference arm restores
``current.out`` from the uncompressed replay in ``prev.out`` and shows the
state with a trailing prompt line; the current arm restores the compressed
state, as a daemon commit does. The shown text is therefore compared without
prompt lines.
"""
from __future__ import annotations

import shutil
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.easycrypt.commands.session_commands import handle_start
from core.easycrypt.ec_backend import BatchBackend
from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.ec_prompt import PROMPT_LINE_RE
from core.easycrypt.session.session_display import compress_current_state
from core.easycrypt.session.session_events import read_events
from core.easycrypt.session.session_runtime import Session

ROOT = Path(__file__).resolve().parents[3]
THEORIES = ROOT / "easycrypt-src" / "theories"

try:
    _MANAGED_EC_AVAILABLE = shutil.which(
        "easycrypt", path=get_ec_env().get("PATH")
    ) is not None
except RuntimeError:
    _MANAGED_EC_AVAILABLE = False

pytestmark = [pytest.mark.easycrypt, pytest.mark.skipif(
    not _MANAGED_EC_AVAILABLE,
    reason="repository-managed EasyCrypt is unavailable",
)]

SOURCE = """require import AllCore.

lemma batch_target (x y : int) : x = y => y = x /\\ true.
proof. admit. qed.
"""

# (operation, tactic, expected status); "undo" is undo_last_step.
SCENARIO = [
    ("commit", "move=> eq.", "ok"),                                  # first commit after -start
    ("commit", "rewrite nonexistent_lemma_p5.", "error"),            # rejection
    ("commit", "split.", "ok"),                                      # commit after a rejection
    ("commit", "have _ : true by trivial.", "no_progress_reverted"), # accepted no-op
    ("commit", "by rewrite eq. rewrite nonexistent_lemma_p5.", "error"),  # second sentence fails
    ("commit", "by rewrite eq.", "ok"),
    ("undo", "", "ok"),
    ("commit", "by rewrite eq.", "ok"),                              # commit after undo_last_step
    ("commit", "trivial.", "ok"),
    ("commit", "qed.", "ok"),                                        # closes the proof
]


class _CountingBatch(BatchBackend):
    def __init__(self, session_dir: Path) -> None:
        super().__init__(session_dir)
        self.runs = 0

    def run(self, input_path, output_path, include_dirs, timeout=None):
        self.runs += 1
        return super().run(input_path, output_path, include_dirs, timeout=timeout)


class _TwoRunBatch(_CountingBatch):
    """The batch commit before it ran once: replay ``prev.hist`` into
    ``prev.out`` first, then the journal."""

    def commit(self, *, history, curr, include_dirs, route, detail=""):
        self.run(self._dir / "prev.hist", self._dir / "prev.out", include_dirs)
        return super().commit(
            history=history, curr=curr, include_dirs=include_dirs,
            route=route, detail=detail,
        )


def _start(session_dir: Path, source: Path, batch: _CountingBatch) -> Session:
    session = Session(session_dir, [str(THEORIES)], batch=batch)
    args = SimpleNamespace(
        file=str(source), lemma="batch_target",
        include_dirs=[str(THEORIES)], force_restart=True,
    )
    assert handle_start(session, args) == 0
    return session


def _observe(session: Session, result) -> dict:
    events = read_events(session.dir)
    last = {}
    for event in events:
        last[event["type"]] = event.get("payload") or {}
    shown = asdict(result)
    shown["output"] = PROMPT_LINE_RE.sub("", shown["output"])
    return {
        "result": shown,
        "tactic.result": last.get("tactic.result"),
        "goal.changed": last.get("goal.changed"),
        "tactic.undone": last.get("tactic.undone"),
        "history": session.history.read_text(encoding="utf-8"),
        "steps": session.steps.read_text(encoding="utf-8"),
        "current": compress_current_state(session.curr.read_text(encoding="utf-8")),
    }


@pytest.fixture
def daemon_disabled(monkeypatch):
    monkeypatch.setenv("EC_DAEMON_DISABLE", "1")
    # A route nobody serves: EasyCrypt runs its provers itself.
    monkeypatch.setenv("WHY3EC_SOCKET", f"/tmp/p5w_{uuid.uuid4().hex[:10]}.sock")


def test_one_run_batch_commits_match_the_two_run_commits(tmp_path, daemon_disabled):
    source = tmp_path / "Batch.ec"
    source.write_text(SOURCE, encoding="utf-8")
    reference_batch = _TwoRunBatch(tmp_path / "two")
    current_batch = _CountingBatch(tmp_path / "one")
    reference = _start(tmp_path / "two", source, reference_batch)
    current = _start(tmp_path / "one", source, current_batch)
    seconds = {"two": 0.0, "one": 0.0}
    commits = 0

    for operation, tactic, expected in SCENARIO:
        observed = {}
        for name, session in (("two", reference), ("one", current)):
            began = time.monotonic()
            if operation == "undo":
                result = session.step_up()
            else:
                result = session.append_block(tactic)
            seconds[name] += time.monotonic() - began
            observed[name] = _observe(session, result)
        commits += operation == "commit"
        what = f"{operation} {tactic!r}"
        assert observed["one"] == observed["two"], what
        if operation == "commit":
            assert observed["one"]["result"]["status"] == expected, what

    final = observed["one"]["tactic.result"]
    assert final["candidate_closed"] is True
    # -start replays once in each arm; the undo replays once in each arm.
    assert reference_batch.runs == 2 + 2 * commits
    assert current_batch.runs == 2 + commits
    print(
        f"\nbatch commits: two-run {seconds['two']:.2f}s, one-run {seconds['one']:.2f}s "
        f"over {commits} commits"
    )
