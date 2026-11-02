from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from workflow.interleaved.project import (
    InterleavedProject,
    PROJECT_ENV,
    validate_project_files,
)
from workflow.interleaved.runtime import ANSWER_SOURCE_ENV, ProjectContext


ROOT = Path(__file__).resolve().parents[3]
PRODUCT = ROOT / "workflow" / "interleaved"
REFERENCE = ROOT / "experiments" / "interleaved_shannon"


def test_product_package_never_imports_experiments() -> None:
    for path in PRODUCT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not str(node.module or "").startswith("experiments")
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith("experiments") for alias in node.names)


def test_reference_adapter_is_a_product_project() -> None:
    project = InterleavedProject.load(REFERENCE / "project.json")
    assert project.target_file == "experiments/interleaved_shannon/task/chacha_poly.ec"
    assert project.final_lemma == "conclusion"
    assert project.artifact_root == "artifacts/interleaved_shannon"
    assert project.warm_handoff_sentinel_lemma == "nth_extend"
    assert validate_project_files(ROOT, project) == []


def test_project_contract_rejects_escaping_paths() -> None:
    with pytest.raises(ValueError, match="repository-relative"):
        InterleavedProject(target_file="../answer.ec", final_lemma="L")


def test_product_contract_round_trip(tmp_path: Path) -> None:
    project = InterleavedProject(
        target_file="projects/demo/Target.ec",
        final_lemma="Final",
        include_dirs=("easycrypt-src/theories", "projects/demo"),
        artifact_root="artifacts/demo-interleaved",
    )
    path = tmp_path / "project.json"
    project.write(path)
    loaded = InterleavedProject.load(path)
    assert loaded == project
    assert loaded.identity_sha256 == project.identity_sha256
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_session_receives_the_library_include_not_the_target_directory() -> None:
    project = InterleavedProject(
        target_file="projects/demo/Target.ec",
        final_lemma="Final",
        include_dirs=("projects/demo", "easycrypt-src/theories"),
    )
    assert project.session_include_dir == "easycrypt-src/theories"
    only_target = InterleavedProject(
        target_file="projects/demo/Target.ec",
        final_lemma="Final",
        include_dirs=("projects/demo",),
    )
    assert only_target.session_include_dir == ""


def test_project_rejects_include_dirs_a_session_cannot_receive() -> None:
    with pytest.raises(ValueError, match="at most one directory"):
        InterleavedProject(
            target_file="projects/demo/Target.ec",
            final_lemma="Final",
            include_dirs=("easycrypt-src/theories", "lib/common", "projects/demo"),
        )


def test_lane_checks_out_include_dirs_but_never_answer_examples(tmp_path: Path) -> None:
    project = InterleavedProject(
        target_file="projects/demo/Target.ec",
        final_lemma="Final",
        include_dirs=("lib/common", "projects/demo"),
    )
    plain = ProjectContext(
        root=tmp_path, project_path=tmp_path / "p.json", project=project,
        answer_source=None,
    )
    assert "/lib/common/" in plain.confined_patterns
    assert "/projects/demo/" in plain.confined_patterns

    confined = ProjectContext(
        root=tmp_path, project_path=tmp_path / "p.json",
        project=InterleavedProject(
            target_file="projects/demo/Target.ec",
            final_lemma="Final",
            include_dirs=("easycrypt-src/examples/shared",),
        ),
        answer_source=tmp_path / "easycrypt-src" / "examples" / "A" / "a.ec",
    )
    assert "/easycrypt-src/examples/shared/" in confined.confined_patterns
    assert confined.confined_patterns[-1] == "!/easycrypt-src/examples/"


def test_product_modules_import_without_a_project_binding() -> None:
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {PROJECT_ENV, ANSWER_SOURCE_ENV}
    }
    modules = ", ".join(
        f"workflow.interleaved.{name}"
        for name in (
            "runner", "jobs", "inner_runner", "warm_handoff",
            "warm_handoff_sentinel", "verify",
        )
    )
    imported = subprocess.run(
        [sys.executable, "-c", f"import {modules}"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=120,
    )
    assert imported.returncode == 0, imported.stderr


def test_child_environment_rebinds_the_same_project(tmp_path: Path) -> None:
    contract = tmp_path / "projects" / "demo" / "interleaved_project.json"
    InterleavedProject(
        target_file="projects/demo/Target.ec",
        final_lemma="Final",
        artifact_root="artifacts/demo-interleaved",
    ).write(contract)
    context = ProjectContext.load(
        "projects/demo/interleaved_project.json",
        answer_source="easycrypt-src/examples/A/a.ec",
        root=tmp_path,
    )
    environment = context.child_environment({ANSWER_SOURCE_ENV: "stale", "KEEP": "1"})
    assert environment == {
        PROJECT_ENV: "projects/demo/interleaved_project.json",
        ANSWER_SOURCE_ENV: "easycrypt-src/examples/A/a.ec",
        "KEEP": "1",
    }
    assert ProjectContext.from_environment(environment, root=tmp_path) == context

    unconfined = ProjectContext.load(
        "projects/demo/interleaved_project.json", root=tmp_path,
    )
    assert ANSWER_SOURCE_ENV not in unconfined.child_environment(environment)
    with pytest.raises(RuntimeError, match="is required"):
        ProjectContext.from_environment({}, root=tmp_path)
    with pytest.raises(RuntimeError, match="repository-relative"):
        ProjectContext.load("../project.json", root=tmp_path)


def test_lane_checkout_contains_the_project_contract(tmp_path: Path) -> None:
    """A lane must hold the contract its inner runner loads.

    The reference contract lives outside its task directory, so checking out
    only the target and include directories would leave it behind.
    """

    def git(*arguments: str, cwd: Path) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
             "-c", "commit.gpgsign=false", *arguments],
            cwd=cwd, check=True, capture_output=True, text=True,
        )

    repository = tmp_path / "repository"
    for relative, text in {
        "workflow/interleaved/x.py": "",
        "adapter/project.json": "{}",
        "adapter/task/Target.ec": "lemma Final : true.\n",
        "adapter/unrelated.txt": "",
        "lib/common/Lib.ec": "",
    }.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git("init", "-q", cwd=repository)
    git("add", "-A", cwd=repository)
    git("commit", "-q", "-m", "start", cwd=repository)
    context = ProjectContext(
        root=repository,
        project_path=repository / "adapter" / "project.json",
        project=InterleavedProject(
            target_file="adapter/task/Target.ec",
            final_lemma="Final",
            include_dirs=("lib/common",),
        ),
        answer_source=None,
    )
    lane = tmp_path / "lane"
    git("worktree", "add", "--detach", str(lane), "HEAD", cwd=repository)
    git("sparse-checkout", "init", "--no-cone", cwd=lane)
    git("sparse-checkout", "set", "--no-cone", *context.confined_patterns, cwd=lane)

    assert (lane / "adapter" / "project.json").is_file()
    assert (lane / "adapter" / "task" / "Target.ec").is_file()
    assert (lane / "lib" / "common" / "Lib.ec").is_file()
    assert not (lane / "adapter" / "unrelated.txt").exists()
