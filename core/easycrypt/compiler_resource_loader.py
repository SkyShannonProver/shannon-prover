"""Manager-internal resolver for proof-state compiler declaration requests.

This module is runtime plumbing, not a compiler pass.  It is the only code in
the resource-loading path that invokes EasyCrypt-backed namespace tools.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


_ALLOWED_QUERY_KINDS = {
    "scope_member_declarations",
    "symbol_declarations",
}
_ALLOWED_DECLARATION_KINDS = {"lemma", "axiom"}
_MAX_REQUESTS = 8
_MAX_TOTAL_RESULTS = 200


@dataclass(frozen=True)
class RuntimeDeclarationRequest:
    request_id: str
    producer_id: str
    query_kind: str
    scope: str
    declaration_kinds: tuple[str, ...]
    member_name_terms: tuple[str, ...]
    max_results: int
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeDeclarationLoadResult:
    declarations: tuple[dict[str, Any], ...]
    report: tuple[dict[str, Any], ...]


def parse_runtime_declaration_requests(
    value: object,
) -> tuple[RuntimeDeclarationRequest, ...]:
    if type(value) is not list:
        raise ValueError("compiler resource requests must be a list")
    if len(value) > _MAX_REQUESTS:
        raise ValueError("compiler resource request count exceeds runtime budget")
    requests = []
    request_ids: set[str] = set()
    total_results = 0
    for index, item in enumerate(value):
        if type(item) is not dict:
            raise ValueError(f"compiler resource request {index} is not an object")
        request_id = str(item.get("request_id") or "")
        producer_id = str(item.get("producer_id") or "")
        query_kind = str(item.get("query_kind") or "")
        scope = str(item.get("scope") or "")
        kinds_value = item.get("declaration_kinds")
        terms_value = item.get("member_name_terms")
        symbols_value = item.get("symbols")
        max_results = item.get("max_results")
        if not request_id or request_id in request_ids:
            raise ValueError("compiler resource requests need unique identities")
        if not producer_id:
            raise ValueError("compiler resource request requires producer identity")
        if query_kind not in _ALLOWED_QUERY_KINDS:
            raise ValueError(f"unsupported compiler resource query {query_kind!r}")
        if (
            type(kinds_value) is not list
            or not kinds_value
            or any(
                type(kind) is not str or kind not in _ALLOWED_DECLARATION_KINDS
                for kind in kinds_value
            )
            or len(kinds_value) != len(set(kinds_value))
        ):
            raise ValueError("compiler resource request has invalid kinds")
        if query_kind == "scope_member_declarations":
            if not _valid_scope(scope) or symbols_value not in (None, ()):
                raise ValueError(f"invalid compiler resource scope {scope!r}")
            if (
                type(terms_value) is not list
                or not terms_value
                or len(terms_value) > 64
                or any(
                    type(term) is not str
                    or not term
                    or term != term.lower()
                    or not term.replace("_", "").isalnum()
                    for term in terms_value
                )
                or len(terms_value) != len(set(terms_value))
            ):
                raise ValueError(
                    "compiler resource request has invalid member-name terms"
                )
            symbols = ()
        else:
            if scope or terms_value not in (None, ()):
                raise ValueError("exact symbol request cannot carry a scope")
            if (
                type(symbols_value) is not list
                or not symbols_value
                or len(symbols_value) > 8
                or any(
                    type(symbol) is not str or not _valid_scope(symbol)
                    for symbol in symbols_value
                )
                or len(symbols_value) != len(set(symbols_value))
            ):
                raise ValueError("compiler resource request has invalid symbols")
            symbols = tuple(symbols_value)
            terms_value = []
        if type(max_results) is not int or not 1 <= max_results <= 100:
            raise ValueError("compiler resource request max_results must be 1..100")
        total_results += max_results
        if total_results > _MAX_TOTAL_RESULTS:
            raise ValueError("compiler resource result budget exceeded")
        request_ids.add(request_id)
        requests.append(RuntimeDeclarationRequest(
            request_id=request_id,
            producer_id=producer_id,
            query_kind=query_kind,
            scope=scope,
            declaration_kinds=tuple(kinds_value),
            member_name_terms=tuple(terms_value),
            max_results=max_results,
            symbols=symbols,
        ))
    return tuple(requests)


def load_requested_declarations(
    requests: tuple[RuntimeDeclarationRequest, ...],
    *,
    context_file: Path,
    include_dirs: tuple[Path, ...],
) -> RuntimeDeclarationLoadResult:
    from core.easycrypt.compiler_namespace_adapter import (
        list_theory_members,
        load_exact_declarations,
    )

    declarations: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for request in requests:
        started = time.perf_counter_ns()
        if request.query_kind == "scope_member_declarations":
            member_result = list_theory_members(
                request.scope,
                context_file,
                list(include_dirs),
            )
            status = str(member_result.get("status") or "error")
            by_kind = member_result.get("by_kind")
            by_kind = by_kind if isinstance(by_kind, dict) else {}
            member_entries = [
                (kind, str(name))
                for kind in request.declaration_kinds
                for name in by_kind.get(kind, [])
                if isinstance(name, str) and name
            ]
            member_term_set = set(request.member_name_terms)
            matched_entries = [
                (kind, name)
                for kind, name in member_entries
                if _identifier_components(name) & member_term_set
            ]
            selected_entries = matched_entries[:request.max_results]
            qualified = [
                f"{request.scope}.{name}" for _kind, name in selected_entries
            ]
        else:
            status = "ok"
            member_entries = []
            matched_entries = []
            qualified = list(request.symbols[:request.max_results])
        resolved = load_exact_declarations(
            qualified,
            context_file,
            list(include_dirs),
        ) if qualified else {}
        loaded_count = 0
        for requested_symbol in qualified:
            item = resolved.get(requested_symbol)
            if not isinstance(item, dict):
                continue
            if item.get("status") != "resolved":
                continue
            body = str(item.get("body") or "").strip()
            symbol = str(item.get("resolved") or "").strip()
            if (
                not body
                or not symbol
                or symbol in seen_symbols
                or (
                    request.query_kind == "symbol_declarations"
                    and symbol not in request.symbols
                )
            ):
                continue
            seen_symbols.add(symbol)
            loaded_count += 1
            declarations.append({
                "symbol": symbol,
                "source_ref": (
                    f"easycrypt-native:print:{context_file.resolve()}#{symbol}"
                ),
                "declaration_sha256": hashlib.sha256(
                    body.encode("utf-8")
                ).hexdigest(),
                "declaration": body,
            })
        if request.query_kind == "symbol_declarations" and loaded_count == 0:
            status = "miss"
        elapsed_ms = max(0, int((time.perf_counter_ns() - started) / 1_000_000))
        record = {
            "request_id": request.request_id,
            "producer_id": request.producer_id,
            "query_kind": request.query_kind,
            "status": status,
            "requested_count": len(qualified),
            "loaded_count": loaded_count,
            "truncated": False,
            "elapsed_ms": elapsed_ms,
        }
        if request.query_kind == "scope_member_declarations":
            record.update({
                "scope": request.scope,
                "member_name_terms": list(request.member_name_terms),
                "member_count": len(member_entries),
                "matched_name_count": len(matched_entries),
                "truncated": len(matched_entries) > len(qualified),
            })
        else:
            record["symbols"] = list(request.symbols)
        report.append(record)
    return RuntimeDeclarationLoadResult(
        declarations=tuple(declarations),
        report=tuple(report),
    )


def _valid_scope(scope: str) -> bool:
    return bool(re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*",
        scope,
    ))


def _identifier_components(value: str) -> set[str]:
    components: set[str] = set()
    for identifier in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", value):
        for part in identifier.replace("'", "").split("_"):
            normalized = part.lower()
            if len(normalized) >= 3:
                components.add(normalized)
    return components
