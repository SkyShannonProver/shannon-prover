"""Managed prover node facade.

This module implements the internal split behind the single manager the prover
agent sees:

* ``ProofNodeManager`` is the node-level facade.
* ``ReplSessionManager`` owns EasyCrypt/session lifecycle and backend calls.
* every run uses ``ManagedGoalViewManager`` for the neutral goal envelope;
* the compiler contributes one already-admitted Markdown block.

The low-level session CLI remains a backend implementation detail here; it is
not part of the agent-facing protocol.  Importing and constructing a current
manager must not load the historical compiler/view modules.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from core.easycrypt.committed_history import (
    read_committed_tactics as _read_committed_tactics,
)
from workflow.proof_management import (
    LemmaLineageStore,
    ManagedTurn,
    NodeProgressSummary,
    ProofCheckpointManager,
    ProofEventManager,
    ProofNodeLifecycleManager,
    ProofStateSnapshot,
    ProofProjectionPipeline,
    ProofRecoveryIntentHandler,
    ProofTurnExecutor,
    ReplSessionManager,
    preflight_intent,
)
from workflow.proof_management.checkpoint_surface import (
    checkpoint_id as _checkpoint_id,
)
from workflow.proof_management.protocol_repair import (
    AgentIntent,
    intent_is_standalone_qed,
    parse_agent_intent,
    repair_prompt_text_for_streak,
)
from workflow.proof_management.repl_session import (
    history_hash as _history_hash,
    session_dir_path as _session_dir_path,
)
from workflow.proof_state_compiler.service import CompilerServiceSkipped
from workflow.proof_state_compiler.configuration import (
    compiler_service_for_profile,
)
from workflow.proof_state_compiler.profile_registry import (
    normalize_current_surface_profile_id,
)
from workflow.proof_state_compiler.managed_goal_view_manager import (
    ManagedGoalViewManager,
)
from workflow.proof_state_compiler.turn_evidence import compiler_turn_evidence

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Anti-premature-give-up gate: a `finish` while the proof is still open is a
# give-up. Push back gently until the agent has insisted ALLOW_AFTER times within
# WINDOW seconds, then honor it. Env-tunable.
_GIVE_UP_WINDOW_S = float(os.environ.get("SHANNON_GIVE_UP_WINDOW_S", str(2 * 60 * 60)))
_GIVE_UP_ALLOW_AFTER = max(1, int(os.environ.get("SHANNON_GIVE_UP_ALLOW_AFTER", "2")))
_ADMIT_RE = re.compile(r"(?<![A-Za-z0-9_])admit(?:\s*\.|\s*;|\s*$)", re.IGNORECASE)


def _tactic_has_admit(tactic: str) -> bool:
    return bool(_ADMIT_RE.search(str(tactic or "")))

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
        self.surface_profile = normalize_current_surface_profile_id(
            surface_profile
        )
        self.repl = ReplSessionManager(
            file_path=file_path,
            lemma_name=lemma_name,
            include_dir=include_dir,
            session_tag=session_tag,
            node_id=self.node_id,
            project_root=project_root,
        )
        self.compiler_service = compiler_service_for_profile(
            self.surface_profile,
            self.repl,
        )
        self.workspace = ManagedGoalViewManager()
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
        self._rejection_goal_hash = ""
        self._current_goal_rejections: list[dict[str, Any]] = []
        self.projection = ProofProjectionPipeline(
            workspace=self.workspace,
            surface_profile=self.surface_profile,
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
            surface_profile=self.surface_profile,
        )
        self.recovery = ProofRecoveryIntentHandler(
            node_id=self.node_id,
            checkpoints=self.checkpoints,
            repl=self.repl,
            committed_tactics=self._current_committed_tactics,
            replay_prefix_count=lambda: self._replay_prefix_count,
            resumed_lineage=lambda: self._resumed_from_prefix,
            clear_replay_prefix=self._clear_replay_prefix,
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
            surface_profile=self.surface_profile,
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
        """The complete unprofiled view, or empty until one was projected here."""

        return self.lifecycle.latest_full_view

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
        session without restarting EasyCrypt.  The donor's serialized
        preflight results are not live authority for this new manager
        incarnation, so adoption clears the private cache and re-runs the
        current-state preflight before the first worker handoff.
        """
        self._clear_goal_rejections()
        self.lifecycle.adopt_bootstrap(bootstrap)
        bootstrap["compiler_markdown"] = self._compile_current_markdown()

    def bootstrap(
        self,
        replay_prefix: list[str] | None = None,
        *,
        resume_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._clear_goal_rejections()
        record = self.lifecycle.bootstrap(
            replay_prefix=replay_prefix,
            resume_context=resume_context,
        )
        record["compiler_markdown"] = self._compile_current_markdown()
        return record

    def handle_agent_message(self, text: str) -> ManagedTurn:
        result = self._handle_agent_message_core(text)
        committed_tactics = tuple(self._current_committed_tactics())
        turn_evidence = compiler_turn_evidence(
            result,
            session_id=str(
                _session_dir_path(
                    self.repl.session_dir,
                    self.repl.project_root,
                ).resolve()
            ),
            committed_history=list(committed_tactics),
        )
        compiler_markdown = self._compile_current_markdown(
            turn_evidence
        )
        return replace(
            result,
            committed_tactics=committed_tactics,
            compiler_markdown=compiler_markdown,
        )

    def _compile_current_markdown(
        self,
        turn_evidence: Any | None = None,
    ) -> str:
        """Call the compiler facade and return its exact admitted Markdown."""

        if self.compiler_service is None:
            return ""
        try:
            result = self.compiler_service.compile_current_state(
                turn_evidence=turn_evidence
            )
        except Exception as exc:
            self._audit({
                "kind": "proof_state_compiler.failed",
                "node": self.node_id,
                "error_type": type(exc).__name__,
                "error": str(exc)[:600],
            })
            return ""
        self._audit({
            "kind": "proof_state_compiler.completed",
            "node": self.node_id,
            **result.telemetry,
        })
        if isinstance(result, CompilerServiceSkipped):
            return ""
        return result.admission.presentation.text

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
        repeat_gate = self._exact_rejected_submission_gate(parsed.intent)
        if repeat_gate is not None:
            return repeat_gate
        give_up_gate = self._give_up_gate(parsed.intent)
        if give_up_gate is not None:
            return give_up_gate
        preflight = preflight_intent(
            intent=parsed.intent,
            latest_view=self.latest_view,
            surface_profile=self.surface_profile,
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
        turn = self.turns.repl_call(
            parsed.intent,
            lambda: self.repl.handle_intent(parsed.intent),
        )
        return turn

    def _exact_rejected_submission_gate(
        self,
        intent: "AgentIntent",
    ) -> ManagedTurn | None:
        """Reject an exact same-goal retry before invoking EasyCrypt again."""

        snapshot_goal = str(getattr(self.latest_snapshot, "goal_hash", "") or "")
        if not snapshot_goal or snapshot_goal != self._rejection_goal_hash:
            return None
        match = next((
            item
            for item in self._current_goal_rejections
            if item.get("intent") == intent.intent
            and item.get("payload") == intent.payload
        ), None)
        if match is None:
            return None
        prompt = (
            "EasyCrypt already rejected this exact intent and payload without "
            "changing the current goal. Change the tactic or inspect current "
            "evidence before retrying."
        )
        self._audit({
            "kind": "proof_intent.exact_rejection_suppressed",
            "node": self.node_id,
            "intent": intent.intent,
            "payload": dict(intent.payload),
            "goal_hash": snapshot_goal,
        })
        return ManagedTurn(
            ok=False,
            workspace_view=dict(self.latest_view),
            snapshot=self.latest_snapshot,
            intent=intent,
            repair_prompt=prompt,
            manager_actions=[{
                "label": "exact_rejection_memory",
                "mutates_proof_state": False,
                "outcome_kind": str(match.get("outcome_kind") or "rejected"),
            }],
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
        lv = self.latest_view if isinstance(self.latest_view, dict) else {}
        ps = lv.get("proof_status") if isinstance(lv.get("proof_status"), dict) else {}
        status = str(ps.get("status") or "")
        remaining = ps.get("remaining_goals")
        # A give-up = finishing while the proof is genuinely OPEN. Closed /
        # Session-closing / complete / unknown statuses are NOT give-ups — never
        # gate a real or closing finish. Exact pending-qed handling belongs to
        # intent preflight.
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
            "tactic, undo a wrong step, or reconsider the current goal. To "
            "stop now, just submit `finish` again."
        )
        return self.turns.menu_turn(
            intent,
            {
                "intent": "finish",
                "kind": "give_up_gate",
                "control_menu": {
                    "title": "Finish while proof is open",
                    "notice": prompt,
                    "items": [
                        {
                            "label": "Finish anyway",
                            "description": "Stop this proof node with goals still open.",
                            "submit": {"intent": "finish", "payload": {}},
                        },
                    ],
                },
            },
            label="give_up_gate",
            audit_kind="give_up.deflected",
            ok=False,
            audit_extra={
                "attempts_in_window": n,
                "allow_after": _GIVE_UP_ALLOW_AFTER,
                "remaining_goals": remaining,
            },
        )

    def _current_committed_tactics(self) -> list[str]:
        return _read_committed_tactics(
            _session_dir_path(self.repl.session_dir, self.repl.project_root)
        )

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

    def _project(
        self,
        snapshot: ProofStateSnapshot,
        *,
        latest_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._record_goal_bound_rejection(snapshot, latest_observation)
        return self.lifecycle.project(
            snapshot,
            latest_observation=latest_observation,
        )

    def _record_goal_bound_rejection(
        self,
        snapshot: ProofStateSnapshot,
        observation: dict[str, Any] | None,
    ) -> None:
        """Remember unchanged rejections for exactly the current goal identity."""
        goal_hash = str(snapshot.goal_hash or "")
        result = observation if isinstance(observation, dict) else {}
        effect = str(result.get("proof_state_effect") or "")
        if effect == "changed":
            self._rejection_goal_hash = goal_hash
            self._current_goal_rejections = []
            return
        if goal_hash != self._rejection_goal_hash:
            self._rejection_goal_hash = goal_hash
            self._current_goal_rejections = []
        if (
            effect != "unchanged"
            or str(result.get("outcome_kind") or "")
            not in {"rejected", "no_progress"}
        ):
            return
        intent = str(result.get("intent") or "").strip()
        payload = result.get("payload")
        if not intent or not isinstance(payload, dict) or not payload:
            return
        item = {
            "intent": intent,
            "payload": dict(payload),
            "outcome_kind": str(result.get("outcome_kind") or ""),
        }
        if not any(
            existing.get("intent") == item["intent"]
            and existing.get("payload") == item["payload"]
            for existing in self._current_goal_rejections
        ):
            self._current_goal_rejections.append(item)

    def _clear_goal_rejections(self) -> None:
        self._rejection_goal_hash = ""
        self._current_goal_rejections = []

    def _audit(self, record: dict[str, Any]) -> None:
        self.events.run_dir = self.run_dir
        self.events.audit(record)


def _confirmation_id(node_id: str, state_version: int, history_hash: str) -> str:
    seed = f"{node_id}:{state_version}:{history_hash}:{time.time_ns()}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
