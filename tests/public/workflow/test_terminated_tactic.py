"""Commit, ``-try`` and the compiler read a submitted tactic the same way."""

from __future__ import annotations

import pytest

from core.easycrypt.proof_state_compiler.contracts import StateRef
from core.easycrypt.proof_text import terminated_tactic
from core.easycrypt.session.session_tactic_precheck import precheck_tactic
from workflow.proof_management.types import AgentIntent
from workflow.proof_state_compiler.turn_evidence import (
    compiler_turn_evidence_from_action,
)


@pytest.mark.parametrize(
    ("submitted", "executed"),
    (
        ("move=> x; split", "move=> x; split."),
        ("move=> x; split.", "move=> x; split."),
        ("smt() (* why *)", "smt() (* why *)."),
        # A trailing comment after the final dot is not a sentence of its
        # own: appending a dot there made a sentence the agent never wrote.
        ("move=> x. (* intro *)", "move=> x. (* intro *)"),
        ("rewrite p.`1", "rewrite p.`1."),
        ("  wp  ", "  wp."),
    ),
)
def test_one_termination_rule(submitted: str, executed: str) -> None:
    assert terminated_tactic(submitted) == executed.rstrip()
    outcome = precheck_tactic(submitted, lambda *_: None)
    assert outcome.block_text == executed.rstrip()


def test_compiler_explains_the_tactic_easycrypt_ran() -> None:
    authority = {
        "authority_kind": "event_bound_tactic_execution_result",
        "event_type": "tactic.execution.produced",
        "event_id": "ter-event-1",
        "event_sequence": 3,
        "artifact_ref": "tactic_execution_results/result.json",
        "artifact_hash": "a" * 40,
        "hash_algorithm": "sha1",
        "submitted_tactics": ["move=> x; split"],
        "status": "error",
        "state_changed": False,
        "history_committed": False,
        "structured_error": "[error] cannot apply split",
    }
    evidence = compiler_turn_evidence_from_action(
        action={
            "label": "commit_tactic",
            "outcome_kind": "rejected",
            "proof_state_effect": "unchanged",
            "execution_authority": authority,
        },
        intent=AgentIntent(
            intent="commit_tactic", payload={"tactic": "move=> x; split"},
        ),
        post_state_ref=StateRef(
            session_id="s",
            state_version=1,
            goal_identity="g",
            goal_identity_required=True,
            committed_prefix_identity="b" * 64,
        ),
    )

    assert evidence is not None
    assert evidence.payload.to_dict() == {"tactic": "move=> x; split."}
