"""Payload audit for live prover runs.

The information-source policy tells us whether a read is allowed, lossy, or
forbidden.  This recorder answers a slightly different audit question: what did
the agent actually receive after each tool call, and which structured artifacts
were available at that frontier?
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from workflow.prover_io_policy import InformationSourceDecision


_FULL_OUTPUT_RE = re.compile(r"Full output saved to:\s*(\S+)")
_WORKSPACE_KIND_RE = re.compile(r'"kind"\s*:\s*"prover_workspace_view"')
_PROBE_CANDIDATE_RE = re.compile(r'"kind"\s*:\s*"probe_candidate_after"')
_WORKSPACE_FIELD_RE = re.compile(r'"workspace"\s*:\s*\{\s*"view"\s*:\s*\{')
_PROBE_CANDIDATE_FIELD_RE = re.compile(r'"candidate_after"\s*:\s*\{')


def summarize_text_payload(text: str) -> dict[str, Any]:
    """Return transport-size markers without copying the full payload."""
    data = text.encode("utf-8", errors="replace")
    contains_proof_context = "proof_context_view" in text
    contains_proof_state = '"proof_state"' in text or "proof_state" in text
    return {
        "chars": len(text),
        "bytes": len(data),
        "lines": 0 if not text else text.count("\n") + 1,
        "sha1": hashlib.sha1(data).hexdigest(),
        "contains_tactic_execution_result": "[TACTIC-EXECUTION-RESULT]" in text,
        "contains_command_summary": "[COMMAND-SUMMARY]" in text,
        "contains_commit_response": "[COMMIT-RESPONSE]" in text,
        "contains_prover_workspace_view": bool(
            _WORKSPACE_KIND_RE.search(text) or _WORKSPACE_FIELD_RE.search(text)
        ),
        "contains_probe_candidate_after": bool(
            _PROBE_CANDIDATE_RE.search(text)
            or _PROBE_CANDIDATE_FIELD_RE.search(text)
        ),
        "contains_proof_context_ref": contains_proof_context,
        "contains_proof_state_json": contains_proof_state,
        # Deprecated compatibility alias.  This never meant that the legacy
        # -agent-view command was printed; it only meant proof-state/context
        # strings were present in the payload.
        "contains_agent_view": contains_proof_context or contains_proof_state,
        "contains_output_too_large": "Output too large" in text,
        "contains_background_notice": "Command running in background" in text,
        "full_output_saved_to": _FULL_OUTPUT_RE.findall(text)[:5],
    }


def coerce_tool_result_text(content: Any) -> str:
    """Normalize Claude stream-json tool_result content into text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    chunks.append(str(text))
        return "\n".join(chunks)
    if content is None:
        return ""
    return str(content)


def _policy_to_dict(policy: InformationSourceDecision | None) -> dict[str, Any]:
    if policy is None:
        return {}
    return {
        "decision": policy.decision,
        "source_type": policy.source_type,
        "authority": policy.authority,
        "reason": policy.reason,
        "lossy": policy.lossy,
        "mutates_proof_state": policy.mutates_proof_state,
        "audit_code": policy.audit_code,
    }


def _summarize_tool_input(tool_name: str, tool_input: Any) -> dict[str, Any]:
    if not isinstance(tool_input, dict):
        return {"input_type": type(tool_input).__name__}
    if tool_name == "Bash":
        command = str(tool_input.get("command") or "")
        return {
            "command_head": command[:500],
            "command_chars": len(command),
            "command_sha1": hashlib.sha1(command.encode("utf-8")).hexdigest(),
        }
    if tool_name == "Read":
        file_path = str(tool_input.get("file_path") or "")
        return {
            "file_path": file_path,
            "offset": tool_input.get("offset"),
            "limit": tool_input.get("limit"),
        }
    if _is_submit_proof_intent_tool(tool_name):
        payload = tool_input.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        tactic = str(payload.get("tactic") or "")
        return {
            "intent": str(tool_input.get("intent") or ""),
            "tactic_head": tactic[:300],
            "tactic_chars": len(tactic),
            "topic": payload.get("topic"),
            "symbol": payload.get("symbol"),
        }
    keys = sorted(str(key) for key in tool_input.keys())
    return {"keys": keys}


def _is_submit_proof_intent_tool(tool_name: str) -> bool:
    return str(tool_name or "").endswith("submit_proof_intent")


def _artifact_stats(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    try:
        stat = path.stat()
    except OSError:
        return {"artifact": path_text, "exists": False}
    return {
        "artifact": path_text,
        "exists": True,
        "bytes": stat.st_size,
        "mtime": stat.st_mtime,
    }


def _json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, sort_keys=True))
    except TypeError:
        return 0


@dataclass
class PayloadAuditRecorder:
    """Append-only JSONL recorder for prover-facing payload evidence."""

    path: Path | str | None
    enabled: bool = True
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.path is not None and not isinstance(self.path, Path):
            self.path = Path(self.path)

    def record(self, event: str, **fields: Any) -> None:
        if not self.enabled or self.path is None:
            return
        payload = {
            "schema_version": 1,
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "event": event,
            **fields,
        }
        path = self.path
        assert isinstance(path, Path)
        try:
            line = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        except TypeError:
            safe_payload = json.loads(json.dumps(payload, default=str))
            line = json.dumps(safe_payload, sort_keys=True, ensure_ascii=False)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def record_tool_use(
        self,
        *,
        tree: str,
        session_tag: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: Any,
        policy: InformationSourceDecision | None = None,
        description: str = "",
        assistant_context: dict[str, Any] | None = None,
    ) -> None:
        self.record(
            "tool_use",
            tree=tree,
            session_tag=session_tag,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            input=_summarize_tool_input(tool_name, tool_input),
            policy=_policy_to_dict(policy),
            description=description[:500],
            assistant_context=assistant_context or {},
        )

    def record_tool_result(
        self,
        *,
        tree: str,
        session_tag: str,
        tool_use_id: str,
        result_text: str,
        pending_kind: str = "",
        pending_description: str = "",
        pending_reason: str = "",
    ) -> None:
        self.record(
            "tool_result",
            tree=tree,
            session_tag=session_tag,
            tool_use_id=tool_use_id,
            pending_kind=pending_kind,
            pending_description=pending_description[:500],
            pending_reason=pending_reason[:500],
            result=summarize_text_payload(result_text),
        )

    def record_session_artifact(
        self,
        *,
        tree: str,
        session_tag: str,
        kind: str,
        snapshot: Any,
    ) -> None:
        if kind == "commit_response":
            payload = getattr(snapshot, "latest_commit_payload", None) or {}
            data = getattr(snapshot, "latest_commit_response", None) or {}
            mutation = data.get("mutation") if isinstance(data, dict) else {}
            if not isinstance(mutation, dict):
                mutation = {}
            self.record(
                "session_artifact",
                tree=tree,
                session_tag=session_tag,
                kind=kind,
                artifact=_artifact_stats(str(payload.get("artifact") or "")),
                payload={
                    "status": payload.get("status"),
                    "proof_status": payload.get("proof_status"),
                    "accepted_count": payload.get("accepted_count"),
                    "attempted_count": payload.get("attempted_count"),
                },
                data={
                    "command": data.get("command") if isinstance(data, dict) else None,
                    "status": data.get("status") if isinstance(data, dict) else None,
                    "json_chars": _json_size(data),
                    "accepted_count": mutation.get("accepted_count"),
                    "attempted_count": mutation.get("attempted_count"),
                    "failed_tactic": mutation.get("failed_tactic"),
                },
                proof_state={
                    "status": getattr(snapshot, "status", "unknown"),
                    "goal_type": getattr(snapshot, "goal_type", "unknown"),
                    "goal_hash": getattr(snapshot, "goal_hash", ""),
                    "num_remaining": getattr(snapshot, "num_remaining", None),
                    "tactic_count": getattr(snapshot, "tactic_count", 0),
                },
            )
            return

        if kind == "tactic_execution_result":
            payload = (
                getattr(snapshot, "latest_tactic_execution_payload", None) or {}
            )
            data = (
                getattr(snapshot, "latest_tactic_execution_result", None) or {}
            )
            workspace = data.get("workspace") if isinstance(data, dict) else {}
            if not isinstance(workspace, dict):
                workspace = {}
            candidate_after = data.get("candidate_after") if isinstance(data, dict) else {}
            if not isinstance(candidate_after, dict):
                candidate_after = {}
            workspace_view = (
                workspace.get("view")
                if isinstance(workspace.get("view"), dict) else {}
            )
            current_goal = (
                workspace_view.get("current_goal")
                if isinstance(workspace_view, dict) else {}
            )
            if not isinstance(current_goal, dict):
                current_goal = {}
            raw_goal_lines = current_goal.get("lines")
            if isinstance(raw_goal_lines, list):
                raw_goal = "\n".join(str(line) for line in raw_goal_lines)
            else:
                raw_goal = str(raw_goal_lines or "")
            candidate_goal = (
                candidate_after.get("current_goal")
                if isinstance(candidate_after.get("current_goal"), dict) else {}
            )
            candidate_lines = candidate_goal.get("lines")
            if isinstance(candidate_lines, list):
                candidate_goal_text = "\n".join(str(line) for line in candidate_lines)
            else:
                candidate_goal_text = str(candidate_lines or "")
            self.record(
                "session_artifact",
                tree=tree,
                session_tag=session_tag,
                kind=kind,
                artifact=_artifact_stats(str(payload.get("artifact") or "")),
                payload={
                    "mode": payload.get("mode"),
                    "status": payload.get("status"),
                    "accepted_count": payload.get("accepted_count"),
                    "workspace_chars": payload.get("workspace_chars"),
                    "candidate_after_available": payload.get(
                        "candidate_after_available"
                    ),
                    "candidate_after_goal_chars": payload.get(
                        "candidate_after_goal_chars"
                    ),
                },
                data={
                    "json_chars": _json_size(data),
                    "workspace_json_chars": _json_size(workspace_view),
                    "compiler_extras_json_chars": max(
                        0,
                        _json_size(workspace_view) - _json_size(current_goal),
                    ),
                    "raw_goal_chars": len(raw_goal),
                    "raw_goal_json_chars": _json_size(raw_goal),
                    "candidate_after_goal_chars": len(candidate_goal_text),
                    "candidate_after_goal_json_chars": _json_size(
                        candidate_goal_text
                    ),
                    "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else [],
                },
                proof_state={
                    "status": getattr(snapshot, "status", "unknown"),
                    "goal_type": getattr(snapshot, "goal_type", "unknown"),
                    "goal_hash": getattr(snapshot, "goal_hash", ""),
                    "num_remaining": getattr(snapshot, "num_remaining", None),
                    "tactic_count": getattr(snapshot, "tactic_count", 0),
                },
            )
            return

        if kind == "agent_view":
            payload = getattr(snapshot, "latest_agent_payload", None) or {}
            data = getattr(snapshot, "latest_agent_view", None) or {}
            proof_state = data.get("proof_state") if isinstance(data, dict) else {}
            if not isinstance(proof_state, dict):
                proof_state = {}
            self.record(
                "session_artifact",
                tree=tree,
                session_tag=session_tag,
                kind=kind,
                artifact=_artifact_stats(str(payload.get("artifact") or "")),
                payload={
                    "proof_status": payload.get("proof_status"),
                    "goal_hash": payload.get("goal_hash"),
                },
                data={
                    "json_chars": _json_size(data),
                    "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else [],
                },
                proof_state={
                    "status": proof_state.get("status"),
                    "goal_type": getattr(snapshot, "goal_type", "unknown"),
                    "goal_hash": getattr(snapshot, "goal_hash", ""),
                    "num_remaining": getattr(snapshot, "num_remaining", None),
                    "tactic_count": getattr(snapshot, "tactic_count", 0),
                },
            )
            return

        if kind == "prover_workspace_view":
            payload = getattr(snapshot, "latest_workspace_payload", None) or {}
            data = getattr(snapshot, "latest_workspace_view", None) or {}
            current_goal = data.get("current_goal") if isinstance(data, dict) else {}
            if not isinstance(current_goal, dict):
                current_goal = {}
            raw_goal_lines = current_goal.get("lines")
            if isinstance(raw_goal_lines, list):
                raw_goal = "\n".join(str(line) for line in raw_goal_lines)
            else:
                raw_goal = str(raw_goal_lines or "")
            self.record(
                "session_artifact",
                tree=tree,
                session_tag=session_tag,
                kind=kind,
                artifact=_artifact_stats(str(payload.get("artifact") or "")),
                payload={
                    "proof_status": payload.get("proof_status"),
                    "goal_hash": payload.get("goal_hash"),
                    "current_goal_text_fully_shown": payload.get(
                        "current_goal_text_fully_shown",
                        payload.get("goal_complete"),
                    ),
                    "current_goal_truncated": payload.get(
                        "current_goal_truncated"
                    ),
                    "goal_chars": payload.get("goal_chars"),
                    "workspace_chars": payload.get("workspace_chars"),
                },
                data={
                    "json_chars": _json_size(data),
                    "compiler_extras_json_chars": max(
                        0,
                        _json_size(data) - _json_size(current_goal),
                    ),
                    "raw_goal_chars": len(raw_goal),
                    "raw_goal_json_chars": _json_size(raw_goal),
                    "top_level_keys": sorted(data.keys()) if isinstance(data, dict) else [],
                },
                proof_state={
                    "status": getattr(snapshot, "status", "unknown"),
                    "goal_type": getattr(snapshot, "goal_type", "unknown"),
                    "goal_hash": getattr(snapshot, "goal_hash", ""),
                    "num_remaining": getattr(snapshot, "num_remaining", None),
                    "tactic_count": getattr(snapshot, "tactic_count", 0),
                },
            )
