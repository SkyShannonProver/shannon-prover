"""Prover agent: prove an EasyCrypt lemma using a Claude Code subagent.

Launches `claude -p` with a task-specific prompt. The subagent has access to
Claude Code tools for source inspection, while EasyCrypt proof interaction
goes through the managed ProofNodeManager intent protocol.

Traces (including thinking tokens) are automatically stored by Claude Code
in `~/.claude/projects/`. The Trace Analyst reads them from there.
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

from core.easycrypt.committed_history import (
    closed_history_tactics,
    read_committed_tactics,
)
from workflow.schemas.config import PROVER_DEFAULTS
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
    _acceptance_gate_for_session,
    _build_proof_text,
    _candidate_gate_for_session,
    _distill_ec_stderr,
    _emit_verification_status,
    _extract_partial_tactics_from_session,
    _extract_prover_notes,
    _extract_prover_report,
    _extract_tactics_from_session,
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
from workflow.surface_profiles import ensure_supported_surface_profile
from workflow.proof_management.lifecycle import replay_prefix_shortfall
from workflow.proof_node_manager import ProofNodeManager
from workflow.tree.policy import DEFAULT_TREE_INITIAL_PROVERS, cap_tree_max_concurrent
from workflow.agents.prover_prompt import (
    _build_child_prover_prompt,
    _build_prover_prompt,
    _session_dir_for_tag,
)

logger = logging.getLogger("workflow.agents.prover")

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# why3server we started for THIS run (per-run socket, see
# _configure_run_why3_socket). Held so the run can tear it down at the end
# instead of leaking it for the next run's global pkill to find. None when no
# server was started by us (e.g. a responsive one was already running).






def _session_include_dirs(file_path: str, include_dir: str) -> list[str]:
    from os.path import dirname as _dirname

    file_dir = _dirname(file_path) or "."
    dirs = [file_dir]
    if include_dir and include_dir != file_dir:
        dirs.append(include_dir)
    return dirs


def _workspace_view_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    workspace = payload.get("workspace")
    if isinstance(workspace, dict):
        view = workspace.get("view")
        if isinstance(view, dict):
            return view
    if isinstance(payload.get("current_goal"), dict) and (
        "candidate_moves" in payload
        or "proof_status" in payload
        or "decision_context" in payload
        or "suggested_next_steps" in payload
        or "proof_position" in payload
    ):
        return payload
    return payload


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


def _bootstrap_opened_real_proof(bootstrap: dict[str, Any]) -> bool:
    """True unless the managed session clearly failed to open the target proof.

    When a file fails to load (e.g. a `require`d theory is missing) EC stays at
    top level with no open proof: the projected view shows ``status`` of
    ``unknown``/``error`` and EC never reports a remaining-goal count, while the
    "goal" is just the bare ``[N|check]>`` prompt. A healthy open *or* complete
    proof always carries an authoritative count (``remaining_goals_known``).

    Fail-open: returns ``True`` on any unrecognized/missing schema so it can
    never block a legitimate run — the eval-suite preflight is the primary guard
    and this is only a backstop for the clear degraded signature.
    """
    view = bootstrap.get("workspace_view")
    if not isinstance(view, dict):
        return True
    ps = view.get("proof_status")
    if not isinstance(ps, dict) or not ps:
        return True  # no proof_status signal at all — fail open
    if ps.get("remaining_goals_known") is True:
        return True  # EC gave a goal count (open or complete) — real proof
    status = str(ps.get("status") or "")
    if status not in ("unknown", "error"):
        # Only an EXPLICIT degraded status is the hollow signature; an absent
        # status is ambiguous, so fail open.
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
        semantic_replay_count = len(replay_prefix or [])
        if isinstance(resume_context, dict):
            try:
                semantic_replay_count = int(
                    resume_context.get("resume_prefix_count")
                    or semantic_replay_count
                )
            except (TypeError, ValueError):
                semantic_replay_count = len(replay_prefix or [])
        bootstrap = {
            "schema_version": 2,
            "kind": "manager_session_bootstrap",
            "node": node_label,
            "session_tag": session_tag,
            "session_dir": _session_dir_for_tag(session_tag),
            "file": file_path,
            "lemma": lemma_name,
            "include_dirs": _session_include_dirs(file_path, include_dir),
            "replay_prefix_count": semantic_replay_count,
            "replay_prefix": list(replay_prefix or []),
            "surface_profile": surface_profile,
            "manager_actions": [{
                "label": "manager_bootstrap_skipped",
                "exit_code": 0,
                "note": "backend session driver is unavailable in this test root",
            }],
            "snapshot": {},
            "workspace_view": {},
        }
        _append_manager_bootstrap_audit(run_dir, bootstrap)
        return bootstrap

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
    _warn_replay_prefix_shortfall(bootstrap, node_label=node_label)
    legacy_bootstrap = dict(bootstrap)
    legacy_bootstrap["kind"] = "manager_session_bootstrap"
    legacy_bootstrap["schema_version"] = 2
    _append_manager_bootstrap_audit(run_dir, bootstrap)
    if (
        os.environ.get("SHANNON_SKIP_BOOTSTRAP_GUARD") != "1"
        and not _bootstrap_opened_real_proof(legacy_bootstrap)
    ):
        raise RuntimeError(
            f"Managed session did not open a proof for lemma '{lemma_name}' in "
            f"{file_path}: EC reports no goal, which almost always means the "
            f"file failed to load (e.g. a missing `require`d theory). Refusing "
            f"to launch the prover against a session with no open proof — that "
            f"would be a 'hollow run' where every tactic errors 'outside a "
            f"proof script'. Set SHANNON_SKIP_BOOTSTRAP_GUARD=1 to override."
        )
    return legacy_bootstrap


def _archive_ec_session_dirs(
    run_dir: Path,
    preferred_session_dir: str | Path | None = None,
) -> list[str]:
    """Copy this prover run's EasyCrypt session dirs into ``run_dir``.

    ``prover.run`` wipes project-root ``.ec_session_*`` directories at the
    start of the next run to prevent proof leakage. Without this archive, the
    event log and generated ProofContextView / TacticExecutionResult artifacts vanish
    before postmortem analysis can inspect them.
    """
    import shutil as _shutil

    candidates: set[Path] = {
        p for p in _PROJECT_ROOT.glob(".ec_session_*") if p.is_dir()
    }
    if preferred_session_dir:
        p = Path(preferred_session_dir)
        if p.exists() and p.is_dir():
            candidates.add(p)

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


def _truthy_env(name: str) -> Optional[bool]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _is_live_smoke_path(path: str | Path) -> bool:
    parts = [p for p in Path(path).parts if p not in {"", "."}]
    return "artifacts" in parts and "live_smoke" in parts


def _should_record_proof_bank(
    file_path: str,
    lemma_name: str,
    run_dir: Path,
    eval_mode: bool,
    explicit: Optional[bool],
) -> bool:
    """Context-aware proof-bank policy.

    Ordinary workflow successes keep feeding regression. Eval and live-smoke
    runs are disposable measurements, so they must not mutate proof_bank unless
    the caller explicitly opts in.
    """
    if explicit is not None:
        return bool(explicit)

    env_choice = _truthy_env("SHANNON_RECORD_PROOF_BANK")
    if env_choice is not None:
        return env_choice

    eval_target = os.environ.get("EVAL_TARGET_LEMMA", "").strip()
    if eval_mode or eval_target == lemma_name:
        return False
    if _is_live_smoke_path(file_path) or _is_live_smoke_path(run_dir):
        return False
    return True


# ---------------------------------------------------------------------------
# Session ID extraction
# ---------------------------------------------------------------------------


# Claude Code stores sessions in ~/.claude/projects/<project-hash>/<session-id>.jsonl
_CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
_PROJECT_HASH = None  # computed lazily


def _get_project_hash() -> str:
    """Get the Claude Code project hash for trace file lookup.

    Claude Code encodes the project path by replacing all / and _ with -.
    E.g. <REPO> -> <PROJECT>
    """
    global _PROJECT_HASH
    if _PROJECT_HASH is not None:
        return _PROJECT_HASH

    # Claude Code replaces both / and _ with -
    project_path = str(_PROJECT_ROOT).replace("/", "-").replace("_", "-")

    # Check which hash exists in ~/.claude/projects/
    if _CLAUDE_PROJECTS_DIR.exists():
        for d in _CLAUDE_PROJECTS_DIR.iterdir():
            if d.is_dir() and d.name == project_path:
                _PROJECT_HASH = d.name
                return _PROJECT_HASH
        # Fallback: partial match
        for d in _CLAUDE_PROJECTS_DIR.iterdir():
            if d.is_dir() and "Shannon" in d.name:
                _PROJECT_HASH = d.name
                return _PROJECT_HASH

    # Fallback: construct it
    _PROJECT_HASH = project_path
    return _PROJECT_HASH


def _is_subagent_session(jsonl_path: Path) -> bool:
    """Check if a JSONL file is a subagent session (claude -p), not interactive.

    Subagent sessions start with 'queue-operation'; interactive sessions
    start with 'permission-mode'. We only want subagent sessions.
    """
    try:
        with jsonl_path.open("r", encoding="utf-8") as f:
            first_line = f.readline()
            if not first_line:
                return False
            import json as _json
            data = _json.loads(first_line)
            return data.get("type") == "queue-operation"
    except Exception:
        return False


def _find_latest_session_id(after_timestamp: float) -> str:
    """Find the most recent Claude Code subagent session JSONL created after a timestamp.

    Only considers subagent sessions (claude -p), not interactive sessions.
    Returns the session ID (filename without .jsonl), or "" if not found.
    """
    project_hash = _get_project_hash()
    sessions_dir = _CLAUDE_PROJECTS_DIR / project_hash

    if not sessions_dir.exists():
        logger.warning("Claude projects dir not found: %s", sessions_dir)
        return ""

    best_path = None
    best_mtime = 0.0

    for f in sessions_dir.glob("*.jsonl"):
        mtime = f.stat().st_mtime
        if mtime > after_timestamp and mtime > best_mtime:
            if _is_subagent_session(f):
                best_mtime = mtime
                best_path = f

    if best_path:
        return best_path.stem
    return ""


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
    model: str = PROVER_DEFAULTS.model,
    effort: str = PROVER_DEFAULTS.effort,
    max_turns: int = 1000,
    timeout_minutes: int = 20,
    parallelism: int = 1,
    warmup_seconds: int = 180,
    kill_gap_tactics: int = 2,
    kill_gap_idle_seconds: int = 60,
    run_dir: Optional[Path] = None,
    plan=None,  # Optional[ProofPlan] — avoid circular import
    use_planner: bool = True,
    eval_mode: Optional[bool] = None,
    surface_profile: str | None = None,
    record_proof_bank: Optional[bool] = None,
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
    """Run the prover as a Claude Code subagent.

    Launches `claude -p` with the proving prompt. The subagent uses the
    manager intent protocol for EasyCrypt proof interaction, Read/Bash for
    legitimate source context, and never owns session lifecycle.
    Traces are stored automatically by Claude Code.

    Planner behavior:
    - By default, a missing ``plan`` is filled by the deterministic proof
      planner before launching Claude. This keeps manual smoke runs aligned
      with the orchestrator workflow.
    - Pass ``use_planner=False`` only for explicit planner-ablation tests.

    Long-lived managed prover mode:
    - "tree": Start one or more proof nodes, each with its own long-lived
      agent runtime. Legacy "racing" requests are routed through tree roots so
      no prover path launches Claude without ``ProofNodeRuntime``.
    """
    from workflow.schemas.prover_result import ProverResult
    profile = ensure_supported_surface_profile(surface_profile)
    if profile is not None:
        surface_profile = profile.name
    run_dir = run_dir or (_PROJECT_ROOT / "workflow" / "runs" / "scratch")
    run_dir.mkdir(parents=True, exist_ok=True)

    from workflow.progress import status as pstatus, error as perror

    if _shutdown_ec_daemon(
        reason="legacy global pre-run cleanup",
        socket_path="/tmp/ec_daemon.sock",
    ):
        pstatus("Prover", "Stopped legacy global EasyCrypt daemon")
    stopped_repo_daemons = _shutdown_repo_ec_daemons(reason="repo-local pre-run cleanup")
    if stopped_repo_daemons:
        pstatus(
            "Prover",
            f"Stopped {stopped_repo_daemons} repo-local EasyCrypt daemon(s)",
        )
    run_ec_daemon_socket = _configure_run_ec_daemon_socket(run_dir)
    logger.info("Using per-run EasyCrypt daemon socket: %s", run_ec_daemon_socket)

    # --- Pre-check: does the lemma already have a proof? ---
    ec_full_path = _PROJECT_ROOT / file_path
    precheck = _precheck_lemma(ec_full_path, lemma_name, include_dir=include_dir)

    if precheck == "proved_and_verified":
        pstatus("Prover", f"{lemma_name} already has a verified proof. Skipping.", "\033[32m")
        return ProverResult(proved=True, ec_file_verified=True, skipped=True)

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
        if mode != "tree":
            pstatus("Prover",
                    "Resume capsule supplied; forcing tree mode so each "
                    "capsule can be a replayed root.",
                    "\033[33m")
            mode = "tree"
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
    record_proof_bank_enabled = _should_record_proof_bank(
        file_path=file_path,
        lemma_name=lemma_name,
        run_dir=run_dir,
        eval_mode=bool(eval_mode),
        explicit=record_proof_bank,
    )

    # The deterministic planner is part of the normal prover contract. Keep
    # this guard in the low-level entry point too, so direct live-smoke calls
    # don't silently degrade into raw stdout/file-reading mode.
    # l1_goal_projection is the planner-free minimal baseline: never run (or
    # re-run) the planner for it, regardless of use_planner. Otherwise a None
    # plan from the orchestrator's L1 gate would trip this fallback.
    _l1_baseline = surface_profile == "l1_goal_projection"
    if plan is None and use_planner and not _l1_baseline:
        try:
            from workflow.schemas.config import RunConfig
            from workflow.agents.proof_planner import run as run_planner

            planner_config = RunConfig(
                file=file_path,
                lemma=lemma_name,
                include_dir=include_dir,
                eval_mode=bool(eval_mode),
            )
            planner_config.prover.model = model
            pstatus("Prover",
                    "No plan supplied; running deterministic planner first")
            plan = run_planner(planner_config, run_dir / "planner")
        except Exception as e:
            perror("Prover", f"Planner failed: {e}")
            return ProverResult(
                proved=False,
                ec_file_verified=False,
                error=(
                    "planner failed; refusing to launch prover without "
                    "planner context. Pass use_planner=False only for "
                    "explicit planner-ablation experiments."
                ),
            )
        if plan is None:
            perror("Prover", "Planner returned no plan")
            return ProverResult(
                proved=False,
                ec_file_verified=False,
                error=(
                    "planner returned no plan; refusing to launch prover "
                    "without planner context. Pass use_planner=False only "
                    "for explicit planner-ablation experiments."
                ),
            )
    elif plan is None and (not use_planner or _l1_baseline):
        pstatus("Prover",
                "Planner-free baseline (l1_goal_projection)" if _l1_baseline
                else "Planner disabled: raw-prover ablation mode",
                "\033[33m")

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

    # Record timestamp before launch (to find the session trace after)
    before_timestamp = time.time()

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
        requested_mode = mode
        tree_initial_provers = max(1, int(parallelism or 1))
        tree_max_concurrent = max(tree_max_concurrent, tree_initial_provers)
        mode = "tree"
        pstatus(
            "Prover",
            f"Routing legacy prover mode {requested_mode!r} through tree mode "
            f"with {tree_initial_provers} long-lived root node(s).",
            "\033[33m",
        )

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
                    "capsule_path": str(ckpt.path),
                    "capsule_score": ckpt.score,
                    "resume_root_policy": resume_root_policy,
                    "resume_diversity": dict(ckpt.resume_diversity or {}),
                    "route_family": {
                        "family": ckpt.route_family,
                    } if ckpt.route_family else {},
                })

        def _build_tree_cmd(session_tag, node_id, replay_prefix, negative_signal,
                            strategy_index=0, parent_goal_state="",
                            discoveries=None, blocked_openers=None,
                            layer_move_action=None,
                            resume_context=None):
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
                    session_tag, replay_prefix, negative_signal, plan=plan,
                    parent_goal_state=parent_goal_state,
                    discoveries=discoveries,
                    blocked_openers=blocked_openers,
                    layer_move_action=layer_move_action,
                    managed_session=managed_session,
                )
            else:
                prompt = _build_prover_prompt(
                    file_path, lemma_name, include_dir,
                    session_tag=session_tag, plan=plan,
                    managed_session=managed_session,
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
                f"(model={model}, timeout={timeout_minutes}min, "
                f"initial_roots={tree_initial_provers}, "
                f"max_concurrent={tree_max_concurrent})")
        try:
            output_text, returncode, winner_node, session_proved = run_tree_prover(
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
        finally:
            if _shutdown_ec_daemon(reason="tree prover finished"):
                pstatus("Prover", "Stopped EasyCrypt daemon after tree prover")
            _shutdown_run_why3server()
        pstatus("Prover", f"Winner: Tree-{winner_node}")
        if getattr(run_tree_prover, "last_destructive_abort", False):
            reason = getattr(run_tree_prover, "last_destructive_reason", "") or (
                "unknown session hygiene violation"
            )
            # A worker rm -rf'd its session dir, Edit'd the source file, or
            # accessed a forbidden proof-cache/session-transcript source; the
            # orchestrator killed all workers. We refuse to
            # write_back, refuse to mark the run as a normal failure,
            # and propagate a hard error up so the human knows to
            # investigate before retrying. Returning the usual
            # (proved=False, verified=False) tuple here would hide the
            # failure mode under the same surface as a "ran out of
            # tactics" miss.
            raise RuntimeError(
                "Prover subagent attempted a session-corrupting operation "
                f"({reason}); run "
                "aborted before write_back. Inspect the surviving "
                ".ec_session_*/ events.jsonl + proof_context_views/ and the "
                "claude trace before retrying — the agent's reasoning "
                "was off-track when it tried this and a blind retry is "
                "likely to repeat the failure.",
            )

    stdout = output_text
    stderr = ""
    elapsed = time.time() - start_time

    # Save raw output
    output_text = stdout or ""
    (run_dir / "prover_output.txt").write_text(output_text[:50000], encoding="utf-8")

    # Get session ID captured from the stream-json output (robust — no file search)
    from workflow.progress import run_tree_prover as _rtp
    session_id = getattr(_rtp, "last_session_id", "")
    session_records = list(getattr(_rtp, "last_session_ids", []) or [])
    ec_session_dir = getattr(_rtp, "last_ec_session_dir", "")
    information_source_audit = list(
        getattr(_rtp, "last_information_source_audit", []) or []
    )
    payload_audit_path = getattr(_rtp, "last_payload_audit_path", "")
    # Fallback to file search only if stream capture failed
    if not session_id:
        session_id = _find_latest_session_id(before_timestamp)
        logger.warning("Stream session_id not captured, fell back to file search")
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
        run_dir, preferred_session_dir=ec_session_dir,
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
    proved = False
    ec_file_verified = False
    event_contract_gate = None
    proof_bank_recorded = False
    tactics = _extract_tactics_from_session(
        lemma_name, parallelism, output_text,
        preferred_session_dir=ec_session_dir,
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
        proved = True
        ec_file_verified = _write_and_verify_proof(ec_full_path, lemma_name, tactics,
                                                     include_dir=include_dir,
                                                     session_proved=session_proved,
                                                     ec_session_dir=ec_session_dir)
        event_contract_gate = _acceptance_gate_for_session(ec_session_dir)
        if ec_file_verified:
            if record_proof_bank_enabled:
                # Record ordinary workflow proofs for regression testing.
                from workflow.proof_bank import record_proof
                record_proof(file_path, lemma_name, include_dir, tactics)
                proof_bank_recorded = True
            else:
                pstatus("Prover",
                        "Proof bank write skipped for eval/live-smoke run "
                        "(set record_proof_bank=True or --record-proof-bank "
                        "to opt in)")
        else:
            pstatus("Prover", "Verification failed. Reverting.", "\033[31m")
            proved = False
    else:
        partial_tactics = _extract_partial_tactics_from_session(
            lemma_name,
            parallelism,
            preferred_session_dir=ec_session_dir,
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
        "Prover finished. Proved: %s, Verified: %s, Time: %.0fs, Session: %s",
        proved, ec_file_verified, elapsed, session_id,
    )
    if session_id and not any(
        str(record.get("session_id") or "") == session_id
        for record in session_records
        if isinstance(record, dict)
    ):
        session_records.append({
            "worker": "Prover",
            "session_id": session_id,
            "winner": True,
        })
    if session_records:
        for record in session_records:
            if not isinstance(record, dict):
                continue
            if str(record.get("session_id") or "") == session_id:
                record["winner"] = True
                record["proved"] = bool(proved)
                record["verified"] = bool(ec_file_verified)
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

    return ProverResult(
        session_id=session_id,
        proved=proved,
        ec_file_verified=ec_file_verified,
        elapsed_seconds=elapsed,
        ec_session_dir=ec_session_dir,
        event_contract_checked=bool(event_contract_gate),
        event_contract_ok=bool(event_contract_gate and event_contract_gate.ok),
        event_contract_errors=(
            list(event_contract_gate.errors) if event_contract_gate else []
        ),
        archived_ec_session_dirs=archived_ec_sessions,
        resume_capsules=resume_capsules,
        information_source_audit=information_source_audit,
        proof_bank_recorded=proof_bank_recorded,
        notes=notes,
        report=prover_report,
    )






# ---------------------------------------------------------------------------
# EC file verification
# ---------------------------------------------------------------------------
















































