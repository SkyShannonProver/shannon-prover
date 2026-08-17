"""Runtime semantic identity is a fail-closed managed-session boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.easycrypt import ec_runtime_identity as runtime_module
from core.easycrypt.ec_runtime_identity import (
    EasyCryptRuntimeIdentity,
    verified_session_runtime_identity,
)
from core.easycrypt.session_events import append_event


RUNTIME = EasyCryptRuntimeIdentity(
    build_id="r-test-1",
    binary_sha256="a" * 64,
)


def _session_with_runtime(path: Path) -> Path:
    path.mkdir()
    (path / "session_meta.json").write_text(json.dumps({
        "file": "/tmp/target.ec",
        "lemma": "target",
        "easycrypt_runtime_identity": RUNTIME.to_payload(),
    }))
    assert append_event(path, "session.started", {
        "file": "/tmp/target.ec",
        "lemma": "target",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
        "easycrypt_build_id": RUNTIME.build_id,
        "easycrypt_runtime_identity_sha256": (
            RUNTIME.semantic_identity_sha256
        ),
    })
    return path


def test_runtime_identity_payload_rejects_semantic_hash_drift() -> None:
    payload = RUNTIME.to_payload()
    payload["binary_sha256"] = "b" * 64

    with pytest.raises(ValueError, match="semantic identity hash mismatch"):
        EasyCryptRuntimeIdentity.from_payload(payload)


def test_session_runtime_requires_metadata_event_and_live_agreement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session_with_runtime(tmp_path / "session")
    monkeypatch.setattr(
        runtime_module,
        "discover_easycrypt_runtime_identity",
        lambda: RUNTIME,
    )

    assert verified_session_runtime_identity(session) == RUNTIME


def test_session_runtime_rejects_executable_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session_with_runtime(tmp_path / "session")
    replacement = EasyCryptRuntimeIdentity(
        build_id=RUNTIME.build_id,
        binary_sha256="b" * 64,
    )
    monkeypatch.setattr(
        runtime_module,
        "discover_easycrypt_runtime_identity",
        lambda: replacement,
    )

    with pytest.raises(ValueError, match="changed after session start"):
        verified_session_runtime_identity(session)


def test_session_runtime_rejects_unbound_start_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session_with_runtime(tmp_path / "session")
    events = session / "events.jsonl"
    item = json.loads(events.read_text().splitlines()[0])
    item["payload"].pop("easycrypt_runtime_identity_sha256")
    events.write_text(json.dumps(item) + "\n")
    monkeypatch.setattr(
        runtime_module,
        "discover_easycrypt_runtime_identity",
        lambda: RUNTIME,
    )

    with pytest.raises(ValueError, match="does not match metadata"):
        verified_session_runtime_identity(session)
