"""Stdio MCP child for invocation-bound manager tools.

This provider-spawned process is the whole child side in one file: newline
JSON framing, fail-closed JSON-RPC/MCP message order (protocol negotiation,
the advertised tool contract, and the readiness ACK gate), and forwarding raw
tool arguments to the authenticated endpoint. It never parses proof intents,
reads files itself, or owns readiness, proof state, or turn presentation.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from typing import Any, BinaryIO, Callable, Mapping

from dataclasses import dataclass
from enum import Enum

from workflow.proof_tool.proof_tool_contract import (
    DECLARATION_RESOLVE_TOOL_IDENTITY,
    PROOF_TOOL_IDENTITY,
    SOURCE_READ_TOOL_IDENTITY,
    SOURCE_SEARCH_TOOL_IDENTITY,
    ProofToolContractManifest,
    ToolIdentity,
    proof_tool_definitions,
)
from workflow.proof_tool.proof_tool_endpoint import (
    ProofToolEndpointClient,
    ProofToolEndpointError,
)


DEFAULT_MAX_MCP_MESSAGE_BYTES = 2_000_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--token", required=True)
    parser.add_argument("--launch-id", required=True)
    parser.add_argument("--manifest-json", required=True)
    parser.add_argument("--manager-timeout-seconds", required=True, type=float)
    parser.add_argument("--endpoint-timeout-seconds", required=True, type=float)
    parser.add_argument("--node-deadline-epoch", type=float)
    args = parser.parse_args(argv)

    try:
        manifest = ProofToolContractManifest.from_dict(
            _strict_json_loads(args.manifest_json)
        )
        adapter = ProofToolMcpAdapter(
            host=args.host,
            port=args.port,
            token=args.token,
            launch_id=args.launch_id,
            manifest=manifest,
            manager_timeout_seconds=args.manager_timeout_seconds,
            endpoint_timeout_seconds=args.endpoint_timeout_seconds,
            node_deadline_epoch=args.node_deadline_epoch,
        )
        return adapter.serve(sys.stdin.buffer, sys.stdout.buffer)
    except Exception as exc:
        # stdout is reserved exclusively for MCP JSON-RPC frames.
        print(
            "proof-tool MCP adapter failed: "
            f"{type(exc).__name__}: {str(exc)[:500]}",
            file=sys.stderr,
            flush=True,
        )
        return 2


class ProofToolMcpAdapter:
    """One invocation-bound stdio adapter."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        token: str,
        launch_id: str,
        manifest: ProofToolContractManifest,
        manager_timeout_seconds: float,
        endpoint_timeout_seconds: float,
        node_deadline_epoch: float | None = None,
        max_message_bytes: int = DEFAULT_MAX_MCP_MESSAGE_BYTES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.host = str(host)
        self.port = int(port)
        self.token = str(token)
        self.launch_id = str(launch_id or "").strip()
        if not self.launch_id:
            raise ValueError("proof-tool MCP adapter requires a launch id")
        self.manifest = manifest
        self.manager_timeout_seconds = _positive_seconds(
            manager_timeout_seconds, "manager timeout"
        )
        self.endpoint_timeout_seconds = _positive_seconds(
            endpoint_timeout_seconds, "endpoint timeout"
        )
        self.node_deadline_epoch = _optional_deadline(node_deadline_epoch)
        self.max_message_bytes = max(1024, int(max_message_bytes))
        self._clock = clock
        self.protocol = McpProtocolSession(
            manifest=manifest,
            launch_id=self.launch_id,
        )
        self._endpoint: ProofToolEndpointClient | None = None

    def serve(self, stdin: BinaryIO, stdout: BinaryIO) -> int:
        while True:
            message = _read_message(stdin, max_bytes=self.max_message_bytes)
            if message is None:
                return 0
            decision = self.protocol.handle(message)

            # tools/list is flushed first. Only the subsequent exact endpoint
            # ACK may transition the protocol session to CALLS_ALLOWED.
            if decision.response is not None:
                _write_message(stdout, decision.response)

            if decision.readiness_claim is not None:
                # Readiness failure is the highest-frequency infra fault; its
                # cause MUST reach stderr (the provider captures child stderr),
                # otherwise the child dies with exit code 2 and zero diagnosis.
                failure = ""
                try:
                    endpoint = self._client(
                        decision.readiness_claim.negotiated_protocol
                    )
                    ack = endpoint.ready()
                    if not self.protocol.acknowledge_readiness(
                        launch_id=ack.launch_id,
                        negotiated_protocol=ack.negotiated_protocol,
                    ):
                        failure = (
                            "readiness ACK did not match this launch "
                            f"(ack launch_id={ack.launch_id!r}, "
                            f"expected {self.launch_id!r}, "
                            f"protocol state {self.protocol.state.value!r})"
                        )
                except (OSError, ProofToolEndpointError, ValueError) as exc:
                    failure = f"{type(exc).__name__}: {exc}"
                if failure:
                    self.protocol.fail_readiness(failure)
                    print(
                        f"proof-tool MCP readiness failed: {failure}",
                        file=sys.stderr,
                        flush=True,
                    )
                    return 2

            if decision.dispatch_tool_call:
                _write_message(stdout, self._dispatch_tool_call(decision))

            if decision.fatal:
                print(
                    "proof-tool MCP protocol fatal: "
                    f"{decision.reason or 'unspecified protocol violation'}",
                    file=sys.stderr,
                    flush=True,
                )
                return 2

    def _dispatch_tool_call(
        self,
        decision: McpProtocolDecision,
    ) -> dict[str, Any]:
        msg_id = decision.tool_call_id
        raw_arguments = decision.raw_arguments
        if self._endpoint is None:
            return _result(msg_id, _tool_text(
                "MANAGER TOOL ERROR: proof-tool endpoint is not ready.",
                is_error=True,
            ))

        call_id = _internal_call_id(self.launch_id, msg_id)
        absolute_deadline = self._clock() + self.manager_timeout_seconds
        if self.node_deadline_epoch is not None:
            absolute_deadline = min(absolute_deadline, self.node_deadline_epoch)
        try:
            if decision.tool_identity == PROOF_TOOL_IDENTITY:
                response = self._endpoint.call(
                    call_id=call_id,
                    raw_arguments=raw_arguments,
                    absolute_deadline=absolute_deadline,
                )
            elif decision.tool_identity in {
                SOURCE_READ_TOOL_IDENTITY,
                SOURCE_SEARCH_TOOL_IDENTITY,
                DECLARATION_RESOLVE_TOOL_IDENTITY,
            }:
                response = self._endpoint.source_resource(
                    tool_identity=decision.tool_identity,
                    call_id=call_id,
                    raw_arguments=raw_arguments,
                    absolute_deadline=absolute_deadline,
                )
            else:
                raise ProofToolEndpointError(
                    "MCP protocol dispatched an unknown manager tool identity"
                )
        except (OSError, ProofToolEndpointError) as exc:
            return _result(msg_id, _tool_text(
                "MANAGER ENDPOINT ERROR: "
                f"{type(exc).__name__}: {str(exc)[:500]}",
                is_error=True,
            ))
        return _result(
            msg_id,
            _tool_text(response.text, is_error=response.is_error),
        )

    def _client(self, negotiated_protocol: str) -> ProofToolEndpointClient:
        if self._endpoint is not None:
            return self._endpoint
        self._endpoint = ProofToolEndpointClient(
            host=self.host,
            port=self.port,
            token=self.token,
            launch_id=self.launch_id,
            manifest=self.manifest,
            negotiated_protocol=negotiated_protocol,
            connect_timeout=min(30.0, self.endpoint_timeout_seconds),
            endpoint_timeout=self.endpoint_timeout_seconds,
            max_response_bytes=self.max_message_bytes,
        )
        return self._endpoint


def _read_message(
    stdin: BinaryIO,
    *,
    max_bytes: int = DEFAULT_MAX_MCP_MESSAGE_BYTES,
) -> dict[str, Any] | None:
    """Read one newline-delimited JSON message (the only framing both
    Claude Code and Codex speak; the legacy LSP Content-Length framing had no
    real client and was removed)."""
    first = stdin.readline(max_bytes + 1)
    if not first:
        return None
    if len(first) > max_bytes:
        raise ValueError("MCP message exceeded its size limit")
    message = _strict_json_loads(first.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("MCP message must be an object")
    return message


def _write_message(stdout: BinaryIO, message: Mapping[str, Any]) -> None:
    body = json.dumps(
        dict(message),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    stdout.write(body + b"\n")
    stdout.flush()


def _tool_text(text: str, *, is_error: bool) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": str(text)}],
        "isError": bool(is_error),
    }


def _internal_call_id(launch_id: str, jsonrpc_id: Any) -> str:
    # Human-readable on purpose: audit logs can be matched back to the
    # JSON-RPC request by eye (the old sha256 of the same pair could not).
    encoded_id = json.dumps(
        jsonrpc_id,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"{launch_id}:{encoded_id}"


def _positive_seconds(value: float, label: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or not (seconds > 0):
        raise ValueError(f"proof-tool {label} must be finite and positive")
    return seconds


def _optional_deadline(value: float | None) -> float | None:
    if value is None:
        return None
    deadline = float(value)
    if not math.isfinite(deadline) or deadline <= 0:
        raise ValueError("proof-tool node deadline must be finite and positive")
    return deadline


def _strict_json_loads(text: str) -> Any:
    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON number is forbidden: {value}")

    return json.loads(text, parse_constant=reject_constant)




# ---------------------------------------------------------------------------
# MCP wire-protocol state (merged from the former workflow/mcp_protocol_session
# module: the framing loop above and this state machine were one thing split
# in two — serve() could not be read without both files open).
# ---------------------------------------------------------------------------

SUPPORTED_MCP_PROTOCOL_VERSIONS = ("2024-11-05",)


class McpProtocolState(str, Enum):
    NEW = "new"
    INITIALIZE_RESPONDED = "initialize_responded"
    INITIALIZED = "initialized"
    AWAITING_READINESS_ACK = "awaiting_readiness_ack"
    CALLS_ALLOWED = "calls_allowed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class McpReadinessClaim:
    launch_id: str
    negotiated_protocol: str


@dataclass(frozen=True)
class McpProtocolDecision:
    """Result of consuming one already-framed MCP message."""

    response: dict[str, Any] | None = None
    readiness_claim: McpReadinessClaim | None = None
    dispatch_tool_call: bool = False
    tool_identity: ToolIdentity | None = None
    tool_call_id: Any = None
    raw_arguments: Any = None
    fatal: bool = False
    reason: str = ""


class McpProtocolSession:
    """One provider-spawned MCP stdio session."""

    def __init__(
        self,
        *,
        manifest: ProofToolContractManifest,
        launch_id: str,
    ) -> None:
        if not isinstance(launch_id, str) or not launch_id.strip():
            raise ValueError("MCP launch identity must be a non-empty string")
        # Authenticate even directly-constructed manifests at the protocol
        # boundary; launch JSON normally arrives through ``from_dict``.
        proof_tool_definitions(manifest)
        self.manifest = manifest
        self.launch_id = launch_id.strip()
        self.state = McpProtocolState.NEW
        self.negotiated_protocol = ""
        self.failure_reason = ""

    def handle(self, message: Mapping[str, Any]) -> McpProtocolDecision:
        """Validate one MCP message and return protocol/dispatch instructions."""

        if not isinstance(message, Mapping):
            return self._fatal(None, -32600, "MCP message is not an object")
        has_id = "id" in message
        msg_id = message.get("id")
        if has_id and not _valid_jsonrpc_id(msg_id):
            return self._fatal(None, -32600, "MCP request id is invalid")
        if message.get("jsonrpc") != "2.0":
            return self._fatal(msg_id, -32600, "MCP message is not JSON-RPC 2.0")
        method = message.get("method")
        if not isinstance(method, str) or not method:
            return self._fatal(msg_id, -32600, "MCP method is missing")

        if self.state == McpProtocolState.UNAVAILABLE:
            return McpProtocolDecision(
                response=_error(msg_id, -32002, "MCP proof-tool session is unavailable"),
                fatal=True,
                reason="MCP proof-tool session is unavailable",
            )
        if method == "initialize":
            return self._initialize(msg_id, has_id, message.get("params"))
        if method == "notifications/initialized":
            return self._initialized_notification(msg_id, has_id)
        if method == "ping":
            if not has_id:
                return self._fatal(None, -32600, "MCP ping must be a request")
            if self.state == McpProtocolState.NEW:
                return self._fatal(msg_id, -32002, "MCP ping arrived before initialize")
            return McpProtocolDecision(response=_result(msg_id, {}))
        if method == "tools/list":
            return self._tools_list(msg_id, has_id)
        if method == "tools/call":
            return self._tools_call(msg_id, has_id, message.get("params"))
        if not has_id:
            self.state = McpProtocolState.UNAVAILABLE
            return McpProtocolDecision(
                fatal=True,
                reason=f"unexpected MCP notification {method!r}",
            )
        return McpProtocolDecision(
            response=_error(msg_id, -32601, f"Unknown MCP method: {method}"),
        )

    def acknowledge_readiness(
        self,
        *,
        launch_id: str,
        negotiated_protocol: str,
    ) -> bool:
        """Open the tool-call gate only for the exact acknowledged launch."""

        matches = (
            self.state == McpProtocolState.AWAITING_READINESS_ACK
            and launch_id == self.launch_id
            and negotiated_protocol == self.negotiated_protocol
        )
        if not matches:
            self.state = McpProtocolState.UNAVAILABLE
            return False
        self.state = McpProtocolState.CALLS_ALLOWED
        return True

    def fail_readiness(self, reason: str) -> None:
        """Permanently close this child after readiness callback failure."""

        self.failure_reason = str(reason or "readiness failed")
        self.state = McpProtocolState.UNAVAILABLE

    def _initialize(
        self,
        msg_id: Any,
        has_id: bool,
        raw_params: Any,
    ) -> McpProtocolDecision:
        if self.state != McpProtocolState.NEW:
            return self._fatal(msg_id, -32600, "MCP initialize was repeated")
        if not has_id:
            return self._fatal(None, -32600, "MCP initialize must be a request")
        if not isinstance(raw_params, Mapping):
            return self._fatal(msg_id, -32602, "MCP initialize params are invalid")
        requested = raw_params.get("protocolVersion")
        if not isinstance(requested, str) or not requested:
            return self._fatal(msg_id, -32602, "MCP protocolVersion is missing")
        negotiated = (
            requested
            if requested in SUPPORTED_MCP_PROTOCOL_VERSIONS
            else SUPPORTED_MCP_PROTOCOL_VERSIONS[-1]
        )
        self.negotiated_protocol = negotiated
        self.state = McpProtocolState.INITIALIZE_RESPONDED
        return McpProtocolDecision(response=_result(msg_id, {
            "protocolVersion": negotiated,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "shannon-proof-node",
                "version": self.manifest.envelope_version,
            },
        }))

    def _initialized_notification(
        self,
        msg_id: Any,
        has_id: bool,
    ) -> McpProtocolDecision:
        if has_id:
            return self._fatal(
                msg_id,
                -32600,
                "MCP notifications/initialized must not have an id",
            )
        if self.state != McpProtocolState.INITIALIZE_RESPONDED:
            return self._fatal(
                None,
                -32600,
                "MCP initialized notification was out of order",
            )
        self.state = McpProtocolState.INITIALIZED
        return McpProtocolDecision()

    def _tools_list(self, msg_id: Any, has_id: bool) -> McpProtocolDecision:
        if not has_id:
            return self._fatal(None, -32600, "MCP tools/list must be a request")
        if self.state == McpProtocolState.CALLS_ALLOWED:
            return McpProtocolDecision(response=_result(msg_id, {
                "tools": proof_tool_definitions(self.manifest),
            }))
        if self.state != McpProtocolState.INITIALIZED:
            return self._fatal(msg_id, -32002, "MCP tools/list was out of order")
        self.state = McpProtocolState.AWAITING_READINESS_ACK
        claim = McpReadinessClaim(
            launch_id=self.launch_id,
            negotiated_protocol=self.negotiated_protocol,
        )
        return McpProtocolDecision(
            response=_result(msg_id, {
                "tools": proof_tool_definitions(self.manifest),
            }),
            readiness_claim=claim,
        )

    def _tools_call(
        self,
        msg_id: Any,
        has_id: bool,
        raw_params: Any,
    ) -> McpProtocolDecision:
        if not has_id:
            return self._fatal(None, -32600, "MCP tools/call must be a request")
        if self.state != McpProtocolState.CALLS_ALLOWED:
            return self._fatal(
                msg_id,
                -32002,
                "MCP tools/call arrived before readiness ACK",
            )
        if not isinstance(raw_params, Mapping):
            return self._fatal(msg_id, -32602, "MCP tools/call params are invalid")
        name = raw_params.get("name")
        identity_by_name = {
            identity.tool: identity for identity in self.manifest.tool_identities
        }
        tool_identity = identity_by_name.get(name)
        if tool_identity is None:
            return McpProtocolDecision(response=_error(
                msg_id,
                -32602,
                f"Unknown MCP tool: {name!r}",
            ))
        # Do not coerce or validate proof intent arguments here.  The manager is
        # the sole semantic decoder and must observe malformed envelopes intact.
        return McpProtocolDecision(
            dispatch_tool_call=True,
            tool_identity=tool_identity,
            tool_call_id=msg_id,
            raw_arguments=raw_params.get("arguments"),
        )

    def _fatal(self, msg_id: Any, code: int, reason: str) -> McpProtocolDecision:
        self.state = McpProtocolState.UNAVAILABLE
        self.failure_reason = reason
        return McpProtocolDecision(
            response=_error(msg_id, code, reason),
            fatal=True,
            reason=reason,
        )


def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": code, "message": message},
    }


def _valid_jsonrpc_id(value: Any) -> bool:
    if value is None or isinstance(value, str):
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not isinstance(value, float) or math.isfinite(value)


if __name__ == "__main__":
    raise SystemExit(main())
