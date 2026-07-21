"""Small, shared classifiers for EasyCrypt program statements.

These helpers classify syntax already present in a proof-state snapshot.  They
do not inspect source files or recommend tactics.  Keeping them below both the
workspace projector and the surface composer prevents the two layers from
quietly disagreeing about the same statement.
"""
from __future__ import annotations

import re
from typing import Any


_PROC_CALL_RE = re.compile(
    r"[A-Za-z_]\w*(?:\((?:[^()]|\([^()]*\))*\))?\.[A-Za-z_]\w*\s*\("
)


def statement_is_procedure_call(text: Any) -> bool:
    """Return whether a displayed program statement is a procedure call.

    EasyCrypt uses ``<@`` for an explicit procedure call and ``<-`` for a
    deterministic assignment.  Bare module procedure applications can also
    appear in projected setup rows, including nested module instantiations.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    if "<@" in text:
        return True
    if "<-" in text:
        return False
    return bool(_PROC_CALL_RE.search(text))
