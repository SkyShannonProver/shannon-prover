"""``commit_chain`` reports the EasyCrypt error of the step that failed.

A rejected step is rolled back before the chain reads ``current.out``, so the
error is only in ``append_block``'s verdict. The chain used to report the
generic "tactic had no effect or was not committed" instead.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
from core.easycrypt.ec_env import get_ec_env  # noqa: E402

pytestmark = pytest.mark.easycrypt

SCLI = ROOT / "core" / "easycrypt" / "session_cli.py"
SAMPLE_EC = ROOT / "eval" / "examples" / "WhileSample.ec"

try:
    _MANAGED_EC_AVAILABLE = shutil.which(
        "easycrypt", path=get_ec_env().get("PATH")
    ) is not None
except RuntimeError:
    _MANAGED_EC_AVAILABLE = False


def _run(session: Path, args: list[str], env_extra: dict[str, str]) -> str:
    env = {**os.environ, **env_extra}
    completed = subprocess.run(
        [sys.executable, str(SCLI), "-d", str(session), *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    assert completed.returncode in (0, 1), completed.stderr[-500:]
    return completed.stdout


@pytest.mark.skipif(not _MANAGED_EC_AVAILABLE,
                    reason="repository-managed EasyCrypt is unavailable")
@pytest.mark.parametrize("env_extra", [{}, {"EC_DAEMON_DISABLE": "1"}],
                         ids=["daemon", "batch"])
def test_a_rejected_chain_step_reports_its_easycrypt_error(tmp_path, env_extra) -> None:
    session = tmp_path / "chain_session"
    _run(session, [
        "-start", "-f", str(SAMPLE_EC), "-I", str(SAMPLE_EC.parent),
        "-lemma", "Sample_lossless2",
    ], env_extra)

    out = _run(session, [
        "-tactic-exec", "commit_chain", "--keep-on-fail", "-c",
        "proc. seq 1 2 : (={ret}). apply (sample_ll _ _ _ _).",
    ], env_extra)
    execution = json.loads(out.split("[TACTIC-EXECUTION-RESULT]\n", 1)[1])["execution"]

    assert execution["accepted_count"] == 2
    assert execution["failed_tactic"] == "apply (sample_ll _ _ _ _)."
    assert execution["failure_reason"].startswith("[error]")
    assert "not committed" not in execution["failure_reason"]
