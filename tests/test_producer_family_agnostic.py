"""Guard: the compiler's producers/analyzers must stay crypto-family-agnostic.

The compiler generalizes by keying on the goal's STRUCTURE (a pRHL `call` goal,
a Pr-relation, a named-predicate application, N live state anchors), never on a
specific family's lemma/module/variable names. If a family token (`inv_cpa`,
`ROin`, `ChaCha`, `SplitC`, …) leaks into a matching pattern or an agent-facing
string, the producer silently becomes ad-hoc to ChaChaPoly and dead on MEE /
MLKEM / etc. This test fails when that happens, so the ad-hoc accretion that
prompted it can't creep back.

Family names are allowed ONLY in comments and docstrings (educational examples);
they must not appear in any other string literal (regex patterns, `when=` /
`advice` text, surfaced messages).
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

# Distinctive ChaChaPoly (and sibling) identifiers — a representative blocklist,
# not exhaustive; extend if a new family-specific token shows up.
_FAMILY = re.compile(
    r"inv_cpa|check_plaintext|valid_topol|ChaCha|poly1305|OpCCinit|EncRnd|"
    r"RealOrcls|CCA_game|\bRO(?:in|out|F)\b|\bSplit[CD]\w*|\bBNR\b|\bCCRO\b|"
    r"make_lbad|inv_lbad")

# Producers / analyzers whose logic + surfaced text must be family-agnostic.
_PRODUCERS = [
    "core/easycrypt/analysis/ec_relational_invariant.py",
    "core/easycrypt/analysis/ec_call_glob_invariant.py",
    "core/easycrypt/analysis/ec_pr_bridge_frontend.py",
    "core/easycrypt/analysis/ec_instantiation_binding.py",
    "core/easycrypt/analysis/ec_called_proc_body.py",
    "core/easycrypt/session_hook_phases.py",
]


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """ids of the string nodes that are module/class/function docstrings (the
    one place a family name is allowed)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                ids.add(id(body[0].value))
    return ids


def test_producers_do_not_hardcode_crypto_family_names():
    offenders: list[str] = []
    for rel in _PRODUCERS:
        f = ROOT / rel
        if not f.exists():
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        docs = _docstring_node_ids(tree)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docs and _FAMILY.search(node.value)):
                snippet = node.value.replace("\n", " ").strip()[:70]
                offenders.append(f"{rel}:{getattr(node, 'lineno', '?')}: {snippet!r}")
    assert not offenders, (
        "Producer matching logic / surfaced text hardcodes crypto-family names "
        "— keep it structural (match goal SHAPE, not family tokens). Family "
        "names belong only in comments/docstrings:\n  " + "\n  ".join(offenders))


def test_ro_domain_side_condition_miner_is_structural():
    """The miner surfaces the `dom ⊆ used-set` ingredients (in-scope RO `.m` maps
    + list/fset tracked sets) on TWO unrelated naming schemes — proving it keys on
    the RO-clone + tracked-set SHAPE, not on any family's names — and stays silent
    when an ingredient is absent."""
    from core.easycrypt.analysis import ec_relational_invariant as ri  # type: ignore

    orig = ri._relational_source_texts
    try:
        # FAMILY A — a `call`-coupling proof with an aux RO clone + a list tracker
        src_a = "module Trk = { var used : nonce list }\nmodule St = { var k : int }\n"
        goal_a = "&1 &2 : Aux.RO.m{1} = x /\\ Trk.used{1} = y ==> St.k{1} = 0"
        # FAMILY B — a DIFFERENT scheme: functored counting oracle + result sig
        src_b = "module Cnt(O : RO.RO) : POracle = { var seen : msg list }\n"
        goal_b = "&1 &2 : ={H.RO.m} /\\ Cnt.seen{2} = elems (fdom H.RO.m{2}) ==> _"

        for src, goal, ro_tok, set_tok in [
            (src_a, goal_a, ".RO.m", "used"),
            (src_b, goal_b, ".RO.m", "seen"),
        ]:
            ri._relational_source_texts = lambda _s, _x=src: [(_x, Path("x.ec"), "t")]
            sc = ri.ro_domain_side_conditions(None, goal)
            assert sc, f"miner should fire (ingredients present, {set_tok})"
            assert any(ro_tok in m for m in sc["ro_maps"]), sc["ro_maps"]
            assert any(set_tok in u for u in sc["used_lists"]), sc["used_lists"]
            assert "forall" in sc["shape"] and "\\in" in sc["shape"]

        # silent when an ingredient is missing:
        ri._relational_source_texts = lambda _s: [(src_a, Path("x.ec"), "t")]
        # (i) a tracked set but NO RO map on the goal head
        assert ri.ro_domain_side_conditions(None, "&1 &2 : Trk.used{1} = y ==> _") is None
        # (ii) an RO map on the head but NO list/fset tracker in source
        ri._relational_source_texts = lambda _s: [
            ("module St = { var k : int }", Path("x.ec"), "t")]
        assert ri.ro_domain_side_conditions(None, "Aux.RO.m{1} = x") is None
    finally:
        ri._relational_source_texts = orig


def test_module_head_parser_handles_functor_result_signatures():
    """`state_field_pool` must scan `var`s inside functor modules that carry a
    result signature (`module M(P : T) : Sig = {`) — a head form newer corpora use
    and older ones omit. Without this the tracked-set vars are never seen."""
    from core.easycrypt.analysis import ec_relational_invariant as ri  # type: ignore
    orig = ri._relational_source_texts
    try:
        src = ("module Plain = { var a : int }\n"
               "module Func(O : RO.RO) : POracle = { var seen : msg list }\n"
               "module (Red(A : Adv) : SAdv) (H : Or) = { var t : key }\n")
        ri._relational_source_texts = lambda _s: [(src, Path("x.ec"), "t")]
        q = {f["qualified"] for f in ri.state_field_pool(None)["fields"]}
        assert "Plain.a" in q          # simple head (no regression)
        assert "Func.seen" in q        # functor + result signature (the fix)
        assert "Red.t" in q            # parenthesized functored name
    finally:
        ri._relational_source_texts = orig
