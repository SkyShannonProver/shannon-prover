"""Abstract-adversary call-site hint generator.

When a pRHL goal contains a procedure call to a module declared as
`declare module A <: Adversary.` (i.e., abstract — its body is unknown,
only its signature/type), the canonical pattern is:

    call (_: ={glob A}).
    call (_: ={glob A} ==> ={res, glob A}).
    call (_: true).

`AUTO-PIVOT-CALL-READY` covers NAMED oracle-equivalence lemmas; this
module covers the un-named case (no equiv lemma exists for an abstract
adversary's procedures, since they are module parameters).

This module is pure: it parses goal/source text and generates candidate
tactic strings. Daemon-verification and rec emission live in the hook
phase that consumes its output.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# Match a procedure call `<@ ModName.proc(args)` or `<@ Mod(arg).proc(args)`
# allowing whitespace variations and possible newlines inside args.
_CALL_RE = re.compile(
    r"<@\s+([A-Za-z_]\w*(?:\([^()]*\))?)\.([A-Za-z_]\w*)\s*\(",
)

# Match the OUTERMOST identifier in a possibly-functored module reference.
_OUTER_MOD_RE = re.compile(r"^([A-Za-z_]\w*)")

# Match `declare module M <: T` or `declare module M : T`.
# Some files use `<:` (subtype) and some use `:` (ascription). EC supports both.
_DECLARE_MOD_RE_TPL = (
    r"\bdeclare\s+module\s+{name}\b"
)


@dataclass(frozen=True)
class AbstractAdvCall:
    module: str
    proc: str


def extract_outer_module(call_text: str) -> str:
    """Given `Mod(Arg).foo` or `Mod.foo`, return outermost `Mod`."""
    m = _OUTER_MOD_RE.match(call_text)
    return m.group(1) if m else ""


def extract_call_sites(goal_text: str) -> list[AbstractAdvCall]:
    """Pull module/proc pairs from `<@ M.f(...)` and `<@ M(arg).f(...)`
    patterns appearing on either pRHL side. De-duplicates by
    (outermost-module, proc).
    """
    seen: set[tuple[str, str]] = set()
    out: list[AbstractAdvCall] = []
    for match in _CALL_RE.finditer(goal_text):
        mod_text, proc = match.group(1), match.group(2)
        outer = extract_outer_module(mod_text)
        if not outer or not proc:
            continue
        key = (outer, proc)
        if key in seen:
            continue
        seen.add(key)
        out.append(AbstractAdvCall(module=outer, proc=proc))
    return out


def is_declared_abstract(source_text: str, module_name: str) -> bool:
    """True iff `source_text` declares `declare module module_name`.

    Uses a word-boundary match so e.g. `declare module A2` is not picked
    up when looking for `A`.
    """
    if not module_name:
        return False
    pat = re.compile(_DECLARE_MOD_RE_TPL.format(name=re.escape(module_name)))
    return bool(pat.search(source_text))


def filter_abstract(
    calls: list[AbstractAdvCall], source_text: str,
) -> list[AbstractAdvCall]:
    """Drop call sites whose outermost module is NOT declared abstract."""
    return [
        c for c in calls
        if is_declared_abstract(source_text, c.module)
    ]


def canonical_inv_shapes(modules: list[str]) -> list[str]:
    """Canonical `Inv` strings for `call (_: Inv)` against abstract advs.

    Order is from most to least specific:
      1. `={glob A, glob B} ==> ={res, glob A, glob B}` (sim post)
      2. `={glob A, glob B}` (one-sided invariant only)
      3. `true` (degenerate; works only when post is already aligned)

    For multi-module call sites, all modules are listed in `glob`. When
    only one module is involved the list collapses.
    """
    if not modules:
        return []
    uniq: list[str] = []
    seen: set[str] = set()
    for m in modules:
        if m and m not in seen:
            seen.add(m)
            uniq.append(m)
    glob_args = ", ".join(f"glob {m}" for m in uniq)
    res_args = "res, " + ", ".join(f"glob {m}" for m in uniq)
    return [
        f"={{{glob_args}}} ==> ={{{res_args}}}",
        f"={{{glob_args}}}",
        "true",
    ]


def candidate_call_tactics(modules: list[str]) -> list[str]:
    """Return `call (_: <Inv>).` strings, one per canonical Inv shape."""
    return [f"call (_: {inv})." for inv in canonical_inv_shapes(modules)]


def detect_and_propose(
    goal_text: str, source_text: str,
) -> tuple[list[AbstractAdvCall], list[str]]:
    """End-to-end helper used by the hook phase.

    Returns ``(abstract_calls, candidate_tactics)``. ``candidate_tactics``
    is empty when no abstract adversary call site is present in the goal.
    """
    calls = filter_abstract(extract_call_sites(goal_text), source_text)
    if not calls:
        return [], []
    modules = [c.module for c in calls]
    return calls, candidate_call_tactics(modules)
