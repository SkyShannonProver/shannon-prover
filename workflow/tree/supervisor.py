"""Tree-mode node supervision: spawn/poll/respawn of prover workers.

Extracted verbatim from workflow/progress.py (backlog #18): ProofTreeNode,
NodeSupervisor (the poll loop), run_tree_prover, and the respawn/capsule
helpers. The remaining known debt is decomposing NodeSupervisor.run into a
tick() method — deferred (hot supervision path).
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from workflow.schemas.config import PROVER_DEFAULTS
from workflow.proof_management.common import (
    node_memory_slug as _shared_node_memory_slug,
)
from workflow.session_observer import WorkflowSessionSnapshot, observe_session
from workflow.payload_audit import (
    PayloadAuditRecorder,
    coerce_tool_result_text,
)
from workflow.proof_management.lineage import LemmaLineageStore
from workflow.proof_management.route_family import infer_route_family
from workflow.tree.policy import (
    DEFAULT_STRUCTURAL_UNDO_SPAWN_DELAY_SECONDS as _DEFAULT_STRUCTURAL_UNDO_SPAWN_DELAY_SECONDS,
    DEFAULT_TREE_INITIAL_PROVERS as _DEFAULT_TREE_INITIAL_PROVERS,
    DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS as _DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS,
    candidate_layer_move_actions as _candidate_layer_move_actions,
    cap_tree_max_concurrent as _cap_tree_max_concurrent,
    effective_progress_count as _effective_progress_count,
    infer_abstraction_layer as _infer_abstraction_layer,
    infer_abstraction_layer_from_proof_ir as _infer_abstraction_layer_from_proof_ir,
    proof_ir_frontier_key as _proof_ir_frontier_key,
    proof_ir_slice_for_layer_move as _proof_ir_slice_for_layer_move,
    tree_spawn_branch_key as _tree_spawn_branch_key,
    tree_spawn_limit_for_branch_key as _tree_spawn_limit_for_branch_key,
    undo_repair_mode as _undo_repair_mode,
)
from workflow.run_ui import (
    _BOLD,
    _CYAN,
    _DIM,
    _GREEN,
    _RED,
    _RESET,
    _YELLOW,
    _clear_status_bar,
    _draw_status_bar,
    _set_status_bar_active,
    _status_bar_active,
    _status_bar_text,
    _timestamp,
    _update_status_bar,
    status,
)
from workflow.tree.trackers import (
    ANALYSIS_TOOL_FLAGS,
    STRUCTURAL_COMMIT_OPENERS,
    _ANALYSIS_TOOL_RE,
    _APPLY_LEMMA_RE,
    _ProverTracker,
    _TreeProverTracker,
    _assistant_context_before_tool,
    _audit_drop_empty,
    _bash_invokes_easycrypt,
    _event_log_has_candidate_closed,
    _extract_apply_lemma_names,
    _first_word,
    _handle_stream_event,
    _is_background_tool_result,
    _is_permission_denied_tool_result,
    _is_proof_success,
    _proof_intent_tool_description,
    _report_tool_call,
    _session_dir_path,
    _session_event_path,
    _session_history_path,
    _session_projection_has_candidate_closed,
    _session_snapshot,
    _session_state_has_candidate_closed,
    _summarize_tool,
    _thinking_markers,
    _truncate_audit_text,
)


def _build_tree_status(nodes: dict, elapsed: float) -> str:
    """Build a one-line tree status.

    Display uses ``committed_count`` (history.ec line count, ground truth)
    rather than ``accepted_tactics`` (event-counter, inflates from chain
    splits + replay). Without this, Run 9 children showed display 96-98
    while their actual history.ec had 4-12 lines — visually misleading.
    Internal logic (kill checks, leader picking, scoring) already uses
    ``committed_count`` per the existing comment chain, so this aligns
    user-visible status with internal ground truth.
    """
    all_nodes = list(nodes.values())
    if not all_nodes:
        return "🌳 (no provers)"
    active = [n for n in all_nodes if not n.tracker.finished]
    killed = [n for n in all_nodes if n.tracker.finished]
    leader = max(
        all_nodes,
        key=lambda n: _effective_progress_count(
            committed_count=n.tracker.committed_count,
            max_committed_count_seen=getattr(
                n.tracker,
                "max_committed_count_seen",
                n.tracker.committed_count,
            ),
            in_undo_repair=_undo_repair_mode(
                committed_count=n.tracker.committed_count,
                max_committed_count_seen=getattr(
                    n.tracker,
                    "max_committed_count_seen",
                    n.tracker.committed_count,
                ),
                last_undo_time=getattr(n.tracker, "last_undo_time", 0.0),
                last_structural_undo_time=getattr(
                    n.tracker,
                    "last_structural_undo_time",
                    0.0,
                ),
                now=time.time(),
            ),
        ),
    )

    parts = []
    for n in active:
        t = n.tracker
        c = t.committed_count
        icon = "🐝"
        in_repair = _undo_repair_mode(
            committed_count=c,
            max_committed_count_seen=getattr(t, "max_committed_count_seen", c),
            last_undo_time=getattr(t, "last_undo_time", 0.0),
            last_structural_undo_time=getattr(t, "last_structural_undo_time", 0.0),
            now=time.time(),
        )
        if time.time() - n.spawn_time < 60 and c == 0:
            icon = "🐣"
        elif in_repair:
            icon = "🔧"
        elif t.errors_since_last_accept >= 3:
            icon = "🐌"
        star = "★" if n is leader and c > 0 else ""
        parts.append(f"{icon}{n.node_id}[{c}]{star}")

    n_killed = len(killed)
    return f"🌳 {len(active)} alive │ {' '.join(parts)} │ {n_killed} killed │ {elapsed:.0f}s"


def _terminate_process_tree(
    proc: subprocess.Popen,
    *,
    grace_seconds: float = 5.0,
) -> None:
    """Terminate a worker and its descendants when it owns a process group.

    Tree workers launch Claude, MCP stdio servers, and bridge helpers. Killing
    only the worker PID can orphan those children, which is exactly what the
    2026-05-12 step3 interrupted run exposed.  Workers are spawned in a new
    session below, so the normal path sends signals to the process group; the
    fallback remains PID-only for tests or platforms where process groups are
    unavailable.
    """
    if proc.poll() is not None:
        return

    pgid: int | None = None
    try:
        candidate = os.getpgid(proc.pid)
        if candidate != os.getpgrp():
            pgid = candidate
    except (AttributeError, ProcessLookupError, PermissionError, OSError):
        pgid = None

    def _signal_group_or_proc(sig: int) -> None:
        if pgid is not None:
            try:
                os.killpg(pgid, sig)
                return
            except ProcessLookupError:
                return
            except (PermissionError, OSError):
                pass
        if sig == signal.SIGTERM:
            proc.terminate()
        else:
            proc.kill()

    _signal_group_or_proc(signal.SIGTERM)
    try:
        proc.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass

    _signal_group_or_proc(signal.SIGKILL)
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        return


def _ctx_min_runway_seconds() -> float:
    """Min wall-clock runway to start a cold Layer-3 replay (env-tunable)."""
    from workflow.ctx_respawn import min_runway_seconds

    return min_runway_seconds()


def respawn_disabled() -> bool:
    """Kill switch passthrough (defined in workflow.ctx_respawn)."""
    from workflow.ctx_respawn import respawn_disabled as _disabled

    return _disabled()


def _load_resume_capsule(path: Path):
    """Load a resume capsule manifest (lazy import to avoid an import cycle)."""
    from workflow.proof_node_resume import load_resume_capsule

    return load_resume_capsule(path)


def _find_node_resume_capsule(run_dir: Path, session_tag: str) -> Path | None:
    """Freshest in-worker checkpoint capsule for one node, or None.

    The in-worker respawn checkpoint writes capsules to
    ``run_dir/resume_capsules/<node_slug>_<session_dir.name>/resume.json``. The
    session dir is ``.ec_session_<session_tag>``, so match capsule dirs whose name
    ends with that session dir name. Newest manifest wins.
    """
    capsules_dir = Path(run_dir) / "resume_capsules"
    if not capsules_dir.is_dir():
        return None
    session_dir_name = f".ec_session_{session_tag}"
    best: tuple[float, Path] | None = None
    try:
        for child in capsules_dir.iterdir():
            if not child.is_dir():
                continue
            if not child.name.endswith(session_dir_name):
                continue
            manifest = child / "resume.json"
            if not manifest.is_file():
                continue
            mtime = manifest.stat().st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, manifest)
    except OSError:
        return None
    return best[1] if best else None


def _mint_fresh_resume_capsule_from_live(
    *,
    cwd: str,
    run_dir: Path,
    session_tag: str,
    target_file: str,
    lemma: str,
    include_dir: str = "",
) -> Path | None:
    """Mint a FRESH resume capsule from a worker's still-on-disk live session dir.

    At Layer-3 crash time the pre-written checkpoint capsule
    (``_find_node_resume_capsule``) is STALE: in-worker checkpoints are only
    written at each swap, so any tactic committed after the LAST swap (e.g. during
    the final, post-respawn-cap generation) is missing from its ``replay_prefix``,
    and its recorded ``current_goal_hash`` lags the prefix. Trusting it both loses
    that post-swap progress AND can trip the supervisor's resume-drift gate (the
    replayed child's observed goal hash won't match the lagged recorded hash),
    which kills the branch and wastes the cold replay.

    The live EC session dir ``<cwd>/.ec_session_<session_tag>`` survives worker
    death (cleanup is end-of-run, not at worker death); its ``history.ec`` holds
    the LATEST committed tactics. ``create_resume_capsules`` reads only on-disk
    files (``history.ec``, ``current.out``, the proof-state projection) — it does
    NOT require a live REPL — so we can re-mint from the dead worker's dir here.

    We mint into a fresh, isolated output dir (so the stale pre-written capsule
    stays intact as a fallback) and return the freshest manifest whose capsule
    name matches this session dir. Best-effort: returns None on any failure so the
    caller can fall back to the stale capsule. The minted capsule's
    ``replay_prefix`` and ``current_goal_hash`` come from the SAME live state, so
    it preserves post-swap progress and avoids the drift-kill.
    """
    session_dir = Path(cwd) / f".ec_session_{session_tag}"
    history_file = session_dir / "history.ec"
    try:
        if not session_dir.is_dir():
            return None
        if not history_file.is_file() or not history_file.read_text(
            encoding="utf-8", errors="ignore"
        ).strip():
            return None
    except OSError:
        return None
    try:
        from workflow.proof_node_resume import create_resume_capsules

        output_dir = Path(run_dir) / "resume_capsules_layer3_live" / session_tag
        created = create_resume_capsules(
            project_root=Path(cwd).resolve(),
            run_dir=Path(run_dir),
            session_dirs=[session_dir],
            target_file=str(target_file or ""),
            lemma=str(lemma or ""),
            include_dir=str(include_dir or ""),
            output_dir=output_dir,
        )
    except Exception:
        return None
    if not created:
        return None
    # The freshest manifest for THIS session dir (create_resume_capsules names
    # capsule dirs `<node_slug>_<session_dir.name>`); match by the session dir
    # name so a stray capsule from another tree can never be picked.
    return _find_layer3_live_capsule(output_dir, session_tag)


def _layer3_gates_pass(
    *,
    respawn_disabled: bool,
    already_respawned: bool,
    proved: bool,
    supervisor_killed: bool,
    worker_crashed: bool,
    context_respawn_count: int,
    committed_count: int,
    depth: int,
    max_depth: int,
    has_run_dir: bool,
    has_runway: bool,
    has_replay_prefix: bool = False,
) -> bool:
    """Pure Layer-3 admission gate (every condition independent, ANDed).

    Extracted so the gate is unit-testable without standing up the whole
    ``run_tree_prover`` supervisor closure. Mirrors the inline checks in
    ``_maybe_layer3_crash_respawn`` exactly. Returns True iff a Layer-3 respawn is
    permitted (subject to a capsule actually being found downstream).
    """
    if respawn_disabled:
        return False
    if already_respawned:  # one-shot per dead node
        return False
    if proved:
        return False
    if supervisor_killed:  # only a worker SELF-exit (crash / clean give-up)
        return False
    if not worker_crashed:
        # CRASH-ONLY (the tightening): a clean give-up exits gracefully
        # (returncode 0 + a final `result` event) and shows up here as
        # `finished and not proved` — but that is a real, MEASURABLE agent
        # decision and must END the run, never be respawned. Only an ABNORMAL
        # worker death (non-zero/killed exit OR no clean final-result emitted)
        # is an infra death the agent didn't decide; replay recovers the lost
        # in-process EC state. See docs/design/context_resume_tightened.md.
        return False
    if int(context_respawn_count or 0) <= 0 and not has_replay_prefix:
        # Degraded-only: the node must have swapped context in-worker OR be a
        # continuation node (Layer-3 child / resume root) that carried a replay
        # prefix — those are by definition from degraded lineage and may exhaust
        # context before reaching the in-worker watermark.
        return False
    if int(committed_count or 0) <= 0:  # real progress only
        return False
    if int(depth) >= int(max_depth):
        return False
    if not has_run_dir:
        return False
    if not has_runway:  # wall-clock runway near end of run
        return False
    return True


def _layer3_select_capsule(
    *,
    cwd: str,
    run_dir: Path,
    session_tag: str,
    source_file: str = "",
    target_lemma: str = "",
) -> tuple[Path, str] | None:
    """Choose the resume capsule for a Layer-3 respawn (the load-bearing fix path).

    PREFER a FRESH capsule minted from the dead worker's live session dir — its
    ``replay_prefix`` includes every tactic committed since the last in-worker swap
    and its ``current_goal_hash`` is consistent with that prefix (both from the same
    live state), so it preserves post-swap progress AND avoids the resume-drift
    kill. FALL BACK to the stale pre-written in-worker checkpoint capsule only when
    the live dir is missing/unreadable/empty.

    Returns ``(manifest_path, source_label)`` where ``source_label`` is ``"live"``
    or ``"checkpoint"``, or ``None`` if neither capsule exists.
    """
    fresh = _mint_fresh_resume_capsule_from_live(
        cwd=cwd,
        run_dir=run_dir,
        session_tag=session_tag,
        target_file=str(source_file or ""),
        lemma=str(target_lemma or ""),
    )
    if fresh is not None:
        return (fresh, "live")
    stale = _find_node_resume_capsule(run_dir, session_tag)
    if stale is not None:
        return (stale, "checkpoint")
    return None


def _find_layer3_live_capsule(output_dir: Path, session_tag: str) -> Path | None:
    """Freshest freshly-minted Layer-3 capsule manifest for one session, or None."""
    session_dir_name = f".ec_session_{session_tag}"
    best: tuple[float, Path] | None = None
    try:
        for child in Path(output_dir).iterdir():
            if not child.is_dir() or not child.name.endswith(session_dir_name):
                continue
            manifest = child / "resume.json"
            if not manifest.is_file():
                continue
            mtime = manifest.stat().st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, manifest)
    except OSError:
        return None
    return best[1] if best else None


def _session_goal_state_text(
    cwd: str, session_dir: str | None, *, max_chars: int = 2000,
) -> str:
    """Return the active goal text through session_state when possible."""
    session_path = _session_dir_path(cwd, session_dir)
    if session_path is None:
        return ""
    try:
        from core.easycrypt.session_projection import read_proof_state_projection
        projection = read_proof_state_projection(session_path)
        if projection.status in ("candidate_closed", "verified"):
            parsed = projection.goal.parsed_goal or {}
            if parsed.get("post_qed_projection"):
                return "Proof is already complete; no current goal remains."
            if projection.goal.active_goal_preview:
                return projection.goal.active_goal_preview
    except Exception:
        pass
    try:
        from core.easycrypt.session_state import read_session_state
        state = read_session_state(session_path)
        text = state.raw_for_goal_tools or state.active_output
        if text:
            return text[-max_chars:] if len(text) > max_chars else text
    except Exception:
        pass
    goal_file = session_path / "current.out"
    try:
        if goal_file.exists():
            text = goal_file.read_text(encoding="utf-8", errors="replace")
            return text[-max_chars:] if len(text) > max_chars else text
    except Exception:
        pass
    return ""


def _fetch_lemma_signature(name: str, cwd: str) -> str:
    """Return the exact declaration for `name` by scanning EC theory dirs.

    Uses `core.easycrypt.ec_search.lookup_lemma_signature` directly (no
    subprocess) for speed. Returns empty string on failure.
    """
    try:
        from pathlib import Path
        from core.easycrypt.search import ec_search
        search_dirs: list[Path] = []
        for rel in ("easycrypt-src/theories", "eval/examples"):
            p = Path(cwd) / rel
            if p.is_dir():
                search_dirs.append(p)
        if not search_dirs:
            return ""
        result = ec_search.lookup_lemma_signature(name, search_dirs, None)
        # Strip the header lines — keep just the signature body
        lines = [ln for ln in result.splitlines()
                 if ln and not ln.startswith("===")
                 and not ln.startswith("Usage:")
                 and not ln.startswith("Supply ")
                 and not ln.startswith("-- ")]
        body = "\n".join(lines).strip()
        # Empty body means "no match" (lookup_lemma_signature returned the
        # "No declaration named..." message which we've just filtered out)
        if "No declaration named" in result:
            return ""
        return body
    except Exception:
        return ""


def _node_memory_slug(value: str) -> str:
    return _shared_node_memory_slug(value)


def _allowed_node_memory_dir(
    payload_audit_path: str | Path | None,
    node_label: str,
) -> Path | None:
    if not payload_audit_path:
        return None
    return (
        Path(payload_audit_path).resolve().parent
        / "node_memory"
        / _node_memory_slug(node_label)
    )


@dataclass
class ProofTreeNode:
    """A node in the recursive proof search tree."""

    node_id: str                          # "root", "root.0", "root.0.1"
    parent_id: Optional[str]
    tracker: _TreeProverTracker
    replay_prefix: list[str]              # tactics replayed at spawn
    failed_at_branch: list[str]           # negative signal from parent
    depth: int
    spawn_time: float
    grace_deadline: Optional[float] = None  # set when child is spawned
    children: list[str] = field(default_factory=list)
    expected_resume_goal_hash: str = ""
    resume_replay_gate_checked: bool = False
    route_family: dict[str, object] = field(default_factory=dict)
    route_family_event_key: str = ""
    # Fresh-context continuation Layer-3 crash net: set once this node's death
    # has been answered with a supervisor respawn (replay), so we never respawn
    # the same dead worker twice.
    layer3_respawned: bool = False


def _find_branch_point(
    tactics: list[str],
    recent_failed_tactic: str = "",
) -> Optional[tuple[list[str], list[str]]]:
    """Find a local branch point for tree divergence.

    Initial root provers already provide broad high-level strategy diversity.
    Once a parent has reached a deep EasyCrypt frontier, children should not
    jump back to the first ``have``/``byequiv`` and replay the whole proof.
    They should recover the verified prefix and explore the current frontier.

    If we know the concrete failed tactic, replay the entire accepted prefix
    and give that failed tactic as the negative signal.  If we do not know it,
    still replay the accepted prefix so the child starts where the parent got
    stuck, but leave the negative signal empty; the layer-move assignment and
    parent goal state then provide the divergence pressure.
    """
    prefix = [t for t in tactics if str(t).strip()]
    if len(prefix) < 2:
        return None
    failed = str(recent_failed_tactic or "").strip()
    if failed:
        return prefix, [failed]
    return prefix, []


def _probability_budget_blocked_shape(
    tactic: str,
    parent_goal: str,
) -> str:
    """Return a shape-level block label for product-budget failures."""

    raw = str(tactic or "").strip()
    lower = raw.lower()
    context = f"{raw}\n{parent_goal}".lower()
    probability_context = (
        "bound" in context
        and "[<=]" in context
        and "/" in context
        and ("*" in context or "^" in context)
    )
    if not probability_context:
        return ""
    if re.search(r"\bcall\s*\(\s*_:\s*true\s*\)\s*\.", lower):
        return "probability_budget:direct_call_true_under_le_bound"
    if not re.match(r"\s*seq\s+\d+\b", lower):
        return ""
    if "size " in lower and ("*" in lower or "^" in lower or "/" in lower):
        return "probability_budget:product_budget_side_fact_seq"
    if "1%r" in lower and not (r"\in" in lower or " in " in lower):
        return "probability_budget:bad_unit_seq_without_matching_event"
    return "probability_budget:specific_seq_shape_only"


def _resume_replay_gate(
    snapshot: WorkflowSessionSnapshot | None,
    *,
    replay_prefix: list[str],
    expected_goal_hash: str,
    agent_has_rewound: bool = False,
) -> tuple[bool, str]:
    """Return (checked, drift_reason) for a resumed branch replay gate.

    This is a ONE-TIME post-resume integrity check: it confirms the committed
    prefix replayed into the session matches the checkpoint we resumed from, to
    catch genuine backend replay desync.

    It must NOT fire once the agent has intentionally rewound into the prefix.
    Under transparent resume the agent owns its whole proof and may
    `undo_to_checkpoint` / `undo_last_step` into the replayed prefix to discharge
    an admit or rebuild an upstream invariant — which legitimately rewrites the
    prefix. A history/prefix mismatch is then the feature working, not desync,
    and the gate can no longer tell the two apart. A genuine replay desync shows
    up immediately on resume, BEFORE any agent undo, so gating on
    ``agent_has_rewound`` keeps real desync detection while it stops the gate
    from killing a valid branch that did exactly what Tasks #1/#2 enabled.
    """
    if not expected_goal_hash:
        return True, ""
    if agent_has_rewound:
        return True, ""
    if snapshot is None or not snapshot.exists:
        return False, ""
    if snapshot.active_tool_mutates:
        return False, ""
    expected_count = len(replay_prefix)
    history = list(snapshot.history_tactics or [])
    if len(history) < expected_count:
        return False, ""
    expected_prefix = [str(tac).strip() for tac in replay_prefix]
    observed_prefix = [str(tac).strip() for tac in history[:expected_count]]
    if observed_prefix != expected_prefix:
        return True, (
            "resume replay prefix drift: session history no longer matches "
            "the checkpoint replay prefix"
        )
    if len(history) == expected_count:
        if expected_count:
            latest_transition = (
                snapshot.latest_transition
                if isinstance(snapshot.latest_transition, dict) else {}
            )
            latest_tactic = str(latest_transition.get("tactic") or "").strip()
            if latest_tactic != expected_prefix[-1]:
                return False, ""
        observed_hash = str(snapshot.goal_hash or "")
        if not observed_hash:
            return False, ""
        if observed_hash != expected_goal_hash:
            return True, (
                "resume replay goal drift: expected "
                f"{expected_goal_hash[:12]}, observed {observed_hash[:12]}"
            )
        return True, ""
    # The child already moved beyond the checkpoint before the monitor saw the
    # exact replay state.  The prefix matched, so avoid killing a valid branch.
    return True, ""


class NodeSupervisor:
    """Owns one tree-search run: spawns/kills/respawns prover nodes and
    selects the winner. Extracted from the former run_tree_prover god-function
    with identical behavior (audit: docs/audit_node_supervisor_refactor_2026-06-22.md);
    run_tree_prover is now a thin wrapper. The former nested closures are the
    private methods on this class; run() is the monitor loop driving them.
    """

    def __init__(
        self,
        build_cmd_fn: Callable,  # (session_tag, node_id, replay_prefix, negative_signal, ...) -> cmd
        cwd: str,
        timeout: int = 1200,
        max_concurrent: int = 4,
        initial_provers: int = _DEFAULT_TREE_INITIAL_PROVERS,
        # Single source: ProverConfig (production always passes explicit values;
    # these defaults only bind for direct/test calls).
    stuck_errors: int = PROVER_DEFAULTS.tree_stuck_errors,
        stuck_idle_seconds: int = 180,   # raised from 120: need time for Mode 1→2→3 cycle
        grace_seconds: int = 180,        # raised from 120: match stuck_idle
        max_depth: int = PROVER_DEFAULTS.tree_max_depth,
        min_alive_seconds: int = 90,
        check_interval: int = 15,
        progress_gap_ratio: float = 1.5,    # kill laggard if leader has 1.5x tactics
        progress_gap_idle: int = 60,        # ...and laggard idle for this long
        structural_undo_spawn_delay_seconds: int = _DEFAULT_STRUCTURAL_UNDO_SPAWN_DELAY_SECONDS,
        undo_repair_protection_seconds: int = _DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS,
        source_file: str | None = None,
        target_lemma: str | None = None,
        initial_branches: list[dict] | None = None,
        payload_audit_path: str | Path | None = None,
    ):
        self.build_cmd_fn = build_cmd_fn
        self.cwd = cwd
        self.timeout = timeout
        # Cap at construction so self.max_concurrent is the single, capped source
        # of truth — matching the former function-top cap. Methods (e.g.
        # _try_spawn_from's make-room gate) read self.max_concurrent, so it MUST be
        # the capped value, not the raw kwarg.
        self.max_concurrent = _cap_tree_max_concurrent(max_concurrent)
        self.initial_provers = initial_provers
        self.stuck_errors = stuck_errors
        self.stuck_idle_seconds = stuck_idle_seconds
        self.grace_seconds = grace_seconds
        self.max_depth = max_depth
        self.min_alive_seconds = min_alive_seconds
        self.check_interval = check_interval
        self.progress_gap_ratio = progress_gap_ratio
        self.progress_gap_idle = progress_gap_idle
        self.structural_undo_spawn_delay_seconds = structural_undo_spawn_delay_seconds
        self.undo_repair_protection_seconds = undo_repair_protection_seconds
        self.source_file = source_file
        self.target_lemma = target_lemma
        self.initial_branches = initial_branches
        self.payload_audit_path = payload_audit_path

        # Cross-iteration loop state (owned by run(); the _tick_* phase
        # methods read/write these through self).
        self._winner = None
        self._destructive_action_detected = False
        self._destructive_action_reason = ""
        self._seen_session_dirs: set = set()
        self._source_file_path = None
        self._source_mtime_at_start = None

    def _active_nodes(self) -> list[ProofTreeNode]:
        return [n for n in self.nodes.values() if not n.tracker.finished]

    def _read_parent_goal(self, node: ProofTreeNode) -> str:
        """Read the parent prover's current goal state from its session dir."""
        session_tag = f"prover_tree_{node.node_id.replace('.', '_')}"
        return _session_goal_state_text(
            self.cwd, f".ec_session_{session_tag}", max_chars=2000,
        )

    def _branch_proof_ir(self, session_dir: Path) -> dict:
        """Read the parent's current ProofIR for child prompt slicing."""
        try:
            from core.easycrypt.session_agent_view import build_proof_context_view

            view = build_proof_context_view(session_dir, live_tool_name=None)
            proof_ir = view.get("proof_ir") if isinstance(view, dict) else None
            return proof_ir if isinstance(proof_ir, dict) else {}
        except Exception:
            return {}

    def _node_route_tactics(self, node: ProofTreeNode) -> list[str]:
        tactics = list(node.tracker.accepted_tactic_texts or [])
        if tactics:
            return tactics
        try:
            return list(node.tracker._history_lines())
        except Exception:
            return list(node.replay_prefix or [])

    def _route_family_key(self, route_family: dict) -> str:
        return json.dumps(route_family or {}, sort_keys=True)

    def _valuable_frontier(self, node: ProofTreeNode) -> bool:
        """Whether this node has reached a frontier worth preserving.

        This is intentionally proof-generic: a node is valuable because it has
        committed enough structural progress and is sitting in a typed proof
        layer, not because of any lemma name.  Valuable parents get longer
        grace before progress-gap or spawned-child cleanup can kill them.
        """
        t = node.tracker
        committed = t.committed_count
        if committed < 4 or not t.has_structural_commit:
            return False
        snapshot = t.session_snapshot
        goal_type = str(snapshot.goal_type if snapshot else "").lower()
        if committed >= 8:
            return True
        return goal_type in {"prhl", "equiv", "phoare", "hoare"}

    def _has_active_child(self, node: ProofTreeNode) -> bool:
        active_ids = {n.node_id for n in self._active_nodes()}
        return any(child_id in active_ids for child_id in node.children)

    def _node_in_undo_repair(self, node: ProofTreeNode) -> bool:
        t = node.tracker
        return _undo_repair_mode(
            committed_count=t.committed_count,
            max_committed_count_seen=t.max_committed_count_seen,
            last_undo_time=t.last_undo_time,
            last_structural_undo_time=t.last_structural_undo_time,
            now=time.time(),
            repair_window_seconds=self.undo_repair_protection_seconds,
        )

    def _node_effective_committed_count(self, node: ProofTreeNode) -> int:
        t = node.tracker
        return _effective_progress_count(
            committed_count=t.committed_count,
            max_committed_count_seen=t.max_committed_count_seen,
            in_undo_repair=self._node_in_undo_repair(node),
        )

    def _node_new_effective_commit_count(self, node: ProofTreeNode) -> int:
        try:
            return max(
                0,
                self._node_effective_committed_count(node)
                - int(getattr(node.tracker, "prefix_credit", 0) or 0),
            )
        except Exception:
            return 0

    def _protected_parent(self, node: ProofTreeNode) -> bool:
        return self._has_active_child(node) and self._valuable_frontier(node)

    def _infer_branch_layer(
        self,
        session_dir: Path,
        parent_goal: str,
        failed_suffix: list[str],
        *,
        proof_ir: dict | None = None,
    ) -> str:
        """Prefer ProofIR's typed layer; fall back to raw goal regex."""
        fallback = _infer_abstraction_layer(parent_goal, failed_suffix)
        try:
            if proof_ir is None:
                proof_ir = self._branch_proof_ir(session_dir)
            layer = _infer_abstraction_layer_from_proof_ir(proof_ir, fallback=fallback)
            return layer or fallback
        except Exception:
            return fallback

    def _attach_proof_ir_slice(
        self,
        session_dir: Path,
        layer_move_action: Optional[dict],
        proof_ir: dict | None = None,
    ) -> Optional[dict]:
        if not isinstance(layer_move_action, dict):
            return layer_move_action
        if proof_ir is None:
            proof_ir = self._branch_proof_ir(session_dir)
        proof_slice = _proof_ir_slice_for_layer_move(
            proof_ir,
            move=str(layer_move_action.get("move") or "same"),
        )
        if not proof_slice:
            return layer_move_action
        enriched = dict(layer_move_action)
        enriched["proof_ir_slice"] = proof_slice
        return enriched

    def _winner_shadow_selection(
        self,
        all_nodes: list[ProofTreeNode],
        selected: ProofTreeNode,
    ) -> dict:
        """Summarize route-family alternatives without changing selection."""

        rows = []
        family_counts: dict[str, int] = {}
        best_by_family: dict[str, dict] = {}
        for node in all_nodes:
            family = str(
                dict(node.route_family or {}).get("family") or "unknown"
            )
            committed = int(node.tracker.committed_count)
            max_seen = int(
                getattr(
                    node.tracker,
                    "max_committed_count_seen",
                    committed,
                )
            )
            row = {
                "node": f"Tree-{node.node_id}",
                "route_family": family,
                "committed_count": committed,
                "max_committed_count_seen": max_seen,
                "proved": bool(node.tracker.proved),
                "selected": node is selected,
            }
            rows.append(row)
            family_counts[family] = family_counts.get(family, 0) + 1
            previous = best_by_family.get(family)
            if previous is None or (
                committed,
                max_seen,
            ) > (
                int(previous.get("committed_count") or 0),
                int(previous.get("max_committed_count_seen") or 0),
            ):
                best_by_family[family] = row
        rows.sort(
            key=lambda item: (
                bool(item.get("proved")),
                int(item.get("committed_count") or 0),
                int(item.get("max_committed_count_seen") or 0),
            ),
            reverse=True,
        )
        selected_family = str(
            dict(selected.route_family or {}).get("family") or "unknown"
        )
        return {
            "kind": "winner_route_family_shadow",
            "mode": "shadow",
            "current_policy": "proved_else_best_committed_prefix",
            "selected_node": f"Tree-{selected.node_id}",
            "selected_route_family": selected_family,
            "route_family_counts": dict(sorted(family_counts.items())),
            "score_order": rows[:8],
            "best_by_family": [
                best_by_family[family]
                for family in sorted(best_by_family)
            ],
            "interpretation": (
                "Shadow evidence only: compare best_by_family when a run "
                "falls back to best_available_branch, but do not treat this "
                "as a changed winner policy."
            ),
        }

    def _refresh_node_route_family(
        self,
        node: ProofTreeNode,
        *,
        reason: str,
    ) -> None:
        tactics = self._node_route_tactics(node)
        route_family = infer_route_family(tactics).to_dict()
        if not route_family:
            route_family = dict(node.route_family or {})
        key = self._route_family_key(route_family)
        if not key or key == node.route_family_event_key:
            return
        node.route_family = dict(route_family)
        node.route_family_event_key = key
        self.lineage.record_route_family_assigned(
            node_id=f"Tree-{node.node_id}",
            route_family=node.route_family,
            tactic_count=len(tactics),
            reason=reason,
        )

    def _kill_node(self, node: ProofTreeNode, reason: str):
        if not node.tracker.finished and node.tracker.proc.poll() is None:
            self._refresh_node_route_family(node, reason="before_kill")
            _terminate_process_tree(node.tracker.proc)
            node.tracker.finished = True
            # Mark this as a SUPERVISOR kill so the Layer-3 crash-respawn gate
            # never resurrects it (a kill is a decision, not a crash). All
            # in-loop supervisor kill paths route through here, so one flag
            # covers drift/hygiene/destructive/capacity/progress-gap/grace/winner.
            node.tracker.supervisor_killed = True
            self.lineage.record_node_killed(
                node_id=f"Tree-{node.node_id}",
                reason=reason,
                committed_count=node.tracker.committed_count,
                max_committed_count_seen=getattr(
                    node.tracker,
                    "max_committed_count_seen",
                    node.tracker.committed_count,
                ),
                route_family=node.route_family,
            )
            self.logger.info("Killed %s: %s", node.node_id, reason)

    def _in_analysis_mode(self, node, window: float = 90.0) -> bool:
        t = node.tracker
        if t.last_analysis_call_time <= 0:
            return False
        return time.time() - t.last_analysis_call_time < window

    def _kill_least_productive(self):
        active = self._active_nodes()
        if not active:
            return
        candidates = [
            n for n in active
            if not self._protected_parent(n)
            and not self._node_in_undo_repair(n)
            and not n.tracker.waiting_on_background_mutation
        ]
        if not candidates:
            candidates = [
                n for n in active
                if not self._protected_parent(n)
                and not self._node_in_undo_repair(n)
            ] or [n for n in active if not self._protected_parent(n)] or active
        # Score: more accepted tactics = better, deeper = more speculative,
        # longer idle = less likely to recover.
        # Young provers (< min_alive_seconds) get a warmup bonus to survive.
        # Replayed prefix tactics do not count as new work, otherwise a
        # replay-only child can outrank the parent it copied.
        def score(n):
            idle = time.time() - n.tracker.last_progress_time
            alive = time.time() - n.spawn_time
            warmup_bonus = 2.0 if alive < self.min_alive_seconds else 0.0
            new_progress = self._node_new_effective_commit_count(n)
            replay_only_penalty = (
                2.0 if n.replay_prefix and new_progress == 0 else 0.0
            )
            parent_bonus = 2.0 if self._has_active_child(n) else 0.0
            frontier_bonus = 2.0 if self._valuable_frontier(n) else 0.0
            repair_bonus = 4.0 if self._node_in_undo_repair(n) else 0.0
            committed_credit = min(self._node_effective_committed_count(n), 20) * 0.2
            return (
                new_progress * 2.0
                + committed_credit
                + parent_bonus
                + frontier_bonus
                + warmup_bonus
                + repair_bonus
                - replay_only_penalty
                - 0.1 * n.depth
                - idle / 300
            )
        worst = min(candidates, key=score)
        self._kill_node(worst, f"capacity (score={score(worst):.1f})")

    def _spawn_node(
        self,
        node_id: str,
        parent_id: Optional[str],
        replay_prefix: list[str],
        negative_signal: list[str],
        depth: int,
        strategy_index: int = 0,
        parent_goal_state: str = "",
        blocked_openers: Optional[list[str]] = None,
        layer_move_action: Optional[dict] = None,
        expected_resume_goal_hash: str = "",
        spawn_reason: str = "",
        route_family: Optional[dict] = None,
        resume_context: Optional[dict] = None,
    ) -> ProofTreeNode:
        session_tag = f"prover_tree_{node_id.replace('.', '_')}"
        build_kwargs = {
            "strategy_index": strategy_index,
            "parent_goal_state": parent_goal_state,
            "discoveries": list(self.shared_discoveries),
            "blocked_openers": list(blocked_openers or []),
            "layer_move_action": layer_move_action,
        }
        if resume_context:
            build_kwargs["resume_context"] = resume_context
        cmd = self.build_cmd_fn(
            session_tag,
            node_id,
            replay_prefix,
            negative_signal,
            **build_kwargs,
        )
        if "--verbose" not in cmd:
            cmd = cmd + ["--verbose"]
        # Inject EC_SESSION_DIR so this tree's session_cli calls default to
        # the correct dir and reject any `-d <other>` typo (e.g., the default
        # `.ec_session` or a sibling tree's dir).
        child_env = os.environ.copy()
        child_env["EC_SESSION_DIR"] = f".ec_session_{session_tag}"
        child_env["SHANNON_LEGACY_DISPLAY"] = os.environ.get(
            "SHANNON_LEGACY_DISPLAY",
            "hidden",
        )
        # Fresh-context continuation safety guard #5 (in-worker runway): hand the
        # worker the supervisor's hard wall-clock deadline (unix epoch seconds) so
        # ProofNodeRuntime._wall_deadline() can refrain from starting an in-worker
        # respawn that cannot finish before the supervisor kills the run. The
        # supervisor enforces `timeout` seconds from `start_time`; without this the
        # worker has no deadline and guard #5 is dead. See
        # docs/design/fresh_context_continuation.md.
        child_env["SHANNON_NODE_DEADLINE_EPOCH"] = repr(self.start_time + float(self.timeout))
        # Retry on `OSError: [Errno 8] Exec format error` — the `claude`
        # binary is a ~215MB Mach-O bundle that gets atomically replaced
        # during Claude Code auto-update; spawns colliding with the
        # update window see a truncated file and error out. The window
        # is 2-5 seconds. Three retries with exponential backoff cover
        # it without slowing the common path. Observed 2026-04-28 —
        # mid-run auto-update killed elgamal launch (1s in) and step3
        # mid-run re-spawn (~24 min in).
        proc = None
        last_err: Optional[Exception] = None
        for attempt in range(4):
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, cwd=self.cwd, env=child_env,
                    start_new_session=True,
                )
                break
            except OSError as e:
                # errno 8 = ENOEXEC; also retry on errno 26 (ETXTBSY,
                # text file busy) which can also occur during binary
                # replacement.
                if e.errno not in (8, 26):
                    raise
                last_err = e
                wait_s = 2.0 * (2 ** attempt)  # 2, 4, 8, 16
                self.logger.warning(
                    "Spawn of Tree-%s failed with errno %d (%s) — likely "
                    "claude binary mid-update; retry %d/3 in %.0fs",
                    node_id, e.errno, e.strerror, attempt + 1, wait_s,
                )
                time.sleep(wait_s)
        if proc is None:
            # All retries exhausted — re-raise the last OSError so the
            # orchestrator gets a clear failure rather than a None proc.
            raise last_err if last_err else RuntimeError("subprocess.Popen failed")
        # Record this detached worker's process group for the supervisor's
        # backstop reaper (covers the orchestrator-SIGKILL'd-before-finally
        # case; the normal finally below already reaps via _terminate_process_tree).
        from workflow.proc_lifecycle import record_worker_pgid, WORKER_PGID_MANIFEST_ENV
        record_worker_pgid(os.environ.get(WORKER_PGID_MANIFEST_ENV), proc.pid)
        name = f"Tree-{node_id}"
        node_memory_dir = _allowed_node_memory_dir(self.payload_audit_path, name)
        tracker = _TreeProverTracker(
            proc,
            name,
            self.cwd,
            session_tag=session_tag,
            payload_audit=self.payload_audit,
            allowed_source_files=[self.source_file] if self.source_file else [],
            allowed_node_memory_dirs=[node_memory_dir] if node_memory_dir else [],
            target_lemma=str(self.target_lemma or ""),
        )
        tracker.prefix_credit = len(replay_prefix)
        inferred_family = dict(route_family or {}) or infer_route_family(
            list(replay_prefix or []),
        ).to_dict()
        node = ProofTreeNode(
            node_id=node_id,
            parent_id=parent_id,
            tracker=tracker,
            replay_prefix=replay_prefix,
            failed_at_branch=negative_signal,
            depth=depth,
            spawn_time=time.time(),
            expected_resume_goal_hash=str(expected_resume_goal_hash or ""),
            route_family=inferred_family,
        )
        # Credit prefix tactics to the child so it doesn't look like
        # it's at "0 tactics" while replaying. Without this, children
        # get killed prematurely by progress gap checks.
        if replay_prefix:
            tracker.accepted_tactics = len(replay_prefix)
        self.nodes[node_id] = node
        self.lineage.record_node_spawned(
            node_id=f"Tree-{node_id}",
            parent_id=f"Tree-{parent_id}" if parent_id and parent_id != "root" else parent_id,
            depth=depth,
            replay_prefix=list(replay_prefix or []),
            strategy_index=strategy_index,
            spawn_reason=spawn_reason,
            route_family=inferred_family,
            failed_at_branch=list(negative_signal or []),
            layer_move_action=layer_move_action,
            expected_resume_goal_hash=str(expected_resume_goal_hash or ""),
        )
        self._refresh_node_route_family(node, reason="spawn")
        return node

    def _maybe_layer3_crash_respawn(self, node: ProofTreeNode) -> bool:
        """Worker-exit fallback (Layer 3): supervisor respawn + replay.

        Fires ONLY when the WORKER PROCESS DIED ABNORMALLY (a crash — non-zero/
        killed exit or no clean `_emit_final` result) after a degraded
        (context-respawned) run while the proof was still open. The trigger is
        `finished and not proved and context_respawn_count>0 and not
        supervisor_killed and worker_crashed`. A crash is an infra death the
        agent never decided; the in-process EC session is gone, so unlike
        Layers 1-2 we pay the replay cost to rebuild proof state. A CLEAN
        give-up (returncode 0 + a final `result` event) is a real, measurable
        agent decision and does NOT fire this — the run ends on the give-up.
        `finished` cannot distinguish crash from clean exit, so `worker_crashed`
        (computed from returncode + `final_result_emitted`) gates that.
        `finished` ALSO cannot distinguish a worker self-exit from a
        deliberate `_kill_node` kill, so the `supervisor_killed` flag (set only by
        `_kill_node`) gates those out: a node the supervisor killed for drift /
        hygiene / destructive-action / capacity / progress-gap / grace / winner
        already had a decision made and must NOT be resurrected here.

        We prefer minting a FRESH capsule from the dead worker's still-on-disk live
        session dir (which holds the LATEST committed tactics, including any
        committed after the last in-worker swap) over the pre-written in-worker
        checkpoint capsule, which is STALE (it omits post-last-swap progress and
        its recorded goal hash lags the prefix — trusting it loses progress and can
        trip the resume-drift gate into killing the branch). We fall back to the
        stale checkpoint capsule only if the live dir is missing/unreadable/empty.
        Then `_spawn_node` a child from the chosen capsule's replay prefix and
        recorded goal hash (which, for a fresh capsule, come from the SAME live
        state, so they are consistent). Heavily gated and one-shot per dead node.
        Returns True iff a respawn was launched.
        See docs/design/fresh_context_continuation.md.
        """
        t = node.tracker
        run_dir = (
            Path(self.payload_audit_path).resolve().parent if self.payload_audit_path else None
        )
        # Wall-clock runway: don't start a cold replay near the end of the run.
        has_runway = (time.time() - self.start_time) <= (
            self.timeout - _ctx_min_runway_seconds()
        )
        # CRASH-ONLY signal: the worker's managed `_emit_final` (in
        # workflow/managed_prover_worker.py) prints a `result` event on EVERY
        # graceful exit (clean finish, give-up, or caught runtime exception),
        # which sets `final_result_emitted`. A hard crash (SIGKILL/OOM/segfault,
        # exit 137/143) dies before reaching it, so no `result` event arrives.
        # We treat the node as crashed iff the process exited abnormally
        # (returncode not in {0, None}) OR no clean final result was emitted. A
        # clean give-up (returncode 0 + final result) is therefore NOT a crash
        # and ends the run (measurable) instead of respawning.
        try:
            rc = t.proc.returncode if t.proc is not None else None
        except Exception:
            rc = None
        worker_crashed = (
            (rc is not None and rc != 0)
            or not bool(getattr(t, "final_result_emitted", False))
        )
        # A real qed is honored upstream (winner block, before this loop); a
        # give-up with proved=True never reaches here. Degraded-only: the node must
        # have actually swapped context in-worker, else it is an ordinary give-up we
        # must honor. committed_count>0: replaying zero tactics is pointless. depth
        # cap + one-shot (layer3_respawned) round out the gate.
        if not _layer3_gates_pass(
            respawn_disabled=respawn_disabled(),
            already_respawned=bool(node.layer3_respawned),
            proved=bool(t.proved),
            supervisor_killed=bool(getattr(t, "supervisor_killed", False)),
            worker_crashed=worker_crashed,
            context_respawn_count=int(getattr(t, "context_respawn_count", 0) or 0),
            committed_count=int(getattr(t, "committed_count", 0) or 0),
            depth=int(node.depth),
            max_depth=int(self.max_depth),
            has_run_dir=run_dir is not None,
            has_runway=has_runway,
            has_replay_prefix=bool(node.replay_prefix),
        ):
            return False
        session_tag = f"prover_tree_{node.node_id.replace('.', '_')}"
        selected = _layer3_select_capsule(
            cwd=self.cwd,
            run_dir=run_dir,
            session_tag=session_tag,
            source_file=str(self.source_file or ""),
            target_lemma=str(self.target_lemma or ""),
        )
        if selected is None:
            return False
        capsule, capsule_source = selected
        try:
            loaded = _load_resume_capsule(capsule)
        except Exception:
            return False
        replay_prefix = list(getattr(loaded, "replay_prefix", []) or [])
        if not replay_prefix:
            return False
        node.layer3_respawned = True
        child_id = f"{node.node_id}.r{int(getattr(t, 'context_respawn_count', 0))}"
        # Surface the physical death cause: the exit code (137=SIGKILL/OOM-killer,
        # 143=SIGTERM, 139=SIGSEGV) plus the last stderr line, and persist the full
        # stderr tail (poll_lines already wrote it on exit) so the post-mortem can
        # tell OOM vs uncaught-exception instead of guessing.
        t.persist_stderr(reason="layer3_crash", returncode=rc)
        _stderr_tail = (getattr(t, "_stderr_tail", "") or "").strip()
        _rc_hint = f" (exit {rc})" if rc not in (None, 0) else ""
        _last = _stderr_tail.splitlines()[-1][:160] if _stderr_tail else ""
        _tail_hint = f" last stderr: {_last}" if _last else " (no stderr captured)"
        status(
            "Orchestrator",
            f"Layer-3 crash respawn: Tree-{node.node_id} exited degraded with the "
            f"proof open{_rc_hint}; resuming from {len(replay_prefix)}-tactic "
            f"{capsule_source} capsule as Tree-{child_id}.{_tail_hint}",
            _YELLOW,
        )
        resume_context = getattr(loaded, "resume_context", None)
        resume_context = dict(resume_context) if isinstance(resume_context, dict) else {}
        # Worker-death attach (SHANNON_EC_DAEMON=1): the dead worker's EC
        # state usually survives in the detached ec_daemon, keyed by the dead
        # node's session dir. Name that dir as the attach donor so the child's
        # bootstrap can ADOPT the live session (zero replay) instead of paying
        # the per-tactic replay tax (~30 min at 167 tactics, observed
        # 2026-06-11 on equiv_step4). Verification + fallback-to-replay live in
        # workflow.proof_management.daemon_attach; with the flag off this block
        # is skipped entirely and the legacy replay path is untouched.
        try:
            from workflow.proof_management.daemon_attach import (
                daemon_session_attach_enabled,
            )

            if daemon_session_attach_enabled():
                resume_context["daemon_attach"] = {
                    "donor_session_dir": f".ec_session_{session_tag}",
                    "expected_goal_hash": str(
                        getattr(loaded, "current_goal_hash", "") or ""
                    ),
                }
        except Exception:
            pass
        # A Layer-3 respawn is OPPORTUNISTIC recovery: `_spawn_node` runs the
        # full managed-session bootstrap (build_cmd_fn -> _prepare_managed_session
        # -> manager.bootstrap -> repl.start(replay_prefix)), which replays the
        # whole prefix and can fail — e.g. ReplBackendTimeout when a deep prefix
        # with heavy smt calls exceeds the aggregate replay budget (observed
        # 2026-06-11: a 123-tactic prefix blew the 600s budget and the uncaught
        # exception killed the entire run, losing the remaining prover window
        # even though a healthy live capsule existed on disk). Any failure here
        # must degrade to "no respawn" so the supervisor loop continues and the
        # run terminates cleanly (capsules/bundles still written), never
        # propagate and kill `run_tree_prover`. `layer3_respawned` stays True:
        # the attempt consumed this node's one shot either way.
        try:
            self._spawn_node(
                child_id,
                node.node_id,
                replay_prefix,
                [],
                depth=node.depth + 1,
                parent_goal_state=str(getattr(loaded, "current_goal_preview", "") or ""),
                expected_resume_goal_hash=str(getattr(loaded, "current_goal_hash", "") or ""),
                spawn_reason="layer3_crash_respawn",
                resume_context=resume_context if isinstance(resume_context, dict) else {},
            )
        except Exception as exc:
            status(
                "Orchestrator",
                f"Layer-3 respawn of Tree-{child_id} failed during bootstrap "
                f"({type(exc).__name__}: {exc}); skipping the respawn and "
                f"continuing so the run can end cleanly.",
                _YELLOW,
            )
            self.payload_audit.record(
                "layer3_respawn_bootstrap_failed",
                node=f"Tree-{node.node_id}",
                child=f"Tree-{child_id}",
                error=f"{type(exc).__name__}: {exc}"[:1200],
                replay_prefix_count=len(replay_prefix),
            )
            return False
        node.children.append(child_id)
        return True

    def _try_spawn_from(self, node, reason_msg):
        """Try to spawn a child from node's branch point. Returns True if spawned."""
        t = node.tracker
        if node.depth >= self.max_depth:
            return False
        if t.committed_count < 2:
            return False
        branch = _find_branch_point(
            t.accepted_tactic_texts,
            recent_failed_tactic=t.recent_failed_tactic,
        )
        if branch is None:
            return False

        prefix, failed_suffix = branch

        # Capture parent's goal state before choosing a child action:
        # the generic layer classifier treats the goal surface as the
        # branch context.
        parent_goal = self._read_parent_goal(node)
        sess_dir = Path(self.cwd) / f".ec_session_{t.session_tag}"
        proof_ir = self._branch_proof_ir(sess_dir)
        snapshot = t.session_snapshot
        goal_hash = str(snapshot.goal_hash or "") if snapshot else ""
        frontier_key = _proof_ir_frontier_key(proof_ir)

        # Fact detection is memory, not strategy ownership. Generic
        # layer-move spawning below chooses the action; facts only help
        # avoid rerunning the same failed experiment.
        failed_experiment_memory = None
        try:
            from core.easycrypt.session_facts import (
                failed_branch_experiment_cluster_facts,
            )
            exp_facts = failed_branch_experiment_cluster_facts(sess_dir)
            if exp_facts:
                failed_experiment_memory = dict(exp_facts[0].payload)
        except Exception:
            failed_experiment_memory = None

        current_layer = self._infer_branch_layer(
            sess_dir,
            parent_goal,
            failed_suffix,
            proof_ir=proof_ir,
        )
        selected_action = None
        selected_branch_key = None
        for layer_move_action in _candidate_layer_move_actions(
            current_layer,
            failed_suffix=failed_suffix,
            failed_experiment_memory=failed_experiment_memory,
        ):
            branch_key = _tree_spawn_branch_key(
                len(prefix),
                failed_suffix[0] if failed_suffix else "",
                failed_experiment_memory=failed_experiment_memory,
                layer_move_action=layer_move_action,
                goal_hash=goal_hash,
                frontier_key=frontier_key,
            )
            branch_limit = _tree_spawn_limit_for_branch_key(branch_key)
            if self.exhausted_branches.get(branch_key, 0) < branch_limit:
                selected_action = layer_move_action
                selected_branch_key = branch_key
                break

        if selected_branch_key is None:
            self.logger.info(
                "Branch point exhausted (prefix=%d, layer=%s) — not spawning",
                len(prefix), current_layer,
            )
            return False
        selected_action = self._attach_proof_ir_slice(
            sess_dir,
            selected_action,
            proof_ir=proof_ir,
        )
        self.exhausted_branches[selected_branch_key] = (
            self.exhausted_branches.get(selected_branch_key, 0) + 1
        )
        child_idx = len(node.children)
        child_id = f"{node.node_id}.{child_idx}"

        # A': accumulate blocked openers. Probability-budget tactics
        # need shape-level memory: a bad side-fact `seq` should not
        # become a blanket ban on every event-preserving `seq`.
        prefix_len = len(prefix)
        blocked = list(self.branch_blocked_openers.get(prefix_len, []))
        if failed_suffix:
            fs0 = failed_suffix[0].strip()
            probability_label = _probability_budget_blocked_shape(
                fs0,
                parent_goal,
            )
            if probability_label and probability_label not in blocked:
                blocked.append(probability_label)
            elif fs0 and fs0 not in blocked:
                blocked.append(fs0)
            # Also add the first-word "opener" (e.g. "byequiv") to the
            # blocked list so the child rejects both the specific
            # failed tactic AND generic variants of it. For product
            # probability `seq`/`call` failures, keep the memory at
            # tactic-shape granularity so valid boundaries survive.
            first_word = "" if probability_label else (
                fs0.split()[0].rstrip(".;") if fs0 else ""
            )
            if first_word and first_word not in blocked:
                blocked.append(first_word)
        self.branch_blocked_openers[prefix_len] = blocked

        # Make room if needed
        if self._n_active >= self.max_concurrent:
            self._kill_least_productive()
            self._n_active = len(self._active_nodes())

        status("Orchestrator",
               f"⚡ {reason_msg} "
               f"Spawning Tree-{child_id} from Tree-{node.node_id} "
               f"(prefix: {len(prefix)} tactics, "
               f"failed: {failed_suffix[0][:40] if failed_suffix else '?'}..."
               + (f", blocked: {len(blocked)} openers" if blocked else "")
               + (
                   f", action: {current_layer}->{selected_action['move']}"
                   if selected_action else ""
               )
               + (
                   f", memory: {failed_experiment_memory['failure_shape']}"
                   if failed_experiment_memory else ""
               )
               + ")",
               _YELLOW)

        self._spawn_node(
            child_id, node.node_id, prefix, failed_suffix,
            depth=node.depth + 1,
            parent_goal_state=parent_goal,
            blocked_openers=blocked,
            layer_move_action=selected_action,
            spawn_reason=reason_msg,
        )
        self.lineage.record_repair_branch_created(
            parent_id=f"Tree-{node.node_id}",
            child_id=f"Tree-{child_id}",
            reason=reason_msg,
            prefix_count=len(prefix),
            failed_suffix=failed_suffix,
            layer_move_action=selected_action,
        )
        node.children.append(child_id)
        self._n_active = len(self._active_nodes())
        return True

    def _check_resume_replay_promises(self) -> None:
        """Kill resumed roots whose replay reconstructed a different frontier
        (a resume capsule is a replay promise; drift burns budget on stale state)."""
        for node in list(self._active_nodes()):
            if (
                not node.expected_resume_goal_hash
                or node.resume_replay_gate_checked
            ):
                continue
            checked, drift_reason = _resume_replay_gate(
                node.tracker.session_snapshot,
                replay_prefix=node.replay_prefix,
                expected_goal_hash=node.expected_resume_goal_hash,
                # An intentional rewind into the replayed prefix
                # (undo_to_checkpoint / undo_last_step) is the transparent-
                # resume feature, not backend desync. Once it has happened
                # the prefix is no longer authoritative — don't drift-kill.
                # Primary signal: history truncation (a stable state BOTH
                # undo intents produce). `last_undo_time` is kept only as
                # redundancy — it is set on `tactic.undone`, which
                # `undo_to_checkpoint` (force-restart) never emits, so on its
                # own it misses the very intent the prover is steered toward.
                agent_has_rewound=(
                    getattr(node.tracker, "history_ever_shrank", False)
                    or getattr(node.tracker, "last_undo_time", 0.0) > 0
                ),
            )
            if checked:
                node.resume_replay_gate_checked = True
            if drift_reason:
                status(
                    "Orchestrator",
                    f"Resume capsule drift in Tree-{node.node_id}: "
                    f"{drift_reason}. Killing branch.",
                    _YELLOW,
                )
                self._kill_node(node, "resume capsule drift")

    def _tick_session_hygiene(self, active, elapsed) -> "str | None":
        """Destructive-action watchdog + per-node session hygiene kills.
        Returns "break" to abort the run, "continue" to skip this periodic
        pass, None to proceed."""
        destructive_msgs: list[str] = []
        node_hygiene_kills: list[tuple[ProofTreeNode, str]] = []
        for node in list(active):
            session_tag = (
                f"prover_tree_{node.node_id.replace('.', '_')}"
            )
            session_dir = Path(self.cwd) / f".ec_session_{session_tag}"
            if node.tracker.unsafe_session_shell_command:
                bad = node.tracker.unsafe_session_shell_command
                if len(bad) > 220:
                    bad = bad[:217] + "..."
                if node.tracker.unsafe_information_source_reason:
                    node_hygiene_kills.append((
                        node,
                        f"Tree-{node.node_id}: prover accessed a forbidden "
                        f"information source: {bad!r}. "
                        f"{node.tracker.unsafe_information_source_reason} "
                        "Killing this tree and preserving other trees.",
                    ))
                else:
                    node_hygiene_kills.append((
                        node,
                        f"Tree-{node.node_id}: prover used an unsafe "
                        f"session command while the worker was live: "
                        f"{bad!r}. Killing this tree and preserving "
                        "other trees.",
                    ))
            key = str(session_dir.resolve())
            exists_now = session_dir.exists()
            if exists_now:
                # Once we've seen the dir, future absence is a
                # destructive action. Before we've seen it, the
                # worker is just in its cold-start window (hasn't
                # run ``-start`` yet) — absence is normal.
                self._seen_session_dirs.add(key)
            elif key in self._seen_session_dirs and (
                node.tracker.proc is not None
                and node.tracker.proc.poll() is None
            ):
                destructive_msgs.append(
                    f"Tree-{node.node_id}: session_dir {session_dir} "
                    "was present earlier but has now disappeared "
                    "while the worker is still running",
                )
        if (
            self._source_file_path is not None
            and self._source_mtime_at_start is not None
            and self._source_file_path.exists()
        ):
            try:
                cur_mtime = self._source_file_path.stat().st_mtime
            except Exception:
                cur_mtime = self._source_mtime_at_start
            if cur_mtime > self._source_mtime_at_start + 0.5:
                destructive_msgs.append(
                    f"Source file {self._source_file_path} mtime advanced "
                    f"({self._source_mtime_at_start:.0f} → {cur_mtime:.0f}); "
                    "an Edit/Write bypassed the orchestrator's "
                    "write_back contract",
                )
        if node_hygiene_kills:
            for node, msg in node_hygiene_kills:
                status("Orchestrator", f"SESSION HYGIENE — {msg}", _YELLOW)
                self.logger.warning("session hygiene node kill: %s", msg)
                self._kill_node(node, "session hygiene node kill")
            # Forbidden information sources pollute that worker's reasoning,
            # but not the whole forest. Let clean siblings continue; if this
            # killed the last active node, the normal best-prefix fallback
            # below will end the run.
            if self._active_nodes():
                return "continue"
            return "break"

        if destructive_msgs:
            self._destructive_action_detected = True
            self._destructive_action_reason = "; ".join(destructive_msgs)
            status("Orchestrator",
                   "SESSION HYGIENE / DESTRUCTIVE ACTION DETECTED — "
                   "aborting run for human investigation:", _RED)
            for msg in destructive_msgs:
                status("Orchestrator", f"  ✗ {msg}", _RED)
            status("Orchestrator",
                   "Inspect each surviving session dir's "
                   "events.jsonl + proof_context_views/ + the claude trace "
                   "before retrying. Don't blindly rerun — the "
                   "agent's reasoning was off-track when it tried "
                   "this.", _RED)
            self.logger.error(
                "session hygiene/destructive action detected; aborting run: %s",
                self._destructive_action_reason,
            )
            for node in list(active):
                self._kill_node(node, "destructive action abort")
            return "break"
        return None

    def _tick_display(self, active, elapsed) -> None:
        """Progress lines (committed_count ground truth) + the status bar."""
        for node in active:
            t = node.tracker
            idle = time.time() - getattr(
                t,
                "last_activity_time",
                t.last_progress_time,
            )
            waiting = (
                ", waiting_on_session_cli"
                if t.waiting_on_background_mutation else ""
            )
            repair = ", undo_repair" if self._node_in_undo_repair(node) else ""
            status("Orchestrator",
                   f"  Tree-{node.node_id} (d={node.depth}): "
                   f"{t.committed_count} tactics, {t.errors} errors, "
                   f"errs_since_accept={t.errors_since_last_accept}, "
                   f"idle {idle:.0f}s{waiting}{repair} "
                   f"({elapsed:.0f}s elapsed)",
                   _DIM)

        # Status bar
        _update_status_bar(_build_tree_status(self.nodes, elapsed))

    def _tick_capture_discoveries(self, active) -> None:
        """Harvest [SEARCH]/lemma discoveries from prover streams into shared_discoveries."""
        for node in active:
            t = node.tracker
            for tac in t.accepted_tactic_texts:
                # Capture lemma names used in tactics (apply, rewrite, have)
                for keyword in ["apply ", "rewrite ", "have :=", "byequiv "]:
                    if keyword in tac and tac not in self.shared_discoveries:
                        discovery = f"[Tree-{node.node_id}] {tac}"
                        if discovery not in self.shared_discoveries:
                            self.shared_discoveries.append(discovery)
                            if len(self.shared_discoveries) > 20:
                                self.shared_discoveries.pop(0)  # keep last 20

    def _tick_sig_escalation(self, active) -> None:
        """C2: inject a [SIG] discovery after repeated apply-failures on one lemma name."""
        for node in active:
            t = node.tracker
            if t.errors_since_last_accept < 1:
                continue
            for lemma_nm, count in t.attempted_applies.items():
                if count < 2:
                    continue
                sig_tag = f"[SIG] {lemma_nm}: "
                # Skip if we already injected a sig for this lemma
                if any(d.startswith(sig_tag) for d in self.shared_discoveries):
                    continue
                sig = _fetch_lemma_signature(lemma_nm, self.cwd)
                if not sig:
                    # Negative cache: don't retry every cycle
                    self.shared_discoveries.append(
                        f"{sig_tag}(lookup failed — name may not match any in-scope decl)"
                    )
                    if len(self.shared_discoveries) > 20:
                        self.shared_discoveries.pop(0)
                    continue
                entry = f"{sig_tag}{sig.strip()[:400]}"
                self.shared_discoveries.append(entry)
                if len(self.shared_discoveries) > 20:
                    self.shared_discoveries.pop(0)
                status("Orchestrator",
                       f"🔎 Auto-sig injected for Tree-{node.node_id}: "
                       f"{lemma_nm} attempted {count}× — signature now in "
                       f"shared discoveries for next spawn.",
                       _YELLOW)

    def _tick_spawn_on_structural_undo(self, active) -> None:
        """Trigger 1: defer-then-spawn a sibling when a node structurally undoes."""
        for node in list(active):
            t = node.tracker
            if t.structural_undo_branch is not None:
                prefix, failed = t.structural_undo_branch
                alive_time = time.time() - node.spawn_time
                branch_age = time.time() - t.structural_undo_branch_time
                if branch_age < self.structural_undo_spawn_delay_seconds:
                    if branch_age < self.check_interval + 1:
                        self.logger.info(
                            "Deferring structural-undo spawn from Tree-%s "
                            "for %.0fs: waiting for the same agent to "
                            "repair its route after undo.",
                            node.node_id,
                            self.structural_undo_spawn_delay_seconds - branch_age,
                        )
                    continue
                if (alive_time >= self.min_alive_seconds
                        and node.depth < self.max_depth
                        and len(prefix) >= 1):  # need at least 1 tactic as prefix
                    parent_goal = self._read_parent_goal(node)
                    sess_dir = Path(self.cwd) / f".ec_session_{t.session_tag}"
                    proof_ir = self._branch_proof_ir(sess_dir)
                    snapshot = t.session_snapshot
                    goal_hash = str(snapshot.goal_hash or "") if snapshot else ""
                    frontier_key = _proof_ir_frontier_key(proof_ir)
                    current_layer = self._infer_branch_layer(
                        sess_dir,
                        parent_goal,
                        failed,
                        proof_ir=proof_ir,
                    )
                    selected_action = None
                    selected_branch_key = None
                    for layer_move_action in _candidate_layer_move_actions(
                        current_layer,
                        failed_suffix=failed,
                    ):
                        branch_key = _tree_spawn_branch_key(
                            len(prefix),
                            failed[0] if failed else "",
                            layer_move_action=layer_move_action,
                            goal_hash=goal_hash,
                            frontier_key=frontier_key,
                        )
                        branch_limit = _tree_spawn_limit_for_branch_key(branch_key)
                        if self.exhausted_branches.get(branch_key, 0) < branch_limit:
                            selected_action = layer_move_action
                            selected_branch_key = branch_key
                            break
                    if selected_branch_key is None:
                        self.logger.info(
                            "Structural-undo branch exhausted "
                            "(prefix=%d, layer=%s) — not spawning",
                            len(prefix), current_layer,
                        )
                        t.structural_undo_branch = None
                        t.structural_undo_branch_time = 0.0
                        continue
                    selected_action = self._attach_proof_ir_slice(
                        sess_dir,
                        selected_action,
                        proof_ir=proof_ir,
                    )
                    self.exhausted_branches[selected_branch_key] = (
                        self.exhausted_branches.get(selected_branch_key, 0) + 1
                    )
                    child_idx = len(node.children)
                    child_id = f"{node.node_id}.{child_idx}"
                    if self._n_active >= self.max_concurrent:
                        self._kill_least_productive()
                        self._n_active = len(self._active_nodes())
                    status("Orchestrator",
                           f"⚡ Structural undo by Tree-{node.node_id} "
                           f"(undid {failed[0][:30] if failed else '?'}). "
                           f"Spawning Tree-{child_id} "
                           f"(prefix: {len(prefix)} tactics, "
                           f"action: {current_layer}->{selected_action['move']})",
                           _YELLOW)
                    self._spawn_node(
                        child_id, node.node_id, prefix, failed,
                        depth=node.depth + 1,
                        parent_goal_state=parent_goal,
                        layer_move_action=selected_action,
                        spawn_reason="structural_undo_repair_branch",
                    )
                    self.lineage.record_repair_branch_created(
                        parent_id=f"Tree-{node.node_id}",
                        child_id=f"Tree-{child_id}",
                        reason="structural_undo_repair_branch",
                        prefix_count=len(prefix),
                        failed_suffix=failed,
                        layer_move_action=selected_action,
                    )
                    node.children.append(child_id)
                    t.structural_undo_branch = None
                    t.structural_undo_branch_time = 0.0
                    self._n_active = len(self._active_nodes())
                elif alive_time >= self.min_alive_seconds:
                    t.structural_undo_branch = None
                    t.structural_undo_branch_time = 0.0

    def _tick_progress_gap(self, active) -> None:
        """Trigger 2: kill laggards behind a clear leader and rebalance one spawn."""
        rebalance_spawned = False
        if self._n_active >= 2:
            # Rank by effective committed count. During undo repair this
            # uses the node's high-water mark, because a good prover may
            # temporarily shorten history.ec while rebuilding a stronger
            # invariant or intermediate assertion.
            best = max(
                active,
                key=lambda n: (
                    self._node_new_effective_commit_count(n),
                    self._node_effective_committed_count(n),
                ),
            )
            for node in list(active):
                if node is best:
                    continue
                alive_time = time.time() - node.spawn_time
                # Children get extra warmup: base + 10s per prefix tactic
                effective_min_alive = self.min_alive_seconds
                if node.replay_prefix:
                    effective_min_alive += len(node.replay_prefix) * 10
                if alive_time < effective_min_alive:
                    continue  # protect warmup — don't kill young provers
                t = node.tracker
                if t.waiting_on_background_mutation:
                    continue
                if self._node_in_undo_repair(node):
                    continue
                idle = time.time() - t.last_accept_time
                laggard_n = t.committed_count
                leader_n = self._node_effective_committed_count(best)
                # Immunity: a tree that has earned a structural commit
                # is on a real proof path. Before killing it, require
                # either a much longer idle window (2x the normal
                # gap) or a strictly larger gap (leader has ≥3 more
                # committed tactics, not just the ratio). This is the
                # "免死金牌" — tactic count alone shouldn't outweigh
                # demonstrated structural positioning.
                structural_grace = t.has_structural_commit
                frontier_grace = self._valuable_frontier(node)
                if frontier_grace:
                    min_idle = max(self.progress_gap_idle * 4, 600)
                    min_gap = 6
                elif structural_grace:
                    min_idle = self.progress_gap_idle * 2
                    min_gap = 3
                else:
                    min_idle = self.progress_gap_idle
                    min_gap = 0
                if self._protected_parent(node) and idle < min_idle:
                    continue
                # Analysis-work grace: if the laggard ran an analysis
                # tool (-bridge-probe, -search, -sig, -try, -goal-info,
                # ...) within the gap window, it's actively doing the
                # kind of probing Step 1b prescribes before a have-> /
                # cross-file apply. Don't kill on tactic-count lag alone.
                if t.last_analysis_call_time > 0:
                    since_analysis = time.time() - t.last_analysis_call_time
                    if since_analysis < max(self.progress_gap_idle, min_idle / 2):
                        continue
                if (leader_n >= laggard_n * self.progress_gap_ratio
                        and leader_n - laggard_n >= min_gap
                        and idle >= min_idle
                        and leader_n >= 4):
                    reason_parts = [f"progress gap ({laggard_n} vs "
                                    f"{leader_n} leader, idle {idle:.0f}s)"]
                    if frontier_grace:
                        reason_parts.append("(frontier grace expired)")
                    elif structural_grace:
                        reason_parts.append("(structural grace expired)")
                    self._kill_node(node, " ".join(reason_parts))
                    # Spawn ONE child from leader (only first kill triggers spawn).
                    # Skip if leader is in analysis mode — the spawn would
                    # produce a child that duplicates the same lemma research.
                    if not rebalance_spawned:
                        if self._in_analysis_mode(best):
                            self.logger.info(
                                "Skip rebalance spawn from Tree-%s: leader is in "
                                "analysis mode (last analysis tool call %.0fs ago). "
                                "Spawn would duplicate research, not explore an "
                                "alternative strategy.",
                                best.node_id,
                                time.time() - best.tracker.last_analysis_call_time,
                            )
                        else:
                            self._try_spawn_from(best, "Rebalancing from leader.")
                        rebalance_spawned = True
                    self._n_active = len(self._active_nodes())

    def _tick_error_accumulation(self, active) -> None:
        """Trigger 3 (fallback): spawn from nodes accumulating rejects while idle."""
        for node in list(self._active_nodes()):
            t = node.tracker
            alive_time = time.time() - node.spawn_time
            effective_min_alive = self.min_alive_seconds
            if node.replay_prefix:
                effective_min_alive += len(node.replay_prefix) * 10
            if alive_time < effective_min_alive:
                continue
            if t.stuck_handled:
                continue
            if t.committed_count < 2:
                continue
            if t.waiting_on_background_mutation:
                continue
            if self._node_in_undo_repair(node):
                continue
            idle_since_accept = time.time() - t.last_accept_time
            if (t.errors_since_last_accept >= self.stuck_errors
                    and idle_since_accept >= self.stuck_idle_seconds):
                # Skip spawn if parent is in analysis mode — errors
                # during -search/-sig research are typically about
                # finding the right lemma name; child would do the
                # same research from same prefix.
                if self._in_analysis_mode(node):
                    now = time.time()
                    if now - t.last_analysis_spawn_skip_log_time >= 30:
                        self.logger.info(
                            "Skip error-stuck spawn from Tree-%s: parent is in "
                            "analysis mode (last analysis tool call %.0fs ago).",
                            node.node_id,
                            now - node.tracker.last_analysis_call_time,
                        )
                        t.last_analysis_spawn_skip_log_time = now
                    continue
                if self._try_spawn_from(node, f"Error stuck ({t.errors_since_last_accept} errs, {idle_since_accept:.0f}s idle)."):
                    node.grace_deadline = time.time() + self.grace_seconds
                t.stuck_handled = True

    def _tick_grace_enforcement(self) -> None:
        """Kill nodes that blew the post-spawn grace period without progress."""
        for node in list(self._active_nodes()):
            if node.grace_deadline is None:
                continue
            if time.time() > node.grace_deadline:
                if node.tracker.waiting_on_background_mutation:
                    node.grace_deadline = time.time() + self.grace_seconds
                    self.logger.info(
                        "Extending grace for Tree-%s: waiting on "
                        "background session_cli mutation.",
                        node.node_id,
                    )
                    continue
                if self._node_in_undo_repair(node):
                    node.grace_deadline = time.time() + self.grace_seconds
                    self.logger.info(
                        "Extending grace for Tree-%s: undo-repair window "
                        "is active.",
                        node.node_id,
                    )
                    continue
                if node.tracker.last_accept_time < (node.grace_deadline - self.grace_seconds):
                    idle_since_accept = time.time() - node.tracker.last_accept_time
                    preserve_window = max(self.grace_seconds * 3, 900)
                    if (
                        self._valuable_frontier(node)
                        and idle_since_accept < preserve_window
                    ):
                        node.grace_deadline = time.time() + self.grace_seconds
                        self.logger.info(
                            "Extending grace for Tree-%s: valuable frontier "
                            "idle %.0fs < %.0fs",
                            node.node_id,
                            idle_since_accept,
                            preserve_window,
                        )
                        continue
                    self._kill_node(node, "grace period expired, no new progress")
                else:
                    node.grace_deadline = None

    def run(self) -> tuple:
        # Rebind config onto locals so the monitor body below reads as it did in
        # the former run_tree_prover (the body uses bare `cwd`/`timeout`/... ; the
        # methods read self.*). last_* writes target the module-global
        # run_tree_prover wrapper, exactly as before.
        build_cmd_fn = self.build_cmd_fn
        cwd = self.cwd
        timeout = self.timeout
        max_concurrent = self.max_concurrent
        initial_provers = self.initial_provers
        stuck_errors = self.stuck_errors
        stuck_idle_seconds = self.stuck_idle_seconds
        grace_seconds = self.grace_seconds
        max_depth = self.max_depth
        min_alive_seconds = self.min_alive_seconds
        check_interval = self.check_interval
        progress_gap_ratio = self.progress_gap_ratio
        progress_gap_idle = self.progress_gap_idle
        structural_undo_spawn_delay_seconds = self.structural_undo_spawn_delay_seconds
        undo_repair_protection_seconds = self.undo_repair_protection_seconds
        source_file = self.source_file
        target_lemma = self.target_lemma
        initial_branches = self.initial_branches
        payload_audit_path = self.payload_audit_path
        import logging
        self.logger = logging.getLogger("workflow.progress.tree_prover")
        logger = self.logger
        # max_concurrent is already capped in __init__ (self.max_concurrent),
        # rebound capped into this local above; cap is no longer repeated here.
        initial_provers = max(1, min(int(initial_provers or 1), max_concurrent))
        run_tree_prover.last_session_ids = []
        run_tree_prover.last_information_source_audit = []
        run_tree_prover.last_payload_audit_path = ""
        resume_root_policy = "score"
        if initial_branches:
            resume_root_policy = str(
                (initial_branches[0] or {}).get("resume_root_policy") or "score"
            )
        self.payload_audit = PayloadAuditRecorder(payload_audit_path)
        payload_audit = self.payload_audit
        self.lineage = LemmaLineageStore(
            run_dir=(
                Path(payload_audit_path).resolve().parent
                if payload_audit_path else None
            ),
        )
        lineage = self.lineage
        if payload_audit_path:
            run_tree_prover.last_payload_audit_path = str(Path(payload_audit_path))
            payload_audit.record(
                "run_start",
                cwd=str(cwd),
                timeout=timeout,
                max_concurrent=max_concurrent,
                initial_provers=initial_provers,
                resume_roots=len(initial_branches or []),
                resume_root_policy=resume_root_policy,
                structural_undo_spawn_delay_seconds=structural_undo_spawn_delay_seconds,
                undo_repair_protection_seconds=undo_repair_protection_seconds,
            )
        lineage.record_tree_run_started(
            cwd=str(cwd),
            timeout=timeout,
            max_concurrent=max_concurrent,
            initial_provers=initial_provers,
            resume_roots=len(initial_branches or []),
            resume_root_policy=resume_root_policy,
        )

        self.nodes: dict[str, ProofTreeNode] = {}
        nodes = self.nodes
        self.shared_discoveries: list[str] = []  # accumulated across all provers
        shared_discoveries = self.shared_discoveries

        # --- Start initial provers (children of the root node) ---
        resume_branches = list(initial_branches or [])
        n_initial = min(
            len(resume_branches) if resume_branches else initial_provers,
            max_concurrent,
        )
        # self.start_time must be assigned BEFORE the initial self._spawn_node calls
        # below: self._spawn_node reads self.start_time to compute the
        # SHANNON_NODE_DEADLINE_EPOCH child-env value. Assigning it after the spawns
        # (its previous location) raised an error on the first spawn, crashing every
        # tree-prover run. Setting it here also makes the wall budget count from the
        # true run start (including the few seconds of spawn/setup), which is correct.
        self.start_time = time.time()
        start_time = self.start_time
        _set_status_bar_active(True)
        if resume_branches:
            status("Orchestrator",
                   f"Tree prover: resuming {n_initial} checkpoint root(s)")
            for i, branch in enumerate(resume_branches[:n_initial]):
                node_id = f"0.{i}"
                lineage.record_resume_root_chosen(
                    node_id=f"Tree-{node_id}",
                    capsule_path=str(branch.get("capsule_path") or ""),
                    capsule_score=float(branch.get("capsule_score") or 0.0),
                    tactic_count=len(list(branch.get("replay_prefix") or [])),
                    route_family=(
                        branch.get("route_family")
                        if isinstance(branch.get("route_family"), dict) else {}
                    ),
                    resume_diversity=(
                        branch.get("resume_diversity")
                        if isinstance(branch.get("resume_diversity"), dict) else {}
                    ),
                    resume_root_policy=str(
                        branch.get("resume_root_policy") or "score"
                    ),
                )
                self._spawn_node(
                    node_id,
                    "root",
                    list(branch.get("replay_prefix") or []),
                    list(branch.get("negative_signal") or []),
                    depth=0,
                    strategy_index=i,
                    parent_goal_state=str(branch.get("parent_goal_state") or ""),
                    blocked_openers=list(branch.get("blocked_openers") or []),
                    layer_move_action=branch.get("layer_move_action"),
                    expected_resume_goal_hash=str(branch.get("expected_goal_hash") or ""),
                    spawn_reason="resume_root",
                    route_family=(
                        branch.get("route_family")
                        if isinstance(branch.get("route_family"), dict) else {}
                    ),
                    resume_context=(
                        branch.get("resume_context")
                        if isinstance(branch.get("resume_context"), dict) else {}
                    ),
                )
        else:
            status("Orchestrator",
                   f"Tree prover: starting {n_initial} provers from root")
            for i in range(n_initial):
                self._spawn_node(
                    f"0.{i}",
                    "root",
                    [],
                    [],
                    depth=0,
                    strategy_index=i,
                    spawn_reason="initial_root",
                )

        # start_time is now assigned earlier (before the initial spawns); see the
        # note there. Only keep the derived bookkeeping here.
        last_check = start_time
        self._winner: Optional[ProofTreeNode] = None
        self._destructive_action_detected = False
        self._destructive_action_reason = ""

        # Capture source-file mtime up-front. Any change to this file by a
        # subagent (Edit/Write that bypassed the deny list) is treated as a
        # corrupting action and aborts the run. None means "skip this check"
        # (used in tests / non-orchestrator callers).
        self._source_file_path = Path(source_file) if source_file else None
        self._source_mtime_at_start: Optional[float] = None
        if self._source_file_path is not None and self._source_file_path.exists():
            try:
                self._source_mtime_at_start = self._source_file_path.stat().st_mtime
            except Exception:
                self._source_mtime_at_start = None

        # Track which session dirs have been observed at least once. The
        # destructive-action watchdog only fires on "dir was here, then
        # disappeared" — not on the cold-start window where the worker is
        # alive but hasn't run ``-start`` yet (orchestrator pre-wiped all
        # ``.ec_session_*`` dirs before launch, so initially-absent dirs
        # are normal). Without this gate the watchdog spuriously aborted
        # 16 s into ChaChaPoly step1 run #2 (2026-05-03) before any worker
        # had a chance to create its session dir.
        self._seen_session_dirs: set[str] = set()

        # Persistent branch memory across check cycles. These maps intentionally
        # live for the whole tree run: otherwise a branch that was exhausted in
        # one monitoring tick can be respawned on the next tick with only trivial
        # tactic-syntax variation.
        self.exhausted_branches: dict[tuple[object, str], int] = {}
        exhausted_branches = self.exhausted_branches
        self.branch_blocked_openers: dict[int, list[str]] = {}
        branch_blocked_openers = self.branch_blocked_openers

        try:
            while True:
                elapsed = time.time() - start_time

                if elapsed > timeout:
                    status("Orchestrator",
                           f"Tree prover timeout ({timeout}s). Stopping all.",
                           _YELLOW)
                    break

                # Poll all active trackers
                active = self._active_nodes()
                if not active:
                    break

                for node in active:
                    node.tracker.poll_lines()
                    self._refresh_node_route_family(node, reason="poll")

                # Resume checkpoints are replay promises. If a replayed root
                # reconstructs a different frontier, kill it before it burns
                # strategy budget on a stale state.
                self._check_resume_replay_promises()

                # Check for winners
                for node in self._active_nodes():
                    if node.tracker.proved:
                        self._winner = node
                        status("Orchestrator",
                               f"Tree-{node.node_id} proved it! "
                               f"Killing {len(self._active_nodes()) - 1} other provers.",
                               _GREEN)
                        break
                if self._winner:
                    # Kill all others, let winner finish
                    for node in self._active_nodes():
                        if node is not self._winner:
                            self._kill_node(node, "winner found")
                    # Wait for winner to finish (write proof, etc.)
                    try:
                        self._winner.tracker.proc.wait(timeout=300)
                    except subprocess.TimeoutExpired:
                        _terminate_process_tree(self._winner.tracker.proc)
                    # Drain remaining output
                    self._winner.tracker.poll_lines()
                    break

                # Check for finished provers (result event)
                for node in list(nodes.values()):
                    if node.tracker.finished and not node.tracker.proved:
                        # The worker process finished without a proof. If it died
                        # degraded (had swapped context in-worker) with the proof
                        # still open, the in-process EC session is gone — pay the
                        # replay cost ONCE to continue from the checkpoint capsule
                        # (Layer 3, crash-only). Otherwise (a non-degraded give-up or
                        # a clean finish) honor it; do nothing.
                        self._maybe_layer3_crash_respawn(node)

                # --- Periodic checks ---
                if time.time() - last_check < check_interval:
                    time.sleep(1)
                    continue
                last_check = time.time()

                active = self._active_nodes()
                self._n_active = len(active)

                # --- Destructive-action watchdog ---
                # rm -rf'ing a session dir or Edit'ing the source .ec file
                # mid-proof are both signals that a worker has fallen into a
                # corrupt reasoning loop (observed on ChaChaPoly step1
                # 2026-05-03). The deny list on subagent launch should
                # block these, but if the agent finds a way around it (or
                # this watchdog is the first to catch a future regression),
                # we abort the run and surface state to a human for
                # debugging — don't let API tokens burn on a bad path.
                flow = self._tick_session_hygiene(active, elapsed)
                if flow == "break":
                    break
                if flow == "continue":
                    continue

                # Progress display.
                # `committed_count` (history.ec ground truth) is the user-visible
                # tactic count — `accepted_tactics` is the event counter that
                # inflates from chain '.' splits + replay (Run 9 children
                # showed display 96-98 vs ground-truth 4-12).
                self._tick_display(active, elapsed)

                # --- Capture discoveries from provers ---
                # When a prover uses -search and finds something, or accepts
                # a tactic with a useful lemma name, capture it.
                self._tick_capture_discoveries(active)

                # --- C2: Auto-escalation on repeat apply failures ---
                # When the same lemma name has been attempted 2+ times on a node
                # that is currently in an error-streak, the prover is guessing
                # argument patterns. Fetch its signature once and inject a [SIG]
                # discovery so subsequent child spawns see the exact declaration.
                self._tick_sig_escalation(active)

                # Helper: is `node` actively doing analysis (search/sig/clones/
                # bridge-probe/...)? If yes, the stuckness it shows is technical
                # research, not a strategic dead end. Spawning a child from it
                # would just have the child redo the same analysis — wasted
                # budget. The kill check already has this immunity at L1879;
                # this extends it to spawn. Observed in step3 Run 9: 3 children
                # spawned from Tree-0.1 while it was researching SplitD.test
                # subtype lemmas (val_insubd, toint_ofintd, C.tointK, ...). All
                # children replayed the prefix and ran into the same lemma-
                # naming wall. Total wasted spawn time: ~25 min, with each
                # child only depositing 4-12 lines into history.ec.

                # --- Trigger 1: Structural undo ---
                # A structural undo is often the prover repairing its own route
                # (e.g. undoing to strengthen an invariant). Defer sibling spawn
                # first; if the same node accepts a repair step, the saved branch
                # is cleared and no child is needed.
                self._tick_spawn_on_structural_undo(active)

                # --- Trigger 2: Progress gap elimination ---
                # If the leader is significantly ahead, kill laggards and spawn
                # ONE child from the leader's branch point. Only 1 spawn per
                # check cycle to avoid cascading duplicates.
                # IMPORTANT: Skip nodes younger than min_alive_seconds — they
                # need time to warm up (start session, replay prefix, research).
                # Children (depth > 0) get extra time proportional to prefix
                # length because they replay the parent's tactics first.
                self._tick_progress_gap(active)

                # --- Trigger 3: Error accumulation (fallback) ---
                self._tick_error_accumulation(active)

                # --- Grace period enforcement ---
                self._tick_grace_enforcement()

                # --- Capacity enforcement ---
                while len(self._active_nodes()) > max_concurrent:
                    self._kill_least_productive()

                time.sleep(1)

        finally:
            # Clean up all remaining processes
            for node in nodes.values():
                if not node.tracker.finished and node.tracker.proc.poll() is None:
                    _terminate_process_tree(node.tracker.proc)
                    node.tracker.finished = True

        # Determine winner
        if self._winner is None:
            all_nodes = list(nodes.values())
            if all_nodes:
                # Priority 1: structured candidate closure from the observer.
                structured_closers = [
                    n for n in all_nodes
                    if n.tracker.session_snapshot
                    and (
                        n.tracker.session_snapshot.candidate_ready
                        or n.tracker.session_snapshot.final_ready
                    )
                ]
                if structured_closers:
                    self._winner = max(
                        structured_closers,
                        key=lambda n: n.tracker.committed_count,
                    )
                    self._winner.tracker.proved = True
                    status("Orchestrator",
                           f"No in-loop winner; recovering from observer snapshot: "
                           f"Tree-{self._winner.node_id} has candidate_ready "
                           f"({self._winner.tracker.committed_count} tactics).",
                           _GREEN)
                else:
                    # Compatibility fallback: old sessions without structured
                    # artifacts may only have history.ec ending in qed.
                    # Without this preference, extract_tactics could later pick a
                    # different qed-closing node than the one reported here.
                    qed_closers = []
                    for n in all_nodes:
                        hist = Path(cwd) / f".ec_session_prover_tree_{n.node_id.replace('.', '_')}" / "history.ec"
                        if hist.exists():
                            try:
                                lines = hist.read_text(encoding="utf-8").splitlines()
                                if any(ln.strip().lower().rstrip(".").strip() == "qed"
                                       for ln in lines):
                                    qed_closers.append(n)
                            except Exception:
                                pass
                    if qed_closers:
                        # Pick the qed-closer with most history tactics (deepest proof)
                        def _hist_len(n):
                            hist = Path(cwd) / f".ec_session_prover_tree_{n.node_id.replace('.', '_')}" / "history.ec"
                            try:
                                return sum(1 for ln in hist.read_text(encoding="utf-8").splitlines() if ln.strip())
                            except Exception:
                                return 0
                        self._winner = max(qed_closers, key=_hist_len)
                        self._winner.tracker.proved = True  # extraction-time qed → compatibility success
                        status("Orchestrator",
                               f"No in-loop winner; recovering from history.ec scan: "
                               f"Tree-{self._winner.node_id} closed with qed ({_hist_len(self._winner)} tactics).",
                               _GREEN)
                    else:
                        # Fallback: most committed tactics (no candidate found anywhere)
                        self._winner = max(all_nodes, key=lambda n: n.tracker.committed_count)
                        status("Orchestrator",
                               f"No prover succeeded. Best: Tree-{self._winner.node_id} "
                               f"({self._winner.tracker.committed_count} tactics)",
                               _YELLOW)
            else:
                # Should not happen
                run_tree_prover.last_session_id = ""
                run_tree_prover.last_ec_session_dir = ""
                return "", 1, "root"

        rc = (self._winner.tracker.proc.wait(timeout=5)
              if self._winner.tracker.proc.poll() is None
              else (self._winner.tracker.proc.returncode or 0))

        # Store winner's session_id
        for node in nodes.values():
            self._refresh_node_route_family(node, reason="run_end")

        run_tree_prover.last_session_id = self._winner.tracker.session_id
        run_tree_prover.last_session_ids = [
            {
                "node": f"Tree-{node.node_id}",
                "session_id": node.tracker.session_id,
                "winner": node is self._winner,
                "proved": bool(node.tracker.proved),
                "committed_count": int(node.tracker.committed_count),
                "max_committed_count_seen": int(
                    getattr(
                        node.tracker,
                        "max_committed_count_seen",
                        node.tracker.committed_count,
                    )
                ),
            }
            for node in sorted(nodes.values(), key=lambda n: n.node_id)
            if node.tracker.session_id
        ]
        winner_session_dir = _session_dir_path(cwd, self._winner.tracker._session_dir)
        run_tree_prover.last_ec_session_dir = (
            str(winner_session_dir.resolve()) if winner_session_dir else ""
        )
        information_source_audit: list[dict[str, str]] = []
        for node in sorted(nodes.values(), key=lambda n: n.node_id):
            for item in node.tracker.information_source_audit:
                information_source_audit.append({
                    "tree": node.node_id,
                    **item,
                })
        run_tree_prover.last_information_source_audit = information_source_audit

        # Log tree summary
        total_spawned = len(nodes)
        max_depth_reached = max(n.depth for n in nodes.values())
        status("Orchestrator",
               f"Tree prover done: {total_spawned} node(s) spawned, "
               f"max depth {max_depth_reached}, "
               f"winner: Tree-{self._winner.node_id}",
               _CYAN)
        lineage.record_winner_selected(
            node_id=f"Tree-{self._winner.node_id}",
            proved=self._winner.tracker.proved,
            returncode=rc,
            committed_count=self._winner.tracker.committed_count,
            max_committed_count_seen=getattr(
                self._winner.tracker,
                "max_committed_count_seen",
                self._winner.tracker.committed_count,
            ),
            route_family=self._winner.route_family,
            selection_reason=(
                "proved" if self._winner.tracker.proved else "best_available_branch"
            ),
            shadow_selection=self._winner_shadow_selection(
                list(nodes.values()),
                self._winner,
            ),
        )
        lineage.record_tree_run_finished(
            winner_node_id=f"Tree-{self._winner.node_id}",
            total_spawned=total_spawned,
            max_depth=max_depth_reached,
            proved=self._winner.tracker.proved,
            returncode=rc,
        )
        payload_audit.record(
            "run_end",
            winner=f"Tree-{self._winner.node_id}",
            total_spawned=total_spawned,
            max_depth=max_depth_reached,
            proved=self._winner.tracker.proved,
            returncode=rc,
        )

        _set_status_bar_active(False)
        # Surface the destructive-action abort flag so the caller (prover.run)
        # can refuse to mark the run as a normal failure and instead halt
        # the whole pipeline with a clear human-investigation message.
        run_tree_prover.last_destructive_abort = bool(self._destructive_action_detected)
        run_tree_prover.last_destructive_reason = self._destructive_action_reason
        return self._winner.tracker.result_text, rc, self._winner.node_id, self._winner.tracker.proved


def run_tree_prover(
    build_cmd_fn: Callable,  # (session_tag, node_id, replay_prefix, negative_signal, ...) -> cmd
    cwd: str,
    timeout: int = 1200,
    max_concurrent: int = 4,
    initial_provers: int = _DEFAULT_TREE_INITIAL_PROVERS,
    stuck_errors: int = 5,           # raised from 3: compose-first provers iterate via chain
    stuck_idle_seconds: int = 180,   # raised from 120: need time for Mode 1→2→3 cycle
    grace_seconds: int = 180,        # raised from 120: match stuck_idle
    max_depth: int = 4,
    min_alive_seconds: int = 90,
    check_interval: int = 15,
    progress_gap_ratio: float = 1.5,    # kill laggard if leader has 1.5x tactics
    progress_gap_idle: int = 60,        # ...and laggard idle for this long
    structural_undo_spawn_delay_seconds: int = _DEFAULT_STRUCTURAL_UNDO_SPAWN_DELAY_SECONDS,
    undo_repair_protection_seconds: int = _DEFAULT_UNDO_REPAIR_PROTECTION_SECONDS,
    source_file: str | None = None,
    target_lemma: str | None = None,
    initial_branches: list[dict] | None = None,
    payload_audit_path: str | Path | None = None,
) -> tuple[str, int, str]:
    """Recursive tree prover: spawn children at branch points when provers get stuck.

    Starts with `initial_provers` independent root provers exploring different
    paths simultaneously. When any prover gets stuck, spawns a child at the
    last good branch point with negative signal about what was tried.

    Args:
        build_cmd_fn: Callback (session_tag, node_id, replay_prefix, negative_signal) -> cmd list
        cwd: Working directory for subprocesses
        timeout: Total wall-clock timeout in seconds
        max_concurrent: Max active provers at any time
        initial_provers: Number of root provers to start simultaneously
        initial_branches: Optional replayed roots for proof-node resume runs.
            Each branch may contain replay_prefix, parent_goal_state,
            negative_signal, blocked_openers, layer_move_action, and
            expected_goal_hash.
        stuck_errors: Errors since last accept to trigger spawn
        stuck_idle_seconds: Idle since last accept to trigger spawn
        grace_seconds: Grace period for stuck prover after child spawns
        max_depth: Max recursion depth (safety cap)
        min_alive_seconds: Min time alive before stuck detection
        check_interval: Seconds between monitoring checks
        structural_undo_spawn_delay_seconds: Delay before spawning from a
            structural undo. If the parent accepts a repair step first, no
            child is spawned.
        undo_repair_protection_seconds: Time window where tactic-count gap
            scheduling uses the node's high-water mark after undo repair.

    Returns:
        (result_text, returncode, winner_node_id, session_proved)
        session_proved is True if EC confirmed the proof via "added lemma".
    """
    return NodeSupervisor(
        build_cmd_fn,
        cwd,
        timeout=timeout,
        max_concurrent=max_concurrent,
        initial_provers=initial_provers,
        stuck_errors=stuck_errors,
        stuck_idle_seconds=stuck_idle_seconds,
        grace_seconds=grace_seconds,
        max_depth=max_depth,
        min_alive_seconds=min_alive_seconds,
        check_interval=check_interval,
        progress_gap_ratio=progress_gap_ratio,
        progress_gap_idle=progress_gap_idle,
        structural_undo_spawn_delay_seconds=structural_undo_spawn_delay_seconds,
        undo_repair_protection_seconds=undo_repair_protection_seconds,
        source_file=source_file,
        target_lemma=target_lemma,
        initial_branches=initial_branches,
        payload_audit_path=payload_audit_path,
    ).run()
