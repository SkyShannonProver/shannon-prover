"""Feature-neutral proof-judgment and top-level relation syntax."""

from __future__ import annotations

import re

from core.easycrypt.proof_state_compiler.contracts.proof_ir import (
    FormulaRelation,
    ProofJudgment,
)


def normalize_formula(value: str) -> str:
    text = " ".join(value.strip().split())
    while _has_balanced_outer_parentheses(text):
        text = " ".join(text[1:-1].strip().split())
    return text


def _has_balanced_outer_parentheses(value: str) -> bool:
    if not (value.startswith("(") and value.endswith(")")):
        return False
    depth = 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(value) - 1:
                return False
            if depth < 0:
                return False
    return depth == 0


def parse_top_level_relation(value: str) -> FormulaRelation | None:
    text = normalize_formula(value)
    depth = 0
    index = 0
    operators = ("<=>", "<=", ">=", "=", "<", ">")
    non_relation_tokens = ("==>", "=>", "<:", "<>")
    while index < len(text):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            ignored = next((
                token
                for token in non_relation_tokens
                if text.startswith(token, index)
            ), "")
            if ignored:
                index += len(ignored)
                continue
            for operator in operators:
                if text.startswith(operator, index):
                    left = normalize_formula(text[:index])
                    right = normalize_formula(text[index + len(operator):])
                    if left and right:
                        return FormulaRelation(operator, left, right)
        index += 1
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
    opening = value.find("[")
    if opening < 0:
        return ""
    depth = 0
    for index in range(opening + 1, len(value)):
        char = value[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif char == ":" and depth == 0:
            return normalize_formula(value[opening + 1:index])
    return ""
