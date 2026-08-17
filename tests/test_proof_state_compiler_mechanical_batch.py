from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    LoadedDeclaration,
    LoadedSourceUnit,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.backend import (
    action_surface_payload,
    admit_action_surface,
)
from core.easycrypt.proof_state_compiler.contracts import (
    APPLICATION_APPLICABLE,
    APPLICATION_INAPPLICABLE,
    APPLICATION_INDETERMINATE,
    CertificationResult,
    CompilerTurnEvidence,
    NativeAttemptDiagnosticQuery,
    NativeSemanticPlanningReport,
    NativeSemanticPlanningStage,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
    frozen_json_sha256,
)
from core.easycrypt.proof_state_compiler.features.accepted_contract_retention import (
    accepted_contract_retention_feature,
)
from core.easycrypt.proof_state_compiler.features.program_operation_readiness import (
    program_operation_readiness_feature,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair import (
    operation_binding_repair_feature,
)
from workflow.proof_state_compiler.configuration import (
    COMPILER_PROFILES,
    compiler_assembly_for_profile,
)
from workflow.proof_state_compiler.activation import AUDIT
from workflow.proof_state_compiler.profile_ids import (
    M04_AUDIT_PROFILE,
    M09_AUDIT_PROFILE,
    OPERATION_BINDING_REPAIR_AUDIT_PROFILE,
    OPERATION_BINDING_REPAIR_TREATMENT_PROFILE,
)
from tests.proof_state_compiler_test_support import (
    attempted_operation_native_observation,
    b2_losslessness_native_observation,
    bare_native_observation,
    instruction,
    module_path,
    native_state,
    program,
    typed_node,
    probability_multislot_native_observation,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.losslessness_module_repair import (
    LOSSLESSNESS_MODULE_REPAIR_NATIVE_PRODUCER_ID,
)
from core.easycrypt.proof_state_compiler.features.operation_binding_repair.probability_multislot_repair import (
    PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID,
)


ROOT = Path(__file__).resolve().parents[1]
M07_CASE = json.loads((
    ROOT / "tests/fixtures/proof_state_compiler/m07_step2_1_theorem.json"
).read_text())


def _state_ref(*, prefix: str = "p" * 64) -> StateRef:
    return StateRef(
        session_id="mechanical-batch-fixture",
        state_version=7,
        goal_identity="mechanical-goal",
        goal_identity_required=True,
        committed_prefix_identity=prefix,
    )


def _snapshot(
    lines: list[str],
    *,
    prefix: str = "p" * 64,
    native_override=None,
):
    state_ref = _state_ref(prefix=prefix)
    return AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="mechanical.fixture",
            authority="prover.workspace_view.produced",
            source_sha256="a" * 64,
            artifact_ref="fixtures/mechanical-view.json",
            source_event_id="view-event-7",
            source_event_sequence=7,
            authoritative=True,
        ),
        target=TargetRef(source_file="eval/mechanical.ec", lemma="fixture"),
        transition=TransitionRef(
            kind="inspected",
            previous_state_ref=state_ref,
            result_artifact_ref="fixtures/mechanical-view.json",
        ),
        goal_lines=lines,
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_override or native_state(
            state_ref,
            formula=typed_node("true", "true"),
        ),
    )


def _program_native(
    *,
    left: tuple[tuple[str, str, str], ...] = (),
    right: tuple[tuple[str, str, str], ...] = (),
    single: tuple[tuple[str, str, str], ...] = (),
    goal_kind: str = "pure",
    formula: dict | None = None,
):
    state_ref = _state_ref()
    values = []
    for side, specs in (("single", single), ("left", left), ("right", right)):
        if not specs:
            continue
        values.append(program(side, tuple(
            instruction(
                kind,
                text,
                side=side,
                position=index,
                procedure=procedure,
            )
            for index, (kind, text, procedure) in enumerate(specs, start=1)
        )))
    return native_state(
        state_ref,
        judgment_kind=goal_kind,
        formula=formula or typed_node("true", "true"),
        programs=tuple(values),
    )


def _turn(
    snapshot,
    *,
    tactic: str,
    outcome: str,
    error: str = "",
    prefix: str | None = None,
) -> CompilerTurnEvidence:
    post_state_ref = snapshot.state_ref
    if prefix is not None:
        post_state_ref = replace(
            post_state_ref,
            committed_prefix_identity=prefix,
        )
    return CompilerTurnEvidence(
        source_event_id="tactic-event-7",
        source_event_sequence=6,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/result-7.json",
        artifact_hash="b" * 64,
        hash_algorithm="sha256",
        post_state_ref=post_state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": tactic}),
        outcome_kind=outcome,
        proof_state_effect="changed" if outcome == "accepted" else "unchanged",
        structured_error=error,
    )


def _environment_from_text(text: str) -> CompilationEnvironment:
    return CompilationEnvironment(
        environment_id="mechanical-source",
        source_units=(LoadedSourceUnit(
            source_ref="eval/mechanical.ec",
            source_sha256=hashlib.sha256(text.encode()).hexdigest(),
            text=text,
        ),),
    )


def _loaded_declaration(symbol: str, declaration: str) -> LoadedDeclaration:
    return LoadedDeclaration(
        symbol=symbol,
        source_ref=f"easycrypt:print:mechanical.ec#{symbol}",
        declaration_sha256=hashlib.sha256(declaration.encode()).hexdigest(),
        declaration=declaration,
    )


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["Current goal", "(1) x <@ Foo.bar();"], "structurally legal"),
        (
            ["Current goal", "(1) x <@ Foo.bar();", "(2) while (b) {"],
            "structurally blocked",
        ),
    ],
)
def test_operation_readiness_reports_only_current_structural_fact(
    lines: list[str], expected: str
) -> None:
    specs = (("call", "x <@ Foo.bar()", "Foo.bar"),)
    if expected == "structurally blocked":
        specs += (("while", "while (b) {}", ""),)
    snapshot = _snapshot(lines, native_override=_program_native(single=specs))
    bundle = ProofStateCompiler(
        features=(program_operation_readiness_feature(),)
    ).compile(snapshot, CompilationEnvironment("empty", ()))

    assert len(bundle.candidate_surface.diagnostics) == 1
    message = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert expected in message
    assert "should" not in message and "next" not in message


@pytest.mark.parametrize(
    "lines",
    [
        ["Current goal", "(1) x <- 0;"],
        ["Current goal", "no program frontier"],
    ],
)
def test_operation_readiness_abstains_on_irrelevant_or_unknown_state(
    lines: list[str],
) -> None:
    native = (
        _program_native(single=(("assign", "x <- 0", ""),))
        if "x <- 0" in lines[-1]
        else native_state(_state_ref())
    )
    bundle = ProofStateCompiler(
        features=(program_operation_readiness_feature(),)
    ).compile(
        _snapshot(lines, native_override=native),
        CompilationEnvironment("empty", ()),
    )
    assert bundle.candidate_surface.empty


def test_operation_readiness_parses_aligned_call_blocked_by_if_tail() -> None:
    lines = [
        "Current goal",
        "x <- 0                 (1-------)  x <- 0",
        "b <@                   (2-------)  b <@",
        "  Left.Game.main()     (  ------)    Right.Game.main()",
        "if (b) {               (3-------)  if (b) {",
        "  x <- 1               (3.1-----)    x <- 1",
        "}                      (3-------)  }",
    ]
    bundle = ProofStateCompiler(
        features=(program_operation_readiness_feature(),)
    ).compile(
        _snapshot(
            lines,
            native_override=_program_native(
                left=(
                    ("assign", "x <- 0", ""),
                    ("call", "b <@ Left.Game.main()", "Left.Game.main"),
                    ("if", "if (b) {}", ""),
                ),
                right=(
                    ("assign", "x <- 0", ""),
                    ("call", "b <@ Right.Game.main()", "Right.Game.main"),
                    ("if", "if (b) {}", ""),
                ),
                goal_kind="equivalence_statement",
                formula=typed_node(
                    "equivalence_statement",
                    "equiv[programs : true ==> true]",
                    children=(typed_node("true", "true"),) * 2,
                    child_roles=("precondition", "postcondition"),
                ),
            ),
        ),
        CompilationEnvironment("empty", ()),
    )

    assert len(bundle.proof_ir.statements) == 6
    assert len(bundle.candidate_surface.diagnostics) == 1
    message = bundle.candidate_surface.diagnostics[0].diagnostic.primary
    assert "call is structurally blocked" in message
    assert "if statement (3) if (b)" in message


def test_operation_readiness_aligned_sides_fail_closed_when_frontiers_differ() -> None:
    lines = [
        "Current goal",
        "b <@ Left.Game.main()   (1-------)  x <- 0",
        "if (b) {               (2-------)  if (b) {",
    ]
    bundle = ProofStateCompiler(
        features=(program_operation_readiness_feature(),)
    ).compile(
        _snapshot(
            lines,
            native_override=_program_native(
                left=(
                    ("call", "b <@ Left.Game.main()", "Left.Game.main"),
                    ("if", "if (b) {}", ""),
                ),
                right=(
                    ("assign", "x <- 0", ""),
                    ("if", "if (b) {}", ""),
                ),
                goal_kind="equivalence_statement",
                formula=typed_node(
                    "equivalence_statement",
                    "equiv[programs : true ==> true]",
                    children=(typed_node("true", "true"),) * 2,
                    child_roles=("precondition", "postcondition"),
                ),
            ),
        ),
        CompilationEnvironment("empty", ()),
    )
    assert bundle.candidate_surface.empty


def test_operation_readiness_relational_one_side_missing_fails_closed() -> None:
    lines = [
        "Current goal",
        "&1 (left ) : {}",
        "&2 (right) : {}",
        "b <@ Left.Game.main()   (1-------)",
    ]
    bundle = ProofStateCompiler(
        features=(program_operation_readiness_feature(),)
    ).compile(
        _snapshot(
            lines,
            native_override=_program_native(
                left=(("call", "b <@ Left.Game.main()", "Left.Game.main"),),
                goal_kind="equivalence_statement",
                formula=typed_node(
                    "equivalence_statement",
                    "equiv[programs : true ==> true]",
                    children=(typed_node("true", "true"),) * 2,
                    child_roles=("precondition", "postcondition"),
                ),
            ),
        ),
        CompilationEnvironment("empty", ()),
    )
    assert bundle.proof_ir.goal.kind == "equiv"
    assert bundle.candidate_surface.empty


def test_operation_readiness_is_audit_only_and_zero_agent_bytes() -> None:
    snapshot = _snapshot(
        ["Current goal", "(1) x <@ Foo.bar();"],
        native_override=_program_native(
            single=(("call", "x <@ Foo.bar()", "Foo.bar"),)
        ),
    )
    bundle = ProofStateCompiler(
        features=(program_operation_readiness_feature(),)
    ).compile(snapshot, CompilationEnvironment("empty", ()))
    audit = compiler_assembly_for_profile(M04_AUDIT_PROFILE)
    treatment = compiler_assembly_for_profile(
        "l4_proof_state_compiler_v2_operation_readiness"
    )
    assert audit is not None and treatment is None
    refresh = compiler_invocation_context(
        snapshot.state_ref, source_event_id="view-event-7"
    )
    audit_result = admit_action_surface(
        bundle.candidate_surface, (), audit.manifest, triggers=refresh.triggers
    )
    assert audit_result.markdown_bytes == 0 and audit_result.action_surface.empty
    assert bundle.candidate_surface.diagnostics
    readiness_activations = tuple(
        (profile_id, activation.mode)
        for profile_id, profile in COMPILER_PROFILES.items()
        for activation in profile.activations
        if activation.feature_id == "program_operation_readiness"
    )
    assert (M04_AUDIT_PROFILE, AUDIT) in readiness_activations
    assert all(mode == AUDIT for _profile_id, mode in readiness_activations)


def _retention_bundle(formula: str, *, boundary: str = "while"):
    lines = [
        "Current goal",
        f"(1) {boundary} (b) {{" if boundary == "while" else "(1) x <@ F.f();",
        "--------",
        formula,
    ]
    native_formula = typed_node(
        "and" if "/\\" in formula else "equality",
        formula,
        children=(
            typed_node("local", "x", type_text="int"),
            typed_node("integer", "0", type_text="int"),
        ) if "/\\" not in formula else (),
    )
    statement = (
        ("while", "while (b) {}", "")
        if boundary == "while"
        else ("call", "x <@ F.f()", "F.f")
    )
    snapshot = _snapshot(
        lines,
        native_override=_program_native(
            single=(statement,), formula=native_formula
        ),
    )
    evidence = _turn(
        snapshot,
        tactic="while (x = 0 /\\ y = 1).",
        outcome="accepted",
    )
    invocation = compiler_invocation_context(snapshot.state_ref, evidence)
    bundle = ProofStateCompiler(
        features=(accepted_contract_retention_feature(),)
    ).compile(snapshot, CompilationEnvironment("empty", ()), invocation)
    return snapshot, invocation, bundle


def test_contract_retention_reports_only_dropped_original_conjunct() -> None:
    _snapshot_value, invocation, bundle = _retention_bundle("x = 0")
    assert not bundle.candidate_surface.empty
    candidate = bundle.candidate_surface.diagnostics[0]
    assert "y = 1" in candidate.diagnostic.primary
    assert "strengthen" not in candidate.diagnostic.primary.lower()
    assert candidate.trigger_id == invocation.event_trigger.trigger_id


def test_contract_retention_abstains_when_all_preserved_or_boundary_differs() -> None:
    assert _retention_bundle("x = 0 /\\ y = 1")[2].candidate_surface.empty
    assert _retention_bundle("x = 0", boundary="call")[2].candidate_surface.empty


def test_contract_retention_consumes_only_canonical_program_coordinate() -> None:
    lines = [
        "Current goal",
        "&1 (left ) : {}",
        "&2 (right) : {}",
        "x <@ F.f();             (1-------)  while (b) {",
        "--------",
        "x = 0",
    ]
    truth = typed_node("true", "true")
    snapshot = _snapshot(
        lines,
        native_override=_program_native(
            left=(("call", "x <@ F.f()", "F.f"),),
            right=(("while", "while (b) {}", ""),),
            goal_kind="equivalence_statement",
            formula=typed_node(
                "equivalence_statement",
                "x = 0",
                children=(truth, truth),
                child_roles=("precondition", "postcondition"),
            ),
        ),
    )
    evidence = _turn(
        snapshot,
        tactic="while (x = 0 /\\ y = 1).",
        outcome="accepted",
    )
    invocation = compiler_invocation_context(snapshot.state_ref, evidence)

    bundle = ProofStateCompiler(
        features=(accepted_contract_retention_feature(),)
    ).compile(snapshot, CompilationEnvironment("empty", ()), invocation)

    assert bundle.analyzed_state.coordinate.status == "unknown"
    assert bundle.candidate_surface.empty


def test_contract_retention_rejects_stale_prefix_before_p2() -> None:
    snapshot = _snapshot(["Current goal", "(1) while (b) {"])
    evidence = _turn(
        snapshot,
        tactic="while (x = 0 /\\ y = 1).",
        outcome="accepted",
        prefix="q" * 64,
    )
    with pytest.raises(ValueError, match="stale"):
        compiler_invocation_context(snapshot.state_ref, evidence)


def test_contract_retention_has_audit_profile_but_no_treatment_profile() -> None:
    assembly = compiler_assembly_for_profile(M09_AUDIT_PROFILE)
    assert assembly is not None
    assert assembly.delivery_plan.admitted_feature_ids == ()
    retention_activations = tuple(
        (profile_id, activation.mode)
        for profile_id, profile in COMPILER_PROFILES.items()
        for activation in profile.activations
        if activation.feature_id == "accepted_contract_retention"
    )
    assert (M09_AUDIT_PROFILE, AUDIT) in retention_activations
    assert all(mode == AUDIT for _profile_id, mode in retention_activations)


def _failure_bundle(
    *, tactic: str, error: str, environment: CompilationEnvironment,
    goal_lines: list[str] | None = None,
    native_observation_transform=None,
):
    lines = goal_lines or ["Current goal", "--------", "true"]
    snapshot = _snapshot(
        lines,
        native_override=_native_failure_fixture(lines),
    )
    evidence = _turn(snapshot, tactic=tactic, outcome="rejected", error=error)
    invocation = compiler_invocation_context(snapshot.state_ref, evidence)
    compiler = ProofStateCompiler(
        features=(operation_binding_repair_feature(),)
    )
    target = _fixture_losslessness_target(lines)
    budget = compiler.native_planning_budget
    planning_stages = []
    for stage_name in ("pre_resource", "post_resource"):
        plan = compiler.plan_native_semantics(
            snapshot,
            environment,
            invocation,
            budget,
        )
        budget_after = budget.consume(plan)
        planning_stages.append(NativeSemanticPlanningStage.from_plan(
            stage=stage_name,
            plan=plan,
            budget_after=budget_after,
        ))
        budget = budget_after
        if not plan.requests:
            break
        observations = []
        for request in plan.requests:
            if isinstance(request.query, NativeAttemptDiagnosticQuery):
                observations.append(attempted_operation_native_observation(
                    request,
                    failure_kind=_fixture_native_failure_kind(error),
                ))
            elif request.producer_id == LOSSLESSNESS_MODULE_REPAIR_NATIVE_PRODUCER_ID:
                observation = b2_losslessness_native_observation(
                    request,
                    target_procedure=target,
                )
                observations.append(
                    native_observation_transform(observation)
                    if native_observation_transform is not None
                    else observation
                )
            elif request.producer_id == PROBABILITY_MULTISLOT_REPAIR_NATIVE_PRODUCER_ID:
                observation = probability_multislot_native_observation(
                    request,
                    result_formula=_fixture_formula(lines),
                )
                observations.append(
                    native_observation_transform(observation)
                    if native_observation_transform is not None
                    else observation
                )
            else:
                observations.append(bare_native_observation(
                    request,
                    resolved_head=f"Top.{request.query.application_term}",
                ))
        environment = environment.with_native_semantic_observations(
            tuple(observations)
        )
    return snapshot, invocation, compiler.compile(
        snapshot,
        environment,
        invocation,
        native_budget=budget,
        planning_report=NativeSemanticPlanningReport(
            state_ref=snapshot.state_ref,
            stages=tuple(planning_stages),
        ),
    )


def _fixture_native_failure_kind(error: str) -> str:
    if "unknown identifier" in error:
        return "proof_term_lookup_failure"
    if "cannot infer module" in error:
        return "cannot_infer_module"
    if "wrong number of arguments" in error or "arity mismatch" in error:
        return "wrong_argument_kind"
    return "unowned_native_failure"


def _native_failure_fixture(lines: list[str]):
    """Typed fixtures corresponding to the archived text shown in each case."""

    state_ref = _state_ref()
    formula_text = _fixture_formula(lines)
    if lines == M07_CASE["goal_lines"]:
        left, right = formula_text.split(" <= ", 1)
        return native_state(
            state_ref,
            judgment_kind="pure",
            formula=typed_node(
                "operator_application",
                formula_text,
                children=(
                    typed_node(
                        "probability",
                        left,
                        type_text="real",
                        memory="&m",
                        procedure="CCA_game(A, RealOrcls(StLSke(St))).main",
                        procedure_module=module_path(
                            "CCA_game(A, RealOrcls(StLSke(St)))",
                            module_path("A"),
                            module_path(
                                "RealOrcls(StLSke(St))",
                                module_path(
                                    "StLSke(St)",
                                    module_path("St"),
                                ),
                            ),
                        ),
                    ),
                    typed_node("operator_application", right, type_text="real"),
                ),
                operator="Top.RealOrder.le",
                relation_operator="<=",
            ),
        )
    target = _fixture_losslessness_target(lines)
    truth = typed_node("true", "true")
    if target and "(1)" not in formula_text:
        return native_state(
            state_ref,
            judgment_kind="bounded_hoare_function",
            formula=typed_node(
                "bounded_hoare_function",
                f"pre = true {target} [=] 1%r post = true",
                children=(
                    truth,
                    truth,
                    typed_node(
                        "operator_application",
                        "1%r",
                        type_text="real",
                    ),
                ),
                child_roles=("precondition", "postcondition", "bound"),
                procedure=target,
                comparison="=",
                lossless=True,
            ),
        )
    if target:
        return native_state(
            state_ref,
            judgment_kind="hoare_statement",
            formula=typed_node(
                "hoare_statement",
                formula_text,
                children=(truth, truth),
                child_roles=("precondition", "postcondition"),
            ),
            programs=(program("single", (instruction(
                "call",
                f"b <@ {target}()",
                side="single",
                position=1,
                procedure=target,
            ),)),),
        )
    return native_state(
        state_ref,
        formula=typed_node("true", formula_text or "true"),
    )


def _fixture_formula(lines: list[str]) -> str:
    try:
        start = next(
            index + 1
            for index, line in enumerate(lines)
            if len(line.strip()) >= 8 and set(line.strip()) == {"-"}
        )
    except StopIteration:
        start = 1
    parts = []
    for line in lines[start:]:
        if line.strip().startswith("[") and line.strip().endswith("]>"):
            break
        parts.append(line.strip())
    return " ".join(" ".join(parts).split())


def _fixture_losslessness_target(lines: list[str]) -> str:
    formula_text = _fixture_formula(lines)
    prefix = "pre = true "
    suffix = " [=] 1%r post = true"
    if formula_text.startswith(prefix) and suffix in formula_text:
        return formula_text[len(prefix):formula_text.index(suffix)]
    return ""


def test_failure_feedback_b1_preserves_exact_and_resource_basename() -> None:
    snapshot, invocation, bundle = _failure_bundle(
        tactic="exact AWord.dword_ll.",
        error="unknown identifier AWord.dword_ll",
        environment=_environment_from_text("lemma dword_ll : true."),
    )
    assert len(bundle.candidate_surface.actions) == 1
    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {"tactic": "exact (dword_ll)."}
    assert action.trigger_id == invocation.event_trigger.trigger_id
    assert bundle.analyzed_state.diagnostics == ()
    assert bundle.state_ref == snapshot.state_ref


def test_failure_feedback_b2_binds_same_losslessness_resource_module() -> None:
    declaration = (
        "declare axiom Alossless (O <: OMac{-A}) : "
        "islossless O.mac => islossless A(O).guess."
    )
    _snapshot_value, invocation, bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=_environment_from_text(declaration),
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            "A(F_to_MAC_Adv(D2(O).O)).guess",
            "[=] 1%r",
            "post = true",
        ],
    )

    assert len(bundle.candidate_surface.actions) == 1
    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {
        "tactic": "apply (Alossless (<: F_to_MAC_Adv(D2(O).O)) _)."
    }
    assert action.trigger_id == invocation.event_trigger.trigger_id
    assert bundle.analyzed_state.diagnostics == ()
    assert action.unresolved_premises == (
        "islossless F_to_MAC_Adv(D2(O).O).mac",
    )


def test_failure_feedback_b2_accepts_verifier_normalized_module_quantifier() -> None:
    declaration = (
        "declare axiom Alossless: forall (O <: OMac{-A}), "
        "islossless O.mac => islossless A(O).guess."
    )
    bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=CompilationEnvironment(
            "loaded-print",
            (),
            (_loaded_declaration("Alossless", declaration),),
        ),
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            "A(F_to_MAC_Adv(D2(O).O)).guess",
            "[=] 1%r",
            "post = true",
        ],
    )[2]

    assert bundle.candidate_surface.actions[0].payload.to_dict() == {
        "tactic": "apply (Alossless (<: F_to_MAC_Adv(D2(O).O)) _)."
    }


def test_failure_feedback_b2_uses_source_spelling_from_canonical_native_target() -> None:
    declaration = (
        "declare axiom Alossless (O <: OMac{-A}) : "
        "islossless O.mac => islossless A(O).guess."
    )
    bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=_environment_from_text(declaration),
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            "A(Top.F_to_MAC_Adv(Top.D2(O).O))./guess",
            "[=] 1%r",
            "post = true",
        ],
    )[2]

    assert bundle.candidate_surface.actions[0].payload.to_dict() == {
        "tactic": "apply (Alossless (<: F_to_MAC_Adv(D2(O).O)) _)."
    }
    binding = bundle.analyzed_state.bindings[0]
    assert binding.target == "A(Top.F_to_MAC_Adv(Top.D2(O).O))./guess"


@pytest.mark.parametrize(
    "native_observation_transform",
    [
        lambda observation: replace(
            observation,
            descriptor=replace(
                observation.descriptor,
                resolved_head=replace(
                    observation.descriptor.resolved_head,
                    identity="Top.AnotherCertificate",
                ),
            ),
        ),
        lambda observation: replace(
            observation,
            descriptor=replace(
                observation.descriptor,
                result=replace(
                    observation.descriptor.result,
                    procedure="Top.AnotherModule./guess",
                ),
            ),
        ),
        lambda observation: replace(
            observation,
            descriptor=replace(
                observation.descriptor,
                result_convertible_to_current_goal=False,
            ),
        ),
    ],
    ids=["wrong_head", "wrong_result_procedure", "nonconvertible_result"],
)
def test_failure_feedback_b2_abstains_on_wrong_native_descriptor(
    native_observation_transform,
) -> None:
    bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=_environment_from_text(
            "declare axiom Alossless (O <: OMac{-A}) : "
            "islossless O.mac => islossless A(O).guess."
        ),
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            "A(F_to_MAC_Adv(D2(O).O)).guess",
            "[=] 1%r",
            "post = true",
        ],
        native_observation_transform=native_observation_transform,
    )[2]

    assert bundle.candidate_surface.empty


def test_failure_feedback_b2_deduplicates_source_and_print_equivalent() -> None:
    source = (
        "axiom Alossless (O <: OMac{-A}) : "
        "islossless O.mac => islossless A(O).guess."
    )
    printed = (
        "* In [lemmas or axioms]:\n\ndeclare  axiom Alossless:\n"
        "  forall (O <: OMac{-A}), "
        "islossless O.mac => islossless A(O).guess."
    )
    environment = _environment_from_text(source)
    environment = replace(
        environment,
        loaded_declarations=(
            _loaded_declaration("Alossless", printed),
        ),
    )
    bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=environment,
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            "A(F_to_MAC_Adv(D2(O).O)).guess",
            "[=] 1%r",
            "post = true",
        ],
    )[2]

    assert len(bundle.proof_ir.resources) == 1
    assert bundle.proof_ir.resources[0].evidence_refs[0].source_kind == (
        "loaded_declaration"
    )
    assert len(bundle.candidate_surface.actions) == 1


def test_failure_feedback_b2_abstains_on_program_body_lookalike() -> None:
    declaration = (
        "axiom Alossless (O <: OMac{-A}) : "
        "islossless O.mac => islossless A(O).guess."
    )
    bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=_environment_from_text(declaration),
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            "(1) b <@ A(F_to_MAC_Adv(D2(O).O)).guess();",
            "post = true",
        ],
    )[2]
    assert bundle.candidate_surface.empty


@pytest.mark.parametrize(
    "declaration",
    [
        "declare axiom Alossless: forall (x : int), true.",
        "declare axiom Alossless: forall (O <: OMac{-A}) islossless O.mac.",
        (
            "declare axiom Alossless (O <: OMac{-A}): "
            "forall (O <: OMac{-A}), islossless O.mac => islossless A(O).guess."
        ),
    ],
)
def test_failure_feedback_b2_abstains_on_unsupported_or_duplicate_quantifier(
    declaration: str,
) -> None:
    bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=CompilationEnvironment(
            "bad-loaded-print",
            (),
            (_loaded_declaration("Alossless", declaration),),
        ),
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            "A(F_to_MAC_Adv(D2(O).O)).guess",
            "[=] 1%r",
            "post = true",
        ],
    )[2]
    assert bundle.candidate_surface.empty


@pytest.mark.parametrize(
    ("error", "failure_class"),
    [
        ("cannot infer module arguments", "b2"),
        ("wrong number of arguments: arity mismatch", "b4"),
    ],
)
def test_failure_feedback_recovers_b2_b4_from_exact_probability_binding(
    error: str, failure_class: str
) -> None:
    symbol = M07_CASE["symbol"]
    declaration = M07_CASE["declaration"]
    environment = CompilationEnvironment(
        environment_id="loaded-m07",
        source_units=(),
        loaded_declarations=(_loaded_declaration(symbol, declaration),),
    )
    _snapshot_value, invocation, bundle = _failure_bundle(
        tactic=f"apply {symbol}.",
        error=error,
        environment=environment,
        goal_lines=M07_CASE["goal_lines"],
    )
    assert len(bundle.candidate_surface.actions) == 1
    action = bundle.candidate_surface.actions[0]
    assert action.payload.to_dict() == {"tactic": M07_CASE["expected_tactic"]}
    assert action.trigger_id == invocation.event_trigger.trigger_id
    assert bundle.analyzed_state.diagnostics == ()
    applicability = bundle.analyzed_state.application_applicabilities[0]
    assert applicability.status == APPLICATION_APPLICABLE
    assert applicability.unique_checked_completion
    assert any(
        item.source_kind == "native_proof_term_descriptor"
        for item in action.evidence_refs
    )
    assert tuple(
        slot.kind for slot in bundle.analyzed_state.bindings[0].slots
    ) == ("module", "proof", "proof", "module", "proof", "memory")


@pytest.mark.parametrize(
    ("native_observation_transform", "expected_diagnostic_code"),
    [
        (
            lambda observation: replace(
                observation,
                descriptor=replace(
                    observation.descriptor,
                    resolved_head=replace(
                        observation.descriptor.resolved_head,
                        identity="Top.AnotherTheorem",
                    ),
                ),
            ),
            None,
        ),
        (
            lambda observation: replace(
                observation,
                descriptor=replace(
                    observation.descriptor,
                    result=replace(
                        observation.descriptor.result,
                        text="false",
                    ),
                    result_convertible_to_current_goal=False,
                ),
                result_formula="false",
            ),
            "application_not_applicable_in_current_state",
        ),
    ],
    ids=["wrong_head", "wrong_result"],
)
def test_failure_feedback_b24_abstains_on_wrong_native_descriptor(
    native_observation_transform,
    expected_diagnostic_code: str | None,
) -> None:
    symbol = M07_CASE["symbol"]
    bundle = _failure_bundle(
        tactic=f"apply {symbol}.",
        error="cannot infer module arguments",
        environment=CompilationEnvironment(
            environment_id="loaded-m07",
            source_units=(),
            loaded_declarations=(
                _loaded_declaration(symbol, M07_CASE["declaration"]),
            ),
        ),
        goal_lines=M07_CASE["goal_lines"],
        native_observation_transform=native_observation_transform,
    )[2]

    assert bundle.candidate_surface.actions == ()
    applicability = bundle.analyzed_state.application_applicabilities[0]
    diagnostics = bundle.candidate_surface.diagnostics
    if expected_diagnostic_code is None:
        assert applicability.status == APPLICATION_INDETERMINATE
        assert diagnostics == ()
    else:
        assert applicability.status == APPLICATION_INAPPLICABLE
        assert len(diagnostics) == 1
        diagnostic = diagnostics[0].diagnostic
        assert diagnostic.code == expected_diagnostic_code
        assert diagnostic.placeholder_shape == ""


def test_failure_feedback_b24_uses_native_relation_not_result_text() -> None:
    symbol = M07_CASE["symbol"]
    bundle = _failure_bundle(
        tactic=f"apply {symbol}.",
        error="cannot infer module arguments",
        environment=CompilationEnvironment(
            environment_id="loaded-m07",
            source_units=(),
            loaded_declarations=(
                _loaded_declaration(symbol, M07_CASE["declaration"]),
            ),
        ),
        goal_lines=M07_CASE["goal_lines"],
        native_observation_transform=lambda observation: replace(
            observation,
            descriptor=replace(
                observation.descriptor,
                result=replace(
                    observation.descriptor.result,
                    text="printer-preserved-type-alias",
                ),
            ),
            result_formula="printer-preserved-type-alias",
        ),
    )[2]

    assert len(bundle.candidate_surface.actions) == 1


def test_failure_feedback_b24_requires_bare_same_resource_apply() -> None:
    symbol = M07_CASE["symbol"]
    bundle = _failure_bundle(
        tactic=f"apply ({symbol} St A).",
        error="wrong number of arguments: arity mismatch",
        environment=CompilationEnvironment(
            environment_id="loaded-m07",
            source_units=(),
            loaded_declarations=(
                _loaded_declaration(symbol, M07_CASE["declaration"]),
            ),
        ),
        goal_lines=M07_CASE["goal_lines"],
    )[2]

    assert bundle.candidate_surface.empty


def test_failure_feedback_abstains_when_b1_resource_is_ambiguous() -> None:
    declarations = (
        _loaded_declaration("Left.dword_ll", "lemma dword_ll : true."),
        _loaded_declaration("Right.dword_ll", "lemma dword_ll : true."),
    )
    bundle = _failure_bundle(
        tactic="exact Wrong.dword_ll.",
        error="unknown identifier Wrong.dword_ll",
        environment=CompilationEnvironment("ambiguous", (), declarations),
    )[2]
    assert bundle.candidate_surface.empty


@pytest.mark.parametrize(
    "error",
    [
        "call target mismatch for procedure",  # B3
        "rewrite transform did not match",  # B5
        "unsolved side condition premise",  # B7
        "unexpected parser failure",  # unclassified
    ],
)
def test_failure_feedback_abstains_on_b3_b5_b7_and_unclassified_errors(
    error: str,
) -> None:
    bundle = _failure_bundle(
        tactic="exact Wrong.dword_ll.",
        error=error,
        environment=_environment_from_text("lemma dword_ll : true."),
    )[2]
    assert bundle.candidate_surface.empty


def test_failure_feedback_requires_certification_and_is_one_compact_item() -> None:
    snapshot, invocation, bundle = _failure_bundle(
        tactic="exact AWord.dword_ll.",
        error="unknown identifier AWord.dword_ll",
        environment=_environment_from_text("lemma dword_ll : true."),
    )
    audit = compiler_assembly_for_profile(
        OPERATION_BINDING_REPAIR_AUDIT_PROFILE
    )
    treatment = compiler_assembly_for_profile(
        OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
    )
    assert audit is not None and treatment is not None
    audit_result = admit_action_surface(
        bundle.candidate_surface, (), audit.manifest, triggers=invocation.triggers
    )
    rejected = admit_action_surface(
        bundle.candidate_surface, (), treatment.manifest,
        triggers=invocation.triggers,
    )
    action = bundle.candidate_surface.actions[0]
    certification = CertificationResult(
        candidate_id=action.candidate_id,
        state_ref=snapshot.state_ref,
        policy=action.certification_policy,
        intent=action.intent,
        payload_sha256=frozen_json_sha256(action.payload),
        accepted=True,
        verification_ref="tactic.execution.produced:fixture@sha1:" + "c" * 40,
        checked_effect=freeze_json_object({
            "goal_after_closed": True,
            "goal_after_remaining": 0,
        }),
    )
    admitted = admit_action_surface(
        bundle.candidate_surface, (certification,), treatment.manifest,
        triggers=invocation.triggers,
    )
    repeated = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        treatment.manifest,
        triggers=invocation.triggers,
        previously_presented=frozenset(admitted.presented_delivery_ids),
    )
    assert audit_result.markdown_bytes == 0
    assert rejected.markdown_bytes == 0
    assert len(admitted.action_surface.actions) == 1
    assert admitted.action_surface.diagnostics == ()
    assert admitted.markdown_bytes <= 520
    assert repeated.markdown_bytes == 0
    assert repeated.action_surface.empty
    assert action_surface_payload(admitted.action_surface)["actions"][0][
        "presentation_kind"
    ] == "failure_linked_repair"


def test_failure_feedback_long_b2_repair_fits_operation_binding_budget() -> None:
    inner = (
        "F_to_MAC_Adv(MAC_to_F(Restrict_sigma(F_to_MAC(Restrict("
        "MAC_to_F(GEN_ECBC(RP_RF1.PRPi.PRPi, D2(O).F0, PRFpadded)))))))"
    )
    snapshot, invocation, bundle = _failure_bundle(
        tactic="apply Alossless.",
        error="cannot infer module arguments",
        environment=_environment_from_text(
            "axiom Alossless (O <: OMac{-A}) : "
            "islossless O.mac => islossless A(O).guess."
        ),
        goal_lines=[
            "Current goal",
            "--------",
            "pre = true",
            f"A({inner}).guess",
            "[=] 1%r",
            "post = true",
        ],
    )
    action = bundle.candidate_surface.actions[0]
    certification = CertificationResult(
        candidate_id=action.candidate_id,
        state_ref=snapshot.state_ref,
        policy=action.certification_policy,
        intent=action.intent,
        payload_sha256=frozen_json_sha256(action.payload),
        accepted=True,
        verification_ref="tactic.execution.produced:fixture@sha1:" + "d" * 40,
        checked_effect=freeze_json_object({
            "goal_after_closed": False,
            "goal_after_remaining": 1,
        }),
    )
    treatment = compiler_assembly_for_profile(
        OPERATION_BINDING_REPAIR_TREATMENT_PROFILE
    )
    assert treatment is not None
    admitted = admit_action_surface(
        bundle.candidate_surface,
        (certification,),
        treatment.manifest,
        triggers=invocation.triggers,
    )

    assert len(admitted.action_surface.actions) == 1
    assert admitted.markdown_bytes <= 1_100
    assert "The proof state is unchanged." in admitted.presentation.text
    assert "EasyCrypt reports:" in admitted.presentation.text
    projected = action_surface_payload(admitted.action_surface)["actions"][0]
    assert "unresolved_premises" not in projected
    assert admitted.action_surface.actions[0].unresolved_premises
