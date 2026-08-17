"""Independent evaluator for the two-failure chained recovery micro."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from workflow.validation.proof_state_compiler_chained_recovery_micro import (
    CAMPAIGN_SHA256,
    INITIAL_REJECTED_TACTIC,
    MAX_LIVE_TURNS,
    REPEATS,
)


ROOT = Path(__file__).resolve().parents[2]


def evaluate_bundle(
    model: dict[str, Any], preparation: dict[str, Any]
) -> dict[str, Any]:
    contract_errors: list[str] = []
    for label, bundle, mode in (
        ("model", model, "model_micro"),
        ("preparation", preparation, "prepare_only"),
    ):
        if bundle.get("kind") != "proof_state_compiler_chained_recovery_micro":
            contract_errors.append(f"{label} kind mismatch")
        if bundle.get("campaign_sha256") != CAMPAIGN_SHA256:
            contract_errors.append(f"{label} campaign hash mismatch")
        if bundle.get("mode") != mode:
            contract_errors.append(f"{label} mode mismatch")
        if bundle.get("git", {}).get("dirty") is not False:
            contract_errors.append(f"{label} worktree was not clean")
        if bundle.get("preparation_valid") is not True:
            contract_errors.append(f"{label} preparation did not pass")
    if preparation.get("trajectories") != []:
        contract_errors.append("preparation unexpectedly called the model")
    preparation_routes = preparation.get("preparation_routes")
    if not isinstance(preparation_routes, list) or len(preparation_routes) != 2:
        contract_errors.append("preparation route cardinality mismatch")
    elif not all(item.get("preparation_valid") is True for item in preparation_routes):
        contract_errors.append("a deterministic preparation route failed")

    trajectories = model.get("trajectories")
    if not isinstance(trajectories, list) or len(trajectories) != REPEATS:
        contract_errors.append("model trajectory cardinality mismatch")
        trajectories = []
    trajectory_reports = [
        _evaluate_trajectory(item, expected_repeat=index)
        for index, item in enumerate(trajectories, start=1)
    ]
    provider_valid = bool(
        len(trajectory_reports) == REPEATS
        and all(item["provider_valid"] for item in trajectory_reports)
    )
    complete_routes = sum(
        item["route_complete"] for item in trajectory_reports
    )
    contract_valid = not contract_errors
    experiment_valid = bool(
        contract_valid
        and model.get("experiment_valid") is True
        and provider_valid
    )
    decision = (
        "CHAIN_PASS"
        if experiment_valid and complete_routes == REPEATS
        else "NO_CHAIN_VALUE"
    )
    return {
        "kind": "proof_state_compiler_chained_recovery_micro_evaluation",
        "campaign_sha256": CAMPAIGN_SHA256,
        "contract_valid": contract_valid,
        "contract_errors": contract_errors,
        "experiment_valid": experiment_valid,
        "provider_valid": provider_valid,
        "complete_routes": complete_routes,
        "required_complete_routes": REPEATS,
        "decision": decision,
        "trajectory_reports": trajectory_reports,
        "aggregate_usage": _aggregate_usage(trajectory_reports),
    }


def _evaluate_trajectory(
    trajectory: dict[str, Any], *, expected_repeat: int
) -> dict[str, Any]:
    turns = trajectory.get("turns")
    turns = turns if isinstance(turns, list) else []
    first = turns[0] if turns else {}
    second = turns[1] if len(turns) > 1 else {}
    fixed = trajectory.get("fixed_trigger")
    fixed = fixed if isinstance(fixed, dict) else {}
    recorded_checks = trajectory.get("route_checks")
    recorded_checks = recorded_checks if isinstance(recorded_checks, dict) else {}
    recomputed = {
        "repeat_identity": trajectory.get("repeat") == expected_repeat,
        "fixed_trigger_exact": fixed.get("tactic") == INITIAL_REJECTED_TACTIC,
        "fixed_trigger_failed_unchanged": (
            fixed.get("failed_unchanged") is True
        ),
        "bounded_live_turns": len(turns) == MAX_LIVE_TURNS,
        "provider_valid": bool(
            trajectory.get("provider_valid") is True
            and all(item.get("provider_valid") is True for item in turns)
        ),
        "first_relation_intent": first.get("relation_intent_family")
        in {"transitivity", "change"},
        "first_intent_failed_unchanged": first.get("execution", {}).get(
            "failed_unchanged"
        ) is True,
        "second_action_was_exact_copy": second.get(
            "matches_compiler_action"
        ) is True,
        "second_action_accepted_changed": second.get("execution", {}).get(
            "accepted_changed"
        ) is True,
        "two_goals_after_bridge": bool(
            second.get("execution", {}).get("goal_count_known") is True
            and second.get("execution", {}).get("goal_count") == 2
        ),
        "runner_route_checks_all_true": bool(
            recorded_checks and all(recorded_checks.values())
        ),
    }
    return {
        "repeat": expected_repeat,
        "provider_valid": recomputed["provider_valid"],
        "route_complete": all(recomputed.values()),
        "criteria": recomputed,
        "first_tactic": str(first.get("model_tactic") or ""),
        "first_relation_intent_family": first.get("relation_intent_family"),
        "second_tactic": str(second.get("model_tactic") or ""),
        "turn_usage": [item.get("usage", {}) for item in turns],
        "turn_duration_ms": [int(item.get("duration_ms") or 0) for item in turns],
        "prompt_sha256": [str(item.get("prompt_sha256") or "") for item in turns],
    }


def _aggregate_usage(reports: list[dict[str, Any]]) -> dict[str, int]:
    usages = [
        usage
        for report in reports
        for usage in report.get("turn_usage", [])
        if isinstance(usage, dict)
    ]
    keys = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    )
    return {
        **{
            key: sum(int(item.get(key) or 0) for item in usages)
            for key in keys
        },
        "model_duration_ms": sum(
            duration
            for report in reports
            for duration in report.get("turn_duration_ms", [])
        ),
    }


def render_markdown(evaluation: dict[str, Any]) -> str:
    lines = [
        "# Chained recovery micro evaluation",
        "",
        f"Decision: **{evaluation['decision']}**",
        "",
        (
            f"Complete treatment routes: {evaluation['complete_routes']}/"
            f"{evaluation['required_complete_routes']}."
        ),
        "",
        "| Repeat | First live tactic | Family | Second live tactic | Complete |",
        "|---:|---|---|---|---:|",
    ]
    for item in evaluation["trajectory_reports"]:
        lines.append(
            f"| {item['repeat']} | `{item['first_tactic']}` | "
            f"{item['first_relation_intent_family'] or ''} | "
            f"`{item['second_tactic']}` | "
            f"{'yes' if item['route_complete'] else 'no'} |"
        )
    usage = evaluation["aggregate_usage"]
    lines.extend([
        "",
        "## Aggregate live-model usage",
        "",
        (
            f"Input {usage['input_tokens']:,}; cached input "
            f"{usage['cached_input_tokens']:,}; output {usage['output_tokens']:,}; "
            f"reasoning output {usage['reasoning_output_tokens']:,}; total "
            f"{usage['total_tokens']:,}; model duration "
            f"{usage['model_duration_ms']:,} ms."
        ),
        "",
    ])
    return "\n".join(lines)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def _write(path: Path, text: str) -> None:
    resolved = path if path.is_absolute() else ROOT / path
    try:
        resolved.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("evaluation output must stay inside project") from exc
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-result", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()
    model_path = args.model_result if args.model_result.is_absolute() else ROOT / args.model_result
    preparation_path = args.preparation if args.preparation.is_absolute() else ROOT / args.preparation
    evaluation = evaluate_bundle(_load(model_path), _load(preparation_path))
    evaluation["input_sha256"] = {
        "model": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "preparation": hashlib.sha256(preparation_path.read_bytes()).hexdigest(),
    }
    rendered_json = json.dumps(evaluation, indent=2, sort_keys=True) + "\n"
    rendered_md = render_markdown(evaluation)
    if args.output_json is not None:
        _write(args.output_json, rendered_json)
    if args.output_md is not None:
        _write(args.output_md, rendered_md)
    print(rendered_json, end="")
    return 0 if evaluation["decision"] == "CHAIN_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
