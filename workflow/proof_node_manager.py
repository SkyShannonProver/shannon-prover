"""Managed prover node facade.

This module implements the internal split behind the single manager the prover
agent sees:

* ``ProofNodeManager`` is the node-level facade.
* ``ReplSessionManager`` owns EasyCrypt/session lifecycle and backend calls.
* ``WorkspaceViewManager`` owns agent-facing view projection/sanitization.

The low-level session CLI remains a backend implementation detail here; it is
not part of the agent-facing protocol.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path
from typing import Any

from core.easycrypt.session_workspace_view_manager import WorkspaceViewManager
from workflow.context_intents import (
    context_payload_for_intent,
    is_context_topic_intent,
    normalize_context_topic,
)
from workflow.proof_management import (
    EscalationPolicy,
    LemmaLineageStore,
    LoopMonitor,
    ManagedTurn,
    ManagerSurfaceProducer,
    NodeProgressSummary,
    ProofCheckpointManager,
    ProofEventManager,
    ProofMemoryManager,
    ProofNodeLifecycleManager,
    ProofNodeStateManager,
    ProofStateSnapshot,
    ProofProjectionPipeline,
    ProofRecoveryIntentHandler,
    ProofTurnExecutor,
    ProofViewRenderer,
    ReplSessionManager,
    preflight_intent,
)
from workflow.proof_management.analyzers import AnalyzerPipeline
from workflow.proof_management.checkpoint_surface import (
    checkpoint_id as _checkpoint_id,
    structural_checkpoints_surface,
)
from workflow.surface_action_preflight import (
    attach_surface_action_preflight,
    action_preflight_key,
    derived_preflight_candidates,
    preflight_result_for_action,
    surface_preflight_candidates,
)
from workflow.surface_action_eligibility import (
    preflight_candidate_state_eligibility,
)
from workflow.proof_management.protocol_repair import (
    AgentIntent,
    intent_is_standalone_qed,
    parse_agent_intent,
    repair_prompt_text_for_streak,
)
from workflow.proof_management.repl_session import (
    history_hash as _history_hash,
    read_committed_tactics as _read_committed_tactics,
    session_dir_path as _session_dir_path,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Anti-premature-give-up gate: a `finish` while the proof is still open is a
# give-up. Push back gently until the agent has insisted ALLOW_AFTER times within
# WINDOW seconds, then honor it. Env-tunable.
_GIVE_UP_WINDOW_S = float(os.environ.get("SHANNON_GIVE_UP_WINDOW_S", str(2 * 60 * 60)))
_GIVE_UP_ALLOW_AFTER = max(1, int(os.environ.get("SHANNON_GIVE_UP_ALLOW_AFTER", "2")))

# Finish-with-admit self-diagnosis nudge (L4 only). When the agent submits
# `finish` while committed admits remain, push back ONCE with a structured
# self-diagnosis prompt (the 4 cases below), then honor `finish` on insist. The
# monotonic per-node counter `_finish_with_admit_count` makes it fire exactly
# once. Default 1 = "ask once, then honor".
_FINISH_WITH_ADMIT_ALLOW_AFTER = max(
    1, int(os.environ.get("SHANNON_FINISH_WITH_ADMIT_ALLOW_AFTER", "1")))

_ADMIT_RE = re.compile(r"(?<![A-Za-z0-9_])admit(?:\s*\.|\s*;|\s*$)", re.IGNORECASE)


def _tactic_has_admit(tactic: str) -> bool:
    return bool(_ADMIT_RE.search(str(tactic or "")))

# The 4-case prompt. Rewind is DEMOTED — its cost is fronted and its mechanics
# appear only in case (a); cases (b)/(c)/(d) explicitly say do NOT rewind — so
# this does not push an agent to rewind when the fix is local or the goal is a
# genuine boundary. The agent self-classifies (the manager cannot read its
# private reasoning). Honoring on the 2nd finish is the escape valve for (c)/(d).
_FINISH_DIAGNOSE_PROMPT = (
    "You submitted `finish`, but the proof still sets aside {n} un-discharged "
    "`admit.` tactic(s): {shown}. An admitted subgoal is parked, not proved — "
    "this proof cannot be accepted while any admit remains. Before you stop, "
    "diagnose what blocks the HARDEST remaining admit and take the matching "
    "action. The four cases below are mutually exclusive; judge which one you are "
    "actually in. (Rewinding re-opens an earlier cut and discards the committed "
    "steps after it — that is the correct move in exactly one of these cases and "
    "the wrong move in the others, so the judgement, not a default, decides.)\n\n"
    "(a) THE CUT WAS WRONG. An earlier committed `seq`/`call`/`while` split or its "
    "invariant is itself incorrect, so this subgoal is unprovable AS STATED — no "
    "tactic on this goal can close it. The fix is to rewind: the direct context "
    "intent `checkpoints` lists the committed cut points; submit the shown "
    "`undo_to_checkpoint` payload to return to before the bad cut and re-cut it "
    "with a corrected split/invariant.\n"
    "(b) PROVABLE, JUST HARD. The cut and invariant are correct; you simply have "
    "not found the steps yet. Keep working in place — more tactics, a helper "
    "lemma, `lookup_symbol`, or smt hints.\n"
    "(c) OUT OF REACH. Closing it needs a lemma that does not exist or a step "
    "beyond the available tactics. Rewinding will not help; record the gap and "
    "finishing is reasonable.\n"
    "(d) THE GOAL IS UNSOUND. You judge the stated goal is false / not provable as "
    "written. Stopping is correct; record why.\n\n"
    "Distinguishing (a) from (b) is the crux: ask whether the obstacle lives in "
    "THIS goal's available facts (then it is (b) — keep working) or is baked into "
    "an earlier cut/invariant that simply cannot supply what this goal needs (then "
    "it is (a) — rewind and re-cut). If after taking the matching action you still "
    "want to stop (case c or d), submit `finish` again and it will be honored — "
    "name which case applies."
)


class ProofNodeManager:
    """Single node manager facade visible to orchestration and the agent."""

    def __init__(
        self,
        *,
        file_path: str,
        lemma_name: str,
        include_dir: str,
        session_tag: str,
        node_id: str = "",
        run_dir: Path | None = None,
        project_root: Path = PROJECT_ROOT,
        surface_profile: str | None = None,
    ) -> None:
        self.node_id = node_id or session_tag
        self.session_tag = session_tag
        self.run_dir = Path(run_dir) if run_dir is not None else None
        # ``surface_profile`` is the RUN profile; for "adaptive" it stays as-is so the
        # MCP tool schema advertises the full intent superset (the agent can SEE the
        # richer levers). Gating + view projection use ``escalation.effective_profile``
        # instead, which starts at the cheap L1 base and flips to the escalate profile
        # once the agent has objectively stalled.
        self.surface_profile = surface_profile
        # Adaptive L1->escalate surface decision lives in EscalationPolicy (audit
        # §8 #8). The callbacks are lazy: `state_version`/`propagate_profile` read
        # components built later in this __init__, but only fire at monitor/escalate
        # time; `propagate_profile` then switches projection + intent-gating together.
        self.escalation = EscalationPolicy(
            surface_profile=surface_profile,
            node_id=self.node_id,
            audit=self._audit,
            state_version=lambda: self.repl.state_version,
            latest_view=lambda: self.latest_view,
            latest_snapshot=lambda: self.latest_snapshot,
            propagate_profile=self._propagate_effective_profile,
        )
        # Mechanism CATCH — the local-patch / no-progress loop detector (episode
        # latch + escalation) lives in LoopMonitor (audit §8 #8). Flag-only: it
        # surfaces a neutral `local_patch_loop` banner, never gates a turn.
        self.loop_monitor = LoopMonitor()
        # Manager-state-derived call-frontier structure lives in
        # ManagerSurfaceProducer (audit §8 #8); the callback reads the live session
        # dir lazily at inject time.
        self.surfaces = ManagerSurfaceProducer(
            session_dir=lambda: getattr(self.repl, "session_dir", None),
        )
        self.repl = ReplSessionManager(
            file_path=file_path,
            lemma_name=lemma_name,
            include_dir=include_dir,
            session_tag=session_tag,
            node_id=self.node_id,
            project_root=project_root,
        )
        self.workspace = WorkspaceViewManager()
        self.node_state = ProofNodeStateManager(
            node_id=self.node_id,
            committed_tactic_reader=lambda: _read_committed_tactics(
                _session_dir_path(self.repl.session_dir, self.repl.project_root)
            ),
        )
        self.analyzers = AnalyzerPipeline()
        self.renderer = ProofViewRenderer()
        self.lineage = LemmaLineageStore(run_dir=self.run_dir)
        self.events = ProofEventManager(
            node_id=self.node_id,
            run_dir=self.run_dir,
        )
        self.checkpoints = ProofCheckpointManager(
            node_id=self.node_id,
            run_dir=self.run_dir,
            history_hash=_history_hash,
            confirmation_id=_confirmation_id,
        )
        self.malformed_count = 0
        self.proof_memory = ProofMemoryManager(
            node_id=self.node_id,
            run_dir=self.run_dir,
            history_hash=_history_hash,
            confirmation_id=_confirmation_id,
        )
        self.projection = ProofProjectionPipeline(
            workspace=self.workspace,
            node_state=self.node_state,
            checkpoints=self.checkpoints,
            proof_memory=self.proof_memory,
            events=self.events,
            analyzers=self.analyzers,
            renderer=self.renderer,
            file_path=self.repl.file_path,
            project_root=str(self.repl.project_root),
            surface_profile=self.escalation.effective_profile,
        )
        self.lifecycle = ProofNodeLifecycleManager(
            node_id=self.node_id,
            session_tag=self.session_tag,
            repl=self.repl,
            projection=self.projection,
            lineage=self.lineage,
            workspace=self.workspace,
            run_dir=lambda: self.run_dir,
            audit=self._audit,
            surface_profile=self.escalation.effective_profile,
        )
        self.recovery = ProofRecoveryIntentHandler(
            node_id=self.node_id,
            checkpoints=self.checkpoints,
            proof_memory=self.proof_memory,
            lineage=self.lineage,
            repl=self.repl,
            committed_tactics=self._current_committed_tactics,
            latest_view=lambda: self.latest_view,
            replay_prefix_count=lambda: self._replay_prefix_count,
            resumed_lineage=lambda: self._resumed_from_prefix,
            clear_replay_prefix=self._clear_replay_prefix,
            run_dir=lambda: self.run_dir,
        )
        self.turns = ProofTurnExecutor(
            node_id=self.node_id,
            repl=self.repl,
            events=self.events,
            lineage=self.lineage,
            latest_snapshot=lambda: self.latest_snapshot,
            latest_view=lambda: self.latest_view,
            set_latest_view=self._set_latest_view,
            project=lambda snapshot, latest: self._project(
                snapshot,
                latest_observation=latest,
            ),
            audit=self._audit,
            run_dir=lambda: self.run_dir,
            surface_profile=self.escalation.effective_profile,
        )

    @property
    def latest_snapshot(self) -> ProofStateSnapshot | None:
        return self.lifecycle.latest_snapshot

    @latest_snapshot.setter
    def latest_snapshot(self, value: ProofStateSnapshot | None) -> None:
        self.lifecycle.latest_snapshot = value

    @property
    def latest_view(self) -> dict[str, Any]:
        return self.lifecycle.latest_view

    @latest_view.setter
    def latest_view(self, value: dict[str, Any]) -> None:
        self.lifecycle.latest_view = dict(value) if isinstance(value, dict) else {}

    @property
    def latest_full_view(self) -> dict[str, Any]:
        """The complete (un-leaned) view for the audit JSON; falls back to the lean
        view if a full view was not captured."""
        return self.lifecycle.latest_full_view or self.lifecycle.latest_view

    @property
    def state_version(self) -> int:
        """The committed EC state version. A manager-facade accessor so callers
        don't reach through to ``manager.repl`` (the one prior facade bypass)."""
        return self.repl.state_version

    @property
    def _resumed_from_prefix(self) -> bool:
        """Durable resumed-lineage marker (survives a rewind-below-floor clear)."""
        return bool(getattr(self.lifecycle, "resumed_from_prefix", False))

    @property
    def _replay_prefix_count(self) -> int:
        return self.lifecycle.replay_prefix_count

    @_replay_prefix_count.setter
    def _replay_prefix_count(self, value: int) -> None:
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        self.lifecycle.replay_prefix_count = max(0, count)

    @property
    def _replay_prefix(self) -> list[str]:
        return self.lifecycle.replay_prefix

    @_replay_prefix.setter
    def _replay_prefix(self, value: list[str]) -> None:
        self.lifecycle.replay_prefix = [
            str(tactic).strip()
            for tactic in (value or [])
            if str(tactic).strip()
        ]

    def adopt_bootstrap(self, bootstrap: dict[str, Any]) -> None:
        """Adopt a session that was already bootstrapped by this manager layer.

        Tree workers run as their own process after the orchestrator prepares
        the node session.  They need to continue the same manager-owned
        session without restarting EasyCrypt, so this method seeds the facade
        with the latest handoff view and metadata.
        """
        self.lifecycle.adopt_bootstrap(bootstrap)

    def bootstrap(
        self,
        replay_prefix: list[str] | None = None,
        *,
        resume_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = self.lifecycle.bootstrap(
            replay_prefix=replay_prefix,
            resume_context=resume_context,
        )
        view = record.get("workspace_view") if isinstance(record, dict) else None
        preflight_results: list[dict[str, Any]] | None = None
        if isinstance(view, dict):
            self.surfaces.inject_call_frontier_structure(view)
            preflight_results = self._surface_action_preflight_results(view)
            attach_surface_action_preflight(view, preflight_results)
            self.lifecycle.latest_view = view
        full = self.lifecycle.latest_full_view
        if isinstance(full, dict) and full is not view:
            self.surfaces.inject_call_frontier_structure(full)
            if preflight_results is not None:
                attach_surface_action_preflight(full, preflight_results)
        return record

    def handle_agent_message(self, text: str) -> ManagedTurn:
        result = self._handle_agent_message_core(text)
        self.escalation.monitor()
        self._assemble_manager_surfaces(result)
        return result

    def _assemble_manager_surfaces(self, result: ManagedTurn) -> None:
        """Assemble manager-derived call-frontier and loop-observation surfaces."""
        lean = getattr(result, "workspace_view", None)
        full = getattr(self.lifecycle, "latest_full_view", None)
        preflight_results: list[dict[str, Any]] | None = None
        if isinstance(lean, dict):
            self.surfaces.inject_call_frontier_structure(lean)
            preflight_results = self._surface_action_preflight_results(lean)
            attach_surface_action_preflight(lean, preflight_results)
            self.loop_monitor.inject(result, full_view=full)
        if isinstance(full, dict) and full is not lean:
            self.surfaces.inject_call_frontier_structure(full)
            if preflight_results is not None:
                attach_surface_action_preflight(full, preflight_results)

    def _surface_action_preflight_results(self, view: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = [
            action
            for action in surface_preflight_candidates(view)
            if preflight_candidate_state_eligibility(
                view,
                str(action.get("intent") or ""),
                action.get("payload")
                if isinstance(action.get("payload"), dict)
                else {},
            ).eligible
        ]
        if not candidates:
            return []
        results: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        seen = {
            action_preflight_key(
                str(action.get("intent") or ""),
                action.get("payload") if isinstance(action.get("payload"), dict) else {},
            )
            for action in candidates
        }
        for action in candidates:
            intent = str(action.get("intent") or "")
            payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
            summary = self.repl.read_only_context_action(intent, payload)
            preflight = preflight_result_for_action(intent, payload, summary)
            results.append(preflight)
            records.append({
                "intent": intent,
                "payload": payload,
                "summary": summary,
                "preflight_result": preflight,
            })
        for action in derived_preflight_candidates(view, records):
            intent = str(action.get("intent") or "")
            payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
            key = action_preflight_key(intent, payload)
            if key in seen:
                continue
            seen.add(key)
            summary = self.repl.read_only_context_action(intent, payload)
            results.append(preflight_result_for_action(intent, payload, summary))
        return results

    def _handle_agent_message_core(self, text: str) -> ManagedTurn:
        parsed = parse_agent_intent(text)
        if not parsed.ok or parsed.intent is None:
            self.malformed_count += 1
            self.events.record_malformed_intent(
                error=parsed.error,
                malformed_count=self.malformed_count,
                state_version=self.repl.state_version,
            )
            # A malformed/empty intent is a RECOVERABLE no-op: the manager ran no
            # EasyCrypt command, so it re-issues the latest workspace view with a
            # corrective nudge instead of bricking the node. We deliberately do
            # NOT emit a terminal `agent_protocol_stuck` health event on a streak
            # — that turned three consecutive empty intents (observed near the
            # finish line of several runs) into a terminal wedge in the runtime
            # bridge (`terminal_health`), killing the node instead of re-prompting.
            # The overall turn budget (`max_turns`) remains the backstop; the
            # nudge escalates with the streak to break the loop.
            self._audit({
                "kind": "agent_intent.malformed",
                "node": self.node_id,
                "error": parsed.error,
                "malformed_count": self.malformed_count,
                "recoverable": True,
            })
            return ManagedTurn(
                ok=False,
                workspace_view=dict(self.latest_view),
                snapshot=self.latest_snapshot,
                repair_prompt=repair_prompt_text_for_streak(self.malformed_count),
                health_event=None,
                manager_actions=[],
            )

        self.malformed_count = 0
        self.events.record_intent_received(
            intent=parsed.intent.intent,
            payload=parsed.intent.payload,
            state_version=self.repl.state_version,
        )
        admit_gate = self._committed_admit_gate(parsed.intent)
        if admit_gate is not None:
            return admit_gate
        give_up_gate = self._give_up_gate(parsed.intent)
        if give_up_gate is not None:
            return give_up_gate
        # ADAPTIVE: in the cheap phase the agent may NOT pull the richer levers — the
        # manager decides escalation from objective stall, not from the agent's reach.
        # Reaching for a gated intent is rejected with guidance; it still counts as a
        # no-progress turn (post-turn monitor), nudging toward auto-escalation.
        if self.escalation.adaptive and not self.escalation.escalated:
            reach_block = self.escalation.reach_block(parsed.intent)
            if reach_block is not None:
                return reach_block
        preflight = preflight_intent(
            intent=parsed.intent,
            latest_view=self.latest_view,
            surface_profile=self.escalation.effective_profile,
        )
        if preflight.should_handle:
            return self.turns.handle_preflight_decision(parsed.intent, preflight)
        if parsed.intent.intent == "fresh_restart":
            return self.turns.execute_recovery_plan(
                parsed.intent,
                self.recovery.handle_fresh_restart(parsed.intent),
            )
        if parsed.intent.intent == "amend_and_replay":
            return self.turns.execute_recovery_plan(
                parsed.intent,
                self.recovery.handle_amend_and_replay(parsed.intent),
            )
        if parsed.intent.intent == "undo_to_checkpoint":
            return self.turns.execute_recovery_plan(
                parsed.intent,
                self.recovery.handle_undo_to_checkpoint(parsed.intent),
            )
        if parsed.intent.intent == "commit_replay_suffix_chunk":
            return self.turns.execute_recovery_plan(
                parsed.intent,
                self.recovery.handle_commit_replay_suffix_chunk(parsed.intent),
            )
        if parsed.intent.intent == "inspect_context" or is_context_topic_intent(parsed.intent.intent):
            topic_payload = (
                context_payload_for_intent(parsed.intent.intent, parsed.intent.payload)
                if is_context_topic_intent(parsed.intent.intent)
                else dict(parsed.intent.payload or {})
            )
            topic = normalize_context_topic(topic_payload.get("topic") or "")
            if topic == "diagnose":
                return self._handle_inspect_diagnose(parsed.intent)
            if topic == "checkpoints":
                return self._handle_inspect_checkpoints(parsed.intent)
        return self.turns.repl_call(
            parsed.intent,
            lambda: self.repl.handle_intent(parsed.intent),
        )

    def _handle_inspect_checkpoints(self, intent: "AgentIntent") -> ManagedTurn:
        """`checkpoints`: the structural rewind menu, on demand.

        The rewind-target menu (`rewind_targets`) was previously surfaced ONLY
        in the failure-recovery focus — i.e. right after a rejected commit. An
        agent at a closed-candidate / admit-discharge state (e.g. a resumed node
        with committed admits remaining) that diagnoses an UPSTREAM cut/invariant as
        the real blocker and wants to rewind to re-cut had no way to DISCOVER the
        checkpoint targets: the `checkpoints` topic 404'd and no menu was in the
        view, so a correct rewind diagnosis could not be acted on (observed live:
        the agent asked for `checkpoints`, got "not surfaced", and
        gave up instead of rewinding). This makes the structural checkpoints —
        each with a ready-to-submit `undo_to_checkpoint` payload — requestable in
        ANY state. Purely additive; never narrows. Never raises.
        """
        view = dict(self.latest_view) if isinstance(self.latest_view, dict) else {}
        try:
            tactics = self._current_committed_tactics()
        except Exception:
            tactics = []
        items: list[dict[str, Any]] = []
        if tactics:
            try:
                items = structural_checkpoints_surface(
                    tactics, replay_prefix_count=self._replay_prefix_count,
                )
            except Exception:
                items = []
        view["checkpoint_menu"] = {
            "checkpoints": items,
            "note": (
                "Structural rewind targets in THIS node's committed proof. "
                "Submit the `undo_to_checkpoint` payload shown on a target to "
                "rewind to it: that restores the committed proof to the selected "
                "point (undoing that tactic and every committed tactic after it), "
                "and later steps can then be re-committed."
            ) if items else "No committed tactics to rewind to yet.",
        }
        ok = bool(items)
        return ManagedTurn(
            ok=ok, workspace_view=view, snapshot=self.latest_snapshot, intent=intent,
            manager_actions=[
                {"label": "checkpoints", "topic": "checkpoints", "ok": ok},
            ],
        )

    def _handle_inspect_diagnose(self, intent: "AgentIntent") -> ManagedTurn:
        """Return the backend diagnosis for the committed EasyCrypt session."""
        return self.turns.repl_call(
            intent, lambda: self.repl.handle_intent(intent)
        )

    def _committed_admit_gate(self, intent: "AgentIntent"):
        """Block finish/qed while committed `admit.` tactics remain.

        Returns a clarification ManagedTurn if the agent tries to finish or qed
        with un-discharged admits; otherwise None (proceed normally).
        """
        is_finish = intent.intent == "finish"
        is_qed = intent_is_standalone_qed(intent.intent, intent.payload)
        if not (is_finish or is_qed):
            return None
        debt = [item["gate_label"] for item in self._committed_admit_records()]
        if not debt:
            return None
        shown = ", ".join(debt[:6]) + ("…" if len(debt) > 6 else "")
        # L4-only finish self-diagnosis nudge. `finish` with admits is a give-up;
        # at L4 — the only profile carrying the rewind affordances this nudge
        # points to (L1 has neither `checkpoints` nor `undo_to_checkpoint`) —
        # push back ONCE with the 4-case prompt, then honor `finish` on insist
        # (monotonic per-node counter). `qed` with admits, and `finish` on any
        # non-L4 profile, keep the flat hard block unchanged.
        # Key on the EFFECTIVE profile (what actually governs the agent's
        # intents/topics), not the raw run profile: under "adaptive" the manager
        # starts at l1 and escalates to l4, and the nudge must fire only once the
        # agent truly holds the l4 affordances (`checkpoints` / `undo_to_checkpoint`).
        is_l4 = str(self.escalation.effective_profile or "").startswith("l4")
        if is_finish and is_l4:
            n = getattr(self, "_finish_with_admit_count", 0)
            if n >= _FINISH_WITH_ADMIT_ALLOW_AFTER:
                self._audit({"kind": "admit_finish.honored",
                             "node": self.node_id, "admits": debt, "pushbacks": n})
                return None  # agent insisted — honor; _give_up_gate is guarded
            self._finish_with_admit_count = n + 1
            self._audit({"kind": "admit_finish.diagnose",
                         "node": self.node_id, "admits": debt, "pushbacks": n + 1})
            prompt = _FINISH_DIAGNOSE_PROMPT.format(n=len(debt), shown=shown)
        else:
            prompt = (
                f"The proof still has {len(debt)} un-discharged `admit.` tactic(s): {shown}. "
                "An `admit`-ed subgoal is set aside, not proved — the lemma is not "
                "complete until each admit is replaced with a real proof. Undo the "
                "admit and prove that subgoal before qed/finish."
            )
        view = dict(self.latest_view) if isinstance(self.latest_view, dict) else {}
        return ManagedTurn(
            ok=False, workspace_view=view, snapshot=self.latest_snapshot,
            intent=intent, repair_prompt=prompt,
            manager_actions=[{"label": "committed_admit_gate", "admits": debt}],
        )

    def _give_up_gate(self, intent: "AgentIntent"):
        """Discourage premature give-up.

        A `finish` while the proof is still OPEN (goals remain) is a give-up. Push
        back gently the first ``_GIVE_UP_ALLOW_AFTER - 1`` times within a sliding
        ``_GIVE_UP_WINDOW_S`` window, then honor the give-up once the agent has
        insisted that many times. NEVER gates a real completion (status complete /
        0 goals) — a successful finish always passes through.

        Returns a clarification ManagedTurn to deflect, or None to proceed.
        """
        if intent.intent != "finish":
            return None
        # Guard against double-prompting: if the L4 admit-finish nudge has
        # already pushed back and then honored this `finish` (counter reached the
        # allow-after threshold), the agent has already self-diagnosed and
        # insisted — do not make it run the give-up gauntlet a second time. The
        # counter is only ever > 0 after the admit gate fired (which requires
        # committed admits), so normal give-ups are unaffected.
        if getattr(self, "_finish_with_admit_count", 0) >= _FINISH_WITH_ADMIT_ALLOW_AFTER:
            return None
        lv = self.latest_view if isinstance(self.latest_view, dict) else {}
        ps = lv.get("proof_status") if isinstance(lv.get("proof_status"), dict) else {}
        status = str(ps.get("status") or "")
        remaining = ps.get("remaining_goals")
        # A give-up = finishing while the proof is genuinely OPEN. Closed /
        # candidate_* (e.g. `candidate_closed_pending_qed`, still needs `qed.`) /
        # complete / unknown statuses are NOT give-ups — never gate a real or
        # closing finish.
        if not (status == "open" and remaining != 0):
            return None
        now = time.time()
        times = [
            t for t in getattr(self, "_give_up_times", [])
            if now - t < _GIVE_UP_WINDOW_S
        ]
        times.append(now)
        self._give_up_times = times
        n = len(times)
        if n >= _GIVE_UP_ALLOW_AFTER:
            self._audit({
                "kind": "give_up.allowed",
                "node": self.node_id,
                "attempts_in_window": n,
                "remaining_goals": remaining,
            })
            return None  # the agent has insisted — honor the give-up
        goals_txt = (
            f"{remaining} goal(s) still open"
            if isinstance(remaining, int) else "the proof still open"
        )
        prompt = (
            f"You submitted `finish` with {goals_txt}. That is your call — if you "
            "have already considered the alternatives and are genuinely blocked, "
            "finishing is fine; just record the blocker in "
            "PROVER REPORT.open_questions so it is captured. If you have not tried "
            "a different angle yet, one more turn is often worth it: a different "
            "tactic, direct context topics such as `diagnose` / `tactic_forms`, "
            "`lookup_symbol` a relevant lemma. To "
            "stop now, just submit `finish` again."
        )
        self._audit({
            "kind": "give_up.deflected",
            "node": self.node_id,
            "attempts_in_window": n,
            "allow_after": _GIVE_UP_ALLOW_AFTER,
            "remaining_goals": remaining,
        })
        view = dict(self.latest_view) if isinstance(self.latest_view, dict) else {}
        return ManagedTurn(
            ok=False, workspace_view=view, snapshot=self.latest_snapshot,
            intent=intent, repair_prompt=prompt,
            manager_actions=[{
                "label": "give_up_gate",
                "attempts_in_window": n,
                "allow_after": _GIVE_UP_ALLOW_AFTER,
            }],
        )

    def _current_committed_tactics(self) -> list[str]:
        return self.node_state.current_committed_tactics()

    def _committed_admits(self) -> list[str]:
        """Un-discharged `admit.` tactics read straight from the committed
        proof (``history.ec``), as the gate's display strings.

        Kept as the string-list façade over `_committed_admit_records`.
        """
        return [
            rec["gate_label"] for rec in self._committed_admit_records()
        ]

    def _committed_admit_records(self) -> list[dict[str, Any]]:
        """Structured ledger of un-discharged `admit.` tactics in the
        committed proof (``history.ec``): step number, tactic, the committed
        step that preceded it (the short context of the parked subgoal), and a
        ready-to-submit rewind checkpoint restoring the proof to just before
        the admit.

        This is the resume-surviving source of truth for admit debt. The
        committed history contains replayed prefixes, reflects every live commit,
        and is truncated on rewind, so scanning it stays honest both at resume
        and after a discharge.

        Checkpoint coordinates: ``cp_N_<digest16>`` rewinds to BEFORE committed
        tactic #N (``rewind_before_tactic`` keeps N-1 tactics), so the
        checkpoint that lands just before an admit at step N is ``cp_N`` — it
        undoes the admit itself and every committed tactic after it. The digest
        is computed over the CURRENT committed history so the id is immediately
        submittable this turn.
        """
        try:
            tactics = [str(t or "") for t in self._current_committed_tactics()]
        except Exception:
            return []

        def _short(text: str) -> str:
            flat = " ".join(text.split())
            return flat if len(flat) <= 60 else flat[:59] + "…"

        records: list[dict[str, Any]] = []
        digest = ""
        for idx, tactic in enumerate(tactics):
            if not _tactic_has_admit(tactic):
                continue
            step = idx + 1
            label = _short(tactic)
            rec: dict[str, Any] = {
                "kind": "committed_admit",
                "step": step,
                "tactic": label,
                "gate_label": f"committed admit (step {step}): {label}",
            }
            if idx > 0:
                rec["parked_after"] = f"step {idx}: `{_short(tactics[idx - 1])}`"
            try:
                if not digest:
                    digest = _history_hash(tactics)
                cid = _checkpoint_id(digest, step)
                rec["rewind_checkpoint"] = {
                    "checkpoint_id": cid,
                    "committed_step_index": step,
                    "label": f"Just before this admit (committed tactic #{step})",
                    "effect_if_selected": (
                        f"Undo committed tactic #{step} (the admit) and every "
                        "committed tactic after it in this node."
                    ),
                    "submit": {
                        "intent": "undo_to_checkpoint",
                        "payload": {"checkpoint_id": cid},
                    },
                }
            except Exception:
                pass
            records.append(rec)
        return records

    def _clear_replay_prefix(self) -> None:
        self.lifecycle.clear_replay_prefix()

    def progress_summary(self) -> NodeProgressSummary:
        return self.lifecycle.progress_summary()

    def _set_latest_view(self, view: dict[str, Any]) -> None:
        self.lifecycle.set_latest_view(view)

    # ---- adaptive surface escalation (lives in EscalationPolicy) ----
    def _propagate_effective_profile(self, profile: str | None) -> None:
        """Push the escalated profile to every live profile-holder so projection
        AND intent-gating switch to the full surface from the next turn. Wired into
        EscalationPolicy as its ``propagate_profile`` callback."""
        self.projection.surface_profile = profile
        self.lifecycle.surface_profile = profile
        self.turns.surface_profile = profile

    def _project(
        self,
        snapshot: ProofStateSnapshot,
        *,
        latest_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.lifecycle.project(
            snapshot,
            latest_observation=latest_observation,
        )

    def _audit(self, record: dict[str, Any]) -> None:
        self.events.run_dir = self.run_dir
        self.events.audit(record)


def _confirmation_id(node_id: str, state_version: int, history_hash: str) -> str:
    seed = f"{node_id}:{state_version}:{history_hash}:{time.time_ns()}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
