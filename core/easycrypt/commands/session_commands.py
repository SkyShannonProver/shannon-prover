"""Current managed-session lifecycle and read-only workspace commands."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def handle_start(session, args) -> int:
    """Create a fresh manager-owned EasyCrypt session."""

    from core.easycrypt.committed_history import read_committed_tactics
    from core.easycrypt.ec_runtime_identity import discover_easycrypt_runtime_identity

    meta_path = session.dir / "session_meta.json"
    previous_restart_count = 0
    if meta_path.exists():
        try:
            previous_restart_count = int(
                json.loads(meta_path.read_text()).get("restart_count", 0)
            )
        except Exception:
            previous_restart_count = 0

    committed = read_committed_tactics(session.dir)
    if committed and not getattr(args, "force_restart", False):
        sys.stderr.write(
            "Refusing to discard a non-empty managed session without "
            "--force-restart.\n"
        )
        return 2

    briefing = session.start()
    runtime_identity = discover_easycrypt_runtime_identity()
    resolved_file = str(Path(args.file).resolve()) if args.file else None
    session.emit_event(
        "session.started",
        {
            "file": resolved_file,
            "lemma": args.lemma,
            "include_dirs": list(args.include_dirs or []),
            "discarded_tactic_count": briefing.get("discarded_tactic_count", 0),
            "pre_restart_checkpoint_path": briefing.get(
                "pre_restart_checkpoint_path"
            ),
            "restart_count": previous_restart_count + 1,
            "easycrypt_build_id": runtime_identity.build_id,
            "easycrypt_runtime_identity_sha256": (
                runtime_identity.semantic_identity_sha256
            ),
        },
    )

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"File not found: {args.file}\n")
            return 1
        if args.lemma:
            from core.easycrypt.lemma_extract import extract_lemma

            try:
                source = extract_lemma(file_path, args.lemma, open_proof=True)
            except ValueError as exc:
                sys.stderr.write(f"Could not extract lemma {args.lemma}: {exc}\n")
                return 1
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", args.lemma)
            extracted_path = session.dir / f"extracted_{safe_name}.ec"
            extracted_path.write_text(source, encoding="utf-8")
            session.load_context(extracted_path)
        else:
            session.load_context(file_path)
        session._run_ec(session.history, session.curr)
        session._compress_curr_inplace()

    metadata = {
        "file": resolved_file,
        "lemma": args.lemma,
        "timestamp": datetime.now().isoformat(),
        "restart_count": previous_restart_count + 1,
        "easycrypt_runtime_identity": runtime_identity.to_payload(),
    }
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    sys.stdout.write(
        json.dumps({"kind": "managed_session_start_ack", "ok": True}) + "\n"
    )
    return 0


def handle_managed_goal_view(session, args) -> int:
    """Emit the narrow event-bound workspace used by L1 and compiler V2."""

    del args
    from core.easycrypt.session.session_managed_goal_view import (
        build_managed_goal_view,
        record_managed_goal_view,
    )

    view = build_managed_goal_view(
        session.dir, live_tool_name="managed-goal-view"
    )
    record_managed_goal_view(session, view)
    sys.stdout.write(json.dumps(view, indent=2) + "\n")
    return 0


def handle_episode_view(session, args) -> int:
    """Emit the event-ordered session timeline used for audit."""

    del args
    from core.easycrypt.session.session_episode_timeline import (
        build_session_episode_timeline,
        record_session_episode_timeline,
    )

    timeline = build_session_episode_timeline(session.dir)
    record_session_episode_timeline(session, timeline)
    sys.stdout.write(json.dumps(timeline, indent=2, sort_keys=True) + "\n")
    return 0
