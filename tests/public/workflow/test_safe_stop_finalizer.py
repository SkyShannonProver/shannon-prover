"""No-model sentinel for non-replaying safe-stop handback."""

from __future__ import annotations

import json
from pathlib import Path


from workflow.node.safe_stop_finalizer import finalize_safe_stop_checkpoint


def test_safe_stop_without_checkpoint_returns_prefix_immediately(tmp_path: Path) -> None:
    lemma = "safe_stop_replay_checkpoint"
    source = tmp_path / "SafeStopReplay.ec"
    source.write_text(
        "require import AllCore.\n\n"
        f"lemma {lemma} : forall (x : int), x = x.\n"
        "proof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    result = finalize_safe_stop_checkpoint(
        run_dir=run_dir,
        target_file=str(source),
        lemma=lemma,
        committed_prefix=("move=> x.",),
        trigger="wall_clock_timeout",
    )

    assert result.completed is True
    assert result.method == "accepted_prefix_only"
    assert result.tactic_count == 1
    assert result.capsule_paths == ()
    assert (run_dir / "partial_proof_prefix.ec").read_text(
        encoding="utf-8"
    ) == "move=> x.\n"
    audit = json.loads(
        (run_dir / "safe_stop_finalization.json").read_text(encoding="utf-8")
    )
    assert audit["completed"] is True
    assert audit["method"] == "accepted_prefix_only"


def test_safe_stop_records_a_bullet_prefix_without_replaying_it(
    tmp_path: Path,
) -> None:
    lemma = "safe_stop_atomic_bullet_checkpoint"
    source = tmp_path / "SafeStopAtomicBullet.ec"
    source.write_text(
        "require import AllCore.\n\n"
        f"lemma {lemma} : forall (x : int), x = x /\\ x = x /\\ x = x.\n"
        "proof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    prefix = ("move=> x; split.", "+ trivial.", "+ split.")

    result = finalize_safe_stop_checkpoint(
        run_dir=run_dir,
        target_file=str(source),
        lemma=lemma,
        committed_prefix=prefix,
        trigger="wall_clock_timeout",
    )

    assert result.completed is True
    assert result.method == "accepted_prefix_only"
    assert result.tactic_count == 3
    assert result.capsule_paths == ()
    assert (run_dir / "partial_proof_prefix.ec").read_text(
        encoding="utf-8"
    ) == "\n".join(prefix) + "\n"
