"""The quarantine list for flaky tests (tests/quarantine.json).

A quarantined test is skipped in normal runs so one flaky test cannot block
the trunk. Each entry needs a reason, an issue (free text) and an expiry date;
an expired or malformed entry fails the run, so a quarantine cannot silently
become permanent. ``SHANNON_RUN_QUARANTINED=1`` runs only the quarantined
tests, which CI does in a step that reports without failing.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

QUARANTINE_PATH = Path(__file__).resolve().parents[1] / "quarantine.json"
REQUIRED = ("nodeid", "reason", "issue", "expires")


def load(path: Path = QUARANTINE_PATH, today: _dt.date | None = None) -> tuple[dict[str, str], list[str]]:
    """(nodeid -> skip reason, errors). A missing file means no quarantine."""
    if not path.is_file():
        return {}, []
    today = today or _dt.date.today()
    entries, errors = {}, []
    for index, entry in enumerate(json.loads(path.read_text(encoding="utf-8")).get("tests", [])):
        missing = [key for key in REQUIRED if not str(entry.get(key, "")).strip()]
        if missing:
            errors.append(f"quarantine entry {index} lacks {', '.join(missing)}")
            continue
        try:
            expires = _dt.date.fromisoformat(entry["expires"])
        except ValueError:
            errors.append(f"quarantine entry {entry['nodeid']}: expires is not a YYYY-MM-DD date")
            continue
        if expires < today:
            errors.append(f"quarantine of {entry['nodeid']} expired on {expires}; fix the test or renew it")
            continue
        entries[entry["nodeid"]] = f"quarantined until {expires}: {entry['reason']} ({entry['issue']})"
    return entries, errors
