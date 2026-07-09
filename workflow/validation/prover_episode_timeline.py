"""Build prover-facing episode timelines from replay artifacts.

CommandSummary was the historical single-step view. This module projects old
summary artifacts into an ordered timeline so replay reports can see how the
proof evolved across commands without sorting hash filenames or parsing stdout.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from core.easycrypt.session_command_summary import command_summary_workspace_metrics
from workflow.validation.replay_artifacts import (
    ReplayArtifact,
    iter_replay_artifacts,
    load_command_summary_artifacts,
)
from core.easycrypt.value_shapes import as_dict as _dict, as_list as _list


TIMELINE_SCHEMA_VERSION = 1
TIMELINE_KIND = "prover_episode_timeline"


def build_episode_timeline(artifact: ReplayArtifact) -> dict[str, Any]:
    items = load_command_summary_artifacts(artifact)
    steps: list[dict[str, Any]] = []
    previous_goal_hash = ""
    for idx, item in enumerate(items, start=1):
        summary = item.summary
        proof = _dict(summary.get("proof"))
        transition = _dict(summary.get("transition"))
        mutation = _dict(summary.get("mutation"))
        current_goal = _dict(summary.get("current_goal"))
        workspace_metrics = command_summary_workspace_metrics(summary)
        goal_hash = str(proof.get("goal_hash") or "")
        step = {
            "step": idx,
            "event_index": item.event_index,
            "command": str(summary.get("command") or ""),
            "command_status": str(summary.get("command_status") or ""),
            "ok": bool(summary.get("ok")),
            "tactic": str(transition.get("tactic") or proof.get("latest_tactic") or ""),
            "accepted_count": _int(mutation.get("accepted_count")),
            "attempted_count": _int(mutation.get("attempted_count")),
            "rollback_count": _int(mutation.get("rollback_count")),
            "proof_status": str(proof.get("status") or ""),
            "goal_type": str(proof.get("goal_type") or current_goal.get("goal_type") or "unknown"),
            "num_remaining": proof.get("num_remaining"),
            "num_remaining_determined": bool(
                proof.get("num_remaining_determined")
            ),
            "goal_hash": goal_hash,
            "goal_hash_changed": bool(
                previous_goal_hash and goal_hash and goal_hash != previous_goal_hash
            ),
            "history_tactic_count": _int(proof.get("history_tactic_count")),
            "transition_kind": str(transition.get("kind") or ""),
            "transition_status": str(transition.get("status") or ""),
            "goals_before": transition.get("goals_before"),
            "goals_after": transition.get("goals_after"),
            "candidate_closed": bool(transition.get("candidate_closed")),
            "no_progress": bool(transition.get("no_progress")),
            "no_progress_reason": str(transition.get("no_progress_reason") or ""),
            "primary_action": str(workspace_metrics.get("primary_action") or ""),
            "runnable_tactic_count": _int(
                workspace_metrics.get("runnable_tactic_count")
            ),
            "inspection_action_count": _int(
                workspace_metrics.get("inspection_action_count")
            ),
            "strategy_hint_count": _int(
                workspace_metrics.get("strategy_hint_count")
            ),
            "error_count": len(_list(summary.get("errors"))),
            "warning_count": len(_list(summary.get("warnings"))),
            "artifact": str(item.path),
        }
        step["prover_observations"] = _step_observations(step)
        steps.append(step)
        if goal_hash:
            previous_goal_hash = goal_hash

    return {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "kind": TIMELINE_KIND,
        "proof_id": artifact.summary.proof_id,
        "file": artifact.summary.file,
        "lemma": artifact.summary.lemma,
        "outcome": artifact.summary.outcome,
        "step_count": len(steps),
        "rollup": _rollup(steps),
        "steps": steps,
        "notes": _episode_notes(steps),
    }


def build_replay_root_timelines(root: Path) -> dict[str, Any]:
    timelines = [build_episode_timeline(a) for a in iter_replay_artifacts(root)]
    return {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "kind": "prover_episode_timeline_report",
        "artifact_root": str(Path(root).resolve()),
        "proof_count": len(timelines),
        "step_count": sum(_int(t.get("step_count")) for t in timelines),
        "timelines": timelines,
    }


def write_report(root: Path, report: dict[str, Any]) -> Path:
    path = Path(root) / "prover_episode_timelines.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _rollup(steps: list[dict[str, Any]]) -> dict[str, Any]:
    transition_counts = Counter(str(s.get("transition_kind") or "") for s in steps)
    primary_counts = Counter(str(s.get("primary_action") or "") for s in steps)
    proof_status_counts = Counter(str(s.get("proof_status") or "") for s in steps)
    return {
        "transition_counts": dict(sorted(transition_counts.items())),
        "primary_action_counts": dict(sorted(primary_counts.items())),
        "proof_status_counts": dict(sorted(proof_status_counts.items())),
        "failed_command_count": sum(1 for s in steps if not s.get("ok")),
        "no_progress_count": sum(1 for s in steps if s.get("no_progress")),
        "goal_hash_change_count": sum(1 for s in steps if s.get("goal_hash_changed")),
        "candidate_closed_step": next(
            (s["step"] for s in steps if s.get("proof_status") == "candidate_closed"),
            0,
        ),
        "final_primary_action": str(steps[-1].get("primary_action") or "") if steps else "",
        "final_proof_status": str(steps[-1].get("proof_status") or "") if steps else "",
    }


def _step_observations(step: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if step.get("proof_status") == "candidate_closed":
        out.append("candidate_closed_verify_next")
    if step.get("proof_status") == "verified":
        out.append("verified_stop")
    if not step.get("ok"):
        out.append("failed_command_diagnose_next")
    if step.get("goal_hash_changed"):
        out.append("active_goal_changed")
    if step.get("transition_kind") == "state_changed_same_goal_count":
        out.append("same_goal_count_state_changed")
    if step.get("transition_kind") == "committed_unknown_effect":
        out.append("effect_unknown_from_goal_count")
    if step.get("primary_action") == "consider_strategy_hint":
        out.append("strategy_hint_before_direct_tactic")
    if step.get("primary_action") == "try_tactic":
        out.append("direct_tactic_available")
    if step.get("no_progress"):
        out.append("no_progress_recorded")
    return out


def _episode_notes(steps: list[dict[str, Any]]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    if not steps:
        return [{
            "code": "timeline.empty",
            "message": "No CommandSummary steps were available for this proof.",
        }]
    unknown = [s for s in steps if s.get("transition_kind") == "committed_unknown_effect"]
    if unknown:
        notes.append({
            "code": "timeline.has_unknown_effect_steps",
            "message": (
                f"{len(unknown)} step(s) were committed but their goal-count "
                "effect was indeterminate; inspect the linked summary if this "
                "matters for strategy."
            ),
        })
    if not any(s.get("proof_status") == "candidate_closed" for s in steps):
        notes.append({
            "code": "timeline.no_candidate_closed_step",
            "message": "No step reached candidate_closed in the prover timeline.",
        })
    repeated_strategy = sum(
        1 for s in steps if s.get("primary_action") == "consider_strategy_hint"
    )
    if repeated_strategy >= 3:
        notes.append({
            "code": "timeline.strategy_hint_heavy",
            "message": (
                f"{repeated_strategy} step(s) asked the prover to consider "
                "strategy hints; direct tactic guidance was not always enough."
            ),
        })
    return notes




def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact-root", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write-report", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.artifact_root)
    report = build_replay_root_timelines(root)
    if not args.no_write_report:
        write_report(root, report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "PROVER-EPISODE-TIMELINE: "
            f"proofs={report['proof_count']} steps={report['step_count']}"
        )
        for timeline in report["timelines"]:
            rollup = timeline.get("rollup") or {}
            print(
                f"- {timeline.get('lemma')}: steps={timeline.get('step_count')} "
                f"final={rollup.get('final_proof_status')} "
                f"primary={rollup.get('final_primary_action')} "
                f"notes={len(timeline.get('notes') or [])}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
