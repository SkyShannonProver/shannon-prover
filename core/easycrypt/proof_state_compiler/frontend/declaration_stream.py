"""Canonical declaration stream for P2 resource discovery."""

from __future__ import annotations

from dataclasses import dataclass

from core.easycrypt.proof_state_compiler.contracts.environment import (
    CompilationEnvironment,
)
from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.frontend.resource_syntax import (
    declarations,
    normalized_declaration,
)


@dataclass(frozen=True)
class DeclarationInput:
    symbol: str
    declaration: str
    evidence: EvidenceRef


def declaration_inputs(
    environment: CompilationEnvironment,
) -> tuple[DeclarationInput, ...]:
    """Return source-scanned and verifier-resolved declarations uniformly."""

    values = []
    for unit in environment.source_units:
        evidence = EvidenceRef(
            evidence_id=f"p2.source.{unit.source_sha256[:16]}",
            source_kind="loaded_source_unit",
            source_ref=unit.source_ref,
            source_sha256=unit.source_sha256,
        )
        values.extend(
            DeclarationInput(
                symbol=symbol,
                declaration=declaration,
                evidence=evidence,
            )
            for symbol, declaration in declarations(unit.text)
        )
    values.extend(
        DeclarationInput(
            symbol=item.symbol,
            declaration=normalized_declaration(item.declaration),
            evidence=EvidenceRef(
                evidence_id=f"p2.declaration.{item.declaration_sha256[:16]}",
                source_kind="loaded_declaration",
                source_ref=item.source_ref,
                source_sha256=item.declaration_sha256,
            ),
        )
        for item in environment.loaded_declarations
    )
    return tuple(values)
