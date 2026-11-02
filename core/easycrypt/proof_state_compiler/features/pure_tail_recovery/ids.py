"""Identity of the pure-tail recovery slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


PURE_TAIL_RECOVERY_FEATURE_ID = "pure_tail_recovery"
PURE_TAIL_RECOVERY_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected the rewrite lemma and direction; native "
        "EasyCrypt identifies one unique current hypothesis target"
    ),
    required_commitment="attempted_rewrite_lemma_and_direction",
)
