"""Mechanical ``call (_: ={glob ...})`` invariant skeleton.

When the proof frontier is an abstract-adversary ``call (_: <inv>)`` obligation
(reached e.g. after ``byequiv; proc; inline *``), the relational invariant the
EasyCrypt ``call`` rule needs almost always *begins* with
``={glob <shared oracle modules>}`` — the global state of the abstract
scheme/oracle modules both games drive must stay synchronized across the call.

This pass is the *mechanical* half of that invariant, per the framework
principle "the compiler synthesizes mechanical structure; the agent explores the
semantic proof strategy":

  * It enumerates the abstract modules ``declare module X <: T`` in scope.
  * It does NOT decide which modules belong in ``={glob ...}`` — it emits a
    daemon *probe plan* (singletons, then the union of whatever applies). The
    daemon gate in ``session_hook_phases`` keeps the **maximal accepted** subset.
    This automatically drops the adversary being called (its ``glob`` is
    forbidden in the invariant by the ``call`` rule — EC rejects it with a
    "module A can write A" restriction error), so no adversary-vs-oracle
    heuristic is needed.
  * It emits ONLY the ``={glob ...}`` frame. Semantic conjuncts (key/state
    correspondences, set-membership, win-implications) are intentionally left
    for the agent — they are not mechanically derivable.

No scheme, game, oracle, invariant, or module-name token is hard-coded; the
abstract modules are read from the loaded session source.
"""
from __future__ import annotations

from typing import Any
import re

# reuse the source-text iterator from the bridge frontend
from core.easycrypt.analysis.ec_pr_bridge_frontend import _session_source_texts


CALL_GLOB_INVARIANT_KIND = "call_glob_invariant_skeleton"

# ``declare module X <: BOUND`` — the abstract modules a section reduces over.
# BOUND is a (possibly clone-qualified) module-type name: dot-joined identifier
# segments, NOT ending in the statement-terminator dot or a ``{`` restriction.
_DECLARE_MODULE = re.compile(
    r"\bdeclare\s+module\s+(?P<name>[A-Z][A-Za-z0-9_']*)\s*<:\s*"
    r"(?P<bound>[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)"
)


def declared_abstract_modules(session_dir: Any) -> list[dict[str, str]]:
    """Abstract modules ``declare module X <: T`` in scope.

    De-duplicated by name (a nested section may re-declare the same name with
    tighter restrictions; the textual order is preserved for determinism).
    """
    out: "dict[str, dict[str, str]]" = {}
    order: list[str] = []
    for text, _path, _kind in _session_source_texts(session_dir):
        for m in _DECLARE_MODULE.finditer(text):
            name = m.group("name")
            if name not in out:
                order.append(name)
            out[name] = {"name": name, "bound": m.group("bound")}
    return [out[n] for n in order]


_MODULE_APP_HEAD = re.compile(r"[A-Z][A-Za-z0-9_']*\s*\(")


def glob_modules_from_goal(
    raw_goal: str, *, exclude: "set[str] | None" = None,
) -> list[dict[str, str]]:
    """Concrete shared modules threaded through the goal's call/proc module
    expressions (functor applications): ``Log(LRO)`` -> Log, LRO;
    ``ChaCha(CCRO(SplitD.RO_DOM(...)))`` -> ChaCha, CCRO, SplitD.RO_DOM, ...

    These are the modules whose glob a ``call (_: ={glob ...})`` frame must keep
    synchronized, and they are NOT ``declare module`` abstracts, so
    ``declared_abstract_modules`` misses them entirely. GENEROUS by design: every
    returned name is daemon-filtered downstream (``maximal_accepted_glob`` only keeps
    probe-accepted globs), so an over-captured non-module is probe-rejected and dropped
    and a false frame can never be surfaced. The called adversary roots are excluded up
    front (the call rule forbids ``={glob A}``)."""
    # local import: avoid cycle. The helpers moved to ec_pr_canonical when 73b1916a
    # trimmed ec_pr_elaborator's re-export wrappers; this caller was not repointed.
    from core.easycrypt.analysis.ec_pr_canonical import (
        application_root,
        matching_bracket,
        module_application_args as _module_application_args,
    )
    text = str(raw_goal or "")
    skip = {str(x) for x in (exclude or set())}
    names: list[str] = []
    seen: set[str] = set()

    def _flatten(expr: str) -> None:
        root = application_root(expr) or ""
        if root and root not in seen:
            seen.add(root)
            if root not in skip:
                names.append(root)
        for arg in _module_application_args(expr):
            a = arg.strip()
            if a:
                _flatten(a)

    covered_until = -1
    for m in _MODULE_APP_HEAD.finditer(text):
        head_start = m.start()
        if head_start <= covered_until:
            continue  # nested inside a top-level app already flattened by recursion
        open_idx = m.end() - 1
        close = matching_bracket(text, open_idx, "(", ")")
        if close <= open_idx:
            continue
        # absorb a leading dotted qualifier so e.g. SplitD.RO_DOM(...) keeps its prefix
        q = head_start
        while q > 0 and (text[q - 1].isalnum() or text[q - 1] in "_.'"):
            q -= 1
        _flatten(text[q:close + 1])
        covered_until = close
    return [{"name": n} for n in names]


def render_glob_invariant(names: "list[str]") -> str:
    """``={glob A, glob B}`` for an ordered list of module names (deduped)."""
    seen: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.append(n)
    if not seen:
        return ""
    return "={" + ", ".join(f"glob {n}" for n in seen) + "}"


def render_call_glob_tactic(names: "list[str]") -> str:
    """``call (_: ={glob A, glob B}).`` — empty string if no modules."""
    inv = render_glob_invariant(names)
    return f"call (_: {inv})." if inv else ""


def maximal_accepted_glob(
    modules: "list[dict[str, str]]",
    probe: "Any",
) -> "list[str]":
    """Maximal subset of ``modules`` whose ``call (_: ={glob subset})`` the
    daemon accepts at the current call obligation.

    ``probe(tactic: str) -> {"accepted": bool, "error": str}`` runs one daemon
    ``try_tactic`` (read-only). Algorithm:
      1. probe each singleton; keep the modules whose own ``={glob X}`` applies
         (this already drops the adversary being called — its ``={glob A}`` is
         rejected with a "module A can write A" restriction);
      2. probe the union of survivors; if rejected, drop the module(s) named in
         the restriction error and retry until accepted or down to a singleton.

    Returns the ordered accepted module names (possibly empty). Purely driven by
    daemon acceptance — no adversary/oracle heuristic, no name hard-coding.
    """
    names = [m.get("name", "") for m in modules if m.get("name")]
    accepted = [n for n in names if _ok(probe(render_call_glob_tactic([n])))]
    if len(accepted) <= 1:
        return accepted
    cur = list(accepted)
    for _ in range(len(cur) + 1):
        r = probe(render_call_glob_tactic(cur))
        if _ok(r):
            return cur
        err = str((r or {}).get("error") or "")
        offending = [n for n in cur
                     if re.search(rf"\bmodule\s+{re.escape(n)}\b", err)]
        if not offending:  # non-restriction rejection: shrink to make progress
            offending = [cur[-1]]
        cur = [n for n in cur if n not in offending]
        if len(cur) <= 1:
            return cur
    return cur


def _ok(result: "Any") -> bool:
    return bool(isinstance(result, dict) and result.get("accepted"))

