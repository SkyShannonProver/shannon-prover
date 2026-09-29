"""CLAUDE.md must not carry a drifted static agent-intent list.

The agent-contract doc had drifted once (listed a non-existent
`request_restart`, omitted 6 real intents). CLAUDE.md has since dropped the
static JSON menu entirely: runtime MCP metadata and the workspace view are
the authoritative source. Both states are guarded here: with no intent JSON
block the doc must not resurrect `request_restart`; if a block ever comes
back, it must equal the parser's set exactly.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.proof_management.protocol_repair import (  # noqa: E402
    ALLOWED_AGENT_INTENTS,
)


def test_claude_md_intents_match_allowed_set() -> None:
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    documented = set(re.findall(r'\{"intent":\s*"([a-z_]+)"', text))
    assert "request_restart" not in text, (
        "CLAUDE.md names request_restart — that intent never existed "
        "(the restart intent is fresh_restart)"
    )
    if not documented:
        # Current policy: no static menu in CLAUDE.md; runtime MCP metadata
        # and the workspace view are the authoritative source.
        return
    canonical = set(ALLOWED_AGENT_INTENTS)
    assert documented == canonical, (
        "CLAUDE.md intent list drifted from ALLOWED_AGENT_INTENTS; "
        f"missing={sorted(canonical - documented)} "
        f"extra={sorted(documented - canonical)}"
    )
