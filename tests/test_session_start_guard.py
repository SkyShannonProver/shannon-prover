from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.easycrypt.commands.session_commands import handle_start
from core.easycrypt.session_runtime import Session


def _args(tmp_path: Path, *, force_restart: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        file=str(tmp_path / "dummy.ec"),
        lemma="L",
        include_dirs=[],
        force_restart=force_restart,
    )


def test_pinned_prover_start_refuses_to_discard_committed_tactics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session_dir = tmp_path / ".ec_session_prover_tree_0_0"
    session = Session(session_dir)
    session.history.write_text("proc.\nwp.\n", encoding="utf-8")
    (tmp_path / "dummy.ec").write_text("lemma L : true. proof. trivial. qed.\n")

    monkeypatch.setenv("EC_SESSION_DIR", str(session_dir))

    assert handle_start(session, _args(tmp_path)) == 2
    assert session.history.read_text(encoding="utf-8") == "proc.\nwp.\n"

