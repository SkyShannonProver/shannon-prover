"""Proof-node lifecycle state.

This module owns the mutable node-lifecycle facts that are not proof strategy:
latest snapshot/view, replay-prefix metadata, bootstrap/adopt handoff, and
projection bookkeeping.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from core.easycrypt.value_shapes import as_dict_copy as _dict
from workflow.proof_state_compiler.surface_profiles import (
    ensure_current_surface_profile,
    require_current_workspace_view,
)

from .types import NodeProgressSummary, ProofStateSnapshot

# A resume that restores materially fewer tactics than it was asked to replay
# is a paid-for-prefix loss the operator must see immediately (observed
# 2026-06-11: a 90-tactic capsule whose live tree later showed ~24 looked like
# a silent replay drop until manually traced). Above this lost-fraction the
# bootstrap emits a dedicated audit record and the orchestrator prints a loud
# "restored X/Y" warning instead of burying the divergence in the bootstrap
# JSON.
REPLAY_SHORTFALL_WARN_RATIO = 0.10
PROOF_NODE_MANAGER_BOOTSTRAP_SCHEMA_VERSION = 3
PROOF_NODE_MANAGER_BOOTSTRAP_KIND = "proof_node_manager_bootstrap"

_BOOTSTRAP_IDENTITY_FIELDS = (
    "node_id",
    "session_tag",
    "session_dir",
    "file",
    "lemma",
)
_BOOTSTRAP_SNAPSHOT_IDENTITY_FIELDS = (
    "node_id",
    "session_tag",
    "session_dir",
)


def require_proof_node_manager_bootstrap(
    bootstrap: object,
    *,
    label: str = "proof-node manager bootstrap",
    expected_identity: Mapping[str, str] | None = None,
    surface_profile: str | None = None,
) -> dict[str, Any]:
    """Return a current bootstrap record or reject the protocol mismatch.

    Bootstrap handoffs cross the orchestrator/worker process boundary.  A
    permissive adopter can silently reinterpret an older record after either
    side changes, so this boundary intentionally has no compatibility mode.
    """
    if not isinstance(bootstrap, dict):
        raise TypeError(f"{label} must be a JSON object")
    schema_version = bootstrap.get("schema_version")
    kind = bootstrap.get("kind")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != PROOF_NODE_MANAGER_BOOTSTRAP_SCHEMA_VERSION
        or kind != PROOF_NODE_MANAGER_BOOTSTRAP_KIND
    ):
        raise ValueError(
            f"{label} must have schema_version="
            f"{PROOF_NODE_MANAGER_BOOTSTRAP_SCHEMA_VERSION} and kind="
            f"{PROOF_NODE_MANAGER_BOOTSTRAP_KIND!r}; got "
            f"schema_version={schema_version!r}, kind={kind!r}"
        )
    if "node" in bootstrap:
        raise ValueError(
            f"{label} contains retired identity field `node`; use `node_id`"
        )
    for field in _BOOTSTRAP_IDENTITY_FIELDS:
        value = bootstrap.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{label} field `{field}` must be a non-empty string"
            )
    if expected_identity is not None:
        for field in _BOOTSTRAP_IDENTITY_FIELDS:
            if field not in expected_identity:
                raise ValueError(
                    f"{label} expected identity is missing `{field}`"
                )
            expected = expected_identity[field]
            actual = bootstrap[field]
            if actual != expected:
                raise ValueError(
                    f"{label} identity mismatch for `{field}`: "
                    f"expected {expected!r}, got {actual!r}"
                )

    include_dirs = bootstrap.get("include_dirs")
    if (
        not isinstance(include_dirs, list)
        or not include_dirs
        or any(not isinstance(item, str) or not item.strip() for item in include_dirs)
    ):
        raise ValueError(
            f"{label} field `include_dirs` must be a non-empty list of strings"
        )
    replay_prefix = bootstrap.get("replay_prefix")
    if not isinstance(replay_prefix, list) or any(
        not isinstance(item, str) or not item.strip() for item in replay_prefix
    ):
        raise ValueError(
            f"{label} field `replay_prefix` must be a list of non-empty strings"
        )
    replay_prefix_count = _require_nonnegative_int(
        bootstrap.get("replay_prefix_count"),
        label=f"{label}.replay_prefix_count",
    )
    if replay_prefix_count > len(replay_prefix):
        raise ValueError(
            f"{label}.replay_prefix_count cannot exceed the committed "
            "`replay_prefix` length"
        )
    _require_nonnegative_int(
        bootstrap.get("replay_prefix_requested_count"),
        label=f"{label}.replay_prefix_requested_count",
    )
    manager_actions = bootstrap.get("manager_actions")
    if not isinstance(manager_actions, list) or any(
        not isinstance(item, dict) for item in manager_actions
    ):
        raise ValueError(
            f"{label} field `manager_actions` must be a list of objects"
        )

    snapshot = bootstrap.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError(f"{label} field `snapshot` must be an object")
    for field in _BOOTSTRAP_SNAPSHOT_IDENTITY_FIELDS:
        value = snapshot.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{label}.snapshot field `{field}` must be a non-empty string"
            )
        if value != bootstrap[field]:
            raise ValueError(
                f"{label}.snapshot identity mismatch for `{field}`: "
                f"expected {bootstrap[field]!r}, got {value!r}"
            )
    _require_nonnegative_int(
        snapshot.get("session_epoch"),
        label=f"{label}.snapshot.session_epoch",
    )
    _require_nonnegative_int(
        snapshot.get("state_version"),
        label=f"{label}.snapshot.state_version",
    )
    for field in (
        "goal_hash",
        "workspace_view_artifact",
    ):
        if not isinstance(snapshot.get(field), str):
            raise ValueError(
                f"{label}.snapshot field `{field}` must be a string"
            )
    if type(snapshot.get("goal_identity_required")) is not bool:
        raise ValueError(
            f"{label}.snapshot field `goal_identity_required` must be a bool"
        )
    if snapshot["goal_identity_required"] != bool(snapshot["goal_hash"]):
        raise ValueError(
            f"{label}.snapshot goal identity class disagrees with goal_hash"
        )
    if not isinstance(snapshot.get("execution_refs"), dict):
        raise ValueError(
            f"{label}.snapshot field `execution_refs` must be an object"
        )

    workspace_view = bootstrap.get("workspace_view")
    if not isinstance(workspace_view, dict):
        raise ValueError(f"{label} field `workspace_view` must be an object")
    profile = ensure_current_surface_profile(surface_profile)
    require_current_workspace_view(
        workspace_view,
        profile_id=profile.name,
        label=f"{label}.workspace_view",
    )
    proof_status = workspace_view.get("proof_status")
    if not isinstance(proof_status, dict) or not proof_status:
        raise ValueError(
            f"{label}.workspace_view.proof_status must be a non-empty object"
        )
    status = proof_status.get("status")
    if not isinstance(status, str) or not status.strip():
        raise ValueError(
            f"{label}.workspace_view.proof_status.status must be a non-empty string"
        )
    if not isinstance(proof_status.get("remaining_goals_known"), bool):
        raise ValueError(
            f"{label}.workspace_view.proof_status.remaining_goals_known must be a bool"
        )
    if (
        proof_status.get("goal_identity_required")
        != snapshot["goal_identity_required"]
        or str(proof_status.get("goal_hash") or "") != snapshot["goal_hash"]
    ):
        raise ValueError(
            f"{label} snapshot and workspace goal identity disagree"
        )
    if not isinstance(workspace_view.get("current_goal"), dict):
        raise ValueError(
            f"{label}.workspace_view.current_goal must be an object"
        )
    return bootstrap


def _require_nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


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
        self.surface_profile = ensure_current_surface_profile(
            surface_profile
        ).name
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
        require_proof_node_manager_bootstrap(
            bootstrap,
            surface_profile=self.surface_profile,
            expected_identity={
                "node_id": self.node_id,
                "session_tag": self.session_tag,
                "session_dir": self.repl.session_dir,
                "file": self.repl.file_path,
                "lemma": self.repl.lemma_name,
            },
        )
        self._adopt_replay_prefix_metadata(bootstrap)
        view = bootstrap["workspace_view"]
        self.latest_view = dict(view)
        snapshot_obj = bootstrap["snapshot"]
        state_version = snapshot_obj["state_version"]
        session_epoch = snapshot_obj["session_epoch"]
        self.repl.adopt_versions(state_version, session_epoch)
        self.latest_snapshot = ProofStateSnapshot(
            node_id=snapshot_obj["node_id"],
            session_tag=snapshot_obj["session_tag"],
            session_dir=snapshot_obj["session_dir"],
            session_epoch=session_epoch,
            state_version=state_version,
            goal_hash=snapshot_obj["goal_hash"],
            goal_identity_required=snapshot_obj["goal_identity_required"],
            workspace_view_artifact=snapshot_obj["workspace_view_artifact"],
            execution_refs=dict(snapshot_obj["execution_refs"]),
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
            # falls back to the canonical restart+replay restore on any
            # failure. With the flag off `_daemon_attach_request` returns
            # None and the same restart+replay call is used.
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
        committed_prefix = self._committed_start_history()
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
            "schema_version": PROOF_NODE_MANAGER_BOOTSTRAP_SCHEMA_VERSION,
            "kind": PROOF_NODE_MANAGER_BOOTSTRAP_KIND,
            "node_id": self.node_id,
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
            # Audit visibility (flag-on only — flag off never reaches here):
            # did the bootstrap
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
        require_proof_node_manager_bootstrap(
            record,
            surface_profile=self.surface_profile,
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

    def _committed_start_history(self) -> list[str]:
        """Return the session's authoritative post-replay history.

        A requested replay prefix describes intent, not committed state.  The
        lifecycle therefore requires the production REPL contract here and
        never manufactures history from the request when the reader is
        missing, fails, or reports an empty session.
        """
        reader = getattr(self.repl, "committed_history", None)
        if not callable(reader):
            raise TypeError(
                "proof-node REPL must provide committed_history()"
            )
        committed = reader()
        if type(committed) is not list or any(
            type(tactic) is not str for tactic in committed
        ):
            raise TypeError(
                "proof-node REPL committed_history() must return list[str]"
            )
        return list(committed)

    def progress_summary(self) -> NodeProgressSummary:
        snapshot = self.latest_snapshot
        view = self.latest_view
        proof_status = (
            view.get("proof_status")
            if isinstance(view.get("proof_status"), dict) else {}
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
        self.latest_full_view = result.full_view
        self._audit({
            "kind": "workspace_view.projected",
            "node": self.node_id,
            "snapshot": snapshot.to_dict(),
            "view_hash": view.get("view_hash"),
            "surface_profile": self.surface_profile,
            "lint": self.workspace.lint_workspace_view(view),
        })
        return view

    def _adopt_replay_prefix_metadata(self, bootstrap: dict[str, Any]) -> None:
        self.replay_prefix = list(bootstrap["replay_prefix"])
        self.replay_prefix_count = bootstrap["replay_prefix_count"]
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
        checkpoint_payload = _dict(resume_context.get("checkpoint_payload"))
        route_events = [
            dict(item)
            for item in list(resume_context.get("route_event_facts") or [])
            if isinstance(item, dict)
        ]
        checkpoints = getattr(self.projection, "checkpoints", None)
        if checkpoints is not None and hasattr(checkpoints, "seed_resume_payload"):
            checkpoints.seed_resume_payload(checkpoint_payload)
        events = getattr(self.projection, "events", None)
        if events is not None and hasattr(events, "seed_resume_route_events"):
            events.seed_resume_route_events(route_events)


def _daemon_attach_request(resume_context: dict[str, Any]) -> dict[str, Any] | None:
    """The validated ``daemon_attach`` request from a resume context, or None.

    Only honored when SHANNON_EC_DAEMON=1 — with the flag off this always
    returns None so ``bootstrap`` issues the ordinary ``repl.start`` call."""
    request = resume_context.get("daemon_attach")
    if not isinstance(request, dict):
        return None
    donor = str(request.get("donor_session_dir") or "").strip()
    if not donor:
        return None
    goal_identity_required = request.get("goal_identity_required")
    if type(goal_identity_required) is not bool:
        return None
    expected_goal_hash = str(request.get("expected_goal_hash") or "").strip()
    if goal_identity_required != bool(expected_goal_hash):
        return None
    try:
        from .daemon_attach import daemon_session_attach_enabled
    except ImportError:
        return None
    if not daemon_session_attach_enabled():
        return None
    return {
        "donor_session_dir": donor,
        "expected_goal_hash": expected_goal_hash,
        "goal_identity_required": goal_identity_required,
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
    count = _require_nonnegative_int(
        resume_context["resume_prefix_count"],
        label="resume context resume_prefix_count",
    )
    if count <= 0:
        return max(0, replayed_count)
    return min(count, max(0, replayed_count))
