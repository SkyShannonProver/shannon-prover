"""Unit tests for the runtime panel-invariant checker (panel_invariants.py)."""
from __future__ import annotations

from core.easycrypt.analysis.panel_invariants import check_panel_invariants


def _clean_view():
    return {
        "current_goal": {
            "lines": [
                "Current goal", "", "Type variables: <none>", "",
                "&m: {}", "-" * 40, "pre = true",
                "( 1)  v1 <- e1", "( 2)  v2 <- e2", "( 3)  v3 <$ d3",
                "( 4)  r <@ M.p(x)", "post = true", "[10|check]>",
            ],
            "goal_type": "phoare", "text_fully_shown": True,
        },
        "proof_status": {"status": "open", "remaining_goals": 1, "goal_type": "phoare"},
        "program_frontier": {
            "procedure_navigation": {
                "absorb_depth": {"left": {"absorbable_statements": 2, "through_order": 2}},
            },
        },
        "facts_and_diagnostics": {"facts": {"unfoldable_goal_heads": [
            {"name": "pre", "declaration_kind": "op"},  # not a <@ call -> fine
        ]}},
        "inspect_lookup_handles": {"ask_manager_for": [
            {"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}},
        ]},
    }


def _invs(view, **kw):
    return {v["invariant"] for v in check_panel_invariants(view, **kw)}


def test_clean_view_has_no_violations():
    assert check_panel_invariants(_clean_view()) == []


def test_status_leak_caught():
    v = _clean_view()
    v["proof_status"]["status"] = "error"   # action outcome leaked into the panel
    assert "status_committed_state" in _invs(v)


def test_sp_non_contiguous_caught():
    v = _clean_view()
    # absorb 3 but through_order 12 -> the count crosses a frontier (the P1/step1 bug)
    v["program_frontier"]["procedure_navigation"]["absorb_depth"]["left"] = {
        "absorbable_statements": 3, "through_order": 12,
    }
    assert "sp_absorb_contiguous" in _invs(v)


def test_sp_over_program_length_caught():
    v = _clean_view()
    v["program_frontier"]["procedure_navigation"]["absorb_depth"]["left"] = {
        "absorbable_statements": 99, "through_order": 99,
    }
    assert "sp_absorb_bound" in _invs(v)


def test_unfoldable_procedure_caught():
    v = _clean_view()
    v["facts_and_diagnostics"]["facts"]["unfoldable_goal_heads"] = [
        {"name": "M.p", "declaration_kind": "op"},   # M.p IS the `<@ M.p(x)` call
    ]
    assert "unfoldable_not_procedure" in _invs(v)


def test_eager_on_single_sided_caught():
    v = _clean_view()
    v["inspect_lookup_handles"]["ask_manager_for"].append(
        {"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}
    )
    assert "eager_two_sided_only" in _invs(v)


def test_eager_on_two_sided_is_fine():
    v = _clean_view()
    v["current_goal"]["goal_type"] = "pRHL"
    v["proof_status"]["goal_type"] = "pRHL"
    v["inspect_lookup_handles"]["ask_manager_for"].append(
        {"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}
    )
    assert "eager_two_sided_only" not in _invs(v)


def test_goal_text_fidelity_caught():
    v = _clean_view()
    raw = list(v["current_goal"]["lines"])
    raw[7] = "( 1)  v1 <- MANGLED"
    assert "goal_text_fidelity" in _invs(v, raw_goal_lines=raw)


def test_goal_text_fidelity_clean_when_equal():
    v = _clean_view()
    raw = list(v["current_goal"]["lines"])
    assert "goal_text_fidelity" not in _invs(v, raw_goal_lines=raw)


def test_checker_never_raises_on_garbage():
    for junk in (None, {}, {"current_goal": 5}, {"proof_status": []}, 42):
        # must return a list, never raise
        assert isinstance(check_panel_invariants(junk), list)
