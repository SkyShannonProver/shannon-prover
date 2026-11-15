"""The manager names the sentence of a multi-sentence commit that failed.

EasyCrypt's REPL runs a commit sentence by sentence and stops at the first
rejection; the manager rolls the whole commit back. The rejected sentence's
position is EasyCrypt's own fact, carried as ``execution.failed_sentence``.
"""

from __future__ import annotations

import pytest

from core.easycrypt.ec_diagnostics import FailedSentence
from workflow.proof_management.backend_actions import (
    _TacticExecutionResolution,
    agent_observation_for_request,
)
from workflow.proof_management.backend_request import BackendRequest


def _observation(tactic: str, failed_sentence: object | None) -> dict:
    execution = {
        "mode": "commit",
        "state_changed": False,
        "history_committed": False,
        "submitted_tactics": [tactic],
    }
    if failed_sentence is not None:
        execution["failed_sentence"] = failed_sentence
    return agent_observation_for_request(
        BackendRequest.commit("commit_tactic", tactic),
        stdout="",
        stderr="",
        exit_code=0,
        tactic_execution_resolution=_TacticExecutionResolution(
            required=True,
            result={
                "execution": execution,
                "result": {
                    "ok": False,
                    "status": "error",
                    "error": "[error] parse error",
                },
            },
        ),
    )


@pytest.mark.parametrize(
    ("index", "expected"),
    (
        (
            1,
            "EasyCrypt rejected the committed tactic at sentence 1 of 3: "
            "`bad.` The whole commit was rolled back; nothing was committed.",
        ),
        (
            2,
            "EasyCrypt rejected the committed tactic at sentence 2 of 3: "
            "`bad.` Sentence 1 ran before it; the whole commit was rolled "
            "back, so nothing was committed.",
        ),
        (
            3,
            "EasyCrypt rejected the committed tactic at sentence 3 of 3: "
            "`bad.` Sentences 1-2 ran before it; the whole commit was rolled "
            "back, so nothing was committed.",
        ),
    ),
)
def test_rejection_names_the_failed_sentence(index: int, expected: str) -> None:
    observation = _observation(
        "proc. bad. wp.",
        {"index": index, "count": 3, "sentence": "bad."},
    )

    assert observation["result"] == expected
    # The error line stays EasyCrypt's own text.
    assert observation["error_summary"] == "[error] parse error"


def test_long_sentence_is_quoted_on_one_bounded_line() -> None:
    sentence = "rewrite\n  " + " ".join(f"lemma_{n}" for n in range(60)) + "."
    observation = _observation(
        "proc. " + sentence,
        {"index": 2, "count": 2, "sentence": sentence},
    )

    quoted = observation["result"].split("`")[1]
    assert "\n" not in quoted
    assert len(quoted) == 160 and quoted.endswith("…")


@pytest.mark.parametrize(
    "failed_sentence",
    (
        None,
        {},
        {"index": 1, "count": 1, "sentence": "bad."},
        {"index": 3, "count": 2, "sentence": "bad."},
        {"index": 1, "count": 2, "sentence": " "},
        {"index": 1, "count": 2, "sentence": "bad.", "extra": True},
        {"index": True, "count": 2, "sentence": "bad."},
    ),
)
def test_without_one_complete_record_the_old_sentence_stays(
    failed_sentence: object,
) -> None:
    observation = _observation("bad. wp.", failed_sentence)

    assert observation["result"] == "EasyCrypt rejected the committed tactic."


def test_record_round_trips_and_rejects_one_sentence() -> None:
    record = FailedSentence(index=2, count=3, sentence="wp.")
    assert FailedSentence.from_payload(record.to_payload()) == record
    with pytest.raises(ValueError):
        FailedSentence(index=1, count=1, sentence="wp.")
