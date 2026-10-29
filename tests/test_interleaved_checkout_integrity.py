"""The final verdict must come from the checkout the run started with.

The outer agent can write the whole checkout, including the verifier, the
target's dependencies and the managed toolchain. Real runs leave only the
target file changed (every recorded `final_git_status` through 2026-09 is
empty or ` M <target>`), so any other change voids the verdict.
"""
from __future__ import annotations

import os
import stat
import subprocess

import pytest

from experiments.interleaved_shannon import run_experiment as runner
from experiments.interleaved_shannon import shannon_jobs as jobs


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "projects/p").mkdir(parents=True)
    (root / "projects/p/Target.ec").write_text("lemma t : true.\nproof. admit. qed.\n")
    (root / "projects/p/Dep.ec").write_text("op c : int.\n")
    (root / "projects/p/Answer.ec").write_text("(* answer *)\n")
    (root / "verify.py").write_text("print('ok')\n")
    (root / ".gitignore").write_text("artifacts/\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "start")
    start = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()
    fingerprint = {"receipt": "r", "why3_config": "w"}
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "ARTIFACT_ROOT", "artifacts/p-interleaved")
    monkeypatch.setattr(runner, "TARGET_REL", "projects/p/Target.ec")
    monkeypatch.setattr(runner, "toolchain_fingerprint", lambda: dict(fingerprint))

    def violations():
        return runner.checkout_integrity_violations(
            start_commit=start, start_toolchain={"receipt": "r", "why3_config": "w"},
        )

    return root, fingerprint, violations


def test_a_normal_run_changes_only_the_target_and_its_artifacts(checkout):
    root, _, violations = checkout
    (root / "projects/p/Target.ec").write_text("lemma t : true.\nproof. trivial. qed.\n")
    run_dir = root / "artifacts/p-interleaved/official_1"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}")
    assert violations() == []


def test_committing_the_target_is_still_a_normal_run(checkout):
    root, _, violations = checkout
    (root / "projects/p/Target.ec").write_text("lemma t : true.\nproof. trivial. qed.\n")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "proof")
    assert violations() == []


def test_an_edited_verifier_voids_the_verdict(checkout):
    root, _, violations = checkout
    (root / "verify.py").write_text("raise SystemExit(0)\n")
    assert violations() == ["modified verify.py"]


def test_a_committed_dependency_change_voids_the_verdict(checkout):
    root, _, violations = checkout
    (root / "projects/p/Dep.ec").write_text("op c : int = 0.\n")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "weaken")
    assert violations() == ["modified projects/p/Dep.ec"]


def test_a_new_source_file_voids_the_verdict(checkout):
    root, _, violations = checkout
    (root / "projects/p/Helper.ec").write_text("lemma h : false by admit.\n")
    assert violations() == ["added projects/p/Helper.ec"]


def test_a_changed_toolchain_voids_the_verdict(checkout):
    _, fingerprint, violations = checkout
    fingerprint["receipt"] = "rebuilt"
    assert violations() == ["managed EasyCrypt toolchain changed during the run"]


def test_files_hidden_by_sparse_checkout_are_not_reported(checkout):
    root, _, violations = checkout
    _git(root, "sparse-checkout", "init", "--no-cone")
    _git(root, "sparse-checkout", "set", "--no-cone", "/*", "!/projects/p/Answer.ec")
    assert not (root / "projects/p/Answer.ec").exists()
    assert violations() == []


# -- private runtime directory -------------------------------------------------


def test_lanes_and_locks_live_in_a_private_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_RUNTIME_PARENT", tmp_path)
    run_dir = tmp_path / "run"
    lane = jobs._lane_path(run_dir, "job1")
    root = tmp_path / f"interleaved-shannon-{os.getuid()}"
    assert lane.is_relative_to(root)
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    with jobs._registry_lock(run_dir):
        assert list(root.glob("jobs-*.lock"))


def test_a_shared_runtime_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "_RUNTIME_PARENT", tmp_path)
    root = tmp_path / f"interleaved-shannon-{os.getuid()}"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    with pytest.raises(RuntimeError, match="mode 0700"):
        jobs._private_runtime_root()


def test_a_runtime_directory_owned_by_someone_else_is_refused(tmp_path, monkeypatch):
    real_uid = os.getuid()
    monkeypatch.setattr(jobs, "_RUNTIME_PARENT", tmp_path)
    (tmp_path / f"interleaved-shannon-{real_uid + 1}").mkdir(mode=0o700)
    monkeypatch.setattr(os, "getuid", lambda: real_uid + 1)
    with pytest.raises(RuntimeError, match="owned by the current user"):
        jobs._private_runtime_root()
