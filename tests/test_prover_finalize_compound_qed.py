"""Regression: finalize must report proved when the proof closed via a
compound final step and a spurious extra ``qed.`` was rejected and undone.

Mirrors the pr_sample_double run of 2026-07-15 (session 8c0580bb): the agent
committed ``by move=> &hr _. qed.`` as one step (proof genuinely closed,
43 committed steps, ``proof.candidate_closed`` emitted), then submitted one
more ``qed.`` which EasyCrypt rejected ("cannot process [save] outside a
proof script") but which still landed in committed history, then removed it
with ``undo_last_step``. Finalize saw a clean 43-line history whose closing
``qed.`` was embedded in the compound line — and ``closed_history_tactics``
required a standalone ``qed`` line, so extraction returned [] and the run
ended Proved: False despite the earlier proved-it event.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import _pathsetup  # noqa: F401  (repo root on sys.path)

from core.easycrypt.committed_history import (  # noqa: E402
    closed_history_tactics,
    split_trailing_qed,
)
from core.easycrypt.session_events import append_event  # noqa: E402
from workflow.agents import prover, prover_writeback  # noqa: E402
from workflow.proof_acceptance import (  # noqa: E402
    validate_candidate_event_contract,
)

# 42 accepted steps + the compound closer = the clean 43-step history that
# finalize must verify. Generic tactics; the shape (compound final line) is
# what matters.
_CLEAN_STEPS = ["proc." ] + ["auto => />."] * 41 + ["by move=> &hr _. qed."]
_COMPOUND_CLOSER = _CLEAN_STEPS[-1]


def _write_admitted_lemma(path: Path) -> None:
    path.write_text(
        "lemma L : true.\n"
        "proof.\n"
        "  admit.\n"
        "qed.\n",
        encoding="utf-8",
    )


def _tactic_step(d: Path, tactic: str, *, lines_before: int, closes: bool,
                 rejected: bool = False) -> None:
    append_event(d, "tool.called", {
        "name": "next",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
    })
    append_event(d, "tactic.submitted", {
        "tactic": tactic,
        "history_lines_before": lines_before,
        "line_count": 1,
    })
    append_event(d, "goal.changed", {
        "tactic": tactic,
        "goals_before": 1 if not rejected else 0,
        "goals_after": 0 if (closes or rejected) else 1,
        "no_more_goals": closes or rejected,
        "async_check_close": False,
        "no_progress": False,
        "candidate_closed": closes,
    })
    result = {
        "tactic": tactic,
        "status": "ok" if not rejected else "error",
        "history_committed": True,
        "candidate_closed": closes,
    }
    if rejected:
        result["has_new_error"] = True
        result["error_lines"] = [
            "[error-0-4]cannot process [save] outside a proof script",
        ]
    append_event(d, "tactic.result", result)
    if closes:
        append_event(d, "proof.candidate_closed", {
            "tactic": tactic,
            "goals_before": 1,
            "goals_after": 0,
            "no_more_goals": True,
            "async_check_close": False,
        })
    append_event(d, "tool.result", {
        "name": "next",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
        "exit_code": 0,
        "status": "ok",
    })


def _build_session(d: Path) -> None:
    """Closed proof, then a rejected extra qed lands in history, then undo."""
    append_event(d, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })
    for i, tactic in enumerate(_CLEAN_STEPS):
        _tactic_step(d, tactic, lines_before=i,
                     closes=(tactic is _COMPOUND_CLOSER))
    # Spurious step 44: extra qed. rejected by EasyCrypt but committed.
    _tactic_step(d, "qed.", lines_before=len(_CLEAN_STEPS),
                 closes=False, rejected=True)
    (d / "history.ec").write_text(
        "\n".join(_CLEAN_STEPS + ["qed."]) + "\n", encoding="utf-8",
    )
    # Agent notices and undoes it — history back to the clean 43 steps.
    append_event(d, "tool.called", {
        "name": "undo_last_step",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
    })
    append_event(d, "tactic.undone", {
        "status": "ok",
        "undone_tactic": "qed.",
        "remaining_steps": len(_CLEAN_STEPS),
        "history_lines_after": len(_CLEAN_STEPS),
    })
    append_event(d, "tool.result", {
        "name": "undo_last_step",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
        "exit_code": 0,
        "status": "ok",
    })
    (d / "history.ec").write_text(
        "\n".join(_CLEAN_STEPS) + "\n", encoding="utf-8",
    )


def test_compound_closer_history_counts_as_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        session_dir = Path(td) / ".ec_session"
        session_dir.mkdir()
        _build_session(session_dir)

        tactics = closed_history_tactics(session_dir)
        # Compound closer is normalized into tactic + standalone qed.
        assert tactics == _CLEAN_STEPS[:-1] + ["by move=> &hr _.", "qed."]

        gate = validate_candidate_event_contract(session_dir)
        assert gate.ok
        assert gate.candidate_closed


def test_finalize_reports_proved_after_rejected_extra_qed_and_undo() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ec_path = root / "A.ec"
        session_dir = root / ".ec_session"
        session_dir.mkdir()
        _write_admitted_lemma(ec_path)
        _build_session(session_dir)

        tactics = prover._extract_tactics_from_session(
            "L",
            1,
            "",
            preferred_session_dir=session_dir,
            scan_project_sessions=False,
        )
        assert tactics, (
            "finalize must extract a closed proof from the clean history"
        )

        pruned = {"tactics": None}
        original_prune = prover_writeback._prune_failing_tactics
        original_verify = prover_writeback._verify_ec_file
        try:
            def _prune(*a, **kw):
                pruned["tactics"] = list(a[2])
                return list(a[2])

            prover_writeback._prune_failing_tactics = _prune
            prover_writeback._verify_ec_file = lambda *a, **kw: (True, "")
            ok = prover._write_and_verify_proof(
                ec_path, "L", tactics,
                session_proved=True,
                ec_session_dir=session_dir,
            )
        finally:
            prover_writeback._prune_failing_tactics = original_prune
            prover_writeback._verify_ec_file = original_verify

        assert ok, "finalize must verify the clean 43-step history"
        # Verification ran against the clean history (43 steps, qed split
        # out), not one that still carries the spurious step 44.
        assert pruned["tactics"] == _CLEAN_STEPS[:-1] + [
            "by move=> &hr _.", "qed.",
        ]
        body = ec_path.read_text(encoding="utf-8")
        assert body.count("qed.") == 1, (
            "compound closer must not produce a double qed"
        )
        assert "by move=> &hr _." in body
        assert "admit." not in body


def test_write_and_verify_normalizes_embedded_qed_directly() -> None:
    """Even if callers hand _write_and_verify_proof a raw compound closer,
    the written proof block must contain exactly one qed."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ec_path = root / "A.ec"
        session_dir = root / ".ec_session"
        session_dir.mkdir()
        _write_admitted_lemma(ec_path)
        _build_session(session_dir)

        original_prune = prover_writeback._prune_failing_tactics
        original_verify = prover_writeback._verify_ec_file
        try:
            prover_writeback._prune_failing_tactics = lambda *a, **kw: list(a[2])
            prover_writeback._verify_ec_file = lambda *a, **kw: (True, "")
            ok = prover._write_and_verify_proof(
                ec_path, "L", ["proc.", "by move=> &hr _. qed."],
                ec_session_dir=session_dir,
            )
        finally:
            prover_writeback._prune_failing_tactics = original_prune
            prover_writeback._verify_ec_file = original_verify

        assert ok
        assert ec_path.read_text(encoding="utf-8").count("qed.") == 1


def test_split_trailing_qed_edge_cases() -> None:
    assert split_trailing_qed([]) == []
    assert split_trailing_qed(["auto.", "qed."]) == ["auto.", "qed."]
    assert split_trailing_qed(["proc; islossless. qed."]) == [
        "proc; islossless.", "qed.",
    ]
    # Identifier tails must not be mistaken for the qed keyword.
    assert split_trailing_qed(["rewrite my_qed."]) == ["rewrite my_qed."]
    assert split_trailing_qed(["apply foo'qed."]) == ["apply foo'qed."]


if __name__ == "__main__":
    test_compound_closer_history_counts_as_closed()
    test_finalize_reports_proved_after_rejected_extra_qed_and_undo()
    test_write_and_verify_normalizes_embedded_qed_directly()
    test_split_trailing_qed_edge_cases()
    print("PASS test_prover_finalize_compound_qed")
