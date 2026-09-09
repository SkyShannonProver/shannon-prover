"""Provider session layer for one managed proof node.

Hosts the per-node Claude Code / OpenAI Codex agent subprocess: launch,
normalized event-stream driving, invocation-bound MCP readiness, and
context-watermark detection.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from workflow.provider.claude_event_normalizer import ClaudeEventNormalizer
from workflow.provider.codex_event_normalizer import (
    CodexEventNormalizer,
    codex_event_text,
)
from workflow.provider.provider_event_lifecycle import (
    AgentCapabilityPolicy,
    AgentEventKind,
    AgentEventLifecycleGuard,
    LifecycleRequirements,
)
from workflow.schemas.config import normalize_agent_backend
from workflow.proof_tool.proof_tool_contract import ProofToolContractManifest
from workflow.proof_tool.proof_tool_launch import (
    CodexCapabilities,
    ProofMcpLaunchSpec,
    codex_feature_disable_args,
    discover_codex_capabilities,
    render_claude_mcp_config,
    render_codex_mcp_overrides,
)
from workflow.provider.prover_io_policy import destructive_tool_denylist
from workflow.provider.eval_agent_confinement import EvalAgentConfinement
from workflow.provider.ctx_respawn import (
    CtxWatermarkDetector,
    context_tokens_from_codex_event,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_BIN = shutil.which("claude") or "claude"
CODEX_BIN = shutil.which("codex") or "codex"

_PROVIDER_CLI_IDENTITY_CACHE: dict[str, dict[str, str]] = {}


def provider_cli_identity(agent_backend: str) -> dict[str, str]:
    """Version + path of the provider CLI this run will actually launch.

    EasyCrypt is commit-pinned and every session records its build identity;
    the agent CLI is the other half of the measured system and its version
    drift has produced real failures (Claude system-subtype events, Codex
    alpha event shapes — both observed live 2026-08-19). Recorded per run so
    win-rate comparisons across time can rule the harness version in or out.
    The provider layer records probe failures; eval wrappers may require the
    complete identity and fail closed when any required field is unavailable.
    """
    backend = str(agent_backend or "codex")
    cached = _PROVIDER_CLI_IDENTITY_CACHE.get(backend)
    if cached is not None:
        return cached
    binary = CODEX_BIN if backend == "codex" else CLAUDE_BIN
    launch_path = shutil.which(binary) or binary
    resolved_path = launch_path
    binary_sha256 = ""
    try:
        resolved_file = Path(launch_path).resolve(strict=True)
        if resolved_file.is_file():
            binary_sha256 = hashlib.sha256(resolved_file.read_bytes()).hexdigest()
            resolved_path = str(resolved_file)
    except OSError:
        pass
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        raw = (proc.stdout or proc.stderr or "").strip()
        version = raw.splitlines()[0].strip() if raw else ""
        if not version:
            version = f"unknown (empty --version output, rc={proc.returncode})"
    except Exception as exc:
        version = f"unknown ({type(exc).__name__}: {exc})"
    identity = {
        "agent_backend": backend,
        "binary": binary,
        "resolved_path": resolved_path,
        "binary_sha256": binary_sha256,
        "version": version,
    }
    _PROVIDER_CLI_IDENTITY_CACHE[backend] = identity
    return identity


@dataclass(frozen=True)
class ClaudeRunResult:
    text: str
    session_id: str
    returncode: int
    turns: int = 0


# Provider-neutral name for new code; retain the historical import for tests
# and downstream tooling that still imports ``ClaudeRunResult``.
AgentRunResult = ClaudeRunResult


# How many of the agent's most-recent assistant message texts to keep in the
# in-memory ring buffer and forward (verdict-stripped) on a watermark respawn.
_RECENT_REASONING_K = max(0, int(
    os.environ.get("SHANNON_RECENT_REASONING_K", "3")))


class _ProviderAgentSessionBase:
    """Provider-neutral process, readiness, and session-registration lifecycle."""

    provider_name = ""

    def __init__(
        self,
        *,
        model: str,
        effort: str = "high",
        source_file: str,
        session_tag: str,
        project_root: Path = _PROJECT_ROOT,
        emit: Callable[[dict[str, Any]], None] | None = None,
        on_session_id: Callable[[str], None] | None = None,
        eval_mode: bool = False,
        eval_confinement: EvalAgentConfinement | None = None,
        proof_tool_manifest: ProofToolContractManifest | None = None,
        readiness_issuer: Callable[[str], None] | None = None,
        readiness_waiter: Callable[[str, float], object | None] | None = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.source_file = source_file
        self.session_tag = session_tag
        self.project_root = Path(project_root)
        self.eval_mode = bool(eval_mode or eval_confinement is not None)
        self.eval_confinement = eval_confinement
        self.proof_tool_manifest = proof_tool_manifest
        self.readiness_issuer = readiness_issuer
        self.readiness_waiter = readiness_waiter
        self.emit = emit or (lambda event: None)
        # Canonical session-registration hook: called exactly once per Claude
        # session id, at the moment the id is first observed on the stream —
        # i.e. at session CREATION, not at teardown. A watermark respawn or a
        # supervisor kill can end a generation without a `result` event, so
        # any registration deferred to end-of-run loses the current session.
        self.on_session_id = on_session_id or (lambda session_id: None)
        self._notified_session_ids: set[str] = set()
        self.proc: subprocess.Popen[str] | None = None
        self.session_id = ""
        # Set by the readiness watchdog when the MCP stdio server never came up
        # for the most recent run() (so the caller can relaunch). Reset per run.
        self.mcp_failed_to_start = False
        # Fresh-context continuation (Layer 1): a per-turn token-watermark
        # detector. When this session's context crosses the watermark for
        # `SHANNON_CTX_WATERMARK_TURNS` consecutive assistant turns, we gracefully
        # end the loop BETWEEN turns and surface `ctx_pressure` so the runtime can
        # swap in a fresh Claude context against the SAME bridge/manager/EC
        # session (zero replay). See docs/design/fresh_context_continuation.md.
        self._ctx_detector = CtxWatermarkDetector()
        self.ctx_pressure = False
        # Transient, in-memory ring buffer of the last K assistant message texts
        # (the agent's own reasoning). On a watermark respawn this is forwarded —
        # verdict-stripped — so the fresh context CONTINUES the work instead of
        # re-diagnosing from scratch. Deliberately NOT persisted to node_memory /
        # run artifacts (CLAUDE.md: artifacts never store thinking text).
        self._recent_reasoning: list[str] = []
        self._recent_reasoning_cap = _RECENT_REASONING_K
        # True once any run() of this session object has opened the provider
        # event log; later generations append instead of truncating it.
        self._event_log_started = False

    def _notify_session_id(self, session_id: str) -> None:
        """Fire the registration hook once per distinct session id."""

        sid = str(session_id or "").strip()
        if not sid or sid in self._notified_session_ids:
            return
        self._notified_session_ids.add(sid)
        try:
            self.on_session_id(sid)
        except Exception as exc:
            print(
                f"agent session registration hook failed for {sid!r}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )

    def _watch_mcp_readiness(
        self,
        proc: subprocess.Popen[str],
        launch_id: str,
        timeout_s: float,
    ) -> None:
        """Require an invocation-bound readiness receipt from the MCP child."""

        waiter = self.readiness_waiter
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        ready: object | None = None
        failure_detail = ""
        while proc.poll() is None and time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                ready = (
                    waiter(launch_id, min(1.0, remaining))
                    if waiter is not None
                    else None
                )
            except Exception as exc:
                # A waiter crash is NOT the same failure as a readiness
                # timeout; carry the reason into the spawn-failed event.
                failure_detail = f"waiter raised {type(exc).__name__}: {exc}"
                ready = None
                break
            if ready is not None:
                return
            if waiter is None:
                break
        # The child may exit before the loop observes it. Check the registry one
        # final time, then classify a missing exact receipt as an MCP startup
        # failure regardless of provider-process liveness so the runtime's
        # bounded retry path is used consistently.
        if ready is None and waiter is not None and not failure_detail:
            try:
                ready = waiter(launch_id, 0.0)
            except Exception as exc:
                failure_detail = f"waiter raised {type(exc).__name__}: {exc}"
                ready = None
        if ready is not None:
            return
        self.mcp_failed_to_start = True
        self.emit({
            "type": "system",
            "mcp_spawn_failed": True,
            "timeout_s": timeout_s,
            "launch_id": launch_id,
            "session_tag": self.session_tag,
            "detail": failure_detail or (
                "child exited before READY"
                if proc.poll() is not None
                else "no READY registration before the deadline"
            ),
            "child_returncode": proc.poll(),
        })
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def close(self, reason: str) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        self.emit({
            "type": "system",
            "long_lived_agent": True,
            "closing_reason": reason,
        })
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)

    # -- shared run() building blocks -------------------------------------
    # Both provider run() methods used to hand-copy these nine blocks; the
    # copies had already drifted (thread names, tail assembly, event-log
    # truncation). run() itself stays per-provider so each launch reads
    # top-to-bottom in one place.

    def _mint_launch(self, mcp_launch_spec: "ProofMcpLaunchSpec | None") -> str:
        """Reset per-run MCP state, mint one launch id, arm endpoint readiness."""
        self.mcp_failed_to_start = False
        if mcp_launch_spec is None:
            return ""
        if (
            self.proof_tool_manifest is None
            or self.proof_tool_manifest != mcp_launch_spec.manifest
        ):
            raise ValueError(
                "agent session proof-tool manifest mismatch: session has "
                f"{self.proof_tool_manifest!r}, launch spec has "
                f"{mcp_launch_spec.manifest!r}"
            )
        if self.readiness_issuer is None:
            raise ValueError("agent session has no readiness issuer")
        launch_id = uuid.uuid4().hex
        self.readiness_issuer(launch_id)
        return launch_id

    def _launch_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["EC_SESSION_DIR"] = f".ec_session_{self.session_tag}"
        return env

    def _spawn(
        self,
        cmd: list[str],
        *,
        env: dict[str, str],
        pipe_stdin: bool = False,
    ) -> subprocess.Popen[str]:
        launch_cmd = (
            self.eval_confinement.wrap_command(
                cmd, agent_backend=self.provider_name
            )
            if self.eval_confinement is not None
            else cmd
        )
        self.proc = subprocess.Popen(
            launch_cmd,
            cwd=str(self.project_root),
            env=env,
            stdin=subprocess.PIPE if pipe_stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return self.proc

    def _start_readiness_watchdog(
        self,
        launch_id: str,
        mcp_launch_spec: "ProofMcpLaunchSpec | None",
    ) -> threading.Thread | None:
        if mcp_launch_spec is None:
            return None
        watchdog = threading.Thread(
            target=self._watch_mcp_readiness,
            args=(
                self.proc,
                launch_id,
                mcp_launch_spec.timing.startup_seconds,
            ),
            name=f"mcp-readiness-{self.provider_name}-{self.session_tag}",
            daemon=True,
        )
        watchdog.start()
        return watchdog

    def _start_stderr_drain(self) -> tuple[threading.Thread, list[str]]:
        chunks: list[str] = []

        def _drain() -> None:
            if self.proc is None or self.proc.stderr is None:
                return
            chunks.append(self.proc.stderr.read())

        thread = threading.Thread(
            target=_drain,
            name=f"{self.provider_name}-stderr-{self.session_tag}",
            daemon=True,
        )
        thread.start()
        return thread, chunks

    def _finish_run(
        self,
        *,
        event_guard: "AgentEventLifecycleGuard | None",
        event_violation: str,
        result_text: str,
        error_texts: list[str],
        stderr_chunks: list[str],
        stderr_thread: threading.Thread,
        watchdog: threading.Thread | None,
    ) -> tuple[int, str]:
        """Wait, audit, and assemble the final (returncode, text) pair.

        A guard violation fails the run closed but never replaces the
        provider's own error text — a violation alone once buried a plain
        quota error two layers deep.
        """
        returncode = self.proc.wait()
        if event_guard is not None:
            audit = event_guard.finish(
                process_exit=returncode,
                cancelled=self.ctx_pressure,
            )
            if audit.violations and not event_violation:
                event_violation = audit.violations[0]
        stderr_thread.join(timeout=5)
        if watchdog is not None:
            watchdog.join(timeout=2)
        stderr = "".join(stderr_chunks)
        if event_violation:
            returncode = 2
            detail = (
                "\n".join(
                    text
                    for text in dict.fromkeys(error_texts)
                    if text != event_violation
                ).strip()
                or stderr.strip()
            )
            result_text = (
                f"{event_violation}\nprovider errors:\n{detail}"
                if detail
                else event_violation
            )
        elif returncode != 0 and not result_text:
            result_text = (
                "\n".join(dict.fromkeys(error_texts)).strip() or stderr.strip()
            )
        if self.session_id:
            self.emit({
                "type": "system",
                "session_id": self.session_id,
                "agent_backend": self.provider_name,
                "long_lived_agent": True,
            })
        return returncode, result_text


def _watermark_stop_ready(
    *,
    ctx_pressure: bool,
    event_guard: "AgentEventLifecycleGuard | None",
) -> bool:
    """Terminate a saturated provider only at a completed tool boundary."""

    return bool(ctx_pressure) and (
        event_guard is None or not event_guard.has_pending_tool_calls
    )


class ClaudeAgentSession(_ProviderAgentSessionBase):
    """One long-lived Claude Code subprocess for a proof node."""

    provider_name = "claude"

    def run(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        mcp_launch_spec: ProofMcpLaunchSpec | None = None,
    ) -> ClaudeRunResult:
        launch_id = self._mint_launch(mcp_launch_spec)
        mcp_config_path: Path | None = None
        if mcp_launch_spec is not None:
            mcp_config_path = (
                mcp_launch_spec.private_dir
                / f"claude_mcp_{launch_id}.json"
            )
            mcp_config_path.parent.mkdir(parents=True, exist_ok=True)
            mcp_config_path.write_text(
                json.dumps(
                    render_claude_mcp_config(
                        mcp_launch_spec,
                        launch_id=launch_id,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            mcp_config_path.chmod(0o600)
        cmd = [
            CLAUDE_BIN,
            "-p",
            prompt,
            "--model",
            self.model,
            "--effort",
            self.effort,
            # Durable per-node anchors (LEGAL_* file paths + the one-intent-per-turn
            # invariant) go in the SYSTEM prompt, which Claude preserves across
            # context compaction — so we no longer re-inject them into every turn's
            # followup. Empty on callers that don't supply one.
            *(["--append-system-prompt", system_prompt] if system_prompt.strip() else []),
            "--dangerously-skip-permissions",
            "--disallowedTools",
            *(
                (
                    "Bash(*)",
                    "Read(*)",
                    "Write(*)",
                    "Edit(*)",
                    "Glob(*)",
                    "Grep(*)",
                    "NotebookEdit(*)",
                    "WebSearch(*)",
                    "WebFetch(*)",
                    "Agent(*)",
                    "Task(*)",
                )
                if self.eval_mode
                else ()
            ),
            *destructive_tool_denylist(
                self.source_file,
                project_root=self.project_root,
            ),
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-thinking-tokens",
            "4000",
        ]
        if mcp_config_path is not None:
            cmd.extend([
                "--mcp-config",
                str(mcp_config_path),
                "--strict-mcp-config",
            ])
        env = self._launch_env()
        # Each run() launches a NEW `claude` process, which mints a NEW session
        # id — a stale id from the previous generation must never mask the
        # continuation's id (that was exactly the bug that orphaned every
        # post-respawn session from the run manifest).
        self.session_id = ""
        # Each generation starts with a clean watermark detector: the fresh
        # context begins near the post-compact floor, so prior hot turns must not
        # carry over.
        self._ctx_detector.reset()
        self.ctx_pressure = False
        # Fresh generation -> fresh reasoning buffer (only the dying generation's
        # own recent reasoning should ever be forwarded on its respawn).
        self._recent_reasoning = []
        self._spawn(cmd, env=env)
        result_text = ""
        watchdog = self._start_readiness_watchdog(launch_id, mcp_launch_spec)

        normalizer = (
            ClaudeEventNormalizer(
                invocation_id=launch_id,
                manifest=mcp_launch_spec.manifest,
            )
            if mcp_launch_spec is not None
            else None
        )
        event_guard = (
            AgentEventLifecycleGuard(
                invocation_id=launch_id,
                provider="claude",
                # Eval mode: only the proof tool is legal. A plain /prove run
                # explicitly grants Read/Bash for source context (the CLI's
                # denylist + post-hoc IO policing are that mode's guardrails);
                # gating them here killed a live node on its first Bash.
                capability_policy=(
                    AgentCapabilityPolicy.proof_eval(
                        mcp_launch_spec.manifest,
                        allow_empty_host_metadata=False,
                    )
                    if self.eval_mode
                    else AgentCapabilityPolicy(allow_all_known_tools=True)
                ),
            )
            if mcp_launch_spec is not None
            else None
        )
        event_violation = ""
        stderr_thread, stderr_chunks = self._start_stderr_drain()
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\n")
            if not line:
                continue
            if normalizer is not None and event_guard is not None:
                normalized = normalizer.normalize(line)
                violations = list(normalized.violations)
                for reason in normalized.violations:
                    event_guard.record_violation(reason)
                for event_record in normalized.events:
                    decision = event_guard.observe(event_record)
                    if not decision.allowed:
                        violations.append(decision.reason)
                if violations:
                    event_violation = violations[0]
                    if self.proc.poll() is None:
                        self.proc.terminate()
                    break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event_violation = "invalid Claude JSON event"
                if self.proc.poll() is None:
                    self.proc.terminate()
                break
            if event.get("session_id") and not self.session_id:
                self.session_id = str(event.get("session_id") or "")
                self._notify_session_id(self.session_id)
            if event.get("type") == "result":
                result_text = str(event.get("result") or "")
                if event.get("session_id"):
                    self.session_id = str(event.get("session_id") or self.session_id)
                    self._notify_session_id(self.session_id)
                continue
            self.emit(event)
            # Keep the agent's recent reasoning in an in-memory ring buffer so a
            # watermark respawn can forward it (Change 3). Best-effort; a failure
            # here must never disturb the stream loop.
            try:
                self._capture_reasoning(event)
            except Exception:
                pass
            # Layer 1: token-watermark detection. Latch pressure immediately,
            # but never terminate between a tool request and its result. Besides
            # preserving the useful result, this lets the invocation lifecycle
            # close cleanly instead of reclassifying an ordinary context refresh
            # as an infrastructure-invalid pending-tool failure.
            if self._ctx_detector.observe(event):
                self.ctx_pressure = True
                self.emit({
                    "type": "system",
                    "ctx_watermark_tripped": True,
                    "ctx_tokens": self._ctx_detector.last_ctx_tokens,
                    "hot_turns": self._ctx_detector.hot_turns,
                    "watermark_tokens": self._ctx_detector.tokens,
                    "session_tag": self.session_tag,
                })
            if _watermark_stop_ready(
                ctx_pressure=self.ctx_pressure,
                event_guard=event_guard,
            ):
                try:
                    self.proc.terminate()
                except Exception:
                    pass
        returncode, result_text = self._finish_run(
            event_guard=event_guard,
            event_violation=event_violation,
            result_text=result_text,
            error_texts=[],
            stderr_chunks=stderr_chunks,
            stderr_thread=stderr_thread,
            watchdog=watchdog,
        )
        return ClaudeRunResult(
            text=result_text,
            session_id=self.session_id,
            returncode=returncode,
        )

    def _capture_reasoning(self, event: dict[str, Any]) -> None:
        """Append one assistant message's TEXT to the in-memory ring buffer.

        Only `assistant` stream events carry the agent's reasoning; their
        ``message.content`` is a list of blocks, of which the ``text`` blocks are
        the reasoning. We join those, ignore tool_use / non-text blocks, and keep
        only the last ``_recent_reasoning_cap`` (default 3) non-empty texts. Pure
        in-memory — never written to disk. Best-effort: callers wrap in try/except.
        """
        if self._recent_reasoning_cap <= 0:
            return
        if not isinstance(event, dict) or event.get("type") != "assistant":
            return
        message = event.get("message")
        if not isinstance(message, dict):
            return
        content = message.get("content")
        if not isinstance(content, list):
            return
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                txt = block.get("text")
                if isinstance(txt, str) and txt.strip():
                    parts.append(txt.strip())
        text = "\n".join(parts).strip()
        if not text:
            return
        self._recent_reasoning.append(text)
        if len(self._recent_reasoning) > self._recent_reasoning_cap:
            del self._recent_reasoning[:-self._recent_reasoning_cap]

class CodexAgentSession(_ProviderAgentSessionBase):
    """One non-interactive OpenAI Codex CLI process for a proof node.

    Codex receives the same private stdio MCP server as Claude Code. Its JSONL
    events are normalized into the small Claude-style stream shape consumed by
    the existing tree liveness and information-source auditors.
    """

    provider_name = "codex"

    def _command(
        self,
        mcp_launch_spec: ProofMcpLaunchSpec | None,
        *,
        launch_id: str = "",
        resume_session_id: str = "",
    ) -> list[str]:
        # When the optional filesystem confinement layer is active, Codex's
        # own sandbox would be a redundant nested bwrap and cannot start on
        # Linux. ``danger-full-access`` therefore means full access only inside
        # that already-confined namespace. Platform-neutral eval runs and plain
        # /prove runs retain Codex's read-only sandbox; eval tool access is
        # independently restricted to the manager-owned MCP contract.
        sandbox_mode = (
            "danger-full-access"
            if self.eval_confinement is not None
            else "read-only"
        )
        if resume_session_id:
            command = [
                CODEX_BIN,
                "exec",
                "resume",
                "--skip-git-repo-check",
                "--json",
                "--model",
                self.model,
                "--ignore-user-config",
                "--strict-config",
                "-c",
                f"sandbox_mode={json.dumps(sandbox_mode)}",
            ]
        else:
            command = [
                CODEX_BIN,
                "exec",
                "-",
                "--skip-git-repo-check",
                "--json",
                "--model",
                self.model,
                "--sandbox",
                sandbox_mode,
                "--ignore-user-config",
                "--strict-config",
            ]
        command.extend([
            "-c",
            f"approval_policy={json.dumps('never')}",
            "-c",
            f"model_reasoning_effort={json.dumps(self.effort)}",
            "-c",
            f"web_search={json.dumps('disabled')}",
        ])
        capabilities = getattr(self, "codex_capabilities", None)
        if capabilities is None:
            capabilities = discover_codex_capabilities(CODEX_BIN)
            self.codex_capabilities = capabilities
        if not isinstance(capabilities, CodexCapabilities):
            raise TypeError("Codex session capabilities have invalid type")
        capabilities.require_managed_proof_node()
        if mcp_launch_spec is not None:
            capability_path = (
                mcp_launch_spec.private_dir / "codex_capabilities.json"
            )
            capability_path.parent.mkdir(parents=True, exist_ok=True)
            capability_path.write_text(
                json.dumps(capabilities.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        command.extend(codex_feature_disable_args(capabilities))
        if mcp_launch_spec is not None:
            for override in render_codex_mcp_overrides(
                mcp_launch_spec,
                launch_id=launch_id,
            ):
                command.extend(["-c", override])
        if resume_session_id:
            command.extend([resume_session_id, "-"])
        return command

    def run(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        mcp_launch_spec: ProofMcpLaunchSpec | None = None,
    ) -> AgentRunResult:
        launch_id = self._mint_launch(mcp_launch_spec)
        env = self._launch_env()
        resume_session_id = self.session_id
        self.last_turn_had_tool_call = False
        if not resume_session_id:
            # A fresh thread is a fresh generation. A RESUMED turn must keep
            # the detector's hot-turn streak and the reasoning ring buffer —
            # run() fires once per Codex turn, so resetting here made the
            # 2-consecutive-hot-turns debounce unreachable (watermark could
            # never trip on the Codex backend).
            self.ctx_pressure = False
            self._recent_reasoning = []
            self._ctx_detector.reset()

        full_prompt = (
            f"{system_prompt.strip()}\n\n{prompt}"
            if system_prompt.strip()
            else prompt
        )
        command = self._command(
            mcp_launch_spec,
            launch_id=launch_id,
            resume_session_id=resume_session_id,
        )
        self._spawn(command, env=env, pipe_stdin=True)
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.write(full_prompt)
                self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

        watchdog = self._start_readiness_watchdog(launch_id, mcp_launch_spec)
        stderr_thread, stderr_chunks = self._start_stderr_drain()

        result_text = ""
        error_texts: list[str] = []
        event_violation = ""
        normalizer = (
            CodexEventNormalizer(
                invocation_id=launch_id,
                manifest=mcp_launch_spec.manifest,
            )
            if mcp_launch_spec is not None
            else None
        )
        event_guard = (
            AgentEventLifecycleGuard(
                invocation_id=launch_id,
                provider="codex",
                # Same eval/run split as the Claude session: strict tool
                # whitelist in eval mode, provider-tool tolerance on
                # a plain /prove run (Codex CLI flags disable its own tools,
                # so provider tools should not appear here anyway).
                capability_policy=(
                    AgentCapabilityPolicy.proof_eval(mcp_launch_spec.manifest)
                    if self.eval_mode
                    else AgentCapabilityPolicy(allow_all_known_tools=True)
                ),
                requirements=LifecycleRequirements(require_turn_started=True),
            )
            if mcp_launch_spec is not None
            else None
        )
        emitted_tool_starts: set[str] = set()
        codex_event_log = (
            mcp_launch_spec.private_dir / "codex_events.jsonl"
            if mcp_launch_spec is not None
            else None
        )
        codex_event_stream = None
        if codex_event_log is not None:
            try:
                # Truncate only on this session object's very first launch; a
                # thread resume AND a fresh-context respawn must both append
                # (a "w" on respawn used to erase every prior generation's
                # events from the audit log).
                codex_event_stream = codex_event_log.open(
                    "a" if (resume_session_id or self._event_log_started) else "w",
                    encoding="utf-8",
                )
                self._event_log_started = True
            except OSError:
                codex_event_stream = None
        assert self.proc.stdout is not None
        try:
            for raw in self.proc.stdout:
                line = raw.rstrip("\n")
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    event_violation = "invalid Codex JSON event"
                    if event_guard is not None:
                        event_guard.record_violation(event_violation)
                    if self.proc.poll() is None:
                        self.proc.terminate()
                    break
                if not isinstance(event, dict):
                    event_violation = "Codex JSON event is not an object"
                    if event_guard is not None:
                        event_guard.record_violation(event_violation)
                    if self.proc.poll() is None:
                        self.proc.terminate()
                    break
                if codex_event_stream is not None:
                    retained_event = dict(event)
                    retained_event["_shannon_invocation_id"] = launch_id
                    codex_event_stream.write(
                        json.dumps(retained_event, ensure_ascii=False) + "\n"
                    )
                    codex_event_stream.flush()
                normalized_events = ()
                if normalizer is not None and event_guard is not None:
                    normalized = normalizer.normalize(event)
                    if normalized.violations:
                        event_violation = normalized.violations[0]
                        event_guard.record_violation(event_violation)
                    else:
                        normalized_events = normalized.events
                        for canonical in normalized_events:
                            decision = event_guard.observe(canonical)
                            if not decision.allowed:
                                event_violation = decision.reason
                                break
                    if event_violation:
                        error_texts.append(event_violation)
                        self.emit({
                            "type": "system",
                            "session_id": self.session_id,
                            "agent_backend": "codex",
                            "codex_event_type": "agent_event_policy.violation",
                            "message": event_violation,
                            "launch_id": launch_id,
                        })
                        if self.proc.poll() is None:
                            self.proc.terminate()
                        break
                event_type = str(event.get("type") or "")
                if event_type == "thread.started":
                    self.session_id = str(event.get("thread_id") or "")
                    self._notify_session_id(self.session_id)
                    self.emit({
                        "type": "system",
                        "subtype": "init",
                        "session_id": self.session_id,
                        "agent_backend": "codex",
                    })
                    continue

                item = event.get("item")
                if isinstance(item, dict):
                    item_id = str(item.get("id") or "")
                    item_type = str(item.get("type") or "")
                    canonical_tool_events = [
                        record
                        for record in normalized_events
                        if record.kind in {
                            AgentEventKind.TOOL_STARTED,
                            AgentEventKind.TOOL_COMPLETED,
                        }
                    ]
                    if canonical_tool_events:
                        canonical_tool = canonical_tool_events[0]
                        if canonical_tool.capability == "host_metadata":
                            if canonical_tool.kind is AgentEventKind.TOOL_COMPLETED:
                                self.emit({
                                    "type": "system",
                                    "session_id": self.session_id,
                                    "agent_backend": "codex",
                                    "codex_event_type": (
                                        "agent_event_policy.host_metadata_empty"
                                    ),
                                    "tool": str(
                                        item.get("tool") or item.get("name") or ""
                                    ),
                                })
                            continue
                        if item_type == "mcp_tool_call":
                            self.last_turn_had_tool_call = True
                        if (
                            canonical_tool.kind is AgentEventKind.TOOL_STARTED
                            and item_id
                            and item_id not in emitted_tool_starts
                        ):
                            emitted_tool_starts.add(item_id)
                            if item_type == "command_execution":
                                tool_name = "Bash"
                                tool_input: dict[str, Any] = {
                                    "command": str(item.get("command") or "")
                                }
                            elif item_type == "mcp_tool_call":
                                server = str(
                                    item.get("server")
                                    or mcp_launch_spec.manifest.identity.server
                                )
                                tool = str(item.get("tool") or item.get("name") or "tool")
                                tool_name = f"mcp__{server}__{tool}"
                                raw_args = item.get("arguments") or item.get("input") or {}
                                tool_input = raw_args if isinstance(raw_args, dict) else {
                                    "arguments": raw_args
                                }
                            else:
                                tool_name = f"Codex::{item_type}"
                                tool_input = {
                                    "status": str(item.get("status") or ""),
                                    "evidence": codex_event_text(item)[:1200],
                                }
                            self.emit({
                                "type": "assistant",
                                "session_id": self.session_id,
                                "agent_backend": "codex",
                                "message": {"content": [{
                                    "type": "tool_use",
                                    "id": item_id,
                                    "name": tool_name,
                                    "input": tool_input,
                                }]},
                            })
                        if (
                            canonical_tool.kind is AgentEventKind.TOOL_COMPLETED
                            and item_id
                        ):
                            self.emit({
                                "type": "user",
                                "session_id": self.session_id,
                                "agent_backend": "codex",
                                "message": {"content": [{
                                    "type": "tool_result",
                                    "tool_use_id": item_id,
                                    "content": codex_event_text(item),
                                }]},
                            })
                        continue

                    text_value = codex_event_text(item)
                    if item_type == "error" and text_value:
                        error_texts.append(text_value)
                        self.emit({
                            "type": "system",
                            "session_id": self.session_id,
                            "agent_backend": "codex",
                            "codex_event_type": "item.error",
                            "message": text_value,
                        })
                        continue
                    if item_type == "agent_message" and event_type == "item.completed":
                        result_text = text_value or result_text
                        if text_value:
                            self.emit({
                                "type": "assistant",
                                "session_id": self.session_id,
                                "agent_backend": "codex",
                                "message": {"content": [{
                                    "type": "text", "text": text_value
                                }]},
                            })
                        continue
                    if item_type == "reasoning" and text_value:
                        self._recent_reasoning.append(text_value)
                        if len(self._recent_reasoning) > self._recent_reasoning_cap:
                            del self._recent_reasoning[:-self._recent_reasoning_cap]
                        continue

                if event_type in {"turn.completed", "turn.failed", "error"}:
                    event_message = codex_event_text(event)
                    if event_type in {"turn.failed", "error"} and event_message:
                        error_texts.append(event_message)
                    # Only request-local context telemetry can trip pressure.
                    # The current exec terminal-usage adapter abstains: its
                    # aggregate spend cannot measure live context size.
                    if event_type == "turn.completed" and (
                        self._ctx_detector.observe_tokens(
                            context_tokens_from_codex_event(event)
                        )
                    ):
                        self.ctx_pressure = True
                        self.emit({
                            "type": "system",
                            "ctx_watermark_tripped": True,
                            "ctx_tokens": self._ctx_detector.last_ctx_tokens,
                            "hot_turns": self._ctx_detector.hot_turns,
                            "watermark_tokens": self._ctx_detector.tokens,
                            "session_tag": self.session_tag,
                            "agent_backend": "codex",
                        })
                    self.emit({
                        "type": "system",
                        "session_id": self.session_id,
                        "agent_backend": "codex",
                        "codex_event_type": event_type,
                        "usage": event.get("usage") or {},
                        "message": event_message,
                    })
        finally:
            if codex_event_stream is not None:
                codex_event_stream.close()

        returncode, result_text = self._finish_run(
            event_guard=event_guard,
            event_violation=event_violation,
            result_text=result_text,
            error_texts=error_texts,
            stderr_chunks=stderr_chunks,
            stderr_thread=stderr_thread,
            watchdog=watchdog,
        )
        return AgentRunResult(
            text=result_text,
            session_id=self.session_id,
            returncode=returncode,
        )


def agent_session_class(agent_backend: str) -> type[_ProviderAgentSessionBase]:
    backend = normalize_agent_backend(agent_backend)
    return CodexAgentSession if backend == "codex" else ClaudeAgentSession
