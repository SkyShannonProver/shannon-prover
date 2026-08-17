"""Fail-closed contract tests for daemon-copied session event lineage."""
from __future__ import annotations

from pathlib import Path

import pytest

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.daemon_backend import session_id_for_dir  # noqa: E402
from core.easycrypt.session_events import (  # noqa: E402
    SessionAdoptionLineageError,
    make_event,
    validate_event,
    validated_session_lineage_aliases,
)


def _adoption_event(donor: Path, target: Path) -> dict:
    return make_event(
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


def test_session_adopted_event_is_registered() -> None:
    donor = Path("/tmp/shannon-lineage-schema-donor")
    target = Path("/tmp/shannon-lineage-schema-target")

    assert validate_event(_adoption_event(donor, target)) == []


def test_lineage_aliases_follow_chained_adoption_oldest_to_newest(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    current = tmp_path / "current"
    events = [
        make_event(first, "error.raised", {"phase": "fixture"}),
        _adoption_event(first, second),
        _adoption_event(second, current),
    ]

    aliases = validated_session_lineage_aliases(events, current)

    assert aliases == frozenset({
        str(first.resolve()),
        str(second.resolve()),
        str(current.resolve()),
    })


def test_lineage_without_adoption_trusts_only_current_dir(tmp_path: Path) -> None:
    current = tmp_path / "current"
    events = [make_event(current, "error.raised", {"phase": "fixture"})]

    assert validated_session_lineage_aliases(events, current) == frozenset({
        str(current.resolve())
    })


@pytest.mark.parametrize(
    "mutate, match",
    [
        (
            lambda event, donor, target: event.update(
                {"session_dir": str(donor.resolve())}
            ),
            "envelope must be bound",
        ),
        (
            lambda event, donor, target: event.update({"source": "fixture"}),
            "source must be",
        ),
        (
            lambda event, donor, target: event["payload"].update(
                {"donor_session_id": "scli_forged"}
            ),
            "donor daemon session id",
        ),
        (
            lambda event, donor, target: event["payload"].update(
                {"unexpected": True}
            ),
            "payload fields",
        ),
    ],
)
def test_lineage_rejects_malformed_or_forged_adoption_link(
    tmp_path: Path,
    mutate,
    match: str,
) -> None:
    donor = tmp_path / "donor"
    target = tmp_path / "target"
    event = _adoption_event(donor, target)
    mutate(event, donor, target)

    with pytest.raises(SessionAdoptionLineageError, match=match):
        validated_session_lineage_aliases([event], target)


def test_lineage_rejects_disconnected_adoption_link(tmp_path: Path) -> None:
    first = tmp_path / "first"
    current = tmp_path / "current"
    stray_donor = tmp_path / "stray-donor"
    stray_target = tmp_path / "stray-target"
    events = [
        _adoption_event(first, current),
        _adoption_event(stray_donor, stray_target),
    ]

    with pytest.raises(SessionAdoptionLineageError, match="disconnected"):
        validated_session_lineage_aliases(events, current)


def test_lineage_rejects_out_of_order_chain(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    current = tmp_path / "current"
    events = [
        _adoption_event(second, current),
        _adoption_event(first, second),
    ]

    with pytest.raises(SessionAdoptionLineageError, match="oldest-to-newest"):
        validated_session_lineage_aliases(events, current)


def test_lineage_rejects_duplicate_target_link(tmp_path: Path) -> None:
    first = tmp_path / "first"
    other = tmp_path / "other"
    current = tmp_path / "current"
    events = [
        _adoption_event(first, current),
        _adoption_event(other, current),
    ]

    with pytest.raises(SessionAdoptionLineageError, match="duplicate"):
        validated_session_lineage_aliases(events, current)
