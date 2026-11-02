"""Single-lemma precheck: which declaration and which proof it judges.

The precheck decides whether `$prove` / `/prove` skips a lemma as already
verified, so it must read the target as EasyCrypt does: commented-out copies
and strings are not declarations, every proof-carrying declaration kind
counts, and only the target's own proof is examined.
"""
from __future__ import annotations

import pytest

from workflow.agents import prover
from workflow.schemas.config import ProverConfig
from workflow.schemas.prover_result import PROVER_RUN_INCOMPLETE


def _no_verification(*_args, **_kwargs):
    raise AssertionError("this target must not reach EasyCrypt verification")


def _verifies(monkeypatch):
    calls = []

    def _verify(path, **kwargs):
        calls.append((path, kwargs))
        return True, ""

    monkeypatch.setattr(prover, "_verify_ec_file", _verify)
    monkeypatch.setattr(prover, "_verify_lemma_extracted", _no_verification)
    return calls


def _precheck(tmp_path, source: str, lemma: str = "t") -> str:
    path = tmp_path / "T.ec"
    path.write_text("require import AllCore.\n" + source, encoding="utf-8")
    return prover._precheck_lemma(path, lemma)


def test_commented_out_copy_does_not_make_a_proved_lemma_a_target(
    tmp_path, monkeypatch,
):
    calls = _verifies(monkeypatch)
    source = (
        "(* previous attempt:\n"
        "lemma t : true.\n"
        "proof. admit. qed.\n"
        "*)\n"
        "lemma t : true.\n"
        "proof.\n"
        "  trivial.\n"
        "qed.\n"
    )
    assert _precheck(tmp_path, source) == "proved_and_verified"
    assert len(calls) == 1


def test_declaration_inside_a_string_is_not_a_declaration(tmp_path, monkeypatch):
    _verifies(monkeypatch)
    source = (
        'op note = "lemma t : false. proof. admit. qed.".\n'
        "lemma t : true.\n"
        "proof.\n"
        "  trivial.\n"
        "qed.\n"
    )
    assert _precheck(tmp_path, source) == "proved_and_verified"


@pytest.mark.parametrize("keyword", ["equiv", "hoare", "phoare", "theorem"])
def test_every_proof_declaration_kind_is_found(tmp_path, monkeypatch, keyword):
    _verifies(monkeypatch)
    source = f"{keyword} t : true.\nproof.\n  trivial.\nqed.\n"
    assert _precheck(tmp_path, source) == "proved_and_verified"


def test_missing_declaration_or_file_is_not_found(tmp_path, monkeypatch):
    _verifies(monkeypatch)
    assert _precheck(tmp_path, "(* lemma t : true. *)\n") == "not_found"
    assert prover._precheck_lemma(tmp_path / "Missing.ec", "t") == "not_found"


def test_extracted_fallback_is_pinned_to_the_uncommented_declaration(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(prover, "_verify_ec_file", lambda *a, **k: (False, "[critical] x"))
    seen = {}

    def _extracted(path, lemma, **kwargs):
        seen.update(kwargs)
        return True, ""

    monkeypatch.setattr(prover, "_verify_lemma_extracted", _extracted)
    source = (
        "(*\n"
        "lemma t : true.\n"
        "*)\n"
        "lemma t : true.\n"
        "proof.\n"
        "  trivial.\n"
        "qed.\n"
    )
    assert _precheck(tmp_path, source) == "proved_and_verified"
    # 0-based line 4 of the written file (after the `require` line).
    assert seen["decl_line"] == 4


@pytest.mark.parametrize("source", [
    # Without `proof.`, the admitted body comes before the next lemma's
    # clean proof; that proof is not the target's.
    "lemma t : false.\n  admit.\nqed.\n\nlemma u : true.\nproof.\n  trivial.\nqed.\n",
    # The target never reaches its own `qed.`; extracting it leaves a proof
    # open at the end of the file, which EasyCrypt accepts.
    "lemma t : false.\n  trivial.\n\nlemma u : true.\nproof.\n  trivial.\nqed.\n",
    "lemma t : false.\nproof.\n  trivial.\n\nlemma u : true.\nproof. trivial. qed.\n",
    "lemma t : false by admit.\n\nlemma u : true.\nproof.\n  trivial.\nqed.\n",
    "lemma t : true.\nproof.\n  (* nothing yet *)\nqed.\n",
])
def test_only_the_targets_own_proof_is_judged(tmp_path, monkeypatch, source):
    monkeypatch.setattr(prover, "_verify_ec_file", _no_verification)
    monkeypatch.setattr(prover, "_verify_lemma_extracted", _no_verification)
    assert _precheck(tmp_path, source) == "has_admit"


def test_one_sentence_by_proof_is_the_targets_proof(tmp_path, monkeypatch):
    _verifies(monkeypatch)
    source = (
        "lemma t : true by trivial.\n\n"
        "lemma u : true.\nproof.\n  admit.\nqed.\n"
    )
    assert _precheck(tmp_path, source) == "proved_and_verified"


def _stub_run_boundary(monkeypatch, tmp_path):
    monkeypatch.setattr(prover, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(prover, "_ensure_why3server", lambda **_k: "")
    monkeypatch.setattr(prover, "_prepare_managed_session", _no_verification)
    monkeypatch.setattr("workflow.tree.supervisor.run_tree_prover", _no_verification)
    # run() binds the process to its own sockets (and eval target); setenv
    # makes monkeypatch restore the prior values afterwards.
    for name in ("WHY3EC_SOCKET", "EC_DAEMON_SOCKET", "EVAL_TARGET_LEMMA"):
        monkeypatch.setenv(name, "")
    from workflow.provider import provider_sessions

    monkeypatch.setattr(
        provider_sessions, "provider_cli_identity",
        lambda backend: {"agent_backend": backend, "binary": "stub",
                         "resolved_path": "stub", "version": "stub 0.0"},
    )


@pytest.mark.parametrize("source, expected", [
    ("(* lemma t : true. *)\nlemma other : true.\nproof. trivial. qed.\n",
     "t is not declared in projects/T.ec"),
    (None, "projects/T.ec is not a file"),
])
def test_run_stops_when_the_target_is_not_found(
    tmp_path, monkeypatch, source, expected,
):
    _stub_run_boundary(monkeypatch, tmp_path)
    if source is not None:
        target = tmp_path / "projects" / "T.ec"
        target.parent.mkdir()
        target.write_text(source, encoding="utf-8")

    result = prover.run(
        file_path="projects/T.ec",
        lemma_name="t",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path / "run",
    )

    assert result.status == PROVER_RUN_INCOMPLETE
    assert expected in result.error
    assert "no proof search was started" in result.error


# -- failing proofs and the verification environment --------------------------

import os  # noqa: E402

from workflow.schemas.prover_result import (  # noqa: E402
    PROVER_RUN_INFRASTRUCTURE_INVALID,
    PROVER_RUN_VERIFIED,
)
from workflow.tree.result import TreeRunResult  # noqa: E402

_PROVED = "require import AllCore.\nlemma t : true.\nproof.\n  smt().\nqed.\n"


@pytest.mark.parametrize("stderr, expected", [
    ("[critical] [T.ec: line 4 (2-8)] cannot prove goal (strict)", "has_proof_but_fails"),
    ("[error-3-0] [T.ec: line 4] cannot prove goal (strict)", "has_proof_but_fails"),
    ("[critical] cannot start & connect to why3server: Unix.Unix_error", "verification_unavailable"),
    ("Command '['easycrypt']' timed out after 600 seconds", "verification_unavailable"),
    ("[Errno 2] No such file or directory: 'easycrypt'", "verification_unavailable"),
    ("decl_line 3 does not declare 't' in T.ec", "verification_unavailable"),
])
def test_only_an_easycrypt_rejection_makes_a_failing_proof(
    tmp_path, monkeypatch, stderr, expected,
):
    monkeypatch.setattr(prover, "_verify_ec_file", lambda *a, **k: (False, stderr))
    monkeypatch.setattr(prover, "_verify_lemma_extracted", lambda *a, **k: (False, stderr))
    path = tmp_path / "T.ec"
    path.write_text(_PROVED, encoding="utf-8")
    assert prover._precheck_lemma(path, "t") == expected


def _run_target(monkeypatch, tmp_path, *, verdict: str, events: list):
    _stub_run_boundary(monkeypatch, tmp_path)
    target = tmp_path / "projects" / "T.ec"
    target.parent.mkdir()
    target.write_text(_PROVED, encoding="utf-8")

    def _ensure(**_kwargs):
        events.append(("ensure", os.environ.get("WHY3EC_SOCKET")))
        return os.environ.get("WHY3EC_SOCKET")

    def _verify(*_args, **_kwargs):
        events.append(("verify", os.environ.get("WHY3EC_SOCKET")))
        return verdict == "pass", verdict

    monkeypatch.setattr(prover, "_ensure_why3server", _ensure)
    monkeypatch.setattr(prover, "_verify_ec_file", _verify)
    monkeypatch.setattr(prover, "_verify_lemma_extracted", _verify)
    monkeypatch.setattr(
        prover, "_shutdown_run_why3server", lambda: events.append(("shutdown", None)),
    )
    return target


def test_precheck_runs_after_the_runs_why3server_is_ready(tmp_path, monkeypatch):
    events: list = []
    _run_target(monkeypatch, tmp_path, verdict="pass", events=events)

    result = prover.run(
        file_path="projects/T.ec",
        lemma_name="t",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path / "run",
    )

    assert result.status == PROVER_RUN_VERIFIED and result.skipped
    names = [name for name, _socket in events]
    assert names == ["ensure", "verify", "shutdown"]
    run_socket = events[0][1]
    assert run_socket and events[1][1] == run_socket


def test_run_without_a_verdict_stops_and_leaves_the_source(tmp_path, monkeypatch):
    events: list = []
    target = _run_target(
        monkeypatch, tmp_path,
        verdict="[critical] cannot start & connect to why3server",
        events=events,
    )

    result = prover.run(
        file_path="projects/T.ec",
        lemma_name="t",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path / "run",
    )

    assert result.status == PROVER_RUN_INFRASTRUCTURE_INVALID
    assert "Could not check the existing proof of t" in result.error
    assert target.read_text(encoding="utf-8") == _PROVED
    assert events[-1] == ("shutdown", None)


def test_run_proves_a_failing_proof_again_without_rewriting_it(tmp_path, monkeypatch):
    events: list = []
    target = _run_target(
        monkeypatch, tmp_path,
        verdict="[critical] [T.ec: line 4 (2-8)] cannot prove goal (strict)",
        events=events,
    )
    monkeypatch.setattr(prover, "_prepare_managed_session", lambda **_k: {})
    monkeypatch.setattr(prover, "_extract_tactics_from_candidate", lambda *a, **k: [])
    searched = []

    def _tree(*, build_cmd_fn, payload_audit_path=None, **_kwargs):
        searched.append(target.read_text(encoding="utf-8"))
        build_cmd_fn("prover_tree_0_0", "0.0", [])
        return TreeRunResult(
            returncode=0, selected_node_id="0.0",
            payload_audit_path=str(payload_audit_path or ""),
        )

    monkeypatch.setattr("workflow.tree.supervisor.run_tree_prover", _tree)

    result = prover.run(
        file_path="projects/T.ec",
        lemma_name="t",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path / "run",
    )

    assert not result.is_verified
    # The search ran on, and the run ended with, the user's own text.
    assert searched == [_PROVED]
    assert target.read_text(encoding="utf-8") == _PROVED


def test_eval_mode_refuses_a_failing_proof_it_cannot_hide(tmp_path, monkeypatch):
    events: list = []
    target = _run_target(
        monkeypatch, tmp_path,
        verdict="[critical] [T.ec: line 4 (2-8)] cannot prove goal (strict)",
        events=events,
    )
    result = prover.run(
        file_path="projects/T.ec",
        lemma_name="t",
        prover=ProverConfig(model="test-model", timeout_minutes=1),
        run_dir=tmp_path / "run",
        eval_mode=True,
    )

    assert result.status == PROVER_RUN_INCOMPLETE
    assert "eval mode must not show it to the agent" in result.error
    assert target.read_text(encoding="utf-8") == _PROVED
    assert events[-1] == ("shutdown", None)
