from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import core.easycrypt.ec_env as ec_env
import eval_suite.run as suite_run
import workflow.validation.run_report_bundle as run_report_bundle
from eval_suite.run import (
    _append_execution_record,
    _execution_record,
    _orchestrator_cmd,
    _preflight_eval_agent_confinement,
    _preflight_target_loads,
    _summary_paths,
    evaluation_artifact_inventory,
    file_identity,
)


def test_preflight_treats_proof_stripped_strict_shell_as_inconclusive(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "Target.ec"
    source.write_text("lemma target : true. proof. admit. qed.\n", encoding="utf-8")
    monkeypatch.setattr(ec_env, "get_ec_env", lambda: {})
    monkeypatch.setattr(
        suite_run.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=(
                "[error-1] Target.ec: line 1 (23-29)\n"
                "cannot prove goal (strict)\n"
            ),
        ),
    )

    ok, reason = _preflight_target_loads(
        ["runner", "--file", str(source)],
        allow_strict_proof_shell_failure=True,
    )

    assert ok is True
    assert reason.startswith("inconclusive")


def test_preflight_does_not_hide_non_shell_easycrypt_error(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "Target.ec"
    source.write_text("lemma target : true.\n", encoding="utf-8")
    monkeypatch.setattr(ec_env, "get_ec_env", lambda: {})
    monkeypatch.setattr(
        suite_run.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="[error-1] Target.ec: unknown identifier Missing\n",
        ),
    )

    ok, reason = _preflight_target_loads(
        ["runner", "--file", str(source)],
        allow_strict_proof_shell_failure=True,
    )

    assert ok is False
    assert "unknown identifier Missing" in reason


def test_confinement_preflight_uses_exact_target_and_negative_probe(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "Target.ec"
    source.write_text("lemma target : true.\n", encoding="utf-8")
    manifest = tmp_path / "source_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    observed = {}

    class FakeConfinement:
        def probe(self, *, agent_backend):
            observed["agent_backend"] = agent_backend
            return {"probe_status": "passed"}

    class FakeFactory:
        @classmethod
        def from_environment(cls, **kwargs):
            observed.update(kwargs)
            return FakeConfinement()

    monkeypatch.setattr(suite_run, "EvalAgentConfinement", FakeFactory)

    ok, reason = _preflight_eval_agent_confinement(
        [
            "runner", "--file", str(source), "--lemma", "target",
            "--include-dir", str(tmp_path),
        ],
        source_manifest=manifest,
        output_dir=tmp_path / "output",
        agent_backend="codex",
    )

    assert ok is True
    assert reason.endswith("passed")
    assert observed["source_file"] == str(source)
    assert observed["target_lemma"] == "target"
    assert observed["agent_backend"] == "codex"


def test_orchestrator_cmd_forwards_model_and_effort(tmp_path) -> None:
    source = tmp_path / "Target.ec"
    source.write_text("lemma target : true. proof. trivial. qed.\n", encoding="utf-8")

    cmd = _orchestrator_cmd(
        target={"id": "target", "file": str(source), "lemma": "target"},
        profile="l4_proof_state_compiler_v2_operation_binding_repair",
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
        profile="l4_proof_state_compiler_v2_operation_binding_repair",
        repeat=1,
        defaults={"output_dir": str(tmp_path / "runs")},
        suite_name="contract_test",
        isolate_source=False,
    )

    assert all("planner" not in part for part in cmd)


def test_orchestrator_cmd_forwards_agent_backend(tmp_path) -> None:
    source = tmp_path / "Target.ec"
    source.write_text("lemma target : true. proof. trivial. qed.\n", encoding="utf-8")

    cmd = _orchestrator_cmd(
        target={"id": "target", "file": str(source), "lemma": "target"},
        profile="l4_proof_state_compiler_v2_operation_binding_repair",
        repeat=1,
        defaults={
            "output_dir": str(tmp_path / "runs"),
            "agent_backend": "codex",
            "model": "gpt-5.6",
        },
        suite_name="contract_test",
        isolate_source=False,
    )

    assert cmd[cmd.index("--agent-backend") + 1] == "codex"
    assert cmd[cmd.index("--prover-model") + 1] == "gpt-5.6"


def test_suite_binds_current_call_by_new_summary_set_difference(tmp_path) -> None:
    output = tmp_path / "profile" / "target" / "r01"
    old = output / "old" / "summary.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}\n", encoding="utf-8")
    before = _summary_paths(output)

    new = output / "new" / "summary.json"
    new.parent.mkdir(parents=True)
    new.write_text("{}\n", encoding="utf-8")
    after = _summary_paths(output)

    assert after - before == frozenset({new})
    assert old not in after - before


def test_suite_execution_manifest_is_incremental_and_ordered(tmp_path) -> None:
    path = tmp_path / "executions" / "id" / "manifest.json"
    manifest = {"runs": [], "status": "running"}
    record = _execution_record(
        target={
            "id": "block",
            "file": "Target.ec",
            "lemma": "target",
        },
        profile="l1_goal_projection",
        repeat=1,
        output_dir=tmp_path / "runs",
        cmd=["python", "-m", "workflow.orchestrator"],
    )
    record["status"] = "completed_valid"

    _append_execution_record(path, manifest, record)

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["runs"][0]["ordinal"] == 1
    assert stored["runs"][0]["target_id"] == "block"
    assert stored["runs"][0]["status"] == "completed_valid"
    assert not path.with_suffix(".tmp").exists()


def test_suite_freezes_only_managed_evaluation_artifacts(tmp_path) -> None:
    run = tmp_path / "run"
    audit = run / "iteration_1" / "proof_node_manager_audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text('{"kind":"agent_intent.handled"}\n', encoding="utf-8")
    summary = run / "summary.json"
    summary.write_text("{}\n", encoding="utf-8")
    derived = run / "iteration_1" / "node_memory" / "Tree_0_0" / "thinking" / "1.md"
    derived.parent.mkdir(parents=True)
    derived.write_text("derived\n", encoding="utf-8")
    rollout = (
        run / "iteration_1" / "runtime_private" / "Tree_0_0"
        / "agent_state" / "codex_home" / "sessions" / "2026"
        / "rollout-thread.jsonl"
    )
    rollout.parent.mkdir(parents=True)
    rollout.write_text('{"type":"event_msg"}\n', encoding="utf-8")

    inventory = evaluation_artifact_inventory(run)

    assert inventory == [
        file_identity(audit, root=run),
        file_identity(rollout, root=run),
        file_identity(summary, root=run),
    ]
    assert all(item["size_bytes"] > 0 for item in inventory)
    assert all(len(item["sha256"]) == 64 for item in inventory)


def test_suite_main_writes_current_call_hash_bound_execution_manifest(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    suite_path = tmp_path / "suite.json"
    output_root = tmp_path / "artifacts"
    suite_path.write_text(json.dumps({
        "suite": "manifest_integration",
        "profiles": ["l1_goal_projection"],
        "defaults": {
            "eval_mode": True,
            "repeats": 1,
            "output_dir": str(output_root),
            "source_isolation": True,
            "strip_proofs": True,
        },
        "targets": [{
            "id": "target",
            "file": "Target.ec",
            "lemma": "target",
        }],
    }), encoding="utf-8")
    environment = {
        "commit": "a" * 9,
        "commit_full": "a" * 40,
        "branch": "test",
        "dirty": False,
    }
    monkeypatch.setattr(
        run_report_bundle,
        "capture_repository_environment",
        lambda: dict(environment),
    )

    def fake_cmd(**kwargs):
        output = suite_run._run_output_dir(
            target=kwargs["target"],
            profile=kwargs["profile"],
            repeat=kwargs["repeat"],
            defaults=kwargs["defaults"],
            suite_name=kwargs["suite_name"],
        )
        source = output / "source" / "Target.ec"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("lemma target : true. proof. admit. qed.\n", encoding="utf-8")
        (output / "source_manifest.json").write_text("{}\n", encoding="utf-8")
        return [
            "python", "-m", "workflow.orchestrator",
            "--file", str(source),
            "--lemma", "target",
            "--output-dir", str(output),
        ]

    class FakeProcess:
        def __init__(self, command, **_kwargs):
            output = Path(command[command.index("--output-dir") + 1])
            run = output / "run-current"
            run.mkdir(parents=True, exist_ok=True)
            (run / "summary.json").write_text(
                '{"final_proved":false}\n', encoding="utf-8"
            )
            (run / "config.json").write_text("{}\n", encoding="utf-8")

        def wait(self):
            return 0

    monkeypatch.setattr(suite_run, "_orchestrator_cmd", fake_cmd)
    monkeypatch.setattr(
        suite_run,
        "_preflight_target_loads",
        lambda _cmd, **_kwargs: (True, "ok"),
    )
    monkeypatch.setattr(
        suite_run,
        "_preflight_eval_agent_confinement",
        lambda *_args, **_kwargs: (True, "ok"),
    )
    monkeypatch.setattr(suite_run, "confinement_environment", lambda **kwargs: kwargs["base"])
    monkeypatch.setattr(suite_run.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(suite_run, "reap_worker_pgid_manifest", lambda _path: None)
    monkeypatch.setattr(
        suite_run,
        "collect_run_metrics",
        lambda _path: {"status": "valid", "validity": {"valid": True, "reasons": []}},
    )
    monkeypatch.setattr(suite_run, "render_markdown", lambda _rows: "ok\n")
    monkeypatch.setattr(
        suite_run,
        "_write_agent_view_bundle",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("deferred bundle must not be generated")
        ),
    )
    manifest_path = (
        output_root / "manifest_integration" / "executions" / "exact"
        / "manifest.json"
    )

    result = suite_run.main([
        "--suite", str(suite_path),
        "--execution-manifest-path", str(manifest_path),
        "--defer-bundles",
    ])

    assert result == 0
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["recorded_run_count"] == 1
    arm = manifest["runs"][0]
    assert arm["status"] == "completed_valid"
    assert arm["source_manifest"]["path"].endswith("source_manifest.json")
    assert {Path(item["path"]).name for item in arm["run_artifacts"]} == {
        "config.json", "summary.json",
    }


def test_suite_confinement_preflight_failure_launches_no_model(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    suite_path = tmp_path / "suite.json"
    output_root = tmp_path / "artifacts"
    suite_path.write_text(json.dumps({
        "suite": "confinement_fail_closed",
        "profiles": ["l1_goal_projection"],
        "defaults": {
            "eval_mode": True,
            "repeats": 1,
            "output_dir": str(output_root),
            "source_isolation": True,
            "strip_proofs": True,
        },
        "targets": [{
            "id": "target",
            "file": "Target.ec",
            "lemma": "target",
        }],
    }), encoding="utf-8")
    environment = {
        "commit": "a" * 9,
        "commit_full": "a" * 40,
        "branch": "test",
        "dirty": False,
    }
    monkeypatch.setattr(
        run_report_bundle,
        "capture_repository_environment",
        lambda: dict(environment),
    )

    def fake_cmd(**kwargs):
        output = suite_run._run_output_dir(
            target=kwargs["target"],
            profile=kwargs["profile"],
            repeat=kwargs["repeat"],
            defaults=kwargs["defaults"],
            suite_name=kwargs["suite_name"],
        )
        source = output / "source" / "Target.ec"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "lemma target : true. proof. admit. qed.\n",
            encoding="utf-8",
        )
        (output / "source_manifest.json").write_text("{}\n", encoding="utf-8")
        return [
            "python", "-m", "workflow.orchestrator",
            "--file", str(source), "--lemma", "target",
            "--output-dir", str(output),
        ]

    monkeypatch.setattr(suite_run, "_orchestrator_cmd", fake_cmd)
    monkeypatch.setattr(
        suite_run,
        "_preflight_target_loads",
        lambda _cmd, **_kwargs: (True, "ok"),
    )
    monkeypatch.setattr(
        suite_run,
        "_preflight_eval_agent_confinement",
        lambda *_args, **_kwargs: (False, "bubblewrap unavailable"),
    )
    monkeypatch.setattr(
        suite_run.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("model/orchestrator must not launch")
        ),
    )

    result = suite_run.main(["--suite", str(suite_path)])

    assert result == 2
    manifest_path = next(
        (output_root / "confinement_fail_closed" / "executions").glob(
            "*/manifest.json"
        )
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    arm = manifest["runs"][0]
    assert arm["status"] == "confinement_preflight_failed"
    assert arm["returncode"] is None
    assert arm["confinement_preflight"] == {
        "status": "failed",
        "reason": "bubblewrap unavailable",
    }
    metrics = json.loads(
        Path(arm["output_dir"], "eval_metrics.json").read_text(encoding="utf-8")
    )
    assert metrics["model_launched"] is False


def test_suite_preflight_only_writes_report_and_never_launches_model(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    suite_path = tmp_path / "suite.json"
    report_path = tmp_path / "preflight.json"
    suite_path.write_text(json.dumps({
        "suite": "no_model_gate",
        "profiles": ["l1_goal_projection"],
        "defaults": {
            "eval_mode": True,
            "repeats": 1,
            "output_dir": str(tmp_path / "artifacts"),
            "source_isolation": True,
            "strip_proofs": True,
        },
        "targets": [{
            "id": "target",
            "file": "Target.ec",
            "lemma": "target",
        }],
    }), encoding="utf-8")
    environment = {
        "commit": "b" * 9,
        "commit_full": "b" * 40,
        "branch": "test",
        "dirty": False,
    }
    monkeypatch.setattr(
        run_report_bundle,
        "capture_repository_environment",
        lambda: dict(environment),
    )

    def fake_cmd(**kwargs):
        output = suite_run._run_output_dir(
            target=kwargs["target"],
            profile=kwargs["profile"],
            repeat=kwargs["repeat"],
            defaults=kwargs["defaults"],
            suite_name=kwargs["suite_name"],
        )
        source = output / "source" / "Target.ec"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "lemma target : true. proof. admit. qed.\n",
            encoding="utf-8",
        )
        (output / "source_manifest.json").write_text("{}\n", encoding="utf-8")
        return [
            "python", "-m", "workflow.orchestrator",
            "--file", str(source), "--lemma", "target",
            "--output-dir", str(output),
        ]

    monkeypatch.setattr(suite_run, "_orchestrator_cmd", fake_cmd)
    monkeypatch.setattr(
        suite_run,
        "_preflight_target_loads",
        lambda _cmd, **_kwargs: (True, "loads OK"),
    )
    monkeypatch.setattr(
        suite_run,
        "_preflight_eval_agent_confinement",
        lambda *_args, **_kwargs: (True, "probe passed"),
    )
    monkeypatch.setattr(
        suite_run.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("model/orchestrator must not launch")
        ),
    )

    result = suite_run.main([
        "--suite", str(suite_path),
        "--preflight-only",
        "--preflight-output", str(report_path),
    ])

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["preflight_valid"] is True
    assert report["model_process_launched"] is False
    assert report["expected_record_count"] == report["recorded_count"] == 1
    assert report["records"][0]["status"] == "preflight_valid"
    assert not list((tmp_path / "artifacts" / "no_model_gate").glob(
        "executions/*/manifest.json"
    ))
