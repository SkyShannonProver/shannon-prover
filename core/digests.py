"""SHA-256 hex digests of bytes, text, JSON values and files."""
from __future__ import annotations

import hashlib
from pathlib import Path

from core.jsonio import canonical_json


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    """Digest of the UTF-8 encoding of ``value``."""
    return sha256_bytes(value.encode("utf-8"))


def sha256_json(value: object) -> str:
    """Digest of the canonical JSON spelling of ``value``."""
    return sha256_text(canonical_json(value))


def sha256_file(path: Path) -> str:
    """Digest of the file's bytes, read in 1 MiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
