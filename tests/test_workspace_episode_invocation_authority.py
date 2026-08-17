"""Current-call authority for aggregate workspace and episode views."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import _pathsetup  # noqa: F401,E402

from core.easycrypt.session_api import open_session  # noqa: E402
from core.easycrypt.session_episode_timeline import (  # noqa: E402
    build_session_episode_timeline,
    record_session_episode_timeline,
)
from core.easycrypt.session_events import read_events  # noqa: E402
from core.easycrypt.session_workspace_artifact import (  # noqa: E402
    record_prover_workspace_view,
)
from tests.helpers.builders import (  # noqa: E402
    start_event,
    tool_called,
    tool_result,
)
from workflow.proof_management.backend_actions import (  # noqa: E402
    backend_action_record,
    capture_authoritative_view_invocation,
    resolve_authoritative_view_invocation,
)
from workflow.proof_management.repl_session import (  # noqa: E402
    ReplBackendError,
    ReplSessionManager,
)


def _workspace(goal_line: str) -> dict:
    return {
        "schema_version": 3,
        "kind": "prover_workspace_view",
        "ok": True,
        "last_result": {},
        "proof_status": {
            "status": "open",
            "goal_identity_required": True,
            "goal_hash": "goal-hash",
            "remaining_goals": 1,
        },
        "current_goal": {
            "lines": ["Current goal", "----", goal_line],
            "text_fully_shown": True,
            "truncated": False,
            "char_count": len(goal_line),
        },
    }


def _command(session_dir: Path, flag: str) -> list[str]:
    return ["python3", "core/easycrypt/session_cli.py", "-d", str(session_dir), flag]


def _record_workspace_invocation(session_dir: Path, view: dict) -> None:
    tool_called(session_dir, "managed-goal-view", mutates=False)
    record_prover_workspace_view(open_session(session_dir), view)
    tool_result(session_dir, "managed-goal-view", mutates=False)


def _record_timeline_invocation(session_dir: Path, timeline: dict) -> None:
    tool_called(session_dir, "episode-view", mutates=False)
    record_session_episode_timeline(open_session(session_dir), timeline)
    tool_result(session_dir, "episode-view", mutates=False)


def _write_managed_meta(session_dir: Path) -> None:
    (session_dir / "session_meta.json").write_text(
        json.dumps({
            "file": "eval/examples/SchnorrPK.ec",
            "lemma": "dummy",
        }),
        encoding="utf-8",
    )


def _rewrite_events(session_dir: Path, mutate) -> None:  # noqa: ANN001
    rows = read_events(session_dir)
    mutate(rows)
    (session_dir / "events.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_repl_snapshot_ignores_forged_managed_goal_view_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="workspace-authority",
        node_id="Tree-workspace-authority",
        project_root=tmp_path,
    )
    session_dir = tmp_path / ".ec_session_workspace-authority"
    session_dir.mkdir()
    start_event(session_dir)
    _write_managed_meta(session_dir)
    authoritative = _workspace("AUTHORITATIVE")
    forged_stdout = json.dumps(_workspace("FORGED STDOUT"))

    def fake_run(*_args, **_kwargs):  # noqa: ANN001
        _record_workspace_invocation(session_dir, authoritative)
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=forged_stdout, stderr="",
        )

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.subprocess.run",
        fake_run,
    )
    monkeypatch.setattr(manager, "_env", lambda: {})

    snapshot = manager._snapshot_from_managed_goal_view(actions=[])

    assert snapshot.raw_workspace_view == authoritative
    assert "FORGED STDOUT" not in json.dumps(snapshot.to_dict())


def test_repl_snapshot_rejects_unsuccessful_event_bound_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="workspace-unsuccessful",
        node_id="Tree-workspace-unsuccessful",
        project_root=tmp_path,
    )
    session_dir = tmp_path / ".ec_session_workspace-unsuccessful"
    session_dir.mkdir()
    start_event(session_dir)
    _write_managed_meta(session_dir)
    unsuccessful = _workspace("UNTRUSTWORTHY")
    unsuccessful["ok"] = False

    def fake_run(*_args, **_kwargs):  # noqa: ANN001
        _record_workspace_invocation(session_dir, unsuccessful)
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(unsuccessful), stderr="",
        )

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.subprocess.run",
        fake_run,
    )
    monkeypatch.setattr(manager, "_env", lambda: {})
    actions: list[dict] = []

    with pytest.raises(ReplBackendError) as exc_info:
        manager._snapshot_from_managed_goal_view(actions=actions)

    assert exc_info.value.action["outcome_kind"] == "backend_error"
    assert actions[-1]["outcome_kind"] == "backend_error"
    assert manager.state_version == 0


def test_episode_action_uses_bound_timeline_not_forged_stdout(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_episode_authority"
    session_dir.mkdir()
    start_event(session_dir)
    _write_managed_meta(session_dir)
    timeline = build_session_episode_timeline(session_dir)
    cmd = _command(session_dir, "-episode-view")
    boundary = capture_authoritative_view_invocation(session_dir, cmd)
    assert boundary is not None
    _record_timeline_invocation(session_dir, timeline)

    action = backend_action_record(
            "episode_view",
        cmd,
        subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"ok": False, "status": "poisoned"}),
            stderr="",
        ),
        authoritative_view_boundary=boundary,
    )

    assert action.get("contract_error") in (None, "")
    assert action["outcome_kind"] == "read_only"
    assert action["agent_observation"]["result"] == (
        "The manager produced the authoritative session timeline."
    )
    assert "poisoned" not in json.dumps(action["agent_observation"])


def test_managed_goal_view_cannot_bypass_bound_artifact(
    tmp_path: Path,
) -> None:
    label = "managed_goal_view"
    session_dir = tmp_path / f".ec_session_{label}"
    session_dir.mkdir()
    start_event(session_dir)
    cmd = _command(session_dir, "-managed-goal-view")
    boundary = capture_authoritative_view_invocation(session_dir, cmd)
    assert boundary is not None
    _record_workspace_invocation(session_dir, _workspace("BOUND"))

    action = backend_action_record(
        label,
        cmd,
        subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"ok": False, "status": "stdout-poison"}),
            stderr="",
        ),
        authoritative_view_boundary=boundary,
    )

    assert "contract_error" not in action
    assert action["outcome_kind"] == "read_only"
    assert "stdout-poison" not in json.dumps(action["agent_observation"])


@pytest.mark.parametrize(
    "case, expected_error",
    (
        ("missing", "exactly one prover.workspace_view.produced"),
        ("stale", "exactly one prover.workspace_view.produced"),
        ("wrong_session", "event session_dir does not match the current session"),
        ("wrong_tool_envelope", "envelope session_dir does not match"),
        ("wrong_tool_payload", "payload session_dir does not match"),
        ("wrong_hash", "view_hash"),
        ("outside_artifact", "outside this session"),
        ("wrong_schema", "schema_version"),
        ("wrong_order", "must occur between tool.called and tool.result"),
        ("duplicate", "exactly one prover.workspace_view.produced"),
        ("replaced_artifact", "view_hash"),
    ),
)
def test_workspace_invocation_fail_closed(
    tmp_path: Path,
    case: str,
    expected_error: str,
) -> None:
    session_dir = tmp_path / f".ec_session_workspace_{case}"
    session_dir.mkdir()
    start_event(session_dir)
    cmd = _command(session_dir, "-managed-goal-view")

    if case == "stale":
        record_prover_workspace_view(open_session(session_dir), _workspace("STALE"))
    boundary = capture_authoritative_view_invocation(session_dir, cmd)
    assert boundary is not None
    if case in {"missing", "stale"}:
        tool_called(session_dir, "managed-goal-view", mutates=False)
        tool_result(session_dir, "managed-goal-view", mutates=False)
    elif case == "wrong_order":
        record_prover_workspace_view(open_session(session_dir), _workspace("ORDER"))
        tool_called(session_dir, "managed-goal-view", mutates=False)
        tool_result(session_dir, "managed-goal-view", mutates=False)
    else:
        tool_called(session_dir, "managed-goal-view", mutates=False)
        record_prover_workspace_view(open_session(session_dir), _workspace("BOUND"))
        if case == "duplicate":
            record_prover_workspace_view(open_session(session_dir), _workspace("BOUND"))
        tool_result(session_dir, "managed-goal-view", mutates=False)

    if case == "wrong_session":
        def mutate_session(rows):  # noqa: ANN001
            event = next(
                row for row in rows
                if row.get("type") == "prover.workspace_view.produced"
            )
            event["session_dir"] = str(tmp_path / "forged-session")
            event["session_id"] = event["session_dir"]
        _rewrite_events(session_dir, mutate_session)
    elif case == "wrong_tool_envelope":
        def mutate_tool_envelope(rows):  # noqa: ANN001
            event = next(row for row in rows if row.get("type") == "tool.called")
            event["session_dir"] = str(tmp_path / "forged-session")
            event["session_id"] = event["session_dir"]
        _rewrite_events(session_dir, mutate_tool_envelope)
    elif case == "wrong_tool_payload":
        def mutate_tool_payload(rows):  # noqa: ANN001
            event = next(row for row in rows if row.get("type") == "tool.result")
            event["payload"]["session_dir"] = str(tmp_path / "forged-session")
        _rewrite_events(session_dir, mutate_tool_payload)
    elif case == "wrong_hash":
        def mutate_hash(rows):  # noqa: ANN001
            event = next(
                row for row in rows
                if row.get("type") == "prover.workspace_view.produced"
            )
            event["payload"]["view_hash"] = "0" * 40
        _rewrite_events(session_dir, mutate_hash)
    elif case == "outside_artifact":
        outside = tmp_path / "outside.json"
        outside.write_text(json.dumps(_workspace("OUTSIDE")), encoding="utf-8")

        def mutate_artifact(rows):  # noqa: ANN001
            event = next(
                row for row in rows
                if row.get("type") == "prover.workspace_view.produced"
            )
            event["payload"]["artifact"] = str(outside)
        _rewrite_events(session_dir, mutate_artifact)
    elif case in {"wrong_schema", "replaced_artifact"}:
        event = next(
            row for row in read_events(session_dir)
            if row.get("type") == "prover.workspace_view.produced"
        )
        artifact = Path(event["payload"]["artifact"])
        replacement = _workspace("REPLACED")
        if case == "wrong_schema":
            replacement["schema_version"] = 999
        artifact.write_text(
            json.dumps(replacement, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    resolution = resolve_authoritative_view_invocation(
        boundary,
        exit_code=0,
    )

    assert resolution.payload is None
    assert expected_error in resolution.error


def test_episode_wrong_event_payload_and_schema_fail_closed(tmp_path: Path) -> None:
    session_dir = tmp_path / ".ec_session_episode_bad"
    session_dir.mkdir()
    start_event(session_dir)
    timeline = build_session_episode_timeline(session_dir)
    cmd = _command(session_dir, "-episode-view")
    boundary = capture_authoritative_view_invocation(session_dir, cmd)
    assert boundary is not None
    _record_timeline_invocation(session_dir, timeline)

    def mutate(rows):  # noqa: ANN001
        event = next(
            row for row in rows
            if row.get("type") == "episode.timeline.produced"
        )
        event["payload"]["timeline_hash"] = "f" * 40
        event["payload"]["schema_version"] = 999

    _rewrite_events(session_dir, mutate)
    resolution = resolve_authoritative_view_invocation(boundary, exit_code=0)

    assert resolution.payload is None
    assert "timeline_hash" in resolution.error
    assert "schema_version" in resolution.error


def test_managed_goal_view_missing_produced_event_raises_backend_contract_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="workspace-missing",
        node_id="Tree-workspace-missing",
        project_root=tmp_path,
    )
    session_dir = tmp_path / ".ec_session_workspace-missing"
    session_dir.mkdir()
    start_event(session_dir)
    _write_managed_meta(session_dir)

    def fake_run(*_args, **_kwargs):  # noqa: ANN001
        tool_called(session_dir, "managed-goal-view", mutates=False)
        tool_result(session_dir, "managed-goal-view", mutates=False)
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(_workspace("POISON")), stderr="",
        )

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.subprocess.run",
        fake_run,
    )
    monkeypatch.setattr(manager, "_env", lambda: {})

    with pytest.raises(ReplBackendError):
        manager._snapshot_from_managed_goal_view(actions=[])


@pytest.mark.parametrize(
    "metadata",
    (
        None,
        "{not-json",
        "[]",
        json.dumps({"file": "eval/examples/SchnorrPK.ec", "lemma": 7}),
        json.dumps({"file": "eval/examples/SchnorrPK.ec", "lemma": " dummy "}),
        json.dumps({"file": "", "lemma": "dummy"}),
        json.dumps({"file": "eval/examples/SchnorrPK.ec", "lemma": "other"}),
        json.dumps({"file": "eval/examples/Other.ec", "lemma": "dummy"}),
    ),
)
def test_managed_snapshot_rejects_untrusted_target_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata: str | None,
) -> None:
    manager = ReplSessionManager(
        file_path="eval/examples/SchnorrPK.ec",
        lemma_name="dummy",
        include_dir="easycrypt-src/theories",
        session_tag="workspace-meta",
        node_id="Tree-workspace-meta",
        project_root=tmp_path,
    )
    session_dir = tmp_path / ".ec_session_workspace-meta"
    session_dir.mkdir()
    start_event(session_dir)
    if metadata is not None:
        (session_dir / "session_meta.json").write_text(
            metadata,
            encoding="utf-8",
        )

    def fake_run(*_args, **_kwargs):  # noqa: ANN001
        _record_workspace_invocation(session_dir, _workspace("BOUND"))
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(_workspace("POISON")), stderr="",
        )

    monkeypatch.setattr(
        "workflow.proof_management.repl_session.subprocess.run",
        fake_run,
    )
    monkeypatch.setattr(manager, "_env", lambda: {})
    actions: list[dict] = []

    with pytest.raises(ReplBackendError) as exc_info:
        manager._snapshot_from_managed_goal_view(actions=actions)

    assert exc_info.value.action["outcome_kind"] == "backend_error"
    assert exc_info.value.action["contract_error"]
    assert actions[-1]["contract_error"]
    assert manager.state_version == 0
