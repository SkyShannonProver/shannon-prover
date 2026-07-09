from __future__ import annotations

from workflow.proof_management.route_diversity import (
    ResumeRouteCandidate,
    build_resume_diversity_index,
    resume_diversity_candidate_summary,
    resume_diversity_handoff_note,
    resume_diversity_markdown,
    resume_route_candidate_from_manifest,
)


def test_resume_diversity_index_preserves_score_order_and_groups() -> None:
    candidates = [
        ResumeRouteCandidate(
            path="seq-a/resume.json",
            score=10.0,
            tactic_count=6,
            route_family={"family": "top_level_seq_route"},
        ),
        ResumeRouteCandidate(
            path="seq-b/resume.json",
            score=9.0,
            tactic_count=5,
            route_family={"family": "top_level_seq_route"},
        ),
        ResumeRouteCandidate(
            path="call-a/resume.json",
            score=8.0,
            tactic_count=7,
            route_family={"family": "call_boundary_route"},
        ),
    ]

    index = build_resume_diversity_index(candidates)

    assert [item["path"] for item in index["score_order"]] == [
        "seq-a/resume.json",
        "seq-b/resume.json",
        "call-a/resume.json",
    ]
    assert [item["path"] for item in index["diversity_order"]] == [
        "seq-a/resume.json",
        "call-a/resume.json",
        "seq-b/resume.json",
    ]
    assert index["route_family_groups"]["top_level_seq_route"]["count"] == 2
    assert index["route_family_groups"]["call_boundary_route"]["best_score"] == 8.0
    assert index["mode"] == "shadow"
    assert index["score_order"][0]["score_rank"] == 0

    note = resume_diversity_handoff_note(
        index,
        capsule_path="call-a/resume.json",
    )
    assert "score-rank 3/3" in note
    assert "diversity-rank 2/3" in note
    assert "call_boundary_route" in note

    summary = resume_diversity_candidate_summary(
        index,
        capsule_path="call-a/resume.json",
    )
    assert summary["score_rank"] == 2
    assert summary["diversity_rank"] == 1
    assert summary["route_family"] == "call_boundary_route"

    briefing = resume_diversity_markdown(index)
    assert "# Resume Route Diversity" in briefing
    assert "## Score Order" in briefing
    assert "## Diversity Order" in briefing


def test_resume_route_candidate_from_manifest_reads_lineage_family() -> None:
    candidate = resume_route_candidate_from_manifest(
        path="capsule/resume.json",
        fallback_score=3.0,
        manifest={
            "score": {"value": 5.0},
            "replay": {"tactic_count": 4},
            "lineage": {
                "route_family": {
                    "family": "pure_tail_repair",
                    "confidence": "medium",
                },
            },
        },
    )

    assert candidate.score == 5.0
    assert candidate.tactic_count == 4
    assert candidate.family() == "pure_tail_repair"
