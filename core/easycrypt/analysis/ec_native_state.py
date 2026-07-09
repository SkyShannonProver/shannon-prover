"""Adapters for EC-native goal/program state artifacts.

This module is deliberately small: it only decides whether an observed session
artifact is authoritative EC state or a local fallback.  Compiler passes may
canonicalize and rank the facts afterwards, but they should not need to know
which JSON key a future EC wrapper used for typed goal/program data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.easycrypt.analysis.ec_utils import as_dict as _dict, as_list as _list


EC_NATIVE_AUTHORITY_RANK = 100
PRETTY_TEXT_AUTHORITY_RANK = 10

GOAL_FALLBACK_FACT_SOURCE = "pretty_goal_text"
PROGRAM_FALLBACK_FACT_SOURCE = "pretty_program_text"
FALLBACK_AUTHORITY = "pretty_text_fallback"

EC_NATIVE_GOAL_FACT_SOURCE = "ec_native_goal_state"
EC_NATIVE_PROGRAM_FACT_SOURCE = "ec_native_program_ast"
EC_NATIVE_AUTHORITY = "ec_native_ground_truth"

_NATIVE_GOAL_TOOLS = {
    "ec-goal-json",
    "ec_goal_json",
    "goal-json-native",
    "goal_json_native",
    "native-goal-state",
    "native_goal_state",
}
_NATIVE_PROGRAM_TOOLS = {
    "ec-program-json",
    "ec_program_json",
    "ec-program-goal-json",
    "ec_program_goal_json",
    "program-json-native",
    "program_json_native",
    "native-program-ast",
    "native_program_ast",
}

_GOAL_PAYLOAD_KEYS = (
    "goal_state",
    "goal_json",
    "goal",
    "parsed_goal",
)
_PROGRAM_PAYLOAD_KEYS = (
    "program_ast",
    "program_state",
    "program_goal_json",
    "program_goal",
    "program",
    "parsed_goal",
)
_PROGRAM_FIELD_KEYS = (
    "left_statements",
    "right_statements",
    "pre",
    "post",
    "call_equiv_candidates",
)


def annotate_goal_fallback(parsed_goal: dict[str, Any]) -> dict[str, Any]:
    """Mark a parsed goal as local pretty-text evidence when no EC fact exists."""
    out = dict(parsed_goal)
    out.setdefault("fact_source", GOAL_FALLBACK_FACT_SOURCE)
    out.setdefault("authority", FALLBACK_AUTHORITY)
    out.setdefault("authority_rank", PRETTY_TEXT_AUTHORITY_RANK)
    out.setdefault("ec_ground_truth", False)
    out.setdefault("native_artifact", "")
    return out


def annotate_program_fallback(parsed_goal: dict[str, Any]) -> dict[str, Any]:
    """Mark program fields as local pretty-text evidence when no EC AST exists."""
    out = dict(parsed_goal)
    out.setdefault("program_fact_source", PROGRAM_FALLBACK_FACT_SOURCE)
    out.setdefault("program_authority", FALLBACK_AUTHORITY)
    out.setdefault("program_authority_rank", PRETTY_TEXT_AUTHORITY_RANK)
    out.setdefault("program_ec_ground_truth", False)
    out.setdefault("program_native_artifact", "")
    return out


def goal_authority(parsed_goal: dict[str, Any]) -> dict[str, Any]:
    parsed = _dict(parsed_goal)
    return {
        "fact_source": str(
            parsed.get("fact_source") or GOAL_FALLBACK_FACT_SOURCE
        ),
        "authority": str(parsed.get("authority") or FALLBACK_AUTHORITY),
        "authority_rank": int(
            parsed.get("authority_rank") or PRETTY_TEXT_AUTHORITY_RANK
        ),
        "ec_ground_truth": bool(parsed.get("ec_ground_truth")),
        "native_artifact": str(parsed.get("native_artifact") or ""),
    }


def program_authority(parsed_goal: dict[str, Any]) -> dict[str, Any]:
    parsed = _dict(parsed_goal)
    return {
        "fact_source": str(
            parsed.get("program_fact_source") or PROGRAM_FALLBACK_FACT_SOURCE
        ),
        "authority": str(parsed.get("program_authority") or FALLBACK_AUTHORITY),
        "authority_rank": int(
            parsed.get("program_authority_rank")
            or PRETTY_TEXT_AUTHORITY_RANK
        ),
        "ec_ground_truth": bool(parsed.get("program_ec_ground_truth")),
        "native_artifact": str(parsed.get("program_native_artifact") or ""),
    }


def has_program_fields(payload: dict[str, Any] | None) -> bool:
    data = _dict(payload)
    return any(key in data for key in _PROGRAM_FIELD_KEYS)


def load_native_goal_fact(
    session_dir: str | Path | None,
    active_goal_hash: str = "",
) -> dict[str, Any]:
    """Return the newest matching EC-native goal artifact for this session."""
    return _load_native_fact(
        session_dir,
        active_goal_hash=active_goal_hash,
        native_tools=_NATIVE_GOAL_TOOLS,
        payload_keys=_GOAL_PAYLOAD_KEYS,
        fact_source=EC_NATIVE_GOAL_FACT_SOURCE,
    )


def load_native_program_fact(
    session_dir: str | Path | None,
    active_goal_hash: str = "",
) -> dict[str, Any]:
    """Return the newest matching EC-native program AST artifact."""
    return _load_native_fact(
        session_dir,
        active_goal_hash=active_goal_hash,
        native_tools=_NATIVE_PROGRAM_TOOLS,
        payload_keys=_PROGRAM_PAYLOAD_KEYS,
        fact_source=EC_NATIVE_PROGRAM_FACT_SOURCE,
        require_program_fields=True,
    )


def merge_native_goal_fact(
    parsed_goal: dict[str, Any],
    native_fact: dict[str, Any] | None,
) -> dict[str, Any]:
    """Overlay EC-native goal fields and mark them as ground truth."""
    out = dict(parsed_goal)
    native = _dict(native_fact)
    if not native:
        return annotate_goal_fallback(out)
    for key, value in native.items():
        if key in {
            "fact_source",
            "authority",
            "authority_rank",
            "ec_ground_truth",
            "native_artifact",
        }:
            continue
        if value not in (None, ""):
            out[key] = value
    out["fact_source"] = str(
        native.get("fact_source") or EC_NATIVE_GOAL_FACT_SOURCE
    )
    out["authority"] = EC_NATIVE_AUTHORITY
    out["authority_rank"] = EC_NATIVE_AUTHORITY_RANK
    out["ec_ground_truth"] = True
    out["native_artifact"] = str(native.get("native_artifact") or "")
    return out


def merge_native_program_fact(
    parsed_goal: dict[str, Any],
    native_fact: dict[str, Any] | None,
) -> dict[str, Any]:
    """Overlay EC-native program fields and mark statement facts authoritative."""
    out = dict(parsed_goal)
    native = _dict(native_fact)
    if not native:
        return annotate_program_fallback(out)
    for key in _PROGRAM_FIELD_KEYS:
        if key in native:
            out[key] = native[key]
    out["program_fact_source"] = str(
        native.get("fact_source") or EC_NATIVE_PROGRAM_FACT_SOURCE
    )
    out["program_authority"] = EC_NATIVE_AUTHORITY
    out["program_authority_rank"] = EC_NATIVE_AUTHORITY_RANK
    out["program_ec_ground_truth"] = True
    out["program_native_artifact"] = str(native.get("native_artifact") or "")
    return out


def native_remaining(parsed_goal: dict[str, Any]) -> tuple[int | None, bool]:
    """Return EC-native remaining-goal count if present."""
    parsed = _dict(parsed_goal)
    if not parsed.get("ec_ground_truth"):
        return None, False
    if parsed.get("num_remaining_determined") is False:
        return None, False
    if "num_remaining" not in parsed:
        return None, False
    try:
        return int(parsed.get("num_remaining")), True
    except Exception:
        return None, False


def _load_native_fact(
    session_dir: str | Path | None,
    *,
    active_goal_hash: str,
    native_tools: set[str],
    payload_keys: tuple[str, ...],
    fact_source: str,
    require_program_fields: bool = False,
) -> dict[str, Any]:
    if session_dir is None:
        return {}
    candidates: list[dict[str, Any]] = []
    for data, artifact in _tool_views(session_dir):
        tool = str(data.get("tool") or "").strip().lower()
        if tool not in native_tools:
            continue
        payload = _extract_payload(data, payload_keys)
        if not payload:
            continue
        if require_program_fields and not has_program_fields(payload):
            continue
        if active_goal_hash:
            seen_hash = _payload_goal_hash(payload, data)
            if seen_hash and seen_hash != active_goal_hash:
                continue
        item = dict(payload)
        item["fact_source"] = fact_source
        item["authority"] = EC_NATIVE_AUTHORITY
        item["authority_rank"] = EC_NATIVE_AUTHORITY_RANK
        item["ec_ground_truth"] = True
        item["native_artifact"] = artifact
        candidates.append(item)
    return candidates[-1] if candidates else {}


def _tool_views(session_dir: str | Path) -> list[tuple[dict[str, Any], str]]:
    root = Path(session_dir) / "tool_views"
    if not root.exists():
        return []
    out: list[tuple[dict[str, Any], str]] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            out.append((data, str(path)))
    return out


def _extract_payload(
    data: dict[str, Any],
    keys: tuple[str, ...],
) -> dict[str, Any]:
    for key in keys:
        payload = data.get(key)
        if isinstance(payload, dict):
            return dict(payload)
    for container_key in ("proof_state", "debug"):
        container = data.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in keys:
            payload = container.get(key)
            if isinstance(payload, dict):
                return dict(payload)
        goal = container.get("goal")
        if isinstance(goal, dict):
            return dict(goal)
    for bucket in _dict(data.get("evidence")).values():
        for item in _list(bucket):
            if not isinstance(item, dict):
                continue
            for key in keys:
                payload = item.get(key)
                if isinstance(payload, dict):
                    return dict(payload)
    return {}


def _payload_goal_hash(
    payload: dict[str, Any],
    envelope: dict[str, Any],
) -> str:
    for data in (payload, envelope):
        for key in ("active_goal_hash", "goal_hash", "source_goal_hash"):
            value = str(_dict(data).get(key) or "")
            if value:
                return value
    proof_goal = _dict(_dict(envelope.get("proof_state")).get("goal"))
    for key in ("active_goal_hash", "goal_hash", "source_goal_hash"):
        value = str(proof_goal.get(key) or "")
        if value:
            return value
    return ""
