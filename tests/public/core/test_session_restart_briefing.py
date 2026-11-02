"""The restart briefing counts and saves EasyCrypt commands, not lines."""
from __future__ import annotations

import pytest

from core.easycrypt.session.session_runtime import Session


@pytest.mark.parametrize("history, commands", [
    ("wp; skip. qed.\n", ["wp; skip.", "qed."]),
    ("move=> x\n  y.\n", ["move=> x\n  y."]),
    ("(* note *)\nproc. auto.\n", ["(* note *)\nproc.", "auto."]),
])
def test_restart_briefing_lists_committed_commands(tmp_path, monkeypatch, history, commands) -> None:
    monkeypatch.setattr(Session, "_invalidate_daemon", lambda self: None)
    session = Session(tmp_path / "sess")
    session.history.write_text(history, encoding="utf-8")

    briefing = session.start()

    assert briefing["discarded_tactic_count"] == len(commands)
    assert briefing["replay_chain"] == " ".join(commands)
    checkpoint = tmp_path / "sess.pre_restart.txt"
    assert checkpoint.read_text(encoding="utf-8") == "\n".join(commands) + "\n"
    assert session.history.read_text(encoding="utf-8") == ""
