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
        seen.add(lemma)
        out.append({
            "lemma": lemma,
            "name": lemma,
            "source": f"{item.get('source')}.pr_rewrite_declaration",
            "source_path": str(item.get("source_path") or ""),
            "declaration_kind": str(item.get("declaration_kind") or "lemma"),
            "declaration": str(item.get("declaration") or ""),
            "fact_source": str(item.get("fact_source") or "source_scan"),
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
            "lhs_game": decl_games[0],
            "rhs_game": decl_games[1],
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
        seen.add(lemma)
        out.append({
            "lemma": lemma,
            "name": lemma,
            "source": f"{item.get('source')}.semantic_pr_bound",
            "source_path": str(item.get("source_path") or ""),
            "declaration_kind": str(item.get("declaration_kind") or "lemma"),
            "declaration": str(item.get("declaration") or ""),
            "fact_source": str(item.get("fact_source") or "source_scan"),
            "authority": str(item.get("authority") or "source_scan_fallback"),
            "authority_rank": int(item.get("authority_rank") or 0),
            "ec_ground_truth": bool(item.get("ec_ground_truth")),
            "pr_game_keys": [
                str(key) for key in _list(item.get("pr_game_keys")) if str(key)
            ],
            "pr_events": [
                str(event) for event in _list(item.get("pr_events")) if str(event)
            ],
            "semantic_tags": sorted(tags),
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
            out.append(item)
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
    if "Pr[" not in text or "<=" in text or "`<=" in text or ">=" in text or "`>=" in text:
        return False
    if not re.search(r"(?<![<>=])=(?!=|>)", text):
        return False
    terms = _pr_terms_with_spans(text)
    if len(terms) != 2:
        return False
    between = text[terms[0][2] : terms[1][1]]
    if not re.fullmatch(r"\s*=\s*", between):
        return False
    after = text[terms[1][2] :].strip().rstrip(".").strip()
    return not after or bool(re.fullmatch(r"(?:\)|\])*\s*", after))


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
    "import_search_roots",
    "imported_theory_files",
    "pr_endpoint_pair_score",
    "require_theory_names",
    "score_pr_rewrite_candidate",
    "semantic_pr_bound_candidates",
    "semantic_pr_rewrite_candidates",
    "semantic_pr_rewrite_declarations",
    "session_context_files",
    "session_target_lemma",
    "source_declarations_by_name",
]
