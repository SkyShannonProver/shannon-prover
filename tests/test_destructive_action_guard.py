"""Tests for the destructive-action guards on the prover subagent.

Two-layer defense (designed 2026-05-03 after a Tree worker rm -rf'd its
session dir on ChaChaPoly step1):

1. Sandbox-layer deny patterns rendered into ``--disallowedTools`` on
   the ``claude -p`` launch — covered by ``_destructive_tool_denylist``.
2. Watchdog at the orchestrator's tick loop that aborts the run when a
   session dir vanishes or the source ``.ec`` file's mtime advances —
   covered by inspecting ``run_tree_prover.last_destructive_abort``
   after a synthetic worker that simulates the failure.

These tests verify the deny patterns construct correctly. The watchdog
itself is exercised by integration tests during a live run; we assert
its API surface here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

# The prover-side wrapper was removed; the denylist now lives only in the policy
# module (applied by ProofNodeRuntime at the claude launch). Test it directly.
from workflow.payload_audit import PayloadAuditRecorder, summarize_text_payload  # noqa: E402
from workflow.prover_io_policy import (  # noqa: E402
    classify_bash_command,
    destructive_tool_denylist as _destructive_tool_denylist,
)


def test_denylist_blocks_rm_in_all_forms() -> None:
    patterns = _destructive_tool_denylist("/tmp/x.ec")
    assert "Bash(rm:*)" in patterns
    assert "Bash(rm -rf:*)" in patterns
    assert "Bash(rmdir:*)" in patterns


def test_denylist_leaves_manager_boundary_to_policy_and_blocks_task_outputs() -> None:
    patterns = _destructive_tool_denylist("/tmp/x.ec")
    assert "Bash(*session_cli.py*|*)" not in patterns
    assert "Bash(*session_cli.py*-next* |*)" not in patterns
    assert "Bash(*session_cli.py*-chain* |*)" not in patterns
    assert "Bash(*session_cli.py*-try* |*)" not in patterns
    assert "Read(//private/tmp/*/tasks/*.output)" in patterns
    assert "Bash(*.ec_session_*/history.ec*)" not in patterns
    assert "Bash(*.ec_session_*/current.out*)" not in patterns
    assert "Read(*.ec_session_*/history.ec)" not in patterns
    assert "Read(*.ec_session_*/current.out)" not in patterns
    assert "Agent(*)" in patterns
    assert "Glob(*)" in patterns
    assert "Bash(curl:*)" in patterns
    assert any("/.claude/" in pattern for pattern in patterns)
    assert any("workflow/runs" in pattern for pattern in patterns)
    assert not any("/tmp/**" in pattern for pattern in patterns)
    assert not any("/worktrees/**" in pattern for pattern in patterns)


def test_denylist_prevents_mutating_session_cli_but_keeps_readonly_signal() -> None:
    # Backlog #4 / audit §6.1: the manager-owned EC-mutation invariant is enforced
    # at the TOOL boundary (prevention), not only by the post-hoc node-kill. The
    # MUTATING session_cli flags + writes into a `.ec_session_*` dir are hard-denied;
    # READ-ONLY session_cli stays allowed so the `session_cli.agent_call_debug_signal`
    # ("the view was insufficient") is preserved.
    from workflow.prover_io_policy import (
        SESSION_CLI_AGENT_FORBIDDEN_LIFECYCLE_FLAGS,
        SESSION_CLI_MUTATING_FLAGS,
        SESSION_CLI_READONLY_FLAGS,
    )
    patterns = _destructive_tool_denylist("/tmp/x.ec")
    for flag in SESSION_CLI_MUTATING_FLAGS | SESSION_CLI_AGENT_FORBIDDEN_LIFECYCLE_FLAGS:
        assert f"Bash(*session_cli*{flag}*)" in patterns, flag
    # `-tactic-exec commit|commit_chain|undo` mutates committed state but lives in
    # its own argparse dest (not in SESSION_CLI_MUTATING_FLAGS) — deny it too.
    assert "Bash(*session_cli*-tactic-exec*)" in patterns
    # read-only flags must NOT be denied — that path is the intentional debug signal
    for flag in SESSION_CLI_READONLY_FLAGS:
        assert f"Bash(*session_cli*{flag}*)" not in patterns, flag
        assert not any(("session_cli" in p and flag in p) for p in patterns), flag
    # writes into a manager-owned session dir are denied (Edit/Write/MultiEdit)
    assert "Edit(**/.ec_session_*/**)" in patterns
    assert "Write(**/.ec_session_*/**)" in patterns
    assert "MultiEdit(**/.ec_session_*/**)" in patterns


def test_denylist_blocks_edit_and_write_on_source_file() -> None:
    patterns = _destructive_tool_denylist("eval/examples/foo.ec")
    # Select the SOURCE-file mutation patterns specifically: the denylist also
    # carries basename-glob Edit/Write/MultiEdit guards for ~/.claude memory
    # notes (e.g. `Edit(*MEMORY.md)`), which are a separate, intentionally
    # non-absolute class and must not be picked up here.
    edit = next(p for p in patterns if p.startswith("Edit(") and "foo.ec" in p)
    multiedit = next(p for p in patterns if p.startswith("MultiEdit(") and "foo.ec" in p)
    write = next(p for p in patterns if p.startswith("Write(") and "foo.ec" in p)
    # Path is resolved to absolute; we only need the source filename to
    # appear in all mutation patterns.
    assert "foo.ec" in edit
    assert "foo.ec" in multiedit
    assert "foo.ec" in write
    assert "Edit(eval/examples/foo.ec)" in patterns
    assert "MultiEdit(eval/examples/foo.ec)" in patterns
    assert "Write(eval/examples/foo.ec)" in patterns
    assert "Edit(./eval/examples/foo.ec)" in patterns
    # basename catch must be `**/name` (matches at any depth), not a bare `*name`
    # glob (which only matches in the cwd subtree).
    assert "MultiEdit(**/foo.ec)" in patterns


def test_denylist_uses_resolved_absolute_path() -> None:
    """A relative path must be resolved before being baked into the
    deny pattern; otherwise the agent could ``Edit ./foo.ec`` and slip
    past a pattern that anchored on the absolute form."""
    patterns = _destructive_tool_denylist("relative/path.ec")
    # The SOURCE-file edit pattern (not the memory-note basename guards) must be
    # resolved to absolute.
    edit = next(p for p in patterns if p.startswith("Edit(") and "path.ec" in p)
    # Resolved path starts with /
    inner = edit[len("Edit("):-1]
    assert inner.startswith("/"), f"expected absolute path in deny pattern: {edit}"


def test_run_tree_prover_advertises_destructive_abort_attribute() -> None:
    """The orchestrator's caller (``prover.run``) reads
    ``run_tree_prover.last_destructive_abort`` to decide whether to
    raise instead of returning a normal failure tuple. The attribute
    must exist as a function-level attr (set by the function on each
    invocation)."""
    from workflow.progress import run_tree_prover
    # The attribute may not be set until the function has been invoked
    # at least once; the contract is that ``getattr(...,..., False)``
    # is the documented access path. Verify that path is safe.
    val = getattr(run_tree_prover, "last_destructive_abort", False)
    assert isinstance(val, bool)


def test_session_cli_shell_detector_blocks_any_agent_session_cli() -> None:
    from workflow.prover_io_policy import (
        classify_bash_command,
        is_session_cli_mutating_command as _is_session_cli_mutating_command,
    )

    def _is_unsafe_session_cli_shell_command(cmd: str) -> bool:
        return classify_bash_command(cmd).decision == "node_fatal"

    def _is_lossy_session_cli_shell_command(cmd: str) -> bool:
        return classify_bash_command(cmd).decision == "warn"

    assert _is_unsafe_session_cli_shell_command(
        "python3 core/easycrypt/session_cli.py -d s -next -c 'idtac.' | head -20"
    )
    assert not _is_lossy_session_cli_shell_command(
        "python3 core/easycrypt/session_cli.py -d s -next -c 'idtac.' | head -20"
    )
    assert _is_unsafe_session_cli_shell_command(
        "python3 core/easycrypt/session_cli.py -d s -status 2>/dev/null | python3 -c 'print(1)'"
    )
    assert _is_unsafe_session_cli_shell_command(
        "python3 core/easycrypt/session_cli.py -d s -try -c 'byequiv => //.' 2>&1 | grep accepted"
    )
    assert not _is_lossy_session_cli_shell_command(
        "python3 core/easycrypt/session_cli.py -d s -try -c 'byequiv => //.' 2>&1 | grep accepted"
    )
    assert not _is_unsafe_session_cli_shell_command(
        "cat .ec_session_prover_tree_0_0/current.out | grep 'Current goal'"
    )
    assert _is_unsafe_session_cli_shell_command(
        "python3 core/easycrypt/session_cli.py -d s -next -c 'case: xs => [|x xs].'"
    )
    assert not _is_unsafe_session_cli_shell_command(
        "rg session_cli.py core | head"
    )
    assert _is_session_cli_mutating_command(
        "python3 core/easycrypt/session_cli.py -d s -next -c 'rnd{2}.' 2>&1"
    )
    assert _is_session_cli_mutating_command(
        "python3 core/easycrypt/session_cli.py -d s -chain --keep-on-fail -c 'wp.'"
    )
    assert not _is_session_cli_mutating_command(
        "python3 core/easycrypt/session_cli.py -d s -goal-info"
    )

def test_denied_unsafe_session_command_does_not_mark_tree_polluted(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tool_id = "toolu_denied"
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session_prover_tree_0_0 "
        "-start -f x.ec -lemma L 2>&1 | tail -80"
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    assert tracker.unsafe_session_shell_command == ""

    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": f"Permission to use Bash with command {cmd} has been denied.",
            }],
        },
    }))
    assert tracker.unsafe_session_shell_command == ""


def test_executed_filtered_session_command_marks_tree_polluted(tmp_path: Path) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tool_id = "toolu_executed"
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session_prover_tree_0_0 "
        "-next -c 'idtac.' 2>&1 | head -20"
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": '[TACTIC-EXECUTION-RESULT]\n{"execution":{}}',
            }],
        },
    }))
    assert tracker.unsafe_session_shell_command == cmd
    assert "debug signal" in tracker.unsafe_information_source_reason
    assert tracker.lossy_session_cli_command == ""
    assert tracker.lossy_session_cli_count == 0


def test_readonly_filtered_session_cli_marks_tree_polluted(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tool_id = "toolu_readonly_filtered"
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session_prover_tree_0_0 "
        "-try -c 'byequiv => //.' 2>&1 | grep accepted"
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": '"accepted": true',
            }],
        },
    }))

    assert tracker.unsafe_session_shell_command == cmd
    assert "debug signal" in tracker.unsafe_information_source_reason
    assert tracker.lossy_session_cli_command == ""
    assert tracker.lossy_session_cli_count == 0


def test_shell_raw_session_artifact_does_not_mark_tree_polluted(tmp_path: Path) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tool_id = "toolu_raw_shell"
    cmd = "cat .ec_session_prover_tree_0_0/current.out"
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    assert tracker.unsafe_session_shell_command == ""
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": "raw goal text",
            }],
        },
    }))
    assert tracker.unsafe_session_shell_command == ""


def test_legal_source_grep_is_audited_not_polluted(tmp_path: Path) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tool_id = "toolu_source_grep"
    cmd = "rg CTXT_security eval/examples/MEE-CBC"
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": "eval/examples/MEE-CBC/RCPA_CMA.ec:lemma CTXT_security",
            }],
        },
    }))

    assert tracker.unsafe_session_shell_command == ""
    assert tracker.information_source_audit[-1]["audit_code"] == "shell_source.inspect"


def test_active_target_source_under_tmp_is_allowed_for_tracker(tmp_path: Path) -> None:
    from workflow.progress import _TreeProverTracker

    target_source = tmp_path / "tmp" / "active" / "target.ec"
    target_source.parent.mkdir(parents=True)
    target_source.write_text(
        "lemma target : true.\nproof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    tracker = _TreeProverTracker(
        object(),
        "Tree-0.0",
        str(tmp_path),
        "prover_tree_0_0",
        allowed_source_files=[target_source],
        target_lemma="target",
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": "toolu_target_source",
                "name": "Read",
                "input": {"file_path": str(target_source)},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": "toolu_target_source",
                "content": "lemma target : true.",
            }],
        },
    }))

    assert tracker.unsafe_session_shell_command == ""
    assert tracker.forbidden_information_source_count == 0
    assert tracker.information_source_audit[-1]["audit_code"] == (
        "read.active_target_source"
    )


def test_active_target_source_with_existing_answer_is_not_allowed(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    target_source = tmp_path / "tmp" / "active" / "target.ec"
    target_source.parent.mkdir(parents=True)
    target_source.write_text(
        "lemma target : true.\nproof.\n  trivial.\nqed.\n",
        encoding="utf-8",
    )
    tracker = _TreeProverTracker(
        object(),
        "Tree-0.0",
        str(tmp_path),
        "prover_tree_0_0",
        allowed_source_files=[target_source],
        target_lemma="target",
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": "toolu_target_source_answer",
                "name": "Read",
                "input": {"file_path": str(target_source)},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": "toolu_target_source_answer",
                "content": "lemma target : true.",
            }],
        },
    }))

    assert tracker.unsafe_session_shell_command == ""
    assert tracker.forbidden_information_source_count == 1
    assert tracker.information_source_audit[-1]["audit_code"] == (
        "read.active_target_source_contains_answer"
    )


def test_forbidden_session_transcript_read_never_kills(
    tmp_path: Path,
) -> None:
    """A forbidden cross-session transcript READ escalates a warn + audit on
    every strike and never arms the hard kill (fix B: a read mutates nothing,
    so killing the tree and discarding its committed work is the wrong trade).
    """
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    path = str(tmp_path / ".ec_session_other" / "history.ec")

    for idx in range(1, 4):
        tool_id = f"toolu_other_session_{idx}"
        tracker._process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "Read",
                    "input": {"file_path": path},
                }],
            },
        }))
        tracker._process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": "old proof transcript",
                }],
            },
        }))
        # every strike accrues a warn + audit but never arms the kill
        assert tracker.unsafe_session_shell_command == ""
        assert tracker.forbidden_information_source_count == idx

    # three strikes later the tree is still kept (warn-only, no kill)
    assert tracker.unsafe_session_shell_command == ""
    assert tracker.forbidden_information_source_count == 3


def test_forbidden_session_transcript_grep_never_kills(
    tmp_path: Path,
) -> None:
    """A forbidden cross-session transcript GREP escalates a warn + audit on
    every strike and never arms the hard kill (fix B): reading another session's
    tactics pollutes reasoning at worst, which the audit records for post-hoc
    validity checks; the hard kill stays reserved for destructive actions.
    """
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    cmd = "rg 'call' .ec_session_other/history.ec"

    for idx in range(1, 4):
        tool_id = f"toolu_other_session_grep_{idx}"
        tracker._process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "Bash",
                    "input": {"command": cmd},
                }],
            },
        }))
        tracker._process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": "old tactic",
                }],
            },
        }))
        # every strike accrues a warn + audit but never arms the kill
        assert tracker.unsafe_session_shell_command == ""
        assert tracker.forbidden_information_source_count == idx

    # three strikes later the tree is still kept (warn-only, no kill)
    assert tracker.unsafe_session_shell_command == ""
    assert tracker.forbidden_information_source_count == 3


def test_legal_source_read_resets_forbidden_source_streak(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    forbidden_path = str(tmp_path / ".ec_session_other" / "history.ec")
    source_cmd = "rg CTXT_security eval/examples/MEE-CBC"

    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": "bad_1",
                "name": "Read",
                "input": {"file_path": forbidden_path},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": "bad_1",
                "content": "old proof transcript",
            }],
        },
    }))
    assert tracker.forbidden_information_source_count == 1

    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": "good_1",
                "name": "Bash",
                "input": {"command": source_cmd},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": "good_1",
                "content": "eval/examples/MEE-CBC/RCPA_CMA.ec:lemma CTXT_security",
            }],
        },
    }))

    assert tracker.forbidden_information_source_count == 0
    assert tracker.unsafe_session_shell_command == ""


def test_raw_session_artifact_read_does_not_mark_tree_polluted(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    path = str(tmp_path / ".ec_session_prover_tree_0_0" / "current.out")
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": "toolu_raw_read",
                "name": "Read",
                "input": {"file_path": path},
            }],
        },
    }))

    assert tracker.unsafe_session_shell_command == ""


def test_backgrounded_mutating_session_command_waits_instead_of_polluting(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tool_id = "toolu_background"
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session_prover_tree_0_0 "
        "-next -c 'rnd{2}.' 2>&1"
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": (
                    "Command running in background with ID: abc. "
                    "Output is being written to: /private/tmp/tasks/abc.output"
                ),
            }],
        },
    }))
    assert tracker.unsafe_session_shell_command == cmd
    assert tracker.background_session_cli_command == ""
    assert tracker.waiting_on_background_mutation is False
    assert tracker.background_session_cli_count == 0


def test_backgrounded_mutating_session_clears_after_structured_result(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker
    from workflow.session_observer import WorkflowSessionSnapshot

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tracker.background_session_cli_command = "python3 session_cli.py -next -c 'wp.'"
    tracker.background_session_cli_time = 1000.0
    tracker.background_session_cli_notice_time = 1000.0

    tracker._refresh_background_session_cli(WorkflowSessionSnapshot(
        session_dir=str(tmp_path / ".ec_session_prover_tree_0_0"),
        exists=True,
        ok=True,
        active_tool_mutates=False,
        last_mutating_tool_at=1002.0,
    ))

    assert tracker.background_session_cli_command == ""
    assert tracker.waiting_on_background_mutation is False


def test_non_background_mutating_session_command_marks_tree_polluted(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    tracker = _TreeProverTracker(object(), "Tree-0.0", str(tmp_path), "prover_tree_0_0")
    tool_id = "toolu_ok"
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session_prover_tree_0_0 "
        "-next -c 'wp.'"
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": '[TACTIC-EXECUTION-RESULT]\n{"execution":{}}',
            }],
        },
    }))
    assert tracker.unsafe_session_shell_command == cmd
    assert "debug signal" in tracker.unsafe_information_source_reason


# ---- Payload audit (merged from test_payload_audit.py) ---------------------
# The payload-audit recorder rides the same _TreeProverTracker transcript feed
# the guards above exercise; these tests cover the recorder itself plus the
# tracker's audit wiring.


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_summarize_text_payload_marks_transport_features() -> None:
    summary = summarize_text_payload(
        "[TACTIC-EXECUTION-RESULT] {}\n"
        "Output too large. Full output saved to: /tmp/tool-results/x.txt"
    )

    assert summary["contains_tactic_execution_result"] is True
    assert summary["contains_output_too_large"] is True
    assert summary["full_output_saved_to"] == ["/tmp/tool-results/x.txt"]
    assert summary["lines"] == 2
    assert summary["contains_prover_workspace_view"] is False


def test_summarize_text_payload_detects_agent_workspace_fields() -> None:
    summary = summarize_text_payload(
        '[TACTIC-EXECUTION-RESULT]\n'
        '{"workspace":{"view":{"current_goal":{"lines":["g"]}}}}\n'
    )

    assert summary["contains_tactic_execution_result"] is True
    assert summary["contains_prover_workspace_view"] is True


def test_payload_audit_records_tool_use_and_result(tmp_path: Path) -> None:
    path = tmp_path / "payload_audit.jsonl"
    recorder = PayloadAuditRecorder(path)
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session_x "
        "-agent-view | head -20"
    )
    policy = classify_bash_command(
        cmd,
        cwd=tmp_path,
        current_session_dir=tmp_path / ".ec_session_x",
    )

    recorder.record_tool_use(
        tree="Tree-0.0",
        session_tag="prover_tree_0_0",
        tool_use_id="toolu_1",
        tool_name="Bash",
        tool_input={"command": cmd},
        policy=policy,
        description=cmd,
    )
    recorder.record_tool_result(
        tree="Tree-0.0",
        session_tag="prover_tree_0_0",
        tool_use_id="toolu_1",
        result_text='[TACTIC-EXECUTION-RESULT]\n{"execution":{"accepted_count":0}}',
        pending_kind="unsafe",
        pending_description=cmd,
        pending_reason=policy.reason,
    )

    rows = _jsonl(path)
    assert [row["event"] for row in rows] == ["tool_use", "tool_result"]
    assert rows[0]["policy"]["lossy"] is True
    assert rows[0]["input"]["command_chars"] == len(cmd)
    assert rows[1]["pending_kind"] == "unsafe"
    assert rows[1]["result"]["contains_tactic_execution_result"] is True


def test_tree_tracker_audits_context_before_file_tool_without_raw_thinking(
    tmp_path: Path,
) -> None:
    from workflow.progress import _TreeProverTracker

    audit_path = tmp_path / "payload_audit.jsonl"
    recorder = PayloadAuditRecorder(audit_path)
    tracker = _TreeProverTracker(
        object(),
        "Tree-0.0",
        str(tmp_path),
        "prover_tree_0_0",
        payload_audit=recorder,
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "thinking",
                    "thinking": (
                        "I should search node_memory and maybe .ec_session_ "
                        "history to understand the route."
                    ),
                },
                {
                    "type": "text",
                    "text": "I will inspect the legal current view first.",
                },
                {
                    "type": "tool_use",
                    "id": "toolu_read",
                    "name": "Read",
                    "input": {
                        "file_path": str(
                            tmp_path / ".ec_session_other" / "history.ec"
                        ),
                    },
                },
            ],
        },
    }))

    rows = _jsonl(audit_path)
    context = rows[0]["assistant_context"]
    assert context["preceding_text_preview"] == (
        "I will inspect the legal current view first."
    )
    assert context["preceding_thinking_blocks"] == 1
    assert context["preceding_thinking_chars"] > 0
    assert "preceding_thinking_sha1" in context
    assert "search node_memory" not in json.dumps(context)
    assert "mentions_node_memory" in context["preceding_thinking_markers"]
    assert "mentions_forbidden_session" in context["preceding_thinking_markers"]


def test_payload_audit_summarizes_structured_mcp_intent(tmp_path: Path) -> None:
    path = tmp_path / "payload_audit.jsonl"
    recorder = PayloadAuditRecorder(path)
    recorder.record_tool_use(
        tree="Tree-0.0",
        session_tag="prover_tree_0_0",
        tool_use_id="toolu_mcp",
        tool_name="mcp__proof_node_manager__submit_proof_intent",
        tool_input={
            "intent": "probe_tactic",
            "payload": {"tactic": "seq 1 1 : (x{1} = x{2})."},
        },
        description="submit_proof_intent probe_tactic",
    )

    rows = _jsonl(path)
    assert rows[0]["event"] == "tool_use"
    assert rows[0]["input"]["intent"] == "probe_tactic"
    assert rows[0]["input"]["tactic_chars"] > 0
    assert "seq 1 1" in rows[0]["input"]["tactic_head"]


def test_tree_tracker_writes_payload_audit_for_forbidden_session_cli_pipe(tmp_path: Path) -> None:
    from workflow.progress import _TreeProverTracker

    audit_path = tmp_path / "payload_audit.jsonl"
    recorder = PayloadAuditRecorder(audit_path)
    tracker = _TreeProverTracker(
        object(),
        "Tree-0.0",
        str(tmp_path),
        "prover_tree_0_0",
        payload_audit=recorder,
    )
    tool_id = "toolu_lossy"
    cmd = (
        "python3 core/easycrypt/session_cli.py -d .ec_session_prover_tree_0_0 "
        "-agent-view | head -20"
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "Bash",
                "input": {"command": cmd},
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": '[TACTIC-EXECUTION-RESULT]\n{"execution":{}}',
            }],
        },
    }))

    rows = _jsonl(audit_path)
    assert rows[0]["event"] == "tool_use"
    assert rows[0]["policy"]["audit_code"] == "session_cli.agent_call_debug_signal"
    assert rows[1]["event"] == "tool_result"
    assert rows[1]["pending_kind"] == "unsafe"


def test_tree_tracker_records_mcp_submit_intent_semantics(tmp_path: Path) -> None:
    from workflow.progress import _TreeProverTracker

    audit_path = tmp_path / "payload_audit.jsonl"
    recorder = PayloadAuditRecorder(audit_path)
    tracker = _TreeProverTracker(
        object(),
        "Tree-0.0",
        str(tmp_path),
        "prover_tree_0_0",
        payload_audit=recorder,
    )
    tool_id = "toolu_mcp"
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": "mcp__proof_node_manager__submit_proof_intent",
                "input": {
                    "intent": "inspect_context",
                    "payload": {"topic": "goal_info"},
                },
            }],
        },
    }))
    tracker._process_line(json.dumps({
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": "Manager result",
            }],
        },
    }))

    rows = _jsonl(audit_path)
    assert rows[0]["event"] == "tool_use"
    assert rows[0]["tool_name"].endswith("submit_proof_intent")
    assert rows[0]["input"]["intent"] == "inspect_context"
    assert rows[0]["input"]["topic"] == "goal_info"
    assert rows[0]["description"] == "submit_proof_intent inspect_context: goal_info"
    assert rows[1]["event"] == "tool_result"


def test_tree_tracker_marks_empty_mcp_intent_as_malformed(tmp_path: Path) -> None:
    from workflow.progress import _TreeProverTracker

    audit_path = tmp_path / "payload_audit.jsonl"
    recorder = PayloadAuditRecorder(audit_path)
    tracker = _TreeProverTracker(
        object(),
        "Tree-0.0",
        str(tmp_path),
        "prover_tree_0_0",
        payload_audit=recorder,
    )
    tracker._process_line(json.dumps({
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": "toolu_empty",
                "name": "mcp__proof_node_manager__submit_proof_intent",
                "input": {"intent": "", "payload": {"tactic": "sp; wp; if."}},
            }],
        },
    }))

    rows = _jsonl(audit_path)
    assert rows[0]["event"] == "tool_use"
    assert rows[0]["input"]["intent"] == ""
    assert rows[0]["description"] == "submit_proof_intent malformed: missing intent"


def main() -> int:
    test_denylist_blocks_rm_in_all_forms()
    test_denylist_leaves_manager_boundary_to_policy_and_blocks_task_outputs()
    test_denylist_blocks_edit_and_write_on_source_file()
    test_denylist_uses_resolved_absolute_path()
    test_run_tree_prover_advertises_destructive_abort_attribute()
    test_session_cli_shell_detector_blocks_any_agent_session_cli()
    test_denied_unsafe_session_command_does_not_mark_tree_polluted(Path("/tmp"))
    test_executed_filtered_session_command_marks_tree_polluted(Path("/tmp"))
    test_readonly_filtered_session_cli_marks_tree_polluted(Path("/tmp"))
    test_shell_raw_session_artifact_does_not_mark_tree_polluted(Path("/tmp"))
    test_legal_source_grep_is_audited_not_polluted(Path("/tmp"))
    test_forbidden_session_transcript_read_never_kills(Path("/tmp"))
    test_forbidden_session_transcript_grep_never_kills(Path("/tmp"))
    test_legal_source_read_resets_forbidden_source_streak(Path("/tmp"))
    test_raw_session_artifact_read_does_not_mark_tree_polluted(Path("/tmp"))
    test_backgrounded_mutating_session_command_waits_instead_of_polluting(Path("/tmp"))
    test_backgrounded_mutating_session_clears_after_structured_result(Path("/tmp"))
    test_non_background_mutating_session_command_marks_tree_polluted(Path("/tmp"))
    print("PASS test_destructive_action_guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
