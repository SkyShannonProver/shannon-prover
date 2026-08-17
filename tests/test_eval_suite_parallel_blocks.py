from __future__ import annotations

import hashlib
import json
from pathlib import Path

import eval_suite.parallel_blocks as parallel_blocks


PROFILES = [
    "l1_goal_projection",
    "l4_proof_state_compiler_v2_operation_binding_repair_audit",
    "l4_proof_state_compiler_v2_operation_binding_repair",
]


def _suite(tmp_path: Path) -> Path:
    targets = []
    orders = [
        PROFILES,
        [PROFILES[2], PROFILES[0], PROFILES[1]],
        [PROFILES[1], PROFILES[2], PROFILES[0]],
        PROFILES,
    ]
    for index, order in enumerate(orders, start=1):
        targets.append({
            "id": f"target_{index}",
            "file": f"Target{index}.ec",
            "lemma": f"target_{index}",
            "profile_order": order,
        })
    path = tmp_path / "suite.json"
    path.write_text(json.dumps({
        "suite": "parallel_contract_test",
        "profiles": PROFILES,
        "defaults": {
            "repeats": 1,
            "output_dir": str(tmp_path / "artifacts"),
        },
        "parallel_execution": {
            "mode": "target_block_waves",
            "within_block": "profile_order_sequential",
            "wave_barrier": True,
            "max_concurrent_blocks": 2,
            "waves": [
                ["target_1", "target_2"],
                ["target_3", "target_4"],
            ],
        },
        "targets": targets,
    }), encoding="utf-8")
    return path


class _FakeChildProcess:
    launches_by_wave: dict[int, list[str]] = {}
    launched_targets: list[str] = []
    incomplete_target = ""

    def __init__(self, command, **_kwargs):
        self.command = list(command)
        self.returncode = None
        self.target_id = self.command[self.command.index("--targets") + 1]
        suite_path = Path(self.command[self.command.index("--suite") + 1])
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        self.wave = next(
            index
            for index, wave in enumerate(
                suite["parallel_execution"]["waves"], start=1
            )
            if self.target_id in wave
        )
        self.launches_by_wave.setdefault(self.wave, []).append(self.target_id)
        self.launched_targets.append(self.target_id)
        target = next(item for item in suite["targets"] if item["id"] == self.target_id)
        profiles = self.command[self.command.index("--profiles") + 1].split(",")
        ordered = [item for item in target["profile_order"] if item in profiles]
        environment = {
            "commit": "a" * 9,
            "commit_full": "a" * 40,
            "branch": "test",
            "dirty": False,
        }
        records = []
        for ordinal, profile in enumerate(ordered, start=1):
            if self.target_id == self.incomplete_target and ordinal > 1:
                continue
            records.append({
                "ordinal": ordinal,
                "target_id": self.target_id,
                "source_file": target["file"],
                "lemma": target["lemma"],
                "profile": profile,
                "repeat": 1,
                "status": "completed_valid",
                "returncode": 0,
                "output_dir": "unused",
                "run_dir": "",
                "run_artifacts": [],
            })
        if "--preflight-only" in self.command:
            result_path = Path(
                self.command[self.command.index("--preflight-output") + 1]
            )
            payload = {
                "kind": "eval_suite_no_model_preflight",
                "suite": suite["suite"],
                "suite_file": str(suite_path),
                "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
                "repository_environment": environment,
                "selected_profiles": profiles,
                "selected_target_ids": [self.target_id],
                "expected_record_count": len(ordered),
                "recorded_count": len(records),
                "preflight_valid": self.target_id != self.incomplete_target,
                "model_process_launched": False,
                "repository_drifted": False,
                "records": [
                    {**record, "status": "preflight_valid"} for record in records
                ],
            }
        else:
            result_path = Path(
                self.command[
                    self.command.index("--execution-manifest-path") + 1
                ]
            )
            payload = {
                "schema_version": 1,
                "kind": "eval_suite_execution_manifest",
                "execution_id": result_path.parent.name,
                "suite": suite["suite"],
                "suite_file": str(suite_path),
                "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
                "repository_environment": environment,
                "selected_profiles": profiles,
                "selected_target_ids": [self.target_id],
                "repeats": 1,
                "expected_run_count": len(ordered),
                "status": (
                    "invalid" if self.target_id == self.incomplete_target
                    else "completed"
                ),
                "runs": records,
            }
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(payload), encoding="utf-8")

    def wait(self):
        # The scheduler must launch the whole wave before waiting on either
        # member, while never launching a later wave across the barrier.
        assert len(self.launches_by_wave[self.wave]) == 2
        assert all(wave <= self.wave for wave in self.launches_by_wave)
        self.returncode = 2 if self.target_id == self.incomplete_target else 0
        return self.returncode

    def poll(self):
        return self.returncode


def _install_fakes(monkeypatch) -> None:
    environment = {
        "commit": "a" * 9,
        "commit_full": "a" * 40,
        "branch": "test",
        "dirty": False,
    }
    _FakeChildProcess.launches_by_wave = {}
    _FakeChildProcess.launched_targets = []
    _FakeChildProcess.incomplete_target = ""
    monkeypatch.setattr(
        parallel_blocks,
        "capture_repository_environment",
        lambda: dict(environment),
    )
    monkeypatch.setattr(parallel_blocks.subprocess, "Popen", _FakeChildProcess)


def test_parallel_scheduler_keeps_arms_sequential_and_merges_frozen_order(
    monkeypatch,
    tmp_path,
) -> None:
    _install_fakes(monkeypatch)
    suite_path = _suite(tmp_path)

    result = parallel_blocks.main([
        "--suite", str(suite_path), "--defer-bundles",
    ])

    assert result == 0
    assert _FakeChildProcess.launched_targets == [
        "target_1", "target_2", "target_3", "target_4",
    ]
    manifest_path = next(
        (tmp_path / "artifacts" / "parallel_contract_test" / "executions").glob(
            "*/manifest.json"
        )
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["recorded_run_count"] == 12
    assert [item["ordinal"] for item in manifest["runs"]] == list(range(1, 13))
    assert [item["target_id"] for item in manifest["runs"]] == [
        "target_1", "target_1", "target_1",
        "target_2", "target_2", "target_2",
        "target_3", "target_3", "target_3",
        "target_4", "target_4", "target_4",
    ]
    assert [item["child_ordinal"] for item in manifest["runs"]] == [
        1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3,
    ]
    assert [item["parallel_wave_ordinal"] for item in manifest["runs"]] == [
        1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2,
    ]
    assert manifest["parallel_protocol_errors"] == []


def test_parallel_preflight_runs_same_waves_without_model(
    monkeypatch,
    tmp_path,
) -> None:
    _install_fakes(monkeypatch)
    suite_path = _suite(tmp_path)
    report = tmp_path / "tmp" / "parallel_preflight.json"

    result = parallel_blocks.main([
        "--suite", str(suite_path),
        "--preflight-only", "--preflight-output", str(report),
    ])

    assert result == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["preflight_valid"] is True
    assert payload["model_process_launched"] is False
    assert payload["recorded_count"] == payload["expected_record_count"] == 12
    assert all(item["status"] == "preflight_valid" for item in payload["records"])


def test_parallel_scheduler_retains_missing_arms_without_retry(
    monkeypatch,
    tmp_path,
) -> None:
    _install_fakes(monkeypatch)
    _FakeChildProcess.incomplete_target = "target_2"
    suite_path = _suite(tmp_path)

    result = parallel_blocks.main([
        "--suite", str(suite_path), "--defer-bundles",
    ])

    assert result == 2
    assert _FakeChildProcess.launched_targets.count("target_2") == 1
    assert _FakeChildProcess.launched_targets == [
        "target_1", "target_2", "target_3", "target_4",
    ]
    manifest_path = next(
        (tmp_path / "artifacts" / "parallel_contract_test" / "executions").glob(
            "*/manifest.json"
        )
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "invalid"
    assert manifest["recorded_run_count"] == 12
    target_2 = [
        item for item in manifest["runs"] if item["target_id"] == "target_2"
    ]
    assert [item["status"] for item in target_2] == [
        "completed_valid",
        "parallel_block_incomplete",
        "parallel_block_incomplete",
    ]
