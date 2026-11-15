"""EasyCrypt itself resolves every declaration kind the adapter asks about.

Earlier tests mocked ``load_exact_declarations``. Against EasyCrypt r2026.06
the adapter missed every operator and type (it expected older ``print``
section names), every labelled axiom, and, in a batch, every symbol after a
missed operator (an unrecognised hit consumed the next anchor).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.easycrypt import ec_env
from core.easycrypt.compiler_namespace_adapter import (
    list_theory_members,
    load_exact_declarations,
)

pytestmark = pytest.mark.easycrypt

# A context file as the manager writes it: the proof of the current target
# is open, inside a section, so section-local declarations are in scope.
CONTEXT = """\
require import AllCore Int.
type t.
op f (x : int) : int = x + 1.
pred P (x : int) = 0 <= x.
axiom [explicit] tointK : forall (x : int), f x = x + 1.
lemma fE x : f x = x + 1 by done.
module M = { proc g(x : int) : int = { return x; } }.
equiv gE : M.g ~ M.g : ={x} ==> ={res}.
proof. by proc. qed.
theory T.
  op h : int = 3.
end T.
section S.
local lemma lE : true by done.
lemma target : true.
proof.
"""


def test_one_batch_resolves_every_declaration_kind_in_order(tmp_path: Path) -> None:
    context = tmp_path / "context.ec"
    context.write_text(CONTEXT, encoding="utf-8")
    expected = {
        "t": ("type", "type t."),
        "f": ("operator", "op f (x : int) : int = x + 1."),
        "nosuch": None,
        "P": ("operator", "pred P (x : int) = 0 <= x."),
        "tointK": ("lemma", "axiom [explicit] tointK:"),
        "fE": ("lemma", "lemma fE:"),
        "gE": ("lemma", "lemma gE: equiv["),
        "lE": ("lemma", "local  lemma lE: true."),
        "M": ("module", "module M = {"),
        "T": ("theory", "theory T."),
        "T.h": ("operator", "op h : int = 3."),
    }

    results = load_exact_declarations(list(expected), context, [])

    for symbol, want in expected.items():
        got = results[symbol]
        if want is None:
            assert got["status"] == "miss", (symbol, got)
            continue
        kind, body_start = want
        assert got["status"] == "resolved", (symbol, got)
        assert got["kind"] == kind, (symbol, got)
        assert got["body"].startswith(body_start), (symbol, got)


# A context whose earlier proofs need smt. The batch query stops at the first
# failed proof. The interactive query carries on past one, so the theory it
# prints then lacks the lemma: `inner` is what shows that query ran smt.
SMT_CONTEXT = """\
require import AllCore Int.
theory T.
  op h : int = 3.
  lemma inner (x y : int) : x < y => x + 1 <= y by smt().
end T.
lemma earlier (x y : int) : x < y => x + 1 <= y by smt().
lemma target : true.
proof.
"""


def _cvc5_only_config(tmp_path: Path) -> Path:
    """The managed Why3 configuration with every prover but CVC5 removed."""

    sections = ec_env.managed_why3_config_file().read_text(encoding="utf-8").split(
        "\n["
    )
    kept = [
        section
        for index, section in enumerate(sections)
        if index == 0 or 'name = "CVC5"' in section
    ]
    if len(kept) != 2:
        pytest.skip("the managed Why3 configuration does not register CVC5")
    config = tmp_path / "why3.conf"
    config.write_text("\n[".join(kept), encoding="utf-8")
    return config


def test_queries_replay_the_context_with_the_registered_provers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both queries replay the context's proofs, so they pass the portfolio.

    EasyCrypt's default prover list lacks CVC5. Without the session's ``-p``
    arguments a configuration that registers CVC5 alone left the replayed
    ``smt()`` with no prover, and the query failed before reaching the name.
    """

    config = _cvc5_only_config(tmp_path)
    monkeypatch.setattr(ec_env, "managed_why3_config_file", lambda: config)
    assert ec_env.managed_smt_provers() == ("CVC5",)
    context = tmp_path / "context.ec"
    context.write_text(SMT_CONTEXT, encoding="utf-8")

    declarations = load_exact_declarations(["earlier", "T.h"], context, [])
    members = list_theory_members("T", context, [])

    assert declarations["earlier"]["status"] == "resolved", declarations
    assert declarations["T.h"]["status"] == "resolved", declarations
    assert members["status"] == "ok", members
    assert members["by_kind"] == {"op": ["h"], "lemma": ["inner"]}, members
