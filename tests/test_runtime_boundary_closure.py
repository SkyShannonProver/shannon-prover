"""Permanent gates for the post-terminal runtime boundary closure."""

from __future__ import annotations

import inspect
from dataclasses import fields

from core.easycrypt import (
    session_episode_timeline,
    session_managed_goal_view,
    session_projection,
)
from core.easycrypt.commands.compiler_commands import handle_compiler_input_v2
from core.easycrypt.session_compiler_input import COMPILER_INPUT_SCHEMA_VERSION
from workflow import proof_acceptance, proof_node_resume, session_observer
from workflow.agents import prover
from workflow.proof_management.types import ManagedTurn
from workflow.proof_node_runtime import NodeMemory
from workflow.proof_state_compiler.service import ProofStateCompilerService
from workflow.tree.result import TreeRunResult


def test_existing_typed_boundaries_carry_proof_and_session_scope() -> None:
    assert "committed_tactics" in {item.name for item in fields(ManagedTurn)}
    assert "managed_session_dirs" in {item.name for item in fields(TreeRunResult)}


def test_node_memory_does_not_recover_history_from_minimal_view() -> None:
    source = inspect.getsource(NodeMemory.write_latest_followup)
    assert 'workspace_view.get("proof_so_far")' not in source
    assert "render_committed_proof_markdown(committed_tactics)" in source


def test_prover_has_no_mtime_session_selection_or_global_archive_scan() -> None:
    assert not hasattr(prover, "_find_latest_session_id")
    archive_source = inspect.getsource(prover._archive_ec_session_dirs)
    assert '.glob(".ec_session_*"' not in archive_source
    assert "session_dirs" in archive_source


def test_resume_capsules_require_an_explicit_managed_session_set() -> None:
    source = inspect.getsource(proof_node_resume.create_resume_capsules)
    assert '.glob(".ec_session_prover_tree_*"' not in source
    assert "session_dirs: Iterable[Path]" in source


def test_acceptance_does_not_resummarize_close_from_raw_events() -> None:
    source = inspect.getsource(proof_acceptance)
    assert "read_event_file" not in source
    assert "summarize_events" not in source
    assert "has_candidate_closed" not in source
    assert "projection.goals_discharged" in source
    assert "candidate_closed" not in source


def test_upper_lifecycle_vocabulary_is_not_candidate_closed() -> None:
    timeline_source = inspect.getsource(session_episode_timeline)
    assert '"candidate_closed"' not in timeline_source
    assert "session_completion_candidate" in timeline_source


def test_projection_owns_qed_committed_for_all_adapters() -> None:
    assert hasattr(session_projection.ProofStateProjection, "qed_committed")
    adapter_sources = (
        inspect.getsource(proof_acceptance),
        inspect.getsource(session_observer.observe_session),
        inspect.getsource(session_managed_goal_view.build_managed_goal_view),
    )
    assert all("projection.qed_committed" in source for source in adapter_sources)
    assert all(
        "projection.goals_discharged and projection.history.has_qed"
        not in source
        for source in adapter_sources
    )


def test_observer_copies_semantics_from_one_projection_read() -> None:
    source = inspect.getsource(session_observer.observe_session)
    assert "read_event_file" not in source
    assert "_read_history_tactics" not in source
    assert "projection.history.tactics" in source
    assert "projection.source_events" in source


def test_compiler_input_is_state_only_and_resources_have_a_distinct_call() -> None:
    assert COMPILER_INPUT_SCHEMA_VERSION == 5
    input_source = inspect.getsource(handle_compiler_input_v2)
    assert "load_requested_declarations" not in input_source
    service_source = inspect.getsource(ProofStateCompilerService.compile_current_state)
    assert "load_compiler_resources_v2" in service_source
    assert "source event remains only planning provenance" not in service_source
