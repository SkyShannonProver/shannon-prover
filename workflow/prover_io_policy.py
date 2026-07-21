"""Information-source policy for live prover agents.

This module is the single place that classifies shell/Read access around
EasyCrypt sessions.  The policy is intentionally about information sources and
side effects, not about the literal word "grep": source grep can be fine,
while a lossy pipe on a mutating session command is not.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence


PolicyDecision = Literal["allow", "warn", "node_fatal", "deny"]

SESSION_CLI_MUTATING_FLAGS = frozenset({
    "-start",
    "-next",
    "-prev",
    "-chain",
    "-checkpoint",
    "-replay",
    "-write-back",
})

SESSION_CLI_AGENT_FORBIDDEN_LIFECYCLE_FLAGS = frozenset({
    "-start",
    "--force-restart",
})

SESSION_CLI_READONLY_FLAGS = frozenset({
    "-try",
    "-swap-search",
    "-status",
    "-agent-view",
    "-episode-view",
    "-goal-json",
    "-program-json",
    "-goal-info",
    "-subgoal-gap",
    "-align",
    "-diagnose",
    "-suggest-close",
    "-bridge-lemmas",
    "-inv-from-lemma",
    "-tactic-forms",
    "-where",
    "-members",
    "-clones",
    "-file-index",
    "-check-lemma",
    "-sig",
    "-search",
    "-search-skeleton",
    "-lemma-hints",
})

_SESSION_CLI_INVOKE_RE = re.compile(
    r"(?<!\S)(?:python3?|python)\s+\S*session_cli\.py\b"
    r"|"
    r"(?<!\S)\S*session_cli\.py\s+-"
)

_SOURCE_AUDIT_COMMANDS = frozenset({
    "cat",
    "grep",
    "head",
    "less",
    "ls",
    "more",
    "nl",
    "rg",
    "sed",
    "tail",
    "wc",
})

_PATHLIKE_SUFFIXES = (
    ".eca",
    ".ec",
    ".jsonl",
    ".json",
    ".log",
    ".md",
    ".out",
    ".py",
    ".txt",
)

_FRAMEWORK_ESCAPE_FILES = frozenset({
    "managed_prover_worker.py",
    "proof_node_manager.py",
    "proof_node_mcp_server.py",
    "proof_node_runtime.py",
    "proof_node_runtime_cli.py",
    "proof_node_runtime_client.py",
})

_BRIDGE_ESCAPE_RE = re.compile(
    r"\b(?:curl|nc|ncat|socat|lsof|netstat)\b.*(?:127\.0\.0\.1|localhost|workspace_view|bridge|token)"
    r"|"
    # NOTE: do NOT include a bare `workspace_view` here. The legal, agent-readable
    # current-node file is named `latest_workspace_view.json`, so a bare substring
    # match false-killed agents that read the exact file the anchor tells them to.
    # Network probing of the live socket view is still caught by the first branch.
    r"(?:manager_bridge|bridge[ _]token|auth token|authentication token)"
)

_RUNTIME_BRIDGE_DIRECT_RE = re.compile(
    r"\bworkflow\.proof_node_(?:runtime_(?:client|cli)|mcp_server)\b"
)


@dataclass(frozen=True)
class InformationSourceDecision:
    decision: PolicyDecision
    source_type: str
    authority: str
    reason: str
    lossy: bool = False
    mutates_proof_state: bool = False
    audit_code: str = ""

    @property
    def is_fatal(self) -> bool:
        return self.decision == "node_fatal"



def has_unquoted_shell_pipe(cmd: str) -> bool:
    """Return True when a shell pipeline appears outside quoted tactic text."""
    quote: str | None = None
    escaped = False
    for ch in cmd:
        if escaped:
            escaped = False
            continue
        if ch == "\\" and quote != "'":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch == "|":
            return True
    return False


def is_session_cli_command(cmd: str) -> bool:
    return bool(_SESSION_CLI_INVOKE_RE.search(cmd))


def session_cli_flags(cmd: str) -> set[str]:
    if not is_session_cli_command(cmd):
        return set()
    try:
        parts = shlex.split(cmd, posix=True)
    except ValueError:
        parts = cmd.split()
    return {part for part in parts if part.startswith("-")}


def tactic_exec_mode(cmd: str) -> str:
    if not is_session_cli_command(cmd):
        return ""
    try:
        parts = shlex.split(cmd, posix=True)
    except ValueError:
        parts = cmd.split()
    for idx, part in enumerate(parts):
        if part == "-tactic-exec" and idx + 1 < len(parts):
            return str(parts[idx + 1])
    return ""


def is_session_cli_mutating_command(cmd: str) -> bool:
    mode = tactic_exec_mode(cmd)
    if mode:
        return True
    return bool(session_cli_flags(cmd) & SESSION_CLI_MUTATING_FLAGS)


def classify_bash_command(
    cmd: str,
    *,
    cwd: str | Path | None = None,
    current_session_dir: str | Path | None = None,
    allowed_source_files: Sequence[str | Path] | None = None,
    allowed_node_memory_dirs: Sequence[str | Path] | None = None,
    target_lemma: str | None = None,
    eval_mode: bool = False,
) -> InformationSourceDecision:
    """Classify a Bash command issued by a prover agent."""
    source_decision: InformationSourceDecision | None = None
    if not is_session_cli_command(cmd):
        source_decision = classify_shell_source_access(
            cmd,
            cwd=cwd,
            current_session_dir=current_session_dir,
            allowed_source_files=allowed_source_files,
            allowed_node_memory_dirs=allowed_node_memory_dirs,
            target_lemma=target_lemma,
            eval_mode=eval_mode,
        )
        if (
            source_decision is not None
            and source_decision.decision == "allow"
            and source_decision.source_type == "shell_current_node_memory"
        ):
            return source_decision
    if _BRIDGE_ESCAPE_RE.search(cmd):
        return InformationSourceDecision(
            decision="node_fatal",
            source_type="manager_bridge_escape_attempt",
            authority="manager_owned_proof_interaction",
            reason=(
                "The prover agent tried to inspect or reverse-engineer the "
                "manager bridge/socket/token instead of submitting proof intents "
                "through the provided bridge client command."
            ),
            audit_code="manager_bridge.escape_attempt",
        )
    if _RUNTIME_BRIDGE_DIRECT_RE.search(cmd):
        return InformationSourceDecision(
            decision="node_fatal",
            source_type="manager_bridge_direct_client",
            authority="manager_owned_proof_interaction",
            reason=(
                "The prover agent bypassed the node submit script and called "
                "the runtime transport directly. Use the structured "
                "submit_proof_intent MCP tool for proof interaction."
            ),
            audit_code="manager_bridge.direct_client",
        )
    if not is_session_cli_command(cmd):
        if source_decision is not None:
            return source_decision
        return InformationSourceDecision(
            decision="allow",
            source_type="shell",
            authority="shell_output",
            reason="Non-session_cli shell command.",
        )
    piped = has_unquoted_shell_pipe(cmd)
    mutating = is_session_cli_mutating_command(cmd)
    return InformationSourceDecision(
        decision="node_fatal",
        source_type="session_cli_agent_debug_signal",
        authority="manager_owned_proof_interaction",
        reason=(
            "The prover agent invoked the low-level EasyCrypt session CLI. "
            "In managed prover runs this is a debug signal: either the "
            "agent-facing view omitted necessary information or the manager "
            "interaction layer is missing an action."
        ),
        lossy=piped,
        mutates_proof_state=mutating,
        audit_code="session_cli.agent_call_debug_signal",
    )


def classify_shell_source_access(
    cmd: str,
    *,
    cwd: str | Path | None = None,
    current_session_dir: str | Path | None = None,
    allowed_source_files: Sequence[str | Path] | None = None,
    allowed_node_memory_dirs: Sequence[str | Path] | None = None,
    target_lemma: str | None = None,
    eval_mode: bool = False,
) -> InformationSourceDecision | None:
    """Classify file sources touched by ordinary shell read/search commands.

    This intentionally does not ban `grep`/`rg`/`cat` as commands.  It extracts
    likely path operands and applies the same file-source policy as `Read`.
    """
    tokens = _shell_tokens(cmd)
    if not tokens:
        return None
    read_like = any(_shell_basename(tok) in _SOURCE_AUDIT_COMMANDS for tok in tokens)
    path_tokens = [tok for tok in tokens if _looks_like_path_operand(tok)]
    if not read_like and not path_tokens:
        return None
    if path_tokens and _is_submit_script_execution(tokens, path_tokens, cwd=cwd):
        path_tokens = [
            tok for tok in path_tokens if not _is_submit_script_path(tok, cwd=cwd)
        ]
        if not read_like and not path_tokens:
            return None

    decisions = [
        classify_read_path(
            tok,
            cwd=cwd,
            current_session_dir=current_session_dir,
            allowed_source_files=allowed_source_files,
            allowed_node_memory_dirs=allowed_node_memory_dirs,
            target_lemma=target_lemma,
            eval_mode=eval_mode,
        )
        for tok in path_tokens
    ]
    denied = next((d for d in decisions if d.decision in {"deny", "node_fatal"}), None)
    if denied is not None:
        return InformationSourceDecision(
            decision=denied.decision,
            source_type=f"shell_{denied.source_type}",
            authority=denied.authority,
            reason=denied.reason,
            audit_code=denied.audit_code or "shell_source.denied",
        )
    warned = next((d for d in decisions if d.decision == "warn"), None)
    if warned is not None:
        return InformationSourceDecision(
            decision="warn",
            source_type=f"shell_{warned.source_type}",
            authority=warned.authority,
            reason=warned.reason,
            audit_code=warned.audit_code or "shell_source.warn",
        )
    if read_like and path_tokens:
        if decisions and all(d.source_type == "current_node_memory" for d in decisions):
            return InformationSourceDecision(
                decision="allow",
                source_type="shell_current_node_memory",
                authority="curated_node_memory",
                reason=(
                    "Legal current node memory lookup. These files are curated "
                    "manager handoffs/history for this node, not backend transport."
                ),
                audit_code="shell_node_memory.inspect",
            )
        return InformationSourceDecision(
            decision="allow",
            source_type="shell_source_inspection",
            authority="source_or_raw_session_text",
            reason=(
                "Legal shell source/raw-session inspection. Treat it as an "
                "audit signal for fields the structured view may need."
            ),
            audit_code="shell_source.inspect",
        )
    return None


def classify_read_path(
    file_path: str,
    *,
    cwd: str | Path | None = None,
    current_session_dir: str | Path | None = None,
    allowed_source_files: Sequence[str | Path] | None = None,
    allowed_node_memory_dirs: Sequence[str | Path] | None = None,
    target_lemma: str | None = None,
    eval_mode: bool = False,
) -> InformationSourceDecision:
    """Classify a Read path used by a prover agent."""
    raw = str(file_path or "")
    normalized = raw.replace("\\", "/")
    resolved = _resolve_path(cwd, raw)
    project_root = _resolve_project_root(cwd)
    # Claude project auto-memory notes (``~/.claude/projects/<p>/memory/``:
    # ``MEMORY.md`` + ``project_*.md``) carry SOLVED hints for target lemmas, so
    # reading them is a hard eval answer-leak. The agent reaches them by basename
    # via the memory tool, so a basename has no ``/.claude/`` substring to catch —
    # match by NAME (``MEMORY.md`` / ``project_*.md``), by the ``/memory/*.md``
    # path shape, AND by any path that RESOLVES under ``~/.claude``. This is
    # ``node_fatal``, not a mere ``deny``: a node that has already seen solved
    # hints must be discarded and respawned fresh, not warned and kept alive.
    name = Path(normalized).name
    try:
        home_claude = str((Path.home() / ".claude").resolve())
    except Exception:
        home_claude = str(Path.home() / ".claude")
    if (
        name == "MEMORY.md"
        or re.fullmatch(r"project_[A-Za-z0-9_]+\.md", name) is not None
        or ("/memory/" in normalized and name.endswith(".md"))
        or normalized == home_claude or normalized.startswith(home_claude + "/")
        or str(resolved) == home_claude or str(resolved).startswith(home_claude + "/")
    ):
        return InformationSourceDecision(
            decision="node_fatal",
            source_type="claude_memory_answer_leak",
            authority="answer_leak_guard",
            reason=(
                "Reading Claude project auto-memory notes (MEMORY.md / "
                "project_*.md) or ~/.claude internal files can expose solved "
                "target-lemma hints and stale proof traces. A node that has seen "
                "them is discarded and respawned fresh; request a manager view or "
                "report TOOL_BOUNDARY_MISSING instead."
            ),
            audit_code="read.claude_memory_answer_leak",
        )
    if "/.claude/" in normalized:
        return InformationSourceDecision(
            decision="deny",
            source_type="claude_internal_trace",
            authority="private_agent_transport",
            reason=(
                "Reading Claude's internal project/session files can expose "
                "prompts, bridge credentials, and stale proof traces."
            ),
            audit_code="read.claude_internal_trace",
        )
    if _is_allowed_source_file(resolved, cwd=cwd, allowed_source_files=allowed_source_files):
        safety = _target_source_answer_safety(resolved, target_lemma)
        if safety in {"contains_substantive_target_proof", "unverified_target_source"}:
            return InformationSourceDecision(
                decision="deny",
                source_type="active_target_source_contains_answer",
                authority="answer_leak_guard",
                reason=(
                    "The active target source file is not safe to expose as "
                    "a raw read: the target lemma proof body is not confirmed "
                    "to be open/admit-only. Use the manager workspace view or "
                    "a sanitized source excerpt instead."
                ),
                audit_code="read.active_target_source_contains_answer",
            )
        return InformationSourceDecision(
            decision="allow",
            source_type="active_target_source",
            authority="source_text",
            reason=(
                "Read is the active target source file for this proof run, "
                "and the target lemma proof body is open/admit-only. "
                "Source text is useful context, but proof-state interaction "
                "still belongs to the manager."
            ),
            audit_code="read.active_target_source",
        )
    if project_root and (
        _path_is_relative_to(resolved, project_root / "tmp")
        or _path_is_relative_to(resolved, project_root / "worktrees")
    ):
        return InformationSourceDecision(
            decision="deny",
            source_type="stale_project_artifact",
            authority="stale_or_sibling_run_artifact",
            reason=(
                "Project tmp/ and worktrees/ artifacts are stale experiments "
                "or sibling workspaces. Use the current ProverWorkspaceView "
                "and current node memory files instead."
            ),
            audit_code="read.stale_project_artifact",
        )
    if _is_submit_script_path(raw, cwd=cwd):
        return InformationSourceDecision(
            decision="deny",
            source_type="manager_bridge_submit_script_read",
            authority="framework_private_transport",
            reason=(
                "The submit_intent.sh file is execution-only. Reading it can "
                "expose manager bridge transport details; use the structured "
                "submit_proof_intent MCP tool instead."
            ),
            audit_code="read.manager_bridge_submit_script",
        )
    if Path(normalized).name == "proof_node_mcp_config.json":
        return InformationSourceDecision(
            decision="deny",
            source_type="manager_bridge_mcp_config_read",
            authority="framework_private_transport",
            reason=(
                "Runtime-private MCP config files can expose proof-node "
                "transport details; use the structured submit_proof_intent "
                "tool without inspecting its configuration."
            ),
            audit_code="read.manager_bridge_mcp_config",
        )
    if _is_allowed_node_memory_file(
        resolved,
        cwd=cwd,
        allowed_node_memory_dirs=allowed_node_memory_dirs,
    ):
        return _current_node_memory_decision()
    if (
        "/workflow/runs/" in normalized
        and "/node_memory/" in normalized
    ):
        return _current_node_memory_decision()
    # (A) The current run's OWN isolated source copy (`<run>/source/...`): the
    # target file plus the sibling/dependency `.ec`/`.eca` it imports (e.g.
    # ChaChaPoly's `ske.ec`, which defines `CPA_game`). Reading these is legal —
    # it is THIS run's source, not a prior-run artifact — even though the copy
    # lives under `artifacts/eval_suite/`. Without this, a needed sibling read was
    # denied as an "eval historical artifact" and (after 3 strikes) killed the
    # tree. The target file itself is handled by `_is_allowed_source_file` above
    # (answer-safety gated); a sibling here carries no target-proof answer, but we
    # still deny a sibling that itself holds the target lemma's substantive proof.
    run_source_root = _current_run_source_root(allowed_source_files, cwd)
    if run_source_root is not None and (
        resolved == run_source_root
        or _path_is_relative_to(resolved, run_source_root)
    ):
        if resolved.suffix in (".ec", ".eca") and (
            _target_source_answer_safety(resolved, target_lemma)
            == "contains_substantive_target_proof"
        ):
            return InformationSourceDecision(
                decision="deny",
                source_type="active_target_source_contains_answer",
                authority="answer_leak_guard",
                reason=(
                    "A file in the run's own source tree holds the target "
                    "lemma's substantive proof; use the manager workspace view "
                    "or a sanitized excerpt instead of a raw read."
                ),
                audit_code="read.active_target_source_contains_answer",
            )
        return InformationSourceDecision(
            decision="allow",
            source_type="current_run_isolated_source",
            authority="source_text",
            reason=(
                "Read/scan is within the current run's OWN isolated source copy "
                "(the target file's sibling/dependency `.ec` it imports). Legal "
                "source context; proof-state interaction still belongs to the "
                "manager."
            ),
            audit_code="read.current_run_isolated_source",
        )
    if eval_mode:
        eval_history = _eval_history_decision(resolved, project_root)
        if eval_history is not None:
            return eval_history
    if (
        "/workflow/runs/" in normalized
        and "/node_memory/" not in normalized
    ):
        return InformationSourceDecision(
            decision="deny",
            source_type="run_artifact_escape",
            authority="orchestrator_private_artifact",
            reason=(
                "Run-level bootstrap/audit artifacts are orchestrator-private; "
                "the prover agent may only read its current node_memory files "
                "for history."
            ),
            audit_code="read.run_artifact_escape",
        )
    if f"/workflow/{Path(normalized).name}" in normalized:
        name = Path(normalized).name
        if name in _FRAMEWORK_ESCAPE_FILES:
            return InformationSourceDecision(
                decision="deny",
                source_type="framework_bridge_code_read",
                authority="framework_private_code",
                reason=(
                    "The prover agent tried to inspect manager/runtime bridge "
                    "implementation details instead of using proof intents."
                ),
                audit_code="read.framework_bridge_code",
            )
    if "/tool-results/" in normalized:
        return InformationSourceDecision(
            decision="allow",
            source_type="claude_tool_result",
            authority="exact_transport_output",
            reason="Full persisted output from the immediately observed tool call.",
        )
    if re.search(r"/private/tmp/.*/tasks/[^/]+\.output$", normalized):
        return InformationSourceDecision(
            decision="deny",
            source_type="background_task_output",
            authority="shell_escape_output",
            reason="Background session_cli task output bypasses structured session state.",
            audit_code="read.background_task_output",
        )
    if eval_mode and (
        "knowledge/session_trace/processed/by_problem/" in normalized
        or normalized.endswith("knowledge/base/sources/proof_bank.jsonl")
        or normalized.endswith("workflow/proof_bank.jsonl")
    ):
        return InformationSourceDecision(
            decision="deny",
            source_type="eval_proof_cache",
            authority="cached_target_proof",
            reason="Eval mode forbids reading target proof caches.",
            audit_code="read.eval_proof_cache",
        )
    if ".ec_session_" in normalized:
        session_dir = _resolve_current_session_dir(cwd, current_session_dir)
        path = resolved
        if session_dir and _path_is_relative_to(path, session_dir):
            return InformationSourceDecision(
                decision="allow",
                source_type="current_session_artifact",
                authority="current_raw_session_artifact",
                reason="Read stays inside the current session directory.",
            )
        if normalized.endswith("/current.out"):
            return InformationSourceDecision(
                decision="warn",
                source_type="unknown_session_current_goal",
                authority="raw_goal_text_unknown_session",
                reason=(
                    "A current.out read is only authoritative for the current "
                    "session; verify the path matches the active -d session."
                ),
                audit_code="read.unknown_session_current_out",
            )
        return InformationSourceDecision(
            decision="deny",
            source_type="other_session_transcript",
            authority="stale_proof_transcript",
            reason="Reading other .ec_session_* transcripts can leak prior proofs.",
            audit_code="read.other_session_transcript",
        )
    # Eval-mode answer-leak guard (last line of defense): an `.ec`/`.eca` that
    # would otherwise be allowed as a plain project/source file but still holds
    # the target lemma's substantive (non-admit) proof leaks the answer. This
    # catches the ORIGINAL corpus file (never in allowed_source_files / outside
    # the run's source root) and any stray or `../`-reached copy — the
    # per-exact-path match above only covered the run's scrubbed isolated copy.
    # Only `contains_substantive_target_proof` is gated; a scrubbed admit-only
    # target and `unverified_target_source` (lemma absent — theory/sibling
    # reads) fall through to the allow below.
    if (eval_mode and target_lemma and resolved.suffix in (".ec", ".eca")
            and _target_source_answer_safety(resolved, target_lemma)
            == "contains_substantive_target_proof"):
        return InformationSourceDecision(
            decision="deny",
            source_type="eval_target_answer_source",
            authority="answer_leak_guard",
            reason=(
                "Eval mode: this file contains the target lemma's substantive "
                "proof, so a raw read would leak the answer. Use the manager "
                "workspace view or a sanitized source excerpt instead."
            ),
            audit_code="read.eval_target_answer_source",
        )
    return InformationSourceDecision(
        decision="allow",
        source_type="source_or_project_file",
        authority="source_text",
        reason="Project/source file read; use typed tools for signatures when available.",
    )


def _eval_history_decision(
    resolved: Path,
    project_root: Path | None,
) -> InformationSourceDecision | None:
    if project_root is None:
        return None
    try:
        rel = resolved.relative_to(project_root)
    except ValueError:
        return None
    parts = rel.parts
    if parts[:3] == ("docs", "reports", "eval_suite"):
        return InformationSourceDecision(
            decision="deny",
            source_type="eval_historical_report",
            authority="cached_eval_report",
            reason=(
                "Eval mode forbids reading prior eval reports; they can contain "
                "proofs, timelines, and analysis from earlier runs."
            ),
            audit_code="read.eval_historical_report",
        )
    if parts[:2] == ("artifacts", "eval_suite"):
        return InformationSourceDecision(
            decision="deny",
            source_type="eval_historical_artifact",
            authority="cached_eval_artifact",
            reason=(
                "Eval mode forbids reading prior eval artifacts unless the path "
                "is the current run's allowed isolated target source or current "
                "node memory."
            ),
            audit_code="read.eval_historical_artifact",
        )
    return None


def _shell_tokens(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


def _shell_basename(token: str) -> str:
    return Path(token).name


def _looks_like_path_operand(token: str) -> bool:
    if not token or token.startswith("-"):
        return False
    if token in {"|", "||", "&&", ";", ">", ">>", "<", "2>&1"}:
        return False
    if "=" in token and "/" not in token and not token.startswith("."):
        return False
    lowered = token.lower()
    if ".ec_session_" in token or "/tool-results/" in token:
        return True
    if "/" in token or token.startswith("."):
        return True
    if any(lowered.endswith(suffix) for suffix in _PATHLIKE_SUFFIXES):
        return True
    return False


def _is_submit_script_execution(
    tokens: list[str],
    path_tokens: list[str],
    *,
    cwd: str | Path | None,
) -> bool:
    submit_indexes = [
        idx for idx, tok in enumerate(tokens) if _is_submit_script_path(tok, cwd=cwd)
    ]
    if not submit_indexes:
        return False
    shell_wrappers = {"bash", "env", "sh", "zsh"}
    for idx in submit_indexes:
        if idx == 0:
            return True
        prev = tokens[idx - 1]
        if prev in {"|", "||", "&&", ";"}:
            return True
        if _shell_basename(prev) in shell_wrappers:
            return True
        if _shell_basename(tokens[0]) in shell_wrappers and idx <= 2:
            return True
    return False


def _is_submit_script_path(
    token: str,
    *,
    cwd: str | Path | None,
) -> bool:
    if Path(str(token)).name != "submit_intent.sh":
        return False
    resolved = _resolve_path(cwd, str(token))
    normalized = str(resolved).replace("\\", "/")
    return "/node_memory/" in normalized


def _current_node_memory_decision() -> InformationSourceDecision:
    return InformationSourceDecision(
        decision="allow",
        source_type="current_node_memory",
        authority="curated_node_memory",
        reason=(
            "Read stays inside curated current-node memory. It is legal "
            "history/current-view context, not proof-state authority."
        ),
        audit_code="read.node_memory",
    )


def _abs_fs_rule(tool: str, abs_path: str | Path) -> str:
    """A ``Read()``/``Edit()`` path rule for an ABSOLUTE filesystem path.

    A single leading slash in a tool path-rule anchors to the PROJECT ROOT
    (gitignore semantics), NOT the filesystem root — so an absolute path given
    with one slash silently fails to match and the read/write is NOT blocked.
    An absolute path must use a DOUBLE leading slash. See the ~/.claude block in
    ``destructive_tool_denylist`` for the regression this prevents.
    """
    s = str(abs_path)
    if s.startswith("//") or s.startswith("~"):
        return f"{tool}({s})"
    if s.startswith("/"):
        return f"{tool}(/{s})"
    return f"{tool}({s})"


def destructive_tool_denylist(
    source_file: str | Path,
    *,
    project_root: str | Path | None = None,
) -> list[str]:
    """Hard-deny only operations that are proof-corrupting or leak-prone."""
    src = Path(source_file).resolve()
    root = Path(project_root).resolve() if project_root is not None else Path.cwd()
    home = Path.home()
    framework_files = [
        root / "workflow" / name for name in sorted(_FRAMEWORK_ESCAPE_FILES)
    ]
    eval_report_dir = root / "docs" / "reports" / "eval_suite" / "**"
    eval_artifact_patterns = [
        root / "artifacts" / "eval_suite" / "**" / "eval_metrics.json",
        root / "artifacts" / "eval_suite" / "**" / "eval_metrics.md",
        root / "artifacts" / "eval_suite" / "**" / "summary.json",
        root / "artifacts" / "eval_suite" / "**" / "payload_audit.jsonl",
        root / "artifacts" / "eval_suite" / "**" / "information_source_audit.json",
        root / "artifacts" / "eval_suite" / "**" / "proof_node_manager_audit.jsonl",
        root / "artifacts" / "eval_suite" / "**" / "prover_prompt*.md",
        root / "artifacts" / "eval_suite" / "**" / "runtime_private" / "**",
    ]
    source_patterns = _source_edit_patterns(source_file, src=src, root=root)
    patterns = [
        "Bash(rm:*)",
        "Bash(rm -rf:*)",
        "Bash(rmdir:*)",
        "Bash(curl:*)",
        "Bash(nc:*)",
        "Bash(ncat:*)",
        "Bash(socat:*)",
        "Bash(lsof:*)",
        "Bash(netstat:*)",
        "Agent(*)",
        "Task(*)",
        "Glob(*)",
        "Bash(cat /private/tmp/*/tasks/*.output*)",
        "Bash(*cat /private/tmp/*/tasks/*.output*)",
        "Read(//private/tmp/*/tasks/*.output)",
        # ANSWER-LEAK GUARD (~/.claude project memory). PATH-ANCHORING CAVEAT: in
        # a Read()/Edit() permission rule a SINGLE leading slash anchors to the
        # PROJECT ROOT (gitignore semantics) — NOT the filesystem root. So
        # `Read(/Users/<u>/.claude/**)` silently fails to match the real absolute
        # path and the read LEAKS (observed: a prover Read its target's memory note
        # in full, then got node-killed only reactively). Absolute paths need a
        # DOUBLE leading slash (`//` = filesystem root) or the `~` form; and a bare
        # `*name` glob does NOT match outside the cwd subtree — use `**/name`.
        # Verified empirically + Claude Code permission docs (2026-06-05).
        f"Read(/{home}/.claude/**)",
        "Read(~/.claude/**)",
        f"Read(/{home}/.claude/projects/**)",
        f"Bash(*{home}/.claude/**)",
        # Auto-memory notes are also reachable by basename (memory tool / relative
        # path); `**/`-prefixed names match at any depth.
        "Read(**/MEMORY.md)",
        "Read(**/project_*.md)",
        "Read(**/memory/**)",
        # And block WRITING to memory: a stuck prover used Edit/Write to record a
        # blocker note into ~/.claude project memory (creating a project_*.md +
        # editing MEMORY.md). That pollutes the user's curated memory AND seeds a
        # self-reinforcing leak (a future prover could read it). Symmetric to the
        # read blocks above; the watchdog also node-kills these (classify of the
        # Edit/Write target -> claude_memory_answer_leak).
        "Edit(**/MEMORY.md)", "Write(**/MEMORY.md)", "MultiEdit(**/MEMORY.md)",
        "Edit(**/project_*.md)", "Write(**/project_*.md)", "MultiEdit(**/project_*.md)",
        "Edit(**/memory/**)", "Write(**/memory/**)", "MultiEdit(**/memory/**)",
        f"Edit(/{home}/.claude/**)", f"Write(/{home}/.claude/**)",
        f"MultiEdit(/{home}/.claude/**)",
        "Edit(~/.claude/**)", "Write(~/.claude/**)", "MultiEdit(~/.claude/**)",
        # Orchestrator-private run artifacts. These are absolute paths under the
        # project root, so the Read rules need the `//` double-slash form (a single
        # slash would anchor back to the project root and never fire); the Bash
        # rules match the command string and are fine as substrings.
        _abs_fs_rule("Read", f"{root}/workflow/runs/**/manager_bootstrap*"),
        _abs_fs_rule("Read", f"{root}/workflow/runs/**/payload_audit.jsonl"),
        _abs_fs_rule("Read", f"{root}/workflow/runs/**/proof_node_manager_audit.jsonl"),
        _abs_fs_rule("Read", f"{root}/workflow/runs/**/prover_prompt*.md"),
        _abs_fs_rule("Read", f"{root}/workflow/runs/**/runtime_private/**"),
        f"Bash(*{root}/workflow/runs/**/runtime_private/**)",
        "Read(**/proof_node_mcp_config.json)",
        "Bash(*proof_node_mcp_config.json*)",
        f"Bash(*manager_bootstrap*)",
        f"Bash(*payload_audit*)",
        f"Bash(*proof_node_manager_audit*)",
        f"Bash(*prover_prompt*.md*)",
        _abs_fs_rule("Read", eval_report_dir),
        f"Bash(*{eval_report_dir})",
    ]
    for path in eval_artifact_patterns:
        patterns.append(_abs_fs_rule("Read", path))
        patterns.append(f"Bash(*{path})")
    for tool in ("Edit", "MultiEdit", "Write"):
        for candidate in source_patterns:
            if str(candidate).startswith("/"):
                patterns.append(_abs_fs_rule(tool, candidate))
            else:
                patterns.append(f"{tool}({candidate})")
    patterns.extend(_abs_fs_rule("Read", path) for path in framework_files)
    patterns.extend(f"Bash(*{path})" for path in framework_files)
    # MANAGER-OWNED EC-MUTATION BOUNDARY (audit §6.1 / backlog #4). The prover's
    # protocol is its ProverWorkspaceView + the MCP intents; the EasyCrypt session
    # is manager-owned. Turn the post-hoc node-kill (``_track_session_hygiene...``)
    # into PREVENTION by hard-denying the MUTATING ``session_cli.py`` flags and any
    # write into the manager's ``.ec_session_*`` dirs at the tool boundary.
    # READ-ONLY session_cli (``-status``/``-goal-info``/``-where``/...) stays
    # allowed: a prover that reaches for it is the intentional
    # ``session_cli.agent_call_debug_signal`` ("the view was insufficient" — see
    # CLAUDE.md Session CLI Policy); blocking it would erase that signal. EC lemma
    # names and ``.ec_session_<tag>`` dirs contain no ``-<flag>`` substrings, so the
    # mutating-flag globs do not false-match a read-only invocation.
    patterns.extend(
        f"Bash(*session_cli*{flag}*)"
        for flag in sorted(
            SESSION_CLI_MUTATING_FLAGS | SESSION_CLI_AGENT_FORBIDDEN_LIFECYCLE_FLAGS
        )
    )
    # `-tactic-exec {commit,commit_chain,undo}` is the Canonical Proof
    # Interaction Manager entry point — a manager-INTERNAL tactic-submission API
    # whose commit/commit_chain/undo modes mutate committed proof state. It lives
    # in its own argparse ``dest`` (NOT in SESSION_CLI_MUTATING_FLAGS), so deny it
    # explicitly. Unlike the read-only INSPECTION flags it is not part of the
    # agent's debug-signal vocabulary, so blocking every mode erases no signal
    # (the agent submits tactics through the MCP intent, never this).
    patterns.append("Bash(*session_cli*-tactic-exec*)")
    patterns.extend([
        "Edit(**/.ec_session_*/**)",
        "Write(**/.ec_session_*/**)",
        "MultiEdit(**/.ec_session_*/**)",
    ])
    return patterns


def _source_edit_patterns(source_file: str | Path, *, src: Path, root: Path) -> list[str]:
    candidates: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    raw = str(source_file)
    add(str(src))
    add(raw)
    if raw and not raw.startswith("./") and not Path(raw).is_absolute():
        add(f"./{raw}")
    try:
        rel = src.relative_to(root)
    except ValueError:
        rel = None
    if rel is not None:
        rel_s = str(rel)
        add(rel_s)
        add(f"./{rel_s}")
    # `**/name` (not bare `*name`) so the basename matches at any depth, not just
    # in the cwd subtree. The relative rel/`./rel` forms above already block the
    # in-tree source path; this is the belt-and-suspenders basename catch.
    add(f"**/{src.name}")
    return candidates


def _resolve_project_root(cwd: str | Path | None) -> Path | None:
    if cwd is None:
        return None
    try:
        return Path(cwd).resolve()
    except Exception:
        return Path(cwd).absolute()


def _resolve_path(cwd: str | Path | None, path: str) -> Path:
    p = Path(path)
    if not p.is_absolute() and cwd is not None:
        p = Path(cwd) / p
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def _is_allowed_source_file(
    resolved: Path,
    *,
    cwd: str | Path | None,
    allowed_source_files: Sequence[str | Path] | None,
) -> bool:
    if not allowed_source_files:
        return False
    for candidate in allowed_source_files:
        cand = _resolve_path(cwd, str(candidate))
        if resolved == cand:
            return True
    return False


def _current_run_source_root(
    allowed_source_files: Sequence[str | Path] | None,
    cwd: str | Path | None,
) -> Path | None:
    """The eval run's OWN isolated source-copy root (``<run>/source/``).

    Derived as the nearest ancestor named ``source`` of an allowed target source
    file. Files under this root are the current run's own source — the target
    file plus the sibling/dependency ``.ec``/``.eca`` it imports (e.g.
    ChaChaPoly's ``ske.ec``) — NOT prior-run artifacts, even though the copy
    physically lives under ``artifacts/eval_suite/``.
    """
    for candidate in allowed_source_files or []:
        cand = _resolve_path(cwd, str(candidate))
        for parent in cand.parents:
            if parent.name == "source":
                return parent
    return None


def _is_allowed_node_memory_file(
    resolved: Path,
    *,
    cwd: str | Path | None,
    allowed_node_memory_dirs: Sequence[str | Path] | None,
) -> bool:
    if not allowed_node_memory_dirs:
        return False
    for candidate in allowed_node_memory_dirs:
        root = _resolve_path(cwd, str(candidate))
        if resolved == root or _path_is_relative_to(resolved, root):
            return True
    return False


def _target_source_answer_safety(path: Path, target_lemma: str | None) -> str:
    """Return whether exposing the active target source could leak the answer."""
    lemma = str(target_lemma or "").strip()
    if not lemma:
        return "unverified_target_source"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unverified_target_source"
    body = _target_lemma_proof_body(text, lemma)
    if body is None:
        return "unverified_target_source"
    scrubbed = _strip_ec_comments(body)
    normalized = re.sub(r"\s+", " ", scrubbed).strip()
    if not normalized:
        return "open_or_empty_target_proof"
    admit_only = re.fullmatch(r"(?:admit\s*\.\s*)+", normalized)
    if admit_only:
        return "admit_only_target_proof"
    return "contains_substantive_target_proof"


def _target_lemma_proof_body(text: str, lemma: str) -> str | None:
    name = re.escape(lemma)
    decl_re = re.compile(
        rf"(?m)^\s*(?:local\s+)?(?:lemma|equiv|hoare|phoare)\s+{name}\b"
    )
    match = decl_re.search(text)
    if not match:
        return None
    rest = text[match.end():]
    next_decl = re.search(
        r"(?m)^\s*(?:local\s+)?(?:lemma|equiv|hoare|phoare)\s+"
        r"[A-Za-z_][A-Za-z0-9_']*\b",
        rest,
    )
    region = rest[: next_decl.start()] if next_decl else rest
    proof = re.search(r"\bproof\s*\.\s*", region)
    if proof:
        after_proof = region[proof.end():]
        qed = re.search(r"\bqed\s*\.", after_proof)
        return after_proof[: qed.start()] if qed else after_proof
    bare_admit = re.search(r"\badmit\s*\.", region)
    if bare_admit:
        return region[bare_admit.start(): bare_admit.end()]
    return ""


def _strip_ec_comments(text: str) -> str:
    out: list[str] = []
    idx = 0
    depth = 0
    while idx < len(text):
        if text.startswith("(*", idx):
            depth += 1
            idx += 2
            continue
        if depth and text.startswith("*)", idx):
            depth -= 1
            idx += 2
            continue
        if depth == 0:
            out.append(text[idx])
        idx += 1
    return "".join(out)


def _resolve_current_session_dir(
    cwd: str | Path | None,
    current_session_dir: str | Path | None,
) -> Path | None:
    if current_session_dir is None:
        return None
    p = Path(current_session_dir)
    if not p.is_absolute() and cwd is not None:
        p = Path(cwd) / p
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
