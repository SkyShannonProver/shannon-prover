"""Single reader for a session's committed proof history (``history.ec``).

Seven call sites across workflow/ used to hand-roll this pair (audit
backlog #19): path minting (``session_dir / "history.ec"``), tactic
parsing, and qed-detection each re-derived per site. This module is now the
only owner of committed-history reading and closure detection. Both public
readers return complete EasyCrypt commands: a manager commit may span several
physical lines, so line-oriented parsing is not a valid proof-prefix model.

Leaf module: stdlib-only at import time (the command splitter is
late-bound from ``ec_lifecycle``).
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


def read_committed_commands(session_dir: str | Path) -> list[str]:
    """Committed history as complete ``.``-terminated EasyCrypt commands.

    A command may span physical lines, and one physical line can pack several
    commands (``wp; skip. qed.`` is two commands). Prefix counts, replay,
    projection, and closure detection must therefore use the EasyCrypt command
    splitter rather than ``splitlines()``. Returns [] if the history cannot be
    read or parsed; silently degrading to physical lines would manufacture a
    different proof prefix.
    """
    path = history_path(session_dir)
    try:
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    try:
        from core.easycrypt.ec_lifecycle import split_ec_commands

        return [c.strip() for c in split_ec_commands(text) if c.strip()]
    except Exception:
        return []


def read_committed_tactics(session_dir: str | Path) -> list[str]:
    """All committed tactics as complete EasyCrypt commands; [] if unreadable.

    This compatibility name remains the canonical reader used across the
    manager and projection layers. It deliberately has command, not physical-
    line, semantics. Replay code that must retain a multi-command manager
    submission uses :func:`read_committed_transactions` as the stronger view.
    """

    return read_committed_commands(session_dir)


def flatten_committed_transactions(
    transactions: list[str] | tuple[str, ...],
) -> list[str]:
    """Expand manager commit transactions into canonical EC commands.

    ``history.ec`` is command-oriented while ``steps.log`` records the
    manager-owned commit boundary.  A transaction can contain several
    commands whose bullet scope is meaningful only when submitted together.
    """

    try:
        from core.easycrypt.ec_lifecycle import split_ec_commands

        return [
            command.strip()
            for transaction in transactions
            for command in split_ec_commands(str(transaction))
            if command.strip()
        ]
    except Exception:
        return []


def read_committed_transactions(session_dir: str | Path) -> list[str]:
    """Return the surviving manager commit blocks from ``history.ec``.

    ``Session.append_block`` appends one physical-line count to ``steps.log``
    per accepted manager transaction, and undo removes that count together
    with the corresponding history suffix.  The pair therefore preserves a
    stronger replay contract than command splitting alone: formatted ``+`` /
    ``-`` bullet blocks must be replayed atomically.

    Old/debug sessions without ``steps.log`` fall back to individual commands
    for compatibility.  A present but malformed/mismatched step ledger fails
    closed instead of manufacturing transaction boundaries.
    """

    session = Path(session_dir)
    path = history_path(session)
    try:
        if not path.is_file():
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    commands = read_committed_commands(session)
    if not commands:
        return []
    steps_path = session / "steps.log"
    if not steps_path.is_file():
        return commands
    try:
        raw_entries = steps_path.read_text(encoding="utf-8").splitlines()
        entries = [int(item.strip()) for item in raw_entries if item.strip()]
    except Exception:
        return []
    if not entries or any(count <= 0 for count in entries):
        return []
    lines = text.splitlines()
    if sum(entries) != len(lines):
        return []
    transactions: list[str] = []
    cursor = 0
    for count in entries:
        block = "\n".join(lines[cursor : cursor + count]).strip()
        if not block:
            return []
        transactions.append(block)
        cursor += count
    if flatten_committed_transactions(transactions) != commands:
        return []
    return transactions


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
