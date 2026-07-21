"""Semantic index for EasyCrypt declarations visible to the current session.

The index is deliberately read-only.  It scans loaded context/source files and
imported theory files, extracts declarations, and records semantic facts that
other compiler passes can consume without knowing project-specific lemma names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_obligation_ir import (
    build_proof_obligation_ir,
    first_top_level_relation,
    local_order_chains,
    top_level_relation_parts,
)

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_present_strings as _dedupe_strings,
)

try:
    from core.easycrypt.analysis.ec_pr_canonical import (
        compact_pr_term,
        game_key,
        parse_pr_terms,
        pr_game_keys_from_text,
        pr_terms_with_spans as _pr_terms_with_spans,
    )
except Exception:  # Script/session_cli import path.
    from core.easycrypt.analysis.ec_pr_canonical import (  # type: ignore
        compact_pr_term,
        game_key,
        parse_pr_terms,
        pr_game_keys_from_text,
        pr_terms_with_spans as _pr_terms_with_spans,
    )


LEMMA_INDEX_SCHEMA_VERSION = 1
LEMMA_INDEX_KIND = "easycrypt_semantic_lemma_index"
_EC_FILE_INDEX: dict[str, dict[str, list[Path]]] = {}

EC_NATIVE_AUTHORITY_RANK = 100
SOURCE_SCAN_AUTHORITY_RANK = 10


def build_semantic_lemma_index(
    session_dir: str | Path | None,
    *,
    include_imported: bool = True,
) -> dict[str, Any]:
    """Build a semantic declaration index for the current EasyCrypt session."""
    items: list[dict[str, Any]] = []
    context_texts: list[tuple[str, Path, str]] = []
    items.extend(_native_tool_declarations(session_dir))
    for path, kind in session_context_files(session_dir):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        context_texts.append((text, path, kind))
        if include_imported and kind == "session_context":
            for imported in imported_theory_files(text, session_dir):
                try:
                    imported_text = imported.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                except Exception:
                    continue
                context_texts.append((imported_text, imported, "imported_theory"))

    for text, path, source in context_texts:
        include_local = source in {"session_context", "source_file"}
        items.extend(_declarations_from_text(
            text,
            source_path=path,
            source=source,
            include_local=include_local,
        ))

    items = _dedupe_items(items)
    return {
        "schema_version": LEMMA_INDEX_SCHEMA_VERSION,
        "kind": LEMMA_INDEX_KIND,
        "summary": {
            "declarations": len(items),
            "ec_native_declarations": sum(
                1 for item in items if item.get("ec_ground_truth")
            ),
            "source_scan_declarations": sum(
                1 for item in items if not item.get("ec_ground_truth")
            ),
            "pr_declarations": sum(1 for item in items if item.get("pr_terms")),
            "pr_rewrite_declarations": sum(
                1 for item in items if "pr_rewrite" in _list(item.get("semantic_tags"))
            ),
            "pr_bound_declarations": sum(
                1 for item in items if "pr_bound" in _list(item.get("semantic_tags"))
            ),
            "source_files": len({
                str(item.get("source_path") or "") for item in items
                if item.get("source_path")
            }),
        },
        "items": items,
    }


def mechanical_goal_candidates(
    lemma_index: dict[str, Any],
    *,
    goal_text: str,
    target_lemma: str = "",
    max_results: int = 16,
) -> list[dict[str, Any]]:
    """Return high-precision loaded-context declarations matching goal shape.

    This is deliberately not a tactic recommender.  It reports exact outer
    conclusions, mechanically verified order schemas, and a small set of
    high-precision structural fingerprints.  Bare symbol overlap remains
    broad search evidence and is never enough to enter this result.
    """
    goal_ir = build_proof_obligation_ir(goal_text)
    goal_conclusion = goal_ir.conclusion.text
    if not goal_conclusion:
        return []
    items = [
        item for item in _list(lemma_index.get("items"))
        if isinstance(item, dict)
        and str(item.get("declaration_kind") or "").lower() in {
            "lemma", "local lemma", "axiom", "local axiom",
        }
    ]
    exact_goal = _normalise_formula(goal_conclusion)
    goal_has_order_chain = bool(local_order_chains(goal_text))
    goal_type_anchors = (
        _mechanical_type_anchors(goal_text)
        | _declared_type_names(goal_text)
    )
    goal_symbols = _mechanical_operator_signature(
        goal_conclusion,
        bound_names=_goal_bound_names(goal_text),
    )
    goal_applied_symbols = _mechanical_applied_symbol_signature(
        goal_conclusion,
        bound_names=_goal_bound_names(goal_text),
    )
    goal_structures = _mechanical_structures(goal_conclusion)
    goal_add_sub_types = _add_sub_operand_types(
        goal_conclusion,
        _declared_variable_types(goal_text),
    )
    transport_transforms = _goal_map_update_transport_transforms(goal_ir)
    out: list[dict[str, Any]] = []
    for item in items:
        lemma = str(item.get("lemma") or "").strip()
        if not lemma or lemma == target_lemma:
            continue
        declaration = _trim_declaration(str(item.get("declaration") or ""))
        statement = _declaration_statement(declaration)
        if not statement:
            continue
        statement_ir = build_proof_obligation_ir(statement)
        conclusion = statement_ir.conclusion.text or statement
        losslessness_match = _losslessness_obligation_match(
            goal_ir=goal_ir,
            declaration_ir=statement_ir,
            declaration=declaration,
            ambient_module_parameters={
                str(name)
                for name in _list(item.get("module_parameters"))
                if str(name)
            },
        )
        exact = _normalise_formula(conclusion) == exact_goal
        order_schema = (
            goal_has_order_chain
            and _is_order_transitivity_schema(statement_ir)
            and bool(
                goal_type_anchors
                & _mechanical_type_anchors(declaration)
            )
        )
        declaration_bound_names = _declaration_bound_names(declaration)
        declaration_symbols = _mechanical_operator_signature(
            conclusion,
            bound_names=declaration_bound_names,
        )
        declaration_structures = _mechanical_structures(conclusion)
        declaration_applied_symbols = _mechanical_applied_symbol_signature(
            conclusion,
            bound_names=declaration_bound_names,
        )
        declaration_types = _declared_type_names(declaration)
        declaration_add_sub_types = _add_sub_operand_types(
            conclusion,
            _declared_variable_types(declaration),
        )
        shared_symbols = sorted(goal_symbols & declaration_symbols)
        shared_structures = sorted(goal_structures & declaration_structures)
        shared_types = sorted(goal_type_anchors & declaration_types)
        shared_add_sub_types = sorted(goal_add_sub_types & declaration_add_sub_types)
        structural = _high_precision_structural_match(
            goal_symbols=goal_symbols,
            declaration_symbols=declaration_symbols,
            shared_symbols=set(shared_symbols),
            goal_structures=goal_structures,
            declaration_structures=declaration_structures,
            shared_structures=set(shared_structures),
            shared_types=set(shared_types),
            shared_add_sub_types=set(shared_add_sub_types),
            goal_applied_symbols=goal_applied_symbols,
            declaration_applied_symbols=declaration_applied_symbols,
        )
        rewrite_head = _loaded_rewrite_head_match(
            item=item,
            relation_parts=top_level_relation_parts(conclusion),
            goal_text=goal_conclusion,
            goal_symbols=goal_symbols,
            declaration_bound_names=declaration_bound_names,
        )
        left_inverse = _loaded_left_inverse_support(
            relation_parts=top_level_relation_parts(conclusion),
            declaration_bound_names=declaration_bound_names,
            transport_transforms=transport_transforms,
        )
        if not any((
            losslessness_match,
            exact,
            order_schema,
            structural,
            rewrite_head,
            left_inverse,
        )):
            continue
        relation = first_top_level_relation(conclusion)
        match_kind = (
            "losslessness_obligation_match" if losslessness_match else
            "exact_conclusion" if exact else
            "order_transitivity_schema" if order_schema else
            "loaded_rewrite_head" if rewrite_head else
            "loaded_left_inverse_support" if left_inverse else
            "loaded_structural_fingerprint"
        )
        score = (
            1100 if losslessness_match else
            1000 if exact else
            700 if order_schema else
            int(rewrite_head.get("score") or 0) if rewrite_head else
            620 if left_inverse else
            500 + 20 * len(shared_structures) + 5 * len(shared_symbols)
        )
        out.append({
            "lemma": lemma,
            "match_kind": match_kind,
            "outer_relation": relation,
            "shared_symbols": shared_symbols,
            "shared_structures": shared_structures,
            "shared_types": (
                shared_add_sub_types
                if "add/sub cancellation equality" in shared_structures
                else shared_types
            ),
            "shared_applied_symbols": sorted(
                goal_applied_symbols & declaration_applied_symbols
            ),
            "rewrite_head": (
                rewrite_head.get("rewrite_head") if rewrite_head else None
            ),
            "rewrite_shape": (
                rewrite_head.get("rewrite_shape") if rewrite_head else None
            ),
            "transform": left_inverse.get("transform") if left_inverse else None,
            "inverse": left_inverse.get("inverse") if left_inverse else None,
            "support_role": left_inverse.get("support_role") if left_inverse else None,
            "declared_procedure": (
                losslessness_match.get("declared_procedure")
                if losslessness_match else None
            ),
            "instantiated_procedure": (
                losslessness_match.get("instantiated_procedure")
                if losslessness_match else None
            ),
            "parameter_bindings": (
                losslessness_match.get("parameter_bindings")
                if losslessness_match else None
            ),
            "direct_application": (
                f"exact {lemma}." if losslessness_match else None
            ),
            "required_premises": (
                losslessness_match.get("required_premises")
                if losslessness_match else [
                    premise.text for premise in statement_ir.premises
                ]
            ),
            "declaration": declaration,
            "source": str(item.get("source") or ""),
            "source_path": str(item.get("source_path") or ""),
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
            "score": score,
        })
    # A bare project-local rewrite head can be useful when it names one
    # unambiguous loaded declaration.  It is not useful when the loaded
    # context contains a whole family with the same bound-only head: that is
    # just a name search result disguised as applicability (for example every
    # ``cbc ...`` or ``weight ...`` lemma).  Fixed nested/literal anchors are
    # precise enough to keep each matching declaration independently.
    ambiguous_head_only = {
        head
        for head in {
            str(item.get("rewrite_head") or "")
            for item in out
            if item.get("match_kind") == "loaded_rewrite_head"
            and _dict(item.get("rewrite_shape")).get("specificity") == "head_only"
        }
        if head and sum(
            1
            for item in out
            if item.get("match_kind") == "loaded_rewrite_head"
            and item.get("rewrite_head") == head
            and _dict(item.get("rewrite_shape")).get("specificity") == "head_only"
        ) > 1
    }
    filtered = [
        item for item in out
        if not (
            item.get("match_kind") == "loaded_rewrite_head"
            and item.get("rewrite_head") in ambiguous_head_only
            and _dict(item.get("rewrite_shape")).get("specificity") == "head_only"
        )
    ]
    return sorted(
        filtered,
        key=lambda item: (
            -int(item.get("score") or 0),
            -int(item.get("authority_rank") or 0),
            str(item.get("lemma") or ""),
        ),
    )[:max_results]


def _goal_map_update_transport_transforms(goal_ir: Any) -> set[str]:
    """Functions visibly transporting keys across two pointwise map relations.

    The signal is intentionally narrow: a quantified premise must relate map
    lookups at ``x`` and ``f x``, and the conclusion must contain finite-map
    updates plus another visible use of ``f``.  A bare occurrence of ``f`` is
    not enough to request inverse support from the loaded lemma index.
    """
    conclusion = str(goal_ir.conclusion.text or "")
    if "<-" not in conclusion or ".[" not in conclusion:
        return set()
    out: set[str] = set()
    outer_binders = {
        name
        for binder_part in goal_ir.binders
        for name in re.findall(
            r"[A-Za-z_][A-Za-z0-9_']*",
            re.sub(r"^forall\s+", "", str(binder_part.text or "")),
        )
        if name not in {"forall"}
    }
    for premise in goal_ir.premises:
        text = str(premise.text or "")
        if (
            ("forall" not in text and not outer_binders)
            or ".[" not in text
            or "=" not in text
        ):
            continue
        binder = re.search(
            r"\bforall\s+(?:\(\s*)?([A-Za-z_][A-Za-z0-9_']*)\b",
            text,
        )
        variables = {binder.group(1)} if binder else outer_binders
        for variable in variables:
            for match in re.finditer(
                rf"\b([A-Za-z_][A-Za-z0-9_.']*)\s+{re.escape(variable)}\b",
                text,
            ):
                transform = match.group(1).rsplit(".", 1)[-1].strip("'")
                if (
                    transform
                    and transform not in _MECHANICAL_TOKEN_SKIP
                    and re.search(rf"\b{re.escape(transform)}\b", conclusion)
                ):
                    out.add(transform)
    return out


def _loaded_left_inverse_support(
    *,
    relation_parts: tuple[str, str, str] | None,
    declaration_bound_names: set[str],
    transport_transforms: set[str],
) -> dict[str, str]:
    """Recognise a loaded declaration of the form ``g (f x) = x``.

    This records algebraic support only.  It does not claim that the complete
    map-update obligation is solved or choose a rewrite order.
    """
    if relation_parts is None or not transport_transforms:
        return {}
    left, relation, right = relation_parts
    if relation != "=":
        return {}
    for variable in sorted(declaration_bound_names, key=len, reverse=True):
        variable_norm = _normalise_formula(variable)
        if not variable_norm:
            continue
        for nested, bare in ((left, right), (right, left)):
            if _normalise_formula(bare) != variable_norm:
                continue
            for transform in sorted(transport_transforms):
                match = re.search(
                    rf"\b([A-Za-z_][A-Za-z0-9_.']*)\s*\(\s*"
                    rf"{re.escape(transform)}\s+{re.escape(variable)}\s*\)",
                    nested,
                )
                if not match:
                    continue
                inverse = match.group(1).rsplit(".", 1)[-1].strip("'")
                if inverse and inverse != transform:
                    return {
                        "transform": transform,
                        "inverse": inverse,
                        "support_role": "left_inverse_for_key_transport",
                    }
    return {}


_BROAD_REWRITE_HEADS = frozenset({
    "size", "nth", "take", "drop", "map", "filter", "mem", "mu", "mu1",
    "iter", "max", "min", "oget",
})
def _loaded_rewrite_head_match(
    *,
    item: dict[str, Any],
    relation_parts: tuple[str, str, str] | None,
    goal_text: str,
    goal_symbols: set[str],
    declaration_bound_names: set[str],
) -> dict[str, Any]:
    """Match a loaded equality by its rewrite head and nested term shape.

    This deliberately stops short of claiming EasyCrypt unification.  A
    project-specific head such as ``gen_CTR_encrypt_bytes`` is precise enough
    on its own. Broad stdlib heads such as ``nth`` or ``size`` are owned by
    dedicated structural producers; admitting them here would duplicate the
    precise structural fact with a large same-head lemma roster.
    """
    if relation_parts is None:
        return {}
    left, relation, _right = relation_parts
    if relation not in {"=", "<=>"}:
        return {}
    declaration = _trim_declaration(str(item.get("declaration") or ""))
    if not declaration or len(declaration) > 4000:
        return {}

    # Forward ``rewrite lemma`` is oriented from the declaration's lhs.  Using
    # the rhs as an independent match turns result constructors such as
    # ``Some`` into a lemma-discovery signal and floods unrelated goals.
    head = _leading_application_head(left, declaration_bound_names)
    if not head or head not in goal_symbols:
        return {}
    if head in _BROAD_REWRITE_HEADS or head in _BROAD_MECHANICAL_SYMBOLS:
        return {}
    fixed_identifiers, fixed_literals = _rewrite_lhs_fixed_anchors(
        left,
        head=head,
        bound_names=declaration_bound_names,
    )
    if not _rewrite_lhs_shape_occurs(
        left,
        goal_text=goal_text,
        head=head,
        bound_names=declaration_bound_names,
    ):
        return {}
    return {
        "rewrite_head": head,
        "rewrite_shape": {
            "declaration_side": "lhs",
            "specificity": (
                "fixed_shape" if fixed_identifiers or fixed_literals else "head_only"
            ),
            "fixed_identifiers": fixed_identifiers,
            "fixed_literals": fixed_literals,
        },
        "score": 640,
    }


def _rewrite_lhs_shape_occurs(
    lhs: str,
    *,
    goal_text: str,
    head: str,
    bound_names: set[str],
) -> bool:
    """Check fixed nested anchors from a rewrite lhs against the goal.

    Bound arguments remain wildcards.  Named constants/operators and their
    parenthesis depth must occur in the same order under one goal occurrence
    of the rewrite head.  This distinguishes ``towords (ofwords x)`` from a
    bare ``towords y`` without pretending to implement EasyCrypt unification.
    """
    lhs_tokens = _identifier_depth_stream(lhs)
    head_index = next(
        (idx for idx, item in enumerate(lhs_tokens) if item[0] == head),
        -1,
    )
    if head_index < 0:
        return False
    head_depth = lhs_tokens[head_index][1]
    anchors, literal_anchors = _rewrite_lhs_fixed_anchors(
        lhs,
        head=head,
        bound_names=bound_names,
    )
    if not anchors and not literal_anchors:
        return True

    # A ground lhs such as ``inv 0%r`` must occur as a whole.  Treating its
    # literal as a free window anchor lets an unrelated later ``else 0%r``
    # make ``invr0`` look applicable to ``inv 4%r``.
    lhs_bound_tokens = {
        leaf for leaf, _depth, _offset in lhs_tokens
        if leaf in bound_names
    }
    if literal_anchors and not lhs_bound_tokens:
        return _normalise_formula(lhs) in _normalise_formula(goal_text)

    goal_tokens = _identifier_depth_stream(goal_text)
    for idx, (leaf, depth, offset) in enumerate(goal_tokens):
        if leaf != head:
            continue
        window = goal_text[offset : offset + 320]
        if any(literal not in window for literal in literal_anchors):
            continue
        if not anchors:
            return True
        anchor_index = 0
        for candidate, candidate_depth, candidate_offset in goal_tokens[idx + 1 :]:
            if candidate_offset - offset > 320 or candidate_depth < depth:
                break
            expected, relative_depth = anchors[anchor_index]
            if candidate == expected and candidate_depth - depth == relative_depth:
                anchor_index += 1
                if anchor_index == len(anchors):
                    return True
        if anchor_index == len(anchors):
            return True
    return False


def _rewrite_lhs_fixed_anchors(
    lhs: str,
    *,
    head: str,
    bound_names: set[str],
) -> tuple[list[tuple[str, int]], list[str]]:
    """Return non-bound identifiers and literals below a rewrite lhs head."""
    lhs_tokens = _identifier_depth_stream(lhs)
    head_index = next(
        (idx for idx, item in enumerate(lhs_tokens) if item[0] == head),
        -1,
    )
    if head_index < 0:
        return [], []
    head_depth = lhs_tokens[head_index][1]
    identifiers: list[tuple[str, int]] = []
    for leaf, depth, _offset in lhs_tokens[head_index + 1 :]:
        if (
            leaf in bound_names
            or leaf.lower() in (_MECHANICAL_TOKEN_SKIP - {"witness"})
        ):
            continue
        identifiers.append((leaf, depth - head_depth))
        if len(identifiers) >= 4:
            break
    literals = list(dict.fromkeys(re.findall(
        r"(?<![A-Za-z0-9_'])(?:-?\d+(?:%[riz])?|true|false)(?![A-Za-z0-9_'])",
        str(lhs or ""),
    )))[:4]
    return identifiers, literals


def _identifier_depth_stream(text: str) -> list[tuple[str, int, int]]:
    source = str(text or "")
    out: list[tuple[str, int, int]] = []
    depth = 0
    idx = 0
    while idx < len(source):
        char = source[idx]
        if char in "([{":
            depth += 1
            idx += 1
            continue
        if char in ")]}":
            depth = max(0, depth - 1)
            idx += 1
            continue
        match = re.match(
            r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*",
            source[idx:],
        )
        if match:
            token = match.group(0)
            out.append((token.rsplit(".", 1)[-1].strip("'"), depth, idx))
            idx += len(token)
            continue
        idx += 1
    return out


def _leading_application_head(text: str, bound_names: set[str]) -> str:
    source = str(text or "").strip()
    source = re.sub(r"^[([{\s]+", "", source)
    match = re.match(r"([A-Za-z_][A-Za-z0-9_.']*)\b", source)
    if not match:
        return ""
    leaf = match.group(1).rsplit(".", 1)[-1].strip("'")
    if leaf in bound_names or leaf.lower() in _MECHANICAL_TOKEN_SKIP:
        return ""
    remainder = source[match.end():].lstrip()
    if (
        not remainder
        or remainder[0] in ".=<>+*/\\|&,:]})"
        or re.match(r"(?:by|proof|qed)\b", remainder)
    ):
        return ""
    return leaf


def _declaration_statement(declaration: str) -> str:
    text = _trim_declaration(declaration)
    match = re.search(r"\b(?:local\s+)?(?:lemma|axiom)\b", text)
    if not match:
        return ""
    depth = 0
    colon = -1
    for idx in range(match.end(), len(text)):
        char = text[idx]
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == ":" and depth == 0 and (idx == 0 or text[idx - 1] != "<"):
            colon = idx
            break
    if colon < 0:
        return ""
    return re.sub(r"\.\s*$", "", text[colon + 1 :].strip())


def _trim_declaration(declaration: str) -> str:
    """Keep one declaration header through its terminating top-level dot."""
    text = str(declaration or "").strip()
    match = re.search(r"\b(?:local\s+)?(?:lemma|axiom)\b", text)
    if not match:
        return ""
    depth = 0
    for idx in range(match.end(), len(text)):
        char = text[idx]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "." and depth == 0:
            next_char = text[idx + 1] if idx + 1 < len(text) else ""
            if not next_char or next_char.isspace():
                return text[: idx + 1].strip()
    proof = re.search(r"\bproof\.", text, flags=re.IGNORECASE)
    return text[: proof.start()].strip() if proof else text


def _normalise_formula(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).rstrip(".")


def _is_order_transitivity_schema(ir: Any) -> bool:
    if len(ir.premises) != 2:
        return False
    first = top_level_relation_parts(ir.premises[0].text)
    second = top_level_relation_parts(ir.premises[1].text)
    conclusion = top_level_relation_parts(ir.conclusion.text)
    if first is None or second is None or conclusion is None:
        return False
    a, first_relation, b = first
    b_again, second_relation, c = second
    a_again, conclusion_relation, c_again = conclusion
    ascending = {"<", "<="}
    descending = {">", ">="}
    relation_family_matches = (
        {first_relation, second_relation, conclusion_relation} <= ascending
        or {first_relation, second_relation, conclusion_relation} <= descending
    )
    return bool(
        relation_family_matches
        and _normalise_formula(a) == _normalise_formula(a_again)
        and _normalise_formula(b) == _normalise_formula(b_again)
        and _normalise_formula(c) == _normalise_formula(c_again)
    )


def _mechanical_type_anchors(text: str) -> set[str]:
    """Small type vocabulary used only to disambiguate structural schemas."""
    anchors = {
        "real", "int", "bool", "unit", "list", "fset", "fmap", "distr",
        "ereal", "word", "field", "ring",
    }
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.']*", str(text or "")))
    return {
        token.rsplit(".", 1)[-1]
        for token in tokens
        if token.lower() in anchors or "." in token
    }


_MECHANICAL_TOKEN_SKIP = frozenset({
    "lemma", "axiom", "local", "forall", "exists", "fun", "let", "in",
    "if", "then", "else", "true", "false", "res", "glob", "with",
    "proof", "qed", "admit", "current", "goal", "type", "variables",
    "none", "left", "right", "pre", "post", "arg", "witness",
    "real", "int", "bool", "unit", "list", "fset", "fmap", "distr",
})

_BROAD_MECHANICAL_SYMBOLS = frozenset({
    "size", "mem", "mu", "mu1", "card", "map", "filter", "nth", "take",
    "drop", "oget", "Some", "None",
})


def _mechanical_operator_signature(
    text: str,
    *,
    bound_names: set[str],
) -> set[str]:
    """Free named symbols in a formula, reduced to their qualified leaf name."""
    out: set[str] = set()
    cleaned = re.sub(r"%[A-Za-z][A-Za-z0-9_']*", " ", str(text or ""))
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_'.]*", cleaned):
        leaf = token.rsplit(".", 1)[-1].strip("'")
        if not leaf or leaf in bound_names or leaf.lower() in _MECHANICAL_TOKEN_SKIP:
            continue
        if leaf.isdigit() or re.fullmatch(r"[A-Z]", leaf):
            continue
        out.add(leaf)
    return out


def _mechanical_applied_symbol_signature(
    text: str,
    *,
    bound_names: set[str],
) -> set[str]:
    """Named operators visibly applied with a parenthesized argument."""
    out: set[str] = set()
    for match in re.finditer(
        r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*\(",
        str(text or ""),
    ):
        leaf = match.group(1).rsplit(".", 1)[-1].strip("'")
        if (
            leaf
            and leaf not in bound_names
            and leaf.lower() not in _MECHANICAL_TOKEN_SKIP
        ):
            out.add(leaf)
    return out


def _declaration_bound_names(declaration: str) -> set[str]:
    text = _trim_declaration(declaration)
    statement = _declaration_statement(text)
    header = text[: text.find(statement)] if statement and statement in text else text
    names: set[str] = set()
    for group in re.finditer(r"\(\s*([^():]+?)\s*:\s*[^)]*\)", header):
        names.update(re.findall(r"[A-Za-z_][A-Za-z0-9_']*", group.group(1)))
    for memory in re.findall(r"&([A-Za-z_][A-Za-z0-9_']*)", header):
        names.add(memory)
    bare_header = re.sub(
        r"\b(?:local\s+)?(?:lemma|axiom)\s+[A-Za-z_][A-Za-z0-9_']*",
        " ",
        header,
        count=1,
    )
    bare_header = re.sub(r"\[[^]]*\]|\([^)]*\)|&[A-Za-z_][A-Za-z0-9_']*", " ", bare_header)
    names.update(re.findall(r"[A-Za-z_][A-Za-z0-9_']*", bare_header))
    for quantifier in re.finditer(
        r"\b(?:forall|exists|fun)\b\s+([^,:=]+?)(?=,|=>)",
        statement,
    ):
        names.update(re.findall(r"[A-Za-z_][A-Za-z0-9_']*", quantifier.group(1)))
    return names


def _goal_bound_names(goal_text: str) -> set[str]:
    names: set[str] = set()
    lines = str(goal_text or "").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped and set(stripped) == {"-"}:
            break
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_' ,]*)\s*:", line)
        if match:
            names.update(re.findall(r"[A-Za-z_][A-Za-z0-9_']*", match.group(1)))
    for group in re.finditer(r"\(\s*([^():]+?)\s*:\s*[^)]*\)", goal_text):
        names.update(re.findall(r"[A-Za-z_][A-Za-z0-9_']*", group.group(1)))
    for memory in re.findall(r"&([A-Za-z_][A-Za-z0-9_']*)", goal_text):
        names.add(memory)
    return names


def _mechanical_structures(text: str) -> set[str]:
    compact = " ".join(str(text or "").split())
    structures: set[str] = set()
    if re.search(r"\bmu\b.{0,160}\(\s*mem\b", compact) and "size" in compact:
        structures.add("finite-membership measure bound")
    if re.search(r"\bmu\b.{0,160}\bpred0\b", compact) and re.search(r"=\s*0%r\b", compact):
        structures.add("zero-event measure")
    if re.search(
        r"\.\[[^\]\n]*<-[^\]\n]*\]\s*\.\[(?![^\]\n]*<-)[^\]\n]*\]",
        compact,
    ):
        structures.add("map update followed by lookup")
    if re.search(r"\.\[[^\]\n]*<-[^\]\n]*\]", compact) and "\\in" in compact:
        if re.search(r"\\in\s+fdom\b", compact):
            structures.add("membership in map domain after update")
        else:
            structures.add("membership after map update")
    if "=" in compact and "+" in compact and "-" in compact:
        structures.add("add/sub cancellation equality")
    return structures


def _declared_type_names(declaration: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r"\([^():]*:\s*([^()]*)\)", declaration):
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_.']*", match.group(1)):
            names.add(token.rsplit(".", 1)[-1].strip("'"))
    for line in str(declaration or "").splitlines():
        match = re.match(r"\s*[A-Za-z_][A-Za-z0-9_' ,]*\s*:\s*(.+)$", line)
        if not match or any(
            marker in match.group(1)
            for marker in ("<=", ">=", "=>", "=", "\\in", "/\\", "\\/")
        ):
            continue
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_.']*", match.group(1)):
            names.add(token.rsplit(".", 1)[-1].strip("'"))
    names.difference_update(_MECHANICAL_TOKEN_SKIP)
    names.discard("")
    return {name for name in names if len(name) > 1}


def _declared_variable_types(text: str) -> dict[str, str]:
    """Map locally declared variables to their simple type names.

    This intentionally recognizes only explicit ``names : type`` binders.
    Structural matching must not infer that an operation belongs to a type
    merely because an unrelated variable of that type is in scope.
    """
    out: dict[str, str] = {}
    binder = re.compile(
        r"(?:^|[({;,])\s*"
        r"([A-Za-z_][A-Za-z0-9_']*(?:\s*(?:,|\s)\s*[A-Za-z_][A-Za-z0-9_']*)*)"
        r"\s*:\s*([A-Za-z_][A-Za-z0-9_.']*)",
        re.M,
    )
    for match in binder.finditer(str(text or "")):
        type_name = match.group(2).rsplit(".", 1)[-1].strip("'")
        if not type_name or type_name in _MECHANICAL_TOKEN_SKIP:
            continue
        for name in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", match.group(1)):
            if name not in _MECHANICAL_TOKEN_SKIP:
                out[name] = type_name
    return out


def _add_sub_operand_types(
    expression: str,
    variable_types: dict[str, str],
) -> set[str]:
    """Return types of declared variables used directly at ``+``/``-``.

    The locality check is the important part: a goal containing integer
    subtraction and an unrelated ``poly_out`` variable must not match a
    ``poly_out`` cancellation lemma.
    """
    compact = " ".join(str(expression or "").split())
    out: set[str] = set()
    for name, type_name in variable_types.items():
        token = rf"\b{re.escape(name)}\b"
        if (
            re.search(rf"{token}\s*(?:\+|-(?!>))", compact)
            or re.search(rf"(?:\+|(?<!<)-)\s*{token}", compact)
        ):
            out.add(type_name)
    return out


def _high_precision_structural_match(
    *,
    goal_symbols: set[str],
    declaration_symbols: set[str],
    shared_symbols: set[str],
    goal_structures: set[str],
    declaration_structures: set[str],
    shared_structures: set[str],
    shared_types: set[str],
    shared_add_sub_types: set[str],
    goal_applied_symbols: set[str],
    declaration_applied_symbols: set[str],
) -> bool:
    if "finite-membership measure bound" in shared_structures:
        return {"mu", "mem", "size"} <= shared_symbols
    # Map updates are intentionally not matched from these broad labels alone.
    # The pure-tail analyzer owns key/update/lookup facts and can distinguish
    # same-key from different-key obligations.  Shared update/membership syntax
    # is not evidence that an arbitrary loaded map lemma applies.
    if "zero-event measure" in shared_structures:
        return True
    if "add/sub cancellation equality" in shared_structures:
        return bool(shared_add_sub_types) and not declaration_symbols
    specific_shared = shared_symbols - _BROAD_MECHANICAL_SYMBOLS
    declaration_specific = declaration_symbols - _BROAD_MECHANICAL_SYMBOLS
    shared_applied = goal_applied_symbols & declaration_applied_symbols
    return bool(
        len(shared_symbols) >= 2
        and specific_shared
        and declaration_specific <= goal_symbols
        and len(shared_symbols) == len(declaration_symbols)
        and declaration_structures <= goal_structures
        and len(declaration_applied_symbols) >= 2
        and declaration_applied_symbols <= shared_applied
    )


def semantic_pr_rewrite_candidates(
    lemma_index: dict[str, Any],
    *,
    parsed: dict[str, Any] | None = None,
    goal_text: str = "",
    target_lemma: str = "",
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Return Pr equality/rewrite candidates that overlap the current goal."""
    parsed = _dict(parsed)
    if str(parsed.get("goal_type") or "") not in {"", "probability"}:
        return []
    if len(pr_game_keys_from_text(goal_text)) not in {1, 2}:
        return []
    goal_keys = goal_pr_game_keys(parsed, goal_text)
    if not goal_keys:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _list(lemma_index.get("items")):
        if not isinstance(item, dict):
            continue
        lemma = str(item.get("lemma") or "")
        if not lemma or lemma == target_lemma or lemma in seen:
            continue
        tags = {str(tag) for tag in _list(item.get("semantic_tags"))}
        if "pr_rewrite" not in tags:
            continue
        decl_games = [
            str(key) for key in _list(item.get("pr_game_keys"))
            if str(key)
        ]
        if len(decl_games) != 2:
            continue
        score = score_pr_rewrite_candidate(goal_keys, decl_games)
        if score < 3:
            continue
        exact_matches = _exact_pr_endpoint_matches(goal_keys, decl_games)
        declaration = _trim_declaration(str(item.get("declaration") or ""))
        statement = _declaration_statement(declaration)
        statement_ir = build_proof_obligation_ir(statement) if statement else None
        seen.add(lemma)
        out.append({
            "lemma": lemma,
            "name": lemma,
            "source": f"{item.get('source')}.pr_rewrite_declaration",
            "source_path": str(item.get("source_path") or ""),
            "declaration_kind": str(item.get("declaration_kind") or "lemma"),
            "declaration": declaration,
            "fact_source": str(item.get("fact_source") or "source_scan"),
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
            "lhs_game": decl_games[0],
            "rhs_game": decl_games[1],
            "required_premises": (
                [premise.text for premise in statement_ir.premises]
                if statement_ir is not None else []
            ),
            "exact_endpoint_match": bool(exact_matches),
            "exact_endpoint_matches": exact_matches,
            "semantic_tags": sorted(tags),
            "score": score,
            "reason": (
                _candidate_reason(item, family="Pr equality/rewrite")
            ),
        })
    return sorted(
        out,
        key=lambda item: (
            -int(item.get("score") or 0),
            -int(item.get("authority_rank") or 0),
            str(item.get("source") or ""),
            str(item.get("lemma") or ""),
        ),
    )[:max_results]


def _exact_pr_endpoint_matches(
    goal_keys: list[str],
    declaration_keys: list[str],
) -> list[dict[str, Any]]:
    if len(declaration_keys) != 2:
        return []
    out: list[dict[str, Any]] = []
    sides = (("lhs", declaration_keys[0], declaration_keys[1]),
             ("rhs", declaration_keys[1], declaration_keys[0]))
    for goal_index, goal_key in enumerate(goal_keys):
        for side, endpoint, other_endpoint in sides:
            if goal_key != endpoint:
                continue
            out.append({
                "goal_endpoint_index": goal_index,
                "goal_endpoint": goal_key,
                "lemma_side": side,
                "other_endpoint": other_endpoint,
                "rewrite_direction": (
                    "lhs_to_rhs" if side == "lhs" else "rhs_to_lhs"
                ),
            })
    return out


def semantic_pr_bound_candidates(
    lemma_index: dict[str, Any],
    *,
    parsed: dict[str, Any] | None = None,
    goal_type: str = "",
    goal_text: str = "",
    target_lemma: str = "",
    max_results: int = 6,
) -> list[dict[str, Any]]:
    """Return project-local Pr bound/union candidates for a Pr inequality."""
    parsed = _dict(parsed)
    form = str(parsed.get("prob_form") or "")
    if str(goal_type or parsed.get("goal_type") or "") != "probability":
        return []
    if "ineq" not in form and "<=" not in str(goal_text or "") and ">=" not in str(goal_text or ""):
        return []
    goal_keys = goal_pr_game_keys(parsed, goal_text)
    goal_events = [str(term.get("event") or "") for term in parse_pr_terms(
        goal_text,
        default_memory="&m",
        default_event="res",
        require_endpoint=False,
    )]
    if not goal_keys and not goal_events:
        return []
    goal_shape = _pr_bound_goal_shape(goal_text)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _list(lemma_index.get("items")):
        if not isinstance(item, dict):
            continue
        lemma = str(item.get("lemma") or "")
        if not lemma or lemma == target_lemma or lemma in seen:
            continue
        tags = {str(tag) for tag in _list(item.get("semantic_tags"))}
        if "pr_bound" not in tags and "pr_inequality" not in tags:
            continue
        score = _score_pr_bound_candidate(
            goal_keys=goal_keys,
            goal_events=goal_events,
            goal_shape=goal_shape,
            item=item,
        )
        if score < 3:
            continue
        declaration = _trim_declaration(str(item.get("declaration") or ""))
        statement = _declaration_statement(declaration)
        statement_ir = build_proof_obligation_ir(statement) if statement else None
        seen.add(lemma)
        out.append({
            "lemma": lemma,
            "name": lemma,
            "source": f"{item.get('source')}.semantic_pr_bound",
            "source_path": str(item.get("source_path") or ""),
            "declaration_kind": str(item.get("declaration_kind") or "lemma"),
            "declaration": declaration,
            "fact_source": str(item.get("fact_source") or "source_scan"),
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
            "pr_game_keys": [
                str(key) for key in _list(item.get("pr_game_keys")) if str(key)
            ],
            "module_parameters": [
                str(name) for name in _list(item.get("module_parameters")) if str(name)
            ],
            "pr_events": [
                str(event) for event in _list(item.get("pr_events")) if str(event)
            ],
            "semantic_tags": sorted(tags),
            "required_premises": (
                [premise.text for premise in statement_ir.premises]
                if statement_ir is not None else []
            ),
            "score": score,
            "goal_shape": goal_shape,
            "reason": (
                _candidate_reason(item, family="Pr inequality/bound")
            ),
        })
    return sorted(
        out,
        key=lambda item: (
            -int(item.get("score") or 0),
            -int(item.get("authority_rank") or 0),
            str(item.get("source") or ""),
            str(item.get("lemma") or ""),
        ),
    )[:max_results]


def high_precision_pr_bound_routes(
    candidates: list[dict[str, Any]],
    *,
    goal_text: str,
    max_results: int = 6,
) -> list[dict[str, Any]]:
    """Select mechanically relevant theorem-level Pr bound declarations.

    Exact current-goal endpoints identify component bounds.  In an additive
    probability goal, one strongly overlapping additive declaration may also
    be retained as the outer decomposition route.  The result is a route set,
    never a selected proof architecture.
    """
    goal_keys = pr_game_keys_from_text(goal_text)
    goal_key_set = set(goal_keys)
    additive_goal = _pr_bound_goal_shape(goal_text) == "additive"
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        keys = [
            str(key) for key in _list(candidate.get("pr_game_keys")) if str(key)
        ]
        exact = [key for key in keys if key in goal_key_set]
        parameterized, bindings = _parameterized_pr_endpoint_matches(
            candidate,
            goal_keys=goal_keys,
        )
        tags = {str(tag) for tag in _list(candidate.get("semantic_tags"))}
        score = int(candidate.get("score") or 0)
        outer_decomposition = bool(
            additive_goal
            and "pr_additive_bound" in tags
            and len(keys) >= 3
            and (score >= 16 or len(parameterized) >= 2)
        )
        visible_matches = _dedupe_strings([*exact, *parameterized])
        exact_component = bool(
            (exact and additive_goal) or len(visible_matches) >= 2
        )
        if not exact_component and not outer_decomposition:
            continue
        out.append({
            "lemma": candidate.get("lemma"),
            "route_role": (
                "outer_bound_decomposition"
                if outer_decomposition else "exact_visible_term_bound"
            ),
            "exact_goal_endpoints": exact,
            "parameterized_goal_endpoints": parameterized,
            "parameter_bindings": bindings,
            "module_parameters": candidate.get("module_parameters"),
            "declared_endpoints": keys,
            "required_premises": candidate.get("required_premises"),
            "score": score,
            "authority": candidate.get("authority"),
            "source_path": candidate.get("source_path"),
            "declaration": candidate.get("declaration"),
        })
    return sorted(
        out,
        key=lambda item: (
            0 if item.get("route_role") == "outer_bound_decomposition" else 1,
            -len(_list(item.get("exact_goal_endpoints"))),
            -int(item.get("score") or 0),
            str(item.get("lemma") or ""),
        ),
    )[:max_results]


def semantic_one_sided_losslessness_candidates(
    lemma_index: dict[str, Any],
    *,
    procedures: list[str],
    target_lemma: str = "",
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Match loaded losslessness conclusions to visible procedure calls.

    This is a declaration-shape match, not an EasyCrypt application verdict.
    Only declaration-bound module identifiers may vary; the functor spine and
    procedure name must remain identical.  The resulting binding and the
    instantiated premises are mechanical context that a later call-site pass
    may expose when the matching call is actually at the live frontier.
    """
    concrete_procedures = _dedupe_strings([
        _compact_losslessness_procedure(procedure)
        for procedure in procedures
        if _compact_losslessness_procedure(procedure)
    ])
    if not concrete_procedures:
        return []

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in _list(lemma_index.get("items")):
        if not isinstance(item, dict):
            continue
        lemma = str(item.get("lemma") or "").strip()
        if not lemma or lemma == target_lemma:
            continue
        declaration = _trim_declaration(str(item.get("declaration") or ""))
        statement = _declaration_statement(declaration)
        if not statement:
            continue
        obligation = build_proof_obligation_ir(statement)
        declared_procedure = _losslessness_conclusion_procedure(
            obligation.conclusion.text,
        )
        if not declared_procedure:
            continue

        explicit_param_order = _ordered_explicit_module_parameters(declaration)
        ambient_params = {
            str(name)
            for name in _list(item.get("module_parameters"))
            if str(name)
        }
        # Source-scanned ambient section modules do not carry their module-type
        # constraints in the declaration text.  Treating them as free binders
        # manufactures unrelated certificates (for example, rewriting an
        # ambient EPRF into any visible *.f procedure).  Only explicit binders
        # have enough declaration-local evidence for this shape match.  Exact
        # ambient-module conclusions remain valid through the equality branch.
        module_params = set(explicit_param_order)
        declared_key = _compact_losslessness_procedure(declared_procedure)
        for concrete in concrete_procedures:
            if declared_key == concrete:
                bindings: dict[str, str] = {}
                match_kind = "exact_procedure"
            elif module_params:
                matched = _match_parameterized_procedure(
                    declared_key,
                    concrete,
                    module_params=module_params,
                    bindings={},
                )
                if matched is None:
                    continue
                bindings = matched
                match_kind = "module_parameter_instantiation"
            else:
                continue

            key = (lemma, concrete)
            if key in seen:
                continue
            seen.add(key)
            visible_bindings = {
                name: value
                for name, value in bindings.items()
                if value != name
            }
            premises = [
                _instantiate_module_parameters(premise.text, bindings)
                for premise in obligation.premises
                if premise.text
            ]
            module_argument_terms = {
                name: f"<: {bindings[name]}"
                for name in explicit_param_order
                if bindings.get(name)
            }
            application_parts = [lemma]
            application_parts.extend(
                f"({module_argument_terms[name]})"
                for name in explicit_param_order
                if name in module_argument_terms
            )
            application_parts.extend("_" for _ in premises)
            complete_module_application = bool(
                explicit_param_order
                and len(module_argument_terms) == len(explicit_param_order)
            )
            instantiated_lemma_head = (
                " ".join(application_parts[: 1 + len(explicit_param_order)])
                if complete_module_application else ""
            )
            call_template = (
                f"call ({' '.join(application_parts)})."
                if complete_module_application else ""
            )
            out.append({
                "lemma": lemma,
                "name": lemma,
                "certificate_kind": "losslessness",
                "procedure": concrete,
                "declared_procedure": declared_procedure,
                "match_kind": match_kind,
                "parameter_bindings": visible_bindings,
                "explicit_module_parameters": explicit_param_order,
                "ambient_module_parameters": sorted(ambient_params),
                "module_argument_terms": module_argument_terms,
                "instantiated_lemma_head": instantiated_lemma_head,
                "proof_argument_placeholders": ["_" for _ in premises],
                "call_template": call_template,
                "required_premises": premises,
                "declaration": declaration,
                "source": f"{item.get('source')}.one_sided_losslessness",
                "source_path": str(item.get("source_path") or ""),
                "fact_source": str(item.get("fact_source") or "source_scan"),
                "authority": str(item.get("authority") or "source_scan_fallback"),
                "authority_rank": int(item.get("authority_rank") or 0),
                "ec_ground_truth": bool(item.get("ec_ground_truth")),
                "verification_status": (
                    "loaded declaration conclusion matches the visible procedure; "
                    "EasyCrypt application is not pre-committed"
                ),
            })

    return sorted(
        out,
        key=lambda candidate: (
            0 if candidate.get("match_kind") == "exact_procedure" else 1,
            -int(candidate.get("authority_rank") or 0),
            str(candidate.get("lemma") or ""),
            str(candidate.get("procedure") or ""),
        ),
    )[:max_results]


def semantic_distribution_certificates(
    lemma_index: dict[str, Any],
    *,
    goal_text: str,
    target_lemma: str = "",
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Bind loaded distribution declarations to the current pure obligation.

    Two narrow mechanical equivalences are admitted here:

    * ``is_lossless d`` and ``weight d = 1%r`` are the two canonical forms of
      the same distribution-losslessness obligation;
    * interval notation ``[i..j]`` is the pretty form of ``dinter i j``.

    The function reports declarations and substitutions only.  It does not
    choose ``exact`` versus ``rewrite``, simplify the resulting arithmetic, or
    claim that the complete goal is discharged.
    """
    obligation = build_proof_obligation_ir(goal_text)
    conclusion = str(obligation.conclusion.text or "").strip()
    if not conclusion:
        return []

    items = [
        item for item in _list(lemma_index.get("items"))
        if isinstance(item, dict)
        and str(item.get("declaration_kind") or "").lower() in {
            "lemma", "local lemma", "axiom", "local axiom",
        }
    ]
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    lossless_distribution = _lossless_distribution_target(conclusion)
    if lossless_distribution:
        goal_key = _normalise_distribution_term(lossless_distribution)
        for item in items:
            lemma = str(item.get("lemma") or "").strip()
            if not lemma or lemma == target_lemma:
                continue
            declaration = _trim_declaration(str(item.get("declaration") or ""))
            statement = _declaration_statement(declaration)
            if not statement:
                continue
            declared_ir = build_proof_obligation_ir(statement)
            declared_distribution = _lossless_distribution_target(
                declared_ir.conclusion.text,
            )
            if (
                not declared_distribution
                or _normalise_distribution_term(declared_distribution) != goal_key
            ):
                continue
            key = (lemma, "losslessness", goal_key)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "lemma": lemma,
                "certificate_kind": "distribution_losslessness",
                "distribution": lossless_distribution,
                "declared_conclusion": declared_ir.conclusion.text,
                "goal_form": conclusion,
                "match_kind": "canonical_losslessness_form",
                "required_premises": [
                    premise.text for premise in declared_ir.premises
                    if premise.text
                ],
                **_distribution_candidate_provenance(item, declaration),
            })

    interval = _goal_interval_point_mass_term(conclusion)
    if interval:
        for item in items:
            lemma = str(item.get("lemma") or "").strip()
            if not lemma or lemma == target_lemma:
                continue
            declaration = _trim_declaration(str(item.get("declaration") or ""))
            statement = _declaration_statement(declaration)
            if not statement:
                continue
            declared_ir = build_proof_obligation_ir(statement)
            declared_mu1 = _declared_dinter_mu1_term(
                declared_ir.conclusion.text,
            )
            if not declared_mu1:
                continue
            bindings = {
                declared_mu1["lower_name"]: interval["lower"],
                declared_mu1["upper_name"]: interval["upper"],
                declared_mu1["point_name"]: interval["point"],
            }
            instantiated = _instantiate_value_parameters(
                declared_ir.conclusion.text,
                bindings,
            )
            cardinality = _interval_cardinality_expression(
                interval["lower"],
                interval["upper"],
            )
            support = _loaded_positive_interval_facts(
                items,
                cardinality=cardinality,
                target_lemma=target_lemma,
            )
            key = (lemma, "normalization", _normalise_formula(instantiated))
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "lemma": lemma,
                "certificate_kind": "finite_interval_point_mass",
                "distribution": interval["display_distribution"],
                "canonical_distribution": (
                    f"dinter {interval['lower']} ({interval['upper']})"
                ),
                "point": interval["point"],
                "match_kind": "interval_notation_to_loaded_identity",
                "declared_conclusion": declared_ir.conclusion.text,
                "parameter_bindings": bindings,
                "instantiated_identity": instantiated,
                "required_premises": [
                    _instantiate_value_parameters(premise.text, bindings)
                    for premise in declared_ir.premises
                    if premise.text
                ],
                "interval_cardinality": cardinality,
                "loaded_supporting_facts": support,
                **_distribution_candidate_provenance(item, declaration),
            })

    return sorted(
        out,
        key=lambda candidate: (
            0 if candidate.get("certificate_kind") == "distribution_losslessness" else 1,
            -int(candidate.get("authority_rank") or 0),
            str(candidate.get("lemma") or ""),
        ),
    )[:max_results]


def _lossless_distribution_target(conclusion: str) -> str:
    text = _strip_balanced_outer_parens(str(conclusion or "").strip().rstrip("."))
    match = re.fullmatch(r"is_lossless\s+(.+)", text, flags=re.DOTALL)
    if match:
        return _strip_balanced_outer_parens(match.group(1).strip())
    relation = top_level_relation_parts(text)
    if relation is None:
        return ""
    left, operator, right = relation
    if operator != "=":
        return ""
    for weight_side, one_side in ((left, right), (right, left)):
        match = re.fullmatch(r"weight\s+(.+)", weight_side.strip(), flags=re.DOTALL)
        if match and _normalise_formula(one_side) == "1%r":
            return _strip_balanced_outer_parens(match.group(1).strip())
    return ""


def _normalise_distribution_term(text: str) -> str:
    return _normalise_formula(_strip_balanced_outer_parens(text))


def _goal_interval_point_mass_term(conclusion: str) -> dict[str, str]:
    relation = _first_top_level_equality_parts(str(conclusion or ""))
    if relation is None:
        return {}
    for side in relation:
        source = side.strip()
        match = re.match(r"(mu1|mu)\s+\[", source)
        if not match:
            continue
        close = source.find("]", match.end())
        if close < 0:
            continue
        interval_body = source[match.end():close]
        bounds = _split_top_level_interval_bounds(interval_body)
        tail = source[close + 1:].strip()
        point = (
            tail
            if match.group(1) == "mu1"
            else _point_from_mass_predicate(tail)
        )
        if bounds is None or not point:
            continue
        lower, upper = bounds
        return {
            "lower": lower,
            "upper": upper,
            "point": point,
            "display_distribution": f"[{lower}..{upper}]",
        }
    return {}


def _first_top_level_equality_parts(text: str) -> tuple[str, str] | None:
    source = _strip_balanced_outer_parens(str(text or "").strip())
    depth = 0
    for idx, char in enumerate(source):
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            depth = max(0, depth - 1)
            continue
        if char != "=" or depth:
            continue
        previous = source[idx - 1] if idx else ""
        following = source[idx + 1] if idx + 1 < len(source) else ""
        if previous in "<>=!" or following in "=>":
            continue
        left = source[:idx].strip()
        right = source[idx + 1:].strip()
        return (left, right) if left and right else None
    return None


def _point_from_mass_predicate(text: str) -> str:
    predicate = _strip_balanced_outer_parens(str(text or "").strip())
    pred1 = re.fullmatch(r"pred1\s+(.+)", predicate, flags=re.DOTALL)
    if pred1:
        return _strip_balanced_outer_parens(pred1.group(1).strip())

    abstraction = re.fullmatch(
        r"fun\s+(?:\(\s*([A-Za-z_][A-Za-z0-9_']*)\s*(?::[^)]*)?\)|"
        r"([A-Za-z_][A-Za-z0-9_']*))\s*=>\s*(.+)",
        predicate,
        flags=re.DOTALL,
    )
    if not abstraction:
        return ""
    variable = abstraction.group(1) or abstraction.group(2)
    body = _strip_balanced_outer_parens(abstraction.group(3).strip())
    relation = top_level_relation_parts(body)
    if relation is None or relation[1] != "=":
        return ""
    left = _strip_balanced_outer_parens(relation[0].strip())
    right = _strip_balanced_outer_parens(relation[2].strip())
    if left == variable and right != variable:
        return right
    if right == variable and left != variable:
        return left
    return ""


def _split_top_level_interval_bounds(text: str) -> tuple[str, str] | None:
    depth = 0
    source = str(text or "")
    for idx in range(len(source) - 1):
        char = source[idx]
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif source[idx:idx + 2] == ".." and depth == 0:
            left = source[:idx].strip()
            right = source[idx + 2:].strip()
            return (left, right) if left and right else None
    return None


def _declared_dinter_mu1_term(conclusion: str) -> dict[str, str]:
    relation = top_level_relation_parts(str(conclusion or ""))
    if relation is None or relation[1] != "=":
        return {}
    lhs = relation[0].strip()
    match = re.fullmatch(
        r"mu1\s+\(\s*dinter\s+([A-Za-z_][A-Za-z0-9_']*)\s+"
        r"([A-Za-z_][A-Za-z0-9_']*)\s*\)\s+"
        r"([A-Za-z_][A-Za-z0-9_']*)",
        lhs,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    return {
        "lower_name": match.group(1),
        "upper_name": match.group(2),
        "point_name": match.group(3),
    }


def _instantiate_value_parameters(text: str, bindings: dict[str, str]) -> str:
    result = str(text or "")
    for name in sorted(bindings, key=len, reverse=True):
        value = bindings[name]
        result = re.sub(
            rf"(?<![A-Za-z0-9_']){re.escape(name)}(?![A-Za-z0-9_'])",
            f"({value})",
            result,
        )
    return re.sub(r"\s+", " ", result).strip()


def _interval_cardinality_expression(lower: str, upper: str) -> str:
    lower_key = _normalise_formula(lower)
    upper_text = _strip_balanced_outer_parens(upper).strip()
    if lower_key in {"0", "0%z"}:
        match = re.fullmatch(r"(.+?)\s*-\s*1", upper_text, flags=re.DOTALL)
        if match:
            return _strip_balanced_outer_parens(match.group(1).strip())
    return f"({upper_text}) - ({lower}) + 1"


def _loaded_positive_interval_facts(
    items: list[dict[str, Any]],
    *,
    cardinality: str,
    target_lemma: str,
) -> list[dict[str, Any]]:
    targets = {
        _normalise_formula(f"0 < {cardinality}"),
        _normalise_formula(f"{cardinality} > 0"),
    }
    out: list[dict[str, Any]] = []
    for item in items:
        lemma = str(item.get("lemma") or "").strip()
        if not lemma or lemma == target_lemma:
            continue
        declaration = _trim_declaration(str(item.get("declaration") or ""))
        statement = _declaration_statement(declaration)
        if not statement:
            continue
        ir = build_proof_obligation_ir(statement)
        if _normalise_formula(ir.conclusion.text) not in targets:
            continue
        out.append({
            "lemma": lemma,
            "fact": ir.conclusion.text,
            "required_premises": [p.text for p in ir.premises if p.text],
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "source_path": str(item.get("source_path") or ""),
        })
    return out[:4]


def _distribution_candidate_provenance(
    item: dict[str, Any],
    declaration: str,
) -> dict[str, Any]:
    return {
        "declaration": declaration,
        "source": f"{item.get('source')}.distribution_certificate",
        "source_path": str(item.get("source_path") or ""),
        "fact_source": str(item.get("fact_source") or "source_scan"),
        "authority": str(item.get("authority") or "source_scan_fallback"),
        "authority_rank": int(item.get("authority_rank") or 0),
        "ec_ground_truth": bool(item.get("ec_ground_truth")),
        "verification_status": (
            "loaded declaration is structurally bound to the current distribution "
            "obligation; EasyCrypt application is not pre-committed"
        ),
    }


def _strip_balanced_outer_parens(text: str) -> str:
    source = str(text or "").strip()
    while source.startswith("(") and source.endswith(")"):
        depth = 0
        balanced = True
        for idx, char in enumerate(source):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and idx != len(source) - 1:
                    balanced = False
                    break
        if not balanced or depth != 0:
            break
        source = source[1:-1].strip()
    return source


def _losslessness_conclusion_procedure(conclusion: str) -> str:
    text = str(conclusion or "").strip().rstrip(".").strip()
    match = re.fullmatch(r"islossless\s+(.+)", text, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def _compact_losslessness_procedure(procedure: str) -> str:
    text = str(procedure or "").strip().rstrip(".").strip()
    if text.endswith("()"):
        text = text[:-2].rstrip()
    return re.sub(r"\s+", "", text)


def _losslessness_obligation_match(
    *,
    goal_ir: Any,
    declaration_ir: Any,
    declaration: str,
    ambient_module_parameters: set[str],
) -> dict[str, Any]:
    """Match a complete loaded losslessness obligation to the current goal.

    The conclusion procedure must match after declaration-bound module
    instantiation, and every premise must match in order after applying the
    same bindings.  This is intentionally stricter than matching only the
    final ``islossless`` head: it prevents a nearby certificate with different
    side conditions from being presented as a direct closer.
    """
    goal_procedure = _losslessness_conclusion_procedure(
        goal_ir.conclusion.text,
    )
    declared_procedure = _losslessness_conclusion_procedure(
        declaration_ir.conclusion.text,
    )
    if not goal_procedure or not declared_procedure:
        return {}

    explicit_order = _ordered_explicit_module_parameters(declaration)
    module_parameters = set(explicit_order) | set(ambient_module_parameters)
    declared_key = _compact_losslessness_procedure(declared_procedure)
    goal_key = _compact_losslessness_procedure(goal_procedure)
    if declared_key == goal_key:
        bindings = {
            name: name
            for name in explicit_order
            if re.search(
                rf"(?<![A-Za-z0-9_']){re.escape(name)}(?![A-Za-z0-9_'])",
                declared_procedure,
            )
        }
    elif module_parameters:
        matched = _match_parameterized_procedure(
            declared_key,
            goal_key,
            module_params=module_parameters,
            bindings={},
        )
        if matched is None:
            return {}
        bindings = matched
    else:
        return {}

    declared_premises = [
        _instantiate_module_parameters(premise.text, bindings)
        for premise in declaration_ir.premises
        if premise.text
    ]
    goal_premises = [
        premise.text for premise in goal_ir.premises if premise.text
    ]
    if len(declared_premises) != len(goal_premises):
        return {}
    if any(
        _normalise_formula(declared) != _normalise_formula(goal)
        for declared, goal in zip(declared_premises, goal_premises)
    ):
        return {}

    visible_bindings = {
        name: value
        for name, value in bindings.items()
        if value != name
    }
    return {
        "declared_procedure": declared_procedure,
        "instantiated_procedure": _instantiate_module_parameters(
            declared_procedure,
            bindings,
        ),
        "parameter_bindings": visible_bindings,
        "required_premises": declared_premises,
    }


def _ordered_explicit_module_parameters(declaration: str) -> list[str]:
    statement = _declaration_statement(declaration)
    header = (
        declaration[: declaration.find(statement)]
        if statement and statement in declaration else declaration
    )
    return re.findall(
        r"\(\s*([A-Za-z_][A-Za-z0-9_']*)\s*<:",
        header,
    )


def _explicit_module_parameters(declaration: str) -> set[str]:
    return set(_ordered_explicit_module_parameters(declaration))


def _instantiate_module_parameters(
    text: str,
    bindings: dict[str, str],
) -> str:
    result = str(text or "")
    for name in sorted(bindings, key=len, reverse=True):
        result = re.sub(
            rf"(?<![A-Za-z0-9_']){re.escape(name)}(?![A-Za-z0-9_'])",
            bindings[name],
            result,
        )
    return result


def _match_parameterized_procedure(
    declared: str,
    concrete: str,
    *,
    module_params: set[str],
    bindings: dict[str, str],
) -> dict[str, str] | None:
    declared_module, declared_leaf = _split_procedure_module_leaf(declared)
    concrete_module, concrete_leaf = _split_procedure_module_leaf(concrete)
    if not declared_leaf or declared_leaf != concrete_leaf:
        return None
    return _match_module_expression(
        declared_module,
        concrete_module,
        module_params=module_params,
        bindings=bindings,
    )


def _split_procedure_module_leaf(procedure: str) -> tuple[str, str]:
    source = re.sub(r"\s+", "", str(procedure or "")).rstrip(".")
    depth = 0
    last_dot = -1
    for idx, char in enumerate(source):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "." and depth == 0:
            last_dot = idx
    if last_dot < 0:
        return "", source
    return source[:last_dot], source[last_dot + 1 :]


def _match_module_expression(
    declared: str,
    concrete: str,
    *,
    module_params: set[str],
    bindings: dict[str, str],
) -> dict[str, str] | None:
    declared = re.sub(r"\s+", "", str(declared or ""))
    concrete = re.sub(r"\s+", "", str(concrete or ""))
    if declared in module_params:
        bound = bindings.get(declared)
        if bound is not None and bound != concrete:
            return None
        return {declared: concrete} if bound is None else {}

    declared_app = _module_application_parts(declared)
    concrete_app = _module_application_parts(concrete)
    if declared_app is None or concrete_app is None:
        return {} if declared == concrete else None
    declared_head, declared_args, declared_suffix = declared_app
    concrete_head, concrete_args, concrete_suffix = concrete_app
    if declared_suffix != concrete_suffix or len(declared_args) != len(concrete_args):
        return None

    local = dict(bindings)
    if declared_head in module_params:
        bound = local.get(declared_head)
        if bound is not None and bound != concrete_head:
            return None
        local.setdefault(declared_head, concrete_head)
    elif declared_head != concrete_head:
        return None

    new_bindings: dict[str, str] = {
        name: value for name, value in local.items() if bindings.get(name) != value
    }
    for declared_arg, concrete_arg in zip(declared_args, concrete_args):
        matched = _match_module_expression(
            declared_arg,
            concrete_arg,
            module_params=module_params,
            bindings={**bindings, **new_bindings},
        )
        if matched is None:
            return None
        new_bindings.update(matched)
    return new_bindings


def _module_application_parts(
    expression: str,
) -> tuple[str, list[str], str] | None:
    source = str(expression or "")
    open_idx = source.find("(")
    if open_idx <= 0:
        return None
    depth = 0
    close_idx = -1
    for idx in range(open_idx, len(source)):
        char = source[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                close_idx = idx
                break
    if close_idx < 0:
        return None
    suffix = source[close_idx + 1 :]
    if suffix and not suffix.startswith("."):
        return None
    return (
        source[:open_idx],
        _split_module_arguments(source[open_idx + 1 : close_idx]),
        suffix,
    )


def _split_module_arguments(text: str) -> list[str]:
    source = str(text or "")
    if not source:
        return []
    out: list[str] = []
    depth = 0
    start = 0
    for idx, char in enumerate(source):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == "," and depth == 0:
            out.append(source[start:idx].strip())
            start = idx + 1
    out.append(source[start:].strip())
    return [item for item in out if item]


def _parameterized_pr_endpoint_matches(
    candidate: dict[str, Any],
    *,
    goal_keys: list[str],
) -> tuple[list[str], dict[str, str]]:
    """Match declared Pr endpoints under one consistent module substitution.

    EasyCrypt theorem declarations commonly quantify a module ``A`` and are
    later instantiated with ``QueryBounder(A)``.  This matcher treats only
    declaration-bound module identifiers as variables; every surrounding game
    constructor and procedure path must remain textually identical.
    """
    declaration = str(candidate.get("declaration") or "")
    module_params = {
        str(name) for name in _list(candidate.get("module_parameters")) if str(name)
    }
    module_params.update(re.findall(
        r"\(\s*([A-Za-z_][A-Za-z0-9_']*)\s*<:",
        declaration,
    ))
    if not module_params:
        return [], {}

    bindings: dict[str, str] = {}
    used_goal_keys: set[str] = set()
    matched: list[str] = []
    for declared_key in [
        str(key) for key in _list(candidate.get("pr_game_keys")) if str(key)
    ]:
        for goal_key in goal_keys:
            if goal_key in used_goal_keys:
                continue
            local = _match_parameterized_game_key(
                declared_key,
                goal_key,
                module_params=module_params,
                bindings=bindings,
            )
            if local is None:
                continue
            bindings.update(local)
            used_goal_keys.add(goal_key)
            matched.append(goal_key)
            break
    return matched, bindings


def _match_parameterized_game_key(
    declared_key: str,
    goal_key: str,
    *,
    module_params: set[str],
    bindings: dict[str, str],
) -> dict[str, str] | None:
    return _match_parameterized_text_key(
        declared_key,
        goal_key,
        module_params=module_params,
        bindings=bindings,
    )


def _match_parameterized_text_key(
    declared_key: str,
    goal_key: str,
    *,
    module_params: set[str],
    bindings: dict[str, str],
) -> dict[str, str] | None:
    pieces: list[str] = []
    cursor = 0
    captured: set[str] = set()
    for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_']*", declared_key):
        pieces.append(re.escape(declared_key[cursor:match.start()]))
        token = match.group(0)
        if token not in module_params:
            pieces.append(re.escape(token))
        elif token in bindings:
            pieces.append(re.escape(bindings[token]))
        elif token in captured:
            pieces.append(f"(?P={token})")
        else:
            pieces.append(f"(?P<{token}>.+?)")
            captured.add(token)
        cursor = match.end()
    pieces.append(re.escape(declared_key[cursor:]))
    result = re.fullmatch("".join(pieces), goal_key)
    if result is None:
        return None
    return {
        name: value
        for name, value in result.groupdict().items()
        if value is not None
    }


def semantic_pr_rewrite_declarations(lemma_index: dict[str, Any]) -> list[dict[str, Any]]:
    """Return indexed Pr equality declarations in the legacy rewrite shape."""
    out: list[dict[str, Any]] = []
    for item in _list(lemma_index.get("items")):
        if not isinstance(item, dict):
            continue
        if "pr_rewrite" not in {str(tag) for tag in _list(item.get("semantic_tags"))}:
            continue
        games = [
            str(key) for key in _list(item.get("pr_game_keys"))
            if str(key)
        ]
        if len(games) != 2:
            continue
        copied = {
            "lemma": str(item.get("lemma") or ""),
            "name": str(item.get("lemma") or ""),
            "declaration": str(item.get("declaration") or ""),
            "declaration_kind": str(item.get("declaration_kind") or ""),
            "source": str(item.get("source") or ""),
            "source_path": str(item.get("source_path") or ""),
            "fact_source": str(item.get("fact_source") or "source_scan"),
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
            "lhs_game": games[0],
            "rhs_game": games[1],
            "semantic_tags": list(item.get("semantic_tags") or []),
        }
        if copied["lemma"]:
            out.append(copied)
    return out


def source_declarations_by_name(
    lemma_index: dict[str, Any],
    names: list[str],
) -> dict[str, dict[str, str]]:
    """Return declarations for specific names from a built semantic index."""
    wanted = {str(name) for name in names if str(name)}
    if not wanted:
        return {}
    out: dict[str, dict[str, str]] = {}
    for item in _list(lemma_index.get("items")):
        if not isinstance(item, dict):
            continue
        lemma = str(item.get("lemma") or "")
        if lemma not in wanted or lemma in out:
            continue
        out[lemma] = {
            "lemma": lemma,
            "declaration_kind": str(item.get("declaration_kind") or ""),
            "source": str(item.get("source") or ""),
            "source_path": str(item.get("source_path") or ""),
            "declaration": str(item.get("declaration") or ""),
            "fact_source": str(item.get("fact_source") or "source_scan"),
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
        }
    return out


def goal_pr_game_keys(parsed: dict[str, Any], goal_text: str) -> list[str]:
    """Return goal game keys from text plus parser-provided probability fields."""
    keys = pr_game_keys_from_text(goal_text)
    for key in (
        "lhs_game",
        "rhs_game",
        "lhs_pos_game",
        "rhs_pos_game",
        "lhs_neg_game",
        "rhs_neg_game",
    ):
        game = game_key(parsed.get(key))
        if game and game not in keys:
            keys.append(game)
    return keys


def score_pr_rewrite_candidate(
    goal_keys: list[str],
    declaration_keys: list[str],
) -> int:
    """Score overlap between goal games and a two-sided Pr rewrite lemma."""
    best = 0
    for goal in goal_keys:
        for declaration in declaration_keys:
            best = max(best, game_similarity(goal, declaration))
    if len(goal_keys) >= 2 and len(declaration_keys) >= 2:
        best = max(
            best,
            pr_endpoint_pair_score(
                goal_keys[0],
                goal_keys[1],
                declaration_keys[0],
                declaration_keys[1],
            ),
        )
    return best


def pr_endpoint_pair_score(
    goal_lhs: str,
    goal_rhs: str,
    declaration_lhs: str,
    declaration_rhs: str,
) -> int:
    forward = (
        game_similarity(goal_lhs, declaration_lhs)
        + game_similarity(goal_rhs, declaration_rhs)
    )
    backward = (
        game_similarity(goal_lhs, declaration_rhs)
        + game_similarity(goal_rhs, declaration_lhs)
    )
    return max(forward, backward)


def game_similarity(left: str, right: str) -> int:
    """Conservative structural score for canonical game keys."""
    if not left or not right:
        return 0
    if left == right:
        return 8
    left_root = game_root(left)
    right_root = game_root(right)
    left_atoms = set(game_atoms(left))
    right_atoms = set(game_atoms(right))
    shared_atoms = len(left_atoms & right_atoms)
    if left_root and left_root == right_root:
        return 4 + min(shared_atoms, 3)
    if shared_atoms >= 2:
        return 3
    if shared_atoms == 1 and (left_root in right_atoms or right_root in left_atoms):
        return 2
    return 0


def game_root(key: str) -> str:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_']*)", str(key or ""))
    return match.group(1) if match else ""


def game_atoms(key: str) -> list[str]:
    root = game_root(key)
    atoms = [
        token for token in re.findall(r"\b[A-Z][A-Za-z0-9_']*\b", str(key or ""))
        if token != root
    ]
    return _dedupe_strings(atoms)


def session_target_lemma(session_dir: str | Path | None) -> str:
    if session_dir is None:
        return ""
    meta_path = Path(session_dir) / "session_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except Exception:
        return ""
    return str(meta.get("lemma") or "")


def session_context_files(session_dir: str | Path | None) -> list[tuple[Path, str]]:
    if session_dir is None:
        return []
    sdir = Path(session_dir)
    out: list[tuple[Path, str]] = []
    ctx = sdir / "context.ec"
    if ctx.exists():
        out.append((ctx, "session_context"))
    meta_path = sdir / "session_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except Exception:
        meta = {}
    raw = meta.get("file") or meta.get("source_file")
    if raw:
        p = Path(str(raw)).expanduser()
        if not p.is_absolute():
            for candidate in (Path.cwd() / p, sdir / p, sdir.parent / p):
                if candidate.exists():
                    p = candidate
                    break
        if p.exists():
            out.append((p, "source_file"))
    deduped: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path, kind in out:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append((path, kind))
    return deduped


def imported_theory_files(
    context_text: str,
    session_dir: str | Path | None,
) -> list[Path]:
    theory_names = require_theory_names(context_text)
    if not theory_names:
        return []
    roots = import_search_roots(session_dir)
    files: list[Path] = []
    seen: set[Path] = set()
    for name in theory_names:
        tail = name.rsplit(".", 1)[-1]
        if not tail:
            continue
        for root in roots:
            for path in ec_files_named(root, f"{tail}.ec")[:4]:
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                files.append(path)
                break
        if len(files) >= 32:
            break
    return files


def require_theory_names(text: str) -> list[str]:
    names: list[str] = []
    cleaned = re.sub(r"\(\*.*?\*\)", " ", str(text or ""), flags=re.DOTALL)
    for match in re.finditer(
        r"\brequire\b(?P<body>.*?)(?=\.)",
        cleaned,
        flags=re.DOTALL,
    ):
        body = re.sub(r"\([^)]*\)", " ", match.group("body") or "")
        body = re.sub(r"\bimport\b", " ", body)
        for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", body):
            if token in {"require", "import"}:
                continue
            names.append(token)
    return _dedupe_strings(names)


def import_search_roots(session_dir: str | Path | None) -> list[Path]:
    roots: list[Path] = []
    cwd = Path.cwd()
    for path in (
        cwd / "easycrypt-src" / "theories",
    ):
        if path.exists():
            roots.append(path)
    if session_dir is not None:
        sdir = Path(session_dir)
        roots.append(sdir)
        meta_path = sdir / "session_meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        except Exception:
            meta = {}
        raw = meta.get("file") or meta.get("source_file")
        if raw:
            source = Path(str(raw)).expanduser()
            if not source.is_absolute():
                source = (sdir.parent / source).resolve()
            if source.exists():
                roots.append(source.parent)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(root)
    return deduped


def ec_files_named(root: Path, filename: str) -> list[Path]:
    resolved = root.resolve()
    direct_candidates = [
        resolved / filename,
        resolved / "crypto" / filename,
        resolved / "datatypes" / filename,
        resolved / "distributions" / filename,
        resolved / "algebra" / filename,
        resolved / "number" / filename,
        resolved / "logic" / filename,
        resolved / "provers" / filename,
    ]
    found = [path for path in direct_candidates if path.exists()]
    if found:
        return found
    key = str(resolved)
    if key not in _EC_FILE_INDEX:
        index: dict[str, list[Path]] = {}
        try:
            paths = (
                list(resolved.glob("*.ec"))
                + list(resolved.glob("*/*.ec"))
                if resolved.is_dir() else []
            )
        except Exception:
            paths = []
        for path in paths:
            index.setdefault(path.name, []).append(path)
        _EC_FILE_INDEX[key] = index
    return list(_EC_FILE_INDEX.get(key, {}).get(filename, []))


def _native_tool_declarations(session_dir: str | Path | None) -> list[dict[str, Any]]:
    """Return declaration facts produced by EasyCrypt-backed lookup tools.

    These artifacts are treated as the highest-authority input for this layer:
    `-where` wraps EC `print`, and `-search-skeleton` wraps EC native AST
    search. Source scans still exist, but only as fallback candidates.
    """
    if session_dir is None:
        return []
    root = Path(session_dir) / "tool_views"
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        tool = str(data.get("tool") or "")
        text = _tool_legacy_text(data)
        if tool == "where":
            decls = _where_tool_declarations(text, path=path)
            fact_source = "ec_native_print"
            source = "ec_native_print.where"
        elif tool == "search-skeleton":
            decls = _search_skeleton_tool_declarations(text, path=path)
            fact_source = "ec_native_search"
            source = "ec_native_search.search_skeleton"
        else:
            continue
        for decl in decls:
            item = _semantic_item(
                lemma=str(decl.get("lemma") or ""),
                declaration_kind=str(decl.get("declaration_kind") or "lemma"),
                declaration=str(decl.get("declaration") or ""),
                source=source,
                source_path=path,
                is_local=bool(decl.get("is_local")),
                fact_source=fact_source,
                authority="ec_native_ground_truth",
                authority_rank=EC_NATIVE_AUTHORITY_RANK,
                ec_ground_truth=True,
                artifact_path=str(path),
                resolved_name=str(decl.get("resolved_name") or ""),
            )
            if item:
                out.append(item)
    return out


def _tool_legacy_text(data: dict[str, Any]) -> str:
    text = str(_dict(data.get("debug")).get("legacy_text") or "")
    if text:
        return text
    for item in _list(_dict(data.get("evidence")).get("raw")):
        if isinstance(item, dict) and item.get("preview"):
            return str(item.get("preview") or "")
    return ""


def _search_skeleton_tool_declarations(
    text: str,
    *,
    path: Path,
) -> list[dict[str, Any]]:
    source = str(text or "")
    if "[SKELETON-HITS]" not in source:
        return []
    start_re = re.compile(
        r"^(?:\(\*\s*(?P<alias>[\w.]+)\s*\*\)\s*\n)?"
        r"(?P<kind>local\s+lemma|lemma|axiom)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_']*)(?![A-Za-z0-9_'])",
        re.MULTILINE,
    )
    matches = list(start_re.finditer(source))
    out: list[dict[str, Any]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        declaration = source[match.start():end].strip()
        declaration = re.sub(r"\n{3,}.*\Z", "", declaration, flags=re.DOTALL).strip()
        alias = str(match.group("alias") or "")
        name = alias or str(match.group("name") or "")
        kind = str(match.group("kind") or "lemma")
        if not name or not declaration:
            continue
        out.append({
            "lemma": name,
            "resolved_name": alias,
            "declaration_kind": kind.replace("local ", ""),
            "declaration": declaration,
            "is_local": kind.startswith("local "),
            "artifact_path": str(path),
        })
    return out[:24]


def _where_tool_declarations(
    text: str,
    *,
    path: Path,
) -> list[dict[str, Any]]:
    source = str(text or "")
    header_re = re.compile(
        r"\[WHERE-HIT(?:-VIA-CLONE|-SOURCE)?\]\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_'.]*)"
        r"(?:\s+->\s+(?P<resolved>[A-Za-z_][A-Za-z0-9_'.]*))?"
        r"\s+\(kind:\s*(?P<kind>[^;)]+)[^\n]*",
    )
    headers = list(header_re.finditer(source))
    if not headers:
        return []
    out: list[dict[str, Any]] = []
    for idx, header in enumerate(headers):
        kind = header.group("kind").strip()
        if kind not in {"lemma", "axiom", "equiv"}:
            continue
        header_name = str(header.group("name") or "")
        resolved_name = str(header.group("resolved") or "")
        name = resolved_name or header_name
        if not name:
            continue
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(source)
        body = source[header.end():end].strip()
        body = re.split(r"\n(?:NOTE:|\[AMBIGUOUS\])", body, maxsplit=1)[0].strip()
        if not body:
            continue
        blocks = _where_declaration_blocks(body) or [body]
        for block in blocks:
            declaration = block.strip()
            if not declaration:
                continue
            block_name = _where_block_name(declaration) or name
            out.append({
                "lemma": block_name,
                "resolved_name": resolved_name,
                "declaration_kind": kind,
                "declaration": declaration,
                "is_local": bool(re.search(
                    r"\blocal\s+(?:lemma|axiom|equiv)\b",
                    declaration,
                )),
                "artifact_path": str(path),
            })
    return out[:24]


def _where_declaration_blocks(body: str) -> list[str]:
    text = str(body or "")
    starts = list(re.finditer(
        r"(?:\(\*\s*[A-Za-z_][A-Za-z0-9_'.]*\s*\*\)\s*)?"
        r"\b(?:local\s+)?(?:lemma|axiom|theorem|equiv)\s+"
        r"[A-Za-z_][A-Za-z0-9_']*\b",
        text,
    ))
    if len(starts) <= 1:
        return [text] if text.strip() else []
    out: list[str] = []
    for idx, match in enumerate(starts):
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        block = text[match.start():end].strip()
        if block:
            out.append(block)
    return out


def _where_block_name(block: str) -> str:
    text = str(block or "")
    alias = re.match(
        r"\s*\(\*\s*([A-Za-z_][A-Za-z0-9_'.]*)\s*\*\)",
        text,
    )
    if alias:
        return alias.group(1)
    match = re.search(
        r"\b(?:local\s+)?(?:lemma|axiom|theorem|equiv)\s+"
        r"([A-Za-z_][A-Za-z0-9_']*)(?![A-Za-z0-9_'])",
        text,
    )
    return match.group(1) if match else ""


def _declarations_from_text(
    text: str,
    *,
    source_path: Path,
    source: str,
    include_local: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    heads = list(re.finditer(
        r"\b(?P<local>local\s+)?(?P<kind>equiv|lemma|theorem|axiom)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_']*)(?![A-Za-z0-9_'])",
        text,
    ))
    ambient_module_params = _ambient_module_parameters_by_declaration(text, heads)
    for idx, match in enumerate(heads):
        if match.group("local") and not include_local:
            continue
        next_start = heads[idx + 1].start() if idx + 1 < len(heads) else len(text)
        proof = re.search(r"\bproof\.", text[match.end():next_start])
        cut = match.end() + proof.start() if proof else next_start
        declaration = re.sub(r"\s+", " ", text[match.start():cut]).strip()
        item = _semantic_item(
            lemma=match.group("name"),
            declaration_kind=match.group("kind"),
            declaration=declaration,
            source=source,
            source_path=source_path,
            is_local=bool(match.group("local")),
        )
        if item:
            params = ambient_module_params.get(match.start(), ())
            if params:
                item["module_parameters"] = list(params)
            out.append(item)
    return out


def _ambient_module_parameters_by_declaration(
    text: str,
    heads: list[re.Match[str]],
) -> dict[int, tuple[str, ...]]:
    """Map declaration offsets to lexically active ``declare module`` names.

    Source-scan declarations omit enclosing section binders from the lemma
    signature.  Preserve those names so endpoint matching can distinguish a
    real section-module instantiation from mere textual similarity.
    """
    head_offsets = {match.start() for match in heads}
    events: list[tuple[int, str, str]] = [
        (offset, "declaration", "") for offset in head_offsets
    ]
    events.extend(
        (match.start(), "section", "")
        for match in re.finditer(
            r"(?<!end )\bsection(?:\s+[A-Za-z_][A-Za-z0-9_']*)?\s*\.", text
        )
    )
    events.extend(
        (match.start(), "end_section", "")
        for match in re.finditer(
            r"\bend\s+section(?:\s+[A-Za-z_][A-Za-z0-9_']*)?\s*\.", text
        )
    )
    events.extend(
        (match.start(), "module", match.group(1))
        for match in re.finditer(
            r"\bdeclare\s+module\s+([A-Za-z_][A-Za-z0-9_']*)\s*<:", text
        )
    )
    stack: list[set[str]] = [set()]
    out: dict[int, tuple[str, ...]] = {}
    priority = {"end_section": 0, "section": 1, "module": 2, "declaration": 3}
    for offset, kind, name in sorted(events, key=lambda item: (item[0], priority[item[1]])):
        if kind == "section":
            stack.append(set())
        elif kind == "end_section":
            if len(stack) > 1:
                stack.pop()
        elif kind == "module":
            stack[-1].add(name)
        else:
            out[offset] = tuple(sorted(set().union(*stack)))
    return out


def _semantic_item(
    *,
    lemma: str,
    declaration_kind: str,
    declaration: str,
    source: str,
    source_path: Path,
    is_local: bool,
    fact_source: str = "source_scan",
    authority: str = "source_scan_fallback",
    authority_rank: int = SOURCE_SCAN_AUTHORITY_RANK,
    ec_ground_truth: bool = False,
    artifact_path: str = "",
    resolved_name: str = "",
) -> dict[str, Any]:
    pr_terms = parse_pr_terms(
        declaration,
        default_memory="&m",
        default_event="res",
        require_endpoint=False,
    )
    compact_terms = [compact_pr_term(term) for term in pr_terms]
    games = _dedupe_strings([
        str(term.get("game_key") or "")
        for term in pr_terms
        if str(term.get("game_key") or "")
    ])
    events = _dedupe_strings([
        str(term.get("event") or "")
        for term in pr_terms
        if str(term.get("event") or "")
    ])
    tags = _semantic_tags(declaration, pr_terms)
    return {
        "lemma": str(lemma or ""),
        "name": str(lemma or ""),
        "declaration_kind": str(declaration_kind or ""),
        "declaration": str(declaration or ""),
        "source": str(source or ""),
        "source_path": str(source_path),
        "is_local": bool(is_local),
        "fact_source": str(fact_source or "source_scan"),
        "authority": str(authority or "source_scan_fallback"),
        "authority_rank": int(authority_rank or 0),
        "ec_ground_truth": bool(ec_ground_truth),
        "artifact_path": str(artifact_path or ""),
        "resolved_name": str(resolved_name or ""),
        "pr_terms": compact_terms,
        "pr_game_keys": games,
        "pr_events": events,
        "semantic_tags": tags,
    }


def _semantic_tags(declaration: str, pr_terms: list[dict[str, Any]]) -> list[str]:
    text = str(declaration or "")
    tags: list[str] = []
    if pr_terms:
        tags.append("pr")
    if re.search(r"\bequiv\s*\[", text) or str(text).lstrip().startswith("equiv "):
        tags.append("equiv")
    if _is_pr_rewrite_declaration(text):
        tags.extend(["pr_equality", "pr_rewrite"])
    if pr_terms and ("<=" in text or "`<=" in text or ">=" in text or "`>=" in text):
        tags.extend(["pr_inequality", "pr_bound"])
    if pr_terms and len(pr_terms) >= 2 and "+" in text and (
        "<=" in text or ">=" in text
    ):
        tags.append("pr_additive_bound")
    if any(_event_is_union(str(term.get("event") or "")) for term in pr_terms):
        tags.append("event_union")
    if any(_event_is_bad_like(str(term.get("event") or "")) for term in pr_terms):
        tags.append("bad_event")
    return _dedupe_strings(tags)


def _is_pr_rewrite_declaration(declaration: str) -> bool:
    text = str(declaration or "")
    statement = _declaration_statement(text) or text
    statement_ir = build_proof_obligation_ir(statement)
    conclusion = statement_ir.conclusion.text or statement
    if "Pr[" not in conclusion or "<=" in conclusion or "`<=" in conclusion or ">=" in conclusion or "`>=" in conclusion:
        return False
    if not re.search(r"(?<![<>=])=(?!=|>)", conclusion):
        return False
    terms = _pr_terms_with_spans(conclusion)
    if len(terms) != 2:
        return False
    before = conclusion[:terms[0][1]].strip()
    between = conclusion[terms[0][2] : terms[1][1]]
    if not re.fullmatch(r"\s*=\s*", between):
        return False
    after = conclusion[terms[1][2] :].strip().rstrip(".").strip()
    wrappers = r"(?:\(|\[)*\s*"
    closing_wrappers = r"(?:\)|\])*\s*"
    return bool(re.fullmatch(wrappers, before)) and (
        not after or bool(re.fullmatch(closing_wrappers, after))
    )


def _score_pr_bound_candidate(
    *,
    goal_keys: list[str],
    goal_events: list[str],
    goal_shape: str,
    item: dict[str, Any],
) -> int:
    score = 0
    item_keys = [
        str(key) for key in _list(item.get("pr_game_keys")) if str(key)
    ]
    for goal in goal_keys:
        for key in item_keys:
            score = max(score, game_similarity(goal, key))
    item_events = [
        str(event) for event in _list(item.get("pr_events")) if str(event)
    ]
    score += min(_event_overlap_score(goal_events, item_events), 4)
    tags = {str(tag) for tag in _list(item.get("semantic_tags"))}
    if goal_shape == "additive" and "pr_additive_bound" in tags:
        score += 4
    if goal_shape == "event_union" and "event_union" in tags:
        score += 4
    if "bad_event" in tags and any(_event_is_bad_like(event) for event in goal_events):
        score += 2
    if "pr_bound" in tags:
        score += 1
    return score


def _event_overlap_score(goal_events: list[str], item_events: list[str]) -> int:
    best = 0
    for goal in goal_events:
        goal_tokens = set(_event_tokens(goal))
        if not goal_tokens:
            continue
        for event in item_events:
            event_tokens = set(_event_tokens(event))
            if not event_tokens:
                continue
            shared = len(goal_tokens & event_tokens)
            if goal == event:
                best = max(best, 6)
            elif shared >= 2:
                best = max(best, 3)
            elif shared == 1:
                best = max(best, 1)
    return best


def _event_tokens(event: str) -> list[str]:
    stop = {"res", "true", "false", "glob", "forall", "exists"}
    return _dedupe_strings([
        token for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", str(event or ""))
        if token not in stop
    ])


def _pr_bound_goal_shape(goal_text: str) -> str:
    text = str(goal_text or "")
    if "+" in text and len(parse_pr_terms(text, require_endpoint=False)) >= 2:
        return "additive"
    if any(
        _event_is_union(str(term.get("event") or ""))
        for term in parse_pr_terms(text, default_memory="&m", default_event="res", require_endpoint=False)
    ):
        return "event_union"
    return "inequality"


def _event_is_union(event: str) -> bool:
    text = str(event or "")
    return r"\/" in text or " predU " in f" {text} " or "||" in text


def _event_is_bad_like(event: str) -> bool:
    return bool(re.search(r"(bad|fail|merr|win)", str(event or ""), flags=re.IGNORECASE))


def _candidate_reason(item: dict[str, Any], *, family: str) -> str:
    if bool(item.get("ec_ground_truth")):
        return (
            f"EasyCrypt native lookup/search produced this {family} declaration; "
            "Shannon only scored its game/event overlap. Inspect with `-where` "
            "for the exact application form before committing a tactic."
        )
    return (
        f"Source-scan fallback found a {family} candidate with overlapping "
        "game or event structure. Treat the name as unconfirmed until `-where` "
        "resolves it in the current EasyCrypt environment."
    )


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    ranked = sorted(
        items,
        key=lambda item: (
            -int(item.get("authority_rank") or 0),
            str(item.get("source") or ""),
            str(item.get("lemma") or ""),
        ),
    )
    best_rank_by_unqualified_name: dict[str, int] = {}
    for item in ranked:
        lemma = str(item.get("lemma") or "")
        if not lemma:
            continue
        rank = int(item.get("authority_rank") or 0)
        if "." not in lemma:
            best_rank = best_rank_by_unqualified_name.setdefault(lemma, rank)
            if rank < best_rank:
                continue
        games = [
            str(key) for key in _list(item.get("pr_game_keys"))
            if str(key)
        ]
        key = (
            lemma,
            "|".join(games),
            str(item.get("declaration_kind") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


__all__ = [
    "LEMMA_INDEX_KIND",
    "LEMMA_INDEX_SCHEMA_VERSION",
    "build_semantic_lemma_index",
    "ec_files_named",
    "game_atoms",
    "game_root",
    "game_similarity",
    "goal_pr_game_keys",
    "high_precision_pr_bound_routes",
    "import_search_roots",
    "imported_theory_files",
    "pr_endpoint_pair_score",
    "require_theory_names",
    "score_pr_rewrite_candidate",
    "semantic_distribution_certificates",
    "semantic_one_sided_losslessness_candidates",
    "semantic_pr_bound_candidates",
    "semantic_pr_rewrite_candidates",
    "semantic_pr_rewrite_declarations",
    "session_context_files",
    "session_target_lemma",
    "source_declarations_by_name",
]
