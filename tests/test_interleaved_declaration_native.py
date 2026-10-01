"""Native forward/return compatibility for outer-authored declaration forms."""
import subprocess

import pytest

from core.easycrypt.ec_env import easycrypt_command, get_ec_env
from core.easycrypt.eval_source_prep import prepare_eval_source
from core.easycrypt.lemma_extract import extract_lemma
from experiments.interleaved_shannon import shannon_jobs as jobs
from workflow.interleaved.verify import verify_lemma_import


@pytest.mark.parametrize("head,claim,tactic", [
    ("local lemma", "true", "trivial."),
    ("local\nlemma", "true", "trivial."),
    ("local (* locality *)\nlemma", "true", "trivial."),
    ("equiv", "M.f ~ M.f : ={arg} ==> ={res}", "proc; auto."),
    ("hoare", "M.f : true ==> res = 0", "proc; auto."),
    ("phoare", "[M.f : true ==> res = 0] = 1%r", "proc; auto."),
])
def test_declared_helper_forward_preparation_and_native_import(tmp_path, head, claim, tactic):
    source = ("require import AllCore.\nmodule M = { proc f() : int = { return 0; } }.\n"
              f"{jobs.SCRATCHPAD_BEGIN}\ntheory Nested.\nsection LocalProof.\n"
              f"{head} Helper : {claim}.\nproof.\n{tactic}\nqed.\n"
              f"end section LocalProof.\nend Nested.\n{jobs.SCRATCHPAD_END}\n"
              "lemma conclusion : 1 = 1.\nproof. admit. qed.\n")
    candidate = tmp_path / "Input.ec"
    candidate.write_text(source)
    (tmp_path / "easycrypt.project").write_text(
        "[general]\nwhy3conf = /missing/interleaved-declaration-why3.conf\n"
    )
    jobs._require_outer_decomposition_boundary(source, "Helper")
    assert jobs._source_contract(source, "Helper")["proof_body_sha256"]
    prepared = prepare_eval_source(source_file=candidate, target_lemma="Helper",
                                   output_dir=tmp_path / "prepared")
    isolated_check = tmp_path / "Prepared.ec"
    isolated_check.write_text(extract_lemma(prepared.isolated_file, "Helper", verify_proof=True))
    native = subprocess.run(easycrypt_command("-no-eco", "-timeout", "10", str(isolated_check)),
                            cwd=tmp_path, env=get_ec_env(), capture_output=True,
                            text=True, timeout=45)
    assert native.returncode == 0, native.stderr
    result = verify_lemma_import(root=tmp_path, candidate=candidate, lemma="Helper",
                                target=tmp_path / "Canonical.ec", include_dirs=(),
                                check_dir=tmp_path / "collect")
    assert result["passed"] is True, result
    assert result["whole_project_verified"] is False
    assert candidate.read_text() == source
