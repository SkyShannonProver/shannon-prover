"""Write-back must never leave an unverified proof in the user's source.

The single-lemma path writes the selected proof into the user's own file.
These tests pin that the file changes only when the exact new content has
passed offline verification, and that verification scratch files are
private to one call.
"""
from __future__ import annotations

from pathlib import Path

from workflow.agents import prover_writeback


def test_extracted_verification_uses_a_private_scratch_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_writeback, "_claude_scratch_path", lambda name: tmp_path / name,
    )
    seen: list[tuple[Path, str]] = []

    def _verify(path, source, **_kwargs):
        seen.append((path, path.read_text(encoding="utf-8")))
        return True, ""

    monkeypatch.setattr(prover_writeback, "_verify_extracted_file", _verify)
    for marker in ("first", "second"):
        source = tmp_path / marker / "T.ec"
        source.parent.mkdir()
        source.write_text(
            f"lemma t : true.\nproof.\n  (* {marker} *) trivial.\nqed.\n",
            encoding="utf-8",
        )
        assert prover_writeback._verify_lemma_extracted(source, "t")[0]

    (first_path, first_text), (second_path, second_text) = seen
    assert first_path != second_path
    assert "first" in first_text and "second" in second_text
    assert not first_path.exists() and not second_path.exists()


# -- write-back ----------------------------------------------------------------

import os  # noqa: E402
import stat  # noqa: E402
import types  # noqa: E402

import pytest  # noqa: E402

_ADMITTED = (
    "require import AllCore Base.\n"
    "lemma t : c = 3.\n"
    "proof.\n"
    "  admit.\n"
    "qed.\n"
)


def _target(tmp_path: Path) -> Path:
    (tmp_path / "Base.ec").write_text("op c : int = 3.\n", encoding="utf-8")
    path = tmp_path / "T.ec"
    path.write_text(_ADMITTED, encoding="utf-8")
    return path


def _stub_gates(monkeypatch, path: Path):
    gate = types.SimpleNamespace(ok=True, verification_status="pass")
    monkeypatch.setattr(
        "workflow.proof_acceptance.validate_completion_candidate_contract",
        lambda _candidate: gate,
    )
    monkeypatch.setattr(prover_writeback, "_acceptance_gate_for_session", lambda _d: gate)
    monkeypatch.setattr(prover_writeback, "_emit_verification_status", lambda *a, **k: True)
    return types.SimpleNamespace(
        target_file=str(path), target_lemma="t",
        session_dir=str(path.parent / ".ec_session"), candidate_id="test",
    )


def _leftovers(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir() if "shannon-verify" in p.name)


def test_interrupted_verification_leaves_the_source_untouched(tmp_path, monkeypatch):
    path = _target(tmp_path)
    candidate = _stub_gates(monkeypatch, path)

    def _interrupted(*_args, **_kwargs):
        raise KeyboardInterrupt  # what SIGTERM becomes in the entry points

    monkeypatch.setattr(prover_writeback, "_verify_ec_file", _interrupted)
    with pytest.raises(KeyboardInterrupt):
        prover_writeback._write_and_verify_proof(
            path, "t", ["by rewrite /c."], candidate,
        )
    assert path.read_text(encoding="utf-8") == _ADMITTED
    assert _leftovers(tmp_path) == []


def test_verification_checks_a_copy_and_the_source_changes_only_after(
    tmp_path, monkeypatch,
):
    path = _target(tmp_path)
    candidate = _stub_gates(monkeypatch, path)
    seen = []

    def _verify(checked: Path, **_kwargs):
        seen.append((checked, checked.read_text(encoding="utf-8"),
                     path.read_text(encoding="utf-8")))
        return True, ""

    monkeypatch.setattr(prover_writeback, "_verify_ec_file", _verify)
    evidence = prover_writeback._write_and_verify_proof(
        path, "t", ["by rewrite /c."], candidate,
    )

    assert evidence.passed
    [(checked, checked_text, source_during_check)] = seen
    assert checked.parent == path.parent.resolve() and checked != path.resolve()
    assert "by rewrite /c." in checked_text
    assert source_during_check == _ADMITTED
    assert path.read_text(encoding="utf-8") == checked_text
    assert _leftovers(tmp_path) == []


def test_failed_verification_never_writes_and_cleans_up(tmp_path, monkeypatch):
    path = _target(tmp_path)
    candidate = _stub_gates(monkeypatch, path)
    copy_names = []

    def _fail(checked: Path, **_kwargs):
        copy_names.append(checked.name)
        return False, f"[critical] [{checked}: line 3 (2-8)] cannot prove goal"

    monkeypatch.setattr(prover_writeback, "_verify_ec_file", _fail)
    monkeypatch.setattr(
        prover_writeback, "_verify_lemma_extracted",
        lambda *a, **k: (False, "[critical] extracted failed"),
    )
    evidence = prover_writeback._write_and_verify_proof(
        path, "t", ["smt()."], candidate,
    )

    assert not evidence.passed
    assert path.read_text(encoding="utf-8") == _ADMITTED
    assert _leftovers(tmp_path) == []
    # The diagnostic names the user's file, not the private copy.
    assert str(path) in evidence.error
    assert copy_names[0] not in evidence.error


def test_source_edited_during_verification_is_kept(tmp_path, monkeypatch):
    path = _target(tmp_path)
    candidate = _stub_gates(monkeypatch, path)
    edited = _ADMITTED + "(* edited while the check ran *)\n"

    def _verify(*_args, **_kwargs):
        path.write_text(edited, encoding="utf-8")
        return True, ""

    monkeypatch.setattr(prover_writeback, "_verify_ec_file", _verify)
    evidence = prover_writeback._write_and_verify_proof(
        path, "t", ["by rewrite /c."], candidate,
    )

    assert not evidence.passed
    assert "changed during verification" in evidence.error
    assert path.read_text(encoding="utf-8") == edited


def test_written_source_keeps_its_permissions(tmp_path, monkeypatch):
    path = _target(tmp_path)
    os.chmod(path, 0o640)
    candidate = _stub_gates(monkeypatch, path)
    monkeypatch.setattr(prover_writeback, "_verify_ec_file", lambda *a, **k: (True, ""))

    assert prover_writeback._write_and_verify_proof(
        path, "t", ["by rewrite /c."], candidate,
    ).passed
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.easycrypt
@pytest.mark.parametrize("tactics, passes", [
    (["by rewrite /c."], True),
    (["by rewrite /c; smt()."], True),
    (["move=> h."], False),
])
def test_real_easycrypt_checks_the_copy_beside_its_sibling_theories(
    tmp_path, monkeypatch, tactics, passes,
):
    path = _target(tmp_path)
    candidate = _stub_gates(monkeypatch, path)
    monkeypatch.setattr(
        prover_writeback, "_claude_scratch_path", lambda name: tmp_path / "scratch" / name,
    )
    (tmp_path / "scratch").mkdir()

    evidence = prover_writeback._write_and_verify_proof(path, "t", tactics, candidate)

    assert evidence.passed is passes
    text = path.read_text(encoding="utf-8")
    assert (tactics[0] in text) is passes
    assert ("admit." in text) is not passes
    assert _leftovers(tmp_path) == []


# The precheck leaves a failing proof in place, so write-back must find it in
# whatever layout the user wrote it.
@pytest.mark.parametrize("failing", [
    "lemma t : c = 3.\nproof. smt(). qed.\n",
    "lemma t : c = 3. proof. smt(). qed.\n",
    "lemma t : c = 3.\nproof.\n  move=> h. qed.\n",
])
def test_writeback_replaces_a_failing_proof_in_any_layout(tmp_path, monkeypatch, failing):
    path = _target(tmp_path)
    original = "require import AllCore Base.\n" + failing + "\nlemma u : true.\nproof. trivial. qed.\n"
    path.write_text(original, encoding="utf-8")
    candidate = _stub_gates(monkeypatch, path)
    monkeypatch.setattr(prover_writeback, "_verify_ec_file", lambda *a, **k: (True, ""))

    assert prover_writeback._write_and_verify_proof(
        path, "t", ["by rewrite /c.", "qed."], candidate,
    ).passed
    text = path.read_text(encoding="utf-8")
    assert "by rewrite /c." in text
    assert "smt()" not in text and "move=> h" not in text
    assert text.endswith("\nlemma u : true.\nproof. trivial. qed.\n")


@pytest.mark.parametrize("target, block", [
    # The block ends at the target's own `qed.`; the following `equiv` is a
    # declaration, not more proof.
    ("lemma t : true.\n  proof. smt(). qed.\n", "proof. smt(). qed."),
    ("lemma t : true.\nproof.\n  smt().\nqed.\n", "proof.\n  smt().\nqed."),
    # Without `proof.`, the sentences through `qed.` are the target's proof.
    ("lemma t : true.\n  admit.\nqed.\n", "  admit.\nqed."),
    ("lemma t : true.\nadmit.\n", "admit."),
])
def test_proof_block_is_the_targets_own(target, block):
    source = target + "\nequiv e : M.f ~ M.f : true ==> true.\nproof.\n  proc; auto.\nqed.\n"

    start, end = prover_writeback._find_proof_block(source, "t")

    assert source[start:end] == block
