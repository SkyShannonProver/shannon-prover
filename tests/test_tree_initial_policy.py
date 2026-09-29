from __future__ import annotations

import inspect

from workflow import orchestrator
from workflow.agents import prover
from workflow.tree.supervisor import run_tree_prover
from workflow.schemas.config import ProverConfig
from workflow.tree.policy import DEFAULT_TREE_INITIAL_PROVERS


def test_tree_initial_root_defaults_are_consistent() -> None:
    assert DEFAULT_TREE_INITIAL_PROVERS == 2
    assert ProverConfig().tree_initial_provers == DEFAULT_TREE_INITIAL_PROVERS
    # prover.run no longer carries per-knob keyword defaults that could drift
    # from the schema: all tree/model/budget knobs travel in one ProverConfig.
    run_params = inspect.signature(prover.run).parameters
    assert "prover" in run_params
    assert not any(name.startswith("tree_") for name in run_params)
    tree_default = inspect.signature(run_tree_prover).parameters["initial_provers"].default
    assert tree_default == DEFAULT_TREE_INITIAL_PROVERS


def test_prove_mode_and_count_are_config_driven_not_difficulty_driven() -> None:
    # The orchestrator no longer branches search topology on plan difficulty:
    # the old ``_prove_mode_and_count_for_difficulty`` helper was removed in
    # favour of reading ``config.prover.mode`` / ``config.prover.tree_initial_provers``
    # directly (see orchestrator.run_orchestrator, "Adaptive mode + prover count").
    # Difficulty now only feeds the progress display, not the topology choice.
    assert not hasattr(orchestrator, "_prove_mode_and_count_for_difficulty")

    # Defaults still resolve to the two-root tree, independent of any difficulty.
    config = ProverConfig()
    assert config.mode == "tree"
    assert config.tree_initial_provers == DEFAULT_TREE_INITIAL_PROVERS
