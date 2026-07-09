"""Run-facing progress facade: pipeline phase UI + re-exports.

Historically a 4,300-line module holding terminal UI, stream trackers,
the tree supervisor, and the phase pipeline (audit backlog #18). The
first three now live in workflow/run_ui.py, workflow/tree/trackers.py,
and workflow/tree/supervisor.py; this module keeps the pipeline phase
helpers and re-exports every moved name so existing importers and tests
are unchanged.
"""
from __future__ import annotations

import sys
import time
import shutil as _shutil
from workflow.run_ui import (  # noqa: F401  (facade re-exports)
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
from workflow.tree.trackers import (  # noqa: F401  (facade re-exports)
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
from workflow.tree.supervisor import (  # noqa: F401  (facade re-exports)
    NodeSupervisor,
    ProofTreeNode,
    _allowed_node_memory_dir,
    _build_tree_status,
    _ctx_min_runway_seconds,
    _fetch_lemma_signature,
    _find_branch_point,
    _find_layer3_live_capsule,
    _find_node_resume_capsule,
    _layer3_gates_pass,
    _layer3_select_capsule,
    _load_resume_capsule,
    _mint_fresh_resume_capsule_from_live,
    _node_memory_slug,
    _probability_budget_blocked_shape,
    _resume_replay_gate,
    _session_goal_state_text,
    _terminate_process_tree,
    respawn_disabled,
    run_tree_prover,
)





# Pipeline state — shared across orchestrator and prover













# ---------------------------------------------------------------------------
# Status printer
# ---------------------------------------------------------------------------


















# ---------------------------------------------------------------------------
# Parallel prover racing (best-of-N with progress comparison)
# ---------------------------------------------------------------------------


_CLAUDE_BIN = _shutil.which("claude") or "claude"


_BLUE = "\033[34m"


_MAGENTA = "\033[35m"


_BG_GRAY = "\033[48;5;236m"


_pipeline_state = {
    "lemma": "",
    "file": "",
    "iteration": 0,
    "max_iterations": 1,
    "phase": 0,          # 0-4
    "phase_status": {},   # phase_num -> "done" | "active" | "pending" | "skipped"
    "phase_info": {},     # phase_num -> brief info string
    "elapsed": 0.0,
    "prover_mode": "",    # "racing" | "tree"
}


_PHASE_NAMES = {
    0: "PLAN",
    1: "PROVE",
    2: "ANALYZE",
    3: "IMPROVE",
    "3b": "REGRESSION",
    4: "REPORT",
}


_PHASE_ICONS = {
    "done": "✅",
    "active": "🔄",
    "pending": "⏳",
    "skipped": "⏭️ ",
    "failed": "❌",
}


def pipeline_ui_reset():
    """No-op. Kept for API compatibility."""
    pass


def pipeline_ui_init(lemma: str, file: str, iteration: int,
                     max_iterations: int, prover_mode: str = "racing"):
    """Initialize pipeline UI state. Called by orchestrator at iteration start."""
    _pipeline_state["lemma"] = lemma
    _pipeline_state["file"] = file
    _pipeline_state["iteration"] = iteration
    _pipeline_state["max_iterations"] = max_iterations
    _pipeline_state["prover_mode"] = prover_mode
    _pipeline_state["phase_status"] = {
        0: "pending", 1: "pending", 2: "pending",
        3: "pending", "3b": "pending", 4: "pending",
    }
    _pipeline_state["phase_info"] = {}
    _pipeline_state["elapsed"] = time.time()


def pipeline_ui_phase(phase, status_str: str, info: str = ""):
    """Update a phase's status. Called by orchestrator at phase transitions."""
    _pipeline_state["phase"] = phase
    _pipeline_state["phase_status"][phase] = status_str
    if info:
        _pipeline_state["phase_info"][phase] = info


def phase_start(phase: str) -> None:
    """Print a phase header."""
    print(f"\n{_BOLD}{'─' * 50}{_RESET}")
    print(f"{_DIM}{_timestamp()}{_RESET} {_YELLOW}{_BOLD}▶ {phase}{_RESET}")
    print(f"{_BOLD}{'─' * 50}{_RESET}")
    sys.stdout.flush()


def phase_done(phase: str, result: str = "") -> None:
    """Print phase completion."""
    suffix = f" → {result}" if result else ""
    print(f"{_DIM}{_timestamp()}{_RESET} {_GREEN}{_BOLD}✓ {phase}{suffix}{_RESET}\n")
    sys.stdout.flush()


def error(agent: str, message: str) -> None:
    """Print an error."""
    print(f"{_DIM}{_timestamp()}{_RESET} {_RED}{_BOLD}✗ [{agent}]{_RESET} {_RED}{message}{_RESET}")
    sys.stdout.flush()


STRUCTURAL_TACTICS = frozenset({
    "proc", "byequiv", "byphoare", "bypr", "seq", "transitivity",
    "while", "eager", "case", "have", "inline", "call",
})


STRATEGY_TACTICS = frozenset({
    "byequiv", "byphoare", "bypr", "transitivity", "eager",
    "have",  # have-chain: branching at have level means trying a different
             # proof structure, not a different sub-proof approach
})
