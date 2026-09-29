from __future__ import annotations

import pytest

from workflow.proof_management.compiler_turn_adapter import (
    CompilerTurnAdapter,
    CompilerTurnDeadlineExceeded,
)


class _FailingCompiler:
    def compile_current_state(self, *, turn_evidence=None):
        raise RuntimeError("backend timed out")


def test_compiler_failure_after_shared_deadline_is_not_an_abstention() -> None:
    readings = iter((10.0, 12.0))
    audit: list[dict] = []
    adapter = CompilerTurnAdapter(
        node_id="Tree-deadline",
        service=_FailingCompiler(),
        session_id=lambda: "session",
        audit=audit.append,
        clock=lambda: next(readings),
    )

    with pytest.raises(CompilerTurnDeadlineExceeded):
        adapter.compile_current(deadline=11.0)

    assert audit[-1]["kind"] == "proof_state_compiler.failed"
