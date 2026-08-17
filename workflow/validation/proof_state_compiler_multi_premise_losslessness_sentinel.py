"""Live no-model sentinel for bounded multi-premise losslessness calls."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from core.easycrypt.proof_state_compiler.contracts import (
    NativeProofTermElaborationQuery,
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
    OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import ProofStateCompilerService
from workflow.validation.proof_state_compiler_turn_evidence import (
    rejected_turn_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "eval/examples/ChaChaPoly/ske.ec"
LEMMA = "A_ll_distinct_reconstruction"
REPLAY_PREFIX = ("proc.",)
RESOURCE = "A_ll"
REJECTED_TACTIC = f"call ({RESOURCE} _ _)."
APPLICATION_TERM = f"{RESOURCE} (<: O) _ _"
EXPECTED_TACTIC = f"call ({APPLICATION_TERM})."
FIXTURE = """
  local module A_ll_driver (O : CCA_Oracles) = {
    proc main() = {
      var b;
      b <@ A(O).main();
      return b;
    }
  }.

  local lemma A_ll_distinct_reconstruction
    (O <: CCA_Oracles{-A}) :
    islossless A_ll_driver(O).main.
  proof.
    proc.
  qed.

"""
INSERTION_MARKER = "  equiv eqv_CCA_UFCMA"


def run_multi_premise_losslessness_sentinel(
    root: Path = ROOT,
) -> dict[str, Any]:
    """Check one rejected call through the complete B2 recovery path."""

    token = uuid.uuid4().hex[:12]
    tag = f"b2_multi_losslessness_{token}"
    source_input = root / f".b2_multi_losslessness_input_{token}"
    source_output = root / f".b2_multi_losslessness_sources_{token}"
    source_root = root / "eval/examples/ChaChaPoly"
    shutil.copytree(
        source_root,
        source_input,
        ignore=shutil.ignore_patterns("*.eco", "__pycache__"),
    )
    patched_source = source_input / Path(SOURCE_FILE).name
    raw = patched_source.read_text(encoding="utf-8")
    if raw.count(INSERTION_MARKER) != 1:
        raise RuntimeError("multi-premise sentinel insertion marker drifted")
    patched_source.write_text(
        raw.replace(INSERTION_MARKER, FIXTURE + INSERTION_MARKER),
        encoding="utf-8",
    )
    prepared = prepare_eval_source(
        source_file=patched_source,
        target_lemma=LEMMA,
        output_dir=source_output,
        copy_root=source_input,
        strip_proofs=True,
    )
    manager = ReplSessionManager(
        file_path=str(prepared.isolated_file),
        lemma_name=LEMMA,
        include_dir="easycrypt-src/theories",
        session_tag=tag,
        node_id=f"validation-{tag}",
        project_root=root,
    )
    session_path = session_dir_path(manager.session_dir, root)
    try:
        _start_snapshot, start_actions = manager.start(
            replay_prefix=list(REPLAY_PREFIX)
        )
        history_before = tuple(manager.committed_history())
        if history_before != REPLAY_PREFIX:
            raise RuntimeError(
                "multi-premise sentinel missed the call boundary: "
                f"history={history_before!r}, actions={start_actions!r}"
            )
        intent = AgentIntent(
            intent="commit_tactic",
            payload={"tactic": REJECTED_TACTIC},
        )
        _snapshot, manager_actions = manager.handle_intent(intent)
        manager_action = next(
            (
                item
                for item in manager_actions
                if item.get("label") == "commit_tactic"
            ),
            None,
        )
        if not isinstance(manager_action, dict):
            raise RuntimeError("multi-premise sentinel observed no failed call")
        if tuple(manager.committed_history()) != history_before:
            raise RuntimeError("failed old-form call changed history")
        compiler_input = runtime_compiler_input(
            manager.read_compiler_input_v2()
        )
        evidence = rejected_turn_evidence(
            state_ref=compiler_input.snapshot.state_ref,
            action=manager_action,
            intent=intent,
            history=history_before,
        )
        assembly = compiler_assembly_for_profile(
            OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
        )
        if assembly is None:
            raise RuntimeError("missing operation-binding treatment profile")
        service_result = ProofStateCompilerService.create(
            runtime=manager,
            assembly=assembly,
        ).compile_current_state(evidence)

        compiler_actions = service_result.action_surface.actions
        action_tactic = (
            ""
            if len(compiler_actions) != 1
            else str(
                compiler_actions[0].payload.to_dict().get("tactic") or ""
            )
        )
        observations = tuple(
            item
            for item in service_result.bundle.proof_ir.native_semantic_observations
            if isinstance(item.query, NativeProofTermElaborationQuery)
            and item.query.application_term == APPLICATION_TERM
        )
        descriptor = (
            None
            if len(observations) != 1
            else observations[0].descriptor
        )
        arguments = () if descriptor is None else descriptor.arguments
        residuals = (
            () if descriptor is None else descriptor.residual_proof_premises
        )
        head = None if descriptor is None else descriptor.resolved_head
        conclusion = None if descriptor is None else descriptor.result
        certifications = service_result.certifications
        history_after = tuple(manager.committed_history())
        try_reports = _try_reports(session_path)
        residual_procedures = tuple(
            item.formula.procedure
            for item in residuals
        )
        passed = bool(
            evidence.proof_state_effect == "unchanged"
            and evidence.outcome_kind in {"rejected", "no_progress"}
            and descriptor is not None
            and observations[0].status == "accepted"
            and head is not None
            and head.kind == "global"
            and head.identity.endswith("." + RESOURCE)
            and [item.kind for item in arguments]
            == ["module", "proof", "proof"]
            and [item.hole for item in arguments]
            == [False, True, True]
            and descriptor.explicit_hole_count == 2
            and len(residuals) == 2
            and all(item.formula.lossless is True for item in residuals)
            and residual_procedures == ("O./enc", "O./dec")
            and conclusion is not None
            and conclusion.lossless is True
            and conclusion.procedure == "A(O)./main"
            and action_tactic == EXPECTED_TACTIC
            and len(certifications) == 1
            and certifications[0].accepted is True
            and service_result.bundle.analyzed_state.recovery_ownership.status
            == "owned"
            and service_result.bundle.analyzed_state.recovery_ownership.claimant_feature_ids
            == ("operation_binding_repair",)
            and history_after == history_before
        )
        return {
            "schema_version": 1,
            "kind": (
                "proof_state_compiler_multi_premise_losslessness_sentinel"
            ),
            "rejected_tactic": REJECTED_TACTIC,
            "manager_outcome": evidence.outcome_kind,
            "manager_state_effect": evidence.proof_state_effect,
            "manager_structured_error": evidence.structured_error,
            "try_reports": try_reports,
            "application_term": APPLICATION_TERM,
            "expected_tactic": EXPECTED_TACTIC,
            "compiler_action": action_tactic,
            "native_status": (
                "missing" if not observations else observations[0].status
            ),
            "resolved_head": None if head is None else head.identity,
            "argument_kinds": [item.kind for item in arguments],
            "argument_holes": [item.hole for item in arguments],
            "explicit_hole_count": (
                None if descriptor is None else descriptor.explicit_hole_count
            ),
            "residual_procedures": list(residual_procedures),
            "residual_order_distinct": bool(
                residual_procedures == ("O./enc", "O./dec")
            ),
            "result_procedure": (
                "" if conclusion is None else conclusion.procedure
            ),
            "certification_count": len(certifications),
            "certification_accepted": bool(
                len(certifications) == 1 and certifications[0].accepted
            ),
            "ownership": (
                service_result.bundle.analyzed_state.recovery_ownership.status
            ),
            "ownership_claimants": list(
                service_result.bundle.analyzed_state.recovery_ownership.claimant_feature_ids
            ),
            "compiler_timings_ms": service_result.telemetry["timings_ms"],
            "native_request_count": service_result.telemetry[
                "native_semantics"
            ]["planned_request_count"],
            "admitted_action_count": service_result.telemetry[
                "admission"
            ]["admitted"],
            "history_unchanged": history_after == history_before,
            "passed": passed,
        }
    finally:
        manager.close()
        if session_path.name.startswith(".ec_session_b2_multi_losslessness_"):
            shutil.rmtree(session_path, ignore_errors=True)
            for suffix in (".cli.lock", ".pre_restart.txt"):
                session_path.with_name(
                    session_path.name + suffix
                ).unlink(missing_ok=True)
        if source_input.name.startswith(".b2_multi_losslessness_input_"):
            shutil.rmtree(source_input, ignore_errors=True)
        if source_output.name.startswith(".b2_multi_losslessness_sources_"):
            shutil.rmtree(source_output, ignore_errors=True)


def main() -> int:
    result = run_multi_premise_losslessness_sentinel()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


def _try_reports(session_path: Path) -> list[str]:
    reports: list[str] = []
    events_path = session_path / "events.jsonl"
    for line in events_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "tactic.try_result":
            reports.append(str(event.get("payload", {}).get("report") or ""))
    return reports


if __name__ == "__main__":
    raise SystemExit(main())
