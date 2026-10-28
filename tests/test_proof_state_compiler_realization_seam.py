"""The feature-neutral seam between attempt diagnosis and feature realizers.

A feature declares its realization kinds through its codecs.  The compiler
asks EasyCrypt for exactly the kinds of the features its activation plan
executes, the transport checks only the feature-neutral envelope, and the
owning feature's codec reads every realization that comes back.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from core.easycrypt.native_semantics import (
    NativeSemanticQuery,
    validate_attempt_descriptor,
)
from core.easycrypt.proof_state_compiler import (
    AuthoritativeSnapshotInput,
    CompilationEnvironment,
    ProofStateCompiler,
    ProvenanceRef,
    StateRef,
)
from core.easycrypt.proof_state_compiler.contracts import (
    CompilerTurnEvidence,
    NativeSemanticRequestProduction,
    RealizationCodec,
    TargetRef,
    TransitionRef,
    compiler_invocation_context,
    freeze_json_object,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery import (
    pure_tail_recovery_feature,
)
from core.easycrypt.proof_state_compiler.features.pure_tail_recovery.realization import (
    PURE_TAIL_REWRITE_CODEC,
    PURE_TAIL_REWRITE_KIND,
    pure_tail_rewrite_of,
)
from core.easycrypt.proof_state_compiler.features.relation_bridge_realization.feature import (
    relation_bridge_realization_feature,
)
from tests.proof_state_compiler_test_support import native_state, typed_node
from workflow.proof_state_compiler.activation import AUDIT, OFF, TREATMENT
from workflow.proof_state_compiler.assembly import assemble_feature_set
from workflow.proof_state_compiler.delivery_policies import (
    default_delivery_policy_catalog,
)
from workflow.proof_state_compiler.input_gateway import (
    _native_attempted_operation_descriptor,
)


TACTIC = "rewrite get_setE."
BRIDGE_KINDS = (
    "relation_bridge_realization.bridge",
    "relation_bridge_realization.choice",
)


def _state_ref() -> StateRef:
    return StateRef(
        session_id="realization-seam-test",
        state_version=3,
        goal_identity="realization-seam-goal",
        goal_identity_required=True,
        committed_prefix_identity="a" * 64,
    )


def _inputs():
    state_ref = _state_ref()
    snapshot = AuthoritativeSnapshotInput(
        state_ref=state_ref,
        provenance=ProvenanceRef(
            producer="realization-seam.fixture",
            authority="compiler.input.produced",
            source_sha256="b" * 64,
            artifact_ref="compiler_inputs/realization-seam.json",
            source_event_id="compiler-input-realization-seam",
            source_event_sequence=3,
            authoritative=True,
        ),
        target=TargetRef("eval/realization_seam.ec", "seam"),
        transition=TransitionRef(
            "rejected", state_ref, "compiler_inputs/realization-seam.json"
        ),
        goal_lines=("Current goal", "--------", "z = v"),
        goal_count=1,
        goal_count_known=True,
        closed=False,
        native_state=native_state(
            state_ref,
            formula=typed_node("operator_application", "z = v"),
        ),
    )
    turn = CompilerTurnEvidence(
        source_event_id="realization-seam-failure",
        source_event_sequence=4,
        authority_kind="event_bound_tactic_execution_result",
        artifact_ref="tactic_execution_results/realization-seam.json",
        artifact_hash="c" * 64,
        hash_algorithm="sha256",
        post_state_ref=state_ref,
        intent="commit_tactic",
        payload=freeze_json_object({"tactic": TACTIC}),
        outcome_kind="rejected",
        proof_state_effect="unchanged",
        structured_error="nothing to rewrite",
    )
    return (
        snapshot,
        CompilationEnvironment("realization-seam-environment", (), ()),
        compiler_invocation_context(state_ref, turn),
    )


def _attempt(realization: dict | None) -> dict:
    return {
        "operation_family": "rewrite",
        "rejected_tactic": TACTIC,
        "exact_resource": "get_setE",
        "argument_kinds": ["rewrite_lemma"],
        "side": "",
        "positions": [],
        "native_diagnostic_status": "blocker",
        "native_failure_kind": "rewrite_target_mismatch",
        "native_error_message": "nothing to rewrite",
        "attempt_outcome": "rejected",
        "goal_kind": "formula",
        "application_head": None,
        "proof_term": None,
        "realization": realization,
    }


def _pure_tail_realization(**changes: object) -> dict:
    payload = {
        "source_operation": "rewrite",
        "selected_resource": "get_setE",
        "target_kind": "hypothesis",
        "target_name": "Hupdate",
        "candidate_tactic": "rewrite get_setE in Hupdate.",
        "accepted_target_count": 1,
        **changes,
    }
    return {
        "kind": PURE_TAIL_REWRITE_KIND,
        "failure_kind": "rewrite_target_mismatch",
        "payload": payload,
    }


def test_planner_requests_every_activation_kind_on_each_attempt() -> None:
    snapshot, environment, invocation = _inputs()
    compiler = ProofStateCompiler(features=(
        pure_tail_recovery_feature(),
        relation_bridge_realization_feature(),
    ))
    expected = tuple(sorted((PURE_TAIL_REWRITE_KIND, *BRIDGE_KINDS)))
    assert compiler.realizer_kinds == expected

    plan = compiler.plan_native_semantics(snapshot, environment, invocation)
    assert [request.query.realizer_kinds for request in plan.requests] == [
        expected
    ]

    # Only pure-tail is eligible for this rewrite; the turn's subset still
    # asks for every executed feature's kinds, so its native unit is shared.
    selected = compiler.select_execution_plan(
        compiler.plan_execution(invocation.turn_evidence)
    )
    assert [item.spec.feature_id for item in selected.features] == [
        "pure_tail_recovery"
    ]
    assert selected.realizer_kinds == expected


def test_off_features_are_never_realized_and_audit_matches_treatment() -> None:
    features = (pure_tail_recovery_feature(), relation_bridge_realization_feature())
    policies = tuple(
        policy
        for policy in default_delivery_policy_catalog().definitions
        if policy.compatible_feature_ids == ("pure_tail_recovery",)
    )
    kinds = {
        mode: assemble_feature_set(
            profile_id=f"test:realization-seam:{mode}",
            features=features,
            modes={
                "pure_tail_recovery": mode,
                "relation_bridge_realization": OFF,
            },
            delivery_policies=policies if mode == TREATMENT else (),
        ).compiler.realizer_kinds
        for mode in (AUDIT, TREATMENT)
    }
    assert kinds == {
        AUDIT: (PURE_TAIL_REWRITE_KIND,),
        TREATMENT: (PURE_TAIL_REWRITE_KIND,),
    }


def test_feature_producers_cannot_choose_realizer_kinds() -> None:
    feature = pure_tail_recovery_feature()
    (producer,) = feature.native_semantic_request_producers

    def choosing(*args) -> NativeSemanticRequestProduction:
        production = producer(*args)
        return replace(production, requests=tuple(
            replace(item, query=replace(item.query, realizer_kinds=BRIDGE_KINDS))
            for item in production.requests
        ))

    compiler = ProofStateCompiler(features=(
        replace(feature, native_semantic_request_producers=(choosing,)),
    ))
    with pytest.raises(ValueError, match="cannot choose native realizer kinds"):
        compiler.plan_native_semantics(*_inputs())


def test_feature_codecs_own_their_kinds() -> None:
    feature = pure_tail_recovery_feature()
    with pytest.raises(ValueError, match="must be its own"):
        replace(feature, realization_codecs=(
            RealizationCodec(BRIDGE_KINDS[0], lambda attempt: attempt),
        ))
    with pytest.raises(ValueError, match="duplicate realization kinds"):
        ProofStateCompiler(
            features=(feature,),
            realization_codecs=(PURE_TAIL_REWRITE_CODEC, PURE_TAIL_REWRITE_CODEC),
        )


def test_gateway_reads_each_realization_with_its_owner_and_fails_closed() -> None:
    codecs = {PURE_TAIL_REWRITE_KIND: PURE_TAIL_REWRITE_CODEC}
    attempt = _native_attempted_operation_descriptor(
        _attempt(_pure_tail_realization()), codecs
    )
    assert pure_tail_rewrite_of(attempt).target_name == "Hupdate"
    assert _native_attempted_operation_descriptor(_attempt(None), {}).realization is None

    with pytest.raises(ValueError, match="no active reader"):
        _native_attempted_operation_descriptor(
            _attempt(_pure_tail_realization()), {}
        )
    with pytest.raises(ValueError, match="does not realize its attempt"):
        _native_attempted_operation_descriptor(
            _attempt(_pure_tail_realization(
                selected_resource="set_getE",
                candidate_tactic="rewrite set_getE in Hupdate.",
            )),
            codecs,
        )
    with pytest.raises(ValueError, match="fields are invalid"):
        _native_attempted_operation_descriptor(
            _attempt(_pure_tail_realization(failure_kind="rewrite_target_mismatch")),
            codecs,
        )


def _query(realizer_kinds: list[str]) -> NativeSemanticQuery:
    return NativeSemanticQuery(
        request_id="realization-seam",
        query_kind="attempt_diagnostic",
        payload={
            "rejected_tactic": TACTIC,
            "observed_outcome_kind": "rejected",
            "realizer_kinds": realizer_kinds,
        },
    )


def test_transport_checks_only_the_feature_neutral_envelope() -> None:
    requested = _query([PURE_TAIL_REWRITE_KIND])
    value = _attempt(_pure_tail_realization())
    assert validate_attempt_descriptor(value, query=requested)["realization"] == (
        value["realization"]
    )
    # The payload is the owner's to read; the transport does not open it.
    opaque = _attempt({**_pure_tail_realization(), "payload": {"any": 1}})
    validate_attempt_descriptor(opaque, query=requested)

    with pytest.raises(RuntimeError, match="realization is invalid"):
        validate_attempt_descriptor(value, query=_query([]))
    with pytest.raises(RuntimeError, match="does not explain the blocker"):
        validate_attempt_descriptor(
            {**value, "native_failure_kind": "rewrite_failure"},
            query=requested,
        )
    with pytest.raises(ValueError, match="realizer kinds are invalid"):
        _query(["pure_tail_rewrite"])
    with pytest.raises(ValueError, match="realizer kinds are invalid"):
        _query([PURE_TAIL_REWRITE_KIND, BRIDGE_KINDS[0]][::-1])
