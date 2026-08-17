"""Run preregistered evaluation blocks in bounded parallel waves.

The atomic :mod:`eval_suite.run` process remains the sole owner of one target
block: it executes that block's profile arms sequentially and writes one child
manifest.  This scheduler only launches independent blocks concurrently,
waits at the preregistered wave barrier, and then merges child manifests into
the frozen suite order.  It never shares a mutable manifest between workers.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, TextIO

from eval_suite import run as atomic_run
from eval_suite.parallel_contract import (
    parallelization_record,
    select_parallel_waves,
)
from workflow.proc_lifecycle import (
    install_terminal_signal_handlers,
    terminate_subprocess_tree,
)
from workflow.validation.run_report_bundle import capture_repository_environment


@dataclass(frozen=True)
class BlockPlan:
    """One independently isolated target block inside a frozen wave."""

    wave_ordinal: int
    block_ordinal: int
    target: dict[str, Any]
    command: tuple[str, ...]
    result_path: Path
    stdout_path: Path
    stderr_path: Path


@dataclass
class ActiveBlock:
    """Process handles owned by the parent scheduler."""

    plan: BlockPlan
    process: subprocess.Popen[Any]
    stdout: TextIO
    stderr: TextIO


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument(
        "--profiles",
        default="",
        help="Comma-separated profile subset; normally use the frozen suite set.",
    )
    parser.add_argument(
        "--targets",
        default="",
        help="Comma-separated target-block subset for a bounded diagnostic run.",
    )
    parser.add_argument("--repeats", type=int, default=0)
    parser.add_argument("--timeout-minutes", type=int, default=0)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run the same waves through source/load/confinement gates only.",
    )
    parser.add_argument(
        "--preflight-output",
        type=Path,
        default=None,
        help="Required aggregate JSON path for --preflight-only.",
    )
    parser.add_argument(
        "--defer-bundles",
        action="store_true",
        help="Do not build tracked agent-view bundles after all blocks finish.",
    )
    args = parser.parse_args(argv)
    if args.preflight_only and args.preflight_output is None:
        parser.error("--preflight-only requires --preflight-output")
    if args.preflight_output is not None and not args.preflight_only:
        parser.error("--preflight-output is valid only with --preflight-only")
    if args.preflight_output is not None and args.preflight_output.exists():
        parser.error("--preflight-output must not already exist")

    install_terminal_signal_handlers()
    suite_path = args.suite.resolve()
    suite = atomic_run._read_suite(suite_path)
    defaults = dict(suite.get("defaults") or {})
    suite_name = str(suite.get("suite") or suite_path.stem)
    profiles = atomic_run._selected_profiles(
        args.profiles, list(suite.get("profiles") or [])
    )
    targets = atomic_run._selected_targets(
        args.targets, list(suite.get("targets") or [])
    )
    repeats = int(args.repeats or defaults.get("repeats") or 1)
    waves = select_parallel_waves(suite, targets)
    environment = capture_repository_environment()
    if environment.get("dirty") is not False:
        print(
            "PARALLEL-SUITE: requires a clean frozen worktree",
            file=sys.stderr,
        )
        return 2

    output_root = Path(defaults.get("output_dir") or "artifacts/eval_suite")
    lock_path = output_root / suite_name / ".parallel_blocks.lock"
    with _exclusive_suite_lock(lock_path):
        if args.preflight_only:
            assert args.preflight_output is not None
            aggregate_path = args.preflight_output.resolve()
            block_root = aggregate_path.parent / f"{aggregate_path.stem}_blocks"
            aggregate = _preflight_header(
                suite_path=suite_path,
                suite=suite,
                suite_name=suite_name,
                profiles=profiles,
                targets=targets,
                repeats=repeats,
                waves=waves,
                environment=environment,
            )
        else:
            aggregate_path = atomic_run._execution_manifest_path(
                defaults=defaults,
                suite_name=suite_name,
            )
            block_root = aggregate_path.parent / "blocks"
            aggregate = _execution_header(
                aggregate_path=aggregate_path,
                suite_path=suite_path,
                suite=suite,
                suite_name=suite_name,
                profiles=profiles,
                targets=targets,
                repeats=repeats,
                waves=waves,
                environment=environment,
            )
            atomic_run._write_execution_manifest(aggregate_path, aggregate)

        plans = _build_plans(
            suite_path=suite_path,
            profiles=profiles,
            repeats=repeats,
            timeout_minutes=args.timeout_minutes,
            waves=waves,
            block_root=block_root,
            preflight_only=args.preflight_only,
        )
        overall_rc, interrupted = _execute_waves(
            plans=plans,
            aggregate=aggregate,
            aggregate_path=aggregate_path,
            suite=suite,
            profiles=profiles,
            repeats=repeats,
            environment=environment,
            preflight_only=args.preflight_only,
        )

        repository_drifted = capture_repository_environment() != environment
        if repository_drifted:
            overall_rc = 2
            aggregate.setdefault("parallel_protocol_errors", []).append(
                "repository git identity changed during parallel execution"
            )

        if args.preflight_only:
            expected = len(targets) * len(profiles) * repeats
            records = list(aggregate.get("records") or [])
            valid = bool(
                overall_rc == 0
                and not interrupted
                and not repository_drifted
                and len(records) == expected
                and all(item.get("status") == "preflight_valid" for item in records)
                and not aggregate.get("parallel_protocol_errors")
            )
            aggregate.update({
                "recorded_count": len(records),
                "preflight_valid": valid,
                "model_process_launched": False,
                "repository_drifted": repository_drifted,
                "status": "completed" if valid else "invalid",
                "finished_at": atomic_run._utc_now(),
            })
            atomic_run._write_execution_manifest(aggregate_path, aggregate)
            print(f"PARALLEL-SUITE-NO-MODEL-PREFLIGHT: {aggregate_path}")
            return 0 if valid else 2

        records = list(aggregate.get("runs") or [])
        if any(item.get("status") != "completed_valid" for item in records):
            overall_rc = 2
        if aggregate.get("parallel_protocol_errors"):
            overall_rc = 2
        aggregate.update({
            "finished_at": atomic_run._utc_now(),
            "status": (
                "interrupted" if interrupted
                else "completed" if overall_rc == 0
                else "invalid"
            ),
            "overall_returncode": 130 if interrupted else overall_rc,
            "repository_drifted": repository_drifted,
            "recorded_run_count": len(records),
        })
        atomic_run._write_execution_manifest(aggregate_path, aggregate)
        if not repository_drifted and not interrupted and not args.defer_bundles:
            _build_deferred_bundles(
                records=records,
                targets=targets,
                defaults=defaults,
                environment=environment,
            )
        print(f"SUITE-EXECUTION-MANIFEST: {aggregate_path}")
        return 130 if interrupted else overall_rc


def _build_plans(
    *,
    suite_path: Path,
    profiles: list[str],
    repeats: int,
    timeout_minutes: int,
    waves: list[list[dict[str, Any]]],
    block_root: Path,
    preflight_only: bool,
) -> list[list[BlockPlan]]:
    result: list[list[BlockPlan]] = []
    block_ordinal = 0
    for wave_ordinal, wave in enumerate(waves, start=1):
        planned_wave: list[BlockPlan] = []
        for target in wave:
            block_ordinal += 1
            target_id = str(target.get("id") or "")
            child_root = block_root / f"{block_ordinal:03d}_{_slug(target_id)}"
            if preflight_only:
                result_path = child_root / "preflight.json"
            else:
                result_path = child_root / "manifest.json"
            command = [
                sys.executable,
                "-m",
                "eval_suite.run",
                "--suite",
                str(suite_path),
                "--targets",
                target_id,
                "--profiles",
                ",".join(profiles),
                "--repeats",
                str(repeats),
            ]
            if timeout_minutes:
                command.extend(["--timeout-minutes", str(timeout_minutes)])
            if preflight_only:
                command.extend([
                    "--preflight-only",
                    "--preflight-output",
                    str(result_path),
                ])
            else:
                command.extend([
                    "--execution-manifest-path",
                    str(result_path),
                    "--defer-bundles",
                ])
            planned_wave.append(BlockPlan(
                wave_ordinal=wave_ordinal,
                block_ordinal=block_ordinal,
                target=target,
                command=tuple(command),
                result_path=result_path,
                stdout_path=child_root / "stdout.log",
                stderr_path=child_root / "stderr.log",
            ))
        result.append(planned_wave)
    return result


def _execute_waves(
    *,
    plans: list[list[BlockPlan]],
    aggregate: dict[str, Any],
    aggregate_path: Path,
    suite: Mapping[str, Any],
    profiles: list[str],
    repeats: int,
    environment: Mapping[str, Any],
    preflight_only: bool,
) -> tuple[int, bool]:
    overall_rc = 0
    global_ordinal = 0
    for wave_index, planned_wave in enumerate(plans):
        if capture_repository_environment() != dict(environment):
            aggregate.setdefault("parallel_protocol_errors", []).append(
                f"repository drift before wave {planned_wave[0].wave_ordinal}"
            )
            for remaining_wave in plans[wave_index:]:
                for plan in remaining_wave:
                    records, global_ordinal = _missing_block_records(
                        plan=plan,
                        profiles=profiles,
                        repeats=repeats,
                        start_ordinal=global_ordinal,
                        status="repository_drift_before_wave",
                        reason="repository git identity changed",
                    )
                    _retain_records(
                        aggregate, records, preflight_only=preflight_only
                    )
            _write_progress(aggregate_path, aggregate)
            return 2, False

        active: list[ActiveBlock] = []
        interrupted = False
        launch_error = ""
        try:
            for plan in planned_wave:
                plan.result_path.parent.mkdir(parents=True, exist_ok=True)
                stdout = plan.stdout_path.open("w", encoding="utf-8")
                stderr = plan.stderr_path.open("w", encoding="utf-8")
                try:
                    process = subprocess.Popen(
                        list(plan.command),
                        cwd=Path.cwd(),
                        env=dict(os.environ),
                        stdout=stdout,
                        stderr=stderr,
                        start_new_session=True,
                    )
                except OSError:
                    stdout.close()
                    stderr.close()
                    raise
                active.append(ActiveBlock(plan, process, stdout, stderr))
            returncodes = [item.process.wait() for item in active]
        except KeyboardInterrupt:
            interrupted = True
            for item in active:
                terminate_subprocess_tree(item.process)
            returncodes = [
                item.process.poll() if item.process.poll() is not None else 130
                for item in active
            ]
        except OSError as exc:
            launch_error = f"{type(exc).__name__}: {exc}"
            for item in active:
                terminate_subprocess_tree(item.process)
            returncodes = [
                item.process.poll() if item.process.poll() is not None else 2
                for item in active
            ]
        finally:
            for item in active:
                item.stdout.close()
                item.stderr.close()

        by_ordinal = {
            item.plan.block_ordinal: (item, returncodes[index])
            for index, item in enumerate(active)
        }
        for plan in planned_wave:
            active_result = by_ordinal.get(plan.block_ordinal)
            if active_result is None:
                status = (
                    "parallel_parent_interrupted"
                    if interrupted
                    else "parallel_block_launch_failed"
                )
                reason = (
                    "parent scheduler interrupted before block launch"
                    if interrupted
                    else launch_error or "block process was not launched"
                )
                records, global_ordinal = _missing_block_records(
                    plan=plan,
                    profiles=profiles,
                    repeats=repeats,
                    start_ordinal=global_ordinal,
                    status=status,
                    reason=reason,
                )
                _retain_records(
                    aggregate, records, preflight_only=preflight_only
                )
                aggregate.setdefault("children", []).append({
                    "wave_ordinal": plan.wave_ordinal,
                    "block_ordinal": plan.block_ordinal,
                    "target_id": str(plan.target.get("id") or ""),
                    "process_returncode": None,
                    "result": {},
                    "stdout": _optional_file_identity(
                        plan.stdout_path, plan.result_path.parent
                    ),
                    "stderr": _optional_file_identity(
                        plan.stderr_path, plan.result_path.parent
                    ),
                })
                aggregate.setdefault("parallel_protocol_errors", []).append(
                    f"block {plan.target.get('id')} was not launched: {reason}"
                )
                overall_rc = 2
                _write_progress(aggregate_path, aggregate)
                continue
            item, returncode = active_result
            records, child_meta, errors, global_ordinal = _collect_block(
                plan=plan,
                profiles=profiles,
                repeats=repeats,
                start_ordinal=global_ordinal,
                suite=suite,
                environment=environment,
                process_returncode=returncode,
                preflight_only=preflight_only,
            )
            _retain_records(aggregate, records, preflight_only=preflight_only)
            aggregate.setdefault("children", []).append(child_meta)
            aggregate.setdefault("parallel_protocol_errors", []).extend(errors)
            if returncode != 0 or errors:
                overall_rc = 2
            if any(
                record.get("status")
                != ("preflight_valid" if preflight_only else "completed_valid")
                for record in records
            ):
                overall_rc = 2
            _write_progress(aggregate_path, aggregate)
        if interrupted:
            for remaining_wave in plans[wave_index + 1:]:
                for plan in remaining_wave:
                    records, global_ordinal = _missing_block_records(
                        plan=plan,
                        profiles=profiles,
                        repeats=repeats,
                        start_ordinal=global_ordinal,
                        status="parallel_parent_interrupted",
                        reason="parent scheduler interrupted before block launch",
                    )
                    _retain_records(
                        aggregate, records, preflight_only=preflight_only
                    )
            _write_progress(aggregate_path, aggregate)
            return 2, True
        if launch_error:
            for remaining_wave in plans[wave_index + 1:]:
                for plan in remaining_wave:
                    records, global_ordinal = _missing_block_records(
                        plan=plan,
                        profiles=profiles,
                        repeats=repeats,
                        start_ordinal=global_ordinal,
                        status="parallel_parent_launch_failed",
                        reason="an earlier wave could not launch completely",
                    )
                    _retain_records(
                        aggregate, records, preflight_only=preflight_only
                    )
            _write_progress(aggregate_path, aggregate)
            return 2, False
    return overall_rc, False


def _collect_block(
    *,
    plan: BlockPlan,
    profiles: list[str],
    repeats: int,
    start_ordinal: int,
    suite: Mapping[str, Any],
    environment: Mapping[str, Any],
    process_returncode: int,
    preflight_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], int]:
    target_id = str(plan.target.get("id") or "")
    expected_status = "preflight_valid" if preflight_only else "completed_valid"
    errors: list[str] = []
    payload: dict[str, Any] = {}
    if not plan.result_path.is_file():
        errors.append(f"block {target_id} produced no result artifact")
    else:
        try:
            payload = json.loads(plan.result_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"block {target_id} result is unreadable: {exc}")
    expected_top = {
        "suite": str(suite.get("suite") or ""),
        "selected_profiles": list(profiles),
        "selected_target_ids": [target_id],
    }
    suite_hash = hashlib.sha256(
        Path(plan.command[plan.command.index("--suite") + 1]).read_bytes()
    ).hexdigest()
    expected_top["suite_sha256"] = suite_hash
    for key, expected in expected_top.items():
        if payload.get(key) != expected:
            errors.append(
                f"block {target_id} {key} drifted: "
                f"expected {expected!r}, got {payload.get(key)!r}"
            )
    if payload.get("repository_environment") != dict(environment):
        errors.append(f"block {target_id} repository identity drifted")
    if int(payload.get("repeats") or repeats) != repeats:
        errors.append(f"block {target_id} repeat count drifted")
    if preflight_only:
        if payload.get("model_process_launched") is not False:
            errors.append(f"block {target_id} preflight launched a model")
        raw_records = payload.get("records")
    else:
        raw_records = payload.get("runs")
    raw_records = raw_records if isinstance(raw_records, list) else []
    positions = _block_positions(plan.target, profiles, repeats)
    by_position: dict[tuple[str, int], dict[str, Any]] = {}
    for record in raw_records:
        if not isinstance(record, Mapping):
            errors.append(f"block {target_id} contains a non-object record")
            continue
        key = (str(record.get("profile") or ""), int(record.get("repeat") or 0))
        if key in by_position:
            errors.append(f"block {target_id} duplicates position {key!r}")
            continue
        by_position[key] = dict(record)
    records: list[dict[str, Any]] = []
    ordinal = start_ordinal
    for profile, repeat in positions:
        ordinal += 1
        source = by_position.get((profile, repeat))
        if source is None:
            source = _missing_record(
                plan=plan,
                profile=profile,
                repeat=repeat,
                status=(
                    "parallel_preflight_block_incomplete"
                    if preflight_only
                    else "parallel_block_incomplete"
                ),
                reason=(
                    f"child process rc={process_returncode}; "
                    "expected position absent from child result"
                ),
            )
        child_ordinal = source.get("ordinal")
        source["child_ordinal"] = child_ordinal
        source["ordinal"] = ordinal
        source["parallel_wave_ordinal"] = plan.wave_ordinal
        source["parallel_block_ordinal"] = plan.block_ordinal
        records.append(source)
    extras = sorted(set(by_position) - set(positions))
    if extras:
        errors.append(f"block {target_id} contains unexpected positions: {extras!r}")
    if errors:
        for record in records:
            if record.get("status") == expected_status:
                record["child_status"] = record["status"]
                record["status"] = "parallel_block_protocol_error"
                record["reason"] = "; ".join(errors)
    child_meta = {
        "wave_ordinal": plan.wave_ordinal,
        "block_ordinal": plan.block_ordinal,
        "target_id": target_id,
        "process_returncode": process_returncode,
        "result": _optional_file_identity(plan.result_path, plan.result_path.parent),
        "stdout": _optional_file_identity(plan.stdout_path, plan.result_path.parent),
        "stderr": _optional_file_identity(plan.stderr_path, plan.result_path.parent),
    }
    return records, child_meta, errors, ordinal


def _block_positions(
    target: dict[str, Any], profiles: list[str], repeats: int
) -> list[tuple[str, int]]:
    return [
        (profile, repeat)
        for profile in atomic_run._target_profile_order(target, profiles)
        for repeat in range(1, repeats + 1)
    ]


def _missing_block_records(
    *,
    plan: BlockPlan,
    profiles: list[str],
    repeats: int,
    start_ordinal: int,
    status: str,
    reason: str,
) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    ordinal = start_ordinal
    for profile, repeat in _block_positions(plan.target, profiles, repeats):
        ordinal += 1
        record = _missing_record(
            plan=plan,
            profile=profile,
            repeat=repeat,
            status=status,
            reason=reason,
        )
        record["ordinal"] = ordinal
        record["parallel_wave_ordinal"] = plan.wave_ordinal
        record["parallel_block_ordinal"] = plan.block_ordinal
        records.append(record)
    return records, ordinal


def _missing_record(
    *,
    plan: BlockPlan,
    profile: str,
    repeat: int,
    status: str,
    reason: str,
) -> dict[str, Any]:
    target = plan.target
    return {
        "ordinal": None,
        "target_id": str(target.get("id") or ""),
        "source_file": str(target.get("file") or ""),
        "lemma": str(target.get("lemma") or ""),
        "profile": profile,
        "repeat": repeat,
        "command": [],
        "output_dir": "",
        "started_at": "",
        "finished_at": atomic_run._utc_now(),
        "status": status,
        "reason": reason,
        "returncode": None,
        "produced_summary_paths": [],
        "run_dir": "",
        "source_manifest": {},
        "run_artifacts": [],
    }


def _retain_records(
    aggregate: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    preflight_only: bool,
) -> None:
    aggregate.setdefault("records" if preflight_only else "runs", []).extend(records)


def _write_progress(path: Path, aggregate: dict[str, Any]) -> None:
    aggregate["last_progress_at"] = atomic_run._utc_now()
    atomic_run._write_execution_manifest(path, aggregate)


def _execution_header(
    *,
    aggregate_path: Path,
    suite_path: Path,
    suite: Mapping[str, Any],
    suite_name: str,
    profiles: list[str],
    targets: list[dict[str, Any]],
    repeats: int,
    waves: list[list[dict[str, Any]]],
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "kind": "eval_suite_execution_manifest",
        "execution_id": aggregate_path.parent.name,
        "suite": suite_name,
        "suite_file": str(suite_path),
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "repository_environment": dict(environment),
        "selected_profiles": list(profiles),
        "selected_target_ids": [str(item.get("id") or "") for item in targets],
        "repeats": repeats,
        "expected_run_count": len(targets) * len(profiles) * repeats,
        "started_at": atomic_run._utc_now(),
        "finished_at": "",
        "status": "running",
        "overall_returncode": None,
        "repository_drifted": False,
        "execution_mode": "target_block_waves",
        "parallelization": parallelization_record(suite, waves),
        "parallel_protocol_errors": [],
        "children": [],
        "runs": [],
    }


def _preflight_header(
    *,
    suite_path: Path,
    suite: Mapping[str, Any],
    suite_name: str,
    profiles: list[str],
    targets: list[dict[str, Any]],
    repeats: int,
    waves: list[list[dict[str, Any]]],
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "kind": "eval_suite_parallel_no_model_preflight",
        "suite": suite_name,
        "suite_file": str(suite_path),
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "repository_environment": dict(environment),
        "selected_profiles": list(profiles),
        "selected_target_ids": [str(item.get("id") or "") for item in targets],
        "repeats": repeats,
        "expected_record_count": len(targets) * len(profiles) * repeats,
        "started_at": atomic_run._utc_now(),
        "finished_at": "",
        "status": "running",
        "repository_drifted": False,
        "execution_mode": "target_block_waves",
        "parallelization": parallelization_record(suite, waves),
        "parallel_protocol_errors": [],
        "children": [],
        "records": [],
        "model_process_launched": False,
    }


def _build_deferred_bundles(
    *,
    records: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    defaults: dict[str, Any],
    environment: Mapping[str, Any],
) -> None:
    target_by_id = {str(item.get("id") or ""): item for item in targets}
    for record in records:
        run_dir = Path(str(record.get("run_dir") or ""))
        if not run_dir.is_dir() or record.get("returncode") != 0:
            continue
        target = target_by_id.get(str(record.get("target_id") or ""))
        if target is None:
            continue
        profile = str(record.get("profile") or "")
        output_dir = Path(str(record.get("output_dir") or ""))
        atomic_run._write_agent_view_bundle(
            run_dir=run_dir,
            target=target,
            profile=profile,
            defaults=defaults,
            bundle_key=(
                f"{target.get('id') or target.get('lemma') or 'target'}"
                f"__{profile}__{output_dir.name}"
            ),
            environment=dict(environment),
        )


def _optional_file_identity(path: Path, root: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return atomic_run.file_identity(path, root=root)


@contextmanager
def _exclusive_suite_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"another parallel suite owns {path}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _slug(value: str) -> str:
    result = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
    return result or "target"


if __name__ == "__main__":
    raise SystemExit(main())
