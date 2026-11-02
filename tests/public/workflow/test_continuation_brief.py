from __future__ import annotations

import hashlib
import json

from workflow.agents.prover_writeback import _extract_prover_report
from workflow.node.continuation_brief import (
    append_source_breadcrumb,
    continuation_brief_from_outer_handoff,
    merge_agent_report,
    render_continuation_brief_markdown,
)
from workflow.node.proof_node_resume import load_resume_capsule


def _anchor() -> dict[str, str]:
    declaration = "lemma useful : true."
    return {
        "symbol": "Useful.useful",
        "intended_use": "apply",
        "role": "closes the residual proposition",
        "source_ref": "theories/Useful.ec:1",
        "declaration_sha256": hashlib.sha256(
            declaration.encode("utf-8")
        ).hexdigest(),
        "declaration": declaration,
    }


def test_report_has_only_blockers_and_evidence_grounded_discoveries() -> None:
    parsed = _extract_prover_report(
        'PROVER REPORT: {"blockers":["rewrite H rejects at goal 2"],'
        '"discoveries":["Useful.useful resolves natively"],'
        '"suggestions":["try something else"],"open_questions":["why?"]}'
    )

    assert parsed == {
        "blockers": ["rewrite H rejects at goal 2"],
        "discoveries": ["Useful.useful resolves natively"],
    }


def test_report_parser_accepts_braces_inside_json_strings() -> None:
    parsed = _extract_prover_report(
        'PROVER REPORT: {"blockers":["goal contains {x} and unmatched }"],'
        '"discoveries":[]}'
    )
    assert parsed == {
        "blockers": ["goal contains {x} and unmatched }"],
        "discoveries": [],
    }


def test_outer_handoff_becomes_bounded_durable_brief() -> None:
    suffix = "x" * 13_000
    brief = continuation_brief_from_outer_handoff({
        "kind": "outer_proof_handoff",
        "strategy_note": "Preserve the coupling invariant.",
        "failed_tactic": "call bad.",
        "failure_summary": "unknown lemma bad",
        "candidate_suffix": suffix,
        "resource_anchors": [_anchor()],
    })
    merged = merge_agent_report(brief, {
        "blockers": ["The call needs a stronger precondition."],
        "discoveries": ["Useful.useful is available."],
        "suggestions": ["ignored"],
    })

    assert len(merged["candidate_suffix"]) == 12_000
    assert merged["candidate_suffix_truncated"] is True
    assert merged["candidate_suffix_full_chars"] == 13_000
    assert merged["blockers"] == ["The call needs a stronger precondition."]
    assert "suggestions" not in merged
    rendered = render_continuation_brief_markdown(merged)
    assert "Decide the next proof strategy yourself" in rendered
    assert "Useful.useful" in rendered


def test_missing_report_fields_preserve_prior_continuation_guidance() -> None:
    prior = merge_agent_report({}, {
        "blockers": ["old blocker"],
        "discoveries": ["old discovery"],
    })
    assert merge_agent_report(prior, {})["blockers"] == ["old blocker"]
    partial = merge_agent_report(prior, {"blockers": ["new blocker"]})
    assert partial["blockers"] == ["new blocker"]
    assert partial["discoveries"] == ["old discovery"]


def test_source_breadcrumbs_are_bounded_and_durable() -> None:
    brief: dict = {}
    for index in range(20):
        brief = append_source_breadcrumb(brief, {
            "event": "easycrypt.source_resource.search",
            "status": "served",
            "query": f"lemma_{index}",
            "scope": "libraries",
            "match_count": 1,
            "locations": [f"theories/T.ec:{index + 1}"],
        })
    assert len(brief["source_breadcrumbs"]) == 12
    assert brief["source_breadcrumbs"][-1]["query"] == "lemma_19"
    assert "Source locations already inspected" in (
        render_continuation_brief_markdown(brief)
    )


def test_resume_capsule_restores_continuation_brief(tmp_path) -> None:
    capsule = tmp_path / "capsule"
    capsule.mkdir()
    (capsule / "history.ec").write_text("proc.\n", encoding="utf-8")
    brief = merge_agent_report({}, {
        "blockers": ["The residual equality has reversed operands."],
        "discoveries": ["The prefix through proc. is accepted."],
    })
    (capsule / "resume.json").write_text(json.dumps({
        "kind": "proof_node_resume_capsule",
        "capsule_version": 2,
        "target": {"file": "target.ec", "lemma": "L", "include_dir": ""},
        "source": {"session_name": ".ec_session_prover_tree_0_0"},
        "replay": {
            "history_file": "history.ec",
            "tactic_count": 1,
            "resume_prefix_count": 1,
            "current_goal_hash": "a" * 64,
            "proof_status": "proof_open",
            "goal_identity_required": True,
            "current_goal_file": "",
            "current_goal_preview": "goal",
        },
        "score": {"value": 1.0, "reasons": []},
        "lineage": {"route_family": {}},
        "handoff": {
            "notes": [],
            "recent_tactics": [],
            "route_event_facts": [],
            "continuation_brief": brief,
        },
    }), encoding="utf-8")

    loaded = load_resume_capsule(capsule)
    assert loaded.resume_context is not None
    assert loaded.resume_context["continuation_brief"] == brief
