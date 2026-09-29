"""Zero-model regressions distilled from the 2026-09-06 ML-KEM audit.

Synthetic inputs exercise production boundaries; they are not a reconstruction
of the unobserved private cause of every historical failed job.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from core.easycrypt.session.session_api import open_session
from core.easycrypt.session.session_events import read_events
from core.easycrypt.lemma_decls import lemma_decl_lines
from workflow.agents import prover_writeback as writeback
from workflow.node import proof_node_resume as resume
from workflow.provider.ctx_respawn import context_tokens_from_codex_event


GOAL = "[1|check]>\nCurrent goal\n----\ntrue\n[2|check]>\n"


def test_batch_error_before_last_goal_is_rejected_and_rolled_back(tmp_path, monkeypatch):
    session = open_session(tmp_path / "session")
    session.curr.write_text(GOAL)
    monkeypatch.setenv("EC_DAEMON_DISABLE", "1")

    def batch(self, history, output, include_dirs=None):
        output.write_text(GOAL if not history.read_text().strip() else
                          "[error-2-0] invalid first command\n  MULTILINE_NATIVE_DETAIL\n" +
                          "[3|check]>\nNo more goals\n[4|check]>\n")
        return 0  # emacs mode can continue after native errors

    monkeypatch.setattr(type(session), "_run_ec", batch)
    session.append_block("definitely_invalid_tactic. trivial.")
    result = [e["payload"] for e in read_events(session.dir)
              if e["type"] == "tactic.result"][-1]
    assert result["status"] == "error"
    assert not result["history_committed"]
    assert not result["candidate_closed"]
    assert session.history.read_text() == ""
    assert session.curr.read_text() == GOAL
    assert "MULTILINE_NATIVE_DETAIL" in result["latest_error"]


def test_daemon_receives_whole_manager_transaction(tmp_path, monkeypatch):
    session = open_session(tmp_path / "session")
    source = tmp_path / "Target.ec"
    source.write_text("lemma L : true.\nproof. admit. qed.\n")
    (session.dir / "session_meta.json").write_text(json.dumps({"file": str(source), "lemma": "L"}))
    session.curr.write_text(GOAL)
    received = []

    class Backend:
        def try_commit_latest(self, _file, _lemma, transactions):
            received.extend(transactions)
            return {"accepted": False, "error": {"raw": "[error] rejected"}, "post_raw": ""}
        def invalidate(self):
            pass

    monkeypatch.delenv("EC_DAEMON_DISABLE", raising=False)
    session._daemon_backend = Backend()
    session.append_block("split.\n+ trivial.\n+ trivial.")
    assert received == ["split.\n+ trivial.\n+ trivial."]


def _candidate(tmp_path, monkeypatch):
    source = tmp_path / "Synthetic.ec"
    source.write_text("lemma L : true.\nproof.\nadmit.\nqed.\n")
    candidate = SimpleNamespace(target_file=str(source), target_lemma="L",
                                session_dir=str(tmp_path / "unused"), candidate_id="synthetic")
    monkeypatch.setattr("workflow.proof_acceptance.validate_completion_candidate_contract",
                        lambda _c: SimpleNamespace(ok=True))
    monkeypatch.setattr(writeback, "_claude_scratch_path", lambda name: tmp_path / name)
    monkeypatch.setattr(writeback, "_emit_verification_status", lambda *a, **kw: True)
    return source, candidate


def test_finalization_never_prunes_candidate(tmp_path, monkeypatch):
    source, candidate = _candidate(tmp_path, monkeypatch)
    before = source.read_bytes()
    calls = []
    def verify(path, **kw):
        calls.append(path.read_text())
        return False, "[critical] invalid first command"
    monkeypatch.setattr(writeback, "_verify_ec_file", verify)
    result = writeback._write_and_verify_proof(source, "L", ["invalid.", "trivial.", "qed."], candidate)
    assert not result.passed
    assert len(calls) == 2  # exact full file, then exact lemma; no repair attempts
    assert all("invalid." in text and "trivial." in text for text in calls)
    assert source.read_bytes() == before


def test_native_diagnostics_survive_failed_finalization(tmp_path, monkeypatch):
    source, candidate = _candidate(tmp_path, monkeypatch)
    errors = iter(["[critical] FULL_NATIVE_ERROR_123", "[critical] EXTRACTED_NATIVE_ERROR_456"])
    monkeypatch.setattr(writeback, "_verify_ec_file", lambda *a, **kw: (False, next(errors)))
    result = writeback._write_and_verify_proof(source, "L", ["trivial.", "qed."], candidate)
    assert "FULL_NATIVE_ERROR_123" in result.error
    assert "EXTRACTED_NATIVE_ERROR_456" in result.error


def test_closure_preserves_last_open_recovery(tmp_path, monkeypatch):
    run = tmp_path / "run"
    session = tmp_path / ".ec_session_prover_synthetic_tree_0"
    session.mkdir()
    history = ["move=> x."]
    state = {"closed": False}
    monkeypatch.setattr(resume, "read_session_goal_identity", lambda _p: SimpleNamespace(
        goal_identity_required=not state["closed"], goal_hash="" if state["closed"] else "a" * 64,
        proof_status="session_closed_pending_verification" if state["closed"] else "open"))
    monkeypatch.setattr(resume, "_git_commit", lambda _p: "synthetic")
    monkeypatch.setattr(resume, "_manager_route_events_for_node", lambda *a: [])
    def mint():
        (session / "history.ec").write_text("\n".join(history) + "\n")
        return resume.create_resume_capsules(project_root=tmp_path, run_dir=run,
            target_file="Synthetic.ec", lemma="L", session_dirs=[session])
    opened = mint()
    open_history = Path(opened[0]).with_name("history.ec").read_bytes()
    history.extend(["trivial.", "qed."])
    state["closed"] = True
    closed = mint()
    assert opened[0] in closed
    assert Path(opened[0]).with_name("history.ec").read_bytes() == open_history
    capsule = resume.load_resume_capsule(opened[0])
    assert capsule.replay_prefix == ["move=> x."]


def test_readonly_daemon_sync_uses_same_transaction_units(tmp_path, monkeypatch):
    session = open_session(tmp_path / "session")
    source = tmp_path / "Target.ec"
    source.write_text("lemma L : true.\nproof. admit. qed.\n")
    (session.dir / "session_meta.json").write_text(json.dumps({"file": str(source), "lemma": "L"}))
    session.history.write_text("split.\n+ trivial.\n")
    session.steps.write_text("2\n")
    received = []
    class Backend:
        def _sync_to(self, _file, _lemma, blocks):
            received.extend(blocks)
            return False  # No actual probe needed to assert sync boundaries.
    session._daemon_backend = Backend()
    monkeypatch.delenv("EC_DAEMON_DISABLE", raising=False)
    session.try_speculative("trivial.")
    assert received == ["split.\n+ trivial."]


def test_byequiv_is_not_a_declaration():
    assert lemma_decl_lines("lemma foo : true.\nproof. trivial. qed.\n"
                            "lemma bar : true.\nproof. byequiv foo => //; qed.\n", "foo") == [1]


def test_cumulative_usage_is_not_live_context():
    assert context_tokens_from_codex_event({"type": "turn.completed", "usage": {
        "input_tokens": 131032256, "cached_input_tokens": 128386944}}) is None
