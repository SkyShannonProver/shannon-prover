#!/usr/bin/env python3
"""Offline builder for the EC stdlib lemma index.

Scans `easycrypt-src/theories/` for lemma declarations, extracts each
lemma's name, full statement, and the polymorphic ops it mentions, and
writes a JSON index that the online lookup can use without re-scanning
the stdlib at every query.

Usage (one-time, or after stdlib update):
    python3 core/easycrypt/build_lemma_index.py

Output: `core/easycrypt/lemma_index.json`

Architecture:
- This script is OFFLINE. It runs once per stdlib version and the JSON
  is committed alongside the source. Online code (`ec_lemma_lookup.py`)
  loads the JSON in ~10ms and queries it in microseconds.
- We use lightweight regex parsing rather than a full EC parser. This
  catches the >95% of lemmas that follow standard form; rare exotic
  declarations are skipped quietly.
- Coverage: `theories/datatypes/`, `theories/algebra/`, `theories/
  distributions/`, `theories/structure/`. Skip `theories/crypto/` and
  `theories/encryption/` which are high-level and less universally
  reusable.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterator

# ── Configuration ──
ROOT = Path(__file__).resolve().parents[3]
THEORY_ROOT = ROOT / "easycrypt-src" / "theories"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "lemma_index.json"

# Subdirs we index. Datatypes is the high-priority coverage (the
# ChaChaPoly step2_2 trace burned 32 errors on List ops). Algebra and
# distributions are the next-most-cited stdlib categories. Crypto /
# encryption / looping are high-level; agents rarely need their lemmas
# at the proof-tactic level.
INDEXED_SUBDIRS = [
    "datatypes",
    "algebra",
    "distributions",
    "structure",
    "core",
    "prelude",
    "analysis",
]

# Identifier tokens we DON'T treat as polymorphic ops (they're keywords,
# logical connectives, common variable names, type names). Keeping this
# list lean — false positives in ops-extraction are mostly harmless
# (just create extra index entries for terms that nobody'll lookup).
_NON_OP_TOKENS = frozenset({
    # EC keywords / constructors
    "forall", "exists", "fun", "let", "in", "if", "then", "else",
    "lemma", "axiom", "op", "pred", "type", "module", "theory",
    "proc", "var", "return", "while", "abstract", "section",
    "True", "False", "true", "false",
    "Some", "None",
    # Logical
    "and", "or", "not",
    # Common type names / generic vars (NOT lemma ops)
    "int", "real", "bool", "unit", "list", "option", "distr",
    # Common variables in lemma statements
    "x", "y", "z", "n", "m", "k", "i", "j", "a", "b", "c", "d",
    "s", "t", "p", "q", "r", "f", "g", "h", "P", "Q", "S", "T",
    "x0", "x1", "x2", "y0", "y1", "y2", "z0", "z1", "z2",
})


# ── Regex tooling ──

# Match `lemma NAME` or `axiom NAME` — `local lemma`, `inductive lemma`,
# etc. are also captured. Skip `hint` / `op` / `pred` etc.
_LEMMA_HEAD = re.compile(
    r"^(?P<prefix>(?:local|abstract)?\s*)"
    r"(?P<kind>lemma|axiom)\s+"
    r"(?P<name>[A-Za-z_][\w']*)"
    r"(?P<rest>.*)$",
    re.MULTILINE,
)

# After the head, the rest of the lemma until the first top-level `.`.
# We need to handle:
#   - Multi-line continuations (`/\` at end of line)
#   - Periods inside `.proof` shouldn't terminate (proofs come after)
#   - Periods inside string/list/notation aren't a concern in stdlib
# Simplest reliable approach: scan forward token-by-token until we
# reach `.\n` (period followed by newline or whitespace+newline) at
# brace-depth zero.

_THEORY_OPEN = re.compile(
    r"^(?:abstract\s+|local\s+)?theory\s+(?P<name>[A-Za-z_]\w*)\s*\.\s*$",
    re.MULTILINE,
)
_THEORY_CLOSE = re.compile(
    r"^end\s+(?P<name>[A-Za-z_]\w*)\s*\.\s*$",
    re.MULTILINE,
)


def _scan_lemmas(content: str, file_rel: str) -> Iterator[dict]:
    """Yield {name, statement, theory_path, ops} for each lemma in ``content``.

    Theory tracking: maintain a stack of currently-open theory names so
    a lemma `foo` declared inside `theory T1 ... theory T2 ... end T2`
    gets recorded as `T1.T2.foo` (matching how EC qualifies it from
    outside).
    """
    theory_stack: list[str] = []
    pos = 0
    n = len(content)

    while pos < n:
        # Find next interesting token: theory open, theory close, or
        # lemma head. We do this by scanning line-by-line; cheap and
        # robust.
        next_newline = content.find("\n", pos)
        if next_newline == -1:
            next_newline = n
        line = content[pos:next_newline]
        line_start = pos
        pos = next_newline + 1

        stripped = line.strip()
        if not stripped or stripped.startswith("(*"):
            continue

        # Theory open
        m = _THEORY_OPEN.match(line)
        if m:
            theory_stack.append(m.group("name"))
            continue
        # Theory close
        m = _THEORY_CLOSE.match(line)
        if m:
            if theory_stack and theory_stack[-1] == m.group("name"):
                theory_stack.pop()
            continue

        # Lemma / axiom head
        m = _LEMMA_HEAD.match(line)
        if not m:
            continue
        name = m.group("name")
        kind = m.group("kind")
        # Statement starts with `rest` from this line, continues until
        # we hit a `.` at end of a line (allowing whitespace).
        stmt_parts: list[str] = [m.group("rest").rstrip()]
        # Already see the terminator on this same line?
        if stmt_parts[-1].rstrip().endswith("."):
            full_stmt = stmt_parts[-1].rstrip().rstrip(".")
        else:
            scan = pos
            while scan < n:
                eol = content.find("\n", scan)
                if eol == -1:
                    eol = n
                cont = content[scan:eol]
                stmt_parts.append(cont.rstrip())
                # Terminator: line ends with `.` (after rstrip), AND
                # not a `..` (range notation) or `.0` (qualified id).
                stripped_cont = cont.rstrip()
                if (stripped_cont.endswith(".")
                        and not stripped_cont.endswith("..")):
                    scan = eol + 1
                    break
                scan = eol + 1
            else:
                # Reached EOF without `.` — probably truncated. Skip.
                continue
            pos = scan
            full_stmt = "\n".join(stmt_parts).rstrip().rstrip(".")

        # Skip if statement is empty or has no `:` (malformed)
        if ":" not in full_stmt:
            continue

        # Extract op references from the statement. Use a permissive
        # identifier regex, then filter out the non-op token set above.
        # Also strip type-variable bindings (`['a 'b]`) and quantifier
        # bindings (`(x : t)`) — we want the ops, not the bound vars.
        ops = _extract_ops(full_stmt)

        # Compute the qualified name path. EC qualifies as
        # `Theory1.Theory2.lemma_name`, but for stdlib lookup the bare
        # `lemma_name` is what agents type. Store both.
        qualified = ".".join(theory_stack + [name]) if theory_stack else name

        yield {
            "name": name,
            "qualified": qualified,
            "kind": kind,
            "statement": full_stmt.strip(),
            "file": file_rel,
            "theory_path": list(theory_stack),
            "ops": sorted(ops),
        }


_IDENT_RE = re.compile(r"\b([A-Za-z_][\w']*)\b")
_TYPE_BIND_RE = re.compile(r"\[\s*(?:'[\w]+\s*)+\]")
_QUANT_BIND_RE = re.compile(
    r"\(\s*[A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*\s*:\s*[^()]*?\s*\)"
)


def _extract_ops(stmt: str) -> set[str]:
    """Return the set of operator-like identifiers mentioned in the
    lemma statement. We strip type-variable bindings and quantifier
    arg-name lists first so `(x : 'a)`-style binders don't pollute the
    result. Then drop EC keywords and very-short common variable names
    (``x``, ``n``, ``s``, ...).

    This is intentionally over-inclusive — false positives mean the op
    appears in some other lemma's index entry, which still surfaces a
    relevant signature.
    """
    # Strip type-var brackets `['a 'b]`
    stmt = _TYPE_BIND_RE.sub(" ", stmt)
    # Strip quantifier binders `(x : t)` / `(x y : t)` — but ONLY a
    # single level, not nested expressions. The regex is conservative;
    # leftover bound-var names are filtered by _NON_OP_TOKENS below.
    stmt = _QUANT_BIND_RE.sub(" ", stmt)
    candidates = set(_IDENT_RE.findall(stmt))
    return {c for c in candidates
            if c not in _NON_OP_TOKENS
            and not (len(c) == 1 and c.islower())
            and not c.isdigit()}


# ── Driver ──

def build() -> dict:
    """Walk indexed subdirs, extract lemmas, return the index dict."""
    print(f"[index] scanning {THEORY_ROOT}", file=sys.stderr)
    if not THEORY_ROOT.exists():
        sys.exit(f"theories root not found: {THEORY_ROOT}")

    lemmas: list[dict] = []
    files_scanned = 0
    for sub in INDEXED_SUBDIRS:
        sub_path = THEORY_ROOT / sub
        if not sub_path.exists():
            print(f"[index] skip {sub} (not found)", file=sys.stderr)
            continue
        for ec_file in sorted(sub_path.glob("*.ec")):
            try:
                content = ec_file.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print(f"[index] skip {ec_file.name}: {e}", file=sys.stderr)
                continue
            file_rel = str(ec_file.relative_to(ROOT))
            n_before = len(lemmas)
            lemmas.extend(_scan_lemmas(content, file_rel))
            files_scanned += 1
            print(f"[index] {file_rel}: +{len(lemmas)-n_before} lemmas",
                  file=sys.stderr)

    # Build the inverse index: op → list[lemma_id]
    op_to_lemmas: dict[str, list[int]] = {}
    for idx, lem in enumerate(lemmas):
        for op in lem["ops"]:
            op_to_lemmas.setdefault(op, []).append(idx)

    return {
        "version": 1,
        "stdlib_root": str(THEORY_ROOT.relative_to(ROOT)),
        "indexed_subdirs": INDEXED_SUBDIRS,
        "files_scanned": files_scanned,
        "n_lemmas": len(lemmas),
        "n_ops": len(op_to_lemmas),
        "lemmas": lemmas,
        "op_to_lemmas": op_to_lemmas,
    }


def main() -> int:
    index = build()
    OUTPUT_PATH.write_text(
        json.dumps(index, separators=(",", ":")),
        encoding="utf-8",
    )
    size_kb = OUTPUT_PATH.stat().st_size // 1024
    print(
        f"[index] wrote {OUTPUT_PATH.name}: "
        f"{index['n_lemmas']} lemmas, {index['n_ops']} ops, "
        f"{size_kb} KB",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
