"""EC error classifier.

Classifies EasyCrypt error messages into two high-level categories (a factual
attribution of the raw EC error — what kind of error it is, not what to do next):
- SYNTAX: the tactic's NAME / STRUCTURE is accepted by EC; only surface-syntax
  is wrong (e.g. argument count/form, an unresolved name).
- STRUCTURE: the tactic's assumption about the current goal/program shape is
  wrong (the error is semantic, not a syntax tweak).

Motivation: ChaChaPoly v7 step1 (2026-04-21) — prover had the right
structural plan (`have -> : Pr[...] = Pr[MainD(G2, RO).distinguish(...)]`)
but wrote `.distinguish(tt)` where the correct syntax was `.distinguish()`.
EC reported "invalid function application: wrong number of arguments".
The prover mis-attributed this to a STRUCTURE problem ("G2 doesn't match
the RO_Distinguisher type") and abandoned the correct path, losing the
proof in the remaining 10 minutes.

Design principles:
1. **High-confidence patterns only.** Unrecognized errors are NOT labeled —
   we preserve the raw EC error and let the agent handle it as before.
   An incorrect label is worse than no label.
2. **Label + "why this class" — nothing more.**
   The classifier does ONE job: tell the agent which way to attribute
   the error (structure OK / structure wrong). It does NOT prescribe a
   fix or a next move (no "do not abandon", no directed-retry variants) —
   that's the agent's decision, informed by the factual attribution.
3. **"Why this class" is mandatory**, because some EC errors (e.g.
   "invalid first instruction") LOOK syntactic in wording but are
   structural in semantics — the explanation bridges that gap.

Public API:
    classify(raw_error: str) -> Optional[dict]
    format_classification(cls: dict, tactic_text=None, file_path=None,
                          raw_error=None) -> str  (pretty block for stdout)

For SYNTAX errors whose tactic head has `-tactic-forms` coverage, the formatted
output appends a single pointer to that grammar-fact reference so the agent can
retrieve the valid argument forms itself — a factual route, not a directed
retry. The agent chooses the next move.
"""

from __future__ import annotations

import re
from typing import Optional


# --- High-confidence patterns ---
# Each entry: (regex, class, subtype, what_it_means, why_this_class)
# Order matters only if patterns overlap; keep distinctive substrings first.
_PATTERNS = [
    # --- SYNTAX class ---
    {
        "regex": re.compile(
            r"invalid function application: wrong number of arguments"
            r"|too many arguments"
            r"|too few arguments"
            r"|(?:expected|expecting) \d+ arguments?\b.*\bgot \d+",
            re.IGNORECASE,
        ),
        "class": "syntax error",
        "subtype": "argument count mismatch",
        "what": (
            "The lemma/function you invoked exists but the arguments "
            "don't match its declared signature."
        ),
        "why": (
            "Your tactic NAME and overall STRUCTURE are accepted by EC. "
            "Only the argument count is wrong. The fix is a different "
            "SYNTAX for the SAME tactic — not a different tactic."
        ),
    },
    {
        "regex": re.compile(
            r"unknown (lemma|operator|variable|constructor|theory|module|type name|symbol)",
            re.IGNORECASE,
        ),
        "class": "syntax error",
        "subtype": "unknown identifier",
        "what": (
            "The name you referenced is not visible in the current scope."
        ),
        "why": (
            "Almost always a spelling/qualification error. The tactic "
            "shape is fine; EC just can't resolve the name."
        ),
    },
    # "unknown memory: &X" — distinct from unknown identifier. Memories in
    # EC are the semantic contexts you can reference with `{1}`/`{2}` in
    # pRHL, `{hr}` in phoare, `{m}` / `&m` for ambient. Using a memory
    # annotation from the wrong judgment kind (e.g. `{hr}` inside a pRHL
    # `seq K L : inv`) produces this error. It's always a syntax issue —
    # your invariant/post is structurally fine, just uses a memory that
    # doesn't exist in the current judgment.
    #
    # Motivation: a pRHL oracle proof had the prover write
    # `seq 1 1 : (... X{1} = X{hr} ...)` inside a pRHL goal and hit
    # "unknown memory: &hr". Prover correctly diagnosed as syntax but
    # instead of retrying with the correct memory (drop `{hr}` or use
    # `{1}`/`{2}`), pivoted to `inline{1}` and destroyed call-lemma
    # applicability — 35 min lost. The SYNTAX label attributes it correctly.
    # Lemma-argument form mismatch: applying a lemma (usually one exported
    # from a `section` with module-typed parameters) with the wrong
    # argument shape. EC raises several closely-related wordings for this
    # underlying issue:
    #   - "cannot infer module arguments"           (missing explicit module args)
    #   - "expecting a `proof-term', not a `formula'"  (passed a type/formula where a proof-term is wanted)
    #   - "<X> is not a valid formula"              (dual: passed a proof-term where a formula is wanted)
    # Common cause: section-exported lemmas keep their module-typed
    # parameters bound to the section module type. Outside the section you
    # must pass concrete modules explicitly: `apply (LEMMA M1 M2 &m)` or
    # `rewrite (LEMMA M1 M2 &m p)`.
    #
    # Motivation: replay audits showed provers trying a section-exported
    # bridge lemma such as `pr_RO_FinRO_D` without explicit module arguments,
    # then cycling through several arity variants before reading the signature.
    # The SYNTAX label surfaces the correct attribution quickly.
    {
        "regex": re.compile(
            r"cannot infer module arguments"
            r"|expecting a .proof-term., not a .formula."
            r"|is not a valid formula"
            r"|invalid proof-term",
            re.IGNORECASE,
        ),
        "class": "syntax error",
        "subtype": "lemma argument form mismatch",
        "what": (
            "You applied a lemma (`apply`, `rewrite`, `have :=`) with "
            "arguments in the wrong form. Very common cause: the lemma "
            "is exported from a `section` and has module-typed parameters "
            "bound inside that section; outside the section you must pass "
            "those modules explicitly, e.g. `apply (LEMMA M1 M2 &m)` or "
            "`rewrite (LEMMA M1 M2 &m p)`. Other causes: passing a "
            "formula where a proof-term is wanted (or vice versa) because "
            "the tactic expects one but you gave the other."
        ),
        "why": (
            "Your tactic name (`apply` / `rewrite` / `have :=`) and your "
            "structural approach (using this particular lemma) are fine. "
            "Only the argument form is wrong. Re-shaping the arguments "
            "fixes it without changing which lemma you invoke."
        ),
    },
    # "cannot infer all placeholders" — applying a lemma (equiv / lemma /
    # axiom) that carries universal parameters without passing enough
    # concrete args for EC to deduce them. Distinct from "cannot infer
    # module arguments" (above) which is about section-exported lemmas
    # and their module-typed params; this one fires on `call LEMMA.` /
    # `ecall LEMMA.` when LEMMA has forall-quantified params (nonces,
    # fmaps, memory snapshots) that the call-site can't pin down.
    #
    # Motivation: local equiv lemmas often carry explicit value parameters
    # for call arguments or state snapshots.  A bare `call LEMMA.` can unify
    # the procedure pair but still leave those universal slots unresolved.
    # Stable fix: lift program expressions with `exlim` into logical
    # parameters, then call the fully applied lemma.
    {
        "regex": re.compile(
            r"cannot infer all placeholders",
            re.IGNORECASE,
        ),
        "class": "syntax error",
        "subtype": "lemma universal params not inferable",
        "what": (
            "The lemma you invoked (`call` / `ecall` / `apply`) carries "
            "universal parameters (e.g. `local equiv bridge n0 state0 : ...` "
            "has explicit value args). EC inserts metavariables for them, tries "
            "to unify the body against the goal, but some metavariables "
            "remain unresolved after unification — EC cannot guess them. "
            "This is the NO-ARGS call form of the lemma hitting a "
            "forall-quantified slot that the goal doesn't pin."
        ),
        "why": (
            "Your structural approach (using this specific lemma here) is "
            "plausible — unification at the call-site got far enough to ask "
            "for lemma parameters. The missing part is typed argument "
            "plumbing: program-state expressions such as `n{1}` or `RO.m{2}` "
            "usually need to be lifted into logical names before they can be "
            "passed as lemma arguments."
        ),
    },
    {
        "regex": re.compile(
            r"unknown memory(?::|\b)|memory not allowed here",
            re.IGNORECASE,
        ),
        "class": "syntax error",
        "subtype": "unknown memory / judgment mismatch",
        "what": (
            "You referenced a memory annotation (`{1}`, `{2}`, `{hr}`, "
            "`{m}`, `&m`) that doesn't exist in the current judgment. "
            "Typical cause: using `{hr}` (phoare memory) inside a pRHL "
            "`seq K L : inv` postcondition, or using `{1}`/`{2}` in a "
            "single-program hoare/phoare judgment."
        ),
        "why": (
            "Your invariant/postcondition is structurally correct — only "
            "the memory identifier is wrong. A syntax tweak (drop the "
            "bad annotation or replace with a legal one) fixes it."
        ),
    },
    # --- STRUCTURE class ---
    # "invalid first/last instruction" sounds syntactic but is semantic —
    # the tactic's assumption about program shape at cursor is wrong.
    {
        "regex": re.compile(
            r"invalid (first|last) instruction",
            re.IGNORECASE,
        ),
        "class": "structural issue",
        "subtype": "tactic-program shape mismatch",
        "what": (
            "Your tactic (typically `call`, `if`, `seq`, `rcondt/rcondf`, "
            "`while`, `exlim`) expected a specific kind of statement at "
            "the cursor position. The actual statement at cursor is a "
            "different kind."
        ),
        "why": (
            "Despite the word 'instruction' in the error, this is NOT a "
            "syntax error about the tactic itself. EC parsed the tactic "
            "fine; it's rejecting the tactic's STRUCTURAL assumption "
            "about the program at cursor."
        ),
    },
    {
        "regex": re.compile(
            r"expecting a goal of the form[: ]|invalid goal shape",
            re.IGNORECASE,
        ),
        "class": "structural issue",
        "subtype": "goal-type mismatch",
        "what": (
            "Your tactic applies to a specific goal type (e.g. `equiv[F]`, "
            "`phoare[F]`, `hoare[S]`), but the current goal is a different "
            "type (e.g. ambient logic, pRHL, probability)."
        ),
        "why": (
            "The tactic and goal are at different abstraction layers. "
            "This is structural — no syntax tweak will fix it."
        ),
    },
    {
        "regex": re.compile(
            r"module \S+ should be abstract|"
            r"should be abstract|"
            r"which reduces to [A-Za-z][\w.]*\.main, should be abstract",
            re.IGNORECASE,
        ),
        "class": "structural issue",
        "subtype": "concrete module in abstract position",
        "what": (
            "You used `call` (or similar) on a procedure inside a "
            "concrete module. `call` requires the target procedure to "
            "be ABSTRACT (a module-typed parameter), not a concretely "
            "instantiated module."
        ),
        "why": (
            "This is a semantic restriction of `call`, not a syntax "
            "issue. No argument variation will make `call` work on a "
            "concrete module — you need a different approach."
        ),
    },
]


def classify(raw_error: str) -> Optional[dict]:
    """Return a classification dict for the given EC error text, or None
    if no high-confidence pattern matches.

    Returning None (instead of a low-confidence label) is deliberate:
    an incorrect label is worse than no label.
    """
    if not raw_error:
        return None
    for entry in _PATTERNS:
        if entry["regex"].search(raw_error):
            return {
                "class": entry["class"],
                "subtype": entry["subtype"],
                "what": entry["what"],
                "why": entry["why"],
            }
    return None


_SUPPORTED_TACTIC_FORMS = {
    "call", "apply", "rewrite", "byequiv", "conseq", "while", "seq", "rnd",
}


def _extract_tactic_head(tactic_text: str) -> Optional[str]:
    """Return the leading tactic name from a tactic string, if it's one we
    have `-tactic-forms` coverage for. Handles things like:
        "call (_: Inv)."          -> "call"
        "apply (LEMMA M &m)."     -> "apply"
        "rewrite -LEMMA."         -> "rewrite"
        "conseq (_: ...)"         -> "conseq"
        "while{2} (...) (...)."   -> "while"
        "proc; inline *; sim."    -> None  (composite, skip hint)
    """
    if not tactic_text:
        return None
    # Strip leading whitespace and an optional bullet / semicolon
    stripped = tactic_text.strip().lstrip('-+*').lstrip()
    # Match leading identifier (optionally followed by {1}/{2})
    m = re.match(r"([A-Za-z_]+)\b", stripped)
    if not m:
        return None
    head = m.group(1).lower()
    if head in _SUPPORTED_TACTIC_FORMS:
        return head
    return None


def format_classification(
    cls: dict,
    tactic_text: Optional[str] = None,
    file_path: Optional[str] = None,
    raw_error: Optional[str] = None,
) -> str:
    """Render a classification dict as a human-readable block for stdout.

    Surfaces only the FACTUAL attribution — which class/subtype the EC error is,
    what it means, and why it falls in that class. If `tactic_text` is provided
    AND the class is SYNTAX AND we have `-tactic-forms` coverage for the tactic,
    append a pointer to the grammar-fact reference so the agent can retrieve the
    valid argument forms itself. No directed-retry / "do not abandon" guidance:
    the agent decides the next move from the facts.
    """
    if not cls:
        return ""
    lines = [
        f"[CLASS: {cls['class']} — {cls['subtype']}]",
        f"  What this means: {cls['what']}",
        f"  Why it's a {cls['class']}: {cls['why']}",
    ]
    # For SYNTAX errors, point to the tactic-forms reference if the
    # tactic is one we cover. Avoids the "agent knows something is off
    # but doesn't know where to look" phase — a single command retrieves
    # the full form menu.
    if cls.get("class") == "syntax error" and tactic_text:
        head = _extract_tactic_head(tactic_text)
        if head:
            lines.append(
                f"  → Run `-tactic-forms {head}` to see the valid argument "
                f"forms for `{head}`."
            )
    return "\n".join(lines) + "\n"
