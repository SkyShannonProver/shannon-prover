"""Manager-owned read-only certification of internal action candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from core.easycrypt.session.session_goal_authority import has_authoritative_open_goal
from core.easycrypt.proof_state_compiler.contracts import (
    CandidateSurface,
    CertificationRequest,
    CertificationResult,
    freeze_json_object,
    frozen_json_sha256,
)


EXACT_TACTIC_PREFLIGHT = "exact_tactic_preflight"


class CertificationRuntime(Protocol):
    def certify_exact_tactic(
        self, tactic: str, *, timeout: int = 30
    ) -> dict[str, Any]: ...


class CertificationPolicy(Protocol):
    def __call__(
        self,
        request: CertificationRequest,
        runtime: CertificationRuntime,
    ) -> CertificationResult | None: ...


@dataclass(frozen=True)
class CertificationGateway:
    """Dispatch declared policies without knowing any feature ID."""

    policies: tuple[tuple[str, CertificationPolicy], ...] = ()

    @classmethod
    def default(cls) -> "CertificationGateway":
        return cls(policies=((EXACT_TACTIC_PREFLIGHT, certify_exact_tactic),))

    def certify(
        self,
        surface: CandidateSurface,
        runtime: CertificationRuntime,
        *,
        eligible_feature_ids: tuple[str, ...],
    ) -> tuple[CertificationResult, ...]:
        handlers = dict(self.policies)
        if len(handlers) != len(self.policies):
            raise ValueError("certification gateway contains duplicate policy IDs")
        results = []
        for candidate in surface.actions:
            if candidate.feature_id not in eligible_feature_ids:
                continue
            handler = handlers.get(candidate.certification_policy)
            if handler is None:
                continue
            request = CertificationRequest(
                candidate_id=candidate.candidate_id,
                state_ref=surface.state_ref,
                policy=candidate.certification_policy,
                intent=candidate.intent,
                payload=candidate.payload,
            )
            result = handler(request, runtime)
            if result is not None:
                results.append(result)
        return tuple(results)


def certify_exact_tactic(
    request: CertificationRequest,
    runtime: CertificationRuntime,
) -> CertificationResult | None:
    """Check an exact commit payload on the unchanged current state."""

    if request.intent != "commit_tactic":
        return None
    tactic = request.payload.to_dict().get("tactic")
    if not isinstance(tactic, str) or not tactic.strip():
        return None
    runtime_result = runtime.certify_exact_tactic(tactic.strip())
    authority = runtime_result.get("authority")
    if not isinstance(authority, dict):
        return None
    event_id = str(authority.get("event_id") or "")
    artifact_hash = str(authority.get("artifact_hash") or "")
    hash_algorithm = str(authority.get("hash_algorithm") or "")
    expected_hash_length = {"sha1": 40, "sha256": 64}.get(hash_algorithm)
    if (
        authority.get("event_type") != "tactic.preflight.produced"
        or not event_id
        or expected_hash_length is None
        or len(artifact_hash) != expected_hash_length
        or any(char not in "0123456789abcdef" for char in artifact_hash)
    ):
        return None
    outcome = exact_tactic_outcome(runtime_result.get("action"), tactic.strip())
    action = runtime_result.get("action")
    action = action if isinstance(action, dict) else {}
    observation = action.get("agent_observation")
    observation = observation if isinstance(observation, dict) else {}
    content = observation.get("content")
    content = content if isinstance(content, dict) else {}
    proof_state = content.get("proof_state")
    proof_state = proof_state if isinstance(proof_state, dict) else {}
    goal = proof_state.get("goal")
    goal = goal if isinstance(goal, dict) else {}
    preflight_goal_identity = str(goal.get("active_goal_hash") or "")
    source_goal_open = has_authoritative_open_goal(proof_state)
    same_goal = (
        request.state_ref.goal_identity_required
        and preflight_goal_identity == request.state_ref.goal_identity
        and source_goal_open
    )
    unchanged = bool(runtime_result.get("history_unchanged")) and (
        runtime_result.get("state_version_before")
        == runtime_result.get("state_version_after")
        == request.state_ref.state_version
    )
    accepted = bool(
        outcome["accepted"]
        and outcome["outcome_known"]
        and unchanged
        and same_goal
    )
    return CertificationResult(
        candidate_id=request.candidate_id,
        state_ref=request.state_ref,
        policy=request.policy,
        intent=request.intent,
        payload_sha256=frozen_json_sha256(request.payload),
        accepted=accepted,
        verification_ref=(
            f"tactic.preflight.produced:{event_id}@{hash_algorithm}:{artifact_hash}"
        ),
        checked_effect=freeze_json_object({
            **outcome,
            "history_unchanged": bool(runtime_result.get("history_unchanged")),
            "source_goal_authoritatively_open": source_goal_open,
            "goal_identity_matches": same_goal,
            "error_summary": str(observation.get("error_summary") or "")[:1200],
            "contract_error": str(runtime_result.get("contract_error") or "")[:1200],
        }),
    )


def exact_tactic_outcome(action: object, tactic: str) -> dict[str, Any]:
    """Read only the bound exact-submit evidence from a preflight artifact."""

    action = action if isinstance(action, dict) else {}
    observation = action.get("agent_observation")
    content = observation.get("content") if isinstance(observation, dict) else None
    if isinstance(content, dict) and content.get("candidate") == tactic:
        evidence = content.get("runnable_evidence")
        if isinstance(evidence, dict):
            submit = evidence.get("exact_submit")
            payload = submit.get("payload") if isinstance(submit, dict) else None
            if not (
                isinstance(payload, dict)
                and submit.get("intent") == "commit_tactic"
                and payload.get("tactic") == tactic
                and evidence.get("validation_status")
                == "daemon_accepted_on_exact_state"
                and evidence.get("no_progress_status") == "progress"
            ):
                evidence = None
        if isinstance(evidence, dict):
            preview = evidence.get("previewed_effect")
            preview = preview if isinstance(preview, dict) else {}
            closed_value = preview.get("goal_after_closed")
            remaining_value = preview.get("goal_after_remaining")
            closed = closed_value if type(closed_value) is bool else None
            remaining = (
                remaining_value
                if type(remaining_value) is int and remaining_value >= 0
                else None
            )
            known = (closed is True and remaining in {None, 0}) or (
                closed is False and remaining is not None
            )
            return {
                "accepted": True,
                "outcome_known": known,
                "goal_after_closed": closed,
                "goal_after_remaining": remaining,
            }
    return {
        "accepted": False,
        "outcome_known": False,
        "goal_after_closed": None,
        "goal_after_remaining": None,
    }
