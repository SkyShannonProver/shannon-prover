"""Five-turn L1/treatment micro for an authentic PHL boundary failure.

The fixed trigger is the failed function-level ``transitivity`` from the
historical ``step1`` bundle.  Each arm then receives at most five live managed
actions.  An accepted rewind does not terminate the trajectory: the manager
refreshes the exact state and the model continues from that new boundary.

This is a bounded local recovery experiment, not a full-proof experiment and
not a natural-trigger-incidence estimate.
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
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair.syntax import (
    is_candidate_phl_transitivity,
)
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
    PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import (
    CompilerServiceResult,
    CompilerServiceSkipped,
    ProofStateCompilerService,
)
from workflow.validation.proof_state_compiler_managed_action_model import (
    run_managed_action_model,
)
from workflow.validation.proof_state_compiler_turn_evidence import (
    rejected_turn_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "eval/examples/ChaChaPoly/chacha_poly.ec"
LEMMA = "step1"
PROFILE = PHL_TRANSITIVITY_BOUNDARY_TREATMENT_PROFILE
MODEL = "gpt-5.6-sol"
EFFORT = "high"
ARMS = ("l1", "treatment")
REPEATS = 3
MAX_LIVE_TURNS = 5
MAX_ASSIST_BYTES = 900
MODEL_TIMEOUT_SECONDS = 300
TRAJECTORY_ORDER = (
    ("l1", 1),
    ("treatment", 1),
    ("treatment", 2),
    ("l1", 2),
    ("l1", 3),
    ("treatment", 3),
)

# Accepted historical prefix through the second ``proc``.  The earlier
# rejected ``rnd`` and the later undone ``inline ChaChaPoly.enc`` are omitted.
REPLAY_PREFIX = (
    "congr.",
    "byequiv.",
    "proc.",
    "inline D(A, IndBlock).guess.",
    "inline RealOrcls(ChaChaPoly).init IndBlock.init D(A, IndBlock).O.init.",
    "inline ChaChaPoly.init ChaChaPoly.kg.",
    "seq 2 1 : (Mem.k{1} = IndBlock.k{2} /\\ ={glob A}).",
    "wp.",
    "rnd.",
    "skip; smt().",
    "wp.",
    "call (_: Mem.k{1} = IndBlock.k{2}).",
    "proc.",
)
FIXED_REJECTED_TACTIC = (
    "transitivity GenChaChaPoly(OpCCinit.OCC(I_stateless)).enc "
    "(arg{1} = arg{2} /\\ Mem.k{1} = Mem.k{2} ==> "
    "res{1} = res{2} /\\ Mem.k{1} = Mem.k{2}) "
    "(arg{1} = arg{2} /\\ Mem.k{1} = IndBlock.k{2} ==> "
    "res{1} = res{2} /\\ Mem.k{1} = IndBlock.k{2})."
)
HISTORICAL_ACCEPTED_TACTIC = (
    "transitivity RealOrcls(GenChaChaPoly(OpCCinit.OCC(I_stateless))).enc "
    "(arg{1} = arg{2} /\\ Mem.k{1} = Mem.k{2} ==> "
    "res{1} = res{2} /\\ Mem.k{1} = Mem.k{2}) "
    "(arg{1} = arg{2} /\\ Mem.k{1} = IndBlock.k{2} ==> "
    "res{1} = res{2} /\\ Mem.k{1} = IndBlock.k{2})."
)
HISTORICAL_STATEMENT_GOAL_IDENTITY = (
    "7b6f418937b95185399a56eb1a3bf0f7aa9500b8"
)
HISTORICAL_BUNDLE = (
    "agent_view_runs/step1/"
    "2026-08-06_1958_step1--step1_audit_first__"
    "l4_proof_state_compiler_v2_failure_feedback_audit__r01__4a7677d72"
)

CAMPAIGN_SPEC = {
    "schema_version": 1,
    "campaign_id": "phl_transitivity_boundary_five_turn_comparison",
    "scope": "bounded_local_l1_treatment_micro",
    "source_file": SOURCE_FILE,
    "lemma": LEMMA,
    "historical_bundle": HISTORICAL_BUNDLE,
    "historical_statement_goal_identity": HISTORICAL_STATEMENT_GOAL_IDENTITY,
    "replay_prefix": list(REPLAY_PREFIX),
    "fixed_trigger": FIXED_REJECTED_TACTIC,
    "historical_accepted_route": [
        {"intent": "undo_last_step", "payload": {}},
        {"intent": "commit_tactic", "tactic": HISTORICAL_ACCEPTED_TACTIC},
    ],
    "arms": list(ARMS),
    "treatment_profile": PROFILE,
    "repeats_per_arm": REPEATS,
    "trajectory_order": [list(item) for item in TRAJECTORY_ORDER],
    "live_turn_horizon_after_fixed_trigger": MAX_LIVE_TURNS,
    "accepted_rewind_stops_early": False,
    "primary_endpoint": "manager-accepted PHL transitivity within five actions",
    "secondary_endpoints": [
        "function_boundary_reached",
        "repeated_same_boundary_mismatches",
        "token_categories",
        "model_compiler_native_wall_clock",
    ],
    "model": MODEL,
    "effort": EFFORT,
    "tools_enabled": False,
    "sample_replacement": False,
    "pass_rule": {
        "minimum_treatment_phl_successes": 2,
        "treatment_phl_successes_not_less_than_l1": True,
        "treatment_repeated_boundary_mismatches_not_more_than_l1": True,
        "treatment_total_tokens_less_than_l1": True,
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
    compiler_input_after: RuntimeCompilerInput
    turn_evidence: object | None

    @property
    def failed_unchanged(self) -> bool:
        return bool(
            self.intent == "commit_tactic"
            and self.action.get("outcome_kind") in {"rejected", "no_progress"}
            and self.action.get("proof_state_effect") == "unchanged"
            and self.history_before == self.history_after
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

    @property
    def accepted_phl_transitivity(self) -> bool:
        return bool(
            self.intent == "commit_tactic"
            and is_candidate_phl_transitivity(self.tactic)
            and self.accepted_changed
        )

    def record(self) -> dict[str, Any]:
        authority = self.action.get("execution_authority")
        authority = authority if isinstance(authority, dict) else {}
        snapshot = self.compiler_input_after.snapshot
        return {
            "intent": self.intent,
            "tactic": self.tactic,
            "outcome_kind": self.action.get("outcome_kind"),
            "proof_state_effect": self.action.get("proof_state_effect"),
            "structured_error": str(authority.get("structured_error") or ""),
            "event_id": str(authority.get("event_id") or ""),
            "state_version": snapshot.state_ref.state_version,
            "goal_identity": snapshot.state_ref.goal_identity,
            "goal_count": snapshot.goal_count,
            "goal_count_known": snapshot.goal_count_known,
            "closed": snapshot.closed,
            "history_before": list(self.history_before),
            "history_after": list(self.history_after),
            "failed_unchanged": self.failed_unchanged,
            "accepted_changed": self.accepted_changed,
            "accepted_phl_transitivity": self.accepted_phl_transitivity,
        }


def run_batch(*, prepare_only: bool, root: Path = ROOT) -> dict[str, Any]:
    git = _tracked_git_identity(root)
    if git["tracked_dirty"]:
        raise RuntimeError("PHL five-turn micro requires no tracked changes")
    with tempfile.TemporaryDirectory(
        prefix="shannon_phl_five_turn_sources_",
        dir="/private/tmp",
    ) as source_dir:
        original_source = root / SOURCE_FILE
        prepared = prepare_eval_source(
            source_file=original_source,
            target_lemma=LEMMA,
            output_dir=Path(source_dir),
            copy_root=original_source.parent,
            strip_proofs=True,
        )
        preparation = _run_preparation(
            prepared_file=prepared.isolated_file,
            root=root,
        )
        trajectories = [] if prepare_only else [
            _run_trajectory(
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
    return {
        "schema_version": 1,
        "kind": "proof_state_compiler_phl_boundary_five_turn_micro",
        "campaign_spec": CAMPAIGN_SPEC,
        "campaign_sha256": CAMPAIGN_SHA256,
        "mode": "prepare_only" if prepare_only else "model_micro",
        "git": git,
        "model_authorization": "explicit_user_request_2026-08-09",
        "source_contract": "proof_stripped_project",
        "preparation": preparation,
        "preparation_valid": preparation["preparation_valid"],
        "trajectories": trajectories,
        "experiment_valid": experiment_valid,
        "summary_by_arm": _summarize_by_arm(trajectories),
    }


def _run_preparation(*, prepared_file: Path, root: Path) -> dict[str, Any]:
    manager, session_path = _manager(
        prepared_file=prepared_file,
        tag=f"phl_five_prepare_{uuid.uuid4().hex[:12]}",
        root=root,
    )
    try:
        manager.start(replay_prefix=list(REPLAY_PREFIX))
        replay_history = tuple(manager.committed_history())
        initial = runtime_compiler_input(manager.read_compiler_input_v2())
        fixed = _execute_action(
            manager,
            intent="commit_tactic",
            tactic=FIXED_REJECTED_TACTIC,
        )
        service = _treatment_service(manager)
        compilation = _compile_occurrence(service, fixed)
        panel = _panel(
            fixed,
            arm="treatment",
            compiler_item=compilation["item"],
        )
        rewind = _execute_action(
            manager,
            intent="undo_last_step",
            tactic="",
        )
        function_goal_identity = (
            rewind.compiler_input_after.snapshot.state_ref.goal_identity
        )
        historical_bridge = _execute_action(
            manager,
            intent="commit_tactic",
            tactic=HISTORICAL_ACCEPTED_TACTIC,
        )
        checks = {
            "replay_prefix_exact": replay_history == REPLAY_PREFIX,
            "historical_statement_goal_identity_matches": (
                initial.snapshot.state_ref.goal_identity
                == HISTORICAL_STATEMENT_GOAL_IDENTITY
            ),
            "fixed_failure_state_identity_unchanged": (
                fixed.compiler_input_after.snapshot.state_ref.goal_identity
                == initial.snapshot.state_ref.goal_identity
            ),
            "fixed_failure_rejected_unchanged": fixed.failed_unchanged,
            "compiler_owner_exact": compilation["eligible_feature_ids"]
            == ["phl_transitivity_boundary_repair"],
            "compiler_diagnostic_exact": bool(
                compilation["kind"] == "diagnostic"
                and compilation["item"].get("code") == "phl_boundary"
            ),
            "panel_advertises_exact_undo": panel.get("proof_controls")
            == [{"intent": "undo_last_step", "payload": {}}],
            "rewind_accepted_changed": rewind.accepted_changed,
            "rewind_reaches_new_function_boundary": bool(
                function_goal_identity
                and function_goal_identity != HISTORICAL_STATEMENT_GOAL_IDENTITY
                and any(
                    "RealOrcls(ChaChaPoly).enc ~ D(A, IndBlock).O.enc" in line
                    for line in rewind.compiler_input_after.snapshot.goal_lines
                )
            ),
            "historical_bridge_accepted": historical_bridge.accepted_phl_transitivity,
            "historical_bridge_history_exact": (
                historical_bridge.history_after
                == (*REPLAY_PREFIX[:-1], HISTORICAL_ACCEPTED_TACTIC)
            ),
        }
        return {
            "initial_state": _snapshot_record(initial),
            "fixed_trigger": fixed.record(),
            "compilation": compilation,
            "treatment_panel": panel,
            "rewind": rewind.record(),
            "function_goal_identity": function_goal_identity,
            "historical_bridge": historical_bridge.record(),
            "checks": checks,
            "preparation_valid": all(checks.values()),
        }
    finally:
        _cleanup_manager(manager, session_path)


def _run_trajectory(
    *, prepared_file: Path, arm: str, repeat: int, root: Path
) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError(f"unsupported PHL micro arm: {arm}")
    manager, session_path = _manager(
        prepared_file=prepared_file,
        tag=f"phl_five_{arm}_r{repeat}_{uuid.uuid4().hex[:12]}",
        root=root,
    )
    try:
        manager.start(replay_prefix=list(REPLAY_PREFIX))
        service = _treatment_service(manager) if arm == "treatment" else None
        fixed = _execute_action(
            manager,
            intent="commit_tactic",
            tactic=FIXED_REJECTED_TACTIC,
        )
        current = fixed
        initial_goal_identity = (
            fixed.compiler_input_after.snapshot.state_ref.goal_identity
        )
        turns: list[dict[str, Any]] = []
        stop_reason = ""
        for turn_index in range(1, MAX_LIVE_TURNS + 1):
            compilation = _compilation_for_arm(
                arm=arm,
                service=service,
                executed=current,
            )
            panel = _panel(
                current,
                arm=arm,
                compiler_item=compilation["item"],
            )
            prompt = _agent_prompt(panel)
            try:
                model_result = run_managed_action_model(
                    prompt,
                    model=MODEL,
                    effort=EFFORT,
                    cwd=root,
                )
            except subprocess.TimeoutExpired:
                model_result = _timeout_result(prompt)
            intent = str(model_result.get("intent") or "").strip()
            tactic = str(model_result.get("tactic") or "").strip()
            provider_valid = _provider_valid(
                model_result,
                intent=intent,
                tactic=tactic,
                panel=panel,
            )
            executed = (
                _execute_action(manager, intent=intent, tactic=tactic)
                if provider_valid
                else None
            )
            turn = {
                "turn_index": turn_index,
                "panel": panel,
                "prompt_sha256": model_result.get("prompt_sha256", ""),
                "prompt_bytes": model_result.get("prompt_bytes", 0),
                "compilation": compilation,
                "model_intent": intent,
                "model_tactic": tactic,
                "model_returncode": model_result.get("returncode"),
                "model_error": model_result.get("error", ""),
                "duration_ms": model_result.get("duration_ms", 0),
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
            current = executed
            if executed.accepted_phl_transitivity:
                stop_reason = "accepted_phl_transitivity"
                break
            if executed.compiler_input_after.snapshot.closed:
                stop_reason = "closed_without_phl_endpoint"
                break
        if not stop_reason:
            stop_reason = "horizon_exhausted"
        provider_valid = bool(
            turns and all(item["provider_valid"] for item in turns)
        )
        valid_stop = stop_reason in {
            "accepted_phl_transitivity",
            "closed_without_phl_endpoint",
            "horizon_exhausted",
        }
        phl_success = any(
            item.get("execution", {}).get("accepted_phl_transitivity") is True
            for item in turns
        )
        function_boundary_reached = any(
            item.get("execution", {}).get("goal_identity")
            and item.get("execution", {}).get("goal_identity")
            != initial_goal_identity
            and any(
                "RealOrcls(ChaChaPoly).enc ~ D(A, IndBlock).O.enc" in line
                for line in item.get("panel_after_goal_lines", [])
            )
            for item in turns
        ) or any(
            item.get("model_intent") == "undo_last_step"
            and item.get("execution", {}).get("accepted_changed") is True
            for item in turns
        )
        repeated_boundary_mismatches = sum(
            item.get("execution", {}).get("failed_unchanged") is True
            and "expecting a goal of the form: equiv[F]" in str(
                item.get("execution", {}).get("structured_error") or ""
            )
            for item in turns
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
            "phl_success": phl_success,
            "function_boundary_reached": function_boundary_reached,
            "repeated_boundary_mismatches": repeated_boundary_mismatches,
            "live_turn_count": len(turns),
            "final_history": list(manager.committed_history()),
            "usage": _aggregate_usage(turns),
            "compiler_cost": _aggregate_compiler_cost(turns),
        }
    finally:
        _cleanup_manager(manager, session_path)


def _execute_action(
    manager: ReplSessionManager,
    *,
    intent: str,
    tactic: str,
) -> ManagedStep:
    if intent not in {"commit_tactic", "undo_last_step"}:
        raise ValueError(f"unsupported managed action: {intent}")
    if intent == "commit_tactic" and not tactic:
        raise ValueError("commit_tactic requires a tactic")
    if intent == "undo_last_step" and tactic:
        raise ValueError("undo_last_step cannot carry a tactic")
    history_before = tuple(manager.committed_history())
    payload = {"tactic": tactic} if intent == "commit_tactic" else {}
    agent_intent = AgentIntent(intent=intent, payload=payload)
    _snapshot, actions = manager.handle_intent(agent_intent)
    action = next(
        (item for item in actions if item.get("label") == intent),
        None,
    )
    if not isinstance(action, dict):
        raise RuntimeError(f"managed action produced no {intent} result")
    history_after = tuple(manager.committed_history())
    compiler_input = runtime_compiler_input(manager.read_compiler_input_v2())
    evidence = None
    if (
        intent == "commit_tactic"
        and action.get("outcome_kind") in {"rejected", "no_progress"}
        and action.get("proof_state_effect") == "unchanged"
    ):
        evidence = rejected_turn_evidence(
            state_ref=compiler_input.snapshot.state_ref,
            action=action,
            intent=agent_intent,
            history=history_after,
        )
    return ManagedStep(
        intent=intent,
        tactic=tactic,
        action=action,
        history_before=history_before,
        history_after=history_after,
        compiler_input_after=compiler_input,
        turn_evidence=evidence,
    )


def _compilation_for_arm(
    *,
    arm: str,
    service: ProofStateCompilerService | None,
    executed: ManagedStep,
) -> dict[str, Any]:
    if arm == "l1" or not executed.failed_unchanged:
        return _no_compilation()
    if service is None:
        raise RuntimeError("treatment arm requires a compiler service")
    return {"compile_invoked": True, **_compile_occurrence(service, executed)}


def _compile_occurrence(
    service: ProofStateCompilerService,
    executed: ManagedStep,
) -> dict[str, Any]:
    if executed.turn_evidence is None:
        raise RuntimeError("PHL recovery requires an unchanged failed action")
    result = service.compile_current_state(executed.turn_evidence)
    if isinstance(result, CompilerServiceSkipped):
        return {
            "kind": "none",
            "item": {},
            "eligible_feature_ids": [],
            "admitted_bytes": 0,
            "timings_ms": result.telemetry.get("timings_ms", {}),
            "native_semantics": result.telemetry.get("native_semantics", {}),
            "certifications": [],
        }
    if not isinstance(result, CompilerServiceResult):
        raise TypeError("unknown compiler service result")
    kind, item = _one_visible_item(result)
    return {
        "kind": kind,
        "item": item,
        "eligible_feature_ids": list(
            result.telemetry["execution"]["eligible_feature_ids"]
        ),
        "admitted_bytes": result.admission.markdown_bytes,
        "timings_ms": result.telemetry.get("timings_ms", {}),
        "native_semantics": {
            key: result.telemetry.get("native_semantics", {}).get(key)
            for key in ("planned_request_count", "batch_count", "elapsed_ms")
        },
        "certifications": [],
    }


def _one_visible_item(
    result: CompilerServiceResult,
) -> tuple[str, dict[str, Any]]:
    payload = action_surface_payload(result.action_surface)
    groups = (
        ("resource", payload["resources"]),
        ("binding", payload["bindings"]),
        ("action", payload["actions"]),
        ("diagnostic", payload["diagnostics"]),
    )
    visible = [(kind, item) for kind, items in groups for item in items]
    if len(visible) > 1:
        raise RuntimeError("PHL micro exposed more than one compiler item")
    return visible[0] if visible else ("none", {})


def _no_compilation() -> dict[str, Any]:
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


def _panel(
    executed: ManagedStep,
    *,
    arm: str,
    compiler_item: dict[str, Any],
) -> dict[str, Any]:
    authority = executed.action.get("execution_authority")
    authority = authority if isinstance(authority, dict) else {}
    panel: dict[str, Any] = {
        "current_goal": {
            "lines": list(executed.compiler_input_after.snapshot.goal_lines)
        },
        "last_result": {
            "intent": executed.intent,
            "tactic": executed.tactic,
            "outcome_kind": str(executed.action.get("outcome_kind") or ""),
            "proof_state_effect": str(
                executed.action.get("proof_state_effect") or ""
            ),
            "error_summary": str(
                authority.get("structured_error") or ""
            )[:1200],
        },
        "proof_controls": (
            [{"intent": "undo_last_step", "payload": {}}]
            if executed.history_after
            else []
        ),
    }
    if arm == "treatment" and compiler_item:
        if len(json.dumps(compiler_item, ensure_ascii=False).encode("utf-8")) > (
            MAX_ASSIST_BYTES
        ):
            raise ValueError("PHL compiler item exceeds micro byte budget")
        panel["compiler_assist"] = [compiler_item]
    return panel


def _agent_prompt(panel: dict[str, Any]) -> str:
    return (
        "Choose exactly one next managed proof action for this packet:\n"
        + json.dumps(panel, ensure_ascii=False, separators=(",", ":"))
    )


def _provider_valid(
    model_result: dict[str, Any],
    *,
    intent: str,
    tactic: str,
    panel: dict[str, Any],
) -> bool:
    audit = model_result.get("provider_event_audit")
    audit = audit if isinstance(audit, dict) else {}
    action_valid = bool(
        (intent == "commit_tactic" and tactic.endswith("."))
        or (
            intent == "undo_last_step"
            and tactic == ""
            and {"intent": "undo_last_step", "payload": {}}
            in panel.get("proof_controls", [])
        )
    )
    return bool(
        model_result.get("returncode") == 0
        and not model_result.get("error")
        and action_valid
        and not model_result.get("tools_observed")
        and audit.get("protocol_valid") is True
        and not audit.get("provider_errors")
        and not audit.get("protocol_unknowns")
        and not audit.get("cardinality_errors")
        and audit.get("reasoning_text_retained") is False
        and audit.get("assistant_text_retained") is False
    )


def _manager(
    *, prepared_file: Path, tag: str, root: Path
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


def _treatment_service(
    manager: ReplSessionManager,
) -> ProofStateCompilerService:
    assembly = compiler_assembly_for_profile(PROFILE)
    if assembly is None:
        raise RuntimeError("missing PHL boundary treatment profile")
    return ProofStateCompilerService.create(runtime=manager, assembly=assembly)


def _cleanup_manager(
    manager: ReplSessionManager, session_path: Path
) -> None:
    manager.close()
    if session_path.name.startswith(".ec_session_phl_five_"):
        shutil.rmtree(session_path, ignore_errors=True)
        session_path.with_name(session_path.name + ".cli.lock").unlink(
            missing_ok=True
        )


def _tracked_git_identity(root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    tracked_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {
        "commit": commit,
        "tracked_dirty": bool(tracked_status),
        "untracked_files_excluded": True,
    }


def _snapshot_record(value: RuntimeCompilerInput) -> dict[str, Any]:
    snapshot = value.snapshot
    return {
        "state_version": snapshot.state_ref.state_version,
        "goal_identity": snapshot.state_ref.goal_identity,
        "goal_count": snapshot.goal_count,
        "goal_count_known": snapshot.goal_count_known,
        "closed": snapshot.closed,
        "goal_lines": list(snapshot.goal_lines),
    }


def _normalized_usage(value: object) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    aliases = {
        "input_tokens": ("input_tokens",),
        "cached_input_tokens": ("cached_input_tokens",),
        "output_tokens": ("output_tokens",),
        "reasoning_output_tokens": (
            "reasoning_output_tokens",
            "reasoning_tokens",
        ),
    }
    normalized = {
        key: next(
            (int(source[name]) for name in names if source.get(name) is not None),
            0,
        )
        for key, names in aliases.items()
    }
    normalized["total_tokens"] = int(
        source.get("total_tokens")
        or normalized["input_tokens"] + normalized["output_tokens"]
    )
    return normalized


def _aggregate_usage(turns: list[dict[str, Any]]) -> dict[str, int]:
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
        "model_wall_clock_ms": sum(
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
    result: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        rows = [item for item in trajectories if item.get("arm") == arm]
        result[arm] = {
            "trajectories": len(rows),
            "valid_trajectories": sum(item.get("trajectory_valid") is True for item in rows),
            "phl_successes": sum(item.get("phl_success") is True for item in rows),
            "function_boundary_reached": sum(
                item.get("function_boundary_reached") is True for item in rows
            ),
            "repeated_boundary_mismatches": sum(
                int(item.get("repeated_boundary_mismatches") or 0) for item in rows
            ),
            "live_turns": sum(int(item.get("live_turn_count") or 0) for item in rows),
            **{
                key: sum(int(item.get("usage", {}).get(key) or 0) for item in rows)
                for key in (
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "reasoning_output_tokens",
                    "total_tokens",
                    "model_wall_clock_ms",
                )
            },
            **{
                key: sum(int(item.get("compiler_cost", {}).get(key) or 0) for item in rows)
                for key in (
                    "compiler_wall_clock_ms",
                    "native_wall_clock_ms",
                    "certification_wall_clock_ms",
                )
            },
        }
    return result


def _timeout_result(prompt: str) -> dict[str, Any]:
    return {
        "intent": "",
        "tactic": "",
        "returncode": -1,
        "duration_ms": MODEL_TIMEOUT_SECONDS * 1000,
        "usage": {},
        "error": "model call exceeded frozen timeout",
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_bytes": len(prompt.encode("utf-8")),
        "tools_observed": [],
        "provider_event_audit": {
            "protocol_valid": False,
            "provider_errors": [{"message": "model timeout"}],
            "protocol_unknowns": [],
            "cardinality_errors": ["model process did not complete"],
        },
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
    success = result["preparation_valid"] if args.prepare_only else result["experiment_valid"]
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
