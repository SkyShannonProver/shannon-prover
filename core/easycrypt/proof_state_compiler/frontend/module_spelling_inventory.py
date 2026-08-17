"""Bounded lexical module spellings for subsequent native type checking.

This frontend helper never claims that a spelling is visible, has a module
type, or satisfies a restriction.  It collects exact source-declared module
heads and exact native goal module terms.  A feature may pass the complete
bounded inventory to EasyCrypt; only native accepted members become semantic
evidence.
"""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.contracts import (
    AttemptedOperationIR,
    CompilationEnvironment,
    EvidenceRef,
    GoalIR,
    ModuleSpellingInventory,
    TypedTermIR,
)
from core.easycrypt.proof_state_compiler.contracts.frozen_json import (
    FrozenJsonObject,
)


_MODULE_HEAD = re.compile(
    r"^\s*(?:(?:local|declare)\s+)?module\s+"
    r"(?!type\b)([A-Za-z_][\w']*)\b",
    re.MULTILINE,
)


def needs_module_spelling_inventory(
    attempted: AttemptedOperationIR | None,
) -> bool:
    """Recognize the shared structural demand without feature dispatch."""

    head = None if attempted is None else attempted.application_head_descriptor
    return bool(
        attempted is not None
        and attempted.native_diagnostic_status == "blocker"
        and attempted.operation in {"apply", "exact"}
        and head is not None
        and not head.input_arguments
        and any(slot.kind == "module" for slot in head.slots)
    )


def bounded_module_spelling_inventory(
    goal: GoalIR,
    environment: CompilationEnvironment,
    *,
    max_terms: int,
) -> ModuleSpellingInventory:
    """Return the complete bounded spelling inventory or typed abstention."""

    if max_terms < 1:
        raise ValueError("module spelling inventory requires a positive bound")
    terms: list[str] = []
    evidence: list[EvidenceRef] = []
    if goal.formula_ir is not None:
        _collect_goal_module_terms(goal.formula_ir, terms)
        evidence.extend(goal.evidence_refs)
    for unit in environment.source_units:
        terms.extend(match.group(1) for match in _MODULE_HEAD.finditer(unit.text))
        evidence.append(EvidenceRef(
            evidence_id=f"module-spellings:{unit.source_sha256[:16]}",
            source_kind="loaded_source_unit",
            source_ref=unit.source_ref,
            source_sha256=unit.source_sha256,
        ))
    canonical = tuple(sorted(set(terms)))
    if (
        len(canonical) > max_terms
        or sum(len(item) for item in canonical) > 16384
        or any(
            len(item) > 512 or any(char in item for char in "\n\r;")
            for item in canonical
        )
    ):
        return ModuleSpellingInventory(
            terms=(),
            evidence_refs=(),
            complete=False,
            reason="module_spelling_inventory_exceeds_bound",
        )
    return ModuleSpellingInventory(
        terms=canonical,
        evidence_refs=tuple(dict.fromkeys(evidence)),
        complete=True,
    )


def _collect_goal_module_terms(term: TypedTermIR, target: list[str]) -> None:
    module = term.properties.get("procedure_module")
    if isinstance(module, FrozenJsonObject):
        _collect_module_term(module, target)
    for child in term.children:
        _collect_goal_module_terms(child, target)


def _collect_module_term(module: FrozenJsonObject, target: list[str]) -> None:
    rendered = module.get("term")
    if isinstance(rendered, str) and rendered:
        target.append(rendered)
    arguments = module.get("arguments")
    if arguments is None:
        return
    for argument in arguments:
        if isinstance(argument, FrozenJsonObject):
            _collect_module_term(argument, target)
