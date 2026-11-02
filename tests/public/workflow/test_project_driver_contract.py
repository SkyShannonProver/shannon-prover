"""Behavior test for the driver→orchestrator invocation contract.

The old hand-assembled flag list drifted from the orchestrator's argparse
(the removed ``--skip-regression`` made every lemma "crash" at argparse exit 2
with zero run dirs). The contract is now a saved ``RunConfig`` passed via
``--config``; this test pins that the config the driver writes actually
round-trips through the schema with the values the run needs.
"""

from pathlib import Path

import workflow.project_driver as project_driver
from workflow.schemas.config import RunConfig


class _FakeProc:
    returncode = 0

    def wait(self, timeout=None):
        return 0


def test_run_one_lemma_invokes_orchestrator_via_config(tmp_path, monkeypatch):
    target = tmp_path / "toy.ec"
    target.write_text("lemma L: true.\nproof. admit. qed.\n", encoding="utf-8")

    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return _FakeProc()

    monkeypatch.setattr(project_driver.subprocess, "Popen", fake_popen)

    result = project_driver.run_one_lemma(
        file_path=target,
        lemma="L",
        include_dir="theories",
        time_cap_sec=600,
        output_dir=tmp_path / "out",
        eval_mode=True,
    )

    cmd = captured["cmd"]
    assert cmd[1:3] == ["-m", "workflow.orchestrator"]
    assert cmd[3] == "--config"
    # No stray flags: the RunConfig schema is the whole interface.
    assert len(cmd) == 5

    config = RunConfig.load(Path(cmd[4]))
    assert config.lemma == "L"
    assert config.file == str(target)
    assert config.include_dir == "theories"
    assert config.eval_mode is True
    assert config.max_iterations == 1
    assert config.prover.timeout_minutes == max(5, 600 // 60 - 2)
    assert config.output_dir.endswith("L.orchestrator_runs")

    # No orchestrator actually ran, so the typed-result read reports a crash;
    # the invocation contract above is the point of this test.
    assert result.name == "L"
    assert result.outcome == "crashed"
