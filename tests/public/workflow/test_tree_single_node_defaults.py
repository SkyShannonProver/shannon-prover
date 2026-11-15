"""Single-node defaults and the spawn heuristics they switch off."""
from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import pytest

import workflow.tree.supervisor as sup
from workflow.schemas.config import ProverConfig, RunConfig
from workflow.tree.policy import (
    DEFAULT_TREE_INITIAL_PROVERS,
    DEFAULT_TREE_MAX_CONCURRENT,
    TREE_MAX_ACTIVE_NODES,
    cap_tree_max_concurrent,
)


def test_default_topology_is_one_node_and_multi_node_stays_available() -> None:
    assert (DEFAULT_TREE_INITIAL_PROVERS, DEFAULT_TREE_MAX_CONCURRENT) == (1, 1)
    config = ProverConfig()
    assert (config.tree_initial_provers, config.tree_max_concurrent) == (1, 1)
    assert config.timeout_minutes == 30
    assert config.tree_max_depth == 8
    # The default is not the cap: an explicit request is still honoured up to 4.
    assert TREE_MAX_ACTIVE_NODES == 4
    assert cap_tree_max_concurrent(3) == 3
    assert cap_tree_max_concurrent(10) == 4


def test_callers_that_build_a_default_run_config_get_one_node(tmp_path) -> None:
    # project_driver, a bare `python -m workflow.orchestrator --file/--lemma`
    # and a --config file without tree fields all start from RunConfig().
    prover = RunConfig(file="f.ec", lemma="L").prover
    assert (prover.tree_initial_provers, prover.tree_max_concurrent) == (1, 1)
    path = tmp_path / "config.json"
    path.write_text('{"file": "f.ec", "lemma": "L", "prover": {}}', encoding="utf-8")
    loaded = RunConfig.load(path).prover
    assert (loaded.tree_initial_provers, loaded.tree_max_concurrent) == (1, 1)


class _Reached(Exception):
    pass


def _stuck_supervisor(tmp_path, monkeypatch, *, max_concurrent):
    supervisor = sup.NodeSupervisor(
        lambda *_args, **_kwargs: ["worker"],
        str(tmp_path),
        max_concurrent=max_concurrent,
        min_alive_seconds=0,
        stuck_errors=1,
        stuck_idle_seconds=0,
        structural_undo_spawn_delay_seconds=0,
    )
    supervisor.logger = logging.getLogger("test.tree_single_node_defaults")
    tracker = SimpleNamespace(
        stuck_handled=False,
        committed_count=5,
        waiting_on_background_mutation=False,
        last_accept_time=time.time() - 3600,
        errors_since_last_accept=9,
        structural_undo_branch=(["proc."], ["byequiv."]),
        structural_undo_branch_time=time.time() - 3600,
    )
    node = SimpleNamespace(
        node_id="0.0", depth=0, replay_prefix=[],
        spawn_time=time.time() - 3600, tracker=tracker,
    )
    monkeypatch.setattr(supervisor, "_active_nodes", lambda: [node])
    monkeypatch.setattr(supervisor, "_node_in_undo_repair", lambda _node: False)
    monkeypatch.setattr(supervisor, "_in_readonly_backend_window", lambda _node: False)
    reached: list[str] = []

    def stuck_spawn(_node, _reason):
        reached.append("stuck")
        return False

    def structural_spawn(_node):
        reached.append("structural")
        raise _Reached

    monkeypatch.setattr(supervisor, "_try_spawn_from", stuck_spawn)
    monkeypatch.setattr(supervisor, "_read_parent_goal", structural_spawn)
    return supervisor, node, reached


def _tick(supervisor, node):
    supervisor._tick_error_accumulation()
    try:
        supervisor._tick_spawn_on_structural_undo([node])
    except _Reached:
        pass


def test_single_node_runs_never_kill_their_node_to_spawn(tmp_path, monkeypatch) -> None:
    supervisor, node, reached = _stuck_supervisor(tmp_path, monkeypatch, max_concurrent=1)
    _tick(supervisor, node)
    assert reached == []
    assert node.tracker.stuck_handled is False


@pytest.mark.parametrize("max_concurrent", [2, 4])
def test_multi_node_runs_keep_both_spawn_heuristics(
    tmp_path, monkeypatch, max_concurrent,
) -> None:
    supervisor, node, reached = _stuck_supervisor(
        tmp_path, monkeypatch, max_concurrent=max_concurrent,
    )
    _tick(supervisor, node)
    assert reached == ["stuck", "structural"]
