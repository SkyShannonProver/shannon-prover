"""Deterministic sentinel for the native EasyCrypt proof-term boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from core.easycrypt.ec_runtime_identity import (
    discover_easycrypt_runtime_identity,
)
from core.easycrypt.ec_env import MANAGED_WHY3_CONFIG_ENV, get_ec_env
from core.easycrypt.native_semantics import (
    NativeSemanticBatchRequest,
    NativeSemanticQuery,
    run_native_semantic_batch,
)
from core.easycrypt.native_semantics.companion import (
    NATIVE_SEMANTIC_FRAME_PREFIX,
    build_and_identify_companion,
    parse_companion_result_frame,
)
from core.easycrypt.session_projection import active_goal_hash_from_raw


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "native_semantics"
TRUE_GOAL = """Current goal

Type variables: <none>

------------------------------------------------------------------------
true
"""
IMPLICIT_GOAL = """Current goal

Type variables: <none>

H: 0 = 1
------------------------------------------------------------------------
true
"""
LOCAL_HEAD_GOAL = """Current goal

Type variables: <none>

H: true
------------------------------------------------------------------------
true
"""
LOCAL_HEAD_INITIAL_GOAL = """Current goal

Type variables: <none>

------------------------------------------------------------------------
true => true
"""
COMPOUND_PREFIX_GOAL = r"""Current goal

Type variables: <none>

------------------------------------------------------------------------
forall (x : int), true => x + eps = x /\ holds x
"""
REAL_RELATION_GOAL = """Current goal

Type variables: <none>

x: real
y: real
------------------------------------------------------------------------
x <= y
"""
REAL_STRICT_RELATION_GOAL = """Current goal

Type variables: <none>

x: real
y: real
------------------------------------------------------------------------
x < y
"""
EQUIV_STATEMENT_GOAL = """Current goal

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {x, y : int} [programs are in sync]
&2 (right) : {x, y : int}

pre = x{1} = x{2}

(1)  y <@ NativeStateCallee.bump(x)

post = y{1} = y{2}
"""
EQUIV_FUNCTION_GOAL = """Current goal

Type variables: <none>

------------------------------------------------------------------------
pre = arg{1} = arg{2}

    NativeStateCaller.run ~ NativeStateCaller.run

post = res{1} = res{2}
"""
EQUIV_FUNCTION_GOAL_NATIVE = EQUIV_FUNCTION_GOAL.replace(
    "NativeStateCaller.run\n\npost",
    "NativeStateCaller.run \n\npost",
)
EAGER_WHILE_GOAL = "\n".join((
    "Current goal",
    "",
    "Type variables: <none>",
    "",
    "------------------------------------------------------------------------",
    "&1 (left ) : {x : int}",
    "&2 (right) : {x : int}",
    "",
    "pre = true",
    "",
    "x <- 0                     (1)  while (false) {".ljust(57),
    "                           (1)  }".ljust(57),
    "while (true) {             (2)  x <- 0".ljust(57),
    "}                          (2)".ljust(57),
    "while (false) {            (3)  while (true) {".ljust(57),
    "}                          (3)  }".ljust(57),
    "",
    "post = true",
    "",
))
EAGER_WHILE_GUARD_GOAL = "\n".join((
    "Current goal",
    "",
    "Type variables: <none>",
    "",
    "------------------------------------------------------------------------",
    "&1 (left ) : {x : int}",
    "&2 (right) : {x : int}",
    "",
    "pre = true",
    "",
    "x <- 0                     (1)  while (false) {".ljust(57),
    "                           (1)  }".ljust(57),
    "while (true) {             (2)  x <- 0".ljust(57),
    "}                          (2)".ljust(57),
    "",
    "post = true",
    "",
))
INT_RELATION_GOAL = """Current goal

Type variables: <none>

x: int
y: int
------------------------------------------------------------------------
x <= y
"""
PURE_TAIL_MAP_GOAL = """Current goal

Type variables: <none>

m: (int, int) fmap
x: int
v: int
z: int option
Hupdate: m.[x <- v].[x] = z
------------------------------------------------------------------------
z = Some v
"""
PURE_TAIL_LIST_GOAL = """Current goal

Type variables: <none>

xs: int list
n: int
Hcat: size (++ xs []) = n
------------------------------------------------------------------------
n = size xs
"""
PURE_TAIL_LOCAL_FACT_GOAL = """Current goal

Type variables: <none>

a: int
b: int
c: int
Ha: a = b
Hac: a = c
------------------------------------------------------------------------
b = c
"""
PURE_TAIL_AMBIGUOUS_GOAL = """Current goal

Type variables: <none>

m: (int, int) fmap
x: int
v: int
z1: int option
z2: int option
Hleft: m.[x <- v].[x] = z1
Hright: m.[x <- v].[x] = z2
------------------------------------------------------------------------
z1 = z2
"""
INTRO_PATTERN_GOAL = """Current goal

Type variables: <none>

a: bool
b: bool
c: bool
d: bool
------------------------------------------------------------------------
a /\\ b /\\ c /\\ d => true
"""
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(
    *,
    request_id: str,
    context_file: Path,
    history_file: Path,
    include_dirs: tuple[Path, ...],
    operation: str,
    application_term: str,
    expected_goal_identity: str,
    expected_context_sha256: str,
    expected_history_sha256: str,
    evaluation_prefix: tuple[str, ...] = (),
) -> NativeSemanticBatchRequest:
    return NativeSemanticBatchRequest(
        batch_id=f"batch-{request_id}",
        context_file=context_file,
        history_file=history_file,
        include_dirs=include_dirs,
        queries=(NativeSemanticQuery(
            request_id=request_id,
            query_kind="proof_term_elaboration",
            payload={
                "operation": operation,
                "application_term": application_term,
            },
            evaluation_prefix=evaluation_prefix,
        ),),
        expected_goal_identity=expected_goal_identity,
        expected_context_sha256=expected_context_sha256,
        expected_history_sha256=expected_history_sha256,
    )


def _diagnostic_request(
    *,
    request_id: str,
    context_file: Path,
    history_file: Path,
    query_kind: str,
    rejected_tactic: str,
    expected_goal_identity: str,
    observed_outcome_kind: str = "rejected",
) -> NativeSemanticBatchRequest:
    payload = {
        "rejected_tactic": rejected_tactic,
        "observed_outcome_kind": observed_outcome_kind,
    }
    return NativeSemanticBatchRequest(
        batch_id=f"batch-{request_id}",
        context_file=context_file,
        history_file=history_file,
        include_dirs=(),
        queries=(NativeSemanticQuery(
            request_id=request_id,
            query_kind=query_kind,
            payload=payload,
        ),),
        expected_goal_identity=expected_goal_identity,
        expected_context_sha256=_sha256(context_file),
        expected_history_sha256=_sha256(history_file),
    )


def _prefix_request(
    *,
    request_id: str,
    context_file: Path,
    history_file: Path,
    rejected_tactic: str,
    candidate_prefixes: tuple[str, ...],
    expected_goal_identity: str,
) -> NativeSemanticBatchRequest:
    return NativeSemanticBatchRequest(
        batch_id=f"batch-{request_id}",
        context_file=context_file,
        history_file=history_file,
        include_dirs=(),
        queries=(NativeSemanticQuery(
            request_id=request_id,
            query_kind="tactic_prefix_diagnostic",
            payload={
                "rejected_tactic": rejected_tactic,
                "candidate_prefixes": list(candidate_prefixes),
            },
        ),),
        expected_goal_identity=expected_goal_identity,
        expected_context_sha256=_sha256(context_file),
        expected_history_sha256=_sha256(history_file),
    )


def _selected_binding_set_request(
    *,
    request_id: str,
    selected_resource: str,
    module_candidates: tuple[str, ...],
) -> NativeSemanticBatchRequest:
    context = FIXTURES / "selected_binding_set_goal.ec"
    history = FIXTURES / "selected_binding_set_history.ec"
    return NativeSemanticBatchRequest(
        batch_id=f"batch-{request_id}",
        context_file=context,
        history_file=history,
        include_dirs=(),
        queries=(NativeSemanticQuery(
            request_id=request_id,
            query_kind="selected_application_binding_set",
            payload={
                "operation": "apply",
                "selected_resource": selected_resource,
                "module_candidates": list(module_candidates),
            },
        ),),
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )


def test_selected_binding_set_rejects_concrete_argument_reinterpretation(
) -> None:
    with pytest.raises(ValueError, match="binding-set payload"):
        NativeSemanticQuery(
            request_id="native-selected-binding-set-conseq-rejected",
            query_kind="selected_application_binding_set",
            payload={
                "operation": "conseq",
                "selected_resource": "RO_FinRO_D",
                "module_candidates": ["G2"],
            },
        )


@pytest.mark.parametrize(
    ("module_candidates", "expected_terms"),
    (
        (
            ("NativeBindingOne", "NativeBindingWrong"),
                ("native_binding_true (<: NativeBindingOne)",),
        ),
        (
            (
                "NativeBindingOne",
                "NativeBindingTwo",
                "NativeBindingWrong",
            ),
            (
                    "native_binding_true (<: NativeBindingOne)",
                    "native_binding_true (<: NativeBindingTwo)",
            ),
        ),
    ),
)
def test_native_selected_application_binding_set_returns_complete_checked_set(
    module_candidates: tuple[str, ...],
    expected_terms: tuple[str, ...],
) -> None:
    request = _selected_binding_set_request(
        request_id="native-selected-binding-set-" + str(len(expected_terms)),
        selected_resource="native_binding_true",
        module_candidates=module_candidates,
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["population_complete"] is True
    assert result.descriptor["candidate_module_term_count"] == len(
        module_candidates
    )
    assert result.descriptor["candidate_check_count"] == len(
        module_candidates
    )
    assert result.descriptor["typed_binding_count"] == len(expected_terms)
    assert result.descriptor["checked_completion_count"] == len(
        expected_terms
    )
    assert tuple(
        item["application_term"]
        for item in result.descriptor["checked_completions"]
    ) == expected_terms
    assert all(
        item["descriptor"]["result_convertible_to_current_goal"] is True
        and item["tactic_effect"] == "accepted_changed"
        for item in result.descriptor["checked_completions"]
    )


def test_native_selected_application_binding_set_reports_complete_zero_match(
) -> None:
    request = _selected_binding_set_request(
        request_id="native-selected-binding-set-zero",
        selected_resource="native_binding_false",
        module_candidates=("NativeBindingOne", "NativeBindingTwo"),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["population_complete"] is True
    assert result.descriptor["typed_binding_count"] == 2
    assert result.descriptor["checked_completion_count"] == 0
    assert result.descriptor["checked_completions"] == []


def test_native_selected_application_binding_set_never_exposes_overflow_prefix(
) -> None:
    candidates = tuple(
        "NativeBinding" + label
        for label in (
            "One", "Two", "Three", "Four", "Five", "Six", "Seven",
            "Eight", "Nine",
        )
    )
    request = _selected_binding_set_request(
        request_id="native-selected-binding-set-overflow",
        selected_resource="native_binding_pair",
        module_candidates=tuple(sorted(candidates)),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["population_complete"] is False
    assert result.descriptor["reason"] == (
        "native_binding_search_exceeds_bound"
    )
    assert result.descriptor["typed_binding_count"] == 65
    assert result.descriptor["checked_completion_count"] == 0
    assert result.descriptor["checked_completions"] == []


def test_native_semantic_adapter_preserves_structured_apperror() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    before = (context.read_bytes(), history.read_bytes())
    request = _request(
        request_id="native-not-functional-sentinel",
        context_file=context,
        history_file=history,
        include_dirs=(),
        operation="apply",
        application_term="trueI _",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    batch = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )
    result = batch.results[0]

    assert result.status == "rejected"
    assert result.structured_error == {
        "code": "not_functional",
        "message": "too many arguments",
    }
    assert batch.companion_identity.easycrypt_toolchain_build_id == (
        batch.runtime_identity.build_id
    )
    assert batch.companion_identity.why3_config_sha256 == _sha256(
        Path(get_ec_env()[MANAGED_WHY3_CONFIG_ENV])
    )
    assert (context.read_bytes(), history.read_bytes()) == before


def test_native_semantic_query_runs_in_exact_scratch_prefix_context() -> None:
    context = FIXTURES / "local_head_goal.ec"
    history = FIXTURES / "empty_history.ec"
    before = (context.read_bytes(), history.read_bytes())
    request = _request(
        request_id="native-scratch-prefix-local-head",
        context_file=context,
        history_file=history,
        include_dirs=(),
        operation="exact",
        application_term="H",
        evaluation_prefix=("move=> H.",),
        expected_goal_identity=active_goal_hash_from_raw(
            LOCAL_HEAD_INITIAL_GOAL
        ),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    )

    assert result.results[0].status == "accepted"
    assert result.results[0].descriptor["resolved_head"] == {
        "kind": "local",
        "identity": "H",
        "type_arguments": [],
    }
    assert (context.read_bytes(), history.read_bytes()) == before


def test_native_semantic_adapter_error_envelope_uses_schema_17() -> None:
    executable, _identity = build_and_identify_companion(
        "native_semantic_adapter",
        discover_easycrypt_runtime_identity(),
    )
    process = subprocess.run(
        [str(executable)],
        cwd=str(executable.parents[2]),
        env=get_ec_env(),
        input=json.dumps({"schema_version": 11}),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 0
    payload = parse_companion_result_frame(
        process.stdout,
        prefix=NATIVE_SEMANTIC_FRAME_PREFIX,
    )
    assert payload == {
        "schema_version": 17,
        "kind": "native_semantic_batch_result",
        "status": "contract_error",
        "message": "unsupported request schema_version",
    }


@pytest.mark.parametrize(
    ("fixture", "history_fixture", "goal", "resource", "target"),
    (
        (
            "pure_tail_map_goal.ec",
            "pure_tail_map_history.ec",
            PURE_TAIL_MAP_GOAL,
            "get_setE",
            "Hupdate",
        ),
        (
            "pure_tail_list_goal.ec",
            "pure_tail_list_history.ec",
            PURE_TAIL_LIST_GOAL,
            "cats0",
            "Hcat",
        ),
        (
            "pure_tail_local_fact_goal.ec",
            "pure_tail_local_fact_history.ec",
            PURE_TAIL_LOCAL_FACT_GOAL,
            "Ha",
            "Hac",
        ),
    ),
)
def test_native_attempt_finds_one_unique_selected_rewrite_target(
    fixture: str,
    history_fixture: str,
    goal: str,
    resource: str,
    target: str,
) -> None:
    context = FIXTURES / fixture
    history = FIXTURES / history_fixture
    request = _diagnostic_request(
        request_id=f"native-pure-tail-{resource}",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=f"rewrite {resource}.",
        expected_goal_identity=active_goal_hash_from_raw(goal),
    )
    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["operation_family"] == "rewrite"
    assert result.descriptor["exact_resource"] == resource
    assert result.descriptor["native_failure_kind"] == (
        "rewrite_target_mismatch"
    )
    assert result.descriptor["pure_tail_rewrite"] == {
        "source_operation": "rewrite",
        "selected_resource": resource,
        "target_kind": "hypothesis",
        "target_name": target,
        "candidate_tactic": f"rewrite {resource} in {target}.",
        "failure_kind": "rewrite_target_mismatch",
        "accepted_target_count": 1,
    }


def test_native_selected_rewrite_abstains_when_two_hypotheses_accept() -> None:
    context = FIXTURES / "pure_tail_ambiguous_goal.ec"
    history = FIXTURES / "pure_tail_ambiguous_history.ec"
    request = _diagnostic_request(
        request_id="native-pure-tail-ambiguous",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="rewrite get_setE.",
        expected_goal_identity=active_goal_hash_from_raw(
            PURE_TAIL_AMBIGUOUS_GOAL
        ),
    )
    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["operation_family"] == "rewrite"
    assert result.descriptor["pure_tail_rewrite"] is None


def test_native_intro_pattern_repair_preserves_ordered_binders() -> None:
    context = FIXTURES / "intro_pattern_goal.ec"
    history = FIXTURES / "intro_pattern_history.ec"
    rejected_tactic = "move => [ha hb [hc hd]]."
    request = _diagnostic_request(
        request_id="native-intro-pattern-repair",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=rejected_tactic,
        expected_goal_identity=active_goal_hash_from_raw(INTRO_PATTERN_GOAL),
    )
    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["operation_family"] == "intro_pattern"
    assert result.descriptor["native_failure_kind"] == (
        "intro_pattern_structure_mismatch"
    )
    assert result.descriptor["application_syntax_repair"] is None
    assert result.descriptor["intro_pattern_realization"] == {
        "source_operation": "intro_pattern",
        "surface_operation": "move",
        "attempted_pattern_kind": "nested_case",
        "binder_names": ["ha", "hb", "hc", "hd"],
        "candidate_tactic": "move => [# ha hb hc hd].",
        "failure_kind": "intro_pattern_structure_mismatch",
        "selected_pattern_count": 1,
    }


@pytest.mark.parametrize(
    "rejected_tactic",
    (
        "move => [ha [hb hc]] [hd].",
        "move => [ha hb [hc ha]].",
        "move => [# ha hb hc hd].",
    ),
)
def test_native_intro_pattern_repair_abstains_without_one_unique_tree(
    rejected_tactic: str,
) -> None:
    context = FIXTURES / "intro_pattern_goal.ec"
    history = FIXTURES / "intro_pattern_history.ec"
    request = _diagnostic_request(
        request_id="native-intro-pattern-abstain",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=rejected_tactic,
        expected_goal_identity=active_goal_hash_from_raw(INTRO_PATTERN_GOAL),
    )
    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "rejected"
    assert result.descriptor == {}


def test_native_semantic_adapter_exports_accepted_head_descriptor() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _request(
        request_id="native-accepted-descriptor",
        context_file=context,
        history_file=history,
        include_dirs=(),
        operation="apply",
        application_term="trueI",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    batch = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )
    result = batch.results[0]

    assert result.status == "accepted"
    assert result.descriptor["resolved_head"]["kind"] == "global"
    assert result.descriptor["resolved_head"]["identity"].endswith(".trueI")
    assert result.descriptor["arguments"] == []
    assert result.descriptor["residual_proof_premises"] == []
    assert result.descriptor["result"]["kind"] == "true"
    assert result.descriptor["can_concretize"] is True
    assert result.descriptor["result_convertible_to_current_goal"] is True


def test_native_descriptor_reports_nonconvertible_result_without_guessing() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _request(
        request_id="native-nonconvertible-result",
        context_file=context,
        history_file=history,
        include_dirs=(),
        operation="apply",
        application_term="native_adapter_false_certificate",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    batch = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )
    result = batch.results[0]

    assert result.status == "accepted"
    assert result.descriptor["result"]["kind"] == "false"
    assert result.descriptor["result_convertible_to_current_goal"] is False


def test_native_descriptor_preserves_module_slot_and_residual_proof_hole() -> None:
    context = FIXTURES / "proof_term_descriptor_goal.ec"
    history = FIXTURES / "proof_term_descriptor_history.ec"
    request = _request(
        request_id="native-module-proof-descriptor",
        context_file=context,
        history_file=history,
        include_dirs=(),
        operation="call",
        application_term=(
            "native_descriptor_certificate (<: NativeDescriptorImpl) _"
        ),
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    batch = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )
    result = batch.results[0]

    descriptor = result.descriptor
    assert descriptor["resolved_head"]["identity"].endswith(
        ".native_descriptor_certificate"
    )
    assert descriptor["explicit_hole_count"] == 1
    assert descriptor["implicit_argument_count"] == 0
    assert [item["actual"]["kind"] for item in descriptor["arguments"]] == [
        "module", "proof"
    ]
    assert descriptor["arguments"][0]["actual"]["identity"].endswith(
        ".NativeDescriptorImpl"
    )
    assert descriptor["arguments"][1]["actual"]["hole"] is True
    assert len(descriptor["residual_proof_premises"]) == 1
    premise = descriptor["residual_proof_premises"][0]["formula"]
    assert premise["kind"] == "bounded_hoare_function"
    assert premise["lossless"] is True
    assert premise["procedure"].endswith(".NativeDescriptorImpl./f")
    assert descriptor["result"]["procedure"] == premise["procedure"]


def test_native_descriptor_rejects_unconcretized_module_hole() -> None:
    context = FIXTURES / "proof_term_descriptor_goal.ec"
    history = FIXTURES / "proof_term_descriptor_history.ec"
    request = _request(
        request_id="native-module-hole-rejected",
        context_file=context,
        history_file=history,
        include_dirs=(),
        operation="call",
        application_term="native_descriptor_certificate _ _",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    batch = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )
    result = batch.results[0]

    assert result.status == "rejected"
    assert result.descriptor == {}
    assert result.structured_error["code"] == "cannot_infer_module"


@pytest.mark.parametrize(
    ("rejected_tactic", "candidate_application", "argument_kinds"),
    (
        (
            "call (native_descriptor_certificate "
            "(NativeDescriptorNest(NativeDescriptorImpl).O) _).",
            "native_descriptor_certificate "
            "(<: NativeDescriptorNest(NativeDescriptorImpl).O) _",
            ["module", "hole"],
        ),
        (
            "call (native_descriptor_certificate "
            "(NativeDescriptorNest(NativeDescriptorImpl).O)).",
            "native_descriptor_certificate "
            "(<: NativeDescriptorNest(NativeDescriptorImpl).O)",
            ["module"],
        ),
        (
            "call (native_descriptor_certificate "
            "NativeDescriptorNest(NativeDescriptorImpl).O).",
            "native_descriptor_certificate "
            "(<: NativeDescriptorNest(NativeDescriptorImpl).O)",
            ["module"],
        ),
    ),
)
def test_native_attempt_resolves_selected_first_module_argument_syntax(
    rejected_tactic: str,
    candidate_application: str,
    argument_kinds: list[str],
) -> None:
    context = FIXTURES / "proof_term_descriptor_goal.ec"
    history = FIXTURES / "proof_term_descriptor_history.ec"
    request = _diagnostic_request(
        request_id="native-module-syntax-" + hashlib.sha256(
            rejected_tactic.encode("utf-8")
        ).hexdigest()[:12],
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=rejected_tactic,
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )
    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["operation_family"] == "call"
    assert descriptor["exact_resource"] == "native_descriptor_certificate"
    assert descriptor["native_failure_kind"] == (
        "application_module_argument_syntax"
    )
    assert descriptor["argument_kinds"] == []
    assert descriptor["application_head"]["slots"][0]["kind"] == "module"
    assert descriptor["intro_pattern_realization"] is None
    assert descriptor["application_syntax_repair"] == {
        "source_operation": "call",
        "selected_resource": "native_descriptor_certificate",
        "module_argument_position": 1,
        "module_term_text": "NativeDescriptorNest(NativeDescriptorImpl).O",
        "candidate_application_term": candidate_application,
        "candidate_tactic": f"call ({candidate_application}).",
        "candidate_argument_kinds": argument_kinds,
        "failure_kind": "application_module_argument_syntax",
        "resolved_candidate_count": 1,
    }


@pytest.mark.parametrize(
    "rejected_tactic",
    (
        "call (native_descriptor_certificate "
        "NativeDescriptorNest (NativeDescriptorImpl).O).",
        "call (native_descriptor_certificate "
        "NativeDescriptorNest(NativeDescriptorImpl).O (* comment *) _).",
    ),
)
def test_native_module_syntax_repair_abstains_on_ambiguous_source(
    rejected_tactic: str,
) -> None:
    context = FIXTURES / "proof_term_descriptor_goal.ec"
    history = FIXTURES / "proof_term_descriptor_history.ec"
    request = _diagnostic_request(
        request_id="native-module-syntax-negative-" + hashlib.sha256(
            rejected_tactic.encode("utf-8")
        ).hexdigest()[:12],
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=rejected_tactic,
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )
    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "rejected"
    assert result.descriptor == {}


def test_native_module_syntax_repair_abstains_on_non_module_slot() -> None:
    context = FIXTURES / "proof_term_descriptor_goal.ec"
    history = FIXTURES / "proof_term_descriptor_history.ec"
    request = _diagnostic_request(
        request_id="native-module-syntax-non-module-slot",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="call (native_formula_head (NativeDescriptorImpl)).",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )
    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["native_failure_kind"] == (
        "call_applicability_failure"
    )
    assert result.descriptor["application_syntax_repair"] is None


def test_native_descriptor_reports_easycrypt_inserted_implicit_arguments() -> None:
    context = FIXTURES / "proof_term_implicit_goal.ec"
    history = FIXTURES / "proof_term_implicit_history.ec"
    request = _request(
        request_id="native-implicit-descriptor",
        context_file=context,
        history_file=history,
        include_dirs=(),
        operation="apply",
        application_term="native_implicit_descriptor 1 H",
        expected_goal_identity=active_goal_hash_from_raw(IMPLICIT_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    batch = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )
    result = batch.results[0]

    descriptor = result.descriptor
    assert descriptor["input_mode"] == "implicit"
    assert len(descriptor["input_arguments"]) == 2
    assert descriptor["implicit_argument_count"] == 1
    assert [item["actual"]["kind"] for item in descriptor["arguments"]] == [
        "formula", "formula", "proof"
    ]
    assert [
        item["actual"]["formula"]["text"]
        for item in descriptor["arguments"][:2]
    ] == ["0", "1"]
    assert descriptor["residual_proof_premises"] == []


def test_native_batch_preserves_order_and_isolates_member_rejections() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = NativeSemanticBatchRequest(
        batch_id="native-mixed-batch",
        context_file=context,
        history_file=history,
        include_dirs=(),
        queries=(
            NativeSemanticQuery(
                request_id="accepted-first",
                query_kind="proof_term_elaboration",
                payload={"operation": "apply", "application_term": "trueI"},
            ),
            NativeSemanticQuery(
                request_id="rejected-second",
                query_kind="proof_term_elaboration",
                payload={"operation": "apply", "application_term": "trueI _"},
            ),
            NativeSemanticQuery(
                request_id="accepted-third",
                query_kind="proof_term_elaboration",
                payload={"operation": "exact", "application_term": "trueI"},
            ),
        ),
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history),
    )

    batch = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=30,
    )

    assert batch.batch_id == "native-mixed-batch"
    assert [item.request_id for item in batch.results] == [
        "accepted-first",
        "rejected-second",
        "accepted-third",
    ]
    assert [item.status for item in batch.results] == [
        "accepted", "rejected", "accepted"
    ]
    assert batch.results[1].structured_error == {
        "code": "not_functional",
        "message": "too many arguments",
    }
    assert batch.results[2].descriptor["resolved_head"]["identity"].endswith(
        ".trueI"
    )


def test_native_attempt_diagnostic_owns_parse_and_failure_kind() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _diagnostic_request(
        request_id="attempt-not-functional",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="apply (trueI _).",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["operation_family"] == "apply"
    assert result.descriptor["exact_resource"].endswith("trueI")
    assert result.descriptor["attempt_outcome"] == "rejected"
    assert result.descriptor["native_diagnostic_status"] == "blocker"
    assert result.descriptor["native_failure_kind"] == "not_functional"
    assert result.descriptor["application_head"]["resolved_head"][
        "identity"
    ].endswith(".trueI")


def test_native_tactic_prefix_diagnostic_reports_accepted_population() -> None:
    context = FIXTURES / "intro_pattern_goal.ec"
    history = FIXTURES / "intro_pattern_history.ec"
    rejected = "move=> H; rewrite H."
    request = _prefix_request(
        request_id="compound-prefix-native",
        context_file=context,
        history_file=history,
        rejected_tactic=rejected,
        candidate_prefixes=("move=> H.",),
        expected_goal_identity=active_goal_hash_from_raw(INTRO_PATTERN_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["rejected_tactic"] == rejected
    assert result.descriptor["candidate_prefixes"] == ["move=> H."]
    assert result.descriptor["accepted_prefixes"] == ["move=> H."]
    assert "selected_prefix" not in result.descriptor
    assert result.descriptor["native_failure_kind"]
    assert result.descriptor["native_error_message"]
    assert result.descriptor["boundary_failure_kind"]
    assert result.descriptor["boundary_error_message"]
    assert result.descriptor["goal_kind"] == "implication"


def test_native_tactic_prefix_diagnostic_reports_longest_accepted_prefix() -> None:
    context = FIXTURES / "compound_prefix_goal.ec"
    history = FIXTURES / "empty_history.ec"
    rejected = "move=> x _; rewrite /eps; smt()."
    prefixes = (
        "move=> x _.",
        "move=> x _; rewrite /eps.",
    )
    request = _prefix_request(
        request_id="compound-prefix-native-longest",
        context_file=context,
        history_file=history,
        rejected_tactic=rejected,
        candidate_prefixes=prefixes,
        expected_goal_identity=active_goal_hash_from_raw(
            COMPOUND_PREFIX_GOAL
        ),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["candidate_prefixes"] == list(prefixes)
    assert result.descriptor["accepted_prefixes"] == list(prefixes)
    assert "cannot prove goal" in result.descriptor["native_error_message"]
    assert "cannot prove goal" in result.descriptor["boundary_error_message"]


def test_native_no_progress_prefix_reuses_full_attempt_dispatch_for_suffix() -> None:
    context = FIXTURES / "real_relation_goal.ec"
    history = FIXTURES / "empty_history.ec"
    rejected = "idtac; transitivity 0%r."
    request = _prefix_request(
        request_id="compound-prefix-native-relation-handoff",
        context_file=context,
        history_file=history,
        rejected_tactic=rejected,
        candidate_prefixes=("idtac.",),
        expected_goal_identity=active_goal_hash_from_raw(REAL_RELATION_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["prefix_effects"] == ["accepted_no_progress"]
    assert descriptor["accepted_prefixes"] == ["idtac."]
    assert descriptor["boundary_tactic"] == "transitivity 0%r."
    boundary = descriptor["boundary_attempt"]
    assert boundary["operation_family"] == "transitivity"
    assert boundary["rejected_tactic"] == "transitivity 0%r."
    assert boundary["relation_bridge"]["relation_family"] == "real_le"
    assert boundary["relation_bridge"]["candidate_tactic"] == (
        "apply (ler_trans 0%r); first last."
    )


def test_native_state_changing_prefix_diagnoses_suffix_in_boundary_state() -> None:
    context = FIXTURES / "local_head_goal.ec"
    history = FIXTURES / "empty_history.ec"
    rejected = "move=> H; exact (H true)."
    request = _prefix_request(
        request_id="compound-prefix-native-changed-handoff",
        context_file=context,
        history_file=history,
        rejected_tactic=rejected,
        candidate_prefixes=("move=> H.",),
        expected_goal_identity=active_goal_hash_from_raw(
            LOCAL_HEAD_INITIAL_GOAL
        ),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["prefix_effects"] == ["accepted_changed"]
    assert descriptor["accepted_prefixes"] == ["move=> H."]
    assert descriptor["boundary_tactic"] == "exact (H true)."
    boundary = descriptor["boundary_attempt"]
    assert boundary["operation_family"] == "exact"
    assert boundary["rejected_tactic"] == "exact (H true)."
    assert boundary["exact_resource"] == "H"
    assert boundary["application_head"]["resolved_head"] == {
        "kind": "local",
        "identity": "H",
        "type_arguments": [],
    }
    assert boundary["native_failure_kind"] in {
        "not_functional", "wrong_argument_kind", "native_user_error"
    }


def test_native_tactic_prefix_localizes_full_parse_error_to_exact_suffix() -> None:
    context = FIXTURES / "intro_pattern_goal.ec"
    history = FIXTURES / "intro_pattern_history.ec"
    request = _prefix_request(
        request_id="compound-prefix-parse-error",
        context_file=context,
        history_file=history,
        rejected_tactic="move=> H; this-is-not-a-tactic.",
        candidate_prefixes=("move=> H.",),
        expected_goal_identity=active_goal_hash_from_raw(INTRO_PATTERN_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["prefix_effects"] == ["accepted_changed"]
    assert descriptor["accepted_prefixes"] == ["move=> H."]
    assert descriptor["boundary_tactic"] == "this-is-not-a-tactic."
    assert descriptor["boundary_attempt"] is None
    assert descriptor["native_failure_kind"] == "parse_error"
    assert descriptor["boundary_failure_kind"] == "parse_error"


def test_native_attempt_identifies_unique_eager_while_dialect_repair() -> None:
    context = FIXTURES / "eager_while_goal.ec"
    history = FIXTURES / "eager_while_history.ec"
    tactic = (
        "eager while (H : x <- 0; ~ x <- 0; : true ==> true)."
    )
    request = _diagnostic_request(
        request_id="attempt-eager-while-dialect",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(EAGER_WHILE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["operation_family"] == "eager"
    assert descriptor["goal_kind"] == "equiv_statement"
    assert descriptor["native_failure_kind"] == "eager_while_dialect_mismatch"
    assert descriptor["eager_while_dialect"] == {
        "source_operation": "eager",
        "eager_subform": "while",
        "attempted_shape": "explicit_statement_contract",
        "failure_kind": "eager_while_dialect_mismatch",
        "candidates": [{
            "invariant_text": "true",
            "candidate_tactic": "eager while (true).",
        }],
    }


def test_native_attempt_exposes_all_checked_submitted_eager_invariants() -> None:
    context = FIXTURES / "eager_while_goal.ec"
    history = FIXTURES / "eager_while_history.ec"
    tactic = "eager while (H : x <- 0; ~ x <- 0; : true ==> ={x})."
    request = _diagnostic_request(
        request_id="attempt-eager-while-choice",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(EAGER_WHILE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["eager_while_dialect"]["candidates"] == [
        {
            "invariant_text": "true",
            "candidate_tactic": "eager while (true).",
        },
        {
            "invariant_text": "={x}",
            "candidate_tactic": "eager while (={x}).",
        },
    ]


def test_native_attempt_identifies_eager_while_guard_mismatch() -> None:
    context = FIXTURES / "eager_while_guard_goal.ec"
    history = FIXTURES / "eager_while_history.ec"
    request = _diagnostic_request(
        request_id="attempt-eager-while-guard",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="eager while (true).",
        expected_goal_identity=active_goal_hash_from_raw(
            EAGER_WHILE_GUARD_GOAL
        ),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["native_failure_kind"] == "eager_while_guard_mismatch"
    assert "both while guards" in descriptor["native_error_message"]
    assert descriptor["eager_while_dialect"] == {
        "source_operation": "eager",
        "eager_subform": "while",
        "attempted_shape": "invariant",
        "failure_kind": "eager_while_guard_mismatch",
        "candidates": [],
    }


def test_native_eager_while_dialect_abstains_on_non_phl_goal() -> None:
    context = FIXTURES / "true_goal.ec"
    request = _diagnostic_request(
        request_id="attempt-eager-while-on-formula",
        context_file=context,
        history_file=FIXTURES / "empty_history.ec",
        query_kind="attempt_diagnostic",
        rejected_tactic=(
            "eager while (H : x <- 0; ~ x <- 0; : true ==> true)."
        ),
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "rejected"
    assert result.descriptor == {}
    assert result.structured_error["code"] == "parse_error"


@pytest.mark.parametrize(
    ("tactic", "operation", "failure_kind", "intermediate"),
    (
        (
            "transitivity 0%r.",
            "transitivity",
            "formula_transitivity_surface_mismatch",
            "0%r",
        ),
        (
            "change 0%r <= y.",
            "change",
            "change_target_not_convertible",
            "0%r",
        ),
    ),
)
def test_native_attempt_identifies_real_le_relation_realization(
    tactic: str,
    operation: str,
    failure_kind: str,
    intermediate: str,
) -> None:
    context = FIXTURES / "real_relation_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _diagnostic_request(
        request_id=f"attempt-real-bridge-{operation}",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(REAL_RELATION_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["operation_family"] == operation
    assert descriptor["native_failure_kind"] == failure_kind
    assert descriptor["application_head"] is None
    assert descriptor["proof_term"] is None
    bridge = descriptor["relation_bridge"]
    assert bridge["source_operation"] == operation
    assert bridge["relation_family"] == "real_le"
    assert bridge["intermediate_text"] == intermediate
    assert bridge["intermediate_type"] == "real"
    assert bridge["candidate_tactic"] == (
        f"apply (ler_trans {intermediate}); first last."
    )
    assert bridge["failure_kind"] == failure_kind
    if operation == "change":
        assert bridge["source_target_present"] is True
        assert bridge["source_target_convertible_to_current_goal"] is False
        assert bridge[
            "source_target_right_convertible_to_current_right"
        ] is True
    else:
        assert bridge["source_target_present"] is False


def test_native_attempt_identifies_checked_int_le_relation_realization() -> None:
    context = FIXTURES / "int_relation_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _diagnostic_request(
        request_id="attempt-int-bridge-transitivity",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="transitivity 0.",
        expected_goal_identity=active_goal_hash_from_raw(INT_RELATION_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    bridge = result.descriptor["relation_bridge"]
    assert bridge["source_operation"] == "transitivity"
    assert bridge["relation_family"] == "int_le"
    assert bridge["intermediate_text"] == "0"
    assert bridge["intermediate_type"] == "int"
    assert bridge["candidate_tactic"] == (
        "apply (Int.lez_trans 0); first last."
    )


def test_native_attempt_exposes_all_checked_real_lt_bridge_choices() -> None:
    context = FIXTURES / "real_strict_relation_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _diagnostic_request(
        request_id="attempt-real-strict-bridge-choice",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="transitivity 0%r.",
        expected_goal_identity=active_goal_hash_from_raw(
            REAL_STRICT_RELATION_GOAL
        ),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["relation_bridge"] is None
    choice = descriptor["relation_bridge_choice"]
    assert choice == {
        "source_operation": "transitivity",
        "relation_family": "real_lt",
        "goal_left_text": "x",
        "intermediate_text": "0%r",
        "goal_right_text": "y",
        "intermediate_type": "real",
        "failure_kind": "formula_transitivity_surface_mismatch",
        "choices": [
            {
                "certificate_family": "ler_lt_trans",
                "left_relation": "<=",
                "right_relation": "<",
                "candidate_tactic": (
                    "apply (ler_lt_trans 0%r); first last."
                ),
            },
            {
                "certificate_family": "ltr_le_trans",
                "left_relation": "<",
                "right_relation": "<=",
                "candidate_tactic": (
                    "apply (ltr_le_trans 0%r); first last."
                ),
            },
            {
                "certificate_family": "ltr_trans",
                "left_relation": "<",
                "right_relation": "<",
                "candidate_tactic": "apply (ltr_trans 0%r); first last.",
            },
        ],
    }


def test_native_attempt_identifies_phl_function_statement_boundary() -> None:
    context = FIXTURES / "equiv_statement_goal.ec"
    history = FIXTURES / "proc_history.ec"
    tactic = (
        "transitivity NativeStateCallee.bump "
        "(={arg} ==> ={res}) (={arg} ==> ={res})."
    )
    request = _diagnostic_request(
        request_id="attempt-phl-function-on-statement",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(EQUIV_STATEMENT_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["operation_family"] == "transitivity"
    assert descriptor["goal_kind"] == "equiv_statement"
    assert descriptor["native_failure_kind"] == (
        "phl_transitivity_boundary_mismatch"
    )
    assert descriptor["relation_bridge"] is None
    assert descriptor["relation_bridge_choice"] is None
    assert descriptor["phl_transitivity_boundary"] == {
        "source_operation": "transitivity",
        "attempted_form": "function",
        "current_goal_form": "statement",
        "side": "",
        "failure_kind": "phl_transitivity_boundary_mismatch",
    }


def test_native_attempt_identifies_phl_statement_function_boundary() -> None:
    context = FIXTURES / "equiv_statement_goal.ec"
    history = FIXTURES / "empty_history.ec"
    tactic = (
        "transitivity{1} { y <@ NativeStateCallee.bump(x); } "
        "(={arg} ==> ={res}) (={arg} ==> ={res})."
    )
    request = _diagnostic_request(
        request_id="attempt-phl-statement-on-function",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(
            EQUIV_FUNCTION_GOAL_NATIVE
        ),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["goal_kind"] == "equiv_function"
    assert descriptor["side"] == "left"
    assert descriptor["phl_transitivity_boundary"] == {
        "source_operation": "transitivity",
        "attempted_form": "statement",
        "current_goal_form": "function",
        "side": "left",
        "failure_kind": "phl_transitivity_boundary_mismatch",
    }


def test_native_attempt_preserves_right_side_for_phl_statement_form() -> None:
    context = FIXTURES / "equiv_statement_goal.ec"
    history = FIXTURES / "empty_history.ec"
    tactic = (
        "transitivity{2} { y <@ NativeStateCallee.bump(x); } "
        "(={arg} ==> ={res}) (={arg} ==> ={res})."
    )
    request = _diagnostic_request(
        request_id="attempt-phl-statement-right-on-function",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(
            EQUIV_FUNCTION_GOAL_NATIVE
        ),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["side"] == "right"
    assert result.descriptor["phl_transitivity_boundary"]["side"] == "right"


@pytest.mark.parametrize(
    ("tactic", "history", "goal"),
    (
        (
            "transitivity NativeStateCallee.bump "
            "(={arg} ==> ={res}) (={arg} ==> ={res}).",
            "empty_history.ec",
            EQUIV_FUNCTION_GOAL_NATIVE,
        ),
        (
            "transitivity{1} { y <@ NativeStateCallee.bump(x); } "
            "(={arg} ==> ={res}) (={arg} ==> ={res}).",
            "proc_history.ec",
            EQUIV_STATEMENT_GOAL,
        ),
    ),
)
def test_native_phl_same_form_does_not_emit_boundary_descriptor(
    tactic: str,
    history: str,
    goal: str,
) -> None:
    context = FIXTURES / "equiv_statement_goal.ec"
    request = _diagnostic_request(
        request_id="attempt-phl-same-form-" + hashlib.sha256(
            tactic.encode("utf-8")
        ).hexdigest()[:8],
        context_file=context,
        history_file=FIXTURES / history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(goal),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    if result.status == "rejected":
        assert result.descriptor == {}
    else:
        assert result.descriptor["phl_transitivity_boundary"] is None


def test_native_phl_transitivity_abstains_on_non_phl_goal() -> None:
    context = FIXTURES / "true_goal.ec"
    tactic = (
        "transitivity NativeStateCallee.bump "
        "(={arg} ==> ={res}) (={arg} ==> ={res})."
    )
    request = _diagnostic_request(
        request_id="attempt-phl-on-formula-goal",
        context_file=context,
        history_file=FIXTURES / "empty_history.ec",
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "rejected"
    assert result.descriptor == {}
    assert result.structured_error


@pytest.mark.parametrize(
    "tactic",
    (
        "change (0%r < y).",
        "change (0%r <= x).",
        "transitivity true.",
    ),
)
def test_native_relation_realization_abstains_outside_registered_real_le_row(
    tactic: str,
) -> None:
    context = FIXTURES / "real_relation_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _diagnostic_request(
        request_id="attempt-real-bridge-abstain-" + hashlib.sha256(
            tactic.encode("utf-8")
        ).hexdigest()[:8],
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic=tactic,
        expected_goal_identity=active_goal_hash_from_raw(REAL_RELATION_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    if result.status == "accepted":
        assert result.descriptor["relation_bridge"] is None
        assert result.descriptor["relation_bridge_choice"] is None
    else:
        assert result.structured_error


def test_native_no_progress_can_retain_a_typed_execution_blocker() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _diagnostic_request(
        request_id="attempt-no-progress-native-blocker",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="apply (trueI _).",
        observed_outcome_kind="no_progress",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["attempt_outcome"] == "no_progress"
    assert descriptor["native_diagnostic_status"] == "blocker"
    assert descriptor["native_failure_kind"] == "not_functional"
    assert descriptor["native_error_message"] == "too many arguments"
    assert descriptor["application_head"]["resolved_head"]["identity"].endswith(
        ".trueI"
    )


def test_native_attempt_head_survives_unconcretized_module_and_proof_slots() -> None:
    context = FIXTURES / "proof_term_descriptor_goal.ec"
    history = FIXTURES / "proof_term_descriptor_history.ec"
    request = _diagnostic_request(
        request_id="attempt-head-module-proof",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="apply native_descriptor_certificate.",
        observed_outcome_kind="no_progress",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["attempt_outcome"] == "no_progress"
    assert descriptor["native_diagnostic_status"] == "blocker"
    assert descriptor["native_failure_kind"] == "cannot_infer_module"
    assert descriptor["proof_term"] is not None
    head = descriptor["application_head"]
    assert head["resolved_head"]["identity"].endswith(
        ".native_descriptor_certificate"
    )
    assert [slot["kind"] for slot in head["slots"]] == ["module", "proof"]
    assert head["slots"][0]["type"] == "NativeDescriptorOracle"
    assert (
        head["slots"][1].get("type")
        or head["slots"][1].get("formula", {}).get("type")
    ) == "bool"


def test_native_attempt_head_preserves_formula_and_proof_slots() -> None:
    context = FIXTURES / "proof_term_descriptor_goal.ec"
    history = FIXTURES / "proof_term_descriptor_history.ec"
    request = _diagnostic_request(
        request_id="attempt-head-formula-proof",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="apply native_formula_head.",
        observed_outcome_kind="no_progress",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["attempt_outcome"] == "no_progress"
    assert result.descriptor["native_diagnostic_status"] == "no_blocker"
    assert result.descriptor["native_failure_kind"] == ""
    head = result.descriptor["application_head"]
    assert head["resolved_head"]["identity"].endswith(".native_formula_head")
    assert [slot["kind"] for slot in head["slots"]] == ["formula", "proof"]
    assert head["slots"][0]["type"] == "bool"
    assert head["slots"][1]["formula"]["kind"] == "formula"
    assert head["slots"][1]["formula"]["text"] == "b"


def test_native_attempt_head_resolves_local_hypothesis() -> None:
    context = FIXTURES / "local_head_goal.ec"
    history = FIXTURES / "local_head_history.ec"
    request = _diagnostic_request(
        request_id="attempt-local-head",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="apply H.",
        observed_outcome_kind="no_progress",
        expected_goal_identity=active_goal_hash_from_raw(LOCAL_HEAD_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    head = result.descriptor["application_head"]
    assert head["resolved_head"] == {
        "kind": "local",
        "identity": "H",
        "type_arguments": [],
    }
    assert head["slots"] == []
    assert head["result"]["kind"] == "true"


def test_native_attempt_lookup_failure_never_fabricates_head_shape() -> None:
    context = FIXTURES / "true_goal.ec"
    history = FIXTURES / "empty_history.ec"
    request = _diagnostic_request(
        request_id="attempt-missing-head",
        context_file=context,
        history_file=history,
        query_kind="attempt_diagnostic",
        rejected_tactic="apply DoesNotExist.",
        expected_goal_identity=active_goal_hash_from_raw(TRUE_GOAL),
    )

    result = run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
    ).results[0]

    assert result.status == "accepted"
    assert result.descriptor["application_head"] is None
    assert result.descriptor["native_diagnostic_status"] == "blocker"
    assert result.descriptor["native_failure_kind"] in {
        "native_user_error",
        "proof_term_lookup_failure",
        "proof_term_native_user_error",
    }


def test_native_companion_frame_ignores_unframed_easycrypt_output() -> None:
    value = parse_companion_result_frame(
        "* In [theories]:\nprinted declaration\n"
        + NATIVE_SEMANTIC_FRAME_PREFIX
        + '{"status":"accepted"}\n',
        prefix=NATIVE_SEMANTIC_FRAME_PREFIX,
    )

    assert value == {"status": "accepted"}


@pytest.mark.parametrize(
    "stdout",
    [
        "ordinary EasyCrypt output only\n",
        NATIVE_SEMANTIC_FRAME_PREFIX + "{}\n"
        + NATIVE_SEMANTIC_FRAME_PREFIX + "{}\n",
    ],
)
def test_native_companion_frame_requires_one_authoritative_occurrence(
    stdout: str,
) -> None:
    with pytest.raises(RuntimeError, match="exactly one result frame"):
        parse_companion_result_frame(
            stdout,
            prefix=NATIVE_SEMANTIC_FRAME_PREFIX,
        )
