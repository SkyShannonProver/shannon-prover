"""Repository-locked EasyCrypt toolchain identity.

Shannon supports one audited EasyCrypt native ABI at a time.  The lock binds
the vendored source/theories to an official release commit.  A generated local
receipt then binds that lock to the exact executable and ecLib artifacts built
inside the repository-managed opam root.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


EASYCRYPT_LOCK_SCHEMA_VERSION = 1
EASYCRYPT_RECEIPT_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_OPAM_ENV_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)='([^']*)'; export \1;$"
)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
EASYCRYPT_LOCK_PATH = Path(__file__).with_name("easycrypt.lock.json")

# These values route live EasyCrypt work and are deliberately configured after
# the orchestrator's toolchain preflight.  They must not be frozen inside the
# cached opam environment assembled by ``_managed_environment_items``.
_RUNTIME_ROUTE_ENV_NAMES = (
    "EC_DAEMON_SOCKET",
    "WHY3EC_SOCKET",
)


@dataclass(frozen=True)
class EasyCryptLock:
    release_tag: str
    source_commit: str
    source_repository: str
    expected_build_id: str
    ocaml_package: str
    native_adapter_abi: int
    source_manifest_sha256: str

    def __post_init__(self) -> None:
        if not self.release_tag or not self.expected_build_id:
            raise ValueError("EasyCrypt lock requires release/build identity")
        if not re.fullmatch(r"ocaml-base-compiler\.\d+\.\d+\.\d+", self.ocaml_package):
            raise ValueError("EasyCrypt lock OCaml package is invalid")
        if not _COMMIT_RE.fullmatch(self.source_commit):
            raise ValueError("EasyCrypt lock requires a full source commit")
        if not self.source_repository.startswith("https://github.com/EasyCrypt/"):
            raise ValueError("EasyCrypt lock source repository is not canonical")
        if type(self.native_adapter_abi) is not int or self.native_adapter_abi < 1:
            raise ValueError("EasyCrypt lock native adapter ABI is invalid")
        if not _SHA256_RE.fullmatch(self.source_manifest_sha256):
            raise ValueError("EasyCrypt lock source manifest hash is invalid")

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": EASYCRYPT_LOCK_SCHEMA_VERSION,
            "distribution": "EasyCrypt",
            "release_tag": self.release_tag,
            "source_commit": self.source_commit,
            "source_repository": self.source_repository,
            "expected_build_id": self.expected_build_id,
            "ocaml_package": self.ocaml_package,
            "native_adapter_abi": self.native_adapter_abi,
            "source_manifest_sha256": self.source_manifest_sha256,
        }

    @property
    def identity_sha256(self) -> str:
        return _canonical_json_sha256(self.payload())


@dataclass(frozen=True)
class EasyCryptToolchainReceipt:
    lock_identity_sha256: str
    build_id: str
    executable_sha256: str
    library_sha256: str

    def __post_init__(self) -> None:
        for value in (
            self.lock_identity_sha256,
            self.executable_sha256,
            self.library_sha256,
        ):
            if not _SHA256_RE.fullmatch(value):
                raise ValueError("EasyCrypt toolchain receipt requires SHA-256")
        if not self.build_id:
            raise ValueError("EasyCrypt toolchain receipt requires build ID")

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": EASYCRYPT_RECEIPT_SCHEMA_VERSION,
            "lock_identity_sha256": self.lock_identity_sha256,
            "build_id": self.build_id,
            "executable_sha256": self.executable_sha256,
            "library_sha256": self.library_sha256,
        }


@lru_cache(maxsize=1)
def load_easycrypt_lock() -> EasyCryptLock:
    try:
        value = json.loads(EASYCRYPT_LOCK_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("EasyCrypt revision lock is unavailable") from exc
    if type(value) is not dict:
        raise RuntimeError("EasyCrypt revision lock must be an object")
    expected = {
        "schema_version",
        "distribution",
        "release_tag",
        "source_commit",
        "source_repository",
        "expected_build_id",
        "ocaml_package",
        "native_adapter_abi",
        "source_manifest_sha256",
    }
    if set(value) != expected or value.get("schema_version") != 1 or (
        value.get("distribution") != "EasyCrypt"
    ):
        raise RuntimeError("EasyCrypt revision lock schema is invalid")
    return EasyCryptLock(
        release_tag=str(value.get("release_tag") or ""),
        source_commit=str(value.get("source_commit") or ""),
        source_repository=str(value.get("source_repository") or ""),
        expected_build_id=str(value.get("expected_build_id") or ""),
        ocaml_package=str(value.get("ocaml_package") or ""),
        native_adapter_abi=value.get("native_adapter_abi"),
        source_manifest_sha256=str(value.get("source_manifest_sha256") or ""),
    )


def easycrypt_source_manifest_sha256(source_root: Path | None = None) -> str:
    """Hash path and bytes of every file in the locked vendored snapshot."""

    root = (source_root or (_PROJECT_ROOT / "easycrypt-src")).resolve()
    if not root.is_dir():
        raise RuntimeError("vendored EasyCrypt source is unavailable")
    digest = hashlib.sha256(b"shannon-easycrypt-source-manifest-v1\0")
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise RuntimeError("vendored EasyCrypt source is empty")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def verify_locked_easycrypt_source() -> EasyCryptLock:
    lock = load_easycrypt_lock()
    actual = easycrypt_source_manifest_sha256()
    if actual != lock.source_manifest_sha256 and _sparse_checkout_enabled():
        actual = _git_head_easycrypt_source_manifest_sha256()
    if actual != lock.source_manifest_sha256:
        raise RuntimeError("vendored EasyCrypt source differs from revision lock")
    return lock


def _sparse_checkout_enabled() -> bool:
    result = subprocess.run(
        ["git", "config", "--bool", "core.sparseCheckout"],
        cwd=_PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_head_easycrypt_source_manifest_sha256() -> str:
    """Hash the committed vendored snapshot without hydrating sparse files.

    Sparse experiment worktrees intentionally omit answer-bearing examples.
    The visible portion must still be clean, and no untracked source may be
    present; the missing bytes are streamed from the pinned HEAD archive only
    inside this trusted lock verifier and are never written into the worktree.
    """

    changed = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", "easycrypt-src"],
        cwd=_PROJECT_ROOT,
        check=False,
    )
    if changed.returncode != 0:
        raise RuntimeError("vendored EasyCrypt source has tracked changes")
    untracked = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "easycrypt-src",
        ],
        cwd=_PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if untracked.returncode != 0 or untracked.stdout.strip():
        raise RuntimeError("vendored EasyCrypt source has untracked files")
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD", "easycrypt-src"],
        cwd=_PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if archive.returncode != 0:
        raise RuntimeError("cannot read vendored EasyCrypt snapshot from Git HEAD")

    digest = hashlib.sha256(b"shannon-easycrypt-source-manifest-v1\0")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as stream:
        members = sorted(
            (member for member in stream.getmembers() if member.isfile()),
            # Match ``sorted(Path.rglob(...))`` above exactly.  Path ordering is
            # component-wise, not the raw slash-containing string order.
            key=lambda member: Path(member.name[len("easycrypt-src/"):]),
        )
        if not members:
            raise RuntimeError("Git HEAD vendored EasyCrypt snapshot is empty")
        for member in members:
            prefix = "easycrypt-src/"
            if not member.name.startswith(prefix):
                raise RuntimeError("Git archive escaped vendored EasyCrypt root")
            relative = member.name[len(prefix):].encode("utf-8")
            source = stream.extractfile(member)
            if source is None:
                raise RuntimeError("cannot read a vendored EasyCrypt Git blob")
            data = source.read()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
    return digest.hexdigest()


def repository_storage_root() -> Path:
    """Return the shared checkout root even when called from a git worktree."""

    marker = _PROJECT_ROOT / ".git"
    if marker.is_dir():
        return _PROJECT_ROOT
    if marker.is_file():
        line = marker.read_text(encoding="utf-8").strip()
        if line.startswith("gitdir:"):
            gitdir = Path(line.split(":", 1)[1].strip()).resolve()
            for parent in (gitdir, *gitdir.parents):
                if parent.name == ".git":
                    return parent.parent
    raise RuntimeError("cannot locate shared repository storage root")


def managed_opam_root() -> Path:
    release = load_easycrypt_lock().release_tag
    if not re.fullmatch(r"r\d{4}\.\d{2}", release):
        raise RuntimeError("EasyCrypt release is unsafe for toolchain path")
    return repository_storage_root() / ".toolchains" / f"opam-{release}"


def managed_switch_name() -> str:
    return f"shannon-easycrypt-{load_easycrypt_lock().release_tag}"


def toolchain_receipt_path() -> Path:
    return managed_opam_root() / "shannon-easycrypt-receipt.json"


def load_toolchain_receipt() -> EasyCryptToolchainReceipt:
    lock = verify_locked_easycrypt_source()
    try:
        value = json.loads(toolchain_receipt_path().read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            "repository-managed EasyCrypt toolchain is not bootstrapped"
        ) from exc
    if type(value) is not dict or set(value) != {
        "schema_version",
        "lock_identity_sha256",
        "build_id",
        "executable_sha256",
        "library_sha256",
    } or value.get("schema_version") != EASYCRYPT_RECEIPT_SCHEMA_VERSION:
        raise RuntimeError("EasyCrypt toolchain receipt schema is invalid")
    receipt = EasyCryptToolchainReceipt(
        lock_identity_sha256=str(value.get("lock_identity_sha256") or ""),
        build_id=str(value.get("build_id") or ""),
        executable_sha256=str(value.get("executable_sha256") or ""),
        library_sha256=str(value.get("library_sha256") or ""),
    )
    if receipt.lock_identity_sha256 != lock.identity_sha256 or (
        receipt.build_id != lock.expected_build_id
    ):
        raise RuntimeError("EasyCrypt toolchain receipt does not match lock")
    return receipt


@lru_cache(maxsize=1)
def _managed_environment_items() -> tuple[tuple[str, str], ...]:
    """Return one verified environment for the repository-managed switch."""

    receipt = load_toolchain_receipt()
    opam = shutil.which("opam")
    if not opam:
        raise RuntimeError("opam is unavailable for managed EasyCrypt")
    root = managed_opam_root()
    switch = managed_switch_name()
    base = dict(os.environ)
    base["OPAMROOT"] = str(root)
    try:
        result = subprocess.run(
            [
                opam,
                "env",
                "--shell=sh",
                "--root",
                str(root),
                "--switch",
                switch,
                "--set-switch",
            ],
            env=base,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("cannot select managed EasyCrypt switch") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-1000:]
        raise RuntimeError(
            "cannot select managed EasyCrypt switch"
            + (f": {detail}" if detail else "")
        )
    env = dict(base)
    for line in result.stdout.splitlines():
        match = _OPAM_ENV_RE.match(line.strip())
        if match:
            env[match.group(1)] = match.group(2)
    if env.get("OPAMSWITCH") != switch or env.get("OPAMROOT") != str(root):
        raise RuntimeError("opam selected a different EasyCrypt switch")
    binary_name = shutil.which("easycrypt", path=env.get("PATH"))
    ocamlfind = shutil.which("ocamlfind", path=env.get("PATH"))
    if not binary_name or not ocamlfind:
        raise RuntimeError("managed EasyCrypt artifacts are unavailable")
    binary = Path(binary_name).resolve()
    library_query = subprocess.run(
        [ocamlfind, "query", "-format", "%d", "easycrypt.ecLib"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    library = Path(library_query.stdout.strip()) / "ecLib.cmxa"
    if library_query.returncode != 0 or not library.is_file():
        raise RuntimeError("managed EasyCrypt ecLib is unavailable")
    if sha256_file(binary) != receipt.executable_sha256 or (
        sha256_file(library) != receipt.library_sha256
    ):
        raise RuntimeError("managed EasyCrypt artifacts differ from receipt")
    return tuple(env.items())


def managed_easycrypt_environment() -> dict[str, str]:
    env = dict(_managed_environment_items())
    # The expensive, verified opam environment is stable and cached.  Socket
    # routes are run-scoped: prover.run selects them only after orchestrator
    # calls check_ec_available(), which primes that cache.  Refresh just those
    # routes from the current process so bootstrap/replay cannot silently fall
    # back to a checkout-scoped daemon or why3server.
    for name in _RUNTIME_ROUTE_ENV_NAMES:
        value = os.environ.get(name)
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
