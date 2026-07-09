#!/usr/bin/env python3
"""Suggest closing tactics for EasyCrypt ambient/logic goals.

When the current goal is a pure logical formula (no program statements),
analyzes the goal structure and suggests closing tactics with relevant
lemma hints.

Usage via session_cli:
    python3 core/easycrypt/session_cli.py -d .ec_session -suggest-close
"""
from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Goal analysis helpers
# ---------------------------------------------------------------------------

def _is_program_free(goal_body: str) -> tuple[bool, bool]:
    """Check if the goal body contains program statements.

    Returns (is_free, has_assigns_only):
      - (True, False)  — no program operators at all
      - (False, True)  — only deterministic assignments (<-), no samples/calls
      - (False, False) — has samples (<$) or calls (<@)
    """
    # Strip comments
    stripped = re.sub(r'\(\*.*?\*\)', '', goal_body, flags=re.DOTALL)
    has_sample_or_call = bool(re.search(r'<\$|<@', stripped))
    has_assign = bool(re.search(r'<-(?!=)', stripped))
    if has_sample_or_call:
        return False, False
    if has_assign:
        return False, True
    return True, False


def _detect_patterns(goal_body: str) -> dict[str, list[str]]:
    """Extract algebraic patterns from the goal body.

    Returns a dict of pattern categories to lists of matched snippets.
    """
    patterns: dict[str, list[str]] = {
        'group_ops': [],
        'trivial': [],
        'membership': [],
        'forall_impl': [],
    }

    # Group operations: g ^ ..., x ^ y, exponentiation
    for m in re.finditer(r'\bg\s*\^\s*\([^)]+\)|\bg\s*\^\s*\w+', goal_body):
        patterns['group_ops'].append(m.group().strip())
    # x ^ y ^ z  (chained exponentiation — suggests expM)
    for m in re.finditer(r'\w+\s*\^\s*\w+\s*\^\s*\w+', goal_body):
        patterns['group_ops'].append(m.group().strip())
    # x * y  (group multiplication)
    if re.search(r'\*', goal_body):
        patterns['group_ops'].append('*')

    # Trivial equalities: x = x
    for m in re.finditer(r'(\w+)\s*=\s*(\w+)', goal_body):
        if m.group(1) == m.group(2):
            patterns['trivial'].append(m.group())

    # Membership: _ \in dt, _ \in {0,1}
    for m in re.finditer(r'\\in\s+(\w+|\{[^}]+\})', goal_body):
        patterns['membership'].append(m.group())

    # Forall / implications at top level
    if '=>' in goal_body:
        patterns['forall_impl'].append('=>')
    if 'forall' in goal_body:
        patterns['forall_impl'].append('forall')

    return patterns


# Known lemma groups for common pattern types.
# These are short, high-value lists — kept small to produce clean suggestions.
_GROUP_LEMMAS = ['expM', 'expD', 'expN', 'mulrC', 'mulrA', 'invrK']
_DIST_LEMMAS = ['dt_ll', 'dbool1E']


def _find_relevant_lemmas(patterns: dict[str, list[str]],
                          search_dirs: list[Path],
                          context_file: Path | None = None) -> list[tuple[str, str]]:
    """Find lemmas relevant to the detected patterns.

    Returns (name, body_preview) pairs.
    """
    # Determine which lemma names to search for
    candidates: set[str] = set()
    if patterns.get('group_ops'):
        candidates.update(_GROUP_LEMMAS)
    if patterns.get('membership'):
        candidates.update(_DIST_LEMMAS)

    if not candidates:
        return []

    # Search in theory files
    decl_pat = re.compile(
        r'^\s*(lemma|axiom)\s+(?:\[.*?\]\s+)?(\w+)',
        re.MULTILINE,
    )

    # Priority order for candidates (most useful first)
    priority = {name: i for i, name in enumerate(
        _GROUP_LEMMAS + _DIST_LEMMAS)}

    found: dict[str, str] = {}  # name -> preview (first match wins)

    files: list[Path] = []
    for d in search_dirs:
        if d.is_dir():
            files.extend(d.rglob('*.ec'))
            files.extend(d.rglob('*.eca'))
    if context_file and context_file.exists():
        files.append(context_file)

    for f in files:
        try:
            text = f.read_text(encoding='utf-8', errors='replace')
        except (OSError, UnicodeDecodeError):
            continue
        for m in decl_pat.finditer(text):
            name = m.group(2)
            if name not in candidates or name in found:
                continue
            # Extract a short body preview
            line_end = text.find('\n', m.start())
            if line_end == -1:
                line_end = len(text)
            preview = text[m.start():line_end].strip()
            if len(preview) > 80:
                preview = preview[:77] + '...'
            found[name] = preview

    # Sort by priority order
    result = sorted(found.items(), key=lambda kv: priority.get(kv[0], 999))
    return result


def _build_suggestions(patterns: dict[str, list[str]],
                       lemmas: list[tuple[str, str]]) -> list[str]:
    """Build a prioritized list of closing tactic suggestions."""
    # Cap at 5 lemma hints to keep suggestions clean
    lemma_names = [n for n, _ in lemmas[:5]]
    hints = ' '.join(lemma_names) if lemma_names else ''
    has_forall = bool(patterns.get('forall_impl'))
    has_group = bool(patterns.get('group_ops'))
    has_trivial = bool(patterns.get('trivial'))

    suggestions: list[str] = []

    # Pure trivial goal
    if has_trivial and not has_group and not lemma_names:
        suggestions.append('done.')
        suggestions.append('trivial.')
        suggestions.append('smt().')
        return suggestions

    # Has algebraic content with lemma hints
    if hints:
        if has_forall:
            suggestions.append(f'move=> />; smt({hints}).')
            suggestions.append(f'smt({hints}).')
        else:
            suggestions.append(f'smt({hints}).')
            suggestions.append(f'move=> />; smt({hints}).')
    else:
        if has_forall:
            suggestions.append('move=> />; smt().')
        suggestions.append('smt().')

    # General fallbacks
    suggestions.append('auto => />.')
    if has_group and not hints:
        suggestions.append('algebra.')

    return suggestions


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def suggest_close(goal_text: str, search_dirs: list[Path],
                  context_file: Path | None = None) -> str:
    """Analyze a goal and suggest closing tactics.

    Args:
        goal_text: the raw goal state text (from current.out or similar)
        search_dirs: directories containing EC theory files
        context_file: the loaded .ec context file (for scope awareness)

    Returns:
        formatted suggestion output
    """
    try:
        from core.easycrypt.session_state import latest_state_is_closed  # type: ignore
        is_closed = latest_state_is_closed(goal_text)
    except Exception:
        is_closed = "No more goals" in goal_text
    if is_closed:
        return "Proof is already complete; no goals to close.\n"

    # Detect probability goals: Pr[...] expressions require byphoare/byequiv
    if re.search(r'\bPr\s*\[', goal_text):
        return ("=== Suggest Close ===\n\n"
                "Goal type: probability statement (contains Pr[...])\n\n"
                "Suggested tactics:\n"
                "  1. byphoare => //.   (* single-game probability bound *)\n"
                "  2. byequiv => //.    (* two-game probability comparison *)\n"
                "  3. bypr ... .        (* probability coupling *)\n")

    # Detect equiv goals: equiv[M1 ~ M2 : ...] or pRHL display (X ~ Y between pre/post)
    if re.search(r'\bequiv\s*\[', goal_text) or re.search(r'\w+\.?\w+\s+~\s+\w+\.?\w+', goal_text):
        return ("=== Suggest Close ===\n\n"
                "Goal type: equivalence statement (contains equiv[...])\n\n"
                "Suggested tactics:\n"
                "  1. proc.              (* enter procedure bodies *)\n"
                "  2. sim.               (* automatic simulation *)\n"
                "  3. transitivity M ... (* decompose via intermediate game *)\n"
                "  4. bypr ... .         (* reduce to probability equality *)\n")

    is_free, assigns_only = _is_program_free(goal_text)
    if not is_free and not assigns_only:
        return ("=== Suggest Close ===\n\n"
                "Goal still contains samples (<$) or calls (<@).\n"
                "Use wp/auto/call/rnd to consume them before using -suggest-close.\n")
    if assigns_only:
        return ("=== Suggest Close ===\n\n"
                "Goal has only deterministic assignments (<-) remaining.\n"
                "Suggested tactics:\n"
                "  1. auto => />; smt().   (* consume assigns, then close *)\n"
                "  2. skip => />; smt().   (* skip assigns, then close *)\n"
                "  3. wp; skip => />.      (* wp consumes assigns *)\n")

    patterns = _detect_patterns(goal_text)
    lemmas = _find_relevant_lemmas(patterns, search_dirs, context_file)
    suggestions = _build_suggestions(patterns, lemmas)

    lines = ["=== Suggest Close ===\n"]

    lines.append("Goal type: ambient logic (program-free)\n")

    # Show detected patterns
    lines.append("Detected patterns:")
    any_pattern = False
    if patterns['group_ops']:
        unique = list(dict.fromkeys(patterns['group_ops']))[:5]
        lines.append(f"  - Group operations: {', '.join(unique)}")
        any_pattern = True
    if patterns['trivial']:
        lines.append(f"  - Trivial equalities: {', '.join(patterns['trivial'][:3])}")
        any_pattern = True
    if patterns['membership']:
        lines.append(f"  - Membership: {', '.join(patterns['membership'][:3])}")
        any_pattern = True
    if patterns['forall_impl']:
        lines.append(f"  - Implications/quantifiers: {', '.join(patterns['forall_impl'])}")
        any_pattern = True
    if not any_pattern:
        lines.append("  (none detected)")
    lines.append("")

    # Show relevant lemmas
    if lemmas:
        lines.append("Relevant lemmas found:")
        for name, preview in lemmas[:8]:
            lines.append(f"  - {name}: {preview}")
        lines.append("")

    # Show suggestions
    lines.append("Suggested tactics (try in order):")
    for i, s in enumerate(suggestions, 1):
        lines.append(f"  {i}. {s}")
    lines.append("")

    return '\n'.join(lines)


def suggest_from_session(session_dir: Path, search_dirs: list[Path]) -> str:
    """Entry point from session_cli: read current.out and suggest."""
    try:
        from core.easycrypt.session_state import (  # type: ignore
            extract_goal_body,
            read_session_state,
        )
        from core.easycrypt.session_projection import read_proof_state_projection  # type: ignore
    except Exception:
        return "session state/projection import failed; cannot inspect current goal.\n"

    projection = read_proof_state_projection(
        session_dir,
        live_tool_name="suggest-close",
    )
    if projection.status in ("candidate_closed", "verified"):
        return "Proof is already complete; no goals to close.\n"
    if projection.consistency.errors:
        return (
            "Inconsistent proof state; refusing to suggest closing tactics.\n"
            + "\n".join(f"  - {e}" for e in projection.consistency.errors)
            + "\n"
        )
    state = read_session_state(session_dir)
    if not state.has_current:
        return "No current goal state. Run -start and -next first.\n"

    goal_text = extract_goal_body(state.raw_for_goal_tools)

    # Find context file
    context_file = None
    ctx_path = session_dir / "context.ec"
    if ctx_path.exists():
        context_file = ctx_path
    for f in session_dir.glob("extracted_*.ec"):
        context_file = f
        break

    return suggest_close(goal_text, search_dirs, context_file)
