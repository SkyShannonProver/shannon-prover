"""Tests for proof-view replay alignment classification."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.validation.proof_view_replay import (  # noqa: E402
    _align_next_tactic,
    _alignment_summary,
    _start_extracted_lemma_session,
    _tactic_bucket,
)


def test_tactic_bucket_classifies_pr_arithmetic_before_bridge() -> None:
    tactic = "apply StdOrder.RealOrder.ler_add; 1: byequiv UFCMA_genCC => //."

    assert _tactic_bucket(tactic, "pr") == "pr_arithmetic"


def test_tactic_bucket_classifies_procedure_and_invariant_frontends() -> None:
    assert _tactic_bucket("wp.", "procedure") == "procedure_control"
    assert _tactic_bucket("seq 5 3 : (={x} /\\ y{1} = y{2}).") == "invariant"
    assert _tactic_bucket("call (_: ={glob A}).") == "invariant"
    assert _tactic_bucket("call poly_mac1.") == "call_handle"
    assert _tactic_bucket("byphoare=> //=; proc.", "pr") == "hoare_prob"
    assert _tactic_bucket("pose ns := undup xs.", "procedure") == "ambient_logic"


def test_align_next_tactic_reports_bucket_only_missing() -> None:
    view = {
        "proof_ir": {
            "current_layer": "pr",
            "candidate_menu": [
                {"action": "Pr arithmetic plan: matching Pr bound lemmas"}
            ],
        }
    }

    alignment = _align_next_tactic(
        view,
        "apply StdOrder.RealOrder.ler_add; 1: byequiv UFCMA_genCC => //.",
    )

    assert alignment["verdict"] == "missing"
    assert alignment["target_bucket"] == "pr_arithmetic"
    assert alignment["support_level"] == "bucket_only"
    assert alignment["target_signal_seen"] is True


def test_alignment_summary_counts_missing_buckets() -> None:
    steps = [
        {
            "index": 0,
            "verdict": "missing",
            "target_bucket": "pr_bridge",
            "support_level": "absent",
            "next_head": "rewrite",
            "next_tactic": "rewrite pr_X.",
        },
        {
            "index": 1,
            "verdict": "head",
            "target_bucket": "procedure_control",
            "support_level": "head",
            "next_head": "wp",
            "next_tactic": "wp.",
        },
    ]

    summary = _alignment_summary(steps)

    assert summary["missing_view_alignments"] == 1
    assert summary["steps_by_bucket"] == {
        "pr_bridge": 1,
        "procedure_control": 1,
    }
    assert summary["missing_by_bucket"] == {"pr_bridge": 1}
    assert summary["missing_absent"] == 1
    assert summary["missing_examples"][0]["head"] == "rewrite"


def test_batch_replay_start_uses_daemon_goal_when_available(tmp_path: Path) -> None:
    source = tmp_path / "Example.ec"
    source.write_text("lemma foo : true.\nproof.\ntrivial.\nqed.\n")

    class FakeSession:
        def __init__(self, root: Path) -> None:
            self.dir = root / "session"
            self.curr = self.dir / "current.out"
            self.prev = self.dir / "prev.out"
            self.history = self.dir / "history.ec"
            self.events: list[tuple[str, dict]] = []
            self.loaded_context = False
            self._daemon_backend = None

        def start(self) -> dict:
            self.dir.mkdir()
            for path in (self.curr, self.prev, self.history):
                path.write_text("")
            return {
                "discarded_tactic_count": 0,
                "pre_restart_checkpoint_path": None,
            }

        def emit_event(self, event_type: str, payload: dict) -> None:
            self.events.append((event_type, payload))

        def _write_curr_compressed(self, raw: str) -> None:
            self.curr.write_text(raw)

        def load_context(self, _path: Path) -> None:
            self.loaded_context = True

        def _run_ec(self, *_args) -> None:
            raise AssertionError("daemon start should avoid subprocess replay")

        def _compress_curr_inplace(self) -> None:
            raise AssertionError("daemon start should avoid subprocess replay")

    class FakeDaemonBackend:
        last_error = ""

        def __init__(self, session_dir: Path, includes: list[str]) -> None:
            self.session_dir = session_dir
            self.includes = includes

        def _sync_to(self, file: Path, lemma: str, tactics: list[str]) -> bool:
            assert file == source
            assert lemma == "foo"
            assert tactics == []
            return True

        def get_goal_raw(self) -> str:
            return "Current goal\n\nType variables: <none>\n\n------------------------------------------------------------------------\ntrue\n[1|check]>\n"

    session = FakeSession(tmp_path)
    _start_extracted_lemma_session(
        session=session,
        file=source,
        lemma="foo",
        includes=["easycrypt-src/theories"],
        extract_lemma=lambda *_args, **_kwargs: "lemma foo : true.\nproof.\n",
        daemon_backend_cls=FakeDaemonBackend,
    )

    assert not session.loaded_context
    assert session.curr.read_text().startswith("Current goal")
    assert session.prev.read_text() == session.curr.read_text()
    meta = json.loads((session.dir / "session_meta.json").read_text())
    assert meta["file"] == str(source.resolve())
    assert meta["lemma"] == "foo"
    assert any(kind == "session.daemon_context_opened" for kind, _ in session.events)
