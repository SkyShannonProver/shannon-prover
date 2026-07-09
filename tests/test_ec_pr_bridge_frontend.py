"""Tests for the typed Pr-bridge frontend's scheme-normalization pass.

These exercise the family-general candidate generator that replaced the retired
ChaChaPoly-shaped regex compiler.  The pass must derive clone-qualified
``have -> ... by byequiv...`` normalization candidates from generic name
resolution + module-type signature matching, with NO benchmark-family token
hardcodes.  Daemon verification (which selects the single correct
instantiation) lives in ``_try_bridge_suggest`` and is covered separately.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_pr_bridge_frontend import (  # noqa: E402
    _clone_alias_map,
    _modules_matching_module_type,
    _oracle_scheme_normalization_bridges,
    _pr_term_records,
    _scheme_normalization_functors,
)


# A synthetic, non-ChaChaPoly family: a concrete scheme `SymCipher`, an
# open/parameterized functor `OSymCipher(S:St)` in a doubly-cloned theory
# `Box`, and two `St`-typed init modules.  None of the benchmark tokens
# (ChaChaPoly / CCA_game / RealOrcls / Mem.k / OChaChaPoly) appear.
_SYNTHETIC_CONTEXT = """
require import AllCore.

abstract theory Box.
  type gs.

  module type St = {
    proc init () : gs
  }.

  module OSymCipher (S:St) = {
    include S [init]
    proc enc (k:int, m:int) : int = { return m; }
  }.
end Box.

clone import Box as Box0 with type gs <- int.
clone import Box as Box1 with type gs <- bool.

module SymCipher = {
  proc init () : unit = {}
  proc enc (k:int, m:int) : int = { return m; }
}.

module St0 = { proc init () : int = { return 0; } }.
module St1 = { proc init () : int = { return 1; } }.
"""


def _session_with_synthetic_context(tmp_path: Path) -> str:
    (tmp_path / "context.ec").write_text(_SYNTHETIC_CONTEXT, encoding="utf-8")
    return str(tmp_path)


def test_clone_and_functor_resolution_is_name_driven(tmp_path) -> None:
    session_dir = _session_with_synthetic_context(tmp_path)

    alias_map = _clone_alias_map(session_dir)
    assert sorted(alias_map.get("Box") or []) == ["Box0", "Box1"]

    functors = {f["name"]: f for f in _scheme_normalization_functors(session_dir)}
    assert "OSymCipher" in functors
    assert functors["OSymCipher"]["formal_bound"] == "St"
    assert functors["OSymCipher"]["theory"] == "Box"

    inits = _modules_matching_module_type(session_dir, "St", {"SymCipher", "St0", "St1"})
    # Exact-signature init modules rank first (St0/St1 over the superset SymCipher).
    assert inits[:2] == ["St0", "St1"]


def test_scheme_normalization_bridges_are_clone_qualified_and_family_general(
    tmp_path,
) -> None:
    session_dir = _session_with_synthetic_context(tmp_path)
    goal_text = (
        "Pr[Exp_game(A, Wrap(SymCipher)).main() @ &m : res] = "
        "Pr[Dist(D(A), Blk).run() @ &m : res]"
    )
    bridges = _oracle_scheme_normalization_bridges(
        session_dir=session_dir,
        terms=_pr_term_records(goal_text),
    )
    tactics = [b["tactic"] for b in bridges]

    assert bridges, "expected scheme-normalization candidates for the wrapper endpoint"

    # The correct-shaped candidate (clone-qualified functor + init substitution)
    # is enumerated; the daemon, not this pass, picks the one it can prove.
    assert any(
        "Wrap(Box0.OSymCipher(St0))" in t for t in tactics
    ), tactics

    for bridge in bridges:
        tactic = bridge["tactic"]
        assert tactic.startswith("have -> :")
        assert tactic.rstrip().endswith("sim.")
        # endpoint-local: only the concrete scheme token is rewritten
        assert bridge["scheme_module"] == "SymCipher"
        assert bridge["edge_kind"] == "scheme_normalization_bridge"
        # clone-qualified target (un-qualified members of a doubly-cloned
        # theory would be ambiguous and fail to resolve)
        assert "Box0." in bridge["adapter_module"] or "Box1." in bridge["adapter_module"]
        # never re-introduce benchmark-family hardcodes
        for forbidden in ("ChaChaPoly", "CCA_game", "RealOrcls", "Mem.k", "OChaChaPoly"):
            assert forbidden not in tactic


def test_no_scheme_bridge_without_a_matching_normalization_functor(tmp_path) -> None:
    """A wrapper whose inner scheme has no name-stem-sharing functor yields no
    candidate (the pass does not invent normalization targets)."""
    session_dir = _session_with_synthetic_context(tmp_path)
    # `Blk` has no `*Blk*` functor in scope -> no normalization bridge.
    goal_text = (
        "Pr[Exp_game(A, Wrap(Blk)).main() @ &m : res] = "
        "Pr[Dist(D(A), Blk).run() @ &m : res]"
    )
    bridges = _oracle_scheme_normalization_bridges(
        session_dir=session_dir,
        terms=_pr_term_records(goal_text),
    )
    assert bridges == []
