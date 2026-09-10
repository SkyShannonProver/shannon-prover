"""Replace every proved lemma/theorem/equiv/hoare proof body with ``admit``.

Pure text transform (re/pathlib only), matching the existing
``(* COMPLETE THIS *)`` convention; leaves already-admit proofs untouched.

Handles these proof forms:
  1. Multi-line ``proof. ... qed.``
  2. Single-line ``proof. tac. qed.``
  3. ``by`` short form: ``lemma foo : P by tac.``
  4. Clone/realize ``by`` clauses, including multi-line tactic bodies

Idempotent. Lives in ``core/easycrypt/`` (the lower layer) so that
eval-source preparation can use it without ``core`` importing ``workflow`` — the
prior layering inversion (audit re-audit §4.1).
"""

import re

from core.easycrypt.lemma_decls import mask_comments
from core.easycrypt.proof_syntax import inline_proof

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


_SOURCE_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z0-9_\']*|\.\.|[^\s]', re.DOTALL)


def _source_tokens(content: str):
    """Lexical offsets only: skip nested comments and keep strings opaque."""
    i = 0
    depth = 0
    while i < len(content):
        pair = content[i:i + 2]
        if pair == "(*":
            depth += 1
            i += 2
        elif depth:
            if pair == "*)":
                depth -= 1
                i += 2
            else:
                i += 1
        elif content[i].isspace():
            i += 1
        else:
            token = _SOURCE_TOKEN.match(content, i)
            assert token is not None
            if token.group() == '"':
                raise ValueError("Cannot strip proofs from an unterminated string")
            yield token.group(), token.start(), token.end()
            i = token.end()
    if depth:
        raise ValueError("Cannot strip proofs from an unterminated comment")


def _redact_by_clauses(content: str) -> tuple[str, int]:
    """Remove residual clone/realize tactics through their lexical boundary.

    EasyCrypt's FINAL token is a dot followed by whitespace/EOF; qualified
    names, strings and comments do not terminate a command (ecLexer.mll).
    Within a clone command, commas and proof/rename/remove delimit clauses only
    outside brackets (ecParser.mly: clone_lemma, theory_clone). This transform
    does not resolve declarations or certify tactics; native loading validates
    the prepared source. An incomplete boundary must fail source preparation.
    """
    replacements: list[tuple[int, int]] = []

    def collect(command: list[tuple[str, int, int]], complete: bool) -> None:
        words = [token[0] for token in command]
        first = 1 if words and words[0] in {"local", "global"} else 0
        if first >= len(words) or words[first] not in {"clone", "realize", "proof"}:
            return
        if words[first:first + 2] == ["proof", "."]:
            return
        clone = words[first] != "realize"
        in_proof = not clone or words[first] == "proof"
        body_start = None
        body_words: list[str] = []
        brackets: list[str] = []
        closing = {")": "(", "]": "[", "}": "{"}

        def finish(end: int) -> None:
            nonlocal body_start, body_words
            if body_start is not None:
                if not body_words:
                    raise ValueError("Cannot strip an empty by-proof body")
                if body_words != ["admit"]:
                    # Keep the whitespace separating the next clause/command.
                    end = body_start + len(content[body_start:end].rstrip())
                    replacements.append((body_start, end))
                body_start = None
                body_words = []

        for j in range(first + 1, len(command)):
            word, start, end = command[j]
            if not brackets:
                if complete and j == len(command) - 1:
                    finish(start)
                    continue
                if clone and word in {",", "proof", "rename", "remove"}:
                    finish(start)
                    if word != ",":
                        in_proof = word == "proof"
                    continue
                if in_proof and word == "by" and body_start is None:
                    body_start = end
                    continue
            if body_start is not None:
                body_words.append(word)
            if word in {"(", "[", "{"}:
                brackets.append(word)
            elif word in closing:
                if not brackets or brackets.pop() != closing[word]:
                    raise ValueError("Cannot strip a by-proof with unbalanced brackets")
        if body_start is not None or brackets or not complete:
            raise ValueError("Cannot strip an unterminated clone/realize proof command")

    command: list[tuple[str, int, int]] = []
    for token in _source_tokens(content):
        word, _, end = token
        command.append(token)
        if word == "." and (end == len(content) or content[end].isspace()):
            collect(command, complete=True)
            command = []
    if command:
        collect(command, complete=False)
    out = []
    previous = 0
    for start, end in replacements:
        out.extend((content[previous:start], " admit"))
        previous = end
    out.append(content[previous:])
    return "".join(out), len(replacements)


def _redact_residual_proof_text(content: str) -> tuple[str, int]:
    """Redact proof text outside lemma/equiv/hoare declarations.

    Clone realization obligations can appear as `realize foo by ...` or
    `realize foo. proof. ... qed.`. They are proof bodies too.

    All structure decisions ignore nested comments: the by-clause scan above
    uses lexical offsets; block scanning below uses offset-aligned masked text.
    Thus `proof.`/`qed.`/`by` inside `(* ... *)` comments are never
    treated as proof structure — a commented-out lemma must pass through
    byte-identical (a naive scan here previously swallowed the closing `*)`
    and unbalanced every comment after it; same bug class as the 2026-06
    context-builder wedge).
    """
    content, replaced = _redact_by_clauses(content)
    lines = content.splitlines(keepends=True)
    mlines = mask_comments(content).splitlines(keepends=True)
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        mline = mlines[i]
        stripped = mline.strip()
        if stripped.startswith("proof.") and inline_proof(
            line,
            masked_source=mline,
        ) is not None:
            indent = re.match(r"^\s*", line).group(0)
            if re.search(r"proof\.\s*admit\.\s*qed\.", stripped):
                out.append(line)
            else:
                out.extend(_make_admit_block(indent))
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

        # Check for single-line `proof. body. qed.` using the shared lexical
        # recognizer so extraction and stripping agree on this proof form.
        if inline_proof(proof_line, masked_source=mlines[i]) is not None:
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
