"""Long-lived prover-agent runtime for one managed proof node.

A worker process hosts exactly one ``ProofNodeRuntime``.  The runtime starts a
manager-owned EasyCrypt node plus one long-lived Claude agent session.  Claude
does not receive backend commands or own proof state; it calls the structured
``submit_proof_intent`` MCP tool, which proxies the existing JSON proof intents
to the internal manager bridge, receives the refreshed ProverWorkspaceView, and
keeps going in the same Claude session.
"""
from __future__ import annotations

import functools
import json
import os
import re
import secrets
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.easycrypt.session_workspace_view_manager import WorkspaceViewManager
from core.easycrypt.committed_history import (
    closed_history_tactics as _closed_history_tactics,
)
from workflow.proof_management.common import read_jsonl
from workflow.proof_management.common import (
    node_memory_slug as _shared_node_memory_slug,
)
from workflow.surface_turn_model import (
    compose_surface_turn,
    proof_surface_from_turn,
    render_surface_turn_markdown,
)

# Gentle reminder prepended to `latest_workspace_view.json` for the L1
# goal-projection baseline. That file is now audit/replay data rather than an
# advertised recovery target, but an agent may still stumble into it through a
# prior run or manual context. Keep the content full for replay/audit and lead
# with this notice so the file is clearly off-surface.
_L1_OFF_SURFACE_NOTICE = (
    "Note for the L1 goal-projection agent: this file is the manager's full audit "
    "view and is intentionally NOT part of your surface. Your current goal is already "
    "shown in full in your latest manager followup — that inline goal is the complete "
    "surface you are meant to act from. You do not need to open this file; decide your "
    "next proof intent from the inline goal rather than from the panels below."
)
from workflow.proof_management import (
    ManagedTurn,
    NodeHealthEvent,
)
from workflow.proof_node_manager import (
    ProofNodeManager,
)
from workflow.proof_management import parse_agent_intent
from workflow.prover_io_policy import destructive_tool_denylist
from workflow.ctx_respawn import (
    CtxWatermarkDetector,
    build_accepted_spine,
    build_frontier_brief,
    min_runway_seconds,
    render_handoff_section,
    respawn_disabled,
    respawn_max,
    strip_closed_verdicts,
)

# Long-lived prompt and proof-so-far helpers. Per-turn
# followup/card presentation is owned by workflow.surface_turn_model.
from workflow.agent_prompt_render import (
    _agent_safe_action_summaries,
    _drop_empty,
    _md_proof_so_far,
    _turn_interpretation,
    render_long_lived_agent_prompt,
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_BIN = shutil.which("claude") or "claude"


@dataclass(frozen=True)
class ClaudeRunResult:
    text: str
    session_id: str
    returncode: int


# --- MCP stdio-spawn readiness watchdog (Task #5) ----------------------------
# The agent's only sanctioned channel is the `submit_proof_intent` MCP tool,
# served by a stdio child that Claude Code spawns from the per-node mcp config.
# That spawn is intermittently flaky: when it fails, Claude never starts the
# server (no `mcp_debug.jsonl` is ever written), fails open with only generic
# harness tools, and the agent correctly refuses and dies at turn 0 with
# `TOOL_BOUNDARY_MISSING` — wasting a whole run slot. The healthy server writes a
# `server_start` event to its debug log within ~1-2s of launch, so the absence
# of that event after a generous window is a reliable "spawn flaked" signal. The
# watchdog kills the doomed subprocess early so the runtime can relaunch it.
_MCP_READY_TIMEOUT_S = float(
    os.environ.get("SHANNON_MCP_READY_TIMEOUT_S", "75"))
_MCP_SPAWN_RETRIES = max(0, int(
    os.environ.get("SHANNON_MCP_SPAWN_RETRIES", "2")))
# How many of the agent's most-recent assistant message texts to keep in the
# in-memory ring buffer and forward (verdict-stripped) on a watermark respawn.
_RECENT_REASONING_K = max(0, int(
    os.environ.get("SHANNON_RECENT_REASONING_K", "3")))


def _mcp_server_started(debug_log: Path) -> bool:
    """True once the MCP server has written its `server_start` event.

    Reads the per-node debug log (the server's first action is to append
    `server_start`). Missing/unreadable file -> not started yet.
    """
    try:
        with open(debug_log, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"server_start"' in line:
                    return True
    except OSError:
        return False
    return False


class NodeMemory:
    """Curated per-node memory files visible to the long-lived agent."""

    def __init__(self, run_dir: Path, node_id: str,
                 surface_profile: str | None = None) -> None:
        self.node_id = node_id
        self.surface_profile = surface_profile
        self.dir = Path(run_dir) / "node_memory" / _slug(node_id)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.timeline = self.dir / "timeline.jsonl"
        self.attempts = self.dir / "attempts.jsonl"
        self.failures = self.dir / "failures.jsonl"
        self.latest_result = self.dir / "latest_manager_result.json"
        self.latest_view = self.dir / "latest_workspace_view.json"
        self.latest_followup = self.dir / "latest_followup.md"
        # The agent's full step-numbered committed proof, refreshed every turn. It
        # is NOT in the per-turn prompt (that would bloat context on long proofs);
        # the standing prompt points the agent here to read it on demand (amend /
        # undo by index, or to re-orient after a context refresh / respawn).
        self.latest_proof = self.dir / "proof_so_far.md"
        self.followups_dir = self.dir / "followups"
        self.manager_results_dir = self.dir / "manager_results"
        self.workspace_views_dir = self.dir / "workspace_views"
        self.notes = self.dir / "notes.md"
        self.agent_sessions = self.dir / "agent_sessions.jsonl"
        self._lock = threading.Lock()
        for path in (
            self.followups_dir,
            self.manager_results_dir,
            self.workspace_views_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        if not self.notes.exists():
            self.notes.write_text(
                "# Node Memory\n\n"
                "Curated notes for this proof node. This is optional history "
                "for the agent to read with file tools; it is not the proof "
                "state authority.\n",
                encoding="utf-8",
            )

    def record_bootstrap(self, bootstrap: dict[str, Any]) -> None:
        self._append_jsonl(
            self.timeline,
            {
                "kind": "bootstrap",
                "node": self.node_id,
                "session_tag": bootstrap.get("session_tag"),
                "session_dir": bootstrap.get("session_dir"),
                # `replay_prefix_count` is the SEMANTIC resume count (where
                # the lineage's ORIGINAL inherited prefix ended, propagated
                # across respawns via resume_context); on a respawned node it
                # is smaller than the actual starting history. Record the
                # committed length too so audits don't conflate the two.
                "replay_prefix_count": bootstrap.get("replay_prefix_count"),
                "replay_prefix_committed_count": len(
                    bootstrap.get("replay_prefix") or []
                ),
                "snapshot": bootstrap.get("snapshot") or {},
            },
        )
        self._write_bootstrap_handoff(bootstrap)

    def record_agent_session(
        self, session_id: str, *, cwd: str | Path | None = None,
    ) -> None:
        """Persist the prover's Claude session id for this node.

        This is the correlation pointer the offline timeline tooling needs to
        locate the node's *reasoning transcript* — the run's own artifacts
        deliberately never store the agent's thinking text, but Claude Code keeps
        it at ``~/.claude/projects/<slug>/<session_id>.jsonl``. Best-effort and
        idempotent: a node that restarts/resumes spawns several sessions, so this
        appends and skips a session id already recorded. Never raises into the
        proof run.
        """
        sid = str(session_id or "").strip()
        if not sid:
            return
        try:
            for existing in self._read_jsonl(self.agent_sessions):
                if str(existing.get("session_id") or "") == sid:
                    return
            self._append_jsonl(
                self.agent_sessions,
                _drop_empty({
                    "kind": "agent_session",
                    "node": self.node_id,
                    "session_id": sid,
                    "transcript_path": _claude_transcript_path(sid, cwd),
                }),
            )
        except Exception:
            return

    def _write_bootstrap_handoff(self, bootstrap: dict[str, Any]) -> None:
        """Persist the initial current-state view before Claude's first turn."""
        raw_view = bootstrap.get("workspace_view")
        if not isinstance(raw_view, dict):
            raw_view = {}
        try:
            view = WorkspaceViewManager().agent_display_view(raw_view)
        except Exception:
            view = dict(raw_view)
        result_payload = _drop_empty({
            "turn": 0,
            "kind": "bootstrap",
            "node": self.node_id,
            "message": "Initial current-state handoff for this proof node.",
            "replay_prefix_count": bootstrap.get("replay_prefix_count"),
            "replay_prefix_committed_count": len(
                bootstrap.get("replay_prefix") or []
            ),
            "view_refreshed": bool(view),
        })
        surface_turn = compose_surface_turn(
            view,
            self.surface_profile,
            handled_intent={},
            ok=True,
            goal_only=self.surface_profile == "l1_goal_projection",
        )
        view = dict(view)
        view["surface_turn"] = surface_turn
        followup = (
            "Initial manager handoff for this proof node.\n\n"
            + render_surface_turn_markdown(
                surface_turn,
                goal_only=self.surface_profile == "l1_goal_projection",
            )
            + "\n\n"
            + f"{_legal_node_memory_anchor(self)}\n"
        )
        self.write_latest_followup(
            turn_index=0,
            result_payload=result_payload,
            workspace_view=view,
            followup_text=followup,
        )

    def record_turn(
        self,
        *,
        turn_index: int,
        raw_text: str,
        handled_intent: dict[str, Any] | None,
        turn: ManagedTurn,
    ) -> None:
        health = turn.health_event.to_dict() if turn.health_event else {}
        actions = _agent_safe_action_summaries(turn.manager_actions)
        record = {
            "kind": "manager_turn",
            "turn": turn_index,
            "node": self.node_id,
            "intent": handled_intent or {},
            "ok": bool(turn.ok),
            "health_event": health,
            "manager_actions": actions,
            "state_version": (
                turn.snapshot.state_version if turn.snapshot is not None else None
            ),
            "goal_hash": turn.snapshot.goal_hash if turn.snapshot else "",
        }
        self._append_jsonl(self.timeline, _drop_empty(record))

        intent_name = str((handled_intent or {}).get("intent") or "")
        if intent_name == "commit_tactic":
            self._append_jsonl(
                self.attempts,
                _drop_empty({
                    "turn": turn_index,
                    "intent": handled_intent,
                    "ok": bool(turn.ok),
                    "manager_actions": actions,
                    "health_event": health,
                }),
            )
        if self._is_failure(turn, actions):
            self._append_jsonl(
                self.failures,
                _drop_empty({
                    "turn": turn_index,
                    "raw_message_preview": raw_text[:500],
                    "intent": handled_intent or {},
                    "ok": bool(turn.ok),
                    "repair_prompt": turn.repair_prompt,
                    "health_event": health,
                    "manager_actions": actions,
                }),
            )

    def _agent_facing_latest_view(
        self, workspace_view: dict[str, Any],
    ) -> dict[str, Any]:
        """Content for ``latest_workspace_view.json``.

        For the L1 goal-projection baseline, prepend ``_l1_surface_notice`` so an
        agent that opens the audit file anyway is reminded it is off-surface.
        Content is otherwise left FULL: resume/replay and the per-turn audit
        archive read this same file and must stay intact, so this is a gentle
        reminder, not a redaction. No-op for non-L1 profiles and idempotent if
        the notice is already present.
        """
        if (
            self.surface_profile == "l1_goal_projection"
            and isinstance(workspace_view, dict)
            and "_l1_surface_notice" not in workspace_view
        ):
            return {"_l1_surface_notice": _L1_OFF_SURFACE_NOTICE, **workspace_view}
        return workspace_view

    def write_latest_followup(
        self,
        *,
        turn_index: int,
        result_payload: dict[str, Any],
        workspace_view: dict[str, Any],
        followup_text: str,
    ) -> None:
        """Persist the latest manager-authored current-state handoff.

        These files are legal for the agent to read because they live in the
        current node's curated memory directory.  They are current-state
        transport, not proof-state authority and not historical search.
        """
        # `latest_workspace_view.json` is kept for audit/replay, not advertised
        # as the normal agent recovery surface. For L1 it leads with an
        # off-surface notice in case a goal-only agent opens it anyway. The
        # per-turn `workspace_views/<turn>.json` archive below stays FULL and
        # un-annotated for audit/replay.
        agent_latest_view = self._agent_facing_latest_view(workspace_view)
        with self._lock:
            self.latest_result.write_text(
                json.dumps(result_payload, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            self.latest_view.write_text(
                json.dumps(agent_latest_view, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            # The full step-numbered committed proof, for on-demand reading (the
            # standing prompt anchors LEGAL_PROOF_SO_FAR). Kept out of the per-turn
            # prompt so long proofs don't bloat context.
            proof_md = _md_proof_so_far(
                workspace_view.get("proof_so_far")
                if isinstance(workspace_view, dict) else None
            )
            self.latest_proof.write_text(
                proof_md or "### Proof so far (0 committed)\n(no committed steps yet)\n",
                encoding="utf-8",
            )
            self.latest_followup.write_text(followup_text, encoding="utf-8")
            turn_stem = f"turn_{turn_index:03d}"
            (self.manager_results_dir / f"{turn_stem}.json").write_text(
                json.dumps(result_payload, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            (self.workspace_views_dir / f"{turn_stem}.json").write_text(
                json.dumps(workspace_view, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            (self.followups_dir / f"{turn_stem}.md").write_text(
                followup_text,
                encoding="utf-8",
            )

    def _is_failure(self, turn: ManagedTurn, actions: list[dict[str, Any]]) -> bool:
        if not turn.ok or turn.health_event is not None:
            return True
        for action in actions:
            if action.get("timed_out"):
                return True
            if action.get("error_summary"):
                return True
            if action.get("exit_code") not in (None, 0):
                return True
        return False

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        clean = _drop_empty({
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **record,
        })
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(clean, sort_keys=True) + "\n")

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        return read_jsonl(path)


def _legal_node_memory_anchor(memory: NodeMemory) -> str:
    """Compact, repeated anchor for legal durable files after compaction."""
    return (
        "### Legal Node Memory Anchor\n\n"
        f"LEGAL_NODE_MEMORY_DIR: `{memory.dir}`\n"
        f"LEGAL_LATEST_MANAGER_RESULT: `{memory.latest_result}`\n"
        f"LEGAL_LATEST_FOLLOWUP: `{memory.latest_followup}`\n"
        f"LEGAL_PROOF_SO_FAR: `{memory.latest_proof}` "
        "(your full step-numbered committed proof — read it to pick a step for "
        "`amend_and_replay`/`undo_to_checkpoint`, or to re-orient)\n\n"
        "Compaction recovery: if these exact paths are missing from your "
        "context, re-read `LEGAL_LATEST_FOLLOWUP` first and "
        "`LEGAL_PROOF_SO_FAR` only when you need accepted-history context. "
        "Submit your next advertised proof intent instead of using shell "
        "directory discovery for proof-state artifacts."
    )


def _prover_system_anchor(memory: NodeMemory) -> str:
    """Durable per-node anchor for the SYSTEM prompt (Claude preserves the system
    prompt across context compaction, so this need not be re-sent every turn).

    Holds the two things that must survive a compaction: the one-intent-per-turn
    invariant and the LEGAL_* durable file paths. Wired via
    ClaudeAgentSession.run(system_prompt=...) -> `--append-system-prompt`."""
    return (
        "## Prover runtime anchor (durable — persists across context compaction)\n\n"
        "You drive the proof ONLY through the MCP tool `submit_proof_intent`: exactly "
        "one intent object per turn, and NEVER end a turn without that call (a turn "
        "with only text abandons the proof). The current goal and panels arrive in "
        "each manager turn; these durable node-memory files are always available to "
        "read on demand:\n\n"
        f"{_legal_node_memory_anchor(memory)}"
    )


class ManagerBridgeServer:
    """Local bridge that accepts proof intents from the long-lived agent."""

    def __init__(
        self,
        *,
        manager: ProofNodeManager,
        memory: NodeMemory,
        response_renderer: Callable[..., str],
        max_turns: int,
    ) -> None:
        self.manager = manager
        self.memory = memory
        self.response_renderer = response_renderer
        self.max_turns = max(1, int(max_turns))
        self.token = secrets.token_urlsafe(24)
        self._turn_index = 0
        self._lock = threading.Lock()
        self._httpd: socketserver.ThreadingTCPServer | None = None
        self._thread: threading.Thread | None = None
        self.host = "127.0.0.1"
        self.port = 0
        self.terminal_health: NodeHealthEvent | None = None

    def start(self) -> None:
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:  # noqa: D401 - inherited protocol method
                raw = self.rfile.readline(2_000_000)
                response = outer._handle_request(raw)
                self.wfile.write(json.dumps(response).encode("utf-8"))

        class ThreadingServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        self._httpd = ThreadingServer((self.host, 0), Handler)
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name=f"proof-node-manager-bridge-{self.manager.node_id}",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _handle_request(self, raw: bytes) -> dict[str, Any]:
        try:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return {
                    "exit_code": 1,
                    "text": "MANAGER BRIDGE ERROR: request was not JSON.",
                }
            if payload.get("token") != self.token:
                return {
                    "exit_code": 1,
                    "text": "MANAGER BRIDGE ERROR: invalid bridge token.",
                }
            text = str(payload.get("text") or "")
            # DESIGN NOTE (rewind false-wedge, fix/rewind-wedge):
            # This lock serializes turn bookkeeping (`_turn_index`,
            # `memory.record_turn`, `terminal_health`) AND the call into
            # `manager.handle_agent_message`, which for a confirmed
            # `undo_to_checkpoint` performs a full EC restart + per-tactic replay
            # of the kept prefix (repl_session._start_locked). Because this is a
            # ThreadingTCPServer, the lock is the *only* thing serializing
            # concurrent intents, so a multi-minute rewind here head-of-line
            # blocks every other intent (even read-only context requests).
            #
            # Considered (Defect B option 2a) scoping this lock to JUST the
            # bookkeeping and running the EC replay outside it (or answering
            # read-only intents with a "rewind in progress" status). DELIBERATELY
            # NOT DONE: it cannot be made correct without a non-trivial
            # concurrency redesign. `manager.repl` is mutated in place by the
            # replay (session epoch / state_version / on-disk session dir), and
            # `_turn_index` + `memory.record_turn` ordering must stay consistent
            # with the EC mutation that turn observed. Releasing the lock across
            # the replay introduces races on the EC session and on turn ordering
            # for any concurrently-arriving intent. The correctness of the EC
            # session and turn bookkeeping is paramount, so the false-wedge is
            # fixed instead by (A) decoupling the MCP client read timeout from
            # the connect timeout (proof_node_mcp_server._bridge_roundtrip), so a
            # slow-but-finite replay is no longer misreported as a wedge, and
            # (B) bounding the replay's wall-clock with an aggregate budget
            # (repl_session._start_locked, SHANNON_REPLAY_AGG_BUDGET) so the lock
            # is never held past that budget. A safe 2a would need a dedicated
            # mutation/turn state machine and is left as future work.
            with self._lock:
                if self.terminal_health is not None:
                    health = self.terminal_health
                    return {
                        "exit_code": 2,
                        "text": (
                            "MANAGER WORKER STOP: proof node is unhealthy: "
                            f"{health.status}: {health.message}"
                        ),
                    }
                if self._turn_index >= self.max_turns:
                    return {
                        "exit_code": 0,
                        "text": (
                            "MANAGER WORKER STOP: turn limit reached before proof "
                            "completion. Produce a concise PROVER REPORT and stop."
                        ),
                    }
                parsed = parse_agent_intent(text)
                handled = (
                    parsed.intent.to_dict()
                    if parsed.ok and parsed.intent else None
                )
                turn = self.manager.handle_agent_message(text)
                self._turn_index += 1
                turn_index = self._turn_index
                self.memory.record_turn(
                    turn_index=turn_index,
                    raw_text=text,
                    handled_intent=handled,
                    turn=turn,
                )
                if turn.health_event is not None:
                    self.terminal_health = turn.health_event
                rendered = self.response_renderer(
                    turn, turn_index, handled, self.memory,
                    full_view=getattr(self.manager, "latest_full_view", None),
                )
            return {
                "exit_code": 2 if turn.health_event is not None else 0,
                "text": rendered,
            }
        except Exception as exc:
            health = NodeHealthEvent(
                node_id=self.manager.node_id,
                status="manager_bridge_exception",
                message=(
                    "manager bridge caught an internal exception and returned "
                    "a structured error instead of closing the MCP connection"
                ),
                state_version=self.manager.state_version,
            )
            self.terminal_health = health
            self.manager._audit({
                "kind": "manager_bridge.exception",
                "node": self.manager.node_id,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
                "health": health.to_dict(),
            })
            return {
                "exit_code": 2,
                "text": (
                    "MANAGER BRIDGE ERROR: internal manager exception; "
                    f"node marked unhealthy ({health.status}). Latest "
                    "completed node-memory files remain available for audit."
                ),
            }


class ClaudeAgentSession:
    """One long-lived Claude Code subprocess for a proof node."""

    def __init__(
        self,
        *,
        model: str,
        effort: str = "high",
        source_file: str,
        session_tag: str,
        project_root: Path = PROJECT_ROOT,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.source_file = source_file
        self.session_tag = session_tag
        self.project_root = Path(project_root)
        self.emit = emit or (lambda event: None)
        self.proc: subprocess.Popen[str] | None = None
        self.session_id = ""
        # Set by the readiness watchdog when the MCP stdio server never came up
        # for the most recent run() (so the caller can relaunch). Reset per run.
        self.mcp_failed_to_start = False
        # Fresh-context continuation (Layer 1): a per-turn token-watermark
        # detector. When this session's context crosses the watermark for
        # `SHANNON_CTX_WATERMARK_TURNS` consecutive assistant turns, we gracefully
        # end the loop BETWEEN turns and surface `ctx_pressure` so the runtime can
        # swap in a fresh Claude context against the SAME bridge/manager/EC
        # session (zero replay). See docs/design/fresh_context_continuation.md.
        self._ctx_detector = CtxWatermarkDetector()
        self.ctx_pressure = False
        # Number of consecutive hot turns at the moment pressure tripped (audit).
        self._ctx_hot_turns = 0
        # Transient, in-memory ring buffer of the last K assistant message texts
        # (the agent's own reasoning). On a watermark respawn this is forwarded —
        # verdict-stripped — so the fresh context CONTINUES the work instead of
        # re-diagnosing from scratch. Deliberately NOT persisted to node_memory /
        # run artifacts (CLAUDE.md: artifacts never store thinking text).
        self._recent_reasoning: list[str] = []
        self._recent_reasoning_cap = _RECENT_REASONING_K

    def run(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        mcp_config_path: Path | None = None,
        mcp_debug_log: Path | None = None,
    ) -> ClaudeRunResult:
        cmd = [
            CLAUDE_BIN,
            "-p",
            prompt,
            "--model",
            self.model,
            "--effort",
            self.effort,
            # Durable per-node anchors (LEGAL_* file paths + the one-intent-per-turn
            # invariant) go in the SYSTEM prompt, which Claude preserves across
            # context compaction — so we no longer re-inject them into every turn's
            # followup. Empty on callers that don't supply one.
            *(["--append-system-prompt", system_prompt] if system_prompt.strip() else []),
            "--dangerously-skip-permissions",
            "--disallowedTools",
            *destructive_tool_denylist(
                self.source_file,
                project_root=self.project_root,
            ),
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-thinking-tokens",
            "4000",
        ]
        if mcp_config_path is not None:
            cmd.extend([
                "--mcp-config",
                str(mcp_config_path),
                "--strict-mcp-config",
            ])
        env = os.environ.copy()
        env["EC_SESSION_DIR"] = f".ec_session_{self.session_tag}"
        env["SHANNON_LEGACY_DISPLAY"] = os.environ.get(
            "SHANNON_LEGACY_DISPLAY",
            "hidden",
        )
        self.mcp_failed_to_start = False
        # Each generation starts with a clean watermark detector: the fresh
        # context begins near the post-compact floor, so prior hot turns must not
        # carry over.
        self._ctx_detector.reset()
        self.ctx_pressure = False
        # Fresh generation -> fresh reasoning buffer (only the dying generation's
        # own recent reasoning should ever be forwarded on its respawn).
        self._recent_reasoning = []
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        result_text = ""
        stderr_chunks: list[str] = []

        # Readiness watchdog: if the MCP stdio server has not announced itself
        # within the timeout (the spawn flaked), kill the doomed subprocess so
        # the runtime can relaunch instead of burning the full turn-0 timeout on
        # an agent that has no proof tool. Only armed when we know where the
        # server's debug log will be.
        watchdog: threading.Thread | None = None
        if mcp_config_path is not None and mcp_debug_log is not None:
            watchdog = threading.Thread(
                target=self._watch_mcp_readiness,
                args=(mcp_debug_log, _MCP_READY_TIMEOUT_S),
                name=f"mcp-readiness-{self.session_tag}",
                daemon=True,
            )
            watchdog.start()

        def _drain_stderr() -> None:
            if self.proc is None or self.proc.stderr is None:
                return
            stderr_chunks.append(self.proc.stderr.read())

        stderr_thread = threading.Thread(
            target=_drain_stderr,
            name=f"claude-stderr-{self.session_tag}",
            daemon=True,
        )
        stderr_thread.start()
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\n")
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("session_id") and not self.session_id:
                self.session_id = str(event.get("session_id") or "")
            if event.get("type") == "result":
                result_text = str(event.get("result") or "")
                if event.get("session_id"):
                    self.session_id = str(event.get("session_id") or self.session_id)
                continue
            self.emit(event)
            # Keep the agent's recent reasoning in an in-memory ring buffer so a
            # watermark respawn can forward it (Change 3). Best-effort; a failure
            # here must never disturb the stream loop.
            try:
                self._capture_reasoning(event)
            except Exception:
                pass
            # Layer 1: token-watermark detection. The trip is a rising edge; on
            # it we emit an audit marker and terminate the child so the runtime's
            # respawn loop can swap in a fresh context. Terminating here CAN land
            # mid tool-call (a tool request may already be in flight when we kill
            # the process), but that is safe because every commit goes through a
            # synchronous, transactional session mutation: a tactic is either
            # fully applied to the live EC session before the call returns or not
            # at all, so a killed mid-flight tool-call cannot leave a half-applied
            # commit. The drained stdout iterator ends cleanly after terminate().
            if self._ctx_detector.observe(event):
                self.ctx_pressure = True
                self._ctx_hot_turns = self._ctx_detector.hot_turns
                self.emit({
                    "type": "system",
                    "ctx_watermark_tripped": True,
                    "ctx_tokens": self._ctx_detector.last_ctx_tokens,
                    "hot_turns": self._ctx_detector.hot_turns,
                    "watermark_tokens": self._ctx_detector.tokens,
                    "session_tag": self.session_tag,
                })
                try:
                    self.proc.terminate()
                except Exception:
                    pass
        returncode = self.proc.wait()
        stderr_thread.join(timeout=5)
        if watchdog is not None:
            watchdog.join(timeout=2)
        stderr = "".join(stderr_chunks)
        if returncode != 0 and not result_text:
            result_text = stderr.strip()
        if self.session_id:
            self.emit({
                "type": "system",
                "session_id": self.session_id,
                "long_lived_agent": True,
            })
        return ClaudeRunResult(
            text=result_text,
            session_id=self.session_id,
            returncode=returncode,
        )

    def _capture_reasoning(self, event: dict[str, Any]) -> None:
        """Append one assistant message's TEXT to the in-memory ring buffer.

        Only `assistant` stream events carry the agent's reasoning; their
        ``message.content`` is a list of blocks, of which the ``text`` blocks are
        the reasoning. We join those, ignore tool_use / non-text blocks, and keep
        only the last ``_recent_reasoning_cap`` (default 3) non-empty texts. Pure
        in-memory — never written to disk. Best-effort: callers wrap in try/except.
        """
        if self._recent_reasoning_cap <= 0:
            return
        if not isinstance(event, dict) or event.get("type") != "assistant":
            return
        message = event.get("message")
        if not isinstance(message, dict):
            return
        content = message.get("content")
        if not isinstance(content, list):
            return
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                txt = block.get("text")
                if isinstance(txt, str) and txt.strip():
                    parts.append(txt.strip())
        text = "\n".join(parts).strip()
        if not text:
            return
        self._recent_reasoning.append(text)
        if len(self._recent_reasoning) > self._recent_reasoning_cap:
            del self._recent_reasoning[:-self._recent_reasoning_cap]

    def _watch_mcp_readiness(self, mcp_debug_log: Path, timeout_s: float) -> None:
        """Kill the subprocess if the MCP stdio server never announces itself.

        The healthy server writes a `server_start` event within ~1-2s; if none
        appears within ``timeout_s`` while the process is still alive, the spawn
        flaked. Set ``mcp_failed_to_start`` and terminate so the runtime can
        relaunch. A process that exits on its own, or a server that came up, is
        left alone. Never raises.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            proc = self.proc
            if proc is None or proc.poll() is not None:
                return  # exited on its own; nothing to guard
            if _mcp_server_started(mcp_debug_log):
                return  # server is up — healthy launch
            time.sleep(1.0)
        proc = self.proc
        if (
            proc is not None
            and proc.poll() is None
            and not _mcp_server_started(mcp_debug_log)
        ):
            self.mcp_failed_to_start = True
            self.emit({
                "type": "system",
                "mcp_spawn_failed": True,
                "timeout_s": timeout_s,
                "session_tag": self.session_tag,
            })
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def close(self, reason: str) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        self.emit({
            "type": "system",
            "long_lived_agent": True,
            "closing_reason": reason,
        })
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)


class ProofNodeRuntime:
    """Own one proof-node manager and one long-lived agent session."""

    def __init__(
        self,
        *,
        prompt: str,
        bootstrap: dict[str, Any],
        file_path: str,
        lemma_name: str,
        include_dir: str,
        session_tag: str,
        node_id: str,
        run_dir: Path,
        model: str,
        effort: str = "high",
        max_turns: int = 1000,
        surface_profile: str | None = None,
        project_root: Path = PROJECT_ROOT,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.prompt = prompt
        self.bootstrap = bootstrap
        self.file_path = file_path
        self.lemma_name = lemma_name
        self.include_dir = include_dir
        self.session_tag = session_tag
        self.node_id = node_id
        self.run_dir = Path(run_dir)
        self.model = model
        self.effort = effort
        self.max_turns = max_turns
        self.surface_profile = surface_profile
        self.project_root = Path(project_root)
        self.emit = emit or _emit_json
        self.manager = ProofNodeManager(
            file_path=file_path,
            lemma_name=lemma_name,
            include_dir=include_dir,
            session_tag=session_tag,
            node_id=node_id,
            run_dir=self.run_dir,
            project_root=self.project_root,
            surface_profile=surface_profile,
        )
        self.manager.adopt_bootstrap(bootstrap)
        self.memory = NodeMemory(self.run_dir, node_id, surface_profile=surface_profile)
        self._private_dir = self.run_dir / "runtime_private" / _slug(node_id)
        self._mcp_config_path = self._private_dir / "proof_node_mcp_config.json"
        self.memory.record_bootstrap(bootstrap)
        self.bridge = ManagerBridgeServer(
            manager=self.manager,
            memory=self.memory,
            response_renderer=functools.partial(
                _render_manager_followup, surface_profile=surface_profile),
            max_turns=max_turns,
        )
        self.agent = ClaudeAgentSession(
            effort=self.effort,
            model=model,
            source_file=file_path,
            session_tag=session_tag,
            project_root=self.project_root,
            emit=self.emit,
        )

    def _committed_count(self) -> int:
        """Snapshot of the manager's accepted-tactic count (the progress metric).

        Read straight from the manager's committed-history source of truth so a
        respawn is gated on tactics EC actually accepted, not tactics submitted.
        Never raises — a read error reads as zero progress.
        """
        try:
            return len(self.manager._current_committed_tactics())
        except Exception:
            return 0

    def _made_progress(self, baseline: int) -> bool:
        """True iff ≥1 tactic was committed since this generation began.

        Zero progress means the block is structural, not contextual — a fresh
        context would hit the same wall, so we do NOT respawn.
        """
        return self._committed_count() > baseline

    def _wall_deadline(self) -> float | None:
        """Absolute wall-clock (unix epoch) deadline for this worker, or None.

        The supervisor owns the hard wall-clock kill; the worker has no inherent
        deadline. When the supervisor wants the in-worker respawn to refrain near
        the end of the run it sets ``SHANNON_NODE_DEADLINE_EPOCH`` (unix seconds);
        we honor it as a runway guard. Absent/unparseable -> no internal limit.
        """
        raw = os.environ.get("SHANNON_NODE_DEADLINE_EPOCH")
        if raw is None or not str(raw).strip():
            return None
        try:
            return float(str(raw).strip())
        except (TypeError, ValueError):
            return None

    def _checkpoint_resume_capsules(self) -> None:
        """Write resume capsules from the live session (crash-safety + Layer-3 root).

        Mirrors ``prover.py``'s post-run ``create_resume_capsules`` call but points
        at THIS node's still-live session dir. The capsule is NOT consumed by the
        in-worker swap (which never replays); it is a crash-safety checkpoint and
        the root the supervisor's Layer-3 net replays from if the worker dies.
        Best-effort; never breaks the run.
        """
        try:
            from workflow.proof_node_resume import create_resume_capsules

            session_dir = self.project_root / f".ec_session_{self.session_tag}"
            create_resume_capsules(
                project_root=self.project_root,
                run_dir=self.run_dir,
                session_dirs=[session_dir],
                target_file=self.file_path,
                lemma=self.lemma_name,
                include_dir=self.include_dir,
            )
        except Exception as exc:  # pragma: no cover - best-effort checkpoint
            self.emit({
                "type": "system",
                "context_respawn_checkpoint_failed": str(exc),
                "node": self.node_id,
            })

    def _build_fresh_prompt(
        self, *, recent_reasoning: list[str] | None = None
    ) -> str:
        """Compact continuation prompt for a respawned (fresh) Claude context.

        Built from the in-process manager view + this node's own curated memory
        (dead-end ledger + frontier brief + accepted spine) — NOT from a disk
        capsule and NOT a tactic replay. Framed as neutral evidence per CLAUDE.md.

        On a watermark respawn the dying generation's own ``recent_reasoning``
        (verdict-stripped) is prepended so the fresh context CONTINUES from it
        rather than re-diagnosing from scratch. All of that is best-effort: any
        failure falls back to today's state-only handoff (never blocks the swap).
        """
        full_view = getattr(self.manager, "latest_full_view", None)
        try:
            committed = list(self.manager._current_committed_tactics())
        except Exception:
            committed = []
        handoff = render_handoff_section(
            frontier_brief=build_frontier_brief(full_view),
            accepted_spine=build_accepted_spine(committed),
        )
        reasoning_section = self._render_recent_reasoning(recent_reasoning)
        if reasoning_section:
            handoff = reasoning_section + "\n\n" + handoff
        # FIX #2: the reopening must be SMALL (spec §Handoff ~≤15k tokens) so the
        # fresh session starts near the post-compact floor. We keep the runtime /
        # tool-protocol block (the fresh session still needs it) but drop the heavy
        # turn-0 bootstrap (`self.prompt` = full lemma source + sibling lemmas +
        # KB). A thin pointer lets the agent re-read source on demand via tools.
        pointer = (
            f"Target lemma `{self.lemma_name}` lives in `{self.file_path}`"
            if self.lemma_name or self.file_path else ""
        )
        base = render_long_lived_agent_prompt(
            self.prompt,
            host=self.bridge.host,
            port=self.bridge.port,
            token=self.bridge.token,
            node_memory_dir=self.memory.dir,
            max_turns=self.max_turns,
            surface_profile=self.surface_profile,
            compact=True,
            compact_pointer=pointer,
        )
        return handoff + "\n\n" + base

    def _render_recent_reasoning(
        self, recent_reasoning: list[str] | None
    ) -> str:
        """Render the dying generation's recent reasoning as a CONTINUE-from block.

        Verdict-stripped (Change 4) and framed as the agent's own in-progress
        thinking — NOT an established conclusion. Best-effort: any failure (or no
        reasoning) returns "" so the caller falls back to the state-only handoff.
        """
        try:
            texts = [t.strip() for t in (recent_reasoning or []) if isinstance(t, str) and t.strip()]
            if not texts:
                return ""
            stripped = [strip_closed_verdicts(t) for t in texts]
            lines: list[str] = []
            lines.append(
                "## Your own recent reasoning before the context swap"
            )
            lines.append("")
            lines.append(
                "This is YOUR in-progress reasoning from just before the swap — "
                "CONTINUE from here. It is NOT established: verify any conclusions "
                "against the live proof state before relying on them."
            )
            lines.append("")
            for chunk in stripped:
                lines.append(chunk)
                lines.append("")
            return "\n".join(lines).strip() + "\n"
        except Exception:
            return ""

    def _turn_limit_exhausted(self) -> bool:
        """True iff the bridge stopped because the cumulative turn budget ran out.

        The bridge's turn-limit STOP (``_handle_request``) returns exit 0 with NO
        ``terminal_health`` — identical on the wire to a clean give-up. But
        ``_turn_index`` is cumulative across generations and is NOT reset on a
        swap, so a fresh context would re-STOP on its first turn. Distinguish it
        here so it is neither a Layer-2 premature give-up nor a respawn trigger.
        """
        try:
            return self.bridge._turn_index >= self.bridge.max_turns
        except Exception:
            return False

    def _should_respawn(self, result: ClaudeRunResult, *, baseline: int) -> bool:
        """All-of guard for the in-worker fresh-context swap (Layer 1 ONLY).

        Resume fires ONLY on context pressure (the token watermark tripped while
        the agent is still working). A GIVE-UP — the agent concluding the proof
        is closed/unprovable and exiting cleanly while the proof is open — is a
        real, measurable outcome and must END the run, not respawn. Respawning a
        give-up papers over the decision AND corrupts the give-up-rate
        measurement. So there is NO premature-give-up branch here (removed): a
        give-up with no ctx_pressure → False → the generation loop breaks → the
        run ends on the give-up. See docs/design/context_resume_tightened.md.
        """
        if respawn_disabled():
            return False
        # Turn-limit exhaustion looks like a clean give-up on the wire (exit 0, no
        # terminal_health) but _turn_index is cumulative across generations — a
        # fresh context would immediately re-STOP. Never respawn into that.
        if self._turn_limit_exhausted():
            return False
        # Sole trigger: Layer-1 token pressure (the watermark tripped). No
        # give-up-based trigger.
        if not bool(getattr(self.agent, "ctx_pressure", False)):
            return False
        # Never respawn a protocol-stuck / exception node — that is terminal.
        if self.bridge.terminal_health is not None:
            return False
        # Structural (zero-progress) blocks are not contextual — do not respawn.
        if not self._made_progress(baseline):
            return False
        return True

    def run(self) -> ClaudeRunResult:
        self.bridge.start()
        deadline = self._wall_deadline()
        try:
            self._write_mcp_config(
                host=self.bridge.host,
                port=self.bridge.port,
                token=self.bridge.token,
            )
            prompt = render_long_lived_agent_prompt(
                self.prompt,
                host=self.bridge.host,
                port=self.bridge.port,
                token=self.bridge.token,
                node_memory_dir=self.memory.dir,
                max_turns=self.max_turns,
                surface_profile=self.surface_profile,
            )
            mcp_debug_log = self._private_dir / "mcp_debug.jsonl"
            # Fresh-context continuation generation loop (Layers 1-2). Mirrors the
            # MCP-spawn-retry loop below: each iteration runs ONE Claude context
            # against the SAME bridge/manager/EC session. When a generation
            # degrades (token watermark) or gives up prematurely (proof still
            # open) AND made progress AND budget/cap remain, we swap in a fresh
            # context with a compact handoff — never tearing down EC -> zero
            # replay. See docs/design/fresh_context_continuation.md.
            generation = 0
            max_respawns = respawn_max()
            while True:
                committed_at_gen_start = self._committed_count()
                result = self.agent.run(
                    prompt,
                    system_prompt=_prover_system_anchor(self.memory),
                    mcp_config_path=self._mcp_config_path,
                    mcp_debug_log=mcp_debug_log,
                )
                # Task #5: the MCP stdio server flakily fails to spawn (~half the
                # time on some hosts). When the watchdog caught that, relaunch the
                # agent against the still-running manager bridge — a fresh Claude
                # process re-attempts the stdio spawn — rather than wasting the
                # slot on a turn-0 `TOOL_BOUNDARY_MISSING`. Bounded retries; the
                # bridge, manager, and EC session are untouched between attempts.
                attempt = 0
                while (
                    getattr(self.agent, "mcp_failed_to_start", False)
                    and attempt < _MCP_SPAWN_RETRIES
                ):
                    attempt += 1
                    self.emit({
                        "type": "system",
                        "mcp_spawn_retry": attempt,
                        "of": _MCP_SPAWN_RETRIES,
                        "node": self.node_id,
                    })
                    # Drop the empty/aborted debug log so the watchdog's
                    # `server_start` check starts clean for the relaunch.
                    try:
                        mcp_debug_log.unlink()
                    except OSError:
                        pass
                    result = self.agent.run(
                        prompt,
                        system_prompt=_prover_system_anchor(self.memory),
                        mcp_config_path=self._mcp_config_path,
                        mcp_debug_log=mcp_debug_log,
                    )
                if generation >= max_respawns:
                    break
                if deadline is not None and (deadline - time.time()) < min_runway_seconds():
                    break
                if not self._should_respawn(result, baseline=committed_at_gen_start):
                    break
                generation += 1
                # Crash-safety checkpoint + audit + Layer-3 fallback root. NOT a
                # replay source for this in-worker swap (EC session stays live).
                self._checkpoint_resume_capsules()
                self.emit({
                    "type": "system",
                    "context_respawn": generation,
                    "of": max_respawns,
                    "node": self.node_id,
                    # Sole trigger after the Layer-2 removal — see _should_respawn.
                    "trigger": "ctx_watermark",
                    "committed_at_swap": self._committed_count(),
                })
                # Capture the agent's recent reasoning BEFORE we tear down the
                # dead child, so the fresh context can CONTINUE from it (Change 3).
                # Best-effort: a failure here must never block the swap.
                try:
                    recent_reasoning = list(
                        getattr(self.agent, "_recent_reasoning", []) or []
                    )
                except Exception:
                    recent_reasoning = []
                # Register THIS link of the session chain before tearing it down.
                # Each swap starts a new Claude session; offline usage/thinking
                # joins need every session id, not just the final one (recorded
                # after the loop) — otherwise all pre-swap turns are orphaned.
                self.memory.record_agent_session(
                    result.session_id, cwd=self.project_root
                )
                # Tear down ONLY the dead Claude child; bridge/manager/EC live on.
                self.agent.close(f"context respawn {generation}")
                self.agent.ctx_pressure = False
                prompt = self._build_fresh_prompt(recent_reasoning=recent_reasoning)
                # Fresh debug log so the readiness watchdog starts clean.
                try:
                    mcp_debug_log.unlink()
                except OSError:
                    pass
        finally:
            self.agent.close("proof node runtime shutting down")
            self.bridge.close()
        # Persist the agent's Claude session id so offline timeline tooling can
        # find this node's reasoning transcript. Best-effort; never breaks the run.
        self.memory.record_agent_session(result.session_id, cwd=self.project_root)
        if self.bridge.terminal_health is not None and result.returncode == 0:
            health = self.bridge.terminal_health
            suffix = (
                "\n\nMANAGER WORKER ERROR: proof node became unhealthy: "
                f"{health.status}: {health.message}"
            )
            result = ClaudeRunResult(
                text=(result.text.strip() + suffix).strip(),
                session_id=result.session_id,
                returncode=2,
            )
        closed = closed_history_tactics(
            self.project_root / f".ec_session_{self.session_tag}"
        )
        if closed and "PROOF TACTICS:" not in result.text:
            result = ClaudeRunResult(
                text=(result.text.strip() + "\n\n" if result.text.strip() else "")
                + "PROOF TACTICS: "
                + " ".join(closed),
                session_id=result.session_id,
                returncode=result.returncode,
            )
        return result

    def _write_mcp_config(self, *, host: str, port: int, token: str) -> None:
        self._private_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "mcpServers": {
                "proof_node_manager": {
                    "type": "stdio",
                    "command": sys.executable,
                    "args": [
                        "-m",
                        "workflow.proof_node_mcp_server",
                        "--host",
                        host,
                        "--port",
                        str(port),
                        "--token",
                        token,
                        "--node-memory-dir",
                        str(self.memory.dir),
                    ],
                    "env": {
                        "PYTHONPATH": str(self.project_root),
                        "SHANNON_LEGACY_DISPLAY": os.environ.get(
                            "SHANNON_LEGACY_DISPLAY",
                            "hidden",
                        ),
                        "SHANNON_MCP_DEBUG_LOG": str(
                            self._private_dir / "mcp_debug.jsonl"
                        ),
                        "SHANNON_SURFACE_PROFILE": self.surface_profile or "",
                    },
                },
            },
        }
        self._mcp_config_path.write_text(
            json.dumps(config, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        self._mcp_config_path.chmod(0o600)


# §3 of the agent prompt: how to READ what the manager returns (facts, not
# verdicts). The FACT/FORK framing is shown to every rung; the signal-weighing
# block names panels/topics only the richer rungs grant, so it is gated to those.
# No braces — safe to interpolate into the wrapper f-string.


# Part of §4 (how to play well): the final-admit gate.


# §2: one-line description per MCP intent. The single home for "how to use the
# manager" — absorbs what used to be scattered across rewind guidance blocks.


def _read_latest_view(memory: "NodeMemory | None") -> dict[str, Any]:
    if memory is None:
        return {}
    try:
        return json.loads(memory.latest_view.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _profiled_surface_view(
    view_manager: WorkspaceViewManager,
    raw_view: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(raw_view, dict) or not raw_view:
        return {}
    try:
        return view_manager.agent_display_view(raw_view)
    except Exception:
        return dict(raw_view)


def _render_manager_followup(
    turn: ManagedTurn,
    turn_index: int,
    handled_intent: dict[str, Any] | None,
    memory: NodeMemory | None = None,
    full_view: dict[str, Any] | None = None,
    surface_profile: str | None = None,
    base_view: dict[str, Any] | None = None,
) -> str:
    goal_only = surface_profile == "l1_goal_projection"
    view_manager = WorkspaceViewManager()
    audit_view = (
        view_manager.agent_display_view(full_view)
        if isinstance(full_view, dict) and full_view else None
    )
    view = (
        view_manager.agent_display_view(turn.workspace_view)
        if isinstance(turn.workspace_view, dict)
        else {}
    )
    health_event = (
        turn.health_event.to_dict()
        if getattr(turn, "health_event", None) is not None else {}
    )
    actions = _agent_safe_action_summaries(turn.manager_actions)
    result_payload = _drop_empty({
        "turn": turn_index,
        "handled_intent": handled_intent,
        "ok": bool(turn.ok),
        "repair_prompt": turn.repair_prompt,
        "health_event": health_event,
        "manager_note": _turn_interpretation(handled_intent, turn.manager_actions),
        "manager_actions": actions,
        "view_refreshed": bool(view),
    })

    prior_view = base_view if isinstance(base_view, dict) and base_view else _read_latest_view(memory)
    prior_surface_view = _profiled_surface_view(view_manager, prior_view)
    prior_surface = proof_surface_from_turn(prior_view.get("surface_turn") or {})
    surface_turn = compose_surface_turn(
        view,
        surface_profile,
        base_view=prior_surface_view,
        base_surface=prior_surface,
        handled_intent=handled_intent,
        ok=bool(turn.ok),
        repair_prompt=turn.repair_prompt,
        manager_actions=turn.manager_actions,
        health_event=health_event,
        goal_only=goal_only,
    )
    result_payload["surface_turn_hash"] = surface_turn.get("surface_turn_hash")

    target_view = audit_view if isinstance(audit_view, dict) else dict(view)
    target_view["surface_turn"] = surface_turn

    if memory is None:
        submit_line = (
            "---\n\n"
            "Submit exactly one proof intent for the next turn "
            "(`submit_proof_intent`: one `intent` + `payload`).\n"
        )
        return render_surface_turn_markdown(
            surface_turn,
            goal_only=goal_only,
            submit_line=submit_line,
        )

    submit_line = (
        "---\n\n"
        "Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool "
        "(only `intent` + `payload`; no node ids, hashes, request ids, or reasoning "
        "fields).\n\n")
    anchor_block = (
        "The current goal is shown in full above. If context is compacted or "
        "this response is truncated, re-read `LEGAL_LATEST_FOLLOWUP` for the "
        "same agent-readable surface; the raw workspace JSON is audit-only.\n")
    if goal_only:
        anchor_block = (
            "The current goal above is your complete surface. "
            "The raw workspace JSON is the manager's audit file, not part of "
            "your surface — you do not need to open it.\n")
    followup = render_surface_turn_markdown(
        surface_turn,
        goal_only=goal_only,
        submit_line=submit_line,
        anchor_block=anchor_block,
    )
    memory.write_latest_followup(
        turn_index=turn_index,
        result_payload=result_payload,
        workspace_view=target_view,
        followup_text=followup,
    )
    return followup


def closed_history_tactics(session_dir: Path) -> list[str]:
    return _closed_history_tactics(session_dir)


def _emit_json(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


def _slug(value: str) -> str:
    return _shared_node_memory_slug(value)


def _claude_transcript_path(session_id: str, cwd: str | Path | None) -> str:
    """Best-effort path to the Claude Code session transcript for ``session_id``.

    Claude Code stores a session at ``~/.claude/projects/<slug>/<session_id>.jsonl``
    where ``<slug>`` is the launch cwd with EACH non-alphanumeric character
    replaced by ``-`` (e.g. ``/x/.worktrees/y`` -> ``-x--worktrees-y`` — the
    ``/`` and ``.`` both map to a dash, so runs are NOT collapsed; a collapsing
    regex pointed worktree runs at a nonexistent single-dash dir, observed
    2026-06-11). The authoritative key is the session id (the transcript
    filename), so a reader can also recover the file by globbing
    ``~/.claude/projects/*/<session_id>.jsonl`` if this guess is stale.
    """
    base = Path(str(cwd)) if cwd else PROJECT_ROOT
    try:
        base = base.resolve()
    except Exception:
        pass
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(base))
    return str(Path.home() / ".claude" / "projects" / slug / f"{session_id}.jsonl")


# Public name: the worker, playground, and panel-audit tools render the
# agent-facing followup through this entry point.
render_manager_followup = _render_manager_followup
