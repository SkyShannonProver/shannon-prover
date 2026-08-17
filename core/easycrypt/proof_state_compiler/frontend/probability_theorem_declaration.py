"""Lexically sketch one probability theorem from a printed declaration.

This parser supports bounded candidate discovery. It does not replace native
EasyCrypt proof-term binder decomposition or type checking.
"""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.contracts.proof_ir import (
    ApplicationSignature,
    ArgumentSlot,
    ProofResource,
)
from core.easycrypt.proof_state_compiler.frontend.declaration_stream import (
    DeclarationInput,
)
from core.easycrypt.proof_state_compiler.frontend.resource_syntax import (
    top_level_colon,
)
from core.easycrypt.proof_state_compiler.syntax.formulas import (
    parse_proof_judgment,
)


def parse_probability_theorem_declaration(
    item: DeclarationInput,
) -> ProofResource | None:
    colon = top_level_colon(item.declaration)
    if colon < 0:
        return None
    proposition = item.declaration[colon + 1:].strip()
    if proposition.endswith("."):
        proposition = proposition[:-1].rstrip()
    parsed = _application_parts(proposition, item)
    if parsed is None:
        return None
    slots, premises, conclusion = parsed
    if not conclusion.lstrip().startswith("Pr["):
        return None
    resource_id = f"{item.symbol}@{item.evidence.source_ref}"
    return ProofResource(
        resource_id=resource_id,
        symbol=item.symbol,
        resource_kind="theorem",
        declaration=item.declaration,
        application_signature=ApplicationSignature(
            resource_id=resource_id,
            slots=tuple(slots),
            evidence_refs=(item.evidence,),
        ),
        premises=tuple(parse_proof_judgment(value) for value in premises),
        conclusion=parse_proof_judgment(conclusion),
        evidence_refs=(item.evidence,),
    )


def _application_parts(
    proposition: str,
    item: DeclarationInput,
) -> tuple[list[ArgumentSlot], list[str], str] | None:
    remaining = proposition.strip()
    slots: list[ArgumentSlot] = []
    premises: list[str] = []
    proof_index = 0
    while remaining.startswith("forall "):
        comma = _top_level_comma(remaining)
        if comma < 0:
            return None
        binder = remaining[len("forall "):comma].strip()
        slot = _binder_slot(binder, len(slots), item)
        if slot is None:
            return None
        slots.append(slot)
        remaining = remaining[comma + 1:].strip()
        while True:
            implication = _first_top_level_implication(remaining)
            if implication is None:
                break
            premise, remaining = implication
            proof_index += 1
            premises.append(premise)
            slots.append(ArgumentSlot(
                slot_id=f"proof:{proof_index}",
                name=f"premise_{proof_index}",
                kind="proof",
                binding_mode="deferred_obligation",
                expected=premise,
                explicit=True,
                evidence_refs=(item.evidence,),
            ))
            remaining = remaining.strip()
            if remaining.startswith("forall "):
                break
    if not remaining or _first_top_level_implication(remaining) is not None:
        return None
    return slots, premises, remaining


def _binder_slot(
    binder: str,
    index: int,
    item: DeclarationInput,
) -> ArgumentSlot | None:
    value = binder.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    module = re.match(
        r"^([A-Za-z_][\w']*)(?:\s*\([^)]*\))?\s*<:\s*(.+)$",
        value,
    )
    if module:
        name, restriction = module.groups()
        return ArgumentSlot(
            slot_id=f"module:{name}",
            name=name,
            kind="module",
            binding_mode="required",
            expected=f"{name} <: {restriction.strip()}",
            explicit=True,
            evidence_refs=(item.evidence,),
        )
    if re.fullmatch(r"&[A-Za-z_][\w']*", value):
        return ArgumentSlot(
            slot_id=f"memory:{value}",
            name=value,
            kind="memory",
            binding_mode="required",
            expected=value,
            explicit=True,
            evidence_refs=(item.evidence,),
        )
    term = re.match(r"^([A-Za-z_][\w']*)\s*:\s*(.+)$", value)
    if term:
        name, expected = term.groups()
        return ArgumentSlot(
            slot_id=f"term:{index}:{name}",
            name=name,
            kind="term",
            binding_mode="required",
            expected=expected.strip(),
            explicit=True,
            evidence_refs=(item.evidence,),
        )
    return None


def _top_level_comma(value: str) -> int:
    depth = 0
    for index, char in enumerate(value):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            return index
    return -1


def _first_top_level_implication(value: str) -> tuple[str, str] | None:
    depth = 0
    index = 0
    while index < len(value) - 1:
        char = value[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif value[index:index + 2] == "=>" and depth == 0:
            return value[:index].strip(), value[index + 2:].strip()
        index += 1
    return None
