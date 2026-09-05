"""Validated project contract shared by the interleaved control planes."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_SCHEMA_VERSION = 1
PROJECT_FILENAME = "interleaved_project.json"
PROJECT_ENV = "SHANNON_INTERLEAVED_PROJECT"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")


def _safe_relative(value: str, label: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be a safe repository-relative path")
    return path.as_posix()


@dataclass(frozen=True)
class InterleavedProject:
    """One product-level outer/inner proof project.

    Evaluation-only policies such as hiding a known answer live in reference
    adapters, not in this contract.
    """

    target_file: str
    final_lemma: str
    include_dirs: tuple[str, ...] = ("easycrypt-src/theories",)
    artifact_root: str = "artifacts/interleaved"
    max_parallel: int = 2
    max_inner_minutes: int = 120
    outer_timeout_seconds: int = 12 * 60 * 60
    verifier: str = ""
    prompt_file: str = ""
    source_probe_symbol: str = ""
    expected_task_files: tuple[str, ...] = ()
    delegation_region_begin: str = ""
    delegation_region_end: str = ""
    warm_handoff_sentinel_lemma: str = ""
    warm_handoff_sentinel_command: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_file", _safe_relative(self.target_file, "target_file"))
        object.__setattr__(self, "artifact_root", _safe_relative(self.artifact_root, "artifact_root"))
        if not _IDENTIFIER.fullmatch(self.final_lemma):
            raise ValueError("final_lemma must be an EasyCrypt identifier")
        if not self.include_dirs:
            raise ValueError("include_dirs must not be empty")
        object.__setattr__(
            self,
            "include_dirs",
            tuple(_safe_relative(item, "include_dir") for item in self.include_dirs),
        )
        if self.verifier:
            object.__setattr__(self, "verifier", _safe_relative(self.verifier, "verifier"))
        if self.prompt_file:
            object.__setattr__(self, "prompt_file", _safe_relative(self.prompt_file, "prompt_file"))
        if self.source_probe_symbol and not _IDENTIFIER.fullmatch(self.source_probe_symbol):
            raise ValueError("source_probe_symbol must be an EasyCrypt identifier")
        for name in self.expected_task_files:
            if Path(name).name != name or not name:
                raise ValueError("expected_task_files must contain plain filenames")
        if bool(self.delegation_region_begin) != bool(self.delegation_region_end):
            raise ValueError("delegation region markers must be configured together")
        if self.warm_handoff_sentinel_lemma and not _IDENTIFIER.fullmatch(
            self.warm_handoff_sentinel_lemma
        ):
            raise ValueError("warm_handoff_sentinel_lemma must be an identifier")
        if bool(self.warm_handoff_sentinel_lemma) != bool(
            self.warm_handoff_sentinel_command
        ):
            raise ValueError("warm-handoff sentinel lemma and command belong together")
        if self.max_parallel < 1:
            raise ValueError("max_parallel must be positive")
        if not 1 <= self.max_inner_minutes <= 24 * 60:
            raise ValueError("max_inner_minutes must be between 1 and 1440")
        if self.outer_timeout_seconds < 60:
            raise ValueError("outer_timeout_seconds must be at least 60")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": PROJECT_SCHEMA_VERSION, **asdict(self)}

    @property
    def identity_sha256(self) -> str:
        payload = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "InterleavedProject":
        if value.get("schema_version") != PROJECT_SCHEMA_VERSION:
            raise ValueError(
                f"project contract requires schema_version {PROJECT_SCHEMA_VERSION}"
            )
        unknown = set(value) - {
            "schema_version", "target_file", "final_lemma", "include_dirs",
            "artifact_root", "max_parallel", "max_inner_minutes",
            "outer_timeout_seconds", "verifier",
            "prompt_file", "source_probe_symbol", "expected_task_files",
            "delegation_region_begin", "delegation_region_end",
            "warm_handoff_sentinel_lemma", "warm_handoff_sentinel_command",
        }
        if unknown:
            raise ValueError("unknown project fields: " + ", ".join(sorted(unknown)))
        return cls(
            target_file=str(value.get("target_file") or ""),
            final_lemma=str(value.get("final_lemma") or ""),
            include_dirs=tuple(str(item) for item in value.get("include_dirs") or ()),
            artifact_root=str(value.get("artifact_root") or "artifacts/interleaved"),
            max_parallel=int(value.get("max_parallel", 2)),
            max_inner_minutes=int(value.get("max_inner_minutes", 120)),
            outer_timeout_seconds=int(value.get("outer_timeout_seconds", 12 * 60 * 60)),
            verifier=str(value.get("verifier") or ""),
            prompt_file=str(value.get("prompt_file") or ""),
            source_probe_symbol=str(value.get("source_probe_symbol") or ""),
            expected_task_files=tuple(
                str(item) for item in value.get("expected_task_files") or ()
            ),
            delegation_region_begin=str(value.get("delegation_region_begin") or ""),
            delegation_region_end=str(value.get("delegation_region_end") or ""),
            warm_handoff_sentinel_lemma=str(
                value.get("warm_handoff_sentinel_lemma") or ""
            ),
            warm_handoff_sentinel_command=str(
                value.get("warm_handoff_sentinel_command") or ""
            ),
        )

    @classmethod
    def load(cls, path: Path) -> "InterleavedProject":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("project contract must be a JSON object")
        return cls.from_dict(value)


def validate_project_files(root: Path, project: InterleavedProject) -> list[str]:
    """Return fail-closed, model-free product preflight errors."""

    errors: list[str] = []
    target = root / project.target_file
    if not target.is_file():
        errors.append(f"target file does not exist: {project.target_file}")
    for include in project.include_dirs:
        if not (root / include).is_dir():
            errors.append(f"include directory does not exist: {include}")
    for label, value in (("verifier", project.verifier), ("prompt", project.prompt_file)):
        if value and not (root / value).is_file():
            errors.append(f"{label} file does not exist: {value}")
    return errors
