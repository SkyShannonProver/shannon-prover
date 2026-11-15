"""Identity of the smt-failure localization slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


SMT_FAILURE_LOCALIZATION_FEATURE_ID = "smt_failure_localization"
# The output only reports facts: where EasyCrypt's first failing smt call
# sits in the agent's own rejected tactic, how many goals it fails on, and
# the kind of the first one.  It names no tactic, lemma, hint or next step.
# The shared delivery contract admits a failure-linked output only as
# commitment-relative, and the facts are anchored to that exact tactic.
SMT_FAILURE_LOCALIZATION_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "facts about the agent's own rejected tactic only: EasyCrypt's first "
        "failing smt call in it, its failed-goal count and the kind of its "
        "first failed goal; no tactic, hint, lemma or next step is chosen"
    ),
    required_commitment="exact_rejected_tactic_and_its_smt_calls",
)
