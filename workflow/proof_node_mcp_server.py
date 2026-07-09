"""MCP transport for one long-lived proof-node manager.

Claude should see a structured ``submit_proof_intent`` tool, not the socket,
token, runtime client, or shell submit script used internally by the runtime.
This server is intentionally tiny: it exposes one MCP tool and proxies the
unchanged proof-intent JSON to the existing per-node manager bridge.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, BinaryIO

from workflow.context_intents import (
    CONTEXT_TOPIC_INTENTS,
    INTENT_CLASS_CONTEXT_TOPIC,
    INTENT_CLASS_SYMBOL_LOOKUP,
    intent_payload_fields,
    intents_by_class,
)
from workflow.surface_profiles import schema_intents_for_surface_profile
from workflow.proof_management import ALLOWED_AGENT_INTENTS
from core.easycrypt.value_shapes import as_dict as _dict


SERVER_NAME = "shannon-proof-node"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

class ManagerBridgeProtocolError(RuntimeError):
    """Raised when the local manager bridge returns an invalid response."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--token", required=True)
    parser.add_argument("--node-memory-dir", required=True)
    args = parser.parse_args(argv)

    server = ProofNodeMcpServer(
        host=args.host,
        port=args.port,
        token=args.token,
        node_memory_dir=Path(args.node_memory_dir),
    )
    _debug("server_start", {"host": args.host, "port": args.port})
    try:
        server.serve(sys.stdin.buffer, sys.stdout.buffer)
    except Exception as exc:
        _debug("server_exception", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        _debug("server_stop", {})
    return 0


class ProofNodeMcpServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        token: str,
        node_memory_dir: Path,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.token = token
        self.node_memory_dir = Path(node_memory_dir)
        self.protocol_version = DEFAULT_PROTOCOL_VERSION

    def serve(self, stdin: BinaryIO, stdout: BinaryIO) -> None:
        while True:
            read = _read_message(stdin)
            if read is None:
                return
            message, framing = read
            _debug("message_in", {
                "method": str(message.get("method") or ""),
                "has_id": message.get("id") is not None,
                "params": _debug_safe(message.get("params")),
                "framing": framing,
            })
            response = self.handle_message(message)
            if response is not None:
                _write_message(stdout, response, framing=framing)
                _debug("message_out", {
                    "id": response.get("id"),
                    "has_error": "error" in response,
                    "result_keys": sorted(_dict(response.get("result")).keys()),
                    "framing": framing,
                })

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = str(message.get("method") or "")
        msg_id = message.get("id")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            params = _dict(message.get("params"))
            requested = str(params.get("protocolVersion") or self.protocol_version)
            self.protocol_version = requested
            return _result(msg_id, {
                "protocolVersion": self.protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            })
        if method == "ping":
            return _result(msg_id, {})
        if method == "tools/list":
            tools = [self._submit_tool_schema()]
            return _result(msg_id, {"tools": tools})
        if method == "tools/call":
            return _result(
                msg_id,
                self._handle_tool_call(_dict(message.get("params"))),
            )
        if msg_id is None:
            return None
        return _error(msg_id, -32601, f"Unknown MCP method: {method}")

    def _submit_tool_schema(self) -> dict[str, Any]:
        allowed_intents = self._schema_allowed_intents()
        return {
            "name": "submit_proof_intent",
            "description": _submit_tool_description(
                allowed_intents,
                self.node_memory_dir,
            ),
            "inputSchema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": allowed_intents,
                        "description": _intent_schema_description(allowed_intents),
                    },
                    "payload": {
                        "type": "object",
                        "description": _payload_description(allowed_intents),
                        "additionalProperties": True,
                    },
                },
                "required": ["intent"],
            },
        }

    def _schema_allowed_intents(self) -> list[str]:
        profile = os.environ.get("SHANNON_SURFACE_PROFILE", "").strip() or None
        # SUPERSET for the schema: an adaptive profile advertises all intents so the
        # agent can reach for a richer one (that reach IS the escalation request);
        # the manager still gates acceptance until escalated.
        return sorted(schema_intents_for_surface_profile(profile) & ALLOWED_AGENT_INTENTS)

    def _handle_tool_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "")
        arguments = _dict(params.get("arguments"))
        if name != "submit_proof_intent":
            return _tool_text(f"Unknown tool: {name}", is_error=True)
        try:
            intent_text = intent_text_from_tool_arguments(arguments)
        except ValueError as exc:
            return _tool_text(str(exc), is_error=True)
        try:
            data = submit_intent_to_bridge(
                host=self.host,
                port=self.port,
                token=self.token,
                intent_text=intent_text,
            )
        except (OSError, ManagerBridgeProtocolError) as exc:
            return _tool_text(f"MANAGER BRIDGE ERROR: {exc}", is_error=True)
        text = str(data.get("text") or "")
        is_error = int(data.get("exit_code") or 0) != 0
        return _tool_text(text, is_error=is_error)


def intent_text_from_tool_arguments(arguments: dict[str, Any]) -> str:
    if not isinstance(arguments, dict):
        arguments = {}
    intent = str(arguments.get("intent") or "").strip()
    payload = arguments.get("payload")
    if payload is None:
        payload = {}
    # Do not reject malformed proof intents at the transport layer.  Forward
    # them to ProofNodeManager so the agent gets the normal repair prompt plus
    # the latest workspace view, and so malformed-intent health/audit counters
    # stay manager-owned.
    return json.dumps(
        {"intent": intent, "payload": payload},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _submit_tool_description(
    allowed_intents: list[str],
    node_memory_dir: Path | None = None,
) -> str:
    allowed = set(allowed_intents)
    if (CONTEXT_TOPIC_INTENTS | {"lookup_symbol"}) & allowed:
        purpose = (
            "proof mutation or profile-visible semantic proof context "
            "(context_topic intents and symbol_lookup), plus proof control"
        )
    else:
        purpose = "proof mutation, rewind/restart negotiation, or finish"
    memory_note = ""
    if node_memory_dir is not None:
        latest_followup = Path(node_memory_dir) / "latest_followup.md"
        proof_so_far = Path(node_memory_dir) / "proof_so_far.md"
        memory_note = (
            f" Current node memory directory: {node_memory_dir}. "
            f"Latest followup: {latest_followup}. Accepted proof so far: "
            f"{proof_so_far}."
        )
    return (
        "Submit exactly one proof-level JSON intent to this proof node's "
        f"manager. Use this tool for every {purpose}. The tool result is "
        "bounded; if context was compacted or a view is truncated, read "
        "latest_followup.md from the current node memory directory, and "
        "proof_so_far.md only when you need the accepted tactic spine. The "
        "raw workspace JSON is audit/replay data, not the normal proof "
        "surface. If those exact paths are unavailable in "
        "context, submit your next proof intent using only the advertised "
        f"intent schema; do not use shell directory discovery.{memory_note}"
    )


def _payload_description(allowed_intents: list[str]) -> str:
    examples: list[str] = []
    allowed = set(allowed_intents)
    if {"commit_tactic", "probe_tactic"} & allowed:
        examples.append("{'tactic': 'smt().'}")
    if CONTEXT_TOPIC_INTENTS & allowed:
        examples.append(
            "{} for no-argument context topics; topic-specific fields for context topics"
        )
    if "lookup_symbol" in allowed:
        examples.append("{'symbol': 'LEMMA'}")
    if examples:
        return "Intent payload, e.g. " + ", ".join(examples) + "."
    return "Intent payload object; use {} for menu/request intents."


def _intent_schema_description(allowed_intents: list[str]) -> str:
    allowed = set(allowed_intents)
    chunks: list[str] = []
    context_topics = intents_by_class(allowed, INTENT_CLASS_CONTEXT_TOPIC)
    if context_topics:
        shown = ", ".join(context_topics[:12])
        more = "" if len(context_topics) <= 12 else f", ... (+{len(context_topics) - 12})"
        chunks.append(f"context_topic: {shown}{more}")
    if "lookup_symbol" in allowed:
        fields = ", ".join(intent_payload_fields("lookup_symbol"))
        chunks.append(f"{INTENT_CLASS_SYMBOL_LOOKUP}: lookup_symbol ({fields})")
    mutation = sorted(
        i for i in allowed
        if i in {"commit_tactic", "commit_replay_suffix_chunk"}
    )
    if mutation:
        chunks.append("proof_mutation: " + ", ".join(mutation))
    control = sorted(
        i for i in allowed
        if i in {"undo_last_step", "undo_to_checkpoint", "fresh_restart", "finish", "amend_and_replay"}
    )
    if control:
        chunks.append("proof_control: " + ", ".join(control))
    if not chunks:
        return "Proof intent name."
    return "Proof intent name. Intent classes: " + "; ".join(chunks) + "."


def submit_intent_to_bridge(
    *,
    host: str,
    port: int,
    token: str,
    intent_text: str,
) -> dict[str, Any]:
    return _bridge_roundtrip(host, int(port), {"token": token, "text": intent_text})


def _bridge_connect_timeout() -> float:
    """Seconds to wait for the TCP connect to the local manager bridge.

    The bridge is an in-process loopback server, so connecting is fast; a short
    timeout here is correct and surfaces a genuinely dead bridge quickly.
    """
    return _env_float("SHANNON_BRIDGE_CONNECT_TIMEOUT", 30.0)


def _bridge_read_timeout() -> float | None:
    """Seconds to wait for the manager's reply once connected.

    This MUST be decoupled from the connect timeout. A legitimate manager
    handler (notably a confirmed ``undo_to_checkpoint`` rewind, which does a
    full EC restart + per-tactic replay of the kept prefix while holding the
    bridge lock) can run for minutes. ``socket.create_connection`` leaves the
    connect timeout installed on the socket, so without resetting it the
    subsequent ``recv`` inherits the (short) connect timeout and a slow-but-
    finite handler is misreported to the agent as a wedge
    (``MANAGER BRIDGE ERROR``). Default generously; ``0``/``none`` => blocking.
    """
    raw = os.environ.get("SHANNON_BRIDGE_READ_TIMEOUT", "").strip().lower()
    if raw in ("0", "none", "off", ""):
        # Default: large finite ceiling. A finite cap (rather than a fully
        # blocking read) still bounds a truly hung bridge while comfortably
        # covering a multi-minute rewind replay.
        if raw in ("0", "none", "off"):
            return None
        return 600.0
    try:
        value = float(raw)
    except ValueError:
        return 600.0
    return None if value <= 0 else value


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _bridge_roundtrip(host: str, port: int, payload: dict[str, Any]) -> dict[str, Any]:
    with socket.create_connection(
        (host, int(port)), timeout=_bridge_connect_timeout()
    ) as sock:
        # Decouple the read deadline from the connect deadline.
        # ``create_connection`` installs the connect timeout on the socket; if we
        # do not override it, ``_read_all``'s ``recv`` inherits it and a
        # legitimately slow handler (e.g. a rewind replay) raises socket.timeout
        # and is misreported as a bridge wedge. See _bridge_read_timeout.
        sock.settimeout(_bridge_read_timeout())
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)
        response = _read_all(sock)
    if not response.strip():
        _debug("bridge_empty_response", {"host": host, "port": int(port)})
        raise ManagerBridgeProtocolError("bridge closed without a response")
    try:
        data = json.loads(response.decode("utf-8"))
    except json.JSONDecodeError as exc:
        preview = response.decode("utf-8", errors="replace")[:1000]
        _debug("bridge_non_json_response", {"preview": preview})
        raise ManagerBridgeProtocolError("bridge returned a non-JSON response") from exc
    if not isinstance(data, dict):
        _debug("bridge_bad_response_shape", {"type": type(data).__name__})
        raise ManagerBridgeProtocolError("bridge returned a non-object response")
    return data


def _read_message(stdin: BinaryIO) -> tuple[dict[str, Any], str] | None:
    first = stdin.readline()
    if not first:
        return None
    if first.lstrip().startswith(b"{"):
        return json.loads(first.decode("utf-8")), "newline"

    content_length: int | None = None
    line = first
    while line not in (b"\r\n", b"\n", b""):
        key, sep, value = line.partition(b":")
        if sep and key.strip().lower() == b"content-length":
            content_length = int(value.strip())
        line = stdin.readline()
    if content_length is None:
        raise ValueError("Missing Content-Length header from MCP client.")
    body = stdin.read(content_length)
    if not body:
        return None
    return json.loads(body.decode("utf-8")), "header"


def _write_message(stdout: BinaryIO, message: dict[str, Any], *, framing: str) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if framing == "header":
        stdout.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
        stdout.write(body)
    else:
        stdout.write(body + b"\n")
    stdout.flush()


def _read_all(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": code, "message": message},
    }


def _tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": bool(is_error),
    }



def _debug(event: str, payload: dict[str, Any]) -> None:
    path = os.environ.get("SHANNON_MCP_DEBUG_LOG", "").strip()
    if not path:
        return
    try:
        record = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            **payload,
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        return


def _debug_safe(value: Any) -> Any:
    try:
        encoded = json.dumps(value, sort_keys=True)
    except TypeError:
        return repr(value)
    if len(encoded) > 1000:
        return encoded[:1000] + "...[truncated]"
    return value


if __name__ == "__main__":
    raise SystemExit(main())
