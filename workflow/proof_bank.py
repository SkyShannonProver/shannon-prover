"""Proof bank: persistent record of proved lemmas and their tactic sequences.

Stores one JSONL entry per proved lemma. Used by the regression tester to
replay proofs after tool changes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("workflow.proof_bank")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROOF_BANK_PATH = _PROJECT_ROOT / "workflow" / "proof_bank.jsonl"


def record_proof(
    file: str,
    lemma: str,
    include_dir: str,
    tactics: list[str],
) -> None:
    """Append a proved lemma to the proof bank.

    Deduplicates: if the same file+lemma already exists, replaces it
    (the latest proof is authoritative).
    """
    entry = {
        "file": file,
        "lemma": lemma,
        "include_dir": include_dir,
        "tactics": tactics,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }

    # Load existing entries, replace if same file+lemma exists
    existing = load_all()
    replaced = False
    for i, e in enumerate(existing):
        if e["file"] == file and e["lemma"] == lemma:
            existing[i] = entry
            replaced = True
            break
    if not replaced:
        existing.append(entry)

    # Write back
    _PROOF_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _PROOF_BANK_PATH.open("w", encoding="utf-8") as f:
        for e in existing:
            f.write(json.dumps(e) + "\n")

    action = "Updated" if replaced else "Added"
    logger.info("%s proof bank entry: %s:%s (%d tactics)", action, file, lemma, len(tactics))


def load_all() -> list[dict]:
    """Load all entries from the proof bank."""
    if not _PROOF_BANK_PATH.exists():
        return []
    entries = []
    for line in _PROOF_BANK_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries
