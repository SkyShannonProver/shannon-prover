"""Independent evaluator for the preregistered PHL boundary micro."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from workflow.validation.proof_state_compiler_phl_boundary_five_turn_micro import (
    CAMPAIGN_SHA256,
    FIXED_REJECTED_TACTIC,
    MAX_LIVE_TURNS,
    TRAJECTORY_ORDER,
)


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
    errors: list[str] = []
    for label, bundle, mode in (
        ("model", model, "model_micro"),
        ("preparation", preparation, "prepare_only"),
    ):
        if bundle.get("kind") != "proof_state_compiler_phl_boundary_five_turn_micro":
            errors.append(f"{label} kind mismatch")
        if bundle.get("campaign_sha256") != CAMPAIGN_SHA256:
            errors.append(f"{label} campaign hash mismatch")
        if bundle.get("mode") != mode:
            errors.append(f"{label} mode mismatch")
        if bundle.get("git", {}).get("tracked_dirty") is not False:
            errors.append(f"{label} had tracked worktree changes")
        if bundle.get("preparation_valid") is not True:
            errors.append(f"{label} deterministic preparation failed")
    if model.get("git", {}).get("commit") != preparation.get("git", {}).get("commit"):
        errors.append("model/preparation commits differ")
    if preparation.get("trajectories") != []:
        errors.append("preparation unexpectedly contains model trajectories")

    trajectories = model.get("trajectories")
    if not isinstance(trajectories, list) or len(trajectories) != len(
        TRAJECTORY_ORDER
    ):
        errors.append("model trajectory cardinality mismatch")
        trajectories = []
    reports = [
        _evaluate_trajectory(item, expected_arm=arm, expected_repeat=repeat)
        for item, (arm, repeat) in zip(trajectories, TRAJECTORY_ORDER)
    ]
    summaries = {
        arm: _arm_summary([item for item in reports if item["arm"] == arm])
        for arm in ("l1", "treatment")
    }
    l1 = summaries["l1"]
    treatment = summaries["treatment"]
    contract_valid = not errors
    experiment_valid = bool(
        contract_valid
        and model.get("experiment_valid") is True
        and len(reports) == len(TRAJECTORY_ORDER)
        and all(item["trajectory_valid"] for item in reports)
    )
    criteria = {
        "experiment_valid": experiment_valid,
        "minimum_two_treatment_phl_successes": treatment["phl_successes"] >= 2,
        "treatment_phl_successes_not_less_than_l1": (
            treatment["phl_successes"] >= l1["phl_successes"]
        ),
        "treatment_repeated_boundary_mismatches_not_more_than_l1": (
            treatment["repeated_boundary_mismatches"]
            <= l1["repeated_boundary_mismatches"]
        ),
        "treatment_total_tokens_less_than_l1": (
            treatment["total_tokens"] < l1["total_tokens"]
        ),
    }
    return {
        "kind": "proof_state_compiler_phl_boundary_five_turn_micro_evaluation",
        "campaign_sha256": CAMPAIGN_SHA256,
        "contract_valid": contract_valid,
        "contract_errors": errors,
        "experiment_valid": experiment_valid,
        "decision": (
            "PHL_BOUNDARY_FIVE_TURN_MICRO_PASS"
            if all(criteria.values())
            else "NO_PHL_BOUNDARY_FIVE_TURN_MICRO_VALUE"
        ),
        "pass_criteria": criteria,
        "trajectory_reports": reports,
        "arm_summaries": summaries,
        "treatment_reduction_percent": {
            key: _reduction_percent(l1[key], treatment[key])
            for key in (
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
                "total_tokens",
                "model_wall_clock_ms",
                "live_turns",
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
    phl_indexes = [
        index
        for index, item in enumerate(turns)
        if item.get("execution", {}).get("accepted_phl_transitivity") is True
    ]
    phl_success = phl_indexes == [len(turns) - 1]
    bounded_stop = bool(
        1 <= len(turns) <= MAX_LIVE_TURNS
        and (
            phl_success
            or len(turns) == MAX_LIVE_TURNS
            or trajectory.get("stop_reason") == "closed_without_phl_endpoint"
        )
    )
    l1_zero_work = all(
        item.get("compilation", {}).get("compile_invoked") is False
        and not item.get("compilation", {}).get("item")
        and "compiler_assist" not in item.get("panel", {})
        for item in turns
    )
    first = turns[0] if turns else {}
    treatment_boundary = bool(
        first.get("compilation", {}).get("compile_invoked") is True
        and first.get("compilation", {}).get("kind") == "diagnostic"
        and first.get("compilation", {}).get("item", {}).get("code")
        == "phl_boundary"
        and first.get("panel", {}).get("compiler_assist")
        == [first.get("compilation", {}).get("item")]
    )
    panels_current = all(
        item.get("panel", {}).get("current_goal", {}).get("lines")
        for item in turns
    )
    undo_is_not_terminal = all(
        not (
            item.get("model_intent") == "undo_last_step"
            and item.get("execution", {}).get("accepted_changed") is True
            and index == len(turns) - 1
            and trajectory.get("stop_reason") == "accepted_phl_transitivity"
        )
        for index, item in enumerate(turns)
    )
    criteria = {
        "arm_identity": trajectory.get("arm") == expected_arm,
        "repeat_identity": trajectory.get("repeat") == expected_repeat,
        "fixed_trigger_exact": fixed.get("tactic") == FIXED_REJECTED_TACTIC,
        "fixed_trigger_failed_unchanged": fixed.get("failed_unchanged") is True,
        "provider_valid": provider_valid,
        "bounded_event_driven_stop": bounded_stop,
        "phl_endpoint_only_terminal": not phl_indexes or phl_success,
        "accepted_undo_not_misclassified_as_endpoint": undo_is_not_terminal,
        "panels_have_current_goal": panels_current,
        "arm_compiler_boundary": (
            l1_zero_work if expected_arm == "l1" else treatment_boundary
        ),
        "runner_trajectory_valid": trajectory.get("trajectory_valid") is True,
        "runner_phl_endpoint_matches": trajectory.get("phl_success") is phl_success,
    }
    usage = {
        key: sum(int(item.get("usage", {}).get(key) or 0) for item in turns)
        for key in USAGE_KEYS
    }
    usage["model_wall_clock_ms"] = sum(
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
        "phl_success": phl_success,
        "function_boundary_reached": bool(
            trajectory.get("function_boundary_reached")
        ),
        "repeated_boundary_mismatches": int(
            trajectory.get("repeated_boundary_mismatches") or 0
        ),
        "stop_reason": str(trajectory.get("stop_reason") or ""),
        "live_turns": len(turns),
        "actions": [
            {
                "intent": str(item.get("model_intent") or ""),
                "tactic": str(item.get("model_tactic") or ""),
            }
            for item in turns
        ],
        "usage": usage,
        "compiler_cost": compiler_cost,
    }


def _arm_summary(reports: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "trajectories": len(reports),
        "valid_trajectories": sum(item["trajectory_valid"] for item in reports),
        "phl_successes": sum(item["phl_success"] for item in reports),
        "function_boundary_reached": sum(
            item["function_boundary_reached"] for item in reports
        ),
        "repeated_boundary_mismatches": sum(
            item["repeated_boundary_mismatches"] for item in reports
        ),
        "live_turns": sum(item["live_turns"] for item in reports),
    }
    for key in (*USAGE_KEYS, "model_wall_clock_ms"):
        summary[key] = sum(item["usage"][key] for item in reports)
    for key in COST_KEYS:
        summary[key] = sum(item["compiler_cost"][key] for item in reports)
    return summary


def _reduction_percent(control: int, treatment: int) -> float | None:
    if control == 0:
        return None
    return round((control - treatment) * 100.0 / control, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("preparation", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evaluation = evaluate_bundle(
        json.loads(args.model.read_text(encoding="utf-8")),
        json.loads(args.preparation.read_text(encoding="utf-8")),
    )
    rendered = json.dumps(evaluation, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if evaluation["experiment_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
