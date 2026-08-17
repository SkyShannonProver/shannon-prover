"""Single reader for a session's committed proof history (``history.ec``).

Seven call sites across workflow/ used to hand-roll this pair (audit
backlog #19): path minting (``session_dir / "history.ec"``), tactic-line
parsing, and qed-detection each re-derived per site. This module is now the
only owner of committed-history reading and closure detection — both the
physical-line reading (``read_committed_tactics``) and the sentence-split
command reading (``read_committed_commands``).

Leaf module: stdlib-only at import time (the command splitter is
late-bound from ``ec_daemon``).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# Sentence-final ``qed.`` token at the end of a committed line. A proof can
# close via a compound step that packs the last tactic and the save command
# into one commit — e.g. ``by move=> &hr _. qed.`` (pr_sample_double,
# 2026-07-15) — so closure detection cannot require a standalone ``qed``
# line. The lookbehind rejects identifier tails such as ``my_qed.`` (EC
# identifiers may contain ``_`` and ``'``).
_TRAILING_QED = re.compile(r"(?i)(?<![a-z0-9_'])qed\s*\.\s*$")


def committed_prefix_identity(tactics: list[str] | tuple[str, ...]) -> str:
    """Canonical SHA-256 identity used by manager and compiler input."""

    encoded = json.dumps(
        list(tactics),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def history_path(session_dir: str | Path) -> Path:
    return Path(session_dir) / "history.ec"


def _is_standalone_qed(line: str) -> bool:
    return line.lower().rstrip(".").strip() == "qed"


def split_trailing_qed(tactics: list[str]) -> list[str]:
    """Normalize a compound closer ``TAC. qed.`` into ``[..., "TAC.", "qed."]``.

    EasyCrypt processes sentences one at a time, so the split list replays
    identically to the compound line. No-op when the last entry is already a
    standalone ``qed`` or carries no trailing ``qed.``.
    """
    if not tactics:
        return tactics
    last = tactics[-1]
    if _is_standalone_qed(last):
        return tactics
    m = _TRAILING_QED.search(last)
    if m is None:
        return tactics
    head = last[:m.start()].rstrip()
    out = tactics[:-1]
    if head:
        out.append(head)
    out.append("qed.")
    return out


def read_committed_tactics(session_dir: str | Path) -> list[str]:
    """All committed tactic lines (stripped, blanks dropped); [] if unreadable."""
    try:
        lines = history_path(session_dir).read_text(encoding="utf-8").splitlines()
    except Exception:
        # Superset of the retired per-site readers (OSError / bare Exception):
        # unreadable or undecodable history means "no committed tactics".
        return []
    return [line.strip() for line in lines if line.strip()]


def read_committed_commands(session_dir: str | Path) -> list[str]:
    """Committed history as ``.``-terminated EasyCrypt commands, not lines.

    A committed physical line can pack several sentences (``wp; skip. qed.``
    is two commands); consumers that reason about command counts or per-
    command shape need the sentence split, not the line split. Falls back to
    the line reading when the splitter is unavailable; [] if unreadable.
    """
    path = history_path(session_dir)
    try:
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    try:
        from core.easycrypt.ec_daemon import _split_ec_commands
        return [c.strip() for c in _split_ec_commands(text) if c.strip()]
    except Exception:
        return [line.strip() for line in text.splitlines() if line.strip()]


def committed_history_has_qed(session_dir: str | Path) -> bool:
    """Whether committed history contains a terminal ``qed`` command.

    This module is the sole owner of history closure syntax, including compound
    final lines such as ``TAC. qed.``. Projection and workflow layers must not
    rederive the fact from physical lines.
    """
    return committed_tactics_have_qed(read_committed_tactics(session_dir))


def committed_tactics_have_qed(tactics: list[str]) -> bool:
    """Canonical closure-syntax predicate for an already-read tactic list."""
    return any(
        _is_standalone_qed(tactic)
        for tactic in split_trailing_qed(list(tactics))
    )


def closed_history_tactics(session_dir: str | Path) -> list[str]:
    """The committed tactics IFF the proof is closed (a ``qed`` sentence
    exists — standalone line or embedded at the end of a compound final
    step), else []. Reporting/write-back paths use this so an unfinished
    history is never mistaken for a proof. A compound closer is normalized
    via ``split_trailing_qed`` so downstream qed handling sees a standalone
    ``qed.`` entry."""
    tactics = split_trailing_qed(read_committed_tactics(session_dir))
    if committed_tactics_have_qed(tactics):
        return tactics
    return []
