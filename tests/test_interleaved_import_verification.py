"""Project verifier ownership and scoped import regressions; no model calls."""

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

import pytest

from workflow.interleaved.project import InterleavedProject, PROJECT_ENV
from workflow.interleaved import verify as verifier


ROOT = Path(__file__).resolve().parents[1]


def test_native_verifiers_use_managed_solver_config_over_project_config(tmp_path, monkeypatch):
    from core.easycrypt.ec_env import get_ec_env
    from experiments.interleaved_shannon import verify_task as reference
    import shutil

    target = tmp_path / "Target.ec"
    target.write_text("lemma L : true.\nproof. trivial. qed.\n")
    config = tmp_path / "easycrypt.project"
    config.write_text("[general]\nwhy3conf = /missing/project-why3.conf\n")
    before = (config.read_bytes(), config.stat().st_mtime_ns)
    environment = get_ec_env()
    executable = shutil.which("easycrypt", path=environment["PATH"])
    assert executable is not None

    imported = verifier.verify_lemma_import(
        root=tmp_path, candidate=target, lemma="L", target=target,
        include_dirs=(), check_dir=tmp_path / "check",
    )
    assert imported["passed"], imported

    project = InterleavedProject(target_file="Target.ec", final_lemma="L")
    monkeypatch.setattr(reference, "TARGET_REL", Path("Target.ec"))
    commands = [verifier._easycrypt_command(Path(executable), project)]
    commands.extend(reference.easycrypt_command(Path(executable), mode=mode)
                    for mode in ("preflight", "final", "check"))
    commands.append(reference.easycrypt_command(Path(executable), mode="upto", upto="1"))
    for command in commands:
        checked = subprocess.run(command, cwd=tmp_path, env=environment,
                                 capture_output=True, text=True, timeout=30)
        assert checked.returncode == 0, (command, checked.stdout, checked.stderr)
    assert (config.read_bytes(), config.stat().st_mtime_ns) == before


def test_scheduler_does_not_own_native_verification():
    source = (ROOT / "workflow/interleaved/jobs.py").read_text()
    tree = ast.parse(source)
    assert "_verify_collected_lemma" not in source
    assert "prover_writeback" not in source
    assert not any(isinstance(node, ast.Constant) and node.value == "easycrypt"
                   for node in ast.walk(tree))


def test_verifier_launch_preserves_current_project_binding(monkeypatch):
    monkeypatch.setenv(PROJECT_ENV, "current/project.json")
    monkeypatch.setenv("INTERLEAVED_RUN_DIR", "artifacts/locked-registry")
    # Native environment caching belongs below this Python process boundary.
    monkeypatch.setattr(verifier, "get_ec_env", lambda: {PROJECT_ENV: "old/project.json"})
    environment = verifier.import_verification_environment()
    assert environment[PROJECT_ENV] == "current/project.json"
    assert "INTERLEAVED_RUN_DIR" not in environment


def test_handback_selects_retained_open_capsule_after_failed_closure(tmp_path, monkeypatch):
    monkeypatch.setenv(PROJECT_ENV, "experiments/interleaved_shannon/project.json")
    from workflow.node import proof_node_resume as resume
    from workflow.interleaved.inner_runner import _terminal_progress
    from workflow.schemas.prover_result import ProverResult
    run = tmp_path / "run"
    session = tmp_path / ".ec_session_prover_synthetic_tree_0"
    session.mkdir()
    closed = False
    monkeypatch.setattr(resume, "read_session_goal_identity", lambda _p: SimpleNamespace(
        goal_identity_required=not closed, goal_hash="" if closed else "a" * 64,
        proof_status="session_closed_pending_verification" if closed else "open"))
    monkeypatch.setattr(resume, "_git_commit", lambda _p: "synthetic")
    monkeypatch.setattr(resume, "_manager_route_events_for_node", lambda *a: [])
    def mint(history):
        (session / "history.ec").write_text(history)
        return resume.create_resume_capsules(project_root=tmp_path, run_dir=run,
            target_file="Synthetic.ec", lemma="L", session_dirs=[session])
    mint("move=> x.\n")
    closed = True
    capsules = mint("move=> x.\ntrivial.\nqed.\n")
    result = ProverResult(status="infrastructure_invalid", error="finalization failed",
        resume_capsules=capsules, verification={"status": "fail", "reason": "native rejected candidate"})
    progress, checkpoint = _terminal_progress(result=result, result_path=run / "prover_run_result.json",
        output_root=tmp_path, lemma="L")
    assert progress["accepted_prefix"]["text"].strip() == "move=> x."
    assert progress["accepted_prefix"]["replay_required_before_use"] is True
    assert progress["verification"]["reason"] == "native rejected candidate"
    assert checkpoint


def test_configured_verifier_rejection_is_not_bypassed(tmp_path, monkeypatch):
    custom = tmp_path / "policy.py"
    custom.write_text(
        "import json, sys\n"
        "assert '--check-import' in sys.argv\n"
        "print(json.dumps({'passed': False, 'errors': ['CUSTOM_POLICY_REJECT']}))\n"
        "sys.exit(1)\n"
    )
    candidate = tmp_path / "candidate.ec"
    candidate.write_text("lemma L : true.\nproof. trivial. qed.\n")
    project = InterleavedProject(target_file="Target.ec", final_lemma="L", verifier="policy.py")
    monkeypatch.setenv("INTERLEAVED_RUN_DIR", "artifacts/should-not-reenter")
    result = verifier.check_import_with_project_verifier(
        root=tmp_path, project=project, candidate=candidate, lemma="L",
        output=tmp_path / "verification.json",
    )
    assert result["passed"] is False
    assert "CUSTOM_POLICY_REJECT" in result["error"]


@pytest.mark.parametrize("failure", ["empty", "old_whole_file", "wrong_candidate", "nonzero_exit"])
def test_import_rejects_stale_or_incompatible_verifier_response(tmp_path, monkeypatch, failure):
    candidate = tmp_path / "candidate.ec"
    candidate.write_text("lemma L : true.\nproof. trivial. qed.\n")
    output = tmp_path / "verification.json"
    payload = {
        "kind": "interleaved_lemma_import_verification", "schema_version": 1,
        "scope": verifier.IMPORT_SCOPE, "lemma": "L", "passed": True,
        "whole_project_verified": False,
        "merged_source_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
    }
    output.write_text(json.dumps(payload))  # A stale successful artifact must not rescue this call.
    if failure == "old_whole_file":
        payload = {"passed": True}
    elif failure == "wrong_candidate":
        payload["merged_source_sha256"] = "0" * 64
    response = "" if failure == "empty" else json.dumps(payload)
    monkeypatch.setattr(verifier.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(
        a, 2 if failure == "nonzero_exit" else 0, response, ""))
    result = verifier.check_import_with_project_verifier(
        root=tmp_path, project=InterleavedProject(target_file="Target.ec", final_lemma="L"),
        candidate=candidate, lemma="L", output=output,
    )
    assert result["passed"] is False
    assert json.loads(output.read_text())["passed"] is False


def test_generic_cli_import_ignores_unfinished_suffix_but_final_rejects(monkeypatch):
    (ROOT / "artifacts").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="import-contract-", dir=ROOT / "artifacts") as directory:
        scratch = Path(directory)
        target = scratch / "Target.ec"
        original = "lemma L : true.\nproof. admit. qed.\nlemma Final : true.\nproof.\ninvalid_suffix\n"
        target.write_text(original)
        candidate = scratch / "candidate.ec"
        candidate.write_text(original.replace("admit.", "trivial."))
        project = InterleavedProject(target_file=str(target.relative_to(ROOT)), final_lemma="Final")
        project_path = scratch / "project.json"
        project.write(project_path)
        monkeypatch.setenv(PROJECT_ENV, str(project_path.relative_to(ROOT)))
        result = verifier.check_import_with_project_verifier(
            root=ROOT, project=project, candidate=candidate, lemma="L",
            output=scratch / "verification.json",
        )
        assert result["passed"], result
        assert result["whole_project_verified"] is False
        assert target.read_text() == original
        code, final = verifier.verify("final")
        assert code != 0 and final["passed"] is False


@pytest.mark.parametrize("violation", [None, "statement", "sibling", "forbidden"])
def test_reference_import_retains_project_policy(tmp_path, monkeypatch, violation):
    from experiments.interleaved_shannon import verify_task as reference
    monkeypatch.setattr(reference, "ROOT", tmp_path)
    monkeypatch.setattr(reference, "TARGET_REL", Path("Target.ec"))
    monkeypatch.setattr(reference, "SIBLING_RELS", (Path("Sibling.ec"),))
    monkeypatch.setattr(reference, "ANSWER_SOURCE", tmp_path / "absent-answer.ec")
    monkeypatch.delenv("INTERLEAVED_RUN_DIR", raising=False)
    pinned = (reference.SCRATCH_BEGIN + "\n" + reference.SCRATCH_END
              + "\nlemma conclusion : true.\nproof.\nadmit.\nqed.\n")
    source = pinned.replace(reference.SCRATCH_END,
                            "lemma L : true.\nproof. trivial. qed.\n"
                            "lemma unfinished : true.\nproof.\nbad downstream syntax\n"
                            + reference.SCRATCH_END)
    if violation == "statement":
        source = source.replace("conclusion : true", "conclusion : false")
    elif violation == "forbidden":
        source = source.replace("trivial.", "axiom invented : true.")
    target = tmp_path / "Target.ec"
    target.write_text(pinned)
    (tmp_path / "Sibling.ec").write_text("changed" if violation == "sibling" else "sibling")
    candidate = tmp_path / "candidate.ec"
    candidate.write_text(source)
    monkeypatch.setattr(reference, "git_bytes", lambda path: pinned.encode() if path.name == "Target.ec" else b"sibling")
    monkeypatch.setattr(reference, "repository_change_errors", lambda mode: ([], {}))
    monkeypatch.setattr(reference, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="test-head"))
    monkeypatch.setattr(reference, "locked_easycrypt", lambda: (Path("easycrypt"), {}, {}))
    calls = []
    def native(**kwargs):
        calls.append(kwargs)
        return {"passed": True, "whole_project_verified": False}
    monkeypatch.setattr(verifier, "verify_lemma_import", native)
    report, passed = reference.verify("import", None, candidate=candidate, lemma="L")
    assert passed is (violation is None), report
    assert bool(calls) is (violation is None)
    assert target.read_text() == pinned
