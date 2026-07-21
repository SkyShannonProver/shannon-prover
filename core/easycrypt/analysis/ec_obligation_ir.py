"""Canonical outer structure for an EasyCrypt proof obligation.

This is deliberately a small frontend, not a second EasyCrypt parser.  It
recognises only outer binders and logical relations needed by downstream
mechanical analysis.  Native goal structure may replace the fallback later;
pretty-printed goal text is always labelled as fallback authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


OBLIGATION_IR_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ObligationPart:
    kind: str
    text: str
    relation: str = ""

    def to_dict(self) -> dict[str, str]:
        out = {"kind": self.kind, "text": self.text}
        if self.relation:
            out["relation"] = self.relation
        return out


@dataclass(frozen=True)
class ProofObligationIR:
    binders: tuple[ObligationPart, ...] = ()
    premises: tuple[ObligationPart, ...] = ()
    conclusion: ObligationPart = field(
        default_factory=lambda: ObligationPart("unknown", "")
    )
    conclusion_parts: tuple[ObligationPart, ...] = ()
    authority: str = "pretty_text_fallback"
    source_refs: tuple[str, ...] = ("current_goal.lines",)
    schema_version: int = OBLIGATION_IR_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "authority": self.authority,
            "source_refs": list(self.source_refs),
            "binders": [part.to_dict() for part in self.binders],
            "premises": [part.to_dict() for part in self.premises],
            "conclusion": self.conclusion.to_dict(),
            "conclusion_parts": [part.to_dict() for part in self.conclusion_parts],
        }


def build_proof_obligation_ir(goal_text: str) -> ProofObligationIR:
    """Parse only the outer logical structure of a pretty-printed goal."""
    body = goal_conclusion_text(goal_text)
    if not body:
        return ProofObligationIR()

    binders: list[ObligationPart] = []
    premises: list[ObligationPart] = []
    remainder = body.strip()
    while remainder:
        binder = _outer_binder(remainder)
        if binder is not None:
            binder_kind, binder_text, remainder = binder
            binders.append(ObligationPart(binder_kind, _compact(binder_text)))
            continue
        arrows = list(_top_level_token_positions(remainder, ("=>",)))
        if not arrows:
            break
        idx, token = arrows[0]
        premise_text = remainder[:idx].strip()
        if not premise_text:
            break
        premises.append(classify_obligation_part(premise_text, role="premise"))
        remainder = remainder[idx + len(token):].strip()

    conclusion_text = remainder
    conclusion = classify_obligation_part(conclusion_text, role="conclusion")

    conjuncts = split_top_level_token(conclusion_text, "/\\")
    conclusion_parts = (
        tuple(classify_obligation_part(text, role="obligation") for text in conjuncts)
        if len(conjuncts) > 1 else ()
    )
    return ProofObligationIR(
        binders=tuple(binders),
        premises=tuple(premises),
        conclusion=conclusion,
        conclusion_parts=conclusion_parts,
    )


def one_sided_program_obligation(
    goal_text: str,
    *,
    goal_type: str = "",
) -> dict[str, Any]:
    """Classify the narrow program-obligation shapes shared by surface users.

    The current contract recognizes only the canonical EasyCrypt
    losslessness encoding: a single-program ``phoare`` goal with equality
    bound ``1%r`` and literal ``true`` pre/postconditions.  It reports the
    obligation class; it does not choose call certificates, loop invariants,
    variants, or an inlining strategy.
    """
    kind = str(goal_type or "").strip().lower()
    text = str(goal_text or "")
    if kind != "phoare":
        return {}
    if not re.search(r"(?m)^\s*Bound\s*:\s*\[=\]\s*1%r\s*$", text):
        return {}
    if not re.search(r"(?m)^\s*pre\s*=\s*true\s*$", text):
        return {}
    if not re.search(r"(?m)^\s*post\s*=\s*true\s*$", text):
        return {}
    return {
        "kind": "procedure_losslessness",
        "goal_type": "phoare",
        "bound_relation": "=",
        "bound_value": "1%r",
        "precondition": "true",
        "postcondition": "true",
        "authority": "pretty_text_fallback",
        "source_refs": ["current_goal.lines", "proof_status.goal_type"],
        "limitations": [
            "classifies the current obligation only",
            "does not choose certificates, invariants, variants, or an inline plan",
        ],
    }


def goal_conclusion_text(goal_text: str) -> str:
    """Return text below the final EasyCrypt turnstile, without the prompt."""
    lines = str(goal_text or "").splitlines()
    separator = -1
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped and set(stripped) == {"-"} and len(stripped) >= 3:
            separator = idx
    body = "\n".join(lines[separator + 1 :]) if separator >= 0 else str(goal_text or "")
    return re.sub(r"\[\s*\d+\s*\|[^\]]*\]>", " ", body).strip()


def classify_obligation_part(text: str, *, role: str) -> ObligationPart:
    compact = _compact(text)
    if not compact:
        return ObligationPart("unknown", "")
    classified = _strip_enclosing_parentheses(compact)
    lowered = classified.lower()
    if re.match(r"^(forall|exists)\b", lowered):
        return ObligationPart("quantified", compact)
    if lowered.startswith("let "):
        return ObligationPart("let_expression", compact)
    if lowered.startswith("if "):
        return ObligationPart("conditional", compact)

    logical = first_top_level_logical_connective(classified)
    if logical == "/\\":
        return ObligationPart("conjunction", compact)
    if logical == "\\/":
        return ObligationPart("disjunction", compact)
    if logical == "=>":
        return ObligationPart("implication", compact)

    relation = first_top_level_relation(classified)
    if relation == "<=>":
        kind = "equivalence"
    elif relation == "=":
        kind = "iter_equality" if re.search(r"\biter\b", classified) else "equality"
    elif relation in {"<=", "<", ">=", ">"}:
        if "size (drop" in classified and relation == "<":
            kind = "size_drop_inequality"
        else:
            kind = "order"
    elif relation in {"\\in", "\\notin"}:
        kind = "membership"
    elif classified in {"true", "false"}:
        kind = "trivial"
    elif "<> []" in classified:
        kind = "nonempty_list"
    else:
        kind = "proposition" if role != "conclusion" else "unknown"
    return ObligationPart(kind, compact, relation)


def split_top_level_token(text: str, token: str) -> list[str]:
    """Split on an exact outer token, respecting EC multi-character operators."""
    source = str(text or "")
    positions = list(_top_level_token_positions(source, (token,)))
    if not positions:
        return [source]
    out: list[str] = []
    start = 0
    for idx, matched in positions:
        out.append(source[start:idx])
        start = idx + len(matched)
    out.append(source[start:])
    return out


def first_top_level_relation(text: str) -> str:
    if first_top_level_logical_connective(text):
        return ""
    relations = ("<=>", "<=", ">=", "<>", "=", "<", ">", "\\notin", "\\in")
    for _idx, token in _top_level_token_positions(str(text or ""), relations):
        return token
    return ""


def first_top_level_logical_connective(text: str) -> str:
    """Return the first outer logical connective, if one is visible."""
    source = _strip_enclosing_parentheses(_compact(text))
    matches = list(_top_level_token_positions(source, ("=>", "/\\", "\\/")))
    return matches[0][1] if matches else ""


def top_level_relation_parts(text: str) -> tuple[str, str, str] | None:
    """Return ``(left, relation, right)`` for one outer relation."""
    relations = ("<=>", "<=", ">=", "<>", "=", "<", ">", "\\notin", "\\in")
    source = _strip_enclosing_parentheses(_compact(text))
    if first_top_level_logical_connective(source):
        return None
    matches = list(_top_level_token_positions(source, relations))
    if len(matches) != 1:
        return None
    idx, relation = matches[0]
    left = source[:idx].strip()
    right = source[idx + len(relation):].strip()
    if not left or not right:
        return None
    return left, relation, right


def named_local_formulas(goal_text: str) -> list[dict[str, str]]:
    """Extract named local formulas without requiring one outer relation.

    Chained bounds such as ``0 <= i < size xs`` and their negations are useful
    mechanical branch evidence, but they intentionally do not parse as one
    ``top_level_relation_parts`` relation.  Keep the complete compact formula
    here; type declarations and memory bindings are still omitted.
    """
    lines = str(goal_text or "").splitlines()
    separator = -1
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped and set(stripped) == {"-"} and len(stripped) >= 3:
            separator = idx
    if separator < 0:
        return []

    entries: list[tuple[str, str]] = []
    name = ""
    body: list[str] = []
    for line in lines[:separator]:
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*(.*)$", line)
        if match:
            if name and body:
                entries.append((name, " ".join(body)))
            name = match.group(1)
            body = [match.group(2).strip()]
        elif name and line.startswith((" ", "\t")) and line.strip():
            body.append(line.strip())
        elif name and line.strip():
            entries.append((name, " ".join(body)))
            name = ""
            body = []
    if name and body:
        entries.append((name, " ".join(body)))

    out: list[dict[str, str]] = []
    for hypothesis, formula in entries:
        compact = _compact(formula)
        if not compact:
            continue
        out.append({"hypothesis": hypothesis, "formula": compact})
    return out


def named_local_hypotheses(goal_text: str) -> list[dict[str, str]]:
    """Extract relation-bearing named hypotheses from the local goal context.

    Type declarations and memory bindings are deliberately omitted.  The
    result is structural evidence only; it does not rank or select a premise.
    """
    out: list[dict[str, str]] = []
    for item in named_local_formulas(goal_text):
        hypothesis = item["hypothesis"]
        formula = item["formula"]
        relation_parts = top_level_relation_parts(formula)
        if relation_parts is None:
            continue
        left, relation, right = relation_parts
        out.append({
            "hypothesis": hypothesis,
            "formula": formula,
            "outer_relation": relation,
            "left": left,
            "right": right,
        })
    return out


def local_order_chains(goal_text: str) -> list[dict[str, Any]]:
    """Find exact two-premise order chains ending at the current conclusion."""
    conclusion = top_level_relation_parts(goal_conclusion_text(goal_text))
    if conclusion is None:
        return []
    goal_left, goal_relation, goal_right = conclusion
    if goal_relation not in {"<", "<=", ">", ">="}:
        return []
    hypotheses = [
        item for item in named_local_hypotheses(goal_text)
        if item["outer_relation"] in {"<", "<=", ">", ">="}
    ]
    out: list[dict[str, Any]] = []
    for first in hypotheses:
        for second in hypotheses:
            if first is second:
                continue
            if not _order_relations_compose(
                first["outer_relation"], second["outer_relation"], goal_relation
            ):
                continue
            if (
                _normalise_term(first["left"]) == _normalise_term(goal_left)
                and _normalise_term(first["right"]) == _normalise_term(second["left"])
                and _normalise_term(second["right"]) == _normalise_term(goal_right)
            ):
                out.append({
                    "premises": [first["hypothesis"], second["hypothesis"]],
                    "chain": [first["left"], first["right"], second["right"]],
                    "relations": [
                        first["outer_relation"], second["outer_relation"], goal_relation,
                    ],
                    "conclusion": goal_conclusion_text(goal_text),
                })
    return out


def obligation_is_trivial(goal_text: str) -> bool:
    """Whether the outer conclusion is mechanically reflexive or ``true``."""
    conclusion = build_proof_obligation_ir(goal_text).conclusion
    text = _strip_enclosing_parentheses(_compact(conclusion.text))
    if text.lower() == "true":
        return True
    parts = top_level_relation_parts(text)
    if parts is None:
        return False
    left, relation, right = parts
    return relation in {"=", "<=>", "<=", ">="} and (
        _normalise_term(left) == _normalise_term(right)
    )


def _order_relations_compose(first: str, second: str, conclusion: str) -> bool:
    ascending = {"<", "<="}
    descending = {">", ">="}
    if {first, second, conclusion} <= ascending:
        return conclusion == "<=" or "<" in {first, second}
    if {first, second, conclusion} <= descending:
        return conclusion == ">=" or ">" in {first, second}
    return False


def _normalise_term(text: str) -> str:
    return re.sub(r"\s+", "", _strip_enclosing_parentheses(str(text or "")))


def _outer_binder(text: str) -> tuple[str, str, str] | None:
    match = re.match(r"\s*(forall|exists)\b", text)
    if not match:
        return None
    comma = _first_top_level_char(text, ",")
    if comma < 0:
        return None
    keyword = match.group(1)
    return (f"{keyword}_binder", text[:comma].strip(), text[comma + 1 :].strip())


def _first_top_level_char(text: str, wanted: str) -> int:
    depth = 0
    for idx, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif depth == 0 and char == wanted:
            return idx
    return -1


def _top_level_token_positions(
    text: str,
    tokens: Iterable[str],
) -> Iterable[tuple[int, str]]:
    ordered = tuple(sorted(set(tokens), key=len, reverse=True))
    depth = 0
    idx = 0
    while idx < len(text):
        char = text[idx]
        if char in "([{":
            depth += 1
            idx += 1
            continue
        if char in ")]}" and depth:
            depth -= 1
            idx += 1
            continue
        if depth == 0:
            matched = next((token for token in ordered if text.startswith(token, idx)), "")
            if matched and _token_is_exact(text, idx, matched):
                yield idx, matched
                idx += len(matched)
                continue
        idx += 1


def _token_is_exact(text: str, idx: int, token: str) -> bool:
    if token == "=>":
        return (
            (idx == 0 or text[idx - 1] not in "<=>")
            and (idx + 2 >= len(text) or text[idx + 2] != ">")
        )
    if token == "=":
        before = text[idx - 1] if idx else ""
        after = text[idx + 1] if idx + 1 < len(text) else ""
        return before not in "<=>" and after not in "=>"
    if token in {"<", ">"}:
        before = text[idx - 1] if idx else ""
        after = text[idx + 1] if idx + 1 < len(text) else ""
        return before not in "<=>" and after not in "=>-"
    if token in {"\\in", "\\notin"}:
        before = text[idx - 1] if idx else " "
        after_idx = idx + len(token)
        after = text[after_idx] if after_idx < len(text) else " "
        return not (before.isalnum() or before in "_'") and not (
            after.isalnum() or after in "_'"
        )
    return True


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _strip_enclosing_parentheses(text: str) -> str:
    out = str(text or "").strip()
    while out.startswith("(") and out.endswith(")"):
        depth = 0
        closes_at_end = False
        for idx, char in enumerate(out):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    closes_at_end = idx == len(out) - 1
                    break
        if not closes_at_end:
            break
        out = out[1:-1].strip()
    return out
