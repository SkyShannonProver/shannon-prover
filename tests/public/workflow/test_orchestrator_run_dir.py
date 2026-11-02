"""Each orchestrator run owns its run directory.

The run's EasyCrypt daemon and why3server sockets are derived from the run
directory, so two runs of one lemma started in the same minute must not
share it: the second run's pre-run cleanup would stop the first run's
daemon.
"""
from __future__ import annotations

from datetime import datetime

from workflow import orchestrator
from workflow.agents import ec_services
from workflow.schemas.config import RunConfig
from workflow.schemas.prover_result import PROVER_RUN_INCOMPLETE, ProverResult


class _FixedMinute(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 28, 21, 33, 5)


def test_two_runs_in_one_minute_get_their_own_directories_and_sockets(
    tmp_path, monkeypatch,
):
    source = tmp_path / "projects" / "T.ec"
    source.parent.mkdir()
    source.write_text("lemma t : true.\nproof. admit. qed.\n", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(orchestrator, "datetime", _FixedMinute)
    monkeypatch.setattr(orchestrator, "_prevent_sleep_on_macos", lambda: None)
    monkeypatch.setattr(
        "core.easycrypt.ec_env.check_ec_available", lambda: (True, "stub"),
    )
    monkeypatch.setenv("SHANNON_SUITE_WILL_BUNDLE", "1")
    for name in ("WHY3EC_SOCKET", "EC_DAEMON_SOCKET", "EVAL_TARGET_LEMMA"):
        monkeypatch.setenv(name, "")
    prover_dirs = []

    def _run_prover(config, iter_dir):
        prover_dirs.append(iter_dir)
        result = ProverResult(status=PROVER_RUN_INCOMPLETE)
        result.save(iter_dir / "prover_run_result.json")
        return result

    monkeypatch.setattr(orchestrator, "run_prover", _run_prover)

    for _ in range(2):
        summary = orchestrator.run(RunConfig(
            file="projects/T.ec", lemma="t", output_dir="runs",
        ))
        assert summary["final_prover_result_status"] == PROVER_RUN_INCOMPLETE

    first, second = (path.parent for path in prover_dirs)
    assert first != second
    assert first.name == "2026-10-28_2133_t"
    assert second.name == "2026-10-28_2133_t_2"
    assert (first / "summary.json").is_file() and (second / "summary.json").is_file()
    sockets = [
        (ec_services._configure_run_ec_daemon_socket(path),
         ec_services._configure_run_why3_socket(path))
        for path in prover_dirs
    ]
    assert sockets[0][0] != sockets[1][0]
    assert sockets[0][1] != sockets[1][1]
