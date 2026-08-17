"""Worker process for one long-lived managed prover node.

The orchestrator still owns tree strategy and process supervision.  This
worker hosts a ``ProofNodeRuntime``: one ``ProofNodeManager`` plus one
long-lived agent session. Claude Code or OpenAI Codex submits proof intents through the
per-node ``submit_proof_intent`` MCP tool; shell submit scripts and runtime
bridge clients are not agent-facing. The worker no longer launches a new
agent once per proof turn.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow.proof_node_runtime import (
    PROJECT_ROOT,
    ProofNodeRuntime,
)
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--bootstrap-file", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--lemma", required=True)
    parser.add_argument("--include-dir", required=True)
    parser.add_argument("--session-tag", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--agent-backend", choices=["claude", "codex"], default="codex"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", default="high")
    parser.add_argument("--max-turns", type=int, default=1000)
    parser.add_argument("--surface-profile", dest="surface_profile", default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
        bootstrap = _read_json(Path(args.bootstrap_file))
        runtime = ProofNodeRuntime(
            prompt=prompt,
            bootstrap=bootstrap,
            file_path=args.file,
            lemma_name=args.lemma,
            include_dir=args.include_dir,
            session_tag=args.session_tag,
            node_id=args.node_id,
            run_dir=Path(args.run_dir),
            agent_backend=args.agent_backend,
            model=args.model,
            effort=args.effort,
            max_turns=args.max_turns,
            surface_profile=args.surface_profile or None,
            project_root=PROJECT_ROOT,
            emit=_emit,
        )
        result = runtime.run()
    except Exception as exc:
        _emit_final(
            "MANAGER WORKER ERROR: long-lived proof node runtime failed: "
            f"{exc}",
        )
        return 1
    if result.returncode != 0:
        _emit_final(
            (result.text or "")
            + f"\n\nMANAGER WORKER ERROR: agent exited with {result.returncode}.",
            session_id=result.session_id,
            turns=result.turns,
        )
        return result.returncode or 1
    _emit_final(
        result.text,
        session_id=result.session_id,
        turns=result.turns,
    )
    # Clean worker exit (completion candidate or give-up): release this node's
    # daemon EC session. Final verification belongs to the run coordinator.
    # A clean exit is final — the Layer-3 crash net never resurrects it — so
    # the live session has no future attacher. Crash exits never reach this
    # line, which is exactly what keeps the session alive for attach. No-op
    # unless SHANNON_EC_DAEMON=1 (the daemon-continuity flag).
    _release_daemon_session(args.session_tag)
    return 0


def _release_daemon_session(session_tag: str) -> None:
    try:
        from workflow.proof_management.daemon_attach import release_daemon_session

        release_daemon_session(f".ec_session_{session_tag}", PROJECT_ROOT)
    except Exception:
        pass



def _emit_final(
    text: str,
    *,
    session_id: str = "",
    turns: int = 0,
) -> None:
    event: dict[str, object] = {"type": "result", "result": text}
    if session_id:
        event["session_id"] = session_id
    event["turns"] = max(0, int(turns))
    _emit(event)


def _emit(event: dict[str, object]) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


def _read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
