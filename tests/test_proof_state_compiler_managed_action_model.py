"""Contracts for the tool-free stateful Codex micro boundary."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from workflow.validation.proof_state_compiler_managed_action_model import (
    ManagedActionConversation,
)


def _stdout(thread_id: str, tactic: str) -> str:
    return "\n".join(
        json.dumps(item)
        for item in (
            {"type": "thread.started", "thread_id": thread_id},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps(
                        {"intent": "commit_tactic", "tactic": tactic}
                    ),
                },
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 12, "output_tokens": 3},
            },
        )
    )


def test_conversation_starts_once_then_resumes_same_thread(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[list[str], str]] = []
    outputs = iter((_stdout("thread-7", "proc."), _stdout("thread-7", "wp.")))

    def fake_run(command, *, cwd, capture_output, text, timeout):
        calls.append((list(command), cwd))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=next(outputs),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    conversation = ManagedActionConversation(
        model="gpt-test",
        effort="high",
        cwd=tmp_path,
    )
    isolated = conversation._isolated
    first = conversation.next_action("first state")
    second = conversation.next_action("second state")

    assert first["thread_id"] == second["thread_id"] == "thread-7"
    assert first["conversation_turn"] == 1
    assert second["conversation_turn"] == 2
    assert "--ephemeral" not in calls[0][0]
    assert calls[0][0][1:3] == ["exec", "--ignore-user-config"]
    assert "resume" not in calls[0][0]
    assert calls[0][0][calls[0][0].index("--sandbox") + 1] == "read-only"
    assert calls[1][0][1:3] == ["exec", "resume"]
    assert "thread-7" in calls[1][0]
    assert calls[0][1] == calls[1][1] == str(isolated)
    assert isolated.exists()

    conversation.close()
    assert not isolated.exists()


def test_conversation_rejects_thread_identity_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outputs = iter((_stdout("thread-a", "proc."), _stdout("thread-b", "wp.")))

    def fake_run(command, **_kwargs):
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=next(outputs),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with ManagedActionConversation(
        model="gpt-test",
        effort="high",
        cwd=tmp_path,
    ) as conversation:
        assert conversation.next_action("first state")["error"] == ""
        changed = conversation.next_action("second state")

    assert "resumed a different thread" in changed["error"]


def test_conversation_accepts_experiment_specific_system_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(list(command))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=_stdout("thread-route", "proc; auto."),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with ManagedActionConversation(
        model="gpt-test",
        effort="high",
        cwd=tmp_path,
        system_prompt="Choose natural atomic or compound granularity.",
    ) as conversation:
        result = conversation.next_action("current state")

    assert result["tactic"] == "proc; auto."
    assert calls[0][-1] == (
        "Choose natural atomic or compound granularity.\n\ncurrent state"
    )
