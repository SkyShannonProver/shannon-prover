"""Proof-node lifecycle state.

This module owns the mutable node-lifecycle facts that are not proof strategy:
latest snapshot/view, replay-prefix metadata, bootstrap/adopt handoff, and
projection bookkeeping.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from core.easycrypt.value_shapes import as_dict_copy as _dict
from typing import Any

from .types import NodeProgressSummary, ProofStateSnapshot

# A resume that restores materially fewer tactics than it was asked to replay
# is a paid-for-prefix loss the operator must see immediately (observed
# 2026-06-11: a 90-tactic capsule whose live tree later showed ~24 looked like
# a silent replay drop until manually traced). Above this lost-fraction the
# bootstrap emits a dedicated audit record and the orchestrator prints a loud
# "restored X/Y" warning instead of burying the divergence in the bootstrap
# JSON.
REPLAY_SHORTFALL_WARN_RATIO = 0.10


def replay_prefix_shortfall(
    requested_count: int,
    committed_count: int,
    *,
    warn_ratio: float = REPLAY_SHORTFALL_WARN_RATIO,
) -> dict[str, Any] | None:
    """Summary of a material replay shortfall, or ``None`` when within tolerance."""
    requested = max(0, _int(requested_count))
    committed = max(0, _int(committed_count))
    if requested <= 0 or committed >= requested:
        return None
    lost = requested - committed
    ratio = lost / requested
    if ratio <= warn_ratio:
        return None
    return {
        "requested": requested,
        "committed": committed,
        "lost": lost,
        "lost_ratio": round(ratio, 4),
    }


class ProofNodeLifecycleManager:
    """Owns per-node lifecycle state for the public manager facade."""

    def __init__(
        self,
        *,
        node_id: str,
        session_tag: str,
        repl: Any,
        projection: Any,
        lineage: Any,
        workspace: Any,
        run_dir: Callable[[], Path | None],
        audit: Callable[[dict[str, Any]], None],
        surface_profile: str | None = None,
    ) -> None:
        self.node_id = node_id
        self.session_tag = session_tag
        self.repl = repl
        self.projection = projection
        self.lineage = lineage
        self.workspace = workspace
        self._run_dir = run_dir
        self._audit = audit
        self.surface_profile = surface_profile
        self.latest_snapshot: ProofStateSnapshot | None = None
        self.latest_view: dict[str, Any] = {}
        self.latest_full_view: dict[str, Any] = {}
        self.replay_prefix_count = 0
        self.replay_prefix: list[str] = []
        # Durable "this node was resumed from an inherited prefix" marker.
        # Unlike ``replay_prefix_count`` (the transient resume FLOOR, which a
        # rewind below it deliberately clears so the shorter history reads as
        # fully agent-owned), this is a write-once LINEAGE fact: a respawn/
        # resume child stays a resumed node for its whole life. The
        # amend_and_replay guard keys off this so a rewind-into-prefix can't
        # silently re-enable amend on a resumed node (it edits + replays the
        # inherited prefix from the lemma, which the resumed-node contract
        # forbids — the agent uses the rewind menu instead).
        self.resumed_from_prefix = False

    def adopt_bootstrap(self, bootstrap: dict[str, Any]) -> None:
        """Adopt a manager bootstrap record without restarting EasyCrypt."""
        if not isinstance(bootstrap, dict):
            return
        self._adopt_replay_prefix_metadata(bootstrap)
        view = bootstrap.get("workspace_view")
        if isinstance(view, dict):
            self.latest_view = dict(view)
        snapshot_obj = bootstrap.get("snapshot")
        if not isinstance(snapshot_obj, dict):
            return
        state_version = _int(snapshot_obj.get("state_version"))
        session_epoch = _int(snapshot_obj.get("session_epoch"))
        self.repl.adopt_versions(state_version, session_epoch)
        self.latest_snapshot = ProofStateSnapshot(
            node_id=str(snapshot_obj.get("node_id") or self.node_id),
            session_tag=str(snapshot_obj.get("session_tag") or self.session_tag),
            session_dir=str(snapshot_obj.get("session_dir") or self.repl.session_dir),
            session_epoch=session_epoch,
            state_version=state_version,
            goal_hash=str(snapshot_obj.get("goal_hash") or ""),
            proof_context_view_artifact=str(
                snapshot_obj.get("proof_context_view_artifact") or ""
            ),
            workspace_view_artifact=str(
                snapshot_obj.get("workspace_view_artifact") or ""
            ),
            execution_refs=dict(snapshot_obj.get("execution_refs") or {}),
            raw_workspace_view=dict(self.latest_view),
        )

    def bootstrap(
        self,
        replay_prefix: list[str] | None = None,
        *,
        resume_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        replay_prefix = [
            str(tactic).strip()
            for tactic in (replay_prefix or [])
            if str(tactic).strip()
        ]
        resume_context = dict(resume_context or {})
        self.replay_prefix = list(replay_prefix)
        self.replay_prefix_count = _semantic_resume_prefix_count(
            resume_context,
            replayed_count=len(replay_prefix),
        )
        daemon_attach = _daemon_attach_request(resume_context)
        if daemon_attach:
            # Worker-death attach (SHANNON_EC_DAEMON=1): the Layer-3
            # respawn names the dead node's session dir; the repl tries to
            # adopt its still-live daemon EC session (zero replay) and
            # falls back to the legacy restart+replay restore on any
            # failure. With the flag off `_daemon_attach_request` returns
            # None, so the legacy call below stays byte-identical.
            snapshot, actions = self.repl.start(
                replay_prefix=replay_prefix,
                daemon_attach=daemon_attach,
            )
        else:
            snapshot, actions = self.repl.start(replay_prefix=replay_prefix)
        # The recorded prefix must be the session's ACTUAL starting history,
        # not an echo of the request: a replayed step that EasyCrypt accepts
        # but the no-progress detector auto-reverts never reaches history.ec,
        # and a bootstrap record echoing the request then misnumbers every
        # live step in replay/audit reconstructions (step4_1 r2 respawn,
        # 2026-06-09: 73 requested vs 72 committed shifted all audits by +1).
        requested_prefix = list(replay_prefix)
        committed_prefix = self._committed_start_history(requested_prefix)
        self.replay_prefix = list(committed_prefix)
        self.replay_prefix_count = _semantic_resume_prefix_count(
            resume_context,
            replayed_count=len(committed_prefix),
        )
        if committed_prefix or self.replay_prefix_count > 0:
            self.resumed_from_prefix = True
        self._seed_resume_context(snapshot, resume_context)
        view = self.project(snapshot)
        record = {
            "schema_version": 2,
            "kind": "proof_node_manager_bootstrap",
            "node": self.node_id,
            "session_tag": self.session_tag,
            "session_dir": snapshot.session_dir,
            "file": self.repl.file_path,
            "lemma": self.repl.lemma_name,
            "include_dirs": self.repl.include_dirs(),
            "replay_prefix_count": self.replay_prefix_count,
            "replay_prefix": list(self.replay_prefix),
            "replay_prefix_requested_count": len(requested_prefix),
            "manager_actions": actions,
            "snapshot": snapshot.to_dict(),
            "workspace_view": view,
        }
        if committed_prefix != requested_prefix:
            from .repl_session import replay_prefix_divergence

            record["replay_prefix_requested"] = requested_prefix
            divergence = replay_prefix_divergence(
                requested_prefix, committed_prefix,
            )
            record["replay_prefix_divergence"] = divergence
            shortfall = replay_prefix_shortfall(
                len(requested_prefix), len(committed_prefix),
            )
            if shortfall is not None:
                dropped = [
                    item for item in list(divergence.get("dropped") or [])
                    if isinstance(item, dict)
                ]
                first_dropped = dropped[0] if dropped else {}
                shortfall = {
                    **shortfall,
                    "first_dropped_index": first_dropped.get("index"),
                    "first_dropped_tactic": first_dropped.get("tactic"),
                }
                record["replay_prefix_shortfall"] = shortfall
                # Dedicated audit record: the bootstrap record itself is one
                # huge JSON blob; operators and post-run tooling need a
                # standalone, greppable event for "restored 24/90".
                self._audit({
                    "kind": "replay_prefix_shortfall",
                    "node": self.node_id,
                    "session_tag": self.session_tag,
                    "lemma": self.repl.lemma_name,
                    **shortfall,
                })
        if daemon_attach:
            # Audit visibility (flag-on only — flag off never reaches here,
            # keeping the legacy record shape unchanged): did the bootstrap
            # adopt a live daemon session (zero replay) or fall back?
            attach_action = next(
                (
                    a for a in actions
                    if isinstance(a, dict)
                    and a.get("label") in ("daemon_attach", "daemon_attach_fallback")
                ),
                None,
            )
            record["daemon_attach_requested"] = dict(daemon_attach)
            record["daemon_attach_result"] = (
                dict(attach_action.get("daemon_attach") or {})
                if isinstance(attach_action, dict) else {}
            )
        self._audit(record)
        self.lineage.run_dir = self._run_dir()
        self.lineage.record_node_bootstrap(
            node_id=self.node_id,
            session_tag=self.session_tag,
            session_dir=snapshot.session_dir,
            replay_prefix_count=self.replay_prefix_count,
        )
        return record

    def clear_replay_prefix(self) -> None:
        # Clears the transient resume FLOOR only. ``resumed_from_prefix`` is a
        # durable lineage fact and is intentionally left untouched: a rewind
        # below the floor lifts the floor but does not turn a resumed node into
        # a from-scratch one (see the field doc in __init__).
        self.replay_prefix_count = 0
        self.replay_prefix = []

    def _committed_start_history(self, fallback: list[str]) -> list[str]:
        """The session's actual post-replay history, or ``fallback``.

        Falls back to the requested prefix when the repl backend cannot
        report its committed history (test fakes, backendless roots).
        """
        reader = getattr(self.repl, "committed_history", None)
        if not callable(reader):
            return list(fallback)
        try:
            committed = reader()
        except Exception:
            return list(fallback)
        if not isinstance(committed, list):
            return list(fallback)
        cleaned = [
            str(tactic).strip()
            for tactic in committed
            if str(tactic).strip()
        ]
        if not cleaned and fallback:
            # An empty read with a non-empty request is indistinguishable
            # from an unreadable history file; a truly all-dropped replay is
            # caught separately by the no-open-proof bootstrap guard.
            return list(fallback)
        return cleaned

    def progress_summary(self) -> NodeProgressSummary:
        snapshot = self.latest_snapshot
        view = self.latest_view
        proof_status = (
            view.get("proof_status")
            if isinstance(view.get("proof_status"), dict) else {}
        )
        if not proof_status:
            proof_status = (
                view.get("proof_position")
                if isinstance(view.get("proof_position"), dict) else {}
            )
        return NodeProgressSummary(
            node_id=self.node_id,
            session_tag=self.session_tag,
            state_version=snapshot.state_version if snapshot else 0,
            goal_hash=snapshot.goal_hash if snapshot else "",
            proof_status=str(proof_status.get("status") or ""),
        )

    def set_latest_view(self, view: dict[str, Any]) -> None:
        self.latest_view = dict(view)

    def project(
        self,
        snapshot: ProofStateSnapshot,
        *,
        latest_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.projection.project(
            snapshot=snapshot,
            latest_observation=latest_observation,
            replay_prefix=self.replay_prefix,
            replay_prefix_count=self.replay_prefix_count,
            file_path=self.repl.file_path,
            project_root=str(self.repl.project_root),
        )
        view = result.view
        self.latest_snapshot = snapshot
        self.latest_view = view
        self.latest_full_view = getattr(result, "full_view", None) or view
        self._audit({
            "kind": "workspace_view.projected",
            "node": self.node_id,
            "snapshot": snapshot.to_dict(),
            "view_hash": view.get("view_hash"),
            "surface_profile": self.surface_profile,
            "lint": self.workspace.lint_agent_view(view),
        })
        return view

    def _adopt_replay_prefix_metadata(self, bootstrap: dict[str, Any]) -> None:
        replay_prefix = bootstrap.get("replay_prefix")
        if isinstance(replay_prefix, list):
            self.replay_prefix = [
                str(tactic).strip()
                for tactic in replay_prefix
                if str(tactic).strip()
            ]
        replay_count = _int(bootstrap.get("replay_prefix_count"))
        if replay_count <= 0 and self.replay_prefix:
            replay_count = len(self.replay_prefix)
        self.replay_prefix_count = max(0, replay_count)
        # The worker manager never calls bootstrap(); it adopts a handoff.
        # Stamp the durable resumed-lineage marker here so the amend guard
        # holds in the very process that serves the agent's turns.
        if self.replay_prefix_count > 0 or self.replay_prefix:
            self.resumed_from_prefix = True

    def _seed_resume_context(
        self,
        snapshot: ProofStateSnapshot,
        resume_context: dict[str, Any],
    ) -> None:
        if not resume_context:
            return
        latest_view = _dict(resume_context.get("latest_workspace_view"))
        route_memory_payload = _dict(resume_context.get("route_memory_payload"))
        checkpoint_payload = _dict(resume_context.get("checkpoint_payload"))
        route_events = [
            dict(item)
            for item in list(resume_context.get("route_event_facts") or [])
            if isinstance(item, dict)
        ]
        probe_alternatives = [
            dict(item)
            for item in list(resume_context.get("probe_alternatives") or [])
            if isinstance(item, dict)
        ]
        verified_route_options = [
            dict(item)
            for item in list(resume_context.get("verified_route_options") or [])
            if isinstance(item, dict)
        ]
        proof_memory = getattr(self.projection, "proof_memory", None)
        if proof_memory is not None and hasattr(proof_memory, "seed_resume_payload"):
            proof_memory.seed_resume_payload(
                route_memory_payload,
                latest_workspace_view=latest_view,
            )
        if (
            proof_memory is not None
            and hasattr(proof_memory, "seed_verified_route_options")
        ):
            proof_memory.seed_verified_route_options(verified_route_options)
        checkpoints = getattr(self.projection, "checkpoints", None)
        if checkpoints is not None and hasattr(checkpoints, "seed_resume_payload"):
            checkpoints.seed_resume_payload(checkpoint_payload)
        events = getattr(self.projection, "events", None)
        if events is not None and hasattr(events, "seed_resume_route_events"):
            events.seed_resume_route_events(route_events)
        probe_manager = getattr(self.projection, "probe_alternatives", None)
        if (
            probe_manager is not None
            and hasattr(probe_manager, "seed_for_snapshot")
        ):
            probe_manager.seed_for_snapshot(snapshot, probe_alternatives)


def _daemon_attach_request(resume_context: dict[str, Any]) -> dict[str, Any] | None:
    """The validated ``daemon_attach`` request from a resume context, or None.

    Only honored when SHANNON_EC_DAEMON=1 — with the flag off this always
    returns None so ``bootstrap`` issues the exact legacy ``repl.start``
    call (test fakes and the measurement-campaign pipeline see no change)."""
    request = resume_context.get("daemon_attach")
    if not isinstance(request, dict):
        return None
    donor = str(request.get("donor_session_dir") or "").strip()
    if not donor:
        return None
    try:
        from .daemon_attach import daemon_session_attach_enabled
    except ImportError:
        return None
    if not daemon_session_attach_enabled():
        return None
    return {
        "donor_session_dir": donor,
        "expected_goal_hash": str(request.get("expected_goal_hash") or ""),
    }


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0



def _semantic_resume_prefix_count(
    resume_context: dict[str, Any],
    *,
    replayed_count: int,
) -> int:
    if "resume_prefix_count" not in resume_context:
        return max(0, replayed_count)
    count = _int(resume_context.get("resume_prefix_count"))
    if count <= 0:
        return max(0, replayed_count)
    return min(count, max(0, replayed_count))
