"""Shannon job records: their states, allowed transitions and on-disk schema.

``submit`` queues a job; the scheduler starts it; a detached worker records
its result; a cancel or the scheduler's reconcile closes a job whose worker
stopped without one; ``collect`` merges a verified job or finds it stale.
``TRANSITIONS`` lists every status change those writers may make, and the
scheduler checks each write against it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import Any


JOB_RECORD_SCHEMA_VERSION = 1
JOB_RECORD_KIND = "interleaved_shannon_job"


class JobStatus(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    VERIFIED = "verified"
    INCOMPLETE = "incomplete"
    INFRASTRUCTURE_INVALID = "infrastructure_invalid"
    CANCELLED = "cancelled"
    MERGED = "merged"
    STALE_MERGE = "stale_merge"


ACTIVE_STATUSES = frozenset({
    JobStatus.STARTING, JobStatus.RUNNING, JobStatus.CANCELLING,
})
# A queued job already holds a lease on the source it snapshotted.
BOUNDARY_LEASE_STATUSES = ACTIVE_STATUSES | {JobStatus.QUEUED}
# The statuses a worker's wrapper result may carry.
RESULT_STATUSES = frozenset({
    JobStatus.VERIFIED, JobStatus.INCOMPLETE, JobStatus.INFRASTRUCTURE_INVALID,
})
TERMINAL_STATUSES = RESULT_STATUSES | {
    JobStatus.CANCELLED, JobStatus.MERGED, JobStatus.STALE_MERGE,
}
# Terminal jobs whose managed checkpoint a later job may resume.
RESUMABLE_STATUSES = frozenset({
    JobStatus.INCOMPLETE, JobStatus.INFRASTRUCTURE_INVALID, JobStatus.CANCELLED,
})

# The statuses a write may move a stored record to. ``None`` is a record not
# yet stored. Rewriting a record with its current status only updates fields.
TRANSITIONS: dict[JobStatus | None, frozenset[JobStatus]] = {
    None: frozenset({JobStatus.QUEUED}),
    JobStatus.QUEUED: frozenset({JobStatus.STARTING, JobStatus.CANCELLED}),
    JobStatus.STARTING: frozenset({
        JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.INFRASTRUCTURE_INVALID,
    }),
    JobStatus.RUNNING: RESULT_STATUSES | {
        JobStatus.CANCELLING, JobStatus.CANCELLED,
    },
    JobStatus.CANCELLING: frozenset({
        JobStatus.CANCELLED, JobStatus.INFRASTRUCTURE_INVALID,
    }),
    JobStatus.VERIFIED: frozenset({JobStatus.MERGED, JobStatus.STALE_MERGE}),
    JobStatus.INCOMPLETE: frozenset(),
    JobStatus.INFRASTRUCTURE_INVALID: frozenset(),
    JobStatus.CANCELLED: frozenset(),
    JobStatus.MERGED: frozenset(),
    JobStatus.STALE_MERGE: frozenset(),
}


def require_transition(previous: JobStatus | None, status: JobStatus) -> None:
    if status != previous and status not in TRANSITIONS[previous]:
        raise ValueError(
            "invalid Shannon job transition: "
            f"{previous.value if previous else 'new'} -> {status.value}"
        )


@dataclass
class JobRecord:
    """One ``job.json``, written by the scheduler and read back by every stage.

    Each optional field stays ``None`` until a stage sets it and is then
    absent from the JSON, so records keep the keys and values earlier
    schedulers wrote. Keys this schema does not name are kept in ``extra``
    and written back unchanged.
    """

    job_id: str
    status: JobStatus
    schema_version: int = JOB_RECORD_SCHEMA_VERSION
    kind: str | None = None
    created_at: str | None = None
    lemma: str | None = None
    # Submission: the snapshot, briefing and fixed inner agent.
    timeout_minutes: int | None = None
    warm_handoff: bool | None = None
    has_candidate_source: bool | None = None
    has_resource_anchors: bool | None = None
    has_continuation_note: bool | None = None
    continuation_note_sha256: str | None = None
    resource_anchors_sha256: str | None = None
    source_contract: dict[str, Any] | None = None
    resume_from_job_id: str | None = None
    resume_from_run_directory: str | None = None
    resume_checkpoint_id: str | None = None
    resume_checkpoint_directory_sha256: str | None = None
    source_commit: str | None = None
    max_parallel: int | None = None
    inner_provider: str | None = None
    inner_model: str | None = None
    inner_effort: str | None = None
    inner_agent: dict[str, Any] | None = None
    agent_profiles_sha256: str | None = None
    inner_profile_sha256: str | None = None
    expected_provider_identity: dict[str, Any] | None = None
    expected_provider_identity_sha256: str | None = None
    invocation_receipt: dict[str, Any] | None = None
    invocation_receipt_sha256: str | None = None
    # Lifecycle.
    started_at: str | None = None
    pid: int | None = None
    inner_pid: int | None = None
    live_progress: dict[str, Any] | None = None
    finished_at: str | None = None
    error: str | None = None
    terminal_event_sequence: int | None = None
    terminal_event_at: str | None = None
    terminal_event_id: str | None = None
    # The worker's validated wrapper result.
    wrapper_exit_code: int | None = None
    prover_result_id: str | None = None
    actual_provider_identity: dict[str, Any] | None = None
    actual_provider_identity_sha256: str | None = None
    eval_source_manifest_sha256: str | None = None
    failure_class: str | None = None
    failure_message: str | None = None
    answer_source_visible_after: bool | None = None
    progress: dict[str, Any] | None = None
    resume_checkpoint_artifact: str | None = None
    proved_source_contract: dict[str, Any] | None = None
    proved_proof_body_sha256: str | None = None
    # Collection.
    collect_status: str | None = None
    collect_verification_scope: str | None = None
    merged_at: str | None = None
    merged_target_sha256: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: object) -> "JobRecord":
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != JOB_RECORD_SCHEMA_VERSION
            or not isinstance(value.get("job_id"), str)
        ):
            raise ValueError("invalid Shannon job record")
        try:
            status = JobStatus(value.get("status"))
        except ValueError as exc:
            raise ValueError("invalid Shannon job record status") from exc
        named = _FIELD_NAMES
        return cls(
            **{
                key: item for key, item in value.items()
                if key in named and key != "status"
            },
            status=status,
            extra={key: item for key, item in value.items() if key not in named},
        )

    def to_dict(self) -> dict[str, Any]:
        value = {
            name: getattr(self, name)
            for name in _FIELD_NAMES
            if getattr(self, name) is not None
        }
        value["status"] = self.status.value
        value.update(self.extra)
        return value


_FIELD_NAMES = frozenset(
    item.name for item in fields(JobRecord) if item.name != "extra"
)
