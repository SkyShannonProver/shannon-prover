"""A flaky-test quarantine needs a reason, an issue and an expiry, and expires loudly."""
import datetime as dt
import json

from tests.helpers import quarantine

TODAY = dt.date(2026, 11, 2)


def _write(tmp_path, *entries):
    path = tmp_path / "quarantine.json"
    path.write_text(json.dumps({"schema_version": 1, "tests": list(entries)}))
    return path


def test_missing_file_means_no_quarantine(tmp_path):
    assert quarantine.load(tmp_path / "absent.json", TODAY) == ({}, [])


def test_live_entry_is_skipped_with_its_reason(tmp_path):
    path = _write(tmp_path, {"nodeid": "tests/public/core/test_x.py::test_y", "reason": "races the daemon",
                             "issue": "daemon socket reuse", "expires": "2026-11-30"})
    entries, errors = quarantine.load(path, TODAY)
    assert errors == []
    assert "races the daemon" in entries["tests/public/core/test_x.py::test_y"]


def test_expired_or_incomplete_entries_fail(tmp_path):
    path = _write(tmp_path,
                  {"nodeid": "a::b", "reason": "r", "issue": "i", "expires": "2026-11-01"},
                  {"nodeid": "c::d", "reason": "r", "expires": "2026-12-01"},
                  {"nodeid": "e::f", "reason": "r", "issue": "i", "expires": "soon"})
    entries, errors = quarantine.load(path, TODAY)
    assert entries == {}
    assert len(errors) == 3
    assert "expired" in errors[0] and "lacks issue" in errors[1] and "YYYY-MM-DD" in errors[2]


def test_repository_quarantine_list_is_valid():
    _entries, errors = quarantine.load()
    assert errors == []
