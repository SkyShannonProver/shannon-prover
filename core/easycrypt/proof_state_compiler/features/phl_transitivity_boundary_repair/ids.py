"""Identity of the PHL transitivity boundary repair slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID = (
    "phl_transitivity_boundary_repair"
)
PHL_TRANSITIVITY_BOUNDARY_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the diagnostic explains the native boundary required by the written "
        "PHL transitivity form and leaves boundary, side, and intermediate "
        "selection to the agent"
    ),
    required_commitment="agent_supplied_phl_transitivity_form",
)
