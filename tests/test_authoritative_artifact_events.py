"""Fail-closed event binding for authoritative session artifacts."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

import core.easycrypt.session_artifact_io as artifact_io  # noqa: E402
from core.easycrypt.daemon_backend import session_id_for_dir  # noqa: E402
from core.easycrypt.session_artifact_io import (  # noqa: E402
    SessionArtifactWriteError,
    write_confined_text_artifact,
)
from core.easycrypt.session_api import open_session  # noqa: E402
from core.easycrypt.session_commit_response import (  # noqa: E402
    build_commit_response,
    record_commit_response,
)
from core.easycrypt.session_events import (  # noqa: E402
    ArtifactEventEmissionError,
    append_event,
    make_event,
    read_events,
)
from core.easycrypt.session_episode_timeline import (  # noqa: E402
    build_session_episode_timeline,
    record_session_episode_timeline,
    write_session_episode_timeline_artifact,
)
from core.easycrypt.session_workspace_artifact import (  # noqa: E402
    record_prover_workspace_view,
)
from core.easycrypt.session_tactic_preflight import (  # noqa: E402
    build_tactic_preflight_artifact,
    record_tactic_preflight_artifact,
)
from core.easycrypt.session_tactic_execution_result import (  # noqa: E402
    build_tactic_execution_result,
    record_tactic_execution_result,
    write_tactic_raw_result_artifact,
)
from core.easycrypt.session_tactic_execution_artifacts import (  # noqa: E402
    load_tactic_execution_artifacts,
    validate_linked_workspace_artifact,
)
from tests.helpers.builders import (  # noqa: E402
    append_bound_workspace_event,
    bind_tactic_execution_workspace,
    managed_workspace_view,
    start_event,
    write_open_goal,
)


Record = Callable[..., dict[str, Any]]

_CASES = (
    ("preflight", "tactic.preflight.produced", "tactic_preflights"),
    (
        "prover_workspace",
        "prover.workspace_view.produced",
        "prover_workspace_views",
    ),
    ("commit_response", "commit.response.produced", "commit_responses"),
    (
        "tactic_execution",
        "tactic.execution.produced",
        "tactic_execution_results",
    ),
    (
        "episode_timeline",
        "episode.timeline.produced",
        "episode_timelines",
    ),
)


def _copy_as_adopted(donor: Path, target: Path) -> None:
    shutil.copytree(donor, target)
    assert append_event(
        target,
        "session.adopted",
        {
            "donor_session_dir": str(donor.resolve()),
            "target_session_dir": str(target.resolve()),
            "donor_session_id": session_id_for_dir(donor),
            "target_session_id": session_id_for_dir(target),
        },
        source="workflow.daemon_attach",
    )


def _record_bound_tactic_execution(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    record, result = _case(root, "tactic_execution")
    payload = record(open_session(root), result, source="test.strict-loader")
    return result, payload, read_events(root)


def _case(root: Path, name: str) -> tuple[Record, dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    write_open_goal(root)
    start_event(root)
    if name == "preflight":
        return record_tactic_preflight_artifact, build_tactic_preflight_artifact(
            proof_state={
                "status": "open",
                "goal_identity_required": True,
                "goal": {
                    "state_kind": "open",
                    "proof_candidate_closed": False,
                    "active_goal_hash": "goal",
                },
                "event_contract": {"ok": True},
                "consistency": {"ok": True},
            },
            result={
                "tactic": "wp.",
                "accepted": True,
                "goal_after_closed": False,
                "goal_after_remaining": 1,
            },
            raw_report="[TRY] accepted: True",
        )
    if name == "prover_workspace":
        return (
            record_prover_workspace_view,
            managed_workspace_view(),
        )
    if name == "commit_response":
        return record_commit_response, build_commit_response(
            root,
            command="commit",
            status="ok",
            attempted_tactics=["wp."],
            accepted_count=1,
            live_tool_name="commit",
            ok=True,
        )
    if name == "tactic_execution":
        commit_response = build_commit_response(
            root,
            command="commit",
            status="ok",
            attempted_tactics=["wp."],
            accepted_count=1,
            live_tool_name="commit",
            ok=True,
        )
        workspace_view = managed_workspace_view()
        result = build_tactic_execution_result(
            mode="commit",
            command="commit",
            commit_response=commit_response,
            workspace_view=workspace_view,
        )
        bound_result = bind_tactic_execution_workspace(root, result)
        append_bound_workspace_event(root, bound_result)
        return record_tactic_execution_result, bound_result
    if name == "episode_timeline":
        return (
            record_session_episode_timeline,
            build_session_episode_timeline(root),
        )
    raise AssertionError(f"unknown artifact case: {name}")


class _ControlledEventSession:
    def __init__(self, root: Path, outcome: bool | BaseException) -> None:
        self.dir = root
        self.outcome = outcome
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        source: str = "session_cli",
    ) -> bool:
        self.calls.append((event_type, payload, source))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


@pytest.mark.parametrize(("name", "event_type", "_artifact_dir"), _CASES)
def test_authoritative_record_emits_exact_payload_on_success(
    tmp_path: Path,
    name: str,
    event_type: str,
    _artifact_dir: str,
) -> None:
    root = tmp_path / name
    record, value = _case(root, name)
    session = open_session(root)

    payload = record(session, value, source="test.authoritative")

    produced = [event for event in read_events(root) if event["type"] == event_type]
    assert len(produced) == 1
    assert produced[0]["source"] == "test.authoritative"
    assert produced[0]["payload"] == payload
    assert json.loads(Path(payload["artifact"]).read_text(encoding="utf-8")) == value


@pytest.mark.parametrize(("name", "event_type", "_artifact_dir"), _CASES)
def test_authoritative_record_rejects_false_event_emission(
    tmp_path: Path,
    name: str,
    event_type: str,
    _artifact_dir: str,
) -> None:
    root = tmp_path / name
    record, value = _case(root, name)
    session = _ControlledEventSession(root, False)

    with pytest.raises(
        ArtifactEventEmissionError,
        match=rf"{event_type}: authoritative event emission returned False",
    ):
        record(session, value)

    assert len(session.calls) == 1
    assert session.calls[0][0] == event_type


@pytest.mark.parametrize(("name", "event_type", "_artifact_dir"), _CASES)
def test_authoritative_record_wraps_event_emission_exception(
    tmp_path: Path,
    name: str,
    event_type: str,
    _artifact_dir: str,
) -> None:
    root = tmp_path / name
    record, value = _case(root, name)
    session = _ControlledEventSession(root, OSError("event log unavailable"))

    with pytest.raises(
        ArtifactEventEmissionError,
        match=rf"{event_type}: authoritative event emission raised OSError",
    ) as raised:
        record(session, value)

    assert isinstance(raised.value.__cause__, OSError)
    assert len(session.calls) == 1


@pytest.mark.parametrize(("name", "event_type", "artifact_dir"), _CASES)
def test_authoritative_record_requires_event_sink_before_writing(
    tmp_path: Path,
    name: str,
    event_type: str,
    artifact_dir: str,
) -> None:
    root = tmp_path / name
    record, value = _case(root, name)

    with pytest.raises(
        ArtifactEventEmissionError,
        match=rf"{event_type}: authoritative record requires emit_event",
    ):
        record(root, value)

    assert not (root / artifact_dir).exists()


@pytest.mark.parametrize(("name", "event_type", "artifact_dir"), _CASES)
def test_authoritative_record_rejects_symlinked_artifact_directory(
    tmp_path: Path,
    name: str,
    event_type: str,
    artifact_dir: str,
) -> None:
    root = tmp_path / name
    record, value = _case(root, name)
    external_dir = tmp_path / f"{name}-external"
    external_dir.mkdir()
    sentinel = external_dir / "sentinel.txt"
    sentinel.write_text("must remain unchanged", encoding="utf-8")
    assert not (root / artifact_dir).exists()
    (root / artifact_dir).symlink_to(
        external_dir,
        target_is_directory=True,
    )
    session = open_session(root)

    with pytest.raises(
        SessionArtifactWriteError,
        match="artifact directory is not a real directory",
    ):
        record(session, value)

    assert sentinel.read_text(encoding="utf-8") == "must remain unchanged"
    assert list(external_dir.iterdir()) == [sentinel]
    assert not any(event["type"] == event_type for event in read_events(root))


def test_confined_writer_rejects_symlinked_target_without_modifying_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "session"
    artifact_dir = root / "tactic_preflights"
    artifact_dir.mkdir(parents=True)
    external = tmp_path / "external.json"
    external.write_text("external sentinel", encoding="utf-8")
    target = artifact_dir / "status.json"
    target.symlink_to(external)

    with pytest.raises(
        SessionArtifactWriteError,
        match="artifact target is not a regular file",
    ):
        write_confined_text_artifact(
            root,
            subdir="tactic_preflights",
            filename="status.json",
            text="replacement",
        )

    assert target.is_symlink()
    assert external.read_text(encoding="utf-8") == "external sentinel"
    assert list(artifact_dir.iterdir()) == [target]


@pytest.mark.parametrize(
    ("artifact_dir", "write"),
    (
        (
            "tactic_raw_results",
            lambda root: write_tactic_raw_result_artifact(
                root,
                command="commit",
                raw_result="raw proof output",
            ),
        ),
        (
            "episode_timelines",
            lambda root: write_session_episode_timeline_artifact(root, {
                "schema_version": 1,
                "kind": "session_episode_timeline",
                "ok": True,
                "session_dir": str(root),
                "step_count": 0,
                "rollup": {},
                "steps": [],
                "notes": [],
                "errors": [],
            }),
        ),
    ),
)
def test_linked_artifact_writers_reject_symlinked_directory(
    tmp_path: Path,
    artifact_dir: str,
    write: Callable[[Path], dict[str, Any]],
) -> None:
    root = tmp_path / artifact_dir
    root.mkdir()
    external_dir = tmp_path / f"{artifact_dir}-external"
    external_dir.mkdir()
    sentinel = external_dir / "sentinel.txt"
    sentinel.write_text("must remain unchanged", encoding="utf-8")
    (root / artifact_dir).symlink_to(
        external_dir,
        target_is_directory=True,
    )

    with pytest.raises(SessionArtifactWriteError):
        write(root)

    assert sentinel.read_text(encoding="utf-8") == "must remain unchanged"
    assert list(external_dir.iterdir()) == [sentinel]


def test_execution_loader_rejects_event_artifact_outside_current_session(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    external = tmp_path / "external-result.json"
    external.write_text(
        json.dumps({"sentinel": "must-not-load"}),
        encoding="utf-8",
    )
    event = make_event(
        session_dir,
        "tactic.execution.produced",
        {"artifact": str(external)},
    )

    loaded = load_tactic_execution_artifacts(session_dir, events=[event])

    assert loaded.event_count == 1
    assert loaded.resolved_event_count == 0
    assert loaded.artifacts == []
    assert loaded.unresolved_event_indexes == [1]


def test_execution_loader_accepts_only_fully_bound_current_session_event(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    result, payload, events = _record_bound_tactic_execution(session_dir)

    loaded = load_tactic_execution_artifacts(session_dir, events=events)

    assert loaded.ok is True
    assert loaded.event_count == 1
    assert loaded.resolved_event_count == 1
    assert loaded.unresolved_event_errors == {}
    assert len(loaded.artifacts) == 1
    assert loaded.artifacts[0].result == result
    assert loaded.artifacts[0].path == Path(payload["artifact"])


def test_execution_loader_and_timeline_survive_chained_daemon_adoptions(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    _record_bound_tactic_execution(first)

    second = tmp_path / "second"
    _copy_as_adopted(first, second)
    one_hop = load_tactic_execution_artifacts(second)
    one_hop_timeline = build_session_episode_timeline(second)
    assert one_hop.ok is True
    assert len(one_hop.artifacts) == 1
    assert one_hop.artifacts[0].path.parent == (
        second.resolve() / "tactic_execution_results"
    )
    assert one_hop_timeline["ok"] is True
    assert one_hop_timeline["step_count"] == 1

    _record_bound_tactic_execution(second)
    current = tmp_path / "current"
    _copy_as_adopted(second, current)
    chained = load_tactic_execution_artifacts(current)
    chained_timeline = build_session_episode_timeline(current)

    assert chained.ok is True
    assert len(chained.artifacts) == 2
    assert all(
        artifact.path.parent == current.resolve() / "tactic_execution_results"
        for artifact in chained.artifacts
    )
    assert chained_timeline["ok"] is True
    assert chained_timeline["step_count"] == 2


def test_execution_loader_rejects_entire_disconnected_adoption_lineage(
    tmp_path: Path,
) -> None:
    donor = tmp_path / "donor"
    _record_bound_tactic_execution(donor)
    current = tmp_path / "current"
    _copy_as_adopted(donor, current)
    stray_donor = tmp_path / "stray-donor"
    stray_target = tmp_path / "stray-target"
    disconnected = make_event(
        stray_target,
        "session.adopted",
        {
            "donor_session_dir": str(stray_donor.resolve()),
            "target_session_dir": str(stray_target.resolve()),
            "donor_session_id": session_id_for_dir(stray_donor),
            "target_session_id": session_id_for_dir(stray_target),
        },
        source="workflow.daemon_attach",
    )
    with (current / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(disconnected, sort_keys=True) + "\n")

    loaded = load_tactic_execution_artifacts(current)
    timeline = build_session_episode_timeline(current)

    assert loaded.resolved_event_count == 0
    assert loaded.artifacts == []
    assert all(
        any("invalid session adoption lineage" in error for error in errors)
        for errors in loaded.unresolved_event_errors.values()
    )
    assert timeline["ok"] is False
    assert timeline["step_count"] == 0
    assert any(
        "invalid session adoption lineage" in error["message"]
        for error in timeline["errors"]
    )


def test_execution_loader_rejects_cross_session_event_envelope(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    _result, _payload, events = _record_bound_tactic_execution(session_dir)
    other_session = tmp_path / "other-session"
    other_session.mkdir()
    tactic_event = next(
        event for event in events
        if event.get("type") == "tactic.execution.produced"
    )
    tactic_index = events.index(tactic_event) + 1
    tactic_event["session_dir"] = str(other_session.resolve())
    tactic_event["session_id"] = str(other_session.resolve())

    loaded = load_tactic_execution_artifacts(session_dir, events=events)

    assert loaded.resolved_event_count == 0
    assert loaded.artifacts == []
    assert any(
        "does not match the current session" in error
        for error in loaded.unresolved_event_errors[tactic_index]
    )


def test_execution_loader_rejects_missing_prior_workspace_event(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    _result, _payload, events = _record_bound_tactic_execution(session_dir)
    tactic_event = next(
        event for event in events
        if event.get("type") == "tactic.execution.produced"
    )

    loaded = load_tactic_execution_artifacts(
        session_dir,
        events=[tactic_event],
    )

    assert loaded.resolved_event_count == 0
    assert loaded.unresolved_event_indexes == [1]
    assert any(
        "no matching prior prover.workspace_view.produced event" in error
        for error in loaded.unresolved_event_errors[1]
    )


def test_execution_loader_rejects_tampered_result_after_event_commit(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    _result, payload, events = _record_bound_tactic_execution(session_dir)
    artifact = Path(payload["artifact"])
    tactic_event = next(
        event for event in events
        if event.get("type") == "tactic.execution.produced"
    )
    tactic_index = events.index(tactic_event) + 1
    tampered = json.loads(artifact.read_text(encoding="utf-8"))
    tampered["notes"] = ["changed after event commit"]
    artifact.write_text(
        json.dumps(tampered, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    loaded = load_tactic_execution_artifacts(session_dir, events=events)

    assert loaded.resolved_event_count == 0
    assert loaded.artifacts == []
    assert any(
        "result_hash" in error
        for error in loaded.unresolved_event_errors[tactic_index]
    )


def test_execution_loader_reports_but_never_returns_unbound_orphan(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    result_dir = session_dir / "tactic_execution_results"
    result_dir.mkdir(parents=True)
    orphan = result_dir / "orphan.json"
    orphan.write_text(json.dumps({"orphan": True}), encoding="utf-8")

    loaded = load_tactic_execution_artifacts(session_dir, events=[])

    assert loaded.artifacts == []
    assert loaded.orphan_paths == [orphan]
    assert loaded.ok is False


def test_execution_loader_rejects_symlinked_artifact_subdirectory(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    external_dir = tmp_path / "external-results"
    external_dir.mkdir()
    external = external_dir / "result.json"
    external.write_text(json.dumps({"sentinel": "outside"}), encoding="utf-8")
    (session_dir / "tactic_execution_results").symlink_to(
        external_dir,
        target_is_directory=True,
    )
    event = make_event(
        session_dir,
        "tactic.execution.produced",
        {"artifact": str(session_dir / "tactic_execution_results" / external.name)},
    )

    loaded = load_tactic_execution_artifacts(session_dir, events=[event])

    assert loaded.resolved_event_count == 0
    assert loaded.artifacts == []
    assert loaded.orphan_paths == []
    assert loaded.unreadable_orphan_paths == []
    assert external.read_text(encoding="utf-8") == json.dumps({
        "sentinel": "outside",
    })


def test_execution_loader_never_reads_symlinked_artifact_file(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    result_dir = session_dir / "tactic_execution_results"
    result_dir.mkdir(parents=True)
    external = tmp_path / "outside-sentinel.json"
    sentinel_text = json.dumps({"sentinel": "must-not-be-read"})
    external.write_text(sentinel_text, encoding="utf-8")
    linked = result_dir / "linked.json"
    linked.symlink_to(external)
    event = make_event(
        session_dir,
        "tactic.execution.produced",
        {"artifact": str(linked)},
    )

    loaded = load_tactic_execution_artifacts(session_dir, events=[event])

    assert loaded.resolved_event_count == 0
    assert loaded.artifacts == []
    assert loaded.orphan_paths == []
    assert loaded.unreadable_orphan_paths == [linked]
    assert external.read_text(encoding="utf-8") == sentinel_text


def test_execution_loader_rejects_file_swapped_to_symlink_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_dir = tmp_path / "session"
    result_dir = session_dir / "tactic_execution_results"
    result_dir.mkdir(parents=True)
    target = result_dir / "raced.json"
    target.write_text(json.dumps({"initial": True}), encoding="utf-8")
    external = tmp_path / "outside-race-sentinel.json"
    sentinel_text = json.dumps({"sentinel": "must-not-be-read"})
    external.write_text(sentinel_text, encoding="utf-8")
    original_open = artifact_io.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == target.name and dir_fd is not None and not swapped:
            swapped = True
            target.unlink()
            target.symlink_to(external)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(artifact_io.os, "open", racing_open)

    loaded = load_tactic_execution_artifacts(session_dir, events=[])

    assert swapped is True
    assert loaded.orphan_paths == []
    assert loaded.unreadable_orphan_paths == [target]
    assert external.read_text(encoding="utf-8") == sentinel_text


def test_execution_loader_rejects_subdir_swapped_to_symlink_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_dir = tmp_path / "session"
    result_dir = session_dir / "tactic_execution_results"
    result_dir.mkdir(parents=True)
    external_dir = tmp_path / "outside-race-results"
    external_dir.mkdir()
    sentinel = external_dir / "sentinel.json"
    sentinel_text = json.dumps({"sentinel": "must-not-be-read"})
    sentinel.write_text(sentinel_text, encoding="utf-8")
    original_open = artifact_io.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == result_dir.name and dir_fd is not None and not swapped:
            swapped = True
            result_dir.rmdir()
            result_dir.symlink_to(external_dir, target_is_directory=True)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(artifact_io.os, "open", racing_open)

    loaded = load_tactic_execution_artifacts(session_dir, events=[])

    assert swapped is True
    assert loaded.orphan_paths == []
    assert loaded.unreadable_orphan_paths == []
    assert sentinel.read_text(encoding="utf-8") == sentinel_text


def test_linked_workspace_rejects_valid_json_outside_session_subdir(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    _, workspace = _case(session_dir, "prover_workspace")
    canonical = json.dumps(workspace, indent=2, sort_keys=True)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    external = tmp_path / "external-workspace.json"
    external.write_text(canonical + "\n", encoding="utf-8")
    result = {
        "workspace": {
            "artifact": str(external),
            "view_hash": digest,
            "view": workspace,
        },
    }

    validation = validate_linked_workspace_artifact(
        result,
        session_dir=session_dir,
    )

    assert validation.ok is False
    assert any(
        "outside the current session's prover_workspace_views" in error
        for error in validation.errors
    )
