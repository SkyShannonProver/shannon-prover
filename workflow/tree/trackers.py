"""Per-node stream trackers for tree-mode prover runs.

Extracted verbatim from workflow/progress.py (backlog #18): _ProverTracker
(single-run stream parsing + hygiene watchdog) and _TreeProverTracker
(per-node variant), with their stream/tool-audit helpers.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional
from core.easycrypt.proof_lifecycle import is_session_completion_candidate
from core.easycrypt.committed_history import read_committed_tactics
from core.easycrypt.value_shapes import drop_empty as _shallow_drop_empty
from workflow.session_observer import WorkflowSessionSnapshot, observe_session
from workflow.prover_io_policy import (
    InformationSourceDecision,
    classify_bash_command,
    classify_read_path,
    detect_target_proof_output_exposure,
)
from workflow.payload_audit import (
    PayloadAuditRecorder,
    coerce_tool_result_text,
)
from workflow.run_ui import (
    _BOLD,
    _CYAN,
    _DIM,
    _GREEN,
    _RED,
    _RESET,
    _YELLOW,
    _clear_status_bar,
    _draw_status_bar,
    _set_status_bar_active,
    _status_bar_active,
    _status_bar_text,
    _timestamp,
    _update_status_bar,
    status,
)


def _handle_stream_event(
    event: dict,
    agent_name: str,
    on_tool_call: Optional[callable],
) -> None:
    """Parse one stream-json event and print progress."""
    event_type = event.get("type", "")

    if event_type == "assistant":
        # Assistant message with tool use
        message = event.get("message", {})
        content = message.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "thinking":
                        # Show that thinking is happening, with a brief preview
                        thinking = block.get("thinking", "")
                        if thinking:
                            # Extract first meaningful line as preview
                            preview = ""
                            for line in thinking.strip().splitlines():
                                line = line.strip()
                                if len(line) > 20:
                                    preview = line[:120] + ("..." if len(line) > 120 else "")
                                    break
                            if preview:
                                status(agent_name, f"🧠 {preview}", _DIM)
                    elif block.get("type") == "tool_use":
                        tool_name = block.get("name", "?")
                        tool_input = block.get("input", {})
                        _report_tool_call(agent_name, tool_name, tool_input, on_tool_call)
                    elif block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            preview = text[:150] + ("..." if len(text) > 150 else "")
                            status(agent_name, f"💬 {preview}", _DIM)

    elif event_type == "tool_use":
        tool_name = event.get("name", "?")
        tool_input = event.get("input", {})
        _report_tool_call(agent_name, tool_name, tool_input, on_tool_call)

    elif event_type == "result":
        cost_usd = event.get("cost_usd", 0)
        duration = event.get("duration_ms", 0)
        if duration:
            status(agent_name, f"Done ({duration/1000:.0f}s)", _GREEN)


def _report_tool_call(
    agent_name: str,
    tool_name: str,
    tool_input: dict,
    on_tool_call: Optional[callable],
) -> None:
    """Print a human-readable summary of a tool call."""
    summary = _summarize_tool(tool_name, tool_input)
    status(agent_name, f"🔧 {summary}", _CYAN)

    if on_tool_call:
        on_tool_call(tool_name, tool_input)


def _summarize_tool(name: str, inp: dict) -> str:
    """One-line summary of a tool call."""
    if name == "Bash":
        cmd = inp.get("command", "")
        if "session_cli" in cmd:
            return "Low-level EC session CLI call (debug signal)"
        if _bash_invokes_easycrypt(cmd):
            return "Verify .ec file"
        return f"bash: {cmd[:100]}"
    if name == "Read":
        fp = inp.get("file_path", "")
        return f"Read {fp.split('/')[-1]}"
    if name == "Edit":
        fp = inp.get("file_path", "")
        return f"Edit {fp.split('/')[-1]}"
    if name == "Write":
        fp = inp.get("file_path", "")
        return f"Write {fp.split('/')[-1]}"
    if name == "Grep":
        return f"Search: {inp.get('pattern', '')[:60]}"
    if name == "Glob":
        return f"Glob: {inp.get('pattern', '')}"
    if name.endswith("submit_proof_intent"):
        return _proof_intent_tool_description(inp)
    return f"{name}({json.dumps(inp, default=str)[:80]})"


def _bash_invokes_easycrypt(cmd: str) -> bool:
    """Return true for actual EasyCrypt verifier invocations.

    Paths such as ``easycrypt-src/theories`` appear in harmless shell commands
    like ``find``; those should not be displayed as file verification.
    """
    try:
        parts = shlex.split(str(cmd or ""))
    except ValueError:
        return False
    for part in parts:
        exe = Path(part).name
        if exe in {"easycrypt", "runeasycrypt"}:
            return True
    return False


def _proof_intent_tool_description(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return "submit_proof_intent malformed: arguments are not an object"
    raw_intent = tool_input.get("intent")
    intent = str(raw_intent or "").strip()
    if not intent:
        return "submit_proof_intent malformed: missing intent"
    payload = tool_input.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    if intent == "commit_tactic":
        tactic = str(payload.get("tactic") or "").strip()
        if len(tactic) > 220:
            tactic = tactic[:217].rstrip() + "..."
        return f"submit_proof_intent {intent}: {tactic}"
    return f"submit_proof_intent {intent}"


def _assistant_context_before_tool(
    content: list,
    tool_block_index: int,
) -> dict:
    """Summarize visible text and opaque thinking immediately before a tool.

    We keep raw assistant text previews because those are user-visible. For
    extended thinking, store only size/hash/keyword markers; the audit should
    tell us why a file tool looked likely without turning private reasoning
    text into durable run artifacts.
    """
    preceding = [
        block for block in content[:tool_block_index]
        if isinstance(block, dict)
    ]
    text_blocks = [
        str(block.get("text") or "").strip()
        for block in preceding
        if block.get("type") == "text" and str(block.get("text") or "").strip()
    ]
    thinking_blocks = [
        str(block.get("thinking") or "")
        for block in preceding
        if block.get("type") == "thinking" and str(block.get("thinking") or "")
    ]
    thinking_text = "\n".join(thinking_blocks)
    markers = _thinking_markers(thinking_text)
    return _audit_drop_empty({
        "preceding_text_preview": _truncate_audit_text(
            "\n".join(text_blocks[-2:]),
            600,
        ),
        "preceding_text_blocks": len(text_blocks),
        "preceding_thinking_blocks": len(thinking_blocks),
        "preceding_thinking_chars": len(thinking_text),
        "preceding_thinking_sha1": (
            hashlib.sha1(thinking_text.encode("utf-8")).hexdigest()
            if thinking_text else ""
        ),
        "preceding_thinking_markers": markers,
    })


def _thinking_markers(text: str) -> list[str]:
    lowered = text.lower()
    markers: list[str] = []
    checks = (
        ("mentions_node_memory", "node_memory"),
        ("mentions_latest_workspace_view", "latest_workspace_view"),
        ("mentions_latest_followup", "latest_followup"),
        ("mentions_history", "history"),
        ("mentions_search", "search"),
        ("mentions_rg", "rg "),
        ("mentions_forbidden_session", ".ec_session_"),
        ("mentions_worktrees", "worktrees"),
        ("mentions_tmp_artifact", "/tmp"),
        ("mentions_claude_internal", ".claude"),
    )
    for marker, needle in checks:
        if needle in lowered:
            markers.append(marker)
    return markers


def _truncate_audit_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 18)].rstrip() + "...[truncated]"


def _audit_drop_empty(value: dict) -> dict:
    return _shallow_drop_empty(value)


def _session_dir_path(cwd: str, session_dir: str | None) -> Path | None:
    if not session_dir:
        return None
    p = Path(session_dir)
    if not p.is_absolute():
        p = Path(cwd) / p
    return p


def _session_snapshot(
    cwd: str,
    session_dir: str | None,
) -> WorkflowSessionSnapshot | None:
    if not session_dir:
        return None
    try:
        return observe_session(session_dir, cwd=cwd)
    except Exception:
        return None


def _snapshot_has_completion_candidate(
    snapshot: WorkflowSessionSnapshot | None,
) -> bool:
    return bool(
        snapshot
        and snapshot.ok
        and (
            snapshot.qed_committed
            and is_session_completion_candidate(snapshot.status)
        )
    )


class _ProverTracker:
    """Track one prover from session snapshots plus stream-json fallback."""

    def __init__(
        self, proc: subprocess.Popen, name: str, cwd: str,
        session_dir: str | None = None,
    ):
        self.proc = proc
        self.name = name
        self.accepted_tactics = 0
        self.errors = 0
        self.last_progress_time = time.time()
        # Any agent/manager activity, including read-only MCP turns and legal
        # node-memory reads.  This is user-facing liveness; proof-search kill
        # checks keep using progress/accept timestamps.
        self.last_activity_time = self.last_progress_time
        self.result_text = ""
        self.manager_turns = 0
        self.session_id = ""
        self.agent_backend = "codex"
        # All provider session/thread ids seen on this worker's stream, in
        # first-seen order and deduped. A context respawn starts a new provider
        # session, so a node can legitimately own several; `session_id` is the
        # initial link and `session_ids` is the complete chain.
        self.session_ids: list[str] = []
        # Search-local fact only.  The run-level prover coordinator is the sole
        # owner of final verification and never consumes this as a proof verdict.
        self.completion_candidate_ready = False
        self.finished = False
        # True iff the worker emitted a clean final `result` event before exiting
        # (the managed worker's `_emit_final` always prints one on EVERY graceful
        # exit path — clean finish, give-up, or even a caught runtime exception).
        # A hard process crash (SIGKILL / OOM / segfault, e.g. exit 137/143) dies
        # WITHOUT reaching `_emit_final`, so no `result` event is seen and this
        # stays False. Layer-3 crash-respawn uses this to tell a real crash (the
        # agent made no decision — replay to recover) from a clean give-up (the
        # agent decided to stop — a measurable outcome we must NOT respawn).
        self.final_result_emitted = False
        # True iff the supervisor deliberately killed this worker via
        # `_kill_node` (drift / hygiene / destructive / capacity / progress-gap /
        # grace / winner). A worker SELF-exit (hard crash drained in `poll_lines`,
        # or a clean degraded give-up via the `result` event) leaves this False.
        # Layer-3 crash-respawn must fire ONLY on a self-exit, so it gates on
        # `not supervisor_killed` — a supervisor kill already made a decision and
        # must not be silently resurrected.
        self.supervisor_killed = False
        self._lines: list[str] = []
        self._cwd = cwd
        self._session_dir = session_dir
        self.session_snapshot: WorkflowSessionSnapshot | None = None
        self._seen_commit_artifacts: set[str] = set()
        self._last_transition_key = ""

    def _min_tactic_credit(self) -> int:
        return 0

    def _apply_session_snapshot(self, snapshot: WorkflowSessionSnapshot) -> None:
        target_count = max(snapshot.tactic_count, self._min_tactic_credit())
        if snapshot.history_exists or snapshot.tactic_count:
            if target_count > self.accepted_tactics:
                self.last_progress_time = time.time()
                self.last_activity_time = self.last_progress_time
            self.accepted_tactics = target_count
        if snapshot.errors_since_progress > 0:
            self.errors = max(self.errors, snapshot.errors_since_progress)
        if snapshot.last_progress_at > 0:
            self.last_progress_time = max(self.last_progress_time, snapshot.last_progress_at)
            self.last_activity_time = max(
                self.last_activity_time,
                self.last_progress_time,
            )
        if snapshot.last_readonly_tool_at > 0:
            self.last_activity_time = max(
                self.last_activity_time,
                snapshot.last_readonly_tool_at,
            )
        self._on_commit_response(snapshot)

    def _on_commit_response(self, snapshot: WorkflowSessionSnapshot) -> None:
        return None

    def _refresh_completion_candidate(self) -> None:
        if self.completion_candidate_ready:
            return
        snapshot = _session_snapshot(self._cwd, self._session_dir)
        if snapshot is not None:
            self.session_snapshot = snapshot
            self._apply_session_snapshot(snapshot)
            if _snapshot_has_completion_candidate(snapshot):
                self.completion_candidate_ready = True

    _STDERR_TAIL_MAX = 128 * 1024  # keep the last 128KB — a crash traceback's tail

    def _drain_stderr(self):
        """Non-blocking pull of any available worker stderr into a bounded tail.

        The worker is spawned with stderr=PIPE but the supervisor otherwise reads
        only stdout, so without this the pipe is never drained: a hard-death
        traceback (OOM / SIGKILL / uncaught exception) is lost when the proc is
        reaped, AND a worker that writes >~64KB to stderr would block forever on a
        full pipe. We read raw via os.read on the fd (the TextIOWrapper buffer is
        left untouched since stderr is never read through it) and keep only the
        last _STDERR_TAIL_MAX bytes, which is what a post-mortem needs.
        """
        import select
        se = getattr(self.proc, "stderr", None)
        if se is None:
            return
        try:
            fd = se.fileno()
        except (ValueError, OSError):
            return
        while True:
            try:
                ready, _, _ = select.select([fd], [], [], 0)
            except (ValueError, OSError):
                return
            if not ready:
                return
            try:
                chunk = os.read(fd, 65536)
            except (BlockingIOError, OSError):
                return
            if not chunk:  # EOF — worker closed stderr
                return
            self._stderr_tail = (
                self._stderr_tail + chunk.decode("utf-8", "replace")
            )[-self._STDERR_TAIL_MAX:]

    def persist_stderr(self, *, reason: str = "", returncode=None):
        """Write the captured stderr tail to node_memory/<tree>/worker_stderr.log
        so a hard worker death (no `result` event) leaves a forensic trail. Writes
        once (idempotent); a no-op without a node-memory dir. Returns the path or
        None."""
        if self._stderr_persisted:
            return None
        # Resolve the exit code if the caller didn't have it yet: stdout EOF can
        # precede the proc being reaped by microseconds, so returncode is still
        # None at that instant. The worker has closed its pipe, so wait() returns
        # promptly. The exit code is the single most useful death signal
        # (137=SIGKILL/OOM, 143=SIGTERM, 139=SIGSEGV).
        if returncode is None:
            try:
                returncode = self.proc.poll()
                if returncode is None:
                    returncode = self.proc.wait(timeout=2.0)
            except Exception:
                returncode = getattr(self.proc, "returncode", None)
        self._stderr_persisted = True
        dirs = self.allowed_node_memory_dirs or []
        if not dirs:
            return None
        try:
            d = Path(dirs[0])
            d.mkdir(parents=True, exist_ok=True)
            path = d / "worker_stderr.log"
            header = (
                f"# worker stderr — node {self.name}\n"
                f"# returncode={returncode} reason={reason} "
                f"time={time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
                "# (empty below = the worker wrote nothing to stderr before exit)\n\n"
            )
            path.write_text(header + self._stderr_tail.strip() + "\n",
                            encoding="utf-8")
            return str(path)
        except OSError:
            return None

    def poll_lines(self):
        """Non-blocking read of available stdout lines."""
        import select
        self._drain_stderr()  # keep stderr drained every poll (deadlock-safe + captured)
        while True:
            # Check if data available (non-blocking)
            if self.proc.stdout is None or self.proc.poll() is not None:
                # Process finished — drain remaining stdout + stderr, then persist.
                if self.proc.stdout:
                    for line in self.proc.stdout:
                        self._process_line(line.strip())
                self._drain_stderr()
                self.persist_stderr(reason="worker_exit",
                                    returncode=getattr(self.proc, "returncode", None))
                self.finished = True
                return
            try:
                ready, _, _ = select.select([self.proc.stdout], [], [], 0.1)
                if ready:
                    line = self.proc.stdout.readline()
                    if not line:
                        self._drain_stderr()
                        self.persist_stderr(reason="worker_eof",
                                            returncode=getattr(self.proc, "returncode", None))
                        self.finished = True
                        return
                    self._process_line(line.strip())
                else:
                    self._refresh_completion_candidate()
                    return  # no data available right now
            except (ValueError, OSError):
                self._drain_stderr()
                self.persist_stderr(reason="worker_io_error",
                                    returncode=getattr(self.proc, "returncode", None))
                self.finished = True
                return

    def _capture_session_id(self, raw: object) -> None:
        """Record one observed Claude session id (first-seen order, deduped)."""
        sid = str(raw or "").strip()
        if not sid:
            return
        if not self.session_id:
            self.session_id = sid
        if sid not in self.session_ids:
            self.session_ids.append(sid)

    def _project_manager_turn_event(self, event: dict[str, object]) -> None:
        """Project the bridge-owned turn index; never infer turns from text."""

        if event.get("kind") != "manager_turn.completed":
            return
        turn_index = event.get("turn_index")
        if isinstance(turn_index, int) and not isinstance(turn_index, bool):
            self.manager_turns = max(self.manager_turns, max(0, turn_index))

    def _process_line(self, line: str):
        if not line:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return

        event_type = event.get("type", "")
        if event.get("agent_backend"):
            self.agent_backend = str(event["agent_backend"])

        # Capture session ids from init or any event. Keep every distinct id —
        # a ctx-respawn continuation streams a NEW session id mid-run, and the
        # run manifest must list the full chain, not just the first link.
        self._capture_session_id(event.get("session_id"))
        self._project_manager_turn_event(event)

        if event_type == "result":
            self.result_text = event.get("result", "")
            turns = event.get("turns")
            if isinstance(turns, int) and not isinstance(turns, bool):
                self.manager_turns = max(self.manager_turns, max(0, turns))
            self.finished = True
            # Clean final-result signal (only `_emit_final` prints this).
            self.final_result_emitted = True

        if event_type == "user":
            self.last_activity_time = time.time()
        if event_type == "assistant":
            self.last_activity_time = time.time()

        # Display events using existing handler
        _handle_stream_event(event, self.name, None)
        self._refresh_completion_candidate()


STRUCTURAL_COMMIT_OPENERS = frozenset({
    "byequiv", "byphoare", "bypr", "proc", "inline", "call",
    "transitivity", "seq", "while", "eager", "case", "sim",
    "rewrite", "have", "conseq",
})


def _is_background_tool_result(text: str) -> bool:
    return (
        "Command running in background" in text
        or "Output is being written to:" in text
    )


def _is_permission_denied_tool_result(text: str) -> bool:
    # Claude Code emits two distinct denial shapes when a tool call is blocked by
    # ``--disallowedTools``; either means the action was REFUSED (no mutation, no
    # leak), so the watchdog must NOT node-kill for it — the agent already got a
    # refusal it can act on. The node-kill is reserved for a denial that did NOT
    # fire, i.e. a genuinely-executed leak/escape (content actually returned).
    #   (1) tool-level deny: "Permission to use <Tool> ... has been denied"
    #   (2) path-based Read/Edit deny (e.g. Read(//~/.claude/**)):
    #       "<tool_use_error>File is in a directory that is denied by your
    #        permission settings.</tool_use_error>"
    if "Permission to use" in text and "has been denied" in text:
        return True
    if "denied by your permission settings" in text:
        return True
    return False


def _session_dir(cwd: str, session_tag: str) -> Path:
    return Path(cwd) / f".ec_session_{session_tag}"


def _first_word(tactic: str) -> str:
    """Strip leading `;` / whitespace and take the first alphabetic token."""
    s = tactic.lstrip(" ;\t")
    m = re.match(r"[a-zA-Z]+", s)
    return m.group(0) if m else ""


class _TreeProverTracker(_ProverTracker):
    """Extended tracker that records tactic texts and error runs."""

    def __init__(self, proc: subprocess.Popen, name: str, cwd: str,
                 session_tag: str = "",
                 payload_audit: PayloadAuditRecorder | None = None,
                 allowed_source_files: list[str | Path] | None = None,
                 allowed_node_memory_dirs: list[str | Path] | None = None,
                 target_lemma: str = ""):
        super().__init__(
            proc, name, cwd,
            session_dir=f".ec_session_{session_tag}" if session_tag else None,
        )
        self.accepted_tactic_texts: list[str] = []
        self.errors_since_last_accept: int = 0
        self.last_accept_time: float = time.time()
        self.stuck_handled: bool = False
        # Fresh-context continuation: how many times the worker has swapped in a
        # fresh Claude context for this node (from the `context_respawn` marker).
        self.context_respawn_count: int = 0
        # Structural undo: saved at undo time so branch point is available at check time
        self.structural_undo_branch: Optional[tuple[list[str], list[str]]] = None  # (prefix, failed)
        self.structural_undo_branch_time: float = 0.0
        self.last_undo_time: float = 0.0
        self.last_structural_undo_time: float = 0.0
        self.max_committed_count_seen: int = 0
        # Sticky: latched once the committed count drops below its high-water
        # mark, i.e. the agent rewound. A forward-only proof's history only
        # grows; ANY rewind — `undo_last_step` OR `undo_to_checkpoint`
        # (force-restart + shorter replay) — truncates history.ec, so the count
        # dips below the max ever seen. This is the resume-drift-gate's
        # authoritative "agent owns the prefix now" signal, because it is a
        # stable state both undo intents produce — unlike `last_undo_time`,
        # which is only set on a `tactic.undone` event that `undo_to_checkpoint`
        # never emits.
        self.history_ever_shrank: bool = False
        # Compose-first tracking
        self.chain_attempts: int = 0          # structured commit-chain results
        self.chain_tactic_estimate: int = 0   # attempted tactics in latest chain
        # Layer-1 deterministic progress metric: read from history.ec so we
        # know what EC actually accepted, not what the prover submitted.
        # Cached with a short TTL to avoid stat()-ing on every kill check.
        self._cwd = cwd
        self._session_tag = session_tag
        self._hist_cache_until: float = 0.0
        self._hist_lines_cache: list[str] = []
        self.prefix_credit: int = 0
        # Timestamp of the last event-bound read-only backend observation. 0.0
        # means never. The kill check grants a short grace period while a
        # compiler/native query is active even though no tactic was committed.
        self.last_readonly_backend_call_time: float = 0.0
        # Log throttle for read-only-work deferrals. Do not use this as a
        # handled flag: once the window expires, the branch should
        # still be eligible for a child.
        self.last_analysis_spawn_skip_log_time: float = 0.0
        # Most recent committed/chain tactic that failed after the current
        # accepted prefix.  Tree children should branch locally from the current
        # frontier and avoid this exact failed move, instead of replaying from
        # the first high-level strategy tactic.
        self.recent_failed_tactic: str = ""
        self.recent_failed_time: float = 0.0
        self.unsafe_session_shell_command: str = ""
        self.unsafe_session_shell_time: float = 0.0
        self.lossy_session_cli_command: str = ""
        self.lossy_session_cli_time: float = 0.0
        self.lossy_session_cli_count: int = 0
        self.background_session_cli_command: str = ""
        self.background_session_cli_time: float = 0.0
        self.background_session_cli_notice_time: float = 0.0
        self.background_session_cli_count: int = 0
        self.forbidden_information_source_count: int = 0
        self.forbidden_information_source_last: str = ""
        self.forbidden_information_source_reason: str = ""
        self.information_source_audit: list[dict[str, str]] = []
        self.unsafe_information_source_reason: str = ""
        self.payload_audit = payload_audit
        self.allowed_source_files = list(allowed_source_files or [])
        self.allowed_node_memory_dirs = list(allowed_node_memory_dirs or [])
        self.target_lemma = str(target_lemma or "")
        # Worker stderr capture: the worker is spawned with stderr=PIPE but the
        # supervisor only drains stdout, so a hard-death traceback was lost and a
        # >64KB stderr write could deadlock the worker. We keep a bounded tail and
        # persist it on exit (see _drain_stderr / persist_stderr).
        self._stderr_tail: str = ""
        self._stderr_persisted: bool = False
        self._payload_audit_seen_commit_artifacts: set[str] = set()
        self._payload_audit_seen_workspace_artifacts: set[str] = set()
        self._payload_audit_seen_tactic_execution_artifacts: set[str] = set()
        self.pending_unsafe_tool_uses: dict[str, str] = {}
        self.pending_unsafe_tool_use_reasons: dict[str, str] = {}
        self.pending_forbidden_tool_uses: dict[str, str] = {}
        self.pending_forbidden_tool_use_reasons: dict[str, str] = {}
        self.pending_non_forbidden_tool_uses: set[str] = set()
        self.pending_lossy_tool_uses: dict[str, str] = {}
        self.pending_lossy_tool_use_policies: dict[str, InformationSourceDecision] = {}
        self.pending_session_cli_background_tool_uses: dict[str, str] = {}

    @property
    def session_tag(self) -> str:
        return self._session_tag

    def _min_tactic_credit(self) -> int:
        return self.prefix_credit

    def _apply_session_snapshot(self, snapshot: WorkflowSessionSnapshot) -> None:
        super()._apply_session_snapshot(snapshot)
        self._record_payload_session_artifacts(snapshot)
        if snapshot.history_exists:
            self.accepted_tactic_texts = list(snapshot.history_tactics)
        observed_committed = max(
            len(snapshot.history_tactics or []),
            int(snapshot.tactic_count or 0),
        )
        # Latch a rewind: the committed count fell below its high-water mark.
        # Only trust a real on-disk read (history_exists) so a transient
        # missing/empty history.ec is not mistaken for a rewind. Safe direction:
        # a false latch only ever DISABLES the drift kill, never causes one.
        #
        # Sampling robustness (why this latch is not racy): a checkpoint rewind
        # runs `-start --force-restart`, which rmtree's the session dir (history
        # -> 0) and then replays the shorter prefix one canonical commit per
        # tactic (~0.6s each). So history.ec climbs 0 -> keep_count over tens of
        # seconds, sitting strictly below the high-water mark the whole time —
        # the ~1s monitor poll samples it dozens of times and latches on the
        # first. To MISS, the rmtree + full replay + a new (LLM-latency) commit
        # past the old max would all have to fit inside one poll interval, which
        # is not physically reachable.
        #
        # FALSE-POSITIVE surface (known, safe-direction): inferring a rewind from
        # an unsynchronized history.ec length sample can also latch WITHOUT a
        # real rewind — a read-only manager diagnostic that commits
        # `have ...; admit.` then undoes it can transiently inflate then lower
        # the count, so a later legit count below that transient peak
        # latches. This only ever DISABLES the drift kill (never causes one), and
        # a missed desync cannot yield an accepted wrong proof (a winner is
        # declared only on backend-confirmed closure) — worst case is a stale
        # branch wasting strategy budget, not a soundness bug.
        #
        # The principled fix for BOTH the residual sampling window and this
        # false-positive is an EXPLICIT rewind signal from the rewind code path
        # (or clearing the orchestrator's stale `node.replay_prefix` when the
        # manager reports `crosses_resume_floor`) rather than inferring it from
        # history length. Deferred: current heuristic is safe-direction and
        # efficiency-only. Revisit if drift early-kill savings matter or the
        # monitor cadence is raised toward the replay duration.
        if snapshot.history_exists and self.max_committed_count_seen > observed_committed:
            self.history_ever_shrank = True
        self.max_committed_count_seen = max(
            self.max_committed_count_seen,
            observed_committed,
        )
        if snapshot.event_log_exists or snapshot.commit_response_count:
            self.errors_since_last_accept = snapshot.errors_since_progress
        if snapshot.last_progress_at > 0:
            self.last_accept_time = max(self.last_accept_time, snapshot.last_progress_at)
        if snapshot.last_readonly_tool_at > 0:
            self.last_readonly_backend_call_time = max(
                self.last_readonly_backend_call_time,
                snapshot.last_readonly_tool_at,
            )
        self._refresh_background_session_cli(snapshot)

        transition = snapshot.latest_transition or {}
        transition_key = json.dumps(transition, sort_keys=True)
        if transition_key and transition_key != self._last_transition_key:
            self._last_transition_key = transition_key
            if transition.get("kind") == "undo":
                undone = str(transition.get("tactic") or "")
                first_word = undone.split()[0].rstrip(".;") if undone else ""
                self.last_undo_time = time.time()
                self.last_progress_time = self.last_undo_time
                undone_lines = len([ln for ln in undone.splitlines() if ln.strip()])
                self.max_committed_count_seen = max(
                    self.max_committed_count_seen,
                    len(snapshot.history_tactics or []) + max(1, undone_lines),
                )
                self.recent_failed_tactic = undone
                self.recent_failed_time = time.time()
                if first_word in STRUCTURAL_COMMIT_OPENERS:
                    self.last_structural_undo_time = self.last_undo_time
                    self.structural_undo_branch = (
                        list(snapshot.history_tactics),
                        [undone],
                    )
                    self.structural_undo_branch_time = self.last_undo_time

        payload = snapshot.latest_commit_payload or {}
        artifact = str(payload.get("artifact") or "")
        if not artifact or artifact in self._seen_commit_artifacts:
            return
        self._seen_commit_artifacts.add(artifact)
        response = snapshot.latest_commit_response or {}
        mutation = response.get("mutation") if isinstance(
            response.get("mutation"), dict,
        ) else {}
        attempted = mutation.get("attempted_tactics")
        attempted = attempted if isinstance(attempted, list) else []
        if response.get("command") == "commit_chain":
            self.chain_attempts += 1
            self.chain_tactic_estimate = int(mutation.get("attempted_count") or 0)
        accepted = mutation.get("accepted_count")
        accepted = accepted if isinstance(accepted, int) else 0
        status = str(response.get("status") or "")
        failed_tactic = str(mutation.get("failed_tactic") or "").strip()
        if failed_tactic:
            self.recent_failed_tactic = failed_tactic
            self.recent_failed_time = time.time()
        if accepted > 0 and status in {"ok", "partial_success"}:
            self.errors_since_last_accept = 0
            self.stuck_handled = False
            self.max_committed_count_seen = max(
                self.max_committed_count_seen,
                self.committed_count,
            )
            # If the same long-lived agent accepted a repair step after a
            # structural undo, let it continue instead of spawning a child from
            # the now-stale branch point.
            if self.last_structural_undo_time > 0:
                self.structural_undo_branch = None
                self.structural_undo_branch_time = 0.0
            if status == "ok" and not failed_tactic:
                self.recent_failed_tactic = ""
                self.recent_failed_time = 0.0
        elif status == "failed":
            self.errors += 1
            self.errors_since_last_accept = max(
                self.errors_since_last_accept,
                1,
            )

    def _record_payload_session_artifacts(
        self,
        snapshot: WorkflowSessionSnapshot,
    ) -> None:
        if self.payload_audit is None:
            return
        commit_payload = snapshot.latest_commit_payload or {}
        commit_artifact = str(commit_payload.get("artifact") or "")
        if (
            commit_artifact
            and commit_artifact not in self._payload_audit_seen_commit_artifacts
        ):
            self._payload_audit_seen_commit_artifacts.add(commit_artifact)
            self.payload_audit.record_session_artifact(
                tree=self.name,
                session_tag=self._session_tag,
                kind="commit_response",
                snapshot=snapshot,
            )
        workspace_payload = snapshot.latest_workspace_payload or {}
        workspace_artifact = str(workspace_payload.get("artifact") or "")
        if (
            workspace_artifact
            and workspace_artifact not in self._payload_audit_seen_workspace_artifacts
        ):
            self._payload_audit_seen_workspace_artifacts.add(workspace_artifact)
            self.payload_audit.record_session_artifact(
                tree=self.name,
                session_tag=self._session_tag,
                kind="prover_workspace_view",
                snapshot=snapshot,
            )
        execution_payload = snapshot.latest_tactic_execution_payload or {}
        execution_artifact = str(execution_payload.get("artifact") or "")
        if (
            execution_artifact
            and execution_artifact
            not in self._payload_audit_seen_tactic_execution_artifacts
        ):
            self._payload_audit_seen_tactic_execution_artifacts.add(
                execution_artifact,
            )
            self.payload_audit.record_session_artifact(
                tree=self.name,
                session_tag=self._session_tag,
                kind="tactic_execution_result",
                snapshot=snapshot,
            )

    def _refresh_background_session_cli(
        self,
        snapshot: WorkflowSessionSnapshot,
    ) -> None:
        if not self.background_session_cli_command:
            return
        now = time.time()
        if snapshot.active_tool_mutates:
            self.last_progress_time = now
            if now - self.background_session_cli_notice_time >= 30:
                status(
                    self.name,
                    "Mutating session_cli command is still running; "
                    "preserving this tree and waiting for structured state.",
                    _YELLOW,
                )
                self.background_session_cli_notice_time = now
            return
        if (
            snapshot.last_mutating_tool_at > 0
            and snapshot.last_mutating_tool_at >= self.background_session_cli_time - 5
        ):
            status(
                self.name,
                "Background mutating session_cli command settled; "
                "structured session state is available again.",
                _CYAN,
            )
            self.background_session_cli_command = ""
            self.background_session_cli_time = 0.0
            self.background_session_cli_notice_time = 0.0

    def _history_lines(self) -> list[str]:
        """Read history.ec with a 2-second cache.

        Returns the list of committed tactic lines (each line = one tactic
        as EC accepted it). Empty list if the file doesn't exist yet or
        the session_tag is unknown.
        """
        if self.session_snapshot and self.session_snapshot.history_exists:
            return list(self.session_snapshot.history_tactics)
        now = time.time()
        if now < self._hist_cache_until:
            return self._hist_lines_cache
        if not self._session_tag:
            self._hist_lines_cache = []
            self._hist_cache_until = now + 2.0
            return self._hist_lines_cache
        lines = read_committed_tactics(
            _session_dir(self._cwd, self._session_tag)
        )
        self._hist_lines_cache = lines
        self._hist_cache_until = now + 2.0
        return lines

    @property
    def committed_count(self) -> int:
        """True count of tactics EC accepted. Ground truth for kill checks.

        Falls back to ``self.accepted_tactics`` when history.ec is
        unreadable (e.g. session not yet started), so rank ordering still
        works during warmup.
        """
        lines = self._history_lines()
        if lines:
            self.max_committed_count_seen = max(
                self.max_committed_count_seen,
                len(lines),
            )
            return len(lines)
        if self.session_snapshot and self.session_snapshot.tactic_count:
            self.max_committed_count_seen = max(
                self.max_committed_count_seen,
                self.session_snapshot.tactic_count,
            )
            return self.session_snapshot.tactic_count
        self.max_committed_count_seen = max(
            self.max_committed_count_seen,
            self.accepted_tactics,
        )
        return self.accepted_tactics

    @property
    def has_structural_commit(self) -> bool:
        """Has this tree committed any structural opener?

        Reading history.ec means we credit only tactics EC actually
        accepted — a failed `byequiv` that got undone does NOT grant
        immunity. Used by the kill check as grace for trees that have
        earned structural positioning.
        """
        for line in self._history_lines():
            if _first_word(line) in STRUCTURAL_COMMIT_OPENERS:
                return True
        return False

    @property
    def waiting_on_background_mutation(self) -> bool:
        return bool(self.background_session_cli_command)

    def _process_line(self, line: str):
        """Parse stream-json, extract tactic text, track error runs."""
        if not line:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return

        event_type = event.get("type", "")
        if event.get("agent_backend"):
            self.agent_backend = str(event["agent_backend"])

        # Capture session ids (full chain — see _ProverTracker._capture_session_id)
        self._capture_session_id(event.get("session_id"))
        self._project_manager_turn_event(event)

        if event_type == "result":
            self.result_text = event.get("result", "")
            turns = event.get("turns")
            if isinstance(turns, int) and not isinstance(turns, bool):
                self.manager_turns = max(self.manager_turns, max(0, turns))
            self.finished = True
            # Clean final-result signal (only `_emit_final` prints this); used by
            # Layer-3 to distinguish a graceful give-up from a hard crash.
            self.final_result_emitted = True

        # Fresh-context continuation observability hygiene: when the worker swaps
        # in a fresh Claude context (Layer 1/2), it emits this `system` marker. The
        # idle / errors-since-accept timers are claude-PROCESS-scoped, so the brief
        # stream gap while the new child boots must NOT be read as a stall or
        # idle-give-up. Completion-candidate state and accepted tactics derive
        # from the surviving EC snapshot and are deliberately left untouched. See
        # docs/design/fresh_context_continuation.md.
        if event_type == "system" and event.get("context_respawn"):
            now = time.time()
            self.last_activity_time = now
            self.last_progress_time = now
            self.last_accept_time = now
            self.errors_since_last_accept = 0
            self.context_respawn_count = max(
                getattr(self, "context_respawn_count", 0),
                int(event.get("context_respawn") or 0),
            )

        if event_type == "assistant":
            self.last_activity_time = time.time()
            self._track_session_hygiene_tool_uses(event)

        if event_type == "user":
            self.last_activity_time = time.time()
            content = event.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        result_text = coerce_tool_result_text(
                            block.get("content", ""),
                        )
                        tool_use_id = str(block.get("tool_use_id") or "")
                        self._resolve_session_hygiene_tool_result(
                            tool_use_id,
                            result_text,
                        )

        # Display events using existing handler
        _handle_stream_event(event, self.name, None)
        self._refresh_completion_candidate()

    def _track_session_hygiene_tool_uses(self, event: dict) -> None:
        content = event.get("message", {}).get("content", [])
        if not isinstance(content, list):
            return
        eval_mode = bool(os.environ.get("EVAL_TARGET_LEMMA", "").strip())
        for block_index, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_use_id = str(block.get("id") or "")
            if not tool_use_id:
                continue
            name = str(block.get("name") or "")
            tool_input = block.get("input") or {}
            if name == "Read":
                file_path = str(tool_input.get("file_path") or "")
                policy = classify_read_path(
                    file_path,
                    cwd=self._cwd,
                    allowed_source_files=self.allowed_source_files,
                    allowed_node_memory_dirs=self.allowed_node_memory_dirs,
                    target_lemma=self.target_lemma,
                    eval_mode=eval_mode,
                )
                self._record_payload_tool_use(
                    tool_use_id,
                    name,
                    tool_input,
                    policy,
                    f"Read({file_path})",
                    assistant_context=_assistant_context_before_tool(
                        content,
                        block_index,
                    ),
                )
                self._track_information_source_policy(
                    tool_use_id,
                    f"Read({file_path})",
                    policy,
                )
                continue
            if name.endswith("submit_proof_intent"):
                self._record_payload_tool_use(
                    tool_use_id,
                    name,
                    tool_input,
                    None,
                    _proof_intent_tool_description(tool_input),
                    assistant_context=_assistant_context_before_tool(
                        content,
                        block_index,
                    ),
                )
                continue
            if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                # Classify WRITES by target path too. The memory/answer-leak guard
                # in classify_read_path is path-based, so it catches an Edit/Write
                # whose target is a ~/.claude memory note (a stuck prover tried to
                # record a blocker note there) -> node_fatal, discard the node.
                file_path = str(
                    tool_input.get("file_path")
                    or tool_input.get("notebook_path")
                    or ""
                )
                policy = classify_read_path(
                    file_path,
                    cwd=self._cwd,
                    allowed_source_files=self.allowed_source_files,
                    allowed_node_memory_dirs=self.allowed_node_memory_dirs,
                    target_lemma=self.target_lemma,
                    eval_mode=eval_mode,
                )
                self._record_payload_tool_use(
                    tool_use_id,
                    name,
                    tool_input,
                    policy,
                    f"{name}({file_path})",
                    assistant_context=_assistant_context_before_tool(
                        content,
                        block_index,
                    ),
                )
                self._track_information_source_policy(
                    tool_use_id,
                    f"{name}({file_path})",
                    policy,
                )
                continue
            if name != "Bash":
                self._record_payload_tool_use(
                    tool_use_id,
                    name,
                    tool_input,
                    None,
                    name,
                    assistant_context=_assistant_context_before_tool(
                        content,
                        block_index,
                    ),
                )
                continue
            cmd = str(tool_input.get("command") or "")
            policy = classify_bash_command(
                cmd,
                cwd=self._cwd,
                allowed_source_files=self.allowed_source_files,
                allowed_node_memory_dirs=self.allowed_node_memory_dirs,
                target_lemma=self.target_lemma,
                eval_mode=eval_mode,
            )
            self._record_payload_tool_use(
                tool_use_id,
                name,
                tool_input,
                policy,
                cmd,
                assistant_context=_assistant_context_before_tool(
                    content,
                    block_index,
                ),
            )
            self._track_information_source_policy(tool_use_id, cmd, policy)
            if policy.mutates_proof_state:
                self.pending_session_cli_background_tool_uses[tool_use_id] = cmd

    def _record_payload_tool_use(
        self,
        tool_use_id: str,
        name: str,
        tool_input: object,
        policy: InformationSourceDecision | None,
        description: str,
        assistant_context: dict | None = None,
    ) -> None:
        if self.payload_audit is None:
            return
        self.payload_audit.record_tool_use(
            tree=self.name,
            session_tag=self._session_tag,
            tool_use_id=tool_use_id,
            tool_name=name,
            tool_input=tool_input,
            policy=policy,
            description=description,
            assistant_context=assistant_context,
        )

    def _track_information_source_policy(
        self,
        tool_use_id: str,
        description: str,
        policy: InformationSourceDecision,
    ) -> None:
        if policy.audit_code:
            self.information_source_audit.append({
                "tool_use_id": tool_use_id,
                "decision": policy.decision,
                "source_type": policy.source_type,
                "authority": policy.authority,
                "audit_code": policy.audit_code,
                "description": description[:240],
            })
            if len(self.information_source_audit) > 200:
                self.information_source_audit = self.information_source_audit[-200:]
        if policy.decision == "node_fatal":
            self.pending_unsafe_tool_uses[tool_use_id] = description
            self.pending_unsafe_tool_use_reasons[tool_use_id] = policy.reason
        elif policy.decision == "deny":
            self.pending_forbidden_tool_uses[tool_use_id] = description
            self.pending_forbidden_tool_use_reasons[tool_use_id] = policy.reason
        elif policy.decision == "warn":
            self.pending_lossy_tool_uses[tool_use_id] = description
            self.pending_lossy_tool_use_policies[tool_use_id] = policy
        else:
            self.pending_non_forbidden_tool_uses.add(tool_use_id)

    def _resolve_session_hygiene_tool_result(
        self,
        tool_use_id: str,
        result_text: str,
    ) -> None:
        pending_unsafe = self.pending_unsafe_tool_uses.pop(tool_use_id, "")
        pending_forbidden = self.pending_forbidden_tool_uses.pop(tool_use_id, "")
        pending_background = self.pending_session_cli_background_tool_uses.pop(
            tool_use_id,
            "",
        )
        pending_lossy = self.pending_lossy_tool_uses.pop(tool_use_id, "")
        pending_unsafe_reason = self.pending_unsafe_tool_use_reasons.pop(
            tool_use_id,
            "",
        )
        pending_forbidden_reason = self.pending_forbidden_tool_use_reasons.pop(
            tool_use_id,
            "",
        )
        pending_non_forbidden = tool_use_id in self.pending_non_forbidden_tool_uses
        self.pending_non_forbidden_tool_uses.discard(tool_use_id)
        pending_lossy_policy = self.pending_lossy_tool_use_policies.pop(
            tool_use_id,
            None,
        )
        exposure = detect_target_proof_output_exposure(
            result_text,
            # A few unit tests construct a deliberately minimal tracker with
            # object.__new__.  Missing eval metadata means there is no target
            # proof to audit; it must not break the pre-existing hygiene path.
            target_lemma=getattr(self, "target_lemma", ""),
            cwd=getattr(self, "_cwd", None),
        )
        exposure_dict = exposure.to_dict() if exposure is not None else {}
        pending_kind = ""
        pending_description = ""
        pending_reason = ""
        if pending_unsafe:
            pending_kind = "unsafe"
            pending_description = pending_unsafe
            pending_reason = pending_unsafe_reason
        elif pending_forbidden:
            pending_kind = "forbidden"
            pending_description = pending_forbidden
            pending_reason = pending_forbidden_reason
        elif pending_lossy:
            pending_kind = "lossy"
            pending_description = pending_lossy
            pending_reason = (
                pending_lossy_policy.reason if pending_lossy_policy else ""
            )
        elif pending_background:
            pending_kind = "session_cli_mutation"
            pending_description = pending_background
        elif pending_non_forbidden:
            pending_kind = "allowed"
        if self.payload_audit is not None:
            self.payload_audit.record_tool_result(
                tree=self.name,
                session_tag=self._session_tag,
                tool_use_id=tool_use_id,
                result_text=result_text,
                pending_kind=pending_kind,
                pending_description=pending_description,
                pending_reason=pending_reason,
                target_proof_exposure=exposure_dict,
            )
        if exposure is not None:
            self.information_source_audit.append({
                "tool_use_id": tool_use_id,
                "decision": "invalidate_run",
                "source_type": "target_proof_output_exposure",
                "authority": "answer_leak_guard",
                "audit_code": exposure.audit_code,
                "description": f"{exposure.path}:{exposure.line}",
            })
            if len(self.information_source_audit) > 200:
                self.information_source_audit = self.information_source_audit[-200:]
        if _is_permission_denied_tool_result(result_text):
            return
        if pending_unsafe:
            self.unsafe_session_shell_command = pending_unsafe
            self.unsafe_session_shell_time = time.time()
            self.unsafe_information_source_reason = pending_unsafe_reason
            return
        if pending_forbidden:
            self.forbidden_information_source_count += 1
            self.forbidden_information_source_last = pending_forbidden
            self.forbidden_information_source_reason = pending_forbidden_reason
            # (B) A forbidden READ never hard-kills the tree. A read mutates
            # nothing — at worst it pollutes reasoning, which an escalating warn
            # corrects and the payload audit records for post-hoc validity checks.
            # The kill is reserved for genuinely DESTRUCTIVE / boundary-breaking
            # actions: a node_fatal bridge/session_cli escape (`pending_unsafe`
            # above), an `rm -rf` of the session dir, or an Edit/Write to the
            # source (both detected by the watchdog below). Killing a whole tree —
            # discarding all its committed proof work — over a read is the wrong
            # trade; warn + audit instead. (Often the read is the agent
            # compensating for a view gap, e.g. a called procedure's body the
            # structured view did not surface.)
            status(
                self.name,
                "Forbidden information source read observed "
                f"(#{self.forbidden_information_source_count}); keeping tree, "
                "auditing it, and asking the agent to use legal views instead.",
                _YELLOW,
            )
            return
        if pending_non_forbidden:
            self.forbidden_information_source_count = 0
            self.forbidden_information_source_last = ""
            self.forbidden_information_source_reason = ""
        if pending_lossy:
            self.forbidden_information_source_count = 0
            self.forbidden_information_source_last = ""
            self.forbidden_information_source_reason = ""
            self.lossy_session_cli_command = pending_lossy
            self.lossy_session_cli_time = time.time()
            self.lossy_session_cli_count += 1
            if (
                pending_lossy_policy is not None
                and pending_lossy_policy.audit_code.startswith("session_cli.")
            ):
                status(
                    self.name,
                    "Lossy session_cli pipeline observed; keeping tree, "
                    "but structured/full output has higher authority.",
                    _YELLOW,
                )
        if pending_background and _is_background_tool_result(result_text):
            now = time.time()
            self.forbidden_information_source_count = 0
            self.forbidden_information_source_last = ""
            self.forbidden_information_source_reason = ""
            self.background_session_cli_command = pending_background
            self.background_session_cli_time = now
            self.background_session_cli_notice_time = now
            self.background_session_cli_count += 1
            self.last_progress_time = now
            self.information_source_audit.append({
                "tool_use_id": tool_use_id,
                "decision": "wait",
                "source_type": "background_session_cli_mutation",
                "authority": "slow_structured_mutation",
                "audit_code": "session_cli.background_mutation_wait",
                "description": pending_background[:240],
            })
            if len(self.information_source_audit) > 200:
                self.information_source_audit = self.information_source_audit[-200:]
            status(
                self.name,
                "Mutating session_cli command is still running in the "
                "background; preserving this tree and waiting.",
                _YELLOW,
            )
