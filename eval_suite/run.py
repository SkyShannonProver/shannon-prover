"""Run ShannonProver paper-eval suites.

Suites are JSON files that describe a small target/profile matrix.  The runner
expands each row into an ordinary ``workflow.orchestrator`` invocation so the
proof workflow, event logs, and validation artifacts remain comparable.
Current suites use only profile names registered by
``workflow.proof_state_compiler.surface_profiles``.  Retired protocol JSON is
provenance-only and is rejected by this runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.easycrypt.eval_source_prep import prepare_eval_source
from eval_suite.metrics import collect_run_metrics, render_markdown
from workflow.proc_lifecycle import (
    WORKER_PGID_MANIFEST_ENV,
    install_terminal_signal_handlers,
    reap_worker_pgid_manifest,
    terminate_subprocess_tree,
)
from workflow.eval_agent_confinement import (
    EvalAgentConfinement,
    EvalAgentConfinementError,
    clear_confinement_environment,
    confinement_environment,
)
from workflow.schemas.config import PROVER_DEFAULTS
from workflow.proof_state_compiler.surface_profiles import (
    ensure_current_surface_profile,
)


def _cmd_flag(cmd: list[str], name: str) -> str | None:
    """Return the value following ``name`` in an argv-style command list."""
    try:
        return cmd[cmd.index(name) + 1]
    except (ValueError, IndexError):
        return None


def _preflight_target_loads(
    cmd: list[str],
    *,
    timeout: int = 240,
    allow_strict_proof_shell_failure: bool = False,
) -> tuple[bool, str]:
    """Compile-check that the target file LOADS before the prover launches.

    A file that fails to load (e.g. a `require` of a theory absent from this
    EasyCrypt env) never opens the target lemma. Without this guard the
    orchestrator still spawns a session, the agent submits tactics into a REPL
    with no open proof, EC answers every one with
    ``cannot process [proof script] outside a proof script``, and the run burns
    its whole budget as a silent *hollow run* that looks like a normal failure.

    Returns ``(ok, reason)``. On any inconclusive condition (timeout, easycrypt
    missing) it returns ``ok=True`` so preflight never blocks a legitimately
    slow-but-loadable target — the runtime bootstrap guard is the backstop.
    """
    ec_file = _cmd_flag(cmd, "--file")
    include_dir = _cmd_flag(cmd, "--include-dir")
    if not ec_file or not Path(ec_file).is_file():
        return False, f"target file not found: {ec_file}"
    include_dirs = [str(Path(ec_file).parent)]
    if include_dir and include_dir not in include_dirs:
        include_dirs.append(include_dir)
    ec_cmd = ["easycrypt"]
    for d in include_dirs:
        ec_cmd += ["-I", d]
    ec_cmd.append(ec_file)
    try:
        from core.easycrypt.ec_env import get_ec_env
        proc = subprocess.run(
            ec_cmd, capture_output=True, text=True,
            timeout=timeout, env=get_ec_env(),
        )
    except subprocess.TimeoutExpired:
        return True, f"inconclusive (compile exceeded {timeout}s) — proceeding"
    except FileNotFoundError:
        return True, "skipped (easycrypt not found on PATH)"
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # Hard load-failure signatures: a require/dependency could not be resolved,
    # so the lemma is unreachable no matter what tactics follow.
    for marker in ("cannot locate theory", "In external theory"):
        if marker in out:
            line = next((ln for ln in out.splitlines() if marker in ln), marker)
            return False, f"file failed to load: {line.strip()[:240]}"
    if proc.returncode != 0:
        diagnostics = _easycrypt_diagnostic_blocks(out)
        hard_diagnostics = [
            block for block in diagnostics
            if not (
                allow_strict_proof_shell_failure
                and "cannot prove goal" in block.lower()
                and "strict" in block.lower()
            )
        ]
        if hard_diagnostics:
            return False, (
                "file did not compile: "
                f"{' '.join(hard_diagnostics[0].split())[:240]}"
            )
        if diagnostics:
            # A proof-stripped source intentionally contains admit shells.
            # r2026.06 reports the first such shell as a strict [error] and
            # stops its batch compile before the target.  That is not positive
            # load evidence, so call it inconclusive: the manager's exact
            # target bootstrap remains the fail-closed authority before any
            # provider process starts.
            return True, (
                "inconclusive (proof-stripped strict shell stopped batch "
                "compile); managed target bootstrap remains authoritative"
            )
        # Non-zero rc with no hard error line (e.g. only `admit` warnings from
        # proof-stripped evaluation sources) is not a load failure.
        return True, "loads OK (non-zero rc, warnings only)"
    return True, "loads OK"


def _easycrypt_diagnostic_blocks(output: str) -> list[str]:
    """Return bounded EasyCrypt error/critical diagnostic blocks."""

    starts = list(
        re.finditer(r"(?im)^\s*\[(?:error|critical)[^\]]*\]", output)
    )
    blocks: list[str] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(output)
        blocks.append(output[match.start():end].strip()[:1000])
    return blocks


def _preflight_eval_agent_confinement(
    cmd: list[str],
    *,
    source_manifest: Path,
    output_dir: Path,
    agent_backend: str,
) -> tuple[bool, str]:
    """Exercise the exact selective namespace before a model can launch."""

    source_file = _cmd_flag(cmd, "--file")
    target_lemma = _cmd_flag(cmd, "--lemma")
    include_dir = _cmd_flag(cmd, "--include-dir") or ""
    if not source_file or not target_lemma:
        return False, "confinement preflight cannot resolve target file/lemma"
    probe_root = output_dir / ".confinement_preflight"
    env = confinement_environment(
        manifest_path=source_manifest,
        base=clear_confinement_environment(os.environ),
    )
    try:
        confinement = EvalAgentConfinement.from_environment(
            project_root=Path.cwd(),
            source_file=source_file,
            target_lemma=target_lemma,
            node_memory_dir=probe_root / "node_memory",
            private_dir=probe_root / "runtime_private",
            include_dir=include_dir,
            environ=env,
        )
        if confinement is None:
            return False, "mandatory confinement unexpectedly resolved to OFF"
        probe = confinement.probe(agent_backend=agent_backend)
    except (EvalAgentConfinementError, OSError, ValueError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if probe.get("probe_status") != "passed":
        return False, f"confinement probe returned {probe.get('probe_status')!r}"
    return True, "selective namespace negative-visibility probe passed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument(
        "--profiles",
        default="",
        help="Comma-separated profile subset overriding the suite profiles.",
    )
    parser.add_argument(
        "--targets",
        default="",
        help="Comma-separated target id subset.",
    )
    parser.add_argument("--repeats", type=int, default=0)
    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=0,
        help="Override every selected target's prover timeout for this run.",
    )
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument("--dry-run", action="store_true")
    run_mode.add_argument(
        "--preflight-only",
        action="store_true",
        help=(
            "Prepare every selected isolated source and run the real EasyCrypt "
            "load plus filesystem-confinement probes, but launch no "
            "orchestrator or model process."
        ),
    )
    parser.add_argument(
        "--preflight-output",
        type=Path,
        default=None,
        help="Required JSON report path for --preflight-only.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help=(
            "Skip the per-target load preflight. By default each target's "
            "source file is compile-checked before the prover launches; a file "
            "that fails to load (e.g. a missing theory) is skipped instead of "
            "producing a silent hollow run where the lemma never opens."
        ),
    )
    parser.add_argument(
        "--execution-manifest-path",
        type=Path,
        default=None,
        help=(
            "Internal scheduler hook: write the long-run execution manifest "
            "to this exact previously absent path instead of allocating one."
        ),
    )
    parser.add_argument(
        "--defer-bundles",
        action="store_true",
        help=(
            "Do not build tracked agent-view report bundles. A composition "
            "runner may defer them until every isolated child run has ended."
        ),
    )
    args = parser.parse_args(argv)
    if args.preflight_only and args.preflight_output is None:
        parser.error("--preflight-only requires --preflight-output")
    if args.preflight_output is not None and not args.preflight_only:
        parser.error("--preflight-output is valid only with --preflight-only")
    if args.preflight_only and args.skip_preflight:
        parser.error("--preflight-only cannot be combined with --skip-preflight")
    if args.execution_manifest_path is not None and (
        args.dry_run or args.preflight_only
    ):
        parser.error(
            "--execution-manifest-path is valid only for a long managed run"
        )
    if (
        args.execution_manifest_path is not None
        and args.execution_manifest_path.exists()
    ):
        parser.error("--execution-manifest-path must not already exist")

    requested_suite = args.suite.resolve()
    if "archived_protocols" in requested_suite.parts:
        parser.error(
            "archived compiler protocols are provenance-only and cannot be run"
        )

    # `kill <pid>` on the suite runner → KeyboardInterrupt → the in-flight
    # orchestrator is reaped by its process group (see the run loop below)
    # rather than orphaned.
    install_terminal_signal_handlers()

    suite = _read_suite(args.suite)
    defaults = dict(suite.get("defaults") or {})
    eval_confinement = bool(
        defaults.get("eval_mode", True)
        and defaults.get("filesystem_confinement", True)
    )
    if eval_confinement and not (
        bool(defaults.get("source_isolation", True))
        and bool(defaults.get("strip_proofs", True))
    ):
        parser.error(
            "eval filesystem confinement requires source_isolation=true and "
            "strip_proofs=true"
        )
    profiles = _selected_profiles(args.profiles, suite.get("profiles") or [])
    targets = _selected_targets(args.targets, suite.get("targets") or [])
    repeats = int(args.repeats or defaults.get("repeats") or 1)
    suite_name = str(suite.get("suite") or args.suite.stem)
    bundle_environment: dict[str, Any] | None = None
    execution_manifest: dict[str, Any] | None = None
    execution_manifest_path: Path | None = None
    if not args.dry_run:
        from workflow.validation.run_report_bundle import (
            capture_repository_environment,
        )
        bundle_environment = capture_repository_environment()
        if not args.preflight_only:
            execution_manifest_path = (
                args.execution_manifest_path.resolve()
                if args.execution_manifest_path is not None
                else _execution_manifest_path(
                    defaults=defaults,
                    suite_name=suite_name,
                )
            )
            execution_manifest = {
                "schema_version": 1,
                "kind": "eval_suite_execution_manifest",
                "execution_id": execution_manifest_path.parent.name,
                "suite": suite_name,
                "suite_file": str(args.suite),
                "suite_sha256": hashlib.sha256(
                    args.suite.read_bytes()
                ).hexdigest(),
                "repository_environment": bundle_environment,
                "selected_profiles": list(profiles),
                "selected_target_ids": [
                    str(target.get("id") or target.get("lemma") or "")
                    for target in targets
                ],
                "repeats": repeats,
                "expected_run_count": len(targets) * len(profiles) * repeats,
                "started_at": _utc_now(),
                "finished_at": "",
                "status": "running",
                "overall_returncode": None,
                "repository_drifted": False,
                "runs": [],
            }
            _write_execution_manifest(
                execution_manifest_path,
                execution_manifest,
            )

    # (cmd, prepare_error, output_dir, target, profile, repeat) per run.
    # Evaluation
    # source prep can fail per-target — e.g. an ambiguous duplicated lemma name
    # — and one broken target must not abort the whole suite, so capture the
    # error and skip that run in the loop below.
    runs = []
    for target in targets:
        for profile in _target_profile_order(target, profiles):
            for repeat in range(1, repeats + 1):
                output_dir = _run_output_dir(
                    target=target,
                    profile=profile,
                    repeat=repeat,
                    defaults=defaults,
                    suite_name=suite_name,
                )
                try:
                    cmd = _orchestrator_cmd(
                        target=target,
                        profile=profile,
                        repeat=repeat,
                        defaults=defaults,
                        suite_name=suite_name,
                        timeout_minutes=args.timeout_minutes,
                        isolate_source=bool(defaults.get("source_isolation", True)),
                        strip_proofs=bool(defaults.get("strip_proofs", True)),
                        prepare=not args.dry_run,
                    )
                except (ValueError, FileNotFoundError) as exc:
                    runs.append((
                        None, str(exc), output_dir, target, profile, repeat,
                    ))
                    continue
                runs.append((
                    cmd, None, output_dir, target, profile, repeat,
                ))

    overall_rc = 0
    repository_drifted = False
    preflight_records: list[dict[str, Any]] = []

    def retain_preflight(record: dict[str, Any]) -> None:
        if args.preflight_only:
            preflight_records.append(dict(record))

    pending_bundles: list[
        tuple[Path, dict[str, Any], str, dict[str, Any], str]
    ] = []
    for cmd, prepare_error, output_dir, target, profile, repeat in runs:
        execution_record = _execution_record(
            target=target,
            profile=profile,
            repeat=repeat,
            output_dir=output_dir,
            cmd=cmd,
        )
        if (
            bundle_environment is not None
            and capture_repository_environment() != bundle_environment
        ):
            print(
                "SUITE: repository git identity changed after the experiment "
                "started; stopping before another prover arm",
                file=sys.stderr,
            )
            repository_drifted = True
            overall_rc = 2
            execution_record.update({
                "status": "repository_drift_before_arm",
                "reason": "repository git identity changed",
                "finished_at": _utc_now(),
            })
            _append_execution_record(
                execution_manifest_path,
                execution_manifest,
                execution_record,
            )
            retain_preflight(execution_record)
            break
        if prepare_error is not None:
            print(
                f"PREPARE FAILED — target '{target.get('id')}' "
                f"(profile {profile}): {prepare_error}. Skipping: launching "
                f"the prover would be a silently broken run.",
                file=sys.stderr,
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "eval_metrics.json").write_text(
                json.dumps(
                    {
                        "status": "prepare_failed",
                        "reason": prepare_error,
                        "target": target.get("id"),
                        "lemma": target.get("lemma"),
                        "profile": profile,
                    },
                    indent=2, sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
            overall_rc = 2
            execution_record.update({
                "status": "prepare_failed",
                "reason": prepare_error,
                "returncode": None,
                "finished_at": _utc_now(),
            })
            _append_execution_record(
                execution_manifest_path,
                execution_manifest,
                execution_record,
            )
            retain_preflight(execution_record)
            continue
        print(" ".join(_quote(part) for part in cmd))
        if args.dry_run:
            continue
        if not args.skip_preflight:
            ok, reason = _preflight_target_loads(
                cmd,
                allow_strict_proof_shell_failure=bool(
                    defaults.get("strip_proofs", True)
                ),
            )
            if not ok:
                print(
                    f"PREFLIGHT FAILED — target '{target.get('id')}' "
                    f"(profile {profile}): {reason}. Skipping: launching the "
                    f"prover would be a hollow run (the lemma never opens). "
                    f"Re-run with --skip-preflight to override.",
                    file=sys.stderr,
                )
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "eval_metrics.json").write_text(
                    json.dumps(
                        {
                            "status": "preflight_failed",
                            "reason": reason,
                            "target": target.get("id"),
                            "lemma": target.get("lemma"),
                            "profile": profile,
                        },
                        indent=2, sort_keys=True,
                    ) + "\n",
                    encoding="utf-8",
                )
                overall_rc = 2
                execution_record.update({
                    "status": "preflight_failed",
                    "reason": reason,
                    "returncode": None,
                    "finished_at": _utc_now(),
                })
                _append_execution_record(
                    execution_manifest_path,
                    execution_manifest,
                    execution_record,
                )
                retain_preflight(execution_record)
                continue
            print(f"PREFLIGHT OK — target '{target.get('id')}': {reason}")
        # Tell the orchestrator NOT to self-bundle: the suite runner bundles
        # below (it keeps the original source path in the report metadata),
        # so this avoids a redundant double build per run.
        #
        # Spawn in its own session and reap the whole group on interrupt:
        # plain subprocess.run() would SIGKILL only the orchestrator PID on
        # Ctrl-C/SIGTERM, orphaning the detached tree workers + why3server.
        worker_pgid_manifest = str(output_dir / "worker_pgids")
        try:
            os.unlink(worker_pgid_manifest)
        except OSError:
            pass
        run_env = clear_confinement_environment(os.environ)
        if eval_confinement:
            source_manifest = output_dir / "source_manifest.json"
            if not source_manifest.is_file():
                print(
                    f"CONFINEMENT FAILED — source manifest is missing for "
                    f"target '{target.get('id')}' (profile {profile}): "
                    f"{source_manifest}",
                    file=sys.stderr,
                )
                overall_rc = 2
                execution_record.update({
                    "status": "confinement_failed",
                    "reason": "source manifest missing",
                    "returncode": None,
                    "finished_at": _utc_now(),
                })
                _append_execution_record(
                    execution_manifest_path,
                    execution_manifest,
                    execution_record,
                )
                retain_preflight(execution_record)
                continue
            execution_record["source_manifest"] = file_identity(
                source_manifest,
                root=Path.cwd(),
            )
            confinement_ok, confinement_reason = (
                _preflight_eval_agent_confinement(
                    cmd,
                    source_manifest=source_manifest,
                    output_dir=output_dir,
                    agent_backend=str(
                        defaults.get("agent_backend")
                        or PROVER_DEFAULTS.agent_backend
                    ),
                )
            )
            execution_record["confinement_preflight"] = {
                "status": "passed" if confinement_ok else "failed",
                "reason": confinement_reason,
            }
            if not confinement_ok:
                print(
                    f"CONFINEMENT PREFLIGHT FAILED — target "
                    f"'{target.get('id')}' (profile {profile}): "
                    f"{confinement_reason}. No model process was launched.",
                    file=sys.stderr,
                )
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "eval_metrics.json").write_text(
                    json.dumps(
                        {
                            "status": "confinement_preflight_failed",
                            "reason": confinement_reason,
                            "target": target.get("id"),
                            "lemma": target.get("lemma"),
                            "profile": profile,
                            "model_launched": False,
                        },
                        indent=2,
                        sort_keys=True,
                    ) + "\n",
                    encoding="utf-8",
                )
                overall_rc = 2
                execution_record.update({
                    "status": "confinement_preflight_failed",
                    "reason": confinement_reason,
                    "returncode": None,
                    "finished_at": _utc_now(),
                })
                _append_execution_record(
                    execution_manifest_path,
                    execution_manifest,
                    execution_record,
                )
                retain_preflight(execution_record)
                continue
            run_env = confinement_environment(
                manifest_path=source_manifest,
                base=run_env,
            )
        if args.preflight_only:
            execution_record.update({
                "status": "preflight_valid",
                "reason": "all no-model preflight gates passed",
                "returncode": 0,
                "finished_at": _utc_now(),
            })
            retain_preflight(execution_record)
            continue
        summaries_before = _summary_paths(output_dir)
        execution_record["started_at"] = _utc_now()
        _orch = subprocess.Popen(
            cmd, cwd=Path.cwd(),
            env={**run_env, "SHANNON_SUITE_WILL_BUNDLE": "1",
                 WORKER_PGID_MANIFEST_ENV: worker_pgid_manifest},
            start_new_session=True)
        try:
            returncode = _orch.wait()
        except KeyboardInterrupt:
            terminate_subprocess_tree(_orch)
            raise
        finally:
            # Backstop reap of any worker group a wedged/SIGKILL'd orchestrator
            # left behind (no-op + file delete on the clean self-reaped path).
            reap_worker_pgid_manifest(worker_pgid_manifest)
        summaries_after = _summary_paths(output_dir)
        produced_summaries = sorted(summaries_after - summaries_before)
        execution_record.update({
            "returncode": returncode,
            "produced_summary_paths": [
                str(path) for path in produced_summaries
            ],
            "finished_at": _utc_now(),
        })
        if len(produced_summaries) != 1:
            execution_record.update({
                "status": "run_artifact_cardinality_error",
                "reason": (
                    "expected exactly one new summary.json from this "
                    f"orchestrator call, got {len(produced_summaries)}"
                ),
            })
            _append_execution_record(
                execution_manifest_path,
                execution_manifest,
                execution_record,
            )
            overall_rc = 2
            continue
        run_dir = produced_summaries[0].parent
        execution_record["run_dir"] = str(run_dir)
        execution_record["run_artifacts"] = evaluation_artifact_inventory(
            run_dir
        )
        if returncode != 0:
            # Record and continue: one crashed orchestrator must not abort the
            # remaining targets (matches the prepare/preflight skip-and-continue
            # design; 06-13 audit finding).
            print(f"SUITE: orchestrator rc={returncode} for "
                  f"{target.get('lemma')} @ {profile}; continuing")
            overall_rc = returncode
            execution_record.update({
                "status": "orchestrator_failed",
                "reason": f"orchestrator returncode {returncode}",
            })
            _append_execution_record(
                execution_manifest_path,
                execution_manifest,
                execution_record,
            )
            continue
        metrics = collect_run_metrics(run_dir)
        (output_dir / "eval_metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "eval_metrics.md").write_text(
            render_markdown([metrics]),
            encoding="utf-8",
        )
        pending_bundles.append((
            run_dir,
            target,
            profile,
            defaults,
            f"{target.get('id') or target.get('lemma') or 'target'}"
            f"__{profile}__{output_dir.name}",
        ))
        metrics_valid = bool((metrics.get("validity") or {}).get("valid"))
        execution_record.update({
            "status": "completed_valid" if metrics_valid else "completed_invalid",
            "metrics_status": metrics.get("status"),
            "metrics_valid": metrics_valid,
            "metrics_validity_reasons": list(
                (metrics.get("validity") or {}).get("reasons") or []
            ),
            "eval_metrics_json": str(output_dir / "eval_metrics.json"),
        })
        _append_execution_record(
            execution_manifest_path,
            execution_manifest,
            execution_record,
        )
        if not metrics_valid:
            overall_rc = 2
    if (
        bundle_environment is not None
        and capture_repository_environment() != bundle_environment
    ):
        repository_drifted = True
        overall_rc = 2
        print(
            "SUITE: repository git identity changed during the final prover "
            "arm; tracked report bundles were not generated",
            file=sys.stderr,
        )
    if args.preflight_only:
        expected_count = len(targets) * len(profiles) * repeats
        preflight_valid = (
            overall_rc == 0
            and not repository_drifted
            and len(preflight_records) == expected_count
            and all(
                record.get("status") == "preflight_valid"
                for record in preflight_records
            )
        )
        report = {
            "schema_version": 1,
            "kind": "eval_suite_no_model_preflight",
            "suite": suite_name,
            "suite_file": str(args.suite),
            "suite_sha256": hashlib.sha256(args.suite.read_bytes()).hexdigest(),
            "repository_environment": bundle_environment,
            "selected_profiles": list(profiles),
            "selected_target_ids": [
                str(target.get("id") or target.get("lemma") or "")
                for target in targets
            ],
            "expected_record_count": expected_count,
            "recorded_count": len(preflight_records),
            "preflight_valid": preflight_valid,
            "model_process_launched": False,
            "repository_drifted": repository_drifted,
            "records": preflight_records,
        }
        assert args.preflight_output is not None
        args.preflight_output.parent.mkdir(parents=True, exist_ok=True)
        args.preflight_output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"SUITE-NO-MODEL-PREFLIGHT: {args.preflight_output}")
        return 0 if preflight_valid else 2
    if not repository_drifted and not args.defer_bundles:
        for run_dir, target, profile, run_defaults, bundle_key in pending_bundles:
            _write_agent_view_bundle(
                run_dir=run_dir,
                target=target,
                profile=profile,
                defaults=run_defaults,
                bundle_key=bundle_key,
                environment=bundle_environment,
            )
    if execution_manifest is not None and execution_manifest_path is not None:
        execution_manifest.update({
            "finished_at": _utc_now(),
            "status": "completed" if overall_rc == 0 else "invalid",
            "overall_returncode": overall_rc,
            "repository_drifted": repository_drifted,
            "recorded_run_count": len(execution_manifest["runs"]),
        })
        _write_execution_manifest(
            execution_manifest_path,
            execution_manifest,
        )
        print(f"SUITE-EXECUTION-MANIFEST: {execution_manifest_path}")
    return overall_rc


def _write_agent_view_bundle(
    *, run_dir: Path, target: dict[str, Any], profile: str,
    defaults: dict[str, Any], bundle_key: str,
    environment: dict[str, Any] | None,
) -> None:
    """Auto-generate the committed agent-view timeline+view bundle for this run
    (fixed location ``agent_view_runs/``). Best-effort: never fails the run."""
    try:
        from workflow.validation.run_report_bundle import build_bundle
        iter_dir = run_dir / "iteration_1"
        if not (iter_dir / "node_memory").is_dir():
            return
        dest = build_bundle(
            iter_dir,
            timestamp=run_dir.name,
            lemma=str(target.get("lemma") or "unknown_lemma"),
            source_file=str(target.get("file") or ""),
            model=str(defaults.get("model") or PROVER_DEFAULTS.model),
            profile=profile,
            trees=defaults.get("tree_initial_provers"),
            eval_mode=bool(defaults.get("eval_mode", True)),
            bundle_key=bundle_key,
            environment=environment,
        )
        if dest is not None:
            print(f"AGENT-VIEW-BUNDLE: wrote {dest}")
    except Exception as exc:  # noqa: BLE001
        print(f"AGENT-VIEW-BUNDLE: skipped ({type(exc).__name__}: {exc})")


def _run_output_dir(
    *,
    target: dict[str, Any],
    profile: str,
    repeat: int,
    defaults: dict[str, Any],
    suite_name: str,
) -> Path:
    output_root = Path(defaults.get("output_dir") or "artifacts/eval_suite")
    return output_root / suite_name / profile / str(target["id"]) / f"r{repeat:02d}"


def _summary_paths(output_dir: Path) -> frozenset[Path]:
    """Snapshot explicit run artifacts for current-call set-difference.

    Older summaries are never selected by mtime or used as a fallback.  The
    suite accepts a run only when the exact orchestrator call adds one and only
    one new ``summary.json`` under its pre-resolved output directory.
    """

    return frozenset(output_dir.glob("*/summary.json"))


def _execution_manifest_path(
    *,
    defaults: dict[str, Any],
    suite_name: str,
) -> Path:
    output_root = Path(defaults.get("output_dir") or "artifacts/eval_suite")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    execution_id = f"{timestamp}_{uuid.uuid4().hex[:12]}"
    return (
        output_root / suite_name / "executions" / execution_id / "manifest.json"
    )


def _execution_record(
    *,
    target: dict[str, Any],
    profile: str,
    repeat: int,
    output_dir: Path,
    cmd: list[str] | None,
) -> dict[str, Any]:
    return {
        "ordinal": None,
        "target_id": str(target.get("id") or target.get("lemma") or ""),
        "source_file": str(target.get("file") or ""),
        "lemma": str(target.get("lemma") or ""),
        "profile": profile,
        "repeat": repeat,
        "command": list(cmd or []),
        "output_dir": str(output_dir),
        "started_at": "",
        "finished_at": "",
        "status": "planned",
        "reason": "",
        "returncode": None,
        "produced_summary_paths": [],
        "run_dir": "",
        "source_manifest": {},
        "run_artifacts": [],
    }


def _append_execution_record(
    path: Path | None,
    manifest: dict[str, Any] | None,
    record: dict[str, Any],
) -> None:
    if path is None or manifest is None:
        return
    stored = dict(record)
    stored["ordinal"] = len(manifest["runs"]) + 1
    manifest["runs"].append(stored)
    _write_execution_manifest(path, manifest)


def _write_execution_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_EVALUATION_ARTIFACT_BASENAMES = frozenset({
    "agent_session_ids.json",
    "agent_sessions.jsonl",
    "codex_events.jsonl",
    "config.json",
    "eval_agent_confinement.json",
    "payload_audit.jsonl",
    "proof_node_mcp_config.json",
    "proof_node_manager_audit.jsonl",
    "session_id.txt",
    "summary.json",
    "surface_profile_manifest.json",
    "timeline.jsonl",
})


def evaluation_artifact_inventory(run_dir: Path) -> list[dict[str, Any]]:
    """Freeze only files used by managed result recomputation.

    The inventory is current-call scoped through ``run_dir``.  It deliberately
    excludes generated report views/thinking files so deferred human report
    bundling cannot mutate the experiment authority after an arm completes.
    """

    files = sorted(
        path for path in run_dir.rglob("*")
        if path.is_file() and (
            path.name in _EVALUATION_ARTIFACT_BASENAMES
            or _is_codex_rollout(path, run_dir=run_dir)
        )
    )
    return [file_identity(path, root=run_dir) for path in files]


def file_identity(path: Path, *, root: Path) -> dict[str, Any]:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    payload = resolved_path.read_bytes()
    return {
        "path": str(resolved_path.relative_to(resolved_root)),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _is_codex_rollout(path: Path, *, run_dir: Path) -> bool:
    if path.suffix != ".jsonl":
        return False
    relative = path.relative_to(run_dir)
    parts = relative.parts
    return "codex_home" in parts and "sessions" in parts


def _orchestrator_cmd(
    *,
    target: dict[str, Any],
    profile: str,
    repeat: int,
    defaults: dict[str, Any],
    suite_name: str,
    timeout_minutes: int = 0,
    isolate_source: bool = True,
    strip_proofs: bool = True,
    prepare: bool = True,
) -> list[str]:
    output_dir = _run_output_dir(
        target=target,
        profile=profile,
        repeat=repeat,
        defaults=defaults,
        suite_name=suite_name,
    )
    prepared = _prepared_target(
        target=target,
        output_dir=output_dir,
        isolate_source=isolate_source,
        strip_proofs=strip_proofs,
        prepare=prepare,
    )
    cmd = [
        sys.executable,
        "-m",
        "workflow.orchestrator",
        "--file",
        str(prepared["file"]),
        "--lemma",
        str(target["lemma"]),
        "--include-dir",
        str(prepared.get("include_dir") or defaults.get("include_dir") or ""),
        "--max-iterations",
        "1",  # eval mode is single-pass; the orchestrator clamps to 1 anyway
        "--prover-timeout-minutes",
        str(
            timeout_minutes
            or target.get("timeout_minutes")
            or defaults.get("timeout_minutes")
            or 30
        ),
        "--surface-profile",
        profile,
    ]
    if defaults.get("eval_mode", True):
        cmd.append("--eval-mode")
    agent_backend = defaults.get("agent_backend")
    if agent_backend:
        cmd.extend(["--agent-backend", str(agent_backend)])
    model = defaults.get("model")
    if model:
        cmd.extend(["--prover-model", str(model)])
    effort = defaults.get("effort")
    if effort:
        cmd.extend(["--prover-effort", str(effort)])
    if defaults.get("tree_initial_provers") is not None:
        cmd.extend(["--tree-initial-provers", str(defaults["tree_initial_provers"])])
    if defaults.get("tree_max_concurrent") is not None:
        cmd.extend(["--tree-max-concurrent", str(defaults["tree_max_concurrent"])])
    cmd.extend(["--output-dir", str(output_dir)])
    return cmd


def _prepared_target(
    *,
    target: dict[str, Any],
    output_dir: Path,
    isolate_source: bool,
    strip_proofs: bool,
    prepare: bool,
) -> dict[str, Any]:
    source = Path(str(target["file"]))
    if not isolate_source:
        return dict(target)
    copy_root = Path(str(target.get("copy_root") or source))
    prepared_result = prepare_eval_source(
        source_file=source,
        target_lemma=str(target["lemma"]),
        output_dir=output_dir,
        copy_root=copy_root,
        strip_proofs=strip_proofs,
        write_manifest=prepare,
    ) if prepare else None
    if prepared_result is None:
        if copy_root.is_file():
            rel_source = Path(source.name)
            dest_root = output_dir / "source"
        else:
            rel_source = source.relative_to(copy_root)
            dest_root = output_dir / "source" / copy_root.name
        dest_file = dest_root / rel_source
    else:
        dest_file = prepared_result.isolated_file
    prepared = dict(target)
    prepared["file"] = str(dest_file)
    return prepared


def _read_suite(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"suite must be a JSON object: {path}")
    return data


def _selected_profiles(override: str, suite_profiles: list[Any]) -> list[str]:
    raw = [item.strip() for item in override.split(",") if item.strip()]
    profiles = raw or [str(item) for item in suite_profiles]
    if not profiles:
        raise ValueError("suite has no profiles")
    for profile in profiles:
        ensure_current_surface_profile(profile)
    return profiles


def _selected_targets(override: str, suite_targets: list[Any]) -> list[dict[str, Any]]:
    wanted = {item.strip() for item in override.split(",") if item.strip()}
    targets = [
        dict(item)
        for item in suite_targets
        if isinstance(item, dict) and (not wanted or str(item.get("id")) in wanted)
    ]
    if not targets:
        raise ValueError("suite target selection is empty")
    return targets


def _target_profile_order(
    target: dict[str, Any],
    selected_profiles: list[str],
) -> list[str]:
    """Apply an optional preregistered per-target arm order.

    The order changes scheduling only.  It cannot add an arm that was not in
    the selected suite/CLI profile set, and it must mention every selected arm
    exactly once.  This supports small counterbalanced experiments without
    duplicating or mutating profile contracts.
    """

    configured = target.get("profile_order")
    if configured is None:
        return list(selected_profiles)
    if not isinstance(configured, list) or not all(
        isinstance(item, str) and item for item in configured
    ):
        raise ValueError("target profile_order must be a list of profile names")
    if len(configured) != len(set(configured)):
        raise ValueError("target profile_order contains duplicate profiles")
    ordered = [item for item in configured if item in selected_profiles]
    if set(ordered) != set(selected_profiles):
        missing = sorted(set(selected_profiles) - set(ordered))
        raise ValueError(
            "target profile_order omits selected profiles: "
            + ", ".join(missing)
        )
    return ordered


def _quote(part: str) -> str:
    if not part:
        return "''"
    if all(ch.isalnum() or ch in "-_./:=," for ch in part):
        return part
    return "'" + part.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
