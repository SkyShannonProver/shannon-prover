"""Canonical stub/fake classes shared across the tests/ tree.

Same import contract as ``tests.helpers.builders``: the project root is on
``sys.path`` via ``tests/conftest.py`` (pytest) or the test file's own
``sys.path.insert`` (script mode). Test files keep their local ``_Fake*``
names as aliases so call sites stay untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class FakeDaemonCli:
    """Scripted daemon CLI: accept every probe, or only tactics containing
    ``accept_pattern``. Records every ``try_tactic`` call."""

    def __init__(self, accept_pattern: str | None = None):
        self._accept_pattern = accept_pattern
        self.calls: list[tuple[str, str]] = []

    def try_tactic(self, session_id: str, tactic: str) -> dict:
        self.calls.append((session_id, tactic))
        if self._accept_pattern is None:
            return {"accepted": True}
        return {"accepted": self._accept_pattern in tactic}


class FakeDaemonBackend:
    _session_id = "session-id"


@dataclass
class FakeDaemonHandle:
    cli: Any
    dbe: FakeDaemonBackend = field(default_factory=FakeDaemonBackend)


@dataclass
class FakeCtx:
    active_goal: str
    daemon_handle: FakeDaemonHandle | None
    scratch: dict = field(default_factory=dict)

    def daemon(self):
        return self.daemon_handle
