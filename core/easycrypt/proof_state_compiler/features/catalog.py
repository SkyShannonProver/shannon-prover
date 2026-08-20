"""Production catalog of publicly shipped compiler feature packages."""

from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    compound_tactic_prefix_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair import (
    intro_pattern_repair_feature,
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


def production_feature_catalog() -> FeatureCatalog:
    """Return only feature packages included in the production treatment."""

    definitions = (
        compound_tactic_prefix_recovery_feature(),
        intro_pattern_repair_feature(),
        operation_binding_repair_feature(),
        phl_transitivity_boundary_repair_feature(),
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
    return catalog
