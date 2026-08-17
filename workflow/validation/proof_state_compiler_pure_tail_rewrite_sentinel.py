"""Live no-model gate for selected-rewrite pure-tail recovery."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from workflow.proof_management.protocol_repair import AgentIntent
from workflow.proof_management.repl_session import (
    ReplSessionManager,
    session_dir_path,
)
from workflow.proof_state_compiler.configuration import (
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.input_gateway import runtime_compiler_input
from workflow.proof_state_compiler.profile_ids import (
    PURE_TAIL_RECOVERY_AUDIT_PROFILE,
    PURE_TAIL_RECOVERY_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import (
    CompilerServiceResult,
    ProofStateCompilerService,
)
from workflow.validation.proof_state_compiler_turn_evidence import (
    rejected_turn_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "tests/fixtures/native_semantics/pure_tail_local_fact_goal.ec"
LEMMA = "native_pure_tail_local_fact_goal"
REPLAY_PREFIX = ("move=> Ha Hac.",)
REJECTED_TACTIC = "rewrite Ha."
EXPECTED_ACTION = "rewrite Ha in Hac."


def run_pure_tail_rewrite_sentinel(root: Path = ROOT) -> dict[str, Any]:
    """Exercise failure, unique native target, preflight, and commit."""

    token = uuid.uuid4().hex[:12]
    tag = f"pure_tail_rewrite_{token}"
    original_source = root / SOURCE_FILE
    manager = ReplSessionManager(
        file_path=str(original_source),
        lemma_name=LEMMA,
        include_dir="easycrypt-src/theories",
        session_tag=tag,
        node_id=f"validation-{tag}",
        project_root=root,
    )
    session_path = session_dir_path(manager.session_dir, root)
    try:
        manager.start(replay_prefix=list(REPLAY_PREFIX))
        history_before = tuple(manager.committed_history())
        if history_before != REPLAY_PREFIX:
            raise RuntimeError("pure-tail sentinel replay prefix diverged")
        before_input = runtime_compiler_input(manager.read_compiler_input_v2())
        before = before_input.snapshot.state_ref
        rejected_intent = AgentIntent(
            intent="commit_tactic",
            payload={"tactic": REJECTED_TACTIC},
        )
        _snapshot, actions = manager.handle_intent(rejected_intent)
        rejected_action = next(
            (item for item in actions if item.get("label") == "commit_tactic"),
            None,
        )
        if not isinstance(rejected_action, dict):
            raise RuntimeError("pure-tail sentinel observed no rejected action")
        history_after_rejection = tuple(manager.committed_history())
        current_input = runtime_compiler_input(manager.read_compiler_input_v2())
        current = current_input.snapshot.state_ref
        if (
            rejected_action.get("outcome_kind")
            not in {"rejected", "no_progress"}
            or rejected_action.get("proof_state_effect") != "unchanged"
        ):
            raise RuntimeError(
                "authentic rewrite trigger drifted: "
                + json.dumps(rejected_action, sort_keys=True)
            )
        evidence = rejected_turn_evidence(
            state_ref=current,
            action=rejected_action,
            intent=rejected_intent,
            history=history_after_rejection,
        )
        audit = _service(
            manager, PURE_TAIL_RECOVERY_AUDIT_PROFILE
        ).compile_current_state(evidence)
        treatment = _service(
            manager, PURE_TAIL_RECOVERY_TREATMENT_PROFILE
        ).compile_current_state(evidence)
        if not isinstance(audit, CompilerServiceResult) or not isinstance(
            treatment, CompilerServiceResult
        ):
            raise RuntimeError("pure-tail recovery was unexpectedly ineligible")

        candidates = treatment.bundle.candidate_surface.actions
        admitted = treatment.action_surface.actions
        candidate_tactic = (
            "" if len(candidates) != 1 else str(
                candidates[0].payload.to_dict().get("tactic") or ""
            )
        )
        admitted_tactic = (
            "" if len(admitted) != 1 else str(
                admitted[0].payload.to_dict().get("tactic") or ""
            )
        )
        attempted = treatment.bundle.proof_ir.attempted_operation
        descriptor = (
            None if attempted is None
            else attempted.pure_tail_rewrite_descriptor
        )
        history_before_action = tuple(manager.committed_history())
        state_before_action = runtime_compiler_input(
            manager.read_compiler_input_v2()
        ).snapshot.state_ref
        accepted_action = None
        if len(admitted) == 1:
            corrected_intent = AgentIntent(
                intent=admitted[0].intent,
                payload=admitted[0].payload.to_dict(),
            )
            _snapshot, corrected_actions = manager.handle_intent(corrected_intent)
            accepted_action = next(
                (
                    item for item in corrected_actions
                    if item.get("label") == "commit_tactic"
                ),
                None,
            )
        history_after_action = tuple(manager.committed_history())
        state_after_action = runtime_compiler_input(
            manager.read_compiler_input_v2()
        ).snapshot.state_ref
        checks = {
            "rejected_attempt_left_history_unchanged": (
                history_after_rejection == history_before
            ),
            "rejected_attempt_left_material_state_unchanged": (
                current.goal_identity == before.goal_identity
                and current.committed_prefix_identity
                == before.committed_prefix_identity
            ),
            "audit_agent_bytes_zero": audit.admission.markdown_bytes == 0,
            "one_unique_native_target": (
                descriptor is not None
                and descriptor.target_name == "Hac"
                and descriptor.accepted_target_count == 1
                and candidate_tactic == EXPECTED_ACTION
            ),
            "one_recovery_owner": (
                treatment.bundle.analyzed_state.recovery_ownership.status
                == "owned"
                and treatment.bundle.analyzed_state.recovery_ownership
                .claimant_feature_ids == ("pure_tail_recovery",)
            ),
            "standard_certification_accepted": (
                len(treatment.certifications) == 1
                and treatment.certifications[0].accepted
            ),
            "one_action_admitted": (
                len(admitted) == 1 and admitted_tactic == EXPECTED_ACTION
            ),
            "admitted_action_changes_state": (
                isinstance(accepted_action, dict)
                and history_after_action
                == history_before_action + (EXPECTED_ACTION,)
                and state_after_action.committed_prefix_identity
                != state_before_action.committed_prefix_identity
                and state_after_action.goal_identity
                != state_before_action.goal_identity
            ),
        }
        return {
            "schema_version": 1,
            "kind": "proof_state_compiler_pure_tail_rewrite_sentinel",
            "source_file": SOURCE_FILE,
            "lemma": LEMMA,
            "rejected_tactic": REJECTED_TACTIC,
            "expected_action": EXPECTED_ACTION,
            "candidate_tactic": candidate_tactic,
            "admitted_tactic": admitted_tactic,
            "target_name": "" if descriptor is None else descriptor.target_name,
            "candidate_count": len(candidates),
            "certification_count": len(treatment.certifications),
            "certifications": [
                {
                    "accepted": item.accepted,
                    "checked_effect": item.checked_effect.to_dict(),
                    "verification_ref": item.verification_ref,
                }
                for item in treatment.certifications
            ],
            "audit_agent_bytes": audit.admission.markdown_bytes,
            "treatment_agent_bytes": treatment.admission.markdown_bytes,
            "history_added_by_action": list(
                history_after_action[len(history_before_action):]
            ),
            "manager_action": accepted_action,
            "manager_outcome": evidence.outcome_kind,
            "manager_error": evidence.structured_error,
            "execution": treatment.telemetry["execution"],
            "native_semantics": treatment.telemetry["native_semantics"],
            "checks": checks,
            "passed": all(checks.values()),
        }
    finally:
        manager.close()
        if session_path.name.startswith(".ec_session_pure_tail_rewrite_"):
            shutil.rmtree(session_path, ignore_errors=True)
            for suffix in (".cli.lock", ".pre_restart.txt"):
                session_path.with_name(
                    session_path.name + suffix
                ).unlink(missing_ok=True)


def _service(
    manager: ReplSessionManager,
    profile_id: str,
) -> ProofStateCompilerService:
    assembly = compiler_assembly_for_profile(profile_id)
    if assembly is None:
        raise RuntimeError(f"missing compiler profile {profile_id}")
    return ProofStateCompilerService.create(runtime=manager, assembly=assembly)


def main() -> int:
    result = run_pure_tail_rewrite_sentinel()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
