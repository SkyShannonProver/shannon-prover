from __future__ import annotations

from pathlib import Path

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
