"""Identity of the relation-bridge realization slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


RELATION_BRIDGE_REALIZATION_FEATURE_ID = "relation_bridge_realization"
RELATION_BRIDGE_REALIZATION_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the correction preserves the native-identified intermediate supplied "
        "by the failed intent and changes only its certified realization"
    ),
    required_commitment="agent_supplied_relation_intermediate",
)
