"""Sampling/coupling obligation frontend for EasyCrypt procedure goals."""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_stripped_strings as _dedupe_strings,
)
from core.easycrypt.analysis.ec_pr_obligations import goal_body
from core.easycrypt.analysis.ec_sampling_statements import (
    sample_distribution_leaf as _sample_distribution_leaf,
    sample_statement_distribution as _sample_statement_distribution,
    sample_statement_var as _sample_statement_var,
)


SAMPLING_OBLIGATION_SCHEMA_VERSION = 1
SAMPLING_OBLIGATION_KIND = "easycrypt_sampling_obligation_frontend"


def build_sampling_obligation_frontend(
    samples: list[dict[str, Any]],
    *,
    parsed: dict[str, Any],
    goal_text: str,
) -> dict[str, Any]:
    """Classify visible sampling as typed local coupling obligations."""
    sample_items = [canonical_sample_item(item) for item in samples]
    sample_items = [item for item in sample_items if item.get("var")]
    if not sample_items:
        return {"available": False, "reason": "no_visible_samples"}
    body = sampling_obligation_body(parsed, goal_text)
    left = [item for item in sample_items if item.get("side") == "left"]
    right = [item for item in sample_items if item.get("side") == "right"]
    obligations: list[dict[str, Any]] = []

    paired_left: set[int] = set()
    paired_right: set[int] = set()
    for left_idx, l_item in enumerate(left):
        match_idx = same_distribution_sample_match_index(
            l_item,
            right,
            paired_right,
        )
        if match_idx is None:
            continue
        paired_left.add(left_idx)
        paired_right.add(match_idx)
        obligations.append(sampling_obligation_for_pair(
            l_item,
            right[match_idx],
            body,
        ))

    for left_idx, l_item in enumerate(left):
        if left_idx in paired_left:
            continue
        match_idx = first_unused_sample_index(right, paired_right)
        r_item = right[match_idx] if match_idx is not None else {}
        if match_idx is not None:
            paired_right.add(match_idx)
        obligations.append(sampling_obligation_for_pair(l_item, r_item, body))

    for idx, r_item in enumerate(right):
        if idx in paired_right:
            continue
        obligations.append(sampling_obligation_for_pair({}, r_item, body))

    families = dedupe_sampling_families(obligations)
    return {
        "available": bool(obligations),
        "obligations": obligations[:4],
        "candidate_families": families,
        "sample_count": len(sample_items),
        "source": "program_ir.samples+post_relation_scan",
    }


def canonical_sample_item(sample: dict[str, Any]) -> dict[str, Any]:
    sample = _dict(sample)
    text = str(sample.get("statement") or sample.get("text") or "").strip()
    var = sample_var(sample, text)
    distribution = sample_distribution(sample, text)
    return {
        "side": str(sample.get("side") or ""),
        "side_index": int(sample.get("side_index") or 0),
        "statement_order": int(sample.get("statement_order") or 0),
        "statement_path": str(sample.get("statement_path") or ""),
        "statement": text,
        "var": var,
        "distribution": distribution,
        "distribution_leaf": distribution_leaf(distribution),
    }


def sample_var(sample: dict[str, Any], text: str) -> str:
    return _sample_statement_var(sample, text)


def sample_distribution(sample: dict[str, Any], text: str) -> str:
    return _sample_statement_distribution(sample, text)


def distribution_leaf(distribution: str) -> str:
    return _sample_distribution_leaf(distribution)


def sampling_obligation_body(parsed: dict[str, Any], goal_text: str) -> str:
    parts = [
        str(_dict(parsed).get("pre") or ""),
        str(_dict(parsed).get("post") or ""),
        goal_body(goal_text),
    ]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def same_distribution_sample_match_index(
    left_item: dict[str, Any],
    right: list[dict[str, Any]],
    used: set[int],
) -> int | None:
    left_dist = str(_dict(left_item).get("distribution_leaf") or "")
    if not left_dist:
        return None
    for idx, item in enumerate(right):
        if idx in used:
            continue
        if left_dist == str(_dict(item).get("distribution_leaf") or ""):
            return idx
    return None


def first_unused_sample_index(
    samples: list[dict[str, Any]],
    used: set[int],
) -> int | None:
    for idx, _item in enumerate(samples):
        if idx not in used:
            return idx
    return None


def sampling_obligation_for_pair(
    left_item: dict[str, Any],
    right_item: dict[str, Any],
    body: str,
) -> dict[str, Any]:
    lvar = str(_dict(left_item).get("var") or "")
    rvar = str(_dict(right_item).get("var") or "")
    ldist = str(_dict(left_item).get("distribution_leaf") or "")
    rdist = str(_dict(right_item).get("distribution_leaf") or "")
    same_distribution = bool(ldist and rdist and ldist == rdist)
    relation = sample_relation_motif(lvar, rvar, body)
    families = coupling_families_for_relation(
        relation,
        same_distribution=same_distribution,
        has_left=bool(left_item),
        has_right=bool(right_item),
    )
    return {
        "kind": "sampling_coupling_obligation",
        "left_sample": left_item,
        "right_sample": right_item,
        "same_distribution": same_distribution,
        "relation_motif": relation,
        "candidate_families": families,
        "required_evidence": sampling_required_evidence(
            left_item,
            right_item,
            families,
        ),
        "epistemic_status": "classification_only_not_verified_tactic",
    }


def sample_relation_motif(lvar: str, rvar: str, body: str) -> dict[str, Any]:
    snippets = sample_relation_snippets([lvar, rvar], body)
    text = " ".join(snippets) if snippets else body
    has_left = mentions_sided_var(text, lvar, "1") if lvar else False
    has_right = mentions_sided_var(text, rvar, "2") if rvar else False
    operators = sample_relation_operators(text)
    equality_like = bool(
        lvar
        and rvar
        and re.search(
            rf"{re.escape(lvar)}\s*\{{1\}}\s*=\s*{re.escape(rvar)}\s*\{{2\}}"
            rf"|{re.escape(rvar)}\s*\{{2\}}\s*=\s*{re.escape(lvar)}\s*\{{1\}}",
            text,
        )
    )
    motif = "unknown"
    if equality_like and not operators:
        motif = "identity"
    elif "boolean_negation" in operators or "conditional" in operators:
        motif = "boolean_or_conditional_flip"
    elif operators & {"additive", "xor", "multiplicative", "subtractive"}:
        motif = "translation_or_affine"
    elif has_left and has_right:
        motif = "relational"
    elif has_left or has_right:
        motif = "one_sided"
    return {
        "motif": motif,
        "mentions_left_sample": has_left,
        "mentions_right_sample": has_right,
        "operators": sorted(operators),
        "offset_candidates": (
            translation_offset_candidates(lvar, rvar, text)
            if motif == "translation_or_affine" else
            []
        ),
        "snippets": snippets[:3],
    }


def translation_offset_candidates(
    lvar: str,
    rvar: str,
    text: str,
) -> list[dict[str, Any]]:
    """Extract affine/translation offsets from a local post relation.

    The extractor is intentionally syntactic and project-neutral.  It looks for
    equations of the form ``right = left +/- offset`` or ``left = right +/-
    offset`` around the sampled variables and turns them into candidate rnd
    maps.  The returned tactics are still strategy hints, not verified proof
    steps.
    """
    if not lvar or not rvar or not text:
        return []
    left = rf"{re.escape(lvar)}\s*\{{1\}}"
    right = rf"{re.escape(rvar)}\s*\{{2\}}"
    candidates: list[dict[str, Any]] = []
    patterns = [
        (
            re.compile(
                rf"{right}\s*=\s*{left}\s*(?P<op>\+|-|\+\^)\s*(?P<offset>{_OFFSET_RE})"
            ),
            "right_is_left_plus_offset",
        ),
        (
            re.compile(
                rf"{left}\s*=\s*{right}\s*(?P<op>\+|-|\+\^)\s*(?P<offset>{_OFFSET_RE})"
            ),
            "left_is_right_plus_offset",
        ),
    ]
    for pattern, orientation in patterns:
        for match in pattern.finditer(text):
            offset = _clean_offset(match.group("offset"))
            op = str(match.group("op") or "+")
            if not offset or _offset_mentions_sample(offset, lvar, rvar):
                continue
            forward, backward = _affine_maps_for_orientation(
                orientation,
                op,
                offset,
            )
            candidates.append({
                "offset": offset,
                "operator": op,
                "orientation": orientation,
                "forward_map": forward,
                "inverse_map": backward,
                "tactic_template": f"rnd ({forward}) ({backward}).",
                "confidence": "medium",
                "reason": (
                    "postcondition relates the paired samples by a visible "
                    f"{op} offset"
                ),
            })
    return _dedupe_offset_candidates(candidates)


def sample_relation_snippets(vars_: list[str], body: str) -> list[str]:
    out: list[str] = []
    if not body:
        return out
    for var in [item for item in vars_ if item]:
        pattern = re.compile(rf".{{0,90}}{re.escape(var)}\s*\{{[12]\}}.{{0,90}}")
        for match in pattern.finditer(body):
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            if snippet:
                out.append(snippet)
            if len(out) >= 6:
                return _dedupe_strings(out)
    return _dedupe_strings(out)


def mentions_sided_var(text: str, var: str, side: str) -> bool:
    if not var:
        return False
    return bool(re.search(rf"\b{re.escape(var)}\s*\{{{side}\}}", text))


def sample_relation_operators(text: str) -> set[str]:
    ops: set[str] = set()
    if re.search(r"\+[\^]?", text):
        ops.add("xor" if "+^" in text else "additive")
    if "-" in text:
        ops.add("subtractive")
    if "*" in text:
        ops.add("multiplicative")
    if re.search(r"\bif\b.+\bthen\b.+\belse\b", text):
        ops.add("conditional")
    if re.search(r"!\s*[A-Za-z_]", text):
        ops.add("boolean_negation")
    return ops


def coupling_families_for_relation(
    relation: dict[str, Any],
    *,
    same_distribution: bool,
    has_left: bool,
    has_right: bool,
) -> list[dict[str, Any]]:
    motif = str(_dict(relation).get("motif") or "")
    families: list[dict[str, Any]] = []
    if has_left and has_right and same_distribution:
        families.append({
            "family": "identity",
            "tactic_template": "rnd.",
            "when": "sampled values are related directly or the postcondition preserves equality",
        })
    if motif == "translation_or_affine":
        offsets = [
            _dict(item) for item in _list(relation.get("offset_candidates"))
            if isinstance(item, dict)
        ]
        tactic_template = (
            str(offsets[0].get("tactic_template") or "")
            if offsets else
            ""
        )
        families.append({
            "family": "translation_or_affine",
            "tactic_template": (
                tactic_template
                or "rnd (fun x => x + <offset>) (fun x => x - <offset>)."
            ),
            "when": "post relates sampled values through a type-level additive/xor/affine mask",
            "offset_candidates": offsets[:4],
        })
    if motif == "boolean_or_conditional_flip":
        families.append({
            "family": "boolean_or_conditional_flip",
            "tactic_template": "rnd (fun b => if <condition> then b else !b).",
            "when": "post relates boolean samples by a conditional negation",
        })
    if has_left and has_right and not same_distribution:
        families.append({
            "family": "custom_bijection_or_distribution_bridge",
            "tactic_template": "rnd (<forward map>) (<inverse map>).",
            "when": "visible samples use different distribution expressions",
        })
    if has_left != has_right:
        families.append({
            "family": "one_sided_lossless_or_predicate",
            "tactic_template": "rnd{1}. / rnd{2}. / rnd predT.",
            "when": "only one side has a visible sampling statement",
        })
    if not families:
        families.append({
            "family": "inspect_sample_relation",
            "tactic_template": "-agent-view / -goal-info; inspect post relation before rnd.",
            "when": "sample relation is not syntactically obvious",
        })
    return families


def sampling_required_evidence(
    left_item: dict[str, Any],
    right_item: dict[str, Any],
    families: list[dict[str, Any]],
) -> dict[str, Any]:
    family_names = {str(_dict(item).get("family") or "") for item in families}
    algebra = []
    if "translation_or_affine" in family_names:
        algebra.extend([
            "forward/backward cancellation for the chosen offset",
            "distribution is full+uniform or funiform under the chosen map",
        ])
    if "boolean_or_conditional_flip" in family_names:
        algebra.extend([
            "boolean negation/conditional map is involutive",
            "sample distribution is uniform/full on booleans",
        ])
    if "identity" in family_names:
        algebra.append("same distribution or identity coupling side conditions")
    return {
        "algebra_obligations": algebra,
        "strategy_boundary": (
            "ProofIR classifies the local sampling problem; the prover chooses "
            "which coupling family to instantiate; a manager commit reports "
            "EasyCrypt's verdict."
        ),
    }


_OFFSET_RE = r".+?(?=\s*(?:/\\|&&|==>|=>|\]|\b(?:pre|post)\s*=|$))"


def _affine_maps_for_orientation(
    orientation: str,
    op: str,
    offset: str,
) -> tuple[str, str]:
    if op == "+^":
        # XOR-style addition is usually self-inverse, but projects may still
        # require a library lemma; keep the map explicit for the prover.
        forward_plus = f"fun x => x +^ {offset}"
        backward_plus = f"fun x => x +^ {offset}"
    elif op == "-":
        forward_plus = f"fun x => x - {offset}"
        backward_plus = f"fun x => x + {offset}"
    else:
        forward_plus = f"fun x => x + {offset}"
        backward_plus = f"fun x => x - {offset}"
    if orientation == "right_is_left_plus_offset":
        return forward_plus, backward_plus
    return backward_plus, forward_plus


def _clean_offset(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.rstrip(" .;")
    return text


def _offset_mentions_sample(offset: str, lvar: str, rvar: str) -> bool:
    return bool(
        re.search(rf"\b{re.escape(lvar)}\s*\{{1\}}", offset)
        or re.search(rf"\b{re.escape(rvar)}\s*\{{2\}}", offset)
    )


def _dedupe_offset_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (
            str(candidate.get("offset") or ""),
            str(candidate.get("operator") or ""),
            str(candidate.get("orientation") or ""),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def dedupe_sampling_families(
    obligations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for obligation in obligations:
        for family in _list(_dict(obligation).get("candidate_families")):
            item = _dict(family)
            name = str(item.get("family") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(item)
    return out


__all__ = [
    "SAMPLING_OBLIGATION_KIND",
    "SAMPLING_OBLIGATION_SCHEMA_VERSION",
    "build_sampling_obligation_frontend",
    "canonical_sample_item",
    "coupling_families_for_relation",
    "dedupe_sampling_families",
    "distribution_leaf",
    "first_unused_sample_index",
    "mentions_sided_var",
    "same_distribution_sample_match_index",
    "sample_distribution",
    "sample_relation_motif",
    "sample_relation_operators",
    "sample_relation_snippets",
    "sample_var",
    "sampling_obligation_body",
    "sampling_obligation_for_pair",
    "sampling_required_evidence",
    "translation_offset_candidates",
]
