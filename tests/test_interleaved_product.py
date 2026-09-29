from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from workflow.interleaved.project import InterleavedProject, validate_project_files


ROOT = Path(__file__).resolve().parents[1]
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
