"""Shared lexical guards for candidate proof text, not proof acceptance."""

import re
from collections.abc import Iterator
from pathlib import Path


# Operator-section forms that EasyCrypt's lexer (ecLexer.mll `main`) prefers,
# by longest match, over the two-character comment opener: `(*)`, `( * )` and
# `(*=)` are operators and `(*+*)` is skipped, so none of them opens a comment.
# The first form is the skipped one; it wins ties by rule order, and since the
# lexer discards it like a blank it is masked like a comment.
_OPCHAR = r"[=<>+\-*/\\%&^|:#$]"
_ICHAR = r"[A-Za-z0-9_']"
_BLANK = r"[ \t\r]*"
_BINOP = rf"(?:{_OPCHAR}+|`{_OPCHAR}+`|\\{_ICHAR}+)"
_PAREN_FORMS = (
    re.compile(rf"\(\*{_BINOP}\*\)"),
    re.compile(rf"\({_BLANK}{_BINOP}{_BLANK}\)"),
    re.compile(rf"\({_BLANK}'[0-9]+{_BLANK}\)"),
    re.compile(rf"\({_BLANK}%(?:[a-z]{_ICHAR}*|_{_ICHAR}+){_BLANK}\)"),
)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")

# EasyCrypt accepts a file in which these leave obligations unchecked: the
# `admit` tactic and the `admitted` proof end close goals as axioms, `exit`
# stops processing with success, and `abort` abandons a proof so that another
# statement can follow under the same name. `pragma Proofs:weak` and
# `Proofs:report` keep failed SMT calls from failing the file, and
# `pragma reset` or `restart` discards the declarations before it.
_UNCHECKED_KEYWORDS = frozenset({"admit", "admitted", "exit", "abort"})
_FILE_WIDE_KEYWORDS = frozenset({"exit"})
_UNCHECKED_PRAGMA_RE = re.compile(
    r"(?<![A-Za-z0-9_'])pragma\s+(?:[+-]\s*)?"
    r"(?:Proofs\s*:\s*(weak|report)|(reset|restart))(?![A-Za-z0-9_'])"
)


def _paren_form_length(text: str, index: int) -> int:
    """Length of the operator form at ``index`` that beats a comment opener."""

    best = 0
    for form in _PAREN_FORMS:
        match = form.match(text, index)
        if match is not None and match.end() - index > best:
            best = match.end() - index
    return best


def _blank(text: str) -> str:
    return "".join("\n" if char == "\n" else " " for char in text)


def _mask(text: str, *, strings: bool) -> tuple[str, list[tuple[int, int]], bool]:
    """Blank comments (and, if asked, string literals) as EasyCrypt reads them.

    The result has the same length as ``text``, so positions carry over, and
    a comment becomes blanks rather than vanishing, so the tokens on either
    side stay separate as they do for EasyCrypt. Also returns the span of
    each outermost comment and whether one is still open at the end.
    """

    out: list[str] = []
    comments: list[tuple[int, int]] = []
    open_comment = False
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("(*", index):
            opener = 3 if text[index + 2:index + 3] in {"&", "^"} else 2
            operator = _paren_form_length(text, index)
            if operator > opener:
                form = text[index:index + operator]
                skipped = _PAREN_FORMS[0].match(text, index)
                discarded = skipped is not None and skipped.end() - index == operator
                out.append(_blank(form) if discarded else form)
                index += operator
                continue
            end = index + 2
            depth = 1
            while end < length and depth:
                if text.startswith("(*", end):
                    depth += 1
                    end += 2
                elif text.startswith("*)", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            open_comment = depth > 0
            comments.append((index, end))
            out.append(_blank(text[index:end]))
            index = end
            continue
        if text[index] == '"':
            end = index + 1
            while end < length and text[end] != '"':
                end += 2 if text[end] == "\\" else 1
            end = min(end + 1, length)
            literal = text[index:end]
            out.append(_blank(literal) if strings else literal)
            index = end
            continue
        out.append(text[index])
        index += 1
    return "".join(out), comments, open_comment


def strip_comments(text: str) -> str:
    """Blank the comments EasyCrypt ignores, keeping positions and strings."""
    return _mask(text, strings=False)[0]


def comment_spans(text: str) -> list[tuple[int, int]]:
    """The ``(start, end)`` offsets of each outermost comment in ``text``."""
    return _mask(text, strings=False)[1]


def easycrypt_code(text: str) -> str:
    """Blank comments and string literals, keeping every other character."""
    return _mask(text, strings=True)[0]


def has_unterminated_comment(text: str) -> bool:
    """Whether a comment in ``text`` is still open at its end.

    EasyCrypt rejects such a file; the masks above blank it to the end.
    """
    return _mask(text, strings=False)[2]


def sentence_ends(text: str, code: str | None = None) -> Iterator[int]:
    """Yield the offset just past each sentence-final dot of ``text``.

    EasyCrypt's FINAL token is a ``.`` followed by a blank, a newline or the
    end of the input. A dot in a comment or a string literal ends nothing,
    and a dot followed by a comment opener is not final either, because the
    lexer looks at the raw character after it. Two dots are the longer
    ``..`` token, so the second dot of ``[1 .. 2]`` is not final. ``code`` is
    ``easycrypt_code(text)`` when the caller already has it.
    """
    if code is None:
        code = easycrypt_code(text)
    length = len(text)
    index = 0
    while index < length:
        if code[index] == ".":
            if text.startswith("..", index):
                index += 2
                continue
            if index + 1 == length or text[index + 1] in " \t\n\r":
                yield index + 1
        index += 1


def split_ec_commands(text: str) -> list[str]:
    """Split EC source text into a list of complete statements.

    A statement ends at a sentence-final dot (``sentence_ends``). This
    matches what EC's toplevel treats as one command in ``-emacs`` mode.

    Each statement keeps the blanks after its dot and one newline. Blank
    lines and comment-only lines are included with the next command so
    offsets stay consistent; text after the last final dot is returned
    stripped.
    """
    out: list[str] = []
    start = 0
    length = len(text)
    for end in sentence_ends(text):
        while end < length and text[end] in " \t":
            end += 1
        if end < length and text[end] == "\n":
            end += 1
        out.append(text[start:end])
        start = end
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def split_tactic_chain(text: str) -> list[str]:
    """The tactics of a chain request, one per EasyCrypt sentence.

    Each is stripped. Text after the last sentence end is a final tactic
    and, like a single submitted tactic, gets the dot it lacks. The backend
    commits these and the manager binds its request to them, so both read
    the chain through this function.
    """
    tactics = [command.strip() for command in split_ec_commands(text)]
    tactics = [tactic for tactic in tactics if tactic]
    if tactics and not tactics[-1].endswith("."):
        tactics[-1] += "."
    return tactics


# Sentence heads whose effect EasyCrypt's ``undo <level>.`` does not revert or
# which move the level themselves. ``pragma`` covers both pragmas and options
# (``pragma +x`` / ``pragma -x`` / ``pragma x = n``): EasyCrypt runs them on
# its global state, outside the scope stack that ``undo`` pops
# (ecCommands.ml ``process_pragma`` / ``process_option``). ``undo`` and the
# session-ending commands change the level or the process themselves.
_UNDO_UNSAFE_HEADS = frozenset({
    "pragma", "undo", "exit", "quit", "drop", "abort", "restart",
})
_SENTENCE_HEAD_RE = re.compile(r"[A-Za-z_]*")


def undo_unsafe_sentence(transaction: str) -> str:
    """The first sentence of ``transaction`` that ``undo`` cannot take back.

    Returns ``""`` when every sentence only changes EasyCrypt's scope stack.
    The test is lexical on purpose: it names commands by their leading
    keyword, as EasyCrypt's parser does, and it errs towards refusing.
    """
    for sentence in split_ec_commands(transaction):
        code = strip_comments(sentence).strip()
        if not code:
            continue
        head = _SENTENCE_HEAD_RE.match(code.lstrip("+-*{} \t\r\n")).group(0)
        if head.lower() in _UNDO_UNSAFE_HEADS:
            return code
    return ""


def _keywords(code: str, keywords: frozenset[str]) -> list[str]:
    return [match.group(0) for match in _TOKEN_RE.finditer(code)
            if match.group(0) in keywords]


def _pragmas(code: str) -> list[str]:
    return [
        f"pragma Proofs:{match.group(1)}" if match.group(1)
        else f"pragma {match.group(2)}"
        for match in _UNCHECKED_PRAGMA_RE.finditer(code)
    ]


def unchecked_proof_constructs(text: str) -> list[str]:
    """Return the constructs with which EasyCrypt accepts unchecked goals."""
    code = easycrypt_code(text)
    return _keywords(code, _UNCHECKED_KEYWORDS) + _pragmas(code)


def file_wide_unchecked_constructs(text: str) -> list[str]:
    """Return the constructs that weaken checking for a whole file.

    Unlike `admit` in another lemma's proof, these affect every proof after
    them, so a file that contains one cannot certify any lemma.
    """
    code = easycrypt_code(text)
    return _keywords(code, _FILE_WIDE_KEYWORDS) + _pragmas(code)


def tactics_contain_admit(tactics: list[str]) -> bool:
    """Whether any candidate tactic closes or skips a goal without proof."""
    return any(unchecked_proof_constructs(tactic) for tactic in tactics)


def discard_sibling_eco(source: Path) -> None:
    """Remove the `.eco` cache next to ``source`` before checking it.

    EasyCrypt exits 0 without checking a file whose `.eco` records matching
    digests, and `-no-eco` only stops it from writing one. Anyone who can
    write next to the file could forge such a cache.
    """
    Path(source).with_suffix(".eco").unlink(missing_ok=True)
