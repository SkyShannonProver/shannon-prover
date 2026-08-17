"""Evidence-gated contract for accepted-contract retention."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


ACCEPTED_CONTRACT_RETENTION_FEATURE_ID = "accepted_contract_retention"
ACCEPTED_CONTRACT_RETENTION_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the result compares only conjuncts in an exact contract the agent "
        "already submitted and EasyCrypt accepted"
    ),
    required_commitment="accepted_structural_contract",
)


def accepted_contract_retention_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=ACCEPTED_CONTRACT_RETENTION_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M09",),
            experiment_id="accepted-contract-retention-audit-v1",
        ),
        correctness_contract=(
            "report only an original accepted conjunct missing at the same "
            "lineage-valid boundary; preserved-all and new strengthening abstain"
        ),
        provenance_contract=(
            "event-bound accepted contract, exact anchor prefix, verified "
            "prefix lineage, and current matching boundary"
        ),
        native_semantic_dependencies=("NativeProofStateSnapshot",),
        shannon_delta_contract=(
            "compare an agent-accepted contract with the lineage-valid current "
            "boundary without proposing a strengthening"
        ),
        lexical_prefilter_contract=(
            "accepted/current conjunct text is an identity candidate only; "
            "the feature remains audit-only"
        ),
        required_ir_capabilities=(
            "CompilerInvocationContext",
            "ProgramStatement",
            "ProofFact",
        ),
        certification_policy="accepted_anchor_conjunct_identity",
        strategy_contracts=(
            ACCEPTED_CONTRACT_RETENTION_STRATEGY_CONTRACT,
        ),
    )


def accepted_contract_retention_feature() -> FeatureDefinition:
    from .analysis import analyze_accepted_contract_retention
    from .surface_lowering import lower_accepted_contract_retention

    return FeatureDefinition(
        spec=accepted_contract_retention_feature_spec(),
        analysis_producers=(analyze_accepted_contract_retention,),
        surface_lowerers=(lower_accepted_contract_retention,),
    )
