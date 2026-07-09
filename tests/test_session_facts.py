"""Tests for the session-level ProofFact collector."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_facts import (  # noqa: E402
    collect_proof_facts,
    ec_scope_context_fact,
    failed_branch_experiment_cluster_facts,
    first_fact,
    recent_failed_attempt_cluster_facts,
)
from core.easycrypt.session_attempts import classify_failure_shape  # noqa: E402


_SOURCE_FIXTURE = """\
clone import OpCC as OpCCinit with type globS <- unit.
clone FinEager as FiniteRO.

section.
  declare module A <: CCA_Adv.

  local module G2(RO:RO) = {
    proc distinguish() = { return witness; }
  }.

  local equiv poly_mac1 :
    Poly(OpCCinit.OCC).mac ~ D(A).Poly.mac : true ==> ={res}.
  proof. by trivial. qed.
end section.
"""


def _make_session(tmp_path: Path, *, with_failures: bool) -> Path:
    sess = tmp_path / "session"
    sess.mkdir()
    src = tmp_path / "target.ec"
    src.write_text(_SOURCE_FIXTURE, encoding="utf-8")
    (sess / "session_meta.json").write_text(
        json.dumps({"file": str(src), "lemma": "step1"}),
        encoding="utf-8",
    )
    (sess / "current.out").write_text(
        "Current goal\n----\nx = y\n[1|check]>\n",
        encoding="utf-8",
    )
    events: list[dict] = [{"type": "session.started", "payload": {}}]
    if with_failures:
        for i in range(4):
            events.append({
                "event_id": f"try-{i}",
                "type": "tactic.try_result",
                "payload": {
                    "accepted": False,
                    "tactic": f"apply (pr_RO_FinRO_D G2 &m arg{i}).",
                    "report": (
                        "[CLASS: syntax error — argument count mismatch]\n"
                        "wrong number of arguments"
                    ),
                    "error_kind": "other",
                },
            })
    with (sess / "events.jsonl").open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    return sess


def test_scope_and_attempt_cluster_facts_are_lower_inputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess = _make_session(Path(tmp), with_failures=True)
        scope_fact = ec_scope_context_fact(sess)
        cluster_facts = recent_failed_attempt_cluster_facts(sess)
    assert scope_fact is not None
    assert scope_fact.kind == "ec_scope_context"
    assert scope_fact.payload["section_bound_modules"] == ["G2", "A"]
    assert scope_fact.payload["named_equivs"] == ["poly_mac1"]
    assert len(cluster_facts) == 1
    assert cluster_facts[0].kind == "recent_failed_tactic_attempt_cluster"
    assert cluster_facts[0].payload["lemma"] == "pr_RO_FinRO_D"
    assert cluster_facts[0].source_event_ids == ("try-0", "try-1", "try-2", "try-3")


def test_collect_proof_facts_filters_by_kind() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess = _make_session(Path(tmp), with_failures=True)
        facts = collect_proof_facts(
            sess,
            include_kinds=["ec_scope_context"],
        )
    fact = first_fact(facts, "ec_scope_context")
    assert fact is not None
    assert fact.payload["section_bound_modules"] == ["G2", "A"]


def test_failed_branch_experiment_facts_are_generic_memory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess = _make_session(Path(tmp), with_failures=False)
        events = []
        for i in range(2):
            events.append({
                "event_id": f"branch-{i}",
                "type": "tactic.try_result",
                "payload": {
                    "accepted": False,
                    "tactic": "have := MainD(G2, FinRO).distinguish(()).",
                    "report": "wrong number of arguments",
                    "error_kind": "other",
                },
            })
        with (sess / "events.jsonl").open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        facts = failed_branch_experiment_cluster_facts(sess)
    assert len(facts) == 1
    fact = facts[0]
    assert fact.kind == "failed_branch_experiment_cluster"
    assert fact.payload["experiment_kind"] == "bridge_rewrite"
    assert fact.payload["failure_shape"] == "wrong_number_of_arguments"
    assert fact.payload["subject"] == "MainD"
    assert fact.source_event_ids == ("branch-0", "branch-1")
    assert fact.evidence["policy_role"] == "dedupe_memory_only"


def test_proc_goal_form_error_classifies_as_goal_shape_mismatch() -> None:
    shape = classify_failure_shape(
        "[error] expecting a goal of the form: hoare[S], ehoare[S], "
        "phoare[S], equiv[S]"
    )
    assert shape == "goal_shape_mismatch"


def main() -> int:
    test_scope_and_attempt_cluster_facts_are_lower_inputs()
    test_collect_proof_facts_filters_by_kind()
    test_failed_branch_experiment_facts_are_generic_memory()
    test_proc_goal_form_error_classifies_as_goal_shape_mismatch()
    print("PASS test_session_facts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
