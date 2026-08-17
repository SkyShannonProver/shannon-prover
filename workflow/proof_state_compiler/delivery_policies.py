"""The only production catalog of delivery-policy definitions."""

from core.easycrypt.proof_state_compiler.contracts import (
    BASE_POLICY_REJECTION_REASONS,
    CERTIFICATION_MISSING_OR_REJECTED,
    DeliveryPolicyCatalog,
    DeliveryPolicyDefinition,
    commitment_result_rule,
    failure_linked_repair_rule,
    intrinsic_changed_fact_rule,
)
from core.easycrypt.proof_state_compiler.features.intro_pattern_repair import (
    INTRO_PATTERN_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.compound_tactic_prefix_recovery import (
    COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.phl_transitivity_boundary_repair import (
    PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization import (
    RELATION_BRIDGE_REALIZATION_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.tactic_dialect_repair import (
    TACTIC_DIALECT_REPAIR_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    PURE_TAIL_RECOVERY_FEATURE_ID,
)


INTRINSIC_CHANGED_FACT_POLICY_ID = "intrinsic_changed_fact"
SELECTED_OPERATION_ONCE_POLICY_ID = "selected_operation_once"
OPERATION_BINDING_REPAIR_ONCE_POLICY_ID = "operation_binding_repair_once"
INTRO_PATTERN_REPAIR_ONCE_POLICY_ID = "intro_pattern_repair_once"
RELATION_BRIDGE_ONCE_POLICY_ID = "relation_bridge_once"
PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID = "phl_transitivity_boundary_once"
TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID = "tactic_dialect_repair_once"
PURE_TAIL_RECOVERY_ONCE_POLICY_ID = "pure_tail_recovery_once"
COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID = (
    "compound_tactic_prefix_recovery_once"
)

def default_delivery_policy_catalog() -> DeliveryPolicyCatalog:
    definitions = (
        DeliveryPolicyDefinition(
            policy_id=COMPOUND_TACTIC_PREFIX_RECOVERY_ONCE_POLICY_ID,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=700,
            dependency_allowance_markdown_bytes=550,
            compatible_feature_ids=(
                COMPOUND_TACTIC_PREFIX_RECOVERY_FEATURE_ID,
            ),
            compatibility_contract=(
                "one exact rolled-back compound occurrence, complete longest "
                "accepted-prefix boundary, first rejected extension, native "
                "error, and no-prefix-committed statement"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS,
        ),
        DeliveryPolicyDefinition(
            policy_id=OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=700,
            compatible_feature_ids=(OPERATION_BINDING_REPAIR_FEATURE_ID,),
            compatibility_contract=(
                "one exact CurrentStateFailure, complete native binding reason, "
                "dynamic application, residual proof holes, and exact checked "
                "operation-binding repair"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ),
        DeliveryPolicyDefinition(
            policy_id=INTRO_PATTERN_REPAIR_ONCE_POLICY_ID,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=600,
            compatible_feature_ids=(INTRO_PATTERN_REPAIR_FEATURE_ID,),
            compatibility_contract=(
                "one exact CurrentStateFailure, complete ordered-binder "
                "explanation, and exact checked intro-pattern realization"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ),
        DeliveryPolicyDefinition(
            policy_id=PURE_TAIL_RECOVERY_ONCE_POLICY_ID,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=600,
            compatible_feature_ids=(PURE_TAIL_RECOVERY_FEATURE_ID,),
            compatibility_contract=(
                "one exact CurrentStateFailure, selected rewrite lemma and "
                "direction, native-unique target, mismatch reason, and exact "
                "checked target-qualified rewrite"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ),
        DeliveryPolicyDefinition(
            policy_id=RELATION_BRIDGE_ONCE_POLICY_ID,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=900,
            compatible_feature_ids=(RELATION_BRIDGE_REALIZATION_FEATURE_ID,),
            compatibility_contract=(
                "one exact CurrentStateFailure, complete relation mismatch "
                "reason, every native-accepted bridge and obligation split, or "
                "one argument-preserving exact checked realization"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ),
        DeliveryPolicyDefinition(
            policy_id=PHL_TRANSITIVITY_BOUNDARY_ONCE_POLICY_ID,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=600,
            compatible_feature_ids=(PHL_TRANSITIVITY_BOUNDARY_REPAIR_FEATURE_ID,),
            compatibility_contract=(
                "one exact CurrentStateFailure, complete native-established "
                "PHL function/statement boundary mismatch, and every "
                "strategy-neutral boundary alternative"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS,
        ),
        DeliveryPolicyDefinition(
            policy_id=TACTIC_DIALECT_REPAIR_ONCE_POLICY_ID,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=800,
            compatible_feature_ids=(TACTIC_DIALECT_REPAIR_FEATURE_ID,),
            compatibility_contract=(
                "one exact CurrentStateFailure and complete native-established "
                "selected eager-while repair, every accepted invariant without "
                "ranking, or the full blocker diagnostic"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ),
        DeliveryPolicyDefinition(
            policy_id=INTRINSIC_CHANGED_FACT_POLICY_ID,
            rule=intrinsic_changed_fact_rule(),
            max_items=1,
            max_markdown_bytes=360,
            compatible_feature_ids=(),
            compatibility_contract=(
                "requires a separately admitted intrinsic delta feature"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS,
        ),
        DeliveryPolicyDefinition(
            policy_id=SELECTED_OPERATION_ONCE_POLICY_ID,
            rule=commitment_result_rule(),
            max_items=1,
            max_markdown_bytes=520,
            compatible_feature_ids=(),
            compatibility_contract=(
                "requires a separately admitted exact selected-operation feature"
            ),
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
                CERTIFICATION_MISSING_OR_REJECTED,
            ),
        ),
    )
    return DeliveryPolicyCatalog(definitions=tuple(sorted(
        definitions,
        key=lambda item: item.policy_id,
    )))
