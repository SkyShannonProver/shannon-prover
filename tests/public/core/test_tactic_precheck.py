"""The commit precheck must commit exactly the tactic that ``-try`` checks."""
from __future__ import annotations

import pytest

from core.easycrypt.session.session_tactic_precheck import precheck_tactic


def _precheck(tactic: str):
    events: list[tuple[str, dict]] = []
    outcome = precheck_tactic(tactic, lambda kind, payload: events.append((kind, payload)))
    return outcome, events


@pytest.mark.parametrize("tactic", [
    "elim: s => [|head tail ih].",
    "case: l => [|x xs] /=.",
    "move=> [|grep sed] //.",
    "have H: a /\\!b.",
    "rewrite -!foo.",
])
def test_valid_tactics_are_committed_verbatim(tactic: str) -> None:
    outcome, events = _precheck(tactic)

    assert outcome.refusal is None
    assert outcome.block_text == tactic
    assert events == []


def test_commit_and_try_agree_on_the_submitted_text() -> None:
    # ``Session.try_speculative`` strips the text and terminates it with ``.``;
    # the commit path must produce the same sentence.
    tactic = "  elim: s => [|head tail ih]  "
    outcome, _ = _precheck(tactic)

    assert outcome.block_text.strip() == tactic.strip() + "."
