"""Regression tests: duplicated lemma names must not break the write-back.

A lemma name declared more than once in the target file used to make a run
structurally unwinnable (observed: `xorK1` declared in both `theory Byte`
and `abstract theory GenBlock` of ChaChaPoly/chacha_poly.ec, 2026-06-11):

  1. `_write_and_verify_proof` located the lemma BY NAME with a
     prefer-needs-proving heuristic and filled the first admitted
     declaration with the proof;
  2. the post-verify `_proof_body_has_admit` re-ran the SAME heuristic on
     the NEW content, where it now resolved to the OTHER still-admitted
     declaration, found `admit`, and unconditionally reverted a genuinely
     proved lemma.

Two layers must keep this from recurring:
  * `_resolve_lemma_decl_start` resolves the declaration ONCE per
    write-back cycle; `_find_proof_block` / `_proof_body_has_admit` /
    `_prune_failing_tactics` / `extract_lemma` accept the pinned identity.
  * `workflow.orchestrator.run` fails fast at startup when the target
    lemma name is declared more than once (the eval suite already fails
    fast at prepare — see tests/test_hollow_run_guards.py).
"""
from __future__ import annotations

import types

import pytest

from core.easycrypt.lemma_decls import lemma_decl_lines, lemma_decl_matches
from core.easycrypt.lemma_extract import extract_lemma
from workflow.agents import prover_writeback, prover
from workflow.agents.prover import (
    _find_proof_block,
    _proof_body_has_admit,
    _resolve_lemma_decl_start,
    _write_and_verify_proof,
)


# The padding comment keeps the two declarations more than 500 bytes apart,
# like the real file (xorK1's declarations are ~150 lines apart in
# chacha_poly.ec) — the prefer-needs-proving heuristic only inspects a
# short window after each declaration, and with the duplicates adjacent the
# first declaration's window would see the second's `admit`, masking the
# exact resolution flip this suite pins down.
_PAD = ("(* " + "-" * 70 + " *)\n") * 8
_DUP_LEMMA_EC = f"""\
theory Byte.
  lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2.
  proof.
    admit.
  qed.
end Byte.

{_PAD}
abstract theory GenBlock.
  lemma addK b : b +^ b = zero.
  proof. trivial. qed.

  lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2.
  proof.
    admit.
  qed.
end GenBlock.
"""


def _decl_starts(content: str, name: str) -> list[int]:
    return [m.start() for m in lemma_decl_matches(content, name)]


# ── declaration resolution ───────────────────────────────────────────────────

def test_resolve_picks_first_admitted_declaration():
    starts = _decl_starts(_DUP_LEMMA_EC, "xorK1")
    assert len(starts) == 2
    assert _resolve_lemma_decl_start(_DUP_LEMMA_EC, "xorK1") == starts[0]


def test_resolve_prefers_needs_proving_over_proved():
    content = (
        "lemma L b : b = b.\n"
        "proof. trivial. qed.\n"
        + _PAD +
        "lemma L b : b = b.\n"
        "proof. admit. qed.\n"
    )
    starts = _decl_starts(content, "L")
    assert _resolve_lemma_decl_start(content, "L") == starts[1]


def test_resolve_ignores_commented_out_declaration():
    content = (
        "(* lemma L old : true.\n   proof. admit. qed. *)\n"
        "lemma L b : b = b.\n"
        "proof. admit. qed.\n"
    )
    starts = _decl_starts(content, "L")
    assert len(starts) == 1
    assert _resolve_lemma_decl_start(content, "L") == starts[0]


def test_find_proof_block_pinned_to_each_declaration():
    first, second = _decl_starts(_DUP_LEMMA_EC, "xorK1")
    b1 = _find_proof_block(_DUP_LEMMA_EC, "xorK1", decl_start=first)
    b2 = _find_proof_block(_DUP_LEMMA_EC, "xorK1", decl_start=second)
    assert b1 is not None and b2 is not None and b1 != b2
    assert first < b1[0] < second < b2[0]
    for s, e in (b1, b2):
        assert _DUP_LEMMA_EC[s:e].lstrip().startswith("proof.")
        assert "admit." in _DUP_LEMMA_EC[s:e]


def test_find_proof_block_rejects_offset_that_is_not_a_declaration():
    assert _find_proof_block(_DUP_LEMMA_EC, "xorK1", decl_start=1) is None


# ── the regression scenario: write-back + admit check ────────────────────────

def _fill_first_declaration(content: str, name: str) -> tuple[str, int]:
    """Splice a real proof (distinctive marker tactic) into the
    heuristic-chosen declaration."""
    decl_start = _resolve_lemma_decl_start(content, name)
    start, end = _find_proof_block(content, name, decl_start=decl_start)
    filled = content[:start] + "proof.\n    by rewrite xorMARK.\n  qed." + content[end:]
    return filled, decl_start


def test_admit_check_pinned_to_filled_declaration_passes():
    new_content, decl_start = _fill_first_declaration(_DUP_LEMMA_EC, "xorK1")
    # The pinned check inspects the declaration the write-back filled.
    assert _proof_body_has_admit(new_content, "xorK1", decl_start=decl_start) is False
    # The OTHER declaration is still admitted — the unpinned heuristic
    # resolves to it (this is exactly the pre-fix revert bug; kept as
    # documentation of why decl_start must be threaded through).
    assert _proof_body_has_admit(new_content, "xorK1") is True


def test_write_and_verify_does_not_revert_proved_duplicate(tmp_path, monkeypatch):
    """End-to-end through _write_and_verify_proof with EC and the event
    gates stubbed out: the proof must be accepted and the file must keep
    the written proof — before the fix this returned False and reverted."""
    f = tmp_path / "dup.ec"
    f.write_text(_DUP_LEMMA_EC)

    monkeypatch.setattr(prover_writeback, "_verify_ec_file", lambda *a, **k: (True, ""))
    monkeypatch.setattr(prover_writeback, "_prune_failing_tactics",
                        lambda ec_path, lemma_name, tactics, **k: tactics)
    gate = types.SimpleNamespace(ok=True)
    monkeypatch.setattr(prover_writeback, "_candidate_gate_for_session", lambda d: gate)
    monkeypatch.setattr(prover_writeback, "_acceptance_gate_for_session", lambda d: gate)
    monkeypatch.setattr(prover_writeback, "_emit_verification_status",
                        lambda *a, **k: True)

    assert _write_and_verify_proof(f, "xorK1", ["trivial."]) is True

    out = f.read_text()
    first, second = _decl_starts(out, "xorK1")
    # The filled declaration kept its proof; the duplicate is untouched.
    b1 = _find_proof_block(out, "xorK1", decl_start=first)
    b2 = _find_proof_block(out, "xorK1", decl_start=second)
    assert "trivial." in out[b1[0]:b1[1]]
    assert "admit." not in out[b1[0]:b1[1]]
    assert "admit." in out[b2[0]:b2[1]]


def test_write_and_verify_still_reverts_real_admit(tmp_path, monkeypatch):
    """Control: the pinned admit check still catches an admit in the
    declaration that was actually written (admit smuggled past the
    tactic-level filter, e.g. inside a multi-tactic string)."""
    f = tmp_path / "dup.ec"
    f.write_text(_DUP_LEMMA_EC)

    monkeypatch.setattr(prover_writeback, "_verify_ec_file", lambda *a, **k: (True, ""))
    monkeypatch.setattr(prover_writeback, "_prune_failing_tactics",
                        lambda ec_path, lemma_name, tactics, **k: tactics)
    gate = types.SimpleNamespace(ok=True)
    monkeypatch.setattr(prover_writeback, "_candidate_gate_for_session", lambda d: gate)
    monkeypatch.setattr(prover_writeback, "_acceptance_gate_for_session", lambda d: gate)
    monkeypatch.setattr(prover_writeback, "_emit_verification_status",
                        lambda *a, **k: True)
    # Bypass the tactic-level admit filter to exercise the post-verify net.
    monkeypatch.setattr(prover_writeback, "_tactics_contain_admit", lambda tactics: False)

    assert _write_and_verify_proof(f, "xorK1", ["admit."]) is False
    assert f.read_text() == _DUP_LEMMA_EC  # reverted


# ── extract_lemma declaration pinning ────────────────────────────────────────

def test_extract_lemma_decl_line_picks_pinned_declaration(tmp_path):
    f = tmp_path / "dup.ec"
    new_content, _ = _fill_first_declaration(_DUP_LEMMA_EC, "xorK1")
    f.write_text(new_content)
    second_start = _decl_starts(new_content, "xorK1")[1]
    second_line = new_content.count("\n", 0, second_start)

    first = extract_lemma(f, "xorK1", verify_proof=True)
    pinned = extract_lemma(f, "xorK1", verify_proof=True, decl_line=second_line)
    assert "xorMARK" in first       # default = first declaration (filled)
    assert "xorMARK" not in pinned  # pinned = second (still admitted)


def test_extract_lemma_decl_line_rejects_non_declaration_line(tmp_path):
    f = tmp_path / "dup.ec"
    f.write_text(_DUP_LEMMA_EC)
    with pytest.raises(ValueError, match="does not declare"):
        extract_lemma(f, "xorK1", verify_proof=True, decl_line=0)


# ── orchestrator startup guard ───────────────────────────────────────────────

def test_orchestrator_fails_fast_on_duplicate_lemma(tmp_path):
    from workflow.orchestrator import run as orchestrator_run
    from workflow.schemas.config import RunConfig

    f = tmp_path / "dup.ec"
    f.write_text(_DUP_LEMMA_EC)
    out_dir = tmp_path / "runs"
    config = RunConfig(file=str(f), lemma="xorK1", output_dir=str(out_dir))

    result = orchestrator_run(config)
    assert "declared 2 times" in result["error"]
    assert "xorK1" in result["error"]
    assert not out_dir.exists()  # failed before creating any run artifacts


def test_orchestrator_guard_allows_unique_lemma(tmp_path):
    from workflow.orchestrator import _duplicate_lemma_error
    from workflow.schemas.config import RunConfig

    f = tmp_path / "ok.ec"
    f.write_text("lemma L b : b = b.\nproof. admit. qed.\n")
    assert _duplicate_lemma_error(RunConfig(file=str(f), lemma="L")) is None
    # Unreadable target fails open — later prechecks own that error.
    missing = RunConfig(file=str(tmp_path / "nope.ec"), lemma="L")
    assert _duplicate_lemma_error(missing) is None


def test_shared_decl_lines_match_fixture():
    assert lemma_decl_lines(_DUP_LEMMA_EC, "xorK1") == [2, 21]
    assert lemma_decl_lines(_DUP_LEMMA_EC, "addK") == [18]


# ── second real-world shape: local sections, different statements ────────────
#
# `local_conclusion` in eval/examples/MEE-CBC/MAC_then_Pad_then_CBC.eca is
# declared twice with DIFFERENT statements (an INDR_CPA bound and an
# INT_PTXT bound) inside two different local sections, and both copies are
# fully PROVED — unlike xorK1, where both were admit stubs. Observed
# 2026-06-11 (suites mee_hard1/mee_hard1b): this shape produced a second
# failure mode — the single-target scrub blanked only ONE declaration's
# proof, the other stayed intact, and the orchestrator's already-proved
# pre-check matched the intact one and reported "Lemma already proved and
# verified. Skipping." (a false-skip; the target goal never opened).
# The duplicate guards must fire on this shape too, BEFORE any scrub or
# already-proved check can run.

_DUP_SECTIONS_EC = f"""\
require import AllCore.

section INDR_CPA.
  declare module A <: RCPA_Adv.

  local lemma local_conclusion &m:
    Pr[INDR_CPA(MtE, A).main() @ &m : res] <= eps_prp + eps_pad.
  proof.
    by apply (Conclusion A &m).
  qed.

  lemma security_cpa &m: Pr[INDR_CPA(MtE, A).main() @ &m : res] <= eps_prp + eps_pad.
  proof. by apply (local_conclusion &m). qed.
end section.

{_PAD}
section INT_PTXT.
  declare module B <: PTXT_Adv.

  local lemma local_conclusion &m:
    Pr[INT_PTXT(MtE, B).main() @ &m : res] <= eps_mac.
  proof.
    by apply (ConclusionP B &m).
  qed.

  lemma security_ptxt &m: Pr[INT_PTXT(MtE, B).main() @ &m : res] <= eps_mac.
  proof. by apply (local_conclusion &m). qed.
end section.
"""


def test_decl_lines_local_lemma_in_sections_different_statements():
    # `local lemma` prefix + section blocks + different statements + proved
    # bodies — the detector must still see both declarations, and must not
    # count the `apply (local_conclusion &m)` USAGE sites as declarations.
    assert lemma_decl_lines(_DUP_SECTIONS_EC, "local_conclusion") == [6, 28]


def test_resolve_falls_back_to_first_when_both_proved():
    # Neither copy needs proving, so the unpinned heuristic falls back to
    # the first declaration — documented so the guards stay the real defense.
    starts = _decl_starts(_DUP_SECTIONS_EC, "local_conclusion")
    assert len(starts) == 2
    assert _resolve_lemma_decl_start(_DUP_SECTIONS_EC, "local_conclusion") == starts[0]


def test_orchestrator_fails_fast_on_sectioned_duplicate(tmp_path):
    # Guard must fire before the already-proved pre-check ever runs — this
    # is the path that produced the mee_hard1b false-skip.
    from workflow.orchestrator import _duplicate_lemma_error
    from workflow.schemas.config import RunConfig

    f = tmp_path / "mte.eca"
    f.write_text(_DUP_SECTIONS_EC)
    err = _duplicate_lemma_error(RunConfig(file=str(f), lemma="local_conclusion"))
    assert err is not None
    assert "declared 2 times" in err
    assert "lines 6, 28" in err


# ── pins on the two real corpus files that produced the field failures ───────
# Both lemmas WERE duplicated (xorK1 in two ChaChaPoly theories ~150 lines
# apart; local_conclusion twice in MEE-CBC) — the structurally-unwinnable case
# this module guards. The corpus has since been de-duplicated (the second
# declaration renamed), so each now resolves to a single line. This pins that
# the de-dup stays intact: if a duplicate is reintroduced, the detector returns
# two lines and this assertion fails.
_REAL_INSTANCES = [
    ("eval/examples/ChaChaPoly/chacha_poly.ec", "xorK1", [54]),
    ("eval/examples/MEE-CBC/MAC_then_Pad_then_CBC.eca", "local_conclusion",
     [411]),
]


@pytest.mark.parametrize("rel_path,lemma,expected_lines", _REAL_INSTANCES)
def test_detector_pins_real_corpus_lemmas(rel_path, lemma, expected_lines):
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / rel_path
    if not f.is_file():
        pytest.skip(f"corpus file not present: {rel_path}")
    assert lemma_decl_lines(f.read_text(encoding="utf-8"), lemma) == expected_lines
