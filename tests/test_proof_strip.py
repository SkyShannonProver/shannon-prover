from __future__ import annotations

from pathlib import Path

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
