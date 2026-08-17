from __future__ import annotations

from dataclasses import replace

import pytest

from core.easycrypt.proof_state_compiler.contracts import EvidenceRef
from core.easycrypt.proof_state_compiler.features.accepted_contract_retention import (
    ACCEPTED_CONTRACT_RETENTION_FEATURE_ID,
    AcceptedContractRetention,
    accepted_contract_retention_feature_spec,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness import (
    PROGRAM_OPERATION_READINESS_FEATURE_ID,
    ProgramOperationReadiness,
    program_operation_readiness_feature_spec,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
    OperationBindingRepair,
    operation_binding_repair_feature_spec,
)
from core.easycrypt.proof_state_compiler.syntax.attempted_operation import (
    bare_operation_resource,
)


def _evidence() -> tuple[EvidenceRef, ...]:
    return (EvidenceRef(
        evidence_id="mechanical-contract:evidence",
        source_kind="projected_goal",
        source_ref="compiler_inputs/current.json#goal_lines",
        source_sha256="a" * 64,
    ),)


def test_operation_readiness_is_intrinsic_and_blocker_exact() -> None:
    blocked = ProgramOperationReadiness(
        operation="call",
        status="blocked",
        tactic_active_boundary="if:left:3",
        blocker="the tactic-active tail is an if statement, not a call",
        evidence_refs=_evidence(),
    )
    legal = ProgramOperationReadiness(
        operation="rnd",
        status="legal",
        tactic_active_boundary="sample:right:2",
        evidence_refs=_evidence(),
    )

    assert blocked.blocker
    assert not legal.blocker
    spec = program_operation_readiness_feature_spec()
    assert spec.feature_id == PROGRAM_OPERATION_READINESS_FEATURE_ID
    assert spec.gate.evidence_ledger_ids == ("M04",)
    assert spec.strategy_contracts[0].strategy_class == "intrinsic"
    with pytest.raises(ValueError, match="blocked readiness requires"):
        replace(blocked, blocker="")
    with pytest.raises(ValueError, match="legal readiness cannot"):
        replace(legal, blocker="unexpected")


def test_contract_retention_carries_only_old_missing_conjuncts() -> None:
    result = AcceptedContractRetention(
        anchor_id="accepted-contract:7",
        anchor_source_event_id="ter-7",
        anchor_prefix_identity="b" * 64,
        current_prefix_identity="b" * 64,
        boundary_identity="while:left:4",
        original_conjuncts=("={x}", "0 <= i"),
        missing_conjuncts=("={x}",),
        evidence_refs=_evidence(),
    )

    assert result.missing_conjuncts == ("={x}",)
    spec = accepted_contract_retention_feature_spec()
    assert spec.feature_id == ACCEPTED_CONTRACT_RETENTION_FEATURE_ID
    assert spec.gate.evidence_ledger_ids == ("M09",)
    assert spec.strategy_contracts[0].strategy_class == "commitment_relative"
    with pytest.raises(ValueError, match="not present in accepted contract"):
        replace(result, missing_conjuncts=("new strengthening fact",))
    with pytest.raises(ValueError, match="missing-conjunct result must abstain"):
        replace(result, missing_conjuncts=())
    with pytest.raises(ValueError, match="stale for current prefix"):
        replace(result, current_prefix_identity="c" * 64)


@pytest.mark.parametrize("failure_class", ["B1", "B2", "B4"])
def test_operation_binding_repair_preserves_operation_and_resource(
    failure_class: str,
) -> None:
    result = OperationBindingRepair(
        attempt_id="attempt:7",
        occurrence_identity="occurrence:7",
        recovery_key="recovery:7",
        trigger_id="current-failure:7",
        failure_class=failure_class,
        operation="apply",
        resource="SelectedLemma",
        rejected_tactic="apply SelectedLemma.",
        corrected_tactic="apply (SelectedLemma M).",
        evidence_refs=_evidence(),
    )

    assert result.operation == "apply"
    assert result.resource == "SelectedLemma"
    spec = operation_binding_repair_feature_spec()
    assert spec.feature_id == OPERATION_BINDING_REPAIR_FEATURE_ID
    assert spec.gate.evidence_ledger_ids == ("M15-B1-B2-B4",)
    assert spec.native_semantic_dependencies == (
        "NativeApplicationSyntaxRepairDescriptor[B2.module_syntax]",
        "NativeProofTermDescriptor[B1]",
        "NativeProofTermDescriptor[B2.losslessness]",
        "NativeProofTermDescriptor[B2.losslessness_call]",
        "NativeProofTermDescriptor[B2/B4.probability_multislot]",
        "NativeSelectedApplicationBindingSetDescriptor[B2.selected_head]",
    )
    assert spec.strategy_contracts[0].strategy_class == "commitment_relative"
    with pytest.raises(ValueError, match="only B1/B2/B4"):
        replace(result, failure_class="B7")
    with pytest.raises(ValueError, match="same semantic operation"):
        replace(result, corrected_tactic="exact OtherLemma.")
    with pytest.raises(ValueError, match="same selected resource"):
        replace(result, corrected_tactic="apply OtherLemma.")


def test_bare_operation_resource_rejects_partially_applied_repairs() -> None:
    assert bare_operation_resource("apply SelectedLemma.") == (
        "apply",
        "SelectedLemma",
    )
    assert bare_operation_resource("apply (SelectedLemma).") == (
        "apply",
        "SelectedLemma",
    )
    assert bare_operation_resource("apply (SelectedLemma M).") is None
