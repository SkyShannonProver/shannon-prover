"""Replace every proved lemma/theorem/equiv/hoare proof body with ``admit``.

Pure text transform (re/pathlib only), matching the existing
``(* COMPLETE THIS *)`` convention; leaves already-admit proofs untouched.

Handles three proof forms:
  1. Multi-line ``proof. ... qed.``
  2. Single-line ``proof. tac. qed.``
  3. ``by`` short form: ``lemma foo : P by tac.``

Idempotent. Lives in ``core/easycrypt/`` (the lower layer) so that
``narrative_safety`` can use it without ``core`` importing ``workflow`` — the
prior layering inversion (audit re-audit §4.1). ``workflow.tools.replace_proofs_with_admit``
re-exports these for its CLI.
"""

import re

from core.easycrypt.lemma_decls import mask_comments

_DECL_RE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<kind>(?:local\s+)?(?:lemma|theorem|equiv|hoare|phoare))\b"
)


def _make_admit_block(indent: str) -> list[str]:
    return [
        f"{indent}proof.\n",
        f"{indent}(* COMPLETE THIS *)\n",
        f"{indent}  admit.\n",
        f"{indent}qed.\n",
    ]


def _is_admit_only_proof(body_text: str) -> bool:
    non_boilerplate = re.sub(
        r"(proof\.|qed\.|admit\.|\(\*.*?\*\))",
        "",
        body_text,
        flags=re.DOTALL,
    ).strip()
    return "admit." in body_text and not non_boilerplate


def _redact_residual_proof_text(content: str) -> tuple[str, int]:
    """Redact proof text outside lemma/equiv/hoare declarations.

    Clone realization obligations can appear as `realize foo by ...` or
    `realize foo. proof. ... qed.`. They are proof bodies too.

    All *decisions* run on comment-masked text (offset-aligned with the
    original), so `proof.`/`qed.`/`by` inside `(* ... *)` comments are never
    treated as proof structure — a commented-out lemma must pass through
    byte-identical (a naive scan here previously swallowed the closing `*)`
    and unbalanced every comment after it; same bug class as the 2026-06
    context-builder wedge).
    """
    lines = content.splitlines(keepends=True)
    mlines = mask_comments(content).splitlines(keepends=True)
    out: list[str] = []
    replaced = 0
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        mline = mlines[i]
        stripped = mline.strip()
        by_line = re.match(r"^(?P<indent>\s*)(?:realize|proof)\b.*\bby\b", mline)
        if by_line and not stripped.startswith("proof."):
            by_idx = mline.find(" by ")
            if by_idx < 0:
                by_idx = mline.find("\tby ")
            prefix = line[:by_idx].rstrip() if by_idx >= 0 else line.rstrip()
            suffix = ".\n" if mline.rstrip().endswith(".") else "\n"
            out.append(f"{prefix} by admit{suffix}")
            replaced += 1
            i += 1
            continue

        if stripped == "proof.":
            indent = re.match(r"^\s*", line).group(0)
            proof_start = i
            i += 1
            qed_line = None
            while i < n:
                if re.match(r"^\s*qed\s*\.", mlines[i]):
                    qed_line = i
                    break
                i += 1
            if qed_line is None:
                out.extend(lines[proof_start:])
                break
            body = lines[proof_start:qed_line + 1]
            body_text = "".join(mlines[proof_start:qed_line + 1])
            if _is_admit_only_proof(body_text):
                out.extend(body)
            else:
                out.extend(_make_admit_block(indent))
                replaced += 1
            i = qed_line + 1
            continue

        out.append(line)
        i += 1

    return "".join(out), replaced


def replace_proofs(content: str) -> tuple[str, int]:
    """Return (new_content, n_replaced).

    Structure detection (declarations, signature ends, `proof.`/`qed.`/`by`)
    runs on comment-masked text; emitted lines come from the original, so
    commented-out proof blocks pass through byte-identical.
    """
    lines = content.splitlines(keepends=True)
    mlines = mask_comments(content).splitlines(keepends=True)
    out: list[str] = []
    n_replaced = 0
    i = 0
    n = len(lines)

    while i < n:
        m = _DECL_RE.match(mlines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue

        indent = m.group("indent")
        decl_start = i

        # Walk until end of signature: a line that terminates with a bare `.`
        # (not inside braces/brackets). Simplest heuristic: count '{[(' vs '}])'
        # and stop on first line ending with `.` at depth 0.
        depth = 0
        sig_end = None
        in_by_short = False  # did the signature terminate with `by ...`?
        while i < n:
            cur = mlines[i]
            # Track bracket depth to avoid being fooled by `.` inside types
            # like `op foo = fun (x:int) => x * 2.` — unlikely in lemma
            # signatures but safe to handle.
            for ch in cur:
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth = max(0, depth - 1)
            stripped = cur.rstrip("\n").rstrip()
            # `by <tac>.` on the same line as the signature is a short-form proof
            if re.search(r"\bby\b", cur) and depth == 0 and stripped.endswith("."):
                sig_end = i
                in_by_short = True
                break
            # Signature line ending with `.`
            if depth == 0 and stripped.endswith("."):
                sig_end = i
                break
            i += 1
        if sig_end is None:
            # Unterminated — emit remainder as-is
            out.extend(lines[decl_start:])
            break

        decl_lines = lines[decl_start : sig_end + 1]

        if in_by_short:
            # Truncate the `by ...` part and emit multi-line admit
            by_match = re.search(r"^(?P<pre>.*?)\s+by\b", mlines[sig_end], re.DOTALL)
            pre = decl_lines[-1][:by_match.end("pre")].rstrip() if by_match else ""
            if pre:
                if not pre.endswith("."):
                    pre += "."
                decl_lines[-1] = pre + "\n"
            else:
                # Multi-line short proofs can place the proof-only `by ...`
                # on its own line. Drop that line and terminate the statement.
                decl_lines = decl_lines[:-1]
                for j in range(len(decl_lines) - 1, -1, -1):
                    if mlines[decl_start + j].strip():
                        stmt = decl_lines[j].rstrip("\n").rstrip()
                        if not stmt.endswith("."):
                            stmt += "."
                        decl_lines[j] = stmt + "\n"
                        break
            out.extend(decl_lines)
            out.extend(_make_admit_block(indent))
            n_replaced += 1
            i = sig_end + 1
            continue

        out.extend(decl_lines)
        i = sig_end + 1

        # Find the proof block start (could be `proof.` on its own line, or
        # `proof. ... qed.` inline on the next non-blank content line).
        # Skip blank lines and comment-only lines (masked to whitespace).
        while i < n and mlines[i].strip() == "":
            out.append(lines[i])
            i += 1
        if i >= n:
            break

        proof_line = lines[i]
        stripped = mlines[i].strip()

        if not stripped.startswith("proof."):
            # Not a proof — some other top-level thing after a declaration.
            # (e.g. `axiom foo : P.` which has no proof body). Skip.
            continue

        # Check for single-line `proof. body. qed.`
        if stripped.endswith("qed.") and "qed." in stripped[6:]:
            # Already admit form? (masked text: comments are whitespace)
            if re.search(r"proof\.\s*admit\.\s*qed\.", stripped):
                out.append(proof_line)
                i += 1
                continue
            out.extend(_make_admit_block(indent))
            n_replaced += 1
            i += 1
            continue

        # Multi-line proof block: find matching qed.
        proof_start = i
        i += 1
        qed_line = None
        while i < n:
            if re.match(r"^\s*qed\s*\.", mlines[i]):
                qed_line = i
                break
            i += 1
        if qed_line is None:
            # Unterminated proof; emit the rest unchanged
            out.extend(lines[proof_start:])
            break

        body = lines[proof_start : qed_line + 1]
        body_text = "".join(mlines[proof_start : qed_line + 1])
        # Already-admit detection: contains `admit.` and nothing else substantive
        if _is_admit_only_proof(body_text):
            # Keep as-is
            out.extend(body)
            i = qed_line + 1
            continue

        # Replace with admit block
        out.extend(_make_admit_block(indent))
        n_replaced += 1
        i = qed_line + 1

    redacted, residual = _redact_residual_proof_text("".join(out))
    return redacted, n_replaced + residual
