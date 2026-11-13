"""No-progress detection for EasyCrypt commits.

Extracted from ``session_runtime.Session`` (#1 of the Session decomposition): the
SINGLE SOURCE OF TRUTH for "did this tactic produce observable progress?", shared
by the commit path (`Session.append_block`) and exact speculative preflight.
Without sharing, preflight can say "accepted" while a subsequent commit of the
same tactic auto-reverts as no-effect
(step3 Run 9 Tree-0.0 incident, see ``detect_no_progress``).

Pure goal-text analysis: no EC execution, no file I/O, no ``Session`` state — only
the goal-text readers of ``session_state``.
"""
from __future__ import annotations

from core.easycrypt.session.session_state import extract_goal_body, infer_goal_count


def _extract_goal_body(text: str) -> str:
    """The active goal body with prompt markers removed, for comparison."""
    return extract_goal_body(text).strip()


def _structural_fingerprint(text: str) -> tuple[str, ...] | None:
    """Normalize the complete printed active goal without semantic parsing.

    No-progress detection is a runtime safety check, not a proof-analysis
    feature.  It therefore compares every visible hypothesis, program line,
    and conclusion while discarding only prompt counters and whitespace.
    Native/compiler semantics never flow through this fingerprint.
    """

    body = _extract_goal_body(text)
    if not body:
        return None
    normalized = tuple(
        " ".join(line.split())
        for line in body.splitlines()
        if line.strip()
    )
    return normalized or None


def detect_no_progress(
    prev_raw: str, curr_raw: str, has_new_error: bool
) -> tuple[bool, str]:
    """Detect whether a tactic produced no observable progress.

    Returns ``(is_no_progress, reason)`` where ``reason`` names the
    check that fired ("text-equal", "structural-fingerprint-equal") or
    is empty when no-progress was not detected.

    SHARED LOGIC between commit-time auto-revert (``append_block``) and
    speculative-time prediction. Without sharing, preflight can say
    "accepted: True" while a subsequent commit of the same tactic gets
    immediately auto-reverted as
    no-effect. Agent burns time committing a tactic that never sticks
    and may even restart the session blaming "accumulated state". Bug
    observed in step3 Run 9 Tree-0.0: ``inline EncRnd.enc.`` was a true
    no-op (procedure didn't exist at that program point), but ``-try``
    reported it accepted, and repeated commits were reverted,
    each commit auto-reverted, agent eventually restarted the session
    and got progress-gap killed.
    """
    if has_new_error:
        return False, ""
    # A context-splitting / hypothesis-adding tactic (`case (cond)`, `if`,
    # `split`, `elim`) increases the number of OPEN GOALS while leaving the
    # printed FIRST-goal program/conclusion text unchanged. The text-equal and
    # structural-fingerprint checks below see only the first goal's body, so
    # such a tactic was falsely flagged NO-PROGRESS and auto-reverted (observed
    # on equiv_step4 Tree_0_1 ~T114: a `case (… \in ROout.m{1})` reverted). A
    # genuine increase in the open-goal count IS progress: short-circuit before
    # the body/fingerprint equality checks. We use EC's own `(remaining: N)`
    # count via `infer_goal_count`, the same parser the commit path uses, so a
    # truly idempotent tactic (`sp` with no effect — count unchanged) is still
    # flagged. Best-effort: if counts can't be inferred, fall through unchanged.
    try:
        _prev_n, _ = infer_goal_count(prev_raw)
        _curr_n, _ = infer_goal_count(curr_raw)
    except Exception:
        _prev_n, _curr_n = -1, -1
    # Only trust a strict increase between two successfully-parsed,
    # non-sentinel counts. (-1 means parse failed / not in a proof.)
    if _prev_n >= 0 and _curr_n >= 0 and _curr_n > _prev_n:
        return False, ""
    # Cheap text-equality check first
    prev_goal = _extract_goal_body(prev_raw)
    curr_goal = _extract_goal_body(curr_raw)
    if prev_goal and curr_goal and prev_goal == curr_goal:
        return True, "text-equal"
    # Structural fingerprint: catches cosmetic differences (whitespace,
    # residual hypotheses) that hide a semantically-identical state.
    # Defense-in-depth — only fires when both parses succeed AND both
    # have non-trivial content (avoids false positives on ambient/
    # smt-closed intermediate states).
    prev_fp = _structural_fingerprint(prev_raw)
    curr_fp = _structural_fingerprint(curr_raw)
    nontrivial = bool(prev_fp and curr_fp)
    if nontrivial and prev_fp == curr_fp:
        return True, "structural-fingerprint-equal"
    return False, ""
