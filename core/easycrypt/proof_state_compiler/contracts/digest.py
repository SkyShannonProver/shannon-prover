"""Content digests behind every compiler identity.

All JSON identities hash one canonical spelling (sorted keys, compact
separators, non-ASCII kept) so equal content yields equal IDs however it was
built.  Text is hashed as UTF-8.  These are the runtime's shared spelling and
digests under the names compiler code imports.
"""

from __future__ import annotations

from core.digests import sha256_json as json_sha256
from core.digests import sha256_text as text_sha256
from core.jsonio import canonical_json

__all__ = ["canonical_json", "json_sha256", "text_sha256"]
