"""Target discovery helpers for the live playground."""
from __future__ import annotations

import re
from pathlib import Path


_DECL_RE = re.compile(
    r"^\s*((?:local\s+)?(?:lemma|equiv|hoare|phoare))\s+([A-Za-z_][A-Za-z0-9_']*)\b"
)


def strip_easycrypt_comments(text: str) -> str:
    out: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        two = text[i : i + 2]
        if two == "(*":
            depth += 1
            i += 2
            continue
        if depth and two == "*)":
            depth -= 1
            i += 2
            continue
        ch = text[i]
        out.append(ch if depth == 0 or ch == "\n" else " ")
        i += 1
    return "".join(out)


def proof_declarations(path: Path) -> list[dict[str, object]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    clean = strip_easycrypt_comments(text)
    seen: set[tuple[str, str]] = set()
    decls: list[dict[str, object]] = []
    for line_no, line in enumerate(clean.splitlines(), start=1):
        match = _DECL_RE.match(line)
        if match is None:
            continue
        kind, name = match.groups()
        kind = " ".join(kind.split())
        key = (kind, name)
        if key in seen:
            continue
        seen.add(key)
        decls.append({"name": name, "kind": kind, "line": line_no})
    return decls
