"""Shared lexical guards for candidate proof text, not proof acceptance."""

import re
from pathlib import Path


# Operator-section forms that EasyCrypt's lexer (ecLexer.mll `main`) prefers,
# by longest match, over the two-character comment opener: `(*)`, `( * )` and
# `(*=)` are operators and `(*+*)` is skipped, so none of them opens a comment.
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


def _mask(text: str, *, strings: bool) -> str:
    """Blank comments (and, if asked, string literals) as EasyCrypt reads them.

    The result has the same length as ``text``, so positions carry over, and
    a comment becomes blanks rather than vanishing, so the tokens on either
    side stay separate as they do for EasyCrypt.
    """

    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("(*", index):
            opener = 3 if text[index + 2:index + 3] in {"&", "^"} else 2
            operator = _paren_form_length(text, index)
            if operator > opener:
                out.append(text[index:index + operator])
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
    return "".join(out)


def strip_comments(text: str) -> str:
    """Blank the comments EasyCrypt ignores, keeping positions and strings."""
    return _mask(text, strings=False)


def easycrypt_code(text: str) -> str:
    """Blank comments and string literals, keeping every other character."""
    return _mask(text, strings=True)


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
