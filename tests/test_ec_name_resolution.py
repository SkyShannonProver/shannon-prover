"""Tests for static EasyCrypt name-resolution pass."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_name_resolution import (  # noqa: E402
    resolution_for_name,
    resolve_goal_unfoldable_names,
    resolve_proof_ir_names,
)


_CONTEXT = """\
local module L = {
  proc enc() = { return witness; }
}.

local module R = {
  proc enc() = { return witness; }
}.

local equiv poly_mac1 :
  L.enc ~ R.enc : true ==> ={res}.
proof. by trivial. qed.
"""


def test_resolves_local_equiv_signature_from_context() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(_CONTEXT, encoding="utf-8")

        result = resolve_proof_ir_names(
            session_dir=session,
            handles={
                "callable_lemmas": [{
                    "lemma": "poly_mac1",
                    "procedure": "L.enc",
                    "handle_kind": "call_equiv",
                }],
            },
        )

    item = result["items"][0]
    assert result["summary"]["resolved"] == 1
    assert item["resolution_status"] == "resolved_local_declaration"
    assert item["exact_signature_known"] is True
    assert "local equiv poly_mac1" in item["declaration"]
    assert item["procedure_match"] == "lhs"
    assert item["instantiation_candidates"][0]["status"] == "ready_template"
    assert resolution_for_name(result, "poly_mac1")["name"] == "poly_mac1"


def test_goal_unfoldable_names_preserve_qualified_clone_heads() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        (session / "context.ec").write_text(
            "\n".join([
                "clone import Split0.SplitDom as SplitD with",
                "  op test = fun p:nonce * C.counter => C.toint p.`2 = 0.",
                "",
                "proof.",
            ]),
            encoding="utf-8",
        )

        result = resolve_goal_unfoldable_names(
            session_dir=session,
            goal_text="if (SplitD.test x) { x <- x; }",
        )

    assert result[0]["name"] == "SplitD.test"
    assert result[0]["unqualified_name"] == "test"
    assert result[0]["unfold_tactic"] == "rewrite /SplitD.test."


def test_cross_scope_name_requests_signature_lookup() -> None:
    result = resolve_proof_ir_names(
        handles={
            "pr_rewrite_candidates": ["OpCCRO.pr_CCP_OCCP"],
        },
    )

    item = result["items"][0]
    assert item["resolution_status"] == "needs_where_lookup"
    assert item["source_kind"] == "cloned_or_imported_theory"
    assert item["signature_lookup_action"] == "-where pr_CCP_OCCP"
    assert result["lookup_actions"] == ["-where pr_CCP_OCCP"]


def test_source_file_declaration_after_frozen_context_needs_scope_check() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        source = session / "target.ec"
        (session / "context.ec").write_text(
            "\n".join([
                "local lemma step2_3 &m :",
                "  Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res].",
                "proof.",
            ]),
            encoding="utf-8",
        )
        source.write_text(
            "\n".join([
                "local lemma step2_3 &m :",
                "  Pr[Game0.main() @ &m : res] = Pr[Game1.main() @ &m : res].",
                "proof. admit. qed.",
                "",
                "local lemma step3 &m :",
                "  Pr[Game2.main() @ &m : res] = Pr[Game3.main() @ &m : res].",
                "proof. admit. qed.",
            ]),
            encoding="utf-8",
        )
        (session / "session_meta.json").write_text(
            json.dumps({"file": str(source), "lemma": "step2_3"}),
            encoding="utf-8",
        )

        result = resolve_proof_ir_names(
            session_dir=session,
            handles={"pr_rewrite_candidates": ["step3"]},
        )

    item = result["items"][0]
    assert item["resolution_status"] == "source_local_scope_check_required"
    assert item["source_kind"] == "source_file_out_of_context"
    assert item["exact_signature_known"] is False
    assert item["requires_instantiation"] is True
    assert item["instantiation_candidates"][0]["status"] == "scope_check_first"
    assert result["lookup_actions"] == ["-where step3"]


def test_signature_tool_view_upgrades_cross_scope_resolution() -> None:
    sig_output = """\
=== Signature of 'pr_CCP_OCCP' (1 match) ===

-- PROM.ec:42 (lemma)
lemma pr_CCP_OCCP (A <: Adv) &m :
  Pr[G1(A).main() @ &m : res] = Pr[G2(A).main() @ &m : res].

Usage: apply (pr_CCP_OCCP <module_arg1> <module_arg2> ... &m).
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "sig_deadbeef.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "sig",
                "kind": "tool_view",
                "ok": True,
                "proof_state": {"status": "open"},
                "guidance": {"recommendations": []},
                "evidence": {
                    "context": [{
                        "id": "context.sig.query",
                        "query": {"name": "pr_CCP_OCCP"},
                    }],
                    "raw": [],
                },
                "notes": [],
                "errors": [],
                "debug": {"legacy_text": sig_output},
            }),
            encoding="utf-8",
        )

        result = resolve_proof_ir_names(
            session_dir=session,
            handles={
                "pr_rewrite_candidates": ["OpCCRO.pr_CCP_OCCP"],
            },
        )

    item = result["items"][0]
    assert result["summary"]["resolved"] == 1
    assert result["lookup_actions"] == []
    assert item["resolution_status"] == "resolved_signature_lookup"
    assert item["source_kind"] == "signature_lookup_tool"
    assert item["exact_signature_known"] is True
    assert item["parameters"] == ["(A <: Adv)", "&m"]
    assert item["parameter_slots"] == [{
        "index": 1,
        "raw": "(A <: Adv)",
        "kind": "module_arg",
        "name": "A",
        "type_or_bound": "Adv",
        "placeholder": "<A_module>",
        "argument": "<A_module>",
    }, {
        "index": 2,
        "raw": "&m",
        "kind": "memory_arg",
        "name": "&m",
        "type_or_bound": "",
        "placeholder": "<m>",
        "argument": "&m",
    }]
    assert item["instantiation_candidates"][0]["status"] == (
        "signature_known_needs_instantiation"
    )
    assert item["instantiation_candidates"][0]["candidate_tactic"] == (
        "rewrite (OpCCRO.pr_CCP_OCCP <A_module> &m)."
    )


def test_signature_parameters_become_typed_slots() -> None:
    sig_output = """\
=== Signature of 'foo' (1 match) ===

-- Local.ec:7 (lemma)
lemma foo {T: Type} (x : int) n &m : true.

Usage: apply (foo <module_arg1> <module_arg2> ... &m).
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "sig_foo.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "sig",
                "kind": "tool_view",
                "ok": True,
                "proof_state": {"status": "open"},
                "guidance": {"recommendations": []},
                "evidence": {
                    "context": [{
                        "id": "context.sig.query",
                        "query": {"name": "foo"},
                    }],
                    "raw": [],
                },
                "notes": [],
                "errors": [],
                "debug": {"legacy_text": sig_output},
            }),
            encoding="utf-8",
        )
        result = resolve_proof_ir_names(
            session_dir=session,
            handles={"have_chain_candidates": [{"lemma": "foo"}]},
        )

    slots = result["items"][0]["parameter_slots"]
    assert [slot["kind"] for slot in slots] == [
        "type_arg",
        "value_arg",
        "value_arg",
        "memory_arg",
    ]
    assert [slot["placeholder"] for slot in slots] == [
        "<T_type>",
        "<x>",
        "<n>",
        "<m>",
    ]
    assert result["items"][0]["instantiation_candidates"][0][
        "candidate_tactic"
    ] == "have := foo <T_type> <x> <n> &m."


def test_where_tool_view_supplies_clone_resolved_section_parameters() -> None:
    where_output = """\
[WHERE-HIT] pr_RO_FinRO_D  (kind: lemma)
* In [lemmas or axioms]:

lemma pr_RO_FinRO_D:
  (forall (_ : nonce * C.counter), is_lossless dblock) =>
  forall (D0(G : RO) <: FinRO_Distinguisher{-RO, -FRO}) &m (x : unit)
    (p : bool -> bool),
    Pr[MainD(D0, RO).distinguish(x) @ &m : p res] =
    Pr[MainD(D0, FinRO).distinguish(x) @ &m : p res].
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "where_pr.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "where",
                "kind": "tool_view",
                "ok": True,
                "proof_state": {"status": "open"},
                "guidance": {"recommendations": []},
                "evidence": {
                    "context": [{
                        "id": "context.where.query",
                        "query": {"name": "pr_RO_FinRO_D"},
                    }],
                    "raw": [],
                },
                "notes": [],
                "errors": [],
                "debug": {"legacy_text": where_output},
            }),
            encoding="utf-8",
        )
        result = resolve_proof_ir_names(
            session_dir=session,
            handles={"pr_rewrite_candidates": ["pr_RO_FinRO_D"]},
        )

    item = result["items"][0]
    assert item["source_kind"] == "where_lookup_tool"
    assert item["resolution_status"] == "resolved_signature_lookup"
    assert item["parameters"] == [
        "(proof1 : (forall (_ : nonce * C.counter), is_lossless dblock))",
        "(D0(G : RO) <: FinRO_Distinguisher{-RO, -FRO})",
        "&m",
        "(x : unit)",
        "(p : bool -> bool)",
    ]
    assert [slot["kind"] for slot in item["parameter_slots"]] == [
        "proof_arg",
        "module_arg",
        "memory_arg",
        "value_arg",
        "value_arg",
    ]
    assert item["parameter_slots"][1]["name"] == "D0"


def test_where_via_clone_tool_view_is_ec_ground_truth() -> None:
    where_output = """\
[WHERE-HIT-VIA-CLONE] ofintdK -> C.ofintdK  (kind: lemma; not at top level)
* In [lemmas or axioms]:

lemma ofintdK:
  forall x, C.toint (C.ofintd x) = x.
"""
    with tempfile.TemporaryDirectory() as td:
        session = Path(td)
        tool_views = session / "tool_views"
        tool_views.mkdir()
        (tool_views / "where_clone.json").write_text(
            json.dumps({
                "schema_version": 1,
                "tool": "where",
                "kind": "tool_view",
                "ok": True,
                "proof_state": {"status": "open"},
                "guidance": {"recommendations": []},
                "evidence": {
                    "context": [{
                        "id": "context.where.query",
                        "query": {"name": "ofintdK"},
                    }],
                    "raw": [],
                },
                "notes": [],
                "errors": [],
                "debug": {"legacy_text": where_output},
            }),
            encoding="utf-8",
        )
        result = resolve_proof_ir_names(
            session_dir=session,
            handles={"have_chain_candidates": [{"lemma": "ofintdK"}]},
        )

    item = result["items"][0]
    assert item["source_kind"] == "where_lookup_tool"
    assert item["resolution_status"] == "resolved_signature_lookup"
    assert item["fact_source"] == "ec_native_print"
    assert item["authority"] == "ec_native_ground_truth"
    assert item["ec_ground_truth"] is True


def main() -> int:
    test_resolves_local_equiv_signature_from_context()
    test_cross_scope_name_requests_signature_lookup()
    test_signature_tool_view_upgrades_cross_scope_resolution()
    test_signature_parameters_become_typed_slots()
    test_where_tool_view_supplies_clone_resolved_section_parameters()
    test_where_via_clone_tool_view_is_ec_ground_truth()
    print("PASS test_ec_name_resolution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
