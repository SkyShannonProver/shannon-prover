#!/usr/bin/env python3
"""Compiler-style state diff for EC goal transitions.

Compares pre-tactic vs post-tactic goal text along structural metrics
(subgoal count, Pr[..] terms, quantifiers, module nesting depth, top-level
connectives) and a small set of cosmetic-noise patterns (beta-redex,
unreduced glob chains, eta wrappers, iota match-redex). Emits a short
``[STATE-DIFF]`` block that classifies the transition into one of:

    PROGRESS                       structural metrics improved cleanly
    PROGRESS_WITH_COSMETIC_NOISE   structural improved + cosmetic gunk added
    NEUTRAL_OR_NO_CHANGE           all metrics same (block suppressed)
    REGRESSION                     structural metrics strictly worse
    MIXED                          some better, some worse

Motivation: EC's raw goal text doesn't separate "syntactically uglier"
from "structurally worse". A ``rewrite`` that simplifies the module tree
(genuine progress) frequently introduces a beta-redex `(fun ... => ..) arg`
that *looks* worse but is one ``simplify`` away from disappearing. Without
a structural verdict, agents conflate the two and chase ``-prev``,
cascading into session restarts.

Public API:
    compute_state_diff(pre_raw, post_raw, tactic) -> dict
    format_state_diff_block(diff) -> str  (or "" if not informative)
"""
from __future__ import annotations

import os
import re
import sys
from typing import Optional


try:
    from core.easycrypt.analysis.ec_goal_parser import classify_goal, _extract_goal_body  # type: ignore
except Exception:  # pragma: no cover — fallback if parser unavailable
    def classify_goal(text: str) -> str:  # type: ignore
        return "ambient"

    def _extract_goal_body(text: str) -> str:  # type: ignore
        return text or ""


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------


_PROMPT_RE = re.compile(r"^\[\d+\|[^\]]*\]>\s*$")
_HEADER_RE = re.compile(
    r"^(?:Current goal(?:\s*\(remaining:\s*\d+\))?|No more goals)\s*$"
)


def _strip_session_chrome(text: str) -> str:
    """Drop prompt markers and `Current goal` headers, keep the body."""
    if not text:
        return ""
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            out.append(ln)
            continue
        if _PROMPT_RE.match(s):
            continue
        if _HEADER_RE.match(s):
            continue
        out.append(ln)
    return "\n".join(out)


def _normalize_for_compare(text: str) -> str:
    """Light normalization so 'identical-up-to-whitespace' counts as no-change."""
    if not text:
        return ""
    # Drop trailing whitespace per line; collapse internal runs of blanks.
    lines = [ln.rstrip() for ln in _strip_session_chrome(text).splitlines()]
    # Drop blank lines so trailing-newline differences don't matter.
    lines = [ln for ln in lines if ln.strip()]
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Metric extractors
# ---------------------------------------------------------------------------


_REMAINING_RE = re.compile(r"Current goal\s*\(remaining:\s*(\d+)\)")
_NO_MORE_RE = re.compile(r"No more goals")
_BARE_GOAL_RE = re.compile(r"Current goal(?!\s*\(remaining)")


def _extract_subgoal_count(raw: str) -> int:
    """Pick the LAST state marker — earlier markers are stale replay chatter.

    Returns 0 when "No more goals" is present, N when "(remaining: N)", and
    1 when only a bare "Current goal" header is found. Returns 1 as a
    benign default when nothing parses (so single-goal text doesn't read as
    "subgoals exploded to 0" and trip false REGRESSION).
    """
    if not raw:
        return 1
    candidates: list[tuple[int, int]] = []
    for m in _REMAINING_RE.finditer(raw):
        candidates.append((m.start(), int(m.group(1))))
    for m in _BARE_GOAL_RE.finditer(raw):
        candidates.append((m.start(), 1))
    for m in _NO_MORE_RE.finditer(raw):
        candidates.append((m.start(), 0))
    if not candidates:
        return 1
    candidates.sort()
    return candidates[-1][1]


# Match Pr[ at top level — we then walk balanced brackets and skip inner Pr[.
_PR_OPEN_RE = re.compile(r"\bPr\s*\[")


def _count_top_level_pr(body: str) -> int:
    """Count Pr[...] occurrences NOT nested inside another Pr[...].

    Walks the string and, on each top-level Pr[, advances past its matching
    `]`. Anything else is ignored. This is intentionally simpler than a
    full EC parser — we only need a stable structural metric, not a
    semantically-perfect one.
    """
    if not body:
        return 0
    n = 0
    i = 0
    L = len(body)
    while i < L:
        m = _PR_OPEN_RE.search(body, i)
        if not m:
            break
        n += 1
        # Walk balanced brackets [/] starting at the '['.
        j = body.find("[", m.start())
        if j < 0:
            break
        depth = 0
        k = j
        while k < L:
            c = body[k]
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    k += 1
                    break
            k += 1
        i = k
    return n


def _count_top_level_quantifiers(body: str) -> int:
    """Count `forall`/`exists` outside any `fun ... =>` lambda body
    AND outside any `Pr[...]` event-expression. Earlier code only
    suppressed inside `fun`, so a goal like `Pr[A : forall x, P x]`
    inflated quantifiers count by 1 — the forall is INSIDE Pr's
    event spec and is not user-visible top-level structure. Audit
    2026-04-29 caught this on synthetic edge cases; real pRHL goals
    rarely trigger it because the Pr's event is usually a simple
    equality, but probability bound proofs (PRG / br93) sometimes
    embed `forall` inside `Pr[... : ... forall ...]`.
    """
    if not body:
        return 0
    n = 0
    paren_depth = 0
    bracket_depth = 0  # `[...]` depth — Pr[...] event spec lives here
    fun_paren_depths: list[int] = []
    i = 0
    L = len(body)
    while i < L:
        c = body[i]
        if c == "(":
            paren_depth += 1
            i += 1
            continue
        if c == ")":
            while fun_paren_depths and fun_paren_depths[-1] >= paren_depth:
                fun_paren_depths.pop()
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue
        if c == "[":
            bracket_depth += 1
            i += 1
            continue
        if c == "]":
            bracket_depth = max(0, bracket_depth - 1)
            i += 1
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < L and (body[j].isalnum() or body[j] == "_"):
                j += 1
            word = body[i:j]
            if word == "fun":
                fun_paren_depths.append(paren_depth)
            elif word in ("forall", "exists"):
                if not fun_paren_depths and bracket_depth == 0:
                    n += 1
            i = j
            continue
        i += 1
    return n


_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")


def _max_module_chain_depth(body: str) -> int:
    """Maximum nesting of `M(N(O(...)))` chains in the goal text.

    A "chain" is a sequence of name-followed-by-( reachable purely by
    descending into the FIRST argument. Skips function applications like
    `f(x, y)` (no nested name+paren immediately inside) and lambda-arg
    parens. We're after EC module/functor nesting like
    `RealOrcls(OChaChaPoly(IFinRO))` (depth 3) and
    `RO_Pair(Split1.IdealAll.RO, Split2.IdealAll.RO)` (depth 2 at root).

    Returns 0 if the body has no name+paren at all.
    """
    if not body:
        return 0
    max_depth = 0
    # Find every "Name(" candidate, then walk inwards counting nested
    # name+paren openings on the leading edge.
    pos = 0
    L = len(body)
    while pos < L:
        m = _NAME_RE.match(body, pos)
        if not m:
            pos += 1
            continue
        end = m.end()
        if end < L and body[end] == "(":
            depth = _scan_chain_depth(body, end)
            if depth > max_depth:
                max_depth = depth
            pos = end + 1
        else:
            pos = end
    return max_depth


def _scan_chain_depth(body: str, lparen_idx: int) -> int:
    """Given the index of `(` after a Name, return chain depth (>=1).

    Walks leading-edge nested `Name(` openings until either no more or
    paren imbalance.
    """
    L = len(body)
    depth = 1
    i = lparen_idx + 1
    while i < L:
        # Skip whitespace
        while i < L and body[i].isspace():
            i += 1
        if i >= L:
            break
        # Read a name
        nm = _NAME_RE.match(body, i)
        if not nm:
            break
        i = nm.end()
        if i < L and body[i] == "(":
            depth += 1
            i += 1
            continue
        else:
            break
    return depth


# Top-level connectives we count as "logical complexity":
#   /\, \/, =>, =, <=, <
# "=" and "<=" are noisy (EC uses them in many positions) — we count them
# at top *paren* level, NOT inside any parenthesized subexpression.
_CONNECTIVES = ("/\\", "\\/", "=>", "<=", "=")


def _count_top_connectives(body: str) -> int:
    """Count occurrences of EC's top-level connectives at paren depth 0."""
    if not body:
        return 0
    n = 0
    paren_depth = 0
    bracket_depth = 0
    i = 0
    L = len(body)
    while i < L:
        c = body[i]
        if c == "(":
            paren_depth += 1
            i += 1
            continue
        if c == ")":
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue
        if c == "[":
            bracket_depth += 1
            i += 1
            continue
        if c == "]":
            bracket_depth = max(0, bracket_depth - 1)
            i += 1
            continue
        if paren_depth == 0 and bracket_depth == 0:
            for tok in _CONNECTIVES:
                if body.startswith(tok, i):
                    # Don't double-count "=>" as "=" + ">", "<=" as "<" + "=".
                    n += 1
                    i += len(tok)
                    break
            else:
                i += 1
        else:
            i += 1
    return n


# ---------------------------------------------------------------------------
# Cosmetic-noise detectors
# ---------------------------------------------------------------------------


# (fun <args> => <body>) <arg-tuple>     (applied lambda — beta-redex)
_BETA_RE = re.compile(r"\(\s*fun\b[^()]*=>[^()]*\)\s*[(\w]")


def _detect_beta_redex(body: str) -> bool:
    """True iff `body` contains an applied `(fun ... => ...)` form."""
    if not body:
        return False
    # The simple regex above misses lambdas with parens in the body. Do
    # a lightweight balanced scan as a backstop: find `(fun `, walk to
    # matching `)`, then require non-whitespace/non-newline immediately
    # after — that's the application argument.
    if _BETA_RE.search(body):
        return True
    i = 0
    L = len(body)
    while True:
        idx = body.find("(fun", i)
        if idx < 0:
            return False
        # Require word boundary after fun
        if idx + 4 < L and (body[idx + 4].isalnum() or body[idx + 4] == "_"):
            i = idx + 1
            continue
        # Require `=>` somewhere before close
        depth = 1
        j = idx + 1
        saw_arrow = False
        while j < L and depth > 0:
            if body[j] == "(":
                depth += 1
            elif body[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            elif body[j] == "=" and j + 1 < L and body[j + 1] == ">":
                saw_arrow = True
            j += 1
        if depth != 0 or not saw_arrow:
            i = idx + 1
            continue
        # Look at the next non-space char after the closing `)`.
        k = j + 1
        while k < L and body[k] in " \t":
            k += 1
        if k < L and (body[k] == "(" or body[k].isalnum() or body[k] == "_"):
            return True
        i = j + 1


_GLOB_RE = re.compile(r"\(\s*glob\s+([A-Za-z_][\w]*(?:\([^()]*\))?)")


def _detect_unreduced_glob(body: str) -> bool:
    """True iff `(glob M(N(O...)))` appears at module-chain depth >= 3."""
    if not body:
        return False
    for m in _GLOB_RE.finditer(body):
        chain = m.group(1)
        depth = _max_module_chain_depth(chain)
        if depth >= 3:
            return True
    return False


# fun x => f x   where x is a single bound variable not appearing in f.
_ETA_RE = re.compile(
    r"\bfun\s+([A-Za-z_]\w*)\s*=>\s*([A-Za-z_][\w.]*)\s+\1\b"
)


def _detect_eta_expansion(body: str) -> bool:
    if not body:
        return False
    for m in _ETA_RE.finditer(body):
        var, fn = m.group(1), m.group(2)
        if var == fn:
            continue  # `fun x => x x` — not eta
        # Cheap check: the function name doesn't itself bind `var`.
        return True
    return False


# match <ctor> <args> with ... end — iota redex (rare in EC interactive output).
_IOTA_RE = re.compile(r"\bmatch\b[^.]*?\bwith\b[^.]*?\bend\b", re.DOTALL)


def _detect_iota_redex(body: str) -> bool:
    if not body:
        return False
    return bool(_IOTA_RE.search(body))


# ---------------------------------------------------------------------------
# Metrics container
# ---------------------------------------------------------------------------


def _compute_metrics(raw: str) -> dict:
    """Compute the full metric vector + extracted body for one side."""
    body = _extract_goal_body(raw) if raw else ""
    if not body:
        # Fall back to chrome-stripped raw if extract_goal_body returns empty.
        body = _strip_session_chrome(raw)
    # Subgoal count uses the FULL raw because the marker may live above body.
    subgoal_n = _extract_subgoal_count(raw)
    return {
        "goal_type": classify_goal(raw) if raw else "ambient",
        "subgoals_count": subgoal_n,
        "pr_terms_count": _count_top_level_pr(body),
        "quantifiers_count": _count_top_level_quantifiers(body),
        "module_depth_max": _max_module_chain_depth(body),
        "top_connectives_count": _count_top_connectives(body),
    }


def _detect_cosmetic_noise(post_body: str, pre_body: str) -> list[str]:
    """Return cosmetic-noise tags newly introduced by the tactic.

    A tag is "new" if the pattern appears in post but did NOT appear in
    pre — otherwise it's pre-existing noise the tactic neither created
    nor cleaned, and surfacing it would be misleading.
    """
    noise: list[str] = []
    checks = (
        ("beta_redex", _detect_beta_redex),
        ("unreduced_glob", _detect_unreduced_glob),
        ("eta_expansion", _detect_eta_expansion),
        ("iota_redex", _detect_iota_redex),
    )
    for tag, detector in checks:
        post_has = detector(post_body)
        pre_has = detector(pre_body)
        if post_has and not pre_has:
            noise.append(tag)
    return noise


# ---------------------------------------------------------------------------
# Verdict + recommendation
# ---------------------------------------------------------------------------


_STRUCT_KEYS = (
    "subgoals_count",
    "pr_terms_count",
    "quantifiers_count",
    "module_depth_max",
    "top_connectives_count",
)


def _compute_verdict(pre_m: dict, post_m: dict, noise: list[str],
                     tactic: str = "",
                     text_unchanged: bool = False) -> str:
    """Verdict on a tactic's structural effect.

    Decision tree (root-cause rewrite, 2026-04-29):

    The previous version compared 5 metrics including module_depth_max
    and top_connectives_count. Replay audit on 5 verified-clean lemmas
    showed those two metrics fire REGRESSION on 70-89% of legitimate
    pRHL steps — `proc` / `inline` / `call <named>` / `wp` / `sp` all
    legitimately unfold the program structure, increasing module
    depth and connective count without regressing the proof. The model
    was misclassifying the dominant case.

    The reliable signal is text-level equality of the normalized goal
    body: toxic loops from rejected bare named-call probes leave it
    bit-identical; legitimate steps mutate it. Subgoal count change is
    the second reliable signal (proof structure progress). Everything
    else (Pr[], quantifiers, module nesting) is noise as a verdict
    input — kept as displayed metrics, not decision inputs.

    Verdicts emitted (and when):
      PROGRESS                — proof closed (post_subgoals=0) OR
                                subgoal_count strictly decreased.
      PROGRESS_DECOMPOSITION  — decomposition tactic + subgoal_count
                                strictly increased. Stays visible
                                because the count change is the
                                ONLY confirmation seq/case/etc landed.
      PROGRESS_WITH_COSMETIC_NOISE
                              — proof actually progressed but cosmetic
                                noise (beta-redex etc) was introduced.
      NEUTRAL_OR_NO_CHANGE    — text bit-identical (catches toxic loops)
                                OR no informative change.
      REGRESSION              — non-decomposition tactic increased
                                subgoal_count. Genuine anomaly.
      (no emit)               — legitimate intermediate steps. Saves
                                agent attention; goal text itself
                                already shows what changed.
    """
    pre_n = pre_m.get("subgoals_count", 0) or 0
    post_n = post_m.get("subgoals_count", 0) or 0

    # Proof closed.
    if post_n == 0 and pre_n > 0:
        return "PROGRESS"

    # Toxic-loop signature: EC accepted the tactic, but the goal body
    # is bit-identical after normalization. This is the discriminator
    # the previous metric-only model couldn't distinguish from a
    # legitimate unfold.
    if text_unchanged:
        return "NEUTRAL_OR_NO_CHANGE"

    # Subgoal count strictly increased AND text changed: a legitimate
    # decomposition step. An earlier tactic-name heuristic consistently
    # missed `congr` / `call (_: Inv)` / `have h : P` / `while (I)` /
    # compound tactics containing `case` — every one a legitimate decomposition.
    # Toxic-loop "subgoal increased on a no-op" was already caught above
    # by text_unchanged. So count-up + text-change = decomposition,
    # period.
    if post_n > pre_n:
        return "PROGRESS_DECOMPOSITION"

    # Subgoal count strictly decreased: proof structurally advanced.
    if post_n < pre_n:
        return "PROGRESS_WITH_COSMETIC_NOISE" if noise else "PROGRESS"

    # post_n == pre_n, text changed, no closure, no decomposition.
    # If ANY metric strictly decreased (and none strictly increased
    # in a way that would normally signal regression — but we already
    # return early on subgoal increase), treat as PROGRESS. This
    # catches `rewrite -LEMMA` simplifying the module tree without
    # changing subgoal count: a legitimate structural improvement
    # where the only signal is that some metric got smaller.
    deltas = {k: post_m.get(k, 0) - pre_m.get(k, 0) for k in _STRUCT_KEYS}
    if any(d < 0 for d in deltas.values()):
        return "PROGRESS_WITH_COSMETIC_NOISE" if noise else "PROGRESS"

    # No discriminating signal: dominant case for pRHL unfolding
    # (`proc`, `inline`, `call <named>`, `wp`, `sp`, `have ->`).
    # Don't synthesize a verdict — agent reads the goal text directly.
    return "NEUTRAL_OR_NO_CHANGE"


# Friendly noise descriptions used in the recommendation text.
_NOISE_FIX = {
    "beta_redex": (
        "applied lambda `(fun .. => ..) arg` — reduce with `simplify`, "
        "`=> /=`, or close with `auto => />`"
    ),
    "unreduced_glob": (
        "`(glob M(N(O..)))` chain — usually disappears after `proc` or "
        "`byequiv` lifts the goal into the program"
    ),
    "eta_expansion": (
        "eta-expanded `fun x => f x` — `simplify` or `congr` collapses it"
    ),
    "iota_redex": (
        "`match` on a known constructor — `simplify` reduces it"
    ),
}


def _build_recommendation(verdict: str, pre_m: dict, post_m: dict,
                          noise: list[str], tactic: str = "") -> str:
    """Compose a short, generic recommendation. NO project-specific names."""
    deltas = {k: post_m.get(k, 0) - pre_m.get(k, 0) for k in _STRUCT_KEYS}

    def _fmt_delta(label: str, key: str) -> str:
        d = deltas[key]
        if d == 0:
            return ""
        arrow = "->"
        return f"{label} {pre_m.get(key, 0)}{arrow}{post_m.get(key, 0)}"

    improved_bits = [
        s for s in (
            _fmt_delta("subgoals", "subgoals_count"),
            _fmt_delta("Pr[]", "pr_terms_count"),
            _fmt_delta("quantifiers", "quantifiers_count"),
            _fmt_delta("module_depth", "module_depth_max"),
            _fmt_delta("connectives", "top_connectives_count"),
        ) if s and (
            (deltas.get(_label_to_key(s)) or 0) < 0
        )
    ]
    worsened_bits = [
        s for s in (
            _fmt_delta("subgoals", "subgoals_count"),
            _fmt_delta("Pr[]", "pr_terms_count"),
            _fmt_delta("quantifiers", "quantifiers_count"),
            _fmt_delta("module_depth", "module_depth_max"),
            _fmt_delta("connectives", "top_connectives_count"),
        ) if s and (
            (deltas.get(_label_to_key(s)) or 0) > 0
        )
    ]

    # Recommendation philosophy: describe state, don't prescribe action.
    # Tools surface information; the agent decides what to do with it.
    # We keep verdicts (PROGRESS / REGRESSION / etc.) as compressed
    # summaries, but the recommendation text only DESCRIBES what's
    # there — agent reasons about whether to undo, continue, or pivot.
    if verdict == "PROGRESS":
        bits = ", ".join(improved_bits) or "metrics improved"
        return f"Structural progress: {bits}."
    if verdict == "PROGRESS_DECOMPOSITION":
        # Tactic-specific descriptive note: what kind of split happened
        # and what each new subgoal contains. Agent decides whether the
        # split is tractable (continue) or whether a different
        # invariant/intermediate would work better (undo + retry).
        bits = ", ".join(worsened_bits) or "new subgoal(s) added"
        tac_lower = (tactic or "").strip().lower()
        if tac_lower.startswith("seq"):
            note = (
                f"Decomposition by `seq K K : (P)`: {bits} reflect "
                f"seq's design — one subgoal asserts P, the rest "
                f"continue the original proof with P available as a "
                f"hypothesis. The metric increase is structural, "
                f"not regressive."
            )
        elif tac_lower.startswith("transitivity"):
            note = (
                f"Decomposition by `transitivity`: {bits} reflect "
                f"the intermediate point — chain legs (LHS~M and M~RHS) "
                f"plus pre/post ambient side-conditions are now separate "
                f"subgoals. The metric increase is structural, not "
                f"regressive."
            )
        elif tac_lower.startswith("case"):
            note = (
                f"Decomposition by `case`: {bits} reflect a split on a "
                f"hypothesis or value — each branch has the case fact "
                f"as an additional precondition."
            )
        elif tac_lower.startswith("if"):
            note = (
                f"Decomposition by `if`: split into then-branch and "
                f"else-branch (plus an ambient side-condition that "
                f"the if-conditions agree on both sides for pRHL). "
                f"{bits} reflect this structural split."
            )
        elif tac_lower.startswith("split"):
            note = (
                f"Decomposition by `split`: the conjunction in the "
                f"post is now N separate subgoals (one per conjunct). "
                f"{bits} reflect that fanout."
            )
        elif tac_lower.startswith("progress"):
            # `progress` is a high-risk decomposer: it eagerly
            # introduces and destructs hypotheses, so each leaf
            # inherits only its locally-needed slice of context.
            # Audit 2026-04-30 (step3 Tree-0.0, 00:51-01:18):
            # `progress.` from a relational ambient goal produced 13
            # leaves; one leaf needed `p0{1} = p0{2}` from the outer
            # context, but progress had stripped it. Agent diagnosed
            # the loss 8 min after the commit and spent 15 more
            # minutes thrashing (12 undos + a full chain replay)
            # before stumbling on `congr; rewrite !get_setE; done.`
            # for an unrelated leaf shape — never recovered the
            # missing hypothesis. This warning surfaces the risk
            # at commit time so the agent can either avoid progress
            # or prefix `move=> &1 &2 [Heq1 [Heq2 ...]];` to name
            # and preserve relational equalities BEFORE the split.
            new_n = post_m.get("subgoals_count", 0) - pre_m.get(
                "subgoals_count", 0)
            big = new_n >= 5
            note = (
                f"Decomposition by `progress`: {bits}. "
                f"{'WARNING — ' if big else 'Note: '}"
                f"`progress` eagerly (a) introduces all leading "
                f"quantifiers (including memory binders `&1` `&2`) "
                f"and (b) destructs conjunctive hypotheses. Two "
                f"consequences each leaf must work around: "
                f"(1) relational equalities from the outer context "
                f"(e.g. `x{{1}} = x{{2}}`) may NOT propagate to every "
                f"leaf — if a downstream leaf needs one, undo and "
                f"prefix with `move=> &1 &2 [Heq1 [Heq2 ...]];` to "
                f"name and preserve those equalities BEFORE "
                f"`progress`. (2) `&1` `&2` are already in scope "
                f"after progress — do NOT re-introduce with "
                f"`move=> &1 &2` (you'll get \"unknown memory: &1\")."
            )
        else:
            note = (
                f"Decomposition by `{(tactic or '').split('.')[0][:40]}`: "
                f"{bits} reflect tactic-specific subgoal/invariant "
                f"introduction, not regression."
            )
        return note
    if verdict == "PROGRESS_WITH_COSMETIC_NOISE":
        bits = ", ".join(improved_bits) or "metrics improved"
        fixes = "; ".join(_NOISE_FIX.get(t, t) for t in noise)
        return (
            f"Structural progress: {bits}. New cosmetic noise also "
            f"appeared (would simplify away under reduction): {fixes}."
        )
    if verdict == "REGRESSION":
        # Post-2026-04-29 semantics: REGRESSION fires only when
        # subgoal_count strictly increased AND the tactic is NOT a
        # known decomposition. Either the tactic spawned speculative
        # subgoals (e.g. `apply LEMMA` with too-loose unification) or
        # it's a decomposition we don't yet recognize.
        sg_pre = pre_m.get("subgoals_count", 0)
        sg_post = post_m.get("subgoals_count", 0)
        return (
            f"Subgoal count {sg_pre}->{sg_post}: increased by a "
            f"non-decomposition tactic. Possible causes: "
            f"(a) tactic spawned speculative subgoals "
            f"(e.g. unification too loose, apply with wrong arity); "
            f"(b) tactic IS a decomposition not yet in the recognized "
            f"list (seq/case/transitivity/if/split/elim/exists)."
        )
    # NEUTRAL_OR_NO_CHANGE (suppressed at format time, recommendation
    # only used by tests / serialization).
    return "No structural change."


# Map a "label X->Y" snippet back to its metric key, for delta lookup.
_LABEL_TO_KEY = {
    "subgoals": "subgoals_count",
    "Pr[]": "pr_terms_count",
    "quantifiers": "quantifiers_count",
    "module_depth": "module_depth_max",
    "connectives": "top_connectives_count",
}


def _label_to_key(formatted: str) -> str:
    label = formatted.split(" ", 1)[0]
    return _LABEL_TO_KEY.get(label, "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_state_diff(pre_raw: str, post_raw: str, tactic: str) -> dict:
    """Compute the structured pre/post diff for a tactic transition.

    Returns a JSON-serializable dict with keys:
        pre_metrics, post_metrics, cosmetic_noise, verdict, recommendation, tactic

    All inputs are strings; missing inputs are tolerated (treated as empty).
    """
    pre_raw = pre_raw or ""
    post_raw = post_raw or ""
    tactic = (tactic or "").strip()

    pre_metrics = _compute_metrics(pre_raw)
    post_metrics = _compute_metrics(post_raw)

    pre_body = _extract_goal_body(pre_raw) or _strip_session_chrome(pre_raw)
    post_body = _extract_goal_body(post_raw) or _strip_session_chrome(post_raw)

    # Text-level equality is the toxic-loop discriminator.
    pre_norm = _normalize_for_compare(pre_body)
    post_norm = _normalize_for_compare(post_body)
    text_unchanged = bool(pre_norm) and pre_norm == post_norm

    noise = _detect_cosmetic_noise(post_body, pre_body)
    verdict = _compute_verdict(
        pre_metrics, post_metrics, noise, tactic, text_unchanged,
    )
    recommendation = _build_recommendation(
        verdict, pre_metrics, post_metrics, noise, tactic
    )

    return {
        "tactic": tactic[:120],
        "pre_metrics": pre_metrics,
        "post_metrics": post_metrics,
        "cosmetic_noise": noise,
        "text_unchanged": text_unchanged,
        "verdict": verdict,
        "recommendation": recommendation,
    }


def format_state_diff_block(diff: dict) -> str:
    """Render the diff as a multi-line `[STATE-DIFF]` block.

    Returns "" when the verdict is NEUTRAL_OR_NO_CHANGE (boring — no
    point spending agent attention on a no-change emission). Block is
    bounded to ~10 lines.
    """
    if not diff:
        return ""
    verdict = diff.get("verdict") or ""
    if verdict == "NEUTRAL_OR_NO_CHANGE":
        return ""

    pre = diff.get("pre_metrics") or {}
    post = diff.get("post_metrics") or {}

    def _row(label: str, key: str) -> Optional[str]:
        a, b = pre.get(key, 0), post.get(key, 0)
        if a == b:
            return None
        return f"  {label}: {a} -> {b}"

    rows = [r for r in (
        _row("subgoals", "subgoals_count"),
        _row("Pr[] terms", "pr_terms_count"),
        _row("quantifiers", "quantifiers_count"),
        _row("module_depth_max", "module_depth_max"),
        _row("top_connectives", "top_connectives_count"),
    ) if r]

    noise = diff.get("cosmetic_noise") or []
    rec = diff.get("recommendation") or ""

    lines = [f"[STATE-DIFF] verdict={verdict}"]
    if rows:
        lines.append("structural metrics (changed only):")
        lines.extend(rows)
    if noise:
        lines.append("cosmetic noise (newly introduced): " + ", ".join(noise))
    # Wrap recommendation onto continuation lines so the block stays
    # under ~12 visual lines. We hard-wrap at ~92 chars.
    rec_lines = _wrap(rec, 92)
    if rec_lines:
        lines.append("recommendation: " + rec_lines[0])
        for ln in rec_lines[1:]:
            lines.append("  " + ln)
    return "\n".join(lines) + "\n"


def _wrap(text: str, width: int) -> list[str]:
    """Greedy word-wrap. Returns [] for empty input."""
    if not text:
        return []
    words = text.split()
    out: list[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
            continue
        if len(cur) + 1 + len(w) > width:
            out.append(cur)
            cur = w
        else:
            cur = cur + " " + w
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------------------
# CLI entry-point (debugging aid)
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Compute structural state diff.")
    ap.add_argument("--pre", required=True, help="Path to pre-tactic goal text.")
    ap.add_argument("--post", required=True, help="Path to post-tactic goal text.")
    ap.add_argument("--tactic", default="", help="Tactic that was applied.")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of block.")
    args = ap.parse_args()

    pre_text = open(args.pre, encoding="utf-8", errors="replace").read()
    post_text = open(args.post, encoding="utf-8", errors="replace").read()
    diff = compute_state_diff(pre_text, post_text, args.tactic)
    if args.json:
        print(json.dumps(diff, indent=2))
    else:
        block = format_state_diff_block(diff)
        sys.stdout.write(block or "[STATE-DIFF] (no informative change)\n")
