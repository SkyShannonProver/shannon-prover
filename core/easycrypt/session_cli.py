#!/usr/bin/env python3
"""Private CLI boundary for the current manager-owned EasyCrypt runtime.

This command is backend transport, not an agent-facing inspect toolbox.  It
exposes only proof-session transactions, bounded compiler/native adapters, the
minimal managed workspace, audit timeline, and developer verification.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.easycrypt.session.session_runtime import Session


@contextmanager
def _session_action_lock(session_dir: Path):
    """Serialize processes sharing one append-only session event stream."""

    import fcntl

    resolved = session_dir.expanduser().resolve()
    lock_path = resolved.with_name(f"{resolved.name}.cli.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Current manager-owned EasyCrypt backend transport."
    )
    parser.add_argument("-d", "--dir", default=None)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("-start", action="store_true")
    actions.add_argument(
        "-tactic-exec", choices=("commit", "commit_chain", "undo")
    )
    actions.add_argument("-try", action="store_true", dest="try_tactic")
    actions.add_argument("-managed-goal-view", action="store_true")
    actions.add_argument("-episode-view", action="store_true")
    actions.add_argument("-compiler-input-v2", action="store_true")
    actions.add_argument("-compiler-resource-load-v2", action="store_true")
    actions.add_argument("-native-semantic-batch-json", action="store_true")
    actions.add_argument("-native-state-projection-json", action="store_true")
    actions.add_argument("-verify", dest="verify_lemma")

    parser.add_argument("--force-restart", action="store_true")
    parser.add_argument("-c", "--command")
    parser.add_argument("--from-file")
    parser.add_argument("-f", "--file")
    parser.add_argument("-lemma")
    parser.add_argument("-I", "--include-dir", action="append", default=[], dest="include_dirs")
    parser.add_argument("-deltas-only", action="store_true")
    parser.add_argument("--keep-on-fail", action="store_true")
    parser.add_argument("--manager-state-version", type=int, default=None)
    parser.add_argument("--compiler-resource-load-request-json", default="{}")
    parser.add_argument("--native-semantic-batch-request-json", default="{}")
    parser.add_argument("--native-state-projection-request-json", default="{}")
    return parser


def _resolve_session_dir(parser: argparse.ArgumentParser, args) -> Path:
    environment_dir = os.environ.get("EC_SESSION_DIR", "").strip()
    if args.dir and environment_dir:
        if Path(args.dir).resolve() != Path(environment_dir).resolve():
            parser.error("-d does not match manager-owned EC_SESSION_DIR")
    raw = args.dir or environment_dir or ".easycrypt_session"
    sanitized = re.sub(r"[^a-zA-Z0-9_./-]", "_", raw)
    if sanitized != raw:
        sys.stderr.write(f"[session_cli] sanitized session dir {raw!r}\n")
    return Path(sanitized)


def _tool_payload(session: Session, args, name: str, mutates: bool) -> dict:
    return {
        "name": name,
        "mutates_proof_state": mutates,
        "session_dir": str(session.dir.resolve()),
        "file": args.file,
        "lemma": args.lemma,
        "from_file": args.from_file,
        "has_command": bool(args.command),
    }


def _run_action(
    session: Session,
    args,
    name: str,
    handler: Callable,
    *,
    mutates: bool,
) -> int:
    with _session_action_lock(session.dir):
        payload = _tool_payload(session, args, name, mutates)
        if name != "start":
            session.emit_event("tool.called", payload)
        try:
            result = handler(session, args)
        except Exception as exc:
            session.emit_error_event(
                "error.raised", exc, {"phase": "cli_action", "action": name}
            )
            if name != "start":
                session.emit_event(
                    "tool.result", {**payload, "exit_code": 1, "status": "failed"}
                )
            raise
        if name == "start":
            session.emit_event("tool.called", {**payload, "logged_after": True})
        session.emit_event(
            "tool.result",
            {
                **payload,
                "exit_code": result,
                "status": "ok" if result == 0 else "failed",
            },
        )
        return result


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    session = Session(_resolve_session_dir(parser, args), args.include_dirs)

    if args.start:
        from core.easycrypt.commands.session_commands import handle_start

        return _run_action(session, args, "start", handle_start, mutates=True)
    if args.tactic_exec:
        from core.easycrypt.commands.commit_commands import handle_tactic_exec

        name = args.tactic_exec
        return _run_action(session, args, name, handle_tactic_exec, mutates=True)
    if args.try_tactic:
        from core.easycrypt.commands.commit_commands import handle_try

        return _run_action(session, args, "try", handle_try, mutates=False)
    if args.managed_goal_view:
        from core.easycrypt.commands.session_commands import handle_managed_goal_view

        return _run_action(
            session, args, "managed-goal-view", handle_managed_goal_view, mutates=False
        )
    if args.episode_view:
        from core.easycrypt.commands.session_commands import handle_episode_view

        return _run_action(session, args, "episode-view", handle_episode_view, mutates=False)
    if args.compiler_input_v2:
        from core.easycrypt.commands.compiler_commands import handle_compiler_input_v2

        return _run_action(
            session, args, "compiler-input-v2", handle_compiler_input_v2, mutates=False
        )
    if args.compiler_resource_load_v2:
        from core.easycrypt.commands.compiler_commands import handle_compiler_resource_load_v2

        return _run_action(
            session,
            args,
            "compiler-resource-load-v2",
            handle_compiler_resource_load_v2,
            mutates=False,
        )
    if args.native_semantic_batch_json:
        from core.easycrypt.commands.compiler_commands import handle_native_semantic_batch_json

        return _run_action(
            session, args, "native-semantic-batch", handle_native_semantic_batch_json, mutates=False
        )
    if args.native_state_projection_json:
        from core.easycrypt.commands.compiler_commands import handle_native_state_projection_json

        return _run_action(
            session, args, "native-state-projection", handle_native_state_projection_json, mutates=False
        )
    if args.verify_lemma:
        from core.easycrypt.commands.validation_commands import handle_verify_lemma

        return _run_action(session, args, "verify", handle_verify_lemma, mutates=False)
    raise AssertionError("unreachable action dispatch")


if __name__ == "__main__":
    raise SystemExit(main())
