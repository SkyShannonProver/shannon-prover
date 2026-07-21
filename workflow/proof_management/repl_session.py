"""Manager-owned EasyCrypt REPL/session backend service."""
from __future__ import annotations

import difflib
import hashlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from core.easycrypt.committed_history import (
    read_committed_tactics as _read_committed_tactics,
)
from core.easycrypt.ec_env import get_ec_env
from workflow.context_intents import (
    context_payload_for_intent,
    is_context_topic_intent,
    normalize_context_topic,
)

from .backend_actions import (
    command_summary,
    timeout_command_summary,
    workspace_payload_from_stdout,
    workspace_view_from_payload,
)
# Single source of truth for the committed-history digest + checkpoint-id
# coordinate system. Re-exported here so the long-standing
# `from .repl_session import history_hash` consumers (checkpoint_store /
# memory_store via DI, recovery_handlers, route_health) stay backed by one
# implementation instead of a copy that can silently drift (audit §6.3/§8 #7).
from .checkpoint_surface import history_hash
from .protocol_repair import AgentIntent
from .types import ProofStateSnapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Aggregate wall-clock budget (seconds) for the per-tactic replay loop of a
# restart+replay-all restore (rewind / restore_committed_tactics / resume). Each
# per-tactic backend call already has its own 180s cap, but a long kept prefix
# has NO aggregate cap, so a deep rewind can hold the bridge lock for minutes
# (the observed false-wedge: ~236-248s while remaining_goals=2). This bounds the
# worst case and surfaces progress instead of replaying silently. 0/negative =>
# unbounded (legacy behaviour).
#
# The budget SCALES with the prefix length: max(600s floor, 15s x kept tactics).
# A flat 600s cap falsely aborted a legitimate deep replay (observed 2026-06-11:
# a known-good 123-tactic prefix with heavy smt calls — already replayed once —
# blew the flat budget during a Layer-3 respawn, >4.9s/tactic average). 15s per
# tactic comfortably covers heavy smt steps while still capping a pathological
# wedge far below per-tactic-cap x count. An explicit SHANNON_REPLAY_AGG_BUDGET
# wins verbatim (no scaling); SHANNON_REPLAY_AGG_BUDGET_PER_TACTIC overrides the
# per-tactic rate.
def _replay_aggregate_budget_seconds(prefix_len: int = 0) -> float:
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
        self._state_version = 0
        self._session_epoch = 0

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
        daemon_attach: dict[str, Any] | None = None,
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        """Start the node's EC session.

        ``daemon_attach`` (SHANNON_EC_DAEMON=1 only) requests worker-death
        attach: ``{"donor_session_dir": ..., "expected_goal_hash": ...}``
        names a dead node's session dir whose EC daemon session may still
        be live. On a verified attach the committed prefix is adopted
        in-place (zero replay); on ANY attach failure this falls back to
        the legacy restart+replay path transparently. With the flag off
        (or ``daemon_attach=None``) behavior is exactly legacy."""
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
                preamble_actions=attach_actions,
            )

    def committed_history(self) -> list[str]:
        """The session's ACTUAL committed history (history.ec lines, stripped).

        This is the authority for what the session contains — a requested
        replay prefix is only a request: a replayed step that EasyCrypt
        accepts but the no-progress detector auto-reverts never reaches
        history.ec, so callers recording "what was replayed" must read this
        instead of echoing the request (step4_1 r2 respawn divergence,
        2026-06-09).
        """
        return read_committed_tactics(
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
            tactics = read_committed_tactics(
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

    def verify_tactic_chunk_from_prefix(
        self,
        prefix_tactics: list[str],
        chunk_tactics: list[str],
    ) -> dict[str, Any]:
        scratch_base = Path(self.project_root) / "tmp" / "replay_chunks"
        scratch_base.mkdir(parents=True, exist_ok=True)
        scratch_dir = Path(
            tempfile.mkdtemp(
                prefix="shannon_replay_chunk_",
                dir=str(scratch_base),
            )
        )
        scratch = ReplSessionManager(
            file_path=self.file_path,
            lemma_name=self.lemma_name,
            include_dir=self.include_dir,
            session_tag=f"{self.session_tag}_replay_{time.time_ns()}",
            node_id=f"{self.node_id}.replay",
            project_root=self.project_root,
        )
        scratch.session_dir = str(scratch_dir)
        actions: list[dict[str, Any]] = []
        accepted: list[str] = []
        try:
            snapshot, start_actions = scratch.start(replay_prefix=prefix_tactics)
            actions.extend(start_actions)
            for tactic in chunk_tactics:
                try:
                    snapshot, step_actions = scratch.handle_intent(
                        AgentIntent(
                            intent="commit_tactic",
                            payload={"tactic": tactic},
                        )
                    )
                    actions.extend(step_actions)
                    accepted.append(tactic)
                except ReplBackendTimeout as exc:
                    actions.append(exc.action)
                    return {
                        "ok": False,
                        "accepted_count": len(accepted),
                        "accepted_tactics": list(accepted),
                        "failed_tactic": tactic,
                        "failure_kind": "timeout",
                        "failure_action": exc.action,
                        "actions": actions,
                    }
                except ReplBackendError as exc:
                    actions.append(exc.action)
                    return {
                        "ok": False,
                        "accepted_count": len(accepted),
                        "accepted_tactics": list(accepted),
                        "failed_tactic": tactic,
                        "failure_kind": "backend_error",
                        "failure_action": exc.action,
                        "actions": actions,
                    }
            return {
                "ok": True,
                "accepted_count": len(accepted),
                "accepted_tactics": list(accepted),
                "actions": actions,
                "post_snapshot": snapshot.to_dict(),
            }
        except Exception as exc:  # scratch replay failures are evidence, not fatal.
            return {
                "ok": False,
                "accepted_count": len(accepted),
                "accepted_tactics": list(accepted),
                "failure_kind": "setup_error",
                "error": str(exc)[-1200:],
                "actions": actions,
            }
        finally:
            try:
                scratch.close()
            finally:
                shutil.rmtree(scratch_dir, ignore_errors=True)

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
        with the legacy restart+replay restore. Caller holds the lock."""
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
        result = attempt_daemon_attach(
            project_root=self.project_root,
            donor_session_dir=donor,
            target_session_dir=self.session_dir,
            file_path=self.file_path,
            lemma_name=self.lemma_name,
            replay_prefix=list(replay_prefix or []),
            expected_goal_hash=str(daemon_attach.get("expected_goal_hash") or ""),
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
                        f"({result.get('reason')}); restoring via the legacy "
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
        snapshot = self._snapshot_from_agent_view(actions=actions)
        return snapshot, actions

    def _start_locked(
        self,
        replay_prefix: list[str] | None = None,
        *,
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
        total = len(replay_prefix)
        agg_budget = _replay_aggregate_budget_seconds(total)
        replay_started = time.perf_counter()
        for index, tactic in enumerate(replay_prefix, start=1):
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
                ["-next", "-c", tactic],
                actions=actions,
                timeout=180,
            )
            if stop_at_first_drop:
                # edit-and-replay: stop at the FIRST replayed tactic that no longer
                # commits (the edited prefix changed the goal, so this step no longer
                # applies). Leave the session at the last tactic that DID apply, so the
                # agent resumes from the divergence point instead of replaying later
                # tactics into a now-wrong state. handle_next always exits 0, so a
                # dropped step is invisible to _run_backend — detect it by the
                # committed history failing to grow to `index`. (Normal fork/respawn
                # replay keeps the skip-and-continue safety net below; this is opt-in.)
                kept_now = read_committed_tactics(
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
            committed = read_committed_tactics(
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

        snapshot = self._snapshot_from_agent_view(actions=actions)
        return snapshot, actions

    def handle_intent(
        self,
        intent: AgentIntent,
    ) -> tuple[ProofStateSnapshot, list[dict[str, Any]]]:
        with self._lock:
            actions: list[dict[str, Any]] = []
            if intent.intent == "commit_tactic":
                tactic = str(intent.payload.get("tactic") or "").strip()
                if tactic:
                    self._run_backend(
                        "commit_tactic",
                        ["-next", "-c", tactic],
                        actions=actions,
                        timeout=180,
                    )
            elif intent.intent == "inspect_context" or is_context_topic_intent(intent.intent):
                payload = (
                    context_payload_for_intent(intent.intent, intent.payload)
                    if is_context_topic_intent(intent.intent)
                    else dict(intent.payload or {})
                )
                topic = normalize_context_topic(payload.get("topic") or "goal_info")
                # call_site_options used to short-circuit here to a static lightweight
                # action, which SHADOWED the real `-pivot-inspect call-site` backend
                # (frontier-gated + daemon-verified named-callee options + called-proc
                # body). Removed so the topic falls through to that backend like every
                # other inspect topic (panel audit: call_site_options 70% useless was
                # the shadow, not the producer).
                self._run_backend(
                    f"inspect_{topic}",
                    self._inspect_args(payload),
                    actions=actions,
                    timeout=120,
                )
            elif intent.intent == "lookup_symbol":
                symbol = str(intent.payload.get("symbol") or "").strip()
                if symbol:
                    self._run_backend(
                        "lookup_symbol",
                        ["-where", symbol],
                        actions=actions,
                        timeout=120,
                    )
            elif intent.intent == "undo_last_step":
                self._run_backend(
                    "undo_last_step",
                    ["-prev"],
                    actions=actions,
                    timeout=120,
                )
            elif intent.intent == "fresh_restart":
                return self._start_locked(
                    label="fresh_restart",
                    force_restart=True,
                )
            elif intent.intent == "finish":
                actions.append({"label": "finish", "exit_code": 0})
            snapshot = self._snapshot_from_agent_view(actions=actions)
            return snapshot, actions

    def read_only_context_action(
        self,
        intent_name: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """Run one read-only context backend action without refreshing the view.

        This is used only for SurfaceModel action preflight: the manager may need
        to know whether a button has displayable content before advertising it.
        It never mutates EasyCrypt proof state and never increments state_version.
        """
        if not is_context_topic_intent(intent_name) and intent_name != "inspect_context":
            return {}
        with self._lock:
            payload = (
                context_payload_for_intent(intent_name, payload or {})
                if is_context_topic_intent(intent_name)
                else dict(payload or {})
            )
            topic = normalize_context_topic(payload.get("topic") or "goal_info")
            actions: list[dict[str, Any]] = []
            try:
                self._run_backend(
                    f"inspect_{topic}",
                    self._inspect_args(payload),
                    actions=actions,
                    timeout=timeout,
                )
            except (ReplBackendTimeout, ReplBackendError):
                pass
            return dict(actions[-1]) if actions else {}


    def _snapshot_from_agent_view(self, *, actions: list[dict[str, Any]]) -> ProofStateSnapshot:
        stdout = self._run_backend(
            "agent_view",
            ["-agent-view"],
            actions=actions,
            timeout=60,
        )
        # Select the workspace view by shape, not "first decodable JSON": this
        # snapshot becomes the agent's entire visible state, so a stray JSON
        # fragment emitted before the view must never be mistaken for it.
        payload = workspace_payload_from_stdout(stdout)
        workspace = workspace_view_from_payload(
            payload if isinstance(payload, dict) else {}
        )
        self._state_version += 1
        goal_hash = _goal_hash(workspace)
        context_artifact = _context_artifact(workspace)
        workspace_artifact = _workspace_artifact(payload if isinstance(payload, dict) else {})
        return ProofStateSnapshot(
            node_id=self.node_id,
            session_tag=self.session_tag,
            session_dir=self.session_dir,
            session_epoch=self._session_epoch,
            state_version=self._state_version,
            goal_hash=goal_hash,
            proof_context_view_artifact=context_artifact,
            workspace_view_artifact=workspace_artifact,
            execution_refs={
                "manager_action_count": len(actions),
                "manager_actions": list(actions),
            },
            raw_workspace_view=workspace,
        )

    def _run_backend(
        self,
        label: str,
        args: list[str],
        *,
        actions: list[dict[str, Any]],
        timeout: int,
    ) -> str:
        cmd = [
            sys.executable,
            "core/easycrypt/session_cli.py",
            "-d",
            self.session_dir,
            *args,
        ]
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
            action = timeout_command_summary(
                label, cmd, exc, timeout, duration_ms,
            )
            actions.append(action)
            raise ReplBackendTimeout(action) from exc
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        action = command_summary(
            label, cmd, result, duration_ms,
            session_dir=session_dir_path(self.session_dir, self.project_root),
        )
        actions.append(action)
        if result.returncode != 0:
            raise ReplBackendError(action)
        return result.stdout or ""

    def _env(self) -> dict[str, str]:
        env = get_ec_env()
        env["EC_SESSION_DIR"] = self.session_dir
        env["SHANNON_LEGACY_DISPLAY"] = "hidden"
        return env

    def include_dirs(self) -> list[str]:
        return self._include_dirs()

    def _include_dirs(self) -> list[str]:
        file_dir = str(Path(self.file_path).parent or ".")
        dirs = [file_dir]
        if self.include_dir and self.include_dir != file_dir:
            dirs.append(self.include_dir)
        return dirs

    def _inspect_args(self, payload: dict[str, Any] | str) -> list[str]:
        if isinstance(payload, dict):
            topic = str(payload.get("topic") or "goal_info")
        else:
            topic = str(payload or "goal_info")
            payload = {}
        normalized = normalize_context_topic(topic)
        simple = {
            "goal_info": ["-goal-info"],
            "diagnose": ["-diagnose"],
            "episode_view": ["-episode-view"],
            "proof_frontier": ["-agent-view"],
            "workspace_view": ["-agent-view"],
            "align": ["-align"],
            "subgoal_gap": ["-subgoal-gap"],
            "lemma_hints": ["-lemma-hints"],
            "lemma_index": ["-lemma-index"],
            "equiv_bridge_lemmas": ["-bridge-lemmas"],
            "suggest_close": ["-suggest-close"],
            "pivot_context": ["-pivot-inspect", "context"],
            "verified_pivot_options": ["-pivot-inspect", "verified"],
            "call_site_options": ["-pivot-inspect", "call-site"],
            "pr_bridge_routes": ["-pivot-inspect", "bridge"],
            "call_invariant_skeleton": ["-pivot-inspect", "call-invariant-skeleton"],
            "rewrite_candidates": ["-pivot-inspect", "rewrite"],
        }
        if normalized in simple:
            return simple[normalized]
        if normalized == "call_subgoals":
            command = str(
                payload.get("command")
                or payload.get("invariant")
                or payload.get("invariant_body")
                or payload.get("tactic")
                or ""
            ).strip()
            return ["-call-subgoals", "-c", command] if command else ["-tactic-forms", "call"]
        if normalized == "tactic_forms":
            name = str(payload.get("name") or payload.get("tactic") or "").strip()
            return ["-tactic-forms", name] if name else ["-goal-info"]
        if normalized == "operator_lemmas":
            # Live EC-native `search OP.` over the LOADED context — returns the
            # applicable lemmas (project-local + cloned, not just stdlib) that mention
            # the operator. A FACT: lemma statements; the agent still picks/applies.
            # `op` may be a bare operator OR a tighter term skeleton like
            # `(big _ _ (_ :: _))` — EC search accepts both; a skeleton narrows a long
            # hit list (e.g. `big` 75 hits -> ~3 with the applicable lemma on top).
            # --max is raised because the default 30 SILENTLY TRUNCATES the list (the
            # needed lemma can sit past position 30 of the bare-operator search).
            op = str(
                payload.get("operator")
                or payload.get("symbol")
                or payload.get("name")
                or payload.get("op")
                or ""
            ).strip()
            return ["-search-skeleton", op, "--max", "200"] if op else ["-goal-info"]
        if normalized == "inv_from_lemma":
            lemma = str(payload.get("lemma") or payload.get("symbol") or "").strip()
            return ["-inv-from-lemma", lemma] if lemma else ["-goal-info"]
        return ["-goal-info"]


def session_dir_path(session_dir: str | Path, project_root: Path) -> Path:
    path = Path(session_dir)
    return path if path.is_absolute() else Path(project_root) / path


def read_committed_tactics(session_dir: Path) -> list[str]:
    return _read_committed_tactics(session_dir)


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
    current_goal = (
        workspace.get("current_goal")
        if isinstance(workspace.get("current_goal"), dict)
        else {}
    )
    proof_position = (
        workspace.get("proof_status")
        if isinstance(workspace.get("proof_status"), dict)
        else workspace.get("proof_position")
        if isinstance(workspace.get("proof_position"), dict)
        else {}
    )
    for value in (
        current_goal.get("goal_hash"),
        proof_position.get("goal_hash"),
    ):
        if isinstance(value, str) and value:
            return value
    lines = current_goal.get("lines") if isinstance(current_goal.get("lines"), list) else []
    text = "\n".join(str(line) for line in lines)
    if text:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()
    return ""


def _context_artifact(workspace: dict[str, Any]) -> str:
    more = (
        workspace.get("inspect_lookup_handles")
        if isinstance(workspace.get("inspect_lookup_handles"), dict)
        else workspace.get("want_more_context")
        if isinstance(workspace.get("want_more_context"), dict)
        else {}
    )
    return str(more.get("full_context_artifact") or "")


def _workspace_artifact(payload: dict[str, Any]) -> str:
    artifacts = (
        payload.get("artifacts")
        if isinstance(payload.get("artifacts"), dict)
        else {}
    )
    return str(artifacts.get("prover_workspace_view") or artifacts.get("workspace_view") or "")
