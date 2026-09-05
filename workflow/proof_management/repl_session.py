"""Manager-owned EasyCrypt REPL/session backend service."""
from __future__ import annotations

import difflib
import math
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.easycrypt import committed_history
from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.session.session_state import read_target_lemma_metadata

from .backend_actions import (
    AuthoritativeViewResolution,
    backend_action_record,
    capture_authoritative_view_invocation,
    capture_tactic_execution_invocation,
    capture_tactic_preflight_invocation,
    resolve_authoritative_view_invocation,
    timeout_backend_action_record,
)
from workflow.proof_management.managed_turn_outcome import classify_manager_action_outcome
from .protocol_repair import AgentIntent
from .types import ProofStateSnapshot

if TYPE_CHECKING:
    from .compiler_surface import CompilerSurface


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Aggregate wall-clock budget (seconds) for the per-tactic replay loop of a
# restart+replay-all restore (rewind / restore_committed_tactics / resume). Each
# per-tactic backend call already has its own 180s cap, but a long kept prefix
# has NO aggregate cap, so a deep rewind can hold the bridge lock for minutes
# (the observed false-wedge: ~236-248s while remaining_goals=2). This bounds the
# worst case and surfaces progress instead of replaying silently. 0/negative =>
# unbounded.
#
# The budget SCALES with the prefix length: max(600s floor, 15s x kept tactics).
# A flat 600s cap falsely aborted a legitimate deep replay (observed 2026-06-11:
# a known-good 123-tactic prefix with heavy smt calls — already replayed once —
# blew the flat budget during a Layer-3 respawn, >4.9s/tactic average). 15s per
# tactic comfortably covers heavy smt steps while still capping a pathological
# wedge far below per-tactic-cap x count. An explicit SHANNON_REPLAY_AGG_BUDGET
# wins verbatim (no scaling); SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC overrides the
# per-tactic rate.
def replay_aggregate_budget_seconds(prefix_len: int = 0) -> float:
    """Return the one aggregate restart/replay timing policy.

    Proof-tool timing derives its outer budgets from this public owner; callers
    must not repeat the environment/default interpretation.
    """

    import os

    raw = os.environ.get("SHANNON_REPLAY_AGG_BUDGET", "").strip()
    if raw:
        try:
            return float(raw)  # <= 0 means "no aggregate cap"
        except ValueError:
            pass  # garbage override -> fall through to the scaled default
    per_tactic = 15.0
    raw_per = os.environ.get("SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC", "").strip()
    if raw_per:
        try:
            per_tactic = float(raw_per)
        except ValueError:
            per_tactic = 15.0
    return max(600.0, per_tactic * max(0, int(prefix_len)))


class ReplBackendTimeout(RuntimeError):
    """Raised when a manager-owned EasyCrypt backend action times out."""

    def __init__(self, action: dict[str, Any]) -> None:
        self.action = dict(action)
        label = str(action.get("label") or "backend_action")
        timeout = action.get("timeout_seconds")
        super().__init__(f"manager backend action {label!r} timed out after {timeout}s")


class ReplBackendError(RuntimeError):
    """Raised when a manager-owned EasyCrypt backend action exits nonzero."""

    def __init__(self, action: dict[str, Any]) -> None:
        self.action = dict(action)
        label = str(action.get("label") or "backend_action")
        exit_code = action.get("exit_code")
        observation = action.get("agent_observation")
        error_summary = ""
        if isinstance(observation, dict):
            error_summary = str(observation.get("error_summary") or "")
        detail = f": {error_summary}" if error_summary else ""
        super().__init__(
            f"manager backend action {label!r} exited with code {exit_code}{detail}"
        )


class ReplSessionManager:
    """Owns all EasyCrypt backend/session lifecycle for one proof node."""

    def __init__(
        self,
        *,
        file_path: str,
        lemma_name: str,
        include_dir: str,
        session_tag: str,
        node_id: str,
        project_root: Path = PROJECT_ROOT,
    ) -> None:
        self.file_path = file_path
        self.lemma_name = lemma_name
        self.include_dir = include_dir
        self.session_tag = session_tag
        self.node_id = node_id
        self.project_root = Path(project_root)
        self.session_dir = f".ec_session_{session_tag}"
        self._lock = threading.Lock()
        self._turn_deadline = threading.local()
        self._state_version = 0
        self._session_epoch = 0
        self._compiler_surface: CompilerSurface | None = None

    @contextmanager
    def turn_deadline(self, deadline: float | None) -> Iterator[None]:
        """Bind one absolute proof-tool deadline to every backend call.

        The manager wraps the complete admission/execution/compile turn in this
        scope.  Compiler runtime calls therefore inherit the same budget even
        though their public APIs retain bounded per-operation timeouts.  The
        binding is thread-local so unrelated read-only callers cannot borrow or
        overwrite another invocation's budget.
        """

        normalized: float | None
        if deadline is None:
            normalized = None
        else:
            normalized = float(deadline)
            if not math.isfinite(normalized) or normalized <= 0:
                raise ValueError(
                    "proof-tool turn deadline must be finite and positive"
                )
        missing = object()
        previous = getattr(self._turn_deadline, "value", missing)
        if previous is not missing and previous is not None:
            normalized = (
                float(previous)
                if normalized is None
                else min(float(previous), normalized)
            )
        self._turn_deadline.value = normalized
        try:
            yield
        finally:
            if previous is missing:
                del self._turn_deadline.value
            else:
                self._turn_deadline.value = previous

    @property
    def state_version(self) -> int:
        return self._state_version

    def adopt_versions(self, state_version: int, session_epoch: int) -> None:
        """Adopt version counters recovered from a bootstrap/capsule snapshot
        (never lowers either counter). The lifecycle service calls this
        instead of poking the private fields."""
        self._state_version = max(self._state_version, int(state_version))
        self._session_epoch = max(self._session_epoch, int(session_epoch))

    @property
    def session_epoch(self) -> int:
        return self._session_epoch

    def close(self) -> bool:
        """Release any live daemon EC session for this manager-owned session.

        The session CLI subprocesses are short-lived, but the daemon fast-path
        keeps EasyCrypt/why3 subprocesses alive under a per-session id. Replay
        and audit tools create many short-lived managers, so they need an
        explicit lifecycle hook instead of waiting for daemon idle cleanup.
        Best-effort; returns True iff a close RPC succeeded."""
        with self._lock:
            try:
                from .daemon_attach import close_daemon_session

                return close_daemon_session(self.session_dir, self.project_root)
            except Exception:
                return False

    def start(
        self,
        replay_prefix: list[str] | None = None,
        *,
        replay_transactions: list[str] | None = None,
        daemon_attach: dict[str, Any] | None = None,
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        """Start the node's EC session.

        ``daemon_attach`` (SHANNON_EC_DAEMON=1 only) requests worker-death
        attach: ``{"donor_session_dir": ..., "expected_goal_hash": ...,
        "goal_identity_required": true|false}``
        names a dead node's session dir whose EC daemon session may still
        be live. On a verified attach the committed prefix is adopted
        in-place (zero replay); on ANY attach failure this falls back to the
        canonical restart+replay path transparently."""
        with self._lock:
            attach_actions: list[dict[str, Any]] = []
            if daemon_attach:
                attached = self._attach_locked(
                    daemon_attach,
                    replay_prefix=replay_prefix,
                    actions=attach_actions,
                )
                if attached is not None:
                    return attached
            return self._start_locked(
                replay_prefix=replay_prefix,
                replay_transactions=replay_transactions,
                preamble_actions=attach_actions,
            )

    def committed_history(self) -> list[str]:
        """The session's ACTUAL committed history as complete EC commands.

        This is the authority for what the session contains — a requested
        replay prefix is only a request: a replayed step that EasyCrypt
        accepts but the no-progress detector auto-reverts never reaches
        history.ec, so callers recording "what was replayed" must read this
        instead of echoing the request (step4_1 r2 respawn divergence,
        2026-06-09).
        """
        return committed_history.read_committed_tactics(
            session_dir_path(self.session_dir, self.project_root)
        )

    def fresh_restart(self) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        with self._lock:
            return self._start_locked(
                label="fresh_restart",
                force_restart=True,
            )

    def rewind_before_tactic(
        self,
        tactic_index: int,
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        with self._lock:
            tactics = committed_history.read_committed_tactics(
                session_dir_path(self.session_dir, self.project_root)
            )
            keep_count = max(0, min(len(tactics), int(tactic_index) - 1))
            return self._start_locked(
                replay_prefix=tactics[:keep_count],
                label="undo_to_checkpoint",
                force_restart=True,
            )

    def restore_committed_tactics(
        self,
        tactics: list[str],
        *,
        label: str = "restore_pre_rewind",
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        with self._lock:
            return self._start_locked(
                replay_prefix=list(tactics),
                label=label,
                force_restart=True,
            )

    def restart_with_edited_prefix(
        self,
        edited_tactics: list[str],
        *,
        label: str = "restart_replay_edit",
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        """Restart from the lemma and replay an EDITED tactic prefix, STOPPING at
        the first tactic that no longer applies.

        For the agent's "fix an earlier step and replay the rest" recovery: the
        caller hands the committed history with one step amended. Unlike
        ``restore_committed_tactics`` (skip-and-continue, for replaying a known-good
        prefix on fork/respawn), this stops at the first step the edit invalidated
        and leaves the session there, so the agent continues from the divergence
        point instead of later tactics landing in a now-wrong state.
        """
        with self._lock:
            return self._start_locked(
                replay_prefix=list(edited_tactics),
                label=label,
                force_restart=True,
                stop_at_first_drop=True,
            )

    def _attach_locked(
        self,
        daemon_attach: dict[str, Any],
        *,
        replay_prefix: list[str] | None,
        actions: list[dict[str, Any]],
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]] | None:
        """Worker-death attach (SHANNON_EC_DAEMON=1): adopt a dead node's
        still-live daemon EC session instead of replaying the prefix.

        Returns the (snapshot, actions) pair on success, or ``None`` after
        recording a non-mutating fallback action so the caller proceeds
        with the canonical restart+replay restore. Caller holds the lock."""
        from .daemon_attach import (
            attempt_daemon_attach,
            daemon_session_attach_enabled,
        )

        if not daemon_session_attach_enabled():
            return None
        donor = str(daemon_attach.get("donor_session_dir") or "").strip()
        if not donor:
            return None
        start_time = time.perf_counter()
        goal_identity_required = daemon_attach.get("goal_identity_required")
        if type(goal_identity_required) is not bool:
            result = {
                "ok": False,
                "reason": "goal_identity_required_invalid",
            }
        else:
            result = attempt_daemon_attach(
                project_root=self.project_root,
                donor_session_dir=donor,
                target_session_dir=self.session_dir,
                file_path=self.file_path,
                lemma_name=self.lemma_name,
                replay_prefix=list(replay_prefix or []),
                expected_goal_hash=str(
                    daemon_attach.get("expected_goal_hash") or ""
                ),
                goal_identity_required=goal_identity_required,
            )
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if not result.get("ok"):
            actions.append({
                "label": "daemon_attach_fallback",
                "argv": ["<daemon session attach>"],
                "exit_code": 0,
                "duration_ms": duration_ms,
                "mutates_proof_state": False,
                "daemon_attach": dict(result),
                "agent_observation": {
                    "label": "daemon_attach_fallback",
                    "result": (
                        "No live daemon EC session could be adopted "
                        f"({result.get('reason')}); restoring via the canonical "
                        "restart+replay path."
                    ),
                },
            })
            return None
        self._session_epoch += 1
        actions.append({
            "label": "daemon_attach",
            "argv": ["<daemon session attach>"],
            "exit_code": 0,
            "duration_ms": duration_ms,
            "mutates_proof_state": True,
            "daemon_attach": dict(result),
            "replay_steps_avoided": int(result.get("replay_avoided") or 0),
            "agent_observation": {
                "label": "daemon_attach",
                "result": (
                    "Adopted the live EC session from "
                    f"{result.get('donor')} — "
                    f"{result.get('replay_avoided')} committed tactics "
                    "restored without replay."
                ),
            },
        })
        snapshot = self._snapshot_from_managed_goal_view(actions=actions)
        return snapshot, actions

    def _start_locked(
        self,
        replay_prefix: list[str] | None = None,
        *,
        replay_transactions: list[str] | None = None,
        label: str = "start",
        force_restart: bool = False,
        preamble_actions: list[dict[str, Any]] | None = None,
        stop_at_first_drop: bool = False,
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        actions: list[dict[str, Any]] = list(preamble_actions or [])
        self._session_epoch += 1
        start_args = ["-start"]
        if force_restart:
            start_args.append("--force-restart")
        start_args.extend(["-f", self.file_path])
        for inc in self._include_dirs():
            start_args.extend(["-I", inc])
        start_args.extend(["-lemma", self.lemma_name])
        self._run_backend(label, start_args, actions=actions, timeout=180)

        replay_prefix = [str(t).strip() for t in (replay_prefix or []) if str(t).strip()]
        execution_prefix = list(replay_prefix)
        if replay_transactions is not None:
            execution_prefix = [
                str(t).strip() for t in replay_transactions if str(t).strip()
            ]
            flattened = committed_history.flatten_committed_transactions(
                execution_prefix
            )
            if flattened != replay_prefix:
                raise ValueError(
                    "replay transactions do not flatten to the requested "
                    "committed prefix"
                )
        total = len(execution_prefix)
        # The public prefix count remains the semantic command count even when
        # fewer atomic manager transactions are issued to preserve bullets.
        agg_budget = replay_aggregate_budget_seconds(len(replay_prefix))
        replay_started = time.perf_counter()
        for index, tactic in enumerate(execution_prefix, start=1):
            # Aggregate budget check BEFORE issuing the next backend call: a long
            # kept prefix must not hold the bridge lock indefinitely. Each step
            # records its own action, so `actions` already carries replay
            # progress; on budget exhaustion we append a synthetic aggregate
            # timeout action (with how-far-we-got) and raise so the manager
            # surfaces a bounded failure instead of a silent multi-minute wedge.
            if agg_budget > 0:
                elapsed = time.perf_counter() - replay_started
                if elapsed >= agg_budget:
                    aggregate_action = {
                        "label": "replay_prefix_aggregate_budget",
                        "argv": ["<aggregate replay budget>"],
                        "exit_code": None,
                        "timed_out": True,
                        "timeout_seconds": agg_budget,
                        "duration_ms": int(elapsed * 1000),
                        "mutates_proof_state": True,
                        "replay_steps_completed": index - 1,
                        "replay_steps_total": total,
                        "agent_observation": {
                            "label": "replay_prefix_aggregate_budget",
                            "error_summary": (
                                f"restart+replay restore exceeded aggregate "
                                f"budget of {agg_budget:g}s after "
                                f"{index - 1}/{total} kept tactics; aborting "
                                "before replaying the remainder to avoid "
                                "holding the manager bridge lock for minutes."
                            ),
                        },
                    }
                    actions.append(aggregate_action)
                    raise ReplBackendTimeout(aggregate_action)
            self._run_backend(
                f"replay_prefix_step_{index}",
                ["-tactic-exec", "commit", "-c", tactic],
                actions=actions,
                timeout=180,
            )
            if stop_at_first_drop:
                # edit-and-replay: stop at the FIRST replayed tactic that no longer
                # commits (the edited prefix changed the goal, so this step no longer
                # applies). Leave the session at the last tactic that DID apply, so the
                # agent resumes from the divergence point instead of replaying later
                # tactics into a now-wrong state. The canonical commit action
                # exits 0 for both kept and auto-reverted steps, so a
                # dropped step is invisible to _run_backend — detect it by the
                # committed history failing to grow to `index`. (Normal fork/respawn
                # replay keeps the skip-and-continue safety net below; this is opt-in.)
                kept_now = committed_history.read_committed_tactics(
                    session_dir_path(self.session_dir, self.project_root)
                )
                if len(kept_now) < index:
                    actions.append({
                        "label": "replay_prefix_stopped_at_divergence",
                        "argv": ["<replay stop-at-first-drop>"],
                        "exit_code": 0,
                        "mutates_proof_state": False,
                        "replay_stopped_at_step": index,
                        "replay_kept_count": len(kept_now),
                        "replay_requested_count": total,
                        "stopped_tactic": tactic,
                        "agent_observation": {
                            "label": "replay_prefix_stopped_at_divergence",
                            "result": (
                                f"Replay stopped at step {index}: after the edit, "
                                f"`{tactic}` no longer applies. Kept the "
                                f"{len(kept_now)} tactic(s) that still hold; the "
                                "session is at that point — continue from here."
                            ),
                        },
                    })
                    break

        if replay_prefix:
            # A replay step can be ACCEPTED by EasyCrypt yet auto-reverted by
            # the no-progress detector (exit 0 either way), so the loop above
            # cannot tell a kept step from a dropped one. Compare the
            # session's actual history against the request and surface any
            # divergence as a dedicated action — without this, downstream
            # records that echo the request misnumber every later step
            # (step4_1 r2 respawn, 2026-06-09: one dropped hypothesis-rewrite
            # shifted all live step numbers by +1 in replay audits).
            committed = committed_history.read_committed_tactics(
                session_dir_path(self.session_dir, self.project_root)
            )
            if committed != replay_prefix:
                divergence = replay_prefix_divergence(replay_prefix, committed)
                actions.append({
                    "label": "replay_prefix_divergence",
                    "argv": ["<post-replay history comparison>"],
                    "exit_code": 0,
                    "mutates_proof_state": False,
                    "replay_requested_count": len(replay_prefix),
                    "replay_committed_count": len(committed),
                    "replay_divergence": divergence,
                    "agent_observation": {
                        "label": "replay_prefix_divergence",
                        "result": (
                            f"Prefix replay kept {len(committed)} of "
                            f"{len(replay_prefix)} requested tactics; the "
                            "session's history.ec is the authority for the "
                            "node's starting state. Dropped steps were "
                            "accepted by EasyCrypt but auto-reverted as "
                            "no-progress during replay."
                        ),
                    },
                })

        snapshot = self._snapshot_from_managed_goal_view(actions=actions)
        return snapshot, actions

    def handle_intent(
        self,
        intent: AgentIntent,
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        with self._lock:
            actions: list[dict[str, Any]] = []
            if intent.intent == "commit_tactic":
                tactic = intent.payload["tactic"].strip()
                self._run_backend(
                    "commit_tactic",
                    ["-tactic-exec", "commit", "-c", tactic],
                    actions=actions,
                    timeout=180,
                )
            elif intent.intent == "undo_last_step":
                self._run_backend(
                    "undo_last_step",
                    ["-tactic-exec", "undo"],
                    actions=actions,
                    timeout=120,
                )
            elif intent.intent == "fresh_restart":
                return self._start_locked(
                    label="fresh_restart",
                    force_restart=True,
                )
            else:
                raise ValueError(
                    f"intent {intent.intent!r} is not a REPL session operation"
                )
            snapshot = self._snapshot_from_managed_goal_view(actions=actions)
            return snapshot, actions

    # ------------------------------------------------------------------
    # Proof-state-compiler RPC surface.  The implementations live in
    # compiler_surface.CompilerSurface; these one-line delegates keep the
    # manager satisfying the CompilerRuntime protocol and leave every
    # existing call site unchanged.
    # ------------------------------------------------------------------
    @property
    def compiler(self) -> "CompilerSurface":
        """The read-only proof-state-compiler RPC surface for this session."""
        if self._compiler_surface is None:
            from .compiler_surface import CompilerSurface

            self._compiler_surface = CompilerSurface(self)
        return self._compiler_surface

    def read_only_tactic_preflight(
        self,
        tactic: str,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        return self.compiler.read_only_tactic_preflight(tactic, timeout=timeout)

    def certify_exact_tactic(
        self,
        tactic: str,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        return self.compiler.certify_exact_tactic(tactic, timeout=timeout)

    def read_compiler_input_v2(self, *, timeout: int = 30) -> dict[str, Any]:
        return self.compiler.read_compiler_input_v2(timeout=timeout)

    def load_compiler_resources_v2(
        self,
        *,
        request_id: str,
        source_snapshot_id: str,
        source_event_id: str,
        expected_state: dict[str, Any],
        load_requests: tuple[Any, ...],
        timeout: int = 30,
    ) -> dict[str, Any]:
        return self.compiler.load_compiler_resources_v2(
            request_id=request_id,
            source_snapshot_id=source_snapshot_id,
            source_event_id=source_event_id,
            expected_state=expected_state,
            load_requests=load_requests,
            timeout=timeout,
        )

    def execute_native_semantic_batch(
        self,
        *,
        batch_id: str,
        requests: tuple[dict[str, object], ...],
        timeout: int = 30,
    ) -> dict[str, Any]:
        return self.compiler.execute_native_semantic_batch(
            batch_id=batch_id,
            requests=requests,
            timeout=timeout,
        )

    def project_native_state(
        self,
        *,
        request_id: str,
        max_nodes: int = 4096,
        max_depth: int = 128,
        timeout: int = 30,
    ) -> dict[str, Any]:
        return self.compiler.project_native_state(
            request_id=request_id,
            max_nodes=max_nodes,
            max_depth=max_depth,
            timeout=timeout,
        )


    def _snapshot_from_managed_goal_view(
        self,
        *,
        actions: list[dict[str, Any]],
    ) -> ProofStateSnapshot:
        label = "managed_goal_view"
        args = ["-managed-goal-view"]
        payload = self._run_backend(
            label,
            args,
            actions=actions,
            timeout=60,
        )
        # The snapshot is decoded only from the current invocation's strictly
        # event-bound workspace artifact. Stdout is human/debug display and can
        # neither forge nor replace the manager's semantic state.
        if not isinstance(payload, dict):
            self._raise_snapshot_contract_error(
                actions,
                f"{label} backend did not return its event-bound workspace artifact",
            )
        if payload.get("ok") is not True:
            self._raise_snapshot_contract_error(
                actions,
                f"{label} workspace artifact must report explicit ok=true",
            )
        metadata_error = self._managed_session_metadata_error()
        if metadata_error:
            self._raise_snapshot_contract_error(actions, metadata_error)
        workspace = payload
        self._state_version += 1
        proof_status = (
            workspace.get("proof_status")
            if isinstance(workspace.get("proof_status"), dict)
            else {}
        )
        goal_identity_required = proof_status.get("goal_identity_required")
        if type(goal_identity_required) is not bool:
            self._raise_snapshot_contract_error(
                actions,
                "workspace proof status lacks an explicit goal identity class",
            )
        goal_hash = _goal_hash(workspace) if goal_identity_required else ""
        if goal_identity_required and not goal_hash:
            self._raise_snapshot_contract_error(
                actions,
                "open workspace has no canonical goal identity",
            )
        workspace_artifact = _workspace_artifact(payload)
        return ProofStateSnapshot(
            node_id=self.node_id,
            session_tag=self.session_tag,
            session_dir=self.session_dir,
            session_epoch=self._session_epoch,
            state_version=self._state_version,
            goal_hash=goal_hash,
            goal_identity_required=goal_identity_required,
            workspace_view_artifact=workspace_artifact,
            execution_refs={
                "manager_action_count": len(actions),
                "manager_actions": list(actions),
            },
            raw_workspace_view=workspace,
        )

    def _managed_session_metadata_error(self) -> str:
        """Return a fail-closed target identity error for manager snapshots."""

        session_path = session_dir_path(self.session_dir, self.project_root)
        target = read_target_lemma_metadata(session_path)
        if target.status != "target_lemma" or target.lemma != self.lemma_name:
            return (
                "managed session metadata does not identify the manager's "
                f"target lemma {self.lemma_name!r}"
            )
        actual_source = Path(target.source_file)
        if not actual_source.is_absolute():
            actual_source = self.project_root / actual_source
        expected_source = Path(self.file_path)
        if not expected_source.is_absolute():
            expected_source = self.project_root / expected_source
        if actual_source.resolve() != expected_source.resolve():
            return "managed session metadata file does not match the manager target"
        return ""

    @staticmethod
    def _raise_snapshot_contract_error(
        actions: list[dict[str, Any]],
        error: str,
    ) -> None:
        action_index = next(
            (
                index
                for index in range(len(actions) - 1, -1, -1)
                if actions[index].get("label") == "managed_goal_view"
            ),
            None,
        )
        action = dict(actions[action_index]) if action_index is not None else {
            "label": "managed_goal_view",
            "exit_code": 0,
            "mutates_proof_state": False,
        }
        action.update(classify_manager_action_outcome(
            status="backend_contract_error",
            ok=False,
            read_only=True,
            mutates_proof_state=False,
            state_changed=False,
        ).to_dict())
        action["contract_error"] = error
        action["agent_observation"] = {
            "manager_action": "managed_goal_view",
            "result": (
                "The backend did not produce a trustworthy managed workspace view."
            ),
            "effect": "The read-only request did not change the proof state.",
            "proof_state": "unchanged",
            "contract_error": error,
        }
        if action_index is not None:
            actions[action_index] = action
        else:
            actions.append(action)
        raise ReplBackendError(action)

    def _run_backend(
        self,
        label: str,
        args: list[str],
        *,
        actions: list[dict[str, Any]],
        timeout: float,
        authoritative_resolutions: list[AuthoritativeViewResolution] | None = None,
    ) -> str | dict[str, Any]:
        retired_tactic_flags = {"-next", "-prev", "-chain"}
        if retired_tactic_flags.intersection(args):
            raise ValueError(
                "ReplSessionManager accepts tactic mutations only through "
                "-tactic-exec commit|commit_chain|undo"
            )
        cmd = [
            sys.executable,
            "core/easycrypt/session_cli.py",
            "-d",
            self.session_dir,
            *args,
        ]
        deadline = getattr(self._turn_deadline, "value", None)
        if deadline is not None:
            remaining = float(deadline) - time.time()
            if remaining <= 0:
                exc = subprocess.TimeoutExpired(cmd=cmd, timeout=0.0)
                action = timeout_backend_action_record(
                    label,
                    cmd,
                    exc,
                    0.0,
                    0,
                )
                action["absolute_deadline"] = float(deadline)
                action["deadline_expired_before_start"] = True
                actions.append(action)
                raise ReplBackendTimeout(action)
            timeout = min(float(timeout), remaining)
        resolved_session_dir = session_dir_path(self.session_dir, self.project_root)
        tactic_preflight_boundary = capture_tactic_preflight_invocation(
            resolved_session_dir,
            cmd,
        )
        tactic_execution_boundary = capture_tactic_execution_invocation(
            resolved_session_dir,
            cmd,
        )
        authoritative_view_boundary = capture_authoritative_view_invocation(
            resolved_session_dir,
            cmd,
        )
        start_time = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                env=self._env(),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            action = timeout_backend_action_record(
                label, cmd, exc, timeout, duration_ms,
            )
            actions.append(action)
            raise ReplBackendTimeout(action) from exc
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        authoritative_view_resolution = resolve_authoritative_view_invocation(
            authoritative_view_boundary,
            exit_code=result.returncode,
            required=authoritative_view_boundary is not None,
        )
        if (
            authoritative_resolutions is not None
            and authoritative_view_resolution.required
        ):
            authoritative_resolutions.append(authoritative_view_resolution)
        action = backend_action_record(
            label, cmd, result, duration_ms,
            tactic_preflight_boundary=tactic_preflight_boundary,
            tactic_execution_boundary=tactic_execution_boundary,
            authoritative_view_boundary=authoritative_view_boundary,
            authoritative_view_resolution=authoritative_view_resolution,
        )
        actions.append(action)
        if (
            result.returncode != 0
            or action.get("outcome_kind") == "backend_error"
            or bool(action.get("contract_error"))
        ):
            raise ReplBackendError(action)
        if authoritative_view_resolution.required:
            return dict(authoritative_view_resolution.payload or {})
        return result.stdout or ""

    def _env(self) -> dict[str, str]:
        env = get_ec_env()
        env["EC_SESSION_DIR"] = self.session_dir
        return env

    def include_dirs(self) -> list[str]:
        return self._include_dirs()

    def _include_dirs(self) -> list[str]:
        file_dir = str(Path(self.file_path).parent or ".")
        dirs = [file_dir]
        if self.include_dir and self.include_dir != file_dir:
            dirs.append(self.include_dir)
        return dirs


def session_dir_path(session_dir: str | Path, project_root: Path) -> Path:
    path = Path(session_dir)
    return path if path.is_absolute() else Path(project_root) / path


def replay_prefix_divergence(
    requested: list[str],
    committed: list[str],
) -> dict[str, Any]:
    """Describe how a session's actual history differs from a requested prefix.

    Returns ``{"dropped": [{"index", "tactic"}...], "added": [...]}`` where
    ``index`` is the 1-based position in the respective sequence. ``dropped``
    are requested steps absent from the session (e.g. auto-reverted during
    replay); ``added`` are session steps that were never requested.
    """
    matcher = difflib.SequenceMatcher(a=requested, b=committed, autojunk=False)
    dropped: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    for op, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if op in ("delete", "replace"):
            dropped.extend(
                {"index": i + 1, "tactic": requested[i]}
                for i in range(a_start, a_end)
            )
        if op in ("insert", "replace"):
            added.extend(
                {"index": i + 1, "tactic": committed[i]}
                for i in range(b_start, b_end)
            )
    return {"dropped": dropped, "added": added}


def _goal_hash(workspace: dict[str, Any]) -> str:
    proof_status = (
        workspace.get("proof_status")
        if isinstance(workspace.get("proof_status"), dict)
        else {}
    )
    value = proof_status.get("goal_hash")
    return value if isinstance(value, str) else ""


def _workspace_artifact(payload: dict[str, Any]) -> str:
    artifacts = (
        payload.get("artifacts")
        if isinstance(payload.get("artifacts"), dict)
        else {}
    )
    return str(artifacts.get("prover_workspace_view") or "")
