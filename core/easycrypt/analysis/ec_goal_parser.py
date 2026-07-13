#!/usr/bin/env python3
"""Structured goal state parser for EasyCrypt.

Classifies goal type (pRHL, eager, hoare, phoare, ambient, probability)
and extracts structured data. Used by the prover agent to select the
right tactic family and by swap_search for automated alignment.

Usage (via session_cli):
    python3 core/easycrypt/session_cli.py -d .ec_session -goal-info

Usage (standalone):
    python3 core/easycrypt/ec_goal_parser.py < current.out
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class GoalInfo:
    goal_type: str  # "pRHL" | "eager" | "hoare" | "phoare" | "ambient" | "probability"
    raw_text: str
    num_remaining: int = 0  # from "Current goal (remaining: N)"

    # pRHL fields (populated when goal_type == "pRHL")
    left_stmts: list[dict] = field(default_factory=list)
    right_stmts: list[dict] = field(default_factory=list)
    pre: str = ""
    post: str = ""
    matches: list[dict] = field(default_factory=list)
    safe_swaps: list[str] = field(default_factory=list)
    dependency_conflicts: list[dict] = field(default_factory=list)

    # eager fields
    eager_left_stmt: str = ""
    eager_left_proc: str = ""
    eager_right_proc: str = ""
    eager_right_stmt: str = ""
    eager_pre: str = ""
    eager_post: str = ""

    # probability fields
    event_expr: str = ""
    event_vars: list[str] = field(default_factory=list)
    # prob_form: "eq"|"ineq"|"prob_eq_const"|"diff_eq"|"compound"|"adv_eq"|"adv_diff_ineq"|"adv_ineq"|"single"
    prob_form: str = ""
    prob_lhs_game: str = ""
    prob_lhs_oracle: str = ""   # argument(s) to lhs game, e.g. "GenChaChaPoly(OCC(IFinRO))"
    prob_rhs_game: str = ""
    prob_rhs_oracle: str = ""   # argument(s) to rhs game, e.g. "IndRO"
    prob_intro_required: bool = False

    # bd-hoare / phoare fields (populated when goal_type == "phoare")
    phoare_proc: str = ""       # the procedure, e.g. "G.main"
    phoare_pre: str = ""
    phoare_post: str = ""       # the post-condition (NOT defaulted to `true`)
    phoare_cmp: str = ""        # the bound comparator: "=", "<=" or ">="
    phoare_bound: str = ""      # the probability bound, e.g. "P" or "1%r / 2%r"

    # hoare field: a literally-`true` postcondition is a REAL trivial obligation EC
    # emits (e.g. the deterministic branch of a bd-hoare `seq`), distinct from a parse
    # failure that left the post empty.
    trivial_postcondition: bool = False
    prob_intro_prefix: str = ""
    # diff_eq extra fields (populated when prob_form == "diff_eq")
    diff_eq_lhs_neg_game: str = ""   # the subtracted game on the LHS
    diff_eq_rhs_neg_game: str = ""   # the subtracted game on the RHS

    # ambient classification (populated when goal_type == "ambient")
    ambient_shape: str = ""  # "trivial_rel"|"lossless"|"eq_mem_init"|"proc_bound"|"algebra"|"simple_eq"|"logical"
    # prob_compound fields (populated when goal_type == "probability" and prob_form == "compound")
    prob_compound_lhs: list[dict] = field(default_factory=list)  # [{game, oracle, event}, ...]
    prob_compound_rhs: list[dict] = field(default_factory=list)

    # tactic guidance
    suggested_tactics: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Execution-level KB details per suggested tactic
    tactic_details: list[dict] = field(default_factory=list)
    # Plan-vs-reality check (if proof_plan.json is available)
    plan_check: Optional[dict] = None


# ---------------------------------------------------------------------------
# Goal type classification
# ---------------------------------------------------------------------------

# Structural markers unique to each goal type in EC's -emacs output.
# These are stable across EC versions because they're part of the emacs protocol.
_EAGER_RE = re.compile(r"eager\s*\[", re.MULTILINE)
_PRHL_SIDES_RE = re.compile(r"&[12]\s*\((?:left|right)\s*\)")  # "&1 (left )" or "&2 (right)"
_PRHL_TILDE_RE = re.compile(r"\.\w+\s+~\s+\S")  # ".<proc> ~ " — any qualified procedure before tilde
_PRHL_POS_RE = re.compile(r"\(\s*\d+[\s.\d-]*\)")  # ( 1--), (11.1), (1), ( 2) — EC statement position markers
_PHOARE_RE = re.compile(r"\[\s*[=<>]+\s*\]")  # [=] 1%r, [<=] 1%r
# EC's compact judgment keywords: `phoare[ M : pre ==> post ] = bound` (and the
# bd_hoare/choare/ehoare variants). This is a DIFFERENT notation from the `[=]`
# bracket above; without it a bd-hoare goal falls through to `hoare`/`ambient` and
# the probability bound is dropped (PBound audit 2026-06-05).
_BDHOARE_KEYWORD_RE = re.compile(r"\b(?:phoare|bd_hoare|choare|ehoare)\s*\[")
_HOARE_KEYWORD_RE = re.compile(r"(?<![\w])hoare\s*\[")
# `phoare[ proc : pre ==> post ] = bound` (bound after the closing bracket): capture
# the procedure, pre, post, comparator and bound.
_PHOARE_JUDGMENT_RE = re.compile(
    r"(?:phoare|bd_hoare|choare|ehoare)\s*\[\s*"
    r"(?P<proc>[^:\]]+?)\s*:\s*(?P<pre>.+?)\s*==>\s*(?P<post>.+?)\s*\]\s*"
    r"(?P<cmp>[<>]?=)\s*(?P<bound>[^\n.]+)",
    re.DOTALL,
)
_PRE_POST_RE = re.compile(r"^pre\s*=", re.MULTILINE)
_PR_RE = re.compile(r"Pr\s*\[")


def classify_goal(raw_text: str) -> str:
    """Classify the goal type from raw EC output text.

    Returns one of: "eager", "pRHL", "equiv", "hoare", "phoare", "ambient", "probability"

    Classification uses structural markers unique to each goal type in EC's
    -emacs output, checked in specificity order (most specific first):

    1. eager  — goal body contains "eager[" (eager judgment, distinct syntax)
    2. pRHL   — has "&1 (left )" / "&2 (right)" headers (two-column program listing)
    3. equiv  — has "Game1.proc ~ Game2.proc" (equivalence before proc/inline)
    4. phoare — has "[=]" or "[<=]" operator (probabilistic hoare)
    5. hoare  — has "pre =" / "post =" without pRHL markers
    6. probability — has "Pr[" (probability expression)
    7. ambient — everything else (pure logic)
    """
    body = _extract_goal_body(raw_text)

    # 1. Eager: distinct "eager[" syntax — never appears in other goal types
    if _EAGER_RE.search(body):
        return "eager"

    # 2. pRHL (after proc/inline): "&1 (left )" and "(N)" position markers
    if _PRHL_SIDES_RE.search(body) and _PRHL_POS_RE.search(body):
        return "pRHL"

    # 2b. pRHL-residue: post-tactic ambient implication form. After
    # `move=> /> *` consumes the program body, the goal becomes
    # `pre ⇒ post` (pure logic) but EC still emits the `&1 (left)` /
    # `&2 (right)` variable headers AND `pre =` / `post =` labels.
    # The pRHL primitive (decompose pre/post into conjuncts) still
    # applies — only the program-slice analysis becomes irrelevant.
    # Without this case, post-call/ecall stuck moments (the most common
    # real-world stuck state) get misclassified as `hoare` and fall out
    # of subgoal_gap's scope.
    if _PRHL_SIDES_RE.search(body) and _PRE_POST_RE.search(body):
        return "pRHL"

    # 3. equiv (before proc): "Game1.proc ~ Game2.proc" with pre/post
    if _PRHL_TILDE_RE.search(body) and _PRE_POST_RE.search(body):
        return "equiv"

    # 3b. bd-hoare/phoare KEYWORD form: `phoare[ M : pre ==> post ] = bound`. EC's
    # compact probabilistic-Hoare judgment — checked before plain `hoare[` so the
    # leading `p`/`bd_`/`c`/`e` is not lost. The `[=]`-bracket form below is the
    # older/alt notation.
    if _BDHOARE_KEYWORD_RE.search(body):
        return "phoare"

    # 4. phoare: "[=] 1%r" or "[<=] bound" operators
    if _PHOARE_RE.search(body):
        return "phoare"

    # 5. hoare: the `hoare[ M : pre ==> post ]` keyword form, or an unfolded goal
    # with `pre =`/`post =` but no pRHL/equiv markers.
    if _HOARE_KEYWORD_RE.search(body) or _PRE_POST_RE.search(body):
        return "hoare"

    # 6. Probability: "Pr[Game.proc() @ &m : event]". If Pr[...] appears
    # behind an implication/quantifier, still classify by the semantic
    # conclusion and let probability guidance say an intro tactic is needed.
    # Treating this as ambient leads to bad closer suggestions (`smt`,
    # `ring`) for goals whose real next move is `move=> H; byphoare ...`.
    if _PR_RE.search(body):
        return "probability"

    # 7. Default: ambient logic (pure propositions, set theory, algebra)
    return "ambient"


def _extract_goal_body(raw_text: str) -> str:
    """Extract the ACTIVE (first) goal body from raw EC output.

    When multiple goals remain, EC shows them all. We extract only the
    first one to avoid misclassification (e.g., a probability goal followed
    by a pRHL subgoal would be classified as pRHL if we read both).
    """
    lines = raw_text.splitlines()
    # Find the FIRST "Current goal" header (= active goal)
    start = 0
    for i, line in enumerate(lines):
        if "Current goal" in line:
            start = i
            break
    # Skip past the separator line (----). No window limit: goals with many
    # hypotheses (e.g. D4_D6 after moves) have 12+ lines above the separator.
    for i in range(start, len(lines)):
        if re.match(r"^-{5,}", lines[i].strip()):
            start = i + 1
            break
        if i > start and "Current goal" in lines[i]:
            break  # next subgoal block — separator not found in this block
    # Trim at prompt markers OR at the next "Current goal" (= next subgoal)
    end = len(lines)
    for i in range(start, len(lines)):
        if re.match(r"^\[\d+\|", lines[i].strip()):
            end = i
            break
        if i > start and "Current goal" in lines[i]:
            end = i
            break
    return "\n".join(lines[start:end])


#: Sentinel returned by ``_extract_remaining_count`` when no state marker is
#: present in the input. Distinct from 0 (= proof genuinely closed via
#: ``No more goals``). Callers / JSON consumers must treat -1 as
#: "indeterminate", NOT as "done".
REMAINING_UNKNOWN = -1


def _extract_remaining_count(raw_text: str) -> int:
    """Extract remaining-goal count from EC session output.

    EC prints three distinct session-state markers:
      - `Current goal (remaining: N)` when N >= 2 goals remain
      - `Current goal` (no parenthesized count) when EXACTLY 1 goal remains
      - `No more goals` when 0 goals remain (proof closed)

    We pick the LAST (most recent) marker in the text so that banner
    output from prior sibling lemmas ("No more goals" emitted as EC
    processes context) doesn't masquerade as the current session state.

    Earlier this function only matched the parenthesized form and
    returned 0 for everything else, conflating "exactly 1 goal remains"
    with "proof closed" — which caused provers to issue qed prematurely
    and get "cannot save an incomplete proof" from EC.

    Returns ``REMAINING_UNKNOWN`` (-1) when no marker is present. Do not
    collapse this into 0 — callers must distinguish "proof done" from
    "can't tell". Agents that read ``num_remaining: 0`` off goal-info and
    try ``qed`` when the state was actually indeterminate have burned
    real time (see 2026-04-23 step3 run: ~10+ minutes of verification
    loops from this exact conflation).
    """
    candidates: list[tuple[int, int]] = []  # (position, count)
    for m in re.finditer(r"Current goal\s*\(remaining:\s*(\d+)\)", raw_text):
        candidates.append((m.start(), int(m.group(1))))
    # Bare `Current goal` not followed by `(remaining:` → exactly 1 goal.
    for m in re.finditer(r"Current goal(?!\s*\(remaining)", raw_text):
        candidates.append((m.start(), 1))
    for m in re.finditer(r"No more goals", raw_text):
        candidates.append((m.start(), 0))
    if not candidates:
        return REMAINING_UNKNOWN
    candidates.sort()
    return candidates[-1][1]


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_goal(raw_text: str) -> GoalInfo:
    """Parse raw EC output into structured GoalInfo."""
    goal_type = classify_goal(raw_text)
    body = _extract_goal_body(raw_text)
    remaining = _extract_remaining_count(raw_text)

    info = GoalInfo(
        goal_type=goal_type,
        raw_text=body[:2000],  # cap for JSON size
        num_remaining=remaining,
    )

    if goal_type == "pRHL":
        _parse_prhl(info, raw_text)
    elif goal_type == "equiv":
        # Summary form (pre-proc, pre-inline): swap_align now returns one
        # CALL Statement per side so downstream Layer-1 can still run a
        # functor-path diff on the two procedure expressions.
        _parse_prhl(info, raw_text)
    elif goal_type == "eager":
        _parse_eager(info, body)
    elif goal_type == "phoare":
        _parse_phoare(info, body)
    elif goal_type == "hoare":
        _parse_hoare(info, body)
    elif goal_type == "probability":
        _parse_probability(info, body)
    elif goal_type == "ambient":
        info.ambient_shape = _classify_ambient_shape(body)

    # No tactic guidance: the parser surfaces only the factual goal structure.
    # `suggested_tactics` / strategy-`warnings` prose (the "Strategy: use X / do
    # NOT use Y" middle-end advice) is removed — the agent decides the move from
    # the structure and pulls `tactic_forms <name>` for the factual argument
    # forms on demand (view boundary: no "which move to make" guidance).
    return info


# ---------------------------------------------------------------------------
# pRHL parser (delegates to swap_align)
# ---------------------------------------------------------------------------


def _parse_prhl(info: GoalInfo, raw_text: str) -> None:
    """Parse pRHL goal using swap_align infrastructure."""
    try:
        from core.easycrypt.analysis.swap_align import (
            parse_prhl_goal, _has_dependency,
        )

        result = parse_prhl_goal(raw_text)
        if result is None:
            return

        info.pre = result.pre
        info.post = result.post
        # vars_written/vars_read are sets on the swap_align statements; sort
        # them at this export boundary so everything derived downstream
        # (dataflow invariant eq-sets, candidate tactic_shapes, preflight
        # hashes) is deterministic across processes (list(set) is
        # PYTHONHASHSEED-ordered).
        info.left_stmts = [
            {"pos": s.pos, "text": s.text.strip(), "type": s.stmt_type,
             "pos_path": s.pos_path,
             "distribution": s.distribution, "procedure": s.procedure,
             "vars_written": sorted(s.vars_written), "vars_read": sorted(s.vars_read)}
            for s in result.left
        ]
        info.right_stmts = [
            {"pos": s.pos, "text": s.text.strip(), "type": s.stmt_type,
             "pos_path": s.pos_path,
             "distribution": s.distribution, "procedure": s.procedure,
             "vars_written": sorted(s.vars_written), "vars_read": sorted(s.vars_read)}
            for s in result.right
        ]
        info.matches = [
            {"left_pos": m.left_pos, "right_pos": m.right_pos,
             "match_type": m.match_type, "label": m.label}
            for m in result.matches
        ]
        info.safe_swaps = result.swaps

        # Build dependency conflicts
        for side_stmts, side in [(result.left, 1), (result.right, 2)]:
            for i, a in enumerate(side_stmts):
                for j, b in enumerate(side_stmts):
                    if i >= j:
                        continue
                    conflict = _has_dependency(side_stmts, a.pos, b.pos)
                    if conflict:
                        info.dependency_conflicts.append({
                            "stmt_a_pos": a.pos, "stmt_b_pos": b.pos,
                            "side": side, "conflict": conflict,
                        })
    except Exception:
        pass  # Fall back to basic info


# ---------------------------------------------------------------------------
# Eager parser
# ---------------------------------------------------------------------------

_EAGER_FULL_RE = re.compile(
    r"eager\s*\[\s*"
    r"(.+?)\s*,\s*"           # left stmt (e.g., "Resample.resample();")
    r"(\S+)\s*~\s*(\S+)"     # proc1 ~ proc2
    r"\s*,\s*(.+?)\s*:\s*"   # right stmt
    r"(.+?)\s*==>\s*"         # pre
    r"(.+?)\s*\]",            # post
    re.DOTALL,
)

# Interactive display format (no pre/post inside brackets):
# eager[ stmt1, proc1 ~ proc2, stmt2; ]
# pre = ={...}
# post = ={...}
_EAGER_DISPLAY_RE = re.compile(
    r"eager\s*\[\s*"
    r"(.+?)\s*,\s*"           # left stmt
    r"(\S+)\s*~\s*(\S+)"     # proc1 ~ proc2
    r"\s*,\s*(.+?)\s*\]",    # right stmt (no pre/post inside)
    re.DOTALL,
)
_EAGER_PRE_RE = re.compile(r"^pre\s*=\s*(.+)$", re.MULTILINE)
_EAGER_POST_RE = re.compile(r"^post\s*=\s*(.+)$", re.MULTILINE)


def _parse_eager(info: GoalInfo, body: str) -> None:
    """Parse an eager judgment goal.

    Handles two formats:
    1. Lemma form: eager [stmt, P ~ Q, stmt : pre ==> post]
    2. Interactive display form: eager[ stmt, P ~ Q, stmt ]  (pre/post on separate lines)
    """
    # Normalize whitespace for regex
    normalized = re.sub(r"\s+", " ", body)
    m = _EAGER_FULL_RE.search(normalized)
    if m:
        info.eager_left_stmt = m.group(1).strip()
        info.eager_left_proc = m.group(2).strip()
        info.eager_right_proc = m.group(3).strip()
        info.eager_right_stmt = m.group(4).strip()
        info.eager_pre = m.group(5).strip()
        info.eager_post = m.group(6).strip()
        return

    # Try interactive display format (pre/post outside brackets)
    m2 = _EAGER_DISPLAY_RE.search(normalized)
    if m2:
        info.eager_left_stmt = m2.group(1).strip()
        info.eager_left_proc = m2.group(2).strip()
        info.eager_right_proc = m2.group(3).strip()
        info.eager_right_stmt = m2.group(4).strip()
        # Extract pre/post from separate lines in original (un-normalized) body
        pre_m = _EAGER_PRE_RE.search(body)
        post_m = _EAGER_POST_RE.search(body)
        if pre_m:
            info.eager_pre = pre_m.group(1).strip()
        if post_m:
            info.eager_post = post_m.group(1).strip()


# ---------------------------------------------------------------------------
# Probability parser
# ---------------------------------------------------------------------------


def _extract_game_name(pr_expr: str) -> str:
    """Extract the top-level game name from a Pr[Game(...).proc() @ &m : e] expression.

    Returns the outermost module name, e.g. "G1" from "G1(GenChaChaPoly(OCC(IFinRO)))".
    """
    m = re.match(r"Pr\s*\[\s*(\w+)", pr_expr.strip())
    return m.group(1) if m else ""


def _extract_game_args(pr_expr: str) -> str:
    """Extract the oracle/argument string passed to the top-level game.

    From "Pr[G1(GenChaChaPoly(OCC(IFinRO))).main() @ &m : res]"
    returns "GenChaChaPoly(OCC(IFinRO))".

    From "Pr[Indist(D(A), IndRO).main() @ &m : res]"
    returns "D(A), IndRO".

    From "Pr[Game.main() @ &m : res]" (no parens) returns "".

    Uses a balanced-parenthesis scan so nested functors are handled correctly.
    """
    # Find the start of the argument list: first '(' after the game name
    # pr_expr starts with "Pr[" so we skip to the game name first.
    inner = re.match(r"Pr\s*\[\s*\w+", pr_expr.strip())
    if not inner:
        return ""
    pos = inner.end()
    if pos >= len(pr_expr) or pr_expr[pos] != "(":
        return ""
    # Balanced scan from pos
    depth = 0
    start = pos + 1
    for i in range(pos, len(pr_expr)):
        if pr_expr[i] == "(":
            depth += 1
        elif pr_expr[i] == ")":
            depth -= 1
            if depth == 0:
                return pr_expr[start:i].strip()
    return ""


def _phoare_clean(s: str) -> str:
    return " ".join(str(s or "").split())


def _parse_phoare(info: GoalInfo, body: str) -> None:
    """Extract the bd-hoare/phoare judgment — procedure, pre, post and the
    probability BOUND. The bound is the whole point of a phoare goal; dropping it
    (and defaulting the post to `true`) is what made PBound's first subgoal read as
    a plain hoare goal with no bound (audit 2026-06-05)."""
    m = _PHOARE_JUDGMENT_RE.search(body)
    if m:
        info.phoare_proc = _phoare_clean(m.group("proc"))
        info.phoare_pre = info.pre = _phoare_clean(m.group("pre"))
        info.phoare_post = info.post = _phoare_clean(m.group("post"))
        info.phoare_cmp = (m.group("cmp") or "=").strip()
        info.phoare_bound = _phoare_clean(m.group("bound")).rstrip(".").strip()
        return
    # Unfolded form: `pre = …`, `post = …`, plus a `[<=]`/`[=]`/`[>=]` bound line.
    pm = re.search(r"^pre\s*=\s*(.+?)(?=^\s*\(|\bpost\s*=|\Z)", body, re.MULTILINE | re.DOTALL)
    if pm:
        info.phoare_pre = info.pre = _phoare_clean(pm.group(1))
    qm = re.search(r"\bpost\s*=\s*(.+?)(?=\[\s*[<>]?=\s*\]|\Z)", body, re.DOTALL)
    if qm:
        info.phoare_post = info.post = _phoare_clean(qm.group(1))
    bm = re.search(r"\[\s*(?P<cmp>[<>]?=)\s*\]\s*(?P<bound>[^\n]+)", body)
    if bm:
        info.phoare_cmp = bm.group("cmp").strip()
        info.phoare_bound = _phoare_clean(bm.group("bound")).rstrip(".").strip()


def _parse_hoare(info: GoalInfo, body: str) -> None:
    """Extract a hoare judgment's pre/post and FLAG a literally-`true` postcondition.
    EC genuinely emits `post = true` for the deterministic branch of a bd-hoare `seq`
    (a goal `auto`/`trivial`/`//` closes); flagging it lets the agent distinguish a
    REAL `… ==> true` obligation from a parse failure that left the post empty — the
    exact confusion that stalled PBound on a trivial subgoal (audit 2026-06-05)."""
    # Only a GENUINE unfolded hoare judgment (an EC `pre = … (prog) post = …` block)
    # is parsed here. A goal that merely starts with `pre = X ==> Y` but has no
    # `post =` line is an ambient/pRHL-residue implication, not a hoare judgment —
    # leave pre/post empty so downstream `==>`-splitters (e.g. ec_obligation_gap) are
    # not derailed by a pre that swallowed the whole conclusion.
    qm = re.search(r"\bpost\s*=\s*(.+?)(?=\[\s*\d+\s*\||\Z)", body, re.DOTALL)
    if not qm:
        return
    info.post = _phoare_clean(qm.group(1))
    pm = re.search(r"^pre\s*=\s*(.+?)(?=^\s*\(|\bpost\s*=|\Z)", body, re.MULTILINE | re.DOTALL)
    if pm:
        info.pre = _phoare_clean(pm.group(1))
    info.trivial_postcondition = info.post.strip().rstrip(".").strip().lower() == "true"


def _parse_probability(info: GoalInfo, body: str) -> None:
    """Parse a probability goal, extracting form (eq/ineq/compound/diff_eq/single) and game names."""
    # Detect prob_form from the operator connecting two Pr[...] expressions.
    # Strip newlines for easier regex matching across line breaks.
    parse_body, intro_prefix = _strip_probability_intro(body)
    info.prob_intro_required = bool(intro_prefix)
    info.prob_intro_prefix = intro_prefix
    flat = " ".join(parse_body.split())

    pr_count = len(re.findall(r"\bPr\s*\[", flat))

    # Advantage forms: goals STARTING with `|...| absolute value wrappers.
    # Detected first because naive pr_count would misclassify as compound (>= 3 Pr terms).
    # Two sub-forms:
    #   adv_eq:        `|Pr[A] - c| = `|Pr[B] - Pr[C]|
    #   adv_diff_ineq: `|Pr[A] - Pr[B]| <= `|Pr[C] - Pr[D]| + epsilon
    # Only trigger when `| is at the START of the goal (not buried in the RHS of Pr[A] <= `|...|)
    if flat.lstrip().startswith("`") and "|" in flat and "Pr" in flat:
        # Check for any absolute-value block containing Pr
        _adv_lhs_m = re.search(r"`\s*\|[^|]*Pr\s*\[", flat)
        if _adv_lhs_m:
            # Determine connecting operator after the first closing |
            _after_first_bar = flat[_adv_lhs_m.start():]
            _bar_close = _after_first_bar.find("|", 2)  # skip opening `|
            _connector = _after_first_bar[_bar_close + 1:].lstrip() if _bar_close != -1 else ""
            if _connector.startswith("=") and not _connector.startswith("=>"):
                info.prob_form = "adv_eq"
            elif _connector.startswith("<="):
                info.prob_form = "adv_diff_ineq"
            else:
                info.prob_form = "adv_eq"  # default to equality form
            # Extract first Pr game (LHS of the absolute value)
            lhs_block_m = re.search(r"`\s*\|([^|]+)\|", flat)
            if lhs_block_m:
                pr_in_lhs = re.search(r"Pr\s*\[[^\]]+\]", lhs_block_m.group(1))
                if pr_in_lhs:
                    info.prob_lhs_game = _extract_game_name(pr_in_lhs.group(0))
                    info.prob_lhs_oracle = _extract_game_args(pr_in_lhs.group(0))
            # Extract second `|...| block's first Pr game (RHS)
            if lhs_block_m:
                rhs_search_start = lhs_block_m.end()
                rhs_block_m = re.search(r"`\s*\|([^|]+)\|", flat[rhs_search_start:])
                if rhs_block_m:
                    pr_in_rhs = re.search(r"Pr\s*\[[^\]]+\]", rhs_block_m.group(1))
                    if pr_in_rhs:
                        info.prob_rhs_game = _extract_game_name(pr_in_rhs.group(0))
                        info.prob_rhs_oracle = _extract_game_args(pr_in_rhs.group(0))
            # Extract event from first Pr[...] term
            ev_m = re.search(r"@\s*&\w+\s*:\s*([^\]]+)\]", parse_body)
            if ev_m:
                info.event_expr = ev_m.group(1).strip()
                info.event_vars = extract_event_vars(info.event_expr)
            return

    # Difference equality: Pr[A] - Pr[B] = Pr[C] - Pr[D]  (e.g. ChaChaPoly step1)
    # Must be checked before the generic pr_count >= 3 compound check, because the
    # compound check would misclassify this form and suppress local_equiv_context.
    diff_eq_m = re.search(
        r"(Pr\s*\[.*?\])\s*-\s*(Pr\s*\[.*?\])\s*=\s*(Pr\s*\[.*?\])\s*-\s*(Pr\s*\[.*?\])",
        flat,
    )
    if diff_eq_m:
        info.prob_form = "diff_eq"
        info.prob_lhs_game = _extract_game_name(diff_eq_m.group(1))
        info.prob_lhs_oracle = _extract_game_args(diff_eq_m.group(1))
        info.prob_rhs_game = _extract_game_name(diff_eq_m.group(3))
        info.prob_rhs_oracle = _extract_game_args(diff_eq_m.group(3))
        info.diff_eq_lhs_neg_game = _extract_game_name(diff_eq_m.group(2))
        info.diff_eq_rhs_neg_game = _extract_game_name(diff_eq_m.group(4))
    elif pr_count >= 3:
        # Sum compound: Pr[A]+Pr[B] <= Pr[C]+Pr[D]  or  Pr[A] <= Pr[B]+Pr[C]
        info.prob_form = "compound"
        _parse_prob_compound(info, flat)
    else:
        # Pr[A] = Pr[B]  — probability equality (two bridges, byequiv approach)
        eq_m = re.search(
            r"(Pr\s*\[.*?\]\s*)\s*=\s*(Pr\s*\[.*?\])", flat
        )
        # Pr[A] <= Pr[B]  — probability inequality, direct form
        ineq_m = re.search(
            r"(Pr\s*\[.*?\])\s*<=\s*(Pr\s*\[.*?\])", flat
        )
        # Pr[A] <= c + Pr[B]  — ineq with constant offset on RHS (e.g. Pr[A] <= 1/2 + Pr[SCDH])
        partial_ineq_m = re.search(r"(Pr\s*\[.*?\])\s*<=", flat)
        # Pr[A] - c <= expr  — advantage ineq (e.g. Pr[CPA] - 1/2 <= qH * Pr[CDH])
        adv_ineq_m = re.search(r"(Pr\s*\[[^\]]+\])\s*-\s*[^=<>]+<=", flat)

        # Pr[A] = constant  — e.g. Pr[Gb] = 1%r/2%r  (byphoare form, NOT byequiv)
        eq_const_m = re.search(r"(Pr\s*\[[^\]]+\])\s*=\s*(?!.*Pr\s*\[)", flat) if pr_count == 1 else None

        if eq_m:
            info.prob_form = "eq"
            info.prob_lhs_game = _extract_game_name(eq_m.group(1))
            info.prob_lhs_oracle = _extract_game_args(eq_m.group(1))
            info.prob_rhs_game = _extract_game_name(eq_m.group(2))
            info.prob_rhs_oracle = _extract_game_args(eq_m.group(2))
        elif eq_const_m:
            info.prob_form = "prob_eq_const"
            info.prob_lhs_game = _extract_game_name(eq_const_m.group(1))
            info.prob_lhs_oracle = _extract_game_args(eq_const_m.group(1))
        elif ineq_m:
            info.prob_form = "ineq"
            info.prob_lhs_game = _extract_game_name(ineq_m.group(1))
            info.prob_lhs_oracle = _extract_game_args(ineq_m.group(1))
            info.prob_rhs_game = _extract_game_name(ineq_m.group(2))
            info.prob_rhs_oracle = _extract_game_args(ineq_m.group(2))
        elif adv_ineq_m:
            # Pr[A] - c <= k * Pr[B]: advantage bounded by scalar multiple
            info.prob_form = "adv_ineq"
            info.prob_lhs_game = _extract_game_name(adv_ineq_m.group(1))
            info.prob_lhs_oracle = _extract_game_args(adv_ineq_m.group(1))
            # Try to extract the RHS Pr game if present (e.g. qH * Pr[CDH...])
            rhs_pr_m = re.search(r"Pr\s*\[[^\]]+\]", flat[adv_ineq_m.end():])
            if rhs_pr_m:
                info.prob_rhs_game = _extract_game_name(rhs_pr_m.group(0))
                info.prob_rhs_oracle = _extract_game_args(rhs_pr_m.group(0))
        elif partial_ineq_m:
            # Pr[A] <= c + Pr[B]: ineq with constant prefix on RHS
            info.prob_form = "ineq"
            info.prob_lhs_game = _extract_game_name(partial_ineq_m.group(1))
            info.prob_lhs_oracle = _extract_game_args(partial_ineq_m.group(1))
            rhs_pr_m = re.search(r"Pr\s*\[[^\]]+\]", flat[partial_ineq_m.end():])
            if rhs_pr_m:
                info.prob_rhs_game = _extract_game_name(rhs_pr_m.group(0))
                info.prob_rhs_oracle = _extract_game_args(rhs_pr_m.group(0))
        else:
            info.prob_form = "single"

    # Extract event expression: match @ &mem : EVENT] at the end of the first Pr[...] term.
    # Using a permissive pattern that handles games with spaces in args (e.g. CCA_game(A, ...)).
    ev_m = re.search(r"@\s*&\w+\s*:\s*([^\]]+)\]", parse_body)
    if ev_m:
        event = ev_m.group(1).strip()
        info.event_expr = event
        info.event_vars = extract_event_vars(event)


def _strip_probability_intro(body: str) -> tuple[str, str]:
    flat = " ".join(body.split())
    first_pr = flat.find("Pr[")
    if first_pr < 0:
        return body, ""
    first_impl = flat.find("=>")
    if 0 <= first_impl < first_pr:
        return flat[first_impl + 2:].strip(), flat[:first_impl].strip()
    quant_m = re.match(r"\s*(forall|exists)\b(.+?),\s*(Pr\s*\[.*)", flat)
    if quant_m:
        return quant_m.group(3).strip(), flat[:quant_m.start(3)].strip()
    return body, ""


def extract_event_vars(event_text: str) -> list[str]:
    """Extract free module state variables from an event expression.

    Given "Bad P.logP F.m", returns ["P.logP", "F.m"].
    Given "res", returns ["res"].
    """
    # Match Module.field patterns (e.g., P.logP, F.m, CCA.log)
    module_vars = re.findall(r"\b([A-Z]\w*\.\w+)\b", event_text)
    # Also match standalone identifiers that look like state (e.g., res)
    standalone = re.findall(r"\b(res)\b", event_text)
    return list(dict.fromkeys(module_vars + standalone))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Tactic guidance
# ---------------------------------------------------------------------------


def _find_pr_expressions(text: str) -> list[str]:
    """Return list of complete Pr[...] strings (balanced brackets)."""
    result = []
    i = 0
    while True:
        m = re.search(r"\bPr\s*\[", text[i:])
        if not m:
            break
        start = i + m.start()
        bstart = i + m.end() - 1
        depth = 0
        found = False
        for j in range(bstart, len(text)):
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    result.append(text[start : j + 1])
                    i = j + 1
                    found = True
                    break
        if not found:
            break
    return result


def _extract_event_from_pr(pr_expr: str) -> str:
    """Extract the event expression after `@ &m :` in a Pr[...] string."""
    m = re.search(r"@\s*&\w+\s*:\s*(.+)", pr_expr, re.DOTALL)
    if not m:
        return ""
    return m.group(1).rstrip("]").strip()


def _split_at_leq(text: str) -> "tuple[str, str] | None":
    """Split `text` at the first top-level `<=` operator."""
    depth = 0
    for i in range(len(text) - 1):
        c = text[i]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif depth == 0 and text[i : i + 2] == "<=":
            return text[:i].rstrip(), text[i + 2 :].lstrip()
    return None


def _parse_prob_compound(info: "GoalInfo", body: str) -> None:
    """Parse a compound probability goal (Pr[A]+Pr[B] <= Pr[C]+Pr[D]) into addend lists."""
    flat = " ".join(body.split())
    sides = _split_at_leq(flat)
    if not sides:
        return
    lhs_text, rhs_text = sides
    for pr_expr in _find_pr_expressions(lhs_text):
        game = _extract_game_name(pr_expr)
        oracle = _extract_game_args(pr_expr)
        event = _extract_event_from_pr(pr_expr)
        if game:
            info.prob_compound_lhs.append({"game": game, "oracle": oracle, "event": event})
    for pr_expr in _find_pr_expressions(rhs_text):
        game = _extract_game_name(pr_expr)
        oracle = _extract_game_args(pr_expr)
        event = _extract_event_from_pr(pr_expr)
        if game:
            info.prob_compound_rhs.append({"game": game, "oracle": oracle, "event": event})


def _classify_ambient_shape(body: str) -> str:
    """Classify an ambient goal's shape for targeted tactic selection.

    Returns one of: "trivial_rel", "lossless", "eq_mem_init", "proc_bound",
    "algebra", "simple_eq", "logical".

    Why: ambient goals after byequiv/call/seq have very predictable shapes.
    Shape-targeted tactic suggestions avoid the agent searching KB by variable
    names in the goal body (same name-matching anti-pattern as prob_eq).
    """
    flat = re.sub(r"\s+", " ", body).strip().lower()

    # Trivial: bare `true`, `res`, or `!false`
    if re.match(r"^\s*(true|res|!\s*false)\s*$", flat):
        return "trivial_rel"

    # Lossless phoare side condition: [=] 1%r or explicit lossless predicate
    if re.search(r"\[=\]\s*1%r|\blossless\b", flat):
        return "lossless"

    # Top-level quantifier or implication — first step is move=> to introduce.
    # Check BEFORE eq_mem_init/arithmetic because goals like
    # "(forall ...) => equiv[ ... res{1} = res{2}]" have {1} inside equiv[...]
    # but the top-level structure is an implication, not a memory equality.
    # Quantified: "forall k &m, Pr[...] = 1%r/4%r"
    quant_m = re.search(r"\bforall\b|\bexists\b|\blambda\b", flat)
    if quant_m:
        # Only treat as logical if quantifier is before any pr[ (not inside an event)
        pr_pos = flat.find("pr[")
        if pr_pos == -1 or quant_m.start() < pr_pos:
            return "logical"
    # Implication: "H => concl" — avoid matching pRHL `==>` and `<=>`.
    # Skip `=>` that follows `fun` (lambda arrow, not top-level implication).
    impl_m = re.search(r"(?<![<=>])=>(?!>)", flat)
    if impl_m and "fun" not in flat[:impl_m.start()]:
        pr_pos = flat.find("pr[")
        if pr_pos == -1 or impl_m.start() < pr_pos:
            return "logical"

    # Memory equality: has {1} or {2} annotation (post-byequiv init conditions).
    # After quantifier/implication checks so that goals like "forall ... => {1} = {2}"
    # are correctly classified as logical (not eq_mem_init).
    if re.search(r"\{[12]\}", body):
        return "eq_mem_init"

    # Size/count bound: `size X <= N` or `count <= bound`
    # Use `<=` or `< ` (with trailing space) to avoid matching `<-` in fmap updates.
    if re.search(r"\bsize\b|\bcount\b|\bcard\b", flat) and re.search(r"<=|<\s", flat):
        return "proc_bound"

    # Arithmetic: reals (`%r`, `real`) or explicit int arithmetic
    if re.search(r"\b\d+%r\b|%r\b|\breal\b", flat) or (
        re.search(r"[+\-*/]", flat) and re.search(r"\bint\b|\bnat\b", flat)
    ):
        return "algebra"

    # Remaining equalities without quantifiers
    if "=" in flat:
        return "simple_eq"

    return "logical"


# ---------------------------------------------------------------------------
# JSON output helpers
# ---------------------------------------------------------------------------


def _proc_base_name(proc: str) -> str:
    """Strip functor args and leading module qualifiers from a procedure path.

    Examples:
      "Poly(OpCCinit.OCC(I_stateless)).mac" → "Poly.mac"
      "D(A, IndBlock).O.Poly.mac"            → "Poly.mac"  (last 2 segments)
      "ChaCha.enc"                            → "ChaCha.enc"

    Why "last two segments": CALL statements like `t' <@ D.O.Poly.mac(...)` match
    local equiv lemmas that reference `Poly.mac` — the outer D.O. wrapping doesn't
    change which primitive is being called. Matching by the last two dotted segments
    keeps the class name + procedure.
    """
    if not proc:
        return proc
    # Strip parenthesized functor args: M(args).foo → M.foo (keep dots outside parens)
    depth = 0
    cleaned = []
    for ch in proc:
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            cleaned.append(ch)
    bare = "".join(cleaned).strip(".")
    parts = [p for p in bare.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return bare


def _compute_seq_suggestions(
    left_stmts: list[dict], right_stmts: list[dict]
) -> list[dict]:
    """Find CALL-at-same-proc pairs as candidate seq cut points.

    When LHS and RHS diverge in stmt count but share CALLs to the same primitive
    (e.g. Poly.mac at LHS pos 5 and RHS pos 3), `seq 5 3 (Inv)` cuts right at the
    matched call so `call <lemma>; auto` can close the prefix. Without this hint the
    agent sees only "stmt count mismatch" and has to guess the cut point.

    Returns a list of {lhs_pos, rhs_pos, procedure, tactic_template} — one per
    matched CALL pair in order of occurrence. Caller picks the first that looks
    useful (typically the earliest match).
    """
    suggestions: list[dict] = []
    lhs_calls = [(i + 1, s) for i, s in enumerate(left_stmts) if s.get("type") == "CALL"]
    rhs_calls = [(i + 1, s) for i, s in enumerate(right_stmts) if s.get("type") == "CALL"]
    used_rhs: set[int] = set()
    for lpos, ls in lhs_calls:
        l_base = _proc_base_name(ls.get("procedure", ""))
        if not l_base:
            continue
        for rpos, rs in rhs_calls:
            if rpos in used_rhs:
                continue
            r_base = _proc_base_name(rs.get("procedure", ""))
            if l_base == r_base:
                suggestions.append({
                    "lhs_pos": lpos,
                    "rhs_pos": rpos,
                    "procedure": l_base,
                    "tactic_template": f"seq {lpos} {rpos} (<invariant>).",
                })
                used_rhs.add(rpos)
                break
    return suggestions


def _analyze_prhl_asymmetry(left_stmts: list[dict], right_stmts: list[dict]) -> dict | None:
    """Detect structural asymmetry between left and right pRHL programs.

    Returns a dict with fields useful to the agent, or None if programs are
    symmetric enough that no asymmetry hint is needed.
    """
    n_left, n_right = len(left_stmts), len(right_stmts)
    lhs_has_while = any(s.get("type") == "WHILE" for s in left_stmts)
    rhs_has_while = any(s.get("type") == "WHILE" for s in right_stmts)

    # Common-prefix length: positions where stmt type + procedure/distribution match
    common_prefix = 0
    for l, r in zip(left_stmts, right_stmts):
        if (l.get("type") == r.get("type")
                and l.get("procedure") == r.get("procedure")
                and l.get("distribution") == r.get("distribution")):
            common_prefix += 1
        else:
            break

    one_sided_while = (lhs_has_while and not rhs_has_while) or (not lhs_has_while and rhs_has_while)
    symmetric = (n_left == n_right and not one_sided_while and common_prefix == n_left)
    if symmetric:
        return None

    hints = []
    if n_left != n_right:
        hints.append(f"stmt count mismatch: left={n_left} right={n_right}; use seq to split or swap to align")
    if one_sided_while:
        side = "left" if lhs_has_while else "right"
        hints.append(f"one-sided WHILE on {side}; use while{{1}} or while{{2}} (not symmetric while)")
    if common_prefix < min(n_left, n_right):
        hints.append(f"common prefix ends at position {common_prefix}; divergence starts there")

    result: dict = {
        "lhs_stmt_count": n_left,
        "rhs_stmt_count": n_right,
        "common_prefix_len": common_prefix,
        "one_sided_while": one_sided_while,
        "structural_hints": hints,
    }
    seq_suggestions = _compute_seq_suggestions(left_stmts, right_stmts)
    if seq_suggestions:
        result["seq_suggestions"] = seq_suggestions
        hints.append(
            f"matched CALL pair(s) found → use `seq L R (<inv>)` to cut at same-proc calls; "
            f"first candidate: {seq_suggestions[0]['tactic_template']} at "
            f"`{seq_suggestions[0]['procedure']}`"
        )
    return result


def _extract_module_root(proc_name: str) -> str:
    """Extract the root module from a procedure name like 'G1(A).proc' → 'G1'."""
    m = re.match(r"(\w+)", proc_name.strip())
    return m.group(1) if m else proc_name


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def goal_to_json(
    info: GoalInfo,
    *,
    local_equiv_context: list[str] | None = None,
    call_equiv_candidates: dict | None = None,
    have_chain_candidates: list[dict] | None = None,
    addend_equiv_candidates: dict | None = None,
    pr_rewrite_candidates: list[dict] | None = None,
) -> dict:
    """Convert GoalInfo to a JSON-serializable dict.

    Structural context fields are injected before strategy hints and legacy
    tactic reference details so the agent reasons from structure, not from raw
    goal text token patterns:
    - local_equiv_context: local equiv names for prob_eq goals (placed after rhs_oracle)
    - call_equiv_candidates: proc→[equiv] map for pRHL CALL statements (placed after safe_swaps)
    - have_chain_candidates: scanned Pr<=Pr lemmas for prob_ineq goals (placed after rhs_oracle)
    - addend_equiv_candidates: game→[equiv] map for prob_compound ambient goals
    - pr_rewrite_candidates: cross-file `lemma pr_* : Pr[A]=Pr[B]` hits whose name
      contains module keywords from the current goal (for example, the
      PROM bridge `pr_RO_FinRO_D` for adjacent RO/FinRO representations)
    """
    d = {}
    d["goal_type"] = info.goal_type
    # Surface the indeterminate case as null + explicit flag so the agent
    # can't silently conflate "can't tell" with "proof done". See
    # REMAINING_UNKNOWN constant above.
    if info.num_remaining == REMAINING_UNKNOWN:
        d["num_remaining"] = None
        d["num_remaining_determined"] = False
    else:
        d["num_remaining"] = info.num_remaining
        d["num_remaining_determined"] = True
    if info.num_remaining == 0:
        d["proof_candidate_closed"] = True
        d["next_action"] = (
            "Proof candidate is structurally closed. Do not commit more "
            "tactics; run session_cli -verify <LEMMA> or the workflow's "
            "offline verifier before accepting the proof."
        )
        return d
    # Prepend a load-bearing warning when indeterminate — agents have
    # historically skipped past `num_remaining: 0` without re-verifying.
    indeterminate_warning = (
        "num_remaining is INDETERMINATE (no `Current goal` or `No more "
        "goals` marker in EC output). DO NOT assume the proof is done. "
        "Force EC to re-emit state with a trivial `-next -c 'idtac.'` "
        "or `-prev` before concluding, then use `-agent-view` / "
        "`-episode-view` for structured state."
    )
    warnings: list[str] = []
    if info.num_remaining == REMAINING_UNKNOWN:
        warnings = [indeterminate_warning] + warnings
    if warnings:
        d["warnings"] = warnings

    if info.goal_type == "pRHL":
        d["pre"] = info.pre
        d["post"] = info.post
        d["left_statements"] = info.left_stmts
        d["right_statements"] = info.right_stmts
        d["matches"] = info.matches
        d["safe_swaps"] = info.safe_swaps
        if call_equiv_candidates:
            d["call_equiv_candidates"] = call_equiv_candidates
        asym = _analyze_prhl_asymmetry(info.left_stmts, info.right_stmts)
        if asym:
            d["stmt_asymmetry"] = asym
        if info.dependency_conflicts:
            d["dependency_conflicts"] = info.dependency_conflicts

    elif info.goal_type == "eager":
        d["eager"] = {
            "left_stmt": info.eager_left_stmt,
            "left_proc": info.eager_left_proc,
            "right_proc": info.eager_right_proc,
            "right_stmt": info.eager_right_stmt,
            "pre": info.eager_pre,
            "post": info.eager_post,
        }

    elif info.goal_type == "phoare":
        # bd-hoare / phoare: surface the post AND the probability BOUND explicitly so
        # the agent is never told `post = true` with the bound silently dropped
        # (PBound audit 2026-06-05).
        if info.pre:
            d["pre"] = info.pre
        if info.phoare_post or info.post:
            d["post"] = info.phoare_post or info.post
        if info.phoare_bound:
            d["phoare_bound"] = {
                "comparator": info.phoare_cmp or "=",
                "bound": info.phoare_bound,
                "procedure": info.phoare_proc,
            }

    elif info.goal_type == "hoare":
        if info.pre:
            d["pre"] = info.pre
        if info.post:
            d["post"] = info.post
        if info.trivial_postcondition:
            # a REAL `… ==> true` obligation EC emits (e.g. the deterministic branch
            # of a bd-hoare `seq`) — genuine, not a parse artifact, and trivial.
            d["trivial_postcondition"] = True

    elif info.goal_type == "equiv":
        # equiv goal (pre-proc): classify by module root to guide opening strategy
        lhs_proc = info.left_stmts[0].get("procedure", "") if info.left_stmts else ""
        rhs_proc = info.right_stmts[0].get("procedure", "") if info.right_stmts else ""
        lhs_root = _extract_module_root(lhs_proc)
        rhs_root = _extract_module_root(rhs_proc)
        same_root = bool(lhs_root and rhs_root and lhs_root == rhs_root)
        d["lhs_proc"] = lhs_proc
        d["rhs_proc"] = rhs_proc
        d["same_root_module"] = same_root
        d["root_module_relation"] = {
            "lhs_root": lhs_root,
            "rhs_root": rhs_root,
            "same_root_module": same_root,
            "meaning": (
                "Procedure endpoint root-name relation only; this is not a "
                "proof action recommendation."
            ),
        }
        if call_equiv_candidates:
            d["matching_local_equivs"] = call_equiv_candidates

    elif info.goal_type == "probability":
        d["prob_form"] = info.prob_form  # "eq"|"ineq"|"diff_eq"|"compound"|"adv_eq"|"adv_ineq"|"single"
        if info.prob_intro_required:
            d["intro_required"] = True
            d["intro_prefix"] = info.prob_intro_prefix
        # Cross-file pr_* rewrite candidates — surface ONCE near the top of the
        # probability block so the agent sees them before diving into
        # byequiv / have-chain strategies.
        if pr_rewrite_candidates:
            d["pr_rewrite_candidates"] = pr_rewrite_candidates
        if info.prob_form == "compound":
            # Compound: list all addends with game names (structural, before any strategy text)
            if info.prob_compound_lhs:
                d["lhs_addends"] = info.prob_compound_lhs
            if info.prob_compound_rhs:
                d["rhs_addends"] = info.prob_compound_rhs
            if addend_equiv_candidates:
                d["addend_equiv_candidates"] = addend_equiv_candidates
        elif info.prob_form == "diff_eq":
            # Difference equality: Pr[A]-Pr[B] = Pr[C]-Pr[D]
            if info.prob_lhs_game:
                d["lhs_pos_game"] = info.prob_lhs_game
            if info.diff_eq_lhs_neg_game:
                d["lhs_neg_game"] = info.diff_eq_lhs_neg_game
            if info.prob_rhs_game:
                d["rhs_pos_game"] = info.prob_rhs_game
            if info.diff_eq_rhs_neg_game:
                d["rhs_neg_game"] = info.diff_eq_rhs_neg_game
            # local_equiv_context is especially important here: after congr., each subgoal
            # is a prob_eq that will need oracle-equiv building blocks.
            if local_equiv_context:
                d["local_equiv_context"] = local_equiv_context
            # congr_subgoals: explicit preview of subgoals after `congr.`, cross-matched
            # against local_equiv_context so the agent plans before committing the tactic.
            congr_sg = []
            if info.prob_lhs_game and info.prob_rhs_game:
                sg1: dict = {"n": 1, "form": "eq", "lhs_game": info.prob_lhs_game, "rhs_game": info.prob_rhs_game}
                if local_equiv_context:
                    sg1["available_equivs"] = local_equiv_context
                congr_sg.append(sg1)
            if info.diff_eq_lhs_neg_game and info.diff_eq_rhs_neg_game:
                sg2: dict = {"n": 2, "form": "eq", "lhs_game": info.diff_eq_lhs_neg_game, "rhs_game": info.diff_eq_rhs_neg_game}
                if local_equiv_context:
                    sg2["available_equivs"] = local_equiv_context
                congr_sg.append(sg2)
            if congr_sg:
                d["congr_subgoals"] = congr_sg
        elif info.prob_form in ("adv_eq", "adv_diff_ineq"):
            # adv_eq: `|Pr[A] - c| = `|Pr[B] - Pr[C]|
            # adv_diff_ineq: `|Pr[A] - Pr[B]| <= `|Pr[C] - Pr[D]| + epsilon
            if info.prob_lhs_game:
                d["lhs_game"] = info.prob_lhs_game
            if info.prob_rhs_game:
                d["rhs_game"] = info.prob_rhs_game
        elif info.prob_form == "adv_ineq":
            # Advantage inequality: Pr[A] - c <= k * Pr[B]
            if info.prob_lhs_game:
                d["lhs_game"] = info.prob_lhs_game
            if info.prob_rhs_game:
                d["rhs_game"] = info.prob_rhs_game
        elif info.prob_form == "prob_eq_const":
            # Probability equals a constant: Pr[A] = c
            if info.prob_lhs_game:
                d["lhs_game"] = info.prob_lhs_game
            if info.prob_lhs_oracle:
                d["lhs_oracle"] = info.prob_lhs_oracle
        else:
            if info.prob_lhs_game:
                d["lhs_game"] = info.prob_lhs_game
            if info.prob_lhs_oracle:
                d["lhs_oracle"] = info.prob_lhs_oracle
            if info.prob_rhs_game:
                d["rhs_game"] = info.prob_rhs_game
            if info.prob_rhs_oracle:
                d["rhs_oracle"] = info.prob_rhs_oracle
            # Structural resource fields placed here so the agent reads
            # available resources before raw goal text token patterns.
            if local_equiv_context:            # prob_eq: local equiv names
                d["local_equiv_context"] = local_equiv_context
            if have_chain_candidates:          # prob_ineq: scanned Pr<=Pr lemmas
                d["have_chain_candidates"] = have_chain_candidates
        d["event_expr"] = info.event_expr
        d["event_vars"] = info.event_vars

    elif info.goal_type == "ambient":
        if info.ambient_shape:
            d["ambient_shape"] = info.ambient_shape

    if info.plan_check:
        d["plan_check"] = info.plan_check

    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    raw = sys.stdin.read()
    info = parse_goal(raw)
    print(json.dumps(goal_to_json(info), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
