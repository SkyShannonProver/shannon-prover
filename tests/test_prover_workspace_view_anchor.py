from __future__ import annotations

import json
from pathlib import Path

from workflow.validation.prover_workspace_view_anchor import (
    compare_manifest,
    compare_paths,
    compare_views,
    semantic_fingerprint,
)


def _view(**overrides):
    view = {
        "last_result": {"status": "ok"},
        "proof_status": {
            "status": "open",
            "remaining_goals": 2,
            "remaining_goals_known": True,
            "goal_type": "pRHL",
            "view_focus": "relational_program",
            "current_layer": "call_site",
        },
        "current_goal": {"lines": ["Current goal (remaining: 2)", "x = y"]},
        "program_frontier": {"shape": "call"},
        "application_context": {
            "selected_handles": [{"name": "Hdec"}],
        },
        "facts_and_diagnostics": {"recent_failures": []},
        "candidate_moves": {
            "moves": [
                {"submit": {"intent": "probe_tactic", "payload": {"tactic": "call Hdec."}}},
            ],
            "navigation": [
                {"submit": {"intent": "undo_to_checkpoint"}},
            ],
            "route_health": [
                {"signal": "call_frontier_recovery"},
            ],
        },
        "inspect_lookup_handles": {
            "topics": [{"topic": "goal_info"}, {"topic": "call_subgoals"}],
        },
        "call_site_surface": {
            "live_call_sites": [],
            "frontier_live_named_handles": [{"name": "Hdec"}],
        },
        "structural_checkpoints": [
            {
                "checkpoint_id": "cp_1",
                "semantic_id": "before_call_route",
                "undo_scope": "call_local",
            }
        ],
        "surface_profile": {"mode": "test"},
    }
    view.update(overrides)
    return view


def test_semantic_fingerprint_keeps_agent_relevant_shape() -> None:
    fp = semantic_fingerprint(_view())

    assert fp["proof_status"]["remaining_goals"] == 2
    assert "call_site_surface" in fp["surface_panels"]
    assert fp["candidate_moves"]["move_heads"] == ["call"]
    assert fp["candidate_moves"]["navigation_intents"] == ["undo_to_checkpoint"]
    assert fp["candidate_moves"]["route_health_signals"] == ["call_frontier_recovery"]
    assert fp["structural_checkpoints"]["semantic_ids"] == ["before_call_route"]
    assert fp["inspect_topics"] == ["call_subgoals", "goal_info"]


def test_compare_views_allows_additive_panels_and_signals() -> None:
    candidate = _view(
        proof_memory={"episodes": []},
        candidate_moves={
            "moves": [
                {"submit": {"intent": "probe_tactic", "payload": {"tactic": "call Hdec."}}},
                {"submit": {"intent": "probe_tactic", "payload": {"tactic": "wp."}}},
            ],
            "navigation": [
                {"submit": {"intent": "undo_to_checkpoint"}},
            ],
            "route_health": [
                {"signal": "call_frontier_recovery"},
                {"signal": "local_pure_surgery_available"},
            ],
        },
        structural_checkpoints=[
            {
                "checkpoint_id": "cp_1",
                "semantic_id": "before_call_route",
                "undo_scope": "call_local",
            },
            {
                "checkpoint_id": "cp_2",
                "semantic_ids": ["after_call_opened"],
                "undo_scope": "call_local",
            },
        ],
    )

    result = compare_views(_view(), candidate)

    assert result["status"] == "pass"
    assert result["additive"]["panel_keys"] == ["proof_memory"]
    assert result["additive"]["route_health_signals"] == ["local_pure_surgery_available"]
    assert result["additive"]["structural_checkpoint_semantic_ids"] == ["after_call_opened"]


def test_compare_views_blocks_goal_or_checkpoint_regression() -> None:
    candidate = _view(
        current_goal={"lines": ["Current goal (remaining: 2)", "x <> y"]},
        structural_checkpoints=[],
    )

    result = compare_views(_view(), candidate)

    assert result["status"] == "fail"
    paths = {diff["path"] for diff in result["diffs"]}
    assert "current_goal" in paths
    assert "structural_checkpoints.semantic_ids" in paths


def test_compare_views_ignores_trailing_easycrypt_prompt_line() -> None:
    candidate = _view(
        current_goal={"lines": ["Current goal (remaining: 2)", "x = y", "[358|check]>"]}
    )

    result = compare_views(_view(), candidate)

    assert result["status"] == "pass"


def test_compare_views_accepts_route_health_signal_refined_into_surface() -> None:
    baseline = _view(
        candidate_moves={
            "moves": [],
            "navigation": [],
            "route_health": [{"signal": "pure_tail_alignment_gap"}],
        }
    )
    candidate = _view(
        candidate_moves={
            "moves": [],
            "navigation": [],
            "route_health": [{"signal": "local_membership_decomposition_available"}],
        },
        pure_tail_surface={
            "gap_analysis": [{"signal": "map_key_membership_head_alignment"}],
        },
    )

    result = compare_views(baseline, candidate)

    assert result["status"] == "pass"


def test_compare_views_warns_on_lost_candidate_head() -> None:
    candidate = _view(candidate_moves={"moves": [], "navigation": [], "route_health": []})

    result = compare_views(_view(), candidate)

    assert result["status"] == "fail"
    assert any(
        diff["severity"] == "warning" and diff["path"] == "candidate_moves.move_heads"
        for diff in result["diffs"]
    )
    assert any(
        diff["severity"] == "blocking" and diff["path"] == "candidate_moves.navigation_intents"
        for diff in result["diffs"]
    )


def _reorder_top_level(view: dict, first: str) -> dict:
    """Return a view with the same keys/values but ``first`` moved to the front."""
    reordered = {first: view[first]}
    for key, value in view.items():
        if key != first:
            reordered[key] = value
    return reordered


def test_compare_views_default_ignores_panel_reorder() -> None:
    baseline = _view()
    candidate = _reorder_top_level(baseline, "candidate_moves")

    # Same panel set, different document order.
    assert list(baseline) != list(candidate)
    assert set(baseline) == set(candidate)

    result = compare_views(baseline, candidate)

    assert result["status"] == "pass"
    assert not any(
        diff["path"].startswith("ordering.") for diff in result["diffs"]
    )


def test_compare_views_ordered_warns_on_panel_reorder() -> None:
    baseline = _view()
    candidate = _reorder_top_level(baseline, "candidate_moves")

    result = compare_views(baseline, candidate, require_order=True)

    # Ordering diffs are non-blocking.
    assert result["status"] == "pass"
    ordering = [
        diff for diff in result["diffs"] if diff["path"] == "ordering.panel_order"
    ]
    assert len(ordering) == 1
    assert ordering[0]["severity"] == "warning"
    assert ordering[0]["baseline"] != ordering[0]["candidate"]


def test_compare_views_ordered_passes_when_panel_order_matches() -> None:
    result = compare_views(_view(), _view(), require_order=True)

    assert result["status"] == "pass"
    assert not any(
        diff["path"].startswith("ordering.") for diff in result["diffs"]
    )


def test_compare_views_ordered_warns_on_candidate_moves_reorder() -> None:
    moves_a = {
        "moves": [
            {"submit": {"intent": "probe_tactic", "payload": {"tactic": "call Hdec."}}},
            {"submit": {"intent": "probe_tactic", "payload": {"tactic": "wp."}}},
        ],
        "navigation": [{"submit": {"intent": "undo_to_checkpoint"}}],
        "route_health": [{"signal": "call_frontier_recovery"}],
    }
    moves_b = {
        "moves": [
            {"submit": {"intent": "probe_tactic", "payload": {"tactic": "wp."}}},
            {"submit": {"intent": "probe_tactic", "payload": {"tactic": "call Hdec."}}},
        ],
        "navigation": [{"submit": {"intent": "undo_to_checkpoint"}}],
        "route_health": [{"signal": "call_frontier_recovery"}],
    }
    baseline = _view(candidate_moves=moves_a)
    candidate = _view(candidate_moves=moves_b)

    # Default is order-insensitive: no ordering diff, status pass.
    default_result = compare_views(baseline, candidate)
    assert default_result["status"] == "pass"
    assert not any(
        diff["path"].startswith("ordering.") for diff in default_result["diffs"]
    )

    result = compare_views(baseline, candidate, require_order=True)

    assert result["status"] == "pass"
    ordering = [
        diff for diff in result["diffs"] if diff["path"] == "ordering.candidate_moves"
    ]
    assert len(ordering) == 1
    assert ordering[0]["severity"] == "warning"
    assert ordering[0]["baseline"] == ["call", "wp"]
    assert ordering[0]["candidate"] == ["wp", "call"]


def test_compare_views_ordered_warns_on_inspect_topic_reorder() -> None:
    baseline = _view(
        inspect_lookup_handles={
            "topics": [{"topic": "goal_info"}, {"topic": "call_subgoals"}],
        }
    )
    candidate = _view(
        inspect_lookup_handles={
            "topics": [{"topic": "call_subgoals"}, {"topic": "goal_info"}],
        }
    )

    assert compare_views(baseline, candidate)["status"] == "pass"

    result = compare_views(baseline, candidate, require_order=True)

    assert result["status"] == "pass"
    ordering = [
        diff for diff in result["diffs"] if diff["path"] == "ordering.inspect_topics"
    ]
    assert len(ordering) == 1
    assert ordering[0]["severity"] == "warning"


def test_compare_manifest_reads_cases(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    manifest = tmp_path / "manifest.json"
    baseline.write_text(json.dumps(_view()), encoding="utf-8")
    candidate.write_text(json.dumps(_view(proof_memory={"episodes": []})), encoding="utf-8")
    manifest.write_text(
        json.dumps([
            {
                "label": "same-point",
                "baseline": baseline.name,
                "candidate": candidate.name,
            }
        ]),
        encoding="utf-8",
    )

    assert compare_paths(baseline, candidate)["status"] == "pass"
    result = compare_manifest(manifest)
    assert result["status"] == "pass"
    assert result["cases"][0]["label"] == "same-point"
