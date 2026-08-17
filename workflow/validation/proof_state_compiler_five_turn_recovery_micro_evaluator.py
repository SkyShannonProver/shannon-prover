"""Independent evaluator for the five-turn L1/treatment recovery micro."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from workflow.validation.proof_state_compiler_five_turn_recovery_micro import (
    CAMPAIGN_SHA256,
    INITIAL_REJECTED_TACTIC,
    MAX_LIVE_TURNS,
    REPEATS,
    TRAJECTORY_ORDER,
)


ROOT = Path(__file__).resolve().parents[2]
USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)
COST_KEYS = (
    "compiler_wall_clock_ms",
    "native_wall_clock_ms",
    "certification_wall_clock_ms",
)


def evaluate_bundle(
    model: dict[str, Any], preparation: dict[str, Any]
) -> dict[str, Any]:
    contract_errors: list[str] = []
    for label, bundle, mode in (
        ("model", model, "model_micro"),
        ("preparation", preparation, "prepare_only"),
    ):
        if bundle.get("kind") != "proof_state_compiler_five_turn_recovery_micro":
            contract_errors.append(f"{label} kind mismatch")
        if bundle.get("campaign_sha256") != CAMPAIGN_SHA256:
            contract_errors.append(f"{label} campaign hash mismatch")
        if bundle.get("mode") != mode:
            contract_errors.append(f"{label} mode mismatch")
        if bundle.get("git", {}).get("dirty") is not False:
            contract_errors.append(f"{label} worktree was not clean")
        if bundle.get("preparation_valid") is not True:
            contract_errors.append(f"{label} preparation did not pass")
    if model.get("git", {}).get("commit") != preparation.get("git", {}).get(
        "commit"
    ):
        contract_errors.append("model/preparation commits differ")
    if preparation.get("trajectories") != []:
        contract_errors.append("preparation unexpectedly called the model")
    routes = preparation.get("preparation_routes")
    if not isinstance(routes, list) or len(routes) != 2:
        contract_errors.append("preparation route cardinality mismatch")
    elif not all(item.get("preparation_valid") is True for item in routes):
        contract_errors.append("a deterministic preparation route failed")

    trajectories = model.get("trajectories")
    if not isinstance(trajectories, list) or len(trajectories) != len(
        TRAJECTORY_ORDER
    ):
        contract_errors.append("model trajectory cardinality mismatch")
        trajectories = []
    reports = [
        _evaluate_trajectory(item, expected_arm=arm, expected_repeat=repeat)
        for item, (arm, repeat) in zip(trajectories, TRAJECTORY_ORDER)
    ]
    arm_summaries = {
        arm: _arm_summary([item for item in reports if item["arm"] == arm])
        for arm in ("l1", "treatment")
    }
    l1 = arm_summaries["l1"]
    treatment = arm_summaries["treatment"]
    contract_valid = not contract_errors
    experiment_valid = bool(
        contract_valid
        and model.get("experiment_valid") is True
        and len(reports) == len(TRAJECTORY_ORDER)
        and all(item["trajectory_valid"] for item in reports)
    )
    pass_criteria = {
        "experiment_valid": experiment_valid,
        "minimum_two_treatment_bridge_successes": (
            treatment["bridge_successes"] >= 2
        ),
        "treatment_recovery_successes_not_less_than_l1": (
            treatment["recovery_successes"] >= l1["recovery_successes"]
        ),
        "treatment_bridge_successes_not_less_than_l1": (
            treatment["bridge_successes"] >= l1["bridge_successes"]
        ),
        "treatment_total_tokens_less_than_l1": (
            treatment["total_tokens"] < l1["total_tokens"]
        ),
    }
    decision = (
        "FIVE_TURN_MICRO_PASS"
        if all(pass_criteria.values())
        else "NO_FIVE_TURN_MICRO_VALUE"
    )
    return {
        "kind": "proof_state_compiler_five_turn_recovery_micro_evaluation",
        "campaign_sha256": CAMPAIGN_SHA256,
        "contract_valid": contract_valid,
        "contract_errors": contract_errors,
        "experiment_valid": experiment_valid,
        "decision": decision,
        "pass_criteria": pass_criteria,
        "trajectory_reports": reports,
        "arm_summaries": arm_summaries,
        "treatment_reduction_percent": {
            key: _reduction_percent(l1[key], treatment[key])
            for key in (
                "input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
                "total_tokens",
                "model_duration_ms",
                "live_turns",
                "executed_attempts",
            )
        },
    }


def _evaluate_trajectory(
    trajectory: dict[str, Any], *, expected_arm: str, expected_repeat: int
) -> dict[str, Any]:
    turns = trajectory.get("turns")
    turns = turns if isinstance(turns, list) else []
    fixed = trajectory.get("fixed_trigger")
    fixed = fixed if isinstance(fixed, dict) else {}
    provider_valid = bool(
        turns and all(item.get("provider_valid") is True for item in turns)
    )
    accepted_indexes = [
        index
        for index, item in enumerate(turns)
        if item.get("execution", {}).get("accepted_changed") is True
    ]
    failed_indexes = [
        index
        for index, item in enumerate(turns)
        if item.get("execution", {}).get("failed_unchanged") is True
    ]
    recovery_success = accepted_indexes == [len(turns) - 1]
    final_execution = turns[-1].get("execution", {}) if turns else {}
    bridge_success = bool(
        recovery_success
        and final_execution.get("goal_count_known") is True
        and final_execution.get("goal_count") == 2
    )
    bounded_stop = bool(
        1 <= len(turns) <= MAX_LIVE_TURNS
        and (
            recovery_success
            or (
                len(turns) == MAX_LIVE_TURNS
                and failed_indexes == list(range(MAX_LIVE_TURNS))
            )
        )
    )
    l1_zero_work = all(
        item.get("compilation", {}).get("compile_invoked") is False
        and item.get("compilation", {}).get("kind") == "none"
        and not item.get("compilation", {}).get("item")
        and "compiler_assist" not in item.get("panel", {})
        for item in turns
    )
    treatment_current_work = all(
        item.get("compilation", {}).get("compile_invoked") is True
        for item in turns
    )
    first_compilation = turns[0].get("compilation", {}) if turns else {}
    arm_boundary = (
        l1_zero_work
        if expected_arm == "l1"
        else bool(
            treatment_current_work
            and first_compilation.get("kind") == "diagnostic"
            and first_compilation.get("item", {}).get("code")
            == "application_applicability_indeterminate"
        )
    )
    criteria = {
        "arm_identity": trajectory.get("arm") == expected_arm,
        "repeat_identity": trajectory.get("repeat") == expected_repeat,
        "fixed_trigger_exact": fixed.get("tactic") == INITIAL_REJECTED_TACTIC,
        "fixed_trigger_failed_unchanged": fixed.get("failed_unchanged") is True,
        "provider_valid": provider_valid,
        "bounded_event_driven_stop": bounded_stop,
        "accepted_only_at_terminal_turn": not accepted_indexes or recovery_success,
        "arm_compiler_boundary": arm_boundary,
        "runner_trajectory_valid": trajectory.get("trajectory_valid") is True,
        "runner_recovery_endpoint_matches": (
            trajectory.get("recovery_success") is recovery_success
        ),
        "runner_bridge_endpoint_matches": (
            trajectory.get("bridge_success") is bridge_success
        ),
    }
    usage = {
        key: sum(int(item.get("usage", {}).get(key) or 0) for item in turns)
        for key in USAGE_KEYS
    }
    usage["model_duration_ms"] = sum(
        int(item.get("duration_ms") or 0) for item in turns
    )
    compiler_cost = {
        "compiler_wall_clock_ms": sum(
            int(item.get("compilation", {}).get("timings_ms", {}).get("total") or 0)
            for item in turns
        ),
        "native_wall_clock_ms": sum(
            int(
                item.get("compilation", {})
                .get("native_semantics", {})
                .get("elapsed_ms")
                or 0
            )
            for item in turns
        ),
        "certification_wall_clock_ms": sum(
            int(
                item.get("compilation", {})
                .get("timings_ms", {})
                .get("certification")
                or 0
            )
            for item in turns
        ),
    }
    return {
        "arm": expected_arm,
        "repeat": expected_repeat,
        "trajectory_valid": all(criteria.values()),
        "criteria": criteria,
        "recovery_success": recovery_success,
        "bridge_success": bridge_success,
        "stop_reason": str(trajectory.get("stop_reason") or ""),
        "live_turns": len(turns),
        "executed_attempts": 1 + len(turns),
        "tactics": [str(item.get("model_tactic") or "") for item in turns],
        "compiler_item_kinds": [
            str(item.get("compilation", {}).get("kind") or "")
            for item in turns
        ],
        "exact_action_accepted": any(
            item.get("matches_compiler_action") is True
            and item.get("execution", {}).get("accepted_changed") is True
            for item in turns
        ),
        "usage": usage,
        "compiler_cost": compiler_cost,
    }


def _arm_summary(reports: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "trajectories": len(reports),
        "valid_trajectories": sum(item["trajectory_valid"] for item in reports),
        "recovery_successes": sum(item["recovery_success"] for item in reports),
        "bridge_successes": sum(item["bridge_success"] for item in reports),
        "exact_actions_accepted": sum(
            item["exact_action_accepted"] for item in reports
        ),
        "live_turns": sum(item["live_turns"] for item in reports),
        "executed_attempts": sum(item["executed_attempts"] for item in reports),
        **{
            key: sum(item["usage"][key] for item in reports)
            for key in (*USAGE_KEYS, "model_duration_ms")
        },
        **{
            key: sum(item["compiler_cost"][key] for item in reports)
            for key in COST_KEYS
        },
    }


def _reduction_percent(control: int, treatment: int) -> float | None:
    if control <= 0:
        return None
    return round((control - treatment) * 100.0 / control, 4)


def render_markdown(evaluation: dict[str, Any]) -> str:
    lines = [
        "# Five-turn recovery micro evaluation",
        "",
        f"Decision: **{evaluation['decision']}**",
        "",
        "| Arm | Recovery | Bridge | Live turns | Output | Reasoning | Total |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ("l1", "treatment"):
        item = evaluation["arm_summaries"][arm]
        lines.append(
            f"| {arm} | {item['recovery_successes']}/{item['trajectories']} | "
            f"{item['bridge_successes']}/{item['trajectories']} | "
            f"{item['live_turns']} | {item['output_tokens']:,} | "
            f"{item['reasoning_output_tokens']:,} | {item['total_tokens']:,} |"
        )
    lines.extend([
        "",
        "| Arm/repeat | Turns | Endpoint | Tactics |",
        "|---|---:|---|---|",
    ])
    for item in evaluation["trajectory_reports"]:
        endpoint = (
            "bridge" if item["bridge_success"]
            else "progress" if item["recovery_success"]
            else "horizon"
        )
        tactics = " → ".join(f"`{tactic}`" for tactic in item["tactics"])
        lines.append(
            f"| {item['arm']}/{item['repeat']} | {item['live_turns']} | "
            f"{endpoint} | {tactics} |"
        )
    lines.append("")
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
    return 0 if evaluation["decision"] == "FIVE_TURN_MICRO_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
