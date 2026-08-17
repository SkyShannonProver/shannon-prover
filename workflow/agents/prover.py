"""Prover agent: prove an EasyCrypt lemma using a managed agent process.

Launches either Claude Code or OpenAI Codex with a task-specific prompt. The
agent has read-only source-inspection tools, while EasyCrypt proof interaction
goes through the managed ProofNodeManager intent protocol.

Claude Code traces are correlated through ``agent_sessions.jsonl``. Codex runs
emit their thread id through the same provider-neutral session registry.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from workflow.schemas.config import PROVER_DEFAULTS, normalize_agent_backend
from workflow.agents.ec_services import (  # noqa: F401  (facade re-exports)
    _AF_UNIX_SOCKET_PATH_LIMIT,
    _EC_DAEMON_SOCKET_NAME_TEMPLATE,
    _RUN_WHY3_PROC,
    _RUN_WHY3_SOCKET,
    _claude_scratch_path,
    _cleanup_stale_why3server,
    _configure_run_ec_daemon_socket,
    _configure_run_why3_socket,
    _ec_daemon_socket_path,
    _ec_daemon_socket_responsive,
    _ensure_why3server,
    _fallback_ec_daemon_socket_root,
    _get_opam_env,
    _git_common_project_root,
    _hard_kill_ec_daemon,
    _is_why3server_responsive,
    _path_fits_af_unix_socket,
    _remove_stale_ec_daemon_socket,
    _resolve_why3server_binary,
    _run_ec_daemon_socket_root,
    _shutdown_ec_daemon,
    _shutdown_repo_ec_daemons,
    _shutdown_run_why3server,
    _workspace_tmp_dir,
)
from workflow.agents.prover_writeback import (  # noqa: F401  (facade re-exports)
    _ADMIT_TOKEN_RE,
    _EC_SPINNER_RE,
    _build_proof_text,
    _distill_ec_stderr,
    _emit_verification_status,
    _extract_partial_tactics_from_sessions,
    _extract_prover_notes,
    _extract_prover_report,
    _extract_tactics_from_candidate,
    _find_proof_block,
    _first_err_msg,
    _has_why3_error,
    _parse_ec_error_line,
    _proof_body_has_admit,
    _prune_failing_tactics,
    _resolve_lemma_decl_start,
    _scratch_line_to_tactic_idx,
    _strip_comments_for_admit_check,
    _tactics_contain_admit,
    _verify_ec_file,
    _verify_extracted_file,
    _verify_lemma_extracted,
    _write_and_verify_proof,
)
from workflow.proof_state_compiler.runtime_profiles import (
    ensure_supported_runtime_surface_profile,
)
from workflow.proof_management.lifecycle import (
    replay_prefix_shortfall,
    require_proof_node_manager_bootstrap,
)
from workflow.proof_node_manager import ProofNodeManager
from workflow.tree.policy import DEFAULT_TREE_INITIAL_PROVERS, cap_tree_max_concurrent
from workflow.tree.result import TreeRunResult
from workflow.agents.prover_prompt import (
    _build_child_prover_prompt,
    _build_prover_prompt,
)

logger = logging.getLogger("workflow.agents.prover")


def _prepare_run_ec_daemon_socket(run_dir: Path) -> tuple[str, bool]:
    """Select this run's socket and clean only an older instance of it.

    Worktrees share the git-common ``tmp/ec_daemons`` directory.  Scanning and
    stopping every socket there makes one evaluation arm terminate another
    arm's live daemon.  The run directory already gives each arm a stable,
    distinct socket name, so only that exact socket is stale for this run.
    """
    socket_path = _configure_run_ec_daemon_socket(run_dir)
    stopped = _shutdown_ec_daemon(
        reason="per-run pre-run cleanup",
        socket_path=socket_path,
    )
    return socket_path, stopped


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# why3server we started for THIS run (per-run socket, see
# _configure_run_why3_socket). Held so the run can tear it down at the end
# instead of leaking it for the next run's global pkill to find. None when no
# server was started by us (e.g. a responsive one was already running).

def _append_manager_bootstrap_audit(
    run_dir: Path | None,
    record: dict[str, Any],
) -> None:
    if run_dir is None:
        return
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "manager_session_bootstrap.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception as exc:
        logger.warning("Failed to write manager bootstrap audit: %s", exc)


def _bootstrap_opened_real_proof(
    bootstrap: dict[str, Any],
    *,
    surface_profile: str | None = None,
) -> bool:
    """True unless the managed session clearly failed to open the target proof.

    When a file fails to load (e.g. a `require`d theory is missing) EC stays at
    top level with no open proof: the projected view shows ``status`` of
    ``unknown``/``error`` and EC never reports a remaining-goal count, while the
    "goal" is just the bare ``[N|check]>`` prompt. A healthy open *or* complete
    proof always carries an authoritative count (``remaining_goals_known``).

    The bootstrap envelope and required proof-status signal are strict. A
    malformed handoff raises before this semantic hollow-state check runs.
    """
    require_proof_node_manager_bootstrap(
        bootstrap,
        surface_profile=surface_profile,
    )
    view = bootstrap["workspace_view"]
    ps = view["proof_status"]
    if ps.get("remaining_goals_known") is True:
        return True  # EC gave a goal count (open or complete) — real proof
    status = str(ps.get("status") or "")
    if status not in ("unknown", "error"):
        return True
    cg = view.get("current_goal") or {}
    lines = cg.get("lines") or []
    has_real_goal = any(
        str(ln).strip() and "check]>" not in str(ln) for ln in lines
    )
    return bool(has_real_goal)


def _warn_replay_prefix_shortfall(
    bootstrap: dict[str, Any],
    *,
    node_label: str,
) -> None:
    """Loud operator warning when a resume restored far fewer tactics than
    requested (divergence rollback during prefix replay). The detail lives in
    the bootstrap record; this is the headline so a "restored 24/90" never
    again hides inside a JSON blob (observed 2026-06-11, upto_X1_X2)."""
    shortfall = bootstrap.get("replay_prefix_shortfall")
    if not isinstance(shortfall, dict) or not shortfall:
        return
    from workflow.progress import status as pstatus

    requested = shortfall.get("requested")
    committed = shortfall.get("committed")
    pct = round(float(shortfall.get("lost_ratio") or 0.0) * 100)
    first_index = shortfall.get("first_dropped_index")
    first_tactic = str(shortfall.get("first_dropped_tactic") or "").strip()
    if len(first_tactic) > 120:
        first_tactic = first_tactic[:117].rstrip() + "..."
    where = (
        f"; first dropped step #{first_index}: `{first_tactic}`"
        if first_tactic else
        ""
    )
    pstatus(
        "Orchestrator",
        f"⚠ RESUME PREFIX SHORTFALL on {node_label or 'node'}: restored "
        f"{committed}/{requested} recorded tactics (lost {pct}%){where}. "
        f"See replay_prefix_divergence in this node's manager bootstrap "
        f"record.",
        "\033[31m",
    )


def _prepare_managed_session(
    *,
    file_path: str,
    lemma_name: str,
    include_dir: str,
    session_tag: str,
    replay_prefix: list[str] | None = None,
    run_dir: Path | None = None,
    node_label: str = "",
    surface_profile: str | None = None,
    resume_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start/replay the EasyCrypt session before the prover agent launches.

    This is the manager-owned lifecycle boundary: the agent receives an already
    live session plus the exact ProverWorkspaceView at handoff.
    """
    backend_path = _PROJECT_ROOT / "core" / "easycrypt" / "session_cli.py"
    if not backend_path.exists():
        raise RuntimeError(
            "Managed proof backend is unavailable: required session driver "
            f"does not exist at {backend_path}. Refusing to manufacture a "
            "bootstrap without an authoritative EasyCrypt session."
        )

    manager = ProofNodeManager(
        file_path=file_path,
        lemma_name=lemma_name,
        include_dir=include_dir,
        session_tag=session_tag,
        node_id=node_label or session_tag,
        run_dir=run_dir,
        project_root=_PROJECT_ROOT,
        surface_profile=surface_profile,
    )
    bootstrap = manager.bootstrap(
        replay_prefix=replay_prefix or [],
        resume_context=resume_context,
    )
    require_proof_node_manager_bootstrap(
        bootstrap,
        surface_profile=manager.surface_profile,
        expected_identity={
            "node_id": node_label or session_tag,
            "session_tag": session_tag,
            "session_dir": f".ec_session_{session_tag}",
            "file": file_path,
            "lemma": lemma_name,
        },
    )
    _warn_replay_prefix_shortfall(bootstrap, node_label=node_label)
    _append_manager_bootstrap_audit(run_dir, bootstrap)
    if (
        os.environ.get("SHANNON_SKIP_BOOTSTRAP_GUARD") != "1"
        and not _bootstrap_opened_real_proof(
            bootstrap,
            surface_profile=manager.surface_profile,
        )
    ):
        raise RuntimeError(
            f"Managed session did not open a proof for lemma '{lemma_name}' in "
            f"{file_path}: EC reports no goal, which almost always means the "
            f"file failed to load (e.g. a missing `require`d theory). Refusing "
            f"to launch the prover against a session with no open proof — that "
            f"would be a 'hollow run' where every tactic errors 'outside a "
            f"proof script'. Set SHANNON_SKIP_BOOTSTRAP_GUARD=1 to override."
        )
    return bootstrap


def _archive_ec_session_dirs(
    run_dir: Path,
    *,
    session_dirs: tuple[str, ...] | list[str],
) -> list[str]:
    """Copy this prover run's EasyCrypt session dirs into ``run_dir``.

    ``prover.run`` wipes project-root ``.ec_session_*`` directories at the
    start of the next run to prevent proof leakage. Without this archive, the
    event log and generated workspace / TacticExecutionResult artifacts vanish
    before postmortem analysis can inspect them.
    """
    import shutil as _shutil

    candidates = {
        Path(value).resolve()
        for value in session_dirs
        if str(value).strip() and Path(value).is_dir()
    }

    if not candidates:
        return []

    archive_root = run_dir / "ec_sessions"
    archive_root.mkdir(parents=True, exist_ok=True)
    archived: list[str] = []
    manifest: list[dict] = []

    for src in sorted(candidates, key=lambda p: str(p.resolve())):
        dest = archive_root / src.name
        try:
            if dest.exists():
                _shutil.rmtree(dest, ignore_errors=True)
            _shutil.copytree(
                src,
                dest,
                ignore=_shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            file_count = sum(1 for p in dest.rglob("*") if p.is_file())
            archived.append(str(dest.resolve()))
            manifest.append({
                "source": str(src.resolve()),
                "archive": str(dest.resolve()),
                "files": file_count,
            })
        except Exception as e:
            logger.warning("Failed to archive EC session %s: %s", src, e)

    if manifest:
        (archive_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
    return archived


# ---------------------------------------------------------------------------
# Pre-check: does the lemma already have a proof?
# ---------------------------------------------------------------------------

# Match a lemma declaration followed by its proof block (proof. ... qed.)
# or just admit.
_LEMMA_PROOF_RE_TEMPLATE = (
    r"((?:local\s+)?(?:lemma|theorem)\s+{lemma}\b[^.]*\.)"  # declaration
    r"\s*"
    r"(proof\.\s*(?:(?!(?:^(?:local\s+)?(?:lemma|theorem|axiom)\s))[\s\S])*?qed\."  # full proof
    r"|admit\.)"  # or just admit
)




































def _precheck_lemma(ec_path: Path, lemma_name: str, include_dir: str = "") -> str:
    """Check the state of a lemma in the .ec file.

    Returns:
        "has_admit"             — lemma has `admit.` (normal case, go prove)
        "proved_and_verified"   — lemma has a real proof and file verifies
        "has_proof_but_fails"   — lemma has a real proof but file doesn't verify
        "not_found"             — lemma not found in file
    """
    if not ec_path.exists():
        return "not_found"

    content = ec_path.read_text(encoding="utf-8")

    # Check if the lemma exists.
    # When multiple lemmas share the same name (e.g., inside/outside section),
    # prefer the one that needs proving (has admit or empty proof).
    lemma_re = re.compile(
        r"(?:local\s+)?(?:lemma|theorem)\s+" + re.escape(lemma_name) + r"(?=[\s:(\[]|$)",
    )
    all_matches = list(lemma_re.finditer(content))
    if not all_matches:
        return "not_found"

    def _match_needs_proving(m):
        after = content[m.end():m.end() + 500]
        return bool(re.search(r'\badmit\b', after[:300])) or \
               bool(re.search(r'proof\.\s*(?:\(\*.*?\*\)\s*)?qed\.', after[:300], re.DOTALL))

    # Prefer the match that needs proving; fall back to last match
    decl_match = next((m for m in all_matches if _match_needs_proving(m)), all_matches[-1])
    decl_pos = decl_match.start()

    # Find the proof body: text between "proof." and "qed." for this lemma.
    # Using index('.') is fragile (matches dots inside expressions like A).main()).
    # Instead, find the "proof." keyword explicitly.
    after_decl = content[decl_pos:]
    proof_kw = re.search(r'\bproof\.', after_decl)
    if not proof_kw:
        return "not_found"
    proof_body = after_decl[proof_kw.end():]

    # Check if the proof body contains admit or is empty (before the qed)
    qed_match = re.search(r'\bqed\.', proof_body)
    if qed_match:
        body_to_qed = proof_body[:qed_match.start()]
        if re.search(r'\badmit\b', body_to_qed):
            return "has_admit"
        # Detect empty proofs: only whitespace/comments between proof. and qed.
        stripped = re.sub(r'\(\*.*?\*\)', '', body_to_qed, flags=re.DOTALL)
        if not stripped.strip():
            return "has_admit"
    elif re.search(r'\badmit\.', proof_body[:500]):
        return "has_admit"

    # Has a real proof (no admit before qed) — verify the file
    ok, stderr = _verify_ec_file(ec_path, include_dir=include_dir)
    if ok:
        return "proved_and_verified"

    # Full-file failed — always try extracted verification as fallback
    logger.info("Full-file verification failed; trying extracted lemma verification")
    if _verify_lemma_extracted(ec_path, lemma_name, include_dir=include_dir):
        return "proved_and_verified"

    return "has_proof_but_fails"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run(
    file_path: str,
    lemma_name: str,
    include_dir: str = "",
    agent_backend: str = PROVER_DEFAULTS.agent_backend,
    model: str = PROVER_DEFAULTS.model,
    effort: str = PROVER_DEFAULTS.effort,
    max_turns: int = 1000,
    timeout_minutes: int = 20,
    parallelism: int = 1,
    warmup_seconds: int = 180,
    kill_gap_tactics: int = 2,
    kill_gap_idle_seconds: int = 60,
    run_dir: Optional[Path] = None,
    eval_mode: Optional[bool] = None,
    surface_profile: str | None = None,
    resume_capsules: Optional[list[str]] = None,
    resume_root_policy: str = "score",
    mode: str = "tree",
    # Tree mode params (only used when mode == "tree")
    tree_initial_provers: int = DEFAULT_TREE_INITIAL_PROVERS,
    tree_max_concurrent: int = 4,
    tree_stuck_errors: int = PROVER_DEFAULTS.tree_stuck_errors,
    tree_stuck_idle_seconds: int = 120,
    tree_grace_seconds: int = 120,
    tree_max_depth: int = PROVER_DEFAULTS.tree_max_depth,
    tree_min_alive_seconds: int = 60,
    tree_progress_gap_ratio: float = 1.5,
    tree_progress_gap_idle: int = 60,
    tree_structural_undo_spawn_delay_seconds: int = 300,
    tree_undo_repair_protection_seconds: int = 900,
):
    """Run the prover as a managed Claude Code or OpenAI Codex agent.

    The selected agent process receives the proving prompt and uses the
    manager intent protocol for EasyCrypt proof interaction, Read/Bash for
    legitimate source context, and never owns session lifecycle.

    Long-lived managed prover mode:
    - "tree": Start one or more proof nodes, each with its own long-lived
      agent runtime.
    """
    agent_backend = normalize_agent_backend(agent_backend)
    from workflow.schemas.prover_result import (
        PROVER_RUN_INCOMPLETE,
        PROVER_RUN_INFRASTRUCTURE_INVALID,
        PROVER_RUN_VERIFIED,
        ProverResult,
    )
    profile = ensure_supported_runtime_surface_profile(surface_profile)
    if profile is not None:
        surface_profile = profile.name
    run_dir = run_dir or (_PROJECT_ROOT / "workflow" / "runs" / "scratch")
    run_dir.mkdir(parents=True, exist_ok=True)

    from workflow.progress import status as pstatus, error as perror

    run_ec_daemon_socket, stopped_previous_run_daemon = (
        _prepare_run_ec_daemon_socket(run_dir)
    )
    if stopped_previous_run_daemon:
        pstatus(
            "Prover",
            "Stopped an older EasyCrypt daemon for this exact run",
        )
    logger.info("Using per-run EasyCrypt daemon socket: %s", run_ec_daemon_socket)

    # --- Pre-check: does the lemma already have a proof? ---
    ec_full_path = _PROJECT_ROOT / file_path
    precheck = _precheck_lemma(ec_full_path, lemma_name, include_dir=include_dir)

    if precheck == "proved_and_verified":
        pstatus("Prover", f"{lemma_name} already has a verified proof. Skipping.", "\033[32m")
        result = ProverResult(
            status=PROVER_RUN_VERIFIED,
            skipped=True,
            verification={
                "status": "pass",
                "method": "preexisting_source_verification",
                "target_file": str(ec_full_path.resolve()),
                "target_lemma": lemma_name,
            },
        )
        result.save(run_dir / "prover_run_result.json")
        return result

    if precheck == "has_proof_but_fails":
        pstatus("Prover",
                f"{lemma_name} has a proof but it doesn't verify. "
                f"Replacing with admit and re-proving.", "\033[33m")
        from core.easycrypt.eval_source_prep import replace_target_proof_with_admit

        if replace_target_proof_with_admit(ec_full_path, lemma_name):
            logger.info("Replaced proof of %s with admit.", lemma_name)
        else:
            logger.warning("Could not find proof block for %s to replace.", lemma_name)

    # If precheck == "has_admit", normal flow — go prove it.
    resume_capsules = list(resume_capsules or [])
    loaded_resume_capsules = []
    if resume_capsules:
        from workflow.proof_node_resume import load_resume_capsules

        loaded_resume_capsules = load_resume_capsules(
            resume_capsules,
            policy=resume_root_policy,
        )
        for ckpt in loaded_resume_capsules:
            if ckpt.target_file and ckpt.target_file != file_path:
                raise ValueError(
                    f"resume capsule target file mismatch: "
                    f"{ckpt.path} has {ckpt.target_file}, run targets {file_path}"
                )
            if ckpt.lemma and ckpt.lemma != lemma_name:
                raise ValueError(
                    f"resume capsule lemma mismatch: "
                    f"{ckpt.path} has {ckpt.lemma}, run targets {lemma_name}"
                )
        tree_initial_provers = max(
            tree_initial_provers,
            len(loaded_resume_capsules),
        )
        tree_max_concurrent = max(
            tree_max_concurrent,
            len(loaded_resume_capsules),
        )
        pstatus(
            "Prover",
            f"Proof-node resume mode: {len(loaded_resume_capsules)} "
            f"resume capsule(s), root policy={resume_root_policy}. "
            "Results are not from-scratch eval.",
            "\033[35m",
        )

    if eval_mode is None:
        eval_mode = os.environ.get("EVAL_TARGET_LEMMA", "").strip() == lemma_name
    if eval_mode:
        os.environ["EVAL_TARGET_LEMMA"] = lemma_name
    elif os.environ.get("EVAL_TARGET_LEMMA", "").strip() == lemma_name:
        os.environ.pop("EVAL_TARGET_LEMMA", None)

    # --- Pre-flight: start from a clean persistent EC daemon. ---
    if _shutdown_ec_daemon(reason="pre-run cleanup"):
        pstatus("Prover", "Stopped stale EasyCrypt daemon from a previous run")

    # --- Pre-flight: ensure why3server is running for smt() ---
    # Per-run socket first so this run (and concurrent eval arms) get isolated
    # servers; the started server is tracked and torn down in the finally below.
    run_why3_socket = _configure_run_why3_socket(run_dir)
    logger.info("Using per-run why3server socket: %s", run_why3_socket)
    why3_socket = _ensure_why3server()
    if why3_socket:
        pstatus("Prover", f"why3server ready on {why3_socket}")
    else:
        pstatus("Prover", "why3server not available — smt() will fail. Continuing anyway.", "\033[33m")

    # Clean up ALL stale session directories at the project root before
    # each prover launch. Any `.ec_session_*` dir left over from a previous
    # run contains a `history.ec` file with tactics that the prover can
    # read (via Glob/Read) and transcribe — effectively a cross-run proof
    # leak. Observed in ChaChaPoly Run 8 step1: prover found .ec_session_
    # step1b/history.ec (64 lines of a prior partial proof) and started
    # copying its tactics verbatim after getting stuck.
    #
    # Prior cleanup only handled dirs matching `prover_<lemma>_<i>` — the
    # current run's own naming. Dirs from manual testing or runs with
    # different naming schemes (step1b, step1_v2, step4_1_final, ...) were
    # NOT cleaned. The fix: wipe every `.ec_session_*` at project root.
    # This is safe because each lemma's session dirs are spawned fresh
    # by the prover we're about to launch.
    import shutil as _shutil
    session_root = _PROJECT_ROOT
    wiped = 0
    try:
        for p in session_root.glob(".ec_session_*"):
            if p.is_dir():
                _shutil.rmtree(p, ignore_errors=True)
                wiped += 1
            elif p.is_file() and p.name.endswith(".cli.lock"):
                # session_cli's flock files (`.ec_session_*.cli.lock`) are never
                # unlinked by their creator and match this glob; sweep them too
                # or they pile up in the repo root (237 observed) and bloat this
                # glob every run (audit §8 #14).
                p.unlink(missing_ok=True)
                wiped += 1
    except Exception as e:
        logger.warning("Session cleanup error (non-fatal): %s", e)
    if wiped:
        logger.info(
            "Wiped %d stale .ec_session_* directories at %s (cross-run leak "
            "prevention).", wiped, session_root,
        )

    if mode != "tree":
        raise ValueError("unsupported prover mode; only 'tree' is current")

    tree_max_concurrent = cap_tree_max_concurrent(tree_max_concurrent)
    tree_initial_provers = max(1, min(int(tree_initial_provers), tree_max_concurrent))

    from workflow.progress import status as pstatus

    start_time = time.time()

    if mode == "tree":
        # --- Tree mode: recursive branch-and-explore ---
        from workflow.progress import run_tree_prover
        resume_initial_branches = []
        if loaded_resume_capsules:
            try:
                current_commit = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(_PROJECT_ROOT),
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            except Exception:
                current_commit = ""
            for ckpt in loaded_resume_capsules:
                if ckpt.commit and current_commit and ckpt.commit != current_commit:
                    pstatus(
                        "Prover",
                        f"Checkpoint {ckpt.path} was captured at "
                        f"{ckpt.commit[:12]}, current commit is "
                        f"{current_commit[:12]}; replay will verify whether "
                        "the prefix still reaches the same state.",
                        "\033[33m",
                    )
                capsule_shortfall = replay_prefix_shortfall(
                    ckpt.recorded_tactic_count, ckpt.tactic_count,
                )
                if capsule_shortfall is not None:
                    pstatus(
                        "Orchestrator",
                        f"⚠ RESUME CAPSULE SHORTFALL: {ckpt.path} records "
                        f"tactic_count={ckpt.recorded_tactic_count} but its "
                        f"history.ec only yields {ckpt.tactic_count} replayable "
                        f"tactics (lost "
                        f"{round(capsule_shortfall['lost_ratio'] * 100)}%). "
                        f"The capsule is internally inconsistent; the resume "
                        f"starts from the shorter prefix.",
                        "\033[31m",
                    )
                handoff_notes = "\n".join(
                    f"- {note}" for note in ckpt.handoff_notes
                )
                recent_window_lines = []
                for item in ckpt.recent_tactics[-8:]:
                    status = str(item.get("status") or "unknown")
                    before = item.get("goals_before")
                    after = item.get("goals_after")
                    tactic = str(item.get("tactic") or "").strip()
                    if len(tactic) > 180:
                        tactic = tactic[:177].rstrip() + "..."
                    goal_delta = (
                        f" goals {before}->{after}"
                        if before is not None and after is not None else
                        ""
                    )
                    recent_window_lines.append(
                        f"- {status}{goal_delta}: {tactic}"
                    )
                recent_window = "\n".join(recent_window_lines)
                tail_hints = (
                    "\n\nResume handoff notes:\n"
                    f"{handoff_notes}\n"
                    if handoff_notes else
                    ""
                )
                parent_goal_state = (
                    f"Resume capsule: {ckpt.path}\n"
                    f"source session: {ckpt.session_name}\n"
                    f"accepted prefix tactics: {ckpt.tactic_count}\n"
                    f"capsule score: {ckpt.score}\n"
                    f"resume root policy: {resume_root_policy}\n"
                    f"route family: {ckpt.route_family or 'unknown'}\n"
                    f"score reasons: {', '.join(ckpt.reasons)}\n"
                    f"current goal hash: {ckpt.current_goal_hash}\n\n"
                    + (
                        "Resume handoff notes:\n"
                        f"{handoff_notes}\n\n"
                        if handoff_notes else
                        ""
                    )
                    + (
                        "Recent tactic window before capsule:\n"
                        f"{recent_window}\n\n"
                        if recent_window else
                        ""
                    )
                    +
                    f"{ckpt.current_goal_preview}"
                    f"{tail_hints}"
                )
                resume_initial_branches.append({
                    "replay_prefix": ckpt.replay_prefix,
                    "resume_context": ckpt.resume_context,
                    "negative_signal": [],
                    "parent_goal_state": parent_goal_state,
                    "expected_goal_hash": ckpt.current_goal_hash,
                    "goal_identity_required": ckpt.goal_identity_required,
                    "capsule_path": str(ckpt.path),
                    "capsule_score": ckpt.score,
                    "resume_root_policy": resume_root_policy,
                    "resume_diversity": dict(ckpt.resume_diversity or {}),
                    "route_family": {
                        "family": ckpt.route_family,
                    } if ckpt.route_family else {},
                })

        def _build_tree_cmd(session_tag, node_id, replay_prefix, negative_signal,
                            layer_move_action=None, resume_context=None):
            managed_session = _prepare_managed_session(
                file_path=file_path,
                lemma_name=lemma_name,
                include_dir=include_dir,
                session_tag=session_tag,
                replay_prefix=list(replay_prefix or []),
                run_dir=run_dir,
                node_label=f"Tree-{node_id}",
                surface_profile=surface_profile,
                resume_context=(
                    resume_context if isinstance(resume_context, dict) else None
                ),
            )
            if replay_prefix:
                prompt = _build_child_prover_prompt(
                    file_path, lemma_name, include_dir,
                    session_tag,
                    layer_move_action=layer_move_action,
                    managed_session=managed_session,
                    surface_profile=surface_profile,
                )
            else:
                prompt = _build_prover_prompt(
                    file_path, lemma_name, include_dir,
                    session_tag=session_tag,
                    managed_session=managed_session,
                    surface_profile=surface_profile,
                )
            prompt_path = run_dir / "prover_prompt.md"
            node_slug = str(node_id).replace(".", "_")
            node_prompt_path = run_dir / f"prover_prompt_{node_slug}.md"
            node_bootstrap_path = run_dir / f"manager_bootstrap_{node_slug}.json"
            node_prompt_path.write_text(prompt, encoding="utf-8")
            node_bootstrap_path.write_text(
                json.dumps(managed_session, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            if node_id in {"root", "0.0"} or not prompt_path.exists():
                prompt_path.write_text(prompt, encoding="utf-8")
            return [
                sys.executable,
                "-m",
                "workflow.managed_prover_worker",
                "--prompt-file",
                str(node_prompt_path),
                "--bootstrap-file",
                str(node_bootstrap_path),
                "--file",
                file_path,
                "--lemma",
                lemma_name,
                "--include-dir",
                include_dir,
                "--session-tag",
                session_tag,
                "--node-id",
                f"Tree-{node_id}",
                "--run-dir",
                str(run_dir),
                "--agent-backend",
                agent_backend,
                "--model",
                model,
                "--effort",
                effort,
                "--max-turns",
                str(max_turns),
                "--surface-profile",
                surface_profile or "",
            ]

        pstatus("Prover", f"Tree mode for {lemma_name} "
                f"(agent={agent_backend}, model={model}, "
                f"timeout={timeout_minutes}min, "
                f"initial_roots={tree_initial_provers}, "
                f"max_concurrent={tree_max_concurrent})")
        try:
            tree_result = run_tree_prover(
                build_cmd_fn=_build_tree_cmd,
                cwd=str(_PROJECT_ROOT),
                timeout=timeout_minutes * 60,
                max_concurrent=tree_max_concurrent,
                initial_provers=tree_initial_provers,
                stuck_errors=tree_stuck_errors,
                stuck_idle_seconds=tree_stuck_idle_seconds,
                grace_seconds=tree_grace_seconds,
                max_depth=tree_max_depth,
                min_alive_seconds=tree_min_alive_seconds,
                progress_gap_ratio=tree_progress_gap_ratio,
                progress_gap_idle=tree_progress_gap_idle,
                structural_undo_spawn_delay_seconds=(
                    tree_structural_undo_spawn_delay_seconds
                ),
                undo_repair_protection_seconds=(
                    tree_undo_repair_protection_seconds
                ),
                source_file=str(file_path),
                target_lemma=lemma_name,
                initial_branches=resume_initial_branches or None,
                payload_audit_path=run_dir / "payload_audit.jsonl",
            )
        except Exception as exc:  # terminal owner records infrastructure failure
            logger.exception("Tree search failed before producing a typed result")
            tree_result = TreeRunResult(
                returncode=1,
                infrastructure_errors=(
                    f"tree search failed: {type(exc).__name__}: {exc}",
                ),
                payload_audit_path=str(run_dir / "payload_audit.jsonl"),
            )
        finally:
            if _shutdown_ec_daemon(reason="tree prover finished"):
                pstatus("Prover", "Stopped EasyCrypt daemon after tree prover")
            _shutdown_run_why3server()
        output_text = tree_result.output_text
        returncode = tree_result.returncode
        winner_node = tree_result.selected_node_id
        pstatus("Prover", f"Selected tree result: Tree-{winner_node}")

    stdout = output_text
    stderr = ""
    elapsed = time.time() - start_time

    # Save raw output
    output_text = stdout or ""
    (run_dir / "prover_output.txt").write_text(output_text[:50000], encoding="utf-8")

    # TreeRunResult is the one typed tree/run boundary. Function attributes and
    # filesystem searches are not semantic handoffs.
    session_id = tree_result.selected_session_id
    session_records = list(tree_result.session_records)
    ec_session_dir = tree_result.selected_session_dir
    completion_candidate = tree_result.completion_candidate
    information_source_audit = list(tree_result.information_source_audit)
    payload_audit_path = tree_result.payload_audit_path
    logger.info("Subagent session_id: %s", session_id or "(not found)")
    logger.info("EasyCrypt session dir: %s", ec_session_dir or "(not found)")
    if information_source_audit:
        (run_dir / "information_source_audit.json").write_text(
            json.dumps(information_source_audit, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "Information-source audit: %d event(s)",
            len(information_source_audit),
        )
    if payload_audit_path:
        logger.info("Payload audit: %s", payload_audit_path)
    archived_ec_sessions = _archive_ec_session_dirs(
        run_dir,
        session_dirs=tree_result.managed_session_dirs,
    )
    if archived_ec_sessions:
        pstatus("Prover",
                f"Archived {len(archived_ec_sessions)} EC session dir(s) "
                f"to {run_dir / 'ec_sessions'}")
    resume_capsules: list[str] = []
    if mode == "tree" and archived_ec_sessions:
        try:
            from workflow.proof_node_resume import create_resume_capsules

            resume_capsules = create_resume_capsules(
                project_root=_PROJECT_ROOT,
                run_dir=run_dir,
                session_dirs=[Path(p) for p in archived_ec_sessions],
                target_file=file_path,
                lemma=lemma_name,
                include_dir=include_dir,
            )
            if resume_capsules:
                pstatus(
                    "Prover",
                    f"Wrote {len(resume_capsules)} proof-node resume "
                    f"capsule(s) to {run_dir / 'resume_capsules'}",
                )
        except Exception as e:
            logger.warning("Failed to create proof-node resume capsules: %s", e)
    # --- Extract tactics, notes, and structured report from output ---
    run_status = PROVER_RUN_INCOMPLETE
    verification: dict[str, Any] = {}
    infrastructure_errors = list(tree_result.infrastructure_errors)
    if tree_result.destructive_abort:
        reason = tree_result.destructive_reason or (
            "unknown session hygiene violation"
        )
        infrastructure_errors.append(
            "prover subagent attempted a session-corrupting operation: "
            + reason
        )
        completion_candidate = None
    event_contract_gate = None
    tactics = (
        []
        if tree_result.destructive_abort
        else _extract_tactics_from_candidate(completion_candidate)
    )
    notes = _extract_prover_notes(output_text)
    prover_report = _extract_prover_report(output_text)
    if notes:
        (run_dir / "prover_notes.txt").write_text(notes, encoding="utf-8")
        logger.info("Prover notes: %d chars", len(notes))
    if prover_report:
        (run_dir / "prover_report.json").write_text(
            json.dumps(prover_report, indent=2), encoding="utf-8")
        n_sugg = len(prover_report.get("suggestions", []))
        logger.info("Prover report: %d suggestions, %d discoveries",
                     n_sugg, len(prover_report.get("discoveries", [])))

    if tactics:
        pstatus("Prover", f"Extracted {len(tactics)} tactics. Writing proof to file...")
        assert completion_candidate is not None
        verification_evidence = _write_and_verify_proof(
            ec_full_path,
            lemma_name,
            tactics,
            completion_candidate,
            include_dir=include_dir,
        )
        event_contract_gate = verification_evidence.event_contract
        if verification_evidence.passed:
            run_status = PROVER_RUN_VERIFIED
            verification = {
                "status": "pass",
                "method": verification_evidence.method,
                "candidate_id": completion_candidate.candidate_id,
                "event_verification_status": (
                    event_contract_gate.verification_status
                    if event_contract_gate is not None
                    else None
                ),
                "event_contract_ok": bool(
                    event_contract_gate and event_contract_gate.ok
                ),
            }
        else:
            pstatus("Prover", "Verification failed. Reverting.", "\033[31m")
            run_status = PROVER_RUN_INFRASTRUCTURE_INVALID
            infrastructure_errors.append(
                "session-closed completion candidate failed final verification"
            )
            verification = {
                "status": "fail",
                "candidate_id": completion_candidate.candidate_id,
                "reason": verification_evidence.error,
            }
    else:
        if completion_candidate is not None:
            run_status = PROVER_RUN_INFRASTRUCTURE_INVALID
            infrastructure_errors.append(
                "session-closed completion candidate could not be extracted"
            )
        elif infrastructure_errors:
            run_status = PROVER_RUN_INFRASTRUCTURE_INVALID
        partial_tactics = _extract_partial_tactics_from_sessions(
            session_dirs=archived_ec_sessions,
            resume_capsules=resume_capsules,
        )
        if partial_tactics:
            (run_dir / "partial_proof_prefix.ec").write_text(
                "\n".join(partial_tactics) + "\n",
                encoding="utf-8",
            )
            (run_dir / "partial_proof_prefix.json").write_text(
                json.dumps(
                    {
                        "kind": "partial_proof_prefix",
                        "lemma": lemma_name,
                        "closed_by_qed": False,
                        "tactic_count": len(partial_tactics),
                        "source": "manager_session_history_or_resume_capsule",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            pstatus(
                "Prover",
                "Could not extract a closed proof; wrote "
                f"{len(partial_tactics)} tactic partial prefix to "
                f"{run_dir / 'partial_proof_prefix.ec'}.",
                "\033[33m",
            )
        else:
            pstatus("Prover", "Could not extract tactics from prover output.", "\033[33m")

    logger.info(
        "Prover finished. Outcome: %s, Time: %.0fs, Session: %s",
        run_status, elapsed, session_id,
    )
    if session_id and not any(
        str(record.get("session_id") or "") == session_id
        for record in session_records
        if isinstance(record, dict)
    ):
        session_records.append({
            "worker": "Prover",
            "session_id": session_id,
            "agent_backend": agent_backend,
            "winner": True,
        })
    if session_records:
        for record in session_records:
            if not isinstance(record, dict):
                continue
            if str(record.get("session_id") or "") == session_id:
                record["winner"] = True
                record["completion_candidate_id"] = (
                    completion_candidate.candidate_id
                    if completion_candidate is not None
                    else ""
                )
        (run_dir / "agent_session_ids.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "agent_session_ids",
                    "sessions": session_records,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    result = ProverResult(
        status=run_status,
        session_id=session_id,
        turns=tree_result.turns,
        elapsed_seconds=elapsed,
        selected_node_id=tree_result.selected_node_id,
        ec_session_dir=ec_session_dir,
        completion_candidate=(
            completion_candidate.to_dict()
            if completion_candidate is not None
            else {}
        ),
        verification=verification,
        infrastructure_errors=infrastructure_errors,
        event_contract_checked=bool(event_contract_gate),
        event_contract_ok=bool(event_contract_gate and event_contract_gate.ok),
        event_contract_errors=(
            list(event_contract_gate.errors) if event_contract_gate else []
        ),
        archived_ec_session_dirs=archived_ec_sessions,
        resume_capsules=resume_capsules,
        information_source_audit=information_source_audit,
        notes=notes,
        report=prover_report,
    )
    result.save(run_dir / "prover_run_result.json")
    return result






# ---------------------------------------------------------------------------
# EC file verification
# ---------------------------------------------------------------------------












