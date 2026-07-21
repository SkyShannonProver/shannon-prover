"""Tests for prover-facing pivot terminology.

The internal pivot sorter still uses tags like ``DISJOINT`` to rank wrapper
tree mismatches. Those words should not leak into the prover view for Pr
bridge checkpoints, because they make a live bridge lemma look irrelevant.
"""
from __future__ import annotations

import json
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_pivot_bridge import (  # noqa: E402
    _bridge_reverses_latest_rewrite,
)
from core.easycrypt.session_hook_phases import (  # noqa: E402
    PivotStrategyPhase,
    _pivot_display_detail,
    _pivot_display_tag,
)
from core.easycrypt.commands.speculative_commands import (  # noqa: E402
    _record_pivot_tool_view,
    _verified_route_option_records,
)
from core.easycrypt.session_hooks import CommitHookContext, HookResult  # noqa: E402
from core.easycrypt.session_events import append_event  # noqa: E402
from core.easycrypt.session_tool_view import make_tool_view, validate_tool_view  # noqa: E402


def _fake_session(tmp_path):
    class FakeSession:
        dir = tmp_path

        def emit_event(self, event_type, payload, source="session_cli"):
            append_event(self.dir, event_type, payload, source=source)

    (tmp_path / "current.out").write_text(
        "Current goal\n----\nx = x\n",
        encoding="utf-8",
    )
    append_event(tmp_path, "session.started", {
        "file": None,
        "lemma": "L",
        "include_dirs": [],
        "discarded_tactic_count": 0,
        "restart_count": 1,
    })
    return FakeSession()


def test_pr_bridge_disjoint_internal_tag_renders_as_checkpoint():
    lem = {
        "name": "pr_CCP_OCCP",
        "statement": (
            "lemma pr_CCP_OCCP (O <: InitRO) (G <: Game) &m : "
            "Pr[A.main() @ &m : res] = Pr[B.main() @ &m : res]."
        ),
    }

    assert _pivot_display_tag(lem, "DISJOINT") == "PR_CHECKPOINT"
    detail = _pivot_display_detail(
        lem,
        "pivot RHS root `OCCP` not reachable from goal RHS root `RealOrcls`",
    )
    assert "live Pr bridge checkpoint" in detail
    assert "`-where pr_CCP_OCCP`" in detail
    assert "not reachable" not in detail


def test_non_pr_disjoint_internal_tag_renders_as_needs_intermediate():
    lem = {
        "name": "equiv_wrapper",
        "statement": "equiv [A.f ~ B.f : ={glob A} ==> ={res}].",
    }

    assert _pivot_display_tag(lem, "DISJOINT") == "NEEDS_INTERMEDIATE"
    detail = _pivot_display_detail(
        lem,
        "wrapper root differs and pivot is not reachable",
    )
    assert "not a one-step" in detail
    assert "irrelevant" in detail
    assert "not reachable" not in detail


def test_structured_pivot_payload_uses_display_tags_only():
    lem = {
        "name": "pr_CCP_OCCP",
        "statement": (
            "lemma pr_CCP_OCCP (O <: InitRO) (G <: Game) &m : "
            "Pr[A.main() @ &m : res] = Pr[B.main() @ &m : res]."
        ),
    }
    phase = PivotStrategyPhase(object())

    recs, evidence = phase._pivot_structured_payload(
        [(4, lem, {
            "tag": "DISJOINT",
            "detail": (
                "pivot RHS root `OCCP` not reachable from goal RHS root "
                "`RealOrcls`"
            ),
            "plan": [],
        })],
        verified=set(),
        tried=set(),
        verification_ran=False,
    )

    assert recs[0]["metadata"]["tag"] == "PR_CHECKPOINT"
    assert recs[0]["metadata"]["unverified_pivot_hint"] is True
    assert recs[0]["metadata"]["source_kind"] == "unverified_pivot_hint"
    assert recs[0]["metadata"]["scheduler_role"] == "unverified_pivot_background"
    assert (
        recs[0]["metadata"]["epistemic_status"]
        == "unverified_pivot_not_frontier_verified"
    )
    assert recs[0]["source_refs"][0]["details"]["tag"] == "PR_CHECKPOINT"
    assert evidence["deterministic"][0]["tag"] == "PR_CHECKPOINT"
    rendered = json.dumps({"recommendations": recs, "evidence": evidence})
    assert "DISJOINT" not in rendered
    assert "not reachable" not in rendered


def test_bridge_reversal_guard_detects_immediate_opposite_rewrite():
    assert _bridge_reverses_latest_rewrite(
        "rewrite (OpCCinit.pr_CCP_OCCP I_stateless G1 &m).",
        "rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).",
    )
    assert _bridge_reverses_latest_rewrite(
        "rewrite -(pr_RO_FinRO_D _ G2 &m () (fun x => x)).",
        "rewrite (pr_RO_FinRO_D _ G2 &m () (fun x => x)).",
    )
    assert not _bridge_reverses_latest_rewrite(
        "rewrite other_bridge.",
        "rewrite -pr_CCP_OCCP.",
    )


def test_commit_time_pivot_phase_does_not_setup_daemon():
    class FakeSession:
        context_file = Path("/missing/context.ec")

        def _load_narrative(self):
            return {}

    phase = PivotStrategyPhase(FakeSession())
    phase._catalog = [{
        "name": "pr_AB",
        "statement": "lemma pr_AB &m : Pr[A.main() @ &m : res] = Pr[B.main() @ &m : res].",
    }]
    phase._target_lemma = ""
    phase._score_pivots = lambda _goal: []  # type: ignore[method-assign]
    called = {"daemon": False}

    def daemon_setup():
        called["daemon"] = True
        return None

    ctx = CommitHookContext(
        session_dir=Path("/tmp/session"),
        trimmed="proc.",
        has_new_error=False,
        no_progress=False,
        prev_count=1,
        curr_count=1,
        active_goal="equiv [A.main ~ B.main : true ==> ={res}]",
        _daemon_setup=daemon_setup,
    )

    phase.run(ctx)

    assert called["daemon"] is False


def test_call_site_options_reject_legacy_narrative_templates():
    class FakeSession:
        def _load_narrative(self):
            return {
                "lemma_catalog": [{
                    "role": "oracle_equiv",
                    "name": "equiv_oracle",
                    "semantic_delta": "same oracle under matched state",
                    "call_template": "call equiv_oracle.",
                    "invariant_sketch": "={glob P}",
                }],
            }

    phase = PivotStrategyPhase(FakeSession())
    result = phase._try_call_suggest(
        "equiv [A.main ~ B.main : ={x} ==> ={res}]",
        None,
    )

    assert result is not None
    assert result.recommendations == []
    assert result.notes[0]["code"] == "call_site_options.legacy_narrative_rejected"
    assert "call_template" not in json.dumps(result.recommendations)

    view = make_tool_view(
        tool="agent-view",
        proof_state={"status": "open"},
        recommendations=result.recommendations,
        evidence=result.evidence,
    ).to_dict()
    validation = validate_tool_view(view)

    assert validation.ok is True
    assert not any("confidence" in warning for warning in validation.warnings)


def test_self_hints_reject_target_lemma_proof_hint_fields():
    class FakeSession:
        def _load_narrative(self):
            return {
                "lemma_catalog": [{
                    "role": "top_level_step",
                    "name": "target",
                    "closer_hints": {"smt_lemmas": ["secret_tail"]},
                    "invariant_sketch": "human invariant",
                    "typical_tail": "by smt(secret_tail).",
                }],
            }

    phase = PivotStrategyPhase(FakeSession())
    phase._target_lemma = "target"

    result = phase._try_self_hints()

    assert result is not None
    assert result.recommendations == []
    assert result.notes[0]["code"] == "self_hints.legacy_narrative_rejected"
    rendered = json.dumps(result.text) + json.dumps(result.evidence)
    assert "secret_tail" not in rendered
    assert "human invariant" not in rendered
    assert "by smt" not in rendered


def test_call_site_options_returns_verified_manager_intent():
    class FakeSession:
        def _load_narrative(self):
            return {}

    class FakeCli:
        def try_tactic(self, session_id, tactic):
            return {"accepted": tactic == "call equiv_oracle."}

    class FakeDbe:
        _session_id = "S"

    phase = PivotStrategyPhase(FakeSession())
    phase._proof_ir_call_site_route = lambda: {  # type: ignore[method-assign]
        "state": "callable_named_call",
        "live_call_sites": [{"id": "call.1"}],
        "named_handles": [{"symbol": "equiv_oracle"}],
        "named_call_templates": [{
            "symbol": "equiv_oracle",
            "status": "direct_named_call",
            "tactic_shape": "call equiv_oracle.",
        }],
    }

    result = phase._try_call_suggest(
        "equiv [A.main ~ B.main : ={x} ==> ={res}]",
        type("Handle", (), {"cli": FakeCli(), "dbe": FakeDbe()})(),
    )

    assert result is not None
    rec = result.recommendations[0]
    assert rec["producer"] == "ProofIR.call_site_route"
    assert rec["confidence"] == "verified"
    assert rec["metadata"]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "call equiv_oracle."},
    }


def test_rewrite_candidates_returns_verified_manager_intent():
    class FakeSession:
        context_file = Path("/missing/context.ec")

        def _get_daemon_meta(self):
            return "", ""

        def _load_narrative(self):
            return {}

    class FakeCli:
        def batch_try(self, session_id, tactics):
            return [
                {"accepted": tactic == "rewrite H.", "no_progress": False}
                for tactic in tactics
            ]

    class FakeDbe:
        _session_id = "S"

    raw_goal = """
H : x = y
------------------------------------------------------------------------
forall z, P x z => P y z
"""
    result = PivotStrategyPhase(FakeSession())._try_rewrite_probe(
        raw_goal,
        type("Handle", (), {"cli": FakeCli(), "dbe": FakeDbe()})(),
    )

    assert result is not None
    rec = result.recommendations[0]
    assert rec["confidence"] == "verified"
    assert rec["metadata"]["submit"] == {
        "intent": "commit_tactic",
        "payload": {"tactic": "rewrite H."},
    }
    assert "-next" not in result.text


def test_rewrite_candidates_reports_daemon_unavailable():
    class FakeSession:
        context_file = Path("/missing/context.ec")

        def _get_daemon_meta(self):
            return "", ""

        def _load_narrative(self):
            return {}

    raw_goal = """
H : x = y
------------------------------------------------------------------------
forall z, P x z => P y z
"""
    result = PivotStrategyPhase(FakeSession())._try_rewrite_probe(raw_goal, None)

    assert result is not None
    assert result.recommendations == []
    assert result.errors[0]["code"] == "rewrite_candidates.daemon_unavailable"


def test_verified_route_option_registry_keeps_only_verified_submits():
    records = _verified_route_option_records(
        mode="bridge",
        topic="bridge_options",
        recommendations=[
            {
                "id": "bridge_options.verified.0",
                "producer": "deterministic_pr_bridge_compiler",
                "action": "rewrite H.",
                "why": "verified route",
                "action_type": "runnable_tactic",
                "confidence": "verified",
                "preconditions": ["proof_state.status == open"],
                "source_refs": [{"kind": "lemma", "id": "H"}],
                "evidence_refs": ["preflight.route.0"],
                "metadata": {
                    "bindings": {"namespace": "M"},
                    "chain": ["rewrite H."],
                    "submit": {
                        "intent": "commit_tactic",
                        "payload": {"tactic": "rewrite H."},
                    },
                },
            },
            {
                "id": "legacy.context",
                "producer": "legacy",
                "action": "call stale.",
                "action_type": "strategy_hint",
                "confidence": "medium",
                "metadata": {},
            },
        ],
        evidence={
            "context": [{"id": "context.route"}],
            "preflight": [{
                "id": "preflight.route.0",
                "accepted": True,
                "producer": "ec_daemon.try_tactic",
            }],
        },
    )

    assert len(records) == 1
    assert records[0]["kind"] == "verified_route_option"
    assert records[0]["submit"]["intent"] == "commit_tactic"
    assert records[0]["bindings"] == {"namespace": "M"}
    assert records[0]["verification_evidence"][0]["accepted"] is True


def test_pivot_tool_view_ignores_inflight_pivot_inspect_event(tmp_path):
    session = _fake_session(tmp_path)
    append_event(tmp_path, "tool.called", {
        "name": "pivot-inspect",
        "mutates_proof_state": False,
        "session_dir": str(tmp_path),
    })

    view = _record_pivot_tool_view(
        session,
        "bridge",
        [],
        "",
        "no_matching_context",
    )

    assert view is not None
    assert view["proof_state"]["event_contract"]["ok"] is True


# ---- Evidence robustness (merged from test_pivot_tool_view_evidence_robustness.py)
#
# Regression: a pivot inspect must not crash on malformed `evidence` buckets.
#
# Bug (2026-05-30, chachapoly step3 run): `inspect_context
# topic=call_invariant_skeleton` crashed the backend with
# `TypeError: 'bool' object is not iterable`. Root cause: the relational-invariant
# skeleton producer emitted `HookResult(evidence={"static": True,
# "predicates_examined": <int>})` — scalar values — while the aggregator
# `_record_pivot_tool_view` treats every evidence bucket as a list[dict] and does
# `[item for item in (items or [])]`, which iterates the scalar.
#
# Two-layer fix under test:
#   * producer now emits the diagnostic as a contract-conforming list[dict]
#     (`evidence={"static": [ {...} ]}`); and
#   * the aggregator skips any non-list bucket so a single misbehaving producer
#     can never crash a read-only inspect that co-runs several producers.
#
# Pure: no EasyCrypt needed.


def test_scalar_evidence_bucket_does_not_crash_pivot_inspect(tmp_path):
    """The exact crash: a producer emits scalar evidence values."""
    session = _fake_session(tmp_path)

    # Shaped like the pre-fix relational-invariant skeleton emit.
    legacy_bad = HookResult(
        text="[CALL-INVARIANT-SKELETON] ...\n",
        layer=2,
        kind="recommendation",
        recommendations=[{"id": "rel.0", "kind": "call_invariant_skeleton",
                          "action": "call (_: inv ...)."}],
        evidence={"static": True, "predicates_examined": 3},
    )

    # Must not raise (pre-fix this raised TypeError: 'bool' object is not iterable).
    view = _record_pivot_tool_view(
        session, "call_invariant_skeleton", [legacy_bad], legacy_bad.text,
        "available",
    )
    assert view is not None


def test_conforming_and_malformed_buckets_aggregate_cleanly(tmp_path):
    """Well-formed list buckets aggregate; scalar/dict buckets are skipped."""
    session = _fake_session(tmp_path)

    glob_result = HookResult(
        text="[CALL-INVARIANT-SKELETON] glob frame\n",
        layer=3,
        kind="recommendation",
        evidence={"context": [{"id": "ctx.glob", "detail": "={glob X}"}]},
    )
    # The post-fix relational producer shape: diagnostic as a list[dict] item.
    relational_result = HookResult(
        text="[CALL-INVARIANT-SKELETON] relational carrier\n",
        layer=2,
        kind="recommendation",
        evidence={"static": [{
            "id": "relational_invariant_skeleton.static",
            "assembled": "statically",
            "predicates_examined": 3,
        }]},
    )
    # A stray scalar bucket from any producer must be ignored, not fatal.
    noisy_result = HookResult(
        text="noise\n",
        layer=2,
        evidence={"oops": True, "count": 7},
    )

    view = _record_pivot_tool_view(
        session,
        "call_invariant_skeleton",
        [glob_result, relational_result, noisy_result],
        "text",
        "available",
    )
    assert view is not None

    evidence = view["evidence"]
    # Conforming buckets survived with their items intact.
    assert any(it.get("id") == "ctx.glob" for it in evidence.get("context", []))
    assert any(
        it.get("id") == "relational_invariant_skeleton.static"
        for it in evidence.get("static", [])
    )
    # The scalar "oops"/"count" bucket was skipped (no crash, no garbage items).
    assert all(isinstance(item, dict) for item in evidence.get("oops", []))
    assert evidence.get("count", []) == []
