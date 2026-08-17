"""Pure-Python tests for prover fail-closed acceptance gates."""
from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_events import append_event, events_of_type, read_events  # noqa: E402
from workflow.agents import prover, prover_writeback  # noqa: E402
from workflow.proof_acceptance import validate_acceptance_event_contract  # noqa: E402
from workflow.session_observer import observe_session  # noqa: E402
from workflow.tree.result import SessionClosureCandidate  # noqa: E402


def _write_admitted_lemma(path: Path) -> None:
    path.write_text(
        "lemma L : true.\n"
        "proof.\n"
        "  admit.\n"
        "qed.\n",
        encoding="utf-8",
    )


def _append_closed_stream(d: Path) -> None:
    append_event(d, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })
    append_event(d, "tool.called", {
        "name": "commit",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
    })
    append_event(d, "tactic.submitted", {
        "tactic": "qed.",
        "history_lines_before": 0,
        "line_count": 1,
    })
    append_event(d, "goal.changed", {
        "tactic": "qed.",
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
        "no_progress": False,
        "candidate_closed": True,
    })
    append_event(d, "tactic.result", {
        "tactic": "qed.",
        "status": "ok",
        "history_committed": True,
        "candidate_closed": True,
    })
    append_event(d, "proof.candidate_closed", {
        "tactic": "qed.",
        "goals_before": 1,
        "goals_after": 0,
        "no_more_goals": True,
        "async_check_close": False,
    })
    append_event(d, "tool.result", {
        "name": "commit",
        "mutates_proof_state": True,
        "session_dir": str(d.resolve()),
        "exit_code": 0,
        "status": "ok",
    })


def _candidate(
    session_dir: Path,
    ec_path: Path,
    *,
    tactics: str = "trivial.\nqed.\n",
) -> SessionClosureCandidate:
    (session_dir / "current.out").write_text(
        "[1|check]>\nNo more goals\n[2|check]>\n",
        encoding="utf-8",
    )
    (session_dir / "history.ec").write_text(tactics, encoding="utf-8")
    snapshot = observe_session(session_dir)
    return SessionClosureCandidate.from_snapshot(
        node_id="Tree-test",
        snapshot=snapshot,
        target_file=str(ec_path),
        target_lemma="L",
    )


def test_write_and_verify_rejects_missing_event_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ec_path = root / "A.ec"
        session_dir = root / ".ec_session"
        session_dir.mkdir()
        _write_admitted_lemma(ec_path)
        _append_closed_stream(session_dir)
        candidate = _candidate(session_dir, ec_path)
        (session_dir / "events.jsonl").unlink()

        calls = {"verify": 0}
        original_prune = prover_writeback._prune_failing_tactics
        original_verify = prover_writeback._verify_ec_file
        try:
            prover_writeback._prune_failing_tactics = lambda *a, **kw: list(a[2])

            def _verify(*_args, **_kwargs):
                calls["verify"] += 1
                return True, ""

            prover_writeback._verify_ec_file = _verify
            ok = prover._write_and_verify_proof(
                ec_path, "L", ["trivial.", "qed."],
                candidate,
            )
        finally:
            prover_writeback._prune_failing_tactics = original_prune
            prover_writeback._verify_ec_file = original_verify

        assert not ok.passed
        assert calls["verify"] == 0
        assert "admit." in ec_path.read_text(encoding="utf-8")


def test_write_and_verify_emits_final_acceptance_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ec_path = root / "A.ec"
        session_dir = root / ".ec_session"
        session_dir.mkdir()
        _write_admitted_lemma(ec_path)
        _append_closed_stream(session_dir)
        candidate = _candidate(session_dir, ec_path)

        original_prune = prover_writeback._prune_failing_tactics
        original_verify = prover_writeback._verify_ec_file
        try:
            prover_writeback._prune_failing_tactics = lambda *a, **kw: list(a[2])
            prover_writeback._verify_ec_file = lambda *a, **kw: (True, "")
            ok = prover._write_and_verify_proof(
                ec_path, "L", ["trivial.", "qed."],
                candidate,
            )
        finally:
            prover_writeback._prune_failing_tactics = original_prune
            prover_writeback._verify_ec_file = original_verify

        assert ok.passed
        assert "trivial." in ec_path.read_text(encoding="utf-8")
        gate = validate_acceptance_event_contract(session_dir)
        assert gate.ok
        assert gate.verification_status == "pass"


def test_write_and_verify_records_extracted_fallback_hygiene() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ec_path = root / "A.ec"
        session_dir = root / ".ec_session"
        session_dir.mkdir()
        _write_admitted_lemma(ec_path)
        _append_closed_stream(session_dir)
        candidate = _candidate(session_dir, ec_path)

        original_prune = prover_writeback._prune_failing_tactics
        original_verify = prover_writeback._verify_ec_file
        original_extracted = prover_writeback._verify_lemma_extracted
        try:
            prover_writeback._prune_failing_tactics = lambda *a, **kw: list(a[2])
            prover_writeback._verify_ec_file = lambda *a, **kw: (
                False,
                "[error-3-0] [/tmp/A.ec: line 822] cannot prove goal (strict)",
            )
            prover_writeback._verify_lemma_extracted = lambda *a, **kw: True
            ok = prover._write_and_verify_proof(
                ec_path, "L", ["trivial.", "qed."],
                candidate,
            )
        finally:
            prover_writeback._prune_failing_tactics = original_prune
            prover_writeback._verify_ec_file = original_verify
            prover_writeback._verify_lemma_extracted = original_extracted

        assert ok.passed
        events = events_of_type(read_events(session_dir), "verification.completed")
        payload = events[-1]["payload"]
        assert payload["status"] == "pass"
        assert payload["reason"] == "extracted_lemma"
        assert payload["full_file_status"] == "fail"
        assert payload["extracted_status"] == "pass"
        assert "line 822" in payload["full_file_error_excerpt"]


def test_extract_tactics_requires_validated_winner_session_history() -> None:
    with tempfile.TemporaryDirectory() as td:
        session_dir = Path(td) / ".ec_session_winner"
        session_dir.mkdir()
        _append_closed_stream(session_dir)
        ec_path = Path(td) / "A.ec"
        _write_admitted_lemma(ec_path)
        candidate = _candidate(
            session_dir,
            ec_path,
            tactics="right.\nqed.\n",
        )

        tactics = prover._extract_tactics_from_candidate(candidate)
        assert tactics == ["right.", "qed."]


def test_final_tactic_extraction_cannot_fall_back_to_sibling_or_prose() -> None:
    assert tuple(inspect.signature(
        prover._extract_tactics_from_candidate,
    ).parameters) == ("candidate",)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        winner = root / ".ec_session_prover_tree_0_0"
        sibling = root / ".ec_session_prover_tree_0_1"
        winner.mkdir()
        sibling.mkdir()
        _append_closed_stream(winner)
        _append_closed_stream(sibling)
        (sibling / "history.ec").write_text(
            "sibling_only.\nqed.\n",
            encoding="utf-8",
        )

        original_root = prover_writeback._PROJECT_ROOT
        try:
            prover_writeback._PROJECT_ROOT = root
            assert prover._extract_tactics_from_candidate(None) == []
        finally:
            prover_writeback._PROJECT_ROOT = original_root

        # Even a closed-looking winner history is not writeback authority
        # without its structured candidate-close contract.
        unverified = root / ".ec_session_unverified"
        unverified.mkdir()
        (unverified / "history.ec").write_text(
            "prose_only_shape.\nqed.\n",
            encoding="utf-8",
        )
        assert prover._extract_tactics_from_candidate(None) == []


def test_extract_partial_tactics_without_qed_is_reporting_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        session_dir = Path(td) / ".ec_session_partial"
        session_dir.mkdir()
        (session_dir / "history.ec").write_text(
            "proc.\nwp.\n",
            encoding="utf-8",
        )

        closed = prover._extract_tactics_from_candidate(None)
        partial = prover._extract_partial_tactics_from_sessions(
            session_dirs=[str(session_dir)],
        )

        assert closed == []
        assert partial == ["proc.", "wp."]


if __name__ == "__main__":
    test_write_and_verify_rejects_missing_event_contract()
    test_write_and_verify_emits_final_acceptance_event()
    test_write_and_verify_records_extracted_fallback_hygiene()
    test_extract_tactics_requires_validated_winner_session_history()
    test_final_tactic_extraction_cannot_fall_back_to_sibling_or_prose()
    test_extract_partial_tactics_without_qed_is_reporting_only()
    print("PASS test_prover_acceptance")
