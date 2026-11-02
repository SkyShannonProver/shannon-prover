"""Identity of the intro-pattern repair slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


INTRO_PATTERN_REPAIR_FEATURE_ID = "intro_pattern_repair"
INTRO_PATTERN_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the agent already selected the destruct operation and exact binder "
        "names/order; native EasyCrypt only realizes that commitment in its "
        "canonical deep-flatten intro dialect"
    ),
    required_commitment="selected_destruct_source_and_ordered_binders",
)
