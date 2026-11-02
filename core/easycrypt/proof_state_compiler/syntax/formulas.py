"""Feature-neutral proof-judgment and top-level relation syntax."""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.contracts.proof_ir import (
    FormulaRelation,
    ProofJudgment,
)
from core.easycrypt.proof_state_compiler.delimiters import (
    find_top_level,
    matching_close,
    parenthesized,
    top_level_indices,
)


def normalize_formula(value: str) -> str:
    text = " ".join(value.strip().split())
    while parenthesized(text):
        text = " ".join(text[1:-1].strip().split())
    return text


def parse_top_level_relation(value: str) -> FormulaRelation | None:
    text = normalize_formula(value)
    operators = ("<=>", "<=", ">=", "=", "<", ">")
    non_relation_tokens = ("==>", "=>", "<:", "<>")
    resume = 0
    for index in top_level_indices(text):
        if index < resume:
            continue
        ignored = next((
            token
            for token in non_relation_tokens
            if text.startswith(token, index)
        ), "")
        if ignored:
            resume = index + len(ignored)
            continue
        for operator in operators:
            if text.startswith(operator, index):
                left = normalize_formula(text[:index])
                right = normalize_formula(text[index + len(operator):])
                if left and right:
                    return FormulaRelation(operator, left, right)
    return None


def parse_proof_judgment(value: str) -> ProofJudgment:
    text = normalize_formula(value.rstrip("."))
    compact = text.replace(" ", "")
    if compact.startswith("equiv["):
        return ProofJudgment(
            kind="equiv",
            text=text,
            subject=_bracket_subject(text),
            relation=parse_top_level_relation(text),
        )
    if compact.startswith("phoare["):
        return ProofJudgment(
            kind="phoare",
            text=text,
            subject=_bracket_subject(text),
            relation=parse_top_level_relation(text),
        )
    if compact.startswith("hoare["):
        return ProofJudgment(
            kind="hoare",
            text=text,
            subject=_bracket_subject(text),
            relation=parse_top_level_relation(text),
        )
    lossless = re.match(r"^islossless\s+(.+)$", text)
    if lossless:
        procedure = normalize_formula(lossless.group(1))
        return ProofJudgment(
            kind="lossless",
            text=text,
            subject=procedure,
            procedure=procedure,
        )
    if text.startswith("Pr["):
        return ProofJudgment(
            kind="probability",
            text=text,
            relation=parse_top_level_relation(text),
        )
    return ProofJudgment(
        kind="formula",
        text=text,
        relation=parse_top_level_relation(text),
    )


def _bracket_subject(value: str) -> str:
    """The text before the first top-level ``:`` inside the first ``[...]``."""

    opening = value.find("[")
    if opening < 0:
        return ""
    closing = matching_close(value, opening)
    scope = value if closing < 0 else value[:closing]
    colon = find_top_level(scope, ":", start=opening + 1)
    return "" if colon < 0 else normalize_formula(value[opening + 1:colon])
