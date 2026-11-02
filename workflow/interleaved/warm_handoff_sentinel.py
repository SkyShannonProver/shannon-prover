"""No-model live sentinel for the outer-to-Shannon warm-handoff boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflow.interleaved.runtime import ProjectContext
from workflow.interleaved.warm_handoff import (
    _proof_body,
    prepare_outer_proof_handoff,
)


def run_warm_handoff_sentinel(ctx: ProjectContext, *, run_dir: Path) -> dict[str, Any]:
    """Replay one multiline command through both real manager preparations."""

    sentinel_lemma = ctx.project.warm_handoff_sentinel_lemma
    sentinel_command = ctx.project.warm_handoff_sentinel_command
    if not sentinel_lemma:
        return {"required": False, "passed": True}

    from core.easycrypt.ec_daemon_client import default_socket_path
    from workflow.agents.ec_services import _shutdown_ec_daemon

    root = ctx.root
    run_dir = run_dir.resolve()
    if not run_dir.is_relative_to(root):
        raise ValueError("warm-handoff sentinel run directory must be in the repo")
    sentinel_dir = run_dir / "warm_handoff_preflight"
    sentinel_dir.mkdir(parents=True, exist_ok=False)

    source = ctx.target.read_text(encoding="utf-8")
    # Splice by position: an identical body, such as another lemma's admit
    # shell, may occur earlier in the file.
    _, (body_start, body_end) = _proof_body(source, sentinel_lemma)
    candidate_body = f"\n{sentinel_command}\n\nadmit.\n"
    candidate = source[:body_start] + candidate_body + source[body_end:]
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
            ctx,
            run_rel=sentinel_dir.relative_to(root),
            lemma=sentinel_lemma,
            strategy_note=str(note_path.relative_to(root)),
            candidate_source=str(candidate_path.relative_to(root)),
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
    if commands != [sentinel_command]:
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
        "lemma": sentinel_lemma,
        "accepted_command_count": 1,
        "committed_spine_count": 1,
        "boundary_goal_hash": boundary["goal_hash"],
        "manifest": str(manifest_path.relative_to(root)),
    }
