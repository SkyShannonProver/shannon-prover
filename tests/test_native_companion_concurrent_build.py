"""Concurrent sessions in one checkout must not break the companion build.

Every native semantic batch and typed-state projection first runs
``dune build`` in the shared companion source tree.  dune refuses to start
while another instance holds that build directory, so without serialization
concurrent proof nodes in one checkout intermittently lose their native
results and the compiler silently abstains for that turn.
"""

from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from core.easycrypt.ec_runtime_identity import discover_easycrypt_runtime_identity


WORKERS = 6
ROUNDS = 3


def _build(start: object) -> str:
    from core.easycrypt.native_semantics.companion import (
        build_and_identify_companion,
    )

    start.wait()
    try:
        build_and_identify_companion(
            "native_semantic_adapter",
            discover_easycrypt_runtime_identity(),
        )
    except Exception as exc:  # reported, then asserted on below
        return f"{type(exc).__name__}: {exc}"
    return ""


def test_concurrent_companion_builds_all_succeed() -> None:
    context = multiprocessing.get_context("spawn")
    with context.Manager() as manager, ProcessPoolExecutor(
        max_workers=WORKERS, mp_context=context
    ) as pool:
        failures = []
        for _round in range(ROUNDS):
            start = manager.Event()
            futures = [pool.submit(_build, start) for _ in range(WORKERS)]
            start.set()
            failures.extend(item for item in (f.result() for f in futures) if item)
    assert failures == []
