"""Regression tests: proofs that EasyCrypt accepts without checking a goal.

EasyCrypt r2026.06 compiles every "proof" of `false` in ``FALSE_PROOFS`` with
exit status 0. A verdict that reports a lemma proved must reject each of them.
Before this suite the shared guard matched only a literal `admit.`, so all
but `by admit.` passed the single-lemma write-back and the project-level
final check (public audit of v0.3.0, 2026-10-28).
"""
from __future__ import annotations

import subprocess
import types

import pytest

from core.easycrypt.commands import validation_commands
from core.easycrypt.ec_env import easycrypt_command, get_ec_env
from core.easycrypt.proof_text import (
    discard_sibling_eco,
    file_wide_unchecked_constructs,
    tactics_contain_admit,
    unchecked_proof_constructs,
)
from workflow.agents import prover, prover_writeback
from workflow.agents.prover_writeback import (
    _proof_body_has_admit,
    _write_and_verify_proof,
)
from workflow.schemas.config import ProverConfig
from workflow.schemas.prover_result import PROVER_RUN_INCOMPLETE


FALSE_PROOFS = {
    "admit_then_tactic": "lemma f : false.\nproof. admit; trivial. qed.\n",
    "parenthesized_admit": "lemma f : false.\nproof. by (admit). qed.\n",
    "try_admit": "lemma f : false.\nproof. try admit; done. qed.\n",
    "by_admit": "lemma f : false by admit.\n",
    "admitted_proof_end": "lemma f : false.\nproof. admitted.\n",
    "weak_pragma": "pragma Proofs:weak.\nlemma f : false.\nproof. smt(). qed.\n",
    "report_pragma": "pragma Proofs : report.\nlemma f : false.\nproof. smt(). qed.\n",
    # Found by an independent review of the first fix: a comment separates
    # tokens, `(*)` is an operator rather than a comment, a string may hold
    # "(*", and `exit`, `abort` and `pragma reset` end or replace a proof.
    "comment_glued_admit": "lemma f : false.\nproof. by(* x *)admit. qed.\n",
    "comment_glued_pragma": "pragma(* x *)Proofs:weak.\nlemma f : false.\nproof. smt(). qed.\n",
    "operator_star": "lemma f : false.\nproof. have h : (*) 1 1 = 1 by trivial. admit. qed.\n",
    "operator_star_space": "lemma f : false.\nproof. have h : (* ) 2 2 = 4 by trivial. admit. qed.\n",
    "string_opener": 'lemma f : false.\nproof. idtac "(*". admit. qed.\n',
    "commented_qed": "lemma f : false.\nproof. (* qed. *) admit. qed.\n",
    "exit_in_proof": "lemma f : false.\nproof. exit. qed.\n",
    "exit_before": "exit.\nlemma f : false.\nproof. smt(). qed.\n",
    "abort_then_restate": "lemma f : false.\nproof. abort. lemma f : true. proof. trivial. qed.\n",
    "reset_then_restate": (
        "lemma f : false.\nproof. pragma reset. require import AllCore.\n"
        "lemma f : true. proof. trivial. qed.\n"
    ),
}


def _compile(tmp_path, body: str) -> subprocess.CompletedProcess[str]:
    source = tmp_path / "Probe.ec"
    source.write_text("require import AllCore.\n" + body, encoding="utf-8")
    return subprocess.run(
        easycrypt_command("compile", "-no-eco", str(source)),
        env=get_ec_env(), cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )


@pytest.mark.parametrize("name", sorted(FALSE_PROOFS))
def test_easycrypt_accepts_each_unchecked_false_proof(tmp_path, name):
    result = _compile(tmp_path, FALSE_PROOFS[name])
    assert result.returncode == 0, result.stdout + result.stderr


def test_easycrypt_rejects_the_checked_control(tmp_path):
    result = _compile(tmp_path, "lemma f : false.\nproof. smt(). qed.\n")
    assert result.returncode != 0


@pytest.mark.parametrize("name", sorted(FALSE_PROOFS))
def test_guard_flags_each_unchecked_false_proof(name):
    assert unchecked_proof_constructs(FALSE_PROOFS[name])


@pytest.mark.parametrize("tactic", [
    "admit; trivial.", "by (admit).", "try admit; done.", "[admit].",
    "do admit.", "admit.", "admitted.", "pragma Proofs:weak.",
    "by(*x*)admit(*y*).", "exit.", "abort.", "pragma reset.",
    '(have h : (*) 1 1 = 1 by trivial); by (admit).',
    'idtac "(*"; by (admit).',
])
def test_tactic_guard_flags_unchecked_tactics(tactic):
    assert tactics_contain_admit(["move=> x.", tactic])


@pytest.mark.parametrize("text", [
    "proof. trivial. qed.",
    "proof. (* admit; trivial. *) trivial. qed.",
    "proof. (* outer (* admit. *) still comment *) trivial. qed.",
    "proof. apply admit_lemma. apply x_admit. apply admit'. apply readmit. qed.",
    "proof. apply Admit.foo. qed.",
    "pragma Proofs:check.\nlemma t : true.\nproof. smt(). qed.",
    "pragma +implicits.",
    'proof. idtac "admit". trivial. qed.',
    "proof. have h : (*) 1 1 = 1 by trivial. trivial. qed.",
    "proof. apply exit_lemma. apply aborted. qed.",
])
def test_guard_ignores_comments_identifiers_and_checking_pragmas(text):
    assert unchecked_proof_constructs(text) == []
    assert not tactics_contain_admit([text])


def test_file_wide_helper_returns_only_constructs_that_affect_later_proofs():
    text = (
        "pragma Proofs:weak.\nlemma f : false.\nproof. admit. qed.\n"
        "lemma g : false.\nproof. abort.\nexit.\n"
    )
    assert sorted(unchecked_proof_constructs(text)) == [
        "abort", "admit", "exit", "pragma Proofs:weak",
    ]
    assert sorted(file_wide_unchecked_constructs(text)) == ["exit", "pragma Proofs:weak"]


# -- single-lemma precheck ----------------------------------------------------

def _no_verification(*_args, **_kwargs):
    raise AssertionError("an unchecked proof must not reach EasyCrypt verification")


@pytest.mark.parametrize("source, expected", [
    ("lemma t : false.\nproof. admit; trivial. qed.\n", "has_admit"),
    ("lemma t : false.\nproof. admitted.\n", "has_admit"),
    ("lemma t : true.\nproof. trivial.\n", "has_admit"),
    ("lemma t : false.\nproof. (* qed. *) admit. qed.\n", "has_admit"),
    ("lemma t : false.\nproof. exit. qed.\n", "unchecked_source"),
    ("exit.\nlemma t : false.\nproof. smt(). qed.\n", "unchecked_source"),
    ("pragma Proofs:weak.\nlemma t : false.\nproof. smt(). qed.\n", "unchecked_source"),
    ("lemma t : false.\nproof. abort. lemma t : true. proof. trivial. qed.\n", "has_admit"),
])
def test_precheck_never_treats_an_unchecked_proof_as_verified(
    tmp_path, monkeypatch, source, expected,
):
    monkeypatch.setattr(prover, "_verify_ec_file", _no_verification)
    monkeypatch.setattr(prover, "_verify_lemma_extracted", _no_verification)
    path = tmp_path / "T.ec"
    path.write_text("require import AllCore.\n" + source, encoding="utf-8")
    assert prover._precheck_lemma(path, "t") == expected


def test_run_stops_on_a_source_that_weakens_proof_checking(tmp_path, monkeypatch):
    target = tmp_path / "projects" / "T.ec"
    target.parent.mkdir()
    target.write_text(
        "pragma Proofs:report.\nlemma t : false.\nproof. smt(). qed.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(prover, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(prover, "_ensure_why3server", lambda: "")
    monkeypatch.setattr(prover, "_prepare_managed_session", _no_verification)
    from workflow.provider import provider_sessions

    monkeypatch.setattr(
        provider_sessions, "provider_cli_identity",
        lambda backend: {"agent_backend": backend, "binary": "stub",
                         "resolved_path": "stub", "version": "stub 0.0"},
    )

    result = prover.run(
        file_path="projects/T.ec",
        lemma_name="t",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path / "run",
    )

    assert result.status == PROVER_RUN_INCOMPLETE
    assert not result.is_verified
    assert "pragma Proofs:report" in result.error


# -- single-lemma write-back -------------------------------------------------

@pytest.mark.parametrize("body", [
    "admit; trivial.", "by (admit).", "try admit; done.", "admitted.",
])
def test_writeback_body_check_flags_unchecked_bodies(body):
    content = f"lemma t : false.\nproof.\n  {body}\nqed.\n"
    assert _proof_body_has_admit(content, "t") is True


def test_writeback_body_check_accepts_a_real_proof():
    content = "lemma t : true.\nproof.\n  trivial. (* not admit *)\nqed.\n"
    assert _proof_body_has_admit(content, "t") is False


def test_writeback_refuses_a_file_that_weakens_proof_checking(tmp_path, monkeypatch):
    original = (
        "pragma Proofs:weak.\n"
        "lemma t : false.\n"
        "proof.\n"
        "  admit.\n"
        "qed.\n"
    )
    path = tmp_path / "T.ec"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(prover_writeback, "_verify_ec_file", lambda *a, **k: (True, ""))
    candidate = types.SimpleNamespace(
        target_file=str(path.resolve()), target_lemma="t",
        session_dir=str(tmp_path / ".ec_session"), candidate_id="test-candidate",
    )

    evidence = _write_and_verify_proof(path, "t", ["smt()."], candidate)

    assert not evidence.passed
    assert evidence.error == "source disables strict proof checking"
    assert path.read_text(encoding="utf-8") == original


# -- session_cli -verify ------------------------------------------------------

class _Session:
    def __init__(self, root, history: str):
        self.dir = root
        self.history = root / "history.ec"
        self.history.write_text(history, encoding="utf-8")
        self._include_dirs = []
        self.events = []

    def emit_event(self, name, payload):
        self.events.append((name, payload))


def _verify(tmp_path, monkeypatch, *, history="", extracted, run=None):
    source = tmp_path / "T.ec"
    source.write_text(extracted, encoding="utf-8")
    import core.easycrypt.ec_env as ec_env
    import core.easycrypt.lemma_extract as lemma_extract
    import core.easycrypt.session.session_common as session_common

    monkeypatch.setattr(lemma_extract, "extract_lemma", lambda *a, **k: extracted)
    monkeypatch.setattr(session_common, "get_ec_env", lambda: {})
    monkeypatch.setattr(ec_env, "easycrypt_command", lambda *a, **k: ["easycrypt", *a])
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if run is None:
            raise AssertionError("an unchecked proof must not reach EasyCrypt")
        return run(command, **kwargs)

    monkeypatch.setattr(validation_commands.subprocess, "run", fake_run)
    session = _Session(tmp_path, history)
    args = types.SimpleNamespace(file=str(source), verify_lemma="t")
    return validation_commands.handle_verify_lemma(session, args), session, calls


def test_verify_rejects_an_admit_in_the_session_proof(tmp_path, monkeypatch):
    code, session, _ = _verify(
        tmp_path, monkeypatch,
        history="admit; trivial.\nqed.\n", extracted="lemma t : false.\nproof.\n",
    )
    assert code == 1
    assert session.events[-1][1]["reason"] == "unchecked_proof"


def test_verify_rejects_a_proof_left_open(tmp_path, monkeypatch):
    code, session, _ = _verify(
        tmp_path, monkeypatch, extracted="lemma t : true.\nproof. trivial.\n",
    )
    assert code == 1
    assert session.events[-1][1]["reason"] == "proof_not_closed"


def test_verify_fails_when_easycrypt_exits_nonzero_without_an_error_line(
    tmp_path, monkeypatch,
):
    code, session, calls = _verify(
        tmp_path, monkeypatch, extracted="lemma t : true.\nproof. trivial. qed.\n",
        run=lambda command, **kwargs: subprocess.CompletedProcess(command, -9),
    )
    assert code == 1
    assert session.events[-1][1]["returncode"] == -9
    assert calls[0][:2] == ["easycrypt", "compile"]


def test_verify_fails_on_timeout(tmp_path, monkeypatch):
    def hang(command, **kwargs):
        assert kwargs["timeout"] == validation_commands._VERIFY_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    code, session, _ = _verify(
        tmp_path, monkeypatch, extracted="lemma t : true.\nproof. trivial. qed.\n",
        run=hang,
    )
    assert code == 1
    assert session.events[-1][1]["reason"] == "timeout"


def test_verify_passes_a_closed_checked_proof(tmp_path, monkeypatch):
    code, session, _ = _verify(
        tmp_path, monkeypatch, extracted="lemma t : true.\nproof. trivial. qed.\n",
        run=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )
    assert code == 0
    assert session.events[-1][1]["status"] == "pass"


@pytest.mark.parametrize("tactics", [
    ["abort.", "lemma t : true.", "trivial."],
    ["exit."],
    ['idtac "(*"; by (admit).'],
])
def test_writeback_rejects_tactics_that_end_or_skip_the_proof(tmp_path, monkeypatch, tactics):
    original = "lemma t : false.\nproof.\n  admit.\nqed.\n"
    path = tmp_path / "T.ec"
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(prover_writeback, "_verify_ec_file", lambda *a, **k: (True, ""))
    candidate = types.SimpleNamespace(
        target_file=str(path.resolve()), target_lemma="t",
        session_dir=str(tmp_path / ".ec_session"), candidate_id="test-candidate",
    )

    evidence = _write_and_verify_proof(path, "t", tactics, candidate)

    assert not evidence.passed
    assert path.read_text(encoding="utf-8") == original


def test_verification_discards_a_forged_eco_before_compiling(tmp_path, monkeypatch):
    source = tmp_path / "T.ec"
    source.write_text("lemma t : true.\nproof. trivial. qed.\n", encoding="utf-8")
    forged = tmp_path / "T.eco"
    forged.write_text("forged", encoding="utf-8")
    seen = []

    def fake_run(command, **kwargs):
        seen.append(forged.exists())
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(prover_writeback.subprocess, "run", fake_run)
    monkeypatch.setattr(prover_writeback, "_get_opam_env", lambda: {})
    import core.easycrypt.ec_proc as ec_proc

    monkeypatch.setattr(ec_proc, "why3_socket_from_env", lambda: None)

    ok, _ = prover_writeback._verify_ec_file(source)

    assert ok and seen == [False]


def test_discard_sibling_eco_tolerates_a_missing_cache(tmp_path):
    discard_sibling_eco(tmp_path / "Absent.ec")


def test_verify_passes_a_one_line_by_proof(tmp_path, monkeypatch):
    code, session, _ = _verify(
        tmp_path, monkeypatch, extracted="lemma t : true by trivial.\n",
        run=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )
    assert code == 0, session.events


def test_verify_rejects_tactics_after_the_statement_left_open(tmp_path, monkeypatch):
    code, session, _ = _verify(
        tmp_path, monkeypatch, extracted="lemma t : true.\nby trivial.\n",
    )
    assert code == 1
    assert session.events[-1][1]["reason"] == "proof_not_closed"


def test_verify_rejects_exit_in_the_extract(tmp_path, monkeypatch):
    code, session, _ = _verify(
        tmp_path, monkeypatch, extracted="exit.\nlemma t : false.\nproof. smt(). qed.\n",
    )
    assert code == 1
    assert session.events[-1][1]["reason"] == "unchecked_proof"


def test_verify_fails_when_the_target_is_missing_from_the_extract(tmp_path, monkeypatch):
    code, session, _ = _verify(
        tmp_path, monkeypatch, extracted="lemma other : true.\nproof. trivial. qed.\n",
    )
    assert code == 1
    assert session.events[-1][1]["reason"] == "target_not_found"


def test_verify_discards_a_forged_eco_next_to_its_scratch_file(tmp_path, monkeypatch):
    forged = tmp_path / "verify_tmp.eco"
    forged.write_text("forged", encoding="utf-8")
    seen = []

    def run(command, **kwargs):
        seen.append(forged.exists())
        return subprocess.CompletedProcess(command, 0)

    code, _, _ = _verify(
        tmp_path, monkeypatch, extracted="lemma t : true.\nproof. trivial. qed.\n", run=run,
    )
    assert code == 0 and seen == [False]
