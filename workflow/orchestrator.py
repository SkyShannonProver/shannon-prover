"""Orchestrator: main entry point for the multi-agent proof improvement workflow.

Usage:
    python -m workflow.orchestrator --file eval/examples/elgamal.ec --lemma ddh1_gb
    python -m workflow.orchestrator --config workflow/runs/my_run/config.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from workflow.schemas.config import RunConfig
from workflow.progress import (
    phase_start, phase_done, status, error as perror,
    pipeline_ui_init, pipeline_ui_phase, pipeline_ui_reset,
)
from workflow.surface_profiles import surface_profile_names

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("workflow.orchestrator")

# ---------------------------------------------------------------------------
# Agent dispatch functions
# ---------------------------------------------------------------------------


def run_prover(config: RunConfig, run_dir: Path):
    """Run the Prover agent. Returns ProverResult."""
    from workflow.agents.prover import run as run_prover_agent
    logger.info("PROVER: starting proof attempt for %s:%s", config.file, config.lemma)
    return run_prover_agent(
        file_path=config.file,
        lemma_name=config.lemma,
        include_dir=config.include_dir,
        model=config.prover.model,
        effort=config.prover.effort,
        max_turns=config.prover.max_total_tactics,
        timeout_minutes=config.prover.timeout_minutes,
        parallelism=config.prover.parallelism,
        warmup_seconds=config.prover.warmup_seconds,
        kill_gap_tactics=config.prover.kill_gap_tactics,
        kill_gap_idle_seconds=config.prover.kill_gap_idle_seconds,
        eval_mode=bool(getattr(config, "eval_mode", False)),
        surface_profile=getattr(config, "surface_profile", None),
        record_proof_bank=getattr(config, "record_proof_bank", None),
        resume_capsules=list(getattr(config, "resume_capsules", []) or []),
        resume_root_policy=getattr(config.prover, "resume_root_policy", "score"),
        run_dir=run_dir,
        mode=config.prover.mode,
        tree_initial_provers=config.prover.tree_initial_provers,
        tree_max_concurrent=config.prover.tree_max_concurrent,
        tree_stuck_errors=config.prover.tree_stuck_errors,
        tree_stuck_idle_seconds=config.prover.tree_stuck_idle_seconds,
        tree_grace_seconds=config.prover.tree_grace_seconds,
        tree_max_depth=config.prover.tree_max_depth,
        tree_min_alive_seconds=config.prover.tree_min_alive_seconds,
        tree_progress_gap_ratio=config.prover.tree_progress_gap_ratio,
        tree_progress_gap_idle=config.prover.tree_progress_gap_idle,
        tree_structural_undo_spawn_delay_seconds=(
            config.prover.tree_structural_undo_spawn_delay_seconds
        ),
        tree_undo_repair_protection_seconds=(
            config.prover.tree_undo_repair_protection_seconds
        ),
    )


def _restore_eval_env_on_exit(fn):
    """Restore EVAL_TARGET_LEMMA to its pre-call value on every exit path.

    Without this, a process that calls run() twice (tests, long-lived server)
    or a caller that sets EVAL_TARGET_LEMMA externally would see the env var
    bleed across runs. Fires on normal return, early return, or exception.
    """
    @functools.wraps(fn)
    def _wrapper(*args, **kwargs):
        prior = os.environ.get("EVAL_TARGET_LEMMA")
        try:
            return fn(*args, **kwargs)
        finally:
            if prior is None:
                os.environ.pop("EVAL_TARGET_LEMMA", None)
            else:
                os.environ["EVAL_TARGET_LEMMA"] = prior
    return _wrapper


def _prevent_sleep_on_macos() -> Optional[subprocess.Popen]:
    """Hold macOS awake for the lifetime of this orchestrator process.

    Fix for the 15-min "subagent silence" we observed on long eval runs:
    after ~12 min of activity the laptop hit idle sleep; both the
    orchestrator and the `claude -p` subagent were frozen by the OS for
    the remainder of the 20-min timeout. The trace file simply stopped
    because no process could run, not because anything was wrong.

    `caffeinate -dis -w <pid>` keeps the display/idle/disk awake and binds
    its own lifetime to the orchestrator's pid — when orchestrator exits
    (normal or crash), caffeinate auto-terminates. No cleanup needed.

    Returns the caffeinate Popen handle (for logging), or None on
    non-macOS / when caffeinate isn't available.
    """
    if sys.platform != "darwin":
        return None
    try:
        return subprocess.Popen(
            ["caffeinate", "-dis", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError) as e:
        logger.warning("caffeinate unavailable (%s); long runs may sleep", e)
        return None


def _duplicate_lemma_error(config: RunConfig) -> Optional[str]:
    """Error message if the target lemma is declared more than once, else None.

    Fails open on an unreadable target file — the EasyCrypt precheck and
    prover bootstrap produce their own, better errors for that case.
    """
    from core.easycrypt.lemma_decls import lemma_decl_lines

    try:
        content = (_PROJECT_ROOT / config.file).read_text(encoding="utf-8")
    except OSError:
        return None
    decl_lines = lemma_decl_lines(content, config.lemma)
    if len(decl_lines) <= 1:
        return None
    return (
        f"lemma '{config.lemma}' is declared {len(decl_lines)} times in "
        f"{config.file} (lines {', '.join(str(ln) for ln in decl_lines)}); "
        "the prover's name-based write-back and admit check cannot "
        "disambiguate which declaration is the target, so the run would be "
        "structurally unwinnable. Rename the duplicate or split the file so "
        "the target name is unique."
    )


@_restore_eval_env_on_exit
def run(config: RunConfig) -> dict:
    """Execute one managed proof-construction run.

    Single-pass. The old analyst/improver/regression/lab-note phases and their
    retry loop were removed; every run now measures raw proof-construction
    ability and stops after the prover. ``config.max_iterations`` is retained
    for config back-compat (it no longer drives a loop).
    """
    # ── Precheck: target lemma name must be unique in the target file ────
    # A duplicated lemma name is structurally unwinnable: the prover's
    # name-based write-back fills one declaration, then the post-verify
    # admit check resolves to the OTHER still-admitted declaration and
    # reverts a genuinely proved lemma (observed: xorK1 declared in both
    # Byte and GenBlock of ChaChaPoly/chacha_poly.ec, 2026-06-11). The eval
    # suite already fails fast at prepare; this guards direct
    # `python -m workflow.orchestrator --lemma NAME` runs. Fail before any
    # run artifacts are created.
    dup_error = _duplicate_lemma_error(config)
    if dup_error:
        perror("Orchestrator", dup_error)
        return {"error": dup_error}

    # Create run directory
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    run_name = f"{date_str}_{config.lemma}"
    run_dir = _PROJECT_ROOT / config.output_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    config.save(run_dir / "config.json")

    # Pin macOS awake for this run. Without this a laptop going to idle
    # sleep mid-run will freeze both the orchestrator and the `claude -p`
    # subagent; when the OS wakes, the wall-clock timeout fires
    # immediately and the subagent is killed before it can emit anything.
    # `caffeinate` self-terminates when our pid exits — no cleanup needed.
    _caff = _prevent_sleep_on_macos()
    if _caff is not None:
        status("Orchestrator",
               f"caffeinate -dis pinned awake (pid={_caff.pid})")

    # Eval mode: advertise the target lemma to subprocesses via env var so
    # prompt/rendering code can enforce target-lemma retrieval guards.
    if getattr(config, "eval_mode", False):
        os.environ["EVAL_TARGET_LEMMA"] = config.lemma
        # In eval mode we stop after the prover, so retries add no value.
        if config.max_iterations != 1:
            status("Orchestrator",
                   f"EVAL MODE: clamping max_iterations "
                   f"{config.max_iterations} → 1", "\033[35m")
            config.max_iterations = 1
        status("Orchestrator",
               f"EVAL MODE: blinding prover to concrete proofs of {config.lemma}",
               "\033[35m")
    else:
        os.environ.pop("EVAL_TARGET_LEMMA", None)

    # ── Precheck: verify EasyCrypt is available ──────────────────
    from core.easycrypt.ec_env import check_ec_available
    ec_ok, ec_msg = check_ec_available()
    if not ec_ok:
        perror("Orchestrator", f"EasyCrypt precheck failed: {ec_msg}")
        return {"error": ec_msg}

    run_start = time.time()
    print()
    status("Orchestrator", f"Starting run for {config.file}:{config.lemma}")
    status("Orchestrator", f"Run directory: {run_dir}")
    status("Orchestrator", f"Max prove attempts: {config.max_iterations}")
    if getattr(config, "resume_capsules", None):
        status("Orchestrator",
               f"Proof-node resume mode: "
               f"{len(config.resume_capsules)} resume capsule(s). "
               "Do not mix this result with from-scratch eval metrics.",
               "\033[35m")

    iteration_summaries = []
    # Single proof-construction pass. ``iteration`` stays 1: it still keys the
    # iteration_1/ run dir, the UI, and the summary records, but no longer
    # indexes a retry loop (the analyst/improver/regression retry was removed).
    iteration = 1
    pipeline_ui_init(config.lemma, config.file, iteration, iteration,
                     config.prover.mode)

    iter_dir = run_dir / f"iteration_{iteration}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    # ── Pre-check: is the lemma already proved? ──────────────
    from workflow.agents.prover import _precheck_lemma
    ec_full_path = _PROJECT_ROOT / config.file
    precheck = _precheck_lemma(ec_full_path, config.lemma,
                               include_dir=config.include_dir)
    if precheck == "proved_and_verified":
        status("Orchestrator",
               "Lemma already proved and verified. Skipping.",
               "\033[32m")
        iteration_summaries.append({
            "iteration": iteration, "proved": True,
            "has_improvements": False, "regression_ok": True,
            "resume_capsules": [],
        })
    else:
        # Search topology is explicit config, independent of the compiler
        # surface profile.  Defaults still use tree mode with two initial
        # provers; callers that want one node set tree_initial_provers=1.
        prove_mode = config.prover.mode
        prove_count = config.prover.tree_initial_provers

        # ── PROVE ───────────────────────────────────────────────────
        phase_start("PROVE")
        pipeline_ui_phase(1, "active",
                          f"{prove_mode} mode, {prove_count} provers")
        prover_result = run_prover(config, iter_dir)

        proved = prover_result.proved
        verified = prover_result.ec_file_verified
        elapsed_prove = prover_result.elapsed_seconds
        skipped = prover_result.skipped
        phase_done("PROVE",
                   f"proved={proved}, verified={verified}, time={elapsed_prove:.0f}s")
        result_str = "✅ proved" if proved and verified else ("⚠️ unverified" if proved else "❌ failed")
        pipeline_ui_phase(1, "done", f"{result_str}, {elapsed_prove:.0f}s")

        if skipped:
            # Already proved — nothing to do
            status("Orchestrator", "Lemma already proved and verified.", "\033[32m")
            iteration_summaries.append({
                "iteration": iteration, "proved": True,
                "has_improvements": False, "regression_ok": True,
                "resume_capsules": list(prover_result.resume_capsules or []),
            })
        else:
            session_id = prover_result.session_id
            (iter_dir / "session_id.txt").write_text(session_id, encoding="utf-8")
            iteration_summaries.append({
                "iteration": iteration, "proved": proved,
                "has_improvements": False, "regression_ok": True,
                "resume_capsules": list(prover_result.resume_capsules or []),
            })

    # ── Final summary ──────────────────────────────────────────────
    total_elapsed = time.time() - run_start
    final_proved = iteration_summaries[-1]["proved"] if iteration_summaries else False
    final_regression_ok = iteration_summaries[-1].get("regression_ok", True) if iteration_summaries else True

    generated_resume_capsules: list[str] = []
    for item in iteration_summaries:
        generated_resume_capsules.extend(list(item.get("resume_capsules") or []))

    summary = {
        "target": {"file": config.file, "lemma": config.lemma},
        "iterations": len(iteration_summaries),
        "final_proved": final_proved,
        "final_regression_ok": final_regression_ok,
        "total_elapsed_minutes": round(total_elapsed / 60, 1),
        "resume_capsules": list(getattr(config, "resume_capsules", []) or []),
        "generated_resume_capsules": generated_resume_capsules,
        "iteration_summaries": iteration_summaries,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8",
    )

    # ── Auto-build the committed agent-view bundle (resume-aware) ──────
    # Every orchestrator run — fresh OR resumed — emits its committed bundle
    # here, so a RESUME leaf produces ONE end-to-end report (the full proof +
    # the whole timeline stitched across the lineage) instead of only the
    # closing chunk. The lineage walk needs the live artifacts intact, which
    # they are at this point (before any worktree cleanup). Skipped when a suite
    # runner will bundle this run itself (it keeps the original source path);
    # best-effort either way — never fail the run.
    if not os.environ.get("SHANNON_SUITE_WILL_BUNDLE"):
        try:
            from workflow.validation.run_report_bundle import build_bundle
            _iter_dir = run_dir / f"iteration_{len(iteration_summaries) or 1}"
            if (_iter_dir / "node_memory").is_dir():
                _prover = getattr(config, "prover", None)
                _dest = build_bundle(
                    _iter_dir,
                    timestamp=run_dir.name,
                    lemma=config.lemma,
                    source_file=config.file,
                    model=getattr(_prover, "model", None),
                    profile=getattr(config, "surface_profile", None),
                    trees=getattr(_prover, "tree_initial_provers", None),
                    eval_mode=getattr(config, "eval_mode", False),
                )
                if _dest is not None:
                    status("Orchestrator", f"Agent-view bundle: {_dest}")
        except Exception as _exc:  # noqa: BLE001
            status("Orchestrator",
                   f"Agent-view bundle skipped ({type(_exc).__name__}: {_exc})")

    pipeline_ui_reset()  # restore normal terminal before final output
    phase_start("RUN COMPLETE")
    proved_str = "\033[32mYES\033[0m" if final_proved else "\033[31mNO\033[0m"
    reg_str = "" if final_regression_ok else " \033[31m(regression FAILED)\033[0m"
    status("Orchestrator",
           f"Iterations: {summary['iterations']}, Proved: {proved_str}{reg_str}, "
           f"Time: {total_elapsed / 60:.1f}min")
    status("Orchestrator", f"Summary: {run_dir / 'summary.json'}")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Run the multi-agent proof improvement workflow"
    )
    parser.add_argument("--config", type=Path, help="Path to config.json")
    parser.add_argument("--file", type=str,
                        help="EC file path (relative to project root)")
    parser.add_argument("--lemma", type=str, help="Lemma name")
    parser.add_argument("--include-dir", type=str, default="",
                        help="EC include directory")
    parser.add_argument("--human-proof-dir", type=str, default=None)
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Max prove failures before stopping (default: 2)")
    parser.add_argument("--prover-effort", type=str, default=None,
                        help="Reasoning effort for the prover Claude session "
                             "(low/medium/high; default from ProverConfig).")
    parser.add_argument("--prover-model", type=str, default=None,
                        help="Override the prover model")
    parser.add_argument("--eval-mode", action="store_true",
                        help="Blind the prover to the target lemma's existing proof: "
                             "prompt/rendering code blocks cached/prior proof "
                             "retrieval for the target lemma.")
    parser.add_argument("--surface-profile",
                        dest="surface_profile",
                        choices=surface_profile_names(include_unsupported=False),
                        help="Paper-eval proof-state surface profile. "
                             "Profiles hide selected proof-state compiler "
                             "surfaces while keeping verifier behavior fixed.")
    parser.add_argument("--prover-mode",
                        choices=["tree"],
                        default=None,
                        help="Proof-search topology mode. Currently `tree`.")
    parser.add_argument("--tree-initial-provers", type=int, default=None,
                        help="Number of root proof nodes to start in tree mode.")
    parser.add_argument("--tree-max-concurrent", type=int, default=None,
                        help="Maximum concurrently active proof nodes in tree mode.")
    parser.add_argument("--record-proof-bank", action="store_true",
                        help="Opt in to writing successful eval/live-smoke proofs "
                             "to workflow/proof_bank.jsonl. By default those "
                             "runs do not modify the proof bank.")
    parser.add_argument("--resume-capsule", action="append", default=[],
                        help="Resume from a proof-node resume capsule "
                             "manifest or capsule directory. May be passed "
                             "multiple times; resumed runs are continuation "
                             "experiments and should not be mixed with "
                             "from-scratch eval metrics.")
    parser.add_argument("--resume-root-policy",
                        choices=["score", "diversity"],
                        default=None,
                        help="Ordering policy for multiple resume capsules. "
                             "`score` preserves current behavior; `diversity` "
                             "interleaves route families using capsule route "
                             "diversity evidence.")
    parser.add_argument("--prover-timeout-minutes", type=int, default=None,
                        help="Override the prover's internal timeout (default: "
                             "config.prover.timeout_minutes = 20). Increase when "
                             "your driver's per-lemma cap is larger than 20 min — "
                             "otherwise the prover hits 20-min and dies even if "
                             "the driver cap allows more. Observed failure: "
                             "ChaChaPoly step1 Run 5 was 90%% done at minute 20:00 "
                             "but hit the 20-min prover cap before closing.")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Override RunConfig.output_dir for suite runners.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Make `kill <pid>` (SIGTERM) unwind like Ctrl-C so prover.run's and
    # run_tree_prover's cleanup finally blocks run — they reap the detached
    # tree workers, why3server, and the EasyCrypt daemon. Without this a
    # plain SIGTERM (how a driver/operator stops a wedged run) orphans the
    # whole worker subtree to PID 1.
    from workflow.proc_lifecycle import install_terminal_signal_handlers
    install_terminal_signal_handlers()

    # Flag a typo'd SHANNON_* knob NAME (e.g. SHANNON_DISABLE_PORBE) loudly —
    # it would otherwise have no effect and silently corrupt an ablation arm.
    from core.env_loader import warn_unknown_shannon_env
    warn_unknown_shannon_env()

    if args.config:
        config = RunConfig.load(args.config)
    elif args.file and args.lemma:
        config = RunConfig(
            file=args.file,
            lemma=args.lemma,
            include_dir=args.include_dir or "",
            human_proof_dir=args.human_proof_dir,
        )
    else:
        parser.error("Either --config or (--file and --lemma) required")

    if args.max_iterations is not None:
        config.max_iterations = args.max_iterations
    if args.prover_model:
        config.prover.model = args.prover_model
    if args.prover_effort:
        config.prover.effort = args.prover_effort
    if args.eval_mode:
        config.eval_mode = True
    if args.surface_profile:
        config.surface_profile = args.surface_profile
    if args.prover_mode:
        config.prover.mode = args.prover_mode
    if args.tree_initial_provers is not None:
        config.prover.tree_initial_provers = args.tree_initial_provers
    if args.tree_max_concurrent is not None:
        config.prover.tree_max_concurrent = args.tree_max_concurrent
    if args.record_proof_bank:
        config.record_proof_bank = True
    resume_capsule_args = list(args.resume_capsule or [])
    if resume_capsule_args:
        config.resume_capsules = resume_capsule_args
    if args.resume_root_policy:
        config.prover.resume_root_policy = args.resume_root_policy
    if args.prover_timeout_minutes is not None:
        config.prover.timeout_minutes = args.prover_timeout_minutes
    if args.output_dir:
        config.output_dir = args.output_dir

    run(config)


if __name__ == "__main__":
    main()
