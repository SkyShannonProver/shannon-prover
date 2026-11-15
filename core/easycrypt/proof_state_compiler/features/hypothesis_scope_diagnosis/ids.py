"""Identity of the hypothesis-scope diagnosis slice.

Analysis and lowering import these instead of ``feature.py``, which
imports them to register the slice.
"""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)


HYPOTHESIS_SCOPE_DIAGNOSIS_FEATURE_ID = "hypothesis_scope_diagnosis"

# The explanation is SC0 content: it states only what EasyCrypt established
# about one name the agent wrote, and introduces no choice.  Failure-linked
# delivery admits only commitment-relative candidates, so the candidate is
# anchored to that exact rejected operation.
HYPOTHESIS_SCOPE_FACT_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "states native facts about one name in the agent's rejected "
        "operation: it is a goal hypothesis outside that operation's lookup "
        "scope; no resource, tactic or route is selected"
    ),
    required_commitment="rejected_operation_named_reference",
)

# The optional action is SC1: the agent's own smt call with exactly the one
# native-identified hypothesis hint removed and every other hint kept.
HYPOTHESIS_SCOPE_SMT_HINT_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "preserves the agent's smt call and its remaining hints in order, "
        "dropping only the hint EasyCrypt could not resolve, which names a "
        "goal hypothesis smt already receives"
    ),
    required_commitment="agent_selected_smt_call_and_remaining_hints",
)
