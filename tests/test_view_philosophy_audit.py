"""Tests for the runnable panel-philosophy audit.

Covers: the module imports without ImportError (the bug that motivated landing
``core/easycrypt/panel_policy.py``), ``main`` returns an int exit code, and the
reader ``_load_views`` excludes replay run artifacts (report/bootstrap/compare)
so a replay output dir is not mis-read as a directory full of views.
"""
from __future__ import annotations

import json

from workflow.validation import view_philosophy_audit as vpa


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_module_imported_panel_policy_constants():
    # If panel_policy failed to import, these names would be missing.
    assert isinstance(vpa.SIZE_TARGET, int)
    assert isinstance(vpa.SIZE_HARD, int)
    assert vpa.SIZE_HARD >= vpa.SIZE_TARGET


def test_main_on_clean_view_returns_int_zero(tmp_path):
    view = {"current_goal": {"lines": ["x"]}, "candidate_moves": {"moves": []}}
    p = tmp_path / "vp.json"
    _write(p, view)
    rc = vpa.main([str(p)])
    assert isinstance(rc, int)
    assert rc == 0  # no ERROR-severity findings on a clean view


def test_main_returns_nonzero_on_imperative_wording(tmp_path):
    view = {"application_context": {"note": "you must do X before Y"}}
    p = tmp_path / "bad.json"
    _write(p, view)
    rc = vpa.main([str(p)])
    assert isinstance(rc, int)
    assert rc == 1  # imperative wording is an ERROR -> nonzero exit


def test_audit_view_produces_sane_findings():
    # imperative wording -> ERROR; over-budget moves -> WARN.
    view = {
        "application_context": {"note": "you must do X before Y"},
        "candidate_moves": {
            "moves": [{"tactic": f"rewrite h{i}."} for i in range(vpa.MAX_CANDIDATE_MOVES + 2)]
        },
    }
    findings = vpa.audit_view(view, "synthetic")
    codes = {f["code"] for f in findings}
    sevs = {f["severity"] for f in findings}
    assert "wording.imperative" in codes
    assert "budget.moves" in codes
    assert "ERROR" in sevs and "WARN" in sevs
    # every finding carries the label it was audited under.
    assert all(f["view"] == "synthetic" for f in findings)


def test_audit_view_clean_view_no_findings():
    view = {"current_goal": {"lines": ["pr[A] = pr[B]"]}}
    assert vpa.audit_view(view, "clean") == []


def test_load_views_excludes_report_loads_only_turn_file(tmp_path):
    # Simulate a replay output dir: a top-level report.json next to the
    # canonical workspace_views/turn_001.json. Only the turn file is a view.
    wv = tmp_path / "workspace_views"
    wv.mkdir()
    turn = {"current_goal": {"lines": ["g"]}}
    _write(wv / "turn_001.json", turn)
    _write(tmp_path / "report.json", {"kind": "manager_view_replay_report"})
    _write(tmp_path / "bootstrap.json", {"workspace_view": {}})

    loaded = vpa._load_views([str(tmp_path)])
    names = [name for name, _ in loaded]
    assert names == ["turn_001.json"]
    assert loaded[0][1] == turn


def test_load_views_views_dir_fallback(tmp_path):
    # Older replay runs wrote to views/ instead of workspace_views/.
    vdir = tmp_path / "views"
    vdir.mkdir()
    _write(vdir / "turn_000_bootstrap.json", {"current_goal": {"lines": ["a"]}})
    _write(vdir / "turn_001_probe.json", {"current_goal": {"lines": ["b"]}})
    _write(tmp_path / "report.json", {"kind": "report"})

    loaded = vpa._load_views([str(tmp_path)])
    names = sorted(name for name, _ in loaded)
    assert names == ["turn_000_bootstrap.json", "turn_001_probe.json"]


def test_load_views_flat_dir_drops_non_view_json(tmp_path):
    # A flat dir of views (no scoped subdir): keep turn_*.json, drop artifacts.
    _write(tmp_path / "turn_001.json", {"current_goal": {"lines": ["a"]}})
    _write(tmp_path / "compare_report.json", {"kind": "compare"})
    _write(tmp_path / "report.json", {"kind": "report"})
    _write(tmp_path / "other.json", {"not": "a view"})

    loaded = vpa._load_views([str(tmp_path)])
    names = [name for name, _ in loaded]
    assert names == ["turn_001.json"]


def test_load_views_explicit_file_path_loads_even_if_named_report(tmp_path):
    # An explicitly named file is honored even if its name would be filtered
    # out of a directory glob (the caller pointed at it deliberately).
    p = tmp_path / "report.json"
    _write(p, {"current_goal": {"lines": ["x"]}})
    loaded = vpa._load_views([str(p)])
    assert [name for name, _ in loaded] == ["report.json"]


def test_load_views_unwraps_view_envelope(tmp_path):
    # A turn file may store the view under a "view" key (an envelope); the
    # reader should unwrap it.
    inner = {"current_goal": {"lines": ["unwrapped"]}}
    wv = tmp_path / "workspace_views"
    wv.mkdir()
    _write(wv / "turn_001.json", {"view": inner, "meta": "ignored"})
    loaded = vpa._load_views([str(tmp_path)])
    assert loaded[0][1] == inner
