"""Static extractor for a CALLED procedure's body, resolving functor aliases.

At a `call (_: <inv>)` over a compound game procedure (e.g. `CPA_game(...).main()`
defined in an imported file), the agent needs to know what `main` *does* — which
oracles it calls, what state they touch — to write the invariant. The structured
view surfaces the goal but not the called procedure's body, so the agent would
otherwise read the source file (and trip the IO policy). This module surfaces the
body in-protocol instead.

Functor-alias aware: `module CPA_game(A,O) = CCA_game(A,O).` resolves to
`CCA_game`, whose `proc main` body is the real definition.
"""
from __future__ import annotations

import re

from core.easycrypt.analysis.ec_utils import matching_delimiter as _matching_delimiter


def _module_head(name: str) -> "re.Pattern[str]":
    return re.compile(
        r"\b(?:local\s+)?module\s+\(?\s*" + re.escape(name) + r"\b\s*"
        r"(?:\([^{}]*?\))?\s*"                                  # functor params
        r"(?::\s*[A-Za-z_][\w'.]*(?:\s*\([^{}]*?\))?\s*)?"      # result signature
        r"=\s*"
    )


_ALIAS_RHS = re.compile(r"^([A-Z][A-Za-z0-9_']*)\s*(\([^)]*\))?\s*\.")


def extract_called_proc_body(
    source_texts: "list[tuple[str, Any]]",
    module_name: str,
    proc_name: str,
    *,
    _depth: int = 0,
    _chain: "Optional[list[str]]" = None,
    max_chars: int = 1800,
) -> "Optional[dict[str, Any]]":
    """Find ``proc <proc_name>``'s body inside ``module <module_name>``.

    ``source_texts`` is a list of ``(text, label)``. Resolves functor aliases
    (``module X(..) = Y(..).``) up to a small depth. Returns
    ``{module, proc, alias_chain, source, body}`` or ``None`` if not found
    (e.g. the proc is brought in via ``include`` — best-effort, no body then).
    """
    chain = list(_chain or [])
    if _depth > 5 or module_name in chain:
        return None
    chain = chain + [module_name]
    head_re = _module_head(module_name)
    for text, label in source_texts:
        m = head_re.search(text)
        if not m:
            continue
        rest = text[m.end():]
        stripped = rest.lstrip()
        if stripped.startswith("{"):
            open_brace = m.end() + (len(rest) - len(stripped))
            close = _matching_delimiter(
                text, open_brace, "{", "}", skip_easycrypt_comments=True
            )
            if close < 0:
                continue
            mod_body = text[open_brace + 1:close]
            pm = re.search(
                r"\bproc\s+" + re.escape(proc_name) + r"\b[^={}]*=\s*\{", mod_body)
            if not pm:
                continue
            pbrace = mod_body.index("{", pm.start())
            pclose = _matching_delimiter(
                mod_body, pbrace, "{", "}", skip_easycrypt_comments=True
            )
            if pclose < 0:
                continue
            body = mod_body[pm.start():pclose + 1].strip()
            return {
                "module": module_name,
                "proc": proc_name,
                "alias_chain": chain,
                "source": str(label),
                "body": body[:max_chars],
                "truncated": len(body) > max_chars,
            }
        am = _ALIAS_RHS.match(stripped)
        if am:
            target = am.group(1)
            res = extract_called_proc_body(
                source_texts, target, proc_name,
                _depth=_depth + 1, _chain=chain, max_chars=max_chars)
            if res is not None:
                return res
    return None


_CALL_TARGET = re.compile(r"<@\s*([A-Z][A-Za-z0-9_']*)\b")


def called_module_proc(call_stmt: str) -> "Optional[tuple[str, str]]":
    """Parse ``(module, proc)`` from a pRHL call statement like
    ``b <@ CPA_game(<args>).main()`` (functor application + ``.proc``)."""
    m = _CALL_TARGET.search(call_stmt)
    if not m:
        return None
    module = m.group(1)
    # skip the balanced functor-arg parens after the module name, then read `.proc`
    i = m.end()
    n = len(call_stmt)
    while i < n and call_stmt[i] in " \t":
        i += 1
    if i < n and call_stmt[i] == "(":
        depth = 0
        while i < n:
            if call_stmt[i] == "(":
                depth += 1
            elif call_stmt[i] == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
    pm = re.match(r"\s*\.\s*([A-Za-z_][\w']*)", call_stmt[i:])
    if not pm:
        return None
    return module, pm.group(1)
