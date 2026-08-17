"""Evidence-gated B1/B2/B4 operation-binding repair vertical slice."""

from core.easycrypt.proof_state_compiler.contracts import (
    COMMITMENT_RELATIVE,
    StrategyContract,
)
from core.easycrypt.proof_state_compiler.features.registry import (
    ExperimentGate,
    FeatureDefinition,
    FeatureSpec,
)


OPERATION_BINDING_REPAIR_FEATURE_ID = "operation_binding_repair"
OPERATION_BINDING_REPAIR_STRATEGY_CONTRACT = StrategyContract(
    strategy_class=COMMITMENT_RELATIVE,
    rationale=(
        "the correction preserves the exact operation and semantic resource "
        "from one authoritative failed occurrence"
    ),
    required_commitment="attempted_same_operation_and_resource",
)


def operation_binding_repair_feature_spec() -> FeatureSpec:
    return FeatureSpec(
        feature_id=OPERATION_BINDING_REPAIR_FEATURE_ID,
        gate=ExperimentGate(
            status="candidate",
            evidence_ledger_ids=("M15-B1-B2-B4",),
            experiment_id="operation-binding-repair-v1",
        ),
        correctness_contract=(
            "claim only strict B1/B2/B4 attempted-operation IR and emit one "
            "exact-state-certified correction preserving operation/resource; "
            "the B2 losslessness family includes apply and bounded one-module "
            "call certificates with one or two deferred proof premises; one "
            "selected call may also realize its already-written first module "
            "argument using canonical EasyCrypt module grammar; a bare "
            "selected apply/exact theorem with module slots may expose only a "
            "complete native-checked zero/one/small-multiple binding result; "
            "concrete supplied arguments are never moved, reinterpreted, or "
            "reordered by that search; a native kind/position mismatch may "
            "expose only the shared expected-versus-supplied argument layout, "
            "explicitly without a checked application, binding, or reordering"
        ),
        provenance_contract=(
            "exact failure occurrence, StateRef, committed prefix, attempted "
            "operation/resource, bounded declaration, and verifier preflight"
        ),
        native_semantic_dependencies=(
            "NativeApplicationSyntaxRepairDescriptor[B2.module_syntax]",
            "NativeProofTermDescriptor[B1]",
            "NativeProofTermDescriptor[B2.losslessness]",
            "NativeProofTermDescriptor[B2.losslessness_call]",
            "NativeProofTermDescriptor[B2/B4.probability_multislot]",
            "NativeSelectedApplicationBindingSetDescriptor[B2.selected_head]",
        ),
        shannon_delta_contract=(
            "preserve one attempted operation/resource; B1 enumerates one "
            "namespace-only correction; B2 losslessness enumerates one module "
            "spelling for apply or one placeholder-only call with one or two "
            "proof premises; B2 module syntax inserts punctuation only around "
            "an exact agent-written module term and preserves its suffix; "
            "generic selected-head search sends a bounded lexical spelling "
            "inventory through one native transaction and never ranks a "
            "multi-result set, and is admitted only for an argument-free bare "
            "apply/exact attempt; B2/B4 probability repair enumerates one "
            "multi-slot spelling; shared argument diagnostics compare only "
            "native head slots and parsed argument kinds; EasyCrypt validates "
            "every candidate"
        ),
        lexical_prefilter_contract=(
            "B1 basename and B2 losslessness procedure matching only bound "
            "native requests; module spellings and probability tokens only "
            "bound native search and have no semantic authority"
        ),
        required_ir_capabilities=(
            "FailureObservation",
            "AttemptedOperationIR",
            "RecoveryClaim",
            "DeclarationLoadRequest.symbol_declarations",
            "ProofResource",
            "ModuleSpellingInventory",
            "ApplicationSignature",
            "SlotResolution",
            "ApplicationCandidate",
            "NativeApplicationSyntaxRepairDescriptor",
        ),
        certification_policy="exact_tactic_preflight",
        strategy_contracts=(OPERATION_BINDING_REPAIR_STRATEGY_CONTRACT,),
    )


def operation_binding_repair_feature() -> FeatureDefinition:
    from .analysis import analyze_operation_binding_repair
    from .resource_discovery import discover_attempted_operation_resources
    from .resource_loading import request_attempted_resource_declaration
    from .surface_lowering import lower_operation_binding_repair
    from .namespace_repair import plan_native_namespace_repair
    from .losslessness_module_repair import (
        plan_native_losslessness_module_repair,
    )
    from .losslessness_call_repair import (
        plan_native_losslessness_call_repair,
    )
    from .application_module_syntax_repair import (
        plan_native_application_module_syntax_repair,
    )
    from .probability_multislot_repair import (
        plan_native_probability_multislot_repair,
    )
    from .selected_application_binding_set import (
        plan_native_selected_application_binding_set,
    )
    from .execution import OPERATION_BINDING_FAILURE_EXECUTION_GATE
    from .attempt_diagnostic import plan_native_operation_binding_attempt

    return FeatureDefinition(
        spec=operation_binding_repair_feature_spec(),
        execution_gate=OPERATION_BINDING_FAILURE_EXECUTION_GATE,
        resource_load_request_producers=(request_attempted_resource_declaration,),
        resource_discoverers=(discover_attempted_operation_resources,),
        native_semantic_request_producers=(
            plan_native_operation_binding_attempt,
            plan_native_namespace_repair,
            plan_native_losslessness_module_repair,
            plan_native_losslessness_call_repair,
            plan_native_application_module_syntax_repair,
            plan_native_probability_multislot_repair,
            plan_native_selected_application_binding_set,
        ),
        analysis_producers=(analyze_operation_binding_repair,),
        surface_lowerers=(lower_operation_binding_repair,),
    )
