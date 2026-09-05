"""Long-lived prover-agent runtime for one managed proof node.

A worker process hosts exactly one ``ProofNodeRuntime``. The runtime starts a
manager-owned EasyCrypt node plus one long-lived agent session. Claude Code or
OpenAI Codex does not receive backend commands or own proof state; it calls the structured
``submit_proof_intent`` MCP tool. Eval nodes may also expose manager-owned
EasyCrypt search, read, and exact declaration-resolution tools. A
provider-neutral contract, stdio protocol
adapter, authenticated endpoint, and serialized proof session carry each call
without transferring proof semantics to the provider.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from workflow.proof_management import ManagedTurn
from workflow.proof_management.node_bootstrap import (
    require_proof_node_manager_bootstrap,
)
from workflow.proof_state_compiler.profile_registry import (
    normalize_runtime_surface_profile_id,
)
from workflow.node.manager_followup_render import render_manager_followup
from workflow.node.node_memory import (
    NodeMemory,
    _legal_node_memory_anchor,
    _slug,
)
from workflow.node.proof_node_manager import (
    ProofNodeManager,
)
from workflow.node.no_progress_guidance import NoProgressGuidance
from workflow.schemas.config import normalize_agent_backend
from workflow.proof_tool.easycrypt_source_resource import EasyCryptSourceResource
from workflow.proof_tool.proof_tool_contract import (
    DECLARATION_RESOLVE_TOOL_IDENTITY,
    SOURCE_READ_TOOL_IDENTITY,
    SOURCE_SEARCH_TOOL_IDENTITY,
    ProofToolContractManifest,
    resolve_proof_tool_contract,
)
from workflow.proof_tool.proof_tool_endpoint import ProofToolEndpointServer
from workflow.proof_tool.proof_tool_launch import (
    ProofMcpLaunchSpec,
    proof_tool_timing_for_prefix,
)
from workflow.proof_tool.proof_tool_session import ProofToolSession
from workflow.provider.provider_sessions import (
    ClaudeRunResult,
    agent_session_class,
)
from workflow.provider.eval_agent_confinement import EvalAgentConfinement
from workflow.provider.ctx_respawn import (
    build_accepted_spine,
    build_frontier_brief,
    min_runway_seconds,
    render_handoff_section,
    respawn_disabled,
    respawn_max,
    strip_closed_verdicts,
)

# Long-lived prompt and proof-so-far helpers. Per-turn presentation is owned by
# proof_state_compiler.current_turn_presentation for every current profile.
from workflow.node.agent_prompt_render import (
    render_long_lived_agent_prompt,
)
from workflow.agents.prover_prompt import bind_authoritative_managed_handoff
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MCP_SPAWN_RETRIES = max(0, int(
    os.environ.get("SHANNON_MCP_SPAWN_RETRIES", "2")))
def _prover_system_anchor(
    memory: NodeMemory,
    manifest: ProofToolContractManifest,
    source_resource: EasyCryptSourceResource | None = None,
) -> str:
    """Durable per-node anchor for the agent's standing prompt.

    Holds the two things that must survive a compaction: the one-intent-per-turn
    invariant and the LEGAL_* durable file paths. Claude receives it through
    ``--append-system-prompt``; Codex receives it before the task prompt."""
    anchor_renderer = getattr(memory, "resource_anchor_markdown", None)
    resource_anchors = (
        str(anchor_renderer() or "") if callable(anchor_renderer) else ""
    )
    brief_renderer = getattr(memory, "continuation_brief_markdown", None)
    continuation_brief = (
        str(brief_renderer() or "") if callable(brief_renderer) else ""
    )
    source_anchor = (
        " Source navigation is available only through the manager-owned MCP "
        f"tools `{SOURCE_SEARCH_TOOL_IDENTITY.tool}`, "
        f"`{SOURCE_READ_TOOL_IDENTITY.tool}`, and "
        f"`{DECLARATION_RESOLVE_TOOL_IDENTITY.tool}`; never use provider-native "
        "filesystem, shell, or source-reading tools."
        if manifest.source_navigation_enabled
        else ""
    )
    source_map = (
        source_resource.render_source_map()
        if source_resource is not None
        else ""
    )
    return (
        "## Prover runtime anchor (durable — persists across context compaction)\n\n"
        "You drive the proof ONLY through the MCP tool "
        f"`{manifest.identity.tool}`: exactly "
        "one intent object per turn, and NEVER end a turn without that call (a turn "
        "with only text abandons the proof)."
        f"{source_anchor} The current goal and any bounded "
        "compiler output arrive in each manager turn; these durable node-memory "
        "files are always available to "
        "read on demand:\n\n"
        f"{_legal_node_memory_anchor(memory)}"
        + ("\n\n" + source_map if source_map else "")
        + (
            "\n\n" + resource_anchors
            if resource_anchors and not continuation_brief
            else ""
        )
        + ("\n\n" + continuation_brief if continuation_brief else "")
    )


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
        agent_backend: str = "codex",
        model: str,
        effort: str = "high",
        max_turns: int = 1000,
        surface_profile: str | None = None,
        project_root: Path = PROJECT_ROOT,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        require_proof_node_manager_bootstrap(
            bootstrap,
            label="proof-node runtime bootstrap",
            surface_profile=surface_profile,
            expected_identity={
                "node_id": node_id,
                "session_tag": session_tag,
                "session_dir": f".ec_session_{session_tag}",
                "file": file_path,
                "lemma": lemma_name,
            },
        )
        self.prompt = prompt
        self.bootstrap = bootstrap
        self.file_path = file_path
        self.lemma_name = lemma_name
        self.include_dir = include_dir
        self.session_tag = session_tag
        self.node_id = node_id
        self.run_dir = Path(run_dir)
        self.agent_backend = normalize_agent_backend(agent_backend)
        self.model = model
        self.effort = effort
        self.max_turns = max_turns
        self.surface_profile = normalize_runtime_surface_profile_id(
            surface_profile
        )
        self.project_root = Path(project_root)
        self.eval_mode = (
            os.environ.get("EVAL_TARGET_LEMMA", "").strip() == lemma_name
        )
        raw_emit = emit or _emit_json
        emit_lock = threading.Lock()

        def _emit_serialized(event: dict[str, Any]) -> None:
            with emit_lock:
                memory = getattr(self, "memory", None)
                if (
                    memory is not None
                    and str(event.get("event") or "").startswith(
                        "easycrypt.source_resource."
                    )
                ):
                    memory.record_source_navigation(event)
                raw_emit(event)

        # Provider, readiness, endpoint, and tool-session events originate on different
        # threads. One serialized stream is the sole worker-event boundary.
        self.emit = _emit_serialized
        self.source_resource = EasyCryptSourceResource.from_environment(
            project_root=self.project_root,
            source_file=file_path,
            target_lemma=lemma_name,
            include_dir=include_dir,
            emit=self.emit,
        )
        self.proof_tool_manifest = resolve_proof_tool_contract(
            self.surface_profile,
            source_navigation_enabled=self.source_resource is not None,
        )
        self.manager = ProofNodeManager(
            file_path=file_path,
            lemma_name=lemma_name,
            include_dir=include_dir,
            session_tag=session_tag,
            node_id=node_id,
            run_dir=self.run_dir,
            project_root=self.project_root,
            surface_profile=self.surface_profile,
            proof_tool_manifest=self.proof_tool_manifest,
        )
        self.manager.adopt_bootstrap(bootstrap)
        self.memory = NodeMemory(
            self.run_dir,
            node_id,
            surface_profile=self.surface_profile,
        )
        self._private_dir = self.run_dir / "runtime_private" / _slug(node_id)
        replay_prefix = bootstrap.get("replay_prefix")
        replay_prefix_length = (
            len(replay_prefix) if isinstance(replay_prefix, list) else 0
        )
        self.proof_tool_timing = proof_tool_timing_for_prefix(
            replay_prefix_length
        )
        self.eval_confinement = EvalAgentConfinement.from_environment(
            project_root=self.project_root,
            source_file=file_path,
            target_lemma=lemma_name,
            node_memory_dir=self.memory.dir,
            private_dir=self._private_dir,
            include_dir=include_dir,
        )
        self.memory.record_bootstrap(bootstrap)
        self.no_progress_guidance = NoProgressGuidance()
        bootstrap_status = bootstrap.get("workspace_view", {}).get(
            "proof_status", {}
        )
        self.no_progress_guidance.seed(
            goal_hash=str(bootstrap_status.get("goal_hash") or ""),
            committed_count=replay_prefix_length,
        )
        # A checkpoint is minted only after a completed manager turn advances
        # the committed spine.  This keeps terminal handback O(prefix bytes)
        # instead of replaying the whole proof after a timeout.
        self._last_checkpointed_tactics = tuple(
            tactic
            for tactic in (replay_prefix or [])
            if isinstance(tactic, str) and tactic.strip()
        )
        self.tool_session = ProofToolSession(
            node_id=self.node_id,
            manifest=self.proof_tool_manifest,
            handle_turn=lambda raw_arguments, absolute_deadline: (
                self.manager.handle_tool_arguments(
                    raw_arguments,
                    deadline=absolute_deadline,
                )
            ),
            memory=self.memory,
            response_renderer=self._render_and_checkpoint_manager_turn,
            max_turns=max_turns,
            initial_committed_tactics=tuple(
                tactic
                for tactic in (replay_prefix or [])
                if isinstance(tactic, str) and tactic.strip()
            ),
            emit=self.emit,
        )
        self.endpoint = ProofToolEndpointServer(
            session=self.tool_session,
            manifest=self.proof_tool_manifest,
            source_resource=self.source_resource,
        )
        self.mcp_launch_spec: ProofMcpLaunchSpec | None = None
        self.agent = agent_session_class(self.agent_backend)(
            effort=self.effort,
            model=model,
            source_file=file_path,
            session_tag=session_tag,
            project_root=self.project_root,
            eval_mode=self.eval_mode,
            eval_confinement=self.eval_confinement,
            emit=self.emit,
            proof_tool_manifest=self.proof_tool_manifest,
            readiness_issuer=self.endpoint.expect_launch,
            readiness_waiter=self.endpoint.wait_ready,
            # Canonical registration boundary: every provider session this node
            # spawns is persisted as soon as its id appears on the stream.
            on_session_id=lambda sid: self.memory.record_agent_session(
                sid,
                cwd=self.project_root,
                agent_backend=self.agent_backend,
                transcript_root=(
                    self.eval_confinement.claude_projects_host_dir
                    if self.eval_confinement is not None
                    else None
                ),
            ),
        )
        self._safe_stop_requested = threading.Event()
        self._safe_stop_finalized = threading.Event()
        self._safe_stop_reason = ""
        self._safe_stop_checkpoint_count = 0

    def _render_and_checkpoint_manager_turn(
        self,
        turn: ManagedTurn,
        turn_index: int,
        handled: dict[str, Any] | None,
        memory: NodeMemory,
    ) -> str:
        """Render one completed turn and durably checkpoint new progress.

        The render first writes the turn-coherent manager view into NodeMemory.
        Only then may the checkpoint reader bind the session history and current
        goal.  Checkpoint IO is best-effort continuation infrastructure: losing
        it must not invalidate an otherwise accepted manager turn.
        """

        rendered = render_manager_followup(
            turn,
            turn_index,
            handled,
            memory,
            full_view=self.manager.latest_full_view,
            surface_profile=self.manager.surface_profile,
            runtime_guidance=self.no_progress_guidance.observe(turn, handled),
        )
        spine = tuple(
            tactic
            for tactic in tuple(turn.committed_tactics or ())
            if isinstance(tactic, str) and tactic.strip()
        )
        if spine and spine != self._last_checkpointed_tactics:
            capsules = self._checkpoint_resume_capsules()
            if capsules:
                self._last_checkpointed_tactics = spine
                self.emit({
                    "type": "system",
                    "kind": "proof_node.progress_checkpointed",
                    "node": self.node_id,
                    "manager_turn": turn_index,
                    "committed_count": len(spine),
                    "checkpoint_count": len(capsules),
                })
        return rendered

    def _committed_count(self) -> int:
        """Last manager-returned accepted-spine size (the progress metric)."""

        return self.tool_session.last_committed_count

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

    def _checkpoint_resume_capsules(self) -> tuple[str, ...]:
        """Write resume capsules from the live session (crash-safety + Layer-3 root).

        Mirrors ``prover.py``'s post-run ``create_resume_capsules`` call but points
        at THIS node's still-live session dir. The capsule is NOT consumed by the
        in-worker swap (which never replays); it is a crash-safety checkpoint and
        the root the supervisor's Layer-3 net replays from if the worker dies.
        Best-effort; never breaks the run.
        """
        try:
            from workflow.node.proof_node_resume import create_resume_capsules

            session_dir = self.project_root / f".ec_session_{self.session_tag}"
            created = create_resume_capsules(
                project_root=self.project_root,
                run_dir=self.run_dir,
                session_dirs=[session_dir],
                target_file=self.file_path,
                lemma=self.lemma_name,
                include_dir=self.include_dir,
            )
            return tuple(created)
        except Exception as exc:  # pragma: no cover - best-effort checkpoint
            self.emit({
                "type": "system",
                "context_respawn_checkpoint_failed": str(exc),
                "node": self.node_id,
            })
            return ()

    def request_safe_stop(self, reason: str) -> None:
        """Drain the current manager call and checkpoint before provider exit.

        Timeout, outer cancellation, and direct worker termination all arrive
        here through the worker signal boundary.  The tool session closes new
        admission immediately, waits for the one in-flight semantic turn, and
        exposes its exact committed spine before this method mints a capsule.
        Run-level finalization falls back to the newest earlier compatible
        checkpoint, or publishes the accepted prefix without a checkpoint.  It
        never replays the archived spine merely to make the job terminal.
        """

        requested = getattr(self, "_safe_stop_requested", None)
        if requested is None:
            requested = self._safe_stop_requested = threading.Event()
        if requested.is_set():
            return
        requested.set()
        self._safe_stop_reason = str(reason or "external stop requested").strip()
        boundary = self.tool_session.request_stop(self._safe_stop_reason)
        capsules = self._checkpoint_resume_capsules()
        self._safe_stop_checkpoint_count = len(capsules or ())
        self.emit({
            "type": "system",
            "kind": "proof_node.safe_stop_finalized",
            "node": self.node_id,
            "reason": self._safe_stop_reason,
            "manager_turn": boundary.turn_index,
            "committed_count": len(boundary.committed_tactics),
            "checkpoint_count": self._safe_stop_checkpoint_count,
        })
        finalized = getattr(self, "_safe_stop_finalized", None)
        if finalized is None:
            finalized = self._safe_stop_finalized = threading.Event()
        finalized.set()
        # Releasing the provider makes agent.run return through the ordinary
        # runtime finally path; manager/session state has already crossed the
        # safe checkpoint boundary above.
        self.agent.close("proof node safe stop finalized")

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
        committed = list(self.tool_session.last_committed_tactics)
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
            proof_tool_manifest=self.proof_tool_manifest,
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
        """Whether the cumulative serving turn budget is exhausted."""

        return self.tool_session.turn_index >= self.max_turns

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
        # The turn index is cumulative across generations; never respawn into an
        # already exhausted serving budget.
        if self._turn_limit_exhausted():
            return False
        # Sole trigger: Layer-1 token pressure (the watermark tripped). No
        # give-up-based trigger.
        if not bool(getattr(self.agent, "ctx_pressure", False)):
            return False
        # Event/protocol violations are infrastructure failures, not context
        # pressure. Do not hide them behind a fresh provider invocation.
        if result.returncode == 2:
            return False
        # Never respawn a stopped or unhealthy serving session.
        if self.tool_session.stop_requested or self.tool_session.unhealthy_reason:
            return False
        # Structural (zero-progress) blocks are not contextual — do not respawn.
        if not self._made_progress(baseline):
            return False
        return True

    def run(self) -> ClaudeRunResult:
        eval_confinement = getattr(self, "eval_confinement", None)
        source_resource = getattr(self, "source_resource", None)
        if eval_confinement is not None:
            confinement_probe = eval_confinement.probe(
                agent_backend=self.agent_backend
            )
            eval_confinement.write_audit_record(confinement_probe)
        self.endpoint.start()
        try:
            deadline = self._wall_deadline()
            self._private_dir.mkdir(parents=True, exist_ok=True)
            self.mcp_launch_spec = ProofMcpLaunchSpec(
                manifest=self.proof_tool_manifest,
                endpoint_host=self.endpoint.host,
                endpoint_port=self.endpoint.port,
                endpoint_token=self.endpoint.token,
                private_dir=self._private_dir,
                timing=self.proof_tool_timing,
                node_deadline_epoch=deadline,
                python_executable=sys.executable,
            )
            (self._private_dir / "proof_tool_launch.json").write_text(
                json.dumps(
                    {
                        "schema": "proof_tool_launch/v1",
                        "agent_backend": self.agent_backend,
                        "contract": self.proof_tool_manifest.to_dict(),
                        "timing": self.proof_tool_timing.to_dict(),
                        "adapter_module": self.mcp_launch_spec.adapter_module,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            self.endpoint.close()
            raise
        try:
            prompt = render_long_lived_agent_prompt(
                self.prompt,
                proof_tool_manifest=self.proof_tool_manifest,
                node_memory_dir=self.memory.dir,
                max_turns=self.max_turns,
                surface_profile=self.surface_profile,
            )
            prompt = bind_authoritative_managed_handoff(
                prompt,
                self.memory.initial_followup.read_text(encoding="utf-8"),
            )
            # Persist at the launch boundary, after profile rendering and live
            # manager binding, so audits can distinguish this exact task prompt
            # from the orchestrator's provisional pre-adoption prompt.
            self.memory.initial_agent_prompt.write_text(prompt, encoding="utf-8")
            # Each generation runs against the same manager/session/endpoint.
            # Every provider invocation gets a fresh launch id and must complete
            # the exact readiness handshake before calls are accepted.
            generation = 0
            max_respawns = respawn_max()
            while True:
                committed_at_gen_start = self._committed_count()
                result = self.agent.run(
                    prompt,
                    system_prompt=_prover_system_anchor(
                        self.memory,
                        self.proof_tool_manifest,
                        source_resource,
                    ),
                    mcp_launch_spec=self.mcp_launch_spec,
                )
                # A failed invocation-bound readiness handshake is retried with a
                # new launch id against the same live semantic session.
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
                    result = self.agent.run(
                        prompt,
                        system_prompt=_prover_system_anchor(
                            self.memory,
                            self.proof_tool_manifest,
                            source_resource,
                        ),
                        mcp_launch_spec=self.mcp_launch_spec,
                    )
                if getattr(self.agent, "mcp_failed_to_start", False):
                    result = ClaudeRunResult(
                        text=(
                            "proof-tool MCP failed to become ready after "
                            f"{attempt + 1} provider launch attempt(s)"
                        ),
                        session_id=result.session_id,
                        returncode=2,
                    )
                codex_turn = 1
                while (
                    getattr(self, "agent_backend", "codex") == "codex"
                    and result.returncode == 0
                    and not self.tool_session.unhealthy_reason
                    and not self.tool_session.stop_requested
                    and bool(getattr(self.agent, "last_turn_had_tool_call", False))
                    # Context watermark tripped: fall through to the generation
                    # loop's fresh-context respawn instead of resuming the
                    # saturated thread.
                    and not getattr(self.agent, "ctx_pressure", False)
                    and not self._turn_limit_exhausted()
                    and codex_turn < self.max_turns
                    # This resumes the same Codex thread against the same live
                    # manager/EC session; it is not a cold context respawn.
                    # The 180-second respawn runway below does not apply here.
                    and (deadline is None or time.time() < deadline)
                ):
                    codex_turn += 1
                    self.emit({
                        "type": "system",
                        "agent_backend": "codex",
                        "codex_resume_turn": codex_turn,
                        "session_id": result.session_id,
                        "node": self.node_id,
                    })
                    result = self.agent.run(
                        "Continue the same proof from the manager result already "
                        "present in this thread. Submit the next single advertised "
                        "proof intent now. Keep working until the proof is closed "
                        "or you are genuinely blocked.",
                        mcp_launch_spec=self.mcp_launch_spec,
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
                    result.session_id,
                    cwd=self.project_root,
                    agent_backend=getattr(self, "agent_backend", "codex"),
                    transcript_root=(
                        eval_confinement.claude_projects_host_dir
                        if eval_confinement is not None
                        else None
                    ),
                )
                # Tear down only the provider child; manager/EC/endpoint live on.
                self.agent.close(f"context respawn {generation}")
                self.agent.ctx_pressure = False
                # A fresh context must actually be fresh: clearing the session
                # id stops the Codex path from `exec resume`-ing the saturated
                # thread (Claude already starts a new session per run()).
                self.agent.session_id = ""
                prompt = self._build_fresh_prompt(recent_reasoning=recent_reasoning)
        finally:
            self.agent.close("proof node runtime shutting down")
            self.endpoint.close()
        # Persist the agent's Claude session id so offline timeline tooling can
        # find this node's reasoning transcript. Best-effort; never breaks the run.
        self.memory.record_agent_session(
            result.session_id,
            cwd=self.project_root,
            agent_backend=getattr(self, "agent_backend", "codex"),
            transcript_root=(
                eval_confinement.claude_projects_host_dir
                if eval_confinement is not None
                else None
            ),
        )
        safe_stop_requested = bool(
            getattr(self, "_safe_stop_requested", None)
            and self._safe_stop_requested.is_set()
        )
        if safe_stop_requested:
            result = ClaudeRunResult(
                text=(
                    result.text.strip()
                    + "\n\nMANAGER WORKER STOP: safe-stop drain completed; "
                    "run-level accepted-prefix handback is pending."
                ).strip(),
                session_id=result.session_id,
                returncode=0,
            )
        elif self.tool_session.unhealthy_reason and result.returncode == 0:
            health = self.tool_session.unhealthy_reason
            suffix = (
                "\n\nMANAGER WORKER ERROR: proof node became unhealthy: "
                f"{health}"
            )
            result = ClaudeRunResult(
                text=(result.text.strip() + suffix).strip(),
                session_id=result.session_id,
                returncode=2,
            )
        return ClaudeRunResult(
            text=result.text,
            session_id=result.session_id,
            returncode=result.returncode,
            turns=self.tool_session.turn_index,
        )


def _emit_json(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)
