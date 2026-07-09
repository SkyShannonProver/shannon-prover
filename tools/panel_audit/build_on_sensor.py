"""Shared K0 shape-typed build-on sensor for panel-audit scripts."""
from __future__ import annotations

import re

_DOTTED_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\b")
_ID_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{3,}'?")
_FRAG_RE = re.compile(r"=\{[^}]{3,}\}|\{[^{}]{6,}\}|\([^()]{8,}\)")
_STOP = frozenset({
    "proof", "qed", "admit", "trivial", "smt", "auto", "move", "skip", "done",
    "progress", "rewrite", "apply", "exact", "case", "elim", "split", "subst",
    "inline", "call", "proc", "byequiv", "byphoare", "while", "swap", "conseq",
    "transitivity", "sim", "glob", "true", "false", "witness", "none", "some",
    "goal", "tactic", "lemma", "invariant", "frontier", "current",
})


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def names(text: str | None) -> set[str]:
    """Legacy dotted Module.proc names only."""
    return set(_DOTTED_RE.findall(text or ""))


def _ids(text: str | None) -> set[str]:
    return {
        token.rstrip(".'")
        for token in _ID_RE.findall(text or "")
        if token.lower().rstrip(".'") not in _STOP
    }


def _frags(text: str | None) -> set[str]:
    return {
        normalized
        for match in _FRAG_RE.findall(text or "")
        for normalized in (_norm(match),)
        if len(normalized) >= 6
    }


def build_on(returned: str | None, commit: str | None) -> bool:
    """Whether a commit builds on returned panel content by names or structure."""
    if _ids(returned) & _ids(commit):
        return True
    normalized_commit = _norm(commit)
    return any(fragment in normalized_commit for fragment in _frags(returned))
