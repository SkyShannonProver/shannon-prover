from __future__ import annotations

from eval_suite.run import _orchestrator_cmd


def test_orchestrator_cmd_forwards_model_and_effort(tmp_path) -> None:
    source = tmp_path / "Target.ec"
    source.write_text("lemma target : true. proof. trivial. qed.\n", encoding="utf-8")

    cmd = _orchestrator_cmd(
        target={"id": "target", "file": str(source), "lemma": "target"},
        profile="l4_checked_action_surface",
        repeat=1,
        defaults={
            "output_dir": str(tmp_path / "runs"),
            "model": "claude-opus-4-8",
            "effort": "high",
        },
        suite_name="contract_test",
        isolate_source=False,
    )

    assert cmd[cmd.index("--prover-model") + 1] == "claude-opus-4-8"
    assert cmd[cmd.index("--prover-effort") + 1] == "high"


def test_orchestrator_cmd_has_no_retired_planner_flag(tmp_path) -> None:
    source = tmp_path / "Target.ec"
    source.write_text("lemma target : true. proof. trivial. qed.\n", encoding="utf-8")

    cmd = _orchestrator_cmd(
        target={"id": "target", "file": str(source), "lemma": "target"},
        profile="l4_checked_action_surface",
        repeat=1,
        defaults={"output_dir": str(tmp_path / "runs")},
        suite_name="contract_test",
        isolate_source=False,
    )

    assert all("planner" not in part for part in cmd)
