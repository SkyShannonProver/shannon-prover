#!/usr/bin/env python3
"""Pr-expression functor path diff — pre-chewed module-tree structure
for the prover.

(This module was previously named ``ec_structural_diff``. Renamed to
disambiguate from ``ec_state_diff`` — different axis: state_diff compares
pre-tactic vs post-tactic GOAL state across time; pr_path_diff compares
LHS vs RHS module trees inside a single STATEMENT.)

Layer 2 (functor path diff): given a lemma statement with two Pr[M(...).proc]
expressions (or an equiv[L.p ~ R.q] statement), walk the two module
expressions as parse trees and report where they differ. Pre-computed
from the lemma statement alone — ready before the prover commits any tactic.

Layer 1 (program alignment): given a parsed pRHL goal's left/right
statement lists, align them row by row and mark each pair
IDENTICAL / DIFFERENT / SIDE-ONLY. Ready as soon as EC emits a pRHL goal
(typically after `proc. inline *.`).

Both produce markdown-ish text blocks intended for direct embedding in the
prover prompt (Layer 2) or tactic response (Layer 1).

Design motivation:
  LLM attention is finite. Forcing the prover to mentally β-reduce
  `RealOrcls(OChaChaPoly(IFinRO)).Oh_Enc` every time it reads the goal
  burns attention on parsing, not reasoning. Pre-computing the diff
  frees that attention for strategy selection.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from core.easycrypt.analysis.ec_pr_canonical import (
    format_module_expr as _format_module_expr,
    parse_module_expr as _parse_module_expr,
    parse_pr_terms as _parse_pr_terms,
)
from core.easycrypt.analysis.ec_procedure_ref import (
    split_procedure_module_and_name as _split_procedure_module_and_name,
)


# ---------------------------------------------------------------------------
# Module expression parser (handles nested parens, comma-separated args)
# ---------------------------------------------------------------------------


def parse_module_expr(expr: str) -> dict:
    """Parse a module expression into a tree.

    >>> parse_module_expr("M")
    {'name': 'M', 'args': []}
    >>> parse_module_expr("RealOrcls(OChaChaPoly(IFinRO))")
    {'name': 'RealOrcls', 'args': [{'name': 'OChaChaPoly', 'args': [{'name': 'IFinRO', 'args': []}]}]}
    >>> parse_module_expr("CCA_game(A, RealOrcls(M))")
    {'name': 'CCA_game', 'args': [{'name': 'A', 'args': []}, {'name': 'RealOrcls', 'args': [{'name': 'M', 'args': []}]}]}
    """
    return _parse_module_expr(expr)


def format_module_expr(tree: dict) -> str:
    """Render a parsed module tree back to text. Inverse of parse_module_expr."""
    return _format_module_expr(tree)


# ---------------------------------------------------------------------------
# Functor path diff (Layer 2)
# ---------------------------------------------------------------------------


def diff_module_trees(lhs: dict, rhs: dict) -> list[dict]:
    """Walk two parsed module trees, return list of differences.

    Each diff has:
      path: list of arg indices (1-based) from root to the difference
      kind: 'name_differ' | 'arity_differ'
      lhs, rhs: formatted text of the subtree at that point
    """
    return _walk_diff(lhs, rhs, path=[])


def _walk_diff(lhs: dict, rhs: dict, path: list[int]) -> list[dict]:
    if lhs["name"] != rhs["name"]:
        return [{
            "path": list(path),
            "kind": "name_differ",
            "lhs": format_module_expr(lhs),
            "rhs": format_module_expr(rhs),
        }]
    if len(lhs["args"]) != len(rhs["args"]):
        return [{
            "path": list(path),
            "kind": "arity_differ",
            "lhs": format_module_expr(lhs),
            "rhs": format_module_expr(rhs),
        }]
    diffs: list[dict] = []
    for i, (la, ra) in enumerate(zip(lhs["args"], rhs["args"]), start=1):
        diffs.extend(_walk_diff(la, ra, path + [i]))
    return diffs


def _format_path(path: list[int]) -> str:
    if not path:
        return "(root)"
    return " → ".join(f"arg_{i}" for i in path)


# ---------------------------------------------------------------------------
# Subtree search + layer analysis (shared by pivot applicability)
# ---------------------------------------------------------------------------


def _trees_equal(a: dict, b: dict) -> bool:
    """Structural equality on parsed module trees."""
    if a.get("name") != b.get("name"):
        return False
    ax = a.get("args") or []
    bx = b.get("args") or []
    if len(ax) != len(bx):
        return False
    return all(_trees_equal(x, y) for x, y in zip(ax, bx))


def _find_subtree(big: dict, small: dict) -> list[int] | None:
    """Return path from ``big`` root down to first occurrence of ``small``.

    Path semantics: ``[]`` = big itself equals small; ``[i]`` = small
    appears as ``big.args[i-1]``; ``[i, j]`` = ``big.args[i-1].args[j-1]``.
    Returns ``None`` when ``small`` is not a subtree of ``big``.

    Used by pivot applicability to decide whether pivot's module shape
    is structurally reachable from the goal's module by peeling off
    outer wrappers via ``inline``.
    """
    if _trees_equal(big, small):
        return []
    for i, arg in enumerate(big.get("args") or [], start=1):
        sub = _find_subtree(arg, small)
        if sub is not None:
            return [i] + sub
    return None


def _classify_module_relation(goal_tree: dict, pivot_tree: dict) -> dict:
    """Classify relation between goal-side and pivot-side module trees.

    Returns a dict with:
      relation : one of
        ``identical``        — same tree verbatim
        ``arg_only_diff``    — root + arity agree, diffs only inside args
        ``pivot_under_goal`` — pivot tree is subtree of goal (unfold goal
                               to reach pivot)
        ``goal_under_pivot`` — goal tree is subtree of pivot (pivot is
                               too abstract; usually indicates instance
                               of a generic lemma)
        ``disjoint``         — neither is a subtree of the other
      path : for ``pivot_under_goal`` / ``goal_under_pivot``, the
             arg-path from the outer tree down to the inner
      first_diff_path : from ``diff_module_trees`` (when relation is
             ``arg_only_diff`` or ``disjoint``)

    The relation drives the actionable tactic plan:
      * identical      → ``apply <pivot>.``
      * arg_only_diff  → ``apply (<pivot> <args>).`` with explicit args
      * pivot_under_goal + path of length N → N ``inline`` calls peel
        the outer wrappers to expose pivot, then ``apply``
      * goal_under_pivot → the pivot is more abstract; prover may use
        ``have := <pivot> <inst_args>.`` to instantiate, or look for a
        more specialized pivot
      * disjoint       → uncertain; module structures don't share a
        nesting relationship — pivot probably not reachable without a
        deeper reduction or a bridging lemma
    """
    if _trees_equal(goal_tree, pivot_tree):
        return {"relation": "identical", "path": [], "first_diff_path": None}
    # Same root? → arg_only_diff
    if (goal_tree.get("name") == pivot_tree.get("name")
            and len(goal_tree.get("args") or []) == len(pivot_tree.get("args") or [])):
        diffs = diff_module_trees(goal_tree, pivot_tree)
        first = diffs[0].get("path", []) if diffs else []
        return {"relation": "arg_only_diff", "path": [], "first_diff_path": first}
    # Pivot nested inside goal?
    sub = _find_subtree(goal_tree, pivot_tree)
    if sub is not None:
        return {"relation": "pivot_under_goal", "path": sub, "first_diff_path": None}
    # Goal nested inside pivot?
    sub = _find_subtree(pivot_tree, goal_tree)
    if sub is not None:
        return {"relation": "goal_under_pivot", "path": sub, "first_diff_path": None}
    # Nothing
    diffs = diff_module_trees(goal_tree, pivot_tree)
    first = diffs[0].get("path", []) if diffs else []
    return {"relation": "disjoint", "path": None, "first_diff_path": first}


# ---------------------------------------------------------------------------
# Extract module expressions from lemma statements
# ---------------------------------------------------------------------------


def extract_pr_modules(lemma_statement: str) -> list[str]:
    """Find all `Pr[<M>.proc(...) ...]` fragments; return each `<M>`.

    `<M>` is the module expression before the top-level `.proc(`. Handles
    nested parens inside the module expression.
    """
    modules: list[str] = []
    for term in _parse_pr_terms(lemma_statement):
        endpoint = term.get("endpoint")
        mod = endpoint.get("module_expr") if isinstance(endpoint, dict) else ""
        if mod:
            modules.append(mod.strip())
    return modules


def _module_before_procedure(pr_content: str) -> str:
    """From 'CCA_game(A, B).main() @ &m : res', extract 'CCA_game(A, B)'.

    Finds the LAST depth-0 `.<name>(` — that's the procedure invocation.
    Intermediate `.`s (e.g. qualified names like `Indist.Distinguish`) are
    part of the module expression, not the procedure call.
    """
    depth = 0
    # First locate the last `.<name>(` at depth 0, then everything BEFORE
    # that `.` is the module expression.
    last_proc_dot = -1
    for i, c in enumerate(pr_content):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "." and depth == 0:
            rest = pr_content[i + 1:]
            # Match `name(` — the procedure call. Must be followed by `(`
            # (possibly spaces). A bare `.name` without `(` is a field,
            # not a proc call, and shouldn't terminate the module.
            if re.match(r"\w+\s*\(", rest):
                last_proc_dot = i
    if last_proc_dot >= 0:
        return pr_content[:last_proc_dot]
    return ""


def _split_module_and_proc(proc_expr: str) -> tuple[str, str]:
    """Split ``M(args).proc`` or ``M(args).proc()`` into ``('M(args)', 'proc')``.

    Unlike ``_module_before_procedure`` (which demands ``.name(``), this
    also accepts a bare ``.name`` tail — the form EC emits in pRHL goal
    summaries before ``proc; inline``.
    """
    return _split_procedure_module_and_name(proc_expr)


def extract_equiv_modules(lemma_statement: str) -> tuple[str, str] | None:
    """For `equiv[M1.f ~ M2.g : ...]`, return ('M1', 'M2'). None if not equiv.

    Handles nested parens in M1/M2.
    """
    m = re.search(r"equiv\s*\[", lemma_statement)
    if not m:
        return None
    start = m.end()
    # Split on the `~` separator at depth 0 (within the [ ])
    depth = 1
    tilde_idx = -1
    i = start
    while i < len(lemma_statement) and depth > 0:
        c = lemma_statement[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                break
        elif c == "~" and depth == 1:
            tilde_idx = i
        i += 1
    if tilde_idx < 0:
        return None
    left = lemma_statement[start:tilde_idx].strip()
    # RHS is from tilde_idx+1 to the `:` or `==>`
    right_part = lemma_statement[tilde_idx + 1:i].strip()
    # Strip trailing `: pre ==> post` if present — take module before the `:`
    right = re.split(r"\s*:\s*", right_part, maxsplit=1)[0].strip()
    # Extract the module before the .proc
    lmod = _module_before_procedure(left)
    rmod = _module_before_procedure(right)
    if not lmod or not rmod:
        return None
    return lmod.strip(), rmod.strip()


# ---------------------------------------------------------------------------
# Layer 2: functor path diff from a lemma statement
# ---------------------------------------------------------------------------


def functor_path_diff(lemma_statement: str) -> str:
    """Render the Layer-2 structural diff of a lemma's functor expressions.

    Extracts the first two comparable module expressions (from Pr[...] pairs
    or from an equiv's two sides) and reports where they differ.
    Returns empty string if the statement doesn't have 2 comparable sides.
    """
    if not lemma_statement:
        return ""

    # Try Pr[...] extraction first (probability lemmas)
    pr_mods = extract_pr_modules(lemma_statement)
    if len(pr_mods) >= 2:
        lhs_expr, rhs_expr = pr_mods[0], pr_mods[1]
        extra_note = ""
        if len(pr_mods) > 2:
            extra_note = (
                f"\n(Statement has {len(pr_mods)} Pr[...] terms total; "
                f"diff above is between the first two. Additional terms: "
                + " ; ".join(pr_mods[2:]) + ")"
            )
        return _render_pair_diff(lhs_expr, rhs_expr, extra_note=extra_note)

    # Try equiv[M1.f ~ M2.g] extraction
    equiv_pair = extract_equiv_modules(lemma_statement)
    if equiv_pair:
        return _render_pair_diff(equiv_pair[0], equiv_pair[1])

    return ""


def _render_pair_diff(lhs_expr: str, rhs_expr: str, extra_note: str = "") -> str:
    lhs = parse_module_expr(lhs_expr)
    rhs = parse_module_expr(rhs_expr)
    diffs = diff_module_trees(lhs, rhs)

    lines = [
        "## Structural Diff (LHS vs RHS)",
        "Pre-computed from your lemma statement — read BEFORE choosing your first tactic.",
        "",
        f"  LHS: {format_module_expr(lhs)}",
        f"  RHS: {format_module_expr(rhs)}",
        "",
    ]

    if not diffs:
        lines.append("  → Modules are **IDENTICAL**. Programs share structure; "
                     "`sim` or `proc; inline *; auto` is the natural opener.")
        lines.append(extra_note) if extra_note else None
        return "\n".join(l for l in lines if l is not None)

    # Describe the diff(s) with context about what's SAME above them
    lines.append(f"  → Found {len(diffs)} point(s) where modules differ:")
    lines.append("")
    for d in diffs:
        path_str = _format_path(d["path"])
        if d["kind"] == "name_differ":
            lines.append(f"  * at {path_str}:")
            lines.append(f"      LHS: {d['lhs']}")
            lines.append(f"      RHS: {d['rhs']}")
            lines.append(f"      (module names differ — semantic equivalence "
                         f"needed, not just renaming)")
        elif d["kind"] == "arity_differ":
            lines.append(f"  * at {path_str}: different number of arguments")
            lines.append(f"      LHS: {d['lhs']}")
            lines.append(f"      RHS: {d['rhs']}")
    lines.append("")
    lines.append(
        "Strategy hint: modules that share outer wrappers but differ at "
        "inner level typically need `call (_: Inv)` with an invariant "
        "linking the inner modules' states — NOT plain `sim` (which "
        "requires identical bodies). For pRHL P20 cases (different "
        "module-qualified globals), use explicit invariant."
    )
    if extra_note:
        lines.append(extra_note)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer 1: program alignment from a parsed pRHL goal
# ---------------------------------------------------------------------------


def program_alignment_diff(goal_info, call_equiv_candidates: dict | None = None) -> str:
    """Render the Layer-1 program alignment from a parsed pRHL GoalInfo.

    Returns empty string if the goal isn't pRHL/equiv or has no body info.
    When the parsed goal is in summary form (one procedure-call statement
    per side, as EC emits before ``proc; inline``), the procedure
    expressions themselves are diffed structurally via the Layer-2
    module-tree walk — so the prover gets a ``RealOrcls(M)`` vs
    ``RealOrcls(N)`` explanation instead of a flat "procs differ" line.

    ``call_equiv_candidates`` (proc_path → [lemma_name, ...]) — when non-empty,
    the DIFFER footer is rewritten to prioritise ``call <lemma_name>`` over
    ``call (_: Inv)``. This preserves proved call-level handles before asking
    the agent to re-prove oracle bodies at a lower layer.
    """
    if not goal_info:
        return ""
    gt = getattr(goal_info, "goal_type", "")
    if gt not in ("pRHL", "equiv"):
        return ""
    left = getattr(goal_info, "left_stmts", []) or []
    right = getattr(goal_info, "right_stmts", []) or []
    if not left and not right:
        return ""

    max_n = max(len(left), len(right))
    rows: list[str] = []
    functor_diffs: list[str] = []
    n_same = 0
    n_diff = 0
    n_only = 0
    for i in range(max_n):
        l = left[i] if i < len(left) else None
        r = right[i] if i < len(right) else None
        l_txt = l["text"] if l else ""
        r_txt = r["text"] if r else ""
        l_proc = l.get("procedure", "") if l else ""
        r_proc = r.get("procedure", "") if r else ""

        if l and not r:
            rows.append(f"  {i+1:3d}. LHS-only: {_truncate(l_txt, 80)}")
            n_only += 1
        elif r and not l:
            rows.append(f"  {i+1:3d}. RHS-only: {_truncate(r_txt, 80)}")
            n_only += 1
        elif l_txt == r_txt:
            rows.append(f"  {i+1:3d}. SAME:     {_truncate(l_txt, 80)}")
            n_same += 1
        else:
            rows.append(
                f"  {i+1:3d}. DIFFER:   {_truncate(l_txt, 40)} ~ "
                f"{_truncate(r_txt, 40)}"
            )
            # Prefer the full statement text for functor extraction —
            # ``procedure`` has already been stripped of functor args.
            l_call = _extract_call_expr(l_txt) or l_proc
            r_call = _extract_call_expr(r_txt) or r_proc
            detail = _render_row_functor_diff(l_call, r_call, row_idx=i + 1)
            if detail:
                functor_diffs.append(detail)
            n_diff += 1

    header = [
        "[AUTO-DIFF] pRHL program alignment",
        f"  {n_same} identical, {n_diff} differing, {n_only} side-only "
        f"(of {max_n} statements total)",
        "",
    ]

    footer: list[str] = []
    if n_diff == 0 and n_only == 0 and n_same > 0:
        footer = [
            "",
            "All statements IDENTICAL → `sim` or `proc; inline *; auto` "
            "likely closes. If sim silently fails, check for module-renamed "
            "globals (P20).",
        ]
    elif n_diff > 0:
        # Prefer `call LEMMA` when matching local equivs exist — the lemma
        # already proves the call-site correspondence as a black box, so
        # `call <lemma>` closes in one step where `call (_: Inv)` would
        # regenerate oracle-body subgoals we'd have to discharge manually.
        # Match each LHS CALL to an RHS CALL that shares at least one local-equiv
        # lemma. This tolerates misaligned row indices (common before `seq` splits
        # the program): LHS[5] Poly.mac should match RHS[3] D.O.Poly.mac even
        # though they're at different rows.
        matched_rows: list[str] = []
        if call_equiv_candidates:
            lhs_calls = [
                (i + 1, s) for i, s in enumerate(left) if s.get("type") == "CALL"
            ]
            rhs_calls = [
                (i + 1, s) for i, s in enumerate(right) if s.get("type") == "CALL"
            ]
            used_r: set[int] = set()
            for lpos, ls in lhs_calls:
                l_proc = ls.get("procedure", "")
                l_hits = call_equiv_candidates.get(l_proc, []) if l_proc else []
                if not l_hits:
                    continue
                for rpos, rs in rhs_calls:
                    if rpos in used_r:
                        continue
                    r_proc = rs.get("procedure", "")
                    r_hits = call_equiv_candidates.get(r_proc, []) if r_proc else []
                    shared = [lm for lm in l_hits if lm in r_hits]
                    if shared:
                        pos_note = (
                            f"both at row {lpos}"
                            if lpos == rpos
                            else f"LHS row {lpos} / RHS row {rpos} — misaligned, "
                                 f"consider `seq {lpos} {rpos} (<inv>)` first"
                        )
                        matched_rows.append(
                            f"    `{l_proc}` ~ `{r_proc}` ({pos_note}) → "
                            f"`call {shared[0]}`"
                            + (f" (alternatives: {', '.join(shared[1:])})" if len(shared) > 1 else "")
                        )
                        used_r.add(rpos)
                        break
        if matched_rows:
            footer = [
                "",
                "Statements DIFFER, BUT matching local equivs are available — "
                "prefer `call <lemma_name>` (black-box, one step) over "
                "`call (_: Inv)` (re-proves oracle bodies inline, fans out "
                "subgoals per method). Matched CALL pairs:",
            ] + matched_rows + [
                "",
                "Fallback: if no pair's candidates apply, fall back to "
                "`call (_: Inv)` with an explicit invariant.",
            ]
        else:
            footer = [
                "",
                "Statements DIFFER → sim alone won't suffice. Use `call (_: Inv)` "
                "at each differing call-site with an invariant that links the "
                "two modules' states. After the call, bodies of the differing "
                "procedures need semantic-equivalence proof (inline or bridge "
                "lemma).",
            ]
    parts = header + rows
    if functor_diffs:
        parts.append("")
        parts.append("  Functor-path diffs for differing call-sites:")
        parts.extend(functor_diffs)
    return "\n".join(parts + footer)


def _extract_call_expr(stmt_text: str) -> str:
    """Extract ``M(args).proc`` from a statement text.

    Handles three shapes:
      * ``b <@ M(args).proc(call_args)`` → ``M(args).proc``
      * ``M(args).proc()`` (statement-form call) → ``M(args).proc``
      * ``M(args).proc`` (summary form, already bare) → unchanged
    Returns '' when the text doesn't look like a procedure call at all.
    """
    s = stmt_text.strip()
    if not s:
        return ""
    if "<@" in s:
        s = s.split("<@", 1)[1].strip()
    # Strip the trailing call-args `(...)` at depth 0. Only strip when
    # the `(` is directly preceded by an identifier (i.e. it's a proc
    # call, not functor application at the root like ``M(args)`` alone).
    if s.endswith(")"):
        depth = 0
        for i in range(len(s) - 1, -1, -1):
            c = s[i]
            if c == ")":
                depth += 1
            elif c == "(":
                depth -= 1
                if depth == 0:
                    # Found the matching outer `(`. Peek at what precedes
                    # it: `.name(` (call args) vs `Name(` (functor args).
                    before = s[:i].rstrip()
                    if before and re.search(r"\.\w+$", before):
                        s = before
                    break
    return s.strip()


def _render_row_functor_diff(l_proc: str, r_proc: str, row_idx: int) -> str:
    """Return an indented module-tree diff for a differing statement pair.

    Empty string when either side lacks a parseable procedure expression
    or the module expressions are identical (only the proc name differs —
    a plain string diff covers that). Otherwise returns 2–4 indented
    lines describing where in the functor tree the two sides diverge.
    """
    if not l_proc or not r_proc:
        return ""
    l_mod, l_name = _split_module_and_proc(l_proc)
    r_mod, r_name = _split_module_and_proc(r_proc)
    if not l_mod or not r_mod:
        return ""
    lhs = parse_module_expr(l_mod)
    rhs = parse_module_expr(r_mod)
    diffs = diff_module_trees(lhs, rhs)
    if not diffs:
        return ""
    lines: list[str] = [f"    row {row_idx}: LHS `{l_mod}.{l_name}` "
                        f"~ RHS `{r_mod}.{r_name}`"]
    for d in diffs:
        path_str = _format_path(d["path"])
        if d["kind"] == "name_differ":
            lines.append(f"      at {path_str}: LHS={d['lhs']}  "
                         f"RHS={d['rhs']}")
        elif d["kind"] == "arity_differ":
            lines.append(f"      at {path_str}: arity differs "
                         f"(LHS={d['lhs']}  RHS={d['rhs']})")
    return "\n".join(lines)


def _truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n - 3] + "..."


# ---------------------------------------------------------------------------
# Lemma inventory extraction (shared between proof_planner and session_cli)
# ---------------------------------------------------------------------------


_SHAPE_ORDER_DIFF = [
    "pr_eq", "pr_ineq", "equiv",
    "phoare_ll", "phoare", "hoare",
    "forall_math", "misc",
]


def _statement_end_dot_ext(content: str, start: int) -> int:
    """Find terminating '.' of an EC declaration at bracket depth 0."""
    paren = bracket = brace = 0
    n = len(content)
    i = start
    while i < n:
        c = content[i]
        if c == '(': paren += 1
        elif c == ')' and paren > 0: paren -= 1
        elif c == '[': bracket += 1
        elif c == ']' and bracket > 0: bracket -= 1
        elif c == '{': brace += 1
        elif c == '}' and brace > 0: brace -= 1
        elif c == '.' and paren == 0 and bracket == 0 and brace == 0:
            nxt = content[i + 1:i + 2]
            if not nxt or nxt.isspace():
                return i + 1
        i += 1
    return n


def extract_lemma_inventory(content: str) -> list[dict]:
    """Extract lemma/theorem/axiom/equiv declarations from .ec file content.

    Returns a list of ``{"name", "statement", "status", "kind"}`` dicts.
    ``status`` ∈ {"proved", "admit", "axiom", "unknown"}. Statement
    text extends to the terminating ``.`` with balanced-paren tracking
    so module paths don't truncate it.

    Shared between the planner (initial prompt injection) and
    session_cli (dynamic [AUTO-PIVOT] hook). Scope: single file — no
    cross-file import resolution here.
    """
    lemmas: list[dict] = []
    decl_re = re.compile(
        r"(?:local\s+)?(lemma|theorem|axiom|equiv)\s+(\w+)\b",
    )
    for m in decl_re.finditer(content):
        kind = m.group(1)
        name = m.group(2)
        stmt_end = _statement_end_dot_ext(content, m.start())
        statement = content[m.start():stmt_end].strip()
        if len(statement) > 400:
            statement = statement[:400] + "..."
        if kind == "axiom":
            status = "axiom"
        else:
            after = content[stmt_end:stmt_end + 500]
            has_admit = bool(re.search(r"\badmit\b", after))
            has_qed = bool(re.search(r"\bqed\b", after))
            if has_qed and not has_admit:
                status = "proved"
            elif has_admit:
                status = "admit"
            else:
                status = "unknown"
        lemmas.append({
            "name": name, "statement": statement,
            "status": status, "kind": kind,
        })
    return lemmas


def classify_lemma_shape(lem: dict) -> str:
    """Shape classifier shared with proof_planner. See planner docs."""
    kind = lem.get("kind", "")
    stmt = lem.get("statement", "") or ""
    body_m = re.match(
        r"(?:local\s+)?(?:lemma|theorem|axiom|equiv)\s+\w+\s*", stmt,
    )
    body = stmt[body_m.end():] if body_m else stmt
    if kind == "equiv":
        return "equiv"
    if re.search(r"\bequiv\s*\[", body):
        return "equiv"
    if re.search(r"\bphoare\s*\[", body):
        compact = body.replace(" ", "")
        if "=1%r" in compact or "<=1%r" in compact:
            return "phoare_ll"
        return "phoare"
    if re.search(r"\bhoare\s*\[", body):
        return "hoare"
    pr_count = len(re.findall(r"\bPr\s*\[", body))
    if pr_count >= 2:
        if re.search(r"\]\s*[^<>=\n]*=", body) and not re.search(r"\]\s*[^=\n]*<=", body):
            return "pr_eq"
        if re.search(r"\]\s*[^<>]*<=", body):
            return "pr_ineq"
        if "=" in body:
            return "pr_eq"
        return "pr_ineq"
    if pr_count == 1:
        return "pr_ineq"
    if re.match(r"forall\b", body.lstrip()) or body.lstrip().startswith("∀"):
        return "forall_math"
    return "misc"


def group_lemmas_by_shape(lemmas: list[dict]) -> dict[str, list[dict]]:
    """Bucket lemmas by ``classify_lemma_shape`` using stable order."""
    groups: dict[str, list[dict]] = {k: [] for k in _SHAPE_ORDER_DIFF}
    for lem in lemmas:
        shape = classify_lemma_shape(lem)
        groups.setdefault(shape, []).append(lem)
    return {k: v for k, v in groups.items() if v}


# ---------------------------------------------------------------------------
# Pivot applicability tagging (used by both plan-time and session_cli AUTO-PIVOT)
# ---------------------------------------------------------------------------


def extract_equiv_proc_pairs(text: str) -> list[tuple[str, str]]:
    """Return every ``M1.f ~ M2.g`` pair in ``text``.

    Handles both named declarations (``equiv foo : M1.f ~ M2.g : ...``)
    and equiv judgments inside a Pr body. Pairs are returned as
    (left_procedure_expr, right_procedure_expr) tuples — raw text, not
    parsed.
    """
    pairs: list[tuple[str, str]] = []
    # Find every "X ~ Y" at paren depth 0 where X and Y look like
    # procedure expressions (contain '.' or start with uppercase).
    # Split input by '~' at depth 0 and find adjacent proc expressions.
    # Simpler: regex for `<word-ish>.<name> ~ <word-ish>.<name>`, with
    # balanced-paren tolerance for the left module.
    pat = re.compile(
        r"([A-Z][\w.()\s,]*?\.\w+)\s*~\s*([A-Z][\w.()\s,]*?\.\w+)",
    )
    for m in pat.finditer(text):
        l = re.sub(r"\s+", " ", m.group(1)).strip()
        r = re.sub(r"\s+", " ", m.group(2)).strip()
        pairs.append((l, r))
    return pairs


# Relative rank for picking the "best" match across goal Pr / equiv sides.
# Lower = more applicable — the caller uses this to surface the strongest
# match first. Kept separate from the user-facing tag so tag presentation
# stays stable while ranking can be tweaked.
_TAG_RANK_TABLE = {
    "DIRECT": 0,
    "ARG_DIFF": 1,
    "UNFOLD": 2,
    "TOO_ABSTRACT": 3,
    "DISJOINT": 4,
    "NAME_MATCH": 5,
    "NO_MATCH": 99,
}


def _proc_name_from_expr(expr: str) -> str:
    """Extract the procedure name from a ``M(args).proc`` expression."""
    _, name = _split_module_and_proc(expr)
    return name


def _pr_pair_verdict(goal_mod_expr: str, pivot_mod_expr: str,
                     gi: int, pj: int) -> dict:
    """Compare one goal Pr module vs one pivot Pr module; return a full
    applicability dict including the tactic plan when actionable."""
    try:
        g = parse_module_expr(goal_mod_expr)
        p = parse_module_expr(pivot_mod_expr)
    except Exception:
        return {"rank": 99, "tag": "NO_MATCH", "detail": "",
                "best_score": 999, "best_side": "-"}
    rel = _classify_module_relation(g, p)
    side = "pivot.LHS" if pj == 0 else ("pivot.RHS" if pj == 1 else f"pivot.Pr#{pj+1}")

    r = rel["relation"]
    if r == "identical":
        return {
            "rank": _TAG_RANK_TABLE["DIRECT"],
            "tag": "DIRECT",
            "detail": (f"{side} matches your goal.Pr#{gi+1} literally — "
                       f"`apply <pivot>.` or `rewrite <pivot>.` are direct route candidates"),
            "plan": [
                "apply <pivot_name>.   "
                "# expected: No more goals on this subgoal.",
            ],
            "best_score": 0,
            "best_side": side,
        }
    if r == "arg_only_diff":
        loc = _format_path(rel["first_diff_path"])
        return {
            "rank": _TAG_RANK_TABLE["ARG_DIFF"],
            "tag": "ARG_DIFF",
            "detail": (f"{side} vs goal.Pr#{gi+1} share the wrapper "
                       f"root; diff at {loc}. `apply (<pivot_name> "
                       f"<args>).` is a route candidate with the arg from your goal's "
                       f"module expression at {loc}."),
            "plan": [
                f"apply (<pivot_name> <instantiate args at {loc}>).   "
                f"# expected: No more goals. If unification fails, "
                f"the error will name the specific arg position that "
                f"doesn't match — read it and adjust.",
            ],
            "best_score": 1,
            "best_side": side,
        }
    if r == "pivot_under_goal":
        path = rel["path"]
        # Extract pivot's proc names to anchor expected-shape messages.
        pivot_proc = _proc_name_from_expr(pivot_mod_expr) or "<proc>"
        pivot_root = format_module_expr(parse_module_expr(pivot_mod_expr))
        plan = [
            "byequiv=> //.   "
            f"# expected: pRHL with both sides' wrapper procs "
            f"visible (summary form, e.g. `<goal_LHS_wrapper>.<proc> "
            f"~ <goal_RHS_wrapper>.<proc> : pre ==> post`).",

            "proc.   "
            f"# expected: both wrapper bodies exposed side-by-side; "
            f"you should now see `<var> <@ {pivot_root}.{pivot_proc}()` "
            f"(or equivalent) as a statement on the matching side. If "
            f"you see unrelated statements instead, the wrapper's body "
            f"doesn't call the pivot's module — pivot is not reachable "
            f"this way; fall back to a different strategy.",

            "call <pivot_name>.   "
            f"# expected: residual goal is pivot's postcondition "
            f"applied to the current context (usually equalities on "
            f"returned values). If this fails with a unification "
            f"error, read the error — it names the exact arg position "
            f"where goal and pivot disagree.",

            "auto.   "
            f"# expected: No more goals (residual equalities close "
            f"automatically). If `auto` leaves a residue, run "
            f"`-goal-info` and solve it with `smt()` or a targeted "
            f"rewrite.",
        ]
        detail = (
            f"{side} is nested {len(path)} wrapper layer(s) inside "
            f"goal.Pr#{gi+1}. Recipe: `byequiv` → pRHL; `proc` unfolds "
            f"the outer wrapper body, exposing the inner procedure "
            f"call; `call <pivot>` applies the pivot at that call site. "
            f"Use `call` rather than `apply`: `apply` needs a bare "
            f"equiv; after `proc` the goal contains a call statement "
            f"and `call` is the tactic that matches there. Lower-level "
            f"`inline *` / `wp` / `sp` before the `call` would erase "
            f"the call structure; probe the shown call plan first."
        )
        return {
            "rank": _TAG_RANK_TABLE["UNFOLD"],
            "tag": "UNFOLD",
            "detail": detail,
            "plan": plan,
            "best_score": len(path),
            "best_side": side,
        }
    if r == "goal_under_pivot":
        return {
            "rank": _TAG_RANK_TABLE["TOO_ABSTRACT"],
            "tag": "TOO_ABSTRACT",
            "detail": (f"pivot is MORE GENERAL than your goal.Pr#{gi+1} "
                       f"(goal's shape appears inside pivot). Instantiate "
                       f"via `have := <pivot_name> <concrete args>.` or "
                       f"look for a specialized variant."),
            "plan": [
                "have h := <pivot_name> <concrete args matching your goal>.   "
                "# expected: new hypothesis `h : <pivot instantiated>` "
                "added to context. Then `apply h.` / `rewrite h.` / "
                "`have := h ...` to use it.",
            ],
            "best_score": 1,
            "best_side": side,
        }
    # disjoint
    loc = _format_path(rel["first_diff_path"])
    return {
        "rank": _TAG_RANK_TABLE["DISJOINT"],
        "tag": "DISJOINT",
        "detail": (f"{side} wrapper root differs from "
                   f"goal.Pr#{gi+1} (at {loc}). Neither is a subtree of "
                   f"the other — pivot is not reachable by pure "
                   f"unfolding. A bridging lemma (e.g. another `Pr[.]=Pr[.]` "
                   f"pivot connecting the two wrappers) is probably "
                   f"needed before this pivot applies."),
        "best_score": 2,
        "best_side": side,
    }


def _equiv_pair_verdict(gl: str, gr: str, pl: str, pr: str,
                        gi: int) -> dict:
    """Combine left + right side verdicts into one applicability dict."""
    gl_mod = gl.rsplit(".", 1)[0]
    gr_mod = gr.rsplit(".", 1)[0]
    pl_mod = pl.rsplit(".", 1)[0]
    pr_mod = pr.rsplit(".", 1)[0]
    try:
        gL = parse_module_expr(gl_mod)
        gR = parse_module_expr(gr_mod)
        pL = parse_module_expr(pl_mod)
        pR = parse_module_expr(pr_mod)
    except Exception:
        return {"rank": 99, "tag": "NO_MATCH", "detail": "",
                "best_score": 999, "best_side": "-"}
    rel_L = _classify_module_relation(gL, pL)
    rel_R = _classify_module_relation(gR, pR)

    # Both identical → DIRECT
    if rel_L["relation"] == "identical" and rel_R["relation"] == "identical":
        return {
            "rank": _TAG_RANK_TABLE["DIRECT"],
            "tag": "DIRECT",
            "detail": ("pivot equiv matches your goal equiv literally — "
                       "`apply <pivot>.` should close it."),
            "plan": [
                "apply <pivot_name>.   "
                "# expected: No more goals on this subgoal.",
            ],
            "best_score": 0,
            "best_side": "equiv pair",
        }
    # Any side disjoint (root differs, neither a subtree) → DISJOINT
    if rel_L["relation"] == "disjoint" or rel_R["relation"] == "disjoint":
        loc_L = (_format_path(rel_L["first_diff_path"])
                 if rel_L["relation"] == "disjoint" else "-")
        loc_R = (_format_path(rel_R["first_diff_path"])
                 if rel_R["relation"] == "disjoint" else "-")
        return {
            "rank": _TAG_RANK_TABLE["DISJOINT"],
            "tag": "DISJOINT",
            "detail": (f"pivot equiv's wrapper roots differ from goal's "
                       f"(LHS diff at {loc_L}, RHS diff at {loc_R}). "
                       f"Pivot is not reachable by pure unfolding — a "
                       f"bridging lemma is probably needed first."),
            "best_score": 4,
            "best_side": "equiv pair",
        }
    # Either side has pivot_under_goal → UNFOLD. For equiv goals in
    # EC, the right tactic is ``proc; call <pivot>; auto`` — ``proc``
    # unfolds both sides' wrapper bodies one layer, exposing the inner
    # procedure calls; ``call`` applies the pivot at those call sites.
    # ``apply <pivot>`` does NOT work at this shape because after
    # ``proc`` the goal contains a call statement, not a bare equiv
    # judgment. (The old design emitted ``inline{N} ... . apply`` —
    # tested live, EC silently rejected `apply` here.)
    if (rel_L["relation"] == "pivot_under_goal"
            or rel_R["relation"] == "pivot_under_goal"):
        depth_L = len(rel_L["path"]) if rel_L["relation"] == "pivot_under_goal" else 0
        depth_R = len(rel_R["path"]) if rel_R["relation"] == "pivot_under_goal" else 0
        pl_proc = pl.rsplit(".", 1)[-1] if "." in pl else "<proc>"
        pr_proc = pr.rsplit(".", 1)[-1] if "." in pr else "<proc>"
        plan = [
            "proc.   "
            f"# expected: both wrapper bodies exposed side-by-side; "
            f"look for `<var> <@ {format_module_expr(parse_module_expr(pl.rsplit('.', 1)[0])) if '.' in pl else '<PL>'}.{pl_proc}()` on LHS and "
            f"`<var> <@ {format_module_expr(parse_module_expr(pr.rsplit('.', 1)[0])) if '.' in pr else '<PR>'}.{pr_proc}()` on RHS. If those "
            f"calls aren't visible, the wrapper's body doesn't route "
            f"to the pivot's modules — try a different pivot or "
            f"strategy.",

            "call <pivot_name>.   "
            f"# expected: residual goal = pivot's postcondition "
            f"`<pivot_post>`. The call sites are replaced by the "
            f"pivot's conclusion; any outer context equalities remain. "
            f"If this fails with unification error, read the error "
            f"— it names the exact arg position or hypothesis that "
            f"doesn't match.",

            "auto.   "
            f"# expected: No more goals (residual closes via ={{...}} "
            f"unification). If `auto` leaves work, look at the "
            f"residue with `-goal-info` and close with `smt()` or a "
            f"targeted `rewrite`.",
        ]
        detail = (
            f"Pivot procedures live inside goal's wrappers "
            f"(LHS depth {depth_L}, RHS depth {depth_R}). Recipe: "
            f"`proc` unfolds both sides' wrapper bodies, exposing the "
            f"inner procedure calls that match the pivot's LHS/RHS; "
            f"`call <pivot>` replaces those calls using the pivot. "
            f"Use `call` rather than `apply`: `apply` only matches bare "
            f"equiv judgments, but after `proc` the goal has a "
            f"procedure-call statement. Lower-level "
            f"`inline *` / `wp` / `sp` before `call` would erase "
            f"the call structure; probe the shown call plan first."
        )
        return {
            "rank": _TAG_RANK_TABLE["UNFOLD"],
            "tag": "UNFOLD",
            "detail": detail,
            "plan": plan,
            "best_score": depth_L + depth_R,
            "best_side": "equiv pair",
        }
    # Both sides arg_only_diff → ARG_DIFF
    if (rel_L["relation"] == "arg_only_diff"
            and rel_R["relation"] == "arg_only_diff"):
        loc_L = _format_path(rel_L["first_diff_path"])
        loc_R = _format_path(rel_R["first_diff_path"])
        return {
            "rank": _TAG_RANK_TABLE["ARG_DIFF"],
            "tag": "ARG_DIFF",
            "detail": (f"pivot equiv shares wrapper shape with your goal; "
                       f"diffs are inside args (LHS at {loc_L}, RHS at "
                       f"{loc_R}). Try `apply (<pivot_name> <args>).` "
                       f"filling those arg positions from your goal."),
            "plan": [
                f"apply (<pivot_name> <args at {loc_L} / {loc_R}>).   "
                f"# expected: No more goals. If unification fails, the "
                f"error names the specific mismatching arg position — "
                f"read it and substitute the right arg from your goal.",
            ],
            "best_score": 2,
            "best_side": "equiv pair",
        }
    # goal_under_pivot anywhere → TOO_ABSTRACT
    if (rel_L["relation"] == "goal_under_pivot"
            or rel_R["relation"] == "goal_under_pivot"):
        return {
            "rank": _TAG_RANK_TABLE["TOO_ABSTRACT"],
            "tag": "TOO_ABSTRACT",
            "detail": ("goal sits inside pivot — pivot is MORE GENERAL. "
                       "Instantiate it via `have := <pivot_name> "
                       "<concrete args>.` and apply to the hypothesis, "
                       "or find a specialized variant."),
            "plan": [
                "have h := <pivot_name> <concrete args>.   "
                "# expected: new hypothesis `h : <pivot instantiated>` "
                "in context. Then `apply h.` / `rewrite h.` etc.",
            ],
            "best_score": 3,
            "best_side": "equiv pair",
        }
    # Fallback (shouldn't hit but safe)
    return {
        "rank": _TAG_RANK_TABLE["DISJOINT"],
        "tag": "DISJOINT",
        "detail": "pivot equiv doesn't share enough structure with the goal — "
                  "probably not applicable from the current shape.",
        "best_score": 4,
        "best_side": "equiv pair",
    }


def pivot_applicability(pivot_statement: str,
                        goal_statement: str) -> dict:
    """Classify how applicable ``pivot`` is to ``goal`` via module trees.

    Tag hierarchy (most actionable first):
      ``DIRECT``        — literal match on at least one side. ``apply
                          <name>.`` usually closes the subgoal.
      ``ARG_DIFF``      — same wrapper shape, differences only inside
                          arg positions. ``apply (<name> <args>).`` with
                          explicit instantiations usually works.
      ``UNFOLD``        — pivot's module is nested inside goal's
                          wrapper. Peel the goal's outer wrapper(s)
                          with targeted ``inline`` calls, THEN apply.
                          Output includes the exact unfold sequence.
                          Use the shown order first. ``inline *`` or
                          ``wp/sp/auto`` before the apply can erase the
                          procedure-call structure; probe the plan first.
      ``TOO_ABSTRACT``  — goal's module is inside pivot; pivot is more
                          general than the goal's current shape. Try
                          ``have := <pivot> <concrete_args>.`` to
                          instantiate, or look for a specialization.
      ``DISJOINT``      — neither subtree relation holds; module
                          wrappers have unrelated roots. Pivot
                          probably needs a bridging reduction before
                          it applies.
      ``NAME_MATCH``    — only token overlap; structurally unrelated
                          at this goal shape. Keep in mind for when
                          transformations bring it into view.
      ``NO_MATCH``      — neither structural nor token relation.

    Returns a dict:
      ``tag``       : one of the above
      ``detail``    : single-line human description
      ``plan``      : (optional) list of tactic strings the prover
                      can apply as-is. Present for DIRECT / ARG_DIFF /
                      UNFOLD; absent otherwise.
      ``best_score``: int (0=identical, 999=no parseable match) — kept
                      for backward-compat sorting
      ``best_side`` : string describing which pivot side matched
    """
    # --- Pr alignment ---
    goal_pr_mods = extract_pr_modules(goal_statement)
    pivot_pr_mods = extract_pr_modules(pivot_statement)

    best = {
        "tag": "NO_MATCH",
        "detail": "",
        "best_score": 999,
        "best_side": "-",
        "best_goal_idx": -1,
    }

    if goal_pr_mods and pivot_pr_mods:
        # Compare every (goal_i, pivot_j) pair; record best
        for gi, gmod in enumerate(goal_pr_mods):
            for pj, pmod in enumerate(pivot_pr_mods):
                verdict = _pr_pair_verdict(gmod, pmod, gi, pj)
                if verdict["rank"] < best.get("rank", 99):
                    best = verdict
        if best.get("rank", 99) < 99:
            best.pop("rank", None)
            return best

    # --- Equiv alignment ---
    goal_eq_pairs = extract_equiv_proc_pairs(goal_statement)
    pivot_eq_pairs = extract_equiv_proc_pairs(pivot_statement)
    if goal_eq_pairs and pivot_eq_pairs:
        for gi, (gl, gr) in enumerate(goal_eq_pairs):
            for (pl, pr) in pivot_eq_pairs:
                verdict = _equiv_pair_verdict(gl, gr, pl, pr, gi)
                if verdict["rank"] < best.get("rank", 99):
                    best = verdict

    if best.get("rank", 99) < 99:
        best.pop("rank", None)
        return best

    # --- Name fallback: share any module token? ---
    # Useful when goal is not yet in a shape that matches pivot directly
    # (e.g. pre-congr, pre-byequiv) but the pivot is topically relevant.
    goal_tokens = set(re.findall(r"[A-Z]\w+", goal_statement))
    pivot_tokens = set(re.findall(r"[A-Z]\w+", pivot_statement))
    shared = goal_tokens & pivot_tokens
    # Exclude noise tokens
    shared -= {"Pr", "N", "LHS", "RHS", "Type", "Game"}
    if shared:
        best["tag"] = "NAME_MATCH"
        shared_sample = sorted(shared)[:3]
        best["detail"] = (
            f"pivot mentions module(s) {', '.join(shared_sample)} that also "
            f"appear in your goal — topically relevant; may become applicable "
            f"after you transform the goal (e.g. via `congr` / `byequiv`)"
        )
    return best


# ---------------------------------------------------------------------------
# Layer 1 for probability / equation goals
# ---------------------------------------------------------------------------


def _extract_full_pr_terms(text: str) -> list[str]:
    """Return every ``Pr[...]`` substring in ``text``, bracket-nesting aware.

    Unlike ``extract_pr_modules`` which returns only the module part, this
    preserves the full ``Pr[M.proc(args) @ &m : event]`` text so the prover
    can see both LHS and RHS verbatim.
    """
    return [
        str(term.get("pr_text") or "")
        for term in _parse_pr_terms(text, require_endpoint=False)
        if str(term.get("pr_text") or "")
    ]


def probability_diff(goal_info) -> str:
    """Render a Layer-1 diff for a probability goal.

    Handles three shapes:
      * ``Pr[M1.p @ &m : e1] = Pr[M2.q @ &m : e2]``        (equation)
      * ``Pr[M.p @ &m : e1] <= Pr[M.p @ &m : e2]``          (event monotonicity)
      * ``Pr[M1.p @ &m : e1] <= Pr[M2.q @ &m : e2] + C``    (union bound / bridge)
      * ``Pr[M.p @ &m : e] <= bound``                       (concrete bound)

    When two comparable ``Pr[...]`` terms exist, walks their module
    expressions as parse trees and names the arg position where they
    diverge — same pattern as the pRHL functor diff.
    """
    if not goal_info or getattr(goal_info, "goal_type", "") != "probability":
        return ""
    raw = getattr(goal_info, "raw_text", "") or ""
    if not raw:
        return ""

    # Join line-wrapped Pr[...] into a single logical line before parsing.
    joined = re.sub(r"\s+", " ", raw)

    # Identify operator: =, <=, >=
    op_match = re.search(r"\]\s*(<=|>=|=)", joined)
    op = op_match.group(1) if op_match else "?"

    pr_terms = _extract_full_pr_terms(joined)
    if not pr_terms:
        return ""

    lines = [f"[AUTO-DIFF] probability goal (operator: {op})"]
    for i, t in enumerate(pr_terms[:4], start=1):
        lines.append(f"  Pr #{i}: {_truncate(t, 100)}")

    # Classify the RHS shape when the operator is an inequality.
    if op in ("<=", ">="):
        # Slice after the first `]<op>` — this is the RHS of the bound.
        split = re.search(r"\]\s*(?:<=|>=)\s*(.+)$", joined)
        rhs = split.group(1).strip() if split else ""
        rhs_pr_count = len(_extract_full_pr_terms(rhs))
        if rhs_pr_count == 0:
            lines.append("  RHS shape: concrete bound (no Pr[...] on RHS) — "
                         "use `byphoare` or direct phoare computation.")
        elif rhs_pr_count == 1 and len(pr_terms) == 2:
            lhs_mods = extract_pr_modules(pr_terms[0])
            rhs_mods = extract_pr_modules(pr_terms[1])
            same_proc = (lhs_mods == rhs_mods
                         and _proc_of_pr(pr_terms[0]) == _proc_of_pr(pr_terms[1]))
            if same_proc:
                lines.append("  RHS shape: same module.proc as LHS, different "
                             "event — event monotonicity. Use `byequiv` with "
                             "an invariant implying `LHS event ⇒ RHS event`, "
                             "or `Pr[..:e1] <= Pr[..:e2]` via `byphoare (:_) ` "
                             "with pointwise implication.")
            else:
                lines.append("  RHS shape: single Pr[...] with different "
                             "module/proc — bridge reduction. Rewrite with "
                             "an `equiv`-derived probability equality, then "
                             "apply event monotonicity.")
        else:
            lines.append("  RHS shape: sum/multiple Pr[...] — union bound or "
                         "ler_trans scenario. Use `byequiv` + `ler_add` / "
                         "`ler_trans` to split.")

    # Module-expression diff between the first two Pr[...] terms.
    mods = extract_pr_modules(joined)
    if len(mods) >= 2:
        lhs = parse_module_expr(mods[0])
        rhs = parse_module_expr(mods[1])
        diffs = diff_module_trees(lhs, rhs)
        if diffs:
            lines.append("")
            lines.append(f"  Module diff ({len(diffs)} differing point(s)):")
            for d in diffs:
                path = _format_path(d["path"])
                lines.append(f"    at {path}: LHS={d['lhs']}  RHS={d['rhs']}")
        elif len(mods) >= 2:
            lines.append("  Modules are IDENTICAL — bodies share structure, "
                         "any reduction will be on the event/args only.")

    return "\n".join(lines)


def _proc_of_pr(pr_term: str) -> str:
    """From `Pr[M(args).proc(call_args) @ &m : e]`, return `proc`."""
    terms = _parse_pr_terms(pr_term)
    if not terms:
        return ""
    endpoint = terms[0].get("endpoint")
    return str(endpoint.get("procedure") or "") if isinstance(endpoint, dict) else ""


# ---------------------------------------------------------------------------
# Layer 1 for eager judgments
# ---------------------------------------------------------------------------


def eager_diff(goal_info) -> str:
    """Render a Layer-1 diff for an eager judgment.

    Input shape: ``eager[ stmt_L, P ~ Q, stmt_R : pre ==> post]``.
    The two procedures ``P`` and ``Q`` are module-expressions that may
    differ functorially; the inserted statements tell us *where* the
    sync point sits. Output names the structural difference and the
    inserted-statement positioning so the prover can pick between
    `eager proc`, `eager while`, or a manual split.
    """
    if not goal_info or getattr(goal_info, "goal_type", "") != "eager":
        return ""
    l_proc = getattr(goal_info, "eager_left_proc", "") or ""
    r_proc = getattr(goal_info, "eager_right_proc", "") or ""
    l_stmt = getattr(goal_info, "eager_left_stmt", "") or ""
    r_stmt = getattr(goal_info, "eager_right_stmt", "") or ""
    if not l_proc or not r_proc:
        return ""

    lines = [f"[AUTO-DIFF] eager judgment: {l_proc} ~ {r_proc}"]
    if l_stmt:
        lines.append(f"  Left inserted stmt (before LHS):  "
                     f"{_truncate(l_stmt, 80)}")
    if r_stmt:
        lines.append(f"  Right inserted stmt (after RHS):  "
                     f"{_truncate(r_stmt, 80)}")

    l_mod, l_name = _split_module_and_proc(l_proc)
    r_mod, r_name = _split_module_and_proc(r_proc)

    if l_mod and r_mod and l_mod != r_mod:
        lhs = parse_module_expr(l_mod)
        rhs = parse_module_expr(r_mod)
        diffs = diff_module_trees(lhs, rhs)
        if diffs:
            lines.append("")
            lines.append(f"  Module diff ({len(diffs)} differing point(s)):")
            for d in diffs:
                path = _format_path(d["path"])
                lines.append(f"    at {path}: LHS={d['lhs']}  RHS={d['rhs']}")
            lines.append("")
            lines.append("  Strategy: procedures live in different modules — "
                         "`eager proc` won't directly apply. Unfold the inner "
                         "calls on both sides with `eager inline` first, "
                         "then `eager proc` on the shared leaves.")
        else:
            lines.append("  Modules resolve to IDENTICAL trees after parsing "
                         "— safe to try `eager proc` directly.")
    elif l_name != r_name:
        lines.append(f"  Same module, different procs ({l_name} vs {r_name}) "
                     "— typically the eager is between a clean and an "
                     "instrumented version; use `eager proc`.")
    else:
        lines.append("  Both sides call the same module.proc — `eager proc` "
                     "should close directly if invariants align.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI (for debugging)
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Structural diff for pRHL goals + lemma statements")
    ap.add_argument("--lemma-statement", help="Full lemma statement (Layer 2)")
    ap.add_argument("--goal-json", help="Path to goal-info JSON output (Layer 1)")
    args = ap.parse_args()

    outputs: list[str] = []
    if args.lemma_statement:
        l2 = functor_path_diff(args.lemma_statement)
        if l2:
            outputs.append(l2)
    if args.goal_json:
        import json
        data = json.loads(Path(args.goal_json).read_text())

        class _GI:
            pass

        gi = _GI()
        gi.goal_type = data.get("goal_type", "")
        gi.left_stmts = data.get("left_statements", [])
        gi.right_stmts = data.get("right_statements", [])
        l1 = program_alignment_diff(gi)
        if l1:
            outputs.append(l1)

    sys.stdout.write("\n\n".join(outputs) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
