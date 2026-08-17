"""Confined, integrity-aware artifact I/O for one proof session.

This module is deliberately domain-neutral: event-specific readers decide
which artifact subdirectory and payload contract apply.  The helpers here only
enforce that a referenced file is a regular file directly inside the requested
session subdirectory and compute the canonical writer-compatible JSON hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class SessionArtifactWriteError(RuntimeError):
    """A session artifact could not be written within its confined directory."""


@dataclass(frozen=True)
class ConfinedJsonObjectRead:
    """One confined JSON target and the data read from its opened inode.

    ``path`` is retained for diagnostics.  ``data is None`` means that the
    target was named inside the prescribed directory but was absent, was not a
    regular non-symlink file, changed while being opened, or was not a JSON
    object.
    """

    path: Path
    data: dict[str, Any] | None = None
    artifact_hash: str = ""

    @property
    def ok(self) -> bool:
        return self.data is not None


@dataclass(frozen=True)
class BoundJsonArtifactRead:
    """One current-session JSON artifact bound to its producing event."""

    data: dict[str, Any] | None = None
    path: Path | None = None
    artifact_hash: str = ""
    event: dict[str, Any] | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.data is not None and not self.errors


ArtifactBindingValidator = Callable[
    [dict[str, Any], dict[str, Any], str],
    tuple[list[str], list[str]],
]


def read_bound_current_json_artifact_event(
    session_dir: str | Path,
    event: dict[str, Any],
    *,
    event_type: str,
    subdir: str,
    validate_binding: ArtifactBindingValidator,
) -> BoundJsonArtifactRead:
    """Resolve one produced event to a confined current-session JSON object.

    This is the common live-reader skeleton for authoritative JSON surfaces.
    Domain validators retain ownership of artifact schemas and payload mirrors;
    this helper owns event schema, current-session identity, path confinement,
    regular-file reading, and canonical content hashing.  Historical/adopted
    reads are intentionally excluded: a current backend invocation may consume
    only the artifact occurrence it just produced in this session.
    """

    from core.easycrypt.session_events import event_payload, validate_event

    errors: list[str] = []
    warnings: list[str] = []
    if type(event) is not dict:
        return BoundJsonArtifactRead(errors=("produced event is not an object",))
    for issue in validate_event(event):
        rendered = f"{issue.code}: {issue.message}"
        if issue.severity == "error":
            errors.append(rendered)
        else:
            warnings.append(rendered)
    if event.get("type") != event_type:
        errors.append(f"event type must be {event_type!r}")

    resolved_session = Path(session_dir).resolve()
    expected_session = str(resolved_session)
    event_session_dir = event.get("session_dir")
    event_session_id = event.get("session_id")
    if event_session_dir != event_session_id:
        errors.append("event session_dir and session_id do not match")
    if event_session_dir != expected_session:
        errors.append(
            "event session_dir does not match the current session: "
            f"expected {expected_session!r}, got {event_session_dir!r}"
        )

    payload = event_payload(event)
    artifact_value = payload.get("artifact")
    if not isinstance(artifact_value, str) or not artifact_value:
        errors.append(f"{event_type} is missing artifact")
        return BoundJsonArtifactRead(
            event=event,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
    artifact_read = read_confined_hashed_json_object(
        resolved_session,
        artifact_value,
        subdir=subdir,
    )
    if artifact_read is None:
        errors.append(f"{event_type} artifact is missing or outside this session")
        return BoundJsonArtifactRead(
            event=event,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
    if not artifact_read.ok or artifact_read.data is None:
        errors.append(f"{event_type} artifact is not a readable JSON object")
        return BoundJsonArtifactRead(
            path=artifact_read.path,
            event=event,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
    binding_errors, binding_warnings = validate_binding(
        artifact_read.data,
        payload,
        artifact_read.artifact_hash,
    )
    errors.extend(binding_errors)
    warnings.extend(binding_warnings)
    return BoundJsonArtifactRead(
        data=None if errors else artifact_read.data,
        path=artifact_read.path,
        artifact_hash=artifact_read.artifact_hash,
        event=event,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def write_confined_text_artifact(
    session_dir: str | Path,
    *,
    subdir: str,
    filename: str,
    text: str,
) -> Path:
    """Atomically write text directly inside one non-symlink session subdir.

    The final file is created as a fresh temporary sibling and installed with
    an atomic rename. Existing symlinked artifact directories and symlinked
    final filenames fail closed; neither is followed for writing.
    """

    if not subdir or Path(subdir).name != subdir:
        raise SessionArtifactWriteError(
            f"artifact subdirectory must be one path component: {subdir!r}"
        )
    if not filename or Path(filename).name != filename:
        raise SessionArtifactWriteError(
            f"artifact filename must be one path component: {filename!r}"
        )
    if type(text) is not str:
        raise TypeError("artifact text must be a string")

    root = Path(session_dir)
    artifact_dir = root / subdir
    try:
        root.mkdir(parents=True, exist_ok=True)
        artifact_dir.mkdir(exist_ok=True)
        directory_stat = artifact_dir.lstat()
    except (OSError, RuntimeError) as exc:
        raise SessionArtifactWriteError(
            f"could not prepare session artifact directory {artifact_dir}: {exc}"
        ) from exc
    if stat.S_ISLNK(directory_stat.st_mode) or not stat.S_ISDIR(
        directory_stat.st_mode
    ):
        raise SessionArtifactWriteError(
            f"session artifact directory is not a real directory: {artifact_dir}"
        )

    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    directory_fd = -1
    temporary_name = f".{filename}.{uuid.uuid4().hex}.tmp"
    try:
        directory_fd = os.open(artifact_dir, directory_flags)
        opened_stat = os.fstat(directory_fd)
        if (
            opened_stat.st_dev != directory_stat.st_dev
            or opened_stat.st_ino != directory_stat.st_ino
            or not stat.S_ISDIR(opened_stat.st_mode)
        ):
            raise SessionArtifactWriteError(
                "session artifact directory changed while opening it"
            )
        try:
            target_stat = os.stat(
                filename,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            target_stat = None
        if target_stat is not None and (
            stat.S_ISLNK(target_stat.st_mode)
            or not stat.S_ISREG(target_stat.st_mode)
        ):
            raise SessionArtifactWriteError(
                f"artifact target is not a regular file: {artifact_dir / filename}"
            )

        file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        file_fd = os.open(
            temporary_name,
            file_flags,
            0o666,
            dir_fd=directory_fd,
        )
        try:
            with os.fdopen(file_fd, "w", encoding="utf-8", newline="") as handle:
                file_fd = -1
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if file_fd >= 0:
                os.close(file_fd)
        current_directory_stat = artifact_dir.lstat()
        if (
            stat.S_ISLNK(current_directory_stat.st_mode)
            or current_directory_stat.st_dev != opened_stat.st_dev
            or current_directory_stat.st_ino != opened_stat.st_ino
        ):
            raise SessionArtifactWriteError(
                "session artifact directory changed while writing"
            )
        os.replace(
            temporary_name,
            filename,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        temporary_name = ""
    except SessionArtifactWriteError:
        raise
    except OSError as exc:
        raise SessionArtifactWriteError(
            f"could not write confined session artifact "
            f"{artifact_dir / filename}: {exc}"
        ) from exc
    finally:
        if directory_fd >= 0:
            if temporary_name:
                try:
                    os.unlink(temporary_name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
            os.close(directory_fd)

    return artifact_dir / filename


def read_hashed_json_object(path: Path) -> tuple[dict[str, Any], str] | None:
    """Read a regular non-symlink JSON file through a checked parent dirfd."""

    parent_fd = _open_checked_directory(path.parent)
    if parent_fd is None:
        return None
    try:
        return _read_hashed_json_object_at(parent_fd, path.name)
    finally:
        os.close(parent_fd)


def read_confined_hashed_json_object(
    session_dir: str | Path,
    value: str,
    *,
    subdir: str,
    allow_frozen_copy: bool = False,
) -> ConfinedJsonObjectRead | None:
    """Read one event-linked JSON object through a confined directory fd.

    Path selection and file opening are deliberately separate: an event path
    may select only a direct child name of ``session_dir/subdir``; the bytes
    are then read with ``openat``-style dirfd operations, ``O_NOFOLLOW``, and
    inode checks.  A path swap after selection therefore cannot redirect the
    read outside the held session directory.
    """

    selected = _select_confined_session_artifact(
        session_dir,
        value,
        subdir=subdir,
        allow_frozen_copy=allow_frozen_copy,
    )
    if selected is None:
        return None
    artifact_dir_fd = _open_confined_artifact_directory(session_dir, subdir)
    if artifact_dir_fd is None:
        return None
    try:
        loaded = _read_hashed_json_object_at(
            artifact_dir_fd,
            selected.name,
        )
    finally:
        os.close(artifact_dir_fd)
    if loaded is None:
        return ConfinedJsonObjectRead(path=selected)
    data, artifact_hash = loaded
    return ConfinedJsonObjectRead(
        path=selected,
        data=data,
        artifact_hash=artifact_hash,
    )


def read_confined_json_object_directory(
    session_dir: str | Path,
    *,
    subdir: str,
    suffix: str = ".json",
) -> list[ConfinedJsonObjectRead]:
    """Enumerate and read direct artifact children through one held dirfd.

    Symlink entries remain visible as unreadable diagnostic paths, but neither
    file symlinks nor a symlinked artifact subdirectory are followed.
    """

    artifact_dir_fd = _open_confined_artifact_directory(session_dir, subdir)
    if artifact_dir_fd is None:
        return []
    try:
        try:
            names = sorted(os.listdir(artifact_dir_fd))
        except OSError:
            return []
        artifact_dir = Path(session_dir).absolute() / subdir
        reads: list[ConfinedJsonObjectRead] = []
        for name in names:
            if not name or Path(name).name != name or not name.endswith(suffix):
                continue
            path = artifact_dir / name
            loaded = _read_hashed_json_object_at(artifact_dir_fd, name)
            if loaded is None:
                reads.append(ConfinedJsonObjectRead(path=path))
                continue
            data, artifact_hash = loaded
            reads.append(ConfinedJsonObjectRead(
                path=path,
                data=data,
                artifact_hash=artifact_hash,
            ))
        return reads
    finally:
        os.close(artifact_dir_fd)


def _select_confined_session_artifact(
    session_dir: str | Path,
    value: str,
    *,
    subdir: str,
    allow_frozen_copy: bool,
) -> Path | None:
    """Select a confined lexical path without trusting the final component."""

    if (
        type(value) is not str
        or not value
        or not subdir
        or Path(subdir).name != subdir
    ):
        return None
    try:
        root = Path(session_dir).absolute()
        canonical_root = Path(session_dir).resolve(strict=True)
        expected_parent = canonical_root / subdir
        raw = Path(value)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        return None

    candidates = [raw] if raw.is_absolute() else [root.parent / raw, root / raw]
    for candidate in candidates:
        if _candidate_names_expected_parent(candidate, expected_parent):
            return root / subdir / candidate.name

    if (
        allow_frozen_copy
        and subdir in raw.parts
        and raw.name
        and Path(raw.name).name == raw.name
    ):
        candidate = root / subdir / raw.name
        if _candidate_names_expected_parent(candidate, expected_parent):
            return candidate
    return None


def _candidate_names_expected_parent(
    candidate: Path,
    expected_parent: Path,
) -> bool:
    if not candidate.name or Path(candidate.name).name != candidate.name:
        return False
    try:
        return candidate.parent.resolve(strict=True) == expected_parent
    except (FileNotFoundError, OSError, RuntimeError):
        return False


def _open_confined_artifact_directory(
    session_dir: str | Path,
    subdir: str,
) -> int | None:
    if not subdir or Path(subdir).name != subdir:
        return None
    try:
        canonical_root = Path(session_dir).resolve(strict=True)
    except (FileNotFoundError, OSError, RuntimeError):
        return None
    root_fd = _open_checked_directory(canonical_root)
    if root_fd is None:
        return None
    try:
        return _open_checked_child_directory(root_fd, subdir)
    finally:
        os.close(root_fd)


def _open_checked_directory(path: Path) -> int | None:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        return None
    try:
        before = path.lstat()
    except (FileNotFoundError, OSError, RuntimeError):
        return None
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        return None
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | no_follow
    try:
        directory_fd = os.open(path, flags)
    except OSError:
        return None
    try:
        after = os.fstat(directory_fd)
    except OSError:
        os.close(directory_fd)
        return None
    if (
        not stat.S_ISDIR(after.st_mode)
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
    ):
        os.close(directory_fd)
        return None
    return directory_fd


def _open_checked_child_directory(parent_fd: int, name: str) -> int | None:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None or not name or Path(name).name != name:
        return None
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return None
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        return None
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | no_follow
    try:
        directory_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError:
        return None
    try:
        after = os.fstat(directory_fd)
    except OSError:
        os.close(directory_fd)
        return None
    if (
        not stat.S_ISDIR(after.st_mode)
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
    ):
        os.close(directory_fd)
        return None
    return directory_fd


def _read_hashed_json_object_at(
    directory_fd: int,
    filename: str,
) -> tuple[dict[str, Any], str] | None:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None or not filename or Path(filename).name != filename:
        return None
    try:
        before = os.stat(
            filename,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        return None
    try:
        file_fd = os.open(
            filename,
            os.O_RDONLY | no_follow,
            dir_fd=directory_fd,
        )
    except OSError:
        return None
    try:
        try:
            after = os.fstat(file_fd)
        except OSError:
            return None
        if (
            not stat.S_ISREG(after.st_mode)
            or after.st_dev != before.st_dev
            or after.st_ino != before.st_ino
        ):
            return None
        try:
            with os.fdopen(file_fd, "r", encoding="utf-8") as handle:
                file_fd = -1
                raw = handle.read()
            data = json.loads(raw)
        except Exception:
            return None
    finally:
        if file_fd >= 0:
            os.close(file_fd)
    if not isinstance(data, dict):
        return None
    canonical = json.dumps(data, indent=2, sort_keys=True)
    return data, hashlib.sha1(canonical.encode("utf-8")).hexdigest()
