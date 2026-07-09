from __future__ import annotations

import json

from workflow.proof_management.analyzers.call_site import CallSiteAnalyzer
from workflow.proof_management.node_state import ProofNodeState


def _state() -> ProofNodeState:
    return ProofNodeState(node_id="node")


def test_call_site_analyzer_reports_surface_and_removes_noncallable_move() -> None:
    view = {
        "proof_status": {"current_layer": "call_site", "view_focus": "relational_program"},
        "current_goal": {
            "lines": [
                "Current goal",
                "&1 (left) : { c2 <@ Wrapper.enc(n, p) }",
                "&2 (right): { c1 <@ EncRnd.cc(n, p) }",
            ]
        },
        "program_frontier": {
            "call_sites": [
                {
                    "id": "left.1",
                    "side": "left",
                    "procedure": "Wrapper.enc",
                    "requires_cut_to_frontier": True,
                },
                {
                    "id": "right.1",
                    "side": "right",
                    "procedure": "EncRnd.cc",
                    "is_frontier_call": True,
                },
            ],
            "frontier_alignment": {
                "rows": [
                    {
                        "role": "residual after call",
                        "left": "BNR.ndec <- BNR.ndec + 1",
                        "right": "BNR.ndec <- BNR.ndec + 1",
                    }
                ]
            },
        },
        "application_context": {
            "selected_handles": [
                {
                    "name": "wrapper_equiv",
                    "kind": "call-equivalence handle",
                    "why_relevant": "visible call handle context",
                }
            ]
        },
        "candidate_moves": {
            "moves": [
                {
                    "title": "Named-call context",
                    "category": "strategy",
                    "tactic": "call old_equiv.",
                    "applicability": "This named-call shape came from program comparison.",
                },
                {"title": "Local wp", "tactic": "wp."},
            ]
        },
    }

    analysis = CallSiteAnalyzer().analyze(state=_state(), view=view)

    assert [item["procedure"] for item in analysis.surface["live_call_sites"]] == [
        "Wrapper.enc",
        "EncRnd.cc",
    ]
    assert analysis.surface["named_handles"][0]["symbol"] == "wrapper_equiv"
    assert analysis.surface["frontier_blockers"][0]["kind"] == "requires_cut_to_frontier"
    assert any(
        item["kind"] == "residual_after_call_site"
        for item in analysis.surface["frontier_blockers"]
    )
    assert analysis.surface["residual_frontier"]["state"] == "residual_after_call"
    assert "old_equiv" in {item["symbol"] for item in analysis.surface["named_handles"]}
    assert "old_equiv" not in json.dumps(analysis.view_overrides.get("candidate_moves", {}))


def test_call_site_analyzer_reports_one_sided_certificate_evidence() -> None:
    view = {
        "proof_status": {"current_layer": "call_site", "view_focus": "relational_program"},
        "current_goal": {
            "lines": [
                "Current goal",
                "Hdec: hoare[ E.dec : true ==> res = None<:ptxt> ]",
                "------------------------------------------------------------------------",
                "&1 (left ) : {p0 : ptxt option, ek : eK, c0 : ctxt}",
                "&2 (right) : {b : bool}",
                "p0 <@ E.dec(ek, c0)        (1)",
            ]
        },
        "program_frontier": {
            "call_sites": [
                {
                    "side": "left",
                    "side_index": 1,
                    "procedure": "E.dec",
                    "statement": "p0 <@ E.dec(ek, c0)",
                }
            ],
            "frontier_alignment": {
                "first_instruction_alignment": {
                    "left_first": "p0 <@ E.dec(ek, c0)",
                    "right_first": "no matching right-side call at this frontier",
                    "branch_alignment": "one-sided_frontier",
                }
            },
        },
        "application_context": {
            "selected_handles": [
                {"name": "E_dec_ll", "kind": "lossless lemma"}
            ]
        },
    }

    analysis = CallSiteAnalyzer().analyze(state=_state(), view=view)
    one_sided = analysis.surface["one_sided_call_surface"]

    assert one_sided["state"] == "one_sided_call_frontier"
    assert one_sided["one_sided_sites"][0]["procedure"] == "E.dec"
    assert one_sided["visible_hoare_handles"][0]["symbol"] == "Hdec"
    assert one_sided["visible_lossless_handles"][0]["symbol"] == "E_dec_ll"
    assert one_sided["packaging_evidence"]["confidence"] == "high"


def test_call_site_analyzer_removes_stale_surface_on_pure_tail() -> None:
    view = {
        "proof_status": {"current_layer": "ambient_logic", "goal_type": "ambient"},
        "current_goal": {"lines": ["Current goal", "forall x, x \\in xs => x = x"]},
        "call_site_surface": {
            "frontier_blockers": [
                {"kind": "named_handle_not_callable_in_current_view"}
            ]
        },
        "candidate_moves": {
            "moves": [
                {
                    "id": "call_site_route",
                    "title": "Old named-call route",
                    "tactic": "call old_equiv.",
                },
                {"title": "Local destructor", "tactic": "move=> x."},
            ]
        },
    }

    analysis = CallSiteAnalyzer().analyze(state=_state(), view=view)

    assert analysis.surface == {}
    assert analysis.removed_panels == ["call_site_surface"]
    assert "old_equiv" not in json.dumps(analysis.view_overrides["candidate_moves"])
    assert analysis.view_overrides["candidate_moves"]["moves"][0]["title"] == "Local destructor"
