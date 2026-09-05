"""Proof-node resume capsules for manager-owned prover runs.

A resume capsule is a durable handoff for an interrupted managed proof node.
It is intentionally centered on the current architecture:

- the accepted EasyCrypt prefix in the node-owned session history
- the latest manager/node_memory workspace view for audit and briefing
- the manager-owned checkpoint sidecar for resumable proof control
- recent failures and accepted manager outcomes

Capsules use ``resume.json`` and can be created from live ``.ec_session_*``
directories before the next prover launch wipes them.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.committed_history import (
    flatten_committed_transactions,
    read_committed_commands,
    read_committed_transactions,
)
from core.easycrypt.proof_lifecycle import has_discharged_goals
from workflow.proof_management.common import node_memory_slug
from workflow.proof_management.checkpoint_store import (
    normalize_checkpoint_state_payload,
)
from workflow.proof_management.event_store import (
    ProofEventManager,
    require_resume_route_event,
    resume_route_event_from_manager_route_event,
)
from workflow.proof_management.route_diversity import (
    ResumeRouteCandidate,
    build_resume_diversity_index,
    resume_diversity_candidate_summary,
    resume_diversity_handoff_note,
    resume_diversity_markdown,
    resume_route_candidate_from_manifest,
)
from workflow.proof_management.route_family import (
    RouteFamilyEvidence,
    infer_route_family,
    route_family_score_adjustment,
)
from workflow.proof_management.session_goal_identity import (
    read_session_goal_identity,
)
from workflow.node.continuation_brief import (
    merge_agent_report,
    normalize_continuation_brief,
)
from core.easycrypt.value_shapes import as_dict as _dict


CAPSULE_VERSION = 2
CAPSULE_KIND = "proof_node_resume_capsule"
RESUME_ROOT_POLICY_SCORE = "score"
RESUME_ROOT_POLICY_DIVERSITY = "diversity"
RESUME_ROOT_POLICIES = {
    RESUME_ROOT_POLICY_SCORE,
    RESUME_ROOT_POLICY_DIVERSITY,
}


@dataclass(frozen=True)
class ProofNodeResumeCapsule:
    """Loaded resume metadata plus replay payload.

    This deliberately mirrors the fields consumed by ``workflow.agents.prover``.
    """

    path: Path
    target_file: str
    lemma: str
    include_dir: str
    commit: str
    session_name: str
    replay_prefix: list[str]
    replay_transactions: list[str]
    current_goal_hash: str
    proof_status: str
    goal_identity_required: bool
    current_goal_preview: str
    current_goal_path: str
    score: float
    reasons: list[str]
    handoff_notes: list[str]
    recent_tactics: list[dict[str, Any]]
    route_family: str = ""
    resume_diversity: dict[str, Any] | None = None
    resume_prefix_count: int = 0
    resume_context: dict[str, Any] | None = None
    # The manifest's own `replay.tactic_count` claim. When this exceeds the
    # tactics actually loaded from history.ec the capsule is internally
    # inconsistent (truncated/mismatched history) and the resume silently
    # starts from a shorter prefix than the index advertises.
    recorded_tactic_count: int = 0

    @property
    def tactic_count(self) -> int:
        return len(self.replay_prefix)


def _read_text(path: Path, *, max_chars: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars]
    return text


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return rows
    for line in lines[-max(1, limit) :]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _history_commands(history_file: Path) -> list[str]:
    """Read a capsule-named history as complete EasyCrypt commands.

    ``history.ec`` normally has one physical line per manager commit, but a
    committed tactic may itself contain newlines (notably a formatted
    ``while{2} (...)`` invariant). Treating physical lines as replay units
    truncates that tactic at ``while{2} (`` and makes an otherwise valid
    checkpoint unreplayable.

    The manifest may name a non-default history file, so use the canonical
    command reader on its parent only when the basename is ``history.ec``;
    otherwise preserve the same splitter semantics on the named file text.
    """

    if history_file.name == "history.ec":
        return read_committed_commands(history_file.parent)
    text = _read_text(history_file)
    if not text:
        return []
    try:
        from core.easycrypt.ec_daemon import _split_ec_commands

        return [item.strip() for item in _split_ec_commands(text) if item.strip()]
    except Exception:
        return [line.strip() for line in text.splitlines() if line.strip()]


def _git_commit(cwd: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""



def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _recent_tactics(
    route_events: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Return recent tactic attempts from the typed manager event spine."""
    out: list[dict[str, Any]] = []
    for item in route_events:
        tactic = str(item.get("tactic") or "").strip()
        if not tactic:
            continue
        row: dict[str, Any] = {
            "turn": item.get("turn_index"),
            "intent": str(item.get("intent") or ""),
            "status": str(item.get("outcome_kind") or "unknown"),
            "tactic": tactic,
        }
        error_summary = str(item.get("error_summary") or "").strip()
        if error_summary:
            row["outcome"] = _truncate(error_summary, 220)
        out.append(row)
    return out[-limit:]


def _manager_route_events_for_node(
    run_dir: Path,
    node_id: str,
) -> list[dict[str, Any]]:
    if not node_id:
        return []
    manager = ProofEventManager(
        node_id=node_id,
        run_dir=run_dir,
        route_event_limit=40,
    )
    return manager.route_event_facts


def _resume_route_events_from_manager(
    route_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        resume_route_event_from_manager_route_event(
            item,
            label=f"manager_route_events[{index}]",
        )
        for index, item in enumerate(route_events)
    ]


def _resume_prefix_count_from_handoff(
    *,
    timeline: list[dict[str, Any]],
    history_count: int,
) -> int:
    """Recover resumed-prefix length from the manager's bootstrap timeline."""
    for item in timeline:
        if str(item.get("kind") or "") != "bootstrap":
            continue
        try:
            count = int(item.get("replay_prefix_count") or 0)
        except (TypeError, ValueError):
            count = 0
        if 0 < count < history_count:
            return count
    return max(0, history_count)


def _latest_workspace_view(memory_dir: Path) -> dict[str, Any]:
    return _read_json(memory_dir / "latest_workspace_view.json")


def _goal_preview_from_view(view: dict[str, Any], fallback: str) -> str:
    current_goal = _dict(view.get("current_goal"))
    lines = current_goal.get("lines")
    if isinstance(lines, list) and lines:
        return "\n".join(str(line) for line in lines)
    preview = current_goal.get("lines_preview")
    if isinstance(preview, str) and preview.strip():
        return preview.strip()
    if fallback.strip():
        return fallback.strip()
    return ""


def _node_id_from_session_dir(session_dir: Path) -> str:
    """Return the canonical manager node id encoded by a tree session dir."""
    name = session_dir.name
    match = re.fullmatch(
        r"\.ec_session_prover_(?:[a-z0-9]{6,32}_)?tree_([A-Za-z0-9_]+)",
        name,
    )
    if not match:
        return ""
    components = [item for item in match.group(1).split("_") if item]
    if not components:
        return ""
    return "Tree-" + ".".join(components)


def _node_memory_for_session(run_dir: Path, session_dir: Path) -> Path | None:
    node_memory_root = run_dir / "node_memory"
    node_id = _node_id_from_session_dir(session_dir)
    if not node_id:
        return None
    candidate = node_memory_root / node_memory_slug(node_id)
    return candidate if candidate.is_dir() else None


def _lineage_tail_for_node(run_dir: Path, node_id: str) -> list[dict[str, Any]]:
    rows = _read_jsonl_tail(run_dir / "lemma_lineage.jsonl", limit=160)
    if not node_id:
        return []
    return [
        row for row in rows
        if row.get("node") == node_id
    ][-40:]


def _sidecar_node_slug(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", node_id)


def _is_canonical_node_id(node_id: Any) -> bool:
    return (
        type(node_id) is str
        and re.fullmatch(r"Tree-[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*", node_id)
        is not None
    )


def _checkpoint_payload_for_node(run_dir: Path, node_id: str) -> dict[str, Any]:
    if not _is_canonical_node_id(node_id):
        return {}
    slug = _sidecar_node_slug(node_id)
    return _current_checkpoint_payload(
        _read_json(
            run_dir / "checkpoint_state" / f"{slug}_checkpoint_state.json"
        ),
        expected_node_id=node_id,
    )


def _current_checkpoint_payload(
    payload: dict[str, Any],
    *,
    expected_node_id: str | None = None,
) -> dict[str, Any]:
    """Project the current checkpoint sidecar to its resumable state."""
    return normalize_checkpoint_state_payload(
        payload,
        expected_node_id=expected_node_id,
        require_anchor=True,
    )


def _lineage_briefing_payload(run_dir: Path) -> dict[str, Any]:
    return _read_json(run_dir / "lemma_lineage_briefing.json")


def _copy_if_exists(src: Path, dst: Path) -> str:
    if not src.exists():
        return ""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst.name


def _capsule_notes(
    *,
    view: dict[str, Any],
    latest_followup: str,
    lineage_briefing: dict[str, Any] | None = None,
    route_family: dict[str, Any] | None = None,
) -> list[str]:
    notes: list[str] = []
    proof_status = _dict(view.get("proof_status"))
    status_bits = []
    for key in ("status", "remaining_goals", "goal_type", "view_focus", "current_layer"):
        if key in proof_status:
            status_bits.append(f"{key}={proof_status.get(key)}")
    if status_bits:
        notes.append("Latest manager view: " + ", ".join(status_bits) + ".")
    family = _dict(route_family)
    if family.get("family"):
        notes.append(
            "Resume route family: "
            + str(family.get("family"))
            + (
                f" ({family.get('confidence')} confidence)"
                if family.get("confidence") else ""
            )
            + "."
        )

    notes.extend(_lineage_briefing_handoff_notes(
        dict(lineage_briefing or {}),
    ))

    if latest_followup:
        marker = "manager_note"
        idx = latest_followup.find(marker)
        excerpt = latest_followup[idx:] if idx >= 0 else latest_followup
        notes.append("Latest followup excerpt: " + _truncate(excerpt, 500))
    return notes[:10]


def _lineage_briefing_handoff_notes(briefing: dict[str, Any]) -> list[str]:
    if not briefing:
        return []
    route_counts = _dict(briefing.get("route_family_counts"))
    pieces: list[str] = []
    if route_counts:
        pieces.append(
            "route families "
            + ", ".join(
                f"{name}={count}"
                for name, count in sorted(route_counts.items())
            )
        )
    winner = _dict(briefing.get("winner"))
    if winner:
        pieces.append(
            "winner "
            + str(winner.get("node") or "")
            + (
                " completion_candidate="
                f"{winner.get('completion_candidate')}"
                if "completion_candidate" in winner else ""
            )
        )
    if not pieces:
        pieces.append(
            f"{briefing.get('node_count', 0)} node(s)"
        )
    return [
        "Run lineage before resume: "
        + _truncate("; ".join(piece for piece in pieces if piece), 420)
        + "."
    ]


def _score_capsule(
    *,
    history: list[str],
    view: dict[str, Any],
    route_family: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = float(len(history))
    if history:
        reasons.append(f"{len(history)} accepted replay tactic(s)")
    remaining = _dict(view.get("proof_status")).get("remaining_goals")
    if isinstance(remaining, int):
        score += max(0.0, 10.0 - remaining)
        reasons.append(f"remaining_goals={remaining}")
    current_layer = str(_dict(view.get("proof_status")).get("current_layer") or "")
    if current_layer:
        score += 0.5
        reasons.append(f"current_layer={current_layer}")
    route_family_dict = _dict(route_family)
    adjustment, reason = route_family_score_adjustment(RouteFamilyEvidence(
        family=str(route_family_dict.get("family") or "unknown"),
        confidence=str(route_family_dict.get("confidence") or "low"),
        evidence=[
            str(item)
            for item in list(route_family_dict.get("evidence") or [])
        ],
    ))
    if adjustment:
        score += adjustment
    if reason:
        reasons.append(reason)
    return score, reasons


def _attach_resume_diversity_handoff(
    *,
    candidates: list[Any],
    diversity_index: dict[str, Any],
) -> None:
    """Attach run-level diversity evidence to every self-contained capsule."""

    if not candidates:
        return
    diversity_markdown = resume_diversity_markdown(diversity_index)
    for candidate in candidates:
        manifest_path = Path(str(candidate.path))
        manifest = _read_json(manifest_path)
        if not manifest:
            continue
        note = resume_diversity_handoff_note(
            diversity_index,
            capsule_path=str(manifest_path),
        )
        diversity_summary = resume_diversity_candidate_summary(
            diversity_index,
            capsule_path=str(manifest_path),
        )
        handoff = _dict(manifest.get("handoff"))
        notes = [str(item) for item in list(handoff.get("notes") or [])]
        if note and note not in notes:
            notes.append(note)
        artifacts = _dict(handoff.get("artifacts"))
        artifacts["resume_route_diversity"] = "resume_route_diversity.json"
        artifacts["resume_route_diversity_md"] = "resume_route_diversity.md"
        handoff["notes"] = notes
        handoff["artifacts"] = artifacts
        manifest["handoff"] = handoff
        lineage = _dict(manifest.get("lineage"))
        if diversity_summary:
            lineage["resume_diversity"] = diversity_summary
        manifest["lineage"] = lineage
        _write_json(manifest_path.parent / "resume_route_diversity.json", diversity_index)
        (manifest_path.parent / "resume_route_diversity.md").write_text(
            diversity_markdown,
            encoding="utf-8",
        )
        _write_json(manifest_path, manifest)


def create_resume_capsules(
    *,
    project_root: Path,
    run_dir: Path,
    target_file: str,
    lemma: str,
    include_dir: str = "",
    session_dirs: Iterable[Path],
    output_dir: Path | None = None,
    agent_report: dict[str, Any] | None = None,
    agent_report_session_name: str = "",
) -> list[str]:
    """Create resume capsules from live managed session dirs and node memory."""

    project_root = project_root.resolve()
    run_dir = run_dir.resolve()
    output_dir = (output_dir or (run_dir / "resume_capsules")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    session_dirs = [Path(p).expanduser() for p in session_dirs]

    created: list[tuple[float, Path]] = []
    for session_dir in session_dirs:
        session_dir = session_dir.resolve()
        if not session_dir.is_dir():
            continue
        history = read_committed_commands(session_dir)
        if not history:
            continue
        transactions = read_committed_transactions(session_dir)
        if not transactions or flatten_committed_transactions(transactions) != history:
            continue
        memory_dir = _node_memory_for_session(run_dir, session_dir)
        view = _latest_workspace_view(memory_dir) if memory_dir else {}
        current_out = _read_text(session_dir / "current.out", max_chars=20000)
        goal_preview = _goal_preview_from_view(view, current_out)
        goal_identity = read_session_goal_identity(session_dir)
        goal_hash = goal_identity.goal_hash
        # An open proof without an identity cannot make a verifiable replay
        # promise.  In particular, never repair this with the node-memory
        # timeline: that hash may describe an older prefix than history.ec.
        if goal_identity.goal_identity_required and not goal_hash:
            continue

        node_id = _node_id_from_session_dir(session_dir)
        if not node_id:
            continue
        lineage_events = _lineage_tail_for_node(run_dir, node_id)
        lineage_briefing = _lineage_briefing_payload(run_dir)
        checkpoint_payload = _checkpoint_payload_for_node(run_dir, node_id)
        route_family = infer_route_family(history).to_dict()
        attempts = _read_jsonl_tail(memory_dir / "attempts.jsonl", limit=80) if memory_dir else []
        timeline = _read_jsonl_tail(memory_dir / "timeline.jsonl", limit=80) if memory_dir else []
        failures = _read_jsonl_tail(memory_dir / "failures.jsonl", limit=40) if memory_dir else []
        manager_route_events = _manager_route_events_for_node(run_dir, node_id)
        route_event_facts = _resume_route_events_from_manager(manager_route_events)
        resume_prefix_count = _resume_prefix_count_from_handoff(
            timeline=timeline,
            history_count=len(history),
        )
        latest_followup = _read_text(memory_dir / "latest_followup.md", max_chars=12000) if memory_dir else ""
        notes = _capsule_notes(
            view=view,
            latest_followup=latest_followup,
            lineage_briefing=lineage_briefing,
            route_family=route_family,
        )
        recent_tactics = _recent_tactics(manager_route_events, limit=16)
        prior_brief = (
            _read_json(memory_dir / "continuation_brief.json")
            if memory_dir
            else {}
        )
        session_report = (
            agent_report
            if agent_report_session_name
            and session_dir.name == agent_report_session_name
            else None
        )
        continuation_brief = merge_agent_report(
            prior_brief,
            session_report or {},
        )
        score, reasons = _score_capsule(
            history=history,
            view=view,
            route_family=route_family,
        )

        rank_name = f"{node_memory_slug(node_id)}_{session_dir.name}"
        capsule_dir = output_dir / rank_name
        capsule_dir.mkdir(parents=True, exist_ok=True)
        _copy_if_exists(session_dir / "history.ec", capsule_dir / "history.ec")
        transaction_payload = {
            "schema_version": 1,
            "kind": "proof_replay_transactions",
            "command_count": len(history),
            "transaction_count": len(transactions),
            "transactions": transactions,
        }
        _write_json(capsule_dir / "transactions.json", transaction_payload)
        goal_file = _copy_if_exists(session_dir / "current.out", capsule_dir / "current_goal.out")
        _copy_if_exists(session_dir / "session_meta.json", capsule_dir / "session_meta.json")
        if memory_dir:
            _copy_if_exists(memory_dir / "latest_workspace_view.json", capsule_dir / "latest_workspace_view.json")
            _copy_if_exists(memory_dir / "latest_followup.md", capsule_dir / "latest_followup.md")
            _copy_if_exists(memory_dir / "notes.md", capsule_dir / "notes.md")
            _write_jsonl(capsule_dir / "attempts_tail.jsonl", attempts)
            _write_jsonl(capsule_dir / "timeline_tail.jsonl", timeline)
            _write_jsonl(capsule_dir / "failures_tail.jsonl", failures)
        if lineage_events:
            _write_jsonl(capsule_dir / "lemma_lineage_tail.jsonl", lineage_events)
        if lineage_briefing:
            _write_json(capsule_dir / "lemma_lineage_briefing.json", lineage_briefing)
            _copy_if_exists(
                run_dir / "lemma_lineage_briefing.md",
                capsule_dir / "lemma_lineage_briefing.md",
            )
        if checkpoint_payload:
            _write_json(capsule_dir / "checkpoint_state.json", checkpoint_payload)

        handoff_artifacts = {
            "latest_workspace_view": "latest_workspace_view.json",
            "latest_followup": "latest_followup.md",
            "attempts_tail": "attempts_tail.jsonl",
            "timeline_tail": "timeline_tail.jsonl",
        }
        if lineage_events:
            handoff_artifacts["lemma_lineage_tail"] = "lemma_lineage_tail.jsonl"
        if lineage_briefing:
            handoff_artifacts["lemma_lineage_briefing"] = (
                "lemma_lineage_briefing.json"
            )
            if (capsule_dir / "lemma_lineage_briefing.md").exists():
                handoff_artifacts["lemma_lineage_briefing_md"] = (
                    "lemma_lineage_briefing.md"
                )
        if checkpoint_payload:
            handoff_artifacts["checkpoint_state"] = "checkpoint_state.json"
        manifest = {
            "kind": CAPSULE_KIND,
            "capsule_version": CAPSULE_VERSION,
            "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "target": {
                "file": target_file,
                "lemma": lemma,
                "include_dir": include_dir,
            },
            "source": {
                "commit": _git_commit(project_root),
                "run_dir": str(run_dir),
                "session_dir": str(session_dir),
                "session_name": session_dir.name,
                "node_memory_dir": str(memory_dir) if memory_dir else "",
                "node_id": node_id,
            },
            "replay": {
                "history_file": "history.ec",
                "transaction_file": "transactions.json",
                "transaction_count": len(transactions),
                "tactic_count": len(history),
                "resume_prefix_count": resume_prefix_count,
                "current_goal_hash": goal_hash,
                "proof_status": goal_identity.proof_status,
                "goal_identity_required": (
                    goal_identity.goal_identity_required
                ),
                "current_goal_file": goal_file,
                "current_goal_preview": goal_preview,
            },
            "score": {
                "value": score,
                "reasons": reasons,
            },
            "lineage": {
                "route_family": route_family,
            },
            "handoff": {
                "notes": notes,
                "recent_tactics": recent_tactics,
                "route_event_facts": route_event_facts[-12:],
                "artifacts": handoff_artifacts,
                "mode": "proof-node-resume",
                "note": (
                    "This capsule resumes an interrupted managed proof node. "
                    "Do not mix resumed success with from-scratch eval metrics."
                ),
                **(
                    {"continuation_brief": continuation_brief}
                    if continuation_brief
                    else {}
                ),
            },
        }
        manifest_path = capsule_dir / "resume.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        created.append((score, manifest_path))

    created.sort(key=lambda item: item[0], reverse=True)
    candidates = [
        resume_route_candidate_from_manifest(
            path=str(path),
            manifest=_read_json(path),
            fallback_score=score,
        )
        for score, path in created
    ]
    diversity_index = build_resume_diversity_index(candidates)
    index = {
        "kind": "proof_node_resume_capsule_index",
        "capsule_version": CAPSULE_VERSION,
        "target": {"file": target_file, "lemma": lemma, "include_dir": include_dir},
        "capsules": [
            candidate.to_dict() for candidate in candidates
        ],
        "route_diversity": diversity_index,
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    _write_json(output_dir / "resume_route_diversity.json", diversity_index)
    (output_dir / "resume_route_diversity.md").write_text(
        resume_diversity_markdown(diversity_index),
        encoding="utf-8",
    )
    _attach_resume_diversity_handoff(
        candidates=candidates,
        diversity_index=diversity_index,
    )
    return [str(path) for _, path in created]


def _resolve_manifest(path: str | Path) -> Path:
    manifest_path = Path(path).expanduser()
    if manifest_path.is_dir():
        manifest_path = manifest_path / "resume.json"
    return manifest_path.resolve()


def load_resume_capsule(path: str | Path) -> ProofNodeResumeCapsule:
    """Load a proof-node resume capsule."""

    manifest_path = _resolve_manifest(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("kind") != CAPSULE_KIND:
        raise ValueError(f"not a proof-node resume capsule: {manifest_path}")
    if (
        type(data.get("capsule_version")) is not int
        or data.get("capsule_version") != CAPSULE_VERSION
    ):
        raise ValueError(
            f"unsupported resume capsule version in {manifest_path}: "
            f"{data.get('capsule_version')}"
        )

    root = manifest_path.parent
    replay = _dict(data.get("replay"))
    target = _dict(data.get("target"))
    source = _dict(data.get("source"))
    score = _dict(data.get("score"))
    lineage = _dict(data.get("lineage"))
    handoff = _dict(data.get("handoff"))
    if (
        "resume_prefix_count" not in replay
        or type(replay.get("resume_prefix_count")) is not int
        or replay.get("resume_prefix_count") < 0
    ):
        raise ValueError(
            f"current resume capsule {manifest_path} requires a non-negative "
            "integer replay.resume_prefix_count"
        )
    if (
        "route_event_facts" not in handoff
        or not isinstance(handoff.get("route_event_facts"), list)
    ):
        raise ValueError(
            f"current resume capsule {manifest_path} requires list field "
            "handoff.route_event_facts"
        )
    route_family = _dict(lineage.get("route_family"))
    source_node_id = source.get("node_id")
    if not _is_canonical_node_id(source_node_id):
        source_node_id = None
    history_file = root / str(replay.get("history_file") or "history.ec")
    replay_prefix = _history_commands(history_file)
    transaction_file_name = str(replay.get("transaction_file") or "").strip()
    if transaction_file_name:
        transaction_payload = _read_json(root / transaction_file_name)
        raw_transactions = transaction_payload.get("transactions")
        if (
            transaction_payload.get("kind") != "proof_replay_transactions"
            or transaction_payload.get("schema_version") != 1
            or not isinstance(raw_transactions, list)
            or any(type(item) is not str or not item.strip() for item in raw_transactions)
        ):
            raise ValueError(
                f"current resume capsule {manifest_path} has invalid "
                "replay transaction artifact"
            )
        replay_transactions = [str(item).strip() for item in raw_transactions]
        if (
            transaction_payload.get("command_count") != len(replay_prefix)
            or transaction_payload.get("transaction_count") != len(replay_transactions)
            or replay.get("transaction_count") != len(replay_transactions)
            or flatten_committed_transactions(replay_transactions) != replay_prefix
        ):
            raise ValueError(
                f"current resume capsule {manifest_path} has replay "
                "transaction/history mismatch"
            )
    else:
        # Version-2 capsules minted before transaction-boundary preservation
        # remain loadable; each already-split command is its own transaction.
        replay_transactions = list(replay_prefix)
    checkpoint_path = root / "checkpoint_state.json"
    raw_checkpoint_payload = _read_json(checkpoint_path)
    if checkpoint_path.is_file() and not raw_checkpoint_payload:
        raise ValueError(
            f"current resume capsule {manifest_path} has invalid "
            "checkpoint_state.json"
        )
    if (
        raw_checkpoint_payload and source_node_id is None
    ):
        raise ValueError(
            f"current resume capsule {manifest_path} requires source.node_id "
            "to bind node-owned sidecars"
        )
    checkpoint_payload = _current_checkpoint_payload(
        raw_checkpoint_payload,
        expected_node_id=source_node_id,
    )
    if raw_checkpoint_payload and not checkpoint_payload:
        raise ValueError(
            f"current resume capsule {manifest_path} has invalid or "
            "misbound checkpoint_state.json"
        )
    route_event_facts: list[dict[str, Any]] = []
    for index, item in enumerate(handoff["route_event_facts"]):
        if not isinstance(item, dict):
            raise ValueError(
                f"current resume capsule {manifest_path} has invalid "
                f"handoff.route_event_facts[{index}]"
            )
        try:
            normalized = require_resume_route_event(
                item,
                label=f"handoff.route_event_facts[{index}]",
            )
        except ValueError as exc:
            raise ValueError(
                f"current resume capsule {manifest_path} has invalid "
                f"handoff.route_event_facts[{index}]: {exc}"
            ) from exc
        route_event_facts.append(normalized)
    resume_prefix_count = replay["resume_prefix_count"]
    resume_context = {
        "resume_prefix_count": resume_prefix_count,
        "replay_transactions": replay_transactions,
        "checkpoint_payload": checkpoint_payload,
        "route_event_facts": route_event_facts,
    }
    raw_continuation_brief = handoff.get("continuation_brief")
    if raw_continuation_brief is not None:
        resume_context["continuation_brief"] = normalize_continuation_brief(
            raw_continuation_brief
        )

    goal_hash = str(replay.get("current_goal_hash") or "")
    proof_status = str(replay.get("proof_status") or "unknown")
    raw_identity_required = replay.get("goal_identity_required")
    if type(raw_identity_required) is not bool:
        raise ValueError(
            f"current resume capsule {manifest_path} requires boolean field "
            "replay.goal_identity_required"
        )
    goal_identity_required = raw_identity_required
    if goal_identity_required and not goal_hash:
        raise ValueError(
            f"current resume capsule {manifest_path} requires non-empty field "
            "replay.current_goal_hash for an open proof"
        )
    if not goal_identity_required and goal_hash:
        raise ValueError(
            f"current resume capsule {manifest_path} requires empty field "
            "replay.current_goal_hash for a closed proof"
        )
    if not goal_identity_required and not has_discharged_goals(proof_status):
        raise ValueError(
            f"current resume capsule {manifest_path} may omit the goal "
            "identity only for a canonically closed proof state"
        )

    return ProofNodeResumeCapsule(
        path=manifest_path,
        target_file=str(target.get("file") or ""),
        lemma=str(target.get("lemma") or ""),
        include_dir=str(target.get("include_dir") or ""),
        commit=str(source.get("commit") or ""),
        session_name=str(source.get("session_name") or source.get("node_id") or root.name),
        replay_prefix=replay_prefix,
        replay_transactions=replay_transactions,
        current_goal_hash=goal_hash,
        proof_status=proof_status,
        goal_identity_required=goal_identity_required,
        current_goal_preview=str(replay.get("current_goal_preview") or ""),
        current_goal_path=str((root / str(replay.get("current_goal_file") or "")).resolve())
        if replay.get("current_goal_file")
        else "",
        score=float(score.get("value") or 0.0),
        reasons=[str(item) for item in list(score.get("reasons") or [])],
        handoff_notes=[str(item) for item in list(handoff.get("notes") or [])],
        recent_tactics=[
            dict(item) for item in list(handoff.get("recent_tactics") or [])
            if isinstance(item, dict)
        ],
        route_family=str(route_family.get("family") or ""),
        resume_diversity=_dict(lineage.get("resume_diversity")),
        resume_prefix_count=resume_prefix_count,
        resume_context=resume_context,
        recorded_tactic_count=_safe_int(replay.get("tactic_count")),
    )


def normalize_resume_root_policy(policy: str | None) -> str:
    value = str(policy or RESUME_ROOT_POLICY_SCORE).strip().lower()
    if value not in RESUME_ROOT_POLICIES:
        raise ValueError(
            "unsupported resume root policy "
            f"{policy!r}; expected one of {sorted(RESUME_ROOT_POLICIES)}"
        )
    return value


def order_resume_capsules(
    capsules: list[ProofNodeResumeCapsule],
    *,
    policy: str | None = RESUME_ROOT_POLICY_SCORE,
) -> list[ProofNodeResumeCapsule]:
    policy = normalize_resume_root_policy(policy)
    if policy == RESUME_ROOT_POLICY_DIVERSITY:
        return _order_resume_capsules_by_diversity(capsules)
    return sorted(
        capsules,
        key=lambda c: (c.score, c.tactic_count),
        reverse=True,
    )


def _order_resume_capsules_by_diversity(
    capsules: list[ProofNodeResumeCapsule],
) -> list[ProofNodeResumeCapsule]:
    candidates = [
        ResumeRouteCandidate(
            path=str(capsule.path),
            score=capsule.score,
            tactic_count=capsule.tactic_count,
            route_family=(
                {"family": capsule.route_family}
                if capsule.route_family else {}
            ),
        )
        for capsule in capsules
    ]
    diversity_index = build_resume_diversity_index(candidates)
    rank_by_path = {
        str(item.get("path") or ""): index
        for index, item in enumerate(
            list(diversity_index.get("diversity_order") or [])
        )
        if isinstance(item, dict)
    }
    return sorted(
        capsules,
        key=lambda capsule: (
            rank_by_path.get(str(capsule.path), len(capsules)),
            -capsule.score,
            -capsule.tactic_count,
        ),
    )


def load_resume_capsules(
    paths: list[str | Path],
    *,
    policy: str | None = RESUME_ROOT_POLICY_SCORE,
) -> list[ProofNodeResumeCapsule]:
    capsules = [load_resume_capsule(path) for path in paths]
    return order_resume_capsules(capsules, policy=policy)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or inspect proof-node resume capsules.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    create = sub.add_parser("create", help="Create capsules from live .ec_session_* dirs.")
    create.add_argument("--project-root", default=".")
    create.add_argument("--run-dir", required=True)
    create.add_argument("--target-file", required=True)
    create.add_argument("--lemma", required=True)
    create.add_argument("--include-dir", default="")
    create.add_argument("--output-dir", default="")
    create.add_argument("--session-dir", action="append", required=True)

    show = sub.add_parser("show", help="Print loaded capsule summaries.")
    show.add_argument("paths", nargs="+")
    show.add_argument(
        "--policy",
        choices=sorted(RESUME_ROOT_POLICIES),
        default=RESUME_ROOT_POLICY_SCORE,
        help=(
            "Capsule ordering policy: score preserves current behavior; "
            "diversity interleaves route families."
        ),
    )

    args = parser.parse_args(argv)
    if args.cmd == "create":
        paths = create_resume_capsules(
            project_root=Path(args.project_root),
            run_dir=Path(args.run_dir),
            target_file=args.target_file,
            lemma=args.lemma,
            include_dir=args.include_dir,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            session_dirs=[Path(p) for p in args.session_dir],
        )
        print(json.dumps({"capsules": paths}, indent=2))
        return 0

    capsules = load_resume_capsules(args.paths, policy=args.policy)
    rows = [
        {
            "path": str(capsule.path),
            "session": capsule.session_name,
            "tactics": capsule.tactic_count,
            "score": capsule.score,
            "route_family": capsule.route_family,
            "goal_hash": capsule.current_goal_hash,
            "notes": capsule.handoff_notes[:3],
        }
        for capsule in capsules
    ]
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
