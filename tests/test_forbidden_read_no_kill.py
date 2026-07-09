#!/usr/bin/env python3
"""(B) A forbidden information-source READ never hard-kills the tree.

Found 2026-05-30: a forbidden read accrued 3 strikes and the session-hygiene
watchdog killed the whole tree, discarding its committed proof work. A read
mutates nothing — at worst it pollutes reasoning, which an escalating warn
corrects and the payload audit records. The hard kill is reserved for genuinely
destructive / boundary-breaking actions: a node_fatal bridge/session_cli escape
(`pending_unsafe`), or an rm -rf / source Edit (detected by the watchdog). This
drives the tracker's strike handler directly.

Run: python3 -m pytest tests/test_forbidden_read_no_kill.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from workflow.progress import _TreeProverTracker  # noqa: E402


def _bare_tracker() -> _TreeProverTracker:
    t = _TreeProverTracker.__new__(_TreeProverTracker)
    for name in (
        "pending_unsafe_tool_uses", "pending_forbidden_tool_uses",
        "pending_session_cli_background_tool_uses", "pending_lossy_tool_uses",
        "pending_unsafe_tool_use_reasons", "pending_forbidden_tool_use_reasons",
        "pending_lossy_tool_use_policies",
    ):
        setattr(t, name, {})
    t.pending_non_forbidden_tool_uses = set()
    t.unsafe_session_shell_command = ""
    t.unsafe_session_shell_time = 0.0
    t.unsafe_information_source_reason = ""
    t.forbidden_information_source_count = 0
    t.forbidden_information_source_last = ""
    t.forbidden_information_source_reason = ""
    t.payload_audit = None
    t.name = "Tree-0.1"
    t._session_tag = "prover_tree_0_1"
    return t


def test_repeated_forbidden_reads_do_not_kill() -> None:
    t = _bare_tracker()
    for i in range(5):  # well past the old 3-strike kill threshold
        tid = f"tu{i}"
        t.pending_forbidden_tool_uses[tid] = "Read(/some/forbidden/source.ec)"
        t.pending_forbidden_tool_use_reasons[tid] = "forbidden source"
        t._resolve_session_hygiene_tool_result(tid, "ok")
    # counter still climbs (for audit/escalation), but NO kill is armed.
    assert t.forbidden_information_source_count == 5
    assert t.unsafe_session_shell_command == "", t.unsafe_session_shell_command


def test_node_fatal_bridge_escape_still_kills() -> None:
    # the destructive/bridge path (pending_unsafe) must STILL arm the kill.
    t = _bare_tracker()
    t.pending_unsafe_tool_uses["x"] = "cat .../submit_intent.sh"
    t.pending_unsafe_tool_use_reasons["x"] = "manager bridge escape"
    t._resolve_session_hygiene_tool_result("x", "ok")
    assert t.unsafe_session_shell_command != ""
    assert "bridge" in t.unsafe_information_source_reason.lower()


def test_blocked_memory_read_denial_does_not_kill() -> None:
    # (2026-06-05) The answer-leak guard classifies a ~/.claude memory Read as
    # node_fatal (pending_unsafe). But once --disallowedTools actually BLOCKS that
    # Read, the agent gets a path-based permission denial and NO content leaks, so
    # the node must NOT be killed — the refusal IS the "you can't read this"
    # warning the user asked for. This is the exact denial text Claude Code emits
    # for a Read(//~/.claude/**)-style block; the watchdog must recognise it and
    # skip the kill (otherwise a properly-blocked read still loses the tree).
    t = _bare_tracker()
    t.pending_unsafe_tool_uses["m"] = (
        "Read(/Users/u/.claude/projects/p/memory/project_x.md)"
    )
    t.pending_unsafe_tool_use_reasons["m"] = "claude_memory_answer_leak"
    denial = ("<tool_use_error>File is in a directory that is denied by your "
              "permission settings.</tool_use_error>")
    t._resolve_session_hygiene_tool_result("m", denial)
    assert t.unsafe_session_shell_command == "", t.unsafe_session_shell_command


def test_leaked_memory_read_content_still_kills() -> None:
    # Defense-in-depth backstop: if the block ever fails and a memory Read is NOT
    # denied (content actually returned — a real answer leak), the node IS still
    # killed, discarding the contaminated tree. Only a refusal is forgiven.
    t = _bare_tracker()
    t.pending_unsafe_tool_uses["m"] = (
        "Read(/Users/u/.claude/projects/p/memory/project_x.md)"
    )
    t.pending_unsafe_tool_use_reasons["m"] = "claude_memory_answer_leak"
    leaked = "1\t---\n2\tname: project_x\n3\tdescription: solved-lemma hints ...\n"
    t._resolve_session_hygiene_tool_result("m", leaked)
    assert t.unsafe_session_shell_command != ""
