"""The only production catalog of proof-state compiler feature packages."""

from core.easycrypt.proof_state_compiler.features.accepted_contract_retention import (
    accepted_contract_retention_feature,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    compound_tactic_prefix_recovery_feature,
)

from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application import (
    losslessness_certificate_application_feature,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair import (
    intro_pattern_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness import (
    program_operation_readiness_feature,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    pure_tail_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    operation_binding_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair import (
    phl_transitivity_boundary_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization import (
    relation_bridge_realization_feature,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair import (
    tactic_dialect_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.registry import FeatureCatalog
from core.easycrypt.proof_state_compiler.contracts import ROUTE_SELECTING
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application import (
    LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,
)


def default_feature_catalog() -> FeatureCatalog:
    """Return the immutable catalog; catalog membership does not enable a feature."""

    definitions = (
        accepted_contract_retention_feature(),
        compound_tactic_prefix_recovery_feature(),
        intro_pattern_repair_feature(),
        losslessness_certificate_application_feature(),
        operation_binding_repair_feature(),
        phl_transitivity_boundary_repair_feature(),
        program_operation_readiness_feature(),
        pure_tail_recovery_feature(),
        relation_bridge_realization_feature(),
        tactic_dialect_repair_feature(),
    )
    catalog = FeatureCatalog(
        definitions=tuple(sorted(
            definitions,
            key=lambda item: item.spec.feature_id,
        ))
    )
    route_selecting = tuple(
        definition.spec.feature_id
        for definition in catalog.definitions
        if any(
            contract.strategy_class == ROUTE_SELECTING
            for contract in definition.spec.strategy_contracts
        )
    )
    if route_selecting != (LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,):
        raise ValueError(
            "production SC2 exception set must contain only frozen M05"
        )
    return catalog
