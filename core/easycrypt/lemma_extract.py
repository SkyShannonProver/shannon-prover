#!/usr/bin/env python3
"""Extract a section-local lemma into a standalone .ec file for interactive proving.

When a lemma is inside a `section ... end section` block, session_cli can't
prove it interactively (tactics are appended outside the section). This module
extracts everything needed into a standalone file with all proof bodies
replaced by `admit.` (so they don't need why3/smt to process), except the
target lemma whose proof is left open.

Usage:
    python3 -m core.easycrypt.lemma_extract FILE LEMMA [-o OUTPUT]

Usage with session_cli:
    python3 core/easycrypt/session_cli.py -d .ec_session -start \\
      -f file.ec -I include_dir -lemma LEMMA
"""
from __future__ import annotations

import argparse
import re
import sys
from bisect import bisect_right
from pathlib import Path

from core.easycrypt.lemma_decls import DECLARATION_KEYWORDS, lemma_declarations
from core.easycrypt.proof_syntax import inline_proof
from core.easycrypt.proof_text import comment_spans, easycrypt_code, strip_comments


_PROOF_SENTENCE_RE = re.compile(r"proof\s*\.(?!\S)")


def _enclosing_block_closers(lines: list[str]) -> list[str]:
    """Balance lexical source framing after truncation; EC verifies the result.

    Keep sections and theories in one stack: closing only the innermost
    section before its surrounding theory can leave outer sections pending.
    Clone substitutions (``theory T <- ...``) do not open a block.
    """
    stack: list[tuple[str, str]] = []
    for line in strip_comments("\n".join(lines)).splitlines():
        stripped = line.strip()
        if match := re.fullmatch(r"section(?:\s+(\w+))?\s*\.", stripped):
            stack.append(("section", match.group(1) or ""))
        elif match := re.fullmatch(r"(?:abstract\s+)?theory\s+(\w+)\s*\.", stripped):
            stack.append(("theory", match.group(1)))
        elif re.fullmatch(r"end\s+section(?:\s+\w+)?\s*\.", stripped):
            if stack and stack[-1][0] == "section":
                stack.pop()
        elif match := re.fullmatch(r"end\s+(\w+)\s*\.", stripped):
            if stack and stack[-1] == ("theory", match.group(1)):
                stack.pop()
    return [(f"end section {name}." if name else "end section.")
            if kind == "section" else f"end {name}."
            for kind, name in reversed(stack)]


def _close_previous_statement_line(result: list[str]) -> None:
    """Ensure the most recent emitted declaration line ends with `.`."""
    for j in range(len(result) - 1, -1, -1):
        if not result[j].strip():
            continue
        if not result[j].rstrip().endswith('.'):
            result[j] = result[j].rstrip() + '.'
        return


def _emit_admit_proof(result: list[str], indent: str = "") -> None:
    result.append(f"{indent}proof.")
    result.append(f"{indent}  admit.")
    result.append(f"{indent}qed.")


def _replace_proofs_with_admit(lines: list[str], keep_open_line: int | None = None,
                               keep_intact: range | None = None) -> list[str]:
    """Replace multi-line proof bodies with `admit.`, except the target's.

    Rules:
    - Single-line proofs like `proof. tactic. qed.` are left as-is
      (they're usually simple and don't need why3).
    - `realize name. body. qed.` blocks are left as-is (clone proof obligations).
    - Multi-line `proof. ... qed.` blocks get body replaced with `admit.`.
    - At keep_open_line: proof is left open (no admit, no qed) for session_cli.
    - Lines in keep_intact (the target's declaration and proof) are kept as-is.

    Structure is read from comment-masked lines, so text in a comment is
    never taken for a proof marker or a `by`. A line holding only comment is
    kept verbatim and changes no state: comments can hold commented-out
    lemmas, and rewriting their text could leave a comment unterminated. The
    rest of a comment goes with the line that opens it when that line is
    dropped or rewritten, so no closer is left without its opener.
    """
    text = "\n".join(lines)
    masked = strip_comments(text).split("\n")
    line_starts = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)
    opened_on: dict[int, int] = {}
    for start, end in comment_spans(text):
        first = bisect_right(line_starts, start) - 1
        for line in range(first + 1, bisect_right(line_starts, end - 1)):
            opened_on[line] = first
    kept: set[int] = set()
    result: list[str] = []

    def keep(index: int) -> None:
        result.append(lines[index])
        kept.add(index)

    in_proof = False
    in_lemma_stmt = False  # True when we've seen a lemma/equiv declaration but no proof. yet
    i = 0
    while i < len(lines):
        if keep_intact is not None and i in keep_intact:
            keep(i)
            i += 1
            continue
        stripped = masked[i].strip()
        if not stripped and lines[i].strip():
            if i not in opened_on or opened_on[i] in kept:
                keep(i)
            i += 1
            continue

        if not in_proof:
            # Check for standalone `by ...` line after a multi-line lemma statement
            # e.g.: lemma aux : ...\n  body\nby case b.
            if in_lemma_stmt and stripped.startswith('by ') and stripped.endswith('.'):
                in_lemma_stmt = False
                if 'smt' in stripped:
                    # Replace smt-dependent by-proof with admit
                    _close_previous_statement_line(result)
                    indent = re.match(r'^(\s*)', lines[i]).group(1)
                    _emit_admit_proof(result, indent)
                else:
                    # Keep simple by-proofs (by case, by auto, etc.)
                    keep(i)
                i += 1
                continue

            # Check for single-line proof (proof. ... qed. on the same line).
            # Opening the target keeps only the declaration/proof prefix; the
            # body and qed are removed just like a multi-line target proof.
            inline = inline_proof(lines[i], masked_source=masked[i])
            if inline is not None:
                in_lemma_stmt = False
                if i == keep_open_line:
                    result.append(inline.open_line(lines[i]))
                    i += 1
                    continue
                # Single-line proof — keep if no smt, replace if smt
                if 'smt' in stripped:
                    result.append(inline.open_line(lines[i]))
                    result.append("    admit.")
                    result.append("  qed.")
                else:
                    keep(i)
                i += 1
                continue

            # Check for start of multi-line proof block
            is_proof_start = (stripped == 'proof.' or
                              (stripped.endswith(' proof.') and 'qed.' not in stripped))

            if is_proof_start:
                in_lemma_stmt = False
                if i == keep_open_line:
                    # Target lemma — keep proof. line, skip body + qed, leave open
                    keep(i)
                    i += 1
                    while i < len(lines):
                        s = masked[i].strip()
                        if s == 'qed.' or s.startswith('qed.'):
                            i += 1  # skip qed
                            break
                        i += 1
                    continue
                # Other lemma — replace body with admit
                keep(i)  # keep proof. line
                result.append("    admit.")
                in_proof = True
                i += 1
                continue

            # Check for inline proof with smt on same line as lemma declaration
            if (re.match(rf'^\s*(local\s+)?(?:{DECLARATION_KEYWORDS}|axiom)\b', stripped) and
                    'by smt' in stripped and i != keep_open_line):
                in_lemma_stmt = False
                by = masked[i].find(' by ')
                before_by = (lines[i][:by] if by >= 0 else lines[i]).rstrip()
                if not before_by.endswith('.'):
                    before_by += '.'
                result.append(before_by)
                indent = re.match(r'^(\s*)', lines[i]).group(1)
                _emit_admit_proof(result, indent)
                i += 1
                continue

            # Track when we enter a lemma/equiv statement (may span multiple lines)
            if re.match(rf'^\s*(local\s+)?(?:{DECLARATION_KEYWORDS})\b', stripped):
                in_lemma_stmt = True
            elif in_lemma_stmt and stripped == '':
                # Blank line after lemma without proof — probably not a lemma continuation
                in_lemma_stmt = False

            # Not a proof line — keep as-is
            keep(i)
        else:
            # Inside a replaced proof body — skip until qed.
            if stripped == 'qed.' or stripped.startswith('qed.'):
                keep(i)  # keep qed.
                in_proof = False

        i += 1

    return result


def _line_of(text: str, offset: int) -> int:
    """0-based line of ``offset`` in ``text``."""
    return text.count("\n", 0, offset)


def extract_lemma(ec_file: Path, lemma_name: str, open_proof: bool = False,
                  verify_proof: bool = False,
                  decl_line: int | None = None) -> str:
    """Extract a lemma and its dependencies into a standalone .ec file.

    Args:
        ec_file: path to the .ec file
        lemma_name: name of the lemma/equiv to extract
        open_proof: if True, leave target proof open (for session_cli -f)
        verify_proof: if True, keep target declaration and proof intact and
            cut the file after the proof. Other proofs are replaced with
            admit. This allows verifying just this lemma without triggering
            SMT-dependent lemmas that appear later in the source file.
            Raises ValueError when the target's proof is not closed by
            `qed.` or a one-line `by`: EasyCrypt accepts a proof left open
            at the end of a file, so the extract would verify nothing.
        decl_line: 0-based line on which the declaration to extract starts.
            Required to disambiguate when ``lemma_name`` is declared more
            than once — the default takes the first declaration, which may
            not be the declaration the caller's write-back targeted. Raises
            ValueError if no declaration of ``lemma_name`` starts there.

    Returns:
        standalone .ec file content as a string
    """
    text = ec_file.read_text(encoding="utf-8")
    lines = text.split('\n')
    masked_lines = strip_comments(text).split('\n')

    # Find the target declaration and its own proof.
    declarations = lemma_declarations(text, lemma_name)
    if decl_line is not None:
        declaration = next(
            (d for d in declarations if _line_of(text, d.start) == decl_line), None,
        )
        if declaration is None:
            raise ValueError(
                f"decl_line {decl_line} does not declare '{lemma_name}' "
                f"in {ec_file}"
            )
    elif declarations:
        declaration = declarations[0]
    else:
        raise ValueError(f"Lemma '{lemma_name}' not found in {ec_file}")

    proof = declaration.proof
    if verify_proof and (proof is None or proof.kind == "open"):
        raise ValueError(
            f"Lemma '{lemma_name}' in {ec_file} has no proof closed by "
            "`qed.` or `by` to verify"
        )
    lemma_line = _line_of(text, declaration.start)
    statement_end = (
        _line_of(text, declaration.statement_end - 1)
        if declaration.statement_end is not None else len(lines) - 1
    )
    # "proof" is a block starting with a `proof.` sentence; "bare" is one
    # without it, such as `admit.` alone. `qed_line` is None when no `qed.`
    # closes the block.
    proof_kind = "none"
    proof_line = qed_line = opener = None
    if proof is not None:
        proof_line = _line_of(text, proof.start)
        if proof.kind == "by":
            proof_kind = "by"
            qed_line = statement_end
        else:
            opener = _PROOF_SENTENCE_RE.match(easycrypt_code(text[proof.start:proof.end]))
            proof_kind = "proof" if opener else "bare"
            qed_line = _line_of(text, proof.end - 1) if proof.kind == "qed" else None

    # Find the section containing this lemma (if any)
    section_start = None

    sections: list[tuple[int, int]] = []
    stack: list[int] = []
    for i, line in enumerate(masked_lines):
        stripped = line.strip()
        if re.match(r'^section\b', stripped):
            stack.append(i)
        elif re.match(r'^end\s+section\b', stripped):
            if stack:
                start = stack.pop()
                sections.append((start, i))

    for start, end in sections:
        if start < lemma_line < end:
            if section_start is None or start > section_start:
                section_start = start

    # Cut through the target's `proof.` when opening it, else through its
    # proof. Opening a `by` proof cuts the statement before `by`; the
    # statement is then closed and a `proof.` line added below, as for a
    # target without a `proof.` sentence.
    if open_proof and proof_kind == "proof":
        target_lines = lines[:proof_line + 1]
        # Drop the target's own tactics written after `proof.` on that line;
        # a one-line `proof. ... qed.` is opened by the rewrite below.
        column = proof.start + opener.end() - (text.rfind("\n", 0, proof.start) + 1)
        rest = masked_lines[proof_line][column:]
        if rest.strip() and inline_proof(lines[proof_line], masked_source=masked_lines[proof_line]) is None:
            target_lines[-1] = lines[proof_line][:column]
    elif open_proof and proof_kind == "by":
        column = proof.start - (text.rfind("\n", 0, proof.start) + 1)
        target_lines = lines[:proof_line] + [lines[proof_line][:column]]
        if not target_lines[-1].strip():
            target_lines.pop()
    elif not open_proof and qed_line is not None:
        target_lines = lines[:qed_line + 1]
    elif not open_proof and proof_line is not None:
        target_lines = lines[:proof_line + 1]
    else:
        target_lines = lines[:statement_end + 1]

    if section_start is not None:
        # Lemma is inside a section.
        # Include: everything before the section + section content up to the cut
        # Replace all proof bodies with admit, except target (left open or intact).
        taken = lines[:section_start]
        taken.append("section.")  # anonymous section (drop original name)
        taken.extend(target_lines[section_start + 1:])
    else:
        taken = list(target_lines)

    generated_keep_open_line = None
    if open_proof and proof_kind != "proof":
        _close_previous_statement_line(taken)
        generated_keep_open_line = len(taken)
        indent = re.match(r'^(\s*)', lines[lemma_line]).group(1)
        taken.append(f"{indent}proof.")
    if section_start is not None:
        taken.append("")
    if not open_proof:
        taken.extend(_enclosing_block_closers(taken))

    if verify_proof:
        result_lines = _replace_proofs_with_admit(
            taken, keep_intact=range(lemma_line, len(target_lines)),
        )
    else:
        keep_line = (
            proof_line
            if open_proof and proof_kind == "proof"
            else generated_keep_open_line
        )
        result_lines = _replace_proofs_with_admit(taken, keep_open_line=keep_line)

    return '\n'.join(result_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Extract a section-local lemma into a standalone .ec file"
    )
    parser.add_argument("file", help="Path to the .ec file")
    parser.add_argument("lemma", help="Name of the lemma to extract")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--open", action="store_true",
                        help="Leave proof open (no admit/qed) for session_cli use")
    parser.add_argument("--verify", action="store_true",
                        help="Keep target proof intact, replace others with admit. "
                             "Use for single-lemma verification without SMT-dependent "
                             "lemmas that appear later in the file.")
    args = parser.parse_args()

    ec_file = Path(args.file)
    if not ec_file.exists():
        sys.stderr.write(f"File not found: {args.file}\n")
        return 1

    try:
        result = extract_lemma(ec_file, args.lemma, open_proof=args.open,
                               verify_proof=args.verify)
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        sys.stderr.write(f"Wrote {args.output}\n")
    else:
        sys.stdout.write(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
