"""Project binding for product projects and evaluation adapters."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from core.paths import REPO_ROOT
from workflow.interleaved.project import InterleavedProject, PROJECT_ENV


ROOT = REPO_ROOT
ANSWER_SOURCE_ENV = "SHANNON_INTERLEAVED_ANSWER_SOURCE"
DEFAULT_VERIFIER = "workflow/interleaved/verify.py"


def _repository_relative(raw: str, label: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"{label} must be repository-relative")
    return relative


@dataclass(frozen=True)
class ProjectContext:
    """One project contract bound to the checkout a process runs in.

    Entry points build it once and pass it down. A child process receives the
    same binding through :meth:`child_environment` and resolves it against its
    own checkout, so a job lane reads the copy of the contract checked out
    into it.
    """

    root: Path
    project_path: Path
    project: InterleavedProject
    answer_source: Path | None

    @classmethod
    def load(
        cls,
        project: str | Path,
        *,
        answer_source: str | Path | None = None,
        root: Path = ROOT,
    ) -> "ProjectContext":
        root = root.resolve()
        relative = _repository_relative(str(project), PROJECT_ENV)
        project_path = (root / relative).resolve()
        if not project_path.is_file():
            raise RuntimeError(f"interleaved project contract not found: {relative}")
        answer: Path | None = None
        if answer_source:
            answer_relative = _repository_relative(str(answer_source), ANSWER_SOURCE_ENV)
            answer = (root / answer_relative).resolve()
            if not answer.is_relative_to(root):
                raise RuntimeError("answer source escaped the repository")
        return cls(
            root=root,
            project_path=project_path,
            project=InterleavedProject.load(project_path),
            answer_source=answer,
        )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] = os.environ,
        *,
        root: Path = ROOT,
    ) -> "ProjectContext":
        raw_project = environ.get(PROJECT_ENV, "").strip()
        if not raw_project:
            raise RuntimeError(
                f"{PROJECT_ENV} is required; launch through python -m workflow.interleaved"
            )
        return cls.load(
            raw_project,
            answer_source=environ.get(ANSWER_SOURCE_ENV, "").strip() or None,
            root=root,
        )

    def child_environment(self, base: Mapping[str, str]) -> dict[str, str]:
        """Return ``base`` bound to this project for a child process."""

        environment = dict(base)
        environment[PROJECT_ENV] = self.project_path.relative_to(self.root).as_posix()
        if self.answer_source is None:
            environment.pop(ANSWER_SOURCE_ENV, None)
        else:
            environment[ANSWER_SOURCE_ENV] = self.answer_source.relative_to(
                self.root
            ).as_posix()
        return environment

    @property
    def target(self) -> Path:
        return self.root / self.project.target_file

    @property
    def verifier(self) -> str:
        return self.project.verifier or DEFAULT_VERIFIER

    def answer_source_visible(self, checkout: Path | None = None) -> bool:
        """Tell whether the answer-bearing source exists in ``checkout``."""

        if self.answer_source is None:
            return False
        if checkout is None:
            return self.answer_source.exists()
        return (checkout / self.answer_source.relative_to(self.root)).exists()

    @property
    def confined_patterns(self) -> tuple[str, ...]:
        """Sparse lane closure for the product plus the selected project."""

        def directory_pattern(directory: str) -> str:
            return "/" if directory == "." else f"/{directory}/"

        target_directory = Path(self.project.target_file).parent.as_posix()
        patterns = [
            "/core/",
            "/workflow/",
            "/tools/",
            "/easycrypt-src/",
            *(directory_pattern(item) for item in self.project.include_dirs),
            directory_pattern(target_directory),
            # The inner runner in a lane loads this same contract.
            "/" + self.project_path.relative_to(self.root).as_posix(),
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
                # The last matching pattern wins, so no include directory
                # can bring the answer-bearing examples back into a lane.
                patterns.append("!/easycrypt-src/examples/")
        return tuple(dict.fromkeys(patterns))
