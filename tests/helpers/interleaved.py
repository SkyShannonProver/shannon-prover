"""Project contexts for the interleaved tests.

Besides the ChaChaPoly reference adapter, the product contract tests run on a
second project whose artifact root, target, final lemma, include directories,
capacity and delegation region all differ from the reference.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from experiments.interleaved_shannon.reference import reference_context
from workflow.interleaved import jobs
from workflow.interleaved.job_record import JobRecord
from workflow.interleaved.project import InterleavedProject
from workflow.interleaved.runtime import ProjectContext


ROOT = Path(__file__).resolve().parents[2]
DEMO_CONTRACT = "projects/demo/interleaved_project.json"
DEMO_PROJECT = InterleavedProject(
    target_file="projects/demo/Target.ec",
    final_lemma="Main",
    include_dirs=("lib/common", "projects/demo"),
    artifact_root="artifacts/demo-interleaved",
    max_parallel=3,
    max_inner_minutes=30,
    outer_timeout_seconds=3600,
)


def reference() -> ProjectContext:
    """The reference adapter bound to this checkout."""

    return reference_context()


def rebind(
    context: ProjectContext,
    root: Path,
    **project_changes: object,
) -> ProjectContext:
    """Bind ``context`` to another checkout, optionally changing its contract."""

    def moved(path: Path | None) -> Path | None:
        return None if path is None else root / path.relative_to(context.root)

    return ProjectContext(
        root=root,
        project_path=moved(context.project_path),
        project=dataclasses.replace(context.project, **project_changes),
        answer_source=moved(context.answer_source),
    )


def demo_context(root: Path, **project_changes: object) -> ProjectContext:
    """The second project, with its contract written below ``root``."""

    project = dataclasses.replace(DEMO_PROJECT, **project_changes)
    path = root / DEMO_CONTRACT
    project.write(path)
    return ProjectContext(
        root=root, project_path=path, project=project, answer_source=None,
    )


def job_record(fields: dict[str, Any]) -> JobRecord:
    """A schema-version-1 job record with the given stored fields."""

    return JobRecord.from_dict({"schema_version": 1, **fields})


def store_job(run_dir: Path, fields: dict[str, Any]) -> JobRecord:
    """Write a record as an earlier stage left it, bypassing transitions."""

    record = job_record(fields)
    jobs._atomic_json(jobs._record_path(run_dir, record.job_id), record.to_dict())
    return record
