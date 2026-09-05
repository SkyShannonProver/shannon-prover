"""Zero-token live gate for Claude's required managed-proof MCP server.

Claude Code starts ``--mcp-config`` servers asynchronously and normally defers
their tools behind ``ToolSearch``.  A managed proof node cannot tolerate that
race: its manager tools must be connected and present in the very first Claude
``system/init`` event.  This sentinel launches the installed Claude CLI with an
invalid local-only API endpoint, so it exercises the real stdio/MCP startup
path without making a model request or spending tokens.
"""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from workflow.proof_tool.proof_tool_contract import resolve_proof_tool_contract
from workflow.proof_tool.proof_tool_endpoint import ProofToolEndpointServer
from workflow.proof_tool.proof_tool_launch import (
    ProofMcpLaunchSpec,
    ProofToolTimingBudget,
    render_claude_mcp_config,
)
from workflow.proof_tool.proof_tool_session import ProofToolSession


class _NoTurnMemory:
    def record_turn(self, **_kwargs: object) -> None:
        raise AssertionError("startup sentinel must not record a manager turn")


def _expected_claude_tools(manifest: Any) -> set[str]:
    server = manifest.identity.server
    return {
        f"mcp__{server}__{identity.tool}"
        for identity in manifest.tool_identities
    }


def validate_claude_init(
    event: dict[str, Any],
    *,
    server_name: str,
    expected_tools: set[str],
) -> tuple[bool, str]:
    """Validate the first provider init as the eager-tool admission boundary."""

    if event.get("type") != "system" or event.get("subtype") != "init":
        return False, "Claude did not emit a system/init event"
    servers = event.get("mcp_servers")
    status = ""
    if isinstance(servers, list):
        for item in servers:
            if isinstance(item, dict) and item.get("name") == server_name:
                status = str(item.get("status") or "")
                break
    if status != "connected":
        return False, (
            f"required MCP server {server_name!r} was not connected in "
            f"Claude system/init (status={status or 'missing'})"
        )
    actual_tools = {
        str(value)
        for value in event.get("tools", [])
        if isinstance(value, str)
    }
    missing = sorted(expected_tools - actual_tools)
    if missing:
        return False, (
            "required eager Claude MCP tools are missing: " + ", ".join(missing)
        )
    return True, ""


def run_claude_required_mcp_sentinel(
    *,
    claude_executable: str,
    model: str,
    output_path: Path,
    project_root: Path,
    startup_seconds: float = 15.0,
) -> dict[str, Any]:
    """Run the installed Claude CLI through the exact required-MCP startup."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = resolve_proof_tool_contract(
        "proof_state_compiler",
        source_navigation_enabled=True,
    )
    expected_tools = _expected_claude_tools(manifest)
    session = ProofToolSession(
        node_id="claude-required-mcp-sentinel",
        manifest=manifest,
        handle_turn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("startup sentinel must not execute a manager turn")
        ),
        memory=_NoTurnMemory(),
        response_renderer=lambda *_args: "unused",
        max_turns=1,
    )
    endpoint = ProofToolEndpointServer(
        session=session,
        manifest=manifest,
        # Startup reaches initialize + tools/list only.  No source operation is
        # admitted, so a semantic source resource is intentionally unnecessary.
        source_resource=object(),
    )
    endpoint.start()
    launch_id = "claude-mcp-sentinel-" + uuid.uuid4().hex
    endpoint.expect_launch(launch_id)
    proc: subprocess.Popen[str] | None = None
    init_event: dict[str, Any] = {}
    stderr_text = ""
    report: dict[str, Any]
    try:
        with tempfile.TemporaryDirectory(
            prefix="claude-required-mcp-",
            dir=output_path.parent,
        ) as raw_private:
            private_dir = Path(raw_private)
            spec = ProofMcpLaunchSpec(
                manifest=manifest,
                endpoint_host=endpoint.host,
                endpoint_port=endpoint.port,
                endpoint_token=endpoint.token,
                private_dir=private_dir,
                timing=ProofToolTimingBudget(
                    startup_seconds=startup_seconds,
                    manager_operation_seconds=5.0,
                    endpoint_read_seconds=6.0,
                    provider_tool_seconds=7.0,
                ),
            )
            config = render_claude_mcp_config(spec, launch_id=launch_id)
            server_config = config["mcpServers"][manifest.identity.server]
            if server_config.get("alwaysLoad") is not True:
                raise RuntimeError("Claude MCP config did not require eager tool loading")
            config_path = private_dir / "claude_mcp.json"
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            config_path.chmod(0o600)

            env = os.environ.copy()
            # Never consume the user's provider budget.  The loopback endpoint
            # is deliberately closed; Claude is terminated immediately after
            # its local system/init proves the MCP server and eager tool catalog.
            env["ANTHROPIC_API_KEY"] = "invalid-claude-mcp-startup-sentinel"
            env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
            command = [
                claude_executable,
                "-p",
                "Startup sentinel only.",
                "--model",
                model,
                "--effort",
                "low",
                "--dangerously-skip-permissions",
                "--output-format",
                "stream-json",
                "--verbose",
                "--no-session-persistence",
                "--max-budget-usd",
                "0.000001",
                "--mcp-config",
                str(config_path),
                "--strict-mcp-config",
            ]
            proc = subprocess.Popen(
                command,
                cwd=project_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            assert proc.stdout is not None
            selector = selectors.DefaultSelector()
            selector.register(proc.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + startup_seconds
            while time.monotonic() < deadline:
                remaining = max(0.0, deadline - time.monotonic())
                ready = selector.select(timeout=min(0.25, remaining))
                if not ready:
                    if proc.poll() is not None:
                        break
                    continue
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "system" and event.get("subtype") == "init":
                    init_event = event
                    break
            selector.close()
            passed, error = validate_claude_init(
                init_event,
                server_name=manifest.identity.server,
                expected_tools=expected_tools,
            )
            ready_receipt = endpoint.wait_ready(launch_id, 0.0)
            if passed and ready_receipt is None:
                passed = False
                error = (
                    "Claude init was connected but no exact endpoint READY "
                    "receipt existed"
                )
            report = {
                "kind": "claude_required_mcp_sentinel",
                "passed": passed,
                "server": manifest.identity.server,
                "server_status": next(
                    (
                        str(item.get("status") or "")
                        for item in init_event.get("mcp_servers", [])
                        if isinstance(item, dict)
                        and item.get("name") == manifest.identity.server
                    ),
                    "",
                ),
                "expected_tools": sorted(expected_tools),
                "visible_required_tools": sorted(
                    expected_tools
                    & {
                        str(value)
                        for value in init_event.get("tools", [])
                        if isinstance(value, str)
                    }
                ),
                "ready_receipt": ready_receipt is not None,
                "model_request_authority": "invalid_loopback_api_key_zero_token",
                "error": error,
            }
    except Exception as exc:
        report = {
            "kind": "claude_required_mcp_sentinel",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if proc is not None:
            try:
                _stdout, stderr_text = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                _stdout, stderr_text = proc.communicate(timeout=5)
        endpoint.close()

    if not report.get("passed") and stderr_text:
        report["provider_stderr_tail"] = stderr_text[-2000:]
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    import argparse
    import shutil

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default="claude-opus-5")
    args = parser.parse_args()
    executable = shutil.which("claude")
    if executable is None:
        parser.error("Claude CLI is not installed")
    report = run_claude_required_mcp_sentinel(
        claude_executable=executable,
        model=args.model,
        output_path=args.output,
        project_root=Path.cwd(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
