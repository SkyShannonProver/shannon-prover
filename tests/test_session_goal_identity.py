from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.easycrypt.session_projection import (
    active_goal_hash_from_raw,
    read_proof_state_projection,
)
from workflow.proof_management import session_goal_identity
from workflow.proof_management.repl_session import _goal_hash


def test_session_goal_hash_uses_canonical_projection_hash(tmp_path: Path) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "current.out").write_text(
        "[1|check]>\nCurrent goal\n----\nx = y\n[2|check]>\n",
        encoding="utf-8",
    )
    from tests.helpers.builders import start_event

    start_event(session_dir)

    expected = read_proof_state_projection(session_dir).goal.active_goal_hash

    assert expected
    assert (
        session_goal_identity.read_session_goal_identity(session_dir).goal_hash
        == expected
    )


def test_session_goal_identity_fails_closed_without_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "current.out").write_text(
        "Current goal\n----\nx = y\n", encoding="utf-8"
    )

    def projection_unavailable(_session_dir: Path):
        raise RuntimeError("projection unavailable")

    monkeypatch.setattr(
        session_goal_identity,
        "read_proof_state_projection",
        projection_unavailable,
    )

    identity = session_goal_identity.read_session_goal_identity(session_dir)

    assert identity.goal_hash == ""
    assert identity.proof_status == "unknown"
    assert identity.goal_identity_required is True


def test_session_goal_identity_never_reparses_current_out_after_projection_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "current.out").write_text(
        "Current goal\n----\nx = y\n[17|check]>\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        session_goal_identity,
        "read_proof_state_projection",
        lambda _session_dir: (_ for _ in ()).throw(
            RuntimeError("projection unavailable")
        ),
    )

    identity = session_goal_identity.read_session_goal_identity(session_dir)

    assert identity.goal_hash == ""
    assert identity.goal_identity_required is True


def test_session_goal_hash_is_empty_when_identity_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    def projection_unavailable(_session_dir: Path):
        raise RuntimeError("projection unavailable")

    monkeypatch.setattr(
        session_goal_identity,
        "read_proof_state_projection",
        projection_unavailable,
    )

    assert (
        session_goal_identity.read_session_goal_identity(session_dir).goal_hash
        == ""
    )


def test_active_goal_hash_is_empty_for_closed_easycrypt_state() -> None:
    assert active_goal_hash_from_raw(
        "[1|check]>\nNo more goals\n+ added lemma: `L'\n[2|check]>\n"
    ) == ""


def test_active_goal_hash_is_empty_without_a_canonical_goal_body() -> None:
    for raw in ("", "[31|check]>", "[31|check]>\n"):
        assert active_goal_hash_from_raw(raw) == ""


def test_open_projection_requires_nonempty_resume_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_goal_identity,
        "read_proof_state_projection",
        lambda _path: SimpleNamespace(
            status="open",
            goal_identity_required=True,
            goal=SimpleNamespace(active_goal_hash=""),
            events=SimpleNamespace(ok=True),
            consistency=SimpleNamespace(ok=True),
        ),
    )

    identity = session_goal_identity.read_session_goal_identity(tmp_path)

    assert identity.goal_hash == ""
    assert identity.proof_status == "open"
    assert identity.goal_identity_required is True


def test_closed_projection_may_omit_resume_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_goal_identity,
        "read_proof_state_projection",
        lambda _path: SimpleNamespace(
            status="candidate_closed",
            goal_identity_required=False,
            goal=SimpleNamespace(active_goal_hash=""),
            events=SimpleNamespace(ok=True),
            consistency=SimpleNamespace(ok=True),
        ),
    )

    identity = session_goal_identity.read_session_goal_identity(tmp_path)

    assert identity.goal_hash == ""
    assert identity.proof_status == "candidate_closed"
    assert identity.goal_identity_required is False


def test_session_goal_identity_rejects_invalid_projection_authority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        session_goal_identity,
        "read_proof_state_projection",
        lambda _path: SimpleNamespace(
            status="candidate_closed",
            goal_identity_required=False,
            goal=SimpleNamespace(active_goal_hash=""),
            events=SimpleNamespace(ok=False),
            consistency=SimpleNamespace(ok=True),
        ),
    )

    identity = session_goal_identity.read_session_goal_identity(tmp_path)

    assert identity.goal_hash == ""
    assert identity.proof_status == "unknown"
    assert identity.goal_identity_required is True


def test_manager_workspace_goal_hash_has_no_goal_text_fallback() -> None:
    lines = [
        "Current goal",
        "",
        "x : int",
        "--------",
        "x = x",
        "[97|check]>",
    ]

    assert active_goal_hash_from_raw("\n".join(lines))
    assert _goal_hash({"current_goal": {"lines": lines}}) == ""


def test_manager_workspace_goal_hash_ignores_noncanonical_goal_panel_alias() -> None:
    assert _goal_hash({
        "current_goal": {
            "goal_hash": "projection-hash",
            "lines": ["Current goal", "--------", "x = x", "[4|check]>"],
        },
    }) == ""


def test_manager_workspace_goal_hash_consumes_v3_proof_status_owner() -> None:
    assert _goal_hash({
        "proof_status": {
            "goal_identity_required": True,
            "goal_hash": "canonical-goal-hash",
        },
        "current_goal": {"goal_hash": "forged-alias"},
    }) == "canonical-goal-hash"


def test_manager_workspace_goal_hash_is_empty_for_closed_display() -> None:
    assert _goal_hash({
        "current_goal": {
            "lines": ["No more goals", "+ added lemma: `L'", "[12|check]>"],
        },
    }) == ""
