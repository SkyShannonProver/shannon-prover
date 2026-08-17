"""Two-failure treatment chain for current-failure compiler composition.

This is a composition micro, not a full proof or a natural-trigger study.  It
starts at the original ``step2_1`` state and executes the authentic historical
premature application as a fixed trigger.  Every later tactic is selected by
the model, executed by the manager in the same session, and may trigger the
next independently owned recovery feature.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from core.easycrypt.proof_state_compiler.backend import action_surface_payload
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization.syntax import (
    relation_bridge_intent_family,
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
    RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import (
    CompilerServiceResult,
    CompilerServiceSkipped,
    ProofStateCompilerService,
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
from workflow.validation.proof_state_compiler_turn_evidence import (
    rejected_turn_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "eval/examples/ChaChaPoly/chacha_poly.ec"
LEMMA = "step2_1"
PROFILE = RELATION_BRIDGE_REALIZATION_TREATMENT_PROFILE
MODEL_BACKEND = "openai"
MODEL = "gpt-5.6-sol"
EFFORT = "high"
REPEATS = 3
MAX_LIVE_TURNS = 2
MAX_ASSIST_BYTES = 900
MODEL_TIMEOUT_SECONDS = 300
INITIAL_REJECTED_TACTIC = "apply CCA_UFCMA.CCA_CPA_UFCMA."
PREPARED_SECOND_INTENTS = (
    (
        "transitivity",
        "transitivity Pr[CCA_game(A, RealOrcls(StLSke(St))).main() "
        "@ &m : res].",
    ),
    (
        "change",
        "change Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res] "
        "<= Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() "
        "@ &m : res] + Pr[UFCMA(A, St).main() @ &m : exists "
        "(c : ciphertext), (c \\in Mem.lc) /\\ dec StLSke.gs Mem.k c "
        "<> None<:nonce * associated_data * bytes>].",
    ),
)

CAMPAIGN_SPEC = {
    "schema_version": 1,
    "campaign_id": "premature_apply_relation_bridge_chained_recovery",
    "scope": "treatment_composition_micro",
    "source_file": SOURCE_FILE,
    "lemma": LEMMA,
    "profile": PROFILE,
    "fixed_initial_trigger": INITIAL_REJECTED_TACTIC,
    "fixed_trigger_provenance": (
        "historical L1 agent intent; theorem discovery held outside this micro"
    ),
    "live_turns": MAX_LIVE_TURNS,
    "repeats": REPEATS,
    "model_backend": MODEL_BACKEND,
    "model": MODEL,
    "effort": EFFORT,
    "tools_enabled": False,
    "expected_route": [
        "fixed premature apply failed unchanged",
        "operation_binding_repair phase redirect presented",
        "live agent relation intent failed unchanged",
        "relation_bridge_realization Do you mean action presented",
        "live agent exact bridge accepted with two remaining goals",
    ],
}
CAMPAIGN_SHA256 = hashlib.sha256(json.dumps(
    CAMPAIGN_SPEC,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")).hexdigest()
TRIAL_SPEC = OneStepTrialSpec(
    trial_id="premature-apply-relation-bridge-chain-v1",
    feature_id="operation_binding_repair+relation_bridge_realization",
    evidence_ledger_ids=(
        "M15-B24-PHASE-REDIRECT",
        "M16-RELATION-BRIDGE-REALIZATION",
    ),
    max_assist_bytes=MAX_ASSIST_BYTES,
)


@dataclass(frozen=True)
class ExecutedIntent:
    tactic: str
    action: dict[str, Any]
    history_before: tuple[str, ...]
    history_after: tuple[str, ...]
    compiler_input_after: RuntimeCompilerInput
    turn_evidence: object | None

    @property
    def failed_unchanged(self) -> bool:
        return bool(
            self.action.get("outcome_kind") in {"rejected", "no_progress"}
            and self.action.get("proof_state_effect") == "unchanged"
            and self.history_before == self.history_after
            and self.turn_evidence is not None
        )

    @property
    def accepted_changed(self) -> bool:
        return bool(
            self.action.get("outcome_kind") == "accepted"
            and self.action.get("proof_state_effect") == "changed"
            and self.history_after == (*self.history_before, self.tactic)
        )

    def record(self) -> dict[str, Any]:
        authority = self.action.get("execution_authority")
        authority = authority if isinstance(authority, dict) else {}
        return {
            "tactic": self.tactic,
            "outcome_kind": self.action.get("outcome_kind"),
            "proof_state_effect": self.action.get("proof_state_effect"),
            "structured_error": str(authority.get("structured_error") or ""),
            "event_id": str(authority.get("event_id") or ""),
            "artifact_ref": str(authority.get("artifact_ref") or ""),
            "state_version": self.compiler_input_after.snapshot.state_ref.state_version,
            "goal_identity": self.compiler_input_after.snapshot.state_ref.goal_identity,
            "goal_count": self.compiler_input_after.snapshot.goal_count,
            "goal_count_known": self.compiler_input_after.snapshot.goal_count_known,
            "closed": self.compiler_input_after.snapshot.closed,
            "history_before": list(self.history_before),
            "history_after": list(self.history_after),
            "failed_unchanged": self.failed_unchanged,
            "accepted_changed": self.accepted_changed,
        }


def run_batch(*, prepare_only: bool, root: Path = ROOT) -> dict[str, Any]:
    git = git_identity(root)
    if git.get("dirty") is not False:
        raise RuntimeError("chained recovery micro requires a clean worktree")
    token = uuid.uuid4().hex[:12]
    source_output = root / f".chained_recovery_sources_{token}"
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
            route["preparation_valid"] for route in preparation_routes
        )
        trajectories = [] if prepare_only else [
            _run_live_trajectory(
                prepared_file=prepared.isolated_file,
                repeat=repeat,
                root=root,
            )
            for repeat in range(1, REPEATS + 1)
        ]
        experiment_valid = bool(
            preparation_valid
            and not prepare_only
            and len(trajectories) == REPEATS
            and all(item["provider_valid"] for item in trajectories)
        )
        return {
            "schema_version": 1,
            "kind": "proof_state_compiler_chained_recovery_micro",
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
            "summary": _summarize(trajectories),
        }
    finally:
        if source_output.name.startswith(".chained_recovery_sources_"):
            shutil.rmtree(source_output, ignore_errors=True)


def _run_prepared_route(
    *,
    prepared_file: Path,
    route_name: str,
    second_intent: str,
    root: Path,
) -> dict[str, Any]:
    manager, session_path = _manager(
        prepared_file=prepared_file,
        tag=f"chained_recovery_prepare_{route_name}_{uuid.uuid4().hex[:12]}",
        root=root,
    )
    try:
        manager.start(replay_prefix=[])
        service = _treatment_service(manager)
        first = _execute_intent(manager, INITIAL_REJECTED_TACTIC)
        first_compilation = _compile_occurrence(
            service, first, expected_kind="diagnostic"
        )
        first_packet = _packet(first, first_compilation["item"])

        second = _execute_intent(manager, second_intent)
        second_compilation = _compile_occurrence(
            service, second, expected_kind="action"
        )
        second_packet = _packet(second, second_compilation["item"])
        exact_action = str(
            second_compilation["item"].get("payload", {}).get("tactic") or ""
        )
        final = _execute_intent(manager, exact_action)
        checks = {
            "started_before_apply": first.history_before == (),
            "fixed_apply_failed_unchanged": first.failed_unchanged,
            "first_owner_operation_binding": first_compilation[
                "eligible_feature_ids"
            ] == ["operation_binding_repair"],
            "first_item_phase_redirect": (
                first_compilation["kind"] == "diagnostic"
                and first_compilation["item"].get("code")
                == "application_applicability_indeterminate"
                and str(first_compilation["item"].get("primary") or "").endswith(
                    "is not applicable at this proof-state phase."
                )
            ),
            "second_intent_failed_unchanged": second.failed_unchanged,
            "second_owner_relation_bridge": second_compilation[
                "eligible_feature_ids"
            ] == ["relation_bridge_realization"],
            "second_item_do_you_mean_action": (
                second_compilation["kind"] == "action"
                and second_compilation["item"].get("correction", {}).get("kind")
                == "do_you_mean"
            ),
            "exact_action_accepted_changed": final.accepted_changed,
            "two_goals_after_bridge": (
                final.compiler_input_after.snapshot.goal_count_known
                and final.compiler_input_after.snapshot.goal_count == 2
            ),
            "one_committed_tactic": final.history_after == (exact_action,),
        }
        return {
            "route_name": route_name,
            "second_intent": second_intent,
            "fixed_trigger": first.record(),
            "first_compilation": first_compilation,
            "first_panel": _panel(first_packet),
            "first_prompt_sha256": _sha256(agent_prompt(first_packet)),
            "second_failure": second.record(),
            "second_compilation": second_compilation,
            "second_panel": _panel(second_packet),
            "second_prompt_sha256": _sha256(agent_prompt(second_packet)),
            "exact_action": exact_action,
            "final_execution": final.record(),
            "checks": checks,
            "preparation_valid": all(checks.values()),
        }
    finally:
        _cleanup_manager(manager, session_path)


def _run_live_trajectory(
    *, prepared_file: Path, repeat: int, root: Path
) -> dict[str, Any]:
    manager, session_path = _manager(
        prepared_file=prepared_file,
        tag=f"chained_recovery_model_r{repeat}_{uuid.uuid4().hex[:12]}",
        root=root,
    )
    try:
        manager.start(replay_prefix=[])
        service = _treatment_service(manager)
        fixed = _execute_intent(manager, INITIAL_REJECTED_TACTIC)
        first_compilation = _compile_occurrence(
            service, fixed, expected_kind="diagnostic"
        )
        first_turn = _run_live_turn(
            manager=manager,
            executed=fixed,
            compiler_item=first_compilation["item"],
            compiler_kind=first_compilation["kind"],
            root=root,
            turn_index=1,
        )
        turns = [first_turn["record"]]
        second_compilation: dict[str, Any] = {}
        if first_turn["executed"].failed_unchanged:
            second_compilation = _compile_occurrence(
                service,
                first_turn["executed"],
                expected_kind=None,
            )
            second_turn = _run_live_turn(
                manager=manager,
                executed=first_turn["executed"],
                compiler_item=second_compilation["item"],
                compiler_kind=second_compilation["kind"],
                root=root,
                turn_index=2,
            )
            turns.append(second_turn["record"])
        provider_valid = bool(
            fixed.failed_unchanged
            and turns
            and all(turn["provider_valid"] for turn in turns)
        )
        route_checks = _route_checks(
            fixed=fixed,
            first_compilation=first_compilation,
            turns=turns,
            second_compilation=second_compilation,
        )
        return {
            "repeat": repeat,
            "fixed_trigger": fixed.record(),
            "first_compilation": first_compilation,
            "turns": turns,
            "second_compilation": second_compilation,
            "provider_valid": provider_valid,
            "route_checks": route_checks,
            "route_complete": all(route_checks.values()),
            "final_history": list(manager.committed_history()),
        }
    finally:
        _cleanup_manager(manager, session_path)


def _run_live_turn(
    *,
    manager: ReplSessionManager,
    executed: ExecutedIntent,
    compiler_item: dict[str, Any],
    compiler_kind: str,
    root: Path,
    turn_index: int,
) -> dict[str, Any]:
    packet = _packet(executed, compiler_item)
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
    next_executed = (
        _execute_intent(manager, tactic)
        if provider_valid
        else executed
    )
    expected_tactic = str(
        compiler_item.get("payload", {}).get("tactic") or ""
    ) if compiler_kind == "action" else ""
    record = {
        "turn_index": turn_index,
        "panel": _panel(packet),
        "prompt_sha256": model_result["prompt_sha256"],
        "prompt_bytes": model_result["prompt_bytes"],
        "compiler_item_kind": compiler_kind,
        "compiler_item": compiler_item,
        "model_tactic": tactic,
        "matches_compiler_action": bool(
            expected_tactic and tactic == expected_tactic
        ),
        "relation_intent_family": relation_bridge_intent_family(tactic),
        "model_returncode": model_result["returncode"],
        "model_error": model_result["error"],
        "duration_ms": model_result["duration_ms"],
        "usage": _normalized_usage(model_result.get("usage", {})),
        "tools_observed": model_result.get("tools_observed", []),
        "provider_event_audit": model_result.get("provider_event_audit", {}),
        "provider_valid": provider_valid,
        "execution": next_executed.record() if provider_valid else {},
    }
    return {"record": record, "executed": next_executed}


def _execute_intent(
    manager: ReplSessionManager, tactic: str
) -> ExecutedIntent:
    if not tactic:
        raise ValueError("cannot execute an empty chained-micro tactic")
    history_before = tuple(manager.committed_history())
    intent = AgentIntent(intent="commit_tactic", payload={"tactic": tactic})
    _snapshot, actions = manager.handle_intent(intent)
    action = next(
        (item for item in actions if item.get("label") == "commit_tactic"),
        None,
    )
    if not isinstance(action, dict):
        raise RuntimeError("chained-micro tactic produced no manager action")
    history_after = tuple(manager.committed_history())
    compiler_input = runtime_compiler_input(manager.read_compiler_input_v2())
    evidence = None
    if (
        action.get("outcome_kind") in {"rejected", "no_progress"}
        and action.get("proof_state_effect") == "unchanged"
    ):
        evidence = rejected_turn_evidence(
            state_ref=compiler_input.snapshot.state_ref,
            action=action,
            intent=intent,
            history=history_after,
        )
    return ExecutedIntent(
        tactic=tactic,
        action=action,
        history_before=history_before,
        history_after=history_after,
        compiler_input_after=compiler_input,
        turn_evidence=evidence,
    )


def _compile_occurrence(
    service: ProofStateCompilerService,
    executed: ExecutedIntent,
    *,
    expected_kind: str | None,
) -> dict[str, Any]:
    if executed.turn_evidence is None:
        raise RuntimeError("compiler recovery requires an unchanged failure")
    result = service.compile_current_state(executed.turn_evidence)
    if isinstance(result, CompilerServiceSkipped):
        record = {
            "kind": "none",
            "item": {},
            "eligible_feature_ids": [],
            "admitted_bytes": 0,
            "timings_ms": result.telemetry.get("timings_ms", {}),
            "native_semantics": result.telemetry.get("native_semantics", {}),
        }
    elif isinstance(result, CompilerServiceResult):
        kind, item = _one_visible_item(result)
        record = {
            "kind": kind,
            "item": item,
            "eligible_feature_ids": list(
                result.telemetry["execution"]["eligible_feature_ids"]
            ),
            "admitted_bytes": result.admission.markdown_bytes,
            "timings_ms": result.telemetry.get("timings_ms", {}),
            "native_semantics": {
                key: result.telemetry.get("native_semantics", {}).get(key)
                for key in (
                    "planned_request_count",
                    "batch_count",
                    "elapsed_ms",
                )
            },
            "certifications": [
                {
                    "accepted": item.accepted,
                    "verification_ref": item.verification_ref,
                    "checked_effect": item.checked_effect.to_dict(),
                }
                for item in result.certifications
            ],
        }
    else:
        raise TypeError("unknown compiler service result")
    if expected_kind is not None and record["kind"] != expected_kind:
        raise RuntimeError(
            f"expected {expected_kind} compiler item, got {record['kind']}"
        )
    return record


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
    visible = [
        (kind, item)
        for kind, items in groups
        for item in items
    ]
    if len(visible) > 1:
        raise RuntimeError("chained recovery exposed more than one compiler item")
    return visible[0] if visible else ("none", {})


def _packet(
    executed: ExecutedIntent, compiler_item: dict[str, Any]
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
        arm="treatment",
        state_ref=executed.compiler_input_after.snapshot.state_ref,
        current_goal_lines=executed.compiler_input_after.snapshot.goal_lines,
        manager_observation=observation,
        compiler_assist=(compiler_item,) if compiler_item else (),
    )


def _panel(packet: TrialPacket) -> dict[str, Any]:
    return json.loads(agent_prompt(packet).split("\n", 1)[1])


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
        raise RuntimeError("missing chained-recovery treatment profile")
    return ProofStateCompilerService.create(runtime=manager, assembly=assembly)


def _cleanup_manager(
    manager: ReplSessionManager, session_path: Path
) -> None:
    manager.close()
    if session_path.name.startswith(".ec_session_chained_recovery_"):
        shutil.rmtree(session_path, ignore_errors=True)
        session_path.with_name(session_path.name + ".cli.lock").unlink(
            missing_ok=True
        )


def _provider_valid(model_result: dict[str, Any], tactic: str) -> bool:
    audit = model_result.get("provider_event_audit")
    audit = audit if isinstance(audit, dict) else {}
    return bool(
        model_result.get("returncode") == 0
        and not model_result.get("error")
        and tactic
        and not model_result.get("tools_observed")
        and audit.get("protocol_valid") is True
        and not audit.get("provider_errors")
        and not audit.get("protocol_unknowns")
        and not audit.get("cardinality_errors")
        and audit.get("reasoning_text_retained") is False
        and audit.get("assistant_text_retained") is False
    )


def _route_checks(
    *,
    fixed: ExecutedIntent,
    first_compilation: dict[str, Any],
    turns: list[dict[str, Any]],
    second_compilation: dict[str, Any],
) -> dict[str, bool]:
    first = turns[0] if turns else {}
    second = turns[1] if len(turns) > 1 else {}
    first_execution = first.get("execution", {})
    second_execution = second.get("execution", {})
    expected_action = str(
        second_compilation.get("item", {}).get("payload", {}).get("tactic")
        or ""
    )
    return {
        "fixed_apply_failed_unchanged": fixed.failed_unchanged,
        "phase_redirect_presented": bool(
            first_compilation.get("kind") == "diagnostic"
            and first_compilation.get("item", {}).get("code")
            == "application_applicability_indeterminate"
            and str(
                first_compilation.get("item", {}).get("primary") or ""
            ).endswith("is not applicable at this proof-state phase.")
        ),
        "first_live_turn_provider_valid": first.get("provider_valid") is True,
        "agent_selected_relation_intent": bool(
            first.get("relation_intent_family") in {"transitivity", "change"}
        ),
        "relation_intent_failed_unchanged": bool(
            first_execution.get("failed_unchanged") is True
        ),
        "relation_owner_selected": bool(
            second_compilation.get("eligible_feature_ids")
            == ["relation_bridge_realization"]
        ),
        "do_you_mean_action_presented": bool(
            second_compilation.get("kind") == "action"
            and second_compilation.get("item", {}).get(
                "correction", {}
            ).get("kind") == "do_you_mean"
        ),
        "second_live_turn_provider_valid": second.get("provider_valid") is True,
        "agent_copied_exact_action": bool(
            expected_action and second.get("model_tactic") == expected_action
        ),
        "bridge_accepted_changed": bool(
            second_execution.get("accepted_changed") is True
        ),
        "two_goals_after_bridge": bool(
            second_execution.get("goal_count_known") is True
            and second_execution.get("goal_count") == 2
        ),
    }


def _normalized_usage(usage: object) -> dict[str, int]:
    source = usage if isinstance(usage, dict) else {}
    values = {
        "input_tokens": int(source.get("input_tokens") or 0),
        "cached_input_tokens": int(source.get("cached_input_tokens") or 0),
        "output_tokens": int(source.get("output_tokens") or 0),
        "reasoning_output_tokens": int(
            source.get("reasoning_output_tokens") or 0
        ),
    }
    values["total_tokens"] = int(
        source.get("total_tokens")
        or values["input_tokens"] + values["output_tokens"]
    )
    return values


def _summarize(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    turns = [
        turn
        for trajectory in trajectories
        for turn in trajectory.get("turns", [])
    ]
    usage_keys = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
    )
    return {
        "trajectories": len(trajectories),
        "provider_valid_trajectories": sum(
            item.get("provider_valid") is True for item in trajectories
        ),
        "complete_routes": sum(
            item.get("route_complete") is True for item in trajectories
        ),
        "live_model_turns": len(turns),
        "model_duration_ms": sum(int(item.get("duration_ms") or 0) for item in turns),
        **{
            key: sum(int(item.get("usage", {}).get(key) or 0) for item in turns)
            for key in usage_keys
        },
    }


def _timeout_result(prompt: str) -> dict[str, Any]:
    return {
        "tactic": "",
        "returncode": -1,
        "duration_ms": MODEL_TIMEOUT_SECONDS * 1000,
        "usage": {},
        "error": "model call exceeded frozen timeout",
        "prompt_sha256": _sha256(prompt),
        "prompt_bytes": len(prompt.encode("utf-8")),
        "tools_observed": [],
        "provider_event_audit": {
            "protocol_valid": False,
            "provider_errors": [{"message": "model timeout"}],
            "protocol_unknowns": [],
            "cardinality_errors": ["model process did not complete"],
        },
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
