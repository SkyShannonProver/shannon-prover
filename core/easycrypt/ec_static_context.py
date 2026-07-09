"""Static EasyCrypt source context.

This module is the proof-search equivalent of a small compiler symbol-table
pass. It extracts scope and clone facts from an EasyCrypt source file, but it
does not diagnose proof failures and does not suggest tactics.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


PROM_FAMILY_LEMMAS = frozenset({
    # FinEager / lazy-eager RO bridges (PROM theory)
    "pr_RO_FinRO_D",
    "RO_FinRO_D",
    "pr_FinRO_FunRO_D",
    "FinRO_FunRO_D",
    "MainD",
    # Split (codomain / domain) bridges
    "pr_Split",
    "Split_D",
})


@dataclass(frozen=True)
class EasyCryptScopeContext:
    """Static scope facts for one EasyCrypt source file."""

    local_modules: tuple[str, ...] = ()
    declared_modules: tuple[str, ...] = ()
    section_bound_modules: tuple[str, ...] = ()
    cloned_theories: tuple[str, ...] = ()
    named_equivs: tuple[str, ...] = ()
    source_path: str = ""
    source_hash: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_modules": list(self.local_modules),
            "declared_modules": list(self.declared_modules),
            "section_bound_modules": list(self.section_bound_modules),
            "cloned_theories": list(self.cloned_theories),
            "named_equivs": list(self.named_equivs),
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "evidence": dict(self.evidence),
        }


def read_ec_scope_context(source_path: str | Path) -> Optional[EasyCryptScopeContext]:
    path = Path(source_path)
    if not path.exists():
        return None
    try:
        source_text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    return analyze_ec_scope_context(source_text, source_path=path)


def analyze_ec_scope_context(
    source_text: str,
    *,
    source_path: str | Path | None = None,
) -> EasyCryptScopeContext:
    local_modules = _scan_local_module_declarations(source_text)
    declared_modules = _scan_declare_module_declarations(source_text)
    section_bound_modules = _dedupe([*local_modules, *declared_modules])
    cloned_theories = _scan_cloned_theories(source_text)
    named_equivs = _scan_named_equivs(source_text)
    spath = str(source_path) if source_path is not None else ""
    return EasyCryptScopeContext(
        local_modules=tuple(local_modules),
        declared_modules=tuple(declared_modules),
        section_bound_modules=tuple(section_bound_modules),
        cloned_theories=tuple(cloned_theories),
        named_equivs=tuple(named_equivs),
        source_path=spath,
        source_hash=_text_hash(source_text),
        evidence={
            "source_scan": "regex",
            "module_binding_kinds": ["local module", "declare module"],
            "clone_forms": [
                "clone",
                "clone import",
                "clone include",
                "clone ... as ...",
                "abstract theory",
            ],
        },
    )


def is_cloned_theory_lemma(
    lemma: str,
    scope_context: EasyCryptScopeContext,
) -> tuple[bool, str]:
    """Return whether ``lemma`` appears to cross a clone/theory boundary."""
    cloned = set(scope_context.cloned_theories)
    head = lemma.split(".", 1)[0] if "." in lemma else ""
    if head and head in cloned:
        return (True, head)
    if lemma in PROM_FAMILY_LEMMAS:
        return (True, "PROM/FinEager")
    return (False, "")


def _scan_local_module_declarations(source_text: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(r"\blocal\s+module\s+([A-Z][A-Za-z0-9_']*)", source_text):
        names.append(m.group(1))
    return _dedupe(names)


def _scan_declare_module_declarations(source_text: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(r"\bdeclare\s+module\s+([A-Z][A-Za-z0-9_']*)", source_text):
        names.append(m.group(1))
    return _dedupe(names)


def _scan_named_equivs(source_text: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(
        r"\b(?:local\s+)?equiv\s+([a-z_][A-Za-z0-9_']*)\s*[:( ]",
        source_text,
    ):
        names.append(m.group(1))
    return _dedupe(names)


def _scan_cloned_theories(source_text: str) -> list[str]:
    out: list[str] = []
    cap = r"[A-Z][A-Za-z0-9_']*"
    clone_re = re.compile(
        rf"\bclone\s+(?:import\s+|include\s+)?({cap}(?:\.{cap})*)"
        rf"(?:\s+as\s+({cap}))?"
    )
    for m in clone_re.finditer(source_text):
        src = m.group(1)
        alias = m.group(2)
        out.extend(src.split("."))
        out.append(src)
        if alias:
            out.append(alias)
    for m in re.finditer(rf"\babstract\s+theory\s+({cap})", source_text):
        out.append(m.group(1))
    return _dedupe(out)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _text_hash(source_text: str) -> str:
    return hashlib.sha1(source_text.encode("utf-8", errors="replace")).hexdigest()
