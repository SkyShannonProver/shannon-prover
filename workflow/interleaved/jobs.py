#!/usr/bin/env python3
"""Nonblocking, bounded Shannon jobs for the interleaved outer agent.

The outer agent never backgrounds ``run_shannon.py`` itself.  ``submit``
records an immutable input snapshot and starts (or queues) a detached worker.
Each worker proves in a separate sparse worktree.  ``collect`` is the sole
owner allowed to merge a verified lemma proof into the canonical outer target.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from core.easycrypt.eval_source_prep import find_target_proof_block
from core.easycrypt.lemma_decls import lemma_decl_matches
from workflow.interleaved.agent_config import (
    agent_profile_sha256,
    PROFILE_PATH,
    profile_for,
    provider_identity_projection,
    provider_identity_sha256,
)
from workflow.interleaved.inner_runner import (
    GUIDANCE_ITEMS_MAX,
    GUIDANCE_TEXT_MAX_CHARS,
    INVOCATION_RECEIPT_KIND,
    INVOCATION_RECEIPT_SCHEMA_VERSION,
    LEMMA,
    PARTIAL_PREFIX_MAX_BYTES,
    RECEIPT_ENV,
    RECEIPT_SHA256_ENV,
    TARGET,
    run_directory,
)
from workflow.interleaved.resume_contract import (
    CHECKPOINT_KIND,
    CHECKPOINT_SCHEMA_VERSION,
    CONTINUATION_NOTE_MAX_CHARS,
    checkpoint_projection,
    directory_content_sha256,
)
from workflow.interleaved.warm_handoff import (
    _lemma_prefix_projection,
)
from workflow.interleaved.runtime import load_runtime_settings
from workflow.interleaved.verify import check_import_with_project_verifier
from workflow.node.proof_node_resume import load_resume_capsule
from workflow.tree.supervisor import (
    MANAGED_LIVE_PROGRESS_FILENAME,
    MANAGED_LIVE_PROGRESS_KIND,
    MANAGED_LIVE_PROGRESS_SCHEMA_VERSION,
)


_SETTINGS = load_runtime_settings()
ROOT = _SETTINGS.root
TARGET = _SETTINGS.project.target_file
ANSWER_SOURCE = _SETTINGS.answer_source or ROOT / ".interleaved-no-answer-source"
CONFINED_PATTERNS = _SETTINGS.confined_patterns
MAX_PARALLEL = _SETTINGS.project.max_parallel
MAX_INNER_MINUTES = _SETTINGS.project.max_inner_minutes
WORKER_HEARTBEAT_INTERVAL_SECONDS = 1.0
WORKER_HEARTBEAT_STALE_SECONDS = 15.0
WORKER_HEARTBEAT_KIND = "interleaved_shannon_worker_heartbeat"
INNER_SAFE_STOP_GRACE_SECONDS = 75.0
WORKER_SAFE_STOP_GRACE_SECONDS = 85.0
MAX_CONTINUATION_ANCESTORS = 64
INNER_PROVIDER_ENV = "INTERLEAVED_INNER_PROVIDER"
INNER_PROVIDER_IDENTITY_ENV = "INTERLEAVED_INNER_PROVIDER_IDENTITY_JSON"
JOB_ID = re.compile(r"^[a-f0-9]{16}$")
ACTIVE_STATUSES = frozenset({"starting", "running", "cancelling"})
BOUNDARY_LEASE_STATUSES = ACTIVE_STATUSES | frozenset({"queued"})
RESULT_STATUSES = frozenset({
    "verified",
    "incomplete",
    "infrastructure_invalid",
})
TERMINAL_STATUSES = RESULT_STATUSES | frozenset({
    "cancelled",
    "merged",
    "stale_merge",
})
FINAL_TARGET_LEMMA = _SETTINGS.project.final_lemma
SCRATCHPAD_BEGIN = _SETTINGS.project.delegation_region_begin
SCRATCHPAD_END = _SETTINGS.project.delegation_region_end


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _expected_provider_identity(
    *,
    profile: Any,
) -> dict[str, str]:
    raw_identity = os.environ.get(INNER_PROVIDER_IDENTITY_ENV, "").strip()
    try:
        value = json.loads(raw_identity)
    except json.JSONDecodeError as exc:
        raise ValueError("fixed inner provider identity is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("fixed inner provider identity must be a JSON object")
    identity = provider_identity_projection(value)
    if (
        identity["agent_backend"] != profile.backend
        or identity["model"] != profile.model
    ):
        raise ValueError("selected inner provider identity does not match its profile")
    return identity


def _invocation_receipt(
    *,
    record: dict[str, Any],
    run_rel: Path,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": INVOCATION_RECEIPT_SCHEMA_VERSION,
        "kind": INVOCATION_RECEIPT_KIND,
        "job_id": record["job_id"],
        "run_directory": run_rel.as_posix(),
        "lemma": record["lemma"],
        "timeout_minutes": record["timeout_minutes"],
        "source_commit": record["source_commit"],
        "target_sha256": record["source_contract"]["target_sha256"],
        "agent_profiles_sha256": record["agent_profiles_sha256"],
        "inner_profile_sha256": record["inner_profile_sha256"],
        "inner_agent": record["inner_agent"],
        "expected_provider_identity": record["expected_provider_identity"],
        "has_resource_anchors": bool(record.get("has_resource_anchors")),
        "resource_anchors_sha256": str(
            record.get("resource_anchors_sha256") or ""
        ),
        "has_resume_checkpoint": bool(record.get("resume_from_job_id")),
        "resume_from_job_id": str(record.get("resume_from_job_id") or ""),
        "resume_from_run_directory": str(
            record.get("resume_from_run_directory") or ""
        ),
        "resume_checkpoint_id": str(record.get("resume_checkpoint_id") or ""),
        "resume_checkpoint_directory_sha256": str(
            record.get("resume_checkpoint_directory_sha256") or ""
        ),
        "has_continuation_note": bool(record.get("has_continuation_note")),
        "continuation_note_sha256": str(
            record.get("continuation_note_sha256") or ""
        ),
    }
    receipt["content_sha256"] = _sha256_bytes(_canonical_json_bytes(receipt))
    return receipt


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _jobs_root(run_dir: Path) -> Path:
    root = run_dir / "shannon_jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _job_dir(run_dir: Path, job_id: str) -> Path:
    if JOB_ID.fullmatch(job_id) is None:
        raise ValueError("invalid Shannon job id")
    return _jobs_root(run_dir) / job_id


def _record_path(run_dir: Path, job_id: str) -> Path:
    return _job_dir(run_dir, job_id) / "job.json"


def _latest_terminal_sequence(run_dir: Path) -> int:
    latest = 0
    for path in _jobs_root(run_dir).glob("*/job.json"):
        try:
            item = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        latest = max(latest, int(item.get("terminal_event_sequence") or 0))
    return latest


def _load_job(run_dir: Path, job_id: str) -> dict[str, Any]:
    path = _record_path(run_dir, job_id)
    if not path.is_file():
        raise ValueError(f"unknown Shannon job: {job_id}")
    record = _read_json(path)
    if record.get("schema_version") != 1 or record.get("job_id") != job_id:
        raise ValueError(f"invalid Shannon job record: {job_id}")
    return record


def _save_job(run_dir: Path, record: dict[str, Any]) -> None:
    path = _record_path(run_dir, str(record["job_id"]))
    prior_status = ""
    if path.is_file():
        try:
            prior_status = str(_read_json(path).get("status") or "")
        except (OSError, ValueError, json.JSONDecodeError):
            prior_status = ""
    status = str(record.get("status") or "")
    if status in TERMINAL_STATUSES and status != prior_status:
        sequence = _latest_terminal_sequence(run_dir) + 1
        at = _now()
        event = {
            "schema_version": 1,
            "kind": "interleaved_shannon_terminal_event",
            "sequence": sequence,
            "at": at,
            "job_id": str(record["job_id"]),
            "lemma": str(record.get("lemma") or ""),
            "status": status,
            "previous_status": prior_status,
        }
        event["event_id"] = _sha256_bytes(_canonical_json_bytes(event))
        record["terminal_event_sequence"] = sequence
        record["terminal_event_at"] = at
        record["terminal_event_id"] = event["event_id"]
    _atomic_json(path, record)


def _all_jobs(run_dir: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for path in sorted(_jobs_root(run_dir).glob("*/job.json")):
        record = _read_json(path)
        if (
            record.get("schema_version") != 1
            or record.get("job_id") != path.parent.name
        ):
            raise ValueError(f"invalid Shannon job record: {path}")
        jobs.append(record)
    return sorted(jobs, key=lambda item: str(item.get("created_at") or ""))


@contextmanager
def _registry_lock(run_dir: Path) -> Iterator[None]:
    identity = hashlib.sha256(str(run_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    path = Path("/tmp") / f"interleaved-shannon-jobs-{identity}.lock"
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def _proof_body_span(content: str, lemma: str) -> tuple[str, tuple[int, int]]:
    block = find_target_proof_block(content, lemma)
    if block is None:
        raise ValueError(f"could not find proof block for {lemma}")
    start, end = block
    block_text = content[start:end]
    # Keep formatting between ``proof.`` and ``qed.`` inside the proof body.
    # Shannon may indent its first tactic differently from the outer admit
    # shell without changing any declaration or suffix byte.
    proof = re.search(r"(?i)\bproof\s*\.", block_text)
    qed = list(re.finditer(r"(?i)\bqed\s*\.", block_text))
    if proof is None or not qed or qed[-1].start() < proof.end():
        raise ValueError(f"{lemma} has no proof./qed. block")
    body_start = start + proof.end()
    body_end = start + qed[-1].start()
    return content[body_start:body_end], (body_start, body_end)


def _source_contract(content: str, lemma: str) -> dict[str, str]:
    body, _ = _proof_body_span(content, lemma)
    return {
        "target_sha256": _sha256_text(content),
        "lemma_prefix_sha256": _sha256_text(
            _lemma_prefix_projection(content, lemma)
        ),
        "proof_body_sha256": _sha256_text(body),
    }


def _resume_source_contract_matches(
    parent: dict[str, object],
    current: dict[str, str],
    *,
    allow_proof_body_change: bool = False,
) -> bool:
    """Bind resume to the selected lemma while permitting suffix-only work.

    The full target digest is an audit identity for each individual job, but it
    is intentionally not the proof-state compatibility boundary.  Outer work
    may add or edit independent declarations after the delegated lemma while a
    Shannon lane is running.  Such suffix changes cannot affect replay of the
    selected lemma; the manager still replays the checkpoint and verifies its
    exact residual goal identity before admitting a resumed agent turn.
    """

    keys = ["lemma_prefix_sha256"]
    if not allow_proof_body_change:
        keys.append("proof_body_sha256")
    for key in keys:
        parent_value = str(parent.get(key) or "")
        current_value = str(current.get(key) or "")
        if (
            re.fullmatch(r"[0-9a-f]{64}", parent_value) is None
            or re.fullmatch(r"[0-9a-f]{64}", current_value) is None
            or parent_value != current_value
        ):
            return False
    return True


def _active_boundary_violations(
    jobs: list[dict[str, Any]],
    current_source: str,
) -> list[dict[str, object]]:
    """Report outer edits that invalidate a live Shannon proof boundary."""

    violations: list[dict[str, object]] = []
    for record in jobs:
        status = str(record.get("status") or "")
        if status not in BOUNDARY_LEASE_STATUSES:
            continue
        job_id = str(record.get("job_id") or "")
        lemma = str(record.get("lemma") or "")
        submitted = dict(record.get("source_contract") or {})
        changed: list[str] = []
        try:
            current = _source_contract(current_source, lemma)
        except ValueError:
            current = {}
            changed.append("lemma_boundary_unavailable")
        if current:
            if current.get("lemma_prefix_sha256") != submitted.get(
                "lemma_prefix_sha256"
            ):
                changed.append("lemma_prefix")
            if current.get("proof_body_sha256") != submitted.get(
                "proof_body_sha256"
            ):
                changed.append("proof_body")
        if not changed:
            continue
        violations.append({
            "schema_version": 1,
            "kind": "interleaved_shannon_active_boundary_violation",
            "authority": "scheduler_submission_source_contract",
            "job_id": job_id,
            "lemma": lemma,
            "status": status,
            "changed": changed,
            "message": (
                f"active Shannon boundary changed for {lemma} ({job_id}); "
                "restore the submitted lemma/prefix and edit only declarations "
                "after that lemma until the job is terminal"
            ),
        })
    return violations


def _raise_for_active_boundary_violations(
    jobs: list[dict[str, Any]],
    current_source: str,
) -> None:
    violations = _active_boundary_violations(jobs, current_source)
    if not violations:
        return
    first = violations[0]
    raise ValueError(str(first["message"]))


def _lemma_claim_projection(content: str, lemma: str) -> str:
    matches = lemma_decl_matches(content, lemma)
    proof = find_target_proof_block(content, lemma)
    if len(matches) != 1 or proof is None or matches[0].end() >= proof[0]:
        raise ValueError(f"could not project the unique claim for {lemma}")
    claim = content[matches[0].end() : proof[0]]
    claim = re.sub(r"&[A-Za-z_][A-Za-z0-9_']*", "&MEM", claim)
    return re.sub(r"\s+", " ", claim).strip()


def _require_outer_decomposition_boundary(content: str, lemma: str) -> None:
    """Require Shannon work to target an outer-authored scratchpad helper."""

    if lemma == FINAL_TARGET_LEMMA:
        raise ValueError(
            f"final target {FINAL_TARGET_LEMMA} cannot be delegated to Shannon; "
            "decompose it into a scratchpad helper lemma first"
        )
    if SCRATCHPAD_BEGIN:
        begin = content.find(SCRATCHPAD_BEGIN)
        end = content.find(SCRATCHPAD_END, begin + len(SCRATCHPAD_BEGIN))
        if begin < 0 or end < 0:
            raise ValueError("configured delegation region markers are missing")
        delegation_region = content[begin + len(SCRATCHPAD_BEGIN) : end]
    else:
        delegation_region = content
    # Share declaration recognition with claim projection and proof writeback:
    # local/multiline declarations and named judgment forms are valid helpers;
    # commented-out declarations are not delegation evidence.
    matches = lemma_decl_matches(delegation_region, lemma)
    if len(matches) != 1:
        raise ValueError(
            "Shannon target must be exactly one outer-defined helper lemma in "
            "the configured delegation region"
        )
    if _lemma_claim_projection(content, lemma) == _lemma_claim_projection(
        content,
        FINAL_TARGET_LEMMA,
    ):
        raise ValueError(
            f"scratchpad helper claim duplicates final target {FINAL_TARGET_LEMMA}; "
            "decompose a proper subclaim before invoking Shannon"
        )


def _valid_source_breadcrumb(value: object) -> bool:
    if not isinstance(value, dict) or value.get("tool") not in {
        "read", "search", "resolve",
    }:
        return False
    allowed = {
        "tool", "path", "query", "scope", "requested", "resolved",
        "status", "start_line", "end_line", "match_count", "locations",
    }
    if set(value) - allowed:
        return False
    if any(
        not isinstance(value[key], str) or len(value[key]) > limit
        for key, limit in (
            ("path", 1_000), ("query", 256), ("scope", 16),
            ("requested", 256), ("resolved", 512), ("status", 32),
        )
        if key in value
    ):
        return False
    if any(
        isinstance(value[key], bool)
        or not isinstance(value[key], int)
        or value[key] < 0
        for key in ("start_line", "end_line", "match_count")
        if key in value
    ):
        return False
    locations = value.get("locations")
    return locations is None or (
        isinstance(locations, list)
        and len(locations) <= 8
        and all(isinstance(item, str) and len(item) <= 1_200 for item in locations)
    )


def _validated_progress(
    value: object,
    *,
    lemma: str,
    terminal_status: str,
) -> dict[str, Any]:
    """Validate the bounded, public continuation capsule from the wrapper."""

    if not isinstance(value, dict):
        raise ValueError("incomplete Shannon result lacks a progress capsule")
    if (
        value.get("schema_version") != 2
        or value.get("kind") != "interleaved_shannon_progress_capsule"
        or value.get("lemma") != lemma
        or not isinstance(value.get("turns"), int)
        or value["turns"] < 0
        or not isinstance(value.get("elapsed_seconds"), (int, float))
        or value["elapsed_seconds"] < 0
    ):
        raise ValueError("invalid Shannon progress capsule")

    accepted = value.get("accepted_prefix")
    if accepted is not None:
        if (
            not isinstance(accepted, dict)
            or not isinstance(accepted.get("tactic_count"), int)
            or accepted["tactic_count"] <= 0
            or not isinstance(accepted.get("byte_count"), int)
            or accepted["byte_count"] <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", str(accepted.get("sha256") or ""))
            or accepted.get("authority")
            != "manager_committed_history_reporting_artifact"
            or accepted.get("replay_required_before_use") is not True
        ):
            raise ValueError("invalid accepted-prefix progress evidence")
        text = accepted.get("text")
        omitted = accepted.get("text_omitted_reason")
        if text is not None:
            if (
                not isinstance(text, str)
                or len(text.encode("utf-8")) > PARTIAL_PREFIX_MAX_BYTES
                or len(text.encode("utf-8")) != accepted["byte_count"]
                or _sha256_text(text) != accepted["sha256"]
                or re.search(r"(?i)\b(?:admit|qed)\s*\.", text)
            ):
                raise ValueError(
                    "accepted-prefix progress text does not match its hash"
                )
        elif not isinstance(omitted, str) or not omitted:
            raise ValueError(
                "accepted-prefix text is missing without an omission reason"
            )

    guidance = value.get("agent_guidance")
    if guidance is not None:
        if (
            not isinstance(guidance, dict)
            or guidance.get("authority") != "untrusted_inner_agent_report"
        ):
            raise ValueError("invalid incomplete Shannon agent guidance")
        for key in ("blockers", "discoveries"):
            items = guidance.get(key)
            if items is not None and (
                not isinstance(items, list)
                or len(items) > GUIDANCE_ITEMS_MAX
                or any(not isinstance(item, str) for item in items)
                or any(len(item) > GUIDANCE_TEXT_MAX_CHARS for item in items)
            ):
                raise ValueError("invalid incomplete Shannon guidance items")

    source_breadcrumbs = value.get("source_breadcrumbs")
    if source_breadcrumbs is not None:
        if (
            not isinstance(source_breadcrumbs, dict)
            or source_breadcrumbs.get("authority")
            != "manager_observed_source_navigation"
            or not isinstance(source_breadcrumbs.get("items"), list)
            or not 1 <= len(source_breadcrumbs["items"]) <= 12
            or any(
                not _valid_source_breadcrumb(item)
                for item in source_breadcrumbs["items"]
            )
        ):
            raise ValueError("invalid incomplete Shannon source breadcrumbs")

    checkpoint = value.get("checkpoint")
    if checkpoint is not None:
        if (
            not isinstance(checkpoint, dict)
            or checkpoint.get("schema_version") != CHECKPOINT_SCHEMA_VERSION
            or checkpoint.get("kind") != CHECKPOINT_KIND
            or checkpoint.get("authority") != "manager_owned_resume_capsule"
            or checkpoint.get("continuation_available") is not True
            or not isinstance(checkpoint.get("tactic_count"), int)
            or checkpoint["tactic_count"] <= 0
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(checkpoint.get("checkpoint_id") or "")
            )
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(checkpoint.get("accepted_prefix_sha256") or ""),
            )
        ):
            raise ValueError("invalid managed Shannon checkpoint")
        goal = checkpoint.get("goal")
        if (
            not isinstance(goal, dict)
            or goal.get("identity_required") is not True
            or not isinstance(goal.get("identity"), str)
            or not goal["identity"]
            or len(goal["identity"]) > 128
            or not isinstance(goal.get("proof_status"), str)
            or not isinstance(goal.get("preview"), str)
            or len(goal["preview"]) > 6000
        ):
            raise ValueError("invalid managed Shannon residual goal")
        if accepted is None or checkpoint["tactic_count"] > accepted["tactic_count"]:
            raise ValueError("managed checkpoint exceeds the accepted prefix")
        lag = accepted["tactic_count"] - checkpoint["tactic_count"]
        if lag == 0:
            if checkpoint["accepted_prefix_sha256"] != accepted["sha256"]:
                raise ValueError(
                    "managed checkpoint is not bound to accepted prefix"
                )
            if value.get("uncheckpointed_tail_tactics") not in {None, 0}:
                raise ValueError("exact checkpoint reports an uncheckpointed tail")
        elif value.get("uncheckpointed_tail_tactics") != lag:
            raise ValueError("managed checkpoint lag is not explicitly reported")
        rejection = checkpoint.get("boundary_rejection")
        if rejection is not None and (
            not isinstance(rejection, dict)
            or rejection.get("status") not in {"rejected", "no_progress"}
            or not isinstance(rejection.get("tactic"), str)
            or len(rejection["tactic"]) > 2000
        ):
            raise ValueError("invalid managed Shannon boundary rejection")
    raw_tail = value.get("uncheckpointed_tail_tactics")
    if raw_tail is not None and (
        not isinstance(raw_tail, int) or isinstance(raw_tail, bool) or raw_tail <= 0
    ):
        raise ValueError("invalid uncheckpointed-tail tactic count")
    if checkpoint is None and raw_tail is not None:
        raise ValueError("uncheckpointed tail requires a managed checkpoint")

    next_actions = value.get("next_actions")
    allowed_actions = {
        "resume_checkpoint",
        "replay_prefix_in_outer",
        "warm_handoff",
        "fresh_restart",
        "redesign_boundary",
    }
    if (
        not isinstance(next_actions, list)
        or not next_actions
        or any(action not in allowed_actions for action in next_actions)
    ):
        raise ValueError("invalid Shannon progress next actions")

    terminal = value.get("terminal")
    if (
        not isinstance(terminal, dict)
        or terminal.get("status") != terminal_status
        or not isinstance(terminal.get("cause"), str)
        or not terminal["cause"]
        or not isinstance(terminal.get("message"), str)
        or len(terminal["message"]) > 2000
    ):
        raise ValueError("invalid Shannon progress terminal cause")

    if (
        accepted is None
        and guidance is None
        and not isinstance(value.get("summary"), str)
    ):
        raise ValueError("empty Shannon progress capsule")
    return dict(value)


def _validated_live_progress(
    value: object,
    *,
    lemma: str,
) -> dict[str, Any]:
    """Validate the manager-owned, text-free projection used by ``status``."""

    if not isinstance(value, dict):
        raise ValueError("managed live progress must be a JSON object")
    if (
        value.get("schema_version") != MANAGED_LIVE_PROGRESS_SCHEMA_VERSION
        or value.get("kind") != MANAGED_LIVE_PROGRESS_KIND
        or value.get("authority")
        != "tree_supervisor_manager_observer_projection"
        or value.get("lemma") != lemma
        or value.get("phase") not in {"proof_search", "finalizing"}
    ):
        raise ValueError("invalid managed live-progress identity")
    for key in (
        "accepted_tactic_count",
        "checkpoint_tactic_count",
        "inner_turns",
        "active_nodes",
    ):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ValueError(f"invalid managed live-progress field: {key}")
    if value["checkpoint_tactic_count"] > value["accepted_tactic_count"]:
        # A stale checkpoint may legitimately be deeper after an intentional
        # rewind, but presenting it as current live progress would mislead the
        # outer agent. Keep the public projection monotone in authority.
        raise ValueError("managed live checkpoint exceeds the accepted prefix")
    for key, required in (("observed_at", True), ("last_progress_at", False)):
        item = value.get(key)
        if not isinstance(item, str) or (required and not item):
            raise ValueError(f"invalid managed live-progress timestamp: {key}")
        if item:
            try:
                datetime.fromisoformat(item.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(
                    f"invalid managed live-progress timestamp: {key}"
                ) from exc
    if value["accepted_tactic_count"] == 0 and value["last_progress_at"]:
        raise ValueError("zero accepted tactics cannot report accepted progress")
    allowed = {
        "schema_version",
        "kind",
        "authority",
        "lemma",
        "phase",
        "accepted_tactic_count",
        "checkpoint_tactic_count",
        "inner_turns",
        "active_nodes",
        "last_progress_at",
        "observed_at",
    }
    if set(value) - allowed:
        raise ValueError("managed live progress contains unknown fields")
    return dict(value)


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    public = {
        key: record.get(key)
        for key in (
            "schema_version",
            "job_id",
            "lemma",
            "status",
            "created_at",
            "started_at",
            "finished_at",
            "merged_at",
            "timeout_minutes",
            "warm_handoff",
            "has_resource_anchors",
            "has_continuation_note",
            "pid",
            "queue_position",
            "wrapper_exit_code",
            "prover_result_id",
            "error",
            "failure_class",
            "failure_message",
            "collect_status",
            "collect_verification_scope",
            "resume_from_job_id",
            "resume_from_run_directory",
            "resume_checkpoint_id",
            "terminal_event_sequence",
            "terminal_event_at",
            "terminal_event_id",
        )
        if record.get(key) not in {None, ""}
    }
    if record.get("status") == "infrastructure_invalid":
        message = str(record.get("error") or "missing_terminal_failure_reason")
        public.setdefault("failure_class", "scheduler_infrastructure_invalid")
        public.setdefault("failure_message", message[:4000])
        public["error"] = message[:4000]
    if isinstance(record.get("progress"), dict):
        public["progress"] = record["progress"]
    if (
        record.get("status") in ACTIVE_STATUSES
        and isinstance(record.get("live_progress"), dict)
    ):
        public["live_progress"] = record["live_progress"]
    return public


def public_job_summary(run_dir: Path) -> dict[str, Any]:
    with _registry_lock(run_dir):
        jobs = _all_jobs(run_dir)
    counts: dict[str, int] = {}
    for item in jobs:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "schema_version": 1,
        "max_parallel": MAX_PARALLEL,
        "terminal_cursor": _latest_terminal_sequence(run_dir),
        "counts": counts,
        "jobs": [_public_record(item) for item in jobs],
    }
    violations = _active_boundary_violations(
        jobs,
        (ROOT / TARGET).read_text(encoding="utf-8"),
    )
    if violations:
        summary["active_boundary_violations"] = violations
    return summary


def private_job_records(run_dir: Path) -> list[dict[str, Any]]:
    """Return scheduler-owned records for runner finalization, never the outer CLI."""

    with _registry_lock(run_dir):
        return _all_jobs(run_dir)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _worker_heartbeat_path(run_dir: Path, job_id: str) -> Path:
    return _job_dir(run_dir, job_id) / "worker_heartbeat.json"


def _write_worker_heartbeat(
    run_dir: Path,
    *,
    job_id: str,
    pid: int,
    phase: str,
) -> None:
    _atomic_json(
        _worker_heartbeat_path(run_dir, job_id),
        {
            "schema_version": 1,
            "kind": WORKER_HEARTBEAT_KIND,
            "job_id": job_id,
            "pid": int(pid),
            "phase": str(phase),
            "updated_at_epoch": time.time(),
        },
    )


def _worker_heartbeat_is_fresh(
    run_dir: Path,
    record: dict[str, Any],
    *,
    now_epoch: float | None = None,
) -> bool:
    job_id = str(record.get("job_id") or "")
    pid = int(record.get("pid") or 0)
    if JOB_ID.fullmatch(job_id) is None or pid <= 0:
        return False
    try:
        heartbeat = _read_json(_worker_heartbeat_path(run_dir, job_id))
        updated_at = float(heartbeat.get("updated_at_epoch"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False
    if (
        heartbeat.get("schema_version") != 1
        or heartbeat.get("kind") != WORKER_HEARTBEAT_KIND
        or heartbeat.get("job_id") != job_id
        or heartbeat.get("pid") != pid
    ):
        return False
    age = float(time.time() if now_epoch is None else now_epoch) - updated_at
    return -5.0 <= age <= WORKER_HEARTBEAT_STALE_SECONDS


def _worker_alive(run_dir: Path, record: dict[str, Any]) -> bool:
    """Check a worker across both shared and isolated PID namespaces."""

    pid = int(record.get("pid") or 0)
    return _pid_alive(pid) or _worker_heartbeat_is_fresh(run_dir, record)


def _reconcile_locked(run_dir: Path) -> None:
    for record in _all_jobs(run_dir):
        if record.get("status") not in ACTIVE_STATUSES:
            continue
        if _worker_alive(run_dir, record):
            continue
        if record.get("status") == "cancelling":
            record["status"] = "infrastructure_invalid"
            record["error"] = (
                "cancelled worker exited before safe-stop checkpoint "
                "finalization completed"
            )
        else:
            record["status"] = "infrastructure_invalid"
            record["error"] = (
                "detached Shannon worker exited without a terminal result"
            )
        record["finished_at"] = _now()
        _save_job(run_dir, record)


def _dispatch_locked(*, run_rel: Path, run_dir: Path) -> None:
    _reconcile_locked(run_dir)
    jobs = _all_jobs(run_dir)
    # Do not start another queued lane while the outer source violates any
    # existing live proof-boundary lease.  Public status/wait/verifier calls
    # project the concrete violation so the outer can restore the boundary.
    if _active_boundary_violations(
        jobs,
        (ROOT / TARGET).read_text(encoding="utf-8"),
    ):
        return
    active = sum(item.get("status") in ACTIVE_STATUSES for item in jobs)
    capacity = MAX_PARALLEL - active
    if capacity <= 0:
        return
    queued = [item for item in jobs if item.get("status") == "queued"]
    for record in queued[:capacity]:
        job_id = str(record["job_id"])
        job_dir = _job_dir(run_dir, job_id)
        stdout = (job_dir / "worker.stdout.log").open("a", encoding="utf-8")
        stderr = (job_dir / "worker.stderr.log").open("a", encoding="utf-8")
        environment = os.environ.copy()
        environment["INTERLEAVED_RUN_DIR"] = run_rel.as_posix()
        record["status"] = "starting"
        record["started_at"] = _now()
        _save_job(run_dir, record)
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "worker",
                    "--job-id",
                    job_id,
                ],
                cwd=ROOT,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        except BaseException as exc:
            record["status"] = "infrastructure_invalid"
            record["finished_at"] = _now()
            record["error"] = f"worker launch failed: {type(exc).__name__}: {exc}"
            _save_job(run_dir, record)
            raise
        finally:
            stdout.close()
            stderr.close()
        record["status"] = "running"
        record["pid"] = process.pid
        _save_job(run_dir, record)
        _write_worker_heartbeat(
            run_dir,
            job_id=job_id,
            pid=process.pid,
            phase="dispatched",
        )


def _resolve_same_run_file(run_dir: Path, raw: str, *, label: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must be a safe repository-relative path")
    resolved = (ROOT / relative).resolve()
    if not resolved.is_relative_to(run_dir.resolve()) or not resolved.is_file():
        raise ValueError(f"{label} must be an existing file in the current run")
    return resolved


def _resolve_candidate_file(run_dir: Path, raw: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("candidate source must be a safe repository-relative path")
    resolved = (ROOT / relative).resolve()
    allowed = [run_dir.resolve()]
    prior_raw = os.environ.get("INTERLEAVED_CONTINUATION_OF", "").strip()
    if prior_raw:
        prior = Path(prior_raw)
        if prior.is_absolute() or ".." in prior.parts:
            raise ValueError("disclosed continuation path is invalid")
        allowed.append((ROOT / prior).resolve())
    if not any(resolved.is_relative_to(directory) for directory in allowed):
        raise ValueError(
            "candidate source must be inside the current run or its disclosed "
            "continuation"
        )
    if not resolved.is_file():
        raise ValueError("candidate source must be an existing file")
    return resolved


def _disclosed_continuation_run_dir(run_dir: Path) -> tuple[Path, Path] | None:
    """Resolve the runner-bound prior run, including its frozen audit hashes."""

    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = _read_json(manifest_path)
    continuation = manifest.get("continuation")
    if not isinstance(continuation, dict):
        return None
    raw = str(continuation.get("run_directory") or "")
    relative = Path(raw)
    if not raw or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("disclosed continuation run directory is invalid")
    resolved = (ROOT / relative).resolve()
    allowed = (ROOT / "artifacts" / "interleaved_shannon").resolve()
    if not resolved.is_relative_to(allowed) or not resolved.is_dir():
        raise ValueError("disclosed continuation run directory is unavailable")
    prior_manifest = resolved / "manifest.json"
    prior_events = resolved / "outer_agent_events.jsonl"
    if not prior_manifest.is_file() or not prior_events.is_file():
        raise ValueError("disclosed continuation audit inputs are unavailable")
    if _sha256_bytes(prior_manifest.read_bytes()) != str(
        continuation.get("manifest_sha256") or ""
    ) or _sha256_bytes(prior_events.read_bytes()) != str(
        continuation.get("outer_events_sha256") or ""
    ):
        raise ValueError("disclosed continuation audit hash drifted")
    return relative, resolved


def _disclosed_continuation_run_chain(
    run_dir: Path,
) -> list[tuple[Path, Path]]:
    """Return every hash-linked ancestor, nearest first.

    Each hop is authorized only by the child run's frozen manifest/event
    hashes.  This lets a valid checkpoint survive an infrastructure-invalid
    continuation without weakening provenance to an artifact directory scan.
    """

    chain: list[tuple[Path, Path]] = []
    seen = {Path(run_dir).resolve()}
    current = Path(run_dir).resolve()
    for _ in range(MAX_CONTINUATION_ANCESTORS):
        disclosed = _disclosed_continuation_run_dir(current)
        if disclosed is None:
            return chain
        relative, resolved = disclosed
        canonical = resolved.resolve()
        if canonical in seen:
            raise ValueError("disclosed continuation chain contains a cycle")
        seen.add(canonical)
        chain.append((relative, canonical))
        current = canonical
    if _disclosed_continuation_run_dir(current) is not None:
        raise ValueError("disclosed continuation chain is too deep")
    return chain


def _resume_parent_run_dir(
    *,
    run_dir: Path,
    parent_job_id: str,
) -> tuple[Path | None, Path]:
    """Choose the current or explicitly disclosed prior scheduler namespace."""

    if _record_path(run_dir, parent_job_id).is_file():
        return None, run_dir
    for disclosed in _disclosed_continuation_run_chain(run_dir):
        if _record_path(disclosed[1], parent_job_id).is_file():
            return disclosed
    raise ValueError(f"unknown Shannon job: {parent_job_id}")


def _validate_prior_run_parent(
    *,
    parent_root: Path,
    parent: dict[str, Any],
    parent_run_rel: Path,
    artifact: Path,
) -> None:
    """Bind a copied checkpoint to its scheduler input and wrapper result."""

    job_id = str(parent["job_id"])
    lemma = str(parent["lemma"])
    receipt = parent.get("invocation_receipt")
    receipt_path = (
        parent_root
        / "lane_run_artifacts"
        / "job_input"
        / job_id
        / "invocation_receipt.json"
    )
    if not isinstance(receipt, dict) or not receipt_path.is_file():
        raise ValueError("prior-run resume job provenance is invalid")
    receipt_bytes = receipt_path.read_bytes()
    try:
        copied_receipt = json.loads(receipt_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError("prior-run invocation receipt is unreadable") from exc
    without_hash = dict(receipt)
    without_hash.pop("content_sha256", None)
    if (
        copied_receipt != receipt
        or _sha256_bytes(receipt_bytes)
        != str(parent.get("invocation_receipt_sha256") or "")
        or _sha256_bytes(_canonical_json_bytes(without_hash))
        != str(receipt.get("content_sha256") or "")
        or receipt.get("run_directory") != parent_run_rel.as_posix()
        or receipt.get("job_id") != job_id
        or receipt.get("lemma") != lemma
    ):
        raise ValueError("prior-run invocation receipt identity drifted")

    input_target = parent_root / "input" / "target.ec"
    if not input_target.is_file():
        raise ValueError("prior-run scheduler input is unavailable")
    input_bytes = input_target.read_bytes()
    if (
        _sha256_bytes(input_bytes) != str(receipt.get("target_sha256") or "")
        or _source_contract(input_bytes.decode("utf-8"), lemma)
        != dict(parent.get("source_contract") or {})
    ):
        raise ValueError("prior-run scheduler input identity drifted")

    wrapper_path = (
        parent_root
        / "lane_run_artifacts"
        / "shannon"
        / lemma
        / job_id
        / "wrapper_result.json"
    )
    if not wrapper_path.is_file():
        raise ValueError("prior-run wrapper result is unavailable")
    wrapper = _read_json(wrapper_path)
    wrapper_progress = wrapper.get("progress")
    wrapper_checkpoint = (
        wrapper_progress.get("checkpoint")
        if isinstance(wrapper_progress, dict)
        else None
    )
    raw_wrapper_artifact = str(wrapper.get("resume_checkpoint_artifact") or "")
    wrapper_artifact = (wrapper_path.parent / raw_wrapper_artifact).resolve()
    allowed_statuses = {str(parent.get("status") or "")}
    if parent.get("status") == "cancelled":
        allowed_statuses.add("incomplete")
    if (
        wrapper.get("kind") != "interleaved_shannon_wrapper_result"
        or wrapper.get("invocation_id") != job_id
        or wrapper.get("lemma") != lemma
        or wrapper.get("status") not in allowed_statuses
        or wrapper.get("invocation_receipt_sha256")
        != parent.get("invocation_receipt_sha256")
        or not isinstance(wrapper_checkpoint, dict)
        or wrapper_checkpoint.get("checkpoint_id")
        != parent.get("resume_checkpoint_id")
        or not raw_wrapper_artifact
        or wrapper_artifact != artifact
    ):
        raise ValueError("prior-run wrapper checkpoint authority drifted")


def _resume_parent_checkpoint(
    *,
    run_dir: Path,
    parent_job_id: str,
    lemma: str,
    source_contract: dict[str, str],
) -> tuple[dict[str, Any], Path, Path | None]:
    """Validate one scheduler-private checkpoint selected by public job id."""

    if JOB_ID.fullmatch(parent_job_id) is None:
        raise ValueError("resume job id is invalid")
    parent_run_rel, parent_run_dir = _resume_parent_run_dir(
        run_dir=run_dir,
        parent_job_id=parent_job_id,
    )
    parent = _load_job(parent_run_dir, parent_job_id)
    if parent.get("status") not in {
        "incomplete",
        "infrastructure_invalid",
        "cancelled",
    }:
        raise ValueError("resume requires a terminal job with partial progress")
    if parent.get("lemma") != lemma:
        raise ValueError("resume job lemma does not match the new submission")
    if not _resume_source_contract_matches(
        dict(parent.get("source_contract") or {}),
        source_contract,
        allow_proof_body_change=parent_run_dir.resolve() != run_dir.resolve(),
    ):
        raise ValueError(
            "resume source changed; use a fresh warm handoff from current source"
        )
    checkpoint_id = str(parent.get("resume_checkpoint_id") or "")
    raw_artifact = str(parent.get("resume_checkpoint_artifact") or "")
    claimed_digest = str(
        parent.get("resume_checkpoint_directory_sha256") or ""
    )
    relative = Path(raw_artifact)
    parent_root = _job_dir(parent_run_dir, parent_job_id).resolve()
    artifact = (parent_root / relative).resolve()
    if (
        not checkpoint_id
        or not raw_artifact
        or relative.is_absolute()
        or ".." in relative.parts
        or artifact.name != "resume.json"
        or not artifact.is_file()
        or not artifact.is_relative_to(parent_root)
        or directory_content_sha256(artifact.parent) != claimed_digest
    ):
        raise ValueError("resume job has no intact managed checkpoint")
    capsule = load_resume_capsule(artifact)
    projected, _ = checkpoint_projection(capsule)
    if projected.get("checkpoint_id") != checkpoint_id:
        raise ValueError("resume job checkpoint identity drifted")
    if parent_run_dir.resolve() != run_dir.resolve():
        if parent_run_rel is None:
            raise ValueError("prior-run resume job provenance is invalid")
        _validate_prior_run_parent(
            parent_root=parent_root,
            parent=parent,
            parent_run_rel=parent_run_rel,
            artifact=artifact,
        )
    return parent, artifact, parent_run_rel


def continuation_resume_options(
    prior_run_dir: Path,
    *,
    source_text: str,
) -> list[dict[str, Any]]:
    """Project intact prior-run checkpoints suitable for the current source."""

    options: list[dict[str, Any]] = []
    candidate_runs = [(None, prior_run_dir.resolve())]
    candidate_runs.extend(_disclosed_continuation_run_chain(prior_run_dir))
    for _, candidate_run_dir in candidate_runs:
        with _registry_lock(candidate_run_dir):
            jobs = _all_jobs(candidate_run_dir)
        for parent in jobs:
            option = _continuation_resume_option(
                candidate_run_dir,
                parent=parent,
                source_text=source_text,
            )
            if option is not None:
                options.append(option)
    return sorted(options, key=lambda item: (item["lemma"], -item["tactic_count"]))


def _continuation_resume_option(
    prior_run_dir: Path,
    *,
    parent: dict[str, Any],
    source_text: str,
) -> dict[str, Any] | None:
    """Validate and project one checkpoint from a trusted chain member."""

    job_id = str(parent.get("job_id") or "")
    lemma = str(parent.get("lemma") or "")
    if (
        parent.get("status") not in {
            "incomplete",
            "infrastructure_invalid",
            "cancelled",
        }
        or JOB_ID.fullmatch(job_id) is None
        or LEMMA.fullmatch(lemma) is None
    ):
        return None
    try:
        contract = _source_contract(source_text, lemma)
        if not _resume_source_contract_matches(
            dict(parent.get("source_contract") or {}),
            contract,
            allow_proof_body_change=True,
        ):
            return None
        raw_artifact = str(parent.get("resume_checkpoint_artifact") or "")
        relative = Path(raw_artifact)
        parent_root = _job_dir(prior_run_dir, job_id).resolve()
        artifact = (parent_root / relative).resolve()
        if (
            not raw_artifact
            or relative.is_absolute()
            or ".." in relative.parts
            or artifact.name != "resume.json"
            or not artifact.is_file()
            or not artifact.is_relative_to(parent_root)
            or directory_content_sha256(artifact.parent)
            != str(parent.get("resume_checkpoint_directory_sha256") or "")
        ):
            return None
        capsule = load_resume_capsule(artifact)
        projected, _ = checkpoint_projection(capsule)
        checkpoint_id = str(parent.get("resume_checkpoint_id") or "")
        if projected.get("checkpoint_id") != checkpoint_id:
            return None
        prior_rel = prior_run_dir.resolve().relative_to(ROOT.resolve())
        _validate_prior_run_parent(
            parent_root=parent_root,
            parent=parent,
            parent_run_rel=prior_rel,
            artifact=artifact,
        )
    except (OSError, ValueError, KeyError):
        return None
    return {
        "job_id": job_id,
        "lemma": lemma,
        "checkpoint_id": checkpoint_id,
        "tactic_count": int(projected.get("tactic_count") or 0),
    }


def submit_job(
    *,
    lemma: str,
    timeout_minutes: int,
    handoff_current: bool,
    strategy_note: str | None,
    resource_anchors: str | None = None,
    candidate_source: str | None = None,
    resume_job_id: str | None = None,
    continuation_note: str | None = None,
) -> dict[str, Any]:
    if LEMMA.fullmatch(lemma) is None:
        raise ValueError("lemma is not a valid EasyCrypt identifier")
    if lemma == FINAL_TARGET_LEMMA:
        raise ValueError(
            f"final target {FINAL_TARGET_LEMMA} cannot be delegated to Shannon; "
            "decompose it into a scratchpad helper lemma first"
        )
    if not 1 <= timeout_minutes <= MAX_INNER_MINUTES:
        raise ValueError(
            f"timeout must be between 1 and {MAX_INNER_MINUTES} minutes"
        )
    if handoff_current and not strategy_note:
        raise ValueError("warm handoff requires a strategy note")
    if resume_job_id and (
        handoff_current or strategy_note or resource_anchors or candidate_source
    ):
        raise ValueError(
            "managed checkpoint resume is exclusive with a fresh warm handoff"
        )
    if continuation_note and not resume_job_id:
        raise ValueError("continuation note requires a managed checkpoint resume")
    if not handoff_current and (strategy_note or resource_anchors or candidate_source):
        raise ValueError(
            "strategy note, resource anchors, and candidate source require warm handoff"
        )

    inner_provider = str(os.environ.get(INNER_PROVIDER_ENV, "")).strip()
    if not inner_provider:
        raise ValueError("fixed inner provider is missing from the active run")
    inner_profile = profile_for(inner_provider)
    expected_inner_profile_hash = os.environ.get(
        "INTERLEAVED_INNER_PROFILE_SHA256", ""
    ).strip()
    actual_inner_profile_hash = agent_profile_sha256(inner_profile)
    if (
        not expected_inner_profile_hash
        or expected_inner_profile_hash != actual_inner_profile_hash
    ):
        raise ValueError("selected inner profile does not match the active run")
    actual_profiles_hash = hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest()
    expected_provider_identity = _expected_provider_identity(profile=inner_profile)

    run_rel, run_dir = run_directory()
    target = ROOT / TARGET
    source_bytes = target.read_bytes()
    source_text = source_bytes.decode("utf-8")
    with _registry_lock(run_dir):
        _raise_for_active_boundary_violations(
            _all_jobs(run_dir),
            source_text,
        )
    _require_outer_decomposition_boundary(source_text, lemma)
    contract = _source_contract(source_text, lemma)

    resume_parent: dict[str, Any] | None = None
    resume_artifact: Path | None = None
    resume_parent_run_rel: Path | None = None
    if resume_job_id:
        resume_parent, resume_artifact, resume_parent_run_rel = (
            _resume_parent_checkpoint(
                run_dir=run_dir,
                parent_job_id=resume_job_id,
                lemma=lemma,
                source_contract=contract,
            )
        )

    note_bytes: bytes | None = None
    if strategy_note:
        note = _resolve_same_run_file(run_dir, strategy_note, label="strategy note")
        note_bytes = note.read_bytes()
        note_text = note_bytes.decode("utf-8")
        if not note_text.strip() or len(note_text) > 8000:
            raise ValueError("strategy note must contain 1 to 8000 characters")
    continuation_note_bytes: bytes | None = None
    if continuation_note:
        note = _resolve_same_run_file(
            run_dir,
            continuation_note,
            label="continuation note",
        )
        continuation_note_bytes = note.read_bytes()
        try:
            continuation_note_text = continuation_note_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("continuation note must be UTF-8") from exc
        if (
            not continuation_note_text.strip()
            or len(continuation_note_text) > CONTINUATION_NOTE_MAX_CHARS
        ):
            raise ValueError("continuation note must contain 1 to 8000 characters")
    resource_anchor_bytes: bytes | None = None
    if resource_anchors:
        anchor_path = _resolve_same_run_file(
            run_dir, resource_anchors, label="resource anchors"
        )
        resource_anchor_bytes = anchor_path.read_bytes()
        try:
            anchor_value = json.loads(resource_anchor_bytes.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"resource anchors must be valid JSON: {exc}") from exc
        if not isinstance(anchor_value, list):
            raise ValueError("resource anchors must be a JSON list")
    candidate_bytes: bytes | None = None
    if candidate_source:
        candidate_bytes = _resolve_candidate_file(run_dir, candidate_source).read_bytes()

    job_id = uuid.uuid4().hex[:16]
    job_dir = _job_dir(run_dir, job_id)
    input_dir = job_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=False)
    _atomic_bytes(input_dir / "target.ec", source_bytes)
    if note_bytes is not None:
        _atomic_bytes(input_dir / "strategy_note.md", note_bytes)
    if continuation_note_bytes is not None:
        _atomic_bytes(
            input_dir / "continuation_note.md",
            continuation_note_bytes,
        )
    if resource_anchor_bytes is not None:
        _atomic_bytes(input_dir / "resource_anchors.json", resource_anchor_bytes)
    if candidate_bytes is not None:
        _atomic_bytes(input_dir / "candidate.ec", candidate_bytes)
    if resume_artifact is not None:
        shutil.copytree(resume_artifact.parent, input_dir / "resume_capsule")

    record: dict[str, Any] = {
        "schema_version": 1,
        "kind": "interleaved_shannon_job",
        "job_id": job_id,
        "created_at": _now(),
        "status": "queued",
        "lemma": lemma,
        "timeout_minutes": timeout_minutes,
        "warm_handoff": handoff_current,
        "has_candidate_source": bool(candidate_source),
        "has_resource_anchors": resource_anchor_bytes is not None,
        "has_continuation_note": continuation_note_bytes is not None,
        "continuation_note_sha256": (
            _sha256_bytes(continuation_note_bytes)
            if continuation_note_bytes is not None
            else ""
        ),
        "resource_anchors_sha256": (
            _sha256_bytes(resource_anchor_bytes)
            if resource_anchor_bytes is not None
            else ""
        ),
        "source_contract": contract,
        "resume_from_job_id": resume_job_id or "",
        "resume_from_run_directory": (
            resume_parent_run_rel.as_posix()
            if resume_parent_run_rel is not None
            else run_rel.as_posix() if resume_job_id else ""
        ),
        "resume_checkpoint_id": (
            str(resume_parent.get("resume_checkpoint_id") or "")
            if resume_parent is not None else ""
        ),
        "resume_checkpoint_directory_sha256": (
            directory_content_sha256(input_dir / "resume_capsule")
            if resume_artifact is not None else ""
        ),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "max_parallel": MAX_PARALLEL,
        "inner_provider": inner_profile.key,
        "inner_model": inner_profile.model,
        "inner_effort": inner_profile.effort,
        "inner_agent": inner_profile.base_dict(),
        "agent_profiles_sha256": actual_profiles_hash,
        "inner_profile_sha256": actual_inner_profile_hash,
        "expected_provider_identity": expected_provider_identity,
        "expected_provider_identity_sha256": provider_identity_sha256(
            expected_provider_identity
        ),
    }
    receipt = _invocation_receipt(record=record, run_rel=run_rel)
    record["invocation_receipt"] = receipt
    record["invocation_receipt_sha256"] = _sha256_bytes(
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )
    with _registry_lock(run_dir):
        _save_job(run_dir, record)
        _dispatch_locked(run_rel=run_rel, run_dir=run_dir)
        record = _load_job(run_dir, job_id)
    return _public_record(record)


def status_jobs(job_id: str | None = None) -> dict[str, Any]:
    run_rel, run_dir = run_directory()
    with _registry_lock(run_dir):
        _dispatch_locked(run_rel=run_rel, run_dir=run_dir)
        jobs = _all_jobs(run_dir)
        violations = _active_boundary_violations(
            jobs,
            (ROOT / TARGET).read_text(encoding="utf-8"),
        )
        if job_id:
            public = _public_record(_load_job(run_dir, job_id))
            relevant = [
                item for item in violations if item.get("job_id") == job_id
            ]
            if relevant:
                public["active_boundary_violation"] = relevant[0]
            return public
        for index, item in enumerate(
            [record for record in jobs if record.get("status") == "queued"],
            start=1,
        ):
            item["queue_position"] = index
        result = {
            "schema_version": 1,
            "max_parallel": MAX_PARALLEL,
            "terminal_cursor": _latest_terminal_sequence(run_dir),
            "jobs": [_public_record(item) for item in jobs],
        }
        if violations:
            result["active_boundary_violations"] = violations
        return result


def wait_for_terminal_events(
    *,
    after_sequence: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Wait for a terminal transition without asynchronously interrupting Opus."""

    if after_sequence < 0:
        raise ValueError("terminal event cursor must be non-negative")
    if not 1 <= timeout_seconds <= 60:
        raise ValueError("wait timeout must be between 1 and 60 seconds")
    run_rel, run_dir = run_directory()
    deadline = time.monotonic() + timeout_seconds
    while True:
        with _registry_lock(run_dir):
            _dispatch_locked(run_rel=run_rel, run_dir=run_dir)
            cursor = _latest_terminal_sequence(run_dir)
            jobs = _all_jobs(run_dir)
            changed = [
                _public_record(item)
                for item in jobs
                if int(item.get("terminal_event_sequence") or 0) > after_sequence
            ]
            violations = _active_boundary_violations(
                jobs,
                (ROOT / TARGET).read_text(encoding="utf-8"),
            )
        if changed or violations or time.monotonic() >= deadline:
            result = {
                "schema_version": 1,
                "terminal_cursor": cursor,
                "changed": changed,
                "timed_out": not changed and not violations,
            }
            if violations:
                result["active_boundary_violations"] = violations
            return result
        time.sleep(0.25)


def _lane_path(run_dir: Path, job_id: str) -> Path:
    identity = hashlib.sha256(str(run_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path("/tmp") / "interleaved-shannon-lanes" / identity / job_id


def _run_checked(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}: "
            + (result.stderr or result.stdout).strip()[-2000:]
        )


def _prepare_lane(*, lane: Path, source_commit: str) -> None:
    lane.parent.mkdir(parents=True, exist_ok=True)
    _run_checked(
        ["git", "worktree", "add", "--detach", str(lane), source_commit],
        cwd=ROOT,
    )
    _run_checked(["git", "sparse-checkout", "init", "--no-cone"], cwd=lane)
    _run_checked(
        ["git", "sparse-checkout", "set", "--no-cone", *CONFINED_PATTERNS],
        cwd=lane,
    )


def _remove_lane(lane: Path) -> None:
    if not lane.exists():
        return
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(lane)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _lane_default_ec_daemon_socket(lane: Path) -> str:
    """Return the fallback daemon socket owned by one detached job lane."""

    key = hashlib.sha1(os.path.realpath(lane).encode("utf-8")).hexdigest()[:12]
    return f"/tmp/ec_daemon_{key}.sock"


def _shutdown_lane_default_ec_daemon(lane: Path) -> bool:
    """Best-effort backstop for bootstrap work that used the fallback route."""

    from workflow.agents.ec_services import _shutdown_ec_daemon

    try:
        return _shutdown_ec_daemon(
            reason="detached Shannon lane finished",
            socket_path=_lane_default_ec_daemon_socket(lane),
        )
    except Exception:
        # Result/checkpoint finalization remains authoritative.  Cleanup must
        # not relabel a completed proof-search job as infrastructure-invalid.
        return False


def _teardown_lane(lane: Path) -> None:
    # A daemon whose cwd is this lane must stop before git removes that cwd;
    # otherwise it survives under PID 1 with a poisoned working directory.
    try:
        _shutdown_lane_default_ec_daemon(lane)
    finally:
        _remove_lane(lane)


class _WorkerInterrupted(RuntimeError):
    pass


def _request_inner_process_stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _stop_inner_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    _request_inner_process_stop(process)
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)


def _copy_lane_artifacts(lane_run_dir: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"job artifact destination already exists: {destination}")
    shutil.copytree(lane_run_dir, destination)


def _worker_result(
    *,
    record: dict[str, Any],
    run_dir: Path,
    lane: Path,
    lane_run_dir: Path,
    wrapper_exit_code: int,
) -> dict[str, Any]:
    job_id = str(record["job_id"])
    lemma = str(record["lemma"])
    wrapper_path = (
        lane_run_dir / "shannon" / lemma / job_id / "wrapper_result.json"
    )
    wrapper = _read_json(wrapper_path)
    if wrapper.get("kind") != "interleaved_shannon_wrapper_result":
        raise ValueError("worker received an invalid Shannon wrapper result")
    if wrapper.get("invocation_id") != job_id or wrapper.get("lemma") != lemma:
        raise ValueError("Shannon wrapper result identity mismatch")
    if (
        wrapper.get("inner_provider") != record.get("inner_provider")
        or wrapper.get("inner_model") != record.get("inner_model")
        or wrapper.get("inner_effort") != record.get("inner_effort")
    ):
        raise ValueError("Shannon wrapper inner-agent configuration mismatch")
    if wrapper.get("invocation_receipt_sha256") != record.get(
        "invocation_receipt_sha256"
    ):
        raise ValueError("Shannon wrapper invocation receipt mismatch")
    status = str(wrapper.get("status") or "")
    if status not in RESULT_STATUSES:
        raise ValueError(f"unsupported Shannon wrapper status: {status}")
    expected_exit = {"verified": 0, "incomplete": 10, "infrastructure_invalid": 20}
    if wrapper_exit_code != expected_exit[status]:
        raise ValueError(
            "Shannon wrapper shell status does not match its canonical result"
        )

    actual_identity = wrapper.get("provider_identity")
    source_boundary = wrapper.get("eval_source_boundary")
    runtime_evidence_present = any((
        bool(actual_identity),
        bool(source_boundary),
        bool(wrapper.get("provider_identity_sha256")),
        bool(wrapper.get("eval_source_manifest_sha256")),
        bool(wrapper.get("prover_result_id")),
    ))
    # A wrapper can fail while preparing a warm handoff, before any provider
    # process exists.  Such a result cannot truthfully contain an *actual*
    # provider identity or runtime source-boundary evidence.  Requiring those
    # fields hid the preparation error behind a second "empty identity"
    # exception.  Completed/incomplete runs, and infrastructure failures that
    # do carry runtime evidence, remain fully bound by the strict checks.
    if status != "infrastructure_invalid" or runtime_evidence_present:
        if (
            not isinstance(actual_identity, dict)
            or provider_identity_projection(actual_identity)
            != provider_identity_projection(
                record.get("expected_provider_identity") or {}
            )
        ):
            raise ValueError("Shannon wrapper actual provider identity mismatch")
        if (
            not isinstance(source_boundary, dict)
            or source_boundary.get("kind")
            != "interleaved_shannon_source_boundary"
            or source_boundary.get("source_contract")
            != "proof_stripped_project"
            or source_boundary.get("source_manifest_sha256")
            != wrapper.get("eval_source_manifest_sha256")
            or any(
                source_boundary.get(key) is not False
                for key in (
                    "answer_source_visible_before",
                    "answer_source_visible_during",
                    "answer_source_visible_after",
                )
            )
        ):
            raise ValueError(
                "Shannon wrapper lacks valid eval source-boundary evidence"
            )
        if not all(
            isinstance(wrapper.get(key), str) and wrapper.get(key)
            for key in (
                "provider_identity_sha256",
                "eval_source_manifest_sha256",
            )
        ):
            raise ValueError("Shannon wrapper lacks canonical identity hashes")
        expected_identity_sha256 = str(
            record.get("expected_provider_identity_sha256") or ""
        )
        if (
            not expected_identity_sha256
            or wrapper.get("provider_identity_sha256")
            != expected_identity_sha256
        ):
            raise ValueError(
                "Shannon wrapper provider identity fingerprint mismatch"
            )

    progress: dict[str, Any] = {}
    if status != "verified" and isinstance(wrapper.get("progress"), dict) and (
        wrapper.get("progress")
    ):
        progress = _validated_progress(
            wrapper.get("progress"),
            lemma=lemma,
            terminal_status=status,
        )

    checkpoint_record: dict[str, str] = {}
    checkpoint = progress.get("checkpoint") if progress else None
    if isinstance(checkpoint, dict):
        raw_artifact = str(wrapper.get("resume_checkpoint_artifact") or "")
        relative_artifact = Path(raw_artifact)
        output_root = wrapper_path.parent.resolve()
        artifact = (output_root / relative_artifact).resolve()
        if (
            not raw_artifact
            or relative_artifact.is_absolute()
            or ".." in relative_artifact.parts
            or artifact.name != "resume.json"
            or not artifact.is_file()
            or not artifact.is_relative_to(output_root)
        ):
            raise ValueError("Shannon checkpoint artifact is unavailable")
        loaded = load_resume_capsule(artifact)
        projected, prefix_text = checkpoint_projection(loaded)
        if (
            projected.get("checkpoint_id") != checkpoint.get("checkpoint_id")
            or projected.get("tactic_count") != checkpoint.get("tactic_count")
            or _sha256_text(prefix_text)
            != checkpoint.get("accepted_prefix_sha256")
        ):
            raise ValueError("Shannon checkpoint artifact identity mismatch")
        copied_relative = Path("lane_run_artifacts") / artifact.relative_to(
            lane_run_dir.resolve()
        )
        checkpoint_record = {
            "resume_checkpoint_artifact": copied_relative.as_posix(),
            "resume_checkpoint_id": str(checkpoint["checkpoint_id"]),
            "resume_checkpoint_directory_sha256": directory_content_sha256(
                artifact.parent
            ),
        }

    result = dict(record)
    infrastructure_errors = [
        str(item).strip()
        for item in (wrapper.get("infrastructure_errors") or [])
        if str(item).strip()
    ]
    if status == "infrastructure_invalid" and not infrastructure_errors:
        infrastructure_errors = ["missing_terminal_failure_reason"]
    result.update({
        "status": status,
        "finished_at": _now(),
        "wrapper_exit_code": wrapper_exit_code,
        "prover_result_id": str(wrapper.get("prover_result_id") or ""),
        "actual_provider_identity": (
            actual_identity if isinstance(actual_identity, dict) else {}
        ),
        "actual_provider_identity_sha256": str(
            wrapper.get("provider_identity_sha256") or ""
        ),
        "eval_source_manifest_sha256": str(
            wrapper.get("eval_source_manifest_sha256") or ""
        ),
        "error": "; ".join(infrastructure_errors),
        "failure_class": str(
            wrapper.get("failure_class") or "wrapper_infrastructure_invalid"
            if status == "infrastructure_invalid"
            else ""
        ),
        "failure_message": str(
            wrapper.get("failure_message")
            or "; ".join(infrastructure_errors)
        )[:4000],
        "answer_source_visible_after": (
            lane / ANSWER_SOURCE.relative_to(ROOT)
        ).exists(),
    })
    if progress:
        result["progress"] = progress
    result.update(checkpoint_record)
    if result["answer_source_visible_after"]:
        raise ValueError("answer-bearing source remained visible after Shannon")
    if status == "verified":
        proved = (lane / TARGET).read_bytes()
        proved_text = proved.decode("utf-8")
        proof_body, _ = _proof_body_span(proved_text, lemma)
        if re.search(r"\badmit\b", proof_body, re.IGNORECASE):
            raise ValueError("verified Shannon result still contains admit")
        _atomic_bytes(
            _job_dir(run_dir, job_id) / "proved_candidate.ec",
            proved,
        )
        result["proved_source_contract"] = _source_contract(proved_text, lemma)
        result["proved_proof_body_sha256"] = _sha256_text(proof_body)
    return result


def _refresh_live_job_progress(
    *,
    run_dir: Path,
    lane_run_dir: Path,
    job_id: str,
    lemma: str,
) -> None:
    """Copy one validated supervisor projection into the public job record."""

    job_output = (
        lane_run_dir
        / "shannon"
        / lemma
        / job_id
    )
    # The orchestrator owns one timestamped run directory below the
    # scheduler-owned job output root.  Keep discovery bounded to that one
    # level and fail closed if an unexpected second run exists.
    candidates = [
        path
        for path in job_output.glob(
            f"*/iteration_1/{MANAGED_LIVE_PROGRESS_FILENAME}"
        )
        if path.is_file()
    ]
    if len(candidates) != 1:
        return
    source = candidates[0]
    try:
        progress = _validated_live_progress(_read_json(source), lemma=lemma)
    except (OSError, ValueError, json.JSONDecodeError):
        # Live telemetry is explicitly non-authoritative for proof outcome.
        # The canonical terminal wrapper still validates all result evidence.
        return
    with _registry_lock(run_dir):
        current = _load_job(run_dir, job_id)
        if current.get("status") not in ACTIVE_STATUSES:
            return
        if current.get("live_progress") == progress:
            return
        current["live_progress"] = progress
        _save_job(run_dir, current)


def run_worker(job_id: str) -> int:
    run_rel, run_dir = run_directory()
    with _registry_lock(run_dir):
        record = _load_job(run_dir, job_id)
        if record.get("status") == "cancelled":
            return 0
        record["status"] = "running"
        record["pid"] = os.getpid()
        _save_job(run_dir, record)

    lane = _lane_path(run_dir, job_id)
    interrupted = threading.Event()
    heartbeat_stop = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        interrupted.set()

    def maintain_heartbeat() -> None:
        while not heartbeat_stop.is_set():
            try:
                _write_worker_heartbeat(
                    run_dir,
                    job_id=job_id,
                    pid=os.getpid(),
                    phase="running",
                )
                with _registry_lock(run_dir):
                    current = _load_job(run_dir, job_id)
                if current.get("status") == "cancelling":
                    interrupted.set()
            except (OSError, ValueError, json.JSONDecodeError):
                # The job record remains terminal authority. A transient
                # heartbeat failure is retried on the next bounded tick.
                pass
            heartbeat_stop.wait(WORKER_HEARTBEAT_INTERVAL_SECONDS)

    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    heartbeat_thread = threading.Thread(
        target=maintain_heartbeat,
        name=f"shannon-heartbeat-{job_id}",
        daemon=True,
    )
    heartbeat_thread.start()
    result_record: dict[str, Any] | None = None
    error = ""
    try:
        _prepare_lane(lane=lane, source_commit=str(record["source_commit"]))
        if interrupted.is_set():
            raise _WorkerInterrupted("Shannon worker was interrupted")
        target = lane / TARGET
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((_job_dir(run_dir, job_id) / "input" / "target.ec").read_bytes())

        lane_run_dir = lane / run_rel
        lane_input = lane_run_dir / "job_input" / job_id
        lane_input.mkdir(parents=True, exist_ok=True)
        receipt_path = lane_input / "invocation_receipt.json"
        _atomic_json(receipt_path, dict(record["invocation_receipt"]))
        receipt_sha256 = _sha256_bytes(receipt_path.read_bytes())
        if receipt_sha256 != record.get("invocation_receipt_sha256"):
            raise ValueError("scheduler invocation receipt hash drifted")
        command = [
            sys.executable,
            str(lane / "workflow/interleaved/inner_runner.py"),
            "--lemma",
            str(record["lemma"]),
            "--timeout-minutes",
            str(record["timeout_minutes"]),
        ]
        input_dir = _job_dir(run_dir, job_id) / "input"
        if record.get("warm_handoff"):
            note = lane_input / "strategy_note.md"
            note.write_bytes((input_dir / "strategy_note.md").read_bytes())
            command.extend([
                "--handoff-current",
                "--strategy-note",
                str(note.relative_to(lane)),
            ])
            resource_anchor_input = input_dir / "resource_anchors.json"
            if resource_anchor_input.is_file():
                anchors = lane_input / "resource_anchors.json"
                anchors.write_bytes(resource_anchor_input.read_bytes())
                if _sha256_bytes(anchors.read_bytes()) != record.get(
                    "resource_anchors_sha256"
                ):
                    raise ValueError("scheduler resource anchors hash drifted")
                command.extend([
                    "--resource-anchors",
                    str(anchors.relative_to(lane)),
                ])
            candidate_input = input_dir / "candidate.ec"
            if candidate_input.is_file():
                candidate = lane_input / "candidate.ec"
                candidate.write_bytes(candidate_input.read_bytes())
                command.extend([
                    "--candidate-source",
                    str(candidate.relative_to(lane)),
                ])
        resume_input = input_dir / "resume_capsule"
        if record.get("resume_from_job_id"):
            resume_lane = lane_input / "resume_capsule"
            shutil.copytree(resume_input, resume_lane)
            if directory_content_sha256(resume_lane) != record.get(
                "resume_checkpoint_directory_sha256"
            ):
                raise ValueError("scheduler resume checkpoint hash drifted")
            command.extend([
                "--resume-capsule",
                str((resume_lane / "resume.json").relative_to(lane)),
            ])
            continuation_note_input = input_dir / "continuation_note.md"
            if record.get("has_continuation_note"):
                continuation_note_lane = lane_input / "continuation_note.md"
                continuation_note_lane.write_bytes(
                    continuation_note_input.read_bytes()
                )
                if _sha256_bytes(
                    continuation_note_lane.read_bytes()
                ) != record.get("continuation_note_sha256"):
                    raise ValueError("scheduler continuation note hash drifted")
                command.extend([
                    "--continuation-note",
                    str(continuation_note_lane.relative_to(lane)),
                ])
        environment = os.environ.copy()
        environment["INTERLEAVED_RUN_DIR"] = run_rel.as_posix()
        environment["INTERLEAVED_SHANNON_INVOCATION_ID"] = job_id
        environment["INTERLEAVED_INNER_PROFILE_SHA256"] = str(
            record["inner_profile_sha256"]
        )
        environment[RECEIPT_ENV] = str(receipt_path.relative_to(lane))
        environment[RECEIPT_SHA256_ENV] = receipt_sha256
        inner_stdout = (_job_dir(run_dir, job_id) / "shannon.stdout.log").open(
            "w", encoding="utf-8"
        )
        inner_stderr = (_job_dir(run_dir, job_id) / "shannon.stderr.log").open(
            "w", encoding="utf-8"
        )
        process: subprocess.Popen[bytes] | None = None
        graceful_stop_deadline: float | None = None
        next_live_progress_refresh = 0.0
        try:
            process = subprocess.Popen(
                command,
                cwd=lane,
                env=environment,
                stdout=inner_stdout,
                stderr=inner_stderr,
                start_new_session=True,
            )
            with _registry_lock(run_dir):
                current = _load_job(run_dir, job_id)
                current["inner_pid"] = process.pid
                _save_job(run_dir, current)
                if current.get("status") == "cancelling":
                    interrupted.set()
            while True:
                try:
                    wrapper_exit_code = process.wait(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    now = time.monotonic()
                    if now >= next_live_progress_refresh:
                        _refresh_live_job_progress(
                            run_dir=run_dir,
                            lane_run_dir=lane_run_dir,
                            job_id=job_id,
                            lemma=str(record["lemma"]),
                        )
                        next_live_progress_refresh = now + 1.0
                    if interrupted.is_set():
                        if graceful_stop_deadline is None:
                            _request_inner_process_stop(process)
                            graceful_stop_deadline = (
                                time.monotonic()
                                + INNER_SAFE_STOP_GRACE_SECONDS
                            )
                        elif time.monotonic() >= graceful_stop_deadline:
                            _stop_inner_process(process)
                            raise _WorkerInterrupted(
                                "Shannon worker interruption checkpoint timed out"
                            )
        finally:
            if process is not None and process.poll() is None:
                _stop_inner_process(process)
            inner_stdout.close()
            inner_stderr.close()
        _copy_lane_artifacts(
            lane_run_dir,
            _job_dir(run_dir, job_id) / "lane_run_artifacts",
        )
        result_record = _worker_result(
            record=record,
            run_dir=run_dir,
            lane=lane,
            lane_run_dir=lane_run_dir,
            wrapper_exit_code=wrapper_exit_code,
        )
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        _teardown_lane(lane)

    with _registry_lock(run_dir):
        current = _load_job(run_dir, job_id)
        if current.get("status") == "cancelling" and result_record is not None:
            # The operator owns the cancelled terminal class, while the
            # completed wrapper owns any checkpoint/progress recovered during
            # cooperative shutdown.
            for key in (
                "progress",
                "resume_checkpoint_artifact",
                "resume_checkpoint_id",
                "resume_checkpoint_directory_sha256",
                "prover_result_id",
                "actual_provider_identity",
                "actual_provider_identity_sha256",
                "eval_source_manifest_sha256",
                "wrapper_exit_code",
            ):
                if key in result_record:
                    current[key] = result_record[key]
            progress = current.get("progress")
            if isinstance(progress, dict):
                terminal = current["progress"].get("terminal")
                if isinstance(terminal, dict):
                    terminal.update({
                        "status": "cancelled",
                        "cause": "outer_cancelled",
                        "message": "cancelled by outer job controller",
                    })
            current["status"] = "cancelled"
            current["finished_at"] = _now()
            current["error"] = "cancelled by outer job controller"
            _save_job(run_dir, current)
        elif current.get("status") == "cancelling":
            current["status"] = "infrastructure_invalid"
            current["finished_at"] = _now()
            current["error"] = error or (
                "outer cancel ended before safe-stop checkpoint finalization"
            )
            _save_job(run_dir, current)
        elif current.get("status") != "cancelled":
            if result_record is None:
                current["status"] = "infrastructure_invalid"
                current["finished_at"] = _now()
                current["error"] = error or "Shannon worker failed"
                current["wrapper_exit_code"] = 20
                _save_job(run_dir, current)
            else:
                _save_job(run_dir, result_record)
        _dispatch_locked(run_rel=run_rel, run_dir=run_dir)
    heartbeat_stop.set()
    heartbeat_thread.join(timeout=2.0)
    try:
        _worker_heartbeat_path(run_dir, job_id).unlink()
    except OSError:
        pass
    return 0 if result_record is not None else 20


def collect_job(job_id: str) -> dict[str, Any]:
    run_rel, run_dir = run_directory()
    with _registry_lock(run_dir):
        record = _load_job(run_dir, job_id)
        if record.get("status") == "merged":
            return _public_record(record)
        if record.get("status") != "verified":
            raise ValueError(
                f"Shannon job {job_id} is not collectable: {record.get('status')}"
            )

        lemma = str(record["lemma"])
        target = ROOT / TARGET
        current_bytes = target.read_bytes()
        current = current_bytes.decode("utf-8")
        current_contract = _source_contract(current, lemma)
        submitted = dict(record.get("source_contract") or {})
        if (
            current_contract["lemma_prefix_sha256"]
            != submitted.get("lemma_prefix_sha256")
            or current_contract["proof_body_sha256"]
            != submitted.get("proof_body_sha256")
        ):
            record["status"] = "stale_merge"
            record["finished_at"] = record.get("finished_at") or _now()
            record["collect_status"] = "source_drift"
            record["error"] = (
                "delegated lemma or its declaration prefix changed while "
                "Shannon was running; canonical source was not modified"
            )
            _save_job(run_dir, record)
            return _public_record(record)

        proved_path = _job_dir(run_dir, job_id) / "proved_candidate.ec"
        proved = proved_path.read_text(encoding="utf-8")
        if (
            _source_contract(proved, lemma)["lemma_prefix_sha256"]
            != submitted.get("lemma_prefix_sha256")
        ):
            raise ValueError("verified job result source prefix is not bound to submission")
        proof_body, _ = _proof_body_span(proved, lemma)
        _, (body_start, body_end) = _proof_body_span(current, lemma)
        merged = current[:body_start] + proof_body + current[body_end:]
        job_dir = _job_dir(run_dir, job_id)
        candidate = job_dir / "collect_candidate.ec"
        _atomic_bytes(candidate, merged.encode("utf-8"))
        verification = check_import_with_project_verifier(
            root=ROOT, project=_SETTINGS.project, candidate=candidate, lemma=lemma,
            output=job_dir / "collect_verification.json",
        )
        if not verification["passed"]:
            record["collect_status"] = "verification_failed"
            record["error"] = (
                "lemma import verification failed; canonical source was not modified: "
                + str(verification.get("error") or verification.get("easycrypt_stderr") or "native rejection")[:1500]
            )
            _save_job(run_dir, record)
            return _public_record(record)

        # The outer can edit independent source while native checking runs.
        # Do not overwrite any such concurrent edit, even beyond the lemma.
        if target.read_bytes() != current_bytes:
            record["collect_status"] = "source_changed_during_check"
            record["error"] = "source changed during collect verification; retry collect"
            _save_job(run_dir, record)
            return _public_record(record)
        _atomic_bytes(target, merged.encode("utf-8"))
        record["status"] = "merged"
        record["merged_at"] = _now()
        record["collect_status"] = "merged_and_checked"
        record["collect_verification_scope"] = "target_lemma_under_declared_dependencies"
        record["merged_target_sha256"] = _sha256_text(merged)
        record["error"] = ""
        _save_job(run_dir, record)
        _dispatch_locked(run_rel=run_rel, run_dir=run_dir)
        return _public_record(record)


def cancel_jobs_in_run(
    *,
    run_rel: Path,
    run_dir: Path,
    job_id: str | None = None,
    dispatch_after: bool = True,
) -> dict[str, Any]:
    cancelled: list[str] = []
    worker_pids: dict[str, tuple[int, int]] = {}

    def still_active(current_job: str, pid: int) -> bool:
        try:
            current = _load_job(run_dir, current_job)
        except (OSError, ValueError, json.JSONDecodeError):
            return _pid_alive(pid)
        if current.get("status") in TERMINAL_STATUSES:
            return False
        return _worker_alive(run_dir, current)

    with _registry_lock(run_dir):
        jobs = [_load_job(run_dir, job_id)] if job_id else _all_jobs(run_dir)
        for record in jobs:
            if record.get("status") in TERMINAL_STATUSES:
                continue
            pid = int(record.get("pid") or 0)
            if pid > 0:
                worker_pids[str(record["job_id"])] = (
                    pid,
                    int(record.get("inner_pid") or 0),
                )
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            record["status"] = "cancelling" if pid > 0 else "cancelled"
            if pid <= 0:
                record["finished_at"] = _now()
                record["error"] = "cancelled by outer job controller"
            _save_job(run_dir, record)
            cancelled.append(str(record["job_id"]))

    # Cooperative shutdown gives the managed runtime enough time to archive
    # the selected session and write its canonical checkpoint handback.
    deadline = time.monotonic() + WORKER_SAFE_STOP_GRACE_SECONDS
    remaining = dict(worker_pids)
    while remaining and time.monotonic() < deadline:
        remaining = {
            current_job: pids
            for current_job, pids in remaining.items()
            if still_active(current_job, pids[0])
        }
        if remaining:
            time.sleep(0.05)

    forcibly_killed: list[str] = []
    for current_job, (pid, inner_pid) in remaining.items():
        if inner_pid > 0:
            try:
                os.killpg(inner_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            os.killpg(pid, signal.SIGKILL)
            forcibly_killed.append(current_job)
        except ProcessLookupError:
            pass

    if remaining:
        kill_deadline = time.monotonic() + 2.0
        while time.monotonic() < kill_deadline and any(
            still_active(current_job, pids[0])
            for current_job, pids in remaining.items()
        ):
            time.sleep(0.05)

    for current_job, (pid, _inner_pid) in worker_pids.items():
        if not still_active(current_job, pid):
            _remove_lane(_lane_path(run_dir, current_job))

    if dispatch_after:
        with _registry_lock(run_dir):
            _dispatch_locked(run_rel=run_rel, run_dir=run_dir)
    return {
        "schema_version": 1,
        "cancelled": cancelled,
        "forcibly_killed": forcibly_killed,
    }


def cancel_jobs(job_id: str | None = None) -> dict[str, Any]:
    run_rel, run_dir = run_directory()
    return cancel_jobs_in_run(
        run_rel=run_rel,
        run_dir=run_dir,
        job_id=job_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit = subparsers.add_parser("submit")
    submit.add_argument("--lemma", required=True)
    submit.add_argument("--timeout-minutes", type=int, required=True)
    submit.add_argument("--handoff-current", action="store_true")
    submit.add_argument("--strategy-note")
    submit.add_argument("--resource-anchors")
    submit.add_argument("--candidate-source")
    submit.add_argument("--resume-job")
    submit.add_argument("--continuation-note")

    status = subparsers.add_parser("status")
    status.add_argument("--job-id")

    wait = subparsers.add_parser("wait")
    wait.add_argument("--after-sequence", type=int, default=0)
    wait.add_argument("--timeout-seconds", type=int, default=30)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--job-id", required=True)

    cancel = subparsers.add_parser("cancel")
    cancel_group = cancel.add_mutually_exclusive_group(required=True)
    cancel_group.add_argument("--job-id")
    cancel_group.add_argument("--all", action="store_true")

    worker = subparsers.add_parser("worker")
    worker.add_argument("--job-id", required=True)

    args = parser.parse_args()
    try:
        if args.command == "submit":
            payload = submit_job(
                lemma=args.lemma,
                timeout_minutes=args.timeout_minutes,
                handoff_current=args.handoff_current,
                strategy_note=args.strategy_note,
                resource_anchors=args.resource_anchors,
                candidate_source=args.candidate_source,
                resume_job_id=args.resume_job,
                continuation_note=args.continuation_note,
            )
        elif args.command == "status":
            payload = status_jobs(args.job_id)
        elif args.command == "wait":
            payload = wait_for_terminal_events(
                after_sequence=args.after_sequence,
                timeout_seconds=args.timeout_seconds,
            )
        elif args.command == "collect":
            payload = collect_job(args.job_id)
        elif args.command == "cancel":
            payload = cancel_jobs(None if args.all else args.job_id)
        else:
            return run_worker(args.job_id)
    except Exception as exc:
        print(
            json.dumps({
                "schema_version": 1,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }, indent=2, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
