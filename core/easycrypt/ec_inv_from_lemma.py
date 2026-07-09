#!/usr/bin/env python3
"""Extract the invariant from a local equiv lemma for use in call (_: bad, Inv).

Given a lemma name like DDH1_G1_dec, finds its precondition in the source file
and formats it as a ready-to-use call template.

Usage (via session_cli):
    python3 core/easycrypt/session_cli.py -d .ec_session -inv-from-lemma DDH1_G1_dec
"""
from __future__ import annotations

import re
from pathlib import Path


def _find_lemma_block(text: str, lemma_name: str) -> tuple[int, int] | None:
    """Find the character span of a local equiv lemma declaration.

    Returns (start, end) indices of the lemma block (from 'local equiv ...' to 'qed.').
    """
    # Match: local equiv <name> [universal params...] :
    # Earlier pattern required `:` right after the name, missing equivs
    # with universal parameters like `local equiv H_equiv x y z:`
    # (oracle equivs with forall-bound slots EC can't always infer).
    # Audit 2026-04-29 caught it: agent runs an invariant lookup on the
    # local equiv name, gets "Lemma not found", and has to
    # fall back to manual signature reading. Allow zero or more
    # whitespace-separated identifier tokens between name and `:`.
    pattern = re.compile(
        rf'(?:local\s+)?equiv\s+{re.escape(lemma_name)}'
        rf'(?:\s+[A-Za-z_]\w*)*\s*:',
        re.MULTILINE
    )
    m = pattern.search(text)
    if not m:
        return None

    start = m.start()
    # Find 'qed.' or end of file after the start
    qed = text.find('qed.', start)
    end = qed + 4 if qed >= 0 else len(text)
    return start, end


def _extract_pre_post(block: str) -> tuple[str, str] | None:
    """Extract precondition and postcondition from an equiv lemma block.

    The structure is:  equiv Name : Proc1 ~ Proc2 : <pre> ==> <post>.
    Returns (pre_text, post_text) or None if not found.
    """
    # Find ':' after the procedure signatures (the one before the pre)
    # The structure is: equiv Name : Sig1 ~ Sig2 : PRE ==> POST.
    # We need the SECOND ':' (after the ~)
    colon_pos = block.find(':')  # first colon after 'equiv Name'
    if colon_pos < 0:
        return None

    # Find '~' — separates the two procedure signatures
    tilde_pos = block.find('~', colon_pos)
    if tilde_pos < 0:
        return None

    # Find the ':' after '~' — this separates sig2 from pre
    pre_colon = block.find(':', tilde_pos)
    if pre_colon < 0:
        return None

    # Find '==>' — separates pre from post
    arrow_pos = block.find('==>', pre_colon)
    if arrow_pos < 0:
        return None

    # Find the terminating '.' of the declaration (before 'proof.')
    proof_pos = block.find('proof.', arrow_pos)
    decl_end = proof_pos if proof_pos >= 0 else len(block)

    pre_text = block[pre_colon + 1: arrow_pos].strip()
    post_text = block[arrow_pos + 3: decl_end].strip().rstrip('.')

    return pre_text, post_text


def _extract_bad_event(pre_text: str) -> str | None:
    """Try to extract the bad event from the pre (e.g., '!G1.bad{2}' → 'G1.bad')."""
    # Look for patterns like !G1.bad{2} or !bad at the start of a conjunction
    m = re.search(r'!\s*([A-Za-z_][A-Za-z0-9_.]*(?:\{[12]\})?)\s*(?:/\\|$)', pre_text)
    if m:
        raw = m.group(1)
        # Remove {1}/{2} suffix for the event name
        return re.sub(r'\{[12]\}', '', raw)
    return None


def _build_invariant(pre_text: str) -> str:
    r"""Strip bad-event and arg-precondition clauses from pre to get the invariant.

    Input example:
        ( !G1.bad{2} /\ c{1} = ci{2} /\
              (G1.x{2} = ... /\ ...) /\ CCA.log{1} = G1.log{2} /\ ...)
    Output (the Inv part for 'call (_: G1.bad, Inv)'):
        (G1.x{2} = ... /\ ...) /\ CCA.log{1} = G1.log{2} /\ ...
    """
    # Flatten to single line for regex processing, preserving structure
    inv = ' '.join(pre_text.split())

    # Strip outer parentheses if the whole pre is wrapped: ( ... )
    inv = inv.strip()
    if inv.startswith('(') and inv.endswith(')'):
        # Only strip if the parens are the outermost wrapper (not part of a tuple)
        depth = 0
        all_wrapped = True
        for i, ch in enumerate(inv):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            if depth == 0 and i < len(inv) - 1:
                all_wrapped = False
                break
        if all_wrapped:
            inv = inv[1:-1].strip()

    # Remove leading !bad_event /\ clause (e.g., "!G1.bad{2} /\")
    inv = re.sub(
        r'^!\s*[A-Za-z_][A-Za-z0-9_.]*(?:\{[12]\})?\s*/\\\s*',
        '', inv
    ).strip()

    # Remove leading simple arg-equality clause (e.g., "c{1} = ci{2} /\")
    # Pattern: <ident>{N} = <ident>{N} /\ (with no nested structure)
    m = re.match(
        r'^[A-Za-z_][A-Za-z0-9_.]*\{[12]\}\s*=\s*[A-Za-z_][A-Za-z0-9_.]*\{[12]\}\s*/\\\s*',
        inv
    )
    if m:
        inv = inv[m.end():].strip()

    return inv


def extract_call_template(source_text: str, lemma_name: str) -> str:
    """Find a local equiv lemma and format it as a call (_: bad, Inv) template.

    Returns a formatted string showing:
      - The lemma's pre/post
      - The extracted bad event and invariant
      - A ready-to-paste call template
    """
    span = _find_lemma_block(source_text, lemma_name)
    if span is None:
        # Distinguish "name doesn't exist anywhere" from "name exists but
        # isn't an equiv". Earlier the latter case erroneously claimed
        # "not found", sending the agent off to grep / -search the
        # source file for a name that's literally there. Audit
        # 2026-04-29: PRG's `ge0_qP` (an op-as-axiom from
        # `op qP : { int | 0 <= qP } as ge0_qP.`) reported as
        # not-found despite being defined.
        import re as _re
        # Quick presence check: any declaration line referencing the name.
        decl_re = _re.compile(
            rf"\b(?:lemma|axiom|local lemma|local axiom|"
            rf"declare module|module|theory|op|pred)\s+"
            rf"{_re.escape(lemma_name)}\b"
        )
        # Also catch `as <name>.` (op subtype shorthand).
        as_re = _re.compile(rf"\bas\s+{_re.escape(lemma_name)}\b")
        if decl_re.search(source_text) or as_re.search(source_text):
            return (
                f"`{lemma_name}` exists in the context file but is NOT an "
                f"equiv lemma (`-inv-from-lemma` only extracts call "
                f"templates from `equiv` / `local equiv` declarations). "
                f"It looks like an axiom / op-subtype / module / theory "
                f"declaration. For the signature run `-sig {lemma_name}`; "
                f"for a regex search use `-search {lemma_name}`.\n"
            )
        return f"Lemma '{lemma_name}' not found in context file.\n"

    block = source_text[span[0]: span[1]]
    result = _extract_pre_post(block)
    if result is None:
        return f"Could not parse pre/post of lemma '{lemma_name}'.\n"

    pre_text, post_text = result
    bad_event = _extract_bad_event(pre_text) or "<bad_event>"
    inv = _build_invariant(pre_text)

    lines: list[str] = []
    lines.append(f"=== Invariant from '{lemma_name}' ===")
    lines.append("")
    lines.append("Full precondition:")
    for ln in pre_text.splitlines():
        lines.append(f"  {ln}")
    lines.append("")
    lines.append(f"Bad event:  {bad_event}")
    lines.append("")
    lines.append("Invariant (pre minus !bad and arg clause):")
    for ln in inv.splitlines():
        lines.append(f"  {ln}")
    lines.append("")
    lines.append("Ready-to-use call template:")
    lines.append(f"  call (_: {bad_event},")
    # Indent invariant for the call
    inv_lines = inv.splitlines()
    for i, ln in enumerate(inv_lines):
        if i == 0:
            lines.append(f"           {ln}")
        else:
            lines.append(f"           {ln}")
    lines.append(f"  ).")
    lines.append(f"  + by apply {lemma_name}.")
    lines.append("")
    lines.append("NOTE: Remove any side-annotation like {{2}} from invariant")
    lines.append("      when the same invariant is used for both call subgoals.")
    lines.append("")

    return "\n".join(lines)


def extract_from_context_file(session_dir: Path, lemma_name: str) -> str:
    """Load the session's context file and extract the invariant."""
    # Try extracted_*.ec first, then context.ec
    ctx_file = None
    for f in sorted(session_dir.glob("extracted_*.ec")):
        ctx_file = f
        break
    if ctx_file is None:
        ctx = session_dir / "context.ec"
        if ctx.exists():
            ctx_file = ctx

    if ctx_file is None:
        return "No context file found. Run -start -f <file.ec> first.\n"

    text = ctx_file.read_text(encoding="utf-8", errors="replace")
    return extract_call_template(text, lemma_name)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 ec_inv_from_lemma.py <file.ec> <lemma_name>")
        sys.exit(1)
    src = Path(sys.argv[1]).read_text()
    print(extract_call_template(src, sys.argv[2]))
