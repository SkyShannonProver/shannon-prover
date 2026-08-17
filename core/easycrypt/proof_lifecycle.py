"""Canonical lifecycle vocabulary for one managed EasyCrypt proof session.

These values describe session facts.  They deliberately do not describe the
outcome of a whole Shannon prover run: only the run-level prover coordinator
may turn a session-closed candidate into a verified proof result.
"""

from __future__ import annotations


OPEN = "open"
ERROR = "error"
UNKNOWN = "unknown"
NO_CURRENT = "no_current"
CLOSED_UNTRUSTED = "closed_untrusted"
GOALS_DISCHARGED_PENDING_QED = "goals_discharged_pending_qed"
SESSION_CLOSED_PENDING_VERIFICATION = "session_closed_pending_verification"
VERIFIED = "verified"

GOAL_IDENTITY_FREE_STATUSES = frozenset({
    CLOSED_UNTRUSTED,
    GOALS_DISCHARGED_PENDING_QED,
    SESSION_CLOSED_PENDING_VERIFICATION,
    VERIFIED,
})


def allows_qed(status: str) -> bool:
    """Whether the session is at the one state where ``qed.`` is next."""

    return status == GOALS_DISCHARGED_PENDING_QED


def requires_qed_before_finish(status: str) -> bool:
    """Whether an agent finish request would strand a discharged candidate."""

    return status == GOALS_DISCHARGED_PENDING_QED


def is_session_completion_candidate(status: str) -> bool:
    """Whether this session has committed ``qed.`` and may be finalized."""

    return status in {SESSION_CLOSED_PENDING_VERIFICATION, VERIFIED}


def has_discharged_goals(status: str) -> bool:
    """Whether the managed lifecycle has authoritative no-goal evidence."""

    return status in {
        GOALS_DISCHARGED_PENDING_QED,
        SESSION_CLOSED_PENDING_VERIFICATION,
        VERIFIED,
    }


def is_verified(status: str) -> bool:
    """Whether offline verification authority has been recorded."""

    return status == VERIFIED


__all__ = [
    "CLOSED_UNTRUSTED",
    "ERROR",
    "GOALS_DISCHARGED_PENDING_QED",
    "GOAL_IDENTITY_FREE_STATUSES",
    "NO_CURRENT",
    "OPEN",
    "SESSION_CLOSED_PENDING_VERIFICATION",
    "UNKNOWN",
    "VERIFIED",
    "allows_qed",
    "has_discharged_goals",
    "is_session_completion_candidate",
    "is_verified",
    "requires_qed_before_finish",
]
