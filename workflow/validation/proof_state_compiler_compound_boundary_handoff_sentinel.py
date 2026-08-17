"""Fresh real-state sentinel for state-changing compound-boundary handoff.

The historical V3 report retained the failed occurrences but not enough session
history to replay their exact ``StateRef``.  This sentinel therefore rebuilds
one nearby, independently reproducible ``step1`` state from the same
proof-stripped source.  It injects the two historical failure shapes and
records what the current all-candidate compiler actually produces.  The result
is fresh reconstruction evidence, never an exact replay of the V3 states.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from core.easycrypt.proof_state_compiler.backend import action_surface_payload
from core.easycrypt.proof_state_compiler.contracts import (
    NativeSelectedApplicationBindingSetDescriptor,
    NativeTacticPrefixDiagnosticDescriptor,
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
    ALL_CANDIDATE_AUDIT_PROFILE,
    ALL_CANDIDATE_TREATMENT_PROFILE,
)
from workflow.proof_state_compiler.service import (
    CompilerServiceResult,
    ProofStateCompilerService,
)
from workflow.validation.proof_state_compiler_turn_evidence import (
    rejected_turn_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILE = "eval/examples/ChaChaPoly/chacha_poly.ec"
LEMMA = "step1"
REPLAY_PREFIX = ("congr.", "byequiv=> //.")
EXPECTED_CCP_MARKDOWN = """## Compiler diagnostic

Your compound tactic failed and was rolled back. `symmetry.` was not committed.

EasyCrypt can execute the first stage:

  symmetry.

That stage changes the goal. The next stage fails:

  apply OpCCinit.CCP_OCCP.

EasyCrypt reports:

  cannot infer module arguments

`OpCCinit.CCP_OCCP` requires two module arguments, in this order:

1. `I` with module type `OpCCinit.Init`
2. `A` with module type `OpCCinit.Adv`

Supplying these arguments only instantiates the theorem.

For the module candidates checked here, no completed instance makes this `apply` succeed in the temporary goal produced by `symmetry.`

`apply H` can succeed only when the conclusion of the instantiated `H` matches—or can be unified with—the entire goal in that temporary state.

If you want to continue from the goal produced by that step, submit `symmetry.` separately. You may instead replace the failing suffix and resubmit the compound. The compiler does not choose between these options."""


@dataclass(frozen=True)
class FreshCase:
    case_id: str
    historical_goal_identity: str
    historical_failure_event_id: str
    rejected_tactic: str
    expected_suffix_handoff: bool


CASES = (
    FreshCase(
        case_id="step1_symmetry_ccp_application",
        historical_goal_identity=(
            "f71da036b79e9d79f963c3bc41defef9ddbf79ae"
        ),
        historical_failure_event_id=(
            "158973e2-e9a0-408d-b696-476d7056ffd9"
        ),
        rejected_tactic="symmetry; apply OpCCinit.CCP_OCCP.",
        expected_suffix_handoff=True,
    ),
    FreshCase(
        case_id="step1_symmetry_ro_conseq",
        historical_goal_identity=(
            "a1f4f9b6cd7b5e275f97a01b88946a10a1451366"
        ),
        historical_failure_event_id=(
            "37f00c4d-c549-40b5-a0b5-b658cf7e726e"
        ),
        rejected_tactic="symmetry; conseq (RO_FinRO_D G2).",
        expected_suffix_handoff=True,
    ),
)


def run(root: Path = ROOT) -> dict[str, Any]:
    rows = [_run_case(case, root=root) for case in CASES]
    return {
        "schema_version": 1,
        "kind": "proof_state_compiler_compound_boundary_handoff_sentinel",
        "state_contract": "fresh_reconstruction_not_historical_exact_replay",
        "source_file": SOURCE_FILE,
        "lemma": LEMMA,
        "replay_prefix": list(REPLAY_PREFIX),
        "rows": rows,
        "valid": all(row["valid"] for row in rows),
    }


def _run_case(case: FreshCase, *, root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="shannon_compound_handoff_", dir="/private/tmp"
    ) as source_dir:
        source = root / SOURCE_FILE
        prepared = prepare_eval_source(
            source_file=source,
            target_lemma=LEMMA,
            output_dir=Path(source_dir),
            copy_root=source.parent,
            strip_proofs=True,
        )
        tag = "compound_handoff_" + uuid.uuid4().hex[:12]
        manager = ReplSessionManager(
            file_path=str(prepared.isolated_file),
            lemma_name=LEMMA,
            include_dir="easycrypt-src/theories",
            session_tag=tag,
            node_id="sentinel-" + tag,
            project_root=root,
        )
        session_path = session_dir_path(manager.session_dir, root)
        try:
            manager.start(replay_prefix=list(REPLAY_PREFIX))
            history = tuple(manager.committed_history())
            intent = AgentIntent(
                intent="commit_tactic",
                payload={"tactic": case.rejected_tactic},
            )
            _snapshot, actions = manager.handle_intent(intent)
            action = next(
                (
                    item for item in actions
                    if item.get("label") == "commit_tactic"
                ),
                None,
            )
            if not isinstance(action, dict):
                raise RuntimeError("fixed trigger produced no manager action")
            compiler_input = runtime_compiler_input(
                manager.read_compiler_input_v2()
            )
            turn = rejected_turn_evidence(
                state_ref=compiler_input.snapshot.state_ref,
                action=action,
                intent=intent,
                history=history,
            )
            audit = _compile(manager, ALL_CANDIDATE_AUDIT_PROFILE, turn)
            treatment = _compile(
                manager, ALL_CANDIDATE_TREATMENT_PROFILE, turn
            )
            handoff = treatment.bundle.proof_ir.attempted_operation
            handoff_payload = (
                {}
                if handoff is None or handoff.recovery_handoff is None
                else handoff.recovery_handoff.to_payload()
            )
            native_prefix_descriptors = [
                observation.descriptor.to_payload()
                for observation in (
                    treatment.bundle.proof_ir.native_semantic_observations
                )
                if isinstance(
                    observation.descriptor,
                    NativeTacticPrefixDiagnosticDescriptor,
                )
            ]
            native_binding_sets = [
                observation.descriptor.to_payload()
                for observation in (
                    treatment.bundle.proof_ir.native_semantic_observations
                )
                if isinstance(
                    observation.descriptor,
                    NativeSelectedApplicationBindingSetDescriptor,
                )
            ]
            audit_payload = action_surface_payload(audit.action_surface)
            treatment_payload = action_surface_payload(
                treatment.action_surface
            )
            history_unchanged = tuple(manager.committed_history()) == history
            native_prefix = (
                native_prefix_descriptors[0]
                if len(native_prefix_descriptors) == 1
                else {}
            )
            native_prefix_is_state_changing_symmetry = bool(
                native_prefix.get("accepted_prefixes") == ["symmetry."]
                and native_prefix.get("prefix_effects")
                == ["accepted_changed"]
            )
            handoff_present = bool(handoff_payload)
            checks = {
                "replay_prefix_exact": history == REPLAY_PREFIX,
                "failure_unchanged": (
                    turn.proof_state_effect == "unchanged"
                ),
                "audit_zero_bytes": (
                    audit.action_surface.empty
                    and audit.admission.markdown_bytes == 0
                ),
                "same_state": (
                    audit.bundle.state_ref
                    == treatment.bundle.state_ref
                    == compiler_input.snapshot.state_ref
                ),
                "native_prefix_is_state_changing_symmetry": (
                    native_prefix_is_state_changing_symmetry
                ),
                "suffix_handoff_matches_supported_family": (
                    handoff_present == case.expected_suffix_handoff
                ),
                "handoff_preserves_state_changing_prefix": (
                    not case.expected_suffix_handoff
                    or (
                        handoff_payload.get("accepted_prefix_tactic")
                        == "symmetry."
                        and handoff_payload.get("accepted_prefix_effect")
                        == "accepted_changed"
                    )
                ),
                "history_unchanged": history_unchanged,
                "at_most_one_visible_item": sum(
                    len(treatment_payload[key])
                    for key in (
                        "resources", "bindings", "actions", "diagnostics"
                    )
                ) <= 1,
                "shape_first_binding_policy_is_sound": (
                    (
                        len(native_binding_sets) == 1
                        and native_binding_sets[0].get(
                            "population_complete"
                        ) is True
                        and native_binding_sets[0].get(
                            "typed_binding_count", 0
                        ) > 0
                        and native_binding_sets[0].get(
                            "checked_completion_count"
                        ) == 0
                        and not treatment_payload["actions"]
                        and len(treatment_payload["diagnostics"]) == 1
                        and treatment.action_surface.diagnostics[0].code
                        == "selected_application_not_applicable"
                        and treatment.admission.presentation.text
                        == EXPECTED_CCP_MARKDOWN
                    )
                    if case.case_id == "step1_symmetry_ccp_application"
                    else (
                        not native_binding_sets
                        and not treatment_payload["actions"]
                        and len(treatment_payload["diagnostics"]) == 1
                        and treatment.action_surface.diagnostics[0].code
                        == "selected_application_argument_layout"
                        and "1. a proof of" in treatment.admission.presentation.text
                        and "1. formula `G2`" in treatment.admission.presentation.text
                        and "preserved your concrete argument"
                        in treatment.admission.presentation.text
                        and "did not reinterpret it"
                        in treatment.admission.presentation.text
                    )
                ),
            }
            return {
                "case_id": case.case_id,
                "historical_provenance": {
                    "goal_identity": case.historical_goal_identity,
                    "failure_event_id": case.historical_failure_event_id,
                    "exact_state_replayed": False,
                },
                "fresh_state": {
                    "state_ref": treatment.bundle.state_ref.identity_payload(),
                    "goal_lines": list(
                        treatment.bundle.projected_state.goal_lines
                    ),
                },
                "failure": {
                    "tactic": case.rejected_tactic,
                    "outcome_kind": turn.outcome_kind,
                    "proof_state_effect": turn.proof_state_effect,
                    "structured_error": turn.structured_error,
                },
                "attempted_operation": (
                    {}
                    if treatment.bundle.proof_ir.attempted_operation is None
                    else _attempt_payload(
                        treatment.bundle.proof_ir.attempted_operation
                    )
                ),
                "recovery_handoff": handoff_payload,
                "native_prefix_descriptors": native_prefix_descriptors,
                "native_selected_application_binding_sets": (
                    native_binding_sets
                ),
                "native_observations": [
                    {
                        "producer_id": observation.producer_id,
                        "query_kind": observation.query_kind,
                        "status": observation.status,
                        "structured_error": (
                            None
                            if observation.structured_error is None
                            else observation.structured_error.to_dict()
                        ),
                    }
                    for observation in (
                        treatment.bundle.proof_ir.native_semantic_observations
                    )
                ],
                "native_planning": (
                    []
                    if treatment.bundle.proof_ir.native_semantic_planning_report
                    is None
                    else [
                        {
                            "stage": stage.stage,
                            "decisions": [
                                decision.to_dict()
                                for decision in stage.decisions
                            ],
                        }
                        for stage in treatment.bundle.proof_ir
                        .native_semantic_planning_report.stages
                    ]
                ),
                "ownership": (
                    _ownership_payload(
                        treatment.bundle.analyzed_state.recovery_ownership
                    )
                ),
                "audit": {
                    "surface": audit_payload,
                    "agent_bytes": audit.admission.markdown_bytes,
                },
                "treatment": {
                    "surface": treatment_payload,
                    "agent_bytes": treatment.admission.markdown_bytes,
                    "markdown": treatment.admission.presentation.text,
                    "certifications": [
                        {
                            "candidate_id": item.candidate_id,
                            "accepted": item.accepted,
                            "policy": item.policy,
                            "intent": item.intent,
                            "verification_ref": item.verification_ref,
                            "checked_effect": item.checked_effect.to_dict(),
                        }
                        for item in treatment.certifications
                    ],
                },
                "checks": checks,
                "valid": all(checks.values()),
            }
        finally:
            manager.close()
            shutil.rmtree(session_path, ignore_errors=True)
            session_path.with_name(session_path.name + ".cli.lock").unlink(
                missing_ok=True
            )


def _attempt_payload(attempt) -> dict[str, Any]:
    return {
        "attempt_id": attempt.attempt_id,
        "operation_family": attempt.operation_family,
        "exact_resource": attempt.exact_resource,
        "rejected_tactic": attempt.rejected_tactic,
        "attempt_outcome_kind": attempt.attempt_outcome_kind,
        "native_diagnostic_status": attempt.native_diagnostic_status,
        "native_failure_kind": attempt.native_failure_kind,
        "native_error_message": attempt.native_error_message,
        "parsed_arguments": list(attempt.parsed_arguments),
        "recovery_handoff": (
            {}
            if attempt.recovery_handoff is None
            else attempt.recovery_handoff.to_payload()
        ),
    }


def _ownership_payload(ownership) -> dict[str, Any]:
    witness = ownership.preservation_witness
    return {
        "status": ownership.status,
        "recovery_key": ownership.recovery_key,
        "owner_feature_id": ownership.owner_feature_id,
        "claimant_feature_ids": list(ownership.claimant_feature_ids),
        "operation_family": ownership.operation_family,
        "selected_resource": ownership.selected_resource,
        "resource_match_kind": ownership.resource_match_kind,
        "allowed_output_kinds": list(ownership.allowed_output_kinds),
        "preservation_witness_id": (
            "" if witness is None else witness.witness_id
        ),
        "audit_reason": ownership.audit_reason,
    }


def _compile(
    manager: ReplSessionManager,
    profile_id: str,
    turn,
) -> CompilerServiceResult:
    assembly = compiler_assembly_for_profile(profile_id)
    if assembly is None:
        raise RuntimeError(f"missing profile {profile_id}")
    result = ProofStateCompilerService.create(
        runtime=manager,
        assembly=assembly,
    ).compile_current_state(turn)
    if not isinstance(result, CompilerServiceResult):
        raise RuntimeError(f"compiler skipped fixed trigger under {profile_id}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
