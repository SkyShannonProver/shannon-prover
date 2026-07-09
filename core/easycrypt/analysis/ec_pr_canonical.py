"""Canonical parsing helpers for EasyCrypt probability terms.

This module is the shared frontend for ``Pr[...]`` syntax.  Downstream passes
should consume the typed records here instead of re-parsing probability goals
with local regex fragments.  The parser is intentionally conservative: it only
records balanced ``Pr[...]`` terms and procedure endpoints that can be located
structurally.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    matching_delimiter as _matching_delimiter,
    split_top_level_commas as _split_top_level_commas,
)


PR_CANONICAL_SCHEMA_VERSION = 1
PR_CANONICAL_KIND = "easycrypt_pr_canonical"


def parse_pr_terms(
    text: str,
    *,
    default_memory: str = "",
    default_event: str = "",
    require_endpoint: bool = True,
) -> list[dict[str, Any]]:
    """Return canonical records for balanced ``Pr[...]`` terms in ``text``."""
    return _parse_pr_terms(
        text,
        default_memory=default_memory,
        default_event=default_event,
        require_endpoint=require_endpoint,
        include_spans=False,
    )


def parse_pr_terms_with_spans(
    text: str,
    *,
    default_memory: str = "",
    default_event: str = "",
    require_endpoint: bool = True,
) -> list[dict[str, Any]]:
    """Return canonical ``Pr[...]`` records with ``start``/``end`` offsets."""
    return _parse_pr_terms(
        text,
        default_memory=default_memory,
        default_event=default_event,
        require_endpoint=require_endpoint,
        include_spans=True,
    )


def _parse_pr_terms(
    text: str,
    *,
    default_memory: str,
    default_event: str,
    require_endpoint: bool,
    include_spans: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    source = str(text or "")
    for match in re.finditer(r"Pr\s*\[", source):
        open_idx = match.end() - 1
        close_idx = matching_bracket(source, open_idx, "[", "]")
        if close_idx <= open_idx:
            continue
        body = source[open_idx + 1 : close_idx].strip()
        game_expr, memory, event = pr_body_parts(
            body,
            default_memory=default_memory,
            default_event=default_event,
        )
        endpoint = procedure_endpoint(game_expr)
        if require_endpoint and not endpoint:
            continue
        item = {
            "pr_text": source[match.start() : close_idx + 1].strip(),
            "game_expr": game_expr,
            "game_key": game_key(game_expr),
            "memory": memory,
            "event": event,
            "endpoint": endpoint,
        }
        if include_spans:
            item["start"] = match.start()
            item["end"] = close_idx + 1
        out.append(item)
    return out


def first_pr_equality_terms(text: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return the first adjacent ``Pr[...] = Pr[...]`` pair in ``text``."""
    terms = parse_pr_terms_with_spans(text, require_endpoint=False)
    for left, right in zip(terms, terms[1:]):
        between = str(text or "")[int(left.get("end") or 0):int(right.get("start") or 0)]
        if re.fullmatch(r"\s*=\s*", between):
            return left, right
    return None


def pr_body_parts(
    body: str,
    *,
    default_memory: str = "",
    default_event: str = "",
) -> tuple[str, str, str]:
    """Split a ``Pr`` body into game expression, memory, and event parts."""
    text = str(body or "").strip()
    game = text
    memory = str(default_memory or "")
    event = str(default_event or "")
    if "@" in text:
        game, after_at = text.split("@", 1)
        if ":" in after_at:
            mem, evt = after_at.split(":", 1)
            memory = mem.strip() or memory
            event = evt.strip() or event
        else:
            memory = after_at.strip() or memory
    return game.strip(), memory, event


def procedure_endpoint(game_expr: str) -> dict[str, Any]:
    """Return the final ``Module.proc(args)`` endpoint in a game expression."""
    text = str(game_expr or "").strip()
    open_idx = final_procedure_open(text)
    if open_idx < 0:
        return {}
    close_idx = matching_bracket(text, open_idx, "(", ")")
    if close_idx < 0:
        return {}
    name_start = open_idx - 1
    while name_start >= 0 and re.match(r"[A-Za-z0-9_']", text[name_start]):
        name_start -= 1
    proc = text[name_start + 1 : open_idx].strip()
    if not proc or name_start < 0 or text[name_start] != ".":
        return {}
    module_expr = text[:name_start].strip()
    args = [
        arg.strip()
        for arg in split_top_level_args(text[open_idx + 1 : close_idx])
        if arg.strip()
    ]
    canonical = f"{module_expr}.{proc}({', '.join(args)})"
    return {
        "module_expr": module_expr,
        "procedure": proc,
        "procedure_args": args,
        "canonical": canonical,
        "module_root": application_root(module_expr),
    }


def final_procedure_open(text: str) -> int:
    """Return the opening paren of the final procedure call, if present."""
    depth = 0
    candidate = -1
    for idx, ch in enumerate(str(text or "")):
        if ch == "(":
            if depth == 0 and looks_like_procedure_call(text, idx):
                candidate = idx
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
    return candidate


def looks_like_procedure_call(text: str, open_idx: int) -> bool:
    idx = open_idx - 1
    while idx >= 0 and re.match(r"[A-Za-z0-9_']", text[idx]):
        idx -= 1
    return idx >= 0 and text[idx] == "."


def endpoint_templates_compatible(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    """Conservatively compare lemma and goal endpoints by proc and module root."""
    if not left or not right:
        return False
    if str(left.get("procedure") or "") != str(right.get("procedure") or ""):
        return False
    lroot = str(left.get("module_root") or "")
    rroot = str(right.get("module_root") or "")
    return bool(lroot and rroot and lroot.rsplit(".", 1)[-1] == rroot.rsplit(".", 1)[-1])


def application_root(expr: str) -> str:
    """Return the head identifier of a module/functor application."""
    text = str(expr or "").strip()
    match = re.match(r"([A-Za-z_][A-Za-z0-9_'.]*)\s*(?:\(|$)", text)
    return match.group(1) if match else ""


def module_application_parts(expr: str) -> dict[str, Any]:
    """Return the root and top-level args of a module/functor application."""
    text = str(expr or "").strip()
    match = re.match(
        r"(?P<root>[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*\(",
        text,
    )
    if not match:
        return {}
    open_idx = match.end() - 1
    close_idx = matching_bracket(text, open_idx, "(", ")")
    if close_idx <= open_idx:
        return {}
    return {
        "root": match.group("root"),
        "args": split_top_level_args(text[open_idx + 1 : close_idx]),
    }


def module_application_args(expr: str) -> list[str]:
    """Return top-level arguments from a module application expression."""
    parts = module_application_parts(expr)
    return [
        str(arg).strip()
        for arg in _list(parts.get("args"))
        if str(arg).strip()
    ]


def parse_module_expr(expr: str) -> dict[str, Any]:
    """Parse a module expression into a small ``{name, args}`` tree."""
    text = str(expr or "").strip()
    if not text:
        return {"name": "", "args": []}

    # Preserve the older path-diff parser's permissive boundary: any first
    # top-level ``(`` splits the head from arguments, even when the head is not
    # a strict EasyCrypt module path.
    depth = 0
    paren_idx = -1
    for idx, ch in enumerate(text):
        if ch == "(":
            if depth == 0:
                paren_idx = idx
                break
            depth += 1
        elif ch == ")":
            pass
    if paren_idx < 0:
        return {"name": text, "args": []}

    name = text[:paren_idx].strip()
    depth = 1
    idx = paren_idx + 1
    while idx < len(text) and depth > 0:
        if text[idx] == "(":
            depth += 1
        elif text[idx] == ")":
            depth -= 1
        idx += 1
    close_idx = idx - 1
    args = split_top_level_args(text[paren_idx + 1 : close_idx])
    return {
        "name": name,
        "args": [
            parse_module_expr(str(arg))
            for arg in args
        ],
    }


def format_module_expr(tree: dict[str, Any]) -> str:
    """Render a parsed module tree back to text."""
    name = str(_dict(tree).get("name") or "")
    args = [
        format_module_expr(arg)
        for arg in _list(_dict(tree).get("args"))
        if isinstance(arg, dict)
    ]
    if not args:
        return name
    return f"{name}({', '.join(args)})"


def endpoint_with_inserted_arg(endpoint: str, arg: str) -> str:
    """Show the invalid endpoint formed by inserting ``arg`` into an empty call."""
    text = str(endpoint or "").strip()
    if not text.endswith(")") or not arg:
        return ""
    open_idx = text.rfind("(")
    if open_idx < 0:
        return ""
    inside = text[open_idx + 1 : -1].strip()
    if inside:
        return ""
    return f"{text[:open_idx]}({arg})"


def event_mentions_name(event: str, name: str) -> bool:
    """Return true when an event predicate mentions a slot name as a token."""
    return bool(re.search(rf"\b{re.escape(name)}\b", str(event or "")))


def compact_pr_term(term: dict[str, Any]) -> dict[str, Any]:
    """Return the small stable shape suitable for JSON summaries."""
    endpoint = _dict(term.get("endpoint"))
    return {
        "pr_text": str(term.get("pr_text") or ""),
        "game_expr": str(term.get("game_expr") or ""),
        "game_key": str(term.get("game_key") or ""),
        "memory": str(term.get("memory") or ""),
        "event": str(term.get("event") or ""),
        "endpoint": {
            "module_expr": str(endpoint.get("module_expr") or ""),
            "procedure": str(endpoint.get("procedure") or ""),
            "procedure_args": [
                str(arg) for arg in _list(endpoint.get("procedure_args"))
            ],
            "canonical": str(endpoint.get("canonical") or ""),
        },
    }


def pr_game_keys_from_text(text: str) -> list[str]:
    """Return unique canonical game keys from ``Pr[...]`` terms in source text."""
    out: list[str] = []
    for term in parse_pr_terms(
        text,
        default_memory="&m",
        default_event="res",
        require_endpoint=False,
    ):
        key = str(term.get("game_key") or "")
        if key and key not in out:
            out.append(key)
    return out


def pr_terms_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Return canonical game keys and source spans for balanced ``Pr[...]`` terms."""
    out: list[tuple[str, int, int]] = []
    for term in parse_pr_terms_with_spans(text, require_endpoint=False):
        key = str(term.get("game_key") or "")
        if key:
            out.append((
                key,
                int(term.get("start") or 0),
                int(term.get("end") or 0),
            ))
    return out


def game_key(value: Any) -> str:
    """Return a whitespace-insensitive key for a game expression."""
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("Pr["):
        keys = pr_game_keys_from_text(text)
        return keys[0] if keys else ""
    text = text.split("@", 1)[0].strip()
    text = strip_trailing_proc_call(text)
    match = re.match(
        r"([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)",
        text,
    )
    if not match:
        return ""
    head = match.group(1)
    rest = text[match.end() :].lstrip()
    if not rest.startswith("("):
        return head
    end = matching_bracket(rest, 0, "(", ")")
    if end < 0:
        return head
    args = re.sub(r"\s+", "", rest[: end + 1])
    return head + args


def strip_trailing_proc_call(text: str) -> str:
    """Remove a final lower-case procedure call while preserving functors."""
    source = str(text or "").strip()
    depth = 0
    last_dot = -1
    for idx, ch in enumerate(source):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "." and depth == 0:
            last_dot = idx
    if last_dot < 0:
        return source
    tail = source[last_dot + 1 :].strip()
    match = re.match(r"([A-Za-z_][A-Za-z0-9_']*)\s*\(", tail)
    if not match:
        return source
    if match.group(1)[:1].isupper():
        return source
    open_idx = last_dot + 1 + tail.find("(")
    close_idx = matching_bracket(source, open_idx, "(", ")")
    if close_idx < 0 or source[close_idx + 1 :].strip():
        return source
    return source[:last_dot].strip()


def pr_term_for_game(game_expr: str, *, memory: str, event: str) -> str:
    """Format a canonical ``Pr`` term from game, memory, and event parts."""
    game = str(game_expr or "").strip()
    if not game:
        return ""
    mem = str(memory or "&m").strip()
    evt = str(event or "res").strip()
    return f"Pr[{game} @ {mem} : {evt}]"


def matching_bracket(text: str, open_idx: int, open_ch: str, close_ch: str) -> int:
    """Return the matching close bracket index, or ``-1``."""
    return _matching_delimiter(str(text or ""), open_idx, open_ch, close_ch)


def split_top_level_args(text: str) -> list[str]:
    """Split comma-separated arguments without crossing bracket depth."""
    return _split_top_level_commas(text)


__all__ = [
    "PR_CANONICAL_KIND",
    "PR_CANONICAL_SCHEMA_VERSION",
    "application_root",
    "compact_pr_term",
    "endpoint_templates_compatible",
    "endpoint_with_inserted_arg",
    "event_mentions_name",
    "final_procedure_open",
    "first_pr_equality_terms",
    "format_module_expr",
    "game_key",
    "looks_like_procedure_call",
    "matching_bracket",
    "module_application_args",
    "module_application_parts",
    "parse_module_expr",
    "parse_pr_terms",
    "parse_pr_terms_with_spans",
    "pr_body_parts",
    "pr_game_keys_from_text",
    "pr_term_for_game",
    "pr_terms_with_spans",
    "procedure_endpoint",
    "split_top_level_args",
    "strip_trailing_proc_call",
]
