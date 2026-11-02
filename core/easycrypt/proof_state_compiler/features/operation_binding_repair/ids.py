"""Feature-local identifiers shared by the operation-binding repair families."""

from __future__ import annotations

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


OPERATION_BINDING_REPAIR_FEATURE_ID = "operation_binding_repair"
OPERATION_BINDING_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the correction preserves the exact operation and semantic resource "
        "from one authoritative failed occurrence"
    ),
    required_commitment="attempted_same_operation_and_resource",
)
OPERATION_BINDING_REPAIR_ANALYSIS_PRODUCER_ID = (
    "operation_binding_repair.analysis"
)
