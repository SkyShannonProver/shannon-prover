"""Content digests behind every compiler identity.

All JSON identities hash one canonical spelling (sorted keys, compact
separators, non-ASCII kept) so equal content yields equal IDs however it was
built.  Text is hashed as UTF-8.
"""

from __future__ import annotations

import hashlib
import json


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_sha256(value: object) -> str:
    return text_sha256(canonical_json(value))
