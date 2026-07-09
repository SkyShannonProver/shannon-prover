#!/usr/bin/env python3
"""Parse an EasyCrypt .ec file and produce a structured index of its declarations.

Mini tool for session_cli:
  -file-index FILE   Print a structured summary of types, ops, modules, clones,
                     and lemmas in FILE (or the session context file if -f omitted).

Replaces manual grepping or opening files individually. Returns a compact,
human-readable outline so the prover can locate relevant names without reading
the entire file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


# A line that STARTS a new top-level declaration — a backstop so the statement
# scan never runs past its own lemma into the next one. hoare / phoare / equiv
# are intentionally excluded: those keywords appear INSIDE lemma statements.
_NEXT_DECL = re.compile(r"^\s*(?:local\s+)?(?:lemma|axiom|module|clone|section)\b")
# Whole-word `by` — the start of an inline proof (`lemma X : STMT by TAC.`).
_INLINE_BY = re.compile(r"(?<!\w)by(?!\w)")


def _extract_statement(lines: list, start: int, max_span: int = 80) -> str:
    """Capture a lemma's statement (signature) from its declaration line up to
    — but NOT including — its proof.

    Eval-safe by construction: it returns the lemma name + type signature only
    and stops at the first proof boundary, so no proof body / tactic ever leaks
    (this is what makes a whole-file lemma index admissible under eval mode,
    where sibling-lemma *statements* are allowed but proofs are not). Three
    boundaries are recognised: an explicit ``proof.``/``qed.``, an inline
    ``by``-closed proof (``lemma X : STMT by TAC.``, which has no ``proof.``),
    and — as a backstop — the start of the next top-level declaration.
    """
    out: list[str] = []
    for j in range(start, min(len(lines), start + max_span)):
        raw = lines[j]
        s = raw.strip()
        if j > start and _NEXT_DECL.match(raw):
            break  # ran into the next declaration without a proof boundary
        if s == "proof." or s.startswith("proof.") or s.endswith(" proof."):
            head = raw.split("proof.")[0].rstrip()
            if head.strip():
                out.append(head.rstrip())
            break
        if s == "qed.":  # defensive: never run past a proof boundary
            break
        # Inline `by`-closed lemma: the proof starts at ` by `; keep only the
        # statement head and stop, so no tactic leaks for a proof-less lemma.
        m = _INLINE_BY.search(raw)
        if m:
            head = raw[:m.start()].rstrip()
            if head:
                out.append(head)
            break
        out.append(raw.rstrip())
    return "\n".join(out).strip()


def index_ec_file(file_path: Path) -> dict:
    """Parse an .ec file and return a structured summary of all declarations.

    Returns a dict with:
      file           — file name (basename)
      total_lines    — total line count
      requires       — list of require/import lines (as strings)
      types          — list of {name, line}
      ops            — list of {name, kind, line}  (op / pred / abbrev)
      axioms         — list of {name, line}
      modules        — list of {name, kind, line, in_section}
      clones         — list of {from, name, line}
      top_level_lemmas  — list of {name, kind, line}
      section_lemmas    — list of {name, kind, line}
      all_lemmas        — list of {name, kind, location, line}
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e), "file": str(file_path)}

    lines = text.split('\n')
    result: dict = {
        "file": file_path.name,
        "total_lines": len(lines),
        "requires": [],
        "types": [],
        "ops": [],
        "axioms": [],
        "modules": [],
        "clones": [],
        "top_level_lemmas": [],
        "section_lemmas": [],
        "all_lemmas": [],
    }

    # Compiled patterns
    require_pat = re.compile(r'^\s*require\s+(?:import\s+)?(.*?)\s*$')
    type_pat = re.compile(r'^\s*(?:abstract\s+)?type\s+(\w+)')
    op_pat = re.compile(r'^\s*(op|pred|abbrev)\s+(?:\[.*?\]\s+)?(\w+)')
    axiom_pat = re.compile(r'^\s*axiom\s+([\w\']+)')
    # module type must be matched before plain module
    module_type_pat = re.compile(r'^\s*module\s+type\s+(\w+)')
    module_pat = re.compile(r'^\s*module\s+(\w+)')
    clone_pat = re.compile(r'^\s*clone\s+(?:import\s+)?(\w[\w.]*)\s+as\s+(\w+)')
    lemma_pat = re.compile(r'^\s*(local\s+)?(lemma|equiv|hoare|phoare)\s+([\w\']+)')
    section_start_pat = re.compile(r'^\s*section\b')
    section_end_pat = re.compile(r'^\s*end\s+section\b')

    # Track section nesting
    section_depth = 0

    for i, line in enumerate(lines):
        ln = i + 1  # 1-based

        # Skip pure comment lines
        stripped = line.strip()
        if stripped.startswith('(*') and '**)' not in stripped:
            # Could be multi-line comment; do simple single-line skip for purity
            pass

        # Section tracking (must come before other patterns)
        if section_start_pat.match(line) and not stripped.startswith('(*'):
            section_depth += 1
            continue
        if section_end_pat.match(line):
            if section_depth > 0:
                section_depth -= 1
            continue

        in_section = section_depth > 0

        # require / require import
        if re.match(r'^\s*require\b', line):
            m = require_pat.match(line)
            if m:
                val = m.group(1).rstrip('.').strip()
                if val:
                    result["requires"].append(val)
            continue

        # type
        m = type_pat.match(line)
        if m:
            result["types"].append({"name": m.group(1), "line": ln})
            continue

        # op / pred / abbrev
        m = op_pat.match(line)
        if m:
            result["ops"].append({"name": m.group(2), "kind": m.group(1), "line": ln})
            continue

        # axiom
        m = axiom_pat.match(line)
        if m:
            result["axioms"].append({"name": m.group(1), "line": ln})
            continue

        # module type (before plain module)
        m = module_type_pat.match(line)
        if m:
            result["modules"].append({
                "name": m.group(1), "kind": "module type",
                "line": ln, "in_section": in_section,
            })
            continue

        # module
        m = module_pat.match(line)
        if m:
            result["modules"].append({
                "name": m.group(1), "kind": "module",
                "line": ln, "in_section": in_section,
            })
            continue

        # clone
        m = clone_pat.match(line)
        if m:
            result["clones"].append({
                "from": m.group(1), "name": m.group(2), "line": ln,
            })
            continue

        # lemma / equiv / hoare / phoare
        m = lemma_pat.match(line)
        if m:
            is_local = bool(m.group(1))
            kind = m.group(2)
            name = m.group(3)
            location = "in_section" if in_section else "top_level"
            # scope/export FACT: a `local` lemma never escapes its section (EC raises
            # `unknown identifier` if you cite it from outside); a non-`local` lemma in
            # a section is exported once the section closes, but abstracted over the
            # section's declared parameters; a plain top-level lemma is exported as-is.
            scope = ("local" if is_local
                     else "exported_after_section" if in_section
                     else "exported")
            entry = {"name": name, "kind": kind, "location": location, "line": ln,
                     "is_local": is_local, "scope": scope,
                     "statement": _extract_statement(lines, i)}
            result["all_lemmas"].append(entry)
            if in_section:
                result["section_lemmas"].append({"name": name, "kind": kind, "line": ln})
            else:
                result["top_level_lemmas"].append({"name": name, "kind": kind, "line": ln})

    return result


def format_lemma_index(idx: dict) -> str:
    """Agent-facing whole-file lemma index: every lemma's name + statement
    (signature), proofs excluded. This is the on-demand `lemma_index` view the
    prover can pull at the start to see what is available to apply/rewrite/bridge
    with, without reading the whole file or pasting it into the prompt.
    """
    if "error" in idx:
        return f"[lemma-index] Error: {idx['error']}\n"
    lemmas = idx.get("all_lemmas", [])
    if not lemmas:
        return f"=== {idx.get('file', '')} — no lemmas found ===\n"
    out = [
        f"=== {idx.get('file', '')}: {len(lemmas)} lemma statement(s) "
        "(signatures only — proofs are NOT shown) ===",
        "These are every lemma declared in the current file. Use them to plan "
        "which lemmas you can apply/rewrite/bridge with; `lookup_symbol` for the "
        "exact declaration of any one before using it.",
        "",
    ]
    for l in lemmas:
        loc = l.get("location", "")
        out.append(f"L{l.get('line')} [{l.get('kind')}, {loc}] {l.get('name')}:")
        stmt = (l.get("statement") or "").strip()
        for sl in (stmt.splitlines() or ["(statement unavailable)"]):
            out.append("    " + sl)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def format_index(idx: dict) -> str:
    """Format the index as compact human-readable text."""
    if "error" in idx:
        return f"[file-index] Error: {idx['error']}\n"

    out = [
        f"=== {idx['file']} ({idx['total_lines']} lines) ===\n",
    ]

    if idx.get("requires"):
        out.append(f"\nRequires ({len(idx['requires'])}):\n")
        for r in idx["requires"]:
            out.append(f"  {r}\n")

    if idx.get("types"):
        out.append(f"\nTypes ({len(idx['types'])}):\n")
        for t in idx["types"]:
            out.append(f"  L{t['line']:4d}: type {t['name']}\n")

    if idx.get("ops"):
        out.append(f"\nOps/Preds ({len(idx['ops'])}):\n")
        for o in idx["ops"]:
            out.append(f"  L{o['line']:4d}: {o['kind']} {o['name']}\n")

    if idx.get("axioms"):
        out.append(f"\nAxioms ({len(idx['axioms'])}):\n")
        for a in idx["axioms"]:
            out.append(f"  L{a['line']:4d}: axiom {a['name']}\n")

    if idx.get("modules"):
        out.append(f"\nModules ({len(idx['modules'])}):\n")
        for m in idx["modules"]:
            loc = " [section]" if m.get("in_section") else ""
            out.append(f"  L{m['line']:4d}: {m['kind']} {m['name']}{loc}\n")

    if idx.get("clones"):
        out.append(f"\nClones ({len(idx['clones'])}):\n")
        for c in idx["clones"]:
            out.append(f"  L{c['line']:4d}: clone {c['from']} as {c['name']}\n")

    lemmas = idx.get("all_lemmas", [])
    if lemmas:
        top_count = len(idx.get("top_level_lemmas", []))
        sec_count = len(idx.get("section_lemmas", []))
        out.append(
            f"\nLemmas/Equiv/Hoare ({len(lemmas)} total: "
            f"{top_count} top-level, {sec_count} in sections):\n"
        )
        for l in lemmas:
            loc = " [section]" if l["location"] == "in_section" else ""
            out.append(f"  L{l['line']:4d}: {l['kind']} {l['name']}{loc}\n")

    return "".join(out)


def _common_prefix_len(a: str, b: str) -> int:
    """Return length of the longest common prefix of two strings."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def check_lemma(file_path: Path, lemma_name: str) -> dict:
    """Check whether a lemma name exists in an .ec file.

    Returns a dict with:
      exists        — True if lemma_name is declared in the file
      lemma_info    — {name, kind, location, line} if found, else None
      close_matches — list of {name, kind, line} for similar names
      all_names     — flat list of all lemma/equiv/hoare/phoare names in file
    """
    idx = index_ec_file(file_path)
    if "error" in idx:
        return {"error": idx["error"], "exists": False, "lemma_info": None,
                "close_matches": [], "all_names": []}

    all_lemmas = idx.get("all_lemmas", [])
    all_names = [l["name"] for l in all_lemmas]

    # Exact match
    exact = [l for l in all_lemmas if l["name"] == lemma_name]
    if exact:
        return {"exists": True, "lemma_info": exact[0],
                "close_matches": [], "all_names": all_names}

    # Close matches: case-insensitive substring or shared prefix >= 4 chars
    lower = lemma_name.lower()
    close = []
    for l in all_lemmas:
        n = l["name"].lower()
        if lower in n or n in lower or _common_prefix_len(lower, n) >= 4:
            close.append({"name": l["name"], "kind": l["kind"], "line": l["line"]})

    return {"exists": False, "lemma_info": None,
            "close_matches": close, "all_names": all_names}


def format_check_lemma(result: dict, lemma_name: str, file_name: str) -> str:
    """Format check_lemma result as human-readable text."""
    if "error" in result:
        return f"[check-lemma] Error reading {file_name}: {result['error']}\n"
    if result["exists"]:
        info = result["lemma_info"]
        return (
            f"[check-lemma] OK: '{lemma_name}' found in {file_name} "
            f"(L{info['line']}: {info['kind']}, {info['location']})\n"
        )
    lines = [f"[check-lemma] NOT FOUND: '{lemma_name}' is not declared in {file_name}.\n"]
    if result["close_matches"]:
        lines.append(f"  Close matches ({len(result['close_matches'])}):\n")
        for m in result["close_matches"]:
            lines.append(f"    L{m['line']:4d}: {m['kind']} {m['name']}\n")
    else:
        total = len(result["all_names"])
        lines.append(f"  File has {total} lemma(s)/equiv(s)/hoare(s). "
                     "Use -file-index to list all.\n")
    return "".join(lines)


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print(f"Usage: {_sys.argv[0]} <file.ec> [--json] [--check-lemma NAME]")
        _sys.exit(1)
    fp = Path(_sys.argv[1])
    if "--check-lemma" in _sys.argv:
        idx2 = _sys.argv.index("--check-lemma")
        if idx2 + 1 >= len(_sys.argv):
            print("Usage: --check-lemma requires a lemma name")
            _sys.exit(1)
        name = _sys.argv[idx2 + 1]
        res = check_lemma(fp, name)
        if "--json" in _sys.argv:
            print(json.dumps(res, indent=2))
        else:
            print(format_check_lemma(res, name, fp.name), end="")
        _sys.exit(0 if res.get("exists") else 1)
    as_json = "--json" in _sys.argv
    idx = index_ec_file(fp)
    if as_json:
        print(json.dumps(idx, indent=2))
    else:
        print(format_index(idx), end="")
