r"""Mechanism CORRECT — up-to-bad call-coherence flag (verifier-grounded, flag-only).

Failure this addresses (lemma ``step4_1``):
    The outer skeleton was a CORRECT up-to-bad reduction —
        ``byequiv (_: ... ==> !(UFCMA.bad1 \/ UFCMA.bad2){2} => ={res})``
    (equivalently ``res{1} => res{2} \/ bad1 \/ bad2``). The relation is
    therefore *allowed to break* once a ``bad`` event fires. But at the oracle
    the agent used the DEFAULT lockstep ``call (_: inv)`` instead of the
    up-to-bad two-clause ``call (_: bad, inv)``. The two games structurally
    diverge once ``bad`` fires, so a lockstep call there is undischargeable —
    and the agent then ground a death-spiral of local patches forever.

Signal (purely verifier-computable from rendered text):
    1. ``up_to_bad_names(post_text)`` — the set of bad-event names that appear in
       a TOP-LEVEL ``\/ B`` DISJUNCT of the equiv/byequiv postcondition (i.e. a
       place where the relation may break on bad). CRITICAL precision rule: a
       ``bad`` that appears only inside an IMPLICATION position (e.g.
       ``(UFCMA.bad1{1} => exists tt ...)`` as in ``step4_bad1_lbad1``) is
       legitimate lockstep bad-tracking and must NOT count.
    2. ``is_lockstep_call(call_tactic)`` — True when a ``call (_: ...)`` argument
       has top-level comma-count 0 (the single-clause lockstep form), as opposed
       to the 2-clause ``call (_: bad, inv)`` up-to-bad form. (Same ``,``-count
       discriminator already used in ``session_goal_context`` and ``ec_diagnose``.)

When (1) is non-empty AND (2) holds AND none of the active bad names already
appears inside the lockstep invariant, ``coherence_flag`` returns a neutral
``decision_context`` entry (key ``up_to_bad_call``) — never a verdict, never a
gate. The suggested ``call (_: bad, inv)`` candidate is built by reusing
``ec_inv_from_lemma.extract_call_template`` when a source/lemma is available, and
otherwise assembled mechanically from the lockstep invariant; it is always marked
UNCERTIFIED.
"""
from __future__ import annotations

import re
from typing import Any

# decision_context key + the verbatim surfaced text template. Validators grep for
# the key; the text is f-string-filled with the concrete bad name / invariant.
DECISION_CONTEXT_KEY = "up_to_bad_call"


def _strip_side_annot(name: str) -> str:
    """Drop a trailing ``{1}``/``{2}`` projection so ``UFCMA.bad1{2}`` -> ``UFCMA.bad1``."""
    return re.sub(r"\{[12]\}", "", name).strip()


def _top_level_split(text: str, sep: str) -> list[str]:
    r"""Split ``text`` on ``sep`` only at top level — paren depth 0 AND brace depth 0.

    Both ``()`` and ``{}`` open a group whose interior is NOT top level. The brace
    tracking is what makes ``is_lockstep_call`` correct on a multi-glob frame:
    ``={glob A, glob B, glob C}`` is ONE clause — its commas are inside the ``{...}``
    group, never clause separators — so ``_top_level_split(arg, ",")`` returns a
    single segment for ``={glob A, glob B}`` and a real two-element split only for a
    true top-level comma (``bad, inv``).

    PAREN-GROUP DESCENT: when the WHOLE (stripped) segment is wrapped in one
    balanced ``(...)``/``{...}`` group, the top-level split would trivially return
    just that one segment and the caller could never see the operators inside. So we
    descend one level: a fully-wrapping outer group is peeled before splitting. This
    lets the harvester look inside a parenthesized pre-conjunct group such as
    step4_1's ``(UFCMA.bad1{2} \/ inv ...)`` and find the ``\/``.
    """
    inner = _peel_wrapping_group(text)
    parts: list[str] = []
    depth = 0
    i = 0
    start = 0
    n = len(inner)
    slen = len(sep)
    while i < n:
        ch = inner[i]
        if ch in "({":
            depth += 1
        elif ch in ")}":
            depth -= 1
        elif depth == 0 and inner[i : i + slen] == sep:
            parts.append(inner[start:i])
            i += slen
            start = i
            continue
        i += 1
    parts.append(inner[start:])
    return parts


def _split_top_conjuncts(text: str) -> list[str]:
    r"""Split ``text`` into its top-level conjuncts on BOTH conjunction renderings —
    logical ``/\\`` and boolean ``&&``. EasyCrypt prints some post conjunctions with
    ``/\\`` and others (a boolean-valued post) with ``&&``; step4_1 turn_005's post is
    ``(!UFCMA.bad1{2} => ...) && forall ...``, so we must split on ``&&`` too or the
    genuine bad in the first parenthesized conjunct is never visited."""
    parts: list[str] = []
    for a in _top_level_split(text, "/\\"):
        parts.extend(_top_level_split(a, "&&"))
    return parts


def _split_top_conj_disj(text: str) -> list[str]:
    r"""Split ``text`` into its top-level conjuncts AND disjuncts (on ``/\\`` and
    ``\/`` at paren/brace depth 0). Used to walk a negated-guard LHS so each
    ``!<operand>`` chunk is isolated (``!bad1 /\\ !bad2`` -> two chunks) before the
    whole operand is checked as a bare flag."""
    parts: list[str] = []
    for a in _top_level_split(text, "/\\"):
        parts.extend(_top_level_split(a, "\\/"))
    return parts


def _peel_wrapping_group(text: str) -> str:
    r"""If ``text`` (stripped) is exactly one balanced ``(...)`` or ``{...}`` group,
    return its interior; else return the stripped text unchanged.

    Used so a fully-parenthesized conjunct/disjunct group (e.g. a pre-conjunct
    ``(bad \/ inv ...)``) is descended ONE level before a top-level split, exposing
    the operator inside. Only a group that spans the entire segment is peeled — a
    leading group followed by more text (``(a) \/ b``) is left alone so its own
    top-level operator is still seen."""
    t = text.strip()
    if len(t) < 2 or t[0] not in "({":
        return t
    close = {"(": ")", "{": "}"}[t[0]]
    depth = 0
    for i, ch in enumerate(t):
        if ch in "({":
            depth += 1
        elif ch in ")}":
            depth -= 1
            if depth == 0:
                # The first group closes at i. Only peel if it is the WHOLE segment
                # and the matching closer is the same bracket kind we opened with.
                if ch != close:
                    return t
                if i == len(t) - 1:
                    return t[1:i].strip()
                # PROJECTION-ANNOTATED GROUP `(...){1}` / `(...){2}` — EasyCrypt
                # renders a side annotation that distributes over the WHOLE group,
                # e.g. step4_1's tactic-text post `((res \/ UFCMA.bad2) \/
                # UFCMA.bad1){2}`. The annotation applies to every name inside and
                # harvested names are side-stripped anyway, so peel to the interior
                # and drop the annotation. (Audit 2026-06-09: NOT peeling this was
                # the proximate cause of the step4_1 resume Tree_0_1 false
                # negative — the sticky byequiv harvest stayed ∅ for the whole
                # 104-turn lineage.)
                if t[i + 1 :].strip() in ("{1}", "{2}"):
                    return t[1:i].strip()
                return t
    return t


def _extract_post(text: str) -> str:
    r"""Pull the RELATION BODY (``pre ==> post``) out of an equiv/byequiv goal.

    We return the whole ``pre ==> post`` body, NOT just the consequent, because the
    negated-guard up-to-bad shape ``!(B1 \/ B2) ==> ={res}`` carries the bad names in
    the PRE — ``up_to_bad_names`` then splits the implication itself and harvests the
    guard from the LHS and disjuncts from the RHS. If no equiv/byequiv bracketing is
    present the flat text is treated as the body (callers may pass just the post)."""
    flat = " ".join(text.split())
    # Prefer the inside of an explicit ``equiv[ progs : pre ==> post ]`` / ``byequiv
    # (_: pre ==> post)`` bracketing if present, else operate on the flat text.
    m = re.search(r"\bequiv\s*\[(.*)\]", flat)
    if m:
        flat = m.group(1)
    else:
        m2 = re.search(r"\bbyequiv\b\s*\(?\s*\(?\s*_?\s*:?(.*)", flat)
        if m2:
            flat = m2.group(1)
    # For an `equiv[ M.f ~ M.g : <body> ]`, the relation body follows the LAST
    # top-level `:` (skipping the `~` program pair). Keep everything after it.
    colon_segs = _top_level_split(flat, ":")
    body = (colon_segs[-1] if len(colon_segs) > 1 else flat).strip()
    # Drop a trailing tactic terminator and any unbalanced `)` left over from the
    # `byequiv (_: ... )` bracketing. e.g. `... \/ bad2{2}).` -> `... \/ bad2{2}`.
    body = body.rstrip(". ").strip()
    while body.endswith(")") and body.count(")") > body.count("("):
        body = body[:-1].rstrip(". ").strip()
    return body


# A bad-event-looking name: an identifier path (``UFCMA.bad1``, ``SUF_Wrap.win``,
# ``bad``, ``forged``, ``cbad2``) optionally side-annotated. We do NOT hardcode the
# literal "bad" — real proofs use win/forged/bad1/cbad2 (see ec_bad_trace docstring).
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:\{[12]\})?")

# A ``forall``/``exists`` quantifier keyword. The EasyCrypt pretty-printer renders a
# quantifier head as ``forall (n1 n2 : T) (m : U), <body>`` — the bound names live in
# the ``(... : ...)`` binder groups before the body's top-level comma.
_BINDER_KW_RE = re.compile(r"\b(?:forall|exists)\b")
# A bare local identifier (no module dots; a bound var is always a simple name like
# ``bad1_R``/``result_L``). Apostrophes occur in EC primed vars (``m'``).
_LOCAL_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")


def _binder_bound_names(text: str) -> set[str]:
    r"""Collect every local name introduced by a visible ``forall (...)``/``exists
    (...)`` binder group in ``text``.

    A binder-bound local (``forall (... bad1_R : bool ...) ...``) can later appear as
    a ``\/`` disjunct partner (``bad1_R \/ inv ...``) and would otherwise be harvested
    as a bad event — but it is a quantified variable, NOT a fireable bad event. We
    walk each ``forall``/``exists`` keyword, consume the consecutive ``(names : type)``
    binder groups that follow it, and harvest the identifiers to the LEFT of each
    group's first top-level ``:``. The caller subtracts these from the harvest. (This
    is what excludes step4_1 turn_005's ``bad1_R``; note ``forged_R`` is likewise a
    binder local that evades the ``forged`` relation-name check via its ``_R`` suffix —
    binder-stripping is the correct fix, not suffix matching.)
    """
    names: set[str] = set()
    n = len(text)
    for kw in _BINDER_KW_RE.finditer(text):
        i = kw.end()
        # Consume the run of ``(names : type)`` groups directly after the keyword.
        while i < n:
            while i < n and text[i].isspace():
                i += 1
            if i >= n or text[i] != "(":
                break  # reached the quantifier body — no more binder groups
            depth = 0
            j = i
            while j < n:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            group = text[i + 1 : j]
            # Names are the identifiers before the FIRST ``:`` (the shared type).
            colon = group.find(":")
            head = group[:colon] if colon >= 0 else group
            for m in _LOCAL_IDENT_RE.finditer(head):
                names.add(m.group(0))
            i = j + 1
    return names


# EasyCrypt reserved RELATION terms — the result/forgery projections that form the
# `relation may break` side of an up-to-bad disjunction `res{1} => res{2} \/ bad`.
# These are NEVER bad flags; they are the relation that the bad event is allowed to
# break. (`forged` is a forgery-result projection that plays the `res` role in the
# CHACHAPOLY/UFCMA developments — see step4_1's `forged{1} => forged{2} \/ bad`.)
_RELATION_RESULT_NAMES = frozenset({"res", "forged"})

# Boolean literals are NEVER bad-event flags. A disjunct `inv x y \/ false` carries
# `false` as the (vacuous) other side of the disjunction, not a fireable event. We
# exclude them here so `_looks_like_event_name` rejects `false`/`true` outright.
_BOOLEAN_LITERALS = frozenset({"false", "true"})


def _looks_like_event_name(token: str) -> bool:
    """A single bare boolean-flag name (no operator/equality/quantifier inside).

    A disjunct like ``={res}``, ``a{1} = b{2}``, or ``inv m1 m2`` is a RELATION, not
    a bad event; and ``res``/``forged`` are the result projections (the relation that
    breaks), never flags. Only a bare qualified + side-annotated identifier counts —
    and a boolean literal (``false``/``true``) is never a flag either."""
    t = token.strip()
    if not t:
        return False
    # Reject anything with relation/logic operators — those are couplings, not flags.
    if any(op in t for op in ("=", "<", ">", "/\\", "\\/", "=>", "<=", "forall", "exists")):
        # `={res}` contains '=' and is a relation, not a bad flag.
        return False
    # Reject an APPLICATION (a name followed by whitespace-separated args, e.g.
    # `inv m1 m2 ...`): a multi-token expression is a relational predicate, not a
    # bare flag. A single token (`UFCMA.bad1{2}`) has no internal space.
    if len(t.split()) != 1:
        return False
    m = _NAME_RE.fullmatch(t)
    if not m:
        return False
    base = _strip_side_annot(t).split(".")[-1]
    if base in _RELATION_RESULT_NAMES:
        return False
    # A boolean literal (`false`/`true`) is a value, never a fireable event flag.
    if base in _BOOLEAN_LITERALS:
        return False
    return True


def _looks_like_relation_break_term(token: str) -> bool:
    r"""True when ``token`` is a RELATION that the bad event is allowed to break.

    This is the OTHER side of an up-to-bad disjunction: a disjunct that asserts the
    games still agree. We recognize it as any of:
      - the result projection ``res``/``forged`` (bare or side-annotated),
      - an equality relation: an ``={...}`` group or any ``a = b`` / ``a <= b`` term,
      - a relational-predicate APPLICATION ``inv m1 m2 ...`` (a name applied to >= 1
        whitespace-separated argument; this is how step4_1's pre-conjunct couples the
        two RO maps: ``UFCMA.bad1 \/ inv SplitC2... UFCMA.log``).
    A bare flag name (``UFCMA.bad1``) is NOT a relation-break term — that is the bad
    side. Quantifier/implication tokens are not relation-break disjuncts either."""
    t = token.strip()
    if not t:
        return False
    if any(op in t for op in ("forall", "exists")):
        return False
    # An equality / order relation (incl. an `={...}` group). `=>` is an implication,
    # not an equality — strip it before checking so `a => b` is not read as `=`.
    no_impl = t.replace("=>", "  ")
    if any(op in no_impl for op in ("=", "<=", ">=", "<", ">")):
        return True
    base = _strip_side_annot(t).split(".")[-1]
    if t.split() and base in _RELATION_RESULT_NAMES and len(t.split()) == 1:
        return True
    # Relational-predicate application: `<name> <arg> ...` (>= 2 whitespace tokens,
    # head is an identifier). A single bare token is a flag, handled elsewhere.
    toks = t.split()
    if len(toks) >= 2 and _NAME_RE.fullmatch(toks[0]):
        return True
    return False


def _flatten_disjuncts(expr: str) -> list[str]:
    r"""Flatten a (possibly NESTED / parenthesized / projection-annotated)
    ``\/``-disjunction into its atomic disjuncts.

    The EasyCrypt pretty-printer and agents both produce nested renderings of the
    same disjunction — ``(forged{2} \/ UFCMA.bad2{2}) \/ UFCMA.bad1{2}`` (rendered)
    and ``((res \/ UFCMA.bad2) \/ UFCMA.bad1){2}`` (tactic text). A top-level-only
    split sees a single opaque group disjunct and the harvest misses the bads
    (audit 2026-06-09: root of the step4_1 scratch Tree_0_1 t18-41 false negative).
    So: split at top level, then recursively expand any disjunct that is itself a
    wrapped group containing a further top-level ``\/`` (``_top_level_split`` peels
    a fully-wrapping ``(...)``/``(...){2}`` group before splitting)."""
    parts = _top_level_split(expr, "\\/")
    if len(parts) == 1:
        return [parts[0].strip()]
    out: list[str] = []
    for d in parts:
        sub = _top_level_split(d, "\\/")
        if len(sub) >= 2:
            out.extend(_flatten_disjuncts(d))
        else:
            out.append(sub[0].strip())
    return out


def _harvest_relation_break_disjunction(expr: str) -> set[str]:
    r"""Harvest bad-event names from a single ``\/``-disjunction — but ONLY when that
    disjunction is a genuine RELATION BREAK: at least one disjunct must be a relation
    that may break (``res``/``forged``/``={...}``/an ``inv ...`` application). The
    OTHER bare-flag disjuncts are then the active bad events.

    This is the precision core: ``forged \/ bad2 \/ bad1`` has a relation disjunct
    (``forged``) so ``{bad1, bad2}`` are harvested (``forged`` itself is the relation,
    not harvested). A bare consequent ``badi`` (step4_badi) is a SINGLE disjunct with
    no relation-break partner -> nothing harvested. A disjunction of only flags with
    no relation term is not a relation-break shape either -> nothing harvested.

    Nested renderings (``(rel \/ bad2) \/ bad1``, ``((rel \/ bad2) \/ bad1){2}``)
    are flattened first so the relation partner inside an inner group is seen.
    """
    # Descend one paren level if the whole disjunction expr is a wrapped group, so a
    # parenthesized pre-conjunct group `(bad \/ inv ...)` exposes its `\/`; then
    # flatten nested disjunction groups so EVERY atomic disjunct is visible.
    disjuncts = [d.strip() for d in _flatten_disjuncts(expr)]
    if len(disjuncts) < 2:
        return set()  # a single term is never a relation-break disjunction
    has_relation = any(_looks_like_relation_break_term(d) for d in disjuncts)
    if not has_relation:
        return set()
    names: set[str] = set()
    for d in disjuncts:
        cand = _strip_side_annot(d)
        if _looks_like_event_name(cand):
            names.add(cand)
    return names


def up_to_bad_names(post_text: str) -> set[str]:
    r"""Bad-event names that sit in a RELATION-BREAK ``\/`` disjunction of the goal.

    A name counts as an up-to-bad event IFF it appears as a DISJUNCT in a ``\/``
    disjunction where at least one OTHER disjunct is the relation that may break
    (``res``/``forged``/``={...}``/an ``inv ...`` relational predicate). Concretely:

        ``forged{1} => forged{2} \/ bad2 \/ bad1``  -> {bad1, bad2}
              (the ``=>`` CONSEQUENT is the disjunction ``forged \/ bad2 \/ bad1``;
               ``forged`` is the relation-break partner, ``bad1``/``bad2`` the bads)
        ``(UFCMA.bad1{2} \/ inv RO.m{1} RO.m{2} ...)`` -> {UFCMA.bad1}
              (a PARENTHESIZED pre-conjunct group; descend one paren level — the
               ``inv ...`` application is the relation-break partner)
        ``!(B1 \/ B2){2} => ={res}``                 -> {B1, B2}
              (negated-bad GUARD; the guarded relation ``={res}`` is the partner)
        ``={res} \/ bad1 \/ bad2``                   -> {bad1, bad2}  (bare disjunction)

    A valid bad-event TOKEN is a **bare boolean flag identifier** — ``Ident`` or
    dotted ``Mod.Ident``, optionally suffixed ``{1}``/``{2}`` — that is NOT a
    relation result (``res``/``forged``), NOT a boolean literal (``true``/``false``),
    NOT bound by a visible ``forall``/``exists`` binder, and NOT an operator/function
    applied to arguments (no whitespace-separated args, no infix comparison). These
    precision claims are ENFORCED in code: ``_looks_like_event_name`` rejects literals
    and applications; a binder-strip pass (``_binder_bound_names``) removes
    quantifier-bound locals; and the negated-guard path checks the WHOLE negated
    operand (so ``! size A <= i`` — an applied operator/comparison — harvests nothing).

    Does NOT harvest:
        - a BARE implication consequent with no ``\/`` (``... => badi{2}`` —
          step4_badi: lockstep bad-TRACKING, not a relation break);
        - a bare ``bad =>`` implication ANTECEDENT (``(UFCMA.bad1{1} => exists ...)``
          — step4_bad1_lbad1: implication-position bad-tracking);
        - a ``forall``/``exists``-BOUND local (``forall (... bad1_R : bool ...) ... =>
          bad1_R \/ inv ...`` — step4_1 turn_005; ``bad1_R``/``forged_R`` are
          quantified vars, stripped by the binder pass, NOT by ``_R``-suffix matching);
        - a boolean LITERAL ``false``/``true`` (``inv x y \/ false`` -> ∅);
        - an OPERATOR/function APPLICATION in a negated guard (``! size A <= i`` -> ∅);
        - a bare ``forged``/``res`` (the relation that breaks, never a flag).

    The whole goal body (``pre ==> post``) is scanned: the up-to-bad disjunct can
    live in the POST consequent OR in a parenthesized PRE-conjunct, so every
    top-level conjunct (BOTH ``/\\`` and ``&&``) and the implication structure are
    walked.
    """
    body = _extract_post(post_text)
    names: set[str] = set()

    # Walk every top-level conjunct of the body (the up-to-bad disjunct may live in
    # a parenthesized PRE-conjunct, e.g. step4_1's `(bad1 \/ inv ...)`). Each
    # conjunct is then examined for the implication / disjunction shapes below.
    # Split on BOTH conjunction renderings: logical `/\` AND boolean `&&` — the EC
    # pretty-printer renders step4_1 turn_005's post as
    # `(!UFCMA.bad1{2} => ... inv ...) && forall ...`, so the genuine bad lives in a
    # parenthesized `&&` conjunct; splitting only on `/\` would hide it.
    for conj in _split_top_conjuncts(body):
        _harvest_from_segment(conj.strip(), names)
    # Also examine the whole body directly (it may itself be a single implication
    # `pre ==> post` with no top-level `/\` — the common post-only call to this fn).
    _harvest_from_segment(body, names)
    # PRECISION: drop any name bound by a visible `forall`/`exists` binder. A binder
    # local (`forall (... bad1_R : bool ...) ... => bad1_R \/ inv ...`) is a quantified
    # variable, not a fireable bad event (step4_1 turn_005's `bad1_R`/`forged_R`).
    bound = _binder_bound_names(body)
    if bound:
        names = {nm for nm in names if _strip_side_annot(nm).split(".")[-1] not in bound}
    return names


def _harvest_from_segment(seg: str, names: set[str]) -> None:
    r"""Harvest relation-break bad names from one body segment (a conjunct or the
    whole body). Handles the implication split (guard on LHS, consequent on RHS) and
    the bare-disjunction case; delegates the relation-break precision check to
    ``_harvest_relation_break_disjunction``.

    A fully-wrapped segment (``(...)`` or projection-annotated ``(...){2}``) is
    peeled and re-examined, and an implication CONSEQUENT that is itself a wrapped
    implication (``={glob A} ==> (res{1} => ((res \/ bad2) \/ bad1){2})`` — the
    step4_1 byequiv tactic text) is descended recursively. Without this descent the
    inner implication was opaque and the harvest stayed ∅ (audit 2026-06-09)."""
    seg = seg.strip()
    if not seg:
        return
    peeled = _peel_wrapping_group(seg)
    if peeled != seg:
        # The whole segment is one wrapped group (possibly `(...){2}`-annotated):
        # descend and re-examine the interior (strictly smaller -> terminates).
        _harvest_from_segment(peeled, names)
        return
    impl_segs = _top_level_split(seg, "=>")
    if len(impl_segs) >= 2:
        # Implication present. The RHS (consequent) may be a relation-break
        # disjunction `... \/ bad`. A BARE consequent (single term, no `\/`) is
        # NOT harvested (step4_badi `=> badi`).
        names |= _harvest_relation_break_disjunction(impl_segs[-1])
        # The consequent may itself be a WRAPPED implication/disjunction group
        # (`res{1} => ((res \/ bad2) \/ bad1){2}` wrapped in the byequiv parens):
        # descend one level so the inner implication's consequent is harvested.
        tail = impl_segs[-1].strip()
        peeled_tail = _peel_wrapping_group(tail)
        if peeled_tail != tail:
            _harvest_from_segment(peeled_tail, names)
        # LHS guard: harvest ONLY from a NEGATED group `!(...)`/`!B` — the up-to-bad
        # negated-bad guard shape, where the guarded relation on the RHS is the
        # break partner. A bare `bad => ...` antecedent is implication-position and
        # is intentionally skipped (precision: step4_bad1_lbad1).
        rhs_is_relation = _looks_like_relation_break_term(impl_segs[-1].strip())
        for lhs in impl_segs[:-1]:
            for neg in re.findall(r"!\s*\(([^()]*)\)", lhs):
                # The negated group's disjuncts are bads guarding the RHS relation.
                for d in _top_level_split(neg, "\\/"):
                    cand = _strip_side_annot(d.strip())
                    if _looks_like_event_name(cand) and (
                        rhs_is_relation or len(_top_level_split(neg, "\\/")) >= 2
                    ):
                        names.add(cand)
            # Bare negated flag `!B => relation`. A negated-guard bad must be a BARE
            # flag identifier (`Mod.flag{2}`) — NOT an operator/function applied to
            # arguments and NOT a relational comparison. So split the LHS into its
            # top-level conjuncts/disjuncts and, for each `!<operand>` chunk, run the
            # WHOLE operand through `_looks_like_event_name` (which already rejects an
            # application `size A <= i` on its multi-token / comparison content). The
            # earlier regex captured only the identifier HEAD and dropped the trailing
            # `A <= i`, so it mis-harvested the operator `size`; this checks the full
            # operand. Parenthesized `!(...)` groups are left to the group path above.
            for piece in _split_top_conj_disj(lhs):
                p = piece.strip()
                if not p.startswith("!"):
                    continue
                operand = p[1:].strip()
                if operand.startswith("("):
                    continue  # handled by the `!(...)` group path above
                cand = _strip_side_annot(operand)
                if _looks_like_event_name(cand) and rhs_is_relation:
                    names.add(cand)
    else:
        # No implication at this level. The segment may STILL be a multi-conjunct
        # block whose up-to-bad disjunct hides inside ONE parenthesized conjunct.
        # E1 (audit 2026-06-09, step4_1 resume Tree_0_0 t34): the pre block is
        # `(b0{2}=b1{2} /\ ... /\ (UFCMA.bad1{2} \/ inv ...)) /\ UFCMA.bad1{2}`;
        # peeling the outer group hands this `else` branch the big `/\` conjunction
        # whose `(UFCMA.bad1{2} \/ inv ...)` conjunct was never re-examined — so the
        # harvest stayed ∅ even though `up_to_bad_names` on that conjunct alone
        # returns {UFCMA.bad1}. Re-split into top conjuncts (`/\` AND `&&`) and
        # recurse so each conjunct is visited; each is strictly smaller -> terminates.
        conjs = _split_top_conjuncts(seg)
        if len(conjs) > 1:
            for c in conjs:
                _harvest_from_segment(c.strip(), names)
            return
        # A single conjunct: a bare disjunction `rel \/ bad \/ ...`.
        names |= _harvest_relation_break_disjunction(seg)


def is_lockstep_call(call_tactic: str) -> bool:
    r"""True for the single-clause lockstep ``call (_: inv)`` form (no bad clause).

    Discriminator (shared with ``session_goal_context``/``ec_diagnose``): the
    ``call (_: ...)`` argument has TOP-LEVEL comma-count 0. The 2-clause up-to-bad
    ``call (_: bad, inv)`` form has a REAL top-level comma and is NOT lockstep.

    BRACE-AWARE: the comma split tracks ``{}`` and ``()`` depth, so commas inside a
    ``={glob A, glob B, glob C}`` / ``{...}`` group are NOT clause separators — that
    whole frame is ONE lockstep clause. So:
        ``call (_: ={glob A, glob B})``        -> lockstep=True  (commas in `={...}`)
        ``call (_: ={glob A} /\ ={x})``        -> lockstep=True  (`/\`, no top comma)
        ``call (_: bad1 \/ bad2, inv)``        -> lockstep=False (real top-level comma)
        ``call (_: UFCMA.bad1)``               -> lockstep=False (BARE-FLAG clause)
    This is what fixes step4_badi's multi-glob call being mis-read as 2-clause.

    BARE-FLAG PRECISION (audit 2026-06-09): a single clause that is itself a bare
    bad-flag name (``call (_: UFCMA.bad1).``) is the ONE-SIDED phoare
    bad-preservation form, NOT a lockstep relational call. Treating it as lockstep
    made ``coherence_flag`` assemble the absurd candidate
    ``call (_: UFCMA.bad2, UFCMA.bad1).`` — a phoare argument promoted to a
    relational invariant (reproduced on the step4_1 resume Tree_0_0 prefix).
    """
    tac = call_tactic.strip()
    low = tac.lower()
    if not low.startswith("call"):
        return False
    m = re.search(r"\(\s*_\s*:(.*)\)\s*\.?\s*$", tac, re.DOTALL)
    if not m:
        # `call` with no `(_: ...)` argument (e.g. `call lemma.`) is not the
        # invariant-call form at all; treat as not-lockstep so we don't fire.
        return False
    arg = m.group(1)
    # Count commas at top level (paren AND brace depth 0). >=1 -> 2-clause up-to-bad.
    if len(_top_level_split(arg, ",")) != 1:
        return False
    # Single clause that is just a bare flag identifier -> phoare bad-preservation
    # (one-sided), not a lockstep relational call.
    if _looks_like_event_name(_strip_side_annot(arg.strip())):
        return False
    return True


def latest_relational_call(tactics: list[str]) -> str:
    r"""The most recent committed RELATIONAL ``call (_: ...)`` form, scanning
    newest-first; ``""`` when none exists.

    Skipped on the way back (audit 2026-06-09 — the step4_1 resume Tree_0_1 false
    negative: three lockstep ``call (_: inv ...)`` at prefix L16-18 were hidden
    behind the temporally-latest ``call (some_lemma n0 mr0 ms0).``):
      - a LEMMA-application call (``call (some_lemma ...).`` — no ``(_:`` argument);
      - a one-sided bare-flag phoare preservation call (``call (_: UFCMA.bad1).``).
    What remains is the relational invariant-call the coherence check should key
    on: lockstep single-clause or 2-clause up-to-bad."""
    for t in reversed(tactics):
        s = t.strip()
        if not s.lower().lstrip("+-* ").startswith("call"):
            continue
        m = re.search(r"\(\s*_\s*:(.*)\)\s*\.?\s*$", s, re.DOTALL)
        if not m:
            continue  # `call (lemma args).` — not the invariant-call form
        arg = m.group(1)
        parts = _top_level_split(arg, ",")
        if len(parts) == 1 and _looks_like_event_name(
            _strip_side_annot(parts[0].strip())
        ):
            continue  # `call (_: bad).` — one-sided phoare bad-preservation
        return s
    return ""


def _call_invariant_arg(call_tactic: str) -> str:
    m = re.search(r"\(\s*_\s*:(.*)\)\s*\.?\s*$", call_tactic.strip(), re.DOTALL)
    return m.group(1).strip() if m else ""


def coherence_flag(
    post_text: str,
    call_tactic: str,
    *,
    source_text: str | None = None,
    lemma_name: str | None = None,
) -> dict[str, Any] | None:
    r"""Return a neutral ``decision_context`` entry, or ``None`` if no incoherence.

    Fires ONLY when:
      - the equiv/byequiv postcondition has >=1 bad name in a top-level ``\/``
        disjunct (``up_to_bad_names`` non-empty), AND
      - the issued/visible ``call`` is the lockstep single-clause form, AND
      - none of those active bad names already appears in the lockstep invariant
        (if it does, the agent is already tracking bad — nothing to flag).

    The returned dict is a SUGGESTION marked UNCERTIFIED, never a verdict/gate.
    """
    bad_names = up_to_bad_names(post_text)
    if not bad_names:
        return None
    if not is_lockstep_call(call_tactic):
        return None
    inv_arg = _call_invariant_arg(call_tactic)
    inv_norm = inv_arg.replace(" ", "")
    # If the lockstep invariant already mentions one of the active bad names, the
    # agent is already carrying it — do not fire (precision).
    for b in bad_names:
        if b.replace(" ", "") in inv_norm:
            return None

    sorted_bads = sorted(bad_names)
    bad_disp = ", ".join(f"`{b}`" for b in sorted_bads)
    # E2 (audit 2026-06-09): when MORE THAN ONE relation-break bad is active, the
    # candidate and the obligation text must cover EVERY active bad — never the
    # sorted-first one only. A single-bad clause silently drops the rest (the
    # step4_1 resume Tree_0_1 hook fact had `bad1, bad2` active but offered only
    # `call (_: UFCMA.bad1, inv)`, leaving bad2's obligation dangling). For >1 bad
    # the up-to-bad clause is their DISJUNCTION `(bad1 \/ bad2)` so the single call
    # discharges the whole relation break; the obligation guard is the negation of
    # that disjunction. For one bad the wording is unchanged (regression red line).
    if len(sorted_bads) == 1:
        bad_clause = sorted_bads[0]
        guard = f"!{bad_clause}"
    else:
        bad_clause = "(" + " \\/ ".join(sorted_bads) + ")"
        guard = f"!{bad_clause}"

    # Build the UNCERTIFIED `call (_: bad, inv)` candidate. Prefer the
    # source-grounded template (ec_inv_from_lemma) when a lemma name + source are
    # available; otherwise assemble mechanically from the lockstep invariant.
    candidate = f"call (_: {bad_clause}, {inv_arg})."
    candidate_source = "assembled_from_lockstep_invariant"
    if source_text and lemma_name:
        try:
            from core.easycrypt.ec_inv_from_lemma import (  # type: ignore
                extract_call_template,
            )
        except Exception:  # pragma: no cover - import-path fallback
            try:
                from core.easycrypt.ec_inv_from_lemma import extract_call_template  # type: ignore
            except Exception:
                extract_call_template = None  # type: ignore
        if extract_call_template is not None:
            try:
                tmpl = extract_call_template(source_text, lemma_name)
                if tmpl and "not found" not in tmpl.lower():
                    candidate = tmpl
                    candidate_source = f"ec_inv_from_lemma:{lemma_name}"
            except Exception:
                pass

    text = (
        f"Upstream postcondition admits `\\/ {bad_clause}`; your `call (_: inv)` is "
        f"lockstep (no bad clause). These games diverge when {bad_disp} fires, so "
        f"a lockstep call cannot be discharged here. Consider the up-to-bad form "
        f"`call (_: {bad_clause}, <inv>)`. It generates these obligations: (1) the "
        f"oracle equiv under `{guard}`, (2) losslessness of both oracles after "
        f"`{bad_clause}`, (3) `{bad_clause}`-preservation."
    )
    return {
        "key": DECISION_CONTEXT_KEY,
        "text": text,
        "active_bad_events": sorted(bad_names),
        "candidate": candidate,
        "candidate_source": candidate_source,
        "certified": False,
        "guarantee": (
            "UNCERTIFIED suggestion — a structural coherence observation from the "
            "postcondition shape, NOT a verdict and NOT a gate. EC verifies any "
            "tactic when EasyCrypt checks it."
        ),
    }
