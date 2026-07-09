#!/usr/bin/env python3
r"""Scan a module for bad-event mutations (`<bad_var> <- true`).

Given a module name, locate it in the session's context file and
report every assignment that flips a flag-shaped variable to `true`
within the module's procedures. Intended for bad-event reductions
(IND-CCA up-to-bad, UFCMA, MLKEM decap-failure, ...) where the
proof's invariant must include `!<module>.<bad>{N}` clauses and the
agent needs to know exactly where each clause might be falsified.

Heuristic: a "bad-event mutation" is any line of the form
    <ident> <- true;
within a `proc` body. We do NOT restrict to vars literally named
"bad" because real proofs use `bad1`, `bad2`, `cbad2`, `forged`,
`abort`, etc. — and over-matching is preferable to under-matching
(missing one is silent; an extra non-bad flag is obvious from
context). Caller (the agent) makes the final classification.

Usage (via session_cli):
    python3 core/easycrypt/session_cli.py -d .ec_session -bad-trace UFCMA

Output:
    === Bad-event mutations in module `UFCMA` ===

    proc init:
      (no flag mutations)

    proc enc:
      line 142:  bad1 <- true;        (under `if (n \in lenc) { ... }`)
      line 156:  bad2 <- true;        (under `if ((n,c) \notin log) { ... }`)
      line 159:  cbad2 <- cbad2 + 1;  (counter mutation, NOT a flag set)

    proc dec:
      (no flag mutations)

If the module isn't a `module` (e.g., it's a theory or a module type),
or the module is parameterized (a functor) and not directly defined,
return a hint pointing at `-where MODULE`.
"""
from __future__ import annotations

import re
from pathlib import Path


# Match the START of a module/local module definition.
# Captures the module name. Permits optional functor parameters.
# Examples matched:
#   module UFCMA = { ... }
#   module UFCMA(A : Adv) = { ... }
#   local module BNR(O : OBO_OR) = { ... }
# NOT matched:
#   module type ORACLE = { ... }   (we want concrete modules)
#   abstract module ABS_M = { ... } (no body)
_MODULE_HEADER = re.compile(
    r"^\s*(?:local\s+)?module\s+(?!type\b)(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*\(.*?\))?"     # optional functor params
    r"(?:\s*:\s*\S+)?"     # optional ascription "M : SIG"
    r"\s*=\s*\{",
    re.MULTILINE,
)

# Procedure header inside a module body.
# Matches `proc init() = { ... }`, `proc enc(p : plain) : cipher = { ... }`,
# `proc enc = ChaChaPolyEnc.enc` (alias — has no body, skip).
_PROC_HEADER = re.compile(
    r"^\s*proc\s+(?P<name>[A-Za-z_]\w*)\s*"
    r"(?:\(.*?\))?"        # optional formal args
    r"(?:\s*:\s*[^=]+?)?"  # optional return type
    r"\s*=\s*(?P<body>\{|[A-Za-z_])",  # `{` for inline body, ident for alias
    re.MULTILINE,
)

# Flag-flip patterns. Real EC sources use two equivalent idioms:
#   (1) `bad <- true;`              — direct flip (under an outer `if`)
#   (2) `bad <- bad || <cond>;`     — disjunctive accumulation
# Both must be caught — chacha_poly's UFCMA uses (2), step4_1 audit
# 2026-04-30 found this when the v1 regex (only form 1) reported
# "no flag mutations" for UFCMA which clearly has bad1/bad2 vars.
# We allow optional `Mod.` qualification on the LHS (rare but legal,
# e.g. `Mem.bad`); deeper nesting is unusual and skipped.
_FLAG_FLIP_DIRECT = re.compile(
    r"^(?P<indent>\s*)(?P<lhs>[A-Za-z_]\w*(?:\.\w+)?)\s*<-\s*true\s*;",
)
_FLAG_FLIP_DISJ = re.compile(
    # EC syntax: both `||` (boolean OR in statements) and `\/` (the
    # Coq-style logical OR, common in older proofs / cramer-shoup
    # style) are accepted. Earlier versions of this regex only matched
    # `||` and missed cramer_shoup's `bad <- bad \/ (...)` pattern
    # entirely. Audit 2026-04-30: real-world test against
    # eval/examples/cramer-shoup/cramer_shoup.ec found `bad <- bad
    # \/ (a_ <> a^w /\ d = ...)` and reported "no flag mutations".
    r"^(?P<indent>\s*)(?P<lhs>[A-Za-z_]\w*(?:\.\w+)?)\s*<-\s*"
    r"(?P=lhs)\s*(?:\|\||\\/)\s*(?P<cond>[^;]+);",
)

# Counter increment pattern: `<ident> <- <ident> + 1;` — adjacent to
# flag flips in real proofs (e.g. UFCMA's `cbad2 <- cbad2 + 1;`),
# semantically NOT a bad-event flip but worth surfacing because the
# invariant often constrains the counter (`cbad2 = 0` implies bad2
# never fired). Reported as "counter mutation" to distinguish.
_COUNTER_INC = re.compile(
    r"^(?P<indent>\s*)(?P<lhs>[A-Za-z_]\w*(?:\.\w+)?)\s*<-\s*"
    r"(?P=lhs)\s*\+\s*\d+\s*;",
)


def _find_module_body(text: str, module_name: str) -> tuple[int, int] | None:
    """Locate the body span (after `=`, before matching `}`) of the
    named module. Returns (body_start_idx, body_end_idx) or None.

    Brace tracking is character-level and ignores braces inside
    string literals — EC sources don't use string-embedded braces in
    practice, so we don't bother with full lexing.
    """
    for m in _MODULE_HEADER.finditer(text):
        if m.group("name") != module_name:
            continue
        # The match ends just past `=\s*{`. Find the matching `}`.
        body_start = m.end() - 1  # at the opening `{`
        depth = 0
        for i in range(body_start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return body_start + 1, i
        # Unterminated body — give up.
        return None
    return None


def _split_proc_bodies(module_body: str, module_offset: int
                       ) -> list[tuple[str, int, int]]:
    """Within a module body, return [(proc_name, body_start, body_end), ...]
    for every `proc NAME ... = { ... }` declaration. body_start/end are
    absolute indices into the FULL source text (i.e. shifted by
    module_offset). Skips alias forms (`proc enc = OtherMod.enc;`)
    that have no inline body.
    """
    out: list[tuple[str, int, int]] = []
    for m in _PROC_HEADER.finditer(module_body):
        name = m.group("name")
        body_marker = m.group("body")
        if body_marker != "{":
            # Alias — no body to scan.
            continue
        # Find matching `}` from the `{`.
        body_start_local = m.end() - 1
        depth = 0
        body_end_local = -1
        for i in range(body_start_local, len(module_body)):
            ch = module_body[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    body_end_local = i
                    break
        if body_end_local < 0:
            continue
        out.append((
            name,
            module_offset + body_start_local + 1,  # past the `{`
            module_offset + body_end_local,
        ))
    return out


def _line_number_at(text: str, offset: int) -> int:
    """1-indexed line number for a character offset."""
    return text.count("\n", 0, offset) + 1


def _scan_proc_for_mutations(text: str, body_start: int, body_end: int
                             ) -> list[tuple[int, str, str, str]]:
    """Within a procedure body span, return [(line_no, kind, lhs, snippet)]
    where kind is "flag" or "counter" and snippet is the trimmed
    source line. Surrounding `if (...)` context is detected by
    walking back to the nearest unclosed `if` on the same indent
    level — a heuristic, fine for typical EC proc shapes.
    """
    body = text[body_start:body_end]
    matches: list[tuple[int, str, str, str]] = []
    line_start = body_start
    for raw_line in body.splitlines(keepends=True):
        line_text = raw_line.rstrip("\n")
        # Order matters: disjunctive form `bad <- bad || cond` must be
        # tested BEFORE the counter form (which also has self-RHS but
        # with `+`); both have similar shapes but different semantics.
        fm_direct = _FLAG_FLIP_DIRECT.match(line_text)
        fm_disj = _FLAG_FLIP_DISJ.match(line_text)
        cm = _COUNTER_INC.match(line_text)
        if fm_direct:
            ln_no = _line_number_at(text, line_start)
            matches.append((
                ln_no, "flag", fm_direct.group("lhs"), line_text.strip(),
            ))
        elif fm_disj:
            ln_no = _line_number_at(text, line_start)
            matches.append((
                ln_no, "flag", fm_disj.group("lhs"), line_text.strip(),
            ))
        elif cm:
            ln_no = _line_number_at(text, line_start)
            matches.append((
                ln_no, "counter", cm.group("lhs"), line_text.strip(),
            ))
        line_start += len(raw_line)
    return matches


def _surrounding_if(text: str, mutation_line: int) -> str:
    """Best-effort: walk back from the mutation line to the nearest
    `if (...)` on a strictly-lower indent level; return its condition
    text (trimmed). Returns "" if no clear if-guard is found within
    a reasonable lookback window (40 lines).
    """
    lines = text.splitlines()
    if mutation_line < 1 or mutation_line > len(lines):
        return ""
    target = lines[mutation_line - 1]
    target_indent = len(target) - len(target.lstrip())
    for i in range(mutation_line - 2, max(-1, mutation_line - 42), -1):
        ln = lines[i]
        if not ln.strip():
            continue
        indent = len(ln) - len(ln.lstrip())
        if indent >= target_indent:
            continue
        # Strict-lower indent. Is it an `if (...)`?
        m = re.match(r"\s*if\s*\((?P<cond>.+?)\)\s*\{?\s*$", ln)
        if m:
            return m.group("cond").strip()
        # Hit an enclosing non-if block — stop searching.
        return ""
    return ""


def trace_module(source_text: str, module_name: str) -> str:
    """Top-level entry. Returns the formatted report as a string."""
    span = _find_module_body(source_text, module_name)
    if span is None:
        # Distinguish "module exists but as a different kind" from
        # "name doesn't exist at all" — match P20 audit guidance.
        type_re = re.compile(
            rf"^\s*module\s+type\s+{re.escape(module_name)}\b",
            re.MULTILINE,
        )
        abstract_re = re.compile(
            rf"^\s*declare\s+module\s+{re.escape(module_name)}\b",
            re.MULTILINE,
        )
        if type_re.search(source_text):
            return (
                f"`{module_name}` is a `module type` (signature only — has "
                f"no procedure bodies to scan). Bad-event tracking applies "
                f"to concrete `module` declarations. For the abstract type "
                f"members run `-members {module_name}`.\n"
            )
        if abstract_re.search(source_text):
            return (
                f"`{module_name}` is a `declare module` (abstract / "
                f"adversary-supplied — no body in this file). Its bad "
                f"events come from how it's instantiated downstream; "
                f"bad-trace can't see them. Look at the call sites that "
                f"close over `{module_name}`.\n"
            )
        return (
            f"Module `{module_name}` not found in context file. "
            f"For an exact name lookup run `-where {module_name}`.\n"
        )

    body_start, body_end = span
    module_body = source_text[body_start:body_end]
    procs = _split_proc_bodies(module_body, body_start)

    if not procs:
        return (
            f"=== Bad-event mutations in module `{module_name}` ===\n"
            f"\n"
            f"Module has no inline procedure bodies (likely all-alias "
            f"or all-abstract). Nothing to scan.\n"
        )

    lines_out: list[str] = []
    lines_out.append(f"=== Bad-event mutations in module `{module_name}` ===")
    lines_out.append("")

    total_flips = 0
    for proc_name, p_start, p_end in procs:
        lines_out.append(f"proc {proc_name}:")
        muts = _scan_proc_for_mutations(source_text, p_start, p_end)
        if not muts:
            lines_out.append("  (no flag mutations)")
            lines_out.append("")
            continue
        for ln_no, kind, lhs, snippet in muts:
            if kind == "flag":
                cond = _surrounding_if(source_text, ln_no)
                guard_note = f"  (under `if ({cond})`)" if cond else ""
                lines_out.append(
                    f"  line {ln_no}:  {snippet}{guard_note}"
                )
                total_flips += 1
            else:  # counter
                lines_out.append(
                    f"  line {ln_no}:  {snippet}     "
                    f"(counter mutation, NOT a flag set)"
                )
        lines_out.append("")

    if total_flips == 0:
        lines_out.append(
            "No `<x> <- true` flips found across procs. "
            f"Module `{module_name}` either has no bad-event tracking, "
            "or its bad-events are set indirectly (via a procedure call). "
            "If the latter, scan the called modules with `-bad-trace` too."
        )
        lines_out.append("")
    else:
        lines_out.append(
            f"Summary: {total_flips} flag flip(s) across "
            f"{len(procs)} proc(s). For each flip, the invariant must "
            f"either (a) imply the guarding condition is false in the "
            f"adversary's reachable states, or (b) explicitly track the "
            f"flag in a `!<module>.<flag>{{N}}` conjunct."
        )
        lines_out.append("")

    return "\n".join(lines_out)


def trace_from_session(session_dir: Path, module_name: str) -> str:
    """Load the session's context file and run trace_module."""
    ctx_file = None
    for f in sorted(session_dir.glob("extracted_*.ec")):
        ctx_file = f
        break
    if ctx_file is None:
        ctx = session_dir / "context.ec"
        if ctx.exists():
            ctx_file = ctx

    if ctx_file is None:
        return "No context file found. Run `-start -f <file.ec>` first.\n"

    text = ctx_file.read_text(encoding="utf-8", errors="replace")
    return trace_module(text, module_name)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 ec_bad_trace.py <file.ec> <module_name>")
        sys.exit(1)
    src = Path(sys.argv[1]).read_text()
    print(trace_module(src, sys.argv[2]))
