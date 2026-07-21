"""Property / unit coverage for the render- and resolver-level panel fixes that
the structural generative suite (test_panel_properties.py) does NOT reach.

Each test targets a real entry point (not a replica) and is paired with a
mutation note describing the regression it guards (verified by reintroducing the
pre-fix behavior and observing the test go red).

Covers:
  B4  workflow.surface_profiles._surgery_where       — symmetric frontier placeholder side
  B6  core...session_prover_workspace_view._workspace_application_context — provenance pass-through
  B7  core...ec_name_resolution.resolve_goal_unfoldable_names — `<@` proc call-site exclusion
  B8  core...ec_lemma_index._declarations_from_text  — primed/suffixed lemma name captured whole
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# B8  lemma-head name class must include the EasyCrypt prime `'` and underscores.
#     Pre-fix `(\w+)\b` dropped the trailing `'`, naming a non-existent lemma.
# ---------------------------------------------------------------------------
from core.easycrypt.analysis.ec_lemma_index import _declarations_from_text


def _decl_names(text: str) -> set[str]:
    out = _declarations_from_text(
        text, source_path=Path("syn.ec"), source="local", include_local=True
    )
    return {str(d.get("name")) for d in out if isinstance(d, dict)}


@pytest.mark.parametrize(
    "name",
    [
        "perm3_perm3'",      # trailing prime — the exact pr_bridge regression
        "foo'",              # single prime
        "foo''",             # double prime
        "lemma_under_score", # underscores
        "h1'_aux",           # digits + prime + underscore mix
        "Plain",             # no special chars (control)
    ],
)
def test_b8_lemma_name_captured_whole(name):
    text = f"lemma {name} : true.\n"
    assert name in _decl_names(text), (
        f"head extraction truncated {name!r}; got {_decl_names(text)}"
    )


def test_b8_name_not_overrun_into_following_token():
    # The negative lookahead must STOP at the name boundary, not swallow more.
    names = _decl_names("lemma foo (x : int) : true.\n")
    assert "foo" in names and not any(n.startswith("foo ") for n in names)


# ---------------------------------------------------------------------------
# B7  a `<@ Mod.proc(...)` call site is NOT an unfoldable op — never offer
#     `rewrite /Mod.proc.` for it, even if an unrelated `op proc` exists.
# ---------------------------------------------------------------------------
from core.easycrypt.analysis import ec_name_resolution as enr
from core.easycrypt.analysis.ec_name_resolution import (
    _Declaration,
    resolve_goal_unfoldable_names,
)


def _op(name: str) -> _Declaration:
    return _Declaration(
        name=name, kind="op",
        declaration=f"op {name} = witness.",
        source_path="syn.ec", source_kind="local_context", has_body=True,
    )


@pytest.fixture
def _patched_decls(monkeypatch):
    # `get` (the unqualified op the bogus FinRO.get used to resolve to) AND a
    # genuine unfoldable op `foo` that SHOULD surface.
    decls = {"get": _op("get"), "foo": _op("foo")}
    monkeypatch.setattr(enr, "_scan_unfoldable_declarations", lambda paths: decls)
    monkeypatch.setattr(enr, "_context_files", lambda session_dir: [])
    return decls


def test_b7_proc_call_site_not_offered_as_unfoldable(_patched_decls):
    goal = "pre ==> r <@ FinRO.get(x); s <- foo a"
    names = {d["name"] for d in resolve_goal_unfoldable_names(goal_text=goal)}
    assert "FinRO.get" not in names and "get" not in names, (
        f"`<@ FinRO.get` call site leaked into unfoldable heads: {names}"
    )


def test_b7_genuine_op_still_offered(_patched_decls):
    # Guard against a vacuous B7 test: the real op MUST still be surfaced.
    goal = "pre ==> s <- foo a"
    names = {d["name"] for d in resolve_goal_unfoldable_names(goal_text=goal)}
    assert "foo" in names, f"genuine unfoldable op dropped: {names}"


# ---------------------------------------------------------------------------
# B4  frontier row: detect the placeholder SIDE symmetrically; show the
#     populated side. Pre-fix only checked `right`, so a right-only row (left is
#     the placeholder) was mislabeled "both sides" and erased the right content.
# ---------------------------------------------------------------------------
from workflow.surface_panels import _surgery_where


def _frontier_view(left: str, right: str, *, one_sided: bool = False):
    return {
        "program_frontier": {
            "frontier_alignment": {
                "first_instruction_alignment": {
                    "branch_alignment": "one-sided" if one_sided else "aligned",
                    "left_head": "h",
                },
                "rows": [{"role": "frontier", "left": left, "right": right,
                          "location": {}}],
            }
        }
    }


def test_b4_right_only_row_labeled_right_side():
    # left is the placeholder -> the populated content is on the RIGHT.
    out = _surgery_where(_frontier_view("no matching left-side call", "x <@ M.p(a)"))
    line = out[0]
    assert "right side only" in line and "x <@ M.p(a)" in line, line
    assert "both sides" not in line


def test_b4_left_only_row_labeled_left_side():
    out = _surgery_where(_frontier_view("y <- e", "no matching right-side call"))
    line = out[0]
    assert "left side only" in line and "y <- e" in line, line


def test_b4_two_sided_row_labeled_both():
    out = _surgery_where(_frontier_view("y <- e", "x <- f"))
    assert "both sides" in out[0], out[0]


# ---------------------------------------------------------------------------
# B6  the thin twin must carry confidence / epistemic_status / source from the
#     full option, so the provenance stamper does not mislabel it "unverified".
# ---------------------------------------------------------------------------
from core.easycrypt import session_prover_workspace_view as spwv


def test_b6_provenance_fields_pass_through(monkeypatch):
    option = {
        "title": "apply daemon-accepted handle",
        "category": "commit", "tactic": "auto.",
        "guidance": "Daemon probe accepted this tactic.",
        "runnable_status": "runnable",
        "confidence": "high",
        "epistemic_status": "daemon_probe_accepted",
        "source": "daemon_probe",
    }
    monkeypatch.setattr(spwv, "_navigation_context", lambda **kw: {})
    monkeypatch.setattr(spwv, "_workspace_proof_options", lambda dc, ctx: [option])
    out = spwv._workspace_application_context(
        {}, state={}, frontier={}, proof_ir={}, evidence={}, plan=None
    )
    handle = (out.get("selected_handles") or [{}])[0]
    assert handle.get("confidence") == "high"
    assert handle.get("epistemic_status") == "daemon_probe_accepted"
    assert handle.get("source") == "daemon_probe"


# ---------------------------------------------------------------------------
# P-HINT  `hint` is a dead/hollow offered topic — suppressed from the offered
#         menu so it never reaches the agent (offered 1011x / pulled 0x in the
#         opus-4-8 corpus; pulling it only dispatched to -goal-info).
#         Mutation note: remove "hint" from _LOW_LEVEL_INSPECT_TOPICS and this
#         goes red. The recommendation `category in {"strategy","hint"}` routing
#         reads a SEPARATE field and must stay unaffected.
# ---------------------------------------------------------------------------
from core.easycrypt.session_prover_workspace_view import _normalize_inspect_topic


def test_phint_dead_hint_topic_suppressed_from_offered_menu():
    # The offered-menu gate calls _normalize_inspect_topic on the topic STRING
    # (payload["topic"] or handle["topic"]); a "" result drops the handle.
    assert _normalize_inspect_topic("hint") == ""
    assert _normalize_inspect_topic("-hint") == ""   # dashed form also normalized
    # real topics still survive — we only dropped the dead one
    assert _normalize_inspect_topic("goal_info") == "goal_info"
    assert _normalize_inspect_topic("call_subgoals") == "call_subgoals"


# ---------------------------------------------------------------------------
# K0  build_on (the panel-audit value sensor) must recognize SHAPE-TYPED transfer
#     that the legacy dotted-name FAIR was blind to — it scored a VERBATIM
#     `call (_: ={glob...})` commit and a lemma_index-driven rewrite as MISSES
#     (lemma_index dotted-FAIR 0/24 → build_on 11/24). Mutation note: revert
#     build_on to dotted-only and the frame/bare-name asserts go red.
# ---------------------------------------------------------------------------
import importlib.util as _ilu  # noqa: E402

_sc_spec = _ilu.spec_from_file_location(
    "_panel_scorecard",
    str(Path(__file__).resolve().parents[1] / "tools" / "panel_audit" / "scorecard.py"),
)
_sc = _ilu.module_from_spec(_sc_spec)
_sc_spec.loader.exec_module(_sc)


def test_k0_build_on_recognizes_frame_and_bare_name_transfer():
    # frame-shaped (={glob...}) — dotted-FAIR was blind; build_on must catch it
    assert _sc.build_on(
        "options: call (_: ={glob OCC, glob I}). (you write the body)",
        "call (_: ={glob OCC, glob I}).")
    # bare lemma/op name (the lemma_index 0/24 blind spot)
    assert _sc.build_on("roster: doublequery_eq : ...; mem_set : ...",
                        "rewrite (doublequery_eq H).")
    # non-transfer must NOT register (guards against over-permissiveness)
    assert not _sc.build_on(
        "call (_: ={glob A}). (you write the invariant)", "auto.")
    assert not _sc.build_on("consider seq or sp to peel the prefix", "qed.")


# ---------------------------------------------------------------------------
# A2  lemma_index is retired from the normal offered menu.  Agents may read the
#     current source file and use lookup_symbol/operator_lemmas; the broad
#     whole-file roster is no longer a state-surface affordance.
# ---------------------------------------------------------------------------
def test_a2_lemma_index_not_wired_into_planning_families():
    from core.easycrypt.session_prover_workspace_view import _manager_context_handles

    def topics(fam):
        return {(h.get("payload") or {}).get("topic")
                for h in _manager_context_handles(fam)}

    for fam in (
        "probability",
        "relational_program",
        "procedure_frontier",
        "ambient_logic",
        "seq_cut",
        "failure_diagnostic",
    ):
        assert "lemma_index" not in topics(fam), f"lemma_index wrongly offered in {fam}"


# ---------------------------------------------------------------------------
# A3  the opus-4-8 panel audit DEMOTES redundant/dead topics from the offered menu
#     (kept reachable by blind pull): episode_view (dead 124/0), align (renderer
#     already prints it, build_on 0%), lemma_hints (hop before lookup_symbol).
#     pr_bridge_routes (re-score FLIP: 40 pulls/40% build_on) and rewrite_candidates
#     (content-gated native-search mapping, thin data) stay offered. Mutation note:
#     remove a topic from _DEMOTED_INSPECT_TOPICS and the membership assert goes red.
# ---------------------------------------------------------------------------
def test_a3_demoted_topics_dropped_from_offered_menu():
    from core.easycrypt.session_prover_workspace_view import _normalize_inspect_topic as N
    for t in ("episode_view", "align", "lemma_hints"):
        assert N(t) == "", f"{t} should be demoted from the offered menu"
    # kept-offered survive
    assert N("pr_bridge_routes") == "pr_bridge_routes"   # re-score: USEFUL
    assert N("rewrite_candidates") == "rewrite_candidates"  # content-gated, thin data
    assert N("call_subgoals") == "call_subgoals"
    assert N("lemma_index") == "lemma_index"
