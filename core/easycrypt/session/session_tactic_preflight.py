"""Event-bound artifact for one exact, non-mutating EasyCrypt tactic check.

This is private compiler certification evidence. It is deliberately not a
generic lookup view, recommendation carrier, or agent-facing inspect surface.
One ``-try`` invocation records one exact tactic, EasyCrypt's verdict, and the
checked residual-goal summary.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.easycrypt.action_evidence_vocabulary import (
    ACTION_EVIDENCE_SCHEMA_VERSION,
)
from core.easycrypt.session.session_artifact_io import (
    read_bound_current_json_artifact_event,
    write_confined_text_artifact,
)
from core.easycrypt.session.session_events import record_authoritative_artifact_event
from core.easycrypt.session.session_goal_authority import (
    authoritative_open_goal_errors,
)
from core.easycrypt.validation_result import ValidationResult


TACTIC_PREFLIGHT_SCHEMA_VERSION = 1
TACTIC_PREFLIGHT_KIND = "exact_tactic_preflight"
TACTIC_PREFLIGHT_EVENT_TYPE = "tactic.preflight.produced"
TACTIC_PREFLIGHT_ARTIFACT_SUBDIR = "tactic_preflights"


class TacticPreflightValidation(ValidationResult):
    """Validation result for the exact tactic-preflight artifact."""


@dataclass(frozen=True)
class BoundTacticPreflightArtifact:
    data: dict[str, Any] | None = None
    artifact: Path | None = None
    artifact_hash: str = ""
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.data is not None and not self.errors


def accepted_runnable_preflight_evidence(
    *,
    tactic: str,
    goal_after_closed: bool,
    goal_after_remaining: int | None,
) -> dict[str, Any]:
    """Return the bounded evidence consumed by compiler certification."""

    return {
        "schema_version": ACTION_EVIDENCE_SCHEMA_VERSION,
        "lifecycle": "ready_for_preflight",
        "action_type": "runnable_tactic",
        "exact_submit": {
            "intent": "commit_tactic",
            "payload": {"tactic": tactic},
        },
        "binding_status": "complete",
        "resolved_bindings": {},
        "prerequisites": [{
            "name": "preflight source goal is authoritatively open",
            "disposition": "satisfied",
        }],
        "validation_status": "daemon_accepted_on_exact_state",
        "no_progress_status": "progress",
        "effect_kind": "proof_state_transition",
        "previewed_effect": {
            "goal_after_closed": goal_after_closed,
            "goal_after_remaining": goal_after_remaining,
        },
        "residual_obligations": [{
            "kind": "closed" if goal_after_closed else "proof_obligations",
            "summary": (
                "all goals close under the checked tactic"
                if goal_after_closed
                else f"{goal_after_remaining} checked subgoal(s) remain"
            ),
        }],
        "unresolved_dependencies": [],
        "strategic_non_guarantee": (
            "Exact tactic acceptance establishes executability on this state; "
            "it does not establish that the continuation is strategically useful."
        ),
        "source_refs": ["exact_tactic_preflight.proof_state"],
        "evidence_refs": ["exact_tactic_preflight.verdict"],
    }


def build_tactic_preflight_artifact(
    *,
    proof_state: dict[str, Any],
    result: dict[str, Any],
    raw_report: str = "",
) -> dict[str, Any]:
    """Build the sole current artifact shape from a parsed ``-try`` result."""

    tactic = str(result.get("tactic") or "").strip()
    accepted_value = result.get("accepted")
    accepted = accepted_value if type(accepted_value) is bool else None
    no_progress = bool(result.get("no_progress_predicted"))
    closed_value = result.get("goal_after_closed")
    closed = closed_value if type(closed_value) is bool else None
    remaining_value = result.get("goal_after_remaining")
    remaining = (
        remaining_value
        if type(remaining_value) is int and remaining_value >= 0
        else None
    )
    outcome_known = bool(
        accepted is True
        and not no_progress
        and (
            (closed is True and remaining in {None, 0})
            or (closed is False and remaining is not None)
        )
    )
    runnable_evidence = (
        accepted_runnable_preflight_evidence(
            tactic=tactic,
            goal_after_closed=bool(closed),
            goal_after_remaining=remaining,
        )
        if outcome_known
        else {}
    )
    data = {
        "schema_version": TACTIC_PREFLIGHT_SCHEMA_VERSION,
        "kind": TACTIC_PREFLIGHT_KIND,
        "ok": not bool(result.get("tool_error")),
        "tactic": tactic,
        "proof_state": dict(proof_state),
        "accepted": accepted,
        "no_progress_predicted": no_progress,
        "goal_after_closed": closed,
        "goal_after_remaining": remaining,
        "outcome_known": outcome_known,
        "error_kind": str(result.get("error_kind") or ""),
        "tool_error": bool(result.get("tool_error")),
        "runnable_evidence": runnable_evidence,
        "raw_report_sha256": hashlib.sha256(
            str(raw_report).encode("utf-8", errors="replace")
        ).hexdigest(),
    }
    validation = validate_tactic_preflight_artifact(data)
    if validation.errors:
        raise ValueError("invalid tactic preflight: " + "; ".join(validation.errors))
    return data


def validate_tactic_preflight_artifact(
    data: dict[str, Any],
) -> TacticPreflightValidation:
    errors: list[str] = []
    required_types = {
        "schema_version": int,
        "kind": str,
        "ok": bool,
        "tactic": str,
        "proof_state": dict,
        "no_progress_predicted": bool,
        "outcome_known": bool,
        "error_kind": str,
        "tool_error": bool,
        "runnable_evidence": dict,
        "raw_report_sha256": str,
    }
    allowed = set(required_types) | {"accepted", "goal_after_closed", "goal_after_remaining"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        errors.append("unknown field(s): " + ", ".join(unknown))
    for key, expected_type in required_types.items():
        value = data.get(key)
        if type(value) is not expected_type:
            errors.append(f"{key} must be {expected_type.__name__}")
    if data.get("schema_version") != TACTIC_PREFLIGHT_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {TACTIC_PREFLIGHT_SCHEMA_VERSION}"
        )
    if data.get("kind") != TACTIC_PREFLIGHT_KIND:
        errors.append(f"kind must be {TACTIC_PREFLIGHT_KIND!r}")
    if not str(data.get("tactic") or "").strip():
        errors.append("tactic must be non-empty")
    for key in ("accepted", "goal_after_closed"):
        if data.get(key) is not None and type(data.get(key)) is not bool:
            errors.append(f"{key} must be bool or null")
    remaining = data.get("goal_after_remaining")
    if remaining is not None and (
        type(remaining) is not int or remaining < 0
    ):
        errors.append("goal_after_remaining must be a non-negative int or null")
    digest = data.get("raw_report_sha256")
    if type(digest) is str and not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append("raw_report_sha256 must be a lowercase sha256 digest")
    outcome_known = data.get("outcome_known") is True
    evidence = data.get("runnable_evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    if outcome_known:
        if data.get("accepted") is not True or data.get("no_progress_predicted"):
            errors.append("outcome_known requires accepted progress")
        submit = evidence.get("exact_submit")
        payload = submit.get("payload") if isinstance(submit, dict) else None
        if not (
            isinstance(payload, dict)
            and submit.get("intent") == "commit_tactic"
            and payload.get("tactic") == data.get("tactic")
            and evidence.get("validation_status")
            == "daemon_accepted_on_exact_state"
            and evidence.get("no_progress_status") == "progress"
        ):
            errors.append("runnable_evidence does not bind the exact accepted tactic")
    elif evidence:
        errors.append("unknown/rejected preflight cannot carry runnable_evidence")
    if data.get("tool_error") is True and data.get("ok") is True:
        errors.append("tool_error contradicts ok=true")
    proof_state = data.get("proof_state")
    proof_state = proof_state if isinstance(proof_state, dict) else {}
    if outcome_known:
        source_errors = authoritative_open_goal_errors(proof_state)
        if source_errors:
            errors.append(
                "runnable preflight requires an authoritatively open source goal: "
                + "; ".join(source_errors)
            )
    return TacticPreflightValidation(errors=errors)


def canonical_tactic_preflight_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def tactic_preflight_event_payload_fields(
    data: dict[str, Any],
    *,
    artifact: str,
    artifact_hash: str,
) -> dict[str, Any]:
    validation = validate_tactic_preflight_artifact(data)
    return {
        "schema_version": int(data.get("schema_version") or 0),
        "kind": str(data.get("kind") or ""),
        "ok": bool(data.get("ok")) and validation.ok,
        "artifact": artifact,
        "artifact_hash": artifact_hash,
        "proof_status": str(
            data.get("proof_state", {}).get("status")
            if isinstance(data.get("proof_state"), dict)
            else ""
        ),
        "tactic_sha256": hashlib.sha256(
            str(data.get("tactic") or "").encode("utf-8")
        ).hexdigest(),
        "accepted": data.get("accepted") is True,
        "verdict_known": type(data.get("accepted")) is bool,
        "outcome_known": data.get("outcome_known") is True,
        "error_count": len(validation.errors),
    }


def write_tactic_preflight_artifact(
    session_dir: str | Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_tactic_preflight_artifact(data)
    if validation.errors:
        raise ValueError("invalid tactic preflight: " + "; ".join(validation.errors))
    text = canonical_tactic_preflight_text(data)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    artifact = write_confined_text_artifact(
        session_dir,
        subdir=TACTIC_PREFLIGHT_ARTIFACT_SUBDIR,
        filename=f"preflight_{digest[:16]}.json",
        text=text + "\n",
    )
    return tactic_preflight_event_payload_fields(
        data,
        artifact=str(artifact),
        artifact_hash=digest,
    )


def record_tactic_preflight_artifact(
    session_or_dir: Any,
    data: dict[str, Any],
    *,
    source: str = "session_cli",
) -> dict[str, Any]:
    session_dir = getattr(session_or_dir, "dir", session_or_dir)
    return record_authoritative_artifact_event(
        session_or_dir,
        TACTIC_PREFLIGHT_EVENT_TYPE,
        lambda: write_tactic_preflight_artifact(session_dir, data),
        source=source,
    )


def validate_tactic_preflight_event_binding(
    data: dict[str, Any],
    payload: dict[str, Any],
    artifact_hash: str,
    *,
    expected_tactic: str | None = None,
) -> TacticPreflightValidation:
    validation = validate_tactic_preflight_artifact(data)
    errors = list(validation.errors)
    expected = tactic_preflight_event_payload_fields(
        data,
        artifact=str(payload.get("artifact") or ""),
        artifact_hash=artifact_hash,
    )
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            errors.append(
                f"{TACTIC_PREFLIGHT_EVENT_TYPE} {key} mismatch: "
                f"expected {expected_value!r}, got {payload.get(key)!r}"
            )
    if expected_tactic is not None and data.get("tactic") != expected_tactic:
        errors.append(
            "preflight tactic does not match current backend request: "
            f"expected {expected_tactic!r}, got {data.get('tactic')!r}"
        )
    return TacticPreflightValidation(errors=errors)


def read_bound_tactic_preflight_event(
    session_dir: str | Path,
    event: dict[str, Any],
    *,
    expected_tactic: str | None = None,
) -> BoundTacticPreflightArtifact:
    bound = read_bound_current_json_artifact_event(
        session_dir,
        event,
        event_type=TACTIC_PREFLIGHT_EVENT_TYPE,
        subdir=TACTIC_PREFLIGHT_ARTIFACT_SUBDIR,
        validate_binding=lambda data, payload, digest: (
            list(validate_tactic_preflight_event_binding(
                data,
                payload,
                digest,
                expected_tactic=expected_tactic,
            ).errors),
            [],
        ),
    )
    return BoundTacticPreflightArtifact(
        data=bound.data,
        artifact=bound.path,
        artifact_hash=bound.artifact_hash,
        errors=bound.errors,
        warnings=bound.warnings,
    )
