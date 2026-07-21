"""Proof-node resume capsules for manager-owned prover runs.

A resume capsule is a durable handoff for an interrupted managed proof node.
It is intentionally centered on the current architecture:

- the accepted EasyCrypt prefix in the node-owned session history
- the latest manager/node_memory workspace view
- recent failures and accepted manager outcomes

Capsules use ``resume.json`` and can be created from live ``.ec_session_*``
directories before the next prover launch wipes them.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from core.easycrypt.committed_history import read_committed_tactics
from core.easycrypt.analysis.probability_budget import analyze_probability_budget
from workflow.context_intents import intent_is_retrieval, is_context_topic_intent
from workflow.proof_management.repair_notes import rewind_note_summary
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
from core.easycrypt.value_shapes import as_dict as _dict


CAPSULE_VERSION = 1
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
    current_goal_hash: str
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


def _history_tactics(history_file: Path) -> list[str]:
    tactics: list[str] = []
    for raw in _read_text(history_file).splitlines():
        line = raw.strip()
        if line:
            tactics.append(line)
    return tactics


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



def _intent_kind(item: dict[str, Any]) -> str:
    return str(_dict(item.get("intent")).get("intent") or "")


def _intent_tactic(item: dict[str, Any]) -> str:
    payload = _dict(_dict(item.get("intent")).get("payload"))
    return str(payload.get("tactic") or "").strip()


def _intent_topic(item: dict[str, Any]) -> str:
    payload = _dict(_dict(item.get("intent")).get("payload"))
    return str(payload.get("topic") or payload.get("symbol") or "")


def _actions_text(item: dict[str, Any]) -> str:
    pieces: list[str] = []
    for action in list(item.get("manager_actions") or []):
        if not isinstance(action, dict):
            continue
        for key in ("action", "outcome", "error_summary"):
            value = action.get(key)
            if value:
                pieces.append(str(value))
    return " ".join(pieces)


def _attempt_status(item: dict[str, Any]) -> str:
    intent = _intent_kind(item)
    text = _actions_text(item).lower()
    if "rejected" in text or "invalid" in text or "error" in text:
        return "failed"
    if "accepted" in text:
        return "accepted"
    if intent_is_retrieval(intent):
        return "read_only_context"
    return "unknown"


def _route_event_facts_from_rows(
    timeline: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = timeline if timeline else attempts
    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in rows[-80:]:
        event = _route_event_fact_from_row(item)
        if not event:
            continue
        key = (
            str(item.get("turn") or ""),
            str(event.get("intent") or ""),
            str(event.get("tactic") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        events.append(event)
    return events[-40:]


def _route_event_fact_from_row(item: dict[str, Any]) -> dict[str, Any]:
    intent_obj = _dict(item.get("intent"))
    intent = str(intent_obj.get("intent") or "").strip()
    payload = _dict(intent_obj.get("payload"))
    if not intent:
        return {}
    tactic = str(payload.get("tactic") or "").strip()
    action_text = _actions_text(item)
    lower = action_text.lower()
    error_summary = _action_error_summary(item)
    accepted = (
        "accepted" in lower
        and "rejected" not in lower
        and not error_summary
    )
    rejected = bool(error_summary) or "rejected" in lower
    changed = (
        intent in {
            "commit_tactic",
            "commit_replay_suffix_chunk",
            "undo_last_step",
            "undo_to_checkpoint",
            "fresh_restart",
        }
        and bool(item.get("ok", True))
        and not rejected
    )
    return _compact_dict({
        "intent": intent,
        "payload": payload,
        "tactic": tactic,
        "tactic_head": _tactic_head(tactic),
        "topic": payload.get("topic"),
        "symbol": payload.get("symbol"),
        "accepted": accepted,
        "rejected": rejected,
        "changed": changed,
        "error_summary": error_summary,
        "status": _attempt_status(item),
    })


def _action_error_summary(item: dict[str, Any]) -> str:
    for action in list(item.get("manager_actions") or []):
        if isinstance(action, dict) and action.get("error_summary"):
            return str(action.get("error_summary") or "").strip()
    return ""


def _tactic_head(tactic: str) -> str:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", str(tactic or "").strip())
    return match.group(1).lower() if match else ""


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


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


def _recent_tactics(attempts: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in attempts:
        intent = _intent_kind(item)
        tactic = _intent_tactic(item)
        if (
            not tactic
            and intent not in {"inspect_context", "lookup_symbol"}
            and not is_context_topic_intent(intent)
        ):
            continue
        row: dict[str, Any] = {
            "turn": item.get("turn"),
            "time": item.get("time"),
            "intent": intent,
            "status": _attempt_status(item),
        }
        if tactic:
            row["tactic"] = tactic
        else:
            row["topic"] = _intent_topic(item)
        action_text = _actions_text(item)
        if action_text:
            row["outcome"] = _truncate(action_text, 220)
        out.append(row)
    return out[-limit:]


def _resume_prefix_count_from_handoff(
    *,
    view: dict[str, Any],
    timeline: list[dict[str, Any]],
    history_count: int,
) -> int:
    # Internal capsule reconstruction (never agent-facing). The replayed-prefix
    # length is recovered from the INTERNAL bootstrap timeline entry. For
    # backward-compatibility with LEGACY capsules saved before the agent-facing
    # surface stopped emitting a resume marker, we also still read a legacy
    # `resume_start` marker if a stale handoff view carries one — this is a
    # read-only internal compat shim; current surfaces never emit it.
    structural = _dict(view.get("structural_checkpoints"))
    for item in list(structural.get("items") or []):
        if not isinstance(item, dict):
            continue
        semantic_ids = {
            str(value)
            for value in list(item.get("semantic_ids") or [])
            if str(value).strip()
        }
        if str(item.get("semantic_id") or ""):
            semantic_ids.add(str(item.get("semantic_id") or ""))
        if "resume_start" not in semantic_ids:
            continue
        try:
            index = int(item.get("committed_step_index") or 0)
        except (TypeError, ValueError):
            index = 0
        if index > 0:
            return min(max(0, index - 1), max(0, history_count))
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


def _goal_text_from_view(view: dict[str, Any]) -> str:
    return _goal_preview_from_view(view, "")


def _goal_hash_from_memory(memory_dir: Path) -> str:
    for item in reversed(_read_jsonl_tail(memory_dir / "timeline.jsonl", limit=40)):
        value = item.get("goal_hash")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _goal_hash_from_session(session_dir: Path) -> str:
    try:
        from core.easycrypt.session_projection import read_proof_state_projection

        projection = read_proof_state_projection(session_dir)
        value = projection.goal.active_goal_hash
        if value:
            return value
    except Exception:
        pass
    current_out = _read_text(session_dir / "current.out")
    return hashlib.sha256(current_out.encode("utf-8")).hexdigest() if current_out else ""


def _node_slug_from_session_dir(session_dir: Path) -> str:
    name = session_dir.name
    match = re.search(r"tree_((?:\d+_)*\d+)$", name)
    if match:
        return f"Tree_{match.group(1)}"
    meta = _read_json(session_dir / "session_meta.json")
    node = str(meta.get("node") or meta.get("node_id") or "")
    if node:
        return node.replace("-", "_").replace(".", "_")
    return name.replace(".", "_").replace("-", "_")


def _node_memory_for_session(run_dir: Path, session_dir: Path) -> Path | None:
    node_memory_root = run_dir / "node_memory"
    slug = _node_slug_from_session_dir(session_dir)
    candidates = [
        node_memory_root / slug,
        node_memory_root / slug.replace("_", "."),
        node_memory_root / slug.replace("_", "-"),
    ]
    if slug.startswith("Tree_"):
        parts = slug.split("_")
        if len(parts) >= 3:
            candidates.append(node_memory_root / f"Tree-{parts[1]}.{'.'.join(parts[2:])}")
            candidates.append(node_memory_root / "_".join(parts))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _lineage_tail_for_node(run_dir: Path, node_slug: str) -> list[dict[str, Any]]:
    rows = _read_jsonl_tail(run_dir / "lemma_lineage.jsonl", limit=160)
    if not node_slug:
        return rows[-40:]
    aliases = {
        node_slug,
        node_slug.replace("_", "."),
        node_slug.replace("_", "-"),
    }
    return [
        row for row in rows
        if str(row.get("node") or "") in aliases
    ][-40:]


def _node_slug_aliases(node_slug: str) -> list[str]:
    """Spellings under which a node's memory files may be keyed on disk.

    The capsule builder derives slugs from SESSION DIR names
    (``.ec_session_prover_tree_0_0`` -> ``Tree_0_0``), but the manager-side
    stores (``ProofMemoryManager``/``ProofCheckpointManager``) key their files
    by NODE ID (``Tree-0.0`` -> ``Tree-0.0_route_replay_memory.json``). A
    lookup using only the session-derived spelling silently misses the file —
    observed 2026-06-11 on upto_X1_X2: the dead node's verifier-checked route
    chunks never made it into the Layer-3 capsule, so the respawned child
    re-derived ~90 tactics by hand. Mirror ``_node_memory_for_session``'s
    alias set so both naming families resolve.
    """
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(node_slug or ""))
    if not slug:
        return []
    aliases = [slug]
    parts = slug.split("_")
    if slug.startswith("Tree_") and len(parts) >= 3:
        aliases.append(f"Tree-{parts[1]}.{'.'.join(parts[2:])}")
    aliases.append(slug.replace("_", "."))
    aliases.append(slug.replace("_", "-"))
    seen: set[str] = set()
    out: list[str] = []
    for alias in aliases:
        if alias and alias not in seen:
            seen.add(alias)
            out.append(alias)
    return out


def _route_memory_payload_for_node(run_dir: Path, node_slug: str) -> dict[str, Any]:
    for slug in _node_slug_aliases(node_slug):
        current = _read_json(
            run_dir / "route_memory" / f"{slug}_route_replay_memory.json"
        )
        if current:
            return current
        legacy = _read_json(
            run_dir / "route_memory" / f"{slug}_rewind_route_memory.json"
        )
        if legacy:
            return legacy
    return {}


def _checkpoint_payload_for_node(run_dir: Path, node_slug: str) -> dict[str, Any]:
    for slug in _node_slug_aliases(node_slug):
        payload = _read_json(
            run_dir / "checkpoint_state" / f"{slug}_checkpoint_state.json"
        )
        if payload:
            return payload
    return {}


def _verified_route_options_for_session(
    session_dir: Path,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = _read_jsonl_tail(
        session_dir / "route_options" / "verified_route_options.jsonl",
        limit=limit,
    )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if (
            row.get("kind") != "verified_route_option"
            or row.get("confidence") != "verified"
        ):
            continue
        submit = _dict(row.get("submit"))
        payload = _dict(submit.get("payload"))
        tactic = str(payload.get("tactic") or "").strip()
        if submit.get("intent") != "commit_tactic" or not tactic:
            continue
        key = str(row.get("option_id") or tactic)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out[-limit:]


def _verified_route_option_handoff_notes(
    options: list[dict[str, Any]],
) -> list[str]:
    if not options:
        return []
    notes = [
        "Verified route options before resume: "
        f"{len(options)} daemon-checked manager option(s) available; "
        "re-check the current goal preconditions before committing."
    ]
    for item in options[-2:]:
        topic = str(item.get("topic") or "route_option")
        objective = str(item.get("semantic_objective") or "").strip()
        bindings = _dict(item.get("bindings"))
        binding_text = (
            "; bindings="
            + json.dumps(bindings, ensure_ascii=False, sort_keys=True)
            if bindings else ""
        )
        option_id = str(item.get("option_id") or "")
        notes.append(
            "Saved verified option "
            + _truncate(
                f"{option_id or topic}: {objective}{binding_text}",
                420,
            )
            + "."
        )
    return notes[:3]


def _legacy_checkpoint_payload_from_view(view: dict[str, Any]) -> dict[str, Any]:
    structural = _dict(view.get("structural_checkpoints"))
    for item in list(structural.get("items") or []):
        if not isinstance(item, dict):
            continue
        semantic_ids = {
            str(value)
            for value in list(item.get("semantic_ids") or [])
            if str(value).strip()
        }
        if str(item.get("semantic_id") or ""):
            semantic_ids.add(str(item.get("semantic_id") or ""))
        if "restore_before_last_rewind" not in semantic_ids:
            continue
        option = dict(item)
        option.pop("submit", None)
        option["legacy_resume_surface"] = True
        option["effect_if_selected"] = (
            "Legacy capsule preserved this restore marker without the full "
            "pre-rewind tactic payload, so it is continuity evidence only."
        )
        return {
            "schema_version": 1,
            "kind": "legacy_checkpoint_state",
            "legacy_pre_rewind_restore_option": option,
        }
    return {}


def _legacy_route_memory_payload_from_view(view: dict[str, Any]) -> dict[str, Any]:
    surface = _dict(view.get("route_replay_memory"))
    if not surface:
        surface = _dict(view.get("rewind_route_memory"))
    if not surface:
        return {}
    return {
        "schema_version": 1,
        "kind": "legacy_route_replay_memory",
        "source": "latest_workspace_view",
        "legacy_route_replay_memory": surface,
    }


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
    lineage_events: list[dict[str, Any]] | None = None,
    lineage_briefing: dict[str, Any] | None = None,
    route_memory_payload: dict[str, Any] | None = None,
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

    last_result = _dict(view.get("last_result"))
    structural = _dict(last_result.get("structural_transition"))
    recommended = _dict(structural.get("recommended_next"))
    submit = _dict(recommended.get("submit"))
    payload = _dict(submit.get("payload"))
    tactic = str(payload.get("tactic") or structural.get("tactic") or "").strip()
    if tactic:
        notes.append(
            "The last view offered an accepted structural transition; if the "
            "replayed view still matches, consider committing exactly: "
            f"{tactic}"
        )

    notes.extend(_probability_budget_event_bridge_notes(view))
    notes.extend(_lineage_briefing_handoff_notes(
        dict(lineage_briefing or {}),
    ))
    notes.extend(_repair_memory_handoff_notes(
        lineage_events=list(lineage_events or []),
        route_memory_payload=dict(route_memory_payload or {}),
    ))
    notes.extend(_route_health_handoff_notes(view))

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
                f" proved={winner.get('proved')}"
                if "proved" in winner else ""
            )
        )
    if not pieces:
        pieces.append(
            f"{briefing.get('node_count', 0)} node(s), "
            f"{briefing.get('repair_episode_count', 0)} repair episode(s)"
        )
    return [
        "Run lineage before resume: "
        + _truncate("; ".join(piece for piece in pieces if piece), 420)
        + "."
    ]


def _repair_memory_handoff_notes(
    *,
    lineage_events: list[dict[str, Any]],
    route_memory_payload: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    repair_events = [
        item for item in lineage_events
        if item.get("kind") == "repair_episode_recorded"
    ]
    for item in repair_events[-2:]:
        note = rewind_note_summary(item.get("rewind_note"))
        pieces: list[str] = []
        checkpoint = str(item.get("from_checkpoint_id") or "").strip()
        tactic_index = item.get("from_tactic_index")
        if checkpoint:
            pieces.append(f"checkpoint `{checkpoint}`")
        if tactic_index not in (None, ""):
            pieces.append(f"tactic_index={tactic_index}")
        hypothesis = str(note.get("hypothesis") or "").strip()
        boundary = str(note.get("broken_boundary_kind") or "").strip()
        intended = str(note.get("intended_repair") or "").strip()
        missing = list(note.get("missing_facts") or [])
        message = (
            "Repair memory before resume: previous branch rewound"
            + (f" from {', '.join(pieces)}" if pieces else "")
            + (f" because {hypothesis}" if hypothesis else "")
            + (f" ({boundary})" if boundary else "")
            + "."
        )
        if missing:
            message += " Missing facts: " + _truncate(", ".join(str(x) for x in missing), 180) + "."
        if intended:
            message += " Intended repair: " + _truncate(intended, 180) + "."
        replay_counts = _dict(item.get("replay_class_counts"))
        if replay_counts:
            message += " Discarded pieces by class: " + json.dumps(
                replay_counts, ensure_ascii=False, sort_keys=True
            ) + "."
        notes.append(_truncate(message, 520))

    route_memories = _route_memories_from_payload(route_memory_payload)
    if route_memories:
        latest = route_memories[0]
        suffix = list(latest.get("discarded_suffix") or [])
        chunks = list(latest.get("structural_chunks") or [])
        note = rewind_note_summary(latest.get("rewind_note"))
        reuse = str(note.get("reuse_expectation") or "").strip()
        message = (
            f"Route replay memory available: {len(route_memories)} saved route(s); "
            f"latest discarded suffix has {len(suffix)} tactic(s)"
            + (f" and {len(chunks)} verifier-checkable chunk(s)" if chunks else "")
            + ". The manager validates replay chunks before committing them."
        )
        if reuse:
            message += " Reuse expectation: " + _truncate(reuse, 180) + "."
        notes.append(_truncate(message, 420))

    for memory in _negative_memories_from_payload(route_memory_payload)[:3]:
        avoid = str(memory.get("avoid_pattern") or "").strip()
        reason = str(memory.get("reason") or "").strip()
        if avoid:
            notes.append(
                "Negative proof memory before resume: avoid repeating "
                f"`{avoid}`"
                + (f" because {_truncate(reason, 220)}" if reason else "")
                + "."
            )
    return notes[:6]


def _route_memories_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    route_memories = list(payload.get("route_memories") or [])
    if not route_memories:
        tree = _dict(payload.get("route_memory_snapshot"))
        route_memories = list(tree.get("route_memories") or [])
    if not route_memories:
        route_memories = list(payload.get("memories") or [])
    return [dict(item) for item in route_memories if isinstance(item, dict)]


def _negative_memories_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    negative = list(payload.get("negative_memories") or [])
    if not negative:
        tree = _dict(payload.get("route_memory_snapshot"))
        negative = list(tree.get("negative_memories") or [])
    return [dict(item) for item in negative if isinstance(item, dict)]


def _probability_budget_event_bridge_notes(view: dict[str, Any]) -> list[str]:
    budget = _dict(_dict(view.get("facts_and_diagnostics")).get("probability_budget"))
    bridge = _dict(budget.get("event_bound_bridge"))
    if not bridge:
        goal_text = _goal_text_from_view(view)
        if goal_text:
            budget = analyze_probability_budget(goal_text)
            bridge = _dict(budget.get("event_bound_bridge"))
    if not bridge:
        return []
    notes: list[str] = []
    collection = str(bridge.get("event_collection") or "")
    size_bound = _dict(bridge.get("size_bound"))
    fact = str(size_bound.get("fact") or "")
    if collection or fact:
        notes.append(
            "Event-bound bridge at resume: "
            + _truncate(
                (
                    f"membership in `{collection}`"
                    if collection else "membership event"
                )
                + (f" with visible `{fact}`" if fact else "")
                + "; inspect list-size times point-mass lemmas before more local sampling.",
                320,
            )
        )
    for lemma in list(bridge.get("candidate_lemma_handles") or [])[:2]:
        if not isinstance(lemma, dict):
            continue
        symbol = str(lemma.get("symbol") or "")
        why = str(lemma.get("why") or "")
        if symbol:
            notes.append(
                "Useful event-bound lookup at resume: "
                f"`{symbol}`" + (f" - {_truncate(why, 180)}" if why else "")
            )
    return notes[:3]


def _route_health_handoff_notes(view: dict[str, Any]) -> list[str]:
    candidate_moves = _dict(view.get("candidate_moves"))
    notes: list[str] = []
    for item in list(candidate_moves.get("route_health") or []):
        if not isinstance(item, dict):
            continue
        signal = str(item.get("signal") or "")
        message = str(item.get("message") or "")
        if signal == "lost_call_abstraction_boundary":
            if message:
                notes.append("Route health before interruption: " + _truncate(message, 240))
            checkpoint = _dict(item.get("repair_checkpoint"))
            label = str(checkpoint.get("label") or "")
            if label:
                notes.append(
                    "Call-boundary recovery checkpoint before resume: "
                    + _truncate(label, 120)
                    + "; inspect call_site_options after rewinding."
                )
            continue
    return notes[:6]


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
        if diversity_summary:
            handoff["resume_diversity"] = diversity_summary
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
    session_dirs: list[Path] | None = None,
    output_dir: Path | None = None,
) -> list[str]:
    """Create resume capsules from live managed session dirs and node memory."""

    project_root = project_root.resolve()
    run_dir = run_dir.resolve()
    output_dir = (output_dir or (run_dir / "resume_capsules")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if session_dirs is None:
        session_dirs = sorted(project_root.glob(".ec_session_prover_tree_*"))
    else:
        session_dirs = [Path(p).expanduser() for p in session_dirs]

    created: list[tuple[float, Path]] = []
    for session_dir in session_dirs:
        session_dir = session_dir.resolve()
        if not session_dir.is_dir():
            continue
        history = read_committed_tactics(session_dir)
        if not history:
            continue
        memory_dir = _node_memory_for_session(run_dir, session_dir)
        view = _latest_workspace_view(memory_dir) if memory_dir else {}
        current_out = _read_text(session_dir / "current.out", max_chars=20000)
        goal_preview = _goal_preview_from_view(view, current_out)
        goal_hash = _goal_hash_from_session(session_dir)
        if not goal_hash and memory_dir:
            goal_hash = _goal_hash_from_memory(memory_dir)

        node_slug = _node_slug_from_session_dir(session_dir)
        lineage_events = _lineage_tail_for_node(run_dir, node_slug)
        lineage_briefing = _lineage_briefing_payload(run_dir)
        route_memory_payload = _route_memory_payload_for_node(run_dir, node_slug)
        if not route_memory_payload:
            route_memory_payload = _legacy_route_memory_payload_from_view(view)
        checkpoint_payload = _checkpoint_payload_for_node(run_dir, node_slug)
        if not checkpoint_payload:
            checkpoint_payload = _legacy_checkpoint_payload_from_view(view)
        verified_route_options = _verified_route_options_for_session(session_dir)
        route_family = infer_route_family(history, view=view).to_dict()
        attempts = _read_jsonl_tail(memory_dir / "attempts.jsonl", limit=80) if memory_dir else []
        timeline = _read_jsonl_tail(memory_dir / "timeline.jsonl", limit=80) if memory_dir else []
        failures = _read_jsonl_tail(memory_dir / "failures.jsonl", limit=40) if memory_dir else []
        route_event_facts = _route_event_facts_from_rows(timeline, attempts)
        resume_prefix_count = _resume_prefix_count_from_handoff(
            view=view,
            timeline=timeline,
            history_count=len(history),
        )
        latest_followup = _read_text(memory_dir / "latest_followup.md", max_chars=12000) if memory_dir else ""
        notes = _capsule_notes(
            view=view,
            latest_followup=latest_followup,
            lineage_events=lineage_events,
            lineage_briefing=lineage_briefing,
            route_memory_payload=route_memory_payload,
            route_family=route_family,
        )
        route_option_notes = _verified_route_option_handoff_notes(
            verified_route_options
        )
        notes = [*route_option_notes, *notes][:10]
        recent_tactics = _recent_tactics(attempts, limit=16)
        score, reasons = _score_capsule(
            history=history,
            view=view,
            route_family=route_family,
        )

        rank_name = f"{node_slug}_{session_dir.name}".replace("/", "_")
        capsule_dir = output_dir / rank_name
        capsule_dir.mkdir(parents=True, exist_ok=True)
        _copy_if_exists(session_dir / "history.ec", capsule_dir / "history.ec")
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
        if route_memory_payload:
            _write_json(capsule_dir / "route_memory.json", route_memory_payload)
        if checkpoint_payload:
            _write_json(capsule_dir / "checkpoint_state.json", checkpoint_payload)
        if verified_route_options:
            _write_jsonl(
                capsule_dir / "verified_route_options.jsonl",
                verified_route_options,
            )

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
        if route_memory_payload:
            handoff_artifacts["route_memory"] = "route_memory.json"
        if checkpoint_payload:
            handoff_artifacts["checkpoint_state"] = "checkpoint_state.json"
        if verified_route_options:
            handoff_artifacts["verified_route_options"] = (
                "verified_route_options.jsonl"
            )

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
                "node_slug": node_slug,
            },
            "replay": {
                "history_file": "history.ec",
                "tactic_count": len(history),
                "resume_prefix_count": resume_prefix_count,
                "current_goal_hash": goal_hash,
                "current_goal_file": goal_file,
                "current_goal_preview": goal_preview,
            },
            "score": {
                "value": score,
                "reasons": reasons,
                "route_family": route_family,
            },
            "lineage": {
                "route_family": route_family,
            },
            "handoff": {
                "notes": notes,
                "recent_tactics": recent_tactics,
                "route_event_facts": route_event_facts[-12:],
                "verified_route_options": [
                    {
                        "option_id": item.get("option_id"),
                        "topic": item.get("topic"),
                        "semantic_objective": item.get("semantic_objective"),
                        "bindings": item.get("bindings"),
                    }
                    for item in verified_route_options[-5:]
                    if isinstance(item, dict)
                ],
                "artifacts": handoff_artifacts,
                "mode": "proof-node-resume",
                "note": (
                    "This capsule resumes an interrupted managed proof node. "
                    "Do not mix resumed success with from-scratch eval metrics."
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
    if int(data.get("capsule_version", 0)) != CAPSULE_VERSION:
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
    route_family = _dict(score.get("route_family"))
    if not route_family:
        route_family = _dict(lineage.get("route_family"))
    history_file = root / str(replay.get("history_file") or "history.ec")
    replay_prefix = _history_tactics(history_file)
    latest_workspace_view = _read_json(root / "latest_workspace_view.json")
    route_memory_payload = _read_json(root / "route_memory.json")
    if not route_memory_payload:
        route_memory_payload = _legacy_route_memory_payload_from_view(
            latest_workspace_view
        )
    checkpoint_payload = _read_json(root / "checkpoint_state.json")
    if not checkpoint_payload:
        checkpoint_payload = _legacy_checkpoint_payload_from_view(latest_workspace_view)
    attempts = _read_jsonl_tail(root / "attempts_tail.jsonl", limit=80)
    timeline = _read_jsonl_tail(root / "timeline_tail.jsonl", limit=80)
    verified_route_options = _read_jsonl_tail(
        root / "verified_route_options.jsonl",
        limit=20,
    )
    if not verified_route_options:
        verified_route_options = [
            dict(item)
            for item in list(handoff.get("verified_route_options") or [])
            if isinstance(item, dict)
        ]
    route_event_facts = [
        dict(item)
        for item in list(handoff.get("route_event_facts") or [])
        if isinstance(item, dict)
    ]
    if not route_event_facts:
        route_event_facts = _route_event_facts_from_rows(timeline, attempts)
    resume_prefix_count = _safe_int(replay.get("resume_prefix_count"))
    if resume_prefix_count <= 0:
        resume_prefix_count = _resume_prefix_count_from_handoff(
            view=latest_workspace_view,
            timeline=timeline,
            history_count=len(replay_prefix),
        )
    resume_context = {
        "resume_prefix_count": resume_prefix_count,
        "latest_workspace_view": latest_workspace_view,
        "route_memory_payload": route_memory_payload,
        "checkpoint_payload": checkpoint_payload,
        "route_event_facts": route_event_facts,
        "verified_route_options": verified_route_options,
    }

    return ProofNodeResumeCapsule(
        path=manifest_path,
        target_file=str(target.get("file") or ""),
        lemma=str(target.get("lemma") or ""),
        include_dir=str(target.get("include_dir") or ""),
        commit=str(source.get("commit") or ""),
        session_name=str(source.get("session_name") or source.get("node_slug") or root.name),
        replay_prefix=replay_prefix,
        current_goal_hash=str(replay.get("current_goal_hash") or ""),
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
        resume_diversity=_dict(
            handoff.get("resume_diversity")
        ) or _dict(lineage.get("resume_diversity")),
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
    create.add_argument("--session-dir", action="append", default=[])

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
            session_dirs=[Path(p) for p in args.session_dir] if args.session_dir else None,
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
