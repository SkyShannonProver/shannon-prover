"""Asymmetric pRHL `seq` hint generator.

When a pRHL goal has unequal statement counts on the two sides, a useful
decomposition family is

    seq <N> <M> : <invariant>.

which splits a pair of prefixes under an explicit invariant tying the local
state of both sides.  There is usually not a single universally-canonical
split point: the right split may be the full visible prefix, the first aligned
call boundary, a boundary before control flow, or the first sample/call
coupling point.  This module therefore emits a small set of structured split
candidates and lets the dispatcher/daemon/cost model decide which one is
currently viable.

Status quo without this generator: AUTO-DIFF produces ``seq N M (<inv>)``
as a strategy_hint with placeholder ``<inv>``. The agent reads that template,
has no idea which equalities to put in ``<inv>``, and may try ad-hoc shapes
that do not carry the right state.

This module synthesizes a CONCRETE first-cut invariant from
``swap_align.AlignResult.matches`` — the variables written by
column-matched statements give equality clauses (``={var}`` when both
sides share a name, ``var_l{1} = var_r{2}`` when names diverge). The
synthesized invariant covers only "things swap_align already saw";
deeper clauses (call-invariant carry-over, internal dataflow) need
higher-level reasoning and are deliberately left for the agent to
extend. Even a partial invariant gives the agent a concrete starting
point instead of a ``<inv>`` placeholder.

The generated tactic string is then daemon-probed by the dispatch
layer. Daemon-accepted candidates surface as ``runnable_tactic`` in
the typed bucket; rejections surface as ``strategy_hint`` so the
agent at least sees the concrete shape and can extend it manually.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional

from core.easycrypt.analysis.ec_utils import (
    dedupe_stripped_strings as _dedupe_strings,
    is_emit_safe_var as _is_emit_safe_var,
    is_live_safe_var as _is_live_safe_var,
)


@dataclass(frozen=True)
class AsymSeqProposal:
    """A single synthesized ``seq N M : <inv>.`` candidate.

    ``invariant`` is just the predicate body (no enclosing parens) so
    callers can wrap it in extra parens or augment it.
    """
    left_n: int
    right_m: int
    invariant: str
    matched_pair_count: int
    """Number of column-matches that contributed clauses; 0 means the
    synthesized invariant is just ``true`` (the agent will need to
    extend it themselves)."""
    origin: str = "full_prefix_alignment"
    """Why this split point was selected, e.g. ``full_prefix_alignment`` or
    ``first_call_boundary``."""
    confidence: str = "medium"
    rationale: str = ""
    preserved_vars: tuple[str, ...] = field(default_factory=tuple)
    live_post_vars: tuple[str, ...] = field(default_factory=tuple)
    prefix_read_vars: tuple[str, ...] = field(default_factory=tuple)
    missing_live_post_vars: tuple[str, ...] = field(default_factory=tuple)
    missing_prefix_read_vars: tuple[str, ...] = field(default_factory=tuple)
    coverage: str = "unknown"

    def to_tactic(self) -> str:
        return f"seq {self.left_n} {self.right_m} : ({self.invariant})."

    def coverage_note(self) -> str:
        """Short neutral note for prover-facing surfaces."""
        pieces: list[str] = []
        if self.preserved_vars:
            pieces.append("preserves " + ", ".join(self.preserved_vars[:6]))
        if self.missing_live_post_vars:
            pieces.append(
                "post-live not in cut: "
                + ", ".join(self.missing_live_post_vars[:6])
            )
        if self.missing_prefix_read_vars:
            pieces.append(
                "prefix reads not carried: "
                + ", ".join(self.missing_prefix_read_vars[:6])
            )
        return "; ".join(pieces)


def synthesize_invariants(align_result) -> list[AsymSeqProposal]:
    """Build candidate ``seq N M : <inv>`` proposals from a ``swap_align``
    result.

    Returns ``[]`` when the goal is symmetric or no usable column matches
    support invariant synthesis.  The first proposal preserves the old
    full-prefix behavior, while later proposals represent local structural
    boundaries such as aligned calls, samples, or control-flow frontiers.

    The invariant joins clauses of two kinds derived from
    column-matched statements:
      * ``={var}`` when both matched statements write the same
        variable name on each side (the common case for inlined
        oracles);
      * ``var_l{1} = var_r{2}`` when matched statements write
        differently-named locals (e.g. ``c0{1} = c{2}`` when the LHS
        oracle parameter has been renamed during inlining).
    """
    left = list(getattr(align_result, "left", None) or [])
    right = list(getattr(align_result, "right", None) or [])
    matches = list(getattr(align_result, "matches", None) or [])
    if not left or not right or len(left) == len(right):
        return []
    if not matches:
        return []

    by_left = {s.pos: s for s in left}
    by_right = {s.pos: s for s in right}
    candidates: list[tuple[int, int, str, str, str]] = [
        (
            len(left),
            len(right),
            "full_prefix_alignment",
            "medium",
            "split the whole asymmetric visible prefix",
        ),
    ]

    first_call = _first_match_of_type(matches, by_left, by_right, "CALL")
    if first_call is not None:
        candidates.append((
            getattr(first_call, "left_pos", 0),
            getattr(first_call, "right_pos", 0),
            "first_call_boundary",
            "medium",
            "split at the first aligned call boundary",
        ))
    first_sample = _first_match_of_type(matches, by_left, by_right, "SAMPLE")
    if first_sample is not None:
        candidates.append((
            getattr(first_sample, "left_pos", 0),
            getattr(first_sample, "right_pos", 0),
            "first_sample_boundary",
            "medium",
            "split at the first aligned sampling boundary",
        ))
    first_contributing = _first_contributing_match(matches, by_left, by_right)
    if first_contributing is not None:
        candidates.append((
            getattr(first_contributing, "left_pos", 0),
            getattr(first_contributing, "right_pos", 0),
            "minimal_matched_prefix",
            "low",
            "split at the first matched statement that contributes state",
        ))
    control = _control_prefix_boundary(left, right, matches)
    if control is not None:
        left_n, right_m = control
        candidates.append((
            left_n,
            right_m,
            "pre_control_boundary",
            "low",
            "split before the first branch/loop frontier",
        ))

    proposals: list[AsymSeqProposal] = []
    seen: set[tuple[int, int, str]] = set()
    live_post_vars = _live_vars_from_text(
        str(getattr(align_result, "post", "") or "")
    )
    for left_n, right_m, origin, confidence, rationale in candidates:
        proposal = _proposal_for_prefix(
            left_n,
            right_m,
            matches,
            by_left,
            by_right,
            left,
            right,
            live_post_vars=live_post_vars,
            origin=origin,
            confidence=confidence,
            rationale=rationale,
        )
        if proposal is None:
            continue
        key = (proposal.left_n, proposal.right_m, proposal.invariant)
        if key in seen:
            continue
        seen.add(key)
        proposals.append(proposal)
    return proposals


def _proposal_for_prefix(
    left_n: int,
    right_m: int,
    matches: list,
    by_left: dict,
    by_right: dict,
    left: list,
    right: list,
    live_post_vars: tuple[str, ...],
    *,
    origin: str,
    confidence: str,
    rationale: str,
) -> AsymSeqProposal | None:
    if left_n <= 0 or right_m <= 0:
        return None

    eq_vars: set[str] = set()
    preserved_vars: set[str] = set()
    asym_clauses: list[str] = []
    contributing = 0
    seen_clauses: set[str] = set()

    for m in matches:
        if getattr(m, "left_pos", 0) > left_n or getattr(m, "right_pos", 0) > right_m:
            continue
        ls = by_left.get(getattr(m, "left_pos", None))
        rs = by_right.get(getattr(m, "right_pos", None))
        if ls is None or rs is None:
            continue
        l_writes = set(getattr(ls, "vars_written", None) or [])
        r_writes = set(getattr(rs, "vars_written", None) or [])
        if not l_writes or not r_writes:
            continue
        contributing += 1
        # Same-name matches: merge into ``={var, var, ...}`` clause.
        for v in l_writes & r_writes:
            if _is_emit_safe_var(v):
                eq_vars.add(v)
                preserved_vars.add(v)
        # Cross-name matches: pair up by stable order so the synthesized
        # clause is deterministic across runs (alphabetic).
        only_left = sorted(v for v in (l_writes - r_writes) if _is_emit_safe_var(v))
        only_right = sorted(v for v in (r_writes - l_writes) if _is_emit_safe_var(v))
        for vl, vr in zip(only_left, only_right):
            clause = f"{vl}{{1}} = {vr}{{2}}"
            if clause not in seen_clauses:
                seen_clauses.add(clause)
                asym_clauses.append(clause)
                preserved_vars.add(vl)
                preserved_vars.add(vr)

    pieces: list[str] = []
    if eq_vars:
        pieces.append("={" + ", ".join(sorted(eq_vars)) + "}")
    pieces.extend(asym_clauses)
    # No synthesized clauses → degrade to silence rather than emit a
    # useless ``seq N M : (true).`` candidate. The agent gets nothing
    # actionable from a tautology invariant; better to leave the slot
    # empty and let other generators / AUTO-DIFF fill in.
    if not pieces:
        return None
    invariant = " /\\ ".join(pieces)
    prefix_read_vars = _prefix_read_vars(left, right, left_n, right_m)
    missing_live_post_vars = tuple(
        var for var in live_post_vars
        if var not in preserved_vars
    )
    missing_prefix_read_vars = tuple(
        var for var in prefix_read_vars
        if var not in preserved_vars
    )
    coverage = _coverage_label(
        live_post_vars=live_post_vars,
        prefix_read_vars=prefix_read_vars,
        preserved_vars=tuple(sorted(preserved_vars)),
    )
    return AsymSeqProposal(
        left_n=left_n,
        right_m=right_m,
        invariant=invariant,
        matched_pair_count=contributing,
        origin=origin,
        confidence=confidence,
        rationale=rationale,
        preserved_vars=tuple(sorted(preserved_vars)),
        live_post_vars=live_post_vars,
        prefix_read_vars=prefix_read_vars,
        missing_live_post_vars=missing_live_post_vars,
        missing_prefix_read_vars=missing_prefix_read_vars,
        coverage=coverage,
    )


def _first_contributing_match(matches: list, by_left: dict, by_right: dict):
    for m in sorted(
        matches,
        key=lambda item: (getattr(item, "left_pos", 0), getattr(item, "right_pos", 0)),
    ):
        ls = by_left.get(getattr(m, "left_pos", None))
        rs = by_right.get(getattr(m, "right_pos", None))
        if ls is None or rs is None:
            continue
        l_writes = set(getattr(ls, "vars_written", None) or [])
        r_writes = set(getattr(rs, "vars_written", None) or [])
        if l_writes and r_writes:
            return m
    return None


def _prefix_read_vars(left: list, right: list, left_n: int, right_m: int) -> tuple[str, ...]:
    vars_out: list[str] = []
    for stmts, limit in ((left, left_n), (right, right_m)):
        for stmt in stmts:
            if getattr(stmt, "pos", 0) > limit:
                continue
            for name in getattr(stmt, "vars_read", None) or []:
                if _is_live_safe_var(str(name)):
                    vars_out.append(str(name))
    return tuple(_dedupe_strings(vars_out))


def _live_vars_from_text(text: str) -> tuple[str, ...]:
    raw = str(text or "")
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_'.]*\b", raw)
    out: list[str] = []
    skip = {
        "pre", "post", "true", "false", "forall", "exists", "fun", "let",
        "in", "res", "glob", "size", "nth", "map", "cat", "filter",
        "witness", "if", "then", "else",
    }
    for token in tokens:
        if token in skip:
            continue
        if _is_live_safe_var(token):
            out.append(token)
    return tuple(_dedupe_strings(out)[:24])


def _coverage_label(
    *,
    live_post_vars: tuple[str, ...],
    prefix_read_vars: tuple[str, ...],
    preserved_vars: tuple[str, ...],
) -> str:
    required = set(live_post_vars) | set(prefix_read_vars)
    if not required:
        return "no_visible_live_vars"
    preserved = set(preserved_vars)
    missing = required - preserved
    if not missing:
        return "covers_visible_live_vars"
    if preserved & required:
        return "partial_visible_live_coverage"
    return "weak_visible_live_coverage"


def _first_match_of_type(matches: list, by_left: dict, by_right: dict, stmt_type: str):
    wanted = str(stmt_type or "").upper()
    for m in sorted(
        matches,
        key=lambda item: (getattr(item, "left_pos", 0), getattr(item, "right_pos", 0)),
    ):
        ls = by_left.get(getattr(m, "left_pos", None))
        rs = by_right.get(getattr(m, "right_pos", None))
        if ls is None or rs is None:
            continue
        if str(getattr(ls, "stmt_type", "")).upper() == wanted and str(
            getattr(rs, "stmt_type", "")
        ).upper() == wanted:
            return m
    return None


def _control_prefix_boundary(left: list, right: list, matches: list) -> tuple[int, int] | None:
    left_pos = _first_control_pos(left)
    right_pos = _first_control_pos(right)
    if left_pos is None and right_pos is None:
        return None
    if left_pos is not None and right_pos is not None:
        return max(1, left_pos - 1), max(1, right_pos - 1)
    if left_pos is not None:
        before = [
            m for m in matches
            if getattr(m, "left_pos", 0) < left_pos and getattr(m, "right_pos", 0) > 0
        ]
        if before:
            return max(1, left_pos - 1), max(getattr(m, "right_pos", 0) for m in before)
    if right_pos is not None:
        before = [
            m for m in matches
            if getattr(m, "right_pos", 0) < right_pos and getattr(m, "left_pos", 0) > 0
        ]
        if before:
            return max(getattr(m, "left_pos", 0) for m in before), max(1, right_pos - 1)
    return None


def _first_control_pos(stmts: list) -> int | None:
    for stmt in sorted(stmts, key=lambda item: getattr(item, "pos", 0)):
        if str(getattr(stmt, "stmt_type", "")).upper() in {"IF", "WHILE"}:
            return getattr(stmt, "pos", None)
    return None


def detect_and_propose(
    goal_text: str, context_file=None,
) -> Optional[AsymSeqProposal]:
    """End-to-end helper returning the preferred asymmetric ``seq`` shape.

    Returns ``None`` if parsing fails, the goal is symmetric, or the
    matches are too sparse to support any clause synthesis.
    """
    proposals = detect_and_propose_all(goal_text, context_file=context_file)
    return proposals[0] if proposals else None


def detect_and_propose_all(
    goal_text: str, context_file=None,
) -> list[AsymSeqProposal]:
    """Parse the pRHL goal and return all asymmetric ``seq`` candidates."""
    try:
        from core.easycrypt.analysis.swap_align import parse_prhl_goal  # type: ignore
    except Exception:
        try:
            from core.easycrypt.analysis.swap_align import (  # type: ignore
                parse_prhl_goal,
            )
        except Exception:
            return []
    try:
        result = parse_prhl_goal(goal_text, context_file=context_file)
    except Exception:
        return []
    if result is None:
        return []
    return synthesize_invariants(result)
