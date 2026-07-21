"""Subgoal gap analyzer — surface the structural gap between current pre/hyps and what a goal/lemma needs.

Two modes (both via `session_cli.py -subgoal-gap`):

MODE A — gap in the current pRHL goal:
  Decompose the goal's pre/post into conjuncts. For each post conjunct,
  classify: PROVED-BY-PRE / LOOSE-MATCH (monotonicity / definition unfold) /
  PROVIDED-BY-NEXT-CALL (covered by a named equiv whose two sides match the
  LHS/RHS first call) / MISSING. The MISSING set is the actionable gap —
  agent decides whether to extend invariant, insert seq, unfold a definition,
  or reconsider the lemma choice.

MODE B — `--against-lemma 'NAME args...'`:
  Project a candidate named-equiv's PRE against the current state. Answers:
  "if I `call`/`ecall LEMMA` here, which pre-conditions are already covered?"
  Each PRE conjunct gets COVERED / LOOSE (with reason — substitution /
  definition unfold / module-alias) / MISSING. A `0 missing` verdict means
  the lemma is correct; if the agent is seeing ambient subgoals it can't
  close, the gap is substitution/unfold/alignment, NOT lemma choice.

Use it AFTER applying a structural tactic (call/ecall/byequiv) when you have
multiple unclosed ambient subgoals and are about to undo. The classification
distinguishes "pre-state alignment is wrong" from "lemma is wrong" — the
former is fixable in one step (rewrite/move=>/seq); the latter requires
restructuring.

Output is structural information, not prescription. The agent reads the
inventory and chooses the action.

Usage:
  python3 core/easycrypt/session_cli.py -d <sess> -subgoal-gap
  python3 core/easycrypt/session_cli.py -d <sess> -subgoal-gap --against-lemma 'equ_X arg1 arg2'
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Ensure the project root is importable when run as a script.
_PKG_ROOT = Path(__file__).resolve().parents[2]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from core.easycrypt.analysis.ec_goal_parser import parse_goal  # noqa: E402
from core.easycrypt.session_state import read_session_state  # noqa: E402
from core.easycrypt.session_projection import read_proof_state_projection  # noqa: E402


# ---------------------------------------------------------------------------
# Conjunct splitting
# ---------------------------------------------------------------------------

def _strip_outer_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        ok = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i < len(s) - 1:
                    ok = False
                    break
        if ok:
            s = s[1:-1].strip()
        else:
            break
    return s


_EQ_SET_RE = re.compile(r'^=\s*\{\s*(.+?)\s*\}$')


def _expand_eq_set_sugar(conjunct: str) -> list[str]:
    """`={X, Y, Z}` → [`X{1} = X{2}`, `Y{1} = Y{2}`, `Z{1} = Z{2}`].

    EC's set-equality syntactic sugar: `={X,Y}` is equivalent to
    `X{1}=X{2} /\\ Y{1}=Y{2}`. Without this expansion, template matching
    against a current pre that has the EXPANDED form (or vice versa)
    fails as a false MISSING.
    """
    m = _EQ_SET_RE.match(conjunct.strip())
    if not m:
        return [conjunct]
    items_raw = m.group(1)
    # Split by comma at depth 0 (don't break inside nested parens like
    # `={(n, a), p}` — though that's pretty unusual in practice)
    items: list[str] = []
    depth = 0
    last = 0
    for i, ch in enumerate(items_raw):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(items_raw[last:i].strip())
            last = i + 1
    items.append(items_raw[last:].strip())
    return [f"{it}{{1}} = {it}{{2}}" for it in items if it]


def split_conjuncts(formula: str) -> list[str]:
    """Split a /\\-conjoined formula into top-level conjuncts, RECURSIVELY.

    Respects parentheses. Drops the outermost parens before splitting.
    If a conjunct itself is a parenthesized conjunction, flatten it.
    Also expands `={X, Y}` syntactic sugar into individual equalities.
    """
    s = _strip_outer_parens(formula)
    out: list[str] = []
    depth = 0
    i = 0
    last = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and s[i:i+2] == "/\\":
            out.append(s[last:i].strip())
            i += 2
            last = i
            continue
        i += 1
    tail = s[last:].strip()
    if tail:
        out.append(tail)
    # Flatten + expand
    flat: list[str] = []
    for c in out:
        c = c.strip()
        if not c:
            continue
        if c.startswith("(") and c.endswith(")"):
            inner = _strip_outer_parens(c)
            if _has_top_level_conj(inner):
                flat.extend(split_conjuncts(inner))
                continue
        # Expand ={X, Y, ...} sugar
        expanded = _expand_eq_set_sugar(c)
        if len(expanded) > 1:
            flat.extend(expanded)
        else:
            flat.append(c)
    return flat


def _has_top_level_conj(s: str) -> bool:
    depth = 0
    for i in range(len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
        elif depth == 0 and s[i:i+2] == "/\\":
            return True
    return False


# ---------------------------------------------------------------------------
# Predicate template extraction
# ---------------------------------------------------------------------------

# A "predicate template" is a tuple representing the shape of a fact, used
# to match conjuncts across pre/post. We use a coarse classification —
# enough to detect "same predicate, different witnesses" patterns like
# `(n,c) \in ROF.m => n \in BNR.lenc` (pre) vs same with `n :: BNR.lenc` (post).

@dataclass
class Predicate:
    raw: str
    kind: str   # "eq" | "neq" | "mem" | "not_mem" | "size_le" | "forall_impl_mem" | "named_rel" | "lossless" | "other"
    symbols: set[str] = field(default_factory=set)   # all top-level idents mentioned (rough)
    template: str = ""  # canonicalized form for matching
    loose_template: str = ""  # loose match template (e.g. drop cons-extension)
    cont_extended: bool = False  # forall_impl_mem with `n :: rest` container


_IDENT_RE = re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*\b')
# Reserved EC keywords / SMT keywords we don't want to count as "symbols"
_KEYWORDS = {
    "forall", "exists", "fun", "if", "then", "else", "let", "in",
    "true", "false", "size", "max_cipher_size",
    "and", "or", "not",
}


def _extract_idents(s: str) -> set[str]:
    return {m.group(0) for m in _IDENT_RE.finditer(s) if m.group(0) not in _KEYWORDS}


def _strip_side_marks(s: str) -> str:
    """Strip {1}/{2} side marks for template matching."""
    return re.sub(r'\{[12]\}', '', s)


def classify_predicate(conjunct: str) -> Predicate:
    raw = conjunct.strip()
    # Strip outer side-mark `(...){1}` or `(...){2}` first — EC sometimes
    # qualifies a whole conjunct with a side-mark when the formula is
    # entirely on one side. Treat as equivalent to inner formula.
    m = re.match(r'^\((.+)\)\{[12]\}$', raw, re.DOTALL)
    if m:
        sub = classify_predicate(m.group(1))
        sub.raw = raw
        return sub
    # Strip outer parens so wrapped forall-impl-mem etc. classify correctly
    inner = _strip_outer_parens(raw)
    if inner != raw:
        # Re-classify on stripped form, but keep raw for display
        sub = classify_predicate(inner)
        sub.raw = raw  # show original
        return sub
    # Try forall-implication-membership pattern first (most informative).
    # Two forms:
    #   forall n c, (n,c) \in M => n \in S
    #   forall (n : T) (c : U), (n,c) \in M => n \in S
    # Strategy: find `forall ` prefix, then find `, (` for the body start,
    # then look for `\in M => x \in S`.
    m = re.match(
        r'forall\s+(.+?),\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*\\in\s+(\S+?)\s*=>\s*(\S+?)\s*\\in\s+(.+?)\s*$',
        raw,
    )
    if m:
        bound_vars = m.group(1).strip()
        map_name = m.group(4).strip()
        cont = m.group(6).strip()
        # Track whether the container is `cons`-extended (a :: rest) — semantic
        # monotonicity weakening relative to non-extended form.
        cont_extended = "::" in cont
        cont_head = cont
        if cont_extended:
            cont_head = cont.split("::")[-1].strip()
        # Two-tier template: strict (preserves cons) and loose (collapsed to head)
        loose_template = f"forall_impl_mem({_strip_side_marks(map_name)}, _, {_strip_side_marks(cont_head)})"
        strict_template = f"forall_impl_mem({_strip_side_marks(map_name)}, _, {_strip_side_marks(cont)})"
        pred = Predicate(
            raw=raw,
            kind="forall_impl_mem",
            symbols=_extract_idents(map_name) | _extract_idents(cont),
            template=strict_template,
        )
        # Stash loose template as attribute for matcher
        pred.loose_template = loose_template
        pred.cont_extended = cont_extended
        return pred
    # not-in pattern: ! (x \in S)  or  !x \in S
    m = re.match(r'!\s*\(?\s*(\S+?)\s*\\in\s+(.+?)\)?\s*$', raw)
    if m:
        x = m.group(1).strip()
        s = m.group(2).strip()
        return Predicate(
            raw=raw,
            kind="not_mem",
            symbols=_extract_idents(x) | _extract_idents(s),
            template=f"not_mem(_, {_strip_side_marks(s)})",
        )
    # in pattern: x \in S
    m = re.match(r'(\S+?)\s*\\in\s+(.+?)\s*$', raw)
    if m:
        x, s = m.group(1).strip(), m.group(2).strip()
        return Predicate(
            raw=raw,
            kind="mem",
            symbols=_extract_idents(x) | _extract_idents(s),
            template=f"mem(_, {_strip_side_marks(s)})",
        )
    # size bound: size E <= K   or   size arg{1}.`3 <= max_cipher_size
    m = re.match(r'size\s+(\S+?)\s*<=\s*(.+?)\s*$', raw)
    if m:
        e, k = m.group(1).strip(), m.group(2).strip()
        return Predicate(
            raw=raw,
            kind="size_le",
            symbols=_extract_idents(e) | _extract_idents(k),
            template=f"size_le(_, {_strip_side_marks(k)})",
        )
    # equality of side-marked vars: ={X, Y, Z}  (EC sugar) — skip; handled
    # specially by stripping  (caller can pre-expand)
    m = re.match(r'=\s*\{\s*(.+?)\s*\}\s*$', raw)
    if m:
        items = [x.strip() for x in m.group(1).split(",")]
        return Predicate(
            raw=raw,
            kind="eq",
            symbols=set(items),
            template=f"eq_set({','.join(sorted(items))})",
        )
    # plain equality   X = Y
    m = re.match(r'(\S.+?)\s*=\s*(.+?)\s*$', raw)
    if m and "=" in m.group(0) and "==" not in raw:
        l, r = m.group(1).strip(), m.group(2).strip()
        # Skip definitions (let in, etc.) — heuristic
        if "let " in raw or "if " in raw:
            pass
        else:
            return Predicate(
                raw=raw,
                kind="eq",
                symbols=_extract_idents(l) | _extract_idents(r),
                template=f"eq({_strip_side_marks(l)}, {_strip_side_marks(r)})",
            )
    # fallback
    return Predicate(
        raw=raw,
        kind="other",
        symbols=_extract_idents(raw),
        template=_strip_side_marks(raw),
    )


# ---------------------------------------------------------------------------
# Gap matching
# ---------------------------------------------------------------------------

@dataclass
class ConjunctVerdict:
    post_conjunct: str
    pred: Predicate
    status: str   # "PROVED_BY_PRE" | "LOOSE_MATCH" | "MISSING" | "PROVIDED_BY_NEXT_CALL"
    matched_pre: Optional[Predicate] = None
    note: str = ""


@dataclass
class NamedEquiv:
    """A `(local )?equiv NAME params : LHS_proc ~ RHS_proc : pre ==> post.` decl."""
    name: str
    params: str        # text between NAME and `:` (e.g. "n0 mr0 ms0")
    lhs_proc: str      # full LHS procedure expression
    rhs_proc: str      # full RHS procedure expression
    pre: str
    post: str
    line_num: int


_EQUIV_DECL_RE = re.compile(
    r'^\s*(?:local\s+)?equiv\s+(\w+)\b([^:]*?):\s*(.*)$',
    re.MULTILINE,
)


def parse_named_equivs(ec_text: str) -> list[NamedEquiv]:
    """Scan an .ec file for `(local )?equiv NAME [params] : LHS ~ RHS : pre ==> post.`

    Handles parameterized form (e.g. `equiv H_equiv x y z : ...`) which
    `ec_bridge_lemmas.parse_equiv_lemmas` misses.
    """
    out: list[NamedEquiv] = []
    lines = ec_text.split("\n")
    i = 0
    while i < len(lines):
        m = _EQUIV_DECL_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        params = m.group(2).strip()
        body_start = m.group(3)
        # Accumulate continuation until we see `==>` AND `.` at end OR `proof.` line
        full = body_start
        j = i + 1
        # Cap continuation at 30 lines (defensive)
        while j < len(lines) and j < i + 30:
            stripped = lines[j].strip()
            if stripped.startswith("proof") or stripped.startswith("(*"):
                break
            # Stop if we already saw the terminating `.` AND `==>`
            if "==>" in full and full.rstrip().endswith("."):
                break
            full += " " + stripped
            j += 1
        # Parse "LHS ~ RHS : pre ==> post."
        tm = re.match(
            r'\s*(.+?)\s*~\s*(.+?)\s*:\s*(.+?)\s*==>\s*(.+?)\s*\.\s*$',
            full,
            re.DOTALL,
        )
        if tm:
            out.append(NamedEquiv(
                name=name,
                params=params,
                lhs_proc=tm.group(1).strip(),
                rhs_proc=tm.group(2).strip(),
                pre=tm.group(3).strip(),
                post=tm.group(4).strip(),
                line_num=i + 1,
            ))
        i += 1
    return out


def _proc_module_chain(proc: str) -> str:
    """Strip wrapper module args to a comparable shape.

    `ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(...), ...), ROF))).enc`
    → `ChaCha.enc` (head module + final method)
    """
    # Find the outermost module name + final method
    proc = proc.strip()
    # Drop leading whitespace and `()` at end
    proc = re.sub(r'\s*\(\s*\)\s*$', '', proc)
    # Match: outer module name (greedy, before first `(`) followed by ... `.method`
    m = re.match(r'^([A-Za-z_][\w]*)\s*\(', proc)
    if m:
        head = m.group(1)
        # Find last `.method` after the closing of the outer paren
        depth = 0
        for i, ch in enumerate(proc):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and i + 1 < len(proc) and proc[i+1] == '.':
                    method = proc[i+2:].strip()
                    # Strip trailing args like "(k, n, p)"
                    method = re.sub(r'\s*\(.*$', '', method)
                    return f"{head}.{method}"
        return head
    # No outer paren — simple `Module.method` form
    m2 = re.match(r'^([A-Za-z_][\w.]*?)\s*$', proc)
    if m2:
        return m2.group(1)
    return proc


def find_matching_equiv_for_calls(
    ec_text: str,
    lhs_call_proc: str,
    rhs_call_proc: str,
) -> Optional[NamedEquiv]:
    """Find a named equiv whose LHS/RHS module chains match the call pair.

    Uses module-head + method-tail comparison so wrapper differences don't
    block matching.
    """
    if not lhs_call_proc or not rhs_call_proc:
        return None
    target_lhs = _proc_module_chain(lhs_call_proc)
    target_rhs = _proc_module_chain(rhs_call_proc)
    equivs = parse_named_equivs(ec_text)
    for eq in equivs:
        eq_lhs = _proc_module_chain(eq.lhs_proc)
        eq_rhs = _proc_module_chain(eq.rhs_proc)
        if eq_lhs == target_lhs and eq_rhs == target_rhs:
            return eq
    return None


def match_post_against_pre(
    pre_preds: list[Predicate],
    post_pred: Predicate,
) -> ConjunctVerdict:
    """For one post conjunct, find best match in pre (if any)."""
    # Exact template match → PROVED_BY_PRE
    for p in pre_preds:
        if p.template == post_pred.template:
            return ConjunctVerdict(
                post_conjunct=post_pred.raw,
                pred=post_pred,
                status="PROVED_BY_PRE",
                matched_pre=p,
                note="Identical template.",
            )

    # forall_impl_mem with cons-extension: post `n0 \in x :: rest` vs
    # pre `n0 \in rest` — monotone weakening, treat as loose.
    if post_pred.kind == "forall_impl_mem" and post_pred.cont_extended:
        for p in pre_preds:
            if p.kind == "forall_impl_mem" and p.template == post_pred.loose_template:
                return ConjunctVerdict(
                    post_conjunct=post_pred.raw,
                    pred=post_pred,
                    status="LOOSE_MATCH",
                    matched_pre=p,
                    note=("Container extended with new element — pre is "
                          "STRONGER (smaller container); post follows by "
                          "monotonicity (`mem_cons`)."),
                )

    # Loose match: same kind + overlapping template prefix
    for p in pre_preds:
        if p.kind == post_pred.kind:
            # forall_impl_mem with same map name → loose
            if post_pred.kind == "forall_impl_mem":
                pre_map = p.template.split(",")[0]
                post_map = post_pred.template.split(",")[0]
                if pre_map == post_map:
                    return ConjunctVerdict(
                        post_conjunct=post_pred.raw,
                        pred=post_pred,
                        status="LOOSE_MATCH",
                        matched_pre=p,
                        note=("Same map domain, but container differs — "
                              "may need monotonicity."),
                    )
            elif post_pred.kind == "size_le":
                pre_k = p.template.split(",")[1].strip().rstrip(")")
                post_k = post_pred.template.split(",")[1].strip().rstrip(")")
                if pre_k == post_k:
                    return ConjunctVerdict(
                        post_conjunct=post_pred.raw,
                        pred=post_pred,
                        status="LOOSE_MATCH",
                        matched_pre=p,
                        note="Same upper bound; subject expression may differ.",
                    )

    # Special semantic hint: `! (x \in S)` in post + `check_plaintext S y` in
    # pre, where x is component of y → unfold of `check_plaintext` likely
    # bridges. This is one of the few domain hints we encode (the predicate
    # `check_plaintext` is canonical in the BNR/CCA ChaChaPoly context).
    if post_pred.kind == "not_mem":
        # post: !(X \in CONTAINER); look for check_plaintext over CONTAINER
        post_cont = post_pred.template.split(", ")[1].rstrip(")") if ", " in post_pred.template else ""
        for p in pre_preds:
            if "check_plaintext" in p.raw and post_cont and post_cont in p.raw:
                return ConjunctVerdict(
                    post_conjunct=post_pred.raw,
                    pred=post_pred,
                    status="LOOSE_MATCH",
                    matched_pre=p,
                    note=("`check_plaintext` predicate in pre bounds the same "
                          "container — its definition unfold yields `!(_ \\in _)`. "
                          "Try `rewrite /check_plaintext`."),
                )

    # Otherwise: missing
    return ConjunctVerdict(
        post_conjunct=post_pred.raw,
        pred=post_pred,
        status="MISSING",
        matched_pre=None,
        note=("No matching template in pre. Need to either extend "
              "invariant/seq to introduce, or derive from program slice."),
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def analyze_session(session_dir: Path) -> str:
    projection = read_proof_state_projection(
        session_dir,
        live_tool_name="subgoal-gap",
    )
    if projection.status in ("candidate_closed", "verified"):
        return (
            "[SUBGOAL GAP ANALYSIS]  proof complete\n\n"
            "No pRHL subgoal gap remains."
        )
    if projection.consistency.errors:
        return _format_projection_error(
            projection.consistency.errors,
            "subgoal-gap",
        )
    state = read_session_state(session_dir)
    if not state.has_current:
        return f"[error] {state.current_path} not found"
    raw = state.raw_for_goal_tools
    info = parse_goal(raw)

    out: list[str] = []
    out.append(f"[SUBGOAL GAP ANALYSIS]  goal_type={info.goal_type}, "
               f"remaining={info.num_remaining}")
    out.append("")

    if info.goal_type != "pRHL":
        # Goal is out of subgoal_gap's structural-decomposition scope.
        # Route the agent to the tool family that DOES handle this shape.
        out.append(f"[note] subgoal_gap operates on pRHL goals "
                   f"(including post-call ambient implications with `&1/&2` "
                   f"variable headers and pre/post labels).")
        out.append(f"Got goal_type={info.goal_type}. Suggested tools for this shape:")
        out.append("")
        if info.goal_type == "probability":
            out.append("  • `-bridge-lemmas`   — for `Pr[L.proc ~ R.proc] = ...` "
                       "or `Pr[A] = Pr[B]`, scan context for transitivity-chain "
                       "candidates.")
            out.append("  • `ec_pr_path_diff` (auto-fired as [AUTO-DIFF]) — "
                       "compares the two game-functor application trees node-by-node.")
        elif info.goal_type == "ambient":
            out.append("  • `-suggest-close`   — for pure logic/algebra goals, "
                       "suggest closing tactics (`rewrite`, `ring`, `algebra`, "
                       "`smt` with hints).")
            out.append("  • `-diagnose`        — if you hit an error here, diagnose "
                       "the failure mode (often a missing smt hint or a missed "
                       "case split on a `bad` event).")
            out.append("  • Hand-decompose: ambient implications `H1 ⇒ ... ⇒ C` "
                       "are typically discharged by `move=> H1 ... Hn`, then "
                       "smt/algebra on the residual conclusion using introduced "
                       "hypotheses as hints.")
        elif info.goal_type == "eager":
            out.append("  • Eager goals: the `eager` family (`eager while` / "
                       "`eager proc` / `eager call`) has specific argument forms — "
                       "inspect `tactic_forms` for the exact form before applying.")
            out.append("  • `-goal-info` will show the eager LHS/RHS structure.")
        elif info.goal_type == "hoare" or info.goal_type == "phoare":
            out.append("  • Single-side hoare/phoare: `proc; <wp/sp/while/seq/...>` "
                       "into the body, then individual tactics on the resulting "
                       "ambient goals.")
            out.append("  • For phoare-with-bound: `byphoare` to convert into a "
                       "pHL judgment on the proc body.")
        elif info.goal_type == "equiv":
            out.append("  • Equiv goal (programs not yet inlined): start with "
                       "`proc.` then decide between sym tactics like `sim`, "
                       "`call (named-equiv)`, or hand inlining.")
            out.append("  • After `proc; inline *` (or partial inlines), the goal "
                       "becomes pRHL — re-run `-subgoal-gap` then.")
        out.append("")
        out.append("Raw goal preview (for inspection):")
        out.append(f"pre  = {info.pre[:160]!r}{'...' if len(info.pre) > 160 else ''}")
        out.append(f"post = {info.post[:160]!r}{'...' if len(info.post) > 160 else ''}")
        return "\n".join(out)

    # Strip "pre = " / "post = " labels if present (post-fix swap_align stitches them in)
    pre = re.sub(r'^\s*pre\s*=\s*', '', info.pre).strip()
    post = re.sub(r'^\s*post\s*=\s*', '', info.post).strip()

    pre_conjuncts = split_conjuncts(pre)
    post_conjuncts = split_conjuncts(post)

    pre_preds = [classify_predicate(c) for c in pre_conjuncts]
    post_preds = [classify_predicate(c) for c in post_conjuncts]

    out.append(f"PRE  ({len(pre_preds)} conjuncts):")
    for i, p in enumerate(pre_preds):
        out.append(f"  [{i}] kind={p.kind:<18} template={p.template}")
        out.append(f"      raw: {p.raw[:150]}")
    out.append("")
    out.append(f"POST ({len(post_preds)} conjuncts) — gap analysis:")
    out.append("")

    proved = []
    loose = []
    missing = []
    for pred in post_preds:
        v = match_post_against_pre(pre_preds, pred)
        if v.status == "PROVED_BY_PRE":
            proved.append(v)
        elif v.status == "LOOSE_MATCH":
            loose.append(v)
        else:
            missing.append(v)

    # ── Program-slice-aware mode ──
    # If the LHS/RHS first statement is a procedure call, look for a named
    # equiv whose two sides match the call pair. If found, project the
    # missing conjuncts against that equiv's POST — a missing conjunct
    # provable by the equiv's post is reclassified PROVIDED-BY-NEXT-CALL.
    next_call_equiv: Optional[NamedEquiv] = None
    next_call_resolved_missing: list[ConjunctVerdict] = []
    ec_file = _find_source_ec_file(session_dir)
    if ec_file and ec_file.exists() and info.left_stmts and info.right_stmts:
        lhs_stmt = info.left_stmts[0]
        rhs_stmt = info.right_stmts[0]
        if lhs_stmt.get("type") == "CALL" and rhs_stmt.get("type") == "CALL":
            lhs_proc = lhs_stmt.get("procedure", "")
            rhs_proc = rhs_stmt.get("procedure", "")
            try:
                ec_text = ec_file.read_text(encoding="utf-8", errors="replace")
                next_call_equiv = find_matching_equiv_for_calls(
                    ec_text, lhs_proc, rhs_proc,
                )
            except Exception:
                next_call_equiv = None

    if next_call_equiv:
        eq_post_conjuncts = split_conjuncts(next_call_equiv.post)
        eq_post_preds = [classify_predicate(c) for c in eq_post_conjuncts]
        # Walk missing list; reclassify those covered by equiv's post
        still_missing: list[ConjunctVerdict] = []
        for v in missing:
            covered = False
            for ep in eq_post_preds:
                if ep.template == v.pred.template:
                    v.status = "PROVIDED_BY_NEXT_CALL"
                    v.note = (f"Provided by `{next_call_equiv.name}`'s POST "
                              f"(line {next_call_equiv.line_num}): "
                              f"`{ep.raw[:80]}`.")
                    next_call_resolved_missing.append(v)
                    covered = True
                    break
                # Loose match for size_le (same upper bound)
                if (ep.kind == v.pred.kind == "size_le"):
                    pre_k = ep.template.split(",")[1].strip().rstrip(")") if "," in ep.template else ""
                    post_k = v.pred.template.split(",")[1].strip().rstrip(")") if "," in v.pred.template else ""
                    if pre_k and post_k and pre_k == post_k:
                        v.status = "PROVIDED_BY_NEXT_CALL"
                        v.note = (f"Provided by `{next_call_equiv.name}`'s POST "
                                  f"(loose match — same upper bound).")
                        next_call_resolved_missing.append(v)
                        covered = True
                        break
            if not covered:
                # Heuristic: ={res} in equiv post + post conjunct of form `lhs = rhs`
                # where the call's result vars match (e.g. c2{1} = c1{2})
                if v.pred.kind == "eq" and "=" in next_call_equiv.post and "{res}" in next_call_equiv.post:
                    lhs_call = info.left_stmts[0]
                    rhs_call = info.right_stmts[0]
                    # Heuristic match: post conjunct's two sides are the result
                    # variables of the LHS / RHS calls
                    raw_clean = v.pred.raw.replace(" ", "")
                    # Check both directions
                    lhs_var = _extract_call_result_var(lhs_call.get("text", ""))
                    rhs_var = _extract_call_result_var(rhs_call.get("text", ""))
                    if lhs_var and rhs_var:
                        cand1 = f"{lhs_var}{{1}}={rhs_var}{{2}}"
                        cand2 = f"{rhs_var}{{2}}={lhs_var}{{1}}"
                        if raw_clean.replace(" ", "") in (cand1, cand2):
                            v.status = "PROVIDED_BY_NEXT_CALL"
                            v.note = (f"Provided by `{next_call_equiv.name}`'s "
                                      f"POST `={{res}}` after substitution "
                                      f"(LHS result `{lhs_var}` ~ RHS result `{rhs_var}`).")
                            next_call_resolved_missing.append(v)
                            covered = True
            if not covered:
                still_missing.append(v)
        missing = still_missing

    for v in proved:
        out.append(f"  ✓ PROVED-BY-PRE")
        out.append(f"      post: {v.post_conjunct[:120]}")
        out.append(f"      pre : {v.matched_pre.raw[:120]}")
        out.append("")
    for v in loose:
        out.append(f"  ~ LOOSE-MATCH ({v.note})")
        out.append(f"      post: {v.post_conjunct[:120]}")
        out.append(f"      pre : {v.matched_pre.raw[:120]}")
        out.append("")
    for v in next_call_resolved_missing:
        out.append(f"  ↪ PROVIDED-BY-NEXT-CALL ({v.note})")
        out.append(f"      post: {v.post_conjunct[:120]}")
        out.append("")
    for v in missing:
        out.append(f"  ✗ MISSING")
        out.append(f"      post: {v.post_conjunct[:200]}")
        out.append(f"      kind: {v.pred.kind}; symbols: {sorted(v.pred.symbols)[:8]}")
        out.append(f"      → {v.note}")
        out.append("")

    out.append("[SUMMARY]")
    out.append(f"  Proved-by-pre        : {len(proved)}")
    out.append(f"  Loose-match          : {len(loose)}  (likely monotonicity / refinement)")
    if next_call_equiv:
        out.append(f"  Provided-by-next-call: {len(next_call_resolved_missing)}  "
                   f"(via `{next_call_equiv.name}` POST — declared at "
                   f"line {next_call_equiv.line_num})")
    out.append(f"  Missing              : {len(missing)}  (need new fact via invariant/seq/unfold)")

    return "\n".join(out)


def _find_source_ec_file(session_dir: Path) -> Optional[Path]:
    """Read session_meta.json to find the original .ec file."""
    meta = session_dir / "session_meta.json"
    if not meta.exists():
        return None
    try:
        import json
        data = json.loads(meta.read_text(encoding="utf-8"))
        f = data.get("file")
        if f:
            return Path(f)
    except Exception:
        pass
    return None


def _extract_call_result_var(stmt_text: str) -> str:
    """`c2 <@ ChaCha(...).enc(k, n, p2)` → `c2`"""
    m = re.match(r'\s*(\w+)\s*<@', stmt_text)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Mode B: --against-lemma NAME [args...]
# Project a named equiv's PRE against current state's pre/hypotheses.
# Answers: "if I apply this lemma now, which of its pre-conditions are
# already covered, which are loose, which are missing?"
# ---------------------------------------------------------------------------

def _apply_substitution(text: str, subs: dict) -> str:
    """Word-boundary replace each key with its value in text.

    Process longer keys first so `n0` doesn't get partially replaced when
    `n00` is also a key.
    """
    if not subs:
        return text
    keys_sorted = sorted(subs.keys(), key=lambda k: -len(k))
    for k in keys_sorted:
        v = subs[k]
        text = re.sub(rf'\b{re.escape(k)}\b', v, text)
    return text


def _map_name_parts(map_name: str) -> set[str]:
    """`SplitD.ROF.RO.m{1}` → {SplitD, ROF, RO, m}.
    Strip {1}/{2} side marks and dot-split."""
    cleaned = re.sub(r'\{[12]\}$', '', map_name.strip())
    return set(p for p in cleaned.split('.') if p)


def _map_names_likely_aliased(a: str, b: str) -> bool:
    """Heuristic: parts of the shorter name all appear in the longer name.

    Catches `ROF.m` (lemma-local functor param) vs `SplitD.ROF.RO.m{1}`
    (externally-qualified clone instance) — same `ROF` and `m` components.

    NOT a proof of aliasing — just a strong "worth flagging" signal.
    """
    pa = _map_name_parts(a)
    pb = _map_name_parts(b)
    short, long_ = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return short.issubset(long_) and len(short) >= 2  # need ≥ 2 parts to avoid noise


def match_lemma_pre_against_current(
    lemma_pre_pred: Predicate,
    current_pre_preds: list[Predicate],
) -> ConjunctVerdict:
    """For one lemma-pre conjunct, find best match in current pre."""
    # Trivially-true reflexive equality (post-substitution): X = X
    if lemma_pre_pred.kind == "eq":
        # template form is "eq(LHS, RHS)"; extract and compare normalized
        m = re.match(r'eq\((.+?),\s*(.+)\)$', lemma_pre_pred.template)
        if m and m.group(1).strip() == m.group(2).strip():
            return ConjunctVerdict(
                post_conjunct=lemma_pre_pred.raw,
                pred=lemma_pre_pred,
                status="PROVED_BY_PRE",
                matched_pre=None,
                note="Reflexive (X = X after witness substitution) — closes by `auto`.",
            )

    # Exact template match
    for cp in current_pre_preds:
        if cp.template == lemma_pre_pred.template:
            return ConjunctVerdict(
                post_conjunct=lemma_pre_pred.raw,
                pred=lemma_pre_pred,
                status="PROVED_BY_PRE",
                matched_pre=cp,
                note="Identical template — covered by current state.",
            )

    # forall_impl_mem: try module-qualification fuzzy match
    if lemma_pre_pred.kind == "forall_impl_mem":
        lemma_map = lemma_pre_pred.template.split(",")[0].lstrip("forall_impl_mem(").strip()
        lemma_cont = (lemma_pre_pred.template.split(",")[2].rstrip(")")
                      if lemma_pre_pred.template.count(",") >= 2 else "")
        for cp in current_pre_preds:
            if cp.kind != "forall_impl_mem":
                continue
            cp_map = cp.template.split(",")[0].lstrip("forall_impl_mem(").strip()
            cp_cont = (cp.template.split(",")[2].rstrip(")")
                       if cp.template.count(",") >= 2 else "")
            if (cp_cont.strip() == lemma_cont.strip() and
                _map_names_likely_aliased(cp_map, lemma_map)):
                return ConjunctVerdict(
                    post_conjunct=lemma_pre_pred.raw,
                    pred=lemma_pre_pred,
                    status="LOOSE_MATCH",
                    matched_pre=cp,
                    note=(f"Possible module-qualification alias: lemma uses "
                          f"`{lemma_map}`, your context has `{cp_map}` "
                          f"(same container, dot-parts overlap). "
                          f"If they ARE aliases (check clone scope), this matches; "
                          f"otherwise extend invariant."),
                )

    # not-mem with check_plaintext bridge (same as match_post_against_pre)
    if lemma_pre_pred.kind == "not_mem":
        post_cont = (lemma_pre_pred.template.split(", ")[1].rstrip(")")
                     if ", " in lemma_pre_pred.template else "")
        for cp in current_pre_preds:
            if "check_plaintext" in cp.raw and post_cont and post_cont in cp.raw:
                return ConjunctVerdict(
                    post_conjunct=lemma_pre_pred.raw,
                    pred=lemma_pre_pred,
                    status="LOOSE_MATCH",
                    matched_pre=cp,
                    note=("Pre has `check_plaintext` over same container — its "
                          "definition unfold yields `!(_ \\in _)`. "
                          "After ecall, try `rewrite /check_plaintext`."),
                )

    # size_le with same upper bound, possibly different subject
    if lemma_pre_pred.kind == "size_le":
        lemma_k = (lemma_pre_pred.template.split(",")[1].strip().rstrip(")")
                   if "," in lemma_pre_pred.template else "")
        for cp in current_pre_preds:
            if cp.kind != "size_le":
                continue
            cp_k = (cp.template.split(",")[1].strip().rstrip(")")
                    if "," in cp.template else "")
            if cp_k and lemma_k and cp_k == lemma_k:
                return ConjunctVerdict(
                    post_conjunct=lemma_pre_pred.raw,
                    pred=lemma_pre_pred,
                    status="LOOSE_MATCH",
                    matched_pre=cp,
                    note=("Same upper bound; subject expression differs "
                          "(lemma's `arg.`3` vs your context — check that the "
                          "two refer to the same value at lemma-call time)."),
                )

    # Conjunct mentions `arg{N}` or `arg{N}.`<field>` → almost certainly
    # resolved by ecall's argument substitution at apply time.
    if re.search(r'\barg\{[12]\}', lemma_pre_pred.raw):
        return ConjunctVerdict(
            post_conjunct=lemma_pre_pred.raw,
            pred=lemma_pre_pred,
            status="LOOSE_MATCH",
            matched_pre=None,
            note=("References `arg{1}`/`arg{2}` — resolved by ecall's argument "
                  "substitution (auto-handled if your call args match the "
                  "procedure signature)."),
        )

    return ConjunctVerdict(
        post_conjunct=lemma_pre_pred.raw,
        pred=lemma_pre_pred,
        status="MISSING",
        matched_pre=None,
        note=("No matching template in current pre. Genuinely missing — "
              "extend the enclosing call's invariant or seq earlier "
              "to introduce this fact."),
    )


def analyze_against_lemma(session_dir: Path, lemma_call_text: str) -> str:
    """Project `lemma_call_text` (e.g. `H_equiv x{1} M1.m{1} M2.m{1}`)
    against the current goal's pre/hypotheses.

    Output: per-conjunct coverage report for the lemma's PRE.
    """
    # Parse the call text
    tokens = lemma_call_text.split()
    if not tokens:
        return "[error] empty lemma name"
    lemma_name = tokens[0]
    arg_exprs = tokens[1:]

    # Find source file
    ec_file = _find_source_ec_file(session_dir)
    if not ec_file or not ec_file.exists():
        return f"[error] could not locate source .ec file for session {session_dir}"

    ec_text = ec_file.read_text(encoding="utf-8", errors="replace")
    equivs = parse_named_equivs(ec_text)
    target = next((e for e in equivs if e.name == lemma_name), None)
    if target is None:
        return (f"[error] Lemma `{lemma_name}` not found among "
                f"{len(equivs)} named equivs in {ec_file.name}. "
                f"Available: {[e.name for e in equivs[:10]]}")

    # Parse params (e.g. "n0 mr0 ms0")
    param_tokens = target.params.strip().split()
    # Substitution map (only if user supplied as many args as lemma has params)
    subs: dict[str, str] = {}
    if arg_exprs and len(arg_exprs) == len(param_tokens):
        subs = dict(zip(param_tokens, arg_exprs))

    # Apply substitution to lemma PRE
    pre_subbed = _apply_substitution(target.pre, subs)

    # Read current state
    projection = read_proof_state_projection(
        session_dir,
        live_tool_name="subgoal-gap",
    )
    if projection.status in ("candidate_closed", "verified"):
        return (
            "[SUBGOAL GAP ANALYSIS]  proof complete\n\n"
            "No candidate lemma precondition gap remains."
        )
    if projection.consistency.errors:
        return _format_projection_error(
            projection.consistency.errors,
            "subgoal-gap --against-lemma",
        )
    state = read_session_state(session_dir)
    if not state.has_current:
        return f"[error] {state.current_path} not found"
    raw = state.raw_for_goal_tools
    info = parse_goal(raw)
    if info.goal_type != "pRHL":
        return (f"[error] Expected pRHL goal, got {info.goal_type}. "
                f"`--against-lemma` is for projection at a pRHL state where "
                f"you're considering a `call`/`ecall LEMMA`.")

    current_pre = re.sub(r'^\s*pre\s*=\s*', '', info.pre).strip()
    current_pre_conjuncts = split_conjuncts(current_pre)
    current_pre_preds = [classify_predicate(c) for c in current_pre_conjuncts]

    lemma_pre_conjuncts = split_conjuncts(pre_subbed)
    lemma_pre_preds = [classify_predicate(c) for c in lemma_pre_conjuncts]

    # Shape compatibility check: does lemma's LHS/RHS module-chain match the
    # current goal's first-call programs? Misalignment is a strong signal that
    # the lemma does NOT apply at this point — without this check, an agent
    # could read "2 covered, 1 missing" and think the lemma is close to working,
    # when actually the program shapes are wrong entirely.
    shape_warning: list[str] = []
    if info.left_stmts and info.right_stmts:
        cur_lhs = info.left_stmts[0].get("procedure", "")
        cur_rhs = info.right_stmts[0].get("procedure", "")
        cur_lhs_chain = _proc_module_chain(cur_lhs) if cur_lhs else ""
        cur_rhs_chain = _proc_module_chain(cur_rhs) if cur_rhs else ""
        lemma_lhs_chain = _proc_module_chain(target.lhs_proc)
        lemma_rhs_chain = _proc_module_chain(target.rhs_proc)
        lhs_match = cur_lhs_chain == lemma_lhs_chain
        rhs_match = cur_rhs_chain == lemma_rhs_chain
        if not (lhs_match and rhs_match):
            shape_warning.append(
                "⚠ SHAPE MISMATCH: lemma's LHS/RHS module chains don't match "
                "the current goal's first-call programs. The pre-coverage "
                "report below is informational only — applying this lemma "
                "will likely fail before the pre-conditions are even checked."
            )
            shape_warning.append(
                f"    Current goal LHS: {cur_lhs_chain or '(none)'}"
            )
            shape_warning.append(
                f"    Lemma   LHS:      {lemma_lhs_chain}  "
                f"{'✓' if lhs_match else '✗ DIFFERENT'}"
            )
            shape_warning.append(
                f"    Current goal RHS: {cur_rhs_chain or '(none)'}"
            )
            shape_warning.append(
                f"    Lemma   RHS:      {lemma_rhs_chain}  "
                f"{'✓' if rhs_match else '✗ DIFFERENT'}"
            )
            shape_warning.append("")

    out: list[str] = []
    out.append(f"[LEMMA-PRE RESIDUAL]  Target: {lemma_name} "
               f"(declared at {ec_file.name}:{target.line_num})")
    if target.params.strip():
        out.append(f"  Params:  {target.params.strip()}")
    if subs:
        out.append(f"  Witnesses: {' '.join(f'{k}={v}' for k, v in subs.items())}")
    elif arg_exprs:
        out.append(f"  Args provided: {arg_exprs} "
                   f"(but lemma has {len(param_tokens)} params; substitution skipped)")
    out.append("")
    if shape_warning:
        out.extend(shape_warning)
    out.append(f"  Lemma LHS: {target.lhs_proc[:80]}")
    out.append(f"  Lemma RHS: {target.rhs_proc[:80]}")
    out.append("")
    out.append(f"  Coverage of {lemma_name}'s PRE ({len(lemma_pre_preds)} conjuncts):")
    out.append("")

    covered = []
    loose = []
    missing = []
    for lp in lemma_pre_preds:
        v = match_lemma_pre_against_current(lp, current_pre_preds)
        if v.status == "PROVED_BY_PRE":
            covered.append(v)
        elif v.status == "LOOSE_MATCH":
            loose.append(v)
        else:
            missing.append(v)

    for v in covered:
        out.append(f"    ✓ COVERED   {v.post_conjunct[:120]}")
    for v in loose:
        out.append(f"    ~ LOOSE     {v.post_conjunct[:120]}")
        out.append(f"                {v.note}")
    for v in missing:
        out.append(f"    ✗ MISSING   {v.post_conjunct[:120]}")
        out.append(f"                {v.note}")
    out.append("")
    out.append(f"  Verdict: {len(covered)} covered, {len(loose)} loose, "
               f"{len(missing)} missing")
    if loose or missing:
        out.append("")
        out.append("  Action surface (informational, not prescriptive):")
        if missing:
            out.append("    • genuinely missing facts: extend the invariant of the "
                       "ENCLOSING `call (_:...)` to include these, OR insert a "
                       "`seq M N : (...)` before this point.")
        if loose:
            out.append("    • LOOSE matches: typically resolved by `move=> /> *`, "
                       "`rewrite /<def>`, or smt with the matched fact as hint. "
                       "If module-qualification alias mismatch — verify clone scope "
                       "(cf. local functor parameter names).")

    return "\n".join(out)


def _format_projection_error(errors: list[str], tool_name: str) -> str:
    lines = [
        f"[error] Inconsistent proof-state projection for `{tool_name}`.",
        "Refusing structural analysis until the session state is reconciled.",
        "",
    ]
    lines.extend(f"  - {e}" for e in errors[:5])
    if len(errors) > 5:
        lines.append(f"  - ... {len(errors) - 5} more")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("-d", "--session-dir", required=True)
    p.add_argument("--against-lemma", metavar="CALL", default="",
                   help="Project a candidate lemma's PRE against current "
                        "state. Pass the lemma name + witness args as a single "
                        "string, e.g. --against-lemma 'H_equiv x{1} M1.m{1} "
                        "M2.m{1}'. Reports COVERED / LOOSE / MISSING per "
                        "conjunct of the lemma's PRE.")
    args = p.parse_args()
    sd = Path(args.session_dir)
    if not sd.exists():
        print(f"[error] {sd} not found", file=sys.stderr)
        return 2
    if args.against_lemma:
        print(analyze_against_lemma(sd, args.against_lemma))
    else:
        print(analyze_session(sd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
