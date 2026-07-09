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
from core.easycrypt.value_shapes import drop_empty as _shallow_drop_empty
from workflow.context_intents import is_context_topic_intent
from workflow.session_observer import WorkflowSessionSnapshot, observe_session
from workflow.prover_io_policy import (
    InformationSourceDecision,
    classify_bash_command,
    classify_read_path,
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
            if "-checkpoint" in cmd:
                return "Save checkpoint"
            if "-replay" in cmd:
                return "Replay from checkpoint"
            if "-status" in cmd:
                return "Check proof status"
            if "-swap-search" in cmd:
                return "Auto swap search"
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
    if intent in {"probe_tactic", "commit_tactic"}:
        tactic = str(payload.get("tactic") or "").strip()
        if len(tactic) > 220:
            tactic = tactic[:217].rstrip() + "..."
        return f"submit_proof_intent {intent}: {tactic}"
    if intent == "inspect_context":
        return (
            "submit_proof_intent inspect_context: "
            f"{str(payload.get('topic') or 'goal_info')}"
        )
    if is_context_topic_intent(intent):
        detail = ""
        for key in ("operator", "symbol", "name", "lemma", "invariant", "command"):
            value = str(payload.get(key) or "").strip()
            if value:
                detail = f": {value}"
                break
        return f"submit_proof_intent {intent}{detail}"
    if intent == "lookup_symbol":
        return (
            "submit_proof_intent lookup_symbol: "
            f"{str(payload.get('symbol') or '')}"
        )
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
        ("mentions_lookup_symbol", "lookup_symbol"),
        ("mentions_inspect_context", "inspect_context"),
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


def _is_proof_success(result_text: str) -> bool:
    """Fallback text check for candidate proof closure.

    Newer session_cli runs also write ``events.jsonl`` with
    ``proof.candidate_closed``. Trackers prefer that structured event
    when they know the prover's session directory; this marker remains
    a compatibility fallback for older sessions and raw tool output.
    """
    return "[ALL_GOALS_CLOSED]" in result_text


def _session_event_path(cwd: str, session_dir: str | None) -> Path | None:
    session_path = _session_dir_path(cwd, session_dir)
    return session_path / "events.jsonl" if session_path else None


def _session_dir_path(cwd: str, session_dir: str | None) -> Path | None:
    if not session_dir:
        return None
    p = Path(session_dir)
    if not p.is_absolute():
        p = Path(cwd) / p
    return p


def _event_log_has_candidate_closed(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    try:
        from workflow.proof_acceptance import validate_candidate_event_contract
        gate = validate_candidate_event_contract(path.parent)
        return gate.ok and gate.candidate_closed
    except Exception:
        return False


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


def _session_projection_has_candidate_closed(
    cwd: str,
    session_dir: str | None,
) -> bool:
    snapshot = _session_snapshot(cwd, session_dir)
    return bool(
        snapshot
        and (snapshot.candidate_ready or snapshot.final_ready)
    )


def _session_state_has_candidate_closed(cwd: str, session_dir: str | None) -> bool:
    """Structured fallback for sessions whose event log is unavailable.

    This keeps progress tracking aligned with session_cli's shared
    prompt/close parsing instead of scanning result text for
    `[ALL_GOALS_CLOSED]`.
    """
    session_path = _session_dir_path(cwd, session_dir)
    if session_path is None:
        return False
    if _session_projection_has_candidate_closed(cwd, session_dir):
        return True
    try:
        from core.easycrypt.session_state import read_session_state
        return bool(read_session_state(session_path).proof_candidate_closed)
    except Exception:
        return False


_APPLY_LEMMA_RE = re.compile(
    r"\b(?:apply|have\s+:=|have\s+\w+\s+:=|rewrite(?:\s+-)?|byequiv)"
    r"\s*\(?\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
)


def _extract_apply_lemma_names(tactic_text: str) -> list[str]:
    """Return lemma names from `apply LEMMA`, `have := LEMMA`, `rewrite LEMMA`.

    Used to track which lemmas the prover keeps trying to apply. Skips tactics
    that operate on in-goal hypotheses (single lowercase letters, short names).
    """
    names: list[str] = []
    for m in _APPLY_LEMMA_RE.finditer(tactic_text):
        name = m.group("name")
        # Ignore short names (likely hypothesis letters like h, h1, H)
        # and common non-lemma keywords
        if len(name) < 4:
            continue
        if name in ("auto", "wp", "sp", "rnd", "skip", "call", "proc",
                    "inline", "smt", "done", "trivial", "simplify", "idtac",
                    "fun", "move", "elim", "case", "split", "by",
                    "true", "false", "witness"):
            continue
        names.append(name)
    return names


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
        self.session_id = ""
        self.proved = False
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
        self._event_path = _session_event_path(cwd, session_dir)
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

    def _has_structured_snapshot(self) -> bool:
        snapshot = self.session_snapshot
        return bool(
            snapshot
            and (
                snapshot.event_log_exists
                or snapshot.history_exists
                or snapshot.commit_response_count
                or snapshot.agent_view_count
            )
        )

    def _allow_text_progress_fallback(self) -> bool:
        """Permit command/stdout heuristics only before structured facts exist."""
        if self._has_structured_snapshot():
            return False
        if self._event_path is not None and self._event_path.exists():
            return False
        return True

    def _refresh_structured_success(self) -> None:
        if self.proved:
            return
        snapshot = _session_snapshot(self._cwd, self._session_dir)
        if snapshot is not None:
            self.session_snapshot = snapshot
            self._apply_session_snapshot(snapshot)
            if snapshot.candidate_ready or snapshot.final_ready:
                self.proved = True
                return
            if snapshot.event_log_exists or snapshot.contract_errors:
                return
        if _session_projection_has_candidate_closed(
            self._cwd, self._session_dir,
        ):
            self.proved = True
            return
        if self._event_path is not None and self._event_path.exists():
            if _event_log_has_candidate_closed(self._event_path):
                self.proved = True
            return
        if not self.proved and _session_state_has_candidate_closed(
            self._cwd, self._session_dir,
        ):
            self.proved = True

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
                    self._refresh_structured_success()
                    return  # no data available right now
            except (ValueError, OSError):
                self._drain_stderr()
                self.persist_stderr(reason="worker_io_error",
                                    returncode=getattr(self.proc, "returncode", None))
                self.finished = True
                return

    def _process_line(self, line: str):
        if not line:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return

        event_type = event.get("type", "")

        # Capture session_id from init or any event
        if not self.session_id and event.get("session_id"):
            self.session_id = event["session_id"]

        if event_type == "result":
            self.result_text = event.get("result", "")
            self.finished = True
            # Clean final-result signal (only `_emit_final` prints this).
            self.final_result_emitted = True

        # Text markers are a compatibility fallback. Once a session event log
        # exists, candidate closure must come from WorkflowSessionSnapshot.
        if event_type == "user":
            self.last_activity_time = time.time()
            content = event.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        result_text = block.get("content", "")
                        self._refresh_structured_success()
                        if (
                            not self.proved
                            and isinstance(result_text, str)
                            and _is_proof_success(result_text)
                            and self._allow_text_progress_fallback()
                        ):
                            self.proved = True

        # Command parsing is now a pre-session fallback for display only.
        # Once events/artifacts exist, WorkflowSessionSnapshot supplies the
        # committed count and error state.
        if event_type == "assistant":
            self.last_activity_time = time.time()
            if not self._allow_text_progress_fallback():
                _handle_stream_event(event, self.name, None)
                self._refresh_structured_success()
                return
            content = event.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use" and block.get("name") == "Bash":
                            cmd = block.get("input", {}).get("command", "")
                            if "session_cli" in cmd and "-next" in cmd and "-c" in cmd:
                                self.accepted_tactics += 1
                                self.last_progress_time = time.time()
                            elif "session_cli" in cmd and "-chain" in cmd and "-c" in cmd:
                                # Count tactics in the chain body. Use max() so
                                # that a re-try with a shorter chain doesn't
                                # regress the counter.
                                chain_text = cmd.split("-c", 1)[-1].strip().strip("'\"").strip()
                                n_tactics = len([t for t in chain_text.split(".") if t.strip()])
                                self.accepted_tactics = max(self.accepted_tactics, n_tactics)
                                self.last_progress_time = time.time()
                            if "-prev" in cmd:
                                self.accepted_tactics = max(0, self.accepted_tactics - 1)
                                self.errors += 1

        # Display events using existing handler
        _handle_stream_event(event, self.name, None)
        self._refresh_structured_success()


STRUCTURAL_COMMIT_OPENERS = frozenset({
    "byequiv", "byphoare", "bypr", "proc", "inline", "call",
    "transitivity", "seq", "while", "eager", "case", "sim",
    "rewrite", "have", "conseq",
})


ANALYSIS_TOOL_FLAGS = (
    "-bridge-probe", "-search", "-sig", "-clones",
    "-goal-info", "-align", "-diagnose", "-inv-from-lemma",
    "-tactic-forms", "-try",
)


_ANALYSIS_TOOL_RE = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(f) for f in ANALYSIS_TOOL_FLAGS) + r")(?![\w-])"
)


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


def _session_history_path(cwd: str, session_tag: str) -> Path:
    return Path(cwd) / f".ec_session_{session_tag}" / "history.ec"


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
        # grows; ANY rewind — `undo_last_step` (-prev) OR `undo_to_checkpoint`
        # (force-restart + shorter replay) — truncates history.ec, so the count
        # dips below the max ever seen. This is the resume-drift-gate's
        # authoritative "agent owns the prefix now" signal, because it is a
        # stable state both undo intents produce — unlike `last_undo_time`,
        # which is only set on a `tactic.undone` event that `undo_to_checkpoint`
        # never emits.
        self.history_ever_shrank: bool = False
        # Compose-first tracking
        self.chain_attempts: int = 0          # total -chain calls
        self.chain_tactic_estimate: int = 0   # estimated tactics in latest chain
        # Layer-1 deterministic progress metric: read from history.ec so we
        # know what EC actually accepted, not what the prover submitted.
        # Cached with a short TTL to avoid stat()-ing on every kill check.
        self._cwd = cwd
        self._session_tag = session_tag
        self._hist_cache_until: float = 0.0
        self._hist_lines_cache: list[str] = []
        self.prefix_credit: int = 0
        # Apply-lemma attempt counter — keyed by bare lemma name. Populated on
        # every `apply LEMMA` or `have := LEMMA` seen in Bash tool_use commands,
        # whether the attempt succeeds or fails. Used by the tree loop's
        # auto-escalation: if the same lemma appears here 2+ times on a node
        # with errors_since_last_accept > 0, the orchestrator fetches its
        # signature and injects a [SIG] discovery for subsequent children.
        self.attempted_applies: dict[str, int] = {}
        # Timestamp of the last analysis / probe session_cli call (see
        # ANALYSIS_TOOL_FLAGS above). 0.0 means never. The kill check
        # uses this to grace laggards that are actively probing (e.g.
        # cycling through `-bridge-probe` variants) even though their
        # committed tactic count hasn't advanced yet.
        self.last_analysis_call_time: float = 0.0
        # Log throttle for analysis-mode stuck-spawn deferrals. Do not use this
        # as a handled flag: once the analysis window expires, the branch should
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
        self._payload_audit_seen_agent_artifacts: set[str] = set()
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
        # -> 0) and then replays the shorter prefix ONE `-next` subprocess per
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
        # `have ...; admit.` then `-prev`s it can transiently inflate then lower
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
            self.last_analysis_call_time = max(
                self.last_analysis_call_time,
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
        if response.get("command") == "chain":
            self.chain_attempts += 1
            self.chain_tactic_estimate = int(mutation.get("attempted_count") or 0)
        for tactic in attempted:
            if not isinstance(tactic, str):
                continue
            for name in _extract_apply_lemma_names(tactic):
                self.attempted_applies[name] = (
                    self.attempted_applies.get(name, 0) + 1
                )
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
        agent_payload = snapshot.latest_agent_payload or {}
        agent_artifact = str(agent_payload.get("artifact") or "")
        if (
            agent_artifact
            and agent_artifact not in self._payload_audit_seen_agent_artifacts
        ):
            self._payload_audit_seen_agent_artifacts.add(agent_artifact)
            self.payload_audit.record_session_artifact(
                tree=self.name,
                session_tag=self._session_tag,
                kind="agent_view",
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
        path = _session_history_path(self._cwd, self._session_tag)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        except (OSError, UnicodeDecodeError):
            lines = []
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

        # Capture session_id
        if not self.session_id and event.get("session_id"):
            self.session_id = event["session_id"]

        if event_type == "result":
            self.result_text = event.get("result", "")
            self.finished = True
            # Clean final-result signal (only `_emit_final` prints this); used by
            # Layer-3 to distinguish a graceful give-up from a hard crash.
            self.final_result_emitted = True

        # Fresh-context continuation observability hygiene: when the worker swaps
        # in a fresh Claude context (Layer 1/2), it emits this `system` marker. The
        # idle / errors-since-accept timers are claude-PROCESS-scoped, so the brief
        # stream gap while the new child boots must NOT be read as a stall or
        # idle-give-up. `proved`/`accepted_tactics` derive from the surviving EC
        # snapshot and are deliberately left untouched. See
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

        # Text markers are fallback only; structured snapshots are authoritative.
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
                        self._refresh_structured_success()
                        if (
                            not self.proved
                            and isinstance(result_text, str)
                            and _is_proof_success(result_text)
                            and self._allow_text_progress_fallback()
                        ):
                            self.proved = True

        # Track tactics from tool_use Bash calls only as a fallback before the
        # structured session stream appears.
        if event_type == "assistant":
            if not self._allow_text_progress_fallback():
                _handle_stream_event(event, self.name, None)
                self._refresh_structured_success()
                return
            content = event.get("message", {}).get("content", [])
            if isinstance(content, list):
                # Note: proof success is detected ONLY from tool_result
                # "added lemma" (EC's confirmation), not from prover text.

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    if block.get("name") != "Bash":
                        continue
                    cmd = block.get("input", {}).get("command", "")
                    if "session_cli" not in cmd:
                        continue

                    # Analysis / probe calls — refresh the timestamp so the
                    # kill check can distinguish "laggard is actively probing"
                    # from "laggard is stuck thinking". Cheap to check; the
                    # regex is compiled once at module scope.
                    if _ANALYSIS_TOOL_RE.search(cmd):
                        self.last_analysis_call_time = time.time()

                    if "-next" in cmd and "-c" in cmd:
                        # Extract tactic text
                        tactic = cmd.split("-c")[-1].strip().strip("'\"").strip()
                        self.accepted_tactics += 1
                        self.last_progress_time = time.time()
                        self.last_accept_time = time.time()
                        self.errors_since_last_accept = 0
                        self.max_committed_count_seen = max(
                            self.max_committed_count_seen,
                            self.accepted_tactics,
                        )
                        self.accepted_tactic_texts.append(tactic)
                        # Reset stuck flag — prover is making progress again
                        self.stuck_handled = False
                        if self.last_structural_undo_time > 0:
                            self.structural_undo_branch = None
                            self.structural_undo_branch_time = 0.0
                        # Do NOT detect qed from the command — it might fail.
                        # Proof success is detected from tool_result "added lemma".
                        # Track apply/have attempts for auto-escalation
                        for name in _extract_apply_lemma_names(tactic):
                            self.attempted_applies[name] = \
                                self.attempted_applies.get(name, 0) + 1

                    elif "-prev" in cmd:
                        self.max_committed_count_seen = max(
                            self.max_committed_count_seen,
                            self.accepted_tactics,
                            len(self.accepted_tactic_texts),
                        )
                        self.accepted_tactics = max(0, self.accepted_tactics - 1)
                        self.errors += 1
                        self.errors_since_last_accept += 1
                        self.last_undo_time = time.time()
                        self.last_progress_time = self.last_undo_time
                        if self.accepted_tactic_texts:
                            undone = self.accepted_tactic_texts.pop()
                            self.recent_failed_tactic = undone
                            self.recent_failed_time = time.time()
                            # Detect structural undo — this is the cleanest
                            # signal for a local child: replay the surviving
                            # prefix and avoid the exact tactic that was
                            # rolled back.
                            first_word = undone.split()[0].rstrip(".;") if undone else ""
                            if first_word in STRUCTURAL_COMMIT_OPENERS:
                                self.last_structural_undo_time = self.last_undo_time
                                # Save: prefix = remaining tactics, failed = undone + what follows
                                self.structural_undo_branch = (
                                    list(self.accepted_tactic_texts),  # copy of prefix
                                    [undone],  # the undone structural tactic
                                )
                                self.structural_undo_branch_time = self.last_undo_time

                    elif "-chain" in cmd and "-c" in cmd:
                        # Chain applies multiple tactics at once.
                        # Count tactics in the command for progress estimation.
                        self.chain_attempts += 1
                        chain_text = cmd.split("-c")[-1].strip().strip("'\"").strip()
                        n_tactics = len([t for t in chain_text.split(".") if t.strip()])
                        self.chain_tactic_estimate = n_tactics
                        # Track apply/have attempts inside the chain
                        for name in _extract_apply_lemma_names(chain_text):
                            self.attempted_applies[name] = \
                                self.attempted_applies.get(name, 0) + 1
                        # Credit chain as progress: use the tactic count from the
                        # chain so the prover doesn't look idle. If the chain fails
                        # and the prover retries, max() keeps the best attempt.
                        self.accepted_tactics = max(self.accepted_tactics, n_tactics)
                        self.max_committed_count_seen = max(
                            self.max_committed_count_seen,
                            self.accepted_tactics,
                        )
                        self.last_progress_time = time.time()
                        self.last_accept_time = time.time()
                        self.errors_since_last_accept = 0
                        self.stuck_handled = False
                        # Do NOT detect qed from chain COMMAND text — the chain
                        # might fail. Only detect qed from -next commands (which
                        # means EC already accepted the tactic) or from the prover's
                        # result text containing "added lemma" / "No more goals".

        # Display events using existing handler
        _handle_stream_event(event, self.name, None)
        self._refresh_structured_success()

    def _track_session_hygiene_tool_uses(self, event: dict) -> None:
        content = event.get("message", {}).get("content", [])
        if not isinstance(content, list):
            return
        current_session_dir = Path(self._cwd) / f".ec_session_{self._session_tag}"
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
                    current_session_dir=current_session_dir,
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
                    current_session_dir=current_session_dir,
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
                current_session_dir=current_session_dir,
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
            )
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
