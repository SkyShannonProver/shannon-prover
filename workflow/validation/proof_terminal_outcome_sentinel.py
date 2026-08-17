"""Live no-model sentinel for the complete terminal-outcome ownership chain."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path

from core.easycrypt.committed_history import read_committed_tactics
from workflow.agents.prover_writeback import (
    _extract_tactics_from_candidate,
    _write_and_verify_proof,
)
from workflow.proof_node_manager import ProofNodeManager
from workflow.proof_node_runtime import render_manager_followup
from workflow.schemas.prover_result import PROVER_RUN_VERIFIED, ProverResult
from workflow.session_observer import observe_session
from workflow.tree.result import SessionClosureCandidate
from workflow.validation.run_report_bundle import _outcome


_REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--include-dir", default="easycrypt-src/theories")
    args = parser.parse_args(argv)

    run_dir = _resolve_repo_path(args.run_dir)
    artifacts_root = (_REPO_ROOT / "artifacts").resolve()
    if not _is_relative_to(run_dir, artifacts_root):
        parser.error("--run-dir must resolve under repository artifacts/")
    if run_dir.exists() and any(run_dir.iterdir()):
        parser.error("--run-dir must be absent or empty")
    run_dir.mkdir(parents=True, exist_ok=True)
    iteration_dir = run_dir / "iteration_1"
    iteration_dir.mkdir()

    lemma = "terminal_outcome_sentinel"
    source = run_dir / "TerminalOutcomeSentinel.ec"
    source.write_text(
        f"lemma {lemma} : true.\nproof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    session_tag = "proof_terminal_outcome_" + uuid.uuid4().hex[:12]
    manager = ProofNodeManager(
        file_path=str(source),
        lemma_name=lemma,
        include_dir=args.include_dir,
        session_tag=session_tag,
        node_id="terminal-outcome-sentinel",
        run_dir=iteration_dir,
        project_root=_REPO_ROOT,
        surface_profile="l1_goal_projection",
    )
    session_dir = (_REPO_ROOT / manager.repl.session_dir).resolve()
    report: dict[str, object]
    try:
        manager.bootstrap(replay_prefix=[])
        close_turn = manager.handle_agent_message(json.dumps({
            "intent": "commit_tactic",
            "payload": {"tactic": "trivial."},
        }))
        close_status = _proof_status(close_turn.workspace_view)
        close_panel = render_manager_followup(
            close_turn,
            1,
            {"intent": "commit_tactic", "payload": {"tactic": "trivial."}},
            surface_profile=manager.surface_profile,
        )
        qed_turn = manager.handle_agent_message(json.dumps({
            "intent": "commit_tactic",
            "payload": {"tactic": "qed."},
        }))
        post_qed_status = _proof_status(qed_turn.workspace_view)
        post_qed_panel = render_manager_followup(
            qed_turn,
            2,
            {"intent": "commit_tactic", "payload": {"tactic": "qed."}},
            surface_profile=manager.surface_profile,
        )
        finish_turn = manager.handle_agent_message(json.dumps({
            "intent": "finish",
            "payload": {},
        }))
        finish_panel = render_manager_followup(
            finish_turn,
            3,
            {"intent": "finish", "payload": {}},
            surface_profile=manager.surface_profile,
        )
        snapshot = observe_session(session_dir)
        candidate = SessionClosureCandidate.from_snapshot(
            node_id="Tree-sentinel",
            snapshot=snapshot,
            target_file=str(source),
            target_lemma=lemma,
        )
        history_before_finalization = read_committed_tactics(session_dir)
        tactics = _extract_tactics_from_candidate(candidate)
        verification_evidence = _write_and_verify_proof(
            source, lemma, tactics, candidate, include_dir=args.include_dir,
        ) if tactics else None
        verified = bool(
            verification_evidence and verification_evidence.passed
        )
        history_after_finalization = read_committed_tactics(session_dir)
        result = ProverResult(
            status=PROVER_RUN_VERIFIED if verified else "infrastructure_invalid",
            completion_candidate=candidate.to_dict(),
            verification=(
                {
                    "status": "pass",
                    "method": "easycrypt_offline",
                    "candidate_id": candidate.candidate_id,
                }
                if verified
                else {"status": "fail", "candidate_id": candidate.candidate_id}
            ),
            infrastructure_errors=(
                [] if verified else ["sentinel finalization failed"]
            ),
            event_contract_checked=True,
            event_contract_ok=verified,
        )
        result.save(iteration_dir / "prover_run_result.json")
        summary = {
            "final_proved": result.is_verified,
            "final_prover_result_id": result.result_id,
            "final_prover_result_status": result.status,
        }
        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_outcome = _outcome(iteration_dir)
        passed = bool(
            close_status == "goals_discharged_pending_qed"
            and "`goals_discharged_pending_qed`" in close_panel
            and "commit `qed.`" in close_panel
            and post_qed_status in {
                "session_closed_pending_verification",
                "verified",
            }
            and "`session_closed_pending_verification`" in post_qed_panel
            and "submit `finish`" in post_qed_panel
            and finish_turn.ok
            and "Finish accepted" in finish_panel
            and "Stop submitting proof intents" in finish_panel
            and "Submit exactly one proof intent" not in finish_panel
            and "Submit exactly ONE proof intent" not in finish_panel
            and snapshot.qed_committed
            and candidate.candidate_id
            and tactics == ["trivial.", "qed."]
            and verified
            and history_after_finalization == history_before_finalization
            and result.is_verified
            and summary["final_proved"] is True
            and summary["final_prover_result_id"] == result.result_id
            and report_outcome == "verified"
        )
        report = {
            "kind": "proof_terminal_outcome_sentinel",
            "passed": passed,
            "close_status": close_status,
            "close_panel_status_visible": (
                "`goals_discharged_pending_qed`" in close_panel
                and "commit `qed.`" in close_panel
            ),
            "post_qed_status": post_qed_status,
            "post_qed_panel_status_visible": (
                "`session_closed_pending_verification`" in post_qed_panel
                and "submit `finish`" in post_qed_panel
            ),
            "finish_panel_terminal": (
                finish_turn.ok
                and "Finish accepted" in finish_panel
                and "Stop submitting proof intents" in finish_panel
                and "Submit exactly one proof intent" not in finish_panel
                and "Submit exactly ONE proof intent" not in finish_panel
            ),
            "qed_committed": snapshot.qed_committed,
            "candidate_id": candidate.candidate_id,
            "candidate_tactic_count": candidate.tactic_count,
            "extracted_tactics": tactics,
            "offline_verified": verified,
            "history_unchanged_by_finalization": (
                history_after_finalization == history_before_finalization
            ),
            "prover_result_id": result.result_id,
            "prover_result_status": result.status,
            "summary_matches_result": (
                summary["final_prover_result_id"] == result.result_id
                and summary["final_prover_result_status"] == result.status
                and summary["final_proved"] == result.is_verified
            ),
            "report_outcome": report_outcome,
        }
    except Exception as exc:
        report = {
            "kind": "proof_terminal_outcome_sentinel",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        manager.repl.close()
        if _is_relative_to(session_dir, _REPO_ROOT) and session_dir.name.startswith(
            ".ec_session_proof_terminal_outcome_"
        ):
            shutil.rmtree(session_dir, ignore_errors=True)

    (run_dir / "sentinel_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") is True else 2


def _proof_status(workspace_view: dict) -> str:
    proof_status = workspace_view.get("proof_status")
    if not isinstance(proof_status, dict):
        return ""
    return str(proof_status.get("status") or "").strip().lower()


def _resolve_repo_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (_REPO_ROOT / path).resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
