"""Job states, their transition table and the shared job-record schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.interleaved_shannon import verify_task
from tests.helpers.interleaved import job_record, reference, store_job
from workflow.interleaved import jobs
from workflow.interleaved.job_record import (
    ACTIVE_STATUSES,
    BOUNDARY_LEASE_STATUSES,
    TERMINAL_STATUSES,
    TRANSITIONS,
    JobRecord,
    JobStatus,
)


JOB_ID = "a" * 16


def test_every_status_is_either_leased_or_terminal() -> None:
    assert set(TRANSITIONS) == {None, *JobStatus}
    assert BOUNDARY_LEASE_STATUSES | TERMINAL_STATUSES == set(JobStatus)
    assert not BOUNDARY_LEASE_STATUSES & TERMINAL_STATUSES
    assert ACTIVE_STATUSES < BOUNDARY_LEASE_STATUSES
    for status in TERMINAL_STATUSES - {JobStatus.VERIFIED}:
        assert TRANSITIONS[status] == frozenset()


@pytest.mark.parametrize("previous", [None, *JobStatus])
@pytest.mark.parametrize("status", list(JobStatus))
def test_every_write_follows_the_transition_table(
    tmp_path: Path,
    previous: JobStatus | None,
    status: JobStatus,
) -> None:
    if previous is not None:
        store_job(tmp_path, {"job_id": JOB_ID, "status": previous.value, "lemma": "L"})
    record = job_record({"job_id": JOB_ID, "status": status.value, "lemma": "L"})
    allowed = status == previous or status in TRANSITIONS[previous]

    if not allowed:
        with pytest.raises(ValueError, match="invalid Shannon job transition"):
            jobs._save_job(tmp_path, record)
        stored = json.loads(jobs._record_path(tmp_path, JOB_ID).read_text()) if (
            previous is not None
        ) else None
        assert stored is None or stored["status"] == previous.value
        return
    jobs._save_job(tmp_path, record)
    assert jobs._load_job(tmp_path, JOB_ID).status == status
    publishes = status in TERMINAL_STATUSES and status != previous
    assert jobs._latest_terminal_sequence(tmp_path) == (1 if publishes else 0)


def test_record_round_trip_keeps_every_stored_key(tmp_path: Path) -> None:
    stored = {
        "schema_version": 1,
        "kind": "interleaved_shannon_job",
        "job_id": JOB_ID,
        "created_at": "2026-10-28T00:00:00-07:00",
        "status": "incomplete",
        "lemma": "L",
        "timeout_minutes": 20,
        "warm_handoff": False,
        "has_resource_anchors": False,
        "resume_checkpoint_id": "",
        "source_contract": {"target_sha256": "b" * 64},
        "progress": {"terminal": {"status": "incomplete"}},
        "pid": 12,
        # An older scheduler's key this schema no longer names.
        "eval_confinement_sha256": "c" * 64,
    }
    record = JobRecord.from_dict(stored)
    assert record.status is JobStatus.INCOMPLETE
    assert record.extra == {"eval_confinement_sha256": "c" * 64}
    assert record.to_dict() == stored
    path = jobs._record_path(tmp_path, JOB_ID)
    jobs._atomic_json(path, stored)
    assert jobs._load_job(tmp_path, JOB_ID).to_dict() == stored


@pytest.mark.parametrize("stored", [
    {"job_id": JOB_ID, "status": "running"},
    {"schema_version": 2, "job_id": JOB_ID, "status": "running"},
    {"schema_version": 1, "status": "running"},
    {"schema_version": 1, "job_id": JOB_ID, "status": "paused"},
    {"schema_version": 1, "job_id": JOB_ID},
])
def test_invalid_records_fail_closed(tmp_path: Path, stored: dict) -> None:
    jobs._atomic_json(jobs._record_path(tmp_path, JOB_ID), stored)
    with pytest.raises(ValueError, match="invalid Shannon job record"):
        jobs._load_job(tmp_path, JOB_ID)


def test_reference_verifier_uses_the_scheduler_status_sets() -> None:
    summary = {
        "jobs": [{"job_id": status.value, "status": status.value} for status in JobStatus]
    }
    (barrier,) = verify_task.active_shannon_job_errors("final", summary)
    assert barrier.endswith(", ".join(
        status.value for status in JobStatus if status in BOUNDARY_LEASE_STATUSES
    ))
    assert {item["status"] for item in verify_task.shannon_terminal_alerts(summary)} == {
        status.value for status in TERMINAL_STATUSES - {JobStatus.MERGED}
    }


# -- finalize_job: the one path that closes a job whose worker stopped -------

WORKER_EXIT = {
    "failure": "Shannon worker failed",
    "cancel_failure": "outer cancel ended before safe-stop checkpoint finalization",
    "failure_exit_code": 20,
}
DEAD_WORKER = {
    "failure": jobs.DEAD_WORKER_FAILURE,
    "cancel_failure": jobs.DEAD_CANCELLED_WORKER_FAILURE,
}


@pytest.fixture
def released(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    released: list[str] = []
    monkeypatch.setattr(
        jobs, "_release_job", lambda _ctx, _run, job_id: released.append(job_id),
    )
    return released


@pytest.mark.parametrize("caller", [WORKER_EXIT, DEAD_WORKER], ids=["worker", "dead"])
@pytest.mark.parametrize("status", ["starting", "running", "cancelling"])
def test_finalize_without_a_result_invalidates_the_job(
    tmp_path: Path, released: list[str], caller: dict, status: str,
) -> None:
    store_job(tmp_path, {"job_id": JOB_ID, "status": status, "lemma": "L"})

    jobs.finalize_job(reference(), tmp_path, JOB_ID, **caller)

    record = jobs._load_job(tmp_path, JOB_ID)
    assert record.status is JobStatus.INFRASTRUCTURE_INVALID
    assert record.error == (
        caller["cancel_failure"] if status == "cancelling" else caller["failure"]
    )
    assert record.wrapper_exit_code == caller.get("failure_exit_code")
    assert record.finished_at
    assert record.terminal_event_sequence == 1
    assert released == [JOB_ID]


def test_finalize_records_the_worker_result(tmp_path: Path, released: list[str]) -> None:
    store_job(tmp_path, {"job_id": JOB_ID, "status": "running", "lemma": "L", "pid": 7})
    result = job_record({
        "job_id": JOB_ID, "status": "verified", "lemma": "L",
        "wrapper_exit_code": 0, "prover_result_id": "result",
    })

    jobs.finalize_job(reference(), tmp_path, JOB_ID, result=result, **WORKER_EXIT)

    stored = jobs._load_job(tmp_path, JOB_ID).to_dict()
    assert stored == {
        **result.to_dict(),
        "terminal_event_sequence": 1,
        "terminal_event_at": stored["terminal_event_at"],
        "terminal_event_id": stored["terminal_event_id"],
    }
    assert released == [JOB_ID]


def test_finalize_cancelled_job_keeps_the_checkpoint_it_recovered(
    tmp_path: Path, released: list[str],
) -> None:
    store_job(tmp_path, {
        "job_id": JOB_ID, "status": "cancelling", "lemma": "L", "inner_pid": 9,
        "resume_checkpoint_id": "",
    })
    result = job_record({
        "job_id": JOB_ID, "status": "incomplete", "lemma": "L",
        "wrapper_exit_code": 10, "prover_result_id": "result",
        "resume_checkpoint_id": "c" * 64,
        "resume_checkpoint_artifact": "lane_run_artifacts/resume.json",
        "progress": {"terminal": {"status": "incomplete", "cause": "x", "message": ""}},
        "failure_class": "not copied",
    })

    jobs.finalize_job(reference(), tmp_path, JOB_ID, result=result, **WORKER_EXIT)

    record = jobs._load_job(tmp_path, JOB_ID)
    assert record.status is JobStatus.CANCELLED
    assert record.error == jobs.CANCELLED_MESSAGE
    assert record.inner_pid == 9
    assert record.wrapper_exit_code == 10
    assert record.prover_result_id == "result"
    assert record.resume_checkpoint_id == "c" * 64
    assert record.resume_checkpoint_artifact == "lane_run_artifacts/resume.json"
    assert record.failure_class is None
    assert record.progress["terminal"] == {
        "status": "cancelled",
        "cause": "outer_cancelled",
        "message": jobs.CANCELLED_MESSAGE,
    }
    assert released == [JOB_ID]


@pytest.mark.parametrize("status", sorted(status.value for status in TERMINAL_STATUSES))
def test_finalize_keeps_a_job_that_is_already_closed(
    tmp_path: Path, released: list[str], status: str,
) -> None:
    stored = store_job(tmp_path, {"job_id": JOB_ID, "status": status, "lemma": "L"})
    result = job_record({"job_id": JOB_ID, "status": "verified", "lemma": "L"})

    jobs.finalize_job(reference(), tmp_path, JOB_ID, result=result, **WORKER_EXIT)

    assert jobs._load_job(tmp_path, JOB_ID).to_dict() == stored.to_dict()
    assert jobs._latest_terminal_sequence(tmp_path) == 0
    assert released == [JOB_ID]
