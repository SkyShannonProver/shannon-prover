"""Project-level verdicts must reject proofs EasyCrypt accepts unchecked.

EasyCrypt r2026.06 exits 0 on `admit; trivial.`, `try admit; done.`, the
`admitted` proof end and `pragma Proofs:weak` followed by `smt()`. Before
the public audit of v0.3.0 (2026-10-28) the final check matched only a
literal `admit.`, so a target whose auxiliary lemma used one of these was
reported proved.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest

from experiments.interleaved_shannon import verify_task as reference
from experiments.interleaved_shannon.run_shannon import _merge_verified_proof
from workflow.interleaved import verify as verifier
from workflow.interleaved.project import PROJECT_ENV, InterleavedProject


ROOT = Path(__file__).resolve().parents[1]

UNCHECKED_AUXILIARY = {
    "admit_then_tactic": "lemma Aux : false.\nproof. admit; trivial. qed.\n",
    "try_admit": "lemma Aux : false.\nproof. try admit; done. qed.\n",
    "admitted": "lemma Aux : false.\nproof. admitted.\n",
    "weak_pragma": "pragma Proofs:weak.\nlemma Aux : false.\nproof. smt(). qed.\n",
    "comment_glued_admit": "lemma Aux : false.\nproof. by(* x *)admit. qed.\n",
    "exit_before_final": "lemma Aux : true.\nproof. trivial. qed.\nexit.\n",
}


@pytest.mark.parametrize("name", sorted(UNCHECKED_AUXILIARY))
def test_final_check_rejects_a_target_that_skips_a_goal(monkeypatch, name):
    (ROOT / "artifacts").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unchecked-final-", dir=ROOT / "artifacts") as directory:
        scratch = Path(directory)
        target = scratch / "Target.ec"
        target.write_text(
            "require import AllCore.\n" + UNCHECKED_AUXILIARY[name]
            + "lemma Final : true.\nproof. trivial. qed.\n",
            encoding="utf-8",
        )
        project = InterleavedProject(
            target_file=str(target.relative_to(ROOT)), final_lemma="Final",
        )
        project_path = scratch / "project.json"
        project.write(project_path)
        monkeypatch.setenv(PROJECT_ENV, str(project_path.relative_to(ROOT)))

        code, final = verifier.verify("final")

        assert code != 0 and final["passed"] is False
        assert final["easycrypt_exit_code"] == 0
        assert any("skips proof obligations" in error for error in final["errors"])


def test_import_check_rejects_a_candidate_that_weakens_checking(tmp_path):
    candidate = tmp_path / "Target.ec"
    candidate.write_text(
        "require import AllCore.\npragma Proofs:weak.\n"
        "lemma L : false.\nproof. smt(). qed.\n",
        encoding="utf-8",
    )

    imported = verifier.verify_lemma_import(
        root=tmp_path, candidate=candidate, lemma="L", target=candidate,
        include_dirs=(), check_dir=tmp_path / "check",
    )

    assert imported["passed"] is False
    assert "disables strict proof checking" in imported["error"]


def test_confined_merge_rejects_a_body_that_weakens_checking(tmp_path):
    current = "lemma L : false.\nproof.\n  admit.\nqed.\n"
    isolated = "lemma L : false.\nproof.\n  pragma Proofs:weak. smt().\nqed.\n"
    target = tmp_path / "target.ec"
    projected = tmp_path / "projected.ec"
    target.write_text(current, encoding="utf-8")
    projected.write_text(isolated, encoding="utf-8")

    with pytest.raises(ValueError, match="still contains admit"):
        _merge_verified_proof(
            isolated_file=projected,
            target_file=target,
            lemma="L",
            prepared_source=current,
            expected_target_sha256=hashlib.sha256(current.encode()).hexdigest(),
        )
    assert target.read_text(encoding="utf-8") == current


def test_reference_final_policy_forbids_the_admitted_proof_end():
    assert reference.editable_region_forbidden_words(
        "final", "", "lemma L : false.\nproof. admitted.\n",
    ) == ["admit"]
    assert reference.editable_region_forbidden_words(
        "check", "", "lemma L : false.\nproof. admitted.\n",
    ) == []


def test_final_check_discards_a_cache_next_to_the_target(monkeypatch):
    (ROOT / "artifacts").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eco-final-", dir=ROOT / "artifacts") as directory:
        scratch = Path(directory)
        target = scratch / "Target.ec"
        target.write_text("lemma Final : true.\nproof. trivial. qed.\n", encoding="utf-8")
        cache = scratch / "Target.eco"
        cache.write_text("forged", encoding="utf-8")
        project = InterleavedProject(
            target_file=str(target.relative_to(ROOT)), final_lemma="Final",
        )
        project_path = scratch / "project.json"
        project.write(project_path)
        monkeypatch.setenv(PROJECT_ENV, str(project_path.relative_to(ROOT)))

        code, final = verifier.verify("final")

        assert code == 0, final
        assert not cache.exists()
