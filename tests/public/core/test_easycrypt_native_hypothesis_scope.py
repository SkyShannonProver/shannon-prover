"""Native sentinel for the hypothesis-scope realizer at real EasyCrypt states.

EasyCrypt names the failing reference (the located smt hint, or the first
rejected rewrite-item prefix) and decides every scope fact; these tests pin
that the companion reports exactly those facts and abstains otherwise.
"""

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
KIND = "hypothesis_scope_diagnosis.out_of_scope_hypothesis"
# Every production realizer runs, as in the treatment, so a claim here also
# shows that no other realizer claims the same trigger.
ALL_REALIZER_KINDS = tuple(sorted(
    codec.kind
    for definition in production_feature_catalog().definitions
    for codec in definition.realization_codecs
))

SMT_GOAL = """Current goal

Type variables: <none>

g: int -> bool
x: int
H4: forall (y : int), g y
------------------------------------------------------------------------
g x
"""
SMT_INITIAL_GOAL = """Current goal

Type variables: <none>

g: int -> bool
x: int
------------------------------------------------------------------------
(forall (y : int), g y) => g x
"""
REWRITE_GOAL = """Current goal

Type variables: <none>

b: bool
c: bool
l: int list
H18: (if b || c then [] else l) = l
Hbad: b || c
------------------------------------------------------------------------
l = []
"""
REWRITE_INITIAL_GOAL = """Current goal

Type variables: <none>

b: bool
c: bool
l: int list
------------------------------------------------------------------------
(if b || c then [] else l) = l => b || c => l = []
"""
REWRITE_BEFORE_GOAL = """Current goal

Type variables: <none>

b: bool
c: bool
l: int list
Hbad: b || c
H18: size l = 0
------------------------------------------------------------------------
l = []
"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(
    stem: str,
    goal: str,
    tactics: tuple[str, ...],
    *,
    history: str | None = None,
    prefixes: tuple[str, ...] | None = None,
):
    context = FIXTURES / f"hypothesis_scope_{stem}_goal.ec"
    history_file = FIXTURES / (
        history or f"hypothesis_scope_{stem}_history.ec"
    )
    queries = tuple(
        NativeSemanticQuery(
            request_id=f"hypothesis-scope-{stem}-{index}",
            query_kind=(
                "attempt_diagnostic" if prefixes is None
                else "tactic_prefix_diagnostic"
            ),
            payload=(
                {
                    "rejected_tactic": tactic,
                    "observed_outcome_kind": "rejected",
                    "realizer_kinds": list(ALL_REALIZER_KINDS),
                }
                if prefixes is None
                else {
                    "rejected_tactic": tactic,
                    "candidate_prefixes": list(prefixes),
                    "realizer_kinds": list(ALL_REALIZER_KINDS),
                }
            ),
        )
        for index, tactic in enumerate(tactics)
    )
    request = NativeSemanticBatchRequest(
        batch_id=f"batch-hypothesis-scope-{stem}",
        context_file=context,
        history_file=history_file,
        include_dirs=(),
        queries=queries,
        expected_goal_identity=active_goal_hash_from_raw(goal),
        expected_context_sha256=_sha256(context),
        expected_history_sha256=_sha256(history_file),
    )
    return run_native_semantic_batch(
        request,
        runtime_identity=discover_easycrypt_runtime_identity(),
        timeout=120,
    ).results


def _realized(descriptor: dict) -> dict | None:
    realization = descriptor["realization"]
    if realization is None or realization["kind"] != KIND:
        return None
    assert realization["failure_kind"] == descriptor["native_failure_kind"]
    return {**realization["payload"], "failure_kind": realization["failure_kind"]}


def _smt_payload(**changes) -> dict:
    payload = {
        "source_operation": "smt",
        "written_name": "H4",
        "reference_position": 1,
        "reference_count": 1,
        "target_name": "",
        "lookup_scope": "global_declarations",
        "goal_hypothesis": True,
        "declared_after_target": False,
        "candidate_tactic": "",
        "remaining_hints": [],
        "failure_kind": "smt_hint_names_goal_hypothesis",
    }
    payload.update(changes)
    return payload


def _rewrite_payload(**changes) -> dict:
    payload = {
        "source_operation": "rewrite",
        "written_name": "Hbad",
        "reference_position": 1,
        "reference_count": 1,
        "target_name": "H18",
        "lookup_scope": "context_before_target",
        "goal_hypothesis": True,
        "declared_after_target": True,
        "candidate_tactic": "",
        "remaining_hints": [],
        "failure_kind": "rewrite_name_declared_after_target",
    }
    payload.update(changes)
    return payload


def test_smt_hints_naming_a_goal_hypothesis() -> None:
    alone, with_lemma, with_unknown, closing = _run(
        "smt",
        SMT_GOAL,
        ("smt(H4).", "smt(f_all H4).", "smt(H4 nosuch).", "by smt(f_all H4)."),
    )

    for result in (alone, with_lemma, with_unknown, closing):
        assert result.status == "accepted"
        assert result.descriptor["operation_family"] == "smt"
        assert result.descriptor["exact_resource"] == "H4"
        # EasyCrypt's own report, carried for display only.
        assert result.descriptor["native_error_message"] == (
            "cannot find lemma `H4'"
        )
    # smt() keeps the call's prover settings and gets no extra lemma.
    assert _realized(alone.descriptor) == _smt_payload(
        candidate_tactic="smt().",
    )
    assert _realized(with_lemma.descriptor) == _smt_payload(
        reference_position=2,
        reference_count=2,
        candidate_tactic="smt(f_all).",
        remaining_hints=["f_all"],
    )
    # Without H4 EasyCrypt stops at `nosuch`, so no candidate is offered.
    assert _realized(with_unknown.descriptor) == _smt_payload(
        reference_count=2,
    )
    # Under a closing `by` the facts hold; no candidate is spelled.
    assert _realized(closing.descriptor) == _smt_payload(
        reference_position=2, reference_count=2,
    )


def test_smt_hint_that_is_not_a_goal_hypothesis_abstains() -> None:
    unknown, unknown_first, theory = _run(
        "smt",
        SMT_GOAL,
        ("smt(nosuch).", "smt(nosuch H4).", "smt(@H4)."),
    )

    # No realizer describes the attempt, so EasyCrypt's error stays the
    # only report; the first unresolved hint decides, and it is `nosuch`.
    for result in (unknown, unknown_first, theory):
        assert result.status == "rejected"
        assert result.structured_error["code"] == "unsupported_attempt_shape"


def test_rewrite_name_declared_after_its_target() -> None:
    direct, chained, closing, visible, unknown = _run(
        "rewrite",
        REWRITE_GOAL,
        (
            "rewrite Hbad in H18.",
            "rewrite /= Hbad in H18.",
            "by rewrite Hbad in H18.",
            "rewrite H18 in Hbad.",
            "rewrite nosuch in H18.",
        ),
    )

    assert direct.status == "accepted"
    assert direct.descriptor["operation_family"] == "rewrite"
    assert direct.descriptor["exact_resource"] == "Hbad"
    assert direct.descriptor["native_error_message"] == "unknown lemma `Hbad'"
    assert _realized(direct.descriptor) == _rewrite_payload()
    # The accepted `rewrite /= in H18` prefix names the second item.
    assert _realized(chained.descriptor) == _rewrite_payload(
        reference_position=2, reference_count=2,
    )
    # `by` runs its body first, so the body's failure is the commit's.
    assert closing.descriptor["native_error_message"] == "unknown lemma `Hbad'"
    assert _realized(closing.descriptor) == _rewrite_payload()
    # H18 is in the context before Hbad: the rewrite fails for another
    # reason, which this slice does not explain.
    for result in (visible, unknown):
        assert result.status == "rejected"


def test_rewrite_name_declared_before_its_target_abstains() -> None:
    (result,) = _run(
        "rewrite_before", REWRITE_BEFORE_GOAL, ("rewrite Hbad in H18.",),
    )

    assert result.status == "rejected"
    assert result.structured_error["code"] == "unsupported_attempt_shape"


def test_compound_suffix_is_diagnosed_after_the_accepted_prefix() -> None:
    (rewrite,) = _run(
        "rewrite",
        REWRITE_INITIAL_GOAL,
        ("move=> H18 Hbad; rewrite Hbad in H18.",),
        history="empty_history.ec",
        prefixes=("move=> H18 Hbad.",),
    )
    (smt,) = _run(
        "smt",
        SMT_INITIAL_GOAL,
        ("move=> H4; smt(H4).",),
        history="empty_history.ec",
        prefixes=("move=> H4.",),
    )

    assert rewrite.status == "accepted"
    assert rewrite.descriptor["prefix_effects"] == ["accepted_changed"]
    assert rewrite.descriptor["boundary_tactic"] == "rewrite Hbad in H18."
    assert _realized(rewrite.descriptor["boundary_attempt"]) == (
        _rewrite_payload()
    )
    assert smt.status == "accepted"
    assert smt.descriptor["boundary_tactic"] == "smt(H4)."
    assert _realized(smt.descriptor["boundary_attempt"]) == _smt_payload(
        candidate_tactic="smt().",
    )


def test_compound_stage_over_several_goals_has_facts_but_no_candidate() -> None:
    """`t1; t2` runs t2 on every goal t1 leaves; the candidate is checked
    at one goal only, so none is offered."""

    (result,) = _run(
        "smt",
        SMT_INITIAL_GOAL,
        ("move=> H4; case: (x = 0); smt(H4).",),
        history="empty_history.ec",
        prefixes=("move=> H4.", "move=> H4; case: (x = 0)."),
    )

    assert result.status == "accepted"
    assert result.descriptor["accepted_prefixes"] == [
        "move=> H4.", "move=> H4; case: (x = 0).",
    ]
    assert _realized(result.descriptor["boundary_attempt"]) == _smt_payload()
