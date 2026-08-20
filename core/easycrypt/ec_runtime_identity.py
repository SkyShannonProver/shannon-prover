"""Stable semantic identity for the EasyCrypt executable in one session.

The proof-state compiler may reuse EasyCrypt's typed semantics only if the
runtime that produced a result is explicit.  A package label such as ``dev``
or a source checkout path is not enough: separate machines can attach that
label to different commits or binaries.  The semantic identity therefore
binds EasyCrypt's self-reported build ID to the exact executable digest.

Discovery belongs to the retained prover runtime, not to a compiler pass.
Compiler contracts may carry this immutable value but must not rediscover or
reinterpret it.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.easycrypt.ec_env import get_ec_env
from core.easycrypt.session.session_events import read_events
from core.easycrypt.toolchain import load_easycrypt_lock


EASYCRYPT_RUNTIME_IDENTITY_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BUILD_ID_RE = re.compile(r"^git-hash:\s*(\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class EasyCryptRuntimeIdentity:
    """Path-independent identity of one EasyCrypt semantic runtime."""

    build_id: str
    binary_sha256: str

    def __post_init__(self) -> None:
        if (
            not self.build_id
            or self.build_id != self.build_id.strip()
            or any(char.isspace() for char in self.build_id)
        ):
            raise ValueError("EasyCrypt runtime identity requires a build ID")
        if not _SHA256_RE.fullmatch(self.binary_sha256):
            raise ValueError("EasyCrypt runtime identity requires binary SHA-256")

    def identity_payload(self) -> dict[str, object]:
        return {
            "schema_version": EASYCRYPT_RUNTIME_IDENTITY_SCHEMA_VERSION,
            "verifier": "easycrypt",
            "build_id": self.build_id,
            "binary_sha256": self.binary_sha256,
        }

    @property
    def semantic_identity_sha256(self) -> str:
        encoded = json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_payload(self) -> dict[str, object]:
        return {
            **self.identity_payload(),
            "semantic_identity_sha256": self.semantic_identity_sha256,
        }

    @classmethod
    def from_payload(cls, value: object) -> "EasyCryptRuntimeIdentity":
        if type(value) is not dict:
            raise ValueError("EasyCrypt runtime identity must be an object")
        payload = dict(value)
        if payload.get("schema_version") != (
            EASYCRYPT_RUNTIME_IDENTITY_SCHEMA_VERSION
        ) or type(payload.get("schema_version")) is not int:
            raise ValueError("unsupported EasyCrypt runtime identity schema")
        if payload.get("verifier") != "easycrypt":
            raise ValueError("runtime identity is not for EasyCrypt")
        identity = cls(
            build_id=str(payload.get("build_id") or ""),
            binary_sha256=str(payload.get("binary_sha256") or ""),
        )
        if payload.get("semantic_identity_sha256") != (
            identity.semantic_identity_sha256
        ):
            raise ValueError("EasyCrypt runtime semantic identity hash mismatch")
        allowed = {
            "schema_version",
            "verifier",
            "build_id",
            "binary_sha256",
            "semantic_identity_sha256",
        }
        if set(payload) != allowed:
            raise ValueError("EasyCrypt runtime identity has unexpected fields")
        return identity


def discover_easycrypt_runtime_identity() -> EasyCryptRuntimeIdentity:
    """Inspect the executable selected by the canonical EasyCrypt environment."""

    env = get_ec_env()
    binary_name = shutil.which("easycrypt", path=env.get("PATH"))
    if not binary_name:
        raise RuntimeError("EasyCrypt executable is unavailable")
    binary_path = Path(binary_name).resolve()
    binary_sha256 = _sha256_file(binary_path)
    try:
        result = subprocess.run(
            [str(binary_path), "config"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("cannot read EasyCrypt runtime configuration") from exc
    if result.returncode != 0:
        raise RuntimeError("EasyCrypt config failed while identifying runtime")
    match = _BUILD_ID_RE.search(result.stdout + "\n" + result.stderr)
    if match is None:
        raise RuntimeError("EasyCrypt config did not report git-hash")
    lock = load_easycrypt_lock()
    if match.group(1) != lock.expected_build_id:
        raise RuntimeError("EasyCrypt runtime does not match repository lock")
    return EasyCryptRuntimeIdentity(
        build_id=match.group(1),
        binary_sha256=binary_sha256,
    )


def verified_session_runtime_identity(
    session_dir: str | Path,
) -> EasyCryptRuntimeIdentity:
    """Return the session runtime only after stored/event/live agreement.

    Old sessions that predate this contract intentionally fail.  Restarting
    creates a new explicit semantic boundary; silently adopting the currently
    installed executable would make a mixed-runtime proof look homogeneous.
    """

    path = Path(session_dir)
    meta_path = path / "session_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("session runtime identity metadata is unavailable") from exc
    if type(meta) is not dict:
        raise ValueError("session runtime identity metadata is invalid")
    stored = EasyCryptRuntimeIdentity.from_payload(
        meta.get("easycrypt_runtime_identity")
    )

    starts = [
        event for event in read_events(path)
        if event.get("type") == "session.started"
    ]
    if not starts:
        raise ValueError("session runtime identity has no start event")
    start_payload = starts[-1].get("payload")
    if type(start_payload) is not dict or (
        start_payload.get("easycrypt_runtime_identity_sha256")
        != stored.semantic_identity_sha256
    ):
        raise ValueError("session start event runtime identity does not match metadata")

    observed = discover_easycrypt_runtime_identity()
    if observed != stored:
        raise ValueError(
            "EasyCrypt runtime changed after session start; restart the session"
        )
    return observed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
