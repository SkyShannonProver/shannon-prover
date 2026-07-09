#!/usr/bin/env python3
"""Bridge equiv lemma detection for sampling equivalence proofs.

For an equiv goal 'L.proc ~ R.proc', scans the loaded context for equiv lemmas
that form a transitivity chain connecting L.proc to R.proc.  Outputs ready-to-use
transitivity tactic templates.

Background
----------
Some equivalence proofs (e.g. D4.sample ~ D6.sample in Dice4_6.ec) should NOT
be opened with 'proc; inline *' because the RHS program contains a while-loop
whose unrolled form is complex.  Instead, the prover should identify bridge lemmas
such as:

    D4_Sample:  D4.sample    ~ D4_6.SampleE.sample  : true ==> ={res}
    D6_Sample:  D6.sample    ~ D4_6.SampleWi.sample : ...  ==> ={res}

and compose them via 'transitivity' without ever inlining the while-loop.

This tool automates that pattern:
  1. Parses all 'equiv' declarations from the context file.
  2. Builds a directed graph (LHS → RHS, and reverse for symmetry).
  3. BFS up to depth 3 to find chains connecting the goal programs.
  4. Outputs transitivity tactic templates for found chains.

Usage (via session_cli):
    python3 core/easycrypt/session_cli.py -d .ec_session -bridge-lemmas

Usage (standalone):
    python3 -m core.easycrypt.ec_bridge_lemmas < current.out
"""
from __future__ import annotations

import re
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.easycrypt.analysis.ec_procedure_ref import (
    procedure_tail_key as _procedure_tail_key,
)

try:
    from .session_state import extract_goal_body as _shared_extract_goal_body
except ImportError:  # pragma: no cover - direct script/session_cli execution
    from core.easycrypt.session_state import (  # type: ignore
        extract_goal_body as _shared_extract_goal_body,
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EquivLemma:
    name: str
    lhs: str        # "Module.proc" (no parentheses, stripped)
    rhs: str        # "Module.proc" (no parentheses, stripped)
    pre: str        # precondition text
    post: str       # postcondition text
    line_num: int = 0
    params: str = ''   # binder names/typed binders before the judgment colon, e.g. "n0 mr0 ms0"


@dataclass
class Chain:
    steps: list[EquivLemma]    # ordered lemmas in the chain
    directions: list[bool]     # True = forward (lhs→rhs), False = backward (rhs→lhs)
    intermediates: list[str]   # intermediate procedure names between steps


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_proc(raw: str) -> str:
    """Strip parentheses and whitespace from a procedure reference.

    "D4_6.SampleE.sample()" → "D4_6.SampleE.sample"
    " D4.sample " → "D4.sample"
    """
    return re.sub(r'\s*\(\s*\)\s*', '', raw).strip()


def _depth0_indices(s: str, ch: str) -> list[int]:
    """Indices of single-char ``ch`` in ``s`` at parenthesis/bracket depth 0.

    Lets the equiv parser split ``<params> : <LHS> ~ <RHS> : <pre>`` without being
    fooled by typed binders ``(x : T)`` or functor endpoints ``ChaCha(CCRO(...)).enc``.
    """
    depth = 0
    out: list[int] = []
    for k, c in enumerate(s):
        if c in '([':
            depth += 1
        elif c in ')]':
            depth = max(0, depth - 1)
        elif c == ch and depth == 0:
            out.append(k)
    return out


def _proc_tail(proc: str) -> str:
    """Return the last two top-level dot-separated components of a procedure path.

    Used for fuzzy matching when module prefixes differ. Dots INSIDE parentheses
    (functor arguments) are ignored so ``ChaCha(CCRO(A.b)).enc`` is not shredded.
    "D4_6.SampleE.sample" → "SampleE.sample"; "D4.sample" → "D4.sample";
    "ChaCha(CCRO(A.b)).enc" → "ChaCha(CCRO(A.b)).enc" (single top-level dot).
    """
    return _procedure_tail_key(proc, strip_outer=False)


def _procs_match(p1: str, p2: str) -> bool:
    """True if p1 and p2 refer to the same procedure.

    Compares both the full path and the last-two-component tail to tolerate
    module-wrapper differences (e.g. 'D4_6.SampleE.sample' vs 'SampleE.sample').
    """
    if p1 == p2:
        return True
    return _proc_tail(p1) == _proc_tail(p2)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_equiv_lemmas(text: str) -> list[EquivLemma]:
    """Parse all 'equiv' declarations from .ec file text.

    Handles:
    - Single-line:  equiv Name: A.f ~ B.g : pre ==> post.
    - Multi-line declarations (collects up to 15 continuation lines).
    - Section-local (prefixed with 'local').
    """
    lemmas: list[EquivLemma] = []
    lines = text.split('\n')

    # Match `(local) equiv <name>` only; the binders + judgment that follow are
    # parsed paren-aware by _parse_equiv_decl. The OLD regex required `:` right
    # after the name, which dropped EVERY parameterized lemma (e.g. a lemma whose
    # name is followed by binders `p0 p1 p2`) and could not capture functor
    # endpoints like `Outer(Inner(...)).proc`.
    head_re = re.compile(r"^\s*(?:local\s+)?equiv\s+([A-Za-z_][\w']*)(.*)$")

    i = 0
    while i < len(lines):
        m = head_re.match(lines[i])
        if m:
            full_decl = m.group(2)
            j = i + 1
            while j < len(lines) and '==>' not in full_decl and j < i + 15:
                stripped = lines[j].strip()
                if not stripped or stripped.startswith('proof') or stripped.startswith('(*'):
                    break
                full_decl += ' ' + stripped
                j += 1
            lem = _parse_equiv_decl(m.group(1), full_decl, i + 1)
            if lem is not None:
                lemmas.append(lem)
        i += 1

    return lemmas


def _parse_equiv_decl(name: str, decl: str, line_num: int) -> Optional[EquivLemma]:
    """Parse the post-name text ``<params> : <LHS> ~ <RHS> : <pre> ==> <post>``.

    Paren-aware: a typed binder colon ``(x : T)`` and functor endpoints
    ``A(B(C)).proc`` do not confuse the ``~``/``:`` splits.
    """
    decl = decl.strip()
    tildes = _depth0_indices(decl, '~')
    if not tildes:
        return None
    left, right = decl[:tildes[0]], decl[tildes[0] + 1:]
    # left = `<params> : <LHS>` — LHS follows the LAST depth-0 colon; params precede it.
    left_colons = _depth0_indices(left, ':')
    if not left_colons:
        return None
    params = left[:left_colons[-1]].strip()
    lhs = _normalize_proc(left[left_colons[-1] + 1:])
    # right = `<RHS> : <pre> ==> <post>` — RHS precedes the FIRST depth-0 colon.
    right_colons = _depth0_indices(right, ':')
    if right_colons:
        rhs = _normalize_proc(right[:right_colons[0]])
        body = right[right_colons[0] + 1:].strip()
    else:
        rhs = _normalize_proc(right)
        body = ''
    if '==>' in body:
        pre_raw, post_raw = body.split('==>', 1)
        pre, post = pre_raw.strip(), post_raw.strip().rstrip('.')
    else:
        pre, post = body.rstrip('.'), ''
    # Sanity: endpoints must not look like a tactic fragment.
    if not lhs or not rhs or re.search(r'[;{}]', lhs + rhs):
        return None
    return EquivLemma(
        name=name, lhs=lhs, rhs=rhs, pre=pre, post=post,
        line_num=line_num, params=params,
    )


def parse_goal_programs(raw_goal: str) -> tuple[Optional[str], Optional[str], str, str]:
    """Extract LHS and RHS procedure names from the current EC goal state.

    Returns (lhs_proc, rhs_proc, pre, post).  Procedures are normalized
    (no parentheses).  Returns (None, None, '', '') if no equiv goal found.

    Handles:
    - Inline equiv form: "equiv [D4.sample ~ D6.sample : pre ==> post]"
    - Display form after 'move=>' with hypotheses stripped:
        "D4.sample ~ D6.sample" on its own line, then "pre = ...", "post = ..."
    """
    body = _shared_extract_goal_body(raw_goal)

    # Pattern A: "equiv [M1.p1 ~ M2.p2 : pre ==> post]"
    equiv_bracket_re = re.compile(
        r'equiv\s*\[\s*([\w.\']+)\s*(?:\(\s*\))?\s*~\s*([\w.\']+)\s*(?:\(\s*\))?\s*:'
        r'\s*(.*?)==>\s*(.*?)\s*\]',
        re.DOTALL,
    )
    m = equiv_bracket_re.search(body)
    if m:
        lhs = _normalize_proc(m.group(1))
        rhs = _normalize_proc(m.group(2))
        pre = m.group(3).strip()
        post = m.group(4).strip()
        return lhs, rhs, pre, post

    # Pattern B: "M1.p1 ~ M2.p2" on a standalone line (after proc/move=>)
    tilde_line_re = re.compile(
        r'^\s*([\w.\']+)\s*(?:\(\s*\))?\s*~\s*([\w.\']+)\s*(?:\(\s*\))?\s*$',
        re.MULTILINE,
    )
    m = tilde_line_re.search(body)
    if m:
        lhs = _normalize_proc(m.group(1))
        rhs = _normalize_proc(m.group(2))
        pre_m = re.search(r'^pre\s*=\s*(.+)$', body, re.MULTILINE)
        post_m = re.search(r'^post\s*=\s*(.+)$', body, re.MULTILINE)
        pre = pre_m.group(1).strip() if pre_m else 'true'
        post = post_m.group(1).strip() if post_m else '={res}'
        return lhs, rhs, pre, post

    # Pattern C: broader tilde search (fallback)
    any_tilde_re = re.compile(
        r'([\w.\']+)\s*(?:\(\s*\))?\s*~\s*([\w.\']+)\s*(?:\(\s*\))?'
    )
    m = any_tilde_re.search(body)
    if m:
        lhs = _normalize_proc(m.group(1))
        rhs = _normalize_proc(m.group(2))
        pre_m = re.search(r'^pre\s*=\s*(.+)$', body, re.MULTILINE)
        post_m = re.search(r'^post\s*=\s*(.+)$', body, re.MULTILINE)
        pre = pre_m.group(1).strip() if pre_m else 'true'
        post = post_m.group(1).strip() if post_m else '={res}'
        return lhs, rhs, pre, post

    return None, None, '', ''


# ---------------------------------------------------------------------------
# Chain finding (BFS up to depth 3)
# ---------------------------------------------------------------------------

def find_bridge_chains(
    goal_lhs: str,
    goal_rhs: str,
    lemmas: list[EquivLemma],
    max_depth: int = 3,
) -> list[Chain]:
    """BFS to find chains of equiv lemmas connecting goal_lhs → goal_rhs.

    Each lemma can be used in forward direction (lhs→rhs) or backward (rhs→lhs).
    Returns up to 5 shortest chains.
    """
    if not lemmas:
        return []

    # Collect all known procedure names
    all_procs: set[str] = {goal_lhs, goal_rhs}
    for lem in lemmas:
        all_procs.add(lem.lhs)
        all_procs.add(lem.rhs)

    # Build adjacency: proc → [(next_proc, lemma, forward)]
    adj: dict[str, list[tuple[str, EquivLemma, bool]]] = {p: [] for p in all_procs}

    for lem in lemmas:
        for src in all_procs:
            if _procs_match(src, lem.lhs):
                for dst in all_procs:
                    if _procs_match(dst, lem.rhs) and not _procs_match(src, dst):
                        adj[src].append((dst, lem, True))
            if _procs_match(src, lem.rhs):
                for dst in all_procs:
                    if _procs_match(dst, lem.lhs) and not _procs_match(src, dst):
                        adj[src].append((dst, lem, False))

    # BFS: state = (current_proc, steps_taken, directions, intermediates)
    queue: deque = deque()
    queue.append((goal_lhs, [], [], []))
    found: list[Chain] = []
    # Track (proc, depth) pairs visited to avoid cycles
    visited: set[tuple[str, int]] = set()

    while queue:
        curr_proc, steps, directions, intermediates = queue.popleft()

        state_key = (curr_proc, len(steps))
        if state_key in visited:
            continue
        visited.add(state_key)

        # Goal reached?
        if len(steps) > 0 and _procs_match(curr_proc, goal_rhs):
            found.append(Chain(
                steps=list(steps),
                directions=list(directions),
                intermediates=list(intermediates),
            ))
            if len(found) >= 5:
                break
            continue

        if len(steps) >= max_depth:
            continue

        for next_proc, lem, forward in adj.get(curr_proc, []):
            # Avoid using the same lemma twice
            if any(s.name == lem.name for s in steps):
                continue
            new_intermediates = intermediates + [curr_proc] if steps else intermediates
            queue.append((
                next_proc,
                steps + [lem],
                directions + [forward],
                new_intermediates,
            ))

    # Deduplicate by (lemma_name, direction) tuple
    seen: set = set()
    unique: list[Chain] = []
    for chain in found:
        key = tuple(zip([l.name for l in chain.steps], chain.directions))
        if key not in seen:
            seen.add(key)
            unique.append(chain)

    # Sort by length (shortest first)
    unique.sort(key=lambda c: len(c.steps))
    return unique


# ---------------------------------------------------------------------------
# Transitivity template generation
# ---------------------------------------------------------------------------

def _proc_display(proc: str) -> str:
    """Format a proc for display in EC tactic: 'Module.proc()'."""
    return proc + '()'


def _format_chain_template(
    chain: Chain,
    goal_lhs: str,
    goal_rhs: str,
    goal_pre: str,
    goal_post: str,
) -> str:
    """Generate a transitivity tactic template for a chain."""
    lines: list[str] = []
    n = len(chain.steps)

    if n == 0:
        return "(* empty chain *)"

    # Build the full proc sequence: lhs → int1 → int2 → ... → rhs
    proc_seq = [goal_lhs]
    for lem, fwd in zip(chain.steps, chain.directions):
        proc_seq.append(lem.rhs if fwd else lem.lhs)

    if n == 1:
        lem = chain.steps[0]
        fwd = chain.directions[0]
        lines.append(f"(* Direct bridge: {lem.name}: {lem.lhs} ~ {lem.rhs} *)")
        if fwd:
            lines.append(f"exact {lem.name}.")
        else:
            lines.append(f"symmetry; exact {lem.name}.")
        return '\n'.join(lines)

    if n == 2:
        lem1, lem2 = chain.steps
        fwd1, fwd2 = chain.directions
        mid = proc_seq[1]
        mid_disp = _proc_display(mid)

        # Determine sensible intermediate pre/post
        # For step 1: goal_pre ==> lem1.post (or lem1.pre ==> lem1.post via sym)
        step1_post = (lem1.post if fwd1 else lem1.pre).strip().rstrip('.')
        if not step1_post:
            step1_post = '={res}'

        lines.append(f"(* 2-step bridge via {mid}: *)")
        lines.append(f"(*   {goal_lhs} ~ {mid} ~ {goal_rhs} *)")
        lines.append(f"transitivity {mid_disp}")
        lines.append(f"  ({goal_pre} ==> {step1_post})")
        lines.append(f"  ({(lem2.pre if fwd2 else lem2.post).strip().rstrip('.') or 'true'} ==> {goal_post})")
        lines.append(f"  + (* {goal_lhs} ~ {mid} via {lem1.name} *)")
        if fwd1:
            lines.append(f"    exact {lem1.name}.")
        else:
            lines.append(f"    symmetry; exact {lem1.name}.")
        lines.append(f"  + (* {mid} ~ {goal_rhs} via {lem2.name} *)")
        if fwd2:
            lines.append(f"    exact {lem2.name}.")
        else:
            lines.append(f"    symmetry; exact {lem2.name}.")
        return '\n'.join(lines)

    # 3+ hops: produce a nested transitivity outline
    lines.append(f"(* {n}-hop chain: {' ~ '.join(proc_seq)} *)")
    lines.append(f"(* Compose with nested transitivity *)")
    lines.append("")

    for k, (lem, fwd) in enumerate(zip(chain.steps, chain.directions)):
        mid = proc_seq[k + 1]
        mid_disp = _proc_display(mid)
        lines.append(f"(* Step {k + 1}: {'forward' if fwd else 'backward/sym'} via {lem.name}: {lem.lhs} ~ {lem.rhs} *)")
        if k == 0:
            lines.append(f"transitivity {mid_disp}")
            lines.append(f"  ({goal_pre} ==> ...)  (* fill: intermediate post *)")
            lines.append(f"  (... ==> {goal_post})  (* fill: intermediate pre *)")
        if fwd:
            lines.append(f"  + exact {lem.name}.")
        else:
            lines.append(f"  + symmetry; exact {lem.name}.")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze_bridge_lemmas(raw_goal: str, context_text: str) -> str:
    """Analyze current goal and context, return bridge lemma suggestions."""
    goal_lhs, goal_rhs, goal_pre, goal_post = parse_goal_programs(raw_goal)

    if goal_lhs is None:
        return (
            "=== Bridge Lemma Analysis ===\n\n"
            "No equiv/pRHL goal with a '~' found in the current goal state.\n"
            "This tool applies to equiv goals (before 'proc') or pRHL goals\n"
            "where the original module names are still visible.\n"
            "Use -goal-info to check the current goal type.\n"
        )

    lemmas = parse_equiv_lemmas(context_text)

    out: list[str] = []
    out.append("=== Bridge Lemma Analysis ===\n")
    out.append(f"Goal: {goal_lhs} ~ {goal_rhs}")
    out.append(f"  pre  = {goal_pre}")
    out.append(f"  post = {goal_post}\n")

    if not lemmas:
        out.append("No equiv lemmas found in context.")
        out.append("Cannot compose via transitivity with available lemmas.")
        out.append("\nFor this goal, consider:")
        out.append("  proc.  (* opens program listing *)")
        out.append("  proc; sim.  (* if programs are structurally similar *)")
        return '\n'.join(out) + '\n'

    out.append(f"Equiv lemmas in context ({len(lemmas)} found):")
    for lem in lemmas:
        out.append(f"  {lem.name}: {lem.lhs} ~ {lem.rhs}")
        if lem.pre and lem.pre != 'true':
            pre_short = lem.pre[:70] + '…' if len(lem.pre) > 70 else lem.pre
            out.append(f"    pre:  {pre_short}")
        post_short = lem.post[:70] + '…' if len(lem.post) > 70 else lem.post
        if post_short:
            out.append(f"    post: {post_short}")
    out.append("")

    # Find chains
    chains = find_bridge_chains(goal_lhs, goal_rhs, lemmas)

    if not chains:
        out.append("No transitivity chain found connecting the goal programs.\n")

        # Show partial matches to help the user understand what's missing
        lhs_matches = [
            l for l in lemmas
            if _procs_match(goal_lhs, l.lhs) or _procs_match(goal_lhs, l.rhs)
        ]
        rhs_matches = [
            l for l in lemmas
            if _procs_match(goal_rhs, l.lhs) or _procs_match(goal_rhs, l.rhs)
        ]

        if lhs_matches:
            out.append(f"Lemmas touching left program ({goal_lhs}):")
            for l in lhs_matches:
                out.append(f"  {l.name}: {l.lhs} ~ {l.rhs}")
        if rhs_matches:
            out.append(f"Lemmas touching right program ({goal_rhs}):")
            for l in rhs_matches:
                out.append(f"  {l.name}: {l.lhs} ~ {l.rhs}")

        out.append("")
        out.append("If a connecting lemma exists in a theory (not loaded in context),")
        out.append("use -search to find it, e.g.: -search 'SampleE.*SampleWi'")
        out.append("Then add it to the context by loading the relevant theory.")
        out.append("")
        out.append("Alternatively, consider direct proof via proc/inline/wp/auto.")
    else:
        out.append(f"Found {len(chains)} bridge chain(s) for transitivity:\n")

        for k, chain in enumerate(chains):
            n = len(chain.steps)
            lem_names = [
                ('sym ' if not fwd else '') + lem.name
                for lem, fwd in zip(chain.steps, chain.directions)
            ]
            proc_seq = [goal_lhs]
            for lem, fwd in zip(chain.steps, chain.directions):
                proc_seq.append(lem.rhs if fwd else lem.lhs)

            out.append(f"Chain {k + 1} ({n} step{'s' if n != 1 else ''}):")
            out.append(f"  " + " →\n  ".join(
                f"{proc_seq[i]}  [{lem_names[i]}]" for i in range(n)
            ) + f"\n  → {proc_seq[-1]}")
            out.append("")

            template = _format_chain_template(
                chain, goal_lhs, goal_rhs, goal_pre, goal_post,
            )
            for line in template.split('\n'):
                out.append(f"  {line}")
            out.append("")

        out.append("NOTES:")
        out.append("  - 'exact lem.' works when the bridge lemma postcondition exactly matches.")
        out.append("    If it does not, you may need 'apply lem => /> ...' to discharge side goals.")
        out.append("  - Fill in the '...' placeholders in the transitivity pre/post with the")
        out.append("    intermediate procedure's invariant (check the bridge lemma's post-condition).")
        out.append("  - If the bijection postcondition (e.g. res{1} = finv res{2}) differs from")
        out.append("    the bridge lemma's post (={res}), add a final 'move=> />' or 'congr' step.")

    return '\n'.join(out) + '\n'


def analyze_bridge_lemmas_from_session(session_dir: str | Path) -> str:
    """Entry point called from session_cli: reads goal state + context from session."""
    session_dir = Path(session_dir)

    try:
        from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore
        from core.easycrypt.session_state import read_session_state  # type: ignore
    except Exception:
        read_proof_state_projection = None  # type: ignore
        read_session_state = None  # type: ignore

    curr = session_dir / "current.out"
    if not curr.exists() or curr.stat().st_size == 0:
        return (
            "[bridge-lemmas] No current goal state found.\n"
            "Run -start -f <file.ec> and at least one -next tactic first.\n"
        )

    if read_proof_state_projection is not None:
        projection = read_proof_state_projection(
            session_dir,
            live_tool_name="bridge-lemmas",
        )
        if projection.status in ("candidate_closed", "verified"):
            return (
                "[bridge-lemmas] Proof is already complete; "
                "no bridge lemmas needed.\n"
            )
        if projection.consistency.errors:
            lines = [
                "[bridge-lemmas] Inconsistent proof state; "
                "refusing bridge analysis.",
            ]
            lines.extend(f"  - {e}" for e in projection.consistency.errors[:5])
            return "\n".join(lines) + "\n"

    if read_session_state is not None:
        state = read_session_state(session_dir)
        raw_goal = state.raw_for_goal_tools
    else:
        raw_goal = curr.read_text(encoding="utf-8", errors="replace")

    # Find context file: prefer extracted_*.ec (lemma-extracted), then context.ec
    context_text = ""
    ctx_file: Optional[Path] = None
    for f in sorted(session_dir.glob("extracted_*.ec")):
        ctx_file = f
        break
    if ctx_file is None:
        ctx_file = session_dir / "context.ec"

    if ctx_file and ctx_file.exists():
        context_text = ctx_file.read_text(encoding="utf-8", errors="replace")

    if not context_text:
        return (
            "[bridge-lemmas] No context file found.\n"
            "Start the session with -start -f <file.ec> to load a context.\n"
        )

    return analyze_bridge_lemmas(raw_goal, context_text)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Read goal state from stdin, context from argv[1]."""
    raw_goal = sys.stdin.read()
    context_text = ""
    if len(sys.argv) > 1:
        ctx_path = Path(sys.argv[1])
        if ctx_path.exists():
            context_text = ctx_path.read_text(encoding="utf-8", errors="replace")
    print(analyze_bridge_lemmas(raw_goal, context_text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
