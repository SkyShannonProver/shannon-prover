"""Identity of the compound-tactic prefix recovery slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID = (
    "compound_tactic_prefix_recovery"
)
COMPOUND_TACTIC_PREFIX_RECOVERY_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected and ordered the compound tactic; native "
        "EasyCrypt reports the longest contiguous accepted source prefix "
        "without asking the agent to commit that prefix alone"
    ),
    required_commitment="exact_rejected_compound_tactic_and_source_order",
)
