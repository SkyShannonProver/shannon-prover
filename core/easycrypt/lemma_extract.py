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
from pathlib import Path


DECL_KINDS_RE = r"lemma|equiv|hoare|phoare"


def _is_decl_start(stripped: str) -> bool:
    proof_decl = re.match(
        rf"^(?:local\s+)?(?:{DECL_KINDS_RE})\s+[A-Za-z_][\w']*(?:[\s:]|$)",
        stripped,
    )
    other_decl = re.match(
        r"^(?:local\s+)?(?:axiom|op|type|module|clone|section\b|end\s+section)",
        stripped,
    )
    return bool(proof_decl or other_decl)


def _find_target_proof(lines: list[str], lemma_line: int) -> dict[str, int | str | None]:
    """Find the proof form that belongs to the target declaration.

    EasyCrypt files in the workflow can mark an unproved lemma either as a
    normal proof block (`proof. admit. qed.`) or as a bare one-line proof
    (`admit.`).  The extractor must not keep scanning into the next lemma and
    mistake that lemma's `proof.` for the target proof start.
    """
    limit = min(lemma_line + 500, len(lines))
    statement_end = lemma_line

    for i in range(lemma_line, limit):
        stripped = lines[i].strip()

        if i > lemma_line and _is_decl_start(stripped):
            break

        if (
            stripped == 'proof.'
            or stripped.startswith('proof.')
            or (stripped.endswith(' proof.') and 'qed.' not in stripped)
        ):
            qed_line = None
            for j in range(i + 1, min(i + 500, len(lines))):
                s = lines[j].strip()
                if s == 'qed.' or s.startswith('qed.'):
                    qed_line = j
                    break
            return {
                "kind": "proof",
                "proof_line": i,
                "qed_line": qed_line,
                "statement_end": max(lemma_line, i - 1),
            }

        if i > lemma_line and stripped == 'admit.':
            return {
                "kind": "admit",
                "proof_line": i,
                "qed_line": i,
                "statement_end": max(lemma_line, i - 1),
            }

        if i > lemma_line and stripped.startswith('by ') and stripped.endswith('.'):
            return {
                "kind": "by",
                "proof_line": i,
                "qed_line": i,
                "statement_end": max(lemma_line, i - 1),
            }

        if stripped.endswith('.'):
            statement_end = i

    return {
        "kind": "none",
        "proof_line": None,
        "qed_line": None,
        "statement_end": statement_end,
    }


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
                               keep_intact_line: int | None = None) -> list[str]:
    """Replace multi-line proof bodies with `admit.`, except at keep_open_line/keep_intact_line.

    Rules:
    - Single-line proofs like `proof. tactic. qed.` are left as-is
      (they're usually simple and don't need why3).
    - `realize name. body. qed.` blocks are left as-is (clone proof obligations).
    - Multi-line `proof. ... qed.` blocks get body replaced with `admit.`.
    - At keep_open_line: proof is left open (no admit, no qed) for session_cli.
    - At keep_intact_line: entire proof block (proof. ... qed.) is kept as-is.
    """
    result: list[str] = []
    in_proof = False
    in_lemma_stmt = False  # True when we've seen a lemma/equiv declaration but no proof. yet
    comment_depth = 0  # nesting depth of (* ... *) comments; never transform inside one
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # Comment-aware guard: lines inside (or opening) a `(* ... *)` comment are
        # passed through verbatim. EasyCrypt comments can wrap commented-out lemmas
        # (e.g. `(* lemma foo. proof. ... qed. *)`); without this, the proof->admit
        # rewrite below would mangle them and drop the closing `*)`, producing an
        # unterminated comment that wedges the persistent EC reader (no prompt ever
        # emitted -> daemon read times out -> orphaned EC -> MANAGER WORKER STOP).
        if comment_depth > 0 or stripped.startswith('(*'):
            result.append(lines[i])
            comment_depth = max(0, comment_depth + lines[i].count('(*') - lines[i].count('*)'))
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
                    result.append(lines[i])
                i += 1
                continue

            # Check for single-line proof (proof. ... qed. on same line)
            if ('proof.' in stripped and 'qed.' in stripped and
                    i != keep_open_line and i != keep_intact_line):
                in_lemma_stmt = False
                # Single-line proof — keep if no smt, replace if smt
                if 'smt' in stripped:
                    result.append(lines[i].split('proof.')[0] + 'proof.')
                    result.append("    admit.")
                    result.append("  qed.")
                else:
                    result.append(lines[i])
                i += 1
                continue

            # Check for start of multi-line proof block
            is_proof_start = (stripped == 'proof.' or
                              (stripped.endswith(' proof.') and 'qed.' not in stripped))

            if is_proof_start:
                in_lemma_stmt = False
                if i == keep_open_line:
                    # Target lemma — keep proof. line, skip body + qed, leave open
                    result.append(lines[i])
                    i += 1
                    while i < len(lines):
                        s = lines[i].strip()
                        if s == 'qed.' or s.startswith('qed.'):
                            i += 1  # skip qed
                            break
                        i += 1
                    continue
                elif i == keep_intact_line:
                    # Target lemma — keep proof. AND body AND qed. all intact
                    result.append(lines[i])  # keep proof. line
                    i += 1
                    while i < len(lines):
                        result.append(lines[i])
                        s = lines[i].strip()
                        if s == 'qed.' or s.startswith('qed.'):
                            i += 1
                            break
                        i += 1
                    continue
                else:
                    # Other lemma — replace body with admit
                    result.append(lines[i])  # keep proof. line
                    result.append("    admit.")
                    in_proof = True
                    i += 1
                    continue

            # Check for inline proof with smt on same line as lemma declaration
            if (re.match(rf'^\s*(local\s+)?(?:{DECL_KINDS_RE}|axiom)\b', stripped) and
                    'by smt' in stripped and i != keep_open_line and i != keep_intact_line):
                in_lemma_stmt = False
                before_by = lines[i].split(' by ')[0].rstrip()
                if not before_by.endswith('.'):
                    before_by += '.'
                result.append(before_by)
                indent = re.match(r'^(\s*)', lines[i]).group(1)
                _emit_admit_proof(result, indent)
                i += 1
                continue

            # Track when we enter a lemma/equiv statement (may span multiple lines)
            if re.match(rf'^\s*(local\s+)?(?:{DECL_KINDS_RE})\b', stripped):
                in_lemma_stmt = True
            elif in_lemma_stmt and stripped == '':
                # Blank line after lemma without proof — probably not a lemma continuation
                in_lemma_stmt = False

            # Not a proof line — keep as-is
            result.append(lines[i])
        else:
            # Inside a replaced proof body — skip until qed.
            if stripped == 'qed.' or stripped.startswith('qed.'):
                result.append(lines[i])  # keep qed.
                in_proof = False

        i += 1

    return result


def extract_lemma(ec_file: Path, lemma_name: str, open_proof: bool = False,
                  verify_proof: bool = False,
                  decl_line: int | None = None) -> str:
    """Extract a lemma and its dependencies into a standalone .ec file.

    Args:
        ec_file: path to the .ec file
        lemma_name: name of the lemma/equiv to extract
        open_proof: if True, leave target proof open (for session_cli -f)
        verify_proof: if True, keep target proof intact and cut file after its qed.
            Other proofs are replaced with admit. This allows verifying just this
            lemma without triggering SMT-dependent lemmas that appear later in
            the source file.
        decl_line: 0-based line of the declaration to extract. Required to
            disambiguate when ``lemma_name`` is declared more than once —
            the default scan takes the FIRST match, which may not be the
            declaration the caller's write-back targeted. Raises ValueError
            if that line does not declare ``lemma_name``.

    Returns:
        standalone .ec file content as a string
    """
    text = ec_file.read_text(encoding="utf-8")
    lines = text.split('\n')

    # Find the target lemma
    lemma_line = None
    lemma_pat = re.compile(
        rf'^\s*(local\s+)?(?:{DECL_KINDS_RE})\s+{re.escape(lemma_name)}(?:[\s:]|$)'
    )
    if decl_line is not None:
        if 0 <= decl_line < len(lines) and lemma_pat.match(lines[decl_line]):
            lemma_line = decl_line
        else:
            raise ValueError(
                f"decl_line {decl_line} does not declare '{lemma_name}' "
                f"in {ec_file}"
            )
    else:
        for i, line in enumerate(lines):
            if lemma_pat.match(line):
                lemma_line = i
                break

    if lemma_line is None:
        raise ValueError(f"Lemma '{lemma_name}' not found in {ec_file}")

    proof_info = _find_target_proof(lines, lemma_line)
    proof_kind = str(proof_info["kind"])
    proof_line = proof_info["proof_line"]
    qed_line = proof_info["qed_line"]
    statement_end = int(proof_info["statement_end"] or lemma_line)

    # Find the section containing this lemma (if any)
    section_start = None
    section_end = None

    sections: list[tuple[int, int]] = []
    stack: list[int] = []
    for i, line in enumerate(lines):
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
                section_end = end

    if section_start is not None:
        # Lemma is inside a section.
        # Include: everything before the section + section content up to after qed of target
        # Replace all proof bodies with admit, except target (left open or intact).

        # Determine cut point: include up to the target's qed/proof marker.
        # Bare `admit.` / `by ...` proofs are converted to an open `proof.`
        # below when open_proof=True.
        generated_keep_open_line = None
        if open_proof:
            if proof_kind == "proof" and isinstance(proof_line, int):
                cut_line = proof_line + 1  # include proof. line
            else:
                cut_line = statement_end + 1
        elif isinstance(qed_line, int):
            cut_line = qed_line + 1
        elif isinstance(proof_line, int):
            cut_line = proof_line + 1
        else:
            cut_line = statement_end + 1

        # Take lines: everything before section + section header + section body up to cut
        taken = lines[:section_start]
        taken.append("section.")  # anonymous section (drop original name)
        taken.extend(lines[section_start + 1: cut_line])
        if open_proof and proof_kind != "proof":
            _close_previous_statement_line(taken)
            generated_keep_open_line = len(taken)
            indent = re.match(r'^(\s*)', lines[lemma_line]).group(1)
            taken.append(f"{indent}proof.")
        taken.append("")
        taken.append("end section.")

        # Close any open theory/module blocks that were opened before the section.
        # Scan the pre-section content for unmatched abstract theory / theory / module type.
        # A real theory opening ends with `.` after the name:
        #     theory Byte.
        #     abstract theory GenBlock.
        # A clone-with theory parameter substitution looks similar but uses `<-`:
        #     clone FinProdType as NonceCount with
        #       theory FT1 <- Nonce.MFinite.Support, theory FT2 <- C.FinType.
        #     clone import FinEager as FiniteRO with
        #       theory FinFrom <- NonceCount
        # The substitution form does NOT open a theory and must not be emitted
        # as `end FT1.` / `end FinFrom.` at file close time. Without this
        # distinction the extracted file fails with "active theory has name
        # `Top', not `FinFrom'" — observed in step1 Run 8 prune-verify
        # (2026-04-27) where extract added spurious `end FinFrom.` and
        # `end FT1.` after the legitimate `end Step1_2.`.
        _theory_open_re = re.compile(r'^(abstract\s+theory|theory)\s+(\w+)\s*\.\s*$')
        open_blocks: list[str] = []
        for line in lines[:section_start]:
            stripped = line.strip()
            m = _theory_open_re.match(stripped)
            if m:
                open_blocks.append(m.group(2))
            elif re.match(r'^end\s+(\w+)\s*\.', stripped):
                end_name = re.match(r'^end\s+(\w+)', stripped).group(1)
                if open_blocks and open_blocks[-1] == end_name:
                    open_blocks.pop()
        # Close in reverse order
        for block_name in reversed(open_blocks):
            taken.append(f"end {block_name}.")

        # Replace all proof bodies with admit, keeping target open or intact
        if verify_proof:
            result_lines = _replace_proofs_with_admit(
                taken,
                keep_intact_line=proof_line if isinstance(proof_line, int) else None,
            )
        else:
            keep_line = (
                proof_line
                if open_proof and proof_kind == "proof" and isinstance(proof_line, int)
                else generated_keep_open_line
            )
            result_lines = _replace_proofs_with_admit(taken, keep_open_line=keep_line)

        return '\n'.join(result_lines)
    else:
        # Lemma is NOT in a section
        generated_keep_open_line = None
        if open_proof:
            if proof_kind == "proof" and isinstance(proof_line, int):
                cut_line = proof_line + 1
            else:
                cut_line = statement_end + 1
        else:
            if isinstance(qed_line, int):
                cut_line = qed_line + 1
            elif isinstance(proof_line, int):
                cut_line = proof_line + 1
            else:
                cut_line = statement_end + 1

        taken = lines[:cut_line]
        if open_proof and proof_kind != "proof":
            _close_previous_statement_line(taken)
            generated_keep_open_line = len(taken)
            indent = re.match(r'^(\s*)', lines[lemma_line]).group(1)
            taken.append(f"{indent}proof.")

        if verify_proof:
            result_lines = _replace_proofs_with_admit(
                taken,
                keep_intact_line=proof_line if isinstance(proof_line, int) else None,
            )
        else:
            keep_line = (
                proof_line
                if open_proof and proof_kind == "proof" and isinstance(proof_line, int)
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
