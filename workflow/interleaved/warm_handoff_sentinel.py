"""No-model live sentinel for the outer-to-Shannon warm-handoff boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflow.interleaved.warm_handoff import (
    TARGET,
    _proof_body,
    prepare_outer_proof_handoff,
)


from workflow.interleaved.runtime import load_runtime_settings


_SETTINGS = load_runtime_settings()
ROOT = _SETTINGS.root
SENTINEL_LEMMA = _SETTINGS.project.warm_handoff_sentinel_lemma
SENTINEL_COMMAND = _SETTINGS.project.warm_handoff_sentinel_command


def run_warm_handoff_sentinel(*, run_dir: Path) -> dict[str, Any]:
    """Replay one multiline command through both real manager preparations."""

    if not SENTINEL_LEMMA:
        return {"required": False, "passed": True}

    from core.easycrypt.ec_daemon_client import default_socket_path
    from workflow.agents.ec_services import _shutdown_ec_daemon

    run_dir = run_dir.resolve()
    if not run_dir.is_relative_to(ROOT):
        raise ValueError("warm-handoff sentinel run directory must be in the repo")
    sentinel_dir = run_dir / "warm_handoff_preflight"
    sentinel_dir.mkdir(parents=True, exist_ok=False)

    target = ROOT / TARGET
    source = target.read_text(encoding="utf-8")
    original_body, _ = _proof_body(source, SENTINEL_LEMMA)
    candidate_body = f"\n{SENTINEL_COMMAND}\n\nadmit.\n"
    candidate = source.replace(original_body, candidate_body, 1)
    if candidate == source:
        raise RuntimeError("warm-handoff sentinel could not build its candidate")

    candidate_path = sentinel_dir / "candidate.ec"
    note_path = sentinel_dir / "strategy.md"
    candidate_path.write_text(candidate, encoding="utf-8")
    note_path.write_text(
        "Continue from the certified open goal; this is a no-model preflight.\n",
        encoding="utf-8",
    )
    socket_path = default_socket_path()
    try:
        manifest_path = prepare_outer_proof_handoff(
            root=ROOT,
            run_rel=sentinel_dir.relative_to(ROOT),
            lemma=SENTINEL_LEMMA,
            strategy_note=str(note_path.relative_to(ROOT)),
            candidate_source=str(candidate_path.relative_to(ROOT)),
        )
    finally:
        # The sentinel runs before prover.run assigns a per-run socket.  It
        # therefore owns the checkout-scoped fallback daemon used by this
        # bootstrap and must stop it on both success and failure.
        _shutdown_ec_daemon(
            reason="warm-handoff sentinel finished",
            socket_path=socket_path,
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replay = manifest.get("replay") or {}
    boundary = manifest.get("boundary") or {}
    commands = replay.get("commands") or []
    if commands != [SENTINEL_COMMAND]:
        raise RuntimeError("warm-handoff sentinel changed the multiline command")
    if replay.get("accepted_command_count") != 1:
        raise RuntimeError("warm-handoff sentinel did not certify its command")
    if replay.get("committed_spine_count") != 1:
        raise RuntimeError(
            "warm-handoff sentinel split one multiline command in the proof spine"
        )
    if replay.get("committed_spine_sha256") != replay.get("commands_sha256"):
        raise RuntimeError(
            "warm-handoff sentinel changed the multiline committed proof spine"
        )
    if boundary.get("goal_identity_required") is not True or not boundary.get(
        "goal_hash"
    ):
        raise RuntimeError("warm-handoff sentinel did not preserve an open goal")
    return {
        "passed": True,
        "lemma": SENTINEL_LEMMA,
        "accepted_command_count": 1,
        "committed_spine_count": 1,
        "boundary_goal_hash": boundary["goal_hash"],
        "manifest": str(manifest_path.relative_to(ROOT)),
    }
