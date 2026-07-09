"""Tests for recent failed tactic-attempt clustering."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_attempts import (  # noqa: E402
    branch_experiment_subject,
    classify_branch_experiment_kind,
    classify_failure_shape,
    cluster_failed_branch_experiments,
    cluster_recent_failed_tactic_attempts,
    extract_lemma_and_modules,
    failed_tactic_attempt_from_dict,
    read_failed_tactic_attempts,
)


def _failure(tactic: str, *, event_id: str = "") -> dict:
    return {
        "event_id": event_id,
        "tactic": tactic,
        "error_text": (
            "[CLASS: syntax error - argument count mismatch]\n"
            "wrong number of arguments"
        ),
        "error_kind": "other",
    }


def test_extract_lemma_and_modules_keeps_attempt_parsing_low_level() -> None:
    extracted = extract_lemma_and_modules(
        "apply (pr_RO_FinRO_D G2 &m tt (fun x => x)).",
    )
    assert extracted is not None
    lemma, modules = extracted
    assert lemma == "pr_RO_FinRO_D"
    assert modules == ["G2"]


def test_cluster_recent_failed_tactic_attempts_groups_by_lemma() -> None:
    failures = [
        _failure("apply (pr_RO_FinRO_D G2 &m).", event_id="try-0"),
        _failure("apply (pr_RO_FinRO_D G2 &m tt).", event_id="try-1"),
        _failure(
            "apply (pr_RO_FinRO_D G2 &m tt (fun x => x)).",
            event_id="try-2",
        ),
    ]
    clusters = cluster_recent_failed_tactic_attempts(failures)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.lemma == "pr_RO_FinRO_D"
    assert cluster.module_args == ("G2",)
    assert cluster.source_event_ids == ("try-0", "try-1", "try-2")
    assert len(cluster.sample_tactics) == 3


def test_read_failed_tactic_attempts_from_session_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess = Path(tmp)
        events = [
            {"event_id": "ok", "type": "tactic.try_result", "payload": {
                "accepted": True,
                "tactic": "trivial.",
            }},
            {"event_id": "bad", "type": "tactic.try_result", "payload": {
                "accepted": False,
                "tactic": "apply (pr_RO_FinRO_D G2 &m).",
                "report": "wrong number of arguments",
                "error_kind": "other",
            }},
        ]
        with (sess / "events.jsonl").open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        attempts = read_failed_tactic_attempts(sess)
    assert len(attempts) == 1
    assert attempts[0].event_id == "bad"
    assert attempts[0].lemma == "pr_RO_FinRO_D"
    assert attempts[0].module_args == ("G2",)


def test_failed_branch_experiment_clusters_generic_shapes() -> None:
    failures = [
        _failure("have := MainD(G2, FinRO).distinguish(()).", event_id="try-0"),
        _failure("have H := MainD(G2, FinRO).distinguish(()).", event_id="try-1"),
    ]
    clusters = cluster_failed_branch_experiments(failures)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.experiment_kind == "bridge_rewrite"
    assert cluster.failure_shape == "wrong_number_of_arguments"
    assert cluster.subject == "MainD"
    assert cluster.source_event_ids == ("try-0", "try-1")


def test_branch_experiment_classifiers_are_low_cardinality() -> None:
    assert classify_failure_shape("expecting a proof-term, not a formula") == (
        "proof_term_mismatch"
    )
    assert classify_branch_experiment_kind("byequiv => //.") == (
        "proof_mode_lowering"
    )
    assert branch_experiment_subject(
        failed_tactic_attempt_from_dict({
            "tactic": "call (_: Inv).",
            "error_text": "cannot unify",
            "event_id": "x",
        })
    ) == "call"


def main() -> int:
    test_extract_lemma_and_modules_keeps_attempt_parsing_low_level()
    test_cluster_recent_failed_tactic_attempts_groups_by_lemma()
    test_read_failed_tactic_attempts_from_session_events()
    test_failed_branch_experiment_clusters_generic_shapes()
    test_branch_experiment_classifiers_are_low_cardinality()
    print("PASS test_session_attempts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
