"""parse_equiv_lemmas must surface PARAMETERIZED / FUNCTOR-endpoint local equivs.

The old regex required `:` right after the name and excluded parens in endpoints,
so it dropped EVERY such lemma (e.g. `local equiv equ_cc n0 mr0 ms0: ChaCha(...).enc
~ EncRnd.cc`) — the agent then read .ec source for the name. And the recommendation
extractor's opener set lacked `exact`/`symmetry`, so a 1-hop direct bridge was dropped
to []. panel audit: project_bridge_lemma_call_frontier_gap / INSPECT_QUALITY.md.
"""
from core.easycrypt.ec_bridge_lemmas import parse_equiv_lemmas
from core.easycrypt.search.handlers import _bridge_lemma_recommendations

EQU_CC = """
  local equiv equ_cc n0 mr0 ms0:
     ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(ROin, ROout), ROF))).enc
     ~
     EncRnd.cc :
       arg{2} = (arg.`2, arg.`3){1} /\\ arg{2}.`1 = n0 ==> ={res}.
"""


def test_parse_parameterized_functor_equiv():
    ls = parse_equiv_lemmas(EQU_CC)
    assert len(ls) == 1
    lem = ls[0]
    assert lem.name == "equ_cc"
    assert lem.params == "n0 mr0 ms0"             # binders captured, not dropped
    assert lem.lhs.startswith("ChaCha(") and lem.lhs.endswith(".enc")  # functor endpoint intact
    assert lem.rhs == "EncRnd.cc"


def test_typed_binder_colon_does_not_split_decl():
    # the `:` inside `(k : key)` must NOT be mistaken for the judgment colon
    ls = parse_equiv_lemmas(
        "local equiv enc_eq (k : key) (p : ptxt) : E.enc ~ E.enc : ={arg} ==> ={res}.")
    assert len(ls) == 1 and ls[0].name == "enc_eq"
    assert ls[0].lhs == "E.enc" and ls[0].rhs == "E.enc"
    assert ls[0].params == "(k : key) (p : ptxt)"


def test_old_single_line_equiv_still_parses():
    ls = parse_equiv_lemmas("equiv Name: A.f ~ B.g : true ==> ={res}.")
    assert len(ls) == 1 and ls[0].name == "Name"
    assert ls[0].lhs == "A.f" and ls[0].rhs == "B.g" and ls[0].params == ""


def test_direct_bridge_exact_symmetry_recommendations_not_dropped():
    out = "exact equ_cc.\nsymmetry; exact bridge0.\n- exact Direct.\n  listing: Foo ~ Bar"
    acts = [r["action"] for r in _bridge_lemma_recommendations(out)]
    assert "exact equ_cc." in acts
    assert any(a.startswith("symmetry") for a in acts)
    assert "exact Direct." in acts
    assert not any("Foo ~ Bar" in a for a in acts)   # a listing line is not a tactic
