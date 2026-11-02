from __future__ import annotations

from pathlib import Path

import pytest

from core.easycrypt.lemma_extract import _replace_proofs_with_admit, extract_lemma


def test_multiline_statement_by_smt_is_closed_before_admit() -> None:
    lines = [
        "lemma helper x:",
        "  P x",
        "by smt().",
        "",
        "lemma target : true.",
        "proof.",
        "  trivial.",
        "qed.",
    ]

    out = _replace_proofs_with_admit(lines, keep_open_line=5)
    joined = "\n".join(out)

    assert "lemma helper x:\n  P x.\nproof.\n  admit.\nqed." in joined
    assert "lemma helper x:\n  P x\nproof." not in joined
    assert "lemma target : true.\nproof." in joined
    assert "trivial." not in joined


def test_extract_finds_phoare_declarations(tmp_path: Path) -> None:
    ec_file = tmp_path / "Sample.ec"
    ec_file.write_text(
        "\n".join([
            "module M = { proc f() : bool = { return true; } }.",
            "",
            "section S.",
            "  phoare target_phoare x :",
            "    [M.f : true ==> res] = 1%r.",
            "  proof.",
            "    proc; auto.",
            "  qed.",
            "end section.",
        ]),
        encoding="utf-8",
    )

    out = extract_lemma(ec_file, "target_phoare", open_proof=True)

    assert "section." in out
    assert "phoare target_phoare x :" in out
    assert "  proof." in out
    assert "proc; auto." not in out
    assert "qed." not in out


def test_extract_opens_bare_admit_target_not_following_lemma(tmp_path: Path) -> None:
    ec_file = tmp_path / "BareAdmit.ec"
    ec_file.write_text(
        "\n".join([
            "section S.",
            "  local lemma target x:",
            "    P x = Q x.",
            "admit.",
            "",
            "  local lemma next : true.",
            "  proof.",
            "    trivial.",
            "  qed.",
            "end section.",
        ]),
        encoding="utf-8",
    )

    out = extract_lemma(ec_file, "target", open_proof=True)

    assert "section." in out
    assert "local lemma target x:" in out
    assert "    P x = Q x." in out
    assert "  proof." in out
    assert "admit." not in out
    assert "local lemma next" not in out
    assert "trivial." not in out
    assert "qed." not in out


def test_extract_keeps_equiv_judgments_inside_multiline_lemma_statement(tmp_path: Path) -> None:
    ec_file = tmp_path / "EquivStatement.ec"
    ec_file.write_text(
        "\n".join([
            "module type PRF = { proc init(): unit proc f(x:int): int }.",
            "module M(P:PRF) = { proc main(): bool = { return true; } }.",
            "",
            "lemma bridge (P <: PRF)",
            "             (P' <: PRF)",
            "             (I: (glob P) -> (glob P') -> bool):",
            "  equiv [P.init ~ P'.init: true ==> I (glob P){1} (glob P'){2}] =>",
            "  equiv [P.f ~ P'.f: ={arg} ==> ={res}] =>",
            "  forall &m,",
            "    Pr[M(P).main() @ &m : res] = Pr[M(P').main() @ &m : res].",
            "proof.",
            "  admit.",
            "qed.",
        ]),
        encoding="utf-8",
    )

    out = extract_lemma(ec_file, "bridge", open_proof=True)

    assert "lemma bridge (P <: PRF)" in out
    assert "(P' <: PRF)" in out
    assert "equiv [P.init ~ P'.init" in out
    assert "equiv [P.f ~ P'.f" in out
    assert "forall &m," in out
    assert "Pr[M(P).main()" in out
    assert "proof." in out
    assert "admit." not in out


def test_extract_opens_single_line_proof_block(tmp_path: Path) -> None:
    ec_file = tmp_path / "SingleLine.ec"
    ec_file.write_text(
        "lemma target : true.\n"
        "proof. trivial. qed.\n"
        "lemma later : true.\n"
        "proof. trivial. qed.\n",
        encoding="utf-8",
    )

    out = extract_lemma(ec_file, "target", open_proof=True)

    assert out.endswith("proof.")
    assert "trivial." not in out
    assert "qed." not in out
    assert "lemma later" not in out


def test_extract_opens_proof_on_declaration_line(tmp_path: Path) -> None:
    ec_file = tmp_path / "InlineDeclaration.ec"
    ec_file.write_text(
        "lemma target : true. proof. trivial. qed.\n",
        encoding="utf-8",
    )

    out = extract_lemma(ec_file, "target", open_proof=True)

    assert out == "lemma target : true. proof."


def _write(tmp_path: Path, text: str) -> Path:
    ec_file = tmp_path / "Target.ec"
    ec_file.write_text(text, encoding="utf-8")
    return ec_file


@pytest.mark.parametrize("text", [
    "lemma target : true.\nproof.\n  trivial.\n",
    "lemma target : true.\nadmit.\nlemma later : true.\nproof. trivial. qed.\n",
    "lemma target : true.\n",
])
def test_verify_refuses_a_target_left_open(tmp_path: Path, text: str) -> None:
    # EasyCrypt accepts a proof left open at the end of a file, so such an
    # extract would verify nothing.
    with pytest.raises(ValueError, match="no proof closed"):
        extract_lemma(_write(tmp_path, text), "target", verify_proof=True)


def test_verify_keeps_a_one_line_by_target_intact(tmp_path: Path) -> None:
    text = (
        "lemma helper : true.\nproof.\n  smt().\nqed.\n"
        "lemma target (x : int) : x = x by smt().\n"
        "lemma later : true.\nproof.\n  smt().\nqed.\n"
    )

    out = extract_lemma(_write(tmp_path, text), "target", verify_proof=True)

    assert out.endswith("lemma target (x : int) : x = x by smt().")
    assert "lemma helper : true.\nproof.\n    admit.\nqed." in out
    assert "later" not in out


def test_open_closes_a_one_line_by_statement(tmp_path: Path) -> None:
    text = "lemma target : true by trivial.\nlemma later : true.\nproof. trivial. qed.\n"

    out = extract_lemma(_write(tmp_path, text), "target", open_proof=True)

    assert out == "lemma target : true.\nproof."


def test_open_skips_a_commented_out_copy_of_the_target(tmp_path: Path) -> None:
    text = (
        "(*\nlemma target : false.\nproof. admit. qed.\n*)\n"
        "lemma target : true.\nproof.\n  trivial.\nqed.\n"
    )

    out = extract_lemma(_write(tmp_path, text), "target", open_proof=True)

    assert out.endswith("*)\nlemma target : true.\nproof.")


def test_open_cuts_tactics_after_proof_on_the_same_line(tmp_path: Path) -> None:
    text = "lemma target : true.\nproof. move=> x.\n  trivial.\nqed.\n"

    out = extract_lemma(_write(tmp_path, text), "target", open_proof=True)

    assert out == "lemma target : true.\nproof."


def test_a_comment_after_proof_does_not_keep_another_proof_body(tmp_path: Path) -> None:
    text = (
        "lemma helper : true.\nproof.   (* slow *)\n  smt().\nqed.\n"
        "lemma target : true.\nproof.\n  trivial.\nqed.\n"
    )

    out = extract_lemma(_write(tmp_path, text), "target", open_proof=True)

    assert "smt()" not in out
    assert "proof.   (* slow *)\n    admit.\nqed." in out


def test_a_dropped_line_takes_the_rest_of_its_comment(tmp_path: Path) -> None:
    text = (
        "lemma helper : true.\nproof.\n  (* kept *)\n  smt(). (* begin\n  end *)\n  trivial.\nqed.\n"
        "lemma target : true.\nproof.\n  trivial.\nqed.\n"
    )

    out = extract_lemma(_write(tmp_path, text), "target", open_proof=True)

    assert out.startswith("lemma helper : true.\nproof.\n    admit.\n  (* kept *)\nqed.\n")
    assert "end *)" not in out
