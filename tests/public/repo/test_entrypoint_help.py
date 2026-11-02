"""The entry points document only options that exist and do what they say."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import workflow.project_driver as project_driver

_ROOT = Path(__file__).resolve().parents[3]


def _help(module: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=_ROOT, capture_output=True, text=True, timeout=120, check=True,
    )
    return " ".join(result.stdout.split())


def test_project_driver_usage_example_uses_only_real_options():
    documented = set(re.findall(r"--[a-z][a-z-]+", project_driver.__doc__))
    accepted = set(re.findall(r"--[a-z][a-z-]+", _help("workflow.project_driver")))
    assert documented and documented <= accepted, documented - accepted


def test_orchestrator_help_does_not_promise_dead_options():
    text = _help("workflow.orchestrator")
    # Nothing reads human_proof_dir, and nothing in the repository passes it.
    assert "--human-proof-dir" not in text
    # Skills and eval_suite still pass --max-iterations, which drives nothing.
    assert "--max-iterations MAX_ITERATIONS Accepted for compatibility and ignored" in text
    assert "default: 2" not in text
