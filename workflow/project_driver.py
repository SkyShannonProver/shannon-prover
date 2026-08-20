"""Project-level driver: prove every admit lemma in a .ec file.

For small files with one target lemma, use `python3 -m workflow.orchestrator`.
For big projects (ChaChaPoly, cramer-shoup) with 20+ admit lemmas and
deep dependency chains, use this driver. It:

  1. Scans all admit lemmas in the file.
  2. Builds a dependency DAG from proof-body references.
  3. Topologically sorts — prove leaves first so later lemmas see proved
     dependencies rather than admit'd ones.
  4. Per-lemma time cap with graceful admit-on-timeout — one stuck lemma
     doesn't block the whole run.
  5. Progress report: proved / admit-still / crashed counts + time per
     lemma, so you know what's left for human fill-in.

Usage:
    python3 -m workflow.project_driver \\
        --file eval/examples/ChaChaPoly/chacha_poly.ec \\
        --include-dir easycrypt-src/theories \\
        --time-cap 900 \\
        --skip-regression
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from workflow.schemas.config import RunConfig
from workflow.proc_lifecycle import (
    WORKER_PGID_MANIFEST_ENV,
    install_terminal_signal_handlers,
    reap_worker_pgid_manifest,
    terminate_subprocess_tree,
)

logger = logging.getLogger("workflow.project_driver")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Lemma inventory + dependency graph
# ---------------------------------------------------------------------------


def scan_admit_lemmas(file_path: Path) -> list[dict]:
    """Return [{name, statement, status, deps, can_prove}] for every lemma in
    the file, classified as admit / proved / unknown. Dependency info is
    populated for admit lemmas so the caller can topo-sort.
    """
    from workflow.easycrypt_source_inventory import (
        detect_admit_dependencies,
        extract_declarations,
    )

    content = file_path.read_text(encoding="utf-8")
    lemmas = extract_declarations(content)
    dep_info = detect_admit_dependencies(content, lemmas)

    out = []
    for lem in lemmas:
        info = {
            "name": lem["name"],
            "statement": lem["statement"],
            "status": lem["status"],
            "deps": [],
            "unproved_deps": [],
            "can_prove": True,
        }
        if lem["name"] in dep_info:
            d = dep_info[lem["name"]]
            info["deps"] = d.get("deps", [])
            info["unproved_deps"] = d.get("unproved_deps", [])
            info["can_prove"] = d.get("can_prove", True)
        out.append(info)
    return out


def topological_order(lemmas: list[dict]) -> list[str]:
    """Return admit lemma names in proving order: leaves (no unproved deps)
    first. Later entries may depend on earlier ones.

    Not a strict topo sort — we do a simple wave: at each iteration, take all
    lemmas whose unproved_deps are empty given what's already scheduled,
    schedule them, mark as "scheduled-proved", repeat. This is good enough
    for the common chain/tree shapes in crypto proofs and degrades to an
    arbitrary order for genuine cycles (which shouldn't exist in valid EC
    files anyway).
    """
    admit = {l["name"]: l for l in lemmas if l["status"] == "admit"}
    scheduled: list[str] = []
    scheduled_set: set[str] = set()

    # Pre-treat already-proved as "scheduled" for dep-resolution purposes.
    already_proved = {l["name"] for l in lemmas if l["status"] == "proved"}

    while len(scheduled) < len(admit):
        progress = False
        for name, info in admit.items():
            if name in scheduled_set:
                continue
            unproved = [d for d in info["unproved_deps"]
                        if d not in scheduled_set and d not in already_proved]
            if not unproved:
                scheduled.append(name)
                scheduled_set.add(name)
                progress = True
        if not progress:
            # Cycle or genuine blocker — append everything in file order so
            # the driver still makes progress (the prover may still succeed
            # even if we get the order "wrong" by our heuristic).
            for name in admit:
                if name not in scheduled_set:
                    scheduled.append(name)
                    scheduled_set.add(name)
            break

    return scheduled


# ---------------------------------------------------------------------------
# Per-lemma run with time cap
# ---------------------------------------------------------------------------


@dataclass
class LemmaResult:
    name: str
    outcome: str  # "proved" | "timeout" | "failed" | "crashed"
    time_sec: float
    proved: bool
    verified: bool
    tactic_count: int = 0
    error_msg: str = ""


def run_one_lemma(
    file_path: Path,
    lemma: str,
    include_dir: str,
    time_cap_sec: int,
    output_dir: Path,
    eval_mode: bool = False,
) -> LemmaResult:
    """Run the orchestrator on a single lemma as a subprocess with time cap.

    Subprocess isolation: if the prover crashes (OOM, stack overflow,
    infinite loop in a tactic), only the child dies — the driver keeps
    going. subprocess.Popen + wait(timeout=...) + kill() gives us clean
    recovery plus a hard wall-clock cap.

    File-state safety: snapshot the .ec file before the run. On timeout
    or crash, restore the snapshot unconditionally — a killed prover may
    have partially written the proof block, leaving the file in an
    inconsistent state that would poison every subsequent lemma run.
    On success, keep the new file state so later lemmas see their
    dependency as `proved` rather than `admit`.
    """
    t0 = time.monotonic()
    log_path = output_dir / f"{lemma}.log"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot the file so we can roll back on failure.
    try:
        snapshot = file_path.read_bytes()
    except OSError as e:
        return LemmaResult(
            name=lemma, outcome="crashed", time_sec=0.0,
            proved=False, verified=False,
            error_msg=f"cannot read {file_path}: {e}",
        )

    # Auto-derive the prover's internal timeout from time_cap, leaving a
    # small buffer (~2 min) so the orchestrator can still write summary.json
    # and the run bundle before the driver's hard time cap kills it.
    prover_timeout_min = max(5, (time_cap_sec // 60) - 2)
    orchestrator_output = output_dir / f"{lemma}.orchestrator_runs"
    before_runs = (
        {path.resolve() for path in orchestrator_output.iterdir() if path.is_dir()}
        if orchestrator_output.is_dir()
        else set()
    )
    # Hand the orchestrator one typed RunConfig instead of a hand-assembled
    # flag list: flag drift between driver and orchestrator argparse (the
    # removed --skip-regression made every lemma "crash" at argparse) cannot
    # recur when the contract is the RunConfig schema itself.
    run_config = RunConfig(
        file=str(file_path),
        lemma=lemma,
        include_dir=include_dir,
        max_iterations=1,
        output_dir=str(orchestrator_output),
        eval_mode=eval_mode,
    )
    run_config.prover.timeout_minutes = prover_timeout_min
    config_path = output_dir / f"{lemma}.config.json"
    run_config.save(config_path)
    cmd = [
        sys.executable, "-m", "workflow.orchestrator",
        "--config", str(config_path),
    ]

    import os as _os
    env = dict(_os.environ)
    if eval_mode:
        env["EVAL_TARGET_LEMMA"] = lemma
    # Per-attempt worker-PGID manifest: the orchestrator records each detached
    # tree worker's group here; if we have to SIGKILL a wedged orchestrator (its
    # own reaping finally never ran), reap_worker_pgid_manifest is the backstop.
    worker_pgid_manifest = str(output_dir / f"{lemma}.worker_pgids")
    env[WORKER_PGID_MANIFEST_ENV] = worker_pgid_manifest
    try:
        Path(worker_pgid_manifest).unlink()
    except OSError:
        pass

    rc = None
    killed = False
    crash_msg = ""
    try:
        with log_path.open("w", encoding="utf-8") as logf:
            try:
                # start_new_session=True puts the orchestrator in its own process
                # group so terminate_subprocess_tree can signal the whole group.
                proc = subprocess.Popen(
                    cmd,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    cwd=str(_PROJECT_ROOT),
                    env=env,
                    start_new_session=True,
                )
                try:
                    proc.wait(timeout=time_cap_sec)
                    rc = proc.returncode
                except subprocess.TimeoutExpired:
                    # Time cap hit. Cooperatively stop the orchestrator's whole
                    # process group (SIGTERM → grace → SIGKILL) so ITS finally
                    # blocks reap the detached tree workers + why3server + daemon.
                    # A bare proc.kill() here SIGKILLs only the orchestrator PID,
                    # skipping its cleanup and orphaning the worker subtree.
                    terminate_subprocess_tree(proc)
                    killed = True
                except KeyboardInterrupt:
                    # Ctrl-C or SIGTERM (see install_terminal_signal_handlers):
                    # tear the orchestrator down gracefully before propagating so
                    # the operator does not leave an orphaned worker subtree.
                    terminate_subprocess_tree(proc)
                    raise
            except KeyboardInterrupt:
                raise
            except Exception as e:
                crash_msg = str(e)
    finally:
        # Backstop: reap any worker group the orchestrator left behind (no-op +
        # file delete on the clean path where it self-reaped), on every exit.
        reap_worker_pgid_manifest(worker_pgid_manifest)

    elapsed = time.monotonic() - t0

    # The subprocess log is diagnostic text, never terminal-outcome authority.
    # Consume the exact typed result written by the run-level prover owner.
    terminal_result = None
    result_error = ""
    if not killed and not crash_msg:
        after_runs = (
            {path.resolve() for path in orchestrator_output.iterdir() if path.is_dir()}
            if orchestrator_output.is_dir()
            else set()
        )
        new_runs = sorted(after_runs - before_runs)
        result_paths = [
            run / "iteration_1" / "prover_run_result.json"
            for run in new_runs
            if (run / "iteration_1" / "prover_run_result.json").is_file()
        ]
        if len(result_paths) == 1:
            try:
                from workflow.schemas.prover_result import ProverResult

                terminal_result = ProverResult.load(result_paths[0])
            except Exception as exc:
                result_error = f"invalid terminal prover result: {exc}"
        else:
            result_error = (
                "expected exactly one terminal prover result from this attempt; "
                f"found {len(result_paths)}"
            )
    proved = bool(terminal_result and terminal_result.is_verified)
    verified = proved
    tactic_count = int(
        (terminal_result.completion_candidate or {}).get("tactic_count") or 0
    ) if terminal_result is not None else 0

    # Decide outcome
    if crash_msg:
        outcome = "crashed"
    elif killed:
        outcome = "timeout"
    elif proved:
        outcome = "proved"
    elif terminal_result is not None and terminal_result.status == "incomplete":
        outcome = "failed"
    else:
        outcome = "crashed"
        crash_msg = result_error or (
            terminal_result.error if terminal_result is not None else ""
        ) or "terminal prover result unavailable"

    # File-state restore: if the run didn't succeed, revert any partial write.
    # Keep the new state on success (subsequent lemmas in the chain see this
    # lemma's proof as committed rather than as admit).
    if outcome != "proved":
        try:
            current = file_path.read_bytes()
        except OSError:
            current = snapshot
        if current != snapshot:
            try:
                file_path.write_bytes(snapshot)
                logger.info(
                    "[%s] outcome=%s: restored %s to pre-run state "
                    "(%d bytes → %d bytes)",
                    lemma, outcome, file_path, len(current), len(snapshot),
                )
            except OSError as e:
                logger.error(
                    "[%s] CRITICAL: could not restore %s (%s) — file may be "
                    "in an inconsistent state; subsequent lemmas may fail",
                    lemma, file_path, e,
                )

    return LemmaResult(
        name=lemma,
        outcome=outcome,
        time_sec=elapsed,
        proved=proved,
        verified=verified,
        tactic_count=tactic_count,
        error_msg=crash_msg or (f"hit {time_cap_sec}s cap" if killed else ""),
    )


# ---------------------------------------------------------------------------
# Driver main
# ---------------------------------------------------------------------------


def run_project(
    file_path: Path,
    include_dir: str,
    time_cap_sec: int = 900,
    eval_mode: bool = False,
    output_dir: Optional[Path] = None,
    only_lemmas: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict:
    """Drive the whole-project prove loop. Returns a summary dict.

    dry_run=True: print the dep graph and planned order, then exit without
    invoking the prover on any lemma. Useful for validating the sort
    order or --only filter before committing to a long run.
    """
    if output_dir is None:
        output_dir = _PROJECT_ROOT / "workflow" / "runs" / f"project_{file_path.stem}_{int(time.time())}"
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        # Pin the laptop awake for the full multi-hour run. Individual
        # orchestrator subprocesses also each call _prevent_sleep_on_macos,
        # but those expire between lemmas; pinning here covers the gaps.
        try:
            from workflow.orchestrator import _prevent_sleep_on_macos
            _caff = _prevent_sleep_on_macos()
            if _caff is not None:
                print(f"[project_driver] caffeinate pinned (pid={_caff.pid}) — laptop will stay awake for the whole run")
        except Exception as _e:
            logger.warning("could not pin laptop awake: %s", _e)

    print(f"[project_driver] scanning {file_path}")
    lemmas = scan_admit_lemmas(file_path)
    admit_names = [l["name"] for l in lemmas if l["status"] == "admit"]
    proved_names = [l["name"] for l in lemmas if l["status"] == "proved"]
    print(f"[project_driver] {len(admit_names)} admit, {len(proved_names)} already proved")

    if only_lemmas:
        admit_names = [n for n in admit_names if n in only_lemmas]
        print(f"[project_driver] filtered to --only: {admit_names}")

    order = [n for n in topological_order(lemmas) if n in admit_names]
    print(f"[project_driver] proving order ({len(order)} lemmas):")
    for i, name in enumerate(order):
        deps_info = next((l for l in lemmas if l["name"] == name), None)
        deps = deps_info.get("unproved_deps", []) if deps_info else []
        status = deps_info.get("status", "?") if deps_info else "?"
        print(f"  {i+1:2d}. {name:35s} [{status}]"
              + (f"   blocked by: {deps}" if deps else ""))

    if dry_run:
        print(f"\n[project_driver] --dry-run: stopping before prover calls.")
        return {
            "file": str(file_path),
            "total_lemmas": len(order),
            "dry_run": True,
            "order": order,
        }

    results: list[LemmaResult] = []
    summary_path = output_dir / "summary.json"
    progress_path = output_dir / "progress_log.txt"

    # Background monitor: every 20 min, append a progress note to
    # progress_log.txt so a human walking by can see state without
    # parsing JSON. Daemon thread exits with the main thread.
    stop_monitor = threading.Event()
    run_started = time.monotonic()

    def _monitor():
        first = True
        while not stop_monitor.wait(timeout=(60 if first else 20 * 60)):
            first = False
            try:
                if not summary_path.exists():
                    continue
                s = json.loads(summary_path.read_text(encoding="utf-8"))
                elapsed_min = (time.monotonic() - run_started) / 60
                now = datetime.now().isoformat(timespec="seconds")
                completed = s.get("completed", 0)
                total = s.get("total_lemmas", 0)
                avg = (elapsed_min * 60 / completed) if completed else 0
                remaining_est = (total - completed) * avg / 60 if avg > 0 else 0
                note = (
                    f"[{now}] elapsed={elapsed_min:.0f}min  "
                    f"{completed}/{total} lemmas done  "
                    f"proved={s.get('proved', 0)} "
                    f"timeout={s.get('timeout', 0)} "
                    f"failed={s.get('failed', 0)} "
                    f"crashed={s.get('crashed', 0)}  "
                    f"avg={avg:.0f}s/lemma  eta≈{remaining_est:.0f}min\n"
                )
                recent = s.get("results", [])[-3:]
                lines = [note]
                for r in recent:
                    lines.append(
                        f"  · {r.get('name', '?'):35s} "
                        f"{r.get('outcome', '?'):10s} "
                        f"{r.get('time_sec', 0):5.0f}s  "
                        f"tac={r.get('tactic_count', 0)}\n"
                    )
                with progress_path.open("a", encoding="utf-8") as f:
                    f.writelines(lines)
            except Exception as e:
                with progress_path.open("a", encoding="utf-8") as f:
                    f.write(f"[monitor-error] {e}\n")

    # dry_run already returned above; the monitor always accompanies a live run.
    threading.Thread(target=_monitor, daemon=True).start()

    def _write_summary(status: str) -> dict:
        """Compute + write summary.json. Called after each lemma AND at
        run end, so a Ctrl+C mid-run leaves a readable partial summary."""
        n_proved = sum(1 for r in results if r.outcome == "proved")
        n_timeout = sum(1 for r in results if r.outcome == "timeout")
        n_failed = sum(1 for r in results if r.outcome == "failed")
        n_crashed = sum(1 for r in results if r.outcome == "crashed")
        total_time = sum(r.time_sec for r in results)
        s = {
            "file": str(file_path),
            "status": status,  # "in_progress" | "done" | "interrupted"
            "total_lemmas": len(order),
            "completed": len(results),
            "proved": n_proved,
            "timeout": n_timeout,
            "failed": n_failed,
            "crashed": n_crashed,
            "total_time_min": round(total_time / 60, 1),
            "time_cap_sec": time_cap_sec,
            "results": [asdict(r) for r in results],
        }
        summary_path.write_text(json.dumps(s, indent=2), encoding="utf-8")
        return s

    try:
        for i, name in enumerate(order):
            print(f"\n[project_driver] === {i+1}/{len(order)}: {name} ===")
            r = run_one_lemma(
                file_path=file_path,
                lemma=name,
                include_dir=include_dir,
                time_cap_sec=time_cap_sec,
                output_dir=output_dir,
                eval_mode=eval_mode,
            )
            results.append(r)
            print(f"  → {r.outcome} in {r.time_sec:.0f}s (tactics={r.tactic_count})")
            # Persist progress after each lemma — if the driver is killed
            # (Ctrl+C, OOM, host shutdown), the summary reflects work done
            # up to this point and the operator can resume with --only.
            _write_summary("in_progress")
    except KeyboardInterrupt:
        print(f"\n[project_driver] interrupted — saving partial summary", flush=True)
        summary = _write_summary("interrupted")
        raise
    except Exception:
        # Unexpected failure — still persist what we have before propagating
        _write_summary("interrupted")
        raise
    finally:
        # Stop the monitor on every exit path; otherwise it keeps appending
        # to progress_log.txt after an interrupt, making a dead run look live.
        stop_monitor.set()

    summary = _write_summary("done")

    print(f"\n{'='*60}")
    print(f"[project_driver] DONE: {summary['proved']}/{len(order)} proved")
    print(f"  timeout: {summary['timeout']}  failed: {summary['failed']}  crashed: {summary['crashed']}")
    print(f"  total wall-clock: {summary['total_time_min']:.1f} min")
    print(f"  summary: {summary_path}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--file", required=True,
                        help="Path to .ec file (relative to project root)")
    parser.add_argument("--include-dir", default="",
                        help="Include dir for easycrypt -I")
    parser.add_argument("--time-cap", type=int, default=900,
                        help="Per-lemma time cap in seconds (default: 900 = 15 min)")
    parser.add_argument("--eval-mode", action="store_true", default=False,
                        help="Blind prover to target lemma's cached proof")
    parser.add_argument("--output-dir", default=None,
                        help="Where to write per-lemma logs + summary.json")
    parser.add_argument("--only", nargs="+", default=None,
                        help="Restrict to these specific lemma names")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the dep graph / order and exit without running the prover")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    # Make `kill <pid>` on the driver unwind through the KeyboardInterrupt
    # path (partial-summary save + graceful orchestrator teardown) instead of
    # abruptly terminating and orphaning the in-flight orchestrator subtree.
    install_terminal_signal_handlers()

    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = _PROJECT_ROOT / file_path
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else None

    summary = run_project(
        file_path=file_path,
        include_dir=args.include_dir,
        time_cap_sec=args.time_cap,
        eval_mode=args.eval_mode,
        output_dir=output_dir,
        only_lemmas=args.only,
        dry_run=args.dry_run,
    )
    if summary.get("dry_run"):
        return 0
    return 0 if summary["crashed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
