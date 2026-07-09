from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow.proof_management.lifecycle import ProofNodeLifecycleManager
from workflow.proof_management.types import ProofStateSnapshot


@dataclass(frozen=True)
class _ProjectionResult:
    view: dict[str, Any]


class _FakeRepl:
    def __init__(self) -> None:
        self.file_path = "target.ec"
        self.lemma_name = "target_lemma"
        self.session_dir = ".ec_session_unit"
        self.project_root = Path("/repo")
        self._state_version = 0
        self._session_epoch = 0
        self.started_with: list[str] = []

    def adopt_versions(self, state_version: int, session_epoch: int) -> None:
        self._state_version = max(self._state_version, int(state_version))
        self._session_epoch = max(self._session_epoch, int(session_epoch))

    def include_dirs(self) -> list[str]:
        return ["easycrypt-src/theories"]

    def start(
        self,
        replay_prefix: list[str] | None = None,
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        self.started_with = list(replay_prefix or [])
        self._state_version = 3
        self._session_epoch = 2
        return (
            ProofStateSnapshot(
                node_id="Tree-unit",
                session_tag="unit",
                session_dir=self.session_dir,
                session_epoch=self._session_epoch,
                state_version=self._state_version,
                goal_hash="goal",
                raw_workspace_view={"proof_status": {"status": "open"}},
            ),
            [{"label": "start", "exit_code": 0}],
        )


class _FakeProjection:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def project(self, **kwargs: Any) -> _ProjectionResult:
        self.calls.append(dict(kwargs))
        return _ProjectionResult(
            view={
                "proof_status": {"status": "open"},
                "view_hash": "hash",
            }
        )


class _FakeWorkspace:
    def lint_agent_view(self, view: dict[str, Any]) -> list[str]:
        return [] if view else ["empty"]


class _FakeLineage:
    def __init__(self) -> None:
        self.run_dir: Path | None = None
        self.bootstraps: list[dict[str, Any]] = []

    def record_node_bootstrap(self, **kwargs: Any) -> None:
        self.bootstraps.append(dict(kwargs))


def _lifecycle(tmp_path: Path) -> tuple[
    ProofNodeLifecycleManager,
    _FakeRepl,
    _FakeProjection,
    _FakeLineage,
    list[dict[str, Any]],
]:
    repl = _FakeRepl()
    projection = _FakeProjection()
    lineage = _FakeLineage()
    audits: list[dict[str, Any]] = []
    lifecycle = ProofNodeLifecycleManager(
        node_id="Tree-unit",
        session_tag="unit",
        repl=repl,
        projection=projection,
        lineage=lineage,
        workspace=_FakeWorkspace(),
        run_dir=lambda: tmp_path,
        audit=lambda record: audits.append(dict(record)),
        surface_profile="unit-profile",
    )
    return lifecycle, repl, projection, lineage, audits


def test_lifecycle_adopts_bootstrap_state_without_restarting(
    tmp_path: Path,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)

    lifecycle.adopt_bootstrap({
        "replay_prefix": ["proc.", "wp."],
        "workspace_view": {
            "proof_status": {"status": "open"},
            "current_goal": {"lines": ["goal"]},
        },
        "snapshot": {
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 4,
            "state_version": 7,
            "goal_hash": "abc",
        },
    })

    assert lifecycle.replay_prefix == ["proc.", "wp."]
    assert lifecycle.replay_prefix_count == 2
    assert lifecycle.latest_view["current_goal"]["lines"] == ["goal"]
    assert lifecycle.latest_snapshot is not None
    assert lifecycle.latest_snapshot.state_version == 7
    assert repl._state_version == 7
    assert repl._session_epoch == 4
    # Adopting a non-empty prefix marks the (worker) node as resumed lineage.
    assert lifecycle.resumed_from_prefix is True


def test_resumed_from_prefix_is_durable_across_a_floor_clear(
    tmp_path: Path,
) -> None:
    # The transient resume FLOOR (replay_prefix_count) is cleared when a rewind
    # crosses it; the durable resumed-lineage marker must survive so the
    # amend_and_replay guard still fires on the resumed node afterward.
    lifecycle, _repl, _, _, _ = _lifecycle(tmp_path)
    lifecycle.adopt_bootstrap({"replay_prefix": ["proc.", "wp."]})
    assert lifecycle.replay_prefix_count == 2
    assert lifecycle.resumed_from_prefix is True

    lifecycle.clear_replay_prefix()

    assert lifecycle.replay_prefix_count == 0
    assert lifecycle.replay_prefix == []
    assert lifecycle.resumed_from_prefix is True


def test_fresh_root_is_not_resumed_lineage(tmp_path: Path) -> None:
    # A from-scratch root (empty prefix) must never look like a resumed node.
    lifecycle, _repl, _, _, _ = _lifecycle(tmp_path)
    lifecycle.bootstrap(replay_prefix=[])
    assert lifecycle.replay_prefix_count == 0
    assert lifecycle.resumed_from_prefix is False


def test_lifecycle_bootstrap_projects_and_records_lineage(tmp_path: Path) -> None:
    lifecycle, repl, projection, lineage, audits = _lifecycle(tmp_path)

    record = lifecycle.bootstrap(replay_prefix=[" proc. ", "", "wp."])

    assert repl.started_with == ["proc.", "wp."]
    assert lifecycle.replay_prefix == ["proc.", "wp."]
    assert lifecycle.replay_prefix_count == 2
    assert projection.calls[0]["replay_prefix"] == ["proc.", "wp."]
    assert record["workspace_view"]["proof_status"]["status"] == "open"
    assert record["include_dirs"] == ["easycrypt-src/theories"]
    assert lineage.run_dir == tmp_path
    assert lineage.bootstraps[0]["replay_prefix_count"] == 2
    assert audits[0]["kind"] == "workspace_view.projected"
    assert audits[1]["kind"] == "proof_node_manager_bootstrap"


class _FakeReplWithHistory(_FakeRepl):
    """A repl whose session history can diverge from the requested prefix —
    models a replay step that EasyCrypt accepted but the no-progress detector
    auto-reverted (so it never reached history.ec)."""

    def __init__(self, committed: list[str]) -> None:
        super().__init__()
        self._committed = list(committed)

    def committed_history(self) -> list[str]:
        return list(self._committed)


def test_bootstrap_records_actual_history_when_replay_drops_a_step(
    tmp_path: Path,
) -> None:
    requested = ["proc.", "rewrite /inv in H.", "wp."]
    committed = ["proc.", "wp."]
    repl = _FakeReplWithHistory(committed)
    projection = _FakeProjection()
    lineage = _FakeLineage()
    audits: list[dict[str, Any]] = []
    lifecycle = ProofNodeLifecycleManager(
        node_id="Tree-unit",
        session_tag="unit",
        repl=repl,
        projection=projection,
        lineage=lineage,
        workspace=_FakeWorkspace(),
        run_dir=lambda: tmp_path,
        audit=lambda record: audits.append(dict(record)),
        surface_profile="unit-profile",
    )

    record = lifecycle.bootstrap(replay_prefix=requested)

    # The recorded prefix is the session's ACTUAL starting history; the
    # request is preserved alongside, with the dropped step called out.
    assert record["replay_prefix"] == committed
    assert lifecycle.replay_prefix == committed
    assert lifecycle.replay_prefix_count == 2
    assert record["replay_prefix_requested"] == requested
    assert record["replay_prefix_requested_count"] == 3
    assert record["replay_prefix_divergence"]["dropped"] == [
        {"index": 2, "tactic": "rewrite /inv in H."},
    ]
    assert record["replay_prefix_divergence"]["added"] == []
    # The projection (agent-facing view) also uses the actual history.
    assert projection.calls[0]["replay_prefix"] == committed


def test_bootstrap_clean_replay_keeps_record_compact(tmp_path: Path) -> None:
    requested = ["proc.", "wp."]
    repl = _FakeReplWithHistory(requested)
    projection = _FakeProjection()
    lineage = _FakeLineage()
    lifecycle = ProofNodeLifecycleManager(
        node_id="Tree-unit",
        session_tag="unit",
        repl=repl,
        projection=projection,
        lineage=lineage,
        workspace=_FakeWorkspace(),
        run_dir=lambda: tmp_path,
        audit=lambda record: None,
        surface_profile="unit-profile",
    )

    record = lifecycle.bootstrap(replay_prefix=requested)

    assert record["replay_prefix"] == requested
    assert record["replay_prefix_requested_count"] == 2
    assert "replay_prefix_requested" not in record
    assert "replay_prefix_divergence" not in record


def test_bootstrap_semantic_count_caps_at_committed_length(
    tmp_path: Path,
) -> None:
    # The semantic resume count (the lineage's original inherited prefix
    # length) survives respawns via resume_context; it must be capped by the
    # ACTUAL committed history, not the requested prefix.
    requested = ["proc.", "rewrite /inv in H.", "wp."]
    committed = ["proc.", "wp."]
    repl = _FakeReplWithHistory(committed)
    lifecycle = ProofNodeLifecycleManager(
        node_id="Tree-unit",
        session_tag="unit",
        repl=repl,
        projection=_FakeProjection(),
        lineage=_FakeLineage(),
        workspace=_FakeWorkspace(),
        run_dir=lambda: tmp_path,
        audit=lambda record: None,
        surface_profile="unit-profile",
    )

    record = lifecycle.bootstrap(
        replay_prefix=requested,
        resume_context={"resume_prefix_count": 99},
    )

    assert record["replay_prefix_count"] == 2
    assert lifecycle.replay_prefix_count == 2


def test_bootstrap_large_replay_shortfall_is_loud(tmp_path: Path) -> None:
    # A resume that restores far fewer tactics than requested (divergence
    # rollback during prefix replay) must surface as a first-class shortfall:
    # a summary on the bootstrap record plus a dedicated greppable audit
    # record — never only a diff buried inside the bootstrap JSON.
    # (Motivating incident 2026-06-11: a 90-tactic capsule whose live tree
    # showed ~24 tactics took a manual artifact dig to explain.)
    requested = [f"tac{i}." for i in range(20)]
    committed = requested[:12]
    repl = _FakeReplWithHistory(committed)
    audits: list[dict[str, Any]] = []
    lifecycle = ProofNodeLifecycleManager(
        node_id="Tree-unit",
        session_tag="unit",
        repl=repl,
        projection=_FakeProjection(),
        lineage=_FakeLineage(),
        workspace=_FakeWorkspace(),
        run_dir=lambda: tmp_path,
        audit=lambda record: audits.append(dict(record)),
        surface_profile="unit-profile",
    )

    record = lifecycle.bootstrap(replay_prefix=requested)

    shortfall = record["replay_prefix_shortfall"]
    assert shortfall["requested"] == 20
    assert shortfall["committed"] == 12
    assert shortfall["lost"] == 8
    assert shortfall["lost_ratio"] == 0.4
    assert shortfall["first_dropped_index"] == 13
    assert shortfall["first_dropped_tactic"] == "tac12."
    audit_kinds = [a.get("kind") for a in audits]
    assert "replay_prefix_shortfall" in audit_kinds
    audit = audits[audit_kinds.index("replay_prefix_shortfall")]
    assert audit["node"] == "Tree-unit"
    assert audit["requested"] == 20
    assert audit["committed"] == 12


def test_bootstrap_small_divergence_is_not_a_shortfall(tmp_path: Path) -> None:
    # One dropped step out of 20 (5%) stays below the 10% shortfall
    # threshold: divergence is still recorded in full, but no shortfall
    # summary or dedicated audit record fires.
    requested = [f"tac{i}." for i in range(20)]
    committed = requested[:10] + requested[11:]
    repl = _FakeReplWithHistory(committed)
    audits: list[dict[str, Any]] = []
    lifecycle = ProofNodeLifecycleManager(
        node_id="Tree-unit",
        session_tag="unit",
        repl=repl,
        projection=_FakeProjection(),
        lineage=_FakeLineage(),
        workspace=_FakeWorkspace(),
        run_dir=lambda: tmp_path,
        audit=lambda record: audits.append(dict(record)),
        surface_profile="unit-profile",
    )

    record = lifecycle.bootstrap(replay_prefix=requested)

    assert "replay_prefix_shortfall" not in record
    assert record["replay_prefix_divergence"]["dropped"] == [
        {"index": 11, "tactic": "tac10."},
    ]
    assert "replay_prefix_shortfall" not in [a.get("kind") for a in audits]


def test_bootstrap_without_history_reader_echoes_request(
    tmp_path: Path,
) -> None:
    # Backendless roots / fakes without committed_history keep the old
    # behaviour: the requested prefix is recorded as-is, no divergence keys.
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)

    record = lifecycle.bootstrap(replay_prefix=["proc.", "wp."])

    assert record["replay_prefix"] == ["proc.", "wp."]
    assert "replay_prefix_requested" not in record
    assert "replay_prefix_divergence" not in record


def test_lifecycle_progress_summary_reads_latest_view(tmp_path: Path) -> None:
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)
    lifecycle.latest_view = {"proof_status": {"status": "open"}}
    lifecycle.latest_snapshot = ProofStateSnapshot(
        node_id="Tree-unit",
        session_tag="unit",
        session_dir=".ec_session_unit",
        session_epoch=1,
        state_version=9,
        goal_hash="goal-hash",
    )

    summary = lifecycle.progress_summary()

    assert summary.node_id == "Tree-unit"
    assert summary.state_version == 9
    assert summary.goal_hash == "goal-hash"
    assert summary.proof_status == "open"
