from __future__ import annotations

from pathlib import Path

import pytest

from core.easycrypt.proof_strip import replace_proofs


ROOT = Path(__file__).resolve().parents[1]


def test_replace_proofs_redacts_inline_realization_proof() -> None:
    source = (
        "realize inhabited.\n"
        "  proof. by exists 0; smt(gt0_max_counter). qed.\n"
    )

    stripped, count = replace_proofs(source)

    assert count == 1
    assert "exists 0" not in stripped
    assert "smt(gt0_max_counter)" not in stripped
    assert stripped == (
        "realize inhabited.\n"
        "  proof.\n"
        "  (* COMPLETE THIS *)\n"
        "    admit.\n"
        "  qed.\n"
    )


def test_replace_proofs_inline_realization_shell_is_idempotent() -> None:
    source = (
        "realize inhabited.\n"
        "  proof.\n"
        "  (* COMPLETE THIS *)\n"
        "    admit.\n"
        "  qed.\n"
    )

    stripped, count = replace_proofs(source)

    assert stripped == source
    assert count == 0


def test_chachapoly_inline_realization_does_not_survive_eval_stripping() -> None:
    source = (
        ROOT / "eval" / "examples" / "ChaChaPoly" / "chacha_poly.ec"
    ).read_text(encoding="utf-8")

    stripped, count = replace_proofs(source)

    assert count > 0
    assert "smt(gt0_max_counter)" not in stripped
    assert "proof. by exists 0; smt(gt0_max_counter). qed." not in stripped


MLKEM_CLONE = """clone PlugAndPray as MlkemCorrGuess with
  type tval <- int,
  op indices <- iota_ 0 (TT.qHC + 1),
  type tin <- unit,
  type tres <- mlkem_corr_trace
  proof indices_not_nil by
    (rewrite -List.size_eq0 List.Iota.size_iota; smt(TT.ge0_qHC)).
"""


def test_mlkem_multiline_clone_removes_whole_body_and_preserves_next_declaration():
    after = "\nop untouched = (1, 2).\n"
    stripped, count = replace_proofs(MLKEM_CLONE + after)
    assert count == 1
    assert stripped == MLKEM_CLONE.split(" by\n")[0] + " by admit.\n" + after
    assert replace_proofs(stripped) == (stripped, 0)


@pytest.mark.parametrize("header", [
    "realize obligation by", "realize obligation\tby\t",
    "realize obligation\n  by", "realize obligation (* by fake. *) by",
    "proof obligation by", "proof obligation\n  by",
])
def test_by_whitespace_and_comments_do_not_change_the_proof_boundary(header):
    source = header + "\n  (rewrite Namespace.fact;\n   trivial). (* retained *)\nop after = true.\n"
    stripped, count = replace_proofs(source)
    assert count == 1
    assert stripped == header.rstrip() + " admit. (* retained *)\nop after = true.\n"
    assert replace_proofs(stripped) == (stripped, 0)


def test_adjacent_clone_clauses_keep_selectors_renames_and_removals():
    source = (
        "clone Base as C\n"
        "  proof first by\n    (rewrite H; trivial), second by trivial\n"
        "  proof third by\n    (trivial)\n"
        '  rename [op] "old" as "new"\n'
        "  remove abbrev helper.\n"
    )
    expected = (
        "clone Base as C\n"
        "  proof first by admit, second by admit\n"
        "  proof third by admit\n"
        '  rename [op] "old" as "new"\n'
        "  remove abbrev helper.\n"
    )
    assert replace_proofs(source) == (expected, 3)
    assert replace_proofs(expected) == (expected, 0)


def test_comments_strings_and_nested_tactic_delimiters_are_opaque():
    prefix = 'op text = "(* proof fake by . \\" *)".\n'
    suffix = " (* keep (* proof fake by hidden. *) this *)\nop tail = true.\n"
    source = (prefix + "clone Base proof p by\n"
              '  (idtac "proof, rename . (*"; (* nested (* . *) by *)\n'
              "   rewrite (f (1, 2)) H.[1..3]; [trivial | trivial])." + suffix)
    expected = prefix + "clone Base proof p by admit." + suffix
    assert replace_proofs(source) == (expected, 1)


def test_same_line_clone_proof_preserves_following_command():
    source = "clone Base proof * by (trivial). op tail = true.\n"
    assert replace_proofs(source) == ("clone Base proof * by admit. op tail = true.\n", 1)


def test_clear_is_a_tactic_not_a_clone_clause_boundary():
    source = "clone Base proof p by clear H.\n"
    assert replace_proofs(source) == ("clone Base proof p by admit.\n", 1)


def test_commented_out_by_proofs_are_byte_identical():
    source = "(* proof p by\n (trivial). (* nested *) realize x by hidden. *)\n"
    assert replace_proofs(source) == (source, 0)


@pytest.mark.parametrize("source", [
    "clone Base proof p by\n (trivial)",
    "clone Base proof p by\n (trivial.\nop tail = true.\n",
    "realize p by\n .\n",
])
def test_incomplete_by_proof_fails_preparation_instead_of_leaking_body(source):
    with pytest.raises(ValueError, match="Cannot strip"):
        replace_proofs(source)


def test_eval_preparation_refuses_incomplete_sibling_clone(tmp_path):
    from core.easycrypt.eval_source_prep import prepare_eval_source

    project = tmp_path / "input"
    project.mkdir()
    target = project / "Main.ec"
    source = "require Helper.\nlemma target : true.\nproof. trivial. qed.\n"
    target.write_text(source)
    sibling = project / "Helper.eca"
    incomplete = "clone Base proof p by\n (trivial"
    sibling.write_text(incomplete)
    output = tmp_path / "prepared"
    with pytest.raises(ValueError, match="Cannot strip"):
        prepare_eval_source(source_file=target, copy_root=project, target_lemma="target",
                            output_dir=output)
    assert not (output / "source_manifest.json").exists()
    assert target.read_text() == source
    assert sibling.read_text() == incomplete
