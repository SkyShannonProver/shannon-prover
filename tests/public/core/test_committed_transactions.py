"""Shared history boundary regressions, independent of the outer product."""
import pytest

from core.easycrypt.committed_history import (
    flatten_committed_transactions,
    read_committed_commands,
    read_committed_tactics,
    read_committed_transactions,
)


def test_multiline_commands_retain_manager_transaction(tmp_path):
    block = "move=> x; split.\n+ trivial.\n+ split."
    (tmp_path / "history.ec").write_text(block + "\n")
    (tmp_path / "steps.log").write_text("3\n")
    assert read_committed_transactions(tmp_path) == [block]
    assert read_committed_tactics(tmp_path) == read_committed_commands(tmp_path)
    assert flatten_committed_transactions([block]) == read_committed_commands(tmp_path)


@pytest.mark.parametrize("ledger", ["", "0\n", "-1\n", "2\n", "invalid\n"])
def test_present_invalid_transaction_ledger_fails_closed(tmp_path, ledger):
    (tmp_path / "history.ec").write_text("trivial.\n")
    (tmp_path / "steps.log").write_text(ledger)
    assert read_committed_transactions(tmp_path) == []


def test_history_without_ledger_retains_command_compatibility(tmp_path):
    (tmp_path / "history.ec").write_text("trivial. qed.\n")
    assert read_committed_transactions(tmp_path) == ["trivial.", "qed."]
