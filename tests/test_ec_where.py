from __future__ import annotations

from pathlib import Path

import core.easycrypt.ec_where as ec_where
from core.easycrypt.ec_where import _parse_print_blocks, format_where


def test_where_parser_accepts_local_equiv_print_output() -> None:
    output = """\
no such object in any category
* In [lemmas or axioms]:
local equiv poly_mac1 :
  L.enc ~ R.enc : true ==> ={res}.
"""

    parsed = _parse_print_blocks(output, "poly_mac1")

    assert parsed is not None
    assert parsed["kind"] == "equiv"
    assert "local equiv poly_mac1" in parsed["body"]


def test_format_where_reports_equiv_kind() -> None:
    rendered = format_where({
        "name": "poly_mac1",
        "status": "direct",
        "resolved": "poly_mac1",
        "kind": "equiv",
        "body": "local equiv poly_mac1 : L.enc ~ R.enc : true ==> ={res}.",
        "attempts": [("poly_mac1", True)],
        "other_hits": [],
        "note": "",
    })

    assert "[WHERE-HIT] poly_mac1  (kind: equiv)" in rendered
    assert "local equiv poly_mac1" in rendered


def test_where_source_fallback_resolves_clone_override_op(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = tmp_path / "context.ec"
    context.write_text(
        "\n".join([
            "clone Split as Split0 with",
            "  type from <- nonce * C.counter,",
            "  type to <- block",
            "  proof *.",
            "",
            "clone import Split0.SplitDom as SplitD with",
            "  op test = fun p:nonce * C.counter => C.toint p.`2 = 0.",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(ec_where, "_run_ec", lambda *args, **kwargs: "")

    result = ec_where.where("SplitD.test", context, [])

    assert result["status"] == "source-resolved"
    assert result["kind"] == "op"
    assert result["resolved"] == "SplitD.test"
    assert "C.toint p.`2 = 0" in result["body"]
    rendered = format_where(result)
    assert "[WHERE-HIT-SOURCE] SplitD.test" in rendered
    assert "source-scan fallback" in rendered
    assert "-search" not in format_where({
        "name": "Missing.name",
        "status": "miss",
        "resolved": None,
        "kind": None,
        "body": None,
        "attempts": [("Missing.name", False)],
        "note": "",
    })


def test_where_source_fallback_resolves_local_equiv_without_proof_body(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = tmp_path / "context.ec"
    context.write_text(
        "\n".join([
            "local equiv poly_mac1 :",
            "  L.enc ~ R.enc : true ==> ={res}.",
            "proof.",
            "  admit.",
            "qed.",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(ec_where, "_run_ec", lambda *args, **kwargs: "")

    result = ec_where.where("poly_mac1", context, [])

    assert result["status"] == "source-resolved"
    assert result["kind"] == "equiv"
    assert "L.enc ~ R.enc" in result["body"]
    assert "admit" not in result["body"]


# --- proof-status static analysis (2026-06-05) -------------------------------
def test_classify_proof_status_distinguishes_proven_admit_aborted() -> None:
    from core.easycrypt.ec_where import classify_proof_status as c
    assert c("lemma f : x=y.\nproof.\n by auto.\nqed.\n", 1, "lemma") == "proven"
    assert c("lemma f : x=y.\nproof.\n admit.\nqed.\n", 1, "lemma") == "admit"
    assert c("equiv f : a~b : p ==> q.\nproof.\n admit.\nqed.\n", 1, "equiv") == "admit"
    assert c("lemma f : x=y.\nproof.\n split; first by auto.\n admit.\nqed.\n",
             1, "lemma") == "contains_admit"
    assert c("lemma f : x=y.\nproof.\n auto.\nabort.\n", 1, "lemma") == "aborted"
    # a `qed.` inside a comment must not be mistaken for the terminator
    assert c("lemma f : x=y.\nproof.\n (* qed. *)\n by auto.\nqed.\n", 1, "lemma") == "proven"
    # non-proof kinds carry no proof status
    assert c("axiom f : x=y.\n", 1, "axiom") is None
    assert c("op f = 3.\n", 1, "op") is None


def test_format_where_surfaces_admit_proof_status() -> None:
    admit = format_where({
        "name": "swap_x", "status": "source-resolved", "resolved": "swap_x",
        "kind": "equiv", "body": "equiv swap_x : a ~ b : true ==> ={res}.",
        "source_line": 10, "note": "", "proof_status": "admit",
    })
    assert "kind: equiv · admit" in admit
    assert "PROOF STATUS: `admit`" in admit
    assert "relying on an unproven obligation" in admit

    proven = format_where({
        "name": "ok_lemma", "status": "direct", "resolved": "ok_lemma",
        "kind": "lemma", "body": "lemma ok_lemma : true.", "proof_status": "proven",
    })
    assert "kind: lemma · proven" in proven
    assert "PROOF STATUS" not in proven  # no warning for a proven lemma

    # back-compat: a result with no proof_status key renders the bare kind
    legacy = format_where({
        "name": "x", "status": "direct", "resolved": "x", "kind": "op",
        "body": "op x = 1.",
    })
    assert "kind: op)" in legacy and "·" not in legacy


def test_classify_scope_distinguishes_local_section_toplevel() -> None:
    from core.easycrypt.ec_where import classify_scope as cs
    src = (
        "require import AllCore.\n"   # 1
        "section S.\n"               # 2
        "  local lemma a : true.\n"  # 3
        "  lemma b : true.\n"        # 4
        "end section.\n"             # 5
        "lemma c : true.\n"          # 6
    )
    assert cs(src, 3) == "local"
    assert cs(src, 4) == "exported_after_section"
    assert cs(src, 6) == "exported"
    assert cs(src, 999) is None


def test_index_ec_file_records_scope(tmp_path) -> None:
    from core.easycrypt.ec_file_index import index_ec_file
    f = tmp_path / "M.ec"
    f.write_text(
        "section S.\n"
        "  local lemma a : true.\n"
        "  lemma b : true.\n"
        "end section.\n"
        "lemma c : true.\n"
    )
    by = {l["name"]: l for l in index_ec_file(f)["all_lemmas"]}
    assert by["a"]["scope"] == "local" and by["a"]["is_local"] is True
    assert by["b"]["scope"] == "exported_after_section"
    assert by["c"]["scope"] == "exported" and by["c"]["is_local"] is False


def test_format_where_surfaces_local_scope_as_not_usable() -> None:
    local = format_where({
        "name": "bound_bad_rng", "status": "found-not-in-scope",
        "resolved": "bound_bad_rng", "kind": "lemma",
        "body": "lemma bound_bad_rng : 0 <= rng_bad.",
        "source_file": "Perm6.ec", "scope": "local", "proof_status": None,
    })
    assert "WHERE-OUT-OF-SCOPE" in local and "Perm6.ec" in local
    assert "SCOPE: `local`" in local and "unknown identifier" in local

    sect = format_where({
        "name": "pr_dist", "status": "found-not-in-scope", "resolved": "pr_dist",
        "kind": "lemma", "body": "lemma pr_dist &m : x.", "source_file": "Perm6.ec",
        "scope": "exported_after_section", "proof_status": None,
    })
    assert "SCOPE: `exported_after_section`" in sect and "section" in sect
    # a plain exported lemma gets no SCOPE warning line (no noise)
    plain = format_where({
        "name": "ok", "status": "direct", "resolved": "ok", "kind": "lemma",
        "body": "lemma ok : true.", "scope": "exported",
    })
    assert "SCOPE:" not in plain


def test_cross_file_finds_section_local_helper_out_of_scope(tmp_path) -> None:
    # The bound_bad_rng case: the helper is section-`local` in an imported theory, so
    # EC `print` and the current-file scan both miss. The cross-file resolver must
    # locate it and report scope=local — so the agent stops chasing it by hand.
    from core.easycrypt.ec_where import _cross_file_symbol_scope
    (tmp_path / "Perm6.ec").write_text(
        "section PROOF.\n"
        "  local lemma bound_bad_rng s q : 0 <= rng_bad s q.\n"
        "  proof. admit. qed.\n"
        "  lemma pr_distinguish_simul_from_three_perm &m : `|x| <= y.\n"
        "  proof. admit. qed.\n"
        "end section.\n"
    )
    ctx = tmp_path / "inter.ec"
    ctx.write_text("require import Perm6.\nlemma g : true.\nproof. trivial. qed.\n")
    res = _cross_file_symbol_scope("bound_bad_rng", ctx, [tmp_path])
    assert res is not None
    assert res["status"] == "found-not-in-scope"
    assert res["scope"] == "local" and res["source_file"] == "Perm6.ec"
    # the exported (post-section) sibling classifies differently
    res2 = _cross_file_symbol_scope(
        "pr_distinguish_simul_from_three_perm", ctx, [tmp_path])
    assert res2 is not None and res2["scope"] == "exported_after_section"
    # boundary: a name in NO imported theory stays a miss (None); the resolver never
    # surfaces close-match / sibling candidates.
    assert _cross_file_symbol_scope("nonexistent_xyz", ctx, [tmp_path]) is None
