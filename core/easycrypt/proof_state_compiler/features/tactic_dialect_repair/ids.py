"""Identity of the tactic-dialect repair slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


TACTIC_DIALECT_REPAIR_FEATURE_ID = "tactic_dialect_repair"
TACTIC_DIALECT_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected eager while; the feature preserves its "
        "submitted invariant candidates and changes only native tactic dialect"
    ),
    required_commitment="agent_supplied_eager_while_operation",
)
