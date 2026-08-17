"""Live no-model gate for applicability-before-argument-repair ordering."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from core.easycrypt.proof_state_compiler.contracts import (
    APPLICATION_APPLICABLE,
    APPLICATION_INDETERMINATE,
)
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
    OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
    OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import ProofStateCompilerService
from workflow.validation.proof_state_compiler_turn_evidence import (
    rejected_turn_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "eval/examples/ChaChaPoly/chacha_poly.ec"
LEMMA = "step2_1"
REJECTED_TACTIC = "apply CCA_UFCMA.CCA_CPA_UFCMA."
POST_LER_PREFIX = (
    "apply (ler_trans Pr[CCA_game(A, RealOrcls(StLSke(St))).main() "
    "@ &m : res]); first last.",
)
EXPECTED_ACTION = (
    "apply (CCA_UFCMA.CCA_CPA_UFCMA St _ _ A A_ll &m)."
)


def run_application_applicability_sentinel(
    root: Path = ROOT,
) -> dict[str, Any]:
    """Compare one selected theorem at initial and committed-route states."""

    token = uuid.uuid4().hex[:12]
    source_output = root / f".application_applicability_sources_{token}"
    original_source = root / SOURCE_FILE
    prepared = prepare_eval_source(
        source_file=original_source,
        target_lemma=LEMMA,
        output_dir=source_output,
        copy_root=original_source.parent,
        strip_proofs=True,
    )
    try:
        initial = _probe_state(
            root=root,
            isolated_file=prepared.isolated_file,
            token=token,
            label="initial",
            replay_prefix=(),
        )
        post_ler = _probe_state(
            root=root,
            isolated_file=prepared.isolated_file,
            token=token,
            label="post_ler_trans",
            replay_prefix=POST_LER_PREFIX,
        )
        initial_passed = bool(
            initial["history_unchanged"]
            and initial["audit_agent_bytes"] == 0
            and initial["action_count"] == 0
            and initial["diagnostic_count"] == 1
            and initial["diagnostic_code"]
            == "application_applicability_indeterminate"
            and initial["diagnostic_placeholder_shape"] == ""
            and initial["diagnostic_primary"] == (
                "CCA_CPA_UFCMA is not applicable at this proof-state phase."
            )
            and initial["diagnostic_notes"] == [
                "EasyCrypt boundary mismatch: current uses "
                "OChaChaPoly(IFinRO); theorem uses StLSke(St).",
            ]
            and initial["applicability_status"]
            == APPLICATION_INDETERMINATE
            and initial["population_complete"] is False
        )
        post_ler_passed = bool(
            post_ler["history_unchanged"]
            and post_ler["audit_agent_bytes"] == 0
            and post_ler["action_count"] == 1
            and post_ler["diagnostic_count"] == 0
            and post_ler["action_tactic"] == EXPECTED_ACTION
            and post_ler["applicability_status"] == APPLICATION_APPLICABLE
            and post_ler["population_complete"] is True
            and post_ler["unique_checked_completion"] is True
            and post_ler["certification_accepted"] is True
        )
        return {
            "schema_version": 1,
            "kind": "proof_state_compiler_application_applicability_sentinel",
            "selected_theorem": "CCA_UFCMA.CCA_CPA_UFCMA",
            "rejected_tactic": REJECTED_TACTIC,
            "initial": initial,
            "post_ler_trans": post_ler,
            "initial_passed": initial_passed,
            "post_ler_trans_passed": post_ler_passed,
            "passed": initial_passed and post_ler_passed,
        }
    finally:
        if source_output.name.startswith(".application_applicability_sources_"):
            shutil.rmtree(source_output, ignore_errors=True)


def _probe_state(
    *,
    root: Path,
    isolated_file: Path,
    token: str,
    label: str,
    replay_prefix: tuple[str, ...],
) -> dict[str, Any]:
    tag = f"application_applicability_{label}_{token}"
    manager = ReplSessionManager(
        file_path=str(isolated_file),
        lemma_name=LEMMA,
        include_dir="easycrypt-src/theories",
        session_tag=tag,
        node_id=f"validation-{tag}",
        project_root=root,
    )
    session_path = session_dir_path(manager.session_dir, root)
    try:
        manager.start(replay_prefix=list(replay_prefix))
        history_before = tuple(manager.committed_history())
        if history_before != replay_prefix:
            raise RuntimeError(f"{label} applicability prefix diverged")
        audit_service = _service(
            manager, OPERATION_BINDING_REPAIR_AUDIT_PROFILE
        )
        treatment_service = _service(
            manager, OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
        )
        intent = AgentIntent(
            intent="commit_tactic",
            payload={"tactic": REJECTED_TACTIC},
        )
        _snapshot, actions = manager.handle_intent(intent)
        action = next(
            (item for item in actions if item.get("label") == "commit_tactic"),
            None,
        )
        if not isinstance(action, dict):
            raise RuntimeError(f"{label} applicability observed no failure")
        if tuple(manager.committed_history()) != history_before:
            raise RuntimeError(f"{label} rejected tactic changed history")
        compiler_input = runtime_compiler_input(
            manager.read_compiler_input_v2()
        )
        evidence = rejected_turn_evidence(
            state_ref=compiler_input.snapshot.state_ref,
            action=action,
            intent=intent,
            history=history_before,
        )
        audit = audit_service.compile_current_state(evidence)
        treatment = treatment_service.compile_current_state(evidence)
        assessments = (
            treatment.bundle.analyzed_state.application_applicabilities
        )
        if len(assessments) != 1:
            raise RuntimeError(
                f"{label} applicability assessment cardinality drifted"
            )
        assessment = assessments[0]
        actions = treatment.bundle.candidate_surface.actions
        diagnostics = treatment.bundle.candidate_surface.diagnostics
        diagnostic = None if not diagnostics else diagnostics[0].diagnostic
        candidate_action = None if not actions else actions[0]
        certifications = treatment.certifications
        return {
            "state": treatment.bundle.state_ref.identity_payload(),
            "replay_prefix": list(replay_prefix),
            "manager_outcome": evidence.outcome_kind,
            "native_failure": evidence.structured_error,
            "applicability_status": assessment.status,
            "population_complete": assessment.population_complete,
            "unique_checked_completion": (
                assessment.unique_checked_completion
            ),
            "accepted_request_count": len(assessment.accepted_request_ids),
            "nonmatching_request_count": len(
                assessment.nonmatching_request_ids
            ),
            "action_count": len(actions),
            "action_tactic": (
                ""
                if candidate_action is None
                else str(
                    candidate_action.payload.to_dict().get("tactic") or ""
                )
            ),
            "diagnostic_count": len(diagnostics),
            "diagnostic_code": "" if diagnostic is None else diagnostic.code,
            "diagnostic_placeholder_shape": (
                "" if diagnostic is None else diagnostic.placeholder_shape
            ),
            "diagnostic_primary": (
                "" if diagnostic is None else diagnostic.primary
            ),
            "diagnostic_notes": (
                [] if diagnostic is None else list(diagnostic.notes)
            ),
            "audit_agent_bytes": audit.admission.markdown_bytes,
            "treatment_agent_bytes": treatment.admission.markdown_bytes,
            "certification_accepted": bool(
                len(certifications) == 1 and certifications[0].accepted
            ),
            "certification_count": len(certifications),
            "certifications": [
                {
                    "accepted": item.accepted,
                    "policy": item.policy,
                    "checked_effect": item.checked_effect.to_dict(),
                }
                for item in certifications
            ],
            "admission": {
                "markdown_bytes": treatment.admission.markdown_bytes,
                "decisions": [
                    {
                        "candidate_id": item.candidate_id,
                        "admitted": item.admitted,
                        "reason": item.reason,
                    }
                    for item in treatment.admission.decisions
                ],
                "presented_delivery_ids": list(
                    treatment.admission.presented_delivery_ids
                ),
            },
            "history_unchanged": (
                tuple(manager.committed_history()) == history_before
            ),
        }
    finally:
        manager.close()
        if session_path.name.startswith(".ec_session_application_applicability_"):
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
    result = run_application_applicability_sentinel()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
