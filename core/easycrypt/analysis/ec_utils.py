"""Tiny dependency-free helpers shared by EasyCrypt analysis passes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable

# Canonical shape guards live in value_shapes; re-exported here because ~24
# analysis modules import them via ec_utils.
from core.easycrypt.value_shapes import (  # noqa: F401
    as_dict,
    as_list,
    drop_empty,
)




def dedupe_strings(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def dedupe_present_strings(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "")
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def dedupe_stripped_strings(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def collapse_ws(value: Any) -> str:
    return " ".join(str(value or "").split())


def string_list(value: Any) -> list[str]:
    return [
        str(item)
        for item in as_list(value)
        if str(item or "").strip()
    ]


def deduped_string_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else []
    return dedupe_strings(str(item) for item in values if str(item))


def deduped_stripped_string_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else []
    return dedupe_stripped_strings(str(item) for item in values if str(item))


def candidate_names(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        for key in ("lemma", "name", "lemma_name", "id"):
            item = value.get(key)
            if isinstance(item, str) and item:
                return [item]
        return []
    if isinstance(value, list):
        for item in value:
            out.extend(candidate_names(item))
    return dedupe_strings(out)


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def dedupe_ranked_by_value(
    candidates: Iterable[dict[str, Any]],
    rank_key: Callable[[dict[str, Any]], Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=rank_key):
        value = str(candidate.get("value") or "")
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(candidate)
    return out


def dedupe_dicts(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        compact = drop_empty_recursive(item)
        key = json.dumps(compact, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(compact)
    return out


def read_session_meta(session_dir: Path) -> dict[str, Any]:
    meta = session_dir / "session_meta.json"
    if not meta.exists():
        return {}
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def session_source_files(session_dir: str | Path | None) -> list[Path]:
    if session_dir is None:
        return []
    sdir = Path(session_dir)
    paths: list[Path] = []
    ctx = sdir / "context.ec"
    if ctx.exists():
        paths.append(ctx)
    meta = read_session_meta(sdir)
    raw = meta.get("file") or meta.get("source_file")
    if raw:
        path = Path(str(raw)).expanduser()
        if not path.is_absolute():
            for candidate in (Path.cwd() / path, sdir / path, sdir.parent / path):
                if candidate.exists():
                    path = candidate
                    break
        if path.exists():
            paths.append(path)
    return dedupe_paths(paths)



def drop_empty_recursive(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            compact = drop_empty_recursive(item)
            if compact in (None, "", [], {}):
                continue
            out[key] = compact
        return out
    if isinstance(value, list):
        return [
            item
            for item in (drop_empty_recursive(item) for item in value)
            if item not in (None, "", [], {})
        ]
    return value


def int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def unqualified(name: str) -> str:
    return name.rsplit(".", 1)[-1] if "." in name else name


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", value).strip("_") or "item"


def is_emit_safe_var(name: str) -> bool:
    text = str(name or "")
    if not text:
        return False
    if text[0].isdigit():
        return False
    return all(ch.isalnum() or ch in {"_", "."} for ch in text)


def is_live_safe_var(name: str) -> bool:
    text = str(name or "")
    if not is_emit_safe_var(text):
        return False
    if "." in text:
        return True
    return not text[:1].isupper()


def lemma_leaf(name: str) -> str:
    return str(name or "").rstrip(".").rsplit(".", 1)[-1]


def strip_balanced_parens(value: str) -> str:
    out: list[str] = []
    depth = 0
    for char in str(value or ""):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(char)
    return "".join(out)


def strip_outer_parens(value: str) -> str:
    """Remove balanced enclosing parentheses from a whole expression."""
    out = str(value or "").strip()
    changed = True
    while changed and out.startswith("(") and out.endswith(")"):
        changed = False
        depth = 0
        encloses = True
        for idx, char in enumerate(out):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and idx != len(out) - 1:
                    encloses = False
                    break
                if depth < 0:
                    encloses = False
                    break
        if encloses and depth == 0:
            out = out[1:-1].strip()
            changed = True
    return out


def split_top_level_at(text: str, token: str) -> tuple[str, str] | None:
    idx = top_level_token_index(text, token)
    if idx < 0:
        return None
    return (text[:idx].strip(), text[idx + len(token):].strip())


def top_level_token_index(text: str, token: str) -> int:
    if not token:
        return -1
    depth = 0
    idx = 0
    source = str(text or "")
    while idx <= len(source) - len(token):
        ch = source[idx]
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        if depth == 0 and source.startswith(token, idx):
            return idx
        idx += 1
    return -1


def split_top_level_commas(text: str) -> list[str]:
    source = str(text or "")
    if source == "":
        return []
    out: list[str] = []
    depth = 0
    start = 0
    for idx, ch in enumerate(source):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            out.append(source[start:idx].strip())
            start = idx + 1
    tail = source[start:].strip()
    if tail:
        out.append(tail)
    return out


def split_top_level_conjuncts(
    text: str,
    *,
    collapse_whitespace: bool = False,
    nesting_open: str = "([{",
) -> list[str]:
    source = str(text or "")
    if collapse_whitespace:
        source = re.sub(r"\s+", " ", source).strip()
    else:
        source = source.strip()
    if not source:
        return []
    close_for = {"(": ")", "[": "]", "{": "}"}
    open_chars = {ch for ch in nesting_open if ch in close_for}
    close_chars = {close_for[ch] for ch in open_chars}
    out: list[str] = []
    start = 0
    depth = 0
    idx = 0
    while idx < len(source):
        ch = source[idx]
        if ch in open_chars:
            depth += 1
            idx += 1
            continue
        if ch in close_chars:
            depth = max(0, depth - 1)
            idx += 1
            continue
        if depth == 0 and source.startswith("/\\", idx):
            part = source[start:idx].strip()
            if part:
                out.append(part)
            idx += 2
            start = idx
            continue
        idx += 1
    tail = source[start:].strip()
    if tail:
        out.append(tail)
    return out


def split_flat_conjuncts(text: str, *, include_double_escaped: bool = True) -> list[str]:
    pattern = r"/\\|/\\\\|&&" if include_double_escaped else r"/\\|&&"
    return re.split(pattern, str(text or ""))


def procedure_tail(proc: str) -> str:
    parts = [part for part in str(proc or "").split(".") if part]
    if not parts:
        return ""
    return ".".join(parts[-2:]) if len(parts) >= 2 else parts[-1]


def matching_delimiter(
    text: str,
    start: int,
    open_ch: str,
    close_ch: str,
    *,
    skip_easycrypt_comments: bool = False,
) -> int:
    source = str(text or "")
    depth = 0
    idx = max(0, start)
    while idx < len(source):
        ch = source[idx]
        if (
            skip_easycrypt_comments
            and ch == "("
            and idx + 1 < len(source)
            and source[idx + 1] == "*"
        ):
            end = source.find("*)", idx + 2)
            idx = (end + 2) if end >= 0 else len(source)
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return idx
        idx += 1
    return -1


def delimited_region(
    text: str,
    open_idx: int,
    open_ch: str,
    close_ch: str,
    *,
    skip_easycrypt_comments: bool = False,
) -> str:
    close_idx = matching_delimiter(
        text,
        open_idx,
        open_ch,
        close_ch,
        skip_easycrypt_comments=skip_easycrypt_comments,
    )
    if close_idx < 0:
        return text[open_idx + 1:]
    return text[open_idx + 1:close_idx]


def first_top_level_implication(text: str) -> int:
    depth = 0
    idx = 0
    while idx < len(text) - 1:
        ch = text[idx]
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        if (
            depth == 0
            and text[idx : idx + 2] == "=>"
            and (idx == 0 or text[idx - 1] not in "<=>")
            and (idx + 2 >= len(text) or text[idx + 2] != ">")
        ):
            return idx
        idx += 1
    return -1


def contains_top_level_implication(text: str) -> bool:
    flat = re.sub(r"\s+", " ", str(text or "")).strip()
    return first_top_level_implication(flat) >= 0


def looks_like_program_residual(goal_text: str, goal_type: str) -> bool:
    if str(goal_type or "") not in {"hoare", "phoare", "pRHL", "equiv", "eager"}:
        return False
    text = str(goal_text or "")
    if not text.strip():
        return False
    if re.search(r"^\s*\(\s*\d", text, flags=re.MULTILINE):
        return True
    return any(token in text for token in ("<@", "<$", "<-", "while ", "if "))


def infer_statement_kind(text: str) -> str:
    low = text.strip().lower()
    if "<@" in text:
        return "CALL"
    if "<$" in text:
        return "SAMPLE"
    if low.startswith("if"):
        return "IF"
    if low.startswith("while"):
        return "WHILE"
    if "<-" in text:
        return "ASSIGN"
    if low.startswith("return"):
        return "RETURN"
    return "UNKNOWN"


def procedure_template_matches(
    template: str,
    concrete: str,
    *,
    key: Callable[[str], str],
) -> bool:
    templ = key(template)
    proc = key(concrete)
    if not templ or not proc:
        return False
    return templ == proc


def legacy_shape_tactic_templates(parsed: dict[str, Any]) -> list[Any]:
    legacy = as_dict(parsed.get("legacy_shape_tactic_templates"))
    items = as_list(legacy.get("items"))
    if items:
        return items
    return as_list(parsed.get("suggested_tactics"))
