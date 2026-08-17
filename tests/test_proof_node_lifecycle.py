from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from workflow.proof_management.lifecycle import ProofNodeLifecycleManager
from workflow.proof_management.types import ProofStateSnapshot


def _workspace_view(**overrides: Any) -> dict[str, Any]:
    view: dict[str, Any] = {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal",
            "remaining_goals_known": True,
        },
        "current_goal": {"lines": []},
        "view_hash": "fixture-view",
    }
    proof_status = dict(view["proof_status"])
    proof_status.update(overrides.pop("proof_status", {}))
    view.update(overrides)
    view["proof_status"] = proof_status
    return view


def _bootstrap(**overrides: Any) -> dict[str, Any]:
    replay_prefix = list(overrides.pop("replay_prefix", []))
    replay_prefix_count = overrides.pop(
        "replay_prefix_count", len(replay_prefix)
    )
    replay_prefix_requested_count = overrides.pop(
        "replay_prefix_requested_count", len(replay_prefix)
    )
    snapshot = {
        "node_id": "Tree-unit",
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "session_epoch": 0,
        "state_version": 0,
        "goal_hash": "goal",
        "goal_identity_required": True,
        "workspace_view_artifact": "",
        "execution_refs": {},
    }
    snapshot.update(overrides.pop("snapshot", {}))
    record: dict[str, Any] = {
        "schema_version": 3,
        "kind": "proof_node_manager_bootstrap",
        "node_id": "Tree-unit",
        "session_tag": "unit",
        "session_dir": ".ec_session_unit",
        "file": "target.ec",
        "lemma": "target_lemma",
        "include_dirs": ["easycrypt-src/theories"],
        "replay_prefix_count": replay_prefix_count,
        "replay_prefix": replay_prefix,
        "replay_prefix_requested_count": replay_prefix_requested_count,
        "manager_actions": [],
        "snapshot": snapshot,
        "workspace_view": _workspace_view(),
    }
    record.update(overrides)
    return record


@dataclass(frozen=True)
class _ProjectionResult:
    view: dict[str, Any]
    full_view: dict[str, Any]


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
                goal_identity_required=True,
                raw_workspace_view={"proof_status": {"status": "open"}},
            ),
            [{"label": "start", "exit_code": 0}],
        )

    def committed_history(self) -> list[str]:
        return list(self.started_with)


class _FakeProjection:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def project(self, **kwargs: Any) -> _ProjectionResult:
        self.calls.append(dict(kwargs))
        view = _workspace_view(
            proof_status={
                "status": "open",
                "remaining_goals_known": True,
            },
            view_hash="hash",
        )
        return _ProjectionResult(
            view=view,
            full_view={**view, "full_only": True},
        )


class _FakeWorkspace:
    def lint_workspace_view(self, view: dict[str, Any]) -> list[str]:
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
        surface_profile="l1_goal_projection",
    )
    return lifecycle, repl, projection, lineage, audits


def test_lifecycle_adopts_bootstrap_state_without_restarting(
    tmp_path: Path,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)

    lifecycle.adopt_bootstrap(_bootstrap(
        replay_prefix=["proc.", "wp."],
        workspace_view=_workspace_view(
            proof_status={
                "status": "open",
                "remaining_goals_known": True,
            },
            current_goal={"lines": ["goal"]},
        ),
        snapshot={
            "node_id": "Tree-unit",
            "session_tag": "unit",
            "session_dir": ".ec_session_unit",
            "session_epoch": 4,
            "state_version": 7,
            "goal_hash": "goal",
        },
    ))

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
    lifecycle.adopt_bootstrap(_bootstrap(replay_prefix=["proc.", "wp."]))
    assert lifecycle.replay_prefix_count == 2
    assert lifecycle.resumed_from_prefix is True

    lifecycle.clear_replay_prefix()

    assert lifecycle.replay_prefix_count == 0
    assert lifecycle.replay_prefix == []
    assert lifecycle.resumed_from_prefix is True


@pytest.mark.parametrize(
    "bootstrap",
    [
        {},
        {"schema_version": 1, "kind": "proof_node_manager_bootstrap"},
        {"schema_version": 3.0, "kind": "proof_node_manager_bootstrap"},
        {"schema_version": True, "kind": "proof_node_manager_bootstrap"},
        {"schema_version": 3, "kind": "manager_session_bootstrap"},
    ],
)
def test_lifecycle_rejects_noncurrent_bootstrap_envelopes(
    tmp_path: Path,
    bootstrap: dict[str, Any],
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)

    with pytest.raises(ValueError, match="schema_version=3"):
        lifecycle.adopt_bootstrap(bootstrap)

    assert lifecycle.latest_snapshot is None
    assert repl._state_version == 0


def test_lifecycle_rejects_incomplete_current_bootstrap_contract(
    tmp_path: Path,
) -> None:
    missing_workspace = _bootstrap()
    missing_workspace.pop("workspace_view")
    invalid_workspace = _bootstrap(workspace_view={})
    empty_status_view = _workspace_view()
    empty_status_view["proof_status"] = {}
    empty_status = _bootstrap(workspace_view=empty_status_view)
    missing_status_view = _workspace_view()
    missing_status_view["proof_status"] = {"remaining_goals_known": True}
    missing_status = _bootstrap(workspace_view=missing_status_view)
    missing_known_view = _workspace_view()
    missing_known_view["proof_status"] = {"status": "open"}
    missing_known = _bootstrap(workspace_view=missing_known_view)
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)

    for bootstrap in (
        missing_workspace,
        invalid_workspace,
        empty_status,
        missing_status,
        missing_known,
    ):
        with pytest.raises(ValueError, match="workspace_view"):
            lifecycle.adopt_bootstrap(bootstrap)

    assert lifecycle.latest_snapshot is None
    assert repl._state_version == 0


@pytest.mark.parametrize(
    "proof_status",
    [
        {
            "status": "candidate_closed",
            "remaining_goals_known": True,
            "goal_identity_required": False,
            "goal_hash": "",
        },
        {
            "status": "open",
            "remaining_goals_known": True,
            "goal_identity_required": True,
            "goal_hash": "another-goal",
        },
    ],
)
def test_lifecycle_rejects_snapshot_workspace_goal_identity_disagreement(
    tmp_path: Path,
    proof_status: dict[str, Any],
) -> None:
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap(
        workspace_view=_workspace_view(proof_status=proof_status),
    )

    with pytest.raises(ValueError, match="goal identity disagree"):
        lifecycle.adopt_bootstrap(bootstrap)


@pytest.mark.parametrize(
    "field",
    ["node_id", "session_tag", "session_dir", "file", "lemma", "snapshot"],
)
def test_lifecycle_rejects_missing_bootstrap_identity_or_snapshot(
    tmp_path: Path,
    field: str,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap()
    bootstrap.pop(field)

    with pytest.raises(ValueError, match=field):
        lifecycle.adopt_bootstrap(bootstrap)

    assert lifecycle.latest_snapshot is None
    assert repl._state_version == 0


@pytest.mark.parametrize(
    "field",
    [
        "include_dirs",
        "replay_prefix_count",
        "replay_prefix",
        "replay_prefix_requested_count",
        "manager_actions",
    ],
)
def test_lifecycle_rejects_missing_bootstrap_metadata(
    tmp_path: Path,
    field: str,
) -> None:
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap()
    bootstrap.pop(field)

    with pytest.raises(ValueError, match=field):
        lifecycle.adopt_bootstrap(bootstrap)


@pytest.mark.parametrize(
    "field",
    [
        "goal_hash",
        "workspace_view_artifact",
        "execution_refs",
    ],
)
def test_lifecycle_rejects_incomplete_snapshot_contract(
    tmp_path: Path,
    field: str,
) -> None:
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap()
    bootstrap["snapshot"].pop(field)

    with pytest.raises(ValueError, match=field):
        lifecycle.adopt_bootstrap(bootstrap)


def test_lifecycle_rejects_retired_node_identity_alias(tmp_path: Path) -> None:
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap()
    bootstrap["node"] = bootstrap["node_id"]

    with pytest.raises(ValueError, match="retired identity field `node`"):
        lifecycle.adopt_bootstrap(bootstrap)


def test_lifecycle_rejects_replay_count_beyond_committed_prefix(
    tmp_path: Path,
) -> None:
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap(replay_prefix=["proc."], replay_prefix_count=2)

    with pytest.raises(ValueError, match="cannot exceed"):
        lifecycle.adopt_bootstrap(bootstrap)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state_version", None),
        ("state_version", "7"),
        ("state_version", True),
        ("state_version", -1),
        ("session_epoch", None),
        ("session_epoch", "4"),
        ("session_epoch", False),
        ("session_epoch", -1),
    ],
)
def test_lifecycle_rejects_missing_or_invalid_snapshot_versions(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap()
    snapshot = bootstrap["snapshot"]
    if value is None:
        snapshot.pop(field)
    else:
        snapshot[field] = value

    with pytest.raises(ValueError, match=field):
        lifecycle.adopt_bootstrap(bootstrap)

    assert lifecycle.latest_snapshot is None
    assert repl._state_version == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("node_id", "Tree-other"),
        ("session_tag", "other"),
        ("session_dir", ".ec_session_other"),
        ("file", "other.ec"),
        ("lemma", "other_lemma"),
    ],
)
def test_lifecycle_rejects_bootstrap_identity_mismatch(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap()
    bootstrap[field] = value
    if field in {"node_id", "session_tag", "session_dir"}:
        bootstrap["snapshot"][field] = value

    with pytest.raises(ValueError, match=f"identity mismatch for `{field}`"):
        lifecycle.adopt_bootstrap(bootstrap)

    assert lifecycle.latest_snapshot is None
    assert repl._state_version == 0


@pytest.mark.parametrize("field", ["node_id", "session_tag", "session_dir"])
def test_lifecycle_rejects_snapshot_identity_mismatch(
    tmp_path: Path,
    field: str,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)
    bootstrap = _bootstrap()
    bootstrap["snapshot"][field] = "different"

    with pytest.raises(ValueError, match=f"snapshot identity mismatch for `{field}`"):
        lifecycle.adopt_bootstrap(bootstrap)

    assert lifecycle.latest_snapshot is None
    assert repl._state_version == 0


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
    assert lifecycle.latest_full_view["full_only"] is True
    assert record["node_id"] == "Tree-unit"
    assert "node" not in record
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
        surface_profile="l1_goal_projection",
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
        surface_profile="l1_goal_projection",
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
        surface_profile="l1_goal_projection",
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
        surface_profile="l1_goal_projection",
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
        surface_profile="l1_goal_projection",
    )

    record = lifecycle.bootstrap(replay_prefix=requested)

    assert "replay_prefix_shortfall" not in record
    assert record["replay_prefix_divergence"]["dropped"] == [
        {"index": 11, "tactic": "tac10."},
    ]
    assert "replay_prefix_shortfall" not in [a.get("kind") for a in audits]


def test_bootstrap_requires_authoritative_committed_history_reader(
    tmp_path: Path,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)
    repl.committed_history = None  # type: ignore[assignment]

    with pytest.raises(TypeError, match="must provide committed_history"):
        lifecycle.bootstrap(replay_prefix=["proc.", "wp."])


def test_bootstrap_does_not_replace_empty_committed_history_with_request(
    tmp_path: Path,
) -> None:
    repl = _FakeReplWithHistory([])
    lifecycle = ProofNodeLifecycleManager(
        node_id="Tree-unit",
        session_tag="unit",
        repl=repl,
        projection=_FakeProjection(),
        lineage=_FakeLineage(),
        workspace=_FakeWorkspace(),
        run_dir=lambda: tmp_path,
        audit=lambda record: None,
        surface_profile="l1_goal_projection",
    )

    record = lifecycle.bootstrap(replay_prefix=["proc.", "wp."])

    assert record["replay_prefix"] == []
    assert record["replay_prefix_divergence"]["dropped"] == [
        {"index": 1, "tactic": "proc."},
        {"index": 2, "tactic": "wp."},
    ]


@pytest.mark.parametrize(
    "committed",
    [None, ("proc.",), ["proc.", True], ["proc.", 7]],
)
def test_bootstrap_rejects_non_list_string_committed_history(
    tmp_path: Path,
    committed: object,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)
    repl.committed_history = lambda: committed  # type: ignore[method-assign,return-value]

    with pytest.raises(TypeError, match=r"must return list\[str\]"):
        lifecycle.bootstrap(replay_prefix=["proc."])


def test_bootstrap_propagates_committed_history_read_failure(
    tmp_path: Path,
) -> None:
    lifecycle, repl, _, _, _ = _lifecycle(tmp_path)

    def fail() -> list[str]:
        raise OSError("history unreadable")

    repl.committed_history = fail  # type: ignore[method-assign]

    with pytest.raises(OSError, match="history unreadable"):
        lifecycle.bootstrap(replay_prefix=["proc."])


@pytest.mark.parametrize("count", [True, False, "2", 2.0, -1, None])
def test_bootstrap_rejects_coerced_resume_prefix_count(
    tmp_path: Path,
    count: object,
) -> None:
    lifecycle, _, _, _, _ = _lifecycle(tmp_path)

    with pytest.raises(ValueError, match="resume_prefix_count"):
        lifecycle.bootstrap(
            replay_prefix=["proc.", "wp."],
            resume_context={"resume_prefix_count": count},
        )


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
        goal_identity_required=True,
    )

    summary = lifecycle.progress_summary()

    assert summary.node_id == "Tree-unit"
    assert summary.state_version == 9
    assert summary.goal_hash == "goal-hash"
    assert summary.proof_status == "open"
