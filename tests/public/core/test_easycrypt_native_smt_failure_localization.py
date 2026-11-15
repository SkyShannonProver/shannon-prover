"""Native EasyCrypt sentinel for the smt-failure localization realizer."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.easycrypt.ec_runtime_identity import (
    discover_easycrypt_runtime_identity,
)
from core.easycrypt.native_semantics import (
    NativeSemanticBatchRequest,
    NativeSemanticQuery,
    run_native_semantic_batch,
)
from core.easycrypt.proof_state_compiler.features.catalog import (
    production_feature_catalog,
)
from core.easycrypt.session.session_projection import active_goal_hash_from_raw

pytestmark = pytest.mark.easycrypt


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "public" / "fixtures" / "native_semantics"
KIND = "smt_failure_localization.first_failed_call"
ALL_REALIZER_KINDS = tuple(sorted(
    codec.kind
    for definition in production_feature_catalog().definitions
    for codec in definition.realization_codecs
))
PURE_CONTEXT = FIXTURES / "smt_failure_goal.ec"
PURE_GOAL = (
    "Current goal\n\nType variables: <none>\n\nx: int\ny: int\n"
    "------------------------------------------------------------------------\n"
    "0 <= x => x + eps = x /\\ holds x /\\ 0 <= x + 1 /\\ holds y\n"
)
PROGRAM_CONTEXT = FIXTURES / "smt_failure_program_goal.ec"
PROGRAM_GOAL = (
    "Current goal\n\nType variables: <none>\n\n"
    "------------------------------------------------------------------------\n"
    "pre = 0 <= arg\n\n    SmtFailureLoop.run \n    [=] 1%r\n\n"
    "post = 0 <= res\n"
)
HISTORY = FIXTURES / "empty_history.ec"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(
    query_kind: str,
    payload: dict,
    *,
    context: Path,
    goal: str,
):
    request = NativeSemanticBatchRequest(
        batch_id=f"batch-smt-{query_kind}",
        context_file=context,
        history_file=HISTORY,
        include_dirs=(),
        queries=(NativeSemanticQuery(
            request_id=f"smt-{query_kind}",
            query_kind=query_kind,
            payload=payload,
        ),),
        expected_goal_identity=active_goal_hash_from_raw(goal),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(HISTORY),
    )
    return run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=120,
    ).results[0]


def _attempt(
    tactic: str,
    *,
    context: Path = PURE_CONTEXT,
    goal: str = PURE_GOAL,
    kinds: tuple[str, ...] = ALL_REALIZER_KINDS,
):
    return _run("attempt_diagnostic", {
        "rejected_tactic": tactic,
        "observed_outcome_kind": "rejected",
        "realizer_kinds": list(kinds),
    }, context=context, goal=goal)


def _localized(descriptor: dict) -> dict:
    realization = descriptor["realization"]
    assert realization is not None and realization["kind"] == KIND
    assert realization["failure_kind"] == "smt_call_failed"
    assert descriptor["operation_family"] == "smt_call"
    assert descriptor["native_failure_kind"] == "smt_call_failed"
    assert descriptor["native_error_message"] == "cannot prove goal (strict)"
    payload = realization["payload"]
    # The strict run stops at the very call report mode first reports.
    assert payload["report_failure_call"] == payload["strict_failure_call"]
    tactic = descriptor["rejected_tactic"].encode("utf-8")
    assert tactic[payload["smt_call_start"]:payload["smt_call_end"]].decode(
        "utf-8"
    ) == payload["smt_call_text"]
    return payload


def _nth(tactic: str, needle: str, occurrence: int) -> int:
    index = -1
    for _ in range(occurrence + 1):
        index = tactic.index(needle, index + 1)
    return index


def test_sequence_reports_the_subgoal_on_which_smt_fails() -> None:
    # split leaves `x + eps = x`, which smt proves, then the conjunction with
    # the abstract `holds`, which it cannot.
    tactic = "move=> H; split; smt()."
    payload = _localized(_attempt(tactic).descriptor)
    assert payload["smt_call_text"] == "smt()"
    assert payload["smt_call_start"] == tactic.index("smt()")
    assert payload["report_failure_call"] == 2
    assert payload["failed_goal_count"] == 1
    assert payload["failed_goal_count_complete"] is True
    assert payload["first_failed_goal_kind"] == "formula"


def test_second_branch_of_a_subgoal_split_is_the_failing_call() -> None:
    tactic = "move=> H; rewrite /eps; split; [smt() | smt()]."
    payload = _localized(_attempt(tactic).descriptor)
    assert payload["smt_call_start"] == _nth(tactic, "smt()", 1)
    assert payload["report_failure_call"] == 2
    assert payload["failed_goal_count"] == 1
    assert payload["first_failed_goal_kind"] == "formula"


def test_call_inside_a_greedy_by_body_is_located() -> None:
    tactic = "by move=> H; split; smt()."
    payload = _localized(_attempt(tactic).descriptor)
    assert payload["smt_call_start"] == tactic.index("smt()")
    assert payload["report_failure_call"] == 2
    assert payload["first_failed_goal_kind"] == "formula"


def test_try_does_not_hide_the_failed_calls_and_counts_every_goal() -> None:
    tactic = "move=> H; progress; try smt()."
    payload = _localized(_attempt(tactic).descriptor)
    assert payload["smt_call_start"] == tactic.index("smt()")
    assert payload["failed_goal_count"] == 2
    assert payload["failed_goal_count_complete"] is True
    assert payload["first_failed_goal_kind"] == "formula"


def test_smt_on_a_program_judgment_names_the_judgment_kind() -> None:
    # auto cannot pass the loop, so smt meets the phoare statement itself.
    payload = _localized(_attempt(
        "proc; auto; smt().",
        context=PROGRAM_CONTEXT,
        goal=PROGRAM_GOAL,
    ).descriptor)
    assert payload["first_failed_goal_kind"] == "phoare_statement"
    assert payload["failed_goal_count"] == 1


def test_failure_that_is_not_an_smt_call_makes_no_claim() -> None:
    result = _attempt("move=> H; rewrite nosuchlemma; smt().")
    assert result.status == "rejected"
    assert result.structured_error["code"] == "unsupported_attempt_shape"


def test_unlocated_intro_pattern_smt_makes_no_claim() -> None:
    # `=> /#` reports its failure without a location in the tactic.
    result = _attempt("move=> H; split => /#.")
    assert result.status == "rejected"


def test_an_accepted_tactic_makes_no_claim() -> None:
    # `first` takes `smt(); smt()`: the tactic leaves a goal but succeeds.
    result = _attempt("move=> H; split; first smt(); smt().")
    assert result.status == "rejected"


def test_realizer_runs_only_when_requested() -> None:
    others = tuple(kind for kind in ALL_REALIZER_KINDS if kind != KIND)
    result = _attempt("move=> H; split; smt().", kinds=others)
    assert result.status == "rejected"


def test_compound_boundary_hands_the_suffix_localization_to_its_consumer() -> None:
    # The #83 shape: auto stops at a loop and the suffix smt meets phoare.
    result = _run("tactic_prefix_diagnostic", {
        "rejected_tactic": "proc; auto; smt().",
        "candidate_prefixes": ["proc.", "proc; auto."],
        "realizer_kinds": list(ALL_REALIZER_KINDS),
    }, context=PROGRAM_CONTEXT, goal=PROGRAM_GOAL)
    assert result.status == "accepted"
    descriptor = result.descriptor
    assert descriptor["accepted_prefixes"] == ["proc.", "proc; auto."]
    assert descriptor["boundary_tactic"] == "smt()."
    boundary = descriptor["boundary_attempt"]
    payload = _localized(boundary)
    assert boundary["rejected_tactic"] == "smt()."
    assert payload["smt_call_start"] == 0
    assert payload["first_failed_goal_kind"] == "phoare_statement"
    assert descriptor["boundary_error_message"] == "cannot prove goal (strict)"
