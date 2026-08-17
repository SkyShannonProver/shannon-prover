"""Runtime declaration-loader contract tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.easycrypt.compiler_resource_loader import (
    load_requested_declarations,
    parse_runtime_declaration_requests,
)
from core.easycrypt.proof_state_compiler.frontend.resource_syntax import (
    normalized_declaration,
)


def _request() -> list[dict[str, object]]:
    return [{
        "request_id": "scope-members:test",
        "producer_id": "test.scope_members",
        "query_kind": "scope_member_declarations",
        "scope": "CCA_UFCMA",
        "declaration_kinds": ["lemma", "axiom"],
        "member_name_terms": ["cpa"],
        "max_results": 40,
    }]


def _symbol_request() -> list[dict[str, object]]:
    return [{
        "request_id": "symbols:test",
        "producer_id": "test.symbols",
        "query_kind": "symbol_declarations",
        "declaration_kinds": ["lemma", "axiom"],
        "symbols": ["Wrong.dword_ll", "dword_ll"],
        "max_results": 2,
    }]


def test_runtime_loader_resolves_bounded_scope_members(monkeypatch, tmp_path: Path) -> None:
    declaration = "lemma CCA_CPA_UFCMA : forall &m, Pr[G.main() @ &m : res] <= 1%r."

    def fake_members(scope, context_file, include_dirs):
        assert scope == "CCA_UFCMA"
        return {
            "status": "ok",
            "by_kind": {
                "lemma": ["CCA_CPA_UFCMA", "other"],
                "op": ["hidden_from_request"],
            },
        }

    def fake_declarations(names, context_file, include_dirs):
        assert names == ["CCA_UFCMA.CCA_CPA_UFCMA"]
        return {
            names[0]: {
                "status": "resolved",
                "resolved": names[0],
                "kind": "equiv",
                "body": declaration,
            },
        }

    monkeypatch.setattr(
        "core.easycrypt.compiler_namespace_adapter.list_theory_members",
        fake_members,
    )
    monkeypatch.setattr(
        "core.easycrypt.compiler_namespace_adapter.load_exact_declarations",
        fake_declarations,
    )
    context = tmp_path / "context.ec"
    context.write_text("clone CCA_CPA_UFCMA as CCA_UFCMA.\n", encoding="utf-8")

    result = load_requested_declarations(
        parse_runtime_declaration_requests(_request()),
        context_file=context,
        include_dirs=(),
    )

    assert len(result.declarations) == 1
    loaded = result.declarations[0]
    assert loaded["symbol"] == "CCA_UFCMA.CCA_CPA_UFCMA"
    assert loaded["declaration"] == declaration
    assert loaded["declaration_sha256"] == hashlib.sha256(
        declaration.encode()
    ).hexdigest()
    assert result.report[0]["loaded_count"] == 1
    assert result.report[0]["member_count"] == 2
    assert result.report[0]["matched_name_count"] == 1
    assert result.report[0]["requested_count"] == 1
    assert result.report[0]["member_name_terms"] == ["cpa"]


def test_runtime_loader_rejects_unbounded_or_unknown_requests() -> None:
    invalid = _request()
    invalid[0]["max_results"] = 101
    with pytest.raises(ValueError, match="max_results"):
        parse_runtime_declaration_requests(invalid)


def test_runtime_loader_resolves_only_exact_bounded_symbols(
    monkeypatch, tmp_path: Path
) -> None:
    declaration = "lemma dword_ll : true."

    def fake_declarations(names, context_file, include_dirs):
        assert names == ["Wrong.dword_ll", "dword_ll"]
        return {
            "dword_ll": {
                "status": "resolved",
                "resolved": "dword_ll",
                "kind": "lemma",
                "body": declaration,
            },
        }

    monkeypatch.setattr(
        "core.easycrypt.compiler_namespace_adapter.load_exact_declarations",
        fake_declarations,
    )
    context = tmp_path / "context.ec"
    context.write_text("lemma dword_ll : true.\n", encoding="utf-8")

    result = load_requested_declarations(
        parse_runtime_declaration_requests(_symbol_request()),
        context_file=context,
        include_dirs=(),
    )

    assert tuple(item["symbol"] for item in result.declarations) == (
        "dword_ll",
    )
    assert result.report == ({
        "request_id": "symbols:test",
        "producer_id": "test.symbols",
        "query_kind": "symbol_declarations",
        "status": "ok",
        "requested_count": 2,
        "loaded_count": 1,
        "truncated": False,
        "elapsed_ms": result.report[0]["elapsed_ms"],
        "symbols": ["Wrong.dword_ll", "dword_ll"],
    },)


def test_runtime_loader_marks_exact_symbol_miss_without_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_declarations(names, context_file, include_dirs):
        assert names == ["Wrong.dword_ll", "dword_ll"]
        return {}

    monkeypatch.setattr(
        "core.easycrypt.compiler_namespace_adapter.load_exact_declarations",
        fake_declarations,
    )
    context = tmp_path / "context.ec"
    context.write_text("lemma unrelated : true.\n", encoding="utf-8")

    result = load_requested_declarations(
        parse_runtime_declaration_requests(_symbol_request()),
        context_file=context,
        include_dirs=(),
    )

    assert result.declarations == ()
    assert result.report[0]["status"] == "miss"
    assert result.report[0]["loaded_count"] == 0


def test_runtime_loader_rejects_mixed_scope_and_symbol_request() -> None:
    invalid = _symbol_request()
    invalid[0]["scope"] = "Wrong"
    with pytest.raises(ValueError, match="cannot carry a scope"):
        parse_runtime_declaration_requests(invalid)


def test_verifier_display_header_is_not_part_of_declaration_syntax() -> None:
    displayed = (
        "* In [lemmas or axioms]:\n\n"
        "lemma L : forall &m, Pr[G.main() @ &m : res] <= 1%r."
    )
    assert normalized_declaration(displayed).startswith("lemma L :")

    invalid = _request()
    invalid[0]["query_kind"] = "symbol_regex"
    with pytest.raises(ValueError, match="unsupported"):
        parse_runtime_declaration_requests(invalid)
