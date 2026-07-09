"""Run ShannonProver paper-eval suites.

Suites are JSON files that describe a small target/profile matrix.  The runner
expands each row into an ordinary ``workflow.orchestrator`` invocation so the
proof workflow, event logs, and validation artifacts remain comparable.
Suites use canonical surface profile names from ``workflow.surface_profiles``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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
from workflow.schemas.config import PROVER_DEFAULTS
from workflow.surface_profiles import ensure_supported_surface_profile


def _cmd_flag(cmd: list[str], name: str) -> str | None:
    """Return the value following ``name`` in an argv-style command list."""
    try:
        return cmd[cmd.index(name) + 1]
    except (ValueError, IndexError):
        return None


def _preflight_target_loads(
    cmd: list[str], *, timeout: int = 240
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
        err = next(
            (ln for ln in out.splitlines()
             if "[error" in ln or "[critical" in ln),
            None,
        )
        if err:
            return False, f"file did not compile: {err.strip()[:240]}"
        # Non-zero rc with no hard error line (e.g. only `admit` warnings from
        # proof-stripped evaluation sources) is not a load failure.
        return True, "loads OK (non-zero rc, warnings only)"
    return True, "loads OK"


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
    parser.add_argument("--dry-run", action="store_true")
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
    args = parser.parse_args(argv)

    # `kill <pid>` on the suite runner → KeyboardInterrupt → the in-flight
    # orchestrator is reaped by its process group (see the run loop below)
    # rather than orphaned.
    install_terminal_signal_handlers()

    suite = _read_suite(args.suite)
    defaults = dict(suite.get("defaults") or {})
    profiles = _selected_profiles(args.profiles, suite.get("profiles") or [])
    targets = _selected_targets(args.targets, suite.get("targets") or [])
    repeats = int(args.repeats or defaults.get("repeats") or 1)

    # (cmd, prepare_error, output_dir, target, profile) per run. Evaluation
    # source prep can fail per-target — e.g. an ambiguous duplicated lemma name
    # — and one broken target must not abort the whole suite, so capture the
    # error and skip that run in the loop below.
    runs = []
    for target in targets:
        for profile in profiles:
            for repeat in range(1, repeats + 1):
                output_dir = _run_output_dir(
                    target=target,
                    profile=profile,
                    repeat=repeat,
                    defaults=defaults,
                    suite_name=str(suite.get("suite") or args.suite.stem),
                )
                try:
                    cmd = _orchestrator_cmd(
                        target=target,
                        profile=profile,
                        repeat=repeat,
                        defaults=defaults,
                        suite_name=str(suite.get("suite") or args.suite.stem),
                        timeout_minutes=args.timeout_minutes,
                        isolate_source=bool(defaults.get("source_isolation", True)),
                        strip_proofs=bool(defaults.get("strip_proofs", True)),
                        prepare=not args.dry_run,
                    )
                except (ValueError, FileNotFoundError) as exc:
                    runs.append((None, str(exc), output_dir, target, profile))
                    continue
                runs.append((cmd, None, output_dir, target, profile))

    overall_rc = 0
    for cmd, prepare_error, output_dir, target, profile in runs:
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
            continue
        print(" ".join(_quote(part) for part in cmd))
        if args.dry_run:
            continue
        if not args.skip_preflight:
            ok, reason = _preflight_target_loads(cmd)
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
        _orch = subprocess.Popen(
            cmd, cwd=Path.cwd(),
            env={**os.environ, "SHANNON_SUITE_WILL_BUNDLE": "1",
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
        if returncode != 0:
            # Record and continue: one crashed orchestrator must not abort the
            # remaining targets (matches the prepare/preflight skip-and-continue
            # design; 06-13 audit finding).
            print(f"SUITE: orchestrator rc={returncode} for "
                  f"{target.get('lemma')} @ {profile}; continuing")
            overall_rc = returncode
            continue
        run_dir = _latest_run_dir(output_dir)
        metrics = collect_run_metrics(run_dir)
        (output_dir / "eval_metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "eval_metrics.md").write_text(
            render_markdown([metrics]),
            encoding="utf-8",
        )
        _write_agent_view_bundle(
            run_dir=run_dir, target=target, profile=profile,
            defaults=defaults,
        )
    return overall_rc


def _write_agent_view_bundle(
    *, run_dir: Path, target: dict[str, Any], profile: str,
    defaults: dict[str, Any],
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


def _latest_run_dir(output_dir: Path) -> Path:
    summaries = sorted(
        output_dir.glob("*/summary.json"),
        key=lambda path: (path.stat().st_mtime, path.parent.name),
    )
    if not summaries:
        return output_dir
    return summaries[-1].parent


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
        ensure_supported_surface_profile(profile)
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


def _quote(part: str) -> str:
    if not part:
        return "''"
    if all(ch.isalnum() or ch in "-_./:=," for ch in part):
        return part
    return "'" + part.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
