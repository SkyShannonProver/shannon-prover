"""Provider-neutral, invocation-bound agent event lifecycle validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol

from workflow.proof_tool.proof_tool_contract import (
    PROOF_TOOL_IDENTITY,
    ProofToolContractManifest,
    ToolIdentity,
)


class AgentEventKind(str, Enum):
    INVOCATION_STARTED = "invocation_started"
    TURN_STARTED = "turn_started"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    MESSAGE_COMPLETED = "message_completed"
    PASSIVE = "passive"
    TERMINAL_COMPLETED = "terminal_completed"
    TERMINAL_FAILED = "terminal_failed"
    PROVIDER_ERROR = "provider_error"


HOST_METADATA_CAPABILITY = "host_metadata"


@dataclass(frozen=True)
class CanonicalAgentEvent:
    invocation_id: str
    provider: str
    kind: AgentEventKind
    raw_event_type: str
    session_id: str = ""
    item_id: str = ""
    tool: ToolIdentity | None = None
    capability: str = ""
    raw_arguments: Any = None
    host_metadata_arguments_valid: bool | None = None
    host_metadata_result_empty: bool | None = None


@dataclass(frozen=True)
class EventNormalizationResult:
    events: tuple[CanonicalAgentEvent, ...] = ()
    violations: tuple[str, ...] = ()


class ProviderEventNormalizer(Protocol):
    invocation_id: str

    def normalize(
        self,
        raw: str | Mapping[str, Any],
    ) -> EventNormalizationResult: ...


@dataclass(frozen=True)
class AgentCapabilityPolicy:
    allowed_tools: frozenset[ToolIdentity] = field(default_factory=frozenset)
    allowed_provider_capabilities: frozenset[str] = field(
        default_factory=frozenset
    )
    allow_empty_host_metadata: bool = False
    allow_all_known_tools: bool = False

    @classmethod
    def proof_eval(
        cls,
        manifest: ProofToolContractManifest,
        *,
        allow_empty_host_metadata: bool = True,
    ) -> "AgentCapabilityPolicy":
        return cls(
            allowed_tools=frozenset({manifest.identity}),
            allow_empty_host_metadata=allow_empty_host_metadata,
        )


@dataclass(frozen=True)
class LifecycleRequirements:
    require_invocation_started: bool = True
    require_turn_started: bool = False
    require_terminal: bool = True
    require_completed_message: bool = True
    require_process_exit: bool = True
    fail_on_provider_error: bool = True

    @classmethod
    def tool_policy_only(cls) -> "LifecycleRequirements":
        return cls(
            require_invocation_started=False,
            require_turn_started=False,
            require_terminal=False,
            require_completed_message=False,
            require_process_exit=False,
            fail_on_provider_error=True,
        )


@dataclass(frozen=True)
class LifecycleDecision:
    allowed: bool
    reason: str = ""


@dataclass(frozen=True)
class InvocationEventAudit:
    invocation_id: str
    provider: str
    proof_tool_started: int
    proof_tool_completed: int
    host_metadata_calls: int
    provider_errors: int
    terminal_kind: str
    process_exit: int | None
    violations: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class _PendingTool:
    tool: ToolIdentity
    capability: str


class AgentEventLifecycleGuard:
    """Validate one exact provider invocation, live or offline."""

    def __init__(
        self,
        *,
        invocation_id: str,
        provider: str,
        capability_policy: AgentCapabilityPolicy,
        requirements: LifecycleRequirements | None = None,
    ) -> None:
        if not invocation_id:
            raise ValueError("event lifecycle requires an invocation identity")
        if not provider:
            raise ValueError("event lifecycle requires a provider name")
        self.invocation_id = invocation_id
        self.provider = provider
        self.capability_policy = capability_policy
        self.requirements = requirements or LifecycleRequirements()
        self._pending: dict[str, _PendingTool] = {}
        self._seen_item_ids: set[str] = set()
        self._violations: list[str] = []
        self._invocation_started = 0
        self._turn_started = 0
        self._completed_messages = 0
        self._terminals: list[AgentEventKind] = []
        self._proof_tool_started = 0
        self._proof_tool_completed = 0
        self._host_metadata_calls = 0
        self._provider_errors = 0
        self._events_observed = 0
        self._finished = False

    def record_violation(self, reason: str) -> None:
        value = str(reason).strip()
        if value:
            self._violations.append(value)

    def observe(self, event: CanonicalAgentEvent) -> LifecycleDecision:
        before = len(self._violations)
        if self._finished:
            self.record_violation("event observed after invocation finalization")
            return LifecycleDecision(False, self._violations[-1])
        if event.invocation_id != self.invocation_id:
            self.record_violation("provider event crossed invocation identity")
            return LifecycleDecision(False, self._violations[-1])
        if event.provider != self.provider:
            self.record_violation("provider event changed provider identity")
            return LifecycleDecision(False, self._violations[-1])
        if self._terminals:
            self.record_violation("provider event arrived after terminal event")

        kind = event.kind
        self._observe_order(kind)
        if kind == AgentEventKind.INVOCATION_STARTED:
            self._invocation_started += 1
            if not event.session_id:
                self.record_violation("provider invocation is missing session identity")
            if self._invocation_started > 1:
                self.record_violation("provider invocation started more than once")
        elif kind == AgentEventKind.TURN_STARTED:
            self._turn_started += 1
            if self._turn_started > 1:
                self.record_violation("provider turn started more than once")
        elif kind == AgentEventKind.TOOL_STARTED:
            self._observe_tool_started(event)
        elif kind == AgentEventKind.TOOL_COMPLETED:
            self._observe_tool_completed(event)
        elif kind == AgentEventKind.MESSAGE_COMPLETED:
            self._completed_messages += 1
        elif kind in {
            AgentEventKind.TERMINAL_COMPLETED,
            AgentEventKind.TERMINAL_FAILED,
        }:
            self._terminals.append(kind)
            if len(self._terminals) > 1:
                self.record_violation("provider emitted more than one terminal event")
        elif kind == AgentEventKind.PROVIDER_ERROR:
            self._provider_errors += 1
        elif kind != AgentEventKind.PASSIVE:
            self.record_violation(f"unknown canonical event kind {kind!r}")
        self._events_observed += 1

        if len(self._violations) == before:
            return LifecycleDecision(True)
        return LifecycleDecision(False, self._violations[-1])

    def finish(
        self,
        *,
        process_exit: int | None,
        cancelled: bool = False,
    ) -> InvocationEventAudit:
        if self._finished:
            raise RuntimeError("provider invocation was finalized more than once")
        self._finished = True
        if self._pending:
            self.record_violation(
                "provider tool calls did not complete: "
                + ", ".join(sorted(self._pending))
            )
        if (
            self.requirements.require_invocation_started
            and self._invocation_started != 1
        ):
            self.record_violation("expected exactly one invocation-start event")
        if self.requirements.require_turn_started and self._turn_started != 1:
            self.record_violation("expected exactly one turn-start event")
        if (
            not cancelled
            and self.requirements.require_terminal
            and len(self._terminals) != 1
        ):
            self.record_violation("expected exactly one terminal turn event")
        if (
            not cancelled
            and self.requirements.require_completed_message
            and self._completed_messages < 1
            # See _observe_order: a FAILED terminal (auth/quota error before
            # the model spoke) legitimately has no completed message.
            and self._terminals != [AgentEventKind.TERMINAL_FAILED]
        ):
            self.record_violation("expected at least one completed agent message")
        if self.requirements.require_process_exit and process_exit is None:
            self.record_violation("provider process exit is missing")
        terminal = self._terminals[0] if len(self._terminals) == 1 else None
        if not cancelled and process_exit is not None and terminal is not None:
            if terminal == AgentEventKind.TERMINAL_COMPLETED and process_exit != 0:
                self.record_violation(
                    "provider completed turn but process exited nonzero"
                )
            if terminal == AgentEventKind.TERMINAL_FAILED and process_exit == 0:
                self.record_violation(
                    "provider failed turn but process exited successfully"
                )
        if self._provider_errors and self.requirements.fail_on_provider_error:
            self.record_violation("provider error event was observed")
        return InvocationEventAudit(
            invocation_id=self.invocation_id,
            provider=self.provider,
            proof_tool_started=self._proof_tool_started,
            proof_tool_completed=self._proof_tool_completed,
            host_metadata_calls=self._host_metadata_calls,
            provider_errors=self._provider_errors,
            terminal_kind=terminal.value if terminal is not None else "",
            process_exit=process_exit,
            violations=tuple(self._violations),
        )

    def _observe_order(self, kind: AgentEventKind) -> None:
        """Reject valid-looking cardinalities emitted in an invalid order."""

        if kind == AgentEventKind.INVOCATION_STARTED:
            if self._events_observed:
                self.record_violation(
                    "provider invocation start arrived after other events"
                )
            return

        if kind == AgentEventKind.TURN_STARTED:
            if self._invocation_started != 1:
                self.record_violation(
                    "provider turn started before invocation start"
                )
            if self._turn_started or self._completed_messages or self._terminals:
                self.record_violation("provider turn start was out of order")
            return

        if (
            self.requirements.require_invocation_started
            and self._invocation_started != 1
        ):
            self.record_violation("provider event arrived before invocation start")
        if self.requirements.require_turn_started and self._turn_started != 1:
            self.record_violation("provider event arrived before turn start")

        if kind == AgentEventKind.MESSAGE_COMPLETED and self._pending:
            self.record_violation(
                "provider agent message completed before tool calls completed"
            )

        if kind in {
            AgentEventKind.TERMINAL_COMPLETED,
            AgentEventKind.TERMINAL_FAILED,
        }:
            if self._pending:
                self.record_violation(
                    "provider terminal arrived before tool calls completed"
                )
            if (
                self.requirements.require_completed_message
                and self._completed_messages < 1
                # A FAILED terminal legitimately arrives with no agent message
                # (auth/quota errors fail the turn before the model speaks);
                # flagging it here buried the provider's own error text behind
                # an ordering violation (observed live 2026-08-19: a Codex
                # usage-limit error surfaced only as this message).
                and kind is not AgentEventKind.TERMINAL_FAILED
            ):
                self.record_violation(
                    "provider terminal arrived before completed agent message"
                )

    def _observe_tool_started(self, event: CanonicalAgentEvent) -> None:
        if not event.item_id:
            self.record_violation("provider tool start is missing item identity")
            return
        if event.item_id in self._seen_item_ids:
            self.record_violation("provider tool item identity was reused")
            return
        if event.tool is None:
            self.record_violation("provider tool start is missing tool identity")
            return
        self._seen_item_ids.add(event.item_id)
        self._pending[event.item_id] = _PendingTool(
            tool=event.tool,
            capability=event.capability,
        )
        if self.capability_policy.allow_all_known_tools:
            if event.tool == PROOF_TOOL_IDENTITY:
                self._proof_tool_started += 1
            return
        if event.capability == HOST_METADATA_CAPABILITY:
            if not self.capability_policy.allow_empty_host_metadata:
                self.record_violation("provider host metadata capability is disabled")
            if event.host_metadata_arguments_valid is not True:
                self.record_violation("provider host metadata arguments are invalid")
            return
        if event.tool in self.capability_policy.allowed_tools:
            if event.tool == PROOF_TOOL_IDENTITY:
                self._proof_tool_started += 1
            return
        if event.capability in self.capability_policy.allowed_provider_capabilities:
            return
        self.record_violation(
            "provider attempted a disabled tool: "
            f"{event.tool.server}:{event.tool.tool}"
        )

    def _observe_tool_completed(self, event: CanonicalAgentEvent) -> None:
        if not event.item_id:
            self.record_violation("provider tool completion is missing item identity")
            return
        pending = self._pending.pop(event.item_id, None)
        if pending is None:
            self.record_violation("provider tool completed without matching start")
            return
        if event.tool is not None and event.tool != pending.tool:
            self.record_violation("provider tool identity changed before completion")
        if event.capability and event.capability != pending.capability:
            self.record_violation("provider tool capability changed before completion")
        if self.capability_policy.allow_all_known_tools:
            if pending.tool == PROOF_TOOL_IDENTITY:
                self._proof_tool_completed += 1
            return
        if pending.capability == HOST_METADATA_CAPABILITY:
            if event.host_metadata_result_empty is not True:
                self.record_violation(
                    "provider host metadata returned non-empty or invalid content"
                )
            else:
                self._host_metadata_calls += 1
        elif pending.tool == PROOF_TOOL_IDENTITY:
            self._proof_tool_completed += 1


def audit_normalized_invocation(
    records: Iterable[str | Mapping[str, Any]],
    *,
    normalizer: ProviderEventNormalizer,
    guard: AgentEventLifecycleGuard,
    process_exit: int | None,
    cancelled: bool = False,
) -> InvocationEventAudit:
    """Apply the same normalizer/guard sequence used by a live runner."""

    for raw in records:
        normalized = normalizer.normalize(raw)
        for reason in normalized.violations:
            guard.record_violation(reason)
        for event in normalized.events:
            guard.observe(event)
    return guard.finish(process_exit=process_exit, cancelled=cancelled)
