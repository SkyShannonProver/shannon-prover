"""Live no-model sentinel for manager-to-compiler turn-evidence binding."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from core.easycrypt.committed_history import read_committed_tactics
from core.easycrypt.proof_lifecycle import (
    has_discharged_goals,
    is_session_completion_candidate,
)
from workflow.proof_node_manager import ProofNodeManager


_REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--lemma", required=True)
    parser.add_argument("--tactic", required=True)
    parser.add_argument("--surface-profile", required=True)
    parser.add_argument("--include-dir", default="easycrypt-src/theories")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--expect-closed",
        action="store_true",
        help="Require the tactic to close the candidate, then save qed and recompile.",
    )
    args = parser.parse_args(argv)

    source = _resolve_repo_path(args.file)
    run_dir = _resolve_repo_path(args.run_dir)
    if not source.is_file() or not _is_relative_to(source, _REPO_ROOT):
        parser.error("--file must resolve to a repository source file")
    artifacts = (_REPO_ROOT / "artifacts").resolve()
    if not _is_relative_to(run_dir, artifacts):
        parser.error("--run-dir must resolve under repository artifacts/")
    if run_dir.exists() and any(run_dir.iterdir()):
        parser.error("--run-dir must be absent or empty")

    session_tag = "psc_manager_turn_sentinel_" + uuid.uuid4().hex[:12]
    manager = ProofNodeManager(
        file_path=str(source),
        lemma_name=args.lemma,
        include_dir=args.include_dir,
        session_tag=session_tag,
        node_id="manager-turn-sentinel",
        run_dir=run_dir,
        project_root=_REPO_ROOT,
        surface_profile=args.surface_profile,
    )
    session_dir = (_REPO_ROOT / manager.repl.session_dir).resolve()
    report: dict[str, Any]
    try:
        manager.bootstrap(replay_prefix=[])
        before_history = read_committed_tactics(session_dir)
        turn = manager.handle_agent_message(json.dumps({
            "intent": "commit_tactic",
            "payload": {"tactic": args.tactic},
        }))
        after_history = read_committed_tactics(session_dir)
        records = _jsonl(run_dir / "proof_node_manager_audit.jsonl")
        handled_index, after_turn = _records_after_latest_handled(records)
        completions = [
            record
            for record in after_turn
            if record.get("kind") == "proof_state_compiler.completed"
        ]
        failures = [
            record
            for record in after_turn
            if record.get("kind") == "proof_state_compiler.failed"
        ]
        primary = next(
            (
                action
                for action in turn.manager_actions
                if isinstance(action, dict)
                and action.get("label") != "managed_goal_view"
            ),
            {},
        )
        accepted = (
            primary.get("outcome_kind") == "accepted"
            and primary.get("proof_state_effect") == "changed"
        )
        history_delta_exact = (
            after_history == [*before_history, args.tactic]
        )
        state_version_unchanged_by_compiler = (
            turn.snapshot is not None
            and manager.state_version == turn.snapshot.state_version
        )
        close_status = _proof_status(turn.workspace_view)
        goals_discharged = has_discharged_goals(close_status)
        qed_accepted: bool | None = None
        qed_history_delta_exact: bool | None = None
        post_qed_completions: list[dict[str, Any]] = []
        post_qed_failures: list[dict[str, Any]] = []
        post_qed_state_version_unchanged: bool | None = None
        post_qed_status = ""
        post_qed_session_completion_candidate = False
        if args.expect_closed:
            qed_turn = manager.handle_agent_message(json.dumps({
                "intent": "commit_tactic",
                "payload": {"tactic": "qed."},
            }))
            final_history = read_committed_tactics(session_dir)
            qed_primary = next(
                (
                    action
                    for action in qed_turn.manager_actions
                    if isinstance(action, dict)
                    and action.get("label") != "managed_goal_view"
                ),
                {},
            )
            qed_accepted = bool(
                qed_primary.get("outcome_kind") == "accepted"
                and qed_primary.get("proof_state_effect") == "changed"
            )
            qed_history_delta_exact = final_history == [*after_history, "qed."]
            post_qed_state_version_unchanged = bool(
                qed_turn.snapshot is not None
                and manager.state_version == qed_turn.snapshot.state_version
            )
            post_qed_status = _proof_status(qed_turn.workspace_view)
            post_qed_session_completion_candidate = (
                is_session_completion_candidate(post_qed_status)
            )
            records = _jsonl(run_dir / "proof_node_manager_audit.jsonl")
            _, after_qed = _records_after_latest_handled(records)
            post_qed_completions = [
                record
                for record in after_qed
                if record.get("kind") == "proof_state_compiler.completed"
            ]
            post_qed_failures = [
                record
                for record in after_qed
                if record.get("kind") == "proof_state_compiler.failed"
            ]
        passed = bool(
            handled_index >= 0
            and accepted
            and history_delta_exact
            and state_version_unchanged_by_compiler
            and completions
            and not failures
            and (
                not args.expect_closed
                or (
                    goals_discharged
                    and qed_accepted
                    and qed_history_delta_exact
                    and post_qed_session_completion_candidate
                    and post_qed_state_version_unchanged
                    and post_qed_completions
                    and not post_qed_failures
                )
            )
        )
        report = {
            "kind": "proof_state_compiler_manager_turn_sentinel",
            "passed": passed,
            "surface_profile": args.surface_profile,
            "source": str(source.relative_to(_REPO_ROOT)),
            "lemma": args.lemma,
            "tactic_accepted": accepted,
            "history_delta_exact": history_delta_exact,
            "state_version_unchanged_by_compiler": (
                state_version_unchanged_by_compiler
            ),
            "post_turn_compiler_completions": len(completions),
            "post_turn_compiler_failures": len(failures),
            "expect_closed": args.expect_closed,
            "goal_discharge_status": close_status,
            "goals_discharged": goals_discharged,
            "qed_accepted": qed_accepted,
            "qed_history_delta_exact": qed_history_delta_exact,
            "post_qed_status": post_qed_status,
            "post_qed_session_completion_candidate": (
                post_qed_session_completion_candidate
            ),
            "post_qed_state_version_unchanged_by_compiler": (
                post_qed_state_version_unchanged
            ),
            "post_qed_compiler_completions": len(post_qed_completions),
            "post_qed_compiler_failures": len(post_qed_failures),
            "compiler_payload_bytes": [
                int((record.get("admission") or {}).get("compiler_markdown_bytes") or 0)
                for record in completions
                if isinstance(record.get("admission"), dict)
            ],
        }
    finally:
        manager.repl.close()
        if _is_relative_to(session_dir, _REPO_ROOT) and session_dir.name.startswith(
            ".ec_session_psc_manager_turn_sentinel_"
        ):
            shutil.rmtree(session_dir, ignore_errors=True)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


def _jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _records_after_latest_handled(
    records: list[dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    handled_index = max(
        (
            index
            for index, record in enumerate(records)
            if record.get("kind") == "agent_intent.handled"
        ),
        default=-1,
    )
    return (
        handled_index,
        records[handled_index + 1:] if handled_index >= 0 else [],
    )


def _proof_status(workspace_view: dict[str, Any]) -> str:
    proof_status = (
        workspace_view.get("proof_status")
        if isinstance(workspace_view.get("proof_status"), dict)
        else {}
    )
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
