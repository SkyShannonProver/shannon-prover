"""Five-turn L1/audit/treatment micro for selected-rewrite target recovery.

The fixture is an explicit counterfactual reconstruction, not an authentic
current-toolchain survivor.  Every trajectory starts at the same proof-stripped
state, executes the same rejected ``rewrite get_setE.``, and retains one
tool-free Codex conversation for at most five manager actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from core.easycrypt.proof_state_compiler.backend import action_surface_payload
from workflow.proof_management.protocol_repair import AgentIntent
from workflow.proof_management.repl_session import (
    ReplSessionManager,
    session_dir_path,
)
from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.input_gateway import (
    RuntimeCompilerInput,
    runtime_compiler_input,
)
from workflow.proof_state_compiler.profile_ids import (
    PURE_TAIL_RECOVERY_AUDIT_PROFILE,
    PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import (
    CompilerServiceResult,
    CompilerServiceSkipped,
    ProofStateCompilerService,
)
from workflow.validation.proof_state_compiler_managed_action_model import (
    ManagedActionConversation,
)
from workflow.validation.proof_state_compiler_turn_evidence import (
    rejected_turn_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "workflow/validation/fixtures/pure_tail_rewrite_micro.ec"
LEMMA = "pure_tail_rewrite_micro"
REPLAY_PREFIX = ("move=> Hupdate.",)
FIXED_TRIGGER = "rewrite get_setE."
EXPECTED_ACTION = "rewrite get_setE in Hupdate."
MODEL = "gpt-5.6-sol"
EFFORT = "high"
ARMS = ("l1", "audit", "treatment")
REPEATS = 3
MAX_LIVE_TURNS = 5
MAX_ASSIST_BYTES = 700
TRAJECTORY_ORDER = (
    ("l1", 1),
    ("treatment", 1),
    ("audit", 1),
    ("audit", 2),
    ("l1", 2),
    ("treatment", 2),
    ("treatment", 3),
    ("audit", 3),
    ("l1", 3),
)

CAMPAIGN_SPEC = {
    "schema_version": 1,
    "campaign_id": "pure_tail_selected_rewrite_target_stateful_micro",
    "scope": "counterfactual_identical_state_l1_audit_treatment",
    "source_file": SOURCE_FILE,
    "lemma": LEMMA,
    "fixture_kind": "reconstructed_selected_rewrite_target_failure",
    "historical_context": (
        "historical plain rewrite failures exist, but the closest conclusion_pr "
        "failure is accepted by the current locked EasyCrypt toolchain"
    ),
    "replay_prefix": list(REPLAY_PREFIX),
    "fixed_trigger": FIXED_TRIGGER,
    "native_checked_endpoint": EXPECTED_ACTION,
    "arms": list(ARMS),
    "profiles": {
        "l1": None,
        "audit": PURE_TAIL_RECOVERY_AUDIT_PROFILE,
        "treatment": PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
    },
    "repeats_per_arm": REPEATS,
    "trajectory_order": [list(item) for item in TRAJECTORY_ORDER],
    "live_action_horizon_after_fixed_trigger": MAX_LIVE_TURNS,
    "one_persistent_agent_conversation_per_trajectory": True,
    "state_refresh_after_every_action": True,
    "early_stop": "first manager-accepted proof-state change",
    "primary_endpoint": (
        "manager accepts the exact compiler action at the original material "
        "boundary within five live actions"
    ),
    "secondary_endpoints": [
        "accepted_alternate_progress",
        "rejected_plain_rewrite_attempts",
        "live_actions",
        "treatment_exact_action_uptake",
        "input_cached_output_reasoning_total_tokens",
        "model_compiler_native_certification_wall_clock",
    ],
    "model": MODEL,
    "effort": EFFORT,
    "tools_enabled": False,
    "sample_replacement": False,
    "pass_rule": {
        "all_trajectories_protocol_valid": True,
        "minimum_treatment_primary_successes": 2,
        "treatment_primary_successes_not_less_than_each_control": True,
        "treatment_rejected_plain_rewrites_not_more_than_each_control": True,
        "treatment_total_tokens_less_than_each_control": True,
    },
}
CAMPAIGN_SHA256 = hashlib.sha256(json.dumps(
    CAMPAIGN_SPEC,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ManagedStep:
    intent: str
    tactic: str
    action: dict[str, Any]
    history_before: tuple[str, ...]
    history_after: tuple[str, ...]
    before: RuntimeCompilerInput
    after: RuntimeCompilerInput
    turn_evidence: object | None

    @property
    def failed_unchanged(self) -> bool:
        before = self.before.snapshot.state_ref
        after = self.after.snapshot.state_ref
        return bool(
            self.intent == "commit_tactic"
            and self.action.get("outcome_kind") in {"rejected", "no_progress"}
            and self.action.get("proof_state_effect") == "unchanged"
            and self.history_before == self.history_after
            and before.goal_identity == after.goal_identity
            and before.committed_prefix_identity
            == after.committed_prefix_identity
            and self.turn_evidence is not None
        )

    @property
    def accepted_changed(self) -> bool:
        if not (
            self.action.get("outcome_kind") == "accepted"
            and self.action.get("proof_state_effect") == "changed"
        ):
            return False
        if self.intent == "undo_last_step":
            return bool(
                self.history_before
                and self.history_after == self.history_before[:-1]
            )
        return self.history_after == (*self.history_before, self.tactic)

    def record(self) -> dict[str, Any]:
        authority = self.action.get("execution_authority")
        authority = authority if isinstance(authority, dict) else {}
        return {
            "intent": self.intent,
            "tactic": self.tactic,
            "outcome_kind": self.action.get("outcome_kind"),
            "proof_state_effect": self.action.get("proof_state_effect"),
            "structured_error": str(authority.get("structured_error") or ""),
            "history_before": list(self.history_before),
            "history_after": list(self.history_after),
            "state_before": _snapshot(self.before),
            "state_after": _snapshot(self.after),
            "failed_unchanged": self.failed_unchanged,
            "accepted_changed": self.accepted_changed,
        }


def run_batch(*, prepare_only: bool, root: Path = ROOT) -> dict[str, Any]:
    git = _git_identity(root)
    if git["tracked_dirty"]:
        raise RuntimeError("pure-tail stateful micro requires no tracked changes")
    with tempfile.TemporaryDirectory(
        prefix="shannon_pure_tail_sources_", dir="/private/tmp"
    ) as source_dir:
        original = root / SOURCE_FILE
        prepared = prepare_eval_source(
            source_file=original,
            target_lemma=LEMMA,
            output_dir=Path(source_dir),
            copy_root=original.parent,
            strip_proofs=True,
        )
        preparation = _prepare(prepared.isolated_file, root)
        trajectories = [] if prepare_only else [
            _trajectory(
                prepared_file=prepared.isolated_file,
                arm=arm,
                repeat=repeat,
                root=root,
            )
            for arm, repeat in TRAJECTORY_ORDER
        ]
    experiment_valid = bool(
        not prepare_only
        and preparation["preparation_valid"]
        and len(trajectories) == len(TRAJECTORY_ORDER)
        and all(item["trajectory_valid"] for item in trajectories)
    )
    summary = _summarize(trajectories)
    return {
        "schema_version": 1,
        "kind": "proof_state_compiler_pure_tail_rewrite_stateful_micro",
        "campaign_spec": CAMPAIGN_SPEC,
        "campaign_sha256": CAMPAIGN_SHA256,
        "mode": "prepare_only" if prepare_only else "model_micro",
        "git": git,
        "model_authorization": "explicit_user_authorization_2026-08-10",
        "source_contract": "proof_stripped_counterfactual_fixture",
        "preparation": preparation,
        "preparation_valid": preparation["preparation_valid"],
        "trajectories": trajectories,
        "experiment_valid": experiment_valid,
        "summary_by_arm": summary,
        "decision": _decision(experiment_valid, summary),
    }


def _prepare(prepared_file: Path, root: Path) -> dict[str, Any]:
    manager, session_path = _manager(
        prepared_file, f"pure_tail_prepare_{uuid.uuid4().hex[:10]}", root
    )
    try:
        manager.start(replay_prefix=list(REPLAY_PREFIX))
        fixed = _execute(manager, "commit_tactic", FIXED_TRIGGER)
        audit = _compile(_service(manager, "audit"), fixed)
        treatment = _compile(_service(manager, "treatment"), fixed)
        exact = _action_tactic(treatment["visible_item"])
        corrected = (
            _execute(manager, "commit_tactic", exact) if exact else None
        )
        checks = {
            "replay_prefix_exact": fixed.history_before == REPLAY_PREFIX,
            "fixed_trigger_failed_unchanged": fixed.failed_unchanged,
            "audit_hidden_candidate_exact": (
                audit["admitted_bytes"] == 0
                and audit["visible_item"] == {}
                and _action_tactic(audit["candidate_item"])
                == EXPECTED_ACTION
            ),
            "treatment_one_exact_action": exact == EXPECTED_ACTION,
            "sole_recovery_owner": treatment["owner_feature_ids"]
            == ["pure_tail_recovery"],
            "standard_certification_accepted": treatment[
                "certification_accepted"
            ],
            "exact_action_manager_accepted": bool(
                corrected is not None and corrected.accepted_changed
            ),
        }
        return {
            "fixed_trigger": fixed.record(),
            "audit_compilation": audit,
            "treatment_compilation": treatment,
            "corrected_action": {} if corrected is None else corrected.record(),
            "checks": checks,
            "preparation_valid": all(checks.values()),
        }
    finally:
        _cleanup(manager, session_path)


def _trajectory(
    *, prepared_file: Path, arm: str, repeat: int, root: Path
) -> dict[str, Any]:
    manager, session_path = _manager(
        prepared_file,
        f"pure_tail_{arm}_r{repeat}_{uuid.uuid4().hex[:10]}",
        root,
    )
    try:
        manager.start(replay_prefix=list(REPLAY_PREFIX))
        fixed = _execute(manager, "commit_tactic", FIXED_TRIGGER)
        initial_goal = fixed.after.snapshot.state_ref.goal_identity
        service = None if arm == "l1" else _service(manager, arm)
        current = fixed
        turns: list[dict[str, Any]] = []
        stop_reason = ""
        with ManagedActionConversation(
            model=MODEL, effort=EFFORT, cwd=root
        ) as conversation:
            for turn_index in range(1, MAX_LIVE_TURNS + 1):
                compilation = (
                    _no_compilation()
                    if arm == "l1" or not current.failed_unchanged
                    else _compile(service, current)
                )
                panel = _panel(current, arm, compilation["visible_item"])
                model_result = conversation.next_action(
                    "Choose exactly one next managed proof action for this packet:\n"
                    + json.dumps(
                        panel, ensure_ascii=False, separators=(",", ":")
                    )
                )
                intent = str(model_result.get("intent") or "").strip()
                tactic = str(model_result.get("tactic") or "").strip()
                provider_valid = _provider_valid(
                    model_result, intent, tactic, panel
                )
                executed = (
                    _execute(manager, intent, tactic)
                    if provider_valid else None
                )
                primary = bool(
                    executed is not None
                    and executed.accepted_changed
                    and executed.intent == "commit_tactic"
                    and executed.tactic == EXPECTED_ACTION
                    and executed.history_before == REPLAY_PREFIX
                    and executed.before.snapshot.state_ref.goal_identity
                    == initial_goal
                )
                visible_action = _action_tactic(compilation["visible_item"])
                turns.append({
                    "turn_index": turn_index,
                    "conversation_turn": model_result.get("conversation_turn"),
                    "thread_id": model_result.get("thread_id", ""),
                    "panel": panel,
                    "compilation": compilation,
                    "model_intent": intent,
                    "model_tactic": tactic,
                    "provider_valid": provider_valid,
                    "model_returncode": model_result.get("returncode"),
                    "model_error": model_result.get("error", ""),
                    "duration_ms": model_result.get("duration_ms", 0),
                    "usage": _usage(model_result.get("usage", {})),
                    "tools_observed": model_result.get("tools_observed", []),
                    "provider_event_audit": model_result.get(
                        "provider_event_audit", {}
                    ),
                    "execution": {} if executed is None else executed.record(),
                    "primary_success": primary,
                    "treatment_exact_action_uptake": bool(
                        arm == "treatment"
                        and visible_action
                        and tactic == visible_action
                    ),
                    "rejected_plain_rewrite": bool(
                        executed is not None
                        and tactic.strip().startswith("rewrite ")
                        and executed.failed_unchanged
                    ),
                })
                if not provider_valid or executed is None:
                    stop_reason = "provider_invalid"
                    break
                current = executed
                if primary:
                    stop_reason = "accepted_exact_recovery"
                    break
                if executed.accepted_changed:
                    stop_reason = "accepted_alternate_progress"
                    break
                if not executed.failed_unchanged:
                    stop_reason = "unexpected_manager_transition"
                    break
        if not stop_reason:
            stop_reason = "horizon_exhausted"
        thread_ids = {
            str(item["thread_id"]) for item in turns if item["thread_id"]
        }
        conversation_valid = bool(
            len(thread_ids) == 1
            and [item["conversation_turn"] for item in turns]
            == list(range(1, len(turns) + 1))
        )
        valid_stop = stop_reason in {
            "accepted_exact_recovery",
            "accepted_alternate_progress",
            "horizon_exhausted",
        }
        return {
            "arm": arm,
            "repeat": repeat,
            "fixed_trigger": fixed.record(),
            "turns": turns,
            "trajectory_valid": bool(
                fixed.failed_unchanged
                and turns
                and all(item["provider_valid"] for item in turns)
                and conversation_valid
                and valid_stop
            ),
            "single_conversation_valid": conversation_valid,
            "stop_reason": stop_reason,
            "primary_success": any(item["primary_success"] for item in turns),
            "accepted_alternate_progress": (
                stop_reason == "accepted_alternate_progress"
            ),
            "rejected_plain_rewrites": sum(
                item["rejected_plain_rewrite"] for item in turns
            ),
            "treatment_exact_action_uptake": sum(
                item["treatment_exact_action_uptake"] for item in turns
            ),
            "live_turn_count": len(turns),
            "usage": _aggregate_usage(turns),
            "compiler_cost": _aggregate_compiler_cost(turns),
            "final_history": list(manager.committed_history()),
        }
    finally:
        _cleanup(manager, session_path)


def _execute(
    manager: ReplSessionManager, intent: str, tactic: str
) -> ManagedStep:
    if intent not in {"commit_tactic", "undo_last_step"}:
        raise ValueError(f"unsupported managed intent {intent}")
    payload = {"tactic": tactic} if intent == "commit_tactic" else {}
    before_history = tuple(manager.committed_history())
    before = runtime_compiler_input(manager.read_compiler_input_v2())
    agent_intent = AgentIntent(intent=intent, payload=payload)
    _snapshot_value, actions = manager.handle_intent(agent_intent)
    action = next(
        (item for item in actions if item.get("label") == intent), None
    )
    if not isinstance(action, dict):
        raise RuntimeError(f"manager produced no {intent} action")
    after_history = tuple(manager.committed_history())
    after = runtime_compiler_input(manager.read_compiler_input_v2())
    evidence = None
    if (
        intent == "commit_tactic"
        and action.get("outcome_kind") in {"rejected", "no_progress"}
        and action.get("proof_state_effect") == "unchanged"
    ):
        evidence = rejected_turn_evidence(
            state_ref=after.snapshot.state_ref,
            action=action,
            intent=agent_intent,
            history=after_history,
        )
    return ManagedStep(
        intent,
        tactic,
        action,
        before_history,
        after_history,
        before,
        after,
        evidence,
    )


def _compile(
    service: ProofStateCompilerService | None, step: ManagedStep
) -> dict[str, Any]:
    if service is None or step.turn_evidence is None:
        return _no_compilation()
    result = service.compile_current_state(step.turn_evidence)
    if isinstance(result, CompilerServiceSkipped):
        return _no_compilation(compile_invoked=True)
    if not isinstance(result, CompilerServiceResult):
        raise TypeError("unknown compiler service result")
    candidates = result.bundle.candidate_surface.actions
    if len(candidates) > 1:
        raise RuntimeError("pure-tail micro observed multiple candidates")
    candidate = {} if not candidates else {
        "intent": candidates[0].intent,
        "payload": candidates[0].payload.to_dict(),
        "correction": (
            {} if candidates[0].correction is None else {
                "presentation_kind": candidates[0].correction.presentation_kind,
                "reason_code": candidates[0].correction.reason_code,
                "reason": candidates[0].correction.reason,
            }
        ),
    }
    payload = action_surface_payload(result.action_surface)
    visible = payload["actions"]
    if len(visible) > 1:
        raise RuntimeError("pure-tail micro exposed multiple actions")
    ownership = result.bundle.analyzed_state.recovery_ownership
    return {
        "compile_invoked": True,
        "candidate_item": candidate,
        "visible_item": {} if not visible else visible[0],
        "owner_feature_ids": list(ownership.claimant_feature_ids),
        "admitted_bytes": result.admission.markdown_bytes,
        "certification_accepted": bool(
            len(result.certifications) == 1
            and result.certifications[0].accepted
        ),
        "timings_ms": result.telemetry.get("timings_ms", {}),
        "native_semantics": {
            key: result.telemetry.get("native_semantics", {}).get(key)
            for key in ("planned_request_count", "batch_count", "elapsed_ms")
        },
    }


def _no_compilation(*, compile_invoked: bool = False) -> dict[str, Any]:
    return {
        "compile_invoked": compile_invoked,
        "candidate_item": {},
        "visible_item": {},
        "owner_feature_ids": [],
        "admitted_bytes": 0,
        "certification_accepted": False,
        "timings_ms": {"total": 0, "certification": 0},
        "native_semantics": {
            "planned_request_count": 0,
            "batch_count": 0,
            "elapsed_ms": 0,
        },
    }


def _panel(
    step: ManagedStep, arm: str, visible_item: dict[str, Any]
) -> dict[str, Any]:
    authority = step.action.get("execution_authority")
    authority = authority if isinstance(authority, dict) else {}
    snapshot = step.after.snapshot
    panel: dict[str, Any] = {
        "state_contract": (
            "This exact current state is authoritative and supersedes all "
            "state analysis from earlier turns."
        ),
        "current_state": {
            "state_version": snapshot.state_ref.state_version,
            "goal_identity": snapshot.state_ref.goal_identity,
            "goal_count": snapshot.goal_count,
            "closed": snapshot.closed,
        },
        "current_goal": {"lines": list(snapshot.goal_lines)},
        "last_result": {
            "intent": step.intent,
            "tactic": step.tactic,
            "outcome_kind": step.action.get("outcome_kind"),
            "proof_state_effect": step.action.get("proof_state_effect"),
            "error_summary": str(
                authority.get("structured_error") or ""
            )[:1200],
        },
        "proof_controls": (
            [{"intent": "undo_last_step", "payload": {}}]
            if step.history_after else []
        ),
    }
    if arm == "treatment" and visible_item:
        encoded = json.dumps(
            visible_item, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) > MAX_ASSIST_BYTES:
            raise ValueError("pure-tail compiler item exceeds byte budget")
        panel["compiler_assist"] = [visible_item]
    return panel


def _provider_valid(
    result: dict[str, Any], intent: str, tactic: str, panel: dict[str, Any]
) -> bool:
    audit = result.get("provider_event_audit")
    audit = audit if isinstance(audit, dict) else {}
    action_valid = bool(
        (intent == "commit_tactic" and tactic.endswith("."))
        or (
            intent == "undo_last_step"
            and not tactic
            and {"intent": "undo_last_step", "payload": {}}
            in panel["proof_controls"]
        )
    )
    return bool(
        result.get("returncode") == 0
        and not result.get("error")
        and action_valid
        and not result.get("tools_observed")
        and audit.get("protocol_valid") is True
        and not audit.get("provider_errors")
        and not audit.get("protocol_unknowns")
        and not audit.get("cardinality_errors")
        and audit.get("reasoning_text_retained") is False
        and audit.get("assistant_text_retained") is False
    )


def _service(
    manager: ReplSessionManager, arm: str
) -> ProofStateCompilerService:
    profile = {
        "audit": PURE_TAIL_RECOVERY_AUDIT_PROFILE,
        "treatment": PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
    }.get(arm)
    if profile is None:
        raise ValueError(f"no pure-tail profile for arm {arm}")
    assembly = compiler_assembly_for_profile(profile)
    if assembly is None:
        raise RuntimeError(f"missing pure-tail profile {profile}")
    return ProofStateCompilerService.create(runtime=manager, assembly=assembly)


def _manager(
    prepared_file: Path, tag: str, root: Path
) -> tuple[ReplSessionManager, Path]:
    manager = ReplSessionManager(
        file_path=str(prepared_file),
        lemma_name=LEMMA,
        include_dir="easycrypt-src/theories",
        session_tag=tag,
        node_id=f"experiment-{tag}",
        project_root=root,
    )
    return manager, session_dir_path(manager.session_dir, root)


def _cleanup(manager: ReplSessionManager, session_path: Path) -> None:
    manager.close()
    if session_path.name.startswith(".ec_session_pure_tail_"):
        shutil.rmtree(session_path, ignore_errors=True)
        for suffix in (".cli.lock", ".pre_restart.txt"):
            session_path.with_name(
                session_path.name + suffix
            ).unlink(missing_ok=True)


def _git_identity(root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return {
        "commit": commit,
        "tracked_dirty": bool(dirty),
        "untracked_files_excluded": True,
    }


def _snapshot(value: RuntimeCompilerInput) -> dict[str, Any]:
    snapshot = value.snapshot
    return {
        "state_version": snapshot.state_ref.state_version,
        "goal_identity": snapshot.state_ref.goal_identity,
        "committed_prefix_identity": (
            snapshot.state_ref.committed_prefix_identity
        ),
        "goal_count": snapshot.goal_count,
        "closed": snapshot.closed,
        "goal_lines": list(snapshot.goal_lines),
    }


def _action_tactic(item: object) -> str:
    source = item if isinstance(item, dict) else {}
    payload = source.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    return str(payload.get("tactic") or "")


def _usage(value: object) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    result = {
        "input_tokens": int(source.get("input_tokens") or 0),
        "cached_input_tokens": int(source.get("cached_input_tokens") or 0),
        "output_tokens": int(source.get("output_tokens") or 0),
        "reasoning_output_tokens": int(
            source.get("reasoning_output_tokens")
            or source.get("reasoning_tokens")
            or 0
        ),
    }
    result["total_tokens"] = int(
        source.get("total_tokens")
        or result["input_tokens"] + result["output_tokens"]
    )
    return result


def _aggregate_usage(turns: list[dict[str, Any]]) -> dict[str, int]:
    keys = (
        "input_tokens", "cached_input_tokens", "output_tokens",
        "reasoning_output_tokens", "total_tokens",
    )
    return {
        **{
            key: sum(int(item["usage"].get(key) or 0) for item in turns)
            for key in keys
        },
        "model_wall_clock_ms": sum(
            int(item.get("duration_ms") or 0) for item in turns
        ),
    }


def _aggregate_compiler_cost(turns: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "compiler_wall_clock_ms": sum(
            int(item["compilation"]["timings_ms"].get("total") or 0)
            for item in turns
        ),
        "native_wall_clock_ms": sum(
            int(item["compilation"]["native_semantics"].get("elapsed_ms") or 0)
            for item in turns
        ),
        "certification_wall_clock_ms": sum(
            int(item["compilation"]["timings_ms"].get("certification") or 0)
            for item in turns
        ),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        selected = [item for item in rows if item.get("arm") == arm]
        result[arm] = {
            "trajectories": len(selected),
            "valid_trajectories": sum(
                item.get("trajectory_valid") is True for item in selected
            ),
            "primary_successes": sum(
                item.get("primary_success") is True for item in selected
            ),
            "accepted_alternate_progress": sum(
                item.get("accepted_alternate_progress") is True
                for item in selected
            ),
            "rejected_plain_rewrites": sum(
                int(item.get("rejected_plain_rewrites") or 0)
                for item in selected
            ),
            "treatment_exact_action_uptake": sum(
                int(item.get("treatment_exact_action_uptake") or 0)
                for item in selected
            ),
            "live_turns": sum(
                int(item.get("live_turn_count") or 0) for item in selected
            ),
            **{
                key: sum(int(item["usage"].get(key) or 0) for item in selected)
                for key in (
                    "input_tokens", "cached_input_tokens", "output_tokens",
                    "reasoning_output_tokens", "total_tokens",
                    "model_wall_clock_ms",
                )
            },
            **{
                key: sum(
                    int(item["compiler_cost"].get(key) or 0)
                    for item in selected
                )
                for key in (
                    "compiler_wall_clock_ms", "native_wall_clock_ms",
                    "certification_wall_clock_ms",
                )
            },
        }
    return result


def _decision(
    valid: bool, summary: dict[str, dict[str, int]]
) -> dict[str, Any]:
    if not valid:
        return {"passed": False, "code": "INVALID_EXPERIMENT", "checks": {}}
    treatment = summary["treatment"]
    controls = (summary["l1"], summary["audit"])
    checks = {
        "minimum_treatment_primary_successes": (
            treatment["primary_successes"] >= 2
        ),
        "treatment_primary_successes_not_less_than_each_control": all(
            treatment["primary_successes"] >= item["primary_successes"]
            for item in controls
        ),
        "treatment_rejected_plain_rewrites_not_more_than_each_control": all(
            treatment["rejected_plain_rewrites"]
            <= item["rejected_plain_rewrites"] for item in controls
        ),
        "treatment_total_tokens_less_than_each_control": all(
            treatment["total_tokens"] < item["total_tokens"]
            for item in controls
        ),
    }
    passed = all(checks.values())
    return {
        "passed": passed,
        "code": (
            "PURE_TAIL_REWRITE_STATEFUL_MICRO_PASS"
            if passed else "PURE_TAIL_REWRITE_STATEFUL_MICRO_FAIL"
        ),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_batch(prepare_only=args.prepare_only)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if (
        result["preparation_valid"]
        if args.prepare_only else result["experiment_valid"]
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
