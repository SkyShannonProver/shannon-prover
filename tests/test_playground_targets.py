from __future__ import annotations

from pathlib import Path

from playground.targets import proof_declarations


def test_playground_target_scanner_includes_local_declarations(tmp_path: Path) -> None:
    src = tmp_path / "demo.ec"
    src.write_text(
        "(* local lemma hidden : true. *)\n"
        "lemma top_level : true.\n"
        "local lemma local_fact : true.\n"
        "  local equiv local_game : M.f ~ N.f : true ==> true.\n",
        encoding="utf-8",
    )

    decls = proof_declarations(src)

    assert {"name": "hidden", "kind": "local lemma", "line": 1} not in decls
    assert {"name": "top_level", "kind": "lemma", "line": 2} in decls
    assert {"name": "local_fact", "kind": "local lemma", "line": 3} in decls
    assert {"name": "local_game", "kind": "local equiv", "line": 4} in decls


def test_playground_target_scanner_exposes_chachapoly_step4_1() -> None:
    path = Path("eval/examples/ChaChaPoly/chacha_poly.ec")

    decls = proof_declarations(path)

    step4 = [item for item in decls if item["name"] == "step4_1"]
    assert step4
    assert step4[0]["kind"] == "local lemma"
    assert isinstance(step4[0]["line"], int) and step4[0]["line"] > 0
