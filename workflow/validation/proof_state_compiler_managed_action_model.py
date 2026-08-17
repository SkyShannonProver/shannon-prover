"""Tool-free Codex boundary for one managed proof action in a micro."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workflow.codex_event_protocol import (
    codex_event_text,
    observe_codex_exec_jsonl,
)
from workflow.validation.proof_state_compiler_one_step_model import (
    CODEX_ONE_STEP_DISABLED_FEATURES,
)


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["commit_tactic", "undo_last_step"],
        },
        "tactic": {"type": "string"},
    },
    "required": ["intent", "tactic"],
    "additionalProperties": False,
}
SYSTEM_PROMPT = (
    "You are selecting exactly one next managed EasyCrypt proof action for "
    "the current state. Do not solve later subgoals. Do not use tools or "
    "external context. Return one JSON object matching the schema. For "
    "commit_tactic, tactic must be directly submit-ready and end with a "
    "period. For undo_last_step, tactic must be the empty string and the "
    "control must be advertised in the packet."
)


def run_managed_action_model(
    prompt: str,
    *,
    model: str,
    effort: str,
    cwd: Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".compiler_managed_action_openai_",
        dir=cwd,
    ) as isolated_dir:
        isolated = Path(isolated_dir)
        schema_path = isolated / "managed_action_output.schema.json"
        schema_path.write_text(
            json.dumps(OUTPUT_SCHEMA, separators=(",", ":")),
            encoding="utf-8",
        )
        command = [
            shutil.which("codex") or "codex",
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
            "--skip-git-repo-check",
            "--cd", str(isolated),
            "--sandbox", "read-only",
            "--model", model,
            "--config", f'model_reasoning_effort="{effort}"',
            "--config", "project_doc_max_bytes=0",
            *[
                argument
                for feature in CODEX_ONE_STEP_DISABLED_FEATURES
                for argument in ("--disable", feature)
            ],
            "--output-schema", str(schema_path),
            "--json",
            SYSTEM_PROMPT + "\n\n" + prompt,
        ]
        started = time.perf_counter()
        result = subprocess.run(
            command,
            cwd=str(isolated),
            capture_output=True,
            text=True,
            timeout=300,
        )
    duration_ms = int((time.perf_counter() - started) * 1000)
    return decode_managed_action_result(
        result.stdout,
        result.stderr,
        returncode=result.returncode,
        duration_ms=duration_ms,
        prompt=prompt,
    )


@dataclass
class ManagedActionConversation:
    """One tool-free Codex conversation retained across a micro trajectory."""

    model: str
    effort: str
    cwd: Path
    system_prompt: str = SYSTEM_PROMPT
    timeout_seconds: int = 300
    thread_id: str = field(default="", init=False)
    _isolated: Path = field(init=False, repr=False)
    _schema_path: Path = field(init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _turn_number: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._isolated = Path(tempfile.mkdtemp(
            prefix=".compiler_managed_conversation_openai_",
            dir=self.cwd,
        ))
        self._schema_path = self._isolated / "managed_action_output.schema.json"
        self._schema_path.write_text(
            json.dumps(OUTPUT_SCHEMA, separators=(",", ":")),
            encoding="utf-8",
        )

    def close(self) -> None:
        if self._closed:
            return
        shutil.rmtree(self._isolated, ignore_errors=True)
        self._closed = True

    def __enter__(self) -> "ManagedActionConversation":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def next_action(self, prompt: str) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("managed action conversation is closed")
        next_turn_number = self._turn_number + 1
        command = (
            self._initial_command(prompt)
            if not self.thread_id
            else self._resume_command(prompt)
        )
        started = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                cwd=str(self._isolated),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return {
                "intent": None,
                "tactic": None,
                "returncode": -1,
                "duration_ms": duration_ms,
                "usage": {},
                "error": "managed action conversation timed out",
                "prompt_sha256": hashlib.sha256(
                    prompt.encode("utf-8")
                ).hexdigest(),
                "prompt_bytes": len(prompt.encode("utf-8")),
                "tools_observed": [],
                "thread_id": self.thread_id,
                "conversation_turn": next_turn_number,
                "provider_event_audit": {
                    "contract": "codex_exec_jsonl.v1",
                    "protocol_valid": False,
                    "provider_errors": [],
                    "protocol_unknowns": [],
                    "cardinality_errors": ["model process did not complete"],
                    "tool_item_types": [],
                },
            }
        duration_ms = int((time.perf_counter() - started) * 1000)
        decoded = decode_managed_action_result(
            result.stdout,
            result.stderr,
            returncode=result.returncode,
            duration_ms=duration_ms,
            prompt=prompt,
        )
        observed_thread = str(decoded.get("thread_id") or "")
        if not observed_thread:
            decoded["error"] = _append_error(
                str(decoded.get("error") or ""),
                "codex emitted no thread identity",
            )
        elif self.thread_id and observed_thread != self.thread_id:
            decoded["error"] = _append_error(
                str(decoded.get("error") or ""),
                "codex resumed a different thread",
            )
        elif not self.thread_id:
            self.thread_id = observed_thread
        self._turn_number = next_turn_number
        decoded["conversation_turn"] = next_turn_number
        decoded["thread_id"] = observed_thread
        return decoded

    def _initial_command(self, prompt: str) -> list[str]:
        return [
            shutil.which("codex") or "codex",
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--cd", str(self._isolated),
            "--sandbox", "read-only",
            "--model", self.model,
            "--config", f'model_reasoning_effort="{self.effort}"',
            "--config", "project_doc_max_bytes=0",
            *[
                argument
                for feature in CODEX_ONE_STEP_DISABLED_FEATURES
                for argument in ("--disable", feature)
            ],
            "--output-schema", str(self._schema_path),
            "--json",
            self.system_prompt + "\n\n" + prompt,
        ]

    def _resume_command(self, prompt: str) -> list[str]:
        return [
            shutil.which("codex") or "codex",
            "exec",
            "resume",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--model", self.model,
            "--config", f'model_reasoning_effort="{self.effort}"',
            "--config", "project_doc_max_bytes=0",
            *[
                argument
                for feature in CODEX_ONE_STEP_DISABLED_FEATURES
                for argument in ("--disable", feature)
            ],
            "--output-schema", str(self._schema_path),
            "--json",
            self.thread_id,
            prompt,
        ]


def decode_managed_action_result(
    stdout: str,
    stderr: str,
    *,
    returncode: int,
    duration_ms: int,
    prompt: str,
) -> dict[str, Any]:
    events, audit = observe_codex_exec_jsonl(stdout, stderr)
    errors = [
        f"invalid codex JSONL line {item['line']}: {item['error']}"
        for item in audit["invalid_jsonl_lines"]
    ]
    errors.extend(audit["cardinality_errors"])
    errors.extend(
        "unknown codex protocol item: "
        f"event={item.get('event_type')!r}, item={item.get('item_type')!r}"
        for item in audit["protocol_unknowns"]
    )
    errors.extend(
        "codex provider error: "
        + (str(item.get("message") or "").strip() or "unspecified error")
        for item in audit["provider_errors"]
    )
    answer_text = ""
    usage: dict[str, Any] = {}
    thread_id = ""
    for event in events:
        if event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id") or thread_id)
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
        ):
            answer_text = codex_event_text(item)
        if event.get("type") == "turn.completed" and isinstance(
            event.get("usage"), dict
        ):
            usage = dict(event["usage"])
    structured: dict[str, Any] = {}
    if answer_text:
        try:
            parsed = json.loads(answer_text)
            if isinstance(parsed, dict):
                structured = parsed
        except json.JSONDecodeError as exc:
            errors.append(f"codex answer did not match JSON schema: {exc}")
    else:
        errors.append("codex produced no final agent message")
    tools_observed = tuple(audit["tool_item_types"])
    if tools_observed:
        errors.append("codex used forbidden tools: " + ", ".join(tools_observed))
    if returncode != 0:
        errors.append(stderr.strip()[-1200:] or "codex call failed")
    return {
        "intent": structured.get("intent"),
        "tactic": structured.get("tactic"),
        "returncode": returncode,
        "duration_ms": duration_ms,
        "usage": usage,
        "error": "; ".join(dict.fromkeys(item for item in errors if item)),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_bytes": len(prompt.encode("utf-8")),
        "tools_observed": list(tools_observed),
        "thread_id": thread_id,
        "provider_event_audit": audit,
    }


def _append_error(current: str, addition: str) -> str:
    return "; ".join(item for item in (current, addition) if item)
