"""Authenticated loopback endpoint for manager-owned agent tools.

The endpoint owns only private transport facts: the versioned envelope, request
size, bearer token, invocation readiness registration, and the loopback socket.
Proof intents are delegated unchanged to :mod:`workflow.proof_tool.proof_tool_session`.
Optional source navigation is served by the separately validated source
resource; it never enters the proof-turn state machine.
"""
from __future__ import annotations

import hmac
import json
import math
import secrets
import socket
import socketserver
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Mapping

from workflow.proof_management.types import TurnDirective
from workflow.proof_tool.easycrypt_source_resource import (
    EasyCryptSourceResponse,
    EasyCryptSourceResource,
)
from workflow.proof_tool.proof_tool_contract import (
    DECLARATION_RESOLVE_TOOL_IDENTITY,
    PROOF_TOOL_IDENTITY,
    SOURCE_READ_TOOL_IDENTITY,
    SOURCE_SEARCH_TOOL_IDENTITY,
    ProofToolContractManifest,
    ToolIdentity,
)
from workflow.proof_tool.proof_tool_session import (
    ProofToolSession,
    ProofToolSessionResponse,
)


DEFAULT_MAX_ENDPOINT_MESSAGE_BYTES = 2_000_000


class ProofToolEndpointError(RuntimeError):
    """Raised when the private endpoint violates its transport contract."""


@dataclass(frozen=True)
class ReadyRegistration:
    launch_id: str
    negotiated_protocol: str


@dataclass(frozen=True)
class _AdmittedCall:
    launch_id: str
    call_id: str
    identity: ToolIdentity
    raw_arguments: Any
    absolute_deadline: float


class ProofToolEndpointServer:
    """One authenticated loopback server for a :class:`ProofToolSession`."""

    def __init__(
        self,
        *,
        session: ProofToolSession,
        manifest: ProofToolContractManifest,
        source_resource: EasyCryptSourceResource | None = None,
        token: str | None = None,
        host: str = "127.0.0.1",
        max_request_bytes: int = DEFAULT_MAX_ENDPOINT_MESSAGE_BYTES,
    ) -> None:
        self.session = session
        self.manifest = manifest
        self.source_resource = source_resource
        if manifest.source_navigation_enabled != (source_resource is not None):
            raise ValueError(
                "proof-tool manifest/source-resource capability mismatch"
            )
        self.token = str(token or secrets.token_urlsafe(32))
        if not self.token:
            raise ValueError("proof-tool endpoint requires a non-empty token")
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("proof-tool endpoint must bind to loopback")
        self.host = host
        self.port = 0
        self.max_request_bytes = max(1024, int(max_request_bytes))
        # Exactly one provider invocation is armed at a time: arming a new
        # launch id revokes the prior child, and READY/call envelopes must name
        # the armed launch. One expected id + one registration slot is the
        # whole state (it used to be three containers synced in four places).
        self._expected_launch_id = ""
        self._ready_registration: ReadyRegistration | None = None
        self._ready_condition = threading.Condition()
        self._httpd: socketserver.ThreadingTCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._httpd is not None:
            raise RuntimeError("proof-tool endpoint is already running")
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:  # noqa: D401 - socketserver protocol
                raw = self.rfile.readline(outer.max_request_bytes + 1)
                if len(raw) > outer.max_request_bytes:
                    response = outer._error(
                        "request_too_large",
                        "proof-tool endpoint request exceeded its size limit",
                    )
                else:
                    try:
                        response = outer.handle_bytes(raw)
                    except Exception as exc:
                        # Without this, socketserver eats the traceback and the
                        # client only ever sees "closed without a response" —
                        # one Python exception crossed two processes as a
                        # connection reset. Return it as a structured error and
                        # keep the traceback on the server's stderr.
                        traceback.print_exc()
                        response = outer._error(
                            "internal_error",
                            f"{type(exc).__name__}: {exc}",
                        )
                encoded = _canonical_json_bytes(response) + b"\n"
                self.wfile.write(encoded)
                self.wfile.flush()

        class ThreadingServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        try:
            self._httpd = ThreadingServer((self.host, 0), Handler)
            self.port = int(self._httpd.server_address[1])
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                name=f"proof-tool-endpoint-{self.session.node_id}",
                daemon=True,
            )
            self._thread.start()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        httpd, thread = self._httpd, self._thread
        self._httpd = None
        self._thread = None
        if httpd is not None:
            if thread is not None and thread.is_alive():
                httpd.shutdown()
            httpd.server_close()
        if thread is not None and thread.ident is not None:
            thread.join(timeout=5)
        with self._ready_condition:
            self._expected_launch_id = ""
            self._ready_registration = None
            self._ready_condition.notify_all()

    def expect_launch(self, launch_id: str) -> None:
        """Arm readiness for exactly one provider invocation before it starts.

        Arming a new invocation revokes the prior child immediately. A stale MCP
        child may still know the node token, but it can no longer register READY
        or submit calls under its retired launch identity.
        """

        expected_launch = _bounded_identity(launch_id, "launch id")
        with self._ready_condition:
            self._expected_launch_id = expected_launch
            self._ready_registration = None
            self._ready_condition.notify_all()

    def wait_ready(
        self,
        launch_id: str,
        timeout: float,
    ) -> ReadyRegistration | None:
        """Wait for the exact invocation-bound READY claim."""

        expected_launch = str(launch_id or "").strip()
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._ready_condition:
            while True:
                claim = self._ready_registration
                if (
                    claim is not None
                    and expected_launch == self._expected_launch_id
                    and claim.launch_id == expected_launch
                ):
                    return claim
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._ready_condition.wait(remaining)

    def handle_bytes(self, raw: bytes) -> dict[str, Any]:
        if not raw:
            return self._error("empty_request", "proof-tool endpoint request was empty")
        try:
            value = _strict_json_loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return self._error("invalid_json", "proof-tool endpoint request was not JSON")
        if not isinstance(value, dict):
            return self._error(
                "invalid_envelope", "proof-tool endpoint envelope must be an object"
            )
        return self.handle_envelope(value)

    def handle_envelope(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        version = str(envelope.get("envelope_version") or "")
        if version != self.manifest.envelope_version:
            return self._error(
                "envelope_version_mismatch",
                "proof-tool endpoint envelope version does not match",
            )
        token = str(envelope.get("token") or "")
        if not hmac.compare_digest(token, self.token):
            return self._error("unauthorized", "proof-tool endpoint token was rejected")
        kind = str(envelope.get("kind") or "")
        if kind == "ready":
            return self._handle_ready(envelope)
        if kind == "call":
            return self._handle_call(envelope)
        if kind == "source_resource":
            return self._handle_source_resource(envelope)
        return self._error("unknown_kind", "proof-tool endpoint envelope kind is unknown")

    def _handle_ready(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        try:
            launch_id = _bounded_identity(envelope.get("launch_id"), "launch id")
            protocol = _bounded_identity(
                envelope.get("negotiated_protocol"), "negotiated protocol"
            )
        except ValueError as exc:
            return self._error("invalid_identity", str(exc))

        with self._ready_condition:
            if launch_id != self._expected_launch_id:
                return self._error(
                    "unexpected_launch",
                    "proof-tool READY does not match the armed invocation "
                    f"(got {launch_id!r}, armed {self._expected_launch_id!r})",
                )
            self._ready_registration = ReadyRegistration(
                launch_id=launch_id,
                negotiated_protocol=protocol,
            )
            self._ready_condition.notify_all()
        return {
            "envelope_version": self.manifest.envelope_version,
            "kind": "ready_ack",
            "ok": True,
            "launch_id": launch_id,
            "negotiated_protocol": protocol,
        }

    def _handle_call(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        admitted, error = self._admit_call(envelope)
        if error is not None:
            return error
        assert admitted is not None
        if admitted.identity != PROOF_TOOL_IDENTITY:
            return self._error(
                "invalid_tool_identity",
                "proof-tool call identity does not match the active node contract",
            )

        response = self.session.submit(
            call_id=admitted.call_id,
            raw_arguments=admitted.raw_arguments,
            absolute_deadline=admitted.absolute_deadline,
        )
        return {
            "envelope_version": self.manifest.envelope_version,
            "kind": "call_result",
            "ok": True,
            "launch_id": admitted.launch_id,
            "call_id": admitted.call_id,
            "response": response.to_dict(),
        }

    def _handle_source_resource(
        self,
        envelope: Mapping[str, Any],
    ) -> dict[str, Any]:
        admitted, error = self._admit_call(envelope)
        if error is not None:
            return error
        assert admitted is not None
        if (
            not self.manifest.source_navigation_enabled
            or admitted.identity not in {
                SOURCE_READ_TOOL_IDENTITY,
                SOURCE_SEARCH_TOOL_IDENTITY,
                DECLARATION_RESOLVE_TOOL_IDENTITY,
            }
            or self.source_resource is None
        ):
            return self._error(
                "invalid_tool_identity",
                "source-resource call is not enabled by the active node contract",
            )
        if time.time() >= admitted.absolute_deadline:
            return self._error(
                "invalid_deadline",
                "source-resource absolute deadline expired",
            )
        if admitted.identity == DECLARATION_RESOLVE_TOOL_IDENTITY:
            remaining = admitted.absolute_deadline - time.time()
            if remaining <= 0:
                return self._error(
                    "invalid_deadline",
                    "source-resource absolute deadline expired",
                )
            response = self.source_resource.resolve_declaration(
                admitted.raw_arguments,
                call_id=admitted.call_id,
                # Leave a small transport margin so a native timeout can still
                # return a structured source-resource error to the provider.
                timeout_seconds=min(60.0, max(0.001, remaining - 0.25)),
            )
        else:
            operation = {
                SOURCE_READ_TOOL_IDENTITY: self.source_resource.read,
                SOURCE_SEARCH_TOOL_IDENTITY: self.source_resource.search,
            }[admitted.identity]
            response = operation(
                admitted.raw_arguments,
                call_id=admitted.call_id,
            )
        return {
            "envelope_version": self.manifest.envelope_version,
            "kind": "source_resource_result",
            "ok": True,
            "launch_id": admitted.launch_id,
            "call_id": admitted.call_id,
            "response": response.to_dict(),
        }

    def _admit_call(
        self,
        envelope: Mapping[str, Any],
    ) -> tuple[_AdmittedCall | None, dict[str, Any] | None]:
        """Validate the shared invocation/identity/deadline envelope once."""

        try:
            launch_id = _bounded_identity(envelope.get("launch_id"), "launch id")
            call_id = _bounded_identity(envelope.get("call_id"), "call id")
            protocol = _bounded_identity(
                envelope.get("negotiated_protocol"), "negotiated protocol"
            )
        except ValueError as exc:
            return None, self._error("invalid_identity", str(exc))
        with self._ready_condition:
            ready = self._ready_registration
            ready_valid = (
                ready is not None
                and launch_id == self._expected_launch_id
                and ready.launch_id == launch_id
                and ready.negotiated_protocol == protocol
            )
        if not ready_valid:
            return None, self._error(
                "invocation_not_ready",
                "manager-tool invocation has no exact READY registration",
            )
        raw_identity = envelope.get("tool_identity")
        if not isinstance(raw_identity, Mapping):
            return None, self._error(
                "invalid_tool_identity", "manager-tool identity must be an object"
            )
        try:
            identity = ToolIdentity(
                server=str(raw_identity.get("server") or ""),
                tool=str(raw_identity.get("tool") or ""),
            )
        except ValueError as exc:
            return None, self._error("invalid_tool_identity", str(exc))
        try:
            absolute_deadline = float(envelope.get("absolute_deadline"))
        except (TypeError, ValueError):
            return None, self._error(
                "invalid_deadline", "manager-tool absolute deadline must be numeric"
            )
        if (
            not math.isfinite(absolute_deadline)
            or absolute_deadline <= 0
        ):
            return None, self._error(
                "invalid_deadline", "manager-tool absolute deadline is invalid"
            )
        return _AdmittedCall(
            launch_id=launch_id,
            call_id=call_id,
            identity=identity,
            raw_arguments=envelope.get("raw_arguments"),
            absolute_deadline=absolute_deadline,
        ), None

    def _error(self, code: str, message: str) -> dict[str, Any]:
        return {
            "envelope_version": self.manifest.envelope_version,
            "kind": "error",
            "ok": False,
            "error": {"code": str(code), "message": str(message)},
        }


class ProofToolEndpointClient:
    """Private transport client used only by the stdio MCP adapter."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        token: str,
        launch_id: str,
        manifest: ProofToolContractManifest,
        negotiated_protocol: str,
        connect_timeout: float,
        endpoint_timeout: float,
        max_response_bytes: int = DEFAULT_MAX_ENDPOINT_MESSAGE_BYTES,
    ) -> None:
        self.host = str(host)
        self.port = int(port)
        self.token = str(token)
        self.launch_id = str(launch_id)
        self.manifest = manifest
        self.negotiated_protocol = str(negotiated_protocol)
        self.connect_timeout = max(0.001, float(connect_timeout))
        self.endpoint_timeout = max(0.001, float(endpoint_timeout))
        self.max_response_bytes = max(1024, int(max_response_bytes))

    def ready(self) -> ReadyRegistration:
        data = self._roundtrip({
            **self._base_envelope("ready"),
            "negotiated_protocol": self.negotiated_protocol,
        }, timeout=self.endpoint_timeout)
        if data.get("kind") != "ready_ack" or data.get("ok") is not True:
            raise _endpoint_error(data)
        return ReadyRegistration(
            launch_id=self.launch_id,
            negotiated_protocol=self.negotiated_protocol,
        )

    def call(
        self,
        *,
        call_id: str,
        raw_arguments: Any,
        absolute_deadline: float,
    ) -> ProofToolSessionResponse:
        remaining = float(absolute_deadline) - time.time()
        if remaining <= 0:
            raise ProofToolEndpointError(
                "proof-tool call deadline expired before endpoint submission"
            )
        data = self._roundtrip({
            **self._base_envelope("call"),
            "call_id": str(call_id),
            "negotiated_protocol": self.negotiated_protocol,
            "tool_identity": self.manifest.identity.to_dict(),
            "raw_arguments": raw_arguments,
            "absolute_deadline": float(absolute_deadline),
        }, timeout=min(self.endpoint_timeout, remaining))
        if data.get("kind") != "call_result" or data.get("ok") is not True:
            raise _endpoint_error(data)
        raw_response = data.get("response")
        if not isinstance(raw_response, Mapping):
            raise ProofToolEndpointError("proof-tool call result is missing response")
        try:
            directive = TurnDirective(str(raw_response.get("directive") or ""))
            return ProofToolSessionResponse(
                exit_code=int(raw_response.get("exit_code")),
                text=str(raw_response.get("text") or ""),
                turn_index=int(raw_response.get("turn_index")),
                directive=directive,
                manager_turn_completed=(
                    raw_response.get("manager_turn_completed") is True
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ProofToolEndpointError(
                "proof-tool call result has invalid response fields"
            ) from exc

    def source_resource(
        self,
        *,
        tool_identity: ToolIdentity,
        call_id: str,
        raw_arguments: Any,
        absolute_deadline: float,
    ) -> EasyCryptSourceResponse:
        if tool_identity not in {
            SOURCE_READ_TOOL_IDENTITY,
            SOURCE_SEARCH_TOOL_IDENTITY,
            DECLARATION_RESOLVE_TOOL_IDENTITY,
        }:
            raise ProofToolEndpointError(
                "source-resource client received an unknown tool identity"
            )
        remaining = float(absolute_deadline) - time.time()
        if remaining <= 0:
            raise ProofToolEndpointError(
                "source-resource call deadline expired before endpoint submission"
            )
        data = self._roundtrip({
            **self._base_envelope("source_resource"),
            "call_id": str(call_id),
            "negotiated_protocol": self.negotiated_protocol,
            "tool_identity": tool_identity.to_dict(),
            "raw_arguments": raw_arguments,
            "absolute_deadline": float(absolute_deadline),
        }, timeout=min(self.endpoint_timeout, remaining))
        if (
            data.get("kind") != "source_resource_result"
            or data.get("ok") is not True
        ):
            raise _endpoint_error(data)
        raw_response = data.get("response")
        if not isinstance(raw_response, Mapping):
            raise ProofToolEndpointError(
                "source-resource call result is missing response"
            )
        text = raw_response.get("text")
        is_error = raw_response.get("is_error")
        if not isinstance(text, str) or not isinstance(is_error, bool):
            raise ProofToolEndpointError(
                "source-resource call result has invalid response fields"
            )
        return EasyCryptSourceResponse(text=text, is_error=is_error)

    def _base_envelope(self, kind: str) -> dict[str, Any]:
        return {
            "envelope_version": self.manifest.envelope_version,
            "kind": kind,
            "token": self.token,
            "launch_id": self.launch_id,
        }

    def _roundtrip(
        self,
        envelope: Mapping[str, Any],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        payload = _canonical_json_bytes(envelope) + b"\n"
        if len(payload) > DEFAULT_MAX_ENDPOINT_MESSAGE_BYTES:
            raise ProofToolEndpointError("proof-tool endpoint request is too large")
        with socket.create_connection(
            (self.host, self.port),
            timeout=min(self.connect_timeout, timeout),
        ) as sock:
            sock.settimeout(timeout)
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            response = _read_bounded(sock, self.max_response_bytes)
        if not response:
            raise ProofToolEndpointError("proof-tool endpoint closed without a response")
        try:
            value = _strict_json_loads(response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ProofToolEndpointError(
                "proof-tool endpoint returned invalid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise ProofToolEndpointError(
                "proof-tool endpoint returned a non-object envelope"
            )
        if str(value.get("envelope_version") or "") != self.manifest.envelope_version:
            raise ProofToolEndpointError(
                "proof-tool endpoint response version mismatch"
            )
        return value


def _bounded_identity(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 512:
        raise ValueError(f"proof-tool {label} is missing or too long")
    return text


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_json_loads(text: str) -> Any:
    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON number is forbidden: {value}")

    return json.loads(text, parse_constant=reject_constant)


def _read_bounded(sock: socket.socket, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = sock.recv(min(65536, limit - total + 1))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise ProofToolEndpointError("proof-tool endpoint response is too large")


def _endpoint_error(data: Mapping[str, Any]) -> ProofToolEndpointError:
    raw = data.get("error")
    if isinstance(raw, Mapping):
        code = str(raw.get("code") or "endpoint_error")
        message = str(raw.get("message") or "proof-tool endpoint rejected request")
        return ProofToolEndpointError(f"{code}: {message}")
    return ProofToolEndpointError("proof-tool endpoint rejected request")
