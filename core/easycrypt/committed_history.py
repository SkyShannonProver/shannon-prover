"""Single reader for a session's committed proof history (``history.ec``).

Seven call sites across workflow/ used to hand-roll this pair (audit
backlog #19): path minting (``session_dir / "history.ec"``), tactic-line
parsing, and qed-detection each re-derived per site. This module is the
one owner; the historical entry points (``proof_node_runtime.
closed_history_tactics``, ``repl_session.read_committed_tactics``) delegate
here under their old names.

Leaf module: stdlib only.
"""
from __future__ import annotations

from pathlib import Path


def history_path(session_dir: str | Path) -> Path:
    return Path(session_dir) / "history.ec"


def read_committed_tactics(session_dir: str | Path) -> list[str]:
    """All committed tactic lines (stripped, blanks dropped); [] if unreadable."""
    try:
        lines = history_path(session_dir).read_text(encoding="utf-8").splitlines()
    except Exception:
        # Superset of the retired per-site readers (OSError / bare Exception):
        # unreadable or undecodable history means "no committed tactics".
        return []
    return [line.strip() for line in lines if line.strip()]


def closed_history_tactics(session_dir: str | Path) -> list[str]:
    """The committed tactics IFF the proof is closed (a standalone ``qed``
    line exists), else []. Reporting/write-back paths use this so an
    unfinished history is never mistaken for a proof."""
    tactics = read_committed_tactics(session_dir)
    if any(ln.lower().rstrip(".").strip() == "qed" for ln in tactics):
        return tactics
    return []
