"""Leaf helpers for EasyCrypt sampling statements."""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import as_dict as _dict, as_list as _list


def is_sample_statement(stmt: dict[str, Any]) -> bool:
    item = _dict(stmt)
    kind = str(item.get("kind") or item.get("type") or "").upper()
    text = str(item.get("statement") or item.get("text") or "")
    return bool(kind in {"SAMPLE", "RND"} or "<$" in text)


def sample_statement_var(
    sample: dict[str, Any],
    text: str | None = None,
    *,
    qualified_lhs: bool = False,
) -> str:
    item = _dict(sample)
    written = [
        str(var).strip()
        for var in _list(item.get("vars_written"))
        if str(var).strip()
    ]
    if written:
        return written[0]
    source = str(text if text is not None else item.get("statement") or "")
    if "<$" not in source:
        return ""
    lhs = source.split("<$", 1)[0]
    if qualified_lhs:
        tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", lhs)
        return tokens[-1] if tokens else ""
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_']*)\s*$", lhs)
    return match.group(1) if match else ""


def sample_statement_distribution(
    sample: dict[str, Any],
    text: str | None = None,
    *,
    strip_explicit: bool = True,
    strip_fallback: bool = True,
) -> str:
    item = _dict(sample)
    explicit = str(item.get("distribution") or "").strip()
    if explicit:
        return explicit.rstrip(".;") if strip_explicit else explicit
    source = str(text if text is not None else item.get("statement") or item.get("text") or "")
    if "<$" not in source:
        return ""
    rhs = source.split("<$", 1)[1].split(";", 1)[0]
    dist = re.sub(r"\s+", " ", rhs).strip()
    return dist.rstrip(".;") if strip_fallback else dist


def sample_distribution_leaf(distribution: str) -> str:
    text = str(distribution or "").strip()
    if not text:
        return ""
    text = text.split()[0]
    text = text.rsplit(".", 1)[-1]
    return re.sub(r"[^A-Za-z0-9_']", "", text)
