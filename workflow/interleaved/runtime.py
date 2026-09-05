"""Runtime binding for product projects and evaluation adapters."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from workflow.interleaved.project import InterleavedProject, PROJECT_ENV


ROOT = Path(__file__).resolve().parents[2]
ANSWER_SOURCE_ENV = "SHANNON_INTERLEAVED_ANSWER_SOURCE"


@dataclass(frozen=True)
class RuntimeSettings:
    root: Path
    project_path: Path
    project: InterleavedProject
    answer_source: Path | None

    @property
    def confined_patterns(self) -> tuple[str, ...]:
        """Sparse lane closure for the product plus the selected project."""

        target_directory = Path(self.project.target_file).parent.as_posix()
        target_pattern = "/" if target_directory == "." else f"/{target_directory}/"
        patterns = [
            "/core/",
            "/workflow/",
            "/tools/",
            "/easycrypt-src/",
            target_pattern,
            "/AGENTS.md",
            "/CLAUDE.md",
            "/README.md",
            "/pyproject.toml",
            "/uv.lock",
            "/.python-version",
            "/.gitignore",
            "/.gitattributes",
            "/LICENSE",
            "/CITATION.cff",
        ]
        if self.answer_source is not None:
            answer_rel = self.answer_source.relative_to(self.root)
            if answer_rel.parts[:2] == ("easycrypt-src", "examples"):
                patterns.insert(4, "!/easycrypt-src/examples/")
        return tuple(dict.fromkeys(patterns))


def load_runtime_settings() -> RuntimeSettings:
    raw_project = os.environ.get(PROJECT_ENV, "").strip()
    if not raw_project:
        raise RuntimeError(
            f"{PROJECT_ENV} is required; launch through python -m workflow.interleaved"
        )
    relative = Path(raw_project)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"{PROJECT_ENV} must be repository-relative")
    project_path = (ROOT / relative).resolve()
    if not project_path.is_file():
        raise RuntimeError(f"interleaved project contract not found: {relative}")
    project = InterleavedProject.load(project_path)

    raw_answer = os.environ.get(ANSWER_SOURCE_ENV, "").strip()
    answer_source: Path | None = None
    if raw_answer:
        answer_relative = Path(raw_answer)
        if answer_relative.is_absolute() or ".." in answer_relative.parts:
            raise RuntimeError(f"{ANSWER_SOURCE_ENV} must be repository-relative")
        answer_source = (ROOT / answer_relative).resolve()
        if not answer_source.is_relative_to(ROOT):
            raise RuntimeError("answer source escaped the repository")
    return RuntimeSettings(
        root=ROOT,
        project_path=project_path,
        project=project,
        answer_source=answer_source,
    )


def runtime_environment(
    project_path: Path,
    *,
    answer_source: str = "",
) -> dict[str, str]:
    """Return an environment fragment for child control-plane processes."""

    resolved = project_path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("project contract must be inside the repository")
    values = {PROJECT_ENV: resolved.relative_to(ROOT).as_posix()}
    if answer_source:
        values[ANSWER_SOURCE_ENV] = answer_source
    return values


def runtime_manifest(settings: RuntimeSettings) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "interleaved_runtime_binding",
        "project": settings.project.to_dict(),
        "project_identity_sha256": settings.project.identity_sha256,
        "project_contract": settings.project_path.relative_to(settings.root).as_posix(),
        "answer_source": (
            settings.answer_source.relative_to(settings.root).as_posix()
            if settings.answer_source is not None
            else None
        ),
    }


def render_runtime_manifest(settings: RuntimeSettings) -> str:
    return json.dumps(runtime_manifest(settings), indent=2, sort_keys=True) + "\n"
