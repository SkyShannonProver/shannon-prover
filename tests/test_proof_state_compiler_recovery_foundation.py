"""Canonical recovery-foundation and independent-delivery migration laws."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    ExperimentGate,
    FeatureCatalog,
    FeatureDefinition,
    FeatureSpec,
    LoadedDeclaration,
    LoadedSourceUnit,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.backend import (
    SurfaceContribution,
    admit_action_surface,
)
from core.easycrypt.proof_state_compiler.contracts import (
    ActionCandidate,
    BASE_POLICY_REJECTION_REASONS,
    CertificationResult,
    CompilerTurnEvidence,
    DeliveryPolicyCatalog,
    DeliveryPolicyDefinition,
    EvidenceRef,
    NativeApplicationHeadDescriptor,
    NativeApplicationSlotDescriptor,
    NativeAttemptDiagnosticQuery,
    NativeCheckedApplication,
    NativeFormulaDescriptor,
    NativeInputArgument,
    NativeProofTermArgument,
    NativeProofTermDescriptor,
    NativeSelectedApplicationBindingSetDescriptor,
    NativeSelectedApplicationBindingSetQuery,
    NativeSemanticRequest,
    NativeSemanticRequestProduction,
    NativeSemanticObservation,
    NativeResolvedHead,
    RecoveryClaim,
    ResolvedDeliveryPlan,
    StrategyContract,
    TargetRef,
    TransitionRef,
    COMMITMENT_RELATIVE,
    ROUTE_SELECTING,
    failure_linked_repair_rule,
    freeze_json_object,
    frozen_json_sha256,
    compiler_invocation_context,
    exact_operation_resource_witness,
)
from core.easycrypt.proof_state_compiler.features.catalog import (
    default_feature_catalog,
)
from core.easycrypt.proof_state_compiler.features.losslessness_certificate_application import (
    LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    OPERATION_BINDING_REPAIR_FEATURE_ID,
    operation_binding_repair_feature,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness import (
    PROGRAM_OPERATION_READINESS_FEATURE_ID,
)
from core.easycrypt.proof_state_compiler.middle_end import AnalysisContribution
from core.easycrypt.proof_state_compiler.middle_end.recovery_ownership import (
    resolve_recovery_ownership,
)
from workflow.proof_state_compiler.activation import (
    TREATMENT,
    CompilerProfile,
    FeatureActivation,
)
from workflow.proof_state_compiler.assembly import assemble_compiler_profile
from workflow.proof_state_compiler.configuration import (
    COMPILER_PROFILES,
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.profile_ids import (
    OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
)
from tests.proof_state_compiler_test_support import (
    attempted_operation_native_observation,
    bare_native_observation,
    native_state,
)
from workflow.proof_state_compiler.delivery_policies import (
    INTRINSIC_CHANGED_FACT_POLICY_ID,
    OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
    default_delivery_policy_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "core/easycrypt/proof_state_compiler"


def _state_ref(
    *,
    event: int = 7,
    prefix: str = "p" * 64,
    goal: str = "recovery-goal",
) -> StateRef:
    return StateRef(
        session_id="recovery-foundation",
        state_version=event,
        goal_identity=goal,
        goal_identity_required=True,
        committed_prefix_identity=prefix,
    )


def _snapshot(state_ref: StateRef | None = None) -> AuthoritativeSnapshotInput:
    state_ref = state_ref or _state_ref()
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="recovery.fixture",
            authority="compiler.input.produced",
            source_sha256="a" * 64,
            artifact_ref="compiler_inputs/recovery.json",
            source_event_id=f"compiler-input-{state_ref.state_version}",
            source_event_sequence=state_ref.state_version,
            authoritative=True,
        ),
        target=TargetRef("eval/recovery.ec", "recovery"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/recovery.json"
        ),
        goal_lines=("Current goal", "--------", "true"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(state_ref),
    )


def _turn(
    state_ref: StateRef,
    *,
    tactic: str = "exact Wrong.dword_ll.",
    error: str = "unknown identifier Wrong.dword_ll",
    event_id: str = "tactic-event-7",
    event_sequence: int = 7,
) -> CompilerTurnEvidence:
    return CompilerTurnEvidence(
        source_event_id=event_id,
        source_event_sequence=event_sequence,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref=f"tactic_execution_results/{event_id}.json",
        artifact_hash="b" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error=error,
    )


def _environment(*symbols: str) -> CompilationEnvironment:
    declarations = tuple(
        LoadedDeclaration(
            symbol=symbol,
            source_ref=f"easycrypt:print:recovery.ec#{symbol}",
            declaration_sha256=hashlib.sha256(
                f"lemma {symbol.rsplit('.', 1)[-1]} : true.".encode()
            ).hexdigest(),
            declaration=f"lemma {symbol.rsplit('.', 1)[-1]} : true.",
        )
        for symbol in symbols
    )
    return CompilationEnvironment("recovery-environment", (), declarations)


def _selected_binding_environment() -> CompilationEnvironment:
    text = "\n".join((
        "module NativeBindingOne = {}.",
        "module NativeBindingTwo = {}.",
    ))
    base = _environment("native_binding_true")
    return CompilationEnvironment(
        environment_id="selected-binding-environment",
        source_units=(LoadedSourceUnit(
            source_ref="eval/selected_binding.ec",
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            text=text,
        ),),
        loaded_declarations=base.loaded_declarations,
    )


def _selected_binding_attempt_head() -> NativeApplicationHeadDescriptor:
    return NativeApplicationHeadDescriptor(
        resolved_head=NativeResolvedHead(
            "global", "Top.native_binding_true"
        ),
        input_mode="implicit",
        input_arguments=(),
        slots=(NativeApplicationSlotDescriptor(
            position=1,
            kind="module",
            name="O",
            type_text="NativeBindingOracle",
        ),),
        result=NativeFormulaDescriptor(
            kind="true",
            text="true",
            type_text="bool",
        ),
    )


def _selected_consequence_attempt_head(
    *, module_slot_count: int = 1,
) -> NativeApplicationHeadDescriptor:
    return NativeApplicationHeadDescriptor(
        resolved_head=NativeResolvedHead(
            "global", "Top.RO_FinRO_D"
        ),
        input_mode="implicit",
        input_arguments=(NativeInputArgument(
            position=1,
            syntax_kind="formula",
            explicit_hole=False,
            source_spelling="G2",
        ),),
        slots=(
            NativeApplicationSlotDescriptor(
                position=1,
                kind="proof",
                formula=NativeFormulaDescriptor(
                    kind="quantifier",
                    text="forall x, is_lossless dblock",
                    type_text="bool",
                ),
            ),
            *(NativeApplicationSlotDescriptor(
                position=2 + index,
                kind="module",
                name=f"D{index + 1}",
                type_text="FinRO_Distinguisher",
            ) for index in range(module_slot_count)),
        ),
        result=NativeFormulaDescriptor(
            kind="formula",
            text="equiv[MainD(D, RO).distinguish ~ MainD(D, FinRO).distinguish]",
            type_text="bool",
        ),
    )


def _selected_binding_completion(term: str) -> NativeCheckedApplication:
    module_identity = term.split("(<: ", 1)[1][:-1]
    descriptor = NativeProofTermDescriptor(
        resolved_head=NativeResolvedHead(
            "global", "Top.native_binding_true"
        ),
        input_mode="implicit",
        input_arguments=(NativeInputArgument(1, "module", False),),
        explicit_hole_count=0,
        implicit_argument_count=0,
        arguments=(NativeProofTermArgument(
            position=1,
            kind="module",
            hole=False,
            expected_name="O",
            expected_type="NativeBindingOracle",
            resolved_identity=module_identity,
        ),),
        can_concretize=True,
        residual_proof_premises=(),
        result=NativeFormulaDescriptor(
            kind="true",
            text="true",
            type_text="bool",
        ),
        result_convertible_to_current_goal=True,
    )
    return NativeCheckedApplication(
        application_term=term,
        candidate_tactic=f"apply ({term}).",
        tactic_effect="accepted_changed",
        descriptor=descriptor,
    )


def _selected_binding_observation(
    request: NativeSemanticRequest,
    completion_terms: tuple[str, ...],
    *,
    typed_binding_count: int | None = None,
) -> NativeSemanticObservation:
    assert isinstance(
        request.query, NativeSelectedApplicationBindingSetQuery
    )
    completions = tuple(
        _selected_binding_completion(term) for term in completion_terms
    )
    descriptor = NativeSelectedApplicationBindingSetDescriptor(
        operation="apply",
        selected_resource="native_binding_true",
        resolved_head=NativeResolvedHead(
            "global", "Top.native_binding_true"
        ),
        module_slot_count=1,
        candidate_module_term_count=len(request.query.module_candidates),
        candidate_check_count=len(request.query.module_candidates),
        typed_binding_count=(
            len(completions)
            if typed_binding_count is None
            else typed_binding_count
        ),
        checked_completion_count=len(completions),
        population_complete=True,
        checked_completions=completions,
    )
    return NativeSemanticObservation.accepted(
        request=request,
        batch_id="test-selected-binding-set",
        batch_index=0,
        batch_size=1,
        batch_elapsed_ms=2,
        result_formula="",
        descriptor=descriptor,
        runtime_identity_sha256="a" * 64,
        companion_identity_sha256="b" * 64,
        elapsed_ms=2,
        provenance=ProvenanceRef(
            producer="test.native_selected_binding_set",
            authority="native.semantic.batch.produced",
            source_sha256="f" * 64,
            artifact_ref="native_semantic_batches/selected-binding-test.json",
            source_event_id="native-selected-binding-test",
            source_event_sequence=3,
            authoritative=True,
        ),
    )


def _compile_operation_repair(
    *,
    state_ref: StateRef | None = None,
    turn: CompilerTurnEvidence | None = None,
    environment: CompilationEnvironment | None = None,
    features: tuple[FeatureDefinition, ...] | None = None,
):
    state_ref = state_ref or _state_ref()
    snapshot = _snapshot(state_ref)
    turn = turn or _turn(state_ref)
    invocation = compiler_invocation_context(state_ref, turn)
    compiler = ProofStateCompiler(
        features=features or (operation_binding_repair_feature(),)
    )
    environment = environment or _environment("dword_ll")
    environment = _resolve_native_dependencies(
        compiler, snapshot, environment, invocation
    )
    bundle = compiler.compile(snapshot, environment, invocation)
    return invocation, bundle


def _resolve_native_dependencies(
    compiler: ProofStateCompiler,
    snapshot: AuthoritativeSnapshotInput,
    environment: CompilationEnvironment,
    invocation,
) -> CompilationEnvironment:
    for _stage in range(2):
        plan = compiler.plan_native_semantics(snapshot, environment, invocation)
        if not plan.requests:
            break
        observations = []
        for request in plan.requests:
            if isinstance(request.query, NativeAttemptDiagnosticQuery):
                observations.append(attempted_operation_native_observation(request))
            else:
                observations.append(bare_native_observation(
                    request,
                    resolved_head=f"Top.{request.query.application_term}",
                ))
        environment = environment.with_native_semantic_observations(
            tuple(observations)
        )
    return environment


def _recovery_contract() -> StrategyContract:
    return StrategyContract(
        strategy_class=COMMITMENT_RELATIVE,
        rationale="synthetic exact failed-operation recovery",
        required_commitment="attempted_same_operation_and_resource",
    )


def _synthetic_recovery_feature(
    feature_id: str,
    *,
    emit_tactic: str = "",
) -> FeatureDefinition:
    contract = _recovery_contract()

    def request_attempt(proof_ir, coordinate, invocation, budget):
        del coordinate, budget
        failure = invocation.failure_observation
        if failure is None:
            return NativeSemanticRequestProduction.not_applicable(
                f"{feature_id}.attempt.native"
            )
        tactic = str(failure.payload.to_dict().get("tactic") or "").strip()
        if not tactic:
            return NativeSemanticRequestProduction.not_applicable(
                f"{feature_id}.attempt.native"
            )
        request = NativeSemanticRequest(
            state_ref=proof_ir.state_ref,
            request_id=f"{feature_id}:attempt",
            producer_id=f"{feature_id}.attempt.native",
            query=NativeAttemptDiagnosticQuery(
                rejected_tactic=tactic,
                observed_outcome_kind="rejected",
            ),
            evidence_refs=(failure.evidence_ref,),
        )
        return NativeSemanticRequestProduction.ready(
            f"{feature_id}.attempt.native", (request,)
        )

    def claim(proof_ir, coordinate, invocation):
        attempted = proof_ir.attempted_operation
        if attempted is None:
            return AnalysisContribution()
        return AnalysisContribution(recovery_claims=(RecoveryClaim(
            feature_id=feature_id,
            recovery_key=attempted.recovery_key,
            attempt_id=attempted.attempt_id,
            occurrence_identity=attempted.occurrence_identity,
            trigger_id=attempted.trigger_id,
            operation_family=attempted.operation_family,
            selected_resource=attempted.exact_resource,
            resource_match_kind=(
                "exact" if attempted.exact_resource else "none"
            ),
            allowed_output_kinds=("action",),
            preservation_witness=exact_operation_resource_witness(
                attempted.operation_family,
                attempted.exact_resource,
            ),
            evidence_refs=attempted.evidence_refs,
        ),))

    def lower(state, invocation):
        attempted = state.attempted_operation
        if (
            not emit_tactic
            or attempted is None
            or not state.recovery_ownership.owns(
                feature_id, attempted.recovery_key
            )
        ):
            return SurfaceContribution()
        return SurfaceContribution(actions=(ActionCandidate(
            candidate_id=f"{feature_id}:candidate",
            feature_id=feature_id,
            intent="commit_tactic",
            payload=freeze_json_object({"tactic": emit_tactic}),
            unresolved_premises=(),
            certification_policy="exact_tactic_preflight",
            strategy_contract=contract,
            evidence_refs=attempted.evidence_refs,
            trigger_id=attempted.trigger_id,
        ),))

    return FeatureDefinition(
        spec=FeatureSpec(
            feature_id=feature_id,
            gate=ExperimentGate(
                status="candidate",
                evidence_ledger_ids=("SYNTHETIC-RECOVERY",),
                experiment_id=f"{feature_id}-test",
            ),
            correctness_contract="test exact recovery ownership",
            provenance_contract="exact attempted operation occurrence",
            native_semantic_dependencies=(),
            shannon_delta_contract="synthetic recovery ownership sentinel",
            lexical_prefilter_contract="none",
            required_ir_capabilities=(
                "AttemptedOperationIR",
                "RecoveryClaim",
                "AnalyzedProofState",
            ),
            certification_policy="exact_tactic_preflight",
            strategy_contracts=(contract,),
        ),
        native_semantic_request_producers=(request_attempt,),
        analysis_producers=(claim,),
        surface_lowerers=(lower,),
    )


def test_failure_frontend_preserves_exact_authoritative_occurrence() -> None:
    invocation, bundle = _compile_operation_repair()
    failure = invocation.failure_observation
    attempted = bundle.proof_ir.attempted_operation

    assert failure is not None and attempted is not None
    assert failure.source_event_id == "tactic-event-7"
    assert failure.source_event_sequence == 7
    assert failure.state_ref == bundle.state_ref
    assert failure.committed_prefix_identity == "p" * 64
    assert failure.payload.to_dict() == {"tactic": "exact Wrong.dword_ll."}
    assert attempted.occurrence_identity == failure.occurrence_identity
    assert attempted.operation == "exact"
    assert attempted.resource == "Wrong.dword_ll"
    assert attempted.trigger_id == invocation.event_trigger.trigger_id


def test_b1_requires_one_accepted_native_descriptor() -> None:
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref))
    environment = _environment("dword_ll")
    compiler = ProofStateCompiler(features=(
        operation_binding_repair_feature(),
    ))

    plan = compiler.plan_native_semantics(snapshot, environment, invocation)

    assert len(plan.requests) == 1
    attempt_request = plan.requests[0]
    assert isinstance(attempt_request.query, NativeAttemptDiagnosticQuery)
    assert attempt_request.query.rejected_tactic == "exact Wrong.dword_ll."
    with pytest.raises(
        ValueError,
        match="unresolved native semantic dependencies",
    ):
        compiler.compile(snapshot, environment, invocation)

    environment = environment.with_native_semantic_observations((
        attempted_operation_native_observation(attempt_request),
    ))
    corrected_plan = compiler.plan_native_semantics(
        snapshot, environment, invocation
    )
    assert len(corrected_plan.requests) == 1
    request = corrected_plan.requests[0]
    assert request.query.operation == "exact"
    assert request.query.application_term == "dword_ll"
    accepted = bare_native_observation(
        request,
        resolved_head="Top.dword_ll",
    )
    bundle = compiler.compile(
        snapshot,
        environment.with_native_semantic_observations((accepted,)),
        invocation,
    )
    assert bundle.proof_ir.module_spelling_inventory is None
    assert len(bundle.candidate_surface.actions) == 1
    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {"tactic": "exact (dword_ll)."}
    assert action.correction is not None
    assert action.correction.presentation_kind == "do_you_mean"
    assert "selected `exact`" in action.correction.reason
    assert "operation and theorem you chose" in action.correction.reason
    assert action.recovery_witness_id == (
        bundle.analyzed_state.recovery_ownership
        .preservation_witness.witness_id
    )
    assert any(
        item.source_kind == "native_proof_term_descriptor"
        for item in action.evidence_refs
    )


@pytest.mark.parametrize("completion_count", (0, 1, 2))
def test_selected_theorem_binding_set_lowers_unique_or_complete_choice(
    completion_count: int,
) -> None:
    state_ref = _state_ref(goal="selected-binding-goal")
    snapshot = _snapshot(state_ref)
    turn = _turn(
        state_ref,
        tactic="apply native_binding_true.",
        error="cannot infer module arguments",
    )
    invocation = compiler_invocation_context(state_ref, turn)
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    environment = _selected_binding_environment()

    attempt_plan = compiler.plan_native_semantics(
        snapshot, environment, invocation
    )
    assert len(attempt_plan.requests) == 1
    attempt_observation = attempted_operation_native_observation(
        attempt_plan.requests[0],
        failure_kind="cannot_infer_module",
        application_head=_selected_binding_attempt_head(),
    )
    environment = environment.with_native_semantic_observations((
        attempt_observation,
    ))
    binding_plan = compiler.plan_native_semantics(
        snapshot, environment, invocation
    )
    binding_requests = tuple(
        request for request in binding_plan.requests
        if isinstance(
            request.query, NativeSelectedApplicationBindingSetQuery
        )
    )
    assert len(binding_requests) == 1
    assert binding_requests[0].query.module_candidates == (
        "NativeBindingOne",
        "NativeBindingTwo",
    )
    terms = tuple(
        f"native_binding_true (<: NativeBinding{label})"
        for label in ("One", "Two")[:completion_count]
    )
    environment = environment.with_native_semantic_observations((
        _selected_binding_observation(
            binding_requests[0],
            terms,
            typed_binding_count=(2 if completion_count == 0 else None),
        ),
    ))

    bundle = compiler.compile(snapshot, environment, invocation)

    if completion_count == 0:
        assert bundle.candidate_surface.actions == ()
        assert len(bundle.candidate_surface.diagnostics) == 1
        diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
        assert diagnostic.code == "selected_application_not_applicable"
        assert diagnostic.primary == (
            "`native_binding_true` requires one module argument, in this "
            "order:\n\n"
            "1. `O` with module type `NativeBindingOracle`\n\n"
            "Supplying these arguments only instantiates the theorem.\n\n"
            "For the module candidates checked here, no completed instance "
            "makes this `apply` succeed in the current proof state.\n\n"
            "`apply H` can succeed only when the conclusion of the "
            "instantiated `H` matches—or can be unified with—the entire "
            "current goal.\n\n"
            "The proof state is unchanged. The compiler found no replacement "
            "`apply` that EasyCrypt accepts in this proof state."
        )
        assert diagnostic.notes == ()
        assert diagnostic.help == ""
        assembly = compiler_assembly_for_profile(
            OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
        )
        assert assembly is not None
        admission = admit_action_surface(
            bundle.candidate_surface,
            (),
            assembly.manifest,
            triggers=invocation.triggers,
        )
        assert len(admission.action_surface.diagnostics) == 1
        assert admission.decisions[0].effective_max_markdown_bytes == 700
        assert admission.markdown_bytes == 562
        assert "requires one module argument" in admission.presentation.text
        assert "no completed instance" in admission.presentation.text
        assert "found no replacement" in admission.presentation.text
    elif completion_count == 1:
        assert len(bundle.candidate_surface.actions) == 1
        assert bundle.candidate_surface.diagnostics == ()
        assert bundle.candidate_surface.actions[0].payload.to_dict() == {
            "tactic": "apply (native_binding_true (<: NativeBindingOne))."
        }
    else:
        assert bundle.candidate_surface.actions == ()
        assert len(bundle.candidate_surface.diagnostics) == 1
        diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
        assert diagnostic.code == (
            "selected_application_binding_choice_required"
        )
        assert diagnostic.applicability == "choice_required"
        assert "apply (native_binding_true (<: NativeBindingOne))." in (
            diagnostic.help
        )
        assert "apply (native_binding_true (<: NativeBindingTwo))." in (
            diagnostic.help
        )
        assert "compiler selected none" in diagnostic.help


def test_selected_binding_query_contract_is_direct_application_only() -> None:
    with pytest.raises(ValueError, match="binding-set operation"):
        NativeSelectedApplicationBindingSetQuery(
            operation="conseq",
            selected_resource="RO_FinRO_D",
            module_candidates=("G2",),
        )


@pytest.mark.parametrize("module_slot_count", (1, 2))
def test_concrete_consequence_mismatch_uses_alignment_without_binding_search(
    module_slot_count: int,
) -> None:
    state_ref = _state_ref(goal="selected-consequence-goal")
    snapshot = _snapshot(state_ref)
    turn = _turn(
        state_ref,
        tactic="conseq (RO_FinRO_D G2).",
        error="expecting a proof-term, not a formula",
    )
    invocation = compiler_invocation_context(state_ref, turn)
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    environment = _environment("RO_FinRO_D")

    attempt_plan = compiler.plan_native_semantics(
        snapshot, environment, invocation
    )
    assert len(attempt_plan.requests) == 1
    attempt = attempted_operation_native_observation(
        attempt_plan.requests[0],
        failure_kind="wrong_argument_kind",
        argument_kinds=("formula",),
        application_head=_selected_consequence_attempt_head(
            module_slot_count=module_slot_count
        ),
    )
    environment = environment.with_native_semantic_observations((attempt,))
    plan = compiler.plan_native_semantics(
        snapshot, environment, invocation
    )
    assert not any(
        isinstance(
            request.query, NativeSelectedApplicationBindingSetQuery
        )
        for request in plan.requests
    )

    bundle = compiler.compile(snapshot, environment, invocation)

    assert bundle.candidate_surface.actions == ()
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.code == "selected_application_argument_layout"
    assert diagnostic.primary.startswith(
        "`RO_FinRO_D` expects arguments in this order:\n\n"
        "1. a proof of `forall x, is_lossless dblock`\n"
        "2. `D1` with module type `FinRO_Distinguisher`"
    )
    assert "You supplied:\n\n1. formula `G2`" in diagnostic.primary
    assert "Argument 1 is a formula, but slot 1 requires a proof." in (
        diagnostic.primary
    )
    assert "preserved your concrete argument" in diagnostic.primary
    assert "did not reinterpret it" in diagnostic.primary
    assert diagnostic.notes == ()
    assert diagnostic.help == ""


def test_selected_consequence_argument_layout_does_not_guess_reordering(
) -> None:
    state_ref = _state_ref(goal="consequence-argument-layout")
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref,
        _turn(
            state_ref,
            tactic="conseq (RO_FinRO_D G2 dout_ll).",
            error="expecting a proof-term, not a formula",
        ),
    )
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    environment = _environment("RO_FinRO_D")
    attempt_request = compiler.plan_native_semantics(
        snapshot, environment, invocation
    ).requests[0]
    head = replace(
        _selected_consequence_attempt_head(),
        input_arguments=(
            NativeInputArgument(1, "formula", False, "G2"),
            NativeInputArgument(2, "formula", False, "dout_ll"),
        ),
    )
    environment = environment.with_native_semantic_observations((
        attempted_operation_native_observation(
            attempt_request,
            failure_kind="wrong_argument_kind",
            argument_kinds=("formula", "formula"),
            application_head=head,
        ),
    ))

    bundle = compiler.compile(snapshot, environment, invocation)

    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        OPERATION_BINDING_REPAIR_FEATURE_ID
    )
    assert bundle.candidate_surface.actions == ()
    assert len(bundle.candidate_surface.diagnostics) == 1
    diagnostic = bundle.candidate_surface.diagnostics[0].diagnostic
    assert diagnostic.code == "selected_application_argument_layout"
    assert diagnostic.primary.startswith(
        "`RO_FinRO_D` expects arguments in this order:\n\n"
        "1. a proof of `forall x, is_lossless dblock`\n"
        "2. `D1` with module type `FinRO_Distinguisher`"
    )
    assert "1. formula `G2`\n2. formula `dout_ll`" in diagnostic.primary
    assert "Argument 1 is a formula, but slot 1 requires a proof." in (
        diagnostic.primary
    )
    assert diagnostic.notes == ()


def test_indeterminate_native_diagnostic_never_produces_an_action() -> None:
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    turn = _turn(
        state_ref,
        tactic="apply Alossless.",
        error="native adapter assertion",
    )
    invocation = compiler_invocation_context(state_ref, turn)
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    environment = _environment("Alossless")
    head = NativeApplicationHeadDescriptor(
        resolved_head=NativeResolvedHead("global", "Top.Alossless"),
        input_mode="implicit",
        input_arguments=(),
        slots=(NativeApplicationSlotDescriptor(
            position=1,
            kind="module",
            name="O",
            type_text="Oracle",
        ),),
        result=NativeFormulaDescriptor(
            kind="true",
            text="true",
            type_text="bool",
        ),
    )
    for _stage in range(2):
        plan = compiler.plan_native_semantics(
            snapshot, environment, invocation
        )
        if not plan.requests:
            break
        observations = []
        for request in plan.requests:
            if isinstance(request.query, NativeAttemptDiagnosticQuery):
                observations.append(attempted_operation_native_observation(
                    request,
                    failure_kind="native_assertion",
                    diagnostic_status="indeterminate",
                    application_head=head,
                ))
            else:
                observations.append(bare_native_observation(
                    request,
                    resolved_head=f"Top.{request.query.application_term}",
                ))
        environment = environment.with_native_semantic_observations(
            tuple(observations)
        )

    bundle = compiler.compile(snapshot, environment, invocation)

    assert bundle.proof_ir.attempted_operation is not None
    assert (
        bundle.proof_ir.attempted_operation.native_diagnostic_status
        == "indeterminate"
    )
    assert bundle.candidate_surface.actions == ()


def test_no_progress_with_native_no_blocker_produces_no_recovery_claim() -> None:
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    turn = replace(
        _turn(state_ref, tactic="apply H."),
        outcome_kind="no_progress",
        structured_error="text-equal",
    )
    invocation = compiler_invocation_context(state_ref, turn)
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    environment = _environment("H")
    request = compiler.plan_native_semantics(
        snapshot, environment, invocation
    ).requests[0]
    head = NativeApplicationHeadDescriptor(
        resolved_head=NativeResolvedHead("local", "H"),
        input_mode="implicit",
        input_arguments=(),
        slots=(),
        result=NativeFormulaDescriptor(
            kind="true",
            text="true",
            type_text="bool",
        ),
    )
    observation = attempted_operation_native_observation(
        request,
        failure_kind="",
        diagnostic_status="no_blocker",
        application_head=head,
    )

    bundle = compiler.compile(
        snapshot,
        environment.with_native_semantic_observations((observation,)),
        invocation,
    )

    assert bundle.proof_ir.attempted_operation is not None
    assert (
        bundle.proof_ir.attempted_operation.native_diagnostic_status
        == "no_blocker"
    )
    assert bundle.analyzed_state.recovery_claims == ()
    assert bundle.candidate_surface.empty


def test_b1_abstains_on_native_rejection_or_different_resolved_head() -> None:
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, _turn(state_ref))
    environment = _environment("dword_ll")
    compiler = ProofStateCompiler(features=(
        operation_binding_repair_feature(),
    ))
    attempt_request = compiler.plan_native_semantics(
        snapshot, environment, invocation
    ).requests[0]
    environment = environment.with_native_semantic_observations((
        attempted_operation_native_observation(attempt_request),
    ))
    request = compiler.plan_native_semantics(
        snapshot, environment, invocation
    ).requests[0]
    accepted = bare_native_observation(
        request,
        resolved_head="Top.dword_ll",
    )
    rejected = NativeSemanticObservation.rejected(
        request=request,
        batch_id=accepted.batch_id,
        batch_index=accepted.batch_index,
        batch_size=accepted.batch_size,
        batch_elapsed_ms=accepted.batch_elapsed_ms,
        structured_error={
            "code": "native_user_error",
            "message": "synthetic native rejection",
        },
        runtime_identity_sha256=accepted.runtime_identity_sha256,
        companion_identity_sha256=accepted.companion_identity_sha256,
        elapsed_ms=accepted.elapsed_ms,
        provenance=accepted.provenance,
    )
    wrong_head = bare_native_observation(
        request,
        resolved_head="Top.another_lemma",
    )

    for observation in (rejected, wrong_head):
        bundle = compiler.compile(
            snapshot,
            environment.with_native_semantic_observations((observation,)),
            invocation,
        )
        assert bundle.analyzed_state.recovery_ownership.status == "owned"
        assert bundle.candidate_surface.empty


def test_b1_namespace_repair_never_drops_attempted_arguments() -> None:
    state_ref = _state_ref()
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(
        state_ref,
        _turn(
            state_ref,
            tactic="exact (Wrong.dword_ll x).",
            error="unknown identifier Wrong.dword_ll",
        ),
    )
    environment = _environment("dword_ll")
    compiler = ProofStateCompiler(features=(
        operation_binding_repair_feature(),
    ))

    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert len(plan.requests) == 1
    environment = environment.with_native_semantic_observations((
        attempted_operation_native_observation(plan.requests[0]),
    ))
    bundle = compiler.compile(snapshot, environment, invocation)

    assert bundle.proof_ir.attempted_operation is not None
    assert bundle.analyzed_state.recovery_ownership.status == "owned"
    assert bundle.candidate_surface.empty


def test_stale_failure_and_changed_prefix_fail_before_p2() -> None:
    state_ref = _state_ref()
    stale = _turn(replace(
        state_ref, committed_prefix_identity="q" * 64
    ))
    with pytest.raises(ValueError, match="stale"):
        compiler_invocation_context(state_ref, stale)


def test_same_tactic_from_another_event_or_state_has_new_recovery_identity() -> None:
    first_invocation, first = _compile_operation_repair()
    second_turn = _turn(
        _state_ref(), event_id="tactic-event-8", event_sequence=8
    )
    second_invocation, second = _compile_operation_repair(turn=second_turn)
    third_state = _state_ref(event=8, goal="another-goal")
    third_invocation, third = _compile_operation_repair(
        state_ref=third_state,
        turn=_turn(
            third_state, event_id="tactic-event-9", event_sequence=9
        ),
    )

    attempts = (
        first.proof_ir.attempted_operation,
        second.proof_ir.attempted_operation,
        third.proof_ir.attempted_operation,
    )
    assert all(item is not None for item in attempts)
    assert len({item.recovery_key for item in attempts}) == 3
    assert len({
        first_invocation.event_trigger.trigger_id,
        second_invocation.event_trigger.trigger_id,
        third_invocation.event_trigger.trigger_id,
    }) == 3


def test_occurrence_identity_does_not_contaminate_material_dependencies() -> None:
    state_ref = _state_ref()
    first_turn = _turn(
        state_ref, event_id="tactic-event-material-1", event_sequence=10
    )
    second_turn = _turn(
        state_ref, event_id="tactic-event-material-2", event_sequence=11
    )
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    snapshot = _snapshot(state_ref)
    empty_environment = _environment()
    first_invocation = compiler_invocation_context(state_ref, first_turn)
    second_invocation = compiler_invocation_context(state_ref, second_turn)

    first_attempt_request = compiler.plan_native_semantics(
        snapshot, empty_environment, first_invocation
    ).requests[0]
    second_attempt_request = compiler.plan_native_semantics(
        snapshot, empty_environment, second_invocation
    ).requests[0]
    first_environment = empty_environment.with_native_semantic_observations((
        attempted_operation_native_observation(first_attempt_request),
    ))
    second_environment = empty_environment.with_native_semantic_observations((
        attempted_operation_native_observation(second_attempt_request),
    ))
    first_plan = compiler.plan_resource_loads(
        snapshot, first_environment, first_invocation
    )
    second_plan = compiler.plan_resource_loads(
        snapshot, second_environment, second_invocation
    )
    assert len(first_plan.requests) == len(second_plan.requests) == 1
    assert first_plan.requests[0].identity_payload() == (
        second_plan.requests[0].identity_payload()
    )
    assert first_plan.requests[0].evidence_refs != (
        second_plan.requests[0].evidence_refs
    )

    environment = _environment("dword_ll")
    first = compiler.compile(
        snapshot,
        _resolve_native_dependencies(
            compiler, snapshot, environment, first_invocation
        ),
        first_invocation,
    )
    second = compiler.compile(
        snapshot,
        _resolve_native_dependencies(
            compiler, snapshot, environment, second_invocation
        ),
        second_invocation,
    )
    first_attempted = first.proof_ir.attempted_operation
    second_attempted = second.proof_ir.attempted_operation
    assert first_attempted is not None and second_attempted is not None
    assert first_attempted.recovery_key != second_attempted.recovery_key
    assert first.candidate_surface.actions[0].candidate_id == (
        second.candidate_surface.actions[0].candidate_id
    )
    assert first.candidate_surface.actions[0].trigger_id != (
        second.candidate_surface.actions[0].trigger_id
    )


def test_missing_or_ambiguous_exact_resource_abstains() -> None:
    _invocation, missing = _compile_operation_repair(
        environment=_environment()
    )
    _invocation, ambiguous = _compile_operation_repair(
        environment=_environment("Left.dword_ll", "Right.dword_ll")
    )
    assert missing.candidate_surface.empty
    assert ambiguous.candidate_surface.empty


@pytest.mark.parametrize(
    "tactic",
    (
        "apply Wrong.dword_ll.",
        "exact OtherLemma.",
        "exact dword_ll; smt().",
        "exact dword_ll. smt().",
        "apply dword_ll. rewrite other_fact.",
        "exact dword_ll (* hidden route *).",
    ),
)
def test_changed_operation_theorem_or_route_changing_repair_is_rejected(
    tactic: str,
) -> None:
    malicious = _synthetic_recovery_feature(
        "synthetic.malicious-recovery", emit_tactic=tactic
    )
    _invocation, bundle = _compile_operation_repair(
        features=(malicious,), environment=_environment()
    )
    assert bundle.analyzed_state.recovery_ownership.owner_feature_id == (
        "synthetic.malicious-recovery"
    )
    assert bundle.candidate_surface.empty
    assert bundle.candidate_surface.audit_reasons == (
        "recovery_candidate_changed_operation_or_resource",
    )


def test_attempted_operation_accepts_one_nested_qualified_application() -> None:
    state_ref = _state_ref()
    turn = _turn(
        state_ref,
        tactic="call (Alossless_F (<: D2(O).O) _).",
        error="wrong number of arguments for Alossless_F",
    )
    invocation = compiler_invocation_context(state_ref, turn)
    compiler = ProofStateCompiler(features=(operation_binding_repair_feature(),))
    snapshot = _snapshot(state_ref)
    environment = _environment()
    request = compiler.plan_native_semantics(
        snapshot, environment, invocation
    ).requests[0]
    environment = environment.with_native_semantic_observations((
        attempted_operation_native_observation(
            request, failure_kind="wrong_argument_kind"
        ),
    ))
    bundle = compiler.compile(
        snapshot, environment, invocation
    )
    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None
    assert attempted.operation == "call"
    assert attempted.resource == "Alossless_F"


def test_zero_one_and_multiple_recovery_owners_are_order_independent() -> None:
    state_ref = _state_ref()
    turn = _turn(state_ref)
    snapshot = _snapshot(state_ref)
    invocation = compiler_invocation_context(state_ref, turn)
    environment = _environment("dword_ll")

    zero = ProofStateCompiler().compile(snapshot, environment, invocation)
    assert zero.analyzed_state.recovery_ownership.status == "unclaimed"
    assert zero.candidate_surface.empty

    one_compiler = ProofStateCompiler(features=(
        operation_binding_repair_feature(),
    ))
    one = one_compiler.compile(
        snapshot,
        _resolve_native_dependencies(
            one_compiler, snapshot, environment, invocation
        ),
        invocation,
    )
    assert one.analyzed_state.recovery_ownership.status == "owned"
    assert one.analyzed_state.recovery_ownership.owner_feature_id == (
        OPERATION_BINDING_REPAIR_FEATURE_ID
    )
    assert len(one.candidate_surface.actions) == 1

    second = _synthetic_recovery_feature("synthetic.second-recovery")
    observed = []
    for features in (
        (operation_binding_repair_feature(), second),
        (second, operation_binding_repair_feature()),
    ):
        conflict_compiler = ProofStateCompiler(features=features)
        conflict = conflict_compiler.compile(
            snapshot,
            _resolve_native_dependencies(
                conflict_compiler, snapshot, environment, invocation
            ),
            invocation,
        )
        observed.append(conflict.analyzed_state.recovery_ownership)
        assert conflict.candidate_surface.empty
        assert conflict.candidate_surface.audit_reasons == (
            "multiple_recovery_owners",
        )
    assert observed[0] == observed[1]
    assert observed[0].status == "conflict"
    assert observed[0].claimant_feature_ids == (
        OPERATION_BINDING_REPAIR_FEATURE_ID,
        "synthetic.second-recovery",
    )


def test_one_feature_cannot_claim_one_recovery_twice_with_new_evidence() -> None:
    invocation, bundle = _compile_operation_repair(features=())
    attempted = bundle.proof_ir.attempted_operation
    assert attempted is not None
    claim = RecoveryClaim(
        feature_id="synthetic.duplicate-owner",
        recovery_key=attempted.recovery_key,
        attempt_id=attempted.attempt_id,
        occurrence_identity=attempted.occurrence_identity,
        trigger_id=attempted.trigger_id,
        operation_family=attempted.operation_family,
        selected_resource=attempted.exact_resource,
        resource_match_kind="exact",
        allowed_output_kinds=("action",),
        preservation_witness=exact_operation_resource_witness(
            attempted.operation_family,
            attempted.exact_resource,
        ),
        evidence_refs=attempted.evidence_refs,
    )
    extra = EvidenceRef(
        evidence_id="synthetic.extra-evidence",
        source_kind="loaded_declaration",
        source_ref="recovery.ec#extra",
        source_sha256="d" * 64,
    )
    ownership = resolve_recovery_ownership(
        bundle.proof_ir,
        invocation,
        (claim, replace(claim, evidence_refs=claim.evidence_refs + (extra,))),
    )
    assert ownership.status == "inconsistent"
    assert ownership.audit_reason == "duplicate_recovery_claim"


def test_current_failure_delivery_is_one_shot_and_bounded() -> None:
    invocation, bundle = _compile_operation_repair()
    assembly = compiler_assembly_for_profile(
        OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
    )
    assert assembly is not None
    action = bundle.candidate_surface.actions[0]
    certification = CertificationResult(
        candidate_id=action.candidate_id,
        state_ref=bundle.state_ref,
        policy=action.certification_policy,
        intent=action.intent,
        payload_sha256=frozen_json_sha256(action.payload),
        accepted=True,
        verification_ref="tactic.preflight.produced:recovery@sha1:" + "c" * 40,
        checked_effect=freeze_json_object({
            "goal_after_closed": True,
            "goal_after_remaining": 0,
        }),
    )
    first = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        assembly.manifest,
        triggers=invocation.triggers,
    )
    repeated = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        assembly.manifest,
        triggers=invocation.triggers,
        previously_presented=frozenset(first.presented_delivery_ids),
    )
    assert len(first.action_surface.actions) == 1
    assert 0 < first.markdown_bytes <= 520
    assert repeated.action_surface.empty
    assert repeated.markdown_bytes == 0
    assert repeated.decisions[0].reason == "delivery_lifetime_suppressed"


def test_delivery_catalog_fails_closed_on_unknown_missing_and_duplicate_policy() -> None:
    feature = _synthetic_recovery_feature("synthetic.delivery")
    catalog = FeatureCatalog(definitions=(feature,))
    with pytest.raises(ValueError, match="requires delivery policy IDs"):
        CompilerProfile(
            profile_id="missing-policy",
            activations=(FeatureActivation("synthetic.delivery", TREATMENT),),
        )

    unknown = CompilerProfile(
        profile_id="unknown-policy",
        activations=(FeatureActivation("synthetic.delivery", TREATMENT),),
        delivery_policy_ids=("not-registered",),
    )
    with pytest.raises(ValueError, match="unknown policies"):
        assemble_compiler_profile(
            unknown, catalog, DeliveryPolicyCatalog()
        )

    policies = tuple(
        DeliveryPolicyDefinition(
            policy_id=policy_id,
            rule=failure_linked_repair_rule(),
            max_items=1,
            max_markdown_bytes=520,
            compatible_feature_ids=("synthetic.delivery",),
            compatibility_contract="synthetic duplicate ownership",
            rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS,
        )
        for policy_id in ("duplicate-a", "duplicate-b")
    )
    duplicate = CompilerProfile(
        profile_id="duplicate-policy",
        activations=(FeatureActivation("synthetic.delivery", TREATMENT),),
        delivery_policy_ids=("duplicate-a", "duplicate-b"),
    )
    with pytest.raises(ValueError, match="duplicate delivery ownership"):
        assemble_compiler_profile(
            duplicate,
            catalog,
            DeliveryPolicyCatalog(definitions=policies),
        )


def test_delivery_plan_identity_includes_policy_audit_contract() -> None:
    policy = DeliveryPolicyDefinition(
        policy_id="identity-policy",
        rule=failure_linked_repair_rule(),
        max_items=1,
        max_markdown_bytes=520,
        compatible_feature_ids=("synthetic.identity",),
        compatibility_contract="identity test",
        rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS,
    )
    changed = replace(
        policy,
        rejection_audit_reasons=BASE_POLICY_REJECTION_REASONS + (
            "feature_specific_rejection",
        ),
    )
    first = ResolvedDeliveryPlan(
        profile_id="identity-plan",
        policies=(policy,),
        feature_policy_bindings=(("synthetic.identity", policy.policy_id),),
    )
    second = ResolvedDeliveryPlan(
        profile_id="identity-plan",
        policies=(changed,),
        feature_policy_bindings=(("synthetic.identity", changed.policy_id),),
    )
    assert first.plan_sha256 != second.plan_sha256


def test_m05_is_the_only_sc2_slice_and_is_held_out_of_production() -> None:
    features = default_feature_catalog()
    route_selecting = tuple(
        definition
        for definition in features.definitions
        if any(
            contract.strategy_class == ROUTE_SELECTING
            for contract in definition.spec.strategy_contracts
        )
    )
    assert tuple(item.spec.feature_id for item in route_selecting) == (
        LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID,
    )
    assert route_selecting[0].spec.gate.status == "hold"

    policies = default_delivery_policy_catalog()
    assert not any(
        LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID
        in policy.compatible_feature_ids
        for policy in policies.definitions
    )
    assert not any(
        activation.feature_id == LOSSLESSNESS_CERTIFICATE_APPLICATION_FEATURE_ID
        for profile in COMPILER_PROFILES.values()
        for activation in profile.activations
    )


def test_m07_and_new_sc2_profile_rows_cannot_assemble() -> None:
    assert not tuple(
        (PACKAGE / "features/probability_theorem_application").glob("*.py")
    )
    assert compiler_assembly_for_profile(
        "l4_proof_state_compiler_v2_m07"
    ) is None

    invented_m07 = CompilerProfile(
        profile_id="invented-m07",
        activations=(FeatureActivation(
            "probability_theorem_application", TREATMENT
        ),),
        delivery_policy_ids=(OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,),
    )
    with pytest.raises(ValueError, match="unknown features"):
        assemble_compiler_profile(
            invented_m07,
            default_feature_catalog(),
            default_delivery_policy_catalog(),
        )

    sc2_contract = StrategyContract(
        strategy_class=ROUTE_SELECTING,
        rationale="synthetic route choice",
        introduced_choice="synthetic_theorem",
    )
    sc2 = FeatureDefinition(
        spec=FeatureSpec(
            feature_id="synthetic.sc2",
            gate=ExperimentGate(
                status="candidate",
                evidence_ledger_ids=("SYNTHETIC-SC2",),
                experiment_id="synthetic-sc2",
            ),
            correctness_contract="synthetic SC2",
            provenance_contract="synthetic",
            native_semantic_dependencies=(),
            shannon_delta_contract="synthetic route-selection sentinel",
            lexical_prefilter_contract="none",
            required_ir_capabilities=("AnalyzedProofState",),
            certification_policy="exact_tactic_preflight",
            strategy_contracts=(sc2_contract,),
        ),
        surface_lowerers=(lambda state, invocation: SurfaceContribution(),),
    )
    profile = CompilerProfile(
        profile_id="invented-sc2-profile",
        activations=(FeatureActivation("synthetic.sc2", TREATMENT),),
        delivery_policy_ids=(OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,),
    )
    with pytest.raises(ValueError, match="missing compatible delivery policy"):
        assemble_compiler_profile(
            profile,
            FeatureCatalog(definitions=(sc2,)),
            default_delivery_policy_catalog(),
        )


def test_m04_standing_treatment_and_failure_reactivation_fail_closed() -> None:
    assert compiler_assembly_for_profile(
        "l4_proof_state_compiler_v2_operation_readiness"
    ) is None
    for policy_id in (
        INTRINSIC_CHANGED_FACT_POLICY_ID,
        OPERATION_BINDING_REPAIR_ONCE_POLICY_ID,
    ):
        profile = CompilerProfile(
            profile_id=f"invented-m04-{policy_id}",
            activations=(FeatureActivation(
                PROGRAM_OPERATION_READINESS_FEATURE_ID, TREATMENT
            ),),
            delivery_policy_ids=(policy_id,),
        )
        with pytest.raises(ValueError, match="missing compatible delivery policy"):
            assemble_compiler_profile(
                profile,
                default_feature_catalog(),
                default_delivery_policy_catalog(),
            )


def test_physical_removal_of_recovery_slice_fails_profile_assembly_only() -> None:
    catalog = default_feature_catalog()
    without_recovery = FeatureCatalog(definitions=tuple(
        item for item in catalog.definitions
        if item.spec.feature_id != OPERATION_BINDING_REPAIR_FEATURE_ID
    ))
    profile = COMPILER_PROFILES[OPERATION_BINDING_REPAIR_TREATMENT_PROFILE]
    with pytest.raises(ValueError, match="unknown features"):
        assemble_compiler_profile(
            profile, without_recovery, default_delivery_policy_catalog()
        )
    assert compiler_assembly_for_profile(
        "l4_proof_state_compiler_v2_m05"
    ) is None


def test_synthetic_recovery_requires_no_generic_boundary_changes() -> None:
    synthetic_id = "synthetic.second-recovery"
    for path in (
        ROOT / "workflow/proof_node_manager.py",
        ROOT / "workflow/proof_state_compiler/service.py",
        ROOT / "workflow/proof_management/turn_view.py",
        ROOT / "core/easycrypt/proof_state_compiler/backend/presentation.py",
    ):
        assert synthetic_id not in path.read_text()


def test_profile_has_no_inline_delivery_rules_or_budgets() -> None:
    fields = CompilerProfile.__dataclass_fields__
    assert tuple(fields) == (
        "profile_id",
        "activations",
        "delivery_policy_ids",
    )
    assert "optional_advisory" not in (
        ROOT / "workflow/proof_state_compiler/activation.py"
    ).read_text()
