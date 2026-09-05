"""Curated per-node memory files for one managed proof node.

Owns the ``node_memory/<node>`` on-disk layout (timeline/attempts/failures
JSONL, latest followup/view/proof-so-far, agent-session registry) and the
durable legal-file anchor rendered into agent prompts.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

from workflow.proof_management.common import read_jsonl
from workflow.proof_management.common import (
    node_memory_slug as _shared_node_memory_slug,
)
from workflow.proof_management import (
    ManagedTurn,
)
from workflow.proof_management.node_bootstrap import (
    require_proof_node_manager_bootstrap,
)
from workflow.proof_state_compiler.current_turn_presentation import (
    compose_current_surface_turn,
    render_current_surface_turn_markdown,
    require_current_workspace_view,
)
from workflow.proof_state_compiler.profile_registry import (
    normalize_runtime_surface_profile_id,
)
from workflow.node.agent_prompt_render import (
    _agent_safe_action_summaries,
    _drop_empty,
    render_committed_proof_markdown,
)
from workflow.node.resource_anchor_render import (
    normalize_resource_anchors,
    render_resource_anchors_markdown,
)
from workflow.node.continuation_brief import (
    append_source_breadcrumb,
    normalize_continuation_brief,
    render_continuation_brief_markdown,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class NodeMemory:
    """Curated per-node memory files visible to the long-lived agent."""

    def __init__(self, run_dir: Path, node_id: str,
                 surface_profile: str | None = None) -> None:
        self.node_id = node_id
        self.surface_profile = normalize_runtime_surface_profile_id(
            surface_profile
        )
        self.dir = Path(run_dir) / "node_memory" / _slug(node_id)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.timeline = self.dir / "timeline.jsonl"
        self.attempts = self.dir / "attempts.jsonl"
        self.failures = self.dir / "failures.jsonl"
        self.latest_result = self.dir / "latest_manager_result.json"
        self.latest_view = self.dir / "latest_workspace_view.json"
        self.latest_followup = self.dir / "latest_followup.md"
        self.initial_followup = self.dir / "initial_followup.md"
        self.initial_view = self.dir / "initial_workspace_view.json"
        # Exact manager-bound task prompt passed to the provider session on its
        # first launch. The orchestrator's ``prover_prompt_<node>.md`` is a
        # pre-adoption construction artifact and cannot carry runnable actions.
        self.initial_agent_prompt = self.dir / "initial_agent_prompt.md"
        # The agent's full step-numbered committed proof, refreshed every turn. It
        # is NOT in the per-turn prompt (that would bloat context on long proofs);
        # the standing prompt points the agent here to read it on demand (amend /
        # undo by index, or to re-orient after a context refresh / respawn).
        self.latest_proof = self.dir / "proof_so_far.md"
        self.continuation_brief = self.dir / "continuation_brief.json"
        self.followups_dir = self.dir / "followups"
        self.manager_results_dir = self.dir / "manager_results"
        self.workspace_views_dir = self.dir / "workspace_views"
        self.notes = self.dir / "notes.md"
        self.agent_sessions = self.dir / "agent_sessions.jsonl"
        self._lock = threading.Lock()
        self.resource_anchors: tuple[dict[str, str], ...] = ()
        self._continuation_brief: dict[str, Any] = {}
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

    def record_bootstrap(
        self,
        bootstrap: dict[str, Any],
    ) -> None:
        require_proof_node_manager_bootstrap(
            bootstrap,
            surface_profile=self.surface_profile,
        )
        self.resource_anchors = normalize_resource_anchors(
            bootstrap.get("resource_anchors")
        )
        raw_brief = bootstrap.get("continuation_brief")
        self._continuation_brief = (
            normalize_continuation_brief(raw_brief)
            if raw_brief is not None
            else {}
        )
        if self._continuation_brief:
            self.continuation_brief.write_text(
                json.dumps(
                    self._continuation_brief,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        elif self.continuation_brief.exists():
            self.continuation_brief.unlink()
        self._append_jsonl(
            self.timeline,
            {
                "kind": "bootstrap",
                "node": self.node_id,
                "session_tag": bootstrap["session_tag"],
                "session_dir": bootstrap["session_dir"],
                # `replay_prefix_count` is the SEMANTIC resume count (where
                # the lineage's ORIGINAL inherited prefix ended, propagated
                # across respawns via resume_context); on a respawned node it
                # is smaller than the actual starting history. Record the
                # committed length too so audits don't conflate the two.
                "replay_prefix_count": bootstrap["replay_prefix_count"],
                "replay_prefix_committed_count": len(
                    bootstrap["replay_prefix"]
                ),
                "snapshot": bootstrap["snapshot"],
            },
        )
        self._write_bootstrap_handoff(bootstrap)

    def record_agent_session(
        self,
        session_id: str,
        *,
        cwd: str | Path | None = None,
        agent_backend: str = "codex",
        transcript_root: str | Path | None = None,
    ) -> None:
        """Persist the prover agent's session/thread id for this node.

        Claude records include its external transcript pointer. Codex records
        retain the thread id but intentionally do not guess at a private rollout
        path. Best-effort and idempotent: a node that restarts/resumes may spawn
        several sessions, so this appends and skips ids already recorded.
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
                    "agent_backend": agent_backend,
                    "transcript_path": (
                        _claude_transcript_path(
                            sid, cwd, transcript_root=transcript_root
                        )
                        if agent_backend == "claude"
                        else ""
                    ),
                }),
            )
        except Exception as exc:
            # Losing this record permanently breaks offline transcript
            # association for the session — leave a trace of why.
            print(
                f"node_memory: could not record agent session {sid!r}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return

    def _write_bootstrap_handoff(
        self,
        bootstrap: dict[str, Any],
    ) -> None:
        """Persist the initial current-state view before Claude's first turn."""
        raw_view = bootstrap["workspace_view"]
        canonical_view = require_current_workspace_view(
            raw_view,
            profile_id=self.surface_profile,
            label="bootstrap current workspace view",
        )
        view = dict(canonical_view)
        result_payload = _drop_empty({
            "turn": 0,
            "kind": "bootstrap",
            "node": self.node_id,
            "message": "Initial current-state handoff for this proof node.",
            "replay_prefix_count": bootstrap["replay_prefix_count"],
            "replay_prefix_committed_count": len(
                bootstrap["replay_prefix"]
            ),
            "view_refreshed": bool(view),
        })
        surface_turn = compose_current_surface_turn(
            view,
            self.surface_profile,
            handled_intent={},
            ok=True,
            compiler_markdown=bootstrap.get("compiler_markdown"),
        )
        rendered_turn = render_current_surface_turn_markdown(surface_turn)
        stored_view = dict(canonical_view)
        stored_view["surface_turn"] = surface_turn
        followup = (
            "Initial manager handoff for this proof node.\n\n"
            + rendered_turn
            + "\n\n"
            + f"{_legal_node_memory_anchor(self)}\n"
            + (
                "\n\n" + self.resource_anchor_markdown() + "\n"
                if self.resource_anchors and not self._continuation_brief
                else ""
            )
            + (
                "\n\n" + self.continuation_brief_markdown() + "\n"
                if self._continuation_brief
                else ""
            )
        )
        self.write_latest_followup(
            turn_index=0,
            result_payload=result_payload,
            workspace_view=stored_view,
            followup_text=followup,
            committed_tactics=tuple(bootstrap["replay_prefix"]),
        )

    def resource_anchor_markdown(self) -> str:
        return render_resource_anchors_markdown(self.resource_anchors)

    def continuation_brief_markdown(self) -> str:
        if not self._continuation_brief:
            return ""
        return render_continuation_brief_markdown(self._continuation_brief)

    def record_source_navigation(self, event: dict[str, Any]) -> None:
        """Keep only bounded, explicit source locations for later resume."""

        if event.get("status") not in {"served", "resolved", "miss"}:
            return
        with self._lock:
            updated = append_source_breadcrumb(self._continuation_brief, event)
            if updated == self._continuation_brief:
                return
            self._continuation_brief = updated
            self.continuation_brief.write_text(
                json.dumps(
                    updated,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
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
            "manager_observations": dict(turn.manager_observations),
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

    def write_latest_followup(
        self,
        *,
        turn_index: int,
        result_payload: dict[str, Any],
        workspace_view: dict[str, Any],
        followup_text: str,
        committed_tactics: tuple[str, ...],
    ) -> None:
        """Persist the latest manager-authored current-state handoff.

        These files are legal for the agent to read because they live in the
        current node's curated memory directory.  They are current-state
        transport, not proof-state authority and not historical search.
        """
        # NodeMemory keeps the curated manager surface that was available to
        # this node, not the durable ProverWorkspaceView envelope.  Full views
        # remain in the session-owned artifact/event stream.  For L1 the latest
        # copy leads with an off-surface notice in case a goal-only agent opens
        # it anyway; the per-turn copies remain unannotated for replay.
        agent_latest_view = (
            dict(workspace_view) if isinstance(workspace_view, dict) else {}
        )
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
            proof_md = render_committed_proof_markdown(committed_tactics)
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
            if turn_index == 0:
                self.initial_followup.write_text(
                    followup_text,
                    encoding="utf-8",
                )
                self.initial_view.write_text(
                    json.dumps(workspace_view, indent=2, sort_keys=False) + "\n",
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
    continuation_brief = getattr(
        memory,
        "continuation_brief",
        Path(memory.dir) / "continuation_brief.json",
    )
    return (
        "### Legal Node Memory Anchor\n\n"
        f"LEGAL_NODE_MEMORY_DIR: `{memory.dir}`\n"
        f"LEGAL_LATEST_MANAGER_RESULT: `{memory.latest_result}`\n"
        f"LEGAL_LATEST_FOLLOWUP: `{memory.latest_followup}`\n"
        f"LEGAL_PROOF_SO_FAR: `{memory.latest_proof}` "
        "(your full step-numbered committed proof — read it to pick a step for "
        "`amend_and_replay`/`undo_to_checkpoint`, or to re-orient)\n"
        f"LEGAL_CONTINUATION_BRIEF: `{continuation_brief}` "
        "(bounded outer guidance plus prior concrete blockers/discoveries, when "
        "present)\n\n"
        "Compaction recovery: if these exact paths are missing from your "
        "context, re-read `LEGAL_LATEST_FOLLOWUP` first and "
        "`LEGAL_PROOF_SO_FAR` only when you need accepted-history context. "
        "Submit your next advertised proof intent instead of using shell "
        "directory discovery for proof-state artifacts."
    )


def _slug(value: str) -> str:
    return _shared_node_memory_slug(value)


def _claude_transcript_path(
    session_id: str,
    cwd: str | Path | None,
    *,
    transcript_root: str | Path | None = None,
) -> str:
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
    root = (
        Path(transcript_root)
        if transcript_root is not None
        else Path.home() / ".claude" / "projects"
    )
    return str(root / slug / f"{session_id}.jsonl")
