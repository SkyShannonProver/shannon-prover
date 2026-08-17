"""Single owner of preregistered block-parallel suite semantics."""
from __future__ import annotations

from typing import Any, Mapping


def select_parallel_waves(
    suite: Mapping[str, Any],
    targets: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Validate and project the exact waves for the selected target set."""

    contract = suite.get("parallel_execution")
    if not isinstance(contract, Mapping):
        raise ValueError("suite has no parallel_execution contract")
    if contract.get("mode") != "target_block_waves":
        raise ValueError("parallel_execution.mode must be target_block_waves")
    if contract.get("within_block") != "profile_order_sequential":
        raise ValueError(
            "parallel_execution.within_block must be profile_order_sequential"
        )
    if contract.get("wave_barrier") is not True:
        raise ValueError("parallel_execution.wave_barrier must be true")
    width = int(contract.get("max_concurrent_blocks") or 0)
    if width < 1:
        raise ValueError("max_concurrent_blocks must be positive")
    configured = contract.get("waves")
    if not isinstance(configured, list) or not configured:
        raise ValueError("parallel_execution.waves must be a nonempty list")
    target_by_id = {str(item.get("id") or ""): item for item in targets}
    seen: list[str] = []
    waves: list[list[dict[str, Any]]] = []
    for raw_wave in configured:
        if not isinstance(raw_wave, list) or not raw_wave:
            raise ValueError("every parallel wave must be a nonempty list")
        if not all(isinstance(item, str) and item for item in raw_wave):
            raise ValueError("parallel wave target IDs must be nonempty strings")
        selected = [target_by_id[item] for item in raw_wave if item in target_by_id]
        if len(selected) > width:
            raise ValueError("parallel wave exceeds max_concurrent_blocks")
        if selected:
            waves.append(selected)
            seen.extend(str(item.get("id") or "") for item in selected)
    expected = [str(item.get("id") or "") for item in targets]
    if seen != expected:
        raise ValueError(
            "parallel waves must mention every selected target exactly once "
            "and preserve suite target order"
        )
    return waves


def parallelization_record(
    suite: Mapping[str, Any],
    waves: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """Return the manifest projection of the validated parallel contract."""

    contract = dict(suite.get("parallel_execution") or {})
    return {
        "mode": contract.get("mode"),
        "within_block": contract.get("within_block"),
        "wave_barrier": contract.get("wave_barrier"),
        "max_concurrent_blocks": contract.get("max_concurrent_blocks"),
        "waves": [
            [str(target.get("id") or "") for target in wave] for wave in waves
        ],
    }


def expected_parallelization(
    suite: Mapping[str, Any],
    targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate once and return the canonical evaluator expectation."""

    return parallelization_record(suite, select_parallel_waves(suite, targets))
