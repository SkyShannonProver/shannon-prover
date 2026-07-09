"""Equiv exact-closer resource pass for EasyCrypt ProofIR.

This pass finds project-local equiv lemmas that already conclude the current
pRHL/equiv procedure pair.  It emits typed resource facts; action rendering
decides whether the corresponding ``exact/...`` tactic is probeable.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_lemma_index import (
    session_context_files as _lemma_index_session_context_files,
)
from core.easycrypt.analysis.ec_utils import (
    procedure_template_matches as _procedure_template_matches_with_key,
)


EQUIV_CLOSERS_SCHEMA_VERSION = 1
EQUIV_CLOSERS_KIND = "easycrypt_equiv_exact_closers"


def build_equiv_exact_closers(
    *,
    session_dir: str | Path | None,
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> list[dict[str, Any]]:
    if goal_type not in {"pRHL", "equiv"}:
        return []
    current_pair = _current_equiv_proc_pair(parsed, goal_text)
    if not current_pair:
        return []
    current_lhs, current_rhs = current_pair
    local_hypotheses = _local_equiv_hypothesis_handles(goal_text)
    out: list[dict[str, Any]] = []
    for item in _source_equiv_declarations(session_dir):
        lemma = str(item.get("lemma") or "")
        lhs = str(item.get("lhs_proc") or "")
        rhs = str(item.get("rhs_proc") or "")
        declaration = str(item.get("declaration") or "")
        if not lemma or not lhs or not rhs or not declaration:
            continue
        if not (
            _procedure_template_matches_with_key(
                lhs,
                current_lhs,
                key=_proc_signature_key,
            )
            and _procedure_template_matches_with_key(
                rhs,
                current_rhs,
                key=_proc_signature_key,
            )
        ):
            continue
        args, missing = _equiv_exact_arguments(declaration, local_hypotheses)
        if missing:
            tactic = f"exact/({lemma} {' '.join(args + missing)})."
        elif args:
            tactic = f"exact/({lemma} {' '.join(args)})."
        else:
            tactic = f"exact/{lemma}."
        out.append({
            "schema_version": EQUIV_CLOSERS_SCHEMA_VERSION,
            "kind": EQUIV_CLOSERS_KIND,
            "lemma": lemma,
            "tactic": tactic,
            "arguments": args,
            "missing_arguments": missing,
            "fully_bound": not missing,
            "declaration": declaration,
            "source_path": str(item.get("source_path") or ""),
            "lhs_proc": lhs,
            "rhs_proc": rhs,
            "fact_source": "source_equiv_declaration",
            "authority": "source_scan_fallback",
            "authority_rank": 10,
            "ec_ground_truth": False,
            "reason": (
                f"Source lemma `{lemma}` concludes the current procedure "
                f"pair `{current_lhs} ~ {current_rhs}`; exact keeps the "
                "proof at the pRHL abstraction instead of reopening bodies."
            ),
        })
    return out[:4]


def _current_equiv_proc_pair(
    parsed: dict[str, Any],
    goal_text: str,
) -> tuple[str, str] | None:
    lhs = str(parsed.get("lhs_proc") or parsed.get("left_proc") or "").strip()
    rhs = str(parsed.get("rhs_proc") or parsed.get("right_proc") or "").strip()
    if lhs and rhs:
        return (_clean_proc(lhs), _clean_proc(rhs))
    text = str(goal_text or "")
    matches = list(re.finditer(
        r"(?m)^\s*(?P<lhs>[A-Za-z_][^\n~]*?)\s+~\s+"
        r"(?P<rhs>[A-Za-z_][^\n:]*?)\s*$",
        text,
    ))
    if not matches:
        matches = list(re.finditer(
            r"equiv\s*\[\s*(?P<lhs>.*?)\s*~\s*(?P<rhs>.*?)\s*:",
            text,
            flags=re.DOTALL,
        ))
    if not matches:
        return None
    match = matches[-1]
    lhs = _clean_proc(match.group("lhs"))
    rhs = _clean_proc(match.group("rhs"))
    return (lhs, rhs) if lhs and rhs else None


def _local_equiv_hypothesis_handles(goal_text: str) -> list[dict[str, Any]]:
    if not goal_text:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    hyp_re = re.compile(
        r"(?ms)^\s*(?P<name>[A-Za-z_][\w']*)\s*:\s*equiv\s*\[\s*"
        r"(?P<body>.*?)\]",
    )
    for match in hyp_re.finditer(goal_text):
        name = match.group("name").strip()
        parsed = _parse_equiv_hypothesis_body(match.group("body"))
        lhs = _clean_proc(str(parsed.get("lhs") or ""))
        rhs = _clean_proc(str(parsed.get("rhs") or ""))
        if not name or not lhs or not rhs or name in seen:
            continue
        seen.add(name)
        pre = str(parsed.get("pre") or "")
        post = str(parsed.get("post") or "")
        out.append({
            "lemma": name,
            "lhs_proc": lhs,
            "rhs_proc": rhs,
            "pre": pre,
            "post": post,
        })
    return out


def _parse_equiv_hypothesis_body(body: str) -> dict[str, str]:
    flat = re.sub(r"\s+", " ", str(body or "")).strip()
    if "~" not in flat or ":" not in flat:
        return {}
    lhs, rest = flat.split("~", 1)
    rhs, spec = rest.split(":", 1)
    if "==>" in spec:
        pre, post = spec.split("==>", 1)
    else:
        pre, post = spec, ""
    return {
        "lhs": lhs.strip(),
        "rhs": rhs.strip(),
        "pre": pre.strip(),
        "post": post.strip(),
    }


def _source_equiv_declarations(
    session_dir: str | Path | None,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for path, kind in _lemma_index_session_context_files(session_dir):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        heads = list(re.finditer(
            r"\b(?P<local>local\s+)?(?P<kind>equiv|lemma|axiom)\s+"
            r"(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b",
            text,
        ))
        for idx, match in enumerate(heads):
            is_local = bool(match.group("local"))
            if is_local and kind != "session_context":
                continue
            next_start = heads[idx + 1].start() if idx + 1 < len(heads) else len(text)
            proof = re.search(r"\bproof\.", text[match.end():next_start])
            cut = match.end() + proof.start() if proof else next_start
            snippet = re.sub(r"\s+", " ", text[match.start():cut]).strip()
            proc_pair = _equiv_proc_pair(snippet)
            if not proc_pair:
                continue
            out.append({
                "lemma": match.group("name"),
                "declaration": snippet,
                "lhs_proc": proc_pair[0],
                "rhs_proc": proc_pair[1],
                "source_path": str(path),
            })
    return out


def _equiv_proc_pair(declaration: str) -> tuple[str, str] | None:
    matches = list(re.finditer(
        r"equiv\s*\[\s*(?P<lhs>.*?)\s*~\s*(?P<rhs>.*?)\s*:",
        declaration,
    ))
    match = matches[-1] if matches else None
    if match is None:
        match = re.search(
            r":\s*(?P<lhs>[A-Za-z_][^:~]*?)\s*~\s*"
            r"(?P<rhs>[A-Za-z_][^:~]*?)\s*:",
            declaration,
        )
    if not match:
        return None
    lhs = _clean_proc(match.group("lhs"))
    rhs = _clean_proc(match.group("rhs"))
    return (lhs, rhs) if lhs and rhs else None


def _equiv_exact_arguments(
    declaration: str,
    local_hypotheses: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    args: list[str] = []
    missing: list[str] = []
    for name in _lemma_binder_names(declaration):
        if name not in args:
            args.append(name)
    for idx, pair in enumerate(_declaration_equiv_premise_pairs(declaration), start=1):
        hyp = _matching_local_equiv_hypothesis(pair, local_hypotheses)
        if hyp:
            name = str(hyp.get("lemma") or "")
            if name and name not in args:
                args.append(name)
        else:
            missing.append(f"<equiv-premise-{idx}>")
    return args, missing


def _lemma_binder_names(declaration: str) -> list[str]:
    text = str(declaration or "")
    equiv_pos = text.find("equiv")
    head = text[:equiv_pos] if equiv_pos >= 0 else text
    names: list[str] = []
    for binder in re.finditer(
        r"\(\s*([A-Za-z_][A-Za-z0-9_']*)\s*(?::|<:)",
        head,
    ):
        name = binder.group(1)
        if name and name not in names:
            names.append(name)
    return names


def _declaration_equiv_premise_pairs(declaration: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(
        r"equiv\s*\[\s*(?P<lhs>.*?)\s*~\s*(?P<rhs>.*?)\s*:",
        str(declaration or ""),
        flags=re.DOTALL,
    ))
    if len(matches) <= 1:
        return []
    out: list[tuple[str, str]] = []
    for match in matches[:-1]:
        lhs = _clean_proc(match.group("lhs"))
        rhs = _clean_proc(match.group("rhs"))
        if lhs and rhs:
            out.append((lhs, rhs))
    return out


def _matching_local_equiv_hypothesis(
    pair: tuple[str, str],
    local_hypotheses: list[dict[str, Any]],
) -> dict[str, Any]:
    lhs, rhs = pair
    for hyp in local_hypotheses:
        if not isinstance(hyp, dict):
            continue
        hyp_lhs = str(hyp.get("lhs_proc") or "")
        hyp_rhs = str(hyp.get("rhs_proc") or "")
        if (
            _procedure_template_matches_with_key(lhs, hyp_lhs, key=_proc_signature_key)
            and _procedure_template_matches_with_key(
                rhs,
                hyp_rhs,
                key=_proc_signature_key,
            )
        ):
            return hyp
    return {}


def _proc_signature_key(proc: str) -> str:
    text = re.sub(r"\s+", "", str(proc or ""))
    if not text:
        return ""
    tail = text.rsplit(".", 1)[-1]
    head = text.split(".", 1)[0]
    head = re.sub(r"\(.*\)", "(...)", head)
    return f"{head}.{tail}" if tail else head


def _clean_proc(proc: str) -> str:
    return re.sub(r"\s+", " ", proc.strip()).strip()


__all__ = [
    "EQUIV_CLOSERS_KIND",
    "EQUIV_CLOSERS_SCHEMA_VERSION",
    "build_equiv_exact_closers",
]
