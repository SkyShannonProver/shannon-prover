"""State-derived concrete choices for surface actions.

This module owns choice generation that is based only on the current workspace
view.  Preflight decides whether a generated choice has displayable backend
content; eligibility decides whether the preflight-confirmed choice reaches the
agent/human surface.
"""
from __future__ import annotations

import re
from typing import Any
from core.easycrypt.value_shapes import as_dict as _dict
from workflow.surface_model import goal_text  # noqa: F401  (re-export)


_GOAL_OPERATOR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("(^^)", re.compile(r"\^\^")),
    ("(+^)", re.compile(r"\+\^")),
    ("(^)", re.compile(r"(?<![\^+\-])\^(?!\^)")),
    ("(++)", re.compile(r"\+\+")),
    ("(%/)", re.compile(r"%/")),
    ("(%%)", re.compile(r"%%")),
    ("nth", re.compile(r"\bnth\b")),
    ("take", re.compile(r"\btake\b")),
    ("drop", re.compile(r"\bdrop\b")),
    ("size", re.compile(r"\bsize\b")),
    ("b2i", re.compile(r"\bb2i\b")),
    ("rcons", re.compile(r"\brcons\b")),
    ("behead", re.compile(r"\bbehead\b")),
    ("head", re.compile(r"\bhead\b")),
    ("map", re.compile(r"\bmap\b")),
    ("mem", re.compile(r"\bmem\b")),
    ("dom", re.compile(r"\bdom\b")),
    ("rng", re.compile(r"\brng\b")),
    ("oget", re.compile(r"\boget\b")),
    ("(\\in)", re.compile(r"\\in\b")),
)

_LIST_OP_TEMPLATES = {
    "big": "(big _ _ {L})",
    "size": "(size {L})",
    "nth": "(nth _ {L} _)",
    "map": "(map _ {L})",
    "take": "(take _ {L})",
    "drop": "(drop _ {L})",
    "rcons": "(rcons {L} _)",
    "behead": "(behead {L})",
    "head": "(head _ {L})",
}

_NON_OPERATOR_TOKENS = frozenset({
    "bool", "int", "list", "unit", "real", "option", "fmap", "distr", "array",
    "word", "nat", "tuple", "Pr", "res", "true", "false", "witness",
})


def operator_queries_for_goal(view: dict[str, Any]) -> list[str]:
    """Concrete operator/skeleton queries visible in the current goal."""
    text = goal_text(view)
    if not text.strip():
        return []
    concl = re.split(r"-{5,}", text)[-1] if "-----" in text else text
    concl = re.sub(r"\[\s*\d+\s*\|\s*\w+\s*\]", "", concl)
    out = [token for token, pattern in _GOAL_OPERATOR_PATTERNS if pattern.search(concl)]
    ps = _dict(view.get("proof_status"))
    layer = str(ps.get("current_layer") or "")
    focus = str(ps.get("view_focus") or "")
    if layer == "ambient_logic" or focus in {"ambient_logic", "pure_tail"}:
        for token in _pure_goal_operator_tokens(text):
            key = re.sub(r"[()\\]", "", token).lower()
            seen = {re.sub(r"[()\\]", "", item).lower() for item in out}
            if (
                not key
                or key in seen
                or token in _NON_OPERATOR_TOKENS
                or re.search(r"\{" + re.escape(token) + r"\}", concl)
            ):
                continue
            out.append(token)
    expanded: list[str] = []
    for op in out:
        skeleton = _operator_skeleton(op, concl)
        if skeleton and skeleton not in expanded:
            expanded.append(skeleton)
        if op not in expanded:
            expanded.append(op)
    return expanded[:6]


def operator_query_is_valid_for_goal(query: str, view: dict[str, Any]) -> bool:
    q = str(query or "").strip()
    if not q or is_placeholder(q):
        return False
    goal = goal_text(view)
    if not goal.strip():
        return False
    tokens = _operator_query_tokens(q)
    if not tokens:
        return False
    return any(_token_visible_in_goal(token, goal) for token in tokens)


def inv_from_lemma_choices_for_view(view: dict[str, Any]) -> list[str]:
    """Lemma names visible enough to try invariant extraction."""
    out: list[str] = []
    for item in _walk_dicts(view):
        for key in ("lemma", "symbol", "name"):
            name = str(item.get(key) or "").strip()
            if not _valid_name_choice(name):
                continue
            if key == "lemma" or _dict_mentions_call_or_equiv(item):
                _append_unique(out, name)
        tactic = str(item.get("tactic_shape") or item.get("action") or item.get("candidate") or "").strip()
        for name in _call_tactic_names(tactic):
            _append_unique(out, name)
        if len(out) >= 6:
            break
    return out[:6]


def call_subgoal_invariant_choices_for_view(view: dict[str, Any]) -> list[str]:
    """Concrete invariants already visible in call/invariant candidates."""
    out: list[str] = []
    for item in _walk_dicts(view):
        for inv in _explicit_invariant_values(item):
            if _looks_like_invariant(inv):
                _append_unique(out, inv.rstrip(".").strip())
        for text in _call_tactic_text_values(item):
            for inv in call_invariants_from_text(text):
                if _valid_invariant_choice(inv):
                    _append_unique(out, inv)
        if len(out) >= 4:
            return out[:4]
    return out[:4]


def _explicit_invariant_values(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "invariant",
        "invariant_body",
        "call_invariant",
        "candidate_invariant",
        "frame_invariant",
    ):
        value = str(item.get(key) or "").strip()
        if _valid_invariant_choice(value):
            values.append(value)
    return values


def _call_tactic_text_values(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "tactic",
        "tactic_shape",
        "submit_tactic",
        "command",
        "action",
        "candidate",
        "preview",
        "result",
    ):
        value = str(item.get(key) or "").strip()
        if value and "call" in value and "(_:" in value:
            values.append(value)
    submit = item.get("submit")
    submit = submit if isinstance(submit, dict) else {}
    payload = submit.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    tactic = str(payload.get("tactic") or "").strip()
    if tactic and "call" in tactic and "(_:" in tactic:
        values.append(tactic)
    return values


def call_invariants_from_text(text: str) -> list[str]:
    """Extract invariant bodies from ``call (_: ...).`` tactic text."""
    source = str(text or "")
    out: list[str] = []
    start_at = 0
    marker = "call"
    while True:
        idx = source.find(marker, start_at)
        if idx < 0:
            break
        wrapper = source.find("(_:", idx)
        if wrapper < 0:
            start_at = idx + len(marker)
            continue
        start = wrapper + 3
        depth = 1
        pos = start
        while pos < len(source):
            ch = source[pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    inv = source[start:pos].strip()
                    if inv:
                        out.append(inv.rstrip(".").strip())
                    break
            pos += 1
        start_at = max(pos + 1, wrapper + 3)
    return out


def is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return (
        not text
        or (text.startswith("<") and text.endswith(">"))
        or text.isupper()
        or "..." in text
        or "NAME" in text
        or "LEMMA" in text
        or "SYMBOL" in text
        or "QUERY" in text
    )


def _operator_query_tokens(query: str) -> list[str]:
    q = query.strip()
    out: list[str] = []
    for sym in ("+^", "^^", "++", "%/", "%%", "\\in", "^"):
        if sym in q:
            out.append(sym)
    for name in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", q):
        if name != "_":
            out.append(name)
    return out


def _pure_goal_operator_tokens(goal: str) -> list[str]:
    try:
        from workflow.proof_management.analyzers.pure_tail import goal_operators
        return list(goal_operators(goal))
    except Exception:
        return []


def _list_structure(concl: str) -> str | None:
    if re.search(r"\s::\s", concl):
        return "(_ :: _)"
    if re.search(r"\s\+\+\s", concl):
        return "(_ ++ _)"
    if re.search(r"\brcons\b", concl):
        return "(rcons _ _)"
    if re.search(r"\bnseq\b", concl):
        return "(nseq _ _)"
    if "[]" in concl:
        return "[]"
    return None


def _operator_skeleton(op: str, concl: str) -> str | None:
    template = _LIST_OP_TEMPLATES.get(op)
    if not template:
        return None
    struct = _list_structure(concl)
    return template.replace("{L}", struct) if struct else None


def _token_visible_in_goal(token: str, goal: str) -> bool:
    if re.match(r"^[A-Za-z_]", token):
        return bool(re.search(rf"\b{re.escape(token)}\b", goal))
    return token in goal


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = [value]
    seen = 0
    while stack and seen < 1000:
        seen += 1
        item = stack.pop()
        if isinstance(item, dict):
            out.append(item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return out


def _walk_strings(value: Any) -> list[str]:
    out: list[str] = []
    stack = [value]
    seen = 0
    while stack and seen < 2000:
        seen += 1
        item = stack.pop()
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return out


def _dict_mentions_call_or_equiv(item: dict[str, Any]) -> bool:
    blob = " ".join(
        str(item.get(key) or "")
        for key in ("kind", "producer", "call_candidate_kind", "tactic_shape", "action", "candidate", "why")
    ).lower()
    return any(marker in blob for marker in ("call", "equiv", "lemma", "bridge"))


def _call_tactic_names(text: str) -> list[str]:
    out: list[str] = []
    for match in re.finditer(r"\b(?:e?call|exact|apply)\s+([A-Za-z_][A-Za-z0-9_'.]*)", text):
        name = match.group(1).strip().rstrip(".")
        if _valid_name_choice(name) and name not in {"_", "lemma"}:
            out.append(name)
    return out


def _looks_like_invariant(text: str) -> bool:
    if not _valid_invariant_choice(text):
        return False
    return any(marker in text for marker in ("={", "glob", "/\\", "\\/", "==>", "inv "))


def _valid_name_choice(name: str) -> bool:
    if is_placeholder(name):
        return False
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_'.]*$", name):
        return False
    return name.lower() not in {"lemma", "equiv", "call", "inv", "invariant", "predicate"}


def _valid_invariant_choice(inv: str) -> bool:
    text = str(inv or "").strip()
    if is_placeholder(text):
        return False
    if not text or len(text) > 1000:
        return False
    return not any(marker in text.lower() for marker in (
        "the easycrypt invariant expression",
        "inside call",
        "placeholder",
    ))


def _append_unique(out: list[str], value: str) -> None:
    if value and value not in out:
        out.append(value)

