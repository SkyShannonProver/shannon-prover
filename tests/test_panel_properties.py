"""Generative PROPERTY tests for agent-view panel fidelity.

Instead of replaying recorded traces (which only proves "no bug on THIS batch"),
these tests ENUMERATE the finite structural space the panel must handle and assert
panel INVARIANTS over every synthetic shape — turning "are we done?" into a
measurable coverage number.

The structural space (the dimensions that actually drive panel behavior):
  program  = sequences over {ASSIGN, SAMPLE, CALL, LOOP, BRANCH}
  goal class = {hoare, phoare, equiv, pRHL, probability(=, <=, |diff|), ambient}
  status   = {open, closed, error, no_progress}
  lexical  = {single-digit `( 1)` vs flush `(10)` numbering, primes, `<:T>`/`<none>`}

Each test drives the PURE analysis/render functions (no live EasyCrypt) and asserts
an invariant that, if it holds for the whole enumerated space, closes that bug class.
Companion to the live replay harness (`tools/panel_audit/`): properties here, real
EC integration there.
"""
from __future__ import annotations

import itertools

import pytest

from core.easycrypt.analysis.ec_procedure_frontend import (
    procedure_statements_from_pretty_goal,
    procedure_straight_line_prefix,
    build_procedure_body_frontend,
)
from core.easycrypt.analysis.ec_procedure_actions import procedure_navigation_map

# ---------------------------------------------------------------------------
# Synthetic EC-pretty program rendering
# ---------------------------------------------------------------------------
_STMT_TPL = {
    "A": "v{i} <- e{i}",          # ASSIGN
    "S": "v{i} <$ d{i}",          # SAMPLE
    "C": "v{i} <@ M.p{i}(x)",     # CALL
    "L": "while (i < n) {{",      # LOOP (WHILE)
    "B": "if (b{i}) {{",          # BRANCH (IF)
}
_KIND_OF = {"A": "ASSIGN", "S": "SAMPLE", "C": "CALL", "L": "WHILE", "B": "IF"}


def _pretty(kinds: str, *, primed: bool = False, annotated: bool = False) -> str:
    """Render a one-sided program (string of A/S/C/L/B) as an EC pretty phoare goal.

    Single-digit line numbers are right-padded `( 1)` (EC alignment) and two-digit
    are flush `(10)` — exactly the lexical trap that dropped statements 1-9.
    """
    header = [
        "Current goal", "", "Type variables: <none>", "",
        "&m: {}",
        "-" * 72,
        "pre = true", "",
    ]
    body = []
    for i, k in enumerate(kinds, start=1):
        num = f"({i:>2})" if i < 10 else f"({i})"
        if k == "A":
            rhs = f"e{i}"
            if primed:
                rhs = f"op_name'{i} {rhs}"        # a primed op in the rhs
            if annotated:
                rhs = f"None<:msg> {rhs}"         # a type annotation
            stmt = f"v{i} <- {rhs}"
        else:
            stmt = _STMT_TPL[k].format(i=i)
        body.append(f"{num}  {stmt}")
    tail = ["", "post = true", "[10|check]>"]
    return "\n".join(header + body + tail)


def _true_leading(kinds: str) -> int:
    """The ground-truth leading contiguous straight-line (ASSIGN) prefix length."""
    n = 0
    for k in kinds:
        if k != "A":
            break
        n += 1
    return n


# Enumerate the full structural space up to length 4 (780 shapes) + a few longer,
# sampling-heavy shapes (the pr_G4 pattern that exercised the P1 bug).
def _enumerate_programs():
    out = []
    for length in range(1, 5):
        for combo in itertools.product("ASCLB", repeat=length):
            out.append("".join(combo))
    out += [
        "AAASASSASASAC",     # pr_G4-like: leading [1,2,3], samples interspersed, call at end
        "SASASASA",          # sample-led (true leading = 0)
        "AAAAAAAAAAAAAAAAAA",  # 18 leading assigns (per-side cap stress)
        "AASAASAASAASAAS",   # repeating assign/sample
    ]
    return out


PROGRAMS = _enumerate_programs()


def _frontend_from(kinds: str):
    return build_procedure_body_frontend({}, "phoare", {"statements": []}, _pretty(kinds))


# ---------------------------------------------------------------------------
# INV-1  pretty-parse completeness — every `( N)` line is parsed, orders 1..N
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kinds", PROGRAMS)
def test_inv_parse_completeness(kinds):
    stmts = procedure_statements_from_pretty_goal(_pretty(kinds), "phoare")
    orders = [int(s.get("order") or 0) for s in stmts]
    n = min(len(kinds), 24)  # the fallback parser caps at 24
    assert orders == list(range(1, n + 1)), (
        f"dropped/renumbered program lines for {kinds!r}: got {orders}"
    )


# ---------------------------------------------------------------------------
# INV-2  leading prefix == the true leading contiguous ASSIGN run
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kinds", PROGRAMS)
def test_inv_leading_prefix(kinds):
    stmts = procedure_statements_from_pretty_goal(_pretty(kinds), "phoare")
    sp = procedure_straight_line_prefix(stmts)
    got_orders = [int(s.get("statement_order") or 0) for s in sp]
    # The leading prefix is bounded per side at 16 (an intentional display cap;
    # real bodies rarely have >16 leading straight-line statements before the first
    # sample/call). So the invariant is min(true_leading, 16).
    expect = list(range(1, min(_true_leading(kinds), 16) + 1))
    assert got_orders == expect, (
        f"leading prefix wrong for {kinds!r}: got {got_orders}, expect {expect}"
    )


# ---------------------------------------------------------------------------
# INV-3  the sp/wp absorb count is a VALID leading prefix (end-to-end from text)
#        - 0 leading  -> no left absorb entry (never emit a hint that crosses a frontier)
#        - k leading  -> absorbable_statements == k, through_order == k (contiguous from 1)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kinds", PROGRAMS)
def test_inv_sp_absorb_count_valid(kinds):
    nav = procedure_navigation_map(_frontend_from(kinds))
    left = (nav.get("absorb_depth") or {}).get("left")
    k = min(_true_leading(kinds), 16)  # per-side leading-prefix display cap
    if k == 0:
        assert left is None, (
            f"{kinds!r}: emitted an sp absorb ({left}) when the leading prefix is "
            f"empty (first statement is a frontier) — `sp` would cross it"
        )
    else:
        assert left is not None and left.get("absorbable_statements") == k, (
            f"{kinds!r}: sp absorb={left}, expect {k}"
        )
        # contiguous from order 1 — never reaches past the first non-ASSIGN
        assert int(left.get("through_order") or 0) == k, (
            f"{kinds!r}: through_order {left.get('through_order')} crosses the "
            f"frontier at order {k + 1}"
        )


# ---------------------------------------------------------------------------
# INV-4  reconciliation: frontend leading-prefix vs alignment setup_counts
#        (the logic where P1 / step1 / the asymmetric-setup bugs lived)
# ---------------------------------------------------------------------------
def _fe(prefix_orders, *, side="left"):
    return {
        "available": True,
        "straight_line_prefix": [
            {"side": side, "side_index": 1 if side == "left" else 2,
             "statement_order": o, "kind": "ASSIGN"}
            for o in prefix_orders
        ],
        "branch_guards": [], "loop_frontiers": [], "frontier_plan": {},
    }


def test_inv_reconcile_prefers_leading_run_over_overcounting_alignment():
    # pr_G4: alignment counts ALL assigns before the call (7) but only [1,2,3] are
    # the leading contiguous run; sp must be 3, not 7.
    fe = _fe([1, 2, 3])
    nav = procedure_navigation_map(fe, setup_counts=(7, 0))
    assert nav["absorb_depth"]["left"]["absorbable_statements"] == 3


def test_inv_reconcile_empty_leading_is_zero_not_alignment():
    # step1: the side's first statement is a sample -> frontend prefix empty ->
    # sp must be 0 (no entry), NOT the alignment's mid-program count.
    fe = _fe([])
    nav = procedure_navigation_map(fe, setup_counts=(1, 0))
    assert (nav.get("absorb_depth") or {}).get("left") is None


def test_inv_reconcile_under_parsed_asymmetric_uses_alignment():
    # parser captured only the right TAIL [4,5] of a 5-statement right setup ->
    # its run starts mid-program -> trust the alignment count (5).
    fe = {
        "available": True,
        "straight_line_prefix": [
            {"side": "left", "side_index": 1, "statement_order": 1, "kind": "ASSIGN"},
            {"side": "left", "side_index": 1, "statement_order": 2, "kind": "ASSIGN"},
            {"side": "right", "side_index": 2, "statement_order": 4, "kind": "ASSIGN"},
            {"side": "right", "side_index": 2, "statement_order": 5, "kind": "ASSIGN"},
        ],
        "branch_guards": [], "loop_frontiers": [], "frontier_plan": {},
    }
    nav = procedure_navigation_map(fe, setup_counts=(2, 5))
    assert nav["absorb_depth"]["left"]["absorbable_statements"] == 2
    assert nav["absorb_depth"]["right"]["absorbable_statements"] == 5


# ---------------------------------------------------------------------------
# INV-5  lexical robustness: single-digit numbering / primes / type annotations
#        must not break parse completeness or the leading prefix.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kinds", ["AAASA", "AAAAAAAAAAS", "ASASAS"])
@pytest.mark.parametrize("primed,annotated",
                         [(False, False), (True, False), (False, True), (True, True)])
def test_inv_lexical_robust(kinds, primed, annotated):
    txt = _pretty(kinds, primed=primed, annotated=annotated)
    stmts = procedure_statements_from_pretty_goal(txt, "phoare")
    assert [s["order"] for s in stmts] == list(range(1, len(kinds) + 1))
    sp = procedure_straight_line_prefix(stmts)
    assert len(sp) == _true_leading(kinds)
    # primes preserved in the parsed statement text
    if primed:
        assert any("op_name'" in str(s.get("text") or s.get("statement") or "")
                   for s in stmts)


# ---------------------------------------------------------------------------
# INV-6  Pr-opener surface: expose mechanical probability structure and a plural
#        tactic-family set, not a single leading route prescription.
# ---------------------------------------------------------------------------
from workflow.surface_composer import compose_surface_model

_SEP = "-" * 72


def _opener_facts(lines):
    model = compose_surface_model(
        {
            "current_goal": {"lines": lines},
            "proof_status": {"current_layer": "pr", "goal_type": "probability"},
            "facts_and_diagnostics": {"facts": {}},
        },
        "l4_checked_action_surface",
    ).to_dict()
    return {
        item["key"]: item.get("value")
        for item in model["primary_panel"].get("facts", [])
    }


# (lines, expected summary fragment, expected tactic-family fragments)
_OPENER_CASES = [
    (["&m: {}", _SEP, "Pr[A(g) @ &m : res] = Pr[B(g) @ &m : res]"],
     "visible Pr terms over 2 program/memory contexts", ("byequiv", "rewrite")),
    (["&m: {}", "sigma: int", "Hs: 0 <= sigma", _SEP,
      "Pr[A @ &m : res] = Pr[B @ &m : res]"],
     "visible Pr terms over 2 program/memory contexts", ("byequiv", "rewrite")),
    (["Type variables: <none>", "&m: {}", _SEP,
      "Pr[A @ &m : res] = Pr[B @ &m : res]"],
     "visible Pr terms over 2 program/memory contexts", ("byequiv", "rewrite")),
    (["&m: {}", _SEP,
      "Pr[A @ &m : res = None<:msg>] = Pr[B @ &m : res]"],
     "visible Pr terms over 2 program/memory contexts", ("byequiv", "rewrite")),
    (["&m: {}", _SEP, "Pr[A @ &m : res] = 1%r / 2%r"],
     "Pr[...] equality", ("byphoare", "rewrite", "byequiv")),
    (["&m: {}", _SEP, "`|Pr[A @ &m : res] - Pr[B @ &m : res]| <= e"],
     "Pr[...] upper bound", ("apply", "rewrite")),
    (["&m: {}", "Hinit: init", _SEP,
      "init => `|Pr[A @ &m : res] - Pr[B @ &m : res]| <= rng + bad"],
     "Pr[...] upper bound", ("apply", "rewrite")),
    (["&m: {}", _SEP, "Pr[A @ &m : res] + Pr[B @ &m : res] <= e"],
     "visible Pr terms over 2 program/memory contexts", ("apply", "rewrite")),
]


@pytest.mark.parametrize("lines,summary_fragment,family_fragments", _OPENER_CASES)
def test_inv_opener_probability_surface(lines, summary_fragment, family_fragments):
    facts = _opener_facts(lines)
    assert "allowed_reductions" not in facts
    assert summary_fragment in facts.get("probability_structure", "")
    families = " ".join(facts.get("tactic_affordances") or [])
    for fragment in family_fragments:
        assert fragment in families


# ---------------------------------------------------------------------------
# INV-7  eager surgery handle present IFF the goal is two-sided
# ---------------------------------------------------------------------------
from core.easycrypt.session_prover_workspace_view import (
    _prhl_surgery_tactic_handles, _manager_context_handles,
)


def _has_eager(handles):
    return any((h.get("payload") or {}).get("name") == "eager" for h in handles)


@pytest.mark.parametrize("two_sided", [True, False])
def test_inv_eager_handle_gating(two_sided):
    assert _has_eager(_prhl_surgery_tactic_handles(two_sided)) is two_sided
    # the single-sided menu must KEEP the genuinely one-sided forms
    names = {(h.get("payload") or {}).get("name")
             for h in _prhl_surgery_tactic_handles(two_sided)}
    assert {"wp", "swap", "rcondt", "rcondf", "conseq", "rnd"} <= names


@pytest.mark.parametrize("goal_type,two_sided", [
    ("hoare", False), ("phoare", False), ("bdhoare", False),
    ("equiv", True), ("pRHL", True), ("", True),  # unknown -> treat as two-sided (keep)
])
def test_inv_eager_gating_by_goal_type(goal_type, two_sided):
    handles = _manager_context_handles("procedure_frontier", goal_type)
    assert _has_eager(handles) is two_sided


def _names(handles):
    return {(h.get("payload") or {}).get("name") for h in handles}


def test_fix5_tactic_forms_gated_on_goal_structure():
    # FIX-5 (cluster ⑤): the structure-specific forms are gated on the goal actually
    # containing the structure at this frontier. `rnd`/`eager` need a `<$` sample;
    # `rcondt`/`rcondf` need a live `if (…)` branch. `wp`/`swap`/`conseq` always stay.
    # No goal_text -> full menu (the discoverability fallback / contract above).
    assert {"rnd", "eager", "rcondt", "rcondf"} <= _names(_prhl_surgery_tactic_handles(True))
    # sample-free, branch-free goal -> drop all four off-route forms
    plain = _prhl_surgery_tactic_handles(True, goal_text="x0 <- a; y <- f x0; r <- g y")
    assert {"rnd", "eager", "rcondt", "rcondf"}.isdisjoint(_names(plain))
    assert {"wp", "swap", "conseq"} <= _names(plain)
    # sample present -> rnd/eager kept; branch present -> rcondt/rcondf kept
    sampled = _prhl_surgery_tactic_handles(True, goal_text="k <$ dkey; c <- e")
    assert {"rnd", "eager"} <= _names(sampled) and {"rcondt", "rcondf"}.isdisjoint(_names(sampled))
    branched = _prhl_surgery_tactic_handles(True, goal_text="if (b) { c <- e } else { c <- d }")
    assert {"rcondt", "rcondf"} <= _names(branched) and {"rnd", "eager"}.isdisjoint(_names(branched))
    # gating threads through the context-handles builder (the production path)
    sample_free = _manager_context_handles("procedure_frontier", "equiv", goal_text="r <- f x")
    assert {"rnd", "rcondt"}.isdisjoint(_names(sample_free))


# ---------------------------------------------------------------------------
# INV-8  probe outcome: accepted+closing / accepted+goal-after / rejected
# ---------------------------------------------------------------------------
from workflow.surface_turn_model import compose_surface_turn, render_surface_turn_markdown


def _probe_head(pp, es=""):
    v = {
        "current_goal": {"lines": ["Current goal"]},
        "last_result": {
            "intent": "probe_tactic",
            "tactic": "apply X.",
            "probe_preview": pp,
            "error_summary": es,
        },
    }
    turn = compose_surface_turn(
        v,
        "l4_checked_action_surface",
        handled_intent={"intent": "probe_tactic", "payload": {"tactic": "apply X."}},
    )
    return render_surface_turn_markdown(turn).split("\n")[0]


def test_inv_probe_closing():
    for pp in ({"goal_after_remaining": 0, "goal_after_probe": {}},
               {"goal_after_closed": True, "goal_after_probe": {}}):
        assert "CLOSES the proof" in _probe_head(pp)


def test_inv_probe_preview_remaining():
    h = _probe_head({"goal_after_remaining": 2, "goal_after_probe": {"lines": ["g"]}})
    assert "Probe preview" in h and "CLOSES" not in h


def test_inv_probe_rejected():
    assert "Probe rejected" in _probe_head({}, es="parse error")


# ---------------------------------------------------------------------------
# INV-9  proof_status reflects the COMMITTED state, never leaks a last-action error
# ---------------------------------------------------------------------------
from core.easycrypt.session_prover_workspace_view import _workspace_proof_status
from core.easycrypt.session_workspace_view_manager import WorkspaceViewPlan, DisplayBudget


def _plan():
    return WorkspaceViewPlan(
        goal_family="procedure_frontier", goal_display_mode="x", phase_summary="",
        budget=DisplayBudget(goal_window_lines=800, goal_window_chars=30000,
                             frontier_chars=2000, max_alternatives=3, max_evidence=6),
        panels=(), authority_order=(), inspect_order=(), focus=(),
        phase_resource_keys=(), frontier_resource_keys=(), frontier_checks=())


@pytest.mark.parametrize("raw_status", ["error", "no_progress", "no_progress_reverted", "refused"])
def test_inv_status_open_when_goal_remains(raw_status):
    st = {"status": raw_status, "remaining_goals": 8, "remaining_goals_known": True,
          "goal_type": "hoare"}
    out = _workspace_proof_status(state=st, phase={}, plan=_plan())
    assert out["status"] == "open", (
        f"status {raw_status} with 8 open goals must read 'open', got {out['status']}"
    )


@pytest.mark.parametrize("status", ["open", "closed", "candidate_closed_pending_qed"])
def test_inv_status_passes_through_non_action_states(status):
    st = {"status": status, "remaining_goals": 1, "remaining_goals_known": True}
    assert _workspace_proof_status(state=st, phase={}, plan=_plan())["status"] == status
