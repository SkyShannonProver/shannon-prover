"""Manager-owned EasyCrypt source navigation for eval proof nodes.

The provider never receives a generic filesystem capability. Reads and literal
searches validate the proof-stripped manifest, approved source/library roots,
and exact stripped-file digests. Exact declaration candidates are resolved by
EasyCrypt itself against that prepared environment.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from core.easycrypt.eval_source_prep import (
    PROOF_STRIPPED_PROJECT_CONTRACT,
    SOURCE_PREP_KIND,
    SOURCE_PREP_SCHEMA_VERSION,
)


SOURCE_RESOURCE_MANIFEST_ENV = "SHANNON_EASYCRYPT_SOURCE_MANIFEST"
SOURCE_READ_MAX_FILE_BYTES = 2_000_000
SOURCE_READ_MAX_LINES = 400
SOURCE_READ_MAX_OUTPUT_CHARS = 120_000
SOURCE_SEARCH_MAX_FILES = 1_000
SOURCE_SEARCH_MAX_TOTAL_BYTES = 20_000_000
SOURCE_SEARCH_MAX_RESULTS = 50
SOURCE_SEARCH_MAX_QUERY_CHARS = 256
SOURCE_RESOLVE_MAX_OUTPUT_CHARS = 120_000
SOURCE_SUFFIXES = frozenset({".ec", ".eca"})
SOURCE_SEARCH_SCOPES = frozenset({"all", "task", "libraries"})
_EASYCRYPT_IDENTIFIER = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*$"
)


class EasyCryptSourceResourceError(ValueError):
    """A source manifest or navigation request crossed the resource contract."""


@dataclass(frozen=True)
class EasyCryptSourceResponse:
    text: str
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "is_error": self.is_error}


@dataclass(frozen=True)
class EasyCryptSourceResource:
    """Validated source boundary owned by one proof-node runtime."""

    project_root: Path
    manifest_path: Path
    isolated_root: Path
    isolated_file: Path
    include_roots: tuple[Path, ...]
    stripped_sha256: Mapping[str, str]
    emit: Callable[[dict[str, Any]], None]

    @classmethod
    def from_environment(
        cls,
        *,
        project_root: Path,
        source_file: str | Path,
        target_lemma: str,
        include_dir: str | Path = "",
        environ: Mapping[str, str] | None = None,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> "EasyCryptSourceResource | None":
        env = environ if environ is not None else os.environ
        raw_manifest = str(env.get(SOURCE_RESOURCE_MANIFEST_ENV) or "").strip()
        if not raw_manifest:
            return None

        root = Path(project_root).resolve()
        manifest_path = _resolve_project_path(root, raw_manifest)
        if not manifest_path.is_file() or not manifest_path.is_relative_to(root):
            raise EasyCryptSourceResourceError(
                "source resource manifest escapes or is missing from the project"
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EasyCryptSourceResourceError(
                f"cannot read source resource manifest: {exc}"
            ) from exc
        if not isinstance(manifest, dict):
            raise EasyCryptSourceResourceError(
                "source resource manifest must be a JSON object"
            )
        if (
            manifest.get("schema_version") != SOURCE_PREP_SCHEMA_VERSION
            or manifest.get("kind") != SOURCE_PREP_KIND
            or manifest.get("source_contract")
            != PROOF_STRIPPED_PROJECT_CONTRACT
            or manifest.get("strip_proofs") is not True
        ):
            raise EasyCryptSourceResourceError(
                "source resource requires the canonical proof-stripped manifest"
            )
        if str(manifest.get("target_lemma") or "") != str(target_lemma):
            raise EasyCryptSourceResourceError(
                "source resource target lemma does not match the active node"
            )

        isolated_root = _resolve_project_path(
            root, str(manifest.get("isolated_root") or "")
        )
        isolated_file = _resolve_project_path(
            root, str(manifest.get("isolated_file") or "")
        )
        actual_source = _resolve_project_path(root, str(source_file))
        if (
            not isolated_root.is_dir()
            or not isolated_file.is_file()
            or not isolated_root.is_relative_to(root)
            or not isolated_file.is_relative_to(isolated_root)
            or actual_source != isolated_file
        ):
            raise EasyCryptSourceResourceError(
                "source resource does not bind the active isolated target"
            )

        raw_stripped = manifest.get("stripped_files")
        if not isinstance(raw_stripped, list) or not raw_stripped:
            raise EasyCryptSourceResourceError(
                "source resource manifest has no stripped-file ledger"
            )
        stripped: dict[str, str] = {}
        for item in raw_stripped:
            if not isinstance(item, Mapping):
                raise EasyCryptSourceResourceError(
                    "source resource stripped-file entry is invalid"
                )
            relative = _safe_relative_source_path(item.get("path"))
            digest = str(item.get("stripped_sha256") or "")
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise EasyCryptSourceResourceError(
                    "source resource stripped-file digest is invalid"
                )
            key = relative.as_posix()
            if key in stripped:
                raise EasyCryptSourceResourceError(
                    "source resource stripped-file path is duplicated"
                )
            candidate = (isolated_root / relative).resolve()
            if (
                not candidate.is_file()
                or not candidate.is_relative_to(isolated_root)
                or _sha256_bytes(candidate.read_bytes()) != digest
            ):
                raise EasyCryptSourceResourceError(
                    "source resource stripped-file ledger drifted"
                )
            stripped[key] = digest
        if int(manifest.get("stripped_file_count") or -1) != len(stripped):
            raise EasyCryptSourceResourceError(
                "source resource stripped-file count drifted"
            )
        target_key = isolated_file.relative_to(isolated_root).as_posix()
        if target_key not in stripped:
            raise EasyCryptSourceResourceError(
                "source resource target is missing from the stripped ledger"
            )

        include_roots: list[Path] = []
        if str(include_dir or "").strip():
            include = _resolve_project_path(root, str(include_dir))
            theories_root = (root / "easycrypt-src" / "theories").resolve()
            if (
                not include.is_dir()
                or not include.is_relative_to(theories_root)
            ):
                raise EasyCryptSourceResourceError(
                    "source resource include directory is not an EasyCrypt theories root"
                )
            include_roots.append(include)

        return cls(
            project_root=root,
            manifest_path=manifest_path,
            isolated_root=isolated_root,
            isolated_file=isolated_file,
            include_roots=tuple(include_roots),
            stripped_sha256=stripped,
            emit=emit or (lambda _event: None),
        )

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        return (self.isolated_root, *self.include_roots)

    @property
    def target_path(self) -> str:
        return self.isolated_file.relative_to(self.project_root).as_posix()

    @property
    def target_sha256(self) -> str:
        key = self.isolated_file.relative_to(self.isolated_root).as_posix()
        return self.stripped_sha256[key]

    @property
    def task_paths(self) -> tuple[str, ...]:
        prefix = self.isolated_root.relative_to(self.project_root)
        paths = [
            (prefix / relative).as_posix()
            for relative in sorted(self.stripped_sha256)
        ]
        return tuple(sorted(
            paths,
            key=lambda path: (path != self.target_path, path),
        ))

    @property
    def library_roots(self) -> tuple[str, ...]:
        return tuple(
            root.relative_to(self.project_root).as_posix()
            for root in self.include_roots
        )

    def render_source_map(self) -> str:
        """Render the small copy-ready catalog shown to each fresh agent context."""

        task_lines = [
            f"- `{path}`" + (" — active target" if path == self.target_path else "")
            for path in self.task_paths
        ]
        library_lines = [f"- `{root}/`" for root in self.library_roots]
        sections = [
            "### Readable EasyCrypt source map",
            "",
            "Prepared proof-stripped task files:",
            *task_lines,
        ]
        if library_lines:
            sections.extend([
                "",
                "Configured library roots (read an exact `.ec`/`.eca` path):",
                *library_lines,
            ])
        sections.extend([
            "",
            "Use `search_easycrypt_source` to locate text or declaration names, "
            "then copy an exact path and line range into `read_easycrypt_source`. "
            "Use `resolve_easycrypt_declaration` when a candidate symbol needs "
            "EasyCrypt-native confirmation.",
        ])
        return "\n".join(sections)

    def read(
        self,
        raw_arguments: Any,
        *,
        call_id: str = "",
    ) -> EasyCryptSourceResponse:
        """Return one bounded source excerpt or a non-fatal tool error."""

        try:
            payload = self._read_payload(raw_arguments)
        except EasyCryptSourceResourceError as exc:
            self.emit({
                "event": "easycrypt.source_resource.read",
                "status": "rejected",
                "call_id": str(call_id),
                "reason": str(exc)[:500],
            })
            return EasyCryptSourceResponse(
                text=f"SOURCE RESOURCE ERROR: {exc}",
                is_error=True,
            )
        self.emit({
            "event": "easycrypt.source_resource.read",
            "status": "served",
            "call_id": str(call_id),
            "path": payload["path"],
            "start_line": payload["start_line"],
            "end_line": payload["end_line"],
            "total_lines": payload["total_lines"],
            "content_sha256": payload["content_sha256"],
        })
        return EasyCryptSourceResponse(
            text=_render_source_excerpt(payload),
        )

    def search(
        self,
        raw_arguments: Any,
        *,
        call_id: str = "",
    ) -> EasyCryptSourceResponse:
        """Return bounded literal matches with copy-ready paths and line numbers."""

        try:
            payload = self._search_payload(raw_arguments)
        except EasyCryptSourceResourceError as exc:
            self.emit({
                "event": "easycrypt.source_resource.search",
                "status": "rejected",
                "call_id": str(call_id),
                "reason": str(exc)[:500],
            })
            return EasyCryptSourceResponse(
                text=f"SOURCE RESOURCE ERROR: {exc}",
                is_error=True,
            )
        self.emit({
            "event": "easycrypt.source_resource.search",
            "status": "served",
            "call_id": str(call_id),
            "query": payload["query"],
            "query_sha256": _sha256_bytes(payload["query"].encode("utf-8")),
            "scope": payload["scope"],
            "path": payload["path"],
            "files_scanned": payload["files_scanned"],
            "match_count": payload["match_count"],
            "shown_count": len(payload["matches"]),
            "truncated": payload["truncated"],
            "locations": [
                f"{match['path']}:{match['line']}"
                for match in payload["matches"][:8]
            ],
        })
        return EasyCryptSourceResponse(text=_render_source_matches(payload))

    def resolve_declaration(
        self,
        raw_arguments: Any,
        *,
        call_id: str = "",
        timeout_seconds: float = 60.0,
    ) -> EasyCryptSourceResponse:
        """Resolve one exact candidate with EasyCrypt's native namespace."""

        requested = ""
        try:
            if not isinstance(raw_arguments, Mapping):
                raise EasyCryptSourceResourceError("arguments must be an object")
            if set(raw_arguments) - {"symbol"}:
                raise EasyCryptSourceResourceError(
                    "arguments contain unknown fields"
                )
            requested = str(raw_arguments.get("symbol") or "").strip()
            if (
                not requested
                or len(requested) > SOURCE_SEARCH_MAX_QUERY_CHARS
                or _EASYCRYPT_IDENTIFIER.fullmatch(requested) is None
            ):
                raise EasyCryptSourceResourceError(
                    "symbol must be one exact EasyCrypt identifier"
                )

            from core.easycrypt.compiler_namespace_adapter import (
                load_exact_declarations,
            )

            result = load_exact_declarations(
                [requested],
                self.isolated_file,
                (self.isolated_root, *self.include_roots),
                timeout=max(0.001, min(60.0, float(timeout_seconds))),
            ).get(requested)
            if not isinstance(result, Mapping):
                raise EasyCryptSourceResourceError(
                    "EasyCrypt returned no declaration result"
                )
            status = str(result.get("status") or "error")
            if status == "miss":
                response = EasyCryptSourceResponse(
                    text=(
                        f"EasyCrypt did not resolve the exact declaration "
                        f"`{requested}` in the prepared target environment. "
                        "Use `search_easycrypt_source` to find lexical candidates; "
                        "a lexical match is not a resolved declaration."
                    )
                )
            elif status == "resolved":
                body = str(result.get("body") or "").strip()
                resolved = str(result.get("resolved") or "").strip()
                kind = str(result.get("kind") or "declaration").strip()
                if not body or not resolved:
                    raise EasyCryptSourceResourceError(
                        "EasyCrypt returned an incomplete declaration"
                    )
                if len(body) > SOURCE_RESOLVE_MAX_OUTPUT_CHARS:
                    raise EasyCryptSourceResourceError(
                        "resolved declaration exceeds the output limit"
                    )
                response = EasyCryptSourceResponse(text=(
                    "EasyCrypt-native declaration resolved.\n"
                    f"requested: `{requested}`\n"
                    f"resolved: `{resolved}`\n"
                    f"kind: `{kind}`\n\n"
                    "```easycrypt\n"
                    f"{body}\n"
                    "```\n\n"
                    "This confirms namespace resolution only; the current proof "
                    "state remains owned by `submit_proof_intent`."
                ))
            else:
                error = str(result.get("error") or "native resolver failed")
                raise EasyCryptSourceResourceError(
                    f"EasyCrypt declaration resolution failed: {error[:500]}"
                )
        except EasyCryptSourceResourceError as exc:
            self.emit({
                "event": "easycrypt.source_resource.resolve",
                "status": "rejected",
                "call_id": str(call_id),
                "requested": requested,
                "reason": str(exc)[:500],
            })
            return EasyCryptSourceResponse(
                text=f"SOURCE RESOURCE ERROR: {exc}",
                is_error=True,
            )
        self.emit({
            "event": "easycrypt.source_resource.resolve",
            "status": status,
            "call_id": str(call_id),
            "requested": requested,
            "resolved": str(result.get("resolved") or ""),
            "declaration_kind": str(result.get("kind") or ""),
        })
        return response

    def _read_payload(self, raw_arguments: Any) -> dict[str, Any]:
        if not isinstance(raw_arguments, Mapping):
            raise EasyCryptSourceResourceError("arguments must be an object")
        if set(raw_arguments) - {"path", "start_line", "end_line"}:
            raise EasyCryptSourceResourceError("arguments contain unknown fields")
        relative, _candidate, _raw, text = self._load_source_file(
            raw_arguments.get("path")
        )
        lines = text.splitlines()
        total_lines = len(lines)
        start = _positive_int(raw_arguments.get("start_line", 1), "start_line")
        default_end = min(total_lines, start + SOURCE_READ_MAX_LINES - 1)
        end = _positive_int(raw_arguments.get("end_line", default_end), "end_line")
        if start > end:
            raise EasyCryptSourceResourceError("start_line must not exceed end_line")
        if end - start + 1 > SOURCE_READ_MAX_LINES:
            raise EasyCryptSourceResourceError(
                f"one read may return at most {SOURCE_READ_MAX_LINES} lines"
            )
        if total_lines == 0:
            if start != 1 or end != 1:
                raise EasyCryptSourceResourceError("empty source has no requested range")
            excerpt = ""
            actual_end = 0
        else:
            if start > total_lines:
                raise EasyCryptSourceResourceError("start_line exceeds the source length")
            actual_end = min(end, total_lines)
            excerpt = "\n".join(lines[start - 1:actual_end])
        if len(excerpt) > SOURCE_READ_MAX_OUTPUT_CHARS:
            raise EasyCryptSourceResourceError("source excerpt exceeds the output limit")
        return {
            "path": relative.as_posix(),
            "start_line": start,
            "end_line": actual_end,
            "total_lines": total_lines,
            "has_more": actual_end < total_lines,
            "content_sha256": _sha256_bytes(excerpt.encode("utf-8")),
            "content": excerpt,
        }

    def _search_payload(self, raw_arguments: Any) -> dict[str, Any]:
        if not isinstance(raw_arguments, Mapping):
            raise EasyCryptSourceResourceError("arguments must be an object")
        allowed_fields = {
            "query", "scope", "path", "case_sensitive", "max_results",
            "context_lines",
        }
        if set(raw_arguments) - allowed_fields:
            raise EasyCryptSourceResourceError("arguments contain unknown fields")
        query = raw_arguments.get("query")
        if (
            not isinstance(query, str)
            or not query
            or len(query) > SOURCE_SEARCH_MAX_QUERY_CHARS
            or "\n" in query
            or "\r" in query
        ):
            raise EasyCryptSourceResourceError(
                "query must be one non-empty line of at most 256 characters"
            )
        scope = str(raw_arguments.get("scope") or "all")
        if scope not in SOURCE_SEARCH_SCOPES:
            raise EasyCryptSourceResourceError(
                "scope must be one of: all, task, libraries"
            )
        case_sensitive = raw_arguments.get("case_sensitive", True)
        if not isinstance(case_sensitive, bool):
            raise EasyCryptSourceResourceError("case_sensitive must be boolean")
        max_results = raw_arguments.get("max_results", 20)
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or not 1 <= max_results <= SOURCE_SEARCH_MAX_RESULTS
        ):
            raise EasyCryptSourceResourceError(
                f"max_results must be 1..{SOURCE_SEARCH_MAX_RESULTS}"
            )
        context_lines = raw_arguments.get("context_lines", 0)
        if (
            isinstance(context_lines, bool)
            or not isinstance(context_lines, int)
            or not 0 <= context_lines <= 3
        ):
            raise EasyCryptSourceResourceError("context_lines must be 0..3")

        requested_path = raw_arguments.get("path")
        if requested_path is not None:
            relative, candidate, _raw, _text = self._load_source_file(
                requested_path
            )
            if scope == "task" and not candidate.is_relative_to(
                self.isolated_root
            ):
                raise EasyCryptSourceResourceError(
                    "requested path is outside the task search scope"
                )
            if scope == "libraries" and not any(
                candidate.is_relative_to(root) for root in self.include_roots
            ):
                raise EasyCryptSourceResourceError(
                    "requested path is outside the libraries search scope"
                )
            candidates = [relative]
        else:
            candidates = self._search_candidates(scope)

        needle = query if case_sensitive else query.casefold()
        matches: list[dict[str, Any]] = []
        match_count = 0
        scanned_bytes = 0
        files_scanned = 0
        for relative in candidates:
            _relative, _candidate, raw, text = self._load_source_file(
                relative.as_posix()
            )
            scanned_bytes += len(raw)
            files_scanned += 1
            if files_scanned > SOURCE_SEARCH_MAX_FILES:
                raise EasyCryptSourceResourceError(
                    "source search exceeded the file budget"
                )
            if scanned_bytes > SOURCE_SEARCH_MAX_TOTAL_BYTES:
                raise EasyCryptSourceResourceError(
                    "source search exceeded the byte budget"
                )
            lines = text.splitlines()
            for index, line in enumerate(lines):
                haystack = line if case_sensitive else line.casefold()
                if needle not in haystack:
                    continue
                match_count += 1
                if len(matches) >= max_results:
                    continue
                start = max(0, index - context_lines)
                end = min(len(lines), index + context_lines + 1)
                matches.append({
                    "path": relative.as_posix(),
                    "line": index + 1,
                    "context_start": start + 1,
                    "context": tuple(lines[start:end]),
                })
        payload = {
            "query": query,
            "scope": scope,
            "path": (
                str(requested_path).strip()
                if isinstance(requested_path, str)
                else ""
            ),
            "case_sensitive": case_sensitive,
            "context_lines": context_lines,
            "files_scanned": files_scanned,
            "match_count": match_count,
            "truncated": match_count > len(matches),
            "matches": tuple(matches),
        }
        rendered = _render_source_matches(payload)
        if len(rendered) > SOURCE_READ_MAX_OUTPUT_CHARS:
            raise EasyCryptSourceResourceError(
                "source search result exceeds the output limit"
            )
        return payload

    def _search_candidates(self, scope: str) -> list[Path]:
        candidates: dict[str, Path] = {}
        if scope in {"all", "task"}:
            for key in sorted(self.stripped_sha256):
                candidate = (self.isolated_root / key).resolve()
                relative = candidate.relative_to(self.project_root)
                candidates[relative.as_posix()] = relative
        if scope in {"all", "libraries"}:
            for root in self.include_roots:
                for candidate in root.rglob("*"):
                    resolved = candidate.resolve()
                    if (
                        candidate.is_file()
                        and candidate.suffix.lower() in SOURCE_SUFFIXES
                        and resolved.is_relative_to(root)
                    ):
                        relative = resolved.relative_to(self.project_root)
                        candidates[relative.as_posix()] = relative
        return [candidates[key] for key in sorted(candidates)]

    def _load_source_file(
        self,
        raw_path: Any,
    ) -> tuple[Path, Path, bytes, str]:
        relative = _safe_relative_source_path(raw_path)
        candidate = (self.project_root / relative).resolve()
        containing_root = next(
            (root for root in self.allowed_roots if candidate.is_relative_to(root)),
            None,
        )
        if containing_root is None or not candidate.is_file():
            raise EasyCryptSourceResourceError(
                "path is outside the prepared source and configured library roots"
            )
        if candidate.suffix.lower() not in SOURCE_SUFFIXES:
            raise EasyCryptSourceResourceError("only .ec and .eca files are readable")
        raw = candidate.read_bytes()
        if len(raw) > SOURCE_READ_MAX_FILE_BYTES:
            raise EasyCryptSourceResourceError("source file exceeds the read limit")
        if containing_root == self.isolated_root:
            key = candidate.relative_to(self.isolated_root).as_posix()
            expected = self.stripped_sha256.get(key)
            if expected is None or _sha256_bytes(raw) != expected:
                raise EasyCryptSourceResourceError(
                    "proof-stripped source file is absent from or drifted against its manifest"
                )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EasyCryptSourceResourceError("source file is not UTF-8") from exc
        return relative, candidate, raw, text


def _resolve_project_path(project_root: Path, raw: str) -> Path:
    path = Path(str(raw or "").strip())
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _safe_relative_source_path(raw: Any) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise EasyCryptSourceResourceError("source path must be a non-empty string")
    path = Path(raw.strip())
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() not in SOURCE_SUFFIXES:
        raise EasyCryptSourceResourceError(
            "source path must be a repository-relative .ec or .eca file"
        )
    return path


def _positive_int(raw: Any, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise EasyCryptSourceResourceError(f"{label} must be a positive integer")
    return raw


def _render_source_excerpt(payload: Mapping[str, Any]) -> str:
    start = int(payload["start_line"])
    end = int(payload["end_line"])
    total = int(payload["total_lines"])
    path = str(payload["path"])
    width = max(1, len(str(max(end, total))))
    content = str(payload["content"])
    body = "\n".join(
        f"{line_number:>{width}} | {line}"
        for line_number, line in enumerate(content.splitlines(), start=start)
    )
    header = (
        f"{path} — empty file"
        if total == 0
        else f"{path} — lines {start}-{end} of {total}"
    )
    if payload["has_more"]:
        footer = f"\n\nMore lines available; continue at start_line={end + 1}."
    else:
        footer = ""
    return header + ("\n" + body if body else "") + footer


def _render_source_matches(payload: Mapping[str, Any]) -> str:
    query = str(payload["query"])
    match_count = int(payload["match_count"])
    shown = payload["matches"]
    header = (
        f"Literal EasyCrypt source search for `{query}`: {match_count} match"
        + ("" if match_count == 1 else "es")
        + f" across {int(payload['files_scanned'])} file"
        + ("" if int(payload["files_scanned"]) == 1 else "s")
        + "."
    )
    if not shown:
        return (
            header
            + "\nNo lexical match was found. This is not an EasyCrypt namespace "
            "resolution result."
        )
    blocks = [header]
    context_lines = int(payload["context_lines"])
    for match in shown:
        path = str(match["path"])
        line_number = int(match["line"])
        context_start = int(match["context_start"])
        context = tuple(match["context"])
        if context_lines == 0:
            blocks.append(f"{path}:{line_number}: {context[0]}")
            continue
        rendered = [f"{path}:{line_number}"]
        for offset, line in enumerate(context, start=context_start):
            marker = ">" if offset == line_number else " "
            rendered.append(f"{marker} {offset} | {line}")
        blocks.append("\n".join(rendered))
    if payload["truncated"]:
        blocks.append(
            "Results truncated; narrow `query`, `scope`, or `path`, or raise "
            f"`max_results` up to {SOURCE_SEARCH_MAX_RESULTS}."
        )
    blocks.append(
        "Matches are lexical candidates, not resolved declarations. Copy a "
        "path and line range into `read_easycrypt_source`, or pass one exact "
        "candidate name to `resolve_easycrypt_declaration`."
    )
    return "\n\n".join(blocks)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = [
    "EasyCryptSourceResponse",
    "EasyCryptSourceResource",
    "EasyCryptSourceResourceError",
    "SOURCE_RESOURCE_MANIFEST_ENV",
    "SOURCE_READ_MAX_LINES",
    "SOURCE_SEARCH_MAX_RESULTS",
]
