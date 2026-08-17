"""Immutable source environment supplied to P2 by the runtime boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from core.easycrypt.ec_runtime_identity import EasyCryptRuntimeIdentity
from core.easycrypt.proof_state_compiler.contracts.evidence import EvidenceRef
from core.easycrypt.proof_state_compiler.contracts.native_semantics import (
    NativeSemanticObservation,
)
from core.easycrypt.proof_state_compiler.contracts.state_ref import StateRef


@dataclass(frozen=True)
class LoadedSourceUnit:
    source_ref: str
    source_sha256: str
    text: str

    def __post_init__(self) -> None:
        if not self.source_ref:
            raise ValueError("loaded source unit requires source_ref")
        digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if self.source_sha256 != digest:
            raise ValueError("loaded source unit hash does not match its text")


@dataclass(frozen=True)
class LoadedDeclaration:
    """One verifier-resolved declaration supplied by the runtime boundary."""

    symbol: str
    source_ref: str
    declaration_sha256: str
    declaration: str

    def __post_init__(self) -> None:
        if not self.symbol or not self.source_ref or not self.declaration:
            raise ValueError("loaded declaration requires symbol, source, and text")
        digest = hashlib.sha256(self.declaration.encode("utf-8")).hexdigest()
        if self.declaration_sha256 != digest:
            raise ValueError("loaded declaration hash does not match its text")


@dataclass(frozen=True)
class DeclarationLoadRequest:
    """One feature-neutral request from P2 dependency discovery.

    The compiler may request a bounded class of declarations, but it cannot
    read files, invoke EasyCrypt, or smuggle a preselected tactic through this
    contract. The runtime resolves the request and binds returned declarations
    into a fresh authoritative resource artifact tied to the existing input.
    """

    request_id: str
    producer_id: str
    query_kind: str
    scope: str
    declaration_kinds: tuple[str, ...]
    member_name_terms: tuple[str, ...]
    max_results: int
    evidence_refs: tuple[EvidenceRef, ...]
    symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id or not self.producer_id:
            raise ValueError("declaration load request requires identity")
        if self.query_kind not in {
            "scope_member_declarations",
            "symbol_declarations",
        }:
            raise ValueError(
                f"unsupported declaration load query {self.query_kind!r}"
            )
        allowed_kinds = {"lemma", "axiom"}
        if (
            not self.declaration_kinds
            or any(kind not in allowed_kinds for kind in self.declaration_kinds)
            or len(self.declaration_kinds) != len(set(self.declaration_kinds))
        ):
            raise ValueError("declaration load request has invalid declaration kinds")
        if self.query_kind == "scope_member_declarations":
            if not self.scope or self.symbols:
                raise ValueError("scope query requires only one exact scope")
            if (
                not self.member_name_terms
                or len(self.member_name_terms) > 64
                or len(self.member_name_terms) != len(set(self.member_name_terms))
                or any(
                    not term
                    or term != term.lower()
                    or not term.replace("_", "").isalnum()
                    for term in self.member_name_terms
                )
            ):
                raise ValueError(
                    "declaration load request has invalid member-name terms"
                )
        elif (
            self.scope
            or self.member_name_terms
            or not self.symbols
            or len(self.symbols) > 8
            or len(self.symbols) != len(set(self.symbols))
            or any(not _valid_symbol(symbol) for symbol in self.symbols)
        ):
            raise ValueError("symbol query requires 1..8 exact symbols only")
        if not 1 <= self.max_results <= 100:
            raise ValueError("declaration load request max_results must be 1..100")
        if not self.evidence_refs:
            raise ValueError("declaration load request requires evidence")

    def identity_payload(self) -> dict[str, object]:
        """Canonical material identity shared by runtime, cache, and audit."""

        payload = {
            "request_id": self.request_id,
            "producer_id": self.producer_id,
            "query_kind": self.query_kind,
            "declaration_kinds": list(self.declaration_kinds),
            "max_results": self.max_results,
        }
        if self.query_kind == "scope_member_declarations":
            payload.update({
                "scope": self.scope,
                "member_name_terms": list(self.member_name_terms),
            })
        else:
            payload["symbols"] = list(self.symbols)
        return payload

    def runtime_payload(self) -> dict[str, object]:
        return self.identity_payload()


def _valid_symbol(value: str) -> bool:
    return bool(value) and all(
        part
        and (part[0].isalpha() or part[0] == "_")
        and all(char.isalnum() or char in "_'" for char in part)
        for part in value.split(".")
    )


@dataclass(frozen=True)
class ResourceLoadPlan:
    """P2 dependency-discovery result for one exact proof state."""

    state_ref: StateRef
    requests: tuple[DeclarationLoadRequest, ...]

    def __post_init__(self) -> None:
        request_ids = [request.request_id for request in self.requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("resource load plan has duplicate request IDs")


@dataclass(frozen=True)
class CompilationEnvironment:
    environment_id: str
    source_units: tuple[LoadedSourceUnit, ...]
    loaded_declarations: tuple[LoadedDeclaration, ...] = ()
    easycrypt_runtime: EasyCryptRuntimeIdentity | None = None
    native_semantic_observations: tuple[NativeSemanticObservation, ...] = ()

    def __post_init__(self) -> None:
        if not self.environment_id:
            raise ValueError("compilation environment requires environment_id")
        refs = [unit.source_ref for unit in self.source_units]
        if len(refs) != len(set(refs)):
            raise ValueError("compilation environment contains duplicate source_ref")
        declaration_refs = [
            (item.symbol, item.source_ref) for item in self.loaded_declarations
        ]
        if len(declaration_refs) != len(set(declaration_refs)):
            raise ValueError(
                "compilation environment contains duplicate loaded declarations"
            )
        request_ids = [
            item.request_id for item in self.native_semantic_observations
        ]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError(
                "compilation environment contains duplicate native observations"
            )

    def with_loaded_declarations(
        self,
        declarations: tuple[LoadedDeclaration, ...],
    ) -> "CompilationEnvironment":
        return CompilationEnvironment(
            environment_id=self.environment_id,
            source_units=self.source_units,
            loaded_declarations=self.loaded_declarations + declarations,
            easycrypt_runtime=self.easycrypt_runtime,
            native_semantic_observations=self.native_semantic_observations,
        )

    def with_native_semantic_observations(
        self,
        observations: tuple[NativeSemanticObservation, ...],
    ) -> "CompilationEnvironment":
        return CompilationEnvironment(
            environment_id=self.environment_id,
            source_units=self.source_units,
            loaded_declarations=self.loaded_declarations,
            easycrypt_runtime=self.easycrypt_runtime,
            native_semantic_observations=(
                self.native_semantic_observations + observations
            ),
        )


def empty_compilation_environment() -> CompilationEnvironment:
    return CompilationEnvironment(environment_id="empty", source_units=())
