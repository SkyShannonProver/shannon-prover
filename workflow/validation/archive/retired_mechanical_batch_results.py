"""Independent result audit for the frozen mechanical micro batch.

The model runner records raw rows as well as convenience summaries.  This
module deliberately recomputes validity, consumption, EasyCrypt acceptance,
route regression, usage, and the preregistered gates from those raw rows.  It
also compares the model packet contract with the clean no-model preparation
artifact.  Embedded summaries and gates are consistency checks, never result
authority.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PREPARATION = ROOT / (
    "docs/reports/proof_state_compiler_v2/non_strategic_mechanical_batch/"
    "mechanical_micro_preparation_clean_a8379434d.json"
)

EXPECTED_MODEL = "gpt-5.6-sol"
EXPECTED_EFFORT = "high"
EXPECTED_REPEATS = 4
EXPECTED_ARM_ORDERS = {
    1: ("control", "treatment"),
    2: ("treatment", "control"),
    3: ("treatment", "control"),
    4: ("control", "treatment"),
}
EXPECTED_SCENARIOS = (
    "m04_step4_bad2",
    "m15_alossless_b1",
    "m15_alossless_b2",
    "m15_step2_1_b24",
)
SCENARIO_FEATURE = {
    "m04_step4_bad2": "program_operation_readiness",
    "m15_alossless_b1": "same_operation_failure_feedback",
    "m15_alossless_b2": "same_operation_failure_feedback",
    "m15_step2_1_b24": "same_operation_failure_feedback",
}
READINESS_SCENARIO = "m04_step4_bad2"
M15_SCENARIOS = EXPECTED_SCENARIOS[1:]
USAGE_KEYS = (
    "total_tokens",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


class ResultContractError(ValueError):
    """The retained bundle does not implement the frozen experiment."""


def evaluate_model_bundle(
    bundle: Mapping[str, Any],
    preparation: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit one retained model bundle without trusting its summaries."""

    errors: list[str] = []
    _check_top_level(bundle, preparation, errors)
    prepared_rows = _rows_by_scenario(preparation, "preparation", errors)
    model_rows = _rows_by_scenario(bundle, "model", errors)

    scenario_reports: list[dict[str, Any]] = []
    for scenario_id in EXPECTED_SCENARIOS:
        prepared = prepared_rows.get(scenario_id)
        row = model_rows.get(scenario_id)
        if prepared is None or row is None:
            continue
        scenario_reports.append(_evaluate_scenario(
            scenario_id=scenario_id,
            row=row,
            prepared=prepared,
            errors=errors,
        ))

    invalid_runs = [
        item
        for report in scenario_reports
        for item in report["invalid_runs"]
    ]
    expected_invalid_scenarios = [
        report["scenario_id"]
        for report in scenario_reports
        if not report["experiment_valid"]
    ]
    embedded_invalid = bundle.get("invalid_scenarios")
    if embedded_invalid != expected_invalid_scenarios:
        errors.append(
            "top.invalid_scenarios disagrees with raw run validity: "
            f"embedded={embedded_invalid!r}, "
            f"recomputed={expected_invalid_scenarios!r}"
        )
    expected_top_valid = bool(
        len(scenario_reports) == len(EXPECTED_SCENARIOS)
        and not expected_invalid_scenarios
    )
    if bundle.get("experiment_valid") is not expected_top_valid:
        errors.append(
            "top.experiment_valid disagrees with raw run validity: "
            f"embedded={bundle.get('experiment_valid')!r}, "
            f"recomputed={expected_top_valid!r}"
        )

    by_id = {row["scenario_id"]: row for row in scenario_reports}
    m04_eligible = _all_pass(by_id, (READINESS_SCENARIO,))
    m15_eligible = _all_pass(by_id, M15_SCENARIOS)
    contract_valid = not errors
    eligibility = {
        "program_operation_readiness": bool(contract_valid and m04_eligible),
        "accepted_contract_retention": False,
        "same_operation_failure_feedback": bool(contract_valid and m15_eligible),
    }
    decisions = {
        "program_operation_readiness": (
            "managed_eligible" if eligibility["program_operation_readiness"]
            else "hold_before_managed"
        ),
        "accepted_contract_retention": "audit_only_no_positive_anchor",
        "same_operation_failure_feedback": (
            "managed_eligible"
            if eligibility["same_operation_failure_feedback"]
            else "hold_before_managed"
        ),
    }
    totals = _sum_metrics(
        row
        for report in scenario_reports
        for row in report["valid_runs"]
    )
    return {
        "schema_version": 1,
        "kind": "proof_state_compiler_mechanical_batch_micro_evaluation",
        "source_bundle_git": copy.deepcopy(bundle.get("git")),
        "preparation_bundle_git": copy.deepcopy(preparation.get("git")),
        "contract_valid": contract_valid,
        "contract_errors": errors,
        "experiment_valid": bool(contract_valid and expected_top_valid),
        "scenario_reports": scenario_reports,
        "invalid_runs": invalid_runs,
        "totals_valid_runs": totals,
        "managed_eligibility": eligibility,
        "feature_decisions": decisions,
        "interpretation": (
            "Valid unfavorable gates are retained as hold decisions. Invalid "
            "rows are listed and are not proof failures or retry authority."
        ),
    }


def _check_top_level(
    bundle: Mapping[str, Any],
    preparation: Mapping[str, Any],
    errors: list[str],
) -> None:
    expected = {
        "schema_version": 1,
        "kind": "proof_state_compiler_mechanical_batch_micro",
        "mode": "model_micro",
        "model_backend": "openai",
        "model": EXPECTED_MODEL,
        "effort": EXPECTED_EFFORT,
        "model_timeout_seconds": 300,
        "repeats": EXPECTED_REPEATS,
        "tools_enabled": False,
        "source_contract": "proof_stripped_project",
        "scenario_order": list(EXPECTED_SCENARIOS),
        "arm_orders": {
            str(repeat): list(order)
            for repeat, order in EXPECTED_ARM_ORDERS.items()
        },
        "preparation_valid": True,
    }
    for key, value in expected.items():
        if bundle.get(key) != value:
            errors.append(
                f"top.{key} drifted: expected {value!r}, "
                f"got {bundle.get(key)!r}"
            )
    prep_expected = dict(expected)
    prep_expected["mode"] = "prepare_only"
    for key, value in prep_expected.items():
        if key in {"model", "effort", "model_backend"}:
            # These still exist on preparation, but they do not execute.
            pass
        if preparation.get(key) != value:
            errors.append(
                f"preparation.{key} drifted: expected {value!r}, "
                f"got {preparation.get(key)!r}"
            )
    git = bundle.get("git")
    if not isinstance(git, Mapping) or not git.get("commit"):
        errors.append("top.git must carry a full commit")
    elif len(str(git["commit"])) != 40:
        errors.append("top.git.commit is not a full hash")
    if isinstance(git, Mapping) and git.get("dirty") is not False:
        errors.append("model batch did not start from a clean worktree")


def _rows_by_scenario(
    data: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    rows = data.get("results")
    if not isinstance(rows, list):
        errors.append(f"{label}.results is not a list")
        return {}
    found: dict[str, Mapping[str, Any]] = {}
    order: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f"{label}.results[{index}] is not an object")
            continue
        scenario_id = str(row.get("scenario_id") or "")
        order.append(scenario_id)
        if not scenario_id:
            errors.append(f"{label}.results[{index}] has no scenario_id")
        elif scenario_id in found:
            errors.append(f"{label} repeats scenario {scenario_id}")
        else:
            found[scenario_id] = row
    if order != list(EXPECTED_SCENARIOS):
        errors.append(
            f"{label} scenario row order drifted: {order!r}"
        )
    return found


def _evaluate_scenario(
    *,
    scenario_id: str,
    row: Mapping[str, Any],
    prepared: Mapping[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    prefix = f"scenario[{scenario_id}]"
    _check_preparation_identity(prefix, row, prepared, errors)
    runs = row.get("runs")
    if not isinstance(runs, list):
        errors.append(f"{prefix}.runs is not a list")
        runs = []
    expected_positions = [
        (repeat, arm)
        for repeat in range(1, EXPECTED_REPEATS + 1)
        for arm in EXPECTED_ARM_ORDERS[repeat]
    ]
    actual_positions = [
        (item.get("repeat"), item.get("arm"))
        if isinstance(item, Mapping) else (None, None)
        for item in runs
    ]
    if actual_positions != expected_positions:
        errors.append(
            f"{prefix}.run order drifted: expected {expected_positions!r}, "
            f"got {actual_positions!r}"
        )

    telemetry = prepared.get("packet_telemetry")
    telemetry = telemetry if isinstance(telemetry, Mapping) else {}
    compiler_tactic = str(prepared.get("compiler_tactic") or "")
    compiler_remaining = _compiler_remaining(prepared)
    valid_runs: list[dict[str, Any]] = []
    invalid_runs: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for index, item in enumerate(runs):
        if not isinstance(item, Mapping):
            invalid_runs.append({
                "scenario_id": scenario_id,
                "position": index,
                "reasons": ["run row is not an object"],
            })
            continue
        audited = _audit_run(
            scenario_id=scenario_id,
            item=item,
            telemetry=telemetry,
            compiler_tactic=compiler_tactic,
            compiler_remaining=compiler_remaining,
            errors=errors,
        )
        all_rows.append(audited)
        if audited["valid_sample"]:
            valid_runs.append(audited)
        else:
            invalid_runs.append({
                "scenario_id": scenario_id,
                "repeat": audited["repeat"],
                "arm": audited["arm"],
                "reasons": audited["invalid_reasons"],
            })

    experiment_valid = bool(
        row.get("preparation_valid") is True
        and len(all_rows) == EXPECTED_REPEATS * 2
        and len(valid_runs) == EXPECTED_REPEATS * 2
    )
    if row.get("experiment_valid") is not experiment_valid:
        errors.append(
            f"{prefix}.experiment_valid disagrees with raw rows: "
            f"embedded={row.get('experiment_valid')!r}, "
            f"recomputed={experiment_valid!r}"
        )

    summary = _summary(all_rows)
    if row.get("summary") != summary:
        errors.append(f"{prefix}.summary disagrees with raw rows")
    gate = (
        _micro_gate(scenario_id, all_rows, compiler_remaining)
        if experiment_valid else {
            "evaluated": False,
            "passed": False,
            "reason": "invalid experiment",
        }
    )
    if row.get("micro_gate") != gate:
        errors.append(f"{prefix}.micro_gate disagrees with raw rows")
    arm_metrics = {
        arm: _sum_metrics(
            item for item in valid_runs if item["arm"] == arm
        )
        for arm in ("control", "treatment")
    }
    return {
        "scenario_id": scenario_id,
        "ledger_id": row.get("ledger_id"),
        "feature_id": row.get("feature_id"),
        "packet": {
            "production_agent_bytes": row.get("production_agent_bytes"),
            "incremental_prompt_bytes": telemetry.get(
                "incremental_prompt_bytes"
            ),
        },
        "experiment_valid": experiment_valid,
        "invalid_runs": invalid_runs,
        "valid_runs": valid_runs,
        "arm_metrics": arm_metrics,
        "treatment_minus_control": _metric_delta(
            arm_metrics["treatment"], arm_metrics["control"]
        ),
        "gate": gate,
    }


def _check_preparation_identity(
    prefix: str,
    row: Mapping[str, Any],
    prepared: Mapping[str, Any],
    errors: list[str],
) -> None:
    stable_fields = (
        "scenario_id",
        "ledger_id",
        "feature_id",
        "source_file",
        "lemma",
        "replay_prefix",
        "production_profile",
        "production_item",
        "production_agent_bytes",
        "production_max_bytes",
        "compiler_tactic",
    )
    for key in stable_fields:
        if row.get(key) != prepared.get(key):
            errors.append(f"{prefix}.{key} drifted from clean preparation")
    if row.get("feature_id") != SCENARIO_FEATURE.get(str(row.get("scenario_id"))):
        errors.append(f"{prefix}.feature_id does not match frozen scenario")
    for label, value in (("model", row), ("preparation", prepared)):
        if value.get("preparation_valid") is not True:
            errors.append(f"{prefix}.{label}.preparation_valid is false")
        if value.get("history_unchanged") is not True:
            errors.append(f"{prefix}.{label}.history changed")
        if value.get("agent_source_reads") != 0:
            errors.append(f"{prefix}.{label}.agent_source_reads is not zero")
    packet_fields = (
        "control_prompt_bytes",
        "treatment_prompt_bytes",
        "incremental_prompt_bytes",
        "control_prompt_sha256",
        "treatment_prompt_sha256",
        "only_delta_is_one_compiler_item",
    )
    model_packet = row.get("packet_telemetry")
    prep_packet = prepared.get("packet_telemetry")
    if not isinstance(model_packet, Mapping) or not isinstance(prep_packet, Mapping):
        errors.append(f"{prefix}.packet_telemetry is missing")
    else:
        for key in packet_fields:
            if model_packet.get(key) != prep_packet.get(key):
                errors.append(
                    f"{prefix}.packet_telemetry.{key} drifted from preparation"
                )
        if model_packet.get("only_delta_is_one_compiler_item") is not True:
            errors.append(f"{prefix} does not have a one-item prompt delta")
    production_bytes = row.get("production_agent_bytes")
    max_bytes = row.get("production_max_bytes")
    if not (
        type(production_bytes) is int
        and type(max_bytes) is int
        and 0 < production_bytes <= max_bytes
    ):
        errors.append(f"{prefix} violates its production byte budget")
    compiler_input = row.get("compiler_input")
    if not isinstance(compiler_input, Mapping):
        errors.append(f"{prefix}.compiler_input is missing")
    else:
        if compiler_input.get("authority") != "compiler.input.produced":
            errors.append(f"{prefix}.compiler_input authority is invalid")
        for key in (
            "event_id",
            "artifact_sha256",
            "goal_identity",
            "committed_prefix_identity",
        ):
            if not compiler_input.get(key):
                errors.append(f"{prefix}.compiler_input.{key} is empty")


def _audit_run(
    *,
    scenario_id: str,
    item: Mapping[str, Any],
    telemetry: Mapping[str, Any],
    compiler_tactic: str,
    compiler_remaining: int | None,
    errors: list[str],
) -> dict[str, Any]:
    repeat = item.get("repeat")
    arm = str(item.get("arm") or "")
    prefix = f"scenario[{scenario_id}].run[{repeat}:{arm}]"
    reasons: list[str] = []
    tactic = str(item.get("tactic") or "").strip()
    expected_presented = arm == "treatment"
    expected_prompt_hash = telemetry.get(f"{arm}_prompt_sha256")
    expected_prompt_bytes = telemetry.get(f"{arm}_prompt_bytes")
    if item.get("presented") is not expected_presented:
        errors.append(f"{prefix}.presented disagrees with arm")
    if item.get("prompt_sha256") != expected_prompt_hash:
        errors.append(f"{prefix}.prompt_sha256 drifted")
    if item.get("prompt_bytes") != expected_prompt_bytes:
        errors.append(f"{prefix}.prompt_bytes drifted")
    if item.get("tools_observed") != []:
        reasons.append("tools were observed")
    if item.get("model_returncode") != 0:
        reasons.append(f"model_returncode={item.get('model_returncode')!r}")
    if item.get("model_error"):
        reasons.append(f"model_error={item.get('model_error')}")
    if not tactic:
        reasons.append("model returned no tactic")
    preflight_authoritative, recomputed_ref = _audit_preflight_authority(item)
    if item.get("preflight_authoritative") is not preflight_authoritative:
        errors.append(f"{prefix}.preflight_authoritative disagrees with authority")
    if not preflight_authoritative:
        reasons.append("EasyCrypt preflight lacks current-call authority")
    verification_ref = str(item.get("preflight_verification_ref") or "")
    if verification_ref != recomputed_ref:
        errors.append(f"{prefix}.preflight_verification_ref disagrees with authority")

    usage = item.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    try:
        normalized = _normalized_usage(usage)
    except (TypeError, ValueError):
        normalized = {key: 0 for key in USAGE_KEYS}
        reasons.append("usage is not a non-negative integer record")
    if item.get("normalized_usage") != normalized:
        errors.append(f"{prefix}.normalized_usage disagrees with raw usage")

    post_state = item.get("easycrypt_post_state")
    post_state = post_state if isinstance(post_state, Mapping) else {}
    if type(post_state.get("accepted")) is not bool:
        reasons.append("EasyCrypt outcome has no boolean accepted field")
    if (
        post_state.get("accepted") is True
        and post_state.get("outcome_known") is not True
    ):
        reasons.append("accepted EasyCrypt outcome has no known effect")
    if post_state.get("contract_error"):
        reasons.append("EasyCrypt outcome carries a contract error")
    accepted = post_state.get("accepted") is True
    if item.get("easycrypt_preflight_accepted") is not accepted:
        errors.append(f"{prefix}.accepted disagrees with EasyCrypt outcome")
    submitted_blocked = bool(
        scenario_id == READINESS_SCENARIO
        and _tactic_submits_operation(tactic, "call")
    )
    matches_compiler = bool(compiler_tactic and tactic == compiler_tactic)
    consumed = (
        not submitted_blocked
        if arm == "treatment" and scenario_id == READINESS_SCENARIO
        else (
            matches_compiler
            if arm == "treatment" and scenario_id in M15_SCENARIOS
            else None
        )
    )
    if item.get("submitted_blocked_operation") is not submitted_blocked:
        errors.append(f"{prefix}.submitted_blocked_operation disagrees")
    if item.get("matches_compiler_action") is not matches_compiler:
        errors.append(f"{prefix}.matches_compiler_action disagrees")
    if item.get("consumed") is not consumed:
        errors.append(f"{prefix}.consumed disagrees with frozen definition")
    if item.get("compiler_remaining_goals") != compiler_remaining:
        errors.append(f"{prefix}.compiler_remaining_goals drifted")

    duration = item.get("duration_ms")
    if type(duration) is not int or duration < 0:
        reasons.append("duration_ms is not a non-negative integer")
    valid_sample = not reasons
    if item.get("valid_sample") is not valid_sample:
        errors.append(
            f"{prefix}.valid_sample disagrees: embedded="
            f"{item.get('valid_sample')!r}, recomputed={valid_sample!r}"
        )
    return {
        "repeat": repeat,
        "arm": arm,
        "presented": expected_presented,
        "consumed": consumed,
        "tactic": tactic,
        "submitted_blocked_operation": submitted_blocked,
        "matches_compiler_action": matches_compiler,
        "easycrypt_preflight_accepted": accepted,
        "easycrypt_post_state": copy.deepcopy(dict(post_state)),
        "compiler_remaining_goals": compiler_remaining,
        "duration_ms": duration if type(duration) is int and duration >= 0 else 0,
        "normalized_usage": normalized,
        "valid_sample": valid_sample,
        "invalid_reasons": reasons,
    }


def _audit_preflight_authority(item: Mapping[str, Any]) -> tuple[bool, str]:
    authority = item.get("preflight_authority")
    authority = authority if isinstance(authority, Mapping) else {}
    before = item.get("preflight_state_version_before")
    after = item.get("preflight_state_version_after")
    valid = bool(
        authority.get("event_type") == "tool.view.produced"
        and authority.get("event_id")
        and authority.get("artifact_hash")
        and authority.get("hash_algorithm") in {"sha1", "sha256"}
        and not item.get("preflight_contract_error")
        and item.get("preflight_history_unchanged") is True
        and type(before) is int
        and before == after
    )
    reference = ""
    if authority:
        reference = (
            f"tool.view.produced:{authority.get('event_id')}@"
            f"{authority.get('hash_algorithm')}:"
            f"{authority.get('artifact_hash')}"
        )
    return valid, reference


def _normalized_usage(usage: Mapping[str, Any]) -> dict[str, int]:
    values = {
        "input_tokens": _nonnegative_int(usage.get("input_tokens")),
        "cached_input_tokens": _nonnegative_int(
            usage.get("cached_input_tokens")
        ),
        "output_tokens": _nonnegative_int(usage.get("output_tokens")),
        "reasoning_output_tokens": _nonnegative_int(
            usage.get("reasoning_output_tokens")
        ),
    }
    raw_total = usage.get("total_tokens")
    values["total_tokens"] = (
        _nonnegative_int(raw_total)
        if raw_total is not None
        else values["input_tokens"] + values["output_tokens"]
    )
    return values


def _nonnegative_int(value: Any) -> int:
    integer = int(value or 0)
    if integer < 0:
        raise ValueError("negative metric")
    return integer


def _summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for arm in ("control", "treatment"):
        rows = [row for row in runs if row["arm"] == arm]
        valid = [row for row in rows if row["valid_sample"]]
        summary[arm] = {
            "runs": len(rows),
            "valid_runs": len(valid),
            "presented": sum(bool(row["presented"]) for row in valid),
            "consumed": sum(row["consumed"] is True for row in valid),
            "accepted": sum(
                bool(row["easycrypt_preflight_accepted"]) for row in valid
            ),
            "rejected": sum(
                not row["easycrypt_preflight_accepted"] for row in valid
            ),
            "submitted_blocked_operation": sum(
                bool(row["submitted_blocked_operation"]) for row in valid
            ),
            "matched_compiler_action": sum(
                bool(row["matches_compiler_action"]) for row in valid
            ),
            "duration_ms": sum(int(row["duration_ms"]) for row in valid),
            **{
                key: sum(row["normalized_usage"][key] for row in valid)
                for key in USAGE_KEYS
            },
        }
    return summary


def _micro_gate(
    scenario_id: str,
    runs: list[dict[str, Any]],
    compiler_remaining: int | None,
) -> dict[str, Any]:
    treatment = [
        row for row in runs
        if row["arm"] == "treatment" and row["valid_sample"]
    ]
    control_by_repeat = {
        row["repeat"]: row
        for row in runs
        if row["arm"] == "control" and row["valid_sample"]
    }
    pair_regressions: list[int] = []
    if scenario_id == READINESS_SCENARIO:
        for row in treatment:
            control = control_by_repeat.get(row["repeat"])
            treatment_remaining = row["easycrypt_post_state"].get(
                "goal_after_remaining"
            )
            control_remaining = (
                control["easycrypt_post_state"].get("goal_after_remaining")
                if control else None
            )
            if (
                row["easycrypt_preflight_accepted"]
                and control
                and control["easycrypt_preflight_accepted"]
                and type(treatment_remaining) is int
                and type(control_remaining) is int
                and treatment_remaining > control_remaining
            ):
                pair_regressions.append(int(row["repeat"]))
    else:
        for row in treatment:
            actual = row["easycrypt_post_state"].get("goal_after_remaining")
            if (
                row["consumed"] is True
                and type(compiler_remaining) is int
                and actual != compiler_remaining
            ):
                pair_regressions.append(int(row["repeat"]))
    consumed = [row for row in treatment if row["consumed"] is True]
    criteria = {
        "four_valid_treatment_repeats": len(treatment) == EXPECTED_REPEATS,
        "all_treatment_repeats_presented": (
            len(treatment) == EXPECTED_REPEATS
            and all(row["presented"] for row in treatment)
        ),
        "at_least_three_consumed": len(consumed) >= 3,
        "every_consumed_tactic_accepted": all(
            row["easycrypt_preflight_accepted"] for row in consumed
        ),
        "no_route_regression_detected": not pair_regressions,
        "no_negative_fixture_exposure": True,
    }
    return {
        "evaluated": True,
        "passed": all(criteria.values()),
        "criteria": criteria,
        "consumed_count": len(consumed),
        "route_regression_repeats": pair_regressions,
        "negative_control_basis": (
            "deterministic B3/B5/B7, ambiguous-resource, irrelevant-state, "
            "and pure-goal abstention fixtures"
        ),
    }


def _compiler_remaining(prepared: Mapping[str, Any]) -> int | None:
    records = prepared.get("compiler_certifications")
    if not isinstance(records, list) or not records:
        return None
    effect = records[0].get("checked_effect")
    if not isinstance(effect, Mapping):
        return None
    value = effect.get("goal_after_remaining")
    return value if type(value) is int else None


def _tactic_submits_operation(tactic: str, operation: str) -> bool:
    return bool(re.search(
        rf"(?:^|[.;])\s*{re.escape(operation)}\b",
        tactic,
        re.IGNORECASE,
    ))


def _sum_metrics(rows) -> dict[str, int]:
    selected = list(rows)
    result = {
        "runs": len(selected),
        "presented": sum(bool(row["presented"]) for row in selected),
        "consumed": sum(row["consumed"] is True for row in selected),
        "accepted": sum(
            bool(row["easycrypt_preflight_accepted"]) for row in selected
        ),
        "rejected": sum(
            not row["easycrypt_preflight_accepted"] for row in selected
        ),
        "duration_ms": sum(int(row["duration_ms"]) for row in selected),
    }
    for key in USAGE_KEYS:
        result[key] = sum(row["normalized_usage"][key] for row in selected)
    return result


def _metric_delta(
    treatment: Mapping[str, int],
    control: Mapping[str, int],
) -> dict[str, int]:
    return {
        key: int(treatment[key]) - int(control[key])
        for key in treatment
        if key in control
    }


def _all_pass(
    reports: Mapping[str, Mapping[str, Any]],
    scenario_ids: tuple[str, ...],
) -> bool:
    return all(
        scenario_id in reports
        and reports[scenario_id]["experiment_valid"]
        and reports[scenario_id]["gate"]["passed"]
        for scenario_id in scenario_ids
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Mechanical Micro Independent Evaluation",
        "",
        f"Contract valid: **{report['contract_valid']}**  ",
        f"Experiment valid: **{report['experiment_valid']}**",
        "",
        "| scenario | valid | presented | consumed | accepted | rejected | "
        "gate | prompt bytes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["scenario_reports"]:
        totals = _sum_metrics(row["valid_runs"])
        lines.append(
            f"| {row['scenario_id']} | {row['experiment_valid']} | "
            f"{totals['presented']} | {totals['consumed']} | "
            f"{totals['accepted']} | {totals['rejected']} | "
            f"{row['gate']['passed']} | "
            f"{row['packet']['incremental_prompt_bytes']} |"
        )
    lines.extend(["", "## Managed eligibility", ""])
    for feature_id, eligible in report["managed_eligibility"].items():
        lines.append(
            f"- `{feature_id}`: {report['feature_decisions'][feature_id]} "
            f"(eligible={eligible})"
        )
    lines.extend(["", "## Invalid runs", ""])
    if report["invalid_runs"]:
        for item in report["invalid_runs"]:
            lines.append(
                f"- `{item.get('scenario_id')}` R{item.get('repeat')} "
                f"{item.get('arm')}: {', '.join(item.get('reasons') or [])}"
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Contract errors", ""])
    if report["contract_errors"]:
        lines.extend(f"- {item}" for item in report["contract_errors"])
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ResultContractError(f"JSON root must be an object: {path}")
    return data


def _write_project_file(path: Path, content: str) -> None:
    resolved = path if path.is_absolute() else ROOT / path
    try:
        resolved.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ResultContractError("result output must stay inside project") from exc
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--preparation", type=Path, default=DEFAULT_PREPARATION)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)
    report = evaluate_model_bundle(
        _read_json(args.bundle),
        _read_json(args.preparation),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        _write_project_file(args.json_output, rendered)
    if args.markdown_output:
        _write_project_file(args.markdown_output, render_markdown(report))
    print(rendered, end="")
    return 0 if report["contract_valid"] and report["experiment_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
