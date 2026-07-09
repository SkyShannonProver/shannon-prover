#!/usr/bin/env python3
"""Diagnose EasyCrypt tactic errors and suggest fixes.

Reads the latest error from a session's current.out, matches it against
a database of known error patterns (seeded from A/B test failures), and
suggests the most likely cause and fix.

Usage via session_cli:
    python3 core/easycrypt/session_cli.py -d .ec_session -diagnose

Usage standalone:
    python3 core/easycrypt/ec_diagnose.py < current.out
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Diagnosis:
    error_pattern: str       # regex to match against EC error message
    tactic_pattern: str      # regex to match against the failing tactic (empty = any)
    diagnosis: str           # what likely went wrong
    suggestion: str          # what to try instead
    pitfall: str = ""        # reference to Pitfall in decision_tree.md (e.g., "P2")
    source: str = ""         # which A/B test discovered this
    level: str = ""          # "execution" | "strategy" | "" (empty = unclassified)
    when_to_abandon: str = ""  # from ec_tactics.json: when to switch strategy


# ---------------------------------------------------------------------------
# Error-diagnosis patterns are hardcoded compiler-skeleton facts only.
#
# The KB pattern catalog (knowledge/base/agent/ec_tactics.json) was REMOVED as a
# diagnose source: it was a heuristic advice catalog that (a) took precedence over
# the hardcoded fact patterns below and (b) fed MCP-path-irrelevant boilerplate
# (shell `!`/apostrophe-quoting causes from the legacy session_cli `-c '...'`
# path) into agent-facing diagnoses — e.g. shadowing the factual parse-error
# diagnosis during eager-while runs on a held-out MAC corpus. Diagnoses now
# come only from the hardcoded `_HARDCODED_PATTERNS` (EC-semantic facts) plus
# the computed error-level classification.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Pattern database — EC-semantic facts seeded from A/B tests
# ---------------------------------------------------------------------------

# Hardcoded fallback patterns (always available)
_HARDCODED_PATTERNS: list[Diagnosis] = [
    # --- Module path / apply failures ---
    Diagnosis(
        error_pattern=r"the given proof-term proves",
        tactic_pattern=r"apply",
        diagnosis="Module path mismatch. The subgoal's module paths (e.g., B_DDH.CCA.log) "
                  "don't match the lemma's paths (e.g., CCA.log).",
        suggestion="If you used 3-arg call (_: bad, Inv, true), switch to 2-arg call (_: bad, Inv). "
                   "The 2-arg form lets EasyCrypt auto-resolve module aliases, making apply work.",
        pitfall="P2",
        source="DDH1_G1 A/B test",
    ),
    Diagnosis(
        error_pattern=r"cannot infer module arguments",
        tactic_pattern=r"apply",
        diagnosis="Section-exported lemma has implicit module parameters that EC can't infer.",
        suggestion="Try apply (lemma_name ExplicitModule). If that also fails, inline the "
                   "lemma's proof body directly. Check the section header for `declare module` "
                   "to find which module to pass.",
        source="CCA_NA A/B test",
    ),

    # --- SMT failures ---
    Diagnosis(
        error_pattern=r"cannot prove goal.*strict",
        tactic_pattern=r"smt",
        diagnosis="SMT solver timeout or insufficient lemma hints.",
        suggestion="Try: (1) add specific lemma hints: smt(lemma1 lemma2). "
                   "(2) Decompose the goal with `have -> : expr1 = expr2 by ...` then retry smt. "
                   "(3) For group algebra: use `algebra` or `rewrite log_bij !(logg1, logrzM, logDr); ring`. "
                   "(4) For multiple conjuncts: `do !split; try algebra; smt()`.",
        source="CCA_DDH0, DDH1_G1 A/B tests",
    ),
    Diagnosis(
        error_pattern=r"Connection error.*why3server",
        tactic_pattern=r"smt|auto.*/#",
        diagnosis="why3server not running. SMT-dependent tactics (smt, auto => /#) need why3.",
        suggestion="Run the command with dangerouslyDisableSandbox: true, or ensure "
                   "why3server is on PATH (check ~/.opam/easycrypt/lib/why3/why3server).",
        source="Multiple A/B tests",
    ),
    Diagnosis(
        error_pattern=r"cannot find lemma",
        tactic_pattern=r"smt",
        diagnosis="Wrong lemma name in smt() hints.",
        suggestion="Use `lookup_symbol <partial_name>` to find the correct name "
                   "or read the current source file for broader declaration "
                   "context; clone-renamed lemmas show up through lookup too.",
        source="CCA_DDH0 A/B test",
    ),

    # --- Swap failures ---
    Diagnosis(
        error_pattern=r"not independent",
        tactic_pattern=r"swap",
        diagnosis="The two statements have a variable read/write dependency.",
        suggestion="Try: (1) swap on the other side (swap{2} instead of swap{1}). "
                   "(2) Apply wp/call first to consume dependent statements, then swap. "
                   "(3) Use -align to check which swaps are safe.",
        source="CCA_DDH0 A/B test",
    ),
    Diagnosis(
        error_pattern=r"too large by|too small by",
        tactic_pattern=r"swap",
        diagnosis="Swap offset is out of bounds.",
        suggestion="EC tells you the correction: 'too large by N' means reduce offset by N. "
                   "Recount statement positions — they change after prior swaps.",
        source="legacy evaluator runs",
    ),

    # --- Goal shape mismatches ---
    Diagnosis(
        error_pattern=r"instruction list is not empty",
        tactic_pattern=r"skip|smt",
        diagnosis="Program still has unconsumed statements.",
        suggestion="Use sp; skip instead of skip. Or apply wp/auto first to consume "
                   "remaining statements before skip/smt.",
        source="CCA_DDH0 A/B test",
    ),
    Diagnosis(
        error_pattern=r"expecting a goal of the form",
        tactic_pattern=r"proc|wp|rnd|call",
        diagnosis="Tactic expects a different goal shape. Two common causes: "
                   "(1) Compound tactic (byequiv; proc.) applied inner tactic to ambient goals. "
                   "(2) Goal is in ambient logic, not a program judgment. "
                   "(3) A named predicate/invariant or wrapper obligation is hiding the "
                   "program judgment one layer underneath.",
        suggestion="(1) Use separate lines: byequiv => //. then proc. separately. "
                   "(2) If post-pRHL ambient goal: use `by auto => />` or `by smt()`. "
                   "If group expressions: `rewrite expM` before auto. "
                   "(3) If the visible goal head is a named predicate/invariant, unfold "
                   "that predicate first, then retry the program tactic.",
        source="legacy evaluator runs, CCA_DDH0 A/B test",
    ),
    Diagnosis(
        error_pattern=r"nothing to rewrite",
        tactic_pattern=r"rewrite",
        diagnosis="The goal doesn't contain the pattern being rewritten.",
        suggestion="Check the goal state carefully — a prior tactic may have simplified "
                   "the expression. Try: (1) print the goal with -next -c 'idtac.'. "
                   "(2) The rewrite target may need a different qualified name.",
        source="Multiple A/B tests",
    ),
    Diagnosis(
        error_pattern=r"not a congruence",
        tactic_pattern=r"congr",
        diagnosis="congr requires both sides to have matching structure (1 - Pr[:E]).",
        suggestion="If the subtraction is flipped (Pr[:E] = 1 - Pr[:!E] instead of "
                   "Pr[:!E] = 1 - Pr[:E]), congr won't work. Use: have ll : Pr[:true] = 1%r "
                   "via byphoare, then rewrite Pr[mu_not] ll /#.",
        source="CCA_NA A/B test",
    ),

    # --- rnd failures ---
    Diagnosis(
        error_pattern=r"nothing to introduce|cannot infer.*set of equalities",
        tactic_pattern=r"rnd",
        diagnosis="rnd bijection can't be applied — goal may not be at a sampling statement, "
                   "or the bijection function type doesn't match.",
        suggestion="Check with -align that both sides are at matching <$ statements. "
                   "Use wp first to consume deterministic statements before rnd. "
                   "For rnd in phoare: rnd (pred1 var) or rnd predT.",
        source="DDH1_G1 A/B test",
    ),
    Diagnosis(
        error_pattern=r"support.*not compatible.*explicit bijection",
        tactic_pattern=r"rnd",
        diagnosis="Bare rnd (no bijection) failed because distributions differ.",
        suggestion="Provide an explicit bijection: rnd (fun x => f x) (fun x => g x). "
                   "The two functions must be inverses.",
        source="DDH1_G1 A/B test",
    ),

    # --- auto failures on reparameterized coupling ---
    Diagnosis(
        error_pattern=r"cannot prove goal",
        tactic_pattern=r"auto.*/>",
        diagnosis="auto => /> gave identity coupling but the postcondition needs non-trivial "
                   "variable relationships. Common when G1 reparameterizes samplings.",
        suggestion="Don't use auto for the entire sampling block. Use interleaved per-variable "
                   "coupling: swap{2} -1; rnd (fun z => z + w*x2) (fun z => z - w*x2); rnd; wp. "
                   "Repeat per variable pair. See Pitfall P3.",
        pitfall="P3",
        source="DDH1_G1 A/B test",
    ),

    # --- Unknown names ---
    Diagnosis(
        error_pattern=r"unknown.*lemma|unknown.*identifier|unknown.*operator",
        tactic_pattern=r"",
        diagnosis="The lemma/identifier name is not in scope.",
        suggestion="(1) Use `lookup_symbol <name>` to find the correct name (or "
                   "read the current source file for the broader declaration roster); "
                   "clone-renamed lemmas show up there too. (2) Check the qualified "
                   "path: the lemma may need a module prefix (e.g. "
                   "GP.ZModE.ZModpField.mulrK instead of mulrK).",
        source="Multiple A/B tests",
    ),

    # --- Intro-pattern / goal-direction mismatches ---
    Diagnosis(
        error_pattern=r"nothing to eliminate|invalid intro.pattern",
        tactic_pattern=r"split|move|case",
        diagnosis="The current goal doesn't support this intro-pattern. Common cause: "
                  "you are in the wrong subgoal direction (e.g., trying to split an "
                  "already-consumed conjunction), or the tactic is applied to a goal "
                  "that is not a product/conjunction/negation.",
        suggestion="Print the current goal with `-next -c 'idtac.'` to check the goal shape. "
                   "If you are trying to handle the backward direction of an iff, use "
                   "`apply/negP => bad; case: bad.` instead of `split. move=> ...`. "
                   "For a negation goal (!P), use `move=> h; apply ...` rather than `split`.",
        source="negBadE A/B test (0031)",
    ),

    # --- Constructor application: using /Constructor as a view ---
    Diagnosis(
        error_pattern=r"tactic failed|ill.typed|ill typed|bad.*application|not a function",
        tactic_pattern=r"/[A-Z]\w+|view.*[A-Z]",
        diagnosis="Using a constructor as a rewrite view with `/Constructor` doesn't work — "
                  "constructors are not iff lemmas. To prove a goal by constructing an "
                  "inductive witness, use `apply Constructor` directly (not `/Constructor`).",
        suggestion="Pattern for proving negation of an inductive predicate by providing a "
                   "witness:\n"
                   "  case (P x) => //.\n"
                   "  by move=> h; apply notBad; apply Constructor.\n"
                   "Or inline: `apply/negP => h; apply notBad; exact (Constructor _ _ h).`\n"
                   "For a Bool-valued predicate: `move=> /negP h; apply notBad; exact (...)`.",
        source="negBadE A/B test (0031): /Cycle was tried but Cycle is a constructor",
    ),

    # --- absurd tactic (does not exist in EasyCrypt) ---
    Diagnosis(
        error_pattern=r"unknown.*absurd|absurd.*unknown|not.*found.*absurd",
        tactic_pattern=r"absurd",
        diagnosis="`absurd` is not a standard EasyCrypt tactic. EC does not have Coq's `absurd`.",
        suggestion="To prove a goal by contradiction given `h : !P` and you want to show `P`, "
                   "use `exfalso` then prove `False`, or structure the proof differently:\n"
                   "  (1) If goal is `P` and you have `notBad : !Bad`, use `apply notBad`.\n"
                   "  (2) For a boolean negation `!P`, use `apply/negP => h; ...`.\n"
                   "  (3) `by move: hypothesis; rewrite ...` to derive contradiction directly.",
        source="negBadE A/B test (0031): absurd was tried but doesn't exist in EC",
    ),

    # --- Catch-all ---
    Diagnosis(
        error_pattern=r"parse error",
        tactic_pattern=r"",
        diagnosis="PARSE ERROR — the tactic did not parse, so EasyCrypt never ran it: "
                  "the proof state is UNCHANGED and this says NOTHING about whether the "
                  "route is valid or the goal is provable. It is purely a SYNTAX "
                  "problem — the tactic name or argument FORM is wrong for EC's grammar. "
                  "(Contrast a SEMANTIC rejection: the tactic parsed but EC rejected the "
                  "math — THAT is a real proof-state signal.) So fix the FORM, not the "
                  "strategy. Common causes: a missing '.' at the end; a bare form "
                  "where the tactic's grammar requires an explicit argument (the "
                  "tactic name written with no argument when one is needed); an "
                  "argument of the WRONG KIND (e.g. a predicate/invariant supplied "
                  "where a relational coupling is expected, or a multi-statement "
                  "block where a single statement or term is expected); or an "
                  "incorrect keyword.",
        suggestion="Get the VALID argument form before retrying — inspect "
                   "`tactic_forms` for the exact tactic you used. Guessing variants "
                   "will keep parse-erroring. Do NOT conclude the route is dead or "
                   "the goal is unprovable from a parse error — it only means the "
                   "spelling/shape is off.",
        source="parse-error A/B tests (wrong tactic-argument forms)",
    ),
]

# Active pattern list: hardcoded EC-semantic facts only (no KB advice catalog).
PATTERNS: list[Diagnosis] = _HARDCODED_PATTERNS


def _check_rnd_scoping(goal_state: str) -> str | None:
    """Check if the goal state shows rnd variable scoping issues.

    After rnd bijections, if a variable was consumed BEFORE its reference
    in a bijection formula, the postcondition contains both a free variable
    (e.g., z2{1}) and a separate quantified variable (e.g., z2L) that should
    be the same but aren't. This makes the postcondition unprovable.

    Returns a diagnosis string if the pattern is detected, None otherwise.
    """
    if not goal_state:
        return None

    # Find free {1} or {2} variable references in arithmetic expressions
    # Pattern: varname{1} or varname{2} in an expression context
    free_refs = re.findall(r'(\w+)\{([12])\}', goal_state)
    if not free_refs:
        return None

    # Find quantified variables (forall (varL : type))
    quantified = re.findall(r'forall\s+\((\w+)\s*:', goal_state)
    if not quantified:
        return None

    # Check for the mismatch pattern: a free ref like "z2{1}" coexisting
    # with a quantified "z2L" where the base names match
    mismatches = []
    for var_name, side in free_refs:
        # Skip common non-problematic references (glob, result, etc.)
        if var_name in ('glob', 'result', 'pred', 'G1', 'CCA', 'B_DDH',
                        'PKE_', 'DBool', 'None', 'Some'):
            continue
        # Look for a quantified variable with the same base + "L" or "R" suffix
        for qvar in quantified:
            if qvar == var_name + 'L' or qvar == var_name + 'R':
                # Check this isn't just the normal rnd coupling structure
                # The mismatch is when BOTH appear in the SAME nested scope
                # (the free ref is from an earlier bijection, the quantified
                # is from a later identity coupling)
                pattern = re.compile(
                    rf'{var_name}\{{{side}\}}.*forall\s+\({qvar}\s*:',
                    re.DOTALL
                )
                if pattern.search(goal_state):
                    mismatches.append((var_name, side, qvar))

    if not mismatches:
        return None

    # Build diagnosis
    examples = []
    for var_name, side, qvar in mismatches[:3]:  # show at most 3
        examples.append(f"  {var_name}{{{side}}} (free, from bijection) vs "
                        f"{qvar} (quantified, from coupling)")

    return (
        f"Likely rnd variable scoping issue. The postcondition contains "
        f"mismatched variable references:\n"
        + '\n'.join(examples) + '\n\n'
        f"Cause: a bijection function referenced {mismatches[0][0]}{{{mismatches[0][1]}}} "
        f"but that variable was consumed by a PREVIOUS rnd, making it a stale "
        f"free variable separate from the quantified {mismatches[0][2]}.\n\n"
        f"Fix: add `swap -1.` before the bijection rnd to ensure the referenced "
        f"variable is still in the program when the bijection executes.\n"
        f"Pattern: swap -1. rnd (bijection). rnd. wp.\n"
        f"See: rnd_variable_scoping and swap_minus_one_idiom in proof_guide.json"
    )


def diagnose(
    error_text: str,
    last_tactic: str = "",
    goal_state: str = "",
    proof_ir: dict | None = None,
) -> str:
    """Match an error against the pattern database and return diagnosis.

    Args:
        error_text: the EC error message (from [error-...] line)
        last_tactic: the tactic that caused the error (if known)
        goal_state: current goal state (for context)

    Returns:
        formatted diagnosis string
    """
    matches: list[tuple[Diagnosis, int]] = []  # (diagnosis, specificity score)
    proof_ir_block = _format_proof_ir_failure(
        proof_ir or {},
        latest_tactic=last_tactic,
        latest_error=error_text,
    )

    for pat in PATTERNS:
        error_match = re.search(pat.error_pattern, error_text, re.IGNORECASE)
        if not error_match:
            continue

        # Check tactic pattern if specified
        tactic_match = True
        specificity = 1
        if pat.tactic_pattern:
            if last_tactic and re.search(pat.tactic_pattern, last_tactic, re.IGNORECASE):
                specificity = 2  # both error and tactic match = more specific
            elif last_tactic:
                tactic_match = False  # tactic specified but doesn't match
            # if no last_tactic provided, skip tactic check

        if tactic_match:
            matches.append((pat, specificity))

    if not matches:
        result = (
            f"No known diagnosis for this error.\n"
            f"Error: {error_text.strip()}\n"
            f"Tactic: {last_tactic}\n\n"
            f"{proof_ir_block}"
            f"General suggestions:\n"
            f"  - Read the goal state carefully\n"
            f"  - Try a simpler version of the tactic\n"
            f"  - Use -search to verify lemma names\n"
            f"  - Step back: if stuck >5 min, reconsider the approach (Pitfall P4)\n"
        )
        rnd_scoping = _check_rnd_scoping(goal_state)
        if rnd_scoping:
            result += f"\n=== Additional: rnd scoping issue detected ===\n\n{rnd_scoping}\n"
        return result

    # Check for rnd scoping issues in the goal state (complements error-based diagnosis)
    rnd_scoping = _check_rnd_scoping(goal_state)

    # Sort by specificity (most specific first)
    matches.sort(key=lambda x: -x[1])
    best = matches[0][0]

    lines = ["=== Error Diagnosis ===\n"]
    lines.append(f"Error:      {error_text.strip()}")
    if last_tactic:
        lines.append(f"Tactic:     {last_tactic}")
    if proof_ir_block:
        lines.append("")
        lines.append(proof_ir_block.rstrip())

    # Strategy vs execution verdict
    if best.level == "strategy":
        lines.append(f"\nLevel:      STRATEGY — this tactic is likely wrong for this goal.")
        lines.append(f"            STOP trying different forms. Switch approach.")
        if best.when_to_abandon:
            lines.append(f"\nWhen to abandon: {best.when_to_abandon}")
    elif best.level == "execution":
        lines.append(f"\nLevel:      EXECUTION — the tactic is right, but the form is wrong.")
        lines.append(f"            Try other forms of the same tactic.")

    lines.append(f"\nDiagnosis:  {best.diagnosis}")
    lines.append(f"\nSuggestion: {best.suggestion}")
    if best.pitfall:
        lines.append(f"\nSee:        Pitfall {best.pitfall} in decision_tree.md")
    lines.append(f"\n(Source: {best.source})")

    # Append rnd scoping diagnosis if detected
    if rnd_scoping:
        lines.append(f"\n\n=== Additional: rnd scoping issue detected ===\n")
        lines.append(rnd_scoping)

    if len(matches) > 1:
        lines.append(f"\n({len(matches) - 1} other possible diagnoses)")

    lines.append("")
    return '\n'.join(lines)


def diagnose_from_session(session_dir: Path) -> str:
    """Read latest error from session and diagnose it.

    Prefers structured ``tactic.result.latest_error`` events, then falls back
    to current.out for older sessions.
    """
    curr = session_dir / "current.out"
    hist = session_dir / "history.ec"

    if not curr.exists():
        return "No session output found. Run -start and -next first.\n"

    projection = None
    event_error = ""
    event_tactic = ""
    try:
        from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore
        projection = read_proof_state_projection(
            session_dir,
            live_tool_name="diagnose",
        )
        event_error = projection.events.latest_error
        event_tactic = projection.events.latest_error_tactic
    except Exception:
        event_error, event_tactic = _latest_event_error(session_dir)

    try:
        from core.easycrypt.session_state import read_session_state  # type: ignore
        state = read_session_state(session_dir)
        curr_text = state.raw_current
        goal_state = state.raw_for_goal_tools
    except Exception:
        curr_text = curr.read_text(encoding="utf-8", errors="replace")
        goal_state = ""

    # Find latest error
    error_re = re.compile(r"^\s*\[(error|critical|fatal)")
    error_lines = [l for l in curr_text.split('\n') if error_re.match(l)]
    if not event_error and not error_lines:
        if projection is not None and projection.status in (
            "candidate_closed", "verified",
        ):
            return "Proof is already complete; no errors to diagnose.\n"
        return "No errors found in current session output.\n"

    latest_error = event_error or error_lines[-1].strip()

    # Find last tactic from history
    last_tactic = event_tactic
    if not last_tactic and projection is not None:
        last_tactic = projection.history.latest_tactic
    if not last_tactic and hist.exists():
        hist_lines = [l.strip() for l in hist.read_text().split('\n') if l.strip()]
        if hist_lines:
            last_tactic = hist_lines[-1]

    # Get goal state for deep analysis. Prefer session_state's active block;
    # keep the legacy scan only as a defensive fallback.
    if not goal_state:
        lines_list = curr_text.split('\n')
        last_goal_idx = -1
        for i, line in enumerate(lines_list):
            if line.strip() == "Current goal":
                last_goal_idx = i
        if last_goal_idx >= 0:
            max_lines = 1000
            end = min(last_goal_idx + max_lines, len(lines_list))
            for j in range(last_goal_idx + 1, end):
                if '[error' in lines_list[j] or '[check]>' in lines_list[j]:
                    end = j
                    break
            goal_state = '\n'.join(lines_list[last_goal_idx:end])
            if end == last_goal_idx + max_lines:
                goal_state += f"\n(goal state truncated at {max_lines} lines)"
    elif len(goal_state.splitlines()) > 1000:
        max_lines = 1000
        goal_state = (
            "\n".join(goal_state.splitlines()[:max_lines])
            + f"\n(goal state truncated at {max_lines} lines)"
        )

    proof_ir = _proof_ir_for_session(
        session_dir,
        projection=projection,
        goal_state=goal_state,
    )
    return diagnose(latest_error, last_tactic, goal_state, proof_ir=proof_ir)


def _format_proof_ir_failure(
    proof_ir: dict,
    *,
    latest_tactic: str,
    latest_error: str,
) -> str:
    if not proof_ir:
        return ""
    try:
        from core.easycrypt.analysis.ec_proof_diagnostics import (
            format_failure_diagnostics,
            proof_ir_failure_diagnostics,
        )
    except Exception:
        try:
            from core.easycrypt.analysis.ec_proof_diagnostics import (  # type: ignore
                format_failure_diagnostics,
                proof_ir_failure_diagnostics,
            )
        except Exception:
            return ""
    diagnostics = proof_ir_failure_diagnostics(
        proof_ir,
        latest_tactic=latest_tactic,
        latest_error=latest_error,
    )
    return format_failure_diagnostics(diagnostics)


def _proof_ir_for_session(
    session_dir: Path,
    *,
    projection,
    goal_state: str,
) -> dict:
    if projection is None:
        return {}
    try:
        from core.easycrypt.session_projection import projection_to_goal_info  # type: ignore
        from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # type: ignore
    except Exception:
        try:
            from core.easycrypt.session_projection import projection_to_goal_info
            from core.easycrypt.analysis.ec_proof_ir import build_proof_ir
        except Exception:
            return {}
    try:
        proof_state = projection_to_goal_info(projection)
        current_goal = projection.goal.to_dict(
            include_raw=bool(goal_state),
            raw_text=goal_state,
        )
        return build_proof_ir(
            session_dir=session_dir,
            proof_state=proof_state,
            current_goal=current_goal,
            external_recommendations=[],
        )
    except Exception:
        return {}


def _latest_event_error(session_dir: Path) -> tuple[str, str]:
    """Return ``(latest_error, tactic)`` from structured events, if present."""
    try:
        from core.easycrypt.session_events import (  # type: ignore
            latest_tactic_error,
            read_events,
        )
        latest = latest_tactic_error(read_events(session_dir))
    except Exception:
        return "", ""
    return latest.error, latest.tactic


def main():
    if len(sys.argv) > 1:
        # Read from file
        text = Path(sys.argv[1]).read_text()
        # Find errors
        errors = [l for l in text.split('\n') if '[error' in l]
        if errors:
            print(diagnose(errors[-1]))
        else:
            print("No errors found.")
    else:
        # Read from stdin
        text = sys.stdin.read()
        errors = [l for l in text.split('\n') if '[error' in l]
        if errors:
            print(diagnose(errors[-1]))
        else:
            print("No errors found.")


if __name__ == '__main__':
    main()
