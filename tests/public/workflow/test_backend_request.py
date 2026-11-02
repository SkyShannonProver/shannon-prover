"""The manager states each backend call once, as a typed request.

Command lines, authority contracts and the read-only classification derive
from the request kind; nothing is rediscovered from argv.
"""
from __future__ import annotations

import pytest


from workflow.proof_management.backend_actions import (
    _tactic_execution_request_contract,
)
from workflow.proof_management.backend_request import BackendRequest


_START = BackendRequest.start(
    "undo_to_checkpoint",
    file_path="eval/examples/A.ec",
    include_dirs=["eval/examples", "easycrypt-src/theories"],
    lemma_name="L",
    force_restart=True,
)


@pytest.mark.parametrize(
    "request_, args, mutates, view",
    (
        (
            _START,
            (
                "-start", "--force-restart", "-f", "eval/examples/A.ec",
                "-I", "eval/examples", "-I", "easycrypt-src/theories",
                "-lemma", "L",
            ),
            True,
            None,
        ),
        (
            BackendRequest.commit("commit_tactic", "wp."),
            ("-tactic-exec", "commit", "-c", "wp."),
            True,
            None,
        ),
        (BackendRequest.undo("undo_last_step"), ("-tactic-exec", "undo"), True, None),
        (BackendRequest.try_tactic("smt()."), ("-try", "-c", "smt()."), False, None),
        (
            BackendRequest.managed_goal_view(),
            ("-managed-goal-view",),
            False,
            ("managed-goal-view", "prover.workspace_view.produced"),
        ),
        (
            BackendRequest.compiler_input(4),
            ("-compiler-input-v2", "--manager-state-version", "4"),
            False,
            ("compiler-input-v2", "compiler.input.produced"),
        ),
        (
            BackendRequest.compiler_resource_load(4, {"b": 1, "a": [2]}),
            (
                "-compiler-resource-load-v2", "--manager-state-version", "4",
                "--compiler-resource-load-request-json", '{"a":[2],"b":1}',
            ),
            False,
            ("compiler-resource-load-v2", "compiler.resources.loaded"),
        ),
        (
            BackendRequest.native_semantic_batch(4, {"batch_id": "b"}),
            (
                "-native-semantic-batch-json", "--manager-state-version", "4",
                "--native-semantic-batch-request-json", '{"batch_id":"b"}',
            ),
            False,
            ("native-semantic-batch", "native.semantic.batch.produced"),
        ),
        (
            BackendRequest.native_state_projection(4, {"request_id": "s"}),
            (
                "-native-state-projection-json", "--manager-state-version", "4",
                "--native-state-projection-request-json", '{"request_id":"s"}',
            ),
            False,
            ("native-state-projection", "native.state.produced"),
        ),
    ),
    ids=lambda value: value.label if isinstance(value, BackendRequest) else "",
)
def test_request_kind_fixes_argv_and_contracts(
    request_: BackendRequest,
    args: tuple[str, ...],
    mutates: bool,
    view: tuple[str, str] | None,
) -> None:
    assert request_.args == args
    assert request_.mutates_proof_state is mutates
    assert request_.read_only is (not mutates)
    assert request_.authoritative_view == view
    assert request_.requires_tactic_preflight is (request_.kind == "try")
    assert request_.requires_tactic_execution_result is (
        request_.kind in {"commit", "undo"}
    )


def test_tactic_execution_contract_binds_the_exact_request() -> None:
    assert _tactic_execution_request_contract(
        BackendRequest.commit("commit_tactic", "  wp.  ")
    ) == ("commit", "commit", "commit", ("wp.",), False)
    assert _tactic_execution_request_contract(
        BackendRequest.undo("undo_last_step")
    ) == ("undo", "undo", "undo", (), False)
    assert _tactic_execution_request_contract(
        BackendRequest.commit_chain("commit_tactic", "proc. bad.")
    ) == ("commit_chain", "commit_chain", "commit_chain", ("proc.", "bad."), True)
    assert _tactic_execution_request_contract(
        BackendRequest.commit("commit_tactic", "  ")
    ) == ("commit", "commit", "commit", None, False)
    assert _tactic_execution_request_contract(_START) is None
    assert _tactic_execution_request_contract(BackendRequest.try_tactic("wp.")) is None


@pytest.mark.parametrize(
    "tactic", ("-start", "-tactic-exec", "-managed-goal-view", "-compiler-input-v2")
)
def test_tactic_text_never_changes_the_call_kind(tactic: str) -> None:
    preflight = BackendRequest.try_tactic(tactic)
    commit = BackendRequest.commit("commit_tactic", tactic)

    assert preflight.read_only and preflight.requires_tactic_preflight
    assert not preflight.requires_tactic_execution_result
    assert preflight.authoritative_view is None
    assert commit.mutates_proof_state and commit.authoritative_view is None
