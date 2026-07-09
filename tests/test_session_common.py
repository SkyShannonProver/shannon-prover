"""Pure-Python tests for shared session helpers."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_common import (  # type: ignore  # noqa: E402
    classify_and_format,
    is_structural_tactic,
    list_lemmas_in_file,
    render_closer_hints,
    trim_after_last_prompt,
)
from core.easycrypt import session_common as package_session_common  # noqa: E402


def test_package_import_boundary() -> None:
    assert package_session_common.is_structural_tactic("call Foo.")


def test_structural_tactic_detection() -> None:
    assert is_structural_tactic("call Foo.")
    assert is_structural_tactic("move=> x. rewrite H.")
    assert is_structural_tactic("auto => />.")
    assert not is_structural_tactic("smt().")
    assert not is_structural_tactic("move=> x.")


def test_trim_after_last_prompt() -> None:
    text = "intro\n[1|check]>\nnoise after prompt\n"
    assert trim_after_last_prompt(text) == "intro\n[1|check]>\n"
    assert trim_after_last_prompt("no prompt\n") == "no prompt\n"


def test_list_lemmas_in_file_by_scope() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "sample.ec"
        path.write_text(
            "\n".join([
                "lemma top_one : true.",
                "proof. trivial. qed.",
                "section S.",
                "  local lemma local_inner : true.",
                "  proof. trivial. qed.",
                "  equiv eq_inner : M.f ~ N.f : true ==> true.",
                "  proof. proc. skip. qed.",
                "  phoare ph_inner : [M.f : true ==> true] = 1%r.",
                "  proof. proc. skip. qed.",
                "end section.",
                "hoare top_hoare : M.f : true ==> true.",
                "phoare top_phoare : [M.f : true ==> true] = 1%r.",
            ]),
            encoding="utf-8",
        )

        info = list_lemmas_in_file(path)
        assert info["top_level"] == ["top_one", "top_hoare", "top_phoare"]
        assert info["in_sections"] == ["local_inner", "eq_inner", "ph_inner"]


def test_render_closer_hints() -> None:
    lines = render_closer_hints({
        "closer_hints": {
            "smt_lemmas": ["A", "B"],
            "unfold_ops": ["foo"],
            "typical_tail": "by smt().",
        },
    })
    joined = "\n".join(lines)
    assert "smt(A B)" in joined
    assert "rewrite /foo." in joined
    assert "by smt()." in joined


def test_classify_and_format_empty_input_is_safe() -> None:
    assert classify_and_format("") == ""


if __name__ == "__main__":
    test_package_import_boundary()
    test_structural_tactic_detection()
    test_trim_after_last_prompt()
    test_list_lemmas_in_file_by_scope()
    test_render_closer_hints()
    test_classify_and_format_empty_input_is_safe()
    print("PASS test_session_common")
