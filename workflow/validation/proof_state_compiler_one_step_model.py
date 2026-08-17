"""Provider-normalized model boundary for one-step compiler micro A/Bs."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from workflow.codex_event_protocol import (
    codex_event_text,
    observe_codex_exec_jsonl,
)
from workflow.validation.proof_state_compiler_one_step_trial import TrialPacket


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"tactic": {"type": "string"}},
    "required": ["tactic"],
    "additionalProperties": False,
}
SYSTEM_PROMPT = (
    "You are selecting exactly one next EasyCrypt tactic for the current "
    "proof state. Do not solve later subgoals. Do not use tools or external "
    "context. Return one JSON object matching the required schema. The tactic "
    "must be directly submit-ready and end with a period."
)
CODEX_ONE_STEP_DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    # Disable the agent-facing Code Mode capability. ``code_mode_host`` is an
    # internal carrier, not a model tool: explicitly disabling that carrier
    # makes Codex emit a provider error even when Code Mode itself is off.
    "code_mode",
    "apps",
    "plugins",
    "browser_use",
    "computer_use",
    "image_generation",
    "multi_agent",
    "goals",
)


def agent_prompt(packet: TrialPacket) -> str:
    visible: dict[str, Any] = {
        "current_goal": {"lines": list(packet.current_goal_lines)},
    }
    if packet.manager_observation:
        visible["last_result"] = dict(packet.manager_observation)
    if packet.compiler_assist:
        visible["compiler_assist"] = list(packet.compiler_assist)
    return (
        "Choose the single next tactic for this packet:\n"
        + json.dumps(visible, ensure_ascii=False, separators=(",", ":"))
    )


def run_model(
    prompt: str,
    *,
    backend: str,
    model: str,
    effort: str,
    cwd: Path,
) -> dict[str, Any]:
    if backend == "openai":
        return _run_openai_codex(prompt, model=model, effort=effort, cwd=cwd)
    if backend == "claude":
        return _run_claude(prompt, model=model, effort=effort, cwd=cwd)
    raise ValueError(f"unsupported model backend: {backend}")


def _run_claude(
    prompt: str,
    *,
    model: str,
    effort: str,
    cwd: Path,
) -> dict[str, Any]:
    command = [
        shutil.which("claude") or "claude",
        "-p", prompt,
        "--model", model,
        "--effort", effort,
        "--system-prompt", SYSTEM_PROMPT,
        "--tools", "",
        "--strict-mcp-config",
        "--mcp-config", '{"mcpServers":{}}',
        "--disable-slash-commands",
        "--no-session-persistence",
        "--setting-sources", "user",
        "--permission-mode", "dontAsk",
        "--output-format", "json",
        "--json-schema", json.dumps(OUTPUT_SCHEMA, separators=(",", ":")),
    ]
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=300,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    outer: dict[str, Any] = {}
    error = ""
    try:
        decoded = json.loads(result.stdout)
        if isinstance(decoded, dict):
            outer = decoded
    except json.JSONDecodeError as exc:
        error = f"invalid claude JSON output: {exc}"
    structured: dict[str, Any] = {}
    raw_answer = outer.get("structured_output")
    if isinstance(raw_answer, dict):
        structured = raw_answer
    else:
        raw_result = outer.get("result")
        if isinstance(raw_result, str):
            try:
                parsed = json.loads(raw_result)
                if isinstance(parsed, dict):
                    structured = parsed
            except json.JSONDecodeError:
                error = error or "claude result did not match output schema"
    if result.returncode != 0:
        process_error = result.stderr.strip()[-1200:] or "claude call failed"
        error = f"{error}; {process_error}" if error else process_error
    usage = outer.get("usage") if isinstance(outer.get("usage"), dict) else {}
    return _model_result(
        tactic=structured.get("tactic"),
        returncode=result.returncode,
        duration_ms=duration_ms,
        usage=usage,
        total_cost_usd=outer.get("total_cost_usd"),
        error=error,
        prompt=prompt,
        tools_observed=(),
    )


def _run_openai_codex(
    prompt: str,
    *,
    model: str,
    effort: str,
    cwd: Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".compiler_one_step_openai_",
        dir=cwd,
    ) as isolated_dir:
        isolated = Path(isolated_dir)
        schema_path = isolated / "tactic_output.schema.json"
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
            *_disabled_feature_args(),
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
    return decode_codex_result(
        result.stdout,
        result.stderr,
        returncode=result.returncode,
        duration_ms=duration_ms,
        prompt=prompt,
    )


def _disabled_feature_args() -> list[str]:
    return [
        argument
        for feature in CODEX_ONE_STEP_DISABLED_FEATURES
        for argument in ("--disable", feature)
    ]


def decode_codex_result(
    stdout: str,
    stderr: str,
    *,
    returncode: int,
    duration_ms: int,
    prompt: str,
) -> dict[str, Any]:
    events, provider_event_audit = observe_codex_exec_jsonl(stdout, stderr)
    errors: list[str] = []
    errors.extend(
        f"invalid codex JSONL line {item['line']}: {item['error']}"
        for item in provider_event_audit["invalid_jsonl_lines"]
    )
    errors.extend(provider_event_audit["cardinality_errors"])
    errors.extend(
        "unknown codex protocol item: "
        f"event={item.get('event_type')!r}, item={item.get('item_type')!r}"
        for item in provider_event_audit["protocol_unknowns"]
    )
    for item in provider_event_audit["provider_errors"]:
        message = str(item.get("message") or "").strip()
        errors.append(
            "codex provider error: "
            + (message or "provider emitted an error event without text")
        )

    answer_text = ""
    usage: dict[str, Any] = {}
    for event in events:
        event_type = str(event.get("type") or "")
        item = event.get("item")
        if isinstance(item, dict):
            item_type = str(item.get("type") or "")
            if (
                event_type == "item.completed"
                and item_type == "agent_message"
            ):
                answer_text = codex_event_text(item)
        if event_type == "turn.completed" and isinstance(
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
    tools_observed = tuple(provider_event_audit["tool_item_types"])
    if tools_observed:
        errors.append(
            "codex used forbidden tools: "
            + ", ".join(tools_observed)
        )
    if returncode != 0:
        errors.append(stderr.strip()[-1200:] or "codex call failed")
    return _model_result(
        tactic=structured.get("tactic"),
        returncode=returncode,
        duration_ms=duration_ms,
        usage=usage,
        total_cost_usd=None,
        error="; ".join(dict.fromkeys(error for error in errors if error)),
        prompt=prompt,
        tools_observed=tools_observed,
        provider_event_audit=provider_event_audit,
    )


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for arm in ("control", "treatment"):
        rows = [row for row in runs if row["arm"] == arm]
        valid = [row for row in rows if row["valid_sample"]]
        summary[arm] = {
            "runs": len(rows),
            "valid_runs": len(valid),
            "accepted": sum(
                1 for row in valid if row["easycrypt_preflight_accepted"]
            ),
            "matched_compiler_action": sum(
                1 for row in valid if row["matches_compiler_action"]
            ),
            "input_tokens": sum(
                int(row["usage"].get("input_tokens") or 0) for row in valid
            ),
            "output_tokens": sum(
                int(row["usage"].get("output_tokens") or 0) for row in valid
            ),
            "reasoning_output_tokens": sum(
                int(row["usage"].get("reasoning_output_tokens") or 0)
                for row in valid
            ),
        }
    return summary


def git_identity(root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def _model_result(
    *,
    tactic: object,
    returncode: int,
    duration_ms: int,
    usage: dict[str, Any],
    total_cost_usd: object,
    error: str,
    prompt: str,
    tools_observed: tuple[str, ...],
    provider_event_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "tactic": tactic,
        "returncode": returncode,
        "duration_ms": duration_ms,
        "usage": usage,
        "total_cost_usd": total_cost_usd,
        "error": error,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_bytes": len(prompt.encode("utf-8")),
        "tools_observed": list(tools_observed),
    }
    if provider_event_audit is not None:
        result["provider_event_audit"] = provider_event_audit
    return result
