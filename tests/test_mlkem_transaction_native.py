"""Native manager regression for the ML-KEM transaction/finalization failure.

No provider is launched. Each case gets a fresh synthetic source/session and
the test fixture owns its daemon; original experiment state is never mutated.
"""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

from core.easycrypt.ec_daemon_client import ECDaemonClient
from core.easycrypt.committed_history import read_committed_commands
from core.easycrypt.session.session_events import read_events
from workflow.node.proof_node_manager import ProofNodeManager
from workflow.tree.session_observer import observe_session
from workflow.tree.result import SessionClosureCandidate
from workflow.agents.prover_writeback import _extract_tactics_from_candidate, _write_and_verify_proof

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_native(monkeypatch):
    monkeypatch.chdir(ROOT)
    socket = f"artifacts/transaction_{uuid.uuid4().hex[:12]}.sock"
    (ROOT / "artifacts").mkdir(exist_ok=True)
    monkeypatch.setenv("EC_DAEMON_SOCKET", socket)
    monkeypatch.setenv("WHY3EC_SOCKET", socket + ".why3")
    process = subprocess.Popen([sys.executable, "core/easycrypt/ec_daemon.py", "--socket", socket],
                               cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = ECDaemonClient(socket)
    try:
        for _ in range(100):
            assert process.poll() is None, "isolated native daemon exited"
            try:
                client.list_sessions()
                break
            except Exception:
                time.sleep(0.05)
        else:
            pytest.fail("isolated native daemon was not ready")
        yield
    finally:
        try:
            client.shutdown()
        except Exception:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.parametrize("profile", ["l1_goal_projection", "proof_state_compiler"])
@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("bad", ["definitely_invalid_tactic. trivial.",
                                 "move=> x. definitely_invalid_tactic."])
def test_rejected_transaction_is_atomic_then_valid_proof_verifies(
    tmp_path, monkeypatch, isolated_native, profile, batch, bad,
):
    monkeypatch.setenv("EC_DAEMON_DISABLE", "1" if batch else "0")
    source = tmp_path / "Synthetic.ec"
    source.write_text("require import AllCore.\nlemma target : forall (x : int), x = x.\n"
                      "proof.\nadmit.\nqed.\n")
    tag = "tx_" + uuid.uuid4().hex[:12]
    manager = ProofNodeManager(file_path=str(source), lemma_name="target",
        include_dir=str(ROOT / "easycrypt-src/theories"), session_tag=tag,
        node_id=tag, run_dir=tmp_path / "iteration_1", project_root=ROOT,
        surface_profile=profile)
    manager.repl.session_dir = str(tmp_path / (".ec_session_" + tag))
    try:
        manager.bootstrap(replay_prefix=[])
        def submit(tactic):
            return manager.handle_agent_message(json.dumps({"intent": "commit_tactic", "payload": {"tactic": tactic}}))
        before = observe_session(manager.session_path)
        submit(bad)
        verdict = [e["payload"] for e in read_events(manager.session_path)
                   if e["type"] == "tactic.result"][-1]
        assert verdict["status"] == "error"
        assert read_committed_commands(manager.session_path) == []
        after = observe_session(manager.session_path)
        assert not after.session_completion_candidate
        assert after.goal_hash == before.goal_hash
        accepted = submit("move=> x. trivial.")
        assert accepted.ok
        assert submit("qed.").ok
        snapshot = observe_session(manager.session_path)
        assert snapshot.session_completion_candidate
        candidate = SessionClosureCandidate.from_snapshot(node_id=tag, snapshot=snapshot,
            target_file=str(source), target_lemma="target")
        tactics = _extract_tactics_from_candidate(candidate)
        history = (manager.session_path / "history.ec").read_bytes()
        evidence = _write_and_verify_proof(source, "target", tactics, candidate,
                                           include_dir=str(ROOT / "easycrypt-src/theories"))
        assert evidence.passed, evidence.error
        assert (manager.session_path / "history.ec").read_bytes() == history
    finally:
        manager.close_session()


@pytest.mark.parametrize("warm", [False, True])
def test_multicommand_probe_replays_exact_state_and_rolls_back(tmp_path, monkeypatch, warm):
    from core.easycrypt.ec_daemon import ECSubprocess
    monkeypatch.setenv("EC_WARM_PROBE", "1" if warm else "0")
    source = tmp_path / "Probe.ec"
    source.write_text("require import AllCore.\nlemma target : forall (x : int), x = x /\\ x = x.\n"
                      "proof.\nadmit.\nqed.\n")
    ec = ECSubprocess([str(ROOT / "easycrypt-src/theories")])
    try:
        ec.spawn()
        ec.load_context_and_enter_proof(source, "target")
        partial = ec.execute("move=> x. split.")
        assert partial.accepted and partial.goal_after.remaining == 2
        rejected = ec.try_tactic("trivial. definitely_invalid_tactic.")
        assert not rejected.accepted
        completed = ec.try_tactic("trivial. trivial.")
        assert completed.accepted and completed.goal_after.is_closed
        # Probing never moves the authoritative committed process.
        assert ec.committed_count == 1
        assert ec.execute("+ trivial.\n+ trivial.").accepted
        assert ec.execute("qed.").accepted
    finally:
        ec.close()


def test_native_transaction_allows_trailing_comment(tmp_path):
    from core.easycrypt.ec_daemon import ECSubprocess
    source = tmp_path / "Comment.ec"
    source.write_text("lemma target : true.\nproof.\nadmit.\nqed.\n")
    ec = ECSubprocess([])
    try:
        ec.spawn()
        ec.load_context_and_enter_proof(source, "target")
        result = ec.execute("trivial. (* accepted proof, trailing comment *)")
        assert result.accepted and result.goal_after.is_closed, result
        assert ec.execute("qed.").accepted
    finally:
        ec.close()
