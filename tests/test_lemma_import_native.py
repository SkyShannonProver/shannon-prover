"""Real EasyCrypt checks for the collect boundary; no agent/provider calls."""
from pathlib import Path

import pytest
from experiments.interleaved_shannon import shannon_jobs as jobs
from workflow.interleaved.verify import verify_lemma_import


def check_candidate(tmp_path, candidate, target):
    source = tmp_path / "candidate.ec"
    source.write_text(candidate)
    return verify_lemma_import(
        root=jobs.ROOT, candidate=source, lemma="L", target=target,
        include_dirs=("easycrypt-src/theories",), check_dir=tmp_path / "collect_check",
    )


@pytest.mark.parametrize("proof,passed", [("trivial.", True), ("invalid.", False),
                                         ("admit.", False), ("abort.", False)])
def test_native_import_ignores_broken_suffix_but_checks_target(tmp_path, proof, passed):
    original = "lemma L : true.\nproof.\nadmit.\nqed.\n"
    target = tmp_path / "Target.ec"
    target.write_text(original)
    candidate = original.replace("admit.", proof)
    candidate += "\nlemma unfinished : true.\nproof.\nthis is not EasyCrypt\n"
    payload = check_candidate(tmp_path, candidate, target)
    assert payload["passed"] is passed, payload
    assert payload["whole_project_verified"] is False
    assert target.read_text() == original


def test_collect_does_not_overwrite_concurrent_source_edit(tmp_path, monkeypatch):
    target = tmp_path / "target.ec"
    source = "lemma L : true.\nproof.\nadmit.\nqed.\n"
    target.write_text(source)
    run = tmp_path / "run"
    run.mkdir()
    job_id = "0000000000000001"
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "TARGET", "target.ec")
    monkeypatch.setattr(jobs, "run_directory", lambda: (Path("run"), run))
    jobs._save_job(run, {"schema_version": 1, "job_id": job_id, "status": "verified",
                         "lemma": "L", "source_contract": jobs._source_contract(source, "L")})
    (jobs._job_dir(run, job_id) / "proved_candidate.ec").write_text(source.replace("admit.", "trivial."))
    def check(**kw):
        target.write_text(source + "(* concurrent outer work *)\n")
        return {"passed": True}
    monkeypatch.setattr(jobs, "check_import_with_project_verifier", check)
    result = jobs.collect_job(job_id)
    assert result["status"] == "verified"
    assert result["collect_status"] == "source_changed_during_check"
    assert "concurrent outer work" in target.read_text()


@pytest.mark.parametrize("nesting", [
    ("theory T.\nsection Outer.\nsection Inner.\n", "end section Inner.\nend section Outer.\nend T.\n"),
    ("section Outer.\nsection Inner.\n", "end section Inner.\nend section Outer.\n"),
    ("theory Outer.\nsection S.\ntheory Inner.\n", "end Inner.\nend section S.\nend Outer.\n"),
    ("theory Outer.\n", "end Outer.\n"),
])
def test_native_import_closes_enclosing_blocks(tmp_path, nesting):
    opening, closing = nesting
    target = tmp_path / "Target.ec"
    source = opening + "lemma L : true.\nproof.\ntrivial.\nqed.\n" + closing
    target.write_text(source)
    from workflow.agents.prover_writeback import _verify_ec_file
    valid, error = _verify_ec_file(target)
    assert valid, error  # The original fixture itself must be native-valid.
    payload = check_candidate(tmp_path, source, target)
    assert payload["passed"], payload
