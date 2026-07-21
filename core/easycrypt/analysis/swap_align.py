#!/usr/bin/env python3
"""Swap alignment tool for pRHL (two-column equiv) goal states.

Parses EasyCrypt's two-column program listing, identifies corresponding
statements between left and right programs, and suggests swap tactics
to align them.

Usage (standalone):
    python3 -m core.easycrypt.swap_align < current.out

Usage (via session_cli):
    python3 core/easycrypt/session_cli.py -d .ec_session -align
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core.easycrypt.analysis.ec_utils import (
    strip_balanced_parens as _strip_balanced_parens,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Statement:
    pos: int              # top-level 1-based position (for swap computation)
    text: str             # full statement text (continuations joined)
    stmt_type: str        # SAMPLE, CALL, ASSIGN, IF, WHILE, RETURN, STRUCTURAL
    distribution: str     # for SAMPLE: "dt", "{0,1}", etc.
    procedure: str        # for CALL: "A.choose", "A.guess", etc.
    vars_written: set = field(default_factory=set)   # variables assigned
    vars_read: set = field(default_factory=set)       # variables referenced
    pos_path: str = ""    # full hierarchical path, e.g. "3.2.1"

    @property
    def depth(self) -> int:
        """Nesting depth: 1 for top-level, 2+ for inside while/if."""
        if not self.pos_path or '.' not in self.pos_path:
            return 1
        return self.pos_path.count('.') + 1


@dataclass
class Match:
    left_pos: int
    right_pos: int
    match_type: str       # "CALL", "SAMPLE"
    label: str            # e.g., "A.choose" or "dt"
    confidence: str       # "high", "medium"


@dataclass
class AlignResult:
    left: list[Statement]
    right: list[Statement]
    matches: list[Match]
    unmatched_left: list[int]
    unmatched_right: list[int]
    swaps: list[str]
    blocked_swaps: list[dict] = field(default_factory=list)
    pre: str = ""
    post: str = ""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _detect_separator_col(lines: list[str]) -> int | None:
    """Find the column position where (N) markers appear.

    Handles various EasyCrypt formats:
    - (N)       standard
    - ( N)      padded
    - ( 1-----)  with dashes (nested/conditional statements)
    - ( 2. 1--) sub-statement numbering
    """
    # Try patterns from most specific to general
    patterns = [
        re.compile(r'\(\s*\d+[-.)]+'),        # ( 1-----) or (1.) or (1-)
        re.compile(r'\(\s*\d+\s*\)'),          # (1) or ( 1)
    ]
    for pat in patterns:
        for line in lines:
            m = pat.search(line)
            if m:
                return m.start()
    return None


def _parse_marker(text: str) -> tuple[int, str] | None:
    """Extract statement number from a marker.

    Handles: '(5)', '( 5)', '( 1-----)', '( 2. 1--)', '( )' (continuation).
    Returns (top_level_pos, full_path) or None for continuations.

    Examples:
      '( 3-----)' → (3, '3')
      '( 3.2.1-)' → (3, '3.2.1')
      '(28.15.1)' → (28, '28.15.1')
      '( 2? 1--)' → (2, '2?1')
      '( )'       → None
    """
    # Remove outer parens and dashes
    inner = text.strip().lstrip('(').rstrip(')')
    inner = inner.strip().rstrip('-').strip()
    if not inner:
        return None
    # Extract full dotted path (digits, dots, spaces around dots, ? for else)
    # First normalize: remove spaces around dots/digits
    normalized = re.sub(r'\s+', '', inner)
    m = re.match(r'([\d.?]+)', normalized)
    if m:
        full_path = m.group(1).rstrip('.')
        top_str = full_path.split('.')[0].replace('?', '')
        if top_str.isdigit():
            return int(top_str), full_path
    return None


# EasyCrypt keywords and constants that are NOT variables
_EC_KEYWORDS = frozenset({
    'if', 'then', 'else', 'true', 'false', 'None', 'Some', 'return',
    'fun', 'let', 'in', 'forall', 'exists', 'oget', 'pred1', 'zero',
    'size', 'g', 'DH', 'DH.G', 'DBool', 'PKE_',
})


def _extract_vars(text: str) -> tuple[set[str], set[str]]:
    """Extract written and read variables from a statement.

    Returns (vars_written, vars_read).
    Heuristic: left of <$/<=/<@ is written, right side identifiers are read.
    For CALL statements, also marks glob as read/written.
    """
    written: set[str] = set()
    read: set[str] = set()

    # Split on the operator
    for op in ['<$', '<@', '<-']:
        if op in text:
            lhs, rhs = text.split(op, 1)
            # Written: extract variable names from LHS
            # Handle tuple assignment: (a, b, c) <- ...
            lhs_clean = lhs.strip().strip('()')
            for v in re.findall(r"[a-zA-Z_][a-zA-Z0-9_'.]*", lhs_clean):
                if v not in _EC_KEYWORDS and not v[0].isupper():
                    written.add(v)
            # Read: extract identifiers from RHS
            for v in re.findall(r"[a-zA-Z_][a-zA-Z0-9_'.]*", rhs):
                if v not in _EC_KEYWORDS and v not in written:
                    read.add(v)
            break
    else:
        # No operator found — entire text is an expression (e.g., return, if)
        for v in re.findall(r"[a-zA-Z_][a-zA-Z0-9_'.]*", text):
            if v not in _EC_KEYWORDS:
                read.add(v)

    return written, read


def _build_dist_aliases(context_file: Path | None) -> dict[str, str]:
    """Build a mapping of distribution aliases from op/clone declarations.

    Parses lines like ``op de = dt.`` and clone-with bodies like
    ``op SigmaProtocol.de = dt`` to build a canonical name map.
    Returns e.g. {"de": "dt", "dt": "dt"}.
    """
    if context_file is None or not context_file.exists():
        return {}
    try:
        text = context_file.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeDecodeError):
        return {}

    aliases: dict[str, str] = {}
    # Match: op [qualified.]name = simple_name.
    for m in re.finditer(
            r'\bop\s+(?:\w+\.)*(\w+)\s*(?:\([^)]*\))?\s*=\s*(\w+)',
            text):
        aliases[m.group(1)] = m.group(2)

    # Transitive closure (one pass is enough for chains of length 2)
    changed = True
    while changed:
        changed = False
        for k, v in list(aliases.items()):
            if v in aliases and aliases[v] != v:
                aliases[k] = aliases[v]
                changed = True

    return aliases


def _classify(text: str) -> tuple[str, str, str]:
    """Classify statement text. Returns (type, distribution, procedure)."""
    text = text.strip()
    distribution = ""
    procedure = ""

    # Structural markers: braces and else blocks
    stripped = text.rstrip()
    if stripped in ('}', '} else {') or stripped.startswith('} else'):
        return 'STRUCTURAL', '', ''

    if '<$' in text:
        stmt_type = 'SAMPLE'
        m = re.search(r'<\$\s*(.+)', text)
        if m:
            distribution = m.group(1).strip().rstrip('.')
    elif '<@' in text:
        stmt_type = 'CALL'
        # Extract full procedure path (skip module arguments in parens).
        # Must handle NESTED parens, e.g.
        # ``CCA(RealOrcls(S), A).A.choose(pk)`` — a flat
        # ``re.sub(r'\([^)]*\)', '', …)`` would leave stray ``)``s.
        m = re.search(r'<@\s*(.+)', text)
        if m:
            procedure = _strip_balanced_parens(m.group(1).strip()).rstrip('.')
    elif text.startswith('if ') or text.startswith('if('):
        stmt_type = 'IF'
    elif text.startswith('while'):
        stmt_type = 'WHILE'
    elif '<-' in text:
        stmt_type = 'ASSIGN'
    else:
        stmt_type = 'ASSIGN'

    return stmt_type, distribution, procedure


def _find_prhl_pre_post(lines: list[str]) -> tuple[int | None, int | None]:
    """Locate the first `pre = ...` line and the FOLLOWING `post = ...` line.

    A single goal chunk can contain multiple pre/post bands when the output
    accidentally concatenates (e.g. the tree prover dumps). We only want the
    first pre and the closest subsequent post so that `program_lines` is the
    body of exactly one goal.
    """
    pre_line: int | None = None
    post_line: int | None = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        is_pre = stripped.startswith('pre =') or stripped.startswith('pre=')
        is_post = stripped.startswith('post =') or stripped.startswith('post=')
        if pre_line is None and is_pre:
            pre_line = i
            continue
        if pre_line is not None and is_post:
            post_line = i
            break
    return pre_line, post_line


def _parse_summary_form(program_lines: list[str]) -> tuple[Statement, Statement] | None:
    """Parse a summary-form pRHL body: ``M1(...).proc1 ~ M2(...).proc2``.

    EC emits this shape before any `proc; inline *` — the body has no
    per-statement markers, just the two procedure expressions joined by
    ` ~ `. Expressions may wrap across lines.

    Returns a (left, right) Statement pair with pos=1, or None if the body
    is not in summary form.
    """
    joined = ' '.join(line.strip() for line in program_lines if line.strip())
    if not joined:
        return None

    # Split on ' ~ ' at paren depth 0. Reject tildes embedded in identifiers.
    depth = 0
    tilde_idx = -1
    for i, c in enumerate(joined):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == '~' and depth == 0:
            prev = joined[i - 1] if i > 0 else ''
            nxt = joined[i + 1] if i + 1 < len(joined) else ''
            if prev.isspace() and nxt.isspace():
                tilde_idx = i
                break
    if tilde_idx < 0:
        return None

    left_expr = joined[:tilde_idx].strip()
    right_expr = joined[tilde_idx + 1:].strip()
    if not left_expr or not right_expr:
        return None

    # Both sides must look like a procedure expression: at least one
    # depth-0 '.' (so `M.proc`) OR a plain identifier. Reject pure
    # formulas that happened to contain ' ~ ' (shouldn't occur in a
    # pRHL body, but guard anyway).
    def _looks_like_proc(e: str) -> bool:
        return bool(re.match(r'^[A-Za-z_]', e))

    if not (_looks_like_proc(left_expr) and _looks_like_proc(right_expr)):
        return None

    left_stmt = Statement(
        pos=1,
        text=left_expr,
        stmt_type='CALL',
        distribution='',
        procedure=left_expr.rstrip('()').rstrip(),
        pos_path='1',
    )
    right_stmt = Statement(
        pos=1,
        text=right_expr,
        stmt_type='CALL',
        distribution='',
        procedure=right_expr.rstrip('()').rstrip(),
        pos_path='1',
    )
    return left_stmt, right_stmt


def parse_prhl_goal(raw_text: str,
                    context_file: Path | None = None) -> AlignResult | None:
    """Parse a pRHL goal state into structured form.

    Handles two shapes:
      * Two-column listing with per-statement markers `(N)` / `( N--)` /
        `(N.M)`, emitted after `proc; inline *`.
      * Summary form `M1(...).proc1 ~ M2(...).proc2` emitted before any
        inline — one statement per side, pos=1, stmt_type='CALL'.

    Returns None only when the text has no pre=/post= band or is a
    non-pRHL judgment (phoare, hoare, ambient, probability).
    """
    lines = raw_text.split('\n')

    pre_line, post_line = _find_prhl_pre_post(lines)
    if pre_line is None or post_line is None:
        return None
    pre_text = lines[pre_line]
    post_text = lines[post_line]

    # ── Multi-line pre/post collection ──
    # EC may wrap a long pre or post over multiple indented lines:
    #     pre =
    #       conj1 /\
    #       conj2 /\
    #       ...
    # The original logic only kept `lines[pre_line]` ("pre =") and dropped
    # the continuation, so downstream gap-analysis tools saw an empty
    # formula. Collect the continuation here and stitch it back into
    # pre_text / post_text.
    pre_value_inline = re.sub(r'^\s*pre\s*=\s*', '', pre_text).strip()
    pre_has_value = bool(pre_value_inline)

    pre_cont: list[str] = []
    if pre_has_value:
        pre_cont.append(pre_value_inline)
    # Continuation lines: from pre_line+1 until first blank line OR another
    # `post =` / `pre =` label. Stop at post_line.
    cont_idx = pre_line + 1
    while cont_idx < post_line:
        s = lines[cont_idx].strip()
        if not s:
            break
        if s.startswith("pre =") or s.startswith("post ="):
            break
        pre_cont.append(s)
        cont_idx += 1
    # Stitched pre formula
    if pre_cont:
        pre_text = "pre = " + " ".join(pre_cont)

    # Same for post: collect continuation lines after post_line until blank
    # line, EC prompt, or end of input.
    post_value_inline = re.sub(r'^\s*post\s*=\s*', '', post_text).strip()
    post_cont: list[str] = []
    if post_value_inline:
        post_cont.append(post_value_inline)
    j = post_line + 1
    _prompt_re = re.compile(r'^\s*\[\d+\|[^\]]+\]>')
    while j < len(lines):
        s = lines[j].strip()
        if not s:
            break
        if _prompt_re.match(lines[j]):
            break
        if s.startswith("pre =") or s.startswith("post ="):
            break
        post_cont.append(s)
        j += 1
    if post_cont:
        post_text = "post = " + " ".join(post_cont)

    # Slice out the band between `pre =` and `post =`. This may also
    # contain pre's continuation lines when the pre expression wraps —
    # those end at the first blank line, and the program body starts
    # after that blank line.
    band = lines[pre_line + 1: post_line]
    # If `pre =` had no value on its own line, skip the continuation
    # (everything up to the next blank line).
    if not pre_has_value:
        # Drop continuation lines until the first blank line.
        while band and band[0].strip():
            band.pop(0)
    program_lines = band
    while program_lines and not program_lines[0].strip():
        program_lines.pop(0)
    while program_lines and not program_lines[-1].strip():
        program_lines.pop()

    if not program_lines:
        # pRHL-residue: program body is empty (e.g. after `move=> /> *`
        # consumed it). Pre/post are still meaningful for downstream
        # gap-analysis tools — return an AlignResult with empty stmt lists
        # rather than None, so callers don't lose access to pre/post.
        return _build_align_result(
            [], [], pre_text, post_text, context_file,
        )

    # Programs-in-sync: EC collapses both sides; no actionable alignment.
    if "[programs are in sync]" in raw_text:
        return _build_align_result(
            [], [], pre_text, post_text, context_file,
        )

    # Reject non-pRHL judgments whose body happens to sit between pre= and
    # post=. phoare/hoare/ambient lack a ' ~ ' separator; reject by shape.
    body_joined = ' '.join(l.strip() for l in program_lines if l.strip())
    if re.search(r'\[\s*(=|<=|>=)\s*\]', body_joined):
        return None  # phoare judgment

    sep_col = _detect_separator_col(program_lines)
    if sep_col is None:
        # No column markers — try summary form (`M1.proc ~ M2.proc`).
        summary = _parse_summary_form(program_lines)
        if summary is None:
            return None
        left_stmts = [summary[0]]
        right_stmts = [summary[1]]
        return _build_align_result(
            left_stmts, right_stmts, pre_text, post_text, context_file,
        )

    # Find marker width by looking at first marker
    # Handles (N), ( N), ( 1-----), ( 2. 1--)
    marker_pat = re.compile(r'\(\s*\d+[\d.\s-]*\)')
    marker_width = 3  # default "(N)"
    for line in program_lines:
        if len(line) > sep_col:
            m = marker_pat.match(line[sep_col:])
            if m:
                marker_width = m.end()
                break

    # Parse each line
    left_stmts: list[Statement] = []
    right_stmts: list[Statement] = []
    current_left_text = ""
    current_right_text = ""
    current_num = 0
    current_path = ""

    def _flush(num: int, path: str, left_text: str, right_text: str):
        """Classify and append the buffered statement to left/right lists."""
        lt, ld, lp = _classify(left_text)
        rt, rd, rp = _classify(right_text)
        if left_text.strip() and lt != 'STRUCTURAL':
            lw, lr = _extract_vars(left_text)
            left_stmts.append(Statement(num, left_text.strip(), lt, ld, lp, lw, lr, pos_path=path))
        if right_text.strip() and rt != 'STRUCTURAL':
            rw, rr = _extract_vars(right_text)
            right_stmts.append(Statement(num, right_text.strip(), rt, rd, rp, rw, rr, pos_path=path))

    for line in program_lines:
        if len(line) <= sep_col:
            # Short line — might be left-only text or empty
            left_text = line.rstrip()
            if current_num > 0 and left_text.strip():
                current_left_text += " " + left_text.strip()
            continue

        left_text = line[:sep_col].rstrip()
        marker_text = line[sep_col:sep_col + marker_width]
        right_text = line[sep_col + marker_width:].rstrip() if len(line) > sep_col + marker_width else ""

        result = _parse_marker(marker_text)

        if result is not None:
            num, path = result
            # New statement — flush previous
            if current_num > 0:
                _flush(current_num, current_path, current_left_text, current_right_text)

            current_num = num
            current_path = path
            current_left_text = left_text
            current_right_text = right_text
        else:
            # Continuation line
            if left_text.strip():
                current_left_text += " " + left_text.strip()
            if right_text.strip():
                current_right_text += " " + right_text.strip()

    # Flush last statement
    if current_num > 0:
        _flush(current_num, current_path, current_left_text, current_right_text)

    if not left_stmts and not right_stmts:
        return None

    return _build_align_result(
        left_stmts, right_stmts, pre_text, post_text, context_file,
    )


def _build_align_result(left_stmts: list[Statement],
                        right_stmts: list[Statement],
                        pre_text: str,
                        post_text: str,
                        context_file: Path | None) -> AlignResult:
    """Compute matches, swaps, and the AlignResult for parsed stmt lists."""
    dist_aliases = _build_dist_aliases(context_file)

    top_left = [s for s in left_stmts if s.depth == 1]
    top_right = [s for s in right_stmts if s.depth == 1]

    matches = match_statements(top_left, top_right, dist_aliases)
    matched_left = {m.left_pos for m in matches}
    matched_right = {m.right_pos for m in matches}
    unmatched_left = [s.pos for s in top_left if s.pos not in matched_left]
    unmatched_right = [s.pos for s in top_right if s.pos not in matched_right]
    swaps, blocked_swaps = compute_swap_plan(top_left, top_right, matches)

    return AlignResult(
        left=left_stmts,
        right=right_stmts,
        matches=matches,
        unmatched_left=unmatched_left,
        unmatched_right=unmatched_right,
        swaps=swaps,
        blocked_swaps=blocked_swaps,
        pre=pre_text,
        post=post_text,
    )


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match_statements(left: list[Statement], right: list[Statement],
                     dist_aliases: dict[str, str] | None = None) -> list[Match]:
    """Match left and right statements by type and content."""
    matches: list[Match] = []
    used_left: set[int] = set()
    used_right: set[int] = set()
    _aliases = dist_aliases or {}

    def _norm_dist(d: str) -> str:
        return _aliases.get(d, d)

    # Priority 1: CALL by procedure name
    for ls in left:
        if ls.stmt_type == 'CALL' and ls.pos not in used_left:
            for rs in right:
                if (rs.stmt_type == 'CALL' and rs.pos not in used_right
                        and _proc_match(ls.procedure, rs.procedure)):
                    matches.append(Match(ls.pos, rs.pos, "CALL", ls.procedure, "high"))
                    used_left.add(ls.pos)
                    used_right.add(rs.pos)
                    break

    # Priority 2: SAMPLE by distribution (with alias normalization)
    # Group unmatched samples by normalized distribution name
    left_samples: dict[str, list[Statement]] = {}
    right_samples: dict[str, list[Statement]] = {}
    for ls in left:
        if ls.stmt_type == 'SAMPLE' and ls.pos not in used_left:
            left_samples.setdefault(_norm_dist(ls.distribution), []).append(ls)
    for rs in right:
        if rs.stmt_type == 'SAMPLE' and rs.pos not in used_right:
            right_samples.setdefault(_norm_dist(rs.distribution), []).append(rs)

    for dist in left_samples:
        if dist in right_samples:
            l_list = left_samples[dist]
            r_list = right_samples[dist]
            # Match in order (positional proximity)
            for ls, rs in zip(l_list, r_list):
                confidence = "high" if len(l_list) == 1 and len(r_list) == 1 else "medium"
                matches.append(Match(ls.pos, rs.pos, "SAMPLE", dist, confidence))
                used_left.add(ls.pos)
                used_right.add(rs.pos)

    # Sort matches by right_pos for consistent output
    matches.sort(key=lambda m: m.right_pos)
    return matches


def _proc_match(p1: str, p2: str) -> bool:
    """Check if two procedure names match (ignoring module wrappers).

    Compares the last two components (e.g., A.choose) since the module
    path prefix can differ (CCA(CramerShoup, A).A.choose vs B_DDH(A).CCA.A.choose).
    """
    def _tail(p: str) -> str:
        parts = p.split('.')
        # Take last 2 parts (e.g., "A.choose") or just the last if only 1
        return '.'.join(parts[-2:]) if len(parts) >= 2 else p
    return _tail(p1) == _tail(p2)


def _has_dependency(stmts: list[Statement], moving_pos: int, target_pos: int) -> str | None:
    """Check if moving a statement from moving_pos to target_pos has a dependency conflict.

    Returns a description of the conflict, or None if independent.
    Checks all statements between the current and target positions.
    Two statements conflict if:
    - One writes a variable the other reads (data dependency)
    - Both write the same variable (output dependency)
    - Either is a CALL (adversary calls read/write glob, creating barriers)
    """
    stmt_map = {s.pos: s for s in stmts}
    moving_stmt = stmt_map.get(moving_pos)
    if not moving_stmt:
        return None

    lo, hi = min(moving_pos, target_pos), max(moving_pos, target_pos)

    for s in stmts:
        # Check all statements between target and current (inclusive of target end)
        if s.pos < lo or s.pos > hi or s.pos == moving_pos:
            continue

        # CALL barrier: adversary calls touch glob A implicitly
        if s.stmt_type == 'CALL' or moving_stmt.stmt_type == 'CALL':
            return f"crosses CALL {s.procedure or moving_stmt.procedure}"

        # Check variable dependencies
        # moving writes, s reads → data dependency
        conflict_vars = moving_stmt.vars_written & s.vars_read
        if conflict_vars:
            return f"writes {conflict_vars} read by stmt {s.pos}"

        # s writes, moving reads → data dependency
        conflict_vars = s.vars_written & moving_stmt.vars_read
        if conflict_vars:
            return f"reads {conflict_vars} written by stmt {s.pos}"

        # both write same var → output dependency
        conflict_vars = moving_stmt.vars_written & s.vars_written
        if conflict_vars:
            return f"both write {conflict_vars}"

    return None


def compute_swap_plan(left: list[Statement], right: list[Statement],
                      matches: list[Match]) -> tuple[list[str], list[dict]]:
    """Compute swap tactics to align left and right programs.

    Strategy:
    1. Try swap{1} (left side) for each misaligned match.
    2. If a swap{1} would cross a CALL barrier, suggest swap{2} instead.
    3. Keep executable static candidates separate from blocked/uncertified
       diagnostics. A static CALL barrier is conservative evidence, not an EC
       rejection and not a proof that the swap is semantically impossible.
    """
    if not matches:
        return [], []

    left_swaps: list[str] = []
    right_swaps: list[str] = []
    blocked: list[dict] = []

    left_pos_map = {s.pos: s for s in left}
    right_pos_map = {s.pos: s for s in right}

    # Sort matches by right position (target order for left side)
    right_idx = {s.pos: i for i, s in enumerate(right)}
    sorted_matches = sorted(matches, key=lambda m: right_idx.get(m.right_pos, 999))

    # Simulate left-side positions
    left_positions = [s.pos for s in left]

    for match in sorted_matches:
        try:
            current_idx = left_positions.index(match.left_pos)
        except ValueError:
            continue

        target_row = match.right_pos
        if target_row < 1:
            target_row = 1
        if target_row > len(left_positions):
            target_row = len(left_positions)

        target_idx = target_row - 1

        if current_idx == target_idx:
            continue

        # Check if this swap has any dependency conflict on left side
        dep_conflict = _has_dependency(left, match.left_pos, target_row)

        stmt = left_pos_map.get(match.left_pos)
        label = ""
        if stmt:
            label = f"{stmt.stmt_type.lower()} {stmt.distribution or stmt.procedure or ''}".strip()

        if not dep_conflict:
            offset = target_idx - current_idx
            ec_pos = current_idx + 1
            left_swaps.append(f"swap{{1}} {ec_pos} {offset}.    (* move {label} to row {target_row} *)")
            # Update simulation
            item = left_positions.pop(current_idx)
            left_positions.insert(target_idx, item)
        else:
            # Suggest swapping on right side instead
            # Compute what right-side swap would achieve the same alignment
            right_positions_sim = [s.pos for s in right]
            try:
                r_current_idx = right_positions_sim.index(match.right_pos)
            except ValueError:
                continue
            r_target_row = match.left_pos
            if r_target_row < 1:
                r_target_row = 1
            if r_target_row > len(right_positions_sim):
                r_target_row = len(right_positions_sim)
            r_target_idx = r_target_row - 1

            if r_current_idx != r_target_idx:
                r_stmt = right_pos_map.get(match.right_pos)
                r_label = ""
                if r_stmt:
                    r_label = f"{r_stmt.stmt_type.lower()} {r_stmt.distribution or r_stmt.procedure or ''}".strip()

                # Check dependency on right side before suggesting swap{2}
                r_dep_conflict = _has_dependency(right, match.right_pos, r_target_row)
                if r_dep_conflict:
                    left_offset = target_idx - current_idx
                    left_ec_pos = current_idx + 1
                    right_offset = r_target_idx - r_current_idx
                    right_ec_pos = r_current_idx + 1
                    blocked.append({
                        "match": {
                            "left_pos": match.left_pos,
                            "right_pos": match.right_pos,
                            "label": match.label,
                            "match_type": match.match_type,
                        },
                        "left_candidate": f"swap{{1}} {left_ec_pos} {left_offset}.",
                        "left_blocker": dep_conflict,
                        "right_candidate": f"swap{{2}} {right_ec_pos} {right_offset}.",
                        "right_blocker": r_dep_conflict,
                        "epistemic_status": "static_blocked_uncertified",
                        "meaning": (
                            "The static dependency scan cannot certify this "
                            "movement without crossing a conservative barrier."
                        ),
                        "not_meaning": (
                            "This is not an EasyCrypt rejection and does not "
                            "prove the swap is semantically impossible."
                        ),
                        "recommended_action": (
                            "Use -try on the candidate tactic if the proof "
                            "strategy needs this movement, or use -swap-search "
                            "for bounded EC-backed search."
                        ),
                    })
                    continue

                r_offset = r_target_idx - r_current_idx
                r_ec_pos = r_current_idx + 1
                right_swaps.append(
                    f"swap{{2}} {r_ec_pos} {r_offset}.    "
                    f"(* move {r_label} to row {r_target_row} — "
                    f"swap{{1}} blocked: {dep_conflict} *)")

    return left_swaps + right_swaps, blocked


# ---------------------------------------------------------------------------
# wp simulation
# ---------------------------------------------------------------------------

def count_trailing_assigns(stmts: list[Statement]) -> int:
    """Count how many statements wp would consume from the end (trailing ASSIGNs)."""
    count = 0
    for s in reversed(stmts):
        if s.stmt_type == 'ASSIGN':
            count += 1
        else:
            break
    return count


def apply_swap(stmts: list[Statement], ec_pos: int, offset: int) -> list[Statement]:
    """Apply swap ec_pos offset to a statement list (1-based position).

    Moves the statement at ec_pos (1-based) by 'offset' positions.
    Positive offset = move forward (down); negative = move backward (up).
    """
    result = list(stmts)
    current_idx = ec_pos - 1  # convert to 0-based
    target_idx = current_idx + offset
    target_idx = max(0, min(len(result) - 1, target_idx))
    if current_idx == target_idx:
        return result
    item = result.pop(current_idx)
    result.insert(target_idx, item)
    return result


def parse_swap_tactic(swap_str: str) -> tuple[int, int, int] | None:
    """Parse 'swap{N} pos offset.' → (side, pos, offset). Returns None if unparseable."""
    m = re.search(r'swap\{(\d)\}\s+(\d+)\s+(-?\d+)', swap_str)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def simulate_wp_after_swaps(
    left: list[Statement],
    right: list[Statement],
    swaps: list[str],
) -> tuple[list[Statement], list[Statement], int, int]:
    """Simulate applying suggested swaps then wp on both sides.

    Returns (remaining_left, remaining_right, left_consumed, right_consumed).
    """
    sim_left = list(left)
    sim_right = list(right)

    for swap_str in swaps:
        parsed = parse_swap_tactic(swap_str)
        if parsed is None:
            continue
        side, pos, offset = parsed
        if side == 1:
            sim_left = apply_swap(sim_left, pos, offset)
        else:
            sim_right = apply_swap(sim_right, pos, offset)

    left_consumed = count_trailing_assigns(sim_left)
    right_consumed = count_trailing_assigns(sim_right)

    remaining_left = sim_left[: len(sim_left) - left_consumed] if left_consumed else sim_left
    remaining_right = sim_right[: len(sim_right) - right_consumed] if right_consumed else sim_right

    return remaining_left, remaining_right, left_consumed, right_consumed


def _fmt_stmt_short(s: Statement, idx: int) -> str:
    tag = s.distribution or s.procedure or s.stmt_type
    text = s.text[:45] + "…" if len(s.text) > 46 else s.text
    return f"  {idx+1:2d}: {text:<47s} [{tag}]"


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_analysis(result: AlignResult) -> str:
    """Format the alignment analysis as human/agent-readable text."""
    lines: list[str] = []
    lines.append("=== pRHL Swap Alignment ===")
    lines.append("")

    def _fmt_stmts(stmts: list[Statement]) -> list[str]:
        top_level = [s for s in stmts if s.depth == 1]
        nested = [s for s in stmts if s.depth > 1]
        out = []
        for s in top_level:
            tag = s.stmt_type
            if s.distribution:
                tag += f" {s.distribution}"
            if s.procedure:
                tag += f" {s.procedure}"
            out.append(f"  {s.pos:2d}: {s.text:<50s} [{tag}]")
            # Show nested children indented
            for ns in nested:
                if ns.pos == s.pos:
                    ntag = ns.stmt_type
                    if ns.distribution:
                        ntag += f" {ns.distribution}"
                    out.append(f"       {ns.pos_path}: {ns.text:<44s} [{ntag}]")
        return out

    # Left program
    top_left_count = sum(1 for s in result.left if s.depth == 1)
    lines.append(f"LEFT ({top_left_count} top-level stmts, {len(result.left)} total):")
    lines.extend(_fmt_stmts(result.left))
    lines.append("")

    # Right program
    top_right_count = sum(1 for s in result.right if s.depth == 1)
    lines.append(f"RIGHT ({top_right_count} top-level stmts, {len(result.right)} total):")
    lines.extend(_fmt_stmts(result.right))

    # Warn if programs are large (likely from inline * instead of selective inline)
    total_stmts = len(result.left) + len(result.right)
    if total_stmts > 20:
        lines.append("")
        lines.append(f"NOTE: Large program alignment ({total_stmts} total statements).")
        lines.append("If this resulted from `inline *`, consider undoing and using selective")
        lines.append("inline (e.g., `inline LRO.o`) to keep programs smaller and more manageable.")
    lines.append("")

    # Matches
    lines.append("MATCHES:")
    for m in result.matches:
        aligned = "aligned" if m.left_pos == m.right_pos else f"L{m.left_pos} != R{m.right_pos}"
        symbol = "=" if m.left_pos == m.right_pos else "!"
        lines.append(f"  L{m.left_pos:2d} <-> R{m.right_pos:2d}  {m.match_type:<8s} {m.label:<16s} [{m.confidence}] {symbol} {aligned}")

    if result.unmatched_left:
        labels = ", ".join(f"L{p}" for p in result.unmatched_left)
        lines.append(f"  Unmatched left:  {labels}  (deterministic, handled by wp/auto)")
    if result.unmatched_right:
        labels = ", ".join(f"R{p}" for p in result.unmatched_right)
        lines.append(f"  Unmatched right: {labels}  (deterministic, handled by wp/auto)")
    lines.append("")

    # Swaps
    if result.swaps:
        lines.append("STATICALLY CERTIFIED SWAP FRAMES:")
        lines.append("  epistemic_status: static_candidate_uncertified_by_ec")
        lines.append("  meaning: static read/write scan found a source statement usable for realignment.")
        lines.append("  not_meaning: the signed offset is NOT unique and NOT a proof-route decision.")
        lines.append("  recommended_action: choose the offset that lands the next sample/rnd target;")
        lines.append("  then check that concrete swap against the current alignment.")
        for swap in result.swaps:
            lines.append(f"  {swap}")
        lines.append("")
        # Check for if/while blocks that may cause position mismatches
        has_control_flow = any(s.stmt_type in ('IF', 'WHILE') for s in result.left + result.right)
        lines.append("NOTE: This is a static alignment tool. It detects CALL barriers and")
        lines.append("variable read/write conflicts conservatively; it does not know the route's")
        lines.append("next coupling target, and many offsets may be EasyCrypt-valid.")
        if has_control_flow:
            lines.append("WARNING: Program has if/while blocks. EasyCrypt's internal statement")
            lines.append("numbering may differ from this tool's. Verify swap positions interactively.")
        lines.append("If a filled swap is unhelpful, choose a different offset or consume more")
        lines.append("statements with wp/auto/call/rcondt/rcondf before realigning.")
    elif result.blocked_swaps:
        lines.append("NO STATICALLY CERTIFIED SWAPS.")
        lines.append("This does NOT mean no swap can work. It only means the conservative")
        lines.append("static read/write scan could not certify a safe movement.")
    else:
        lines.append("NO SWAPS NEEDED: matched statements are already aligned.")

    lines.append("")

    if result.blocked_swaps:
        lines.append("STATICALLY BLOCKED / UNCERTIFIED CANDIDATES:")
        lines.append("  epistemic_status: static_blocked_uncertified")
        lines.append("  meaning: the analyzer found a conservative barrier.")
        lines.append("  not_meaning: this is NOT an EasyCrypt rejection and NOT a proof")
        lines.append("  that the candidate is semantically impossible.")
        lines.append("  recommended_action: if the proof strategy needs one of these")
        lines.append("  moves, run -try on the candidate tactic or use -swap-search.")
        for item in result.blocked_swaps:
            match = item.get("match", {})
            label = match.get("label", "?")
            lpos = match.get("left_pos", "?")
            rpos = match.get("right_pos", "?")
            lines.append(f"  L{lpos} <-> R{rpos} {label}:")
            lines.append(f"    candidate: {item.get('left_candidate', '')}   blocked_by: {item.get('left_blocker', '')}")
            lines.append(f"    candidate: {item.get('right_candidate', '')}   blocked_by: {item.get('right_blocker', '')}")
        lines.append("")

    # wp simulation section
    rem_left, rem_right, lc, rc = simulate_wp_after_swaps(result.left, result.right, result.swaps)
    if lc > 0 or rc > 0:
        lines.append("WP SIMULATION (after suggested swaps + wp):")
        lines.append(f"  wp consumes: {lc} trailing assigns on left, {rc} on right")
        lines.append(f"  Left reduces to {len(rem_left)} stmts:")
        for i, s in enumerate(rem_left):
            lines.append(_fmt_stmt_short(s, i))
        lines.append(f"  Right reduces to {len(rem_right)} stmts:")
        for i, s in enumerate(rem_right):
            lines.append(_fmt_stmt_short(s, i))
        # Flag any SAMPLE pairs that are out of order in the remaining programs
        # (these need bijection coupling, processed from the END)
        rem_samples_left = [s for s in rem_left if s.stmt_type == 'SAMPLE']
        rem_samples_right = [s for s in rem_right if s.stmt_type == 'SAMPLE']
        if rem_samples_left or rem_samples_right:
            lines.append("")
            lines.append("  COUPLING ORDER: process sampling pairs from the END of remaining programs.")
            lines.append("  Last sampling pair to handle first:")
            if rem_samples_left:
                last_l = rem_samples_left[-1]
                lines.append(f"    Left  last SAMPLE: pos {rem_left.index(last_l)+1}: {last_l.text[:50]}")
            if rem_samples_right:
                last_r = rem_samples_right[-1]
                lines.append(f"    Right last SAMPLE: pos {rem_right.index(last_r)+1}: {last_r.text[:50]}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def analyze_and_suggest(raw_text: str, context_file: 'Path | None' = None) -> str:
    """Parse a goal state and return formatted alignment analysis."""
    if "[programs are in sync]" in raw_text:
        return ("Programs are in sync — both sides have identical code.\n"
                "No swap alignment needed. Tactics like `wp`, `auto`, `sim`,\n"
                "or `while (invariant)` can proceed directly.\n")
    result = parse_prhl_goal(raw_text, context_file=context_file)
    if result is None:
        return "No two-column pRHL program found in goal state.\n(This tool only works after proc; inline * in a byequiv goal.)\n"
    return format_analysis(result)


def main():
    """Read goal state from stdin or file argument."""
    if len(sys.argv) > 1:
        text = open(sys.argv[1]).read()
    else:
        text = sys.stdin.read()
    print(analyze_and_suggest(text))


if __name__ == "__main__":
    main()
