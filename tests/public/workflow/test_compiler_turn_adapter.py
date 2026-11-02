from __future__ import annotations

from types import SimpleNamespace

import pytest

from workflow.proof_management.compiler_turn_adapter import (
    CompilerTurnAdapter,
    CompilerTurnDeadlineExceeded,
)
from workflow.proof_state_compiler.service import CompilerReadOnlyViolation


class _FailingCompiler:
    def compile_current_state(self, *, turn_evidence=None):
        raise RuntimeError("backend timed out")


def test_compiler_failure_after_shared_deadline_is_not_an_abstention() -> None:
    readings = iter((10.0, 12.0))
    audit: list[dict] = []
    adapter = CompilerTurnAdapter(
        node_id="Tree-deadline",
        service=_FailingCompiler(),
        repl=SimpleNamespace(session_path="session"),
        audit=audit.append,
        clock=lambda: next(readings),
    )

    with pytest.raises(CompilerTurnDeadlineExceeded):
        adapter.compile_current(deadline=11.0)

    assert audit[-1]["kind"] == "proof_state_compiler.failed"


class _MutatingCompiler:
    def compile_current_state(self, *, turn_evidence=None):
        raise CompilerReadOnlyViolation(
            "compiler service changed committed proof history"
        )


def test_read_only_violation_fails_closed_instead_of_abstaining() -> None:
    audit: list[dict] = []
    adapter = CompilerTurnAdapter(
        node_id="Tree-violation",
        service=_MutatingCompiler(),
        repl=SimpleNamespace(session_path="session"),
        audit=audit.append,
    )

    with pytest.raises(CompilerReadOnlyViolation):
        adapter.compile_current()

    assert audit[-1]["kind"] == "proof_state_compiler.read_only_violation"


def test_ordinary_compiler_failure_remains_an_abstention() -> None:
    audit: list[dict] = []
    adapter = CompilerTurnAdapter(
        node_id="Tree-abstain",
        service=_FailingCompiler(),
        repl=SimpleNamespace(session_path="session"),
        audit=audit.append,
    )

    assert adapter.compile_current() == ""
    assert audit[-1]["kind"] == "proof_state_compiler.failed"
