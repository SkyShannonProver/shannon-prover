"""No-model end-to-end smoke for the complete managed proof-tool stack."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import _pathsetup  # noqa: F401
from workflow.node.proof_node_manager import ProofNodeManager
from workflow.node.manager_followup_render import render_manager_followup
from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
from workflow.proof_tool.proof_tool_endpoint import ProofToolEndpointServer
from workflow.proof_tool.proof_tool_session import ProofToolSession


ROOT = Path(__file__).resolve().parents[1]


class _Memory:
    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []

    def record_turn(self, **kwargs: Any) -> None:
        self.turns.append(kwargs)


def test_stdio_mcp_drives_real_manager_and_easycrypt_to_finish(tmp_path: Path) -> None:
    lemma = "mcp_real_manager_smoke"
    source = tmp_path / "McpRealManagerSmoke.ec"
    source.write_text(
        f"lemma {lemma} : true.\nproof.\n  admit.\nqed.\n",
        encoding="utf-8",
    )
    session_tag = "mcp_real_manager_" + uuid.uuid4().hex[:12]
    manifest = resolve_proof_tool_contract("l1_goal_projection")
    manager = ProofNodeManager(
        file_path=str(source),
        lemma_name=lemma,
        include_dir="easycrypt-src/theories",
        session_tag=session_tag,
        node_id="mcp-real-manager-smoke",
        run_dir=tmp_path / "run",
        project_root=ROOT,
        surface_profile="l1_goal_projection",
        proof_tool_manifest=manifest,
    )
    endpoint: ProofToolEndpointServer | None = None
    proc: subprocess.Popen[bytes] | None = None
    session_dir = manager.session_path
    try:
        manager.bootstrap(replay_prefix=[])
        memory = _Memory()
        tool_session = ProofToolSession(
            node_id="mcp-real-manager-smoke",
            manifest=manifest,
            handle_turn=lambda raw, deadline: manager.handle_tool_arguments(
                raw,
                deadline=deadline,
            ),
            memory=memory,
            response_renderer=lambda turn, index, handled, _memory: (
                render_manager_followup(
                    turn,
                    index,
                    handled,
                    surface_profile=manager.surface_profile,
                )
            ),
            max_turns=5,
        )
        endpoint = ProofToolEndpointServer(
            session=tool_session,
            manifest=manifest,
            token="-leading-dash-real-manager-token",
        )
        endpoint.start()
        endpoint.expect_launch("real-manager-launch")
        command = [
            sys.executable,
            "-m",
            "workflow.proof_tool.proof_node_mcp_server",
            "--host",
            endpoint.host,
            "--port",
            str(endpoint.port),
            f"--token={endpoint.token}",
            "--launch-id",
            "real-manager-launch",
            "--manifest-json",
            json.dumps(manifest.to_dict(), separators=(",", ":"), sort_keys=True),
            "--manager-timeout-seconds",
            "120",
            "--endpoint-timeout-seconds",
            "150",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=ROOT,
            env=env,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None

        def exchange(message: dict[str, Any]) -> dict[str, Any]:
            assert proc is not None and proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(
                json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
            )
            proc.stdin.flush()
            line = proc.stdout.readline()
            assert line, proc.stderr.read().decode("utf-8", errors="replace")
            return json.loads(line)

        initialized = exchange({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })
        assert initialized["result"]["protocolVersion"] == "2024-11-05"
        proc.stdin.write(
            b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        )
        proc.stdin.flush()
        listed = exchange({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        assert listed["result"]["tools"][0]["name"] == manifest.identity.tool
        assert endpoint.wait_ready(
            "real-manager-launch",
            timeout=2,
        ) is not None

        responses = []
        for call_id, arguments in enumerate((
            {"intent": "commit_tactic", "payload": {"tactic": "trivial."}},
            {"intent": "commit_tactic", "payload": {"tactic": "qed."}},
            {"intent": "finish", "payload": {}},
        ), start=3):
            responses.append(exchange({
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {
                    "name": manifest.identity.tool,
                    "arguments": arguments,
                },
            }))

        assert all(response["result"]["isError"] is False for response in responses)
        assert "goals_discharged_pending_qed" in responses[0]["result"]["content"][0]["text"]
        assert "session_closed_pending_verification" in responses[1]["result"]["content"][0]["text"]
        assert "Finish accepted" in responses[2]["result"]["content"][0]["text"]
        assert tool_session.last_committed_tactics == ("trivial.", "qed.")
        assert tool_session.turn_index == 3
        assert len(memory.turns) == 3
    finally:
        if proc is not None:
            if proc.stdin is not None and not proc.stdin.closed:
                proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=5)
        if endpoint is not None:
            endpoint.close()
        manager.close_session()
        if session_dir.name.startswith(".ec_session_mcp_real_manager_"):
            shutil.rmtree(session_dir, ignore_errors=True)
