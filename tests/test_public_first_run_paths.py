"""Paths a new user takes first must work in the public tree.

Each case reproduces a failure found by the public audit of v0.3.0
(2026-10-28): the suite example in eval_suite/README.md crashed with
KeyError 'id', a single-lemma run left an untracked `agent_view_runs/` that
made project-level runs refuse the checkout, and a missing research package
raised ModuleNotFoundError instead of reporting an unknown profile.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from workflow.proof_state_compiler import profile_registry
from workflow.reporting.run_report_bundle import _ensure_bundle_root


ROOT = Path(__file__).resolve().parents[1]


def test_eval_suite_readme_example_dry_runs(tmp_path):
    readme = (ROOT / "eval_suite/README.md").read_text(encoding="utf-8")
    example = re.search(r"## Suite JSON\n\n```json\n(.*?)```", readme, re.S).group(1)
    suite = json.loads(example)
    assert all(target.get("id") for target in suite["targets"])
    path = tmp_path / "suite.json"
    path.write_text(example, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "eval_suite.run", "--suite", str(path), "--dry-run"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "--lemma PIR_correct" in result.stdout


def _git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True,
    ).stdout


def test_a_new_bundle_root_stays_out_of_git_status(tmp_path):
    _git(tmp_path, "init", "-q")
    root = tmp_path / "agent_view_runs"

    _ensure_bundle_root(root)
    (root / "PIR_correct" / "run").mkdir(parents=True)
    (root / "PIR_correct" / "run" / "run_meta.json").write_text("{}")
    (root / "INDEX.md").write_text("runs\n")

    assert _git(tmp_path, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_an_existing_bundle_root_is_left_as_it_is(tmp_path):
    root = tmp_path / "agent_view_runs"
    root.mkdir()
    (root / "curated").mkdir()

    _ensure_bundle_root(root)

    assert not (root / ".gitignore").exists()


class _AbsentPackage:
    """Make a package unimportable as it is in the public tree.

    A None entry in sys.modules would report the submodule as missing; a
    public clone lacks the package directory, so the package itself is.
    """

    def __init__(self, name):
        self.name = name

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.name:
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


def test_a_missing_research_package_is_an_unknown_profile(monkeypatch):
    package = profile_registry._RESEARCH_PACKAGE
    for name in [n for n in sys.modules if n == package or n.startswith(package + ".")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "meta_path", [_AbsentPackage(package), *sys.meta_path])

    assert dict(profile_registry._research_profile_registrations()) == {}
    with pytest.raises(ValueError, match="not a registered"):
        profile_registry.runtime_profile_registration(
            "l4_proof_state_compiler_v2_compound_operation_binding_audit"
        )
    assert profile_registry.runtime_profile_registration(
        "proof_state_compiler"
    ).profile_id == "proof_state_compiler"
