"""Five-turn L1/treatment recovery micro at the historical premature apply.

This is a bounded local recovery comparison, not a full proof or a natural
trigger-incidence experiment.  Every trajectory executes the authentic first
failed ``apply`` and then gives the live model at most five manager-executed
turns.  The first accepted proof-state change stops the trajectory early.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from workflow.validation.proof_state_compiler_chained_recovery_micro import (
    EFFORT,
    INITIAL_REJECTED_TACTIC,
    LEMMA,
    MAX_ASSIST_BYTES,
    MODEL,
    MODEL_BACKEND,
    MODEL_TIMEOUT_SECONDS,
    PREPARED_SECOND_INTENTS,
    SOURCE_FILE,
    ExecutedIntent,
    _cleanup_manager,
    _compile_occurrence,
    _execute_intent,
    _manager,
    _normalized_usage,
    _panel,
    _provider_valid,
    _run_prepared_route,
    _sha256,
    _timeout_result,
    _treatment_service,
)
from workflow.validation.proof_state_compiler_one_step_model import (
    agent_prompt,
    git_identity,
    run_model,
)
from workflow.validation.proof_state_compiler_one_step_trial import (
    OneStepTrialSpec,
    TrialPacket,
)


ROOT = Path(__file__).resolve().parents[2]
ARMS = ("l1", "treatment")
REPEATS = 3
MAX_LIVE_TURNS = 5
# Alternate the leading arm across repeat blocks to bound simple time-order
# drift while retaining a fully preregistered call order.
TRAJECTORY_ORDER = (
    ("l1", 1),
    ("treatment", 1),
    ("treatment", 2),
    ("l1", 2),
    ("l1", 3),
    ("treatment", 3),
)

CAMPAIGN_SPEC = {
    "schema_version": 1,
    "campaign_id": "premature_apply_five_turn_recovery_comparison",
    "scope": "bounded_local_l1_treatment_micro",
    "source_file": SOURCE_FILE,
    "lemma": LEMMA,
    "arms": list(ARMS),
    "repeats_per_arm": REPEATS,
    "trajectory_order": [list(item) for item in TRAJECTORY_ORDER],
    "fixed_initial_trigger": INITIAL_REJECTED_TACTIC,
    "fixed_trigger_counts_as_attempt": 1,
    "live_turn_horizon_after_fixed_trigger": MAX_LIVE_TURNS,
    "maximum_executed_attempts": MAX_LIVE_TURNS + 1,
    "early_stop": "first manager-accepted proof-state change",
    "primary_endpoint": "accepted proof-state change from empty prefix",
    "bridge_endpoint": "accepted change with exactly two remaining goals",
    "model_backend": MODEL_BACKEND,
    "model": MODEL,
    "effort": EFFORT,
    "tools_enabled": False,
    "sample_replacement": False,
    "reported_economics": [
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
        "model_wall_clock_ms",
        "compiler_wall_clock_ms",
        "native_wall_clock_ms",
        "certification_wall_clock_ms",
    ],
    "pass_rule": {
        "minimum_treatment_bridge_successes": 2,
        "treatment_recovery_successes_not_less_than_l1": True,
        "treatment_bridge_successes_not_less_than_l1": True,
        "treatment_total_tokens_less_than_l1": True,
    },
}
CAMPAIGN_SHA256 = hashlib.sha256(json.dumps(
    CAMPAIGN_SPEC,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")).hexdigest()

TRIAL_SPEC = OneStepTrialSpec(
    trial_id="premature-apply-five-turn-recovery-v1",
    feature_id="operation_binding_repair+relation_bridge_realization",
    evidence_ledger_ids=(
        "M15-B24-PHASE-REDIRECT",
        "M16-RELATION-BRIDGE-REALIZATION",
    ),
    max_assist_bytes=MAX_ASSIST_BYTES,
)


def run_batch(*, prepare_only: bool, root: Path = ROOT) -> dict[str, Any]:
    git = git_identity(root)
    if git.get("dirty") is not False:
        raise RuntimeError("five-turn recovery micro requires a clean worktree")
    token = uuid.uuid4().hex[:12]
    source_output = root / f".five_turn_recovery_sources_{token}"
    original_source = root / SOURCE_FILE
    prepared = prepare_eval_source(
        source_file=original_source,
        target_lemma=LEMMA,
        output_dir=source_output,
        copy_root=original_source.parent,
        strip_proofs=True,
    )
    try:
        preparation_routes = [
            _run_prepared_route(
                prepared_file=prepared.isolated_file,
                route_name=route_name,
                second_intent=second_intent,
                root=root,
            )
            for route_name, second_intent in PREPARED_SECOND_INTENTS
        ]
        preparation_valid = all(
            item.get("preparation_valid") is True
            for item in preparation_routes
        )
        trajectories = [] if prepare_only else [
            _run_live_trajectory(
                prepared_file=prepared.isolated_file,
                arm=arm,
                repeat=repeat,
                root=root,
            )
            for arm, repeat in TRAJECTORY_ORDER
        ]
        experiment_valid = bool(
            preparation_valid
            and not prepare_only
            and len(trajectories) == len(TRAJECTORY_ORDER)
            and all(item.get("trajectory_valid") is True for item in trajectories)
        )
        return {
            "schema_version": 1,
            "kind": "proof_state_compiler_five_turn_recovery_micro",
            "campaign_spec": CAMPAIGN_SPEC,
            "campaign_sha256": CAMPAIGN_SHA256,
            "mode": "prepare_only" if prepare_only else "model_micro",
            "git": git,
            "model_authorization": "explicit_user_request_2026-08-09",
            "source_contract": "proof_stripped_project",
            "preparation_routes": preparation_routes,
            "preparation_valid": preparation_valid,
            "trajectories": trajectories,
            "experiment_valid": experiment_valid,
            "summary_by_arm": _summarize_by_arm(trajectories),
        }
    finally:
        if source_output.name.startswith(".five_turn_recovery_sources_"):
            shutil.rmtree(source_output, ignore_errors=True)


def _run_live_trajectory(
    *, prepared_file: Path, arm: str, repeat: int, root: Path
) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError(f"unsupported five-turn arm: {arm}")
    manager, session_path = _manager(
        prepared_file=prepared_file,
        tag=(
            f"chained_recovery_five_{arm}_r{repeat}_"
            f"{uuid.uuid4().hex[:12]}"
        ),
        root=root,
    )
    try:
        manager.start(replay_prefix=[])
        # L1 owns no compiler service and therefore performs zero hidden work.
        service = _treatment_service(manager) if arm == "treatment" else None
        fixed = _execute_intent(manager, INITIAL_REJECTED_TACTIC)
        turns: list[dict[str, Any]] = []
        current = fixed
        stop_reason = ""
        for turn_index in range(1, MAX_LIVE_TURNS + 1):
            if not current.failed_unchanged:
                stop_reason = "unsupported_manager_outcome"
                break
            compilation = _compilation_for_arm(
                arm=arm,
                service=service,
                executed=current,
            )
            packet = _packet_for_arm(
                arm=arm,
                executed=current,
                compiler_item=compilation["item"],
            )
            prompt = agent_prompt(packet)
            try:
                model_result = run_model(
                    prompt,
                    backend=MODEL_BACKEND,
                    model=MODEL,
                    effort=EFFORT,
                    cwd=root,
                )
            except subprocess.TimeoutExpired:
                model_result = _timeout_result(prompt)
            tactic = str(model_result.get("tactic") or "").strip()
            provider_valid = _provider_valid(model_result, tactic)
            executed = _execute_intent(manager, tactic) if provider_valid else None
            expected = (
                str(compilation["item"].get("payload", {}).get("tactic") or "")
                if compilation["kind"] == "action"
                else ""
            )
            turn = {
                "turn_index": turn_index,
                "panel": _panel(packet),
                "prompt_sha256": model_result["prompt_sha256"],
                "prompt_bytes": model_result["prompt_bytes"],
                "compilation": compilation,
                "model_tactic": tactic,
                "matches_compiler_action": bool(expected and tactic == expected),
                "model_returncode": model_result["returncode"],
                "model_error": model_result["error"],
                "duration_ms": model_result["duration_ms"],
                "usage": _normalized_usage(model_result.get("usage", {})),
                "tools_observed": model_result.get("tools_observed", []),
                "provider_event_audit": model_result.get(
                    "provider_event_audit", {}
                ),
                "provider_valid": provider_valid,
                "execution": executed.record() if executed is not None else {},
            }
            turns.append(turn)
            if not provider_valid:
                stop_reason = "provider_invalid"
                break
            if executed is None:
                stop_reason = "missing_execution"
                break
            if executed.accepted_changed:
                stop_reason = "accepted_progress"
                current = executed
                break
            if not executed.failed_unchanged:
                stop_reason = "unsupported_manager_outcome"
                current = executed
                break
            current = executed
        if not stop_reason:
            stop_reason = "horizon_exhausted"
        provider_valid = bool(
            turns and all(item.get("provider_valid") is True for item in turns)
        )
        recovery_success = bool(
            turns and turns[-1].get("execution", {}).get("accepted_changed") is True
        )
        final_execution = turns[-1].get("execution", {}) if turns else {}
        bridge_success = bool(
            recovery_success
            and final_execution.get("goal_count_known") is True
            and final_execution.get("goal_count") == 2
        )
        valid_stop = bool(
            (recovery_success and stop_reason == "accepted_progress")
            or (
                not recovery_success
                and stop_reason == "horizon_exhausted"
                and len(turns) == MAX_LIVE_TURNS
                and all(
                    item.get("execution", {}).get("failed_unchanged") is True
                    for item in turns
                )
            )
        )
        return {
            "arm": arm,
            "repeat": repeat,
            "fixed_trigger": fixed.record(),
            "turns": turns,
            "provider_valid": provider_valid,
            "trajectory_valid": bool(
                fixed.failed_unchanged and provider_valid and valid_stop
            ),
            "stop_reason": stop_reason,
            "recovery_success": recovery_success,
            "bridge_success": bridge_success,
            "horizon_exhausted": stop_reason == "horizon_exhausted",
            "phase_redirect_presented": _phase_redirect_presented(turns),
            "relation_action_presented": _relation_action_presented(turns),
            "exact_action_accepted": _exact_action_accepted(turns),
            "live_turn_count": len(turns),
            "executed_attempt_count": 1 + len(turns),
            "final_history": list(manager.committed_history()),
            "usage": _aggregate_turn_usage(turns),
            "compiler_cost": _aggregate_compiler_cost(turns),
        }
    finally:
        _cleanup_manager(manager, session_path)


def _compilation_for_arm(
    *,
    arm: str,
    service: object | None,
    executed: ExecutedIntent,
) -> dict[str, Any]:
    if arm == "l1":
        return {
            "compile_invoked": False,
            "kind": "none",
            "item": {},
            "eligible_feature_ids": [],
            "admitted_bytes": 0,
            "timings_ms": {"total": 0, "certification": 0},
            "native_semantics": {
                "planned_request_count": 0,
                "batch_count": 0,
                "elapsed_ms": 0,
            },
            "certifications": [],
        }
    if service is None:
        raise RuntimeError("treatment arm requires one compiler service")
    result = _compile_occurrence(service, executed, expected_kind=None)
    return {"compile_invoked": True, **result}


def _packet_for_arm(
    *, arm: str, executed: ExecutedIntent, compiler_item: dict[str, Any]
) -> TrialPacket:
    authority = executed.action.get("execution_authority")
    authority = authority if isinstance(authority, dict) else {}
    observation = (
        ("tactic", executed.tactic),
        ("outcome_kind", str(executed.action.get("outcome_kind") or "")),
        (
            "proof_state_effect",
            str(executed.action.get("proof_state_effect") or ""),
        ),
        ("error_summary", str(authority.get("structured_error") or "")[:1200]),
    )
    return TrialPacket(
        spec=TRIAL_SPEC,
        arm=arm,
        state_ref=executed.compiler_input_after.snapshot.state_ref,
        current_goal_lines=executed.compiler_input_after.snapshot.goal_lines,
        manager_observation=observation,
        compiler_assist=(compiler_item,) if compiler_item else (),
    )


def _phase_redirect_presented(turns: list[dict[str, Any]]) -> bool:
    if not turns:
        return False
    item = turns[0].get("compilation", {}).get("item", {})
    return bool(
        turns[0].get("compilation", {}).get("kind") == "diagnostic"
        and item.get("code") == "application_applicability_indeterminate"
    )


def _relation_action_presented(turns: list[dict[str, Any]]) -> bool:
    return any(
        turn.get("compilation", {}).get("kind") == "action"
        and turn.get("compilation", {}).get("item", {}).get(
            "correction", {}
        ).get("kind") == "do_you_mean"
        for turn in turns
    )


def _exact_action_accepted(turns: list[dict[str, Any]]) -> bool:
    return any(
        turn.get("matches_compiler_action") is True
        and turn.get("execution", {}).get("accepted_changed") is True
        for turn in turns
    )


def _aggregate_turn_usage(turns: list[dict[str, Any]]) -> dict[str, int]:
    keys = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    )
    return {
        **{
            key: sum(int(item.get("usage", {}).get(key) or 0) for item in turns)
            for key in keys
        },
        "model_duration_ms": sum(
            int(item.get("duration_ms") or 0) for item in turns
        ),
    }


def _aggregate_compiler_cost(turns: list[dict[str, Any]]) -> dict[str, int]:
    return {
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


def _summarize_by_arm(
    trajectories: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    summaries: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        rows = [item for item in trajectories if item.get("arm") == arm]
        usage_keys = (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "total_tokens",
            "model_duration_ms",
        )
        cost_keys = (
            "compiler_wall_clock_ms",
            "native_wall_clock_ms",
            "certification_wall_clock_ms",
        )
        summaries[arm] = {
            "trajectories": len(rows),
            "valid_trajectories": sum(
                item.get("trajectory_valid") is True for item in rows
            ),
            "recovery_successes": sum(
                item.get("recovery_success") is True for item in rows
            ),
            "bridge_successes": sum(
                item.get("bridge_success") is True for item in rows
            ),
            "horizon_exhausted": sum(
                item.get("horizon_exhausted") is True for item in rows
            ),
            "live_turns": sum(int(item.get("live_turn_count") or 0) for item in rows),
            "executed_attempts": sum(
                int(item.get("executed_attempt_count") or 0) for item in rows
            ),
            "relation_actions_presented": sum(
                item.get("relation_action_presented") is True for item in rows
            ),
            "exact_actions_accepted": sum(
                item.get("exact_action_accepted") is True for item in rows
            ),
            **{
                key: sum(int(item.get("usage", {}).get(key) or 0) for item in rows)
                for key in usage_keys
            },
            **{
                key: sum(
                    int(item.get("compiler_cost", {}).get(key) or 0)
                    for item in rows
                )
                for key in cost_keys
            },
        }
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_batch(prepare_only=args.prepare_only)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        try:
            output.resolve().relative_to(ROOT.resolve())
        except ValueError as exc:
            raise ValueError("experiment output must stay inside project") from exc
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    success = (
        result["preparation_valid"]
        if args.prepare_only
        else result["experiment_valid"]
    )
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
