from __future__ import annotations

from workflow.proof_management import CommittedTurnSpine, ProofStateSnapshot


def _snapshot() -> ProofStateSnapshot:
    return ProofStateSnapshot(
        node_id="Tree-spine",
        session_tag="spine",
        session_dir=".ec_session_spine",
        session_epoch=2,
        state_version=7,
        goal_hash="goal-hash",
        goal_identity_required=True,
    )


def test_spine_reads_session_owner_once_and_binds_exact_snapshot() -> None:
    class Runtime:
        node_id = "Tree-spine"
        session_dir = ".ec_session_spine"
        session_epoch = 2
        state_version = 7
        calls = 0

        def committed_history(self) -> list[str]:
            self.calls += 1
            return ["proc.", "wp."]

    runtime = Runtime()
    snapshot = _snapshot()

    spine = CommittedTurnSpine.capture(runtime, snapshot)

    assert runtime.calls == 1
    assert spine.snapshot is snapshot
    assert spine.tactics == ("proc.", "wp.")


def test_spine_is_immutable_transport_without_close_judgments() -> None:
    class Runtime:
        node_id = "Tree-spine"
        session_dir = ".ec_session_spine"
        session_epoch = 2
        state_version = 7

        def committed_history(self) -> list[str]:
            return ["qed."]

    spine = CommittedTurnSpine.capture(Runtime(), _snapshot())

    assert spine.tactics == ("qed.",)
    assert not hasattr(spine, "closed")
    assert not hasattr(spine, "qed_committed")
