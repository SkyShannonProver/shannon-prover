"""Shared build/runtime identity for read-only EasyCrypt companions."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.easycrypt.ec_env import (
    MANAGED_WHY3_CONFIG_ENV,
    get_ec_env,
)
from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.toolchain import load_easycrypt_lock, load_toolchain_receipt


NATIVE_COMPANION_PROTOCOL_VERSION = 2
NATIVE_ADAPTER_ABI = 3
NATIVE_SEMANTIC_FRAME_PREFIX = "SHANNON_NATIVE_SEMANTIC_V1:"
NATIVE_STATE_FRAME_PREFIX = "SHANNON_NATIVE_STATE_V1:"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXECUTABLE_NAME_RE = re.compile(r"^native_[a-z0-9_]+_adapter$")
_SOURCE_DIR = Path(__file__).resolve().parent


def parse_companion_result_frame(stdout: str, *, prefix: str) -> object:
    """Extract exactly one protocol frame amid EasyCrypt command output.

    Replaying a source unit can legitimately execute commands such as
    ``print``, whose human-oriented output shares the companion's stdout.
    Native adapters therefore emit one explicitly prefixed, single-line JSON
    frame.  Missing or duplicate frames fail closed; surrounding output is
    never guessed to be protocol data.
    """

    if not prefix or "\n" in prefix or "\r" in prefix:
        raise ValueError("native companion frame prefix is invalid")
    frames = [
        line[len(prefix):]
        for line in stdout.splitlines()
        if line.startswith(prefix)
    ]
    if len(frames) != 1 or not frames[0]:
        raise RuntimeError("native companion did not emit exactly one result frame")
    try:
        return json.loads(frames[0])
    except Exception as exc:
        raise RuntimeError("native companion result frame is invalid JSON") from exc


@dataclass(frozen=True)
class NativeCompanionIdentity:
    protocol_version: int
    easycrypt_toolchain_build_id: str
    easycrypt_library_sha256: str
    companion_binary_sha256: str
    why3_config_sha256: str

    def __post_init__(self) -> None:
        if type(self.protocol_version) is not int or (
            self.protocol_version != NATIVE_COMPANION_PROTOCOL_VERSION
        ):
            raise ValueError("unsupported native companion protocol")
        if not self.easycrypt_toolchain_build_id:
            raise ValueError("native companion requires EasyCrypt toolchain build ID")
        for value in (
            self.easycrypt_library_sha256,
            self.companion_binary_sha256,
            self.why3_config_sha256,
        ):
            if not _SHA256_RE.fullmatch(value):
                raise ValueError("native companion identity requires SHA-256")

    def identity_payload(self) -> dict[str, object]:
        return {
            "protocol_version": self.protocol_version,
            "easycrypt_toolchain_build_id": self.easycrypt_toolchain_build_id,
            "easycrypt_library_sha256": self.easycrypt_library_sha256,
            "companion_binary_sha256": self.companion_binary_sha256,
            "why3_config_sha256": self.why3_config_sha256,
        }

    @classmethod
    def from_payload(cls, value: object) -> "NativeCompanionIdentity":
        if type(value) is not dict:
            raise ValueError("native companion identity must be an object")
        payload = dict(value)
        allowed = {
            "protocol_version",
            "easycrypt_toolchain_build_id",
            "easycrypt_library_sha256",
            "companion_binary_sha256",
            "why3_config_sha256",
        }
        if set(payload) != allowed:
            raise ValueError("native companion identity has unexpected fields")
        return cls(
            protocol_version=payload.get("protocol_version"),
            easycrypt_toolchain_build_id=str(
                payload.get("easycrypt_toolchain_build_id") or ""
            ),
            easycrypt_library_sha256=str(
                payload.get("easycrypt_library_sha256") or ""
            ),
            companion_binary_sha256=str(
                payload.get("companion_binary_sha256") or ""
            ),
            why3_config_sha256=str(payload.get("why3_config_sha256") or ""),
        )

    @property
    def semantic_identity_sha256(self) -> str:
        encoded = json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def build_and_identify_companion(
    executable_name: str,
    runtime_identity: EasyCryptRuntimeIdentity,
    *,
    timeout: int = 120,
) -> tuple[Path, NativeCompanionIdentity]:
    """Build one named companion and prove executable/library agreement."""

    if not _EXECUTABLE_NAME_RE.fullmatch(executable_name):
        raise ValueError("invalid native companion executable name")
    if timeout <= 0:
        raise ValueError("native companion build timeout must be positive")
    env = get_ec_env()
    why3_config = Path(env[MANAGED_WHY3_CONFIG_ENV])
    dune = shutil.which("dune", path=env.get("PATH"))
    ocamlfind = shutil.which("ocamlfind", path=env.get("PATH"))
    if not dune or not ocamlfind:
        raise RuntimeError("native companion build tools are unavailable")
    lock = load_easycrypt_lock()
    if lock.native_adapter_abi != NATIVE_ADAPTER_ABI:
        raise RuntimeError("native companion implementation/lock ABI mismatch")
    executable = _SOURCE_DIR / "_build" / "default" / f"{executable_name}.exe"
    build = subprocess.run(
        [
            dune,
            "build",
            f"./{executable_name}.exe",
        ],
        cwd=str(_SOURCE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if build.returncode != 0 or not executable.is_file():
        raise RuntimeError("native companion build failed")
    receipt = load_toolchain_receipt()
    library_dir = Path(_ocamlfind_query(ocamlfind, env, "%d"))
    library_archive = library_dir / "ecLib.cmxa"
    library_sha256 = _sha256_file(library_archive)
    if runtime_identity.build_id != receipt.build_id or (
        runtime_identity.binary_sha256 != receipt.executable_sha256
    ):
        raise RuntimeError(
            "EasyCrypt executable differs from managed toolchain receipt"
        )
    if library_sha256 != receipt.library_sha256:
        raise RuntimeError("native EasyCrypt library differs from toolchain receipt")
    return executable, NativeCompanionIdentity(
        protocol_version=NATIVE_COMPANION_PROTOCOL_VERSION,
        easycrypt_toolchain_build_id=receipt.build_id,
        easycrypt_library_sha256=library_sha256,
        companion_binary_sha256=_sha256_file(executable),
        why3_config_sha256=_sha256_file(why3_config),
    )


def _ocamlfind_query(
    ocamlfind: str,
    env: dict[str, str],
    output_format: str,
) -> str:
    result = subprocess.run(
        [ocamlfind, "query", "-format", output_format, "easycrypt.ecLib"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise RuntimeError("cannot identify installed easycrypt.ecLib")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RuntimeError(f"cannot hash native dependency {path.name}") from exc
    return digest.hexdigest()
