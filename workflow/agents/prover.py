"""Prover agent: prove an EasyCrypt lemma using a managed agent process.

Launches either Claude Code or OpenAI Codex with a task-specific prompt. The
agent has manager-owned source-navigation tools, while EasyCrypt proof
interaction goes through the managed ProofNodeManager intent protocol.

Claude Code traces are correlated through ``agent_sessions.jsonl``. Codex runs
emit their thread id through the same provider-neutral session registry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from workflow.schemas.config import ProverConfig, normalize_agent_backend
from workflow.agents.ec_services import (
    _configure_run_ec_daemon_socket,
    _configure_run_why3_socket,
    _ensure_why3server,
    _shutdown_ec_daemon,
    _shutdown_run_why3server,
)
from workflow.agents.prover_writeback import (
    _extract_partial_tactics_from_sessions,
    _extract_partial_transactions_from_sessions,
    _extract_prover_notes,
    _extract_prover_report,
    _extract_tactics_from_candidate,
    _verify_ec_file,
    _verify_lemma_extracted,
    _write_and_verify_proof,
)
from workflow.proof_state_compiler.runtime_profiles import (
    ensure_supported_runtime_surface_profile,
)
from workflow.proof_management.node_bootstrap import (
    replay_prefix_shortfall,
    require_proof_node_manager_bootstrap,
)
from workflow.node.proof_node_manager import ProofNodeManager
from workflow.tree.policy import cap_tree_max_concurrent
from workflow.tree.result import (
    TREE_RUN_TERMINATION_WALL_CLOCK_TIMEOUT,
    TreeRunResult,
)
from workflow.agents.prover_prompt import (
    _build_child_prover_prompt,
    _build_prover_prompt,
)

logger = logging.getLogger("workflow.agents.prover")


def _tree_result_infrastructure_errors(tree_result: TreeRunResult) -> list[str]:
    """Project process-level tree failure into the canonical run boundary."""

    errors = [
        str(item).strip()
        for item in tree_result.infrastructure_errors
        if str(item).strip()
    ]
    # The supervisor enforces its wall-clock budget by terminating active
    # workers.  Their signal return code is expected search control, not a
    # worker crash; the typed termination reason distinguishes the two.
    if (
        tree_result.returncode != 0
        and tree_result.termination_reason
        != TREE_RUN_TERMINATION_WALL_CLOCK_TIMEOUT
    ):
        message = (
            "selected proof worker exited nonzero "
            f"(code {tree_result.returncode})"
        )
        if message not in errors:
            errors.append(message)
    return errors


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


def _create_run_session_namespace(run_dir: Path) -> str:
    """Create and record the owner identity for this invocation's sessions.

    Tree node ids are only unique within a run. A random run namespace makes
    their project-root session paths disjoint even when several evaluation
    arms intentionally share one frozen checkout. This record is provenance,
    not a discovery mechanism; consumers receive exact session paths from the
    typed tree result.
    """
    namespace = secrets.token_hex(6)
    identity_path = run_dir / "run_session_identity.json"
    identity_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "run_owned_easycrypt_session_namespace",
                "namespace": namespace,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return namespace


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
    from workflow.run_ui import status as pstatus

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

    Live runs own disjoint, namespaced session paths. This archive preserves
    their event log and generated workspace / TacticExecutionResult artifacts
    for postmortem analysis without scanning or interpreting sibling sessions.
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
    *,
    prover: Optional[ProverConfig] = None,
    run_dir: Optional[Path] = None,
    eval_mode: Optional[bool] = None,
    surface_profile: str | None = None,
    resume_capsules: Optional[list[str]] = None,
    outer_proof_handoff: str = "",
):
    """Run the prover as a managed Claude Code or OpenAI Codex agent.

    The selected agent process receives the proving prompt and uses the
    manager intent protocol for EasyCrypt proof interaction, Read/Bash for
    legitimate source context, and never owns session lifecycle.

    All model/budget/tree knobs travel in one ``ProverConfig`` — the previous
    29-keyword signature kept a second copy of every default, and six of them
    had silently drifted from the schema (e.g. tree_grace_seconds 120 vs 300).

    Long-lived managed prover mode:
    - "tree": Start one or more proof nodes, each with its own long-lived
      agent runtime.
    """
    prover = prover if prover is not None else ProverConfig()
    agent_backend = normalize_agent_backend(prover.agent_backend)
    model = prover.model
    effort = prover.effort
    max_turns = prover.max_total_tactics
    timeout_minutes = prover.timeout_minutes
    resume_root_policy = prover.resume_root_policy
    mode = prover.mode
    tree_initial_provers = prover.tree_initial_provers
    tree_max_concurrent = prover.tree_max_concurrent
    tree_stuck_errors = prover.tree_stuck_errors
    tree_stuck_idle_seconds = prover.tree_stuck_idle_seconds
    tree_grace_seconds = prover.tree_grace_seconds
    tree_max_depth = prover.tree_max_depth
    tree_min_alive_seconds = prover.tree_min_alive_seconds
    tree_progress_gap_ratio = prover.tree_progress_gap_ratio
    tree_progress_gap_idle = prover.tree_progress_gap_idle
    tree_structural_undo_spawn_delay_seconds = (
        prover.tree_structural_undo_spawn_delay_seconds
    )
    tree_undo_repair_protection_seconds = (
        prover.tree_undo_repair_protection_seconds
    )
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
    run_session_namespace = _create_run_session_namespace(run_dir)

    # Record the agent-CLI half of the measured system, mirroring the pinned
    # EasyCrypt identity recorded per session: CLI version drift is a real
    # confound for cross-time win-rate comparisons and produced live failures.
    from workflow.provider.provider_sessions import provider_cli_identity

    provider_identity = provider_cli_identity(agent_backend)
    (run_dir / "provider_identity.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "provider_cli_identity",
                "model": model,
                **provider_identity,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info(
        "Agent CLI: %s (%s)",
        provider_identity["version"],
        provider_identity["resolved_path"],
    )

    from workflow.run_ui import status as pstatus

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
    loaded_outer_handoff = None
    if outer_proof_handoff:
        if resume_capsules:
            raise ValueError(
                "outer proof handoff and resume capsules are mutually exclusive"
            )
        from workflow.node.outer_proof_handoff import load_outer_proof_handoff

        loaded_outer_handoff = load_outer_proof_handoff(outer_proof_handoff)
        handoff_outer_root = (
            _PROJECT_ROOT / loaded_outer_handoff.outer_run_dir
        ).resolve()
        handoff_manifest = loaded_outer_handoff.path.resolve()
        resolved_run_dir = Path(run_dir).resolve()
        if (
            not handoff_manifest.is_relative_to(handoff_outer_root)
            or not resolved_run_dir.is_relative_to(handoff_outer_root)
        ):
            raise ValueError(
                "outer proof handoff is not invocation-bound to this experiment run"
            )
        if loaded_outer_handoff.target_file != file_path:
            raise ValueError(
                "outer proof handoff target file mismatch: "
                f"{loaded_outer_handoff.target_file} != {file_path}"
            )
        if loaded_outer_handoff.lemma != lemma_name:
            raise ValueError(
                "outer proof handoff lemma mismatch: "
                f"{loaded_outer_handoff.lemma} != {lemma_name}"
            )
        try:
            current_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(_PROJECT_ROOT),
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            current_commit = ""
        if (
            loaded_outer_handoff.source_commit
            and current_commit
            and loaded_outer_handoff.source_commit != current_commit
        ):
            raise ValueError(
                "outer proof handoff commit mismatch: "
                f"{loaded_outer_handoff.source_commit} != {current_commit}"
            )
    loaded_resume_capsules = []
    if resume_capsules:
        from workflow.node.proof_node_resume import load_resume_capsules

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
    elif loaded_outer_handoff is not None:
        tree_initial_provers = 1
        tree_max_concurrent = max(1, tree_max_concurrent)
        pstatus(
            "Prover",
            "Same-experiment outer proof handoff: manager will replay "
            f"{len(loaded_outer_handoff.replay_commands)} certified command(s) "
            "and verify the recorded boundary before launching the selected "
            "proof-node agent.",
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

    if mode != "tree":
        raise ValueError("unsupported prover mode; only 'tree' is current")

    tree_max_concurrent = cap_tree_max_concurrent(tree_max_concurrent)
    tree_initial_provers = max(1, min(int(tree_initial_provers), tree_max_concurrent))

    from workflow.run_ui import status as pstatus

    start_time = time.time()

    if mode == "tree":
        # --- Tree mode: recursive branch-and-explore ---
        from workflow.tree.supervisor import (
            MANAGED_LIVE_PROGRESS_FILENAME,
            run_tree_prover,
        )
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
        elif loaded_outer_handoff is not None:
            resume_initial_branches.append({
                "replay_prefix": list(loaded_outer_handoff.replay_commands),
                "resume_context": {
                    "resume_prefix_count": len(loaded_outer_handoff.replay_commands),
                    "outer_proof_handoff": loaded_outer_handoff.manager_context(),
                },
                "negative_signal": [],
                "parent_goal_state": loaded_outer_handoff.current_goal_preview,
                "expected_goal_hash": loaded_outer_handoff.boundary_goal_hash,
                "goal_identity_required": loaded_outer_handoff.goal_identity_required,
                "capsule_path": str(loaded_outer_handoff.path),
                "capsule_score": 0.0,
                "resume_root_policy": "same_run_outer_handoff",
                "resume_diversity": {},
                "route_family": {},
            })

        def _build_tree_cmd(session_tag, node_id, replay_prefix, negative_signal,
                            layer_move_action=None, resume_context=None):
            resolved_resume_context = (
                dict(resume_context) if isinstance(resume_context, dict) else {}
            )
            outer_context = resolved_resume_context.get("outer_proof_handoff")
            if isinstance(outer_context, dict):
                from workflow.node.continuation_brief import (
                    continuation_brief_from_outer_handoff,
                )

                resolved_resume_context["continuation_brief"] = (
                    continuation_brief_from_outer_handoff(outer_context)
                )
            managed_session = _prepare_managed_session(
                file_path=file_path,
                lemma_name=lemma_name,
                include_dir=include_dir,
                session_tag=session_tag,
                replay_prefix=list(replay_prefix or []),
                run_dir=run_dir,
                node_label=f"Tree-{node_id}",
                surface_profile=surface_profile,
                resume_context=resolved_resume_context or None,
            )
            if isinstance(outer_context, dict):
                from workflow.node.outer_proof_handoff import (
                    proof_command_sequence_sha256,
                )

                status = managed_session.get("workspace_view", {}).get(
                    "proof_status", {}
                )
                actual_hash = str(status.get("goal_hash") or "")
                expected_hash = str(outer_context.get("boundary_goal_hash") or "")
                actual_prefix = list(managed_session.get("replay_prefix") or [])
                actual_spine_hash = proof_command_sequence_sha256(actual_prefix)
                expected_spine_hash = str(
                    outer_context.get("committed_spine_sha256") or ""
                )
                if actual_spine_hash != expected_spine_hash:
                    raise RuntimeError(
                        "outer proof handoff replay changed the committed proof spine"
                    )
                if actual_hash != expected_hash:
                    raise RuntimeError(
                        "outer proof handoff goal identity drifted after replay: "
                        f"{actual_hash or '<missing>'} != {expected_hash or '<missing>'}"
                    )
                # This is manager-owned durable construction context, not a
                # proof-state claim. The runtime validates and repeats it in
                # every followup/system anchor so context compaction cannot
                # silently erase an explicitly handed-over declaration.
            continuation_brief = managed_session.get("continuation_brief")
            if isinstance(continuation_brief, dict):
                managed_session["resource_anchors"] = list(
                    continuation_brief.get("resource_anchors") or []
                )
            if replay_prefix or isinstance(outer_context, dict):
                prompt = _build_child_prover_prompt(
                    file_path, lemma_name, include_dir,
                    session_tag,
                    layer_move_action=layer_move_action,
                    managed_session=managed_session,
                    surface_profile=surface_profile,
                    outer_proof_handoff=outer_context,
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
                "workflow.node.managed_prover_worker",
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
                session_namespace=run_session_namespace,
                live_progress_path=run_dir / MANAGED_LIVE_PROGRESS_FILENAME,
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
    # Parse the agent's bounded public handback before minting continuation
    # capsules so a resumed job keeps concrete blockers/discoveries alongside
    # the manager-owned accepted prefix.
    prover_report = _extract_prover_report(output_text)
    resume_capsules: list[str] = []
    if mode == "tree" and archived_ec_sessions:
        try:
            from workflow.node.proof_node_resume import create_resume_capsules

            resume_capsules = create_resume_capsules(
                project_root=_PROJECT_ROOT,
                run_dir=run_dir,
                session_dirs=[Path(p) for p in archived_ec_sessions],
                target_file=file_path,
                lemma=lemma_name,
                include_dir=include_dir,
                agent_report=prover_report,
                agent_report_session_name=(
                    Path(ec_session_dir).name if ec_session_dir else ""
                ),
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
    infrastructure_errors = _tree_result_infrastructure_errors(tree_result)
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
        if tree_result.destructive_abort or infrastructure_errors
        else _extract_tactics_from_candidate(completion_candidate)
    )
    notes = _extract_prover_notes(output_text)
    if notes:
        (run_dir / "prover_notes.txt").write_text(notes, encoding="utf-8")
        logger.info("Prover notes: %d chars", len(notes))
    if prover_report:
        (run_dir / "prover_report.json").write_text(
            json.dumps(prover_report, indent=2), encoding="utf-8")
        logger.info(
            "Prover report: %d blocker(s), %d discovery item(s)",
            len(prover_report.get("blockers", [])),
            len(prover_report.get("discoveries", [])),
        )

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
        partial_transactions = _extract_partial_transactions_from_sessions(
            session_dirs=archived_ec_sessions,
            committed_prefix=partial_tactics,
            resume_capsules=resume_capsules,
        )
        # One synchronous terminal boundary owns timeout, outer interruption,
        # and ordinary worker exit.  It preserves the exact accepted reporting
        # prefix and reuses the newest compatible checkpoint minted at a prior
        # completed manager turn.  Cold replay belongs only to a later explicit
        # resume; terminal handback never re-executes the proof spine.
        try:
            from workflow.node.safe_stop_finalizer import (
                finalize_safe_stop_checkpoint,
            )

            stop_finalization = finalize_safe_stop_checkpoint(
                project_root=_PROJECT_ROOT,
                run_dir=run_dir,
                target_file=file_path,
                lemma=lemma_name,
                include_dir=include_dir,
                committed_prefix=partial_tactics,
                committed_transactions=partial_transactions or None,
                existing_capsules=resume_capsules,
                surface_profile=surface_profile,
                agent_report=prover_report,
                trigger=(
                    tree_result.termination_reason
                    or (
                        "outer_interrupt"
                        if any(
                            "tree search interrupted" in item
                            for item in infrastructure_errors
                        )
                        else "worker_process_exit"
                    )
                ),
            )
        except Exception as exc:
            from workflow.node.safe_stop_finalizer import SafeStopFinalization

            stop_finalization = SafeStopFinalization(
                completed=False,
                method="finalizer_failed",
                tactic_count=len(partial_tactics),
                error=f"{type(exc).__name__}: {exc}",
            )
        if stop_finalization.completed:
            for capsule_path in stop_finalization.capsule_paths:
                if capsule_path not in resume_capsules:
                    resume_capsules.append(capsule_path)
            pstatus(
                "Prover",
                "Safe-stop checkpoint finalized via "
                f"{stop_finalization.method} "
                f"({stop_finalization.tactic_count} tactic(s)).",
            )
        else:
            message = (
                "safe-stop checkpoint finalization failed: "
                + (stop_finalization.error or stop_finalization.method)
            )
            if message not in infrastructure_errors:
                infrastructure_errors.append(message)
            run_status = PROVER_RUN_INFRASTRUCTURE_INVALID
        if partial_tactics:
            partial_text = "\n".join(partial_tactics) + "\n"
            partial_bytes = partial_text.encode("utf-8")
            (run_dir / "partial_proof_prefix.ec").write_bytes(partial_bytes)
            (run_dir / "partial_proof_prefix.json").write_text(
                json.dumps(
                    {
                        "kind": "partial_proof_prefix",
                        "schema_version": 2,
                        "lemma": lemma_name,
                        "closed_by_qed": False,
                        "tactic_count": len(partial_tactics),
                        "byte_count": len(partial_bytes),
                        "sha256": hashlib.sha256(partial_bytes).hexdigest(),
                        "source": "manager_session_history_or_resume_capsule",
                        "replay_required_before_use": True,
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
