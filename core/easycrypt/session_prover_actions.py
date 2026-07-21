"""Unified prover-facing action projection.

ToolView recommendations explain what one producer thinks. ProofContextView
uses this module to compile those recommendations plus canonical proof state
into concrete actions that ProverWorkspaceView can present to the prover.

The important distinction is epistemic:

* ``strategy`` actions are non-executable candidates or require instantiation.
* ``commit`` actions are EasyCrypt-verified tactics for ``-next`` / ``-chain``.
* ``strategy`` actions require reasoning or instantiation before execution.
* ``inspect`` / ``diagnose`` / ``verify`` actions call tools instead of tactics.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.easycrypt.session_placeholders import requires_placeholder_instantiation
from core.easycrypt.value_shapes import as_dict as _dict


PROVER_ACTION_SCHEMA_VERSION = 1
PROVER_ACTION_CATEGORIES = (
    "commit",
    "inspect",
    "diagnose",
    "verify",
    "strategy",
    "avoid",
    "none",
)


@dataclass(frozen=True)
class ProverActionValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def build_prover_actions(
    *,
    session_dir: str | Path | None = None,
    proof_state: dict[str, Any] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    safe_next_actions: list[dict[str, Any]] | None = None,
    latest_errors: list[dict[str, Any]] | None = None,
    command_ok: bool = True,
    max_actions: int = 6,
) -> list[dict[str, Any]]:
    """Return the canonical ordered action list for the current prover view."""
    state = _dict(proof_state)
    status = str(state.get("status") or "")
    goal = _dict(state.get("goal"))
    goal_hash = str(goal.get("active_goal_hash") or "")
    session_lemma = str(state.get("lemma") or _session_lemma(session_dir) or "")
    actions: list[dict[str, Any]] = []

    if status == "verified":
        return [_state_action(
            "proof.verified",
            category="none",
            title="No action needed",
            why="The proof-state projection is already verified.",
        )]
    if status == "candidate_closed":
        return [_tool_action(
            "proof.verify",
            category="verify",
            tool="verify",
            session_dir=session_dir,
            why="The proof candidate is closed; run verification next.",
            goal_hash=goal_hash,
            metadata={"verify_lemma": session_lemma} if session_lemma else {},
        )]

    event_contract = _dict(state.get("event_contract"))
    if not event_contract.get("ok", True):
        actions.append(_tool_action(
            "inspect.event_contract",
            category="inspect",
            tool="status",
            session_dir=session_dir,
            why="The event contract has errors; inspect status before acting.",
            goal_hash=goal_hash,
        ))

    transition = _dict(state.get("latest_transition"))
    no_progress_only = (
        bool(transition.get("no_progress"))
        or str(transition.get("kind") or "") == "no_progress"
        or str(transition.get("status") or "") == "no_progress_reverted"
    )
    has_positive_guidance = bool(recommendations or safe_next_actions)
    actionable_latest_errors = [
        err for err in (latest_errors or [])
        if str(_dict(err).get("temporal_scope") or "current_attempt")
        != "prior_attempt"
    ]
    status_error_is_historical = (
        status == "error"
        and bool(latest_errors)
        and not actionable_latest_errors
    )
    if (
        actionable_latest_errors
        or (status == "error" and not status_error_is_historical)
        or (not command_ok and not (no_progress_only and has_positive_guidance))
    ):
        failed = ""
        if actionable_latest_errors:
            failed = str(_dict(actionable_latest_errors[0]).get("tactic") or "")
        actions.append(_tool_action(
            "inspect.latest_error",
            category="diagnose",
            tool="diagnose",
            session_dir=session_dir,
            why="The latest transition recorded an error.",
            goal_hash=goal_hash,
            metadata={"failed_tactic": failed} if failed else {},
        ))

    for rec in recommendations or []:
        action = _action_from_recommendation(
            rec,
            session_dir=session_dir,
            goal_hash=goal_hash,
        )
        if action:
            actions.append(action)

    for item in safe_next_actions or []:
        action = _action_from_safe_next_action(
            item,
            session_dir=session_dir,
            goal_hash=goal_hash,
        )
        if action:
            actions.append(action)

    actions = _dedupe_actions(actions)
    return _select_diverse_actions(actions, max_actions=max_actions)


def prover_contract_for_recommendation(rec: dict[str, Any]) -> dict[str, str]:
    """Explain how a prover should treat a recommendation.

    This is intentionally user/prover-facing rather than proof-theoretic
    metadata.  It separates compiler analysis, daemon-verified actions, and
    read-only context so a tactic-shaped string is not mistaken for an order.
    """
    if not isinstance(rec, dict):
        return _prover_contract(
            role="context",
            meaning="This item is structured context.",
            not_meaning="It is not a tactic to commit directly.",
            expected_use="Use it only after checking the current goal.",
        )
    action_type = str(rec.get("action_type") or _dict(rec.get("metadata")).get("action_type") or "")
    metadata = _dict(rec.get("metadata"))
    epistemic = _epistemic_status(rec, default="")
    family = str(metadata.get("proof_ir_tactic_family") or "")
    producer = str(rec.get("producer") or rec.get("source") or "guidance")
    confidence = str(rec.get("confidence") or "")
    verified = (
        confidence == "verified"
        or epistemic in {
            "easycrypt_preflight_accepted",
            "daemon_chain_accepted",
            "easycrypt_verified",
            "verified_by_easycrypt",
        }
    )
    if verified and action_type in {"runnable_tactic", "inspection_action"}:
        return _prover_contract(
            role="verified_commit_candidate",
            meaning=(
                f"{producer} reports that EasyCrypt accepted this action on "
                "the current goal."
            ),
            not_meaning=(
                "It is not already committed to the proof history unless the "
                "view says the state changed."
            ),
            expected_use=(
                "Commit it if it matches your proof plan; otherwise inspect "
                "nearby alternatives before mutating the proof state."
            ),
        )
    if action_type == "tactic_candidate":
        if family == "pr_path_plan":
            meaning = (
                "ProofIR generated this as a typed Pr-path candidate from current "
                "endpoints, live handles, and local adapter structure."
            )
        else:
            meaning = (
                f"{producer} generated this as an unverified tactic candidate for "
                "the current goal."
            )
        return _prover_contract(
            role="tactic_candidate",
            meaning=meaning,
            not_meaning=(
                "It is not a proof obligation, not a forced next step, and "
                "not a runnable action until EasyCrypt validates it."
            ),
            expected_use=(
                "Use it as mechanical context. Submit a commit only when it "
                "matches your proof plan; the manager will report EasyCrypt's result."
            ),
            failure_interpretation=(
                "An EasyCrypt rejection is evidence about this candidate/form, not "
                "a reason to distrust the whole proof state."
            ),
        )
    if action_type == "inspection_action":
        return _prover_contract(
            role="inspection_reference",
            meaning=(
                f"{producer} is asking for read-only information such as a "
                "signature, declaration, or diagnostic."
            ),
            not_meaning="It is not a tactic and does not change the proof state.",
            expected_use=(
                "Run the inspection when the missing name/type information is "
                "blocking a concrete tactic choice."
            ),
        )
    if action_type == "avoid_action":
        return _prover_contract(
            role="avoid_warning",
            meaning=(
                "The compiler view believes this action would lose resources "
                "or violate the current proof phase."
            ),
            not_meaning="It is not forbidden by EasyCrypt.",
            expected_use=(
                "Prefer the positive alternatives first; retry only with a "
                "specific reason."
            ),
        )
    return _prover_contract(
        role="strategy_context",
        meaning=(
            f"{producer} is providing reasoning context or a tactic shape that "
            "still needs judgment or instantiation."
        ),
        not_meaning="It is not directly runnable as-is.",
        expected_use=(
            "Use it to choose among actions, fill missing arguments, or decide "
            "which inspection or candidate validation should come next."
        ),
    )


def _prover_contract(
    *,
    role: str,
    meaning: str,
    not_meaning: str,
    expected_use: str,
    failure_interpretation: str = "",
) -> dict[str, str]:
    contract = {
        "role": role,
        "meaning": meaning,
        "not_meaning": not_meaning,
        "expected_use": expected_use,
        "choice_space": (
            "This item is one ranked option; compare it with neighboring "
            "actions and the current goal before acting."
        ),
    }
    if failure_interpretation:
        contract["failure_interpretation"] = failure_interpretation
    return contract


def primary_action_from_actions(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return "inspect"
    category = str(_dict(actions[0]).get("category") or "")
    if category == "none":
        return "none"
    if category == "verify":
        return "verify"
    if category == "diagnose":
        return "diagnose"
    if category == "commit":
        return "try_tactic"
    if category == "strategy":
        return "consider_strategy_hint"
    if category == "inspect":
        return "inspect"
    if category == "avoid":
        return "avoid"
    return "inspect"


def validate_prover_actions(actions: Any, *, label: str = "actions") -> ProverActionValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(actions, list):
        return ProverActionValidation(errors=[f"{label} must be a list"])
    for idx, action in enumerate(actions):
        prefix = f"{label}[{idx}]"
        if not isinstance(action, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ("id", "category", "title", "why"):
            if not isinstance(action.get(key), str) or not str(action.get(key)).strip():
                errors.append(f"{prefix}.{key} must be a non-empty string")
        category = str(action.get("category") or "")
        if category and category not in PROVER_ACTION_CATEGORIES:
            errors.append(
                f"{prefix}.category must be one of "
                f"{', '.join(PROVER_ACTION_CATEGORIES)}"
            )
        if "state_changed" in action and not isinstance(action["state_changed"], bool):
            errors.append(f"{prefix}.state_changed must be a bool")
        if category == "commit" and not str(action.get("tactic") or "").strip():
            errors.append(f"{prefix}.{category} action must include a tactic")
        if category in {"inspect", "diagnose", "verify"} and not str(action.get("tool") or "").strip():
            errors.append(f"{prefix}.{category} action must include a tool")
        cost = str(action.get("cost") or "")
        if cost and cost not in {"free", "cheap", "moderate", "expensive", "unknown"}:
            warnings.append(f"{prefix}.cost has unusual value {cost!r}")
    return ProverActionValidation(errors=errors, warnings=warnings)


def _action_from_recommendation(
    rec: dict[str, Any],
    *,
    session_dir: str | Path | None,
    goal_hash: str,
) -> dict[str, Any] | None:
    if not isinstance(rec, dict):
        return None
    tactic_or_command = str(rec.get("action") or "").strip()
    if not tactic_or_command:
        return None
    metadata = _dict(rec.get("metadata"))
    action_type = str(rec.get("action_type") or metadata.get("action_type") or "")
    category = str(rec.get("category") or "")
    requires_instantiation = bool(
        rec.get("requires_instantiation")
        or metadata.get("requires_instantiation")
        or _requires_instantiation(tactic_or_command)
    )

    if (
        _looks_like_chain_command(tactic_or_command)
        and _is_verified_commit_recommendation(rec)
        and not requires_instantiation
    ):
        return _chain_action(
            f"{_safe_id(str(rec.get('id') or 'recommendation'))}.commit",
            command=tactic_or_command,
            session_dir=session_dir,
            rec=rec,
            goal_hash=goal_hash,
        )

    if action_type == "tactic_candidate":
        if requires_instantiation:
            return _recommendation_action(
                f"{_safe_id(str(rec.get('id') or 'recommendation'))}.strategy",
                category="strategy",
                title="Instantiate tactic candidate",
                rec=rec,
                goal_hash=goal_hash,
                requires_instantiation=True,
            )
        return _recommendation_action(
            f"{_safe_id(str(rec.get('id') or 'recommendation'))}.candidate",
            category="strategy",
            title="Unverified tactic candidate",
            rec=rec,
            goal_hash=goal_hash,
            requires_instantiation=False,
        )
    if action_type == "avoid_action" or category == "warning":
        return _recommendation_action(
            f"{_safe_id(str(rec.get('id') or 'recommendation'))}.avoid",
            category="avoid",
            title="Avoid action",
            rec=rec,
            goal_hash=goal_hash,
            requires_instantiation=requires_instantiation,
        )
    if (
        action_type == "strategy_hint"
        or category == "strategy_hint"
        or requires_instantiation
    ):
        return _recommendation_action(
            f"{_safe_id(str(rec.get('id') or 'recommendation'))}.strategy",
            category="strategy",
            title="Reason about strategy hint",
            rec=rec,
            goal_hash=goal_hash,
            requires_instantiation=requires_instantiation,
        )
    if action_type == "inspection_action" or _looks_like_cli_command(tactic_or_command):
        return _inspection_recommendation_action(
            f"{_safe_id(str(rec.get('id') or 'recommendation'))}.inspect",
            rec=rec,
            session_dir=session_dir,
            goal_hash=goal_hash,
            requires_instantiation=requires_instantiation,
        )
    if action_type == "runnable_tactic" or category == "runnable_tactic" or _looks_like_tactic_kind(rec):
        if not _is_verified_commit_recommendation(rec):
            return _recommendation_action(
                f"{_safe_id(str(rec.get('id') or 'recommendation'))}.candidate",
                category="strategy",
                title="Unverified tactic candidate",
                rec=rec,
                goal_hash=goal_hash,
                requires_instantiation=requires_instantiation,
            )
        return _tactic_action(
            f"{_safe_id(str(rec.get('id') or 'recommendation'))}.commit",
            category="commit",
            tactic=tactic_or_command,
            session_dir=session_dir,
            rec=rec,
            goal_hash=goal_hash,
            requires_instantiation=requires_instantiation,
        )
    return _recommendation_action(
        f"{_safe_id(str(rec.get('id') or 'recommendation'))}.strategy",
        category="strategy",
        title="Reason about guidance",
        rec=rec,
        goal_hash=goal_hash,
        requires_instantiation=requires_instantiation,
    )


def _action_from_safe_next_action(
    item: dict[str, Any],
    *,
    session_dir: str | Path | None,
    goal_hash: str,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    kind = str(item.get("kind") or "")
    tool = str(item.get("tool") or "")
    why = str(item.get("why") or "Safe next action from ProofContextView.")
    action_id = str(item.get("id") or f"safe.{kind or tool or 'action'}")
    if kind == "none":
        return _state_action(action_id, category="none", title="No action needed", why=why)
    if kind == "verify" or tool == "verify":
        return _tool_action(action_id, category="verify", tool="verify", session_dir=session_dir, why=why, goal_hash=goal_hash)
    if kind == "diagnose" or tool == "diagnose":
        return _tool_action(action_id, category="diagnose", tool="diagnose", session_dir=session_dir, why=why, goal_hash=goal_hash)
    if kind == "inspect" or tool:
        return _tool_action(action_id, category="inspect", tool=tool or kind, session_dir=session_dir, why=why, goal_hash=goal_hash)
    if kind.startswith("consider_"):
        return None
    return None


def _tactic_action(
    action_id: str,
    *,
    category: str,
    tactic: str,
    session_dir: str | Path | None,
    rec: dict[str, Any],
    goal_hash: str,
    requires_instantiation: bool,
) -> dict[str, Any]:
    metadata = _dict(rec.get("metadata"))
    contract = _dict(rec.get("prover_contract")) or prover_contract_for_recommendation(rec)
    return {
        "schema_version": PROVER_ACTION_SCHEMA_VERSION,
        "id": action_id,
        "category": category,
        "title": "Commit runnable tactic",
        "tool": "next",
        "command": _tactic_command("next", tactic, session_dir=session_dir),
        "tactic": tactic,
        "state_changed": True,
        "cost": str(metadata.get("cost") or "moderate"),
        "epistemic_status": _epistemic_status(rec, default="easycrypt_verified"),
        "confidence": str(rec.get("confidence") or ""),
        "why": str(rec.get("why") or "Structured recommendation produced this tactic."),
        "source": str(rec.get("producer") or rec.get("source") or ""),
        "recommendation_id": str(rec.get("id") or ""),
        "goal_hash": goal_hash,
        "requires_instantiation": bool(requires_instantiation),
        "evidence_refs": _string_list(rec.get("evidence_refs")),
        "prover_contract": contract,
        "metadata": _public_metadata(metadata),
    }


def _inspection_recommendation_action(
    action_id: str,
    *,
    rec: dict[str, Any],
    session_dir: str | Path | None,
    goal_hash: str,
    requires_instantiation: bool,
) -> dict[str, Any]:
    command = str(rec.get("action") or "")
    tool = _tool_from_command(command)
    contract = _dict(rec.get("prover_contract")) or prover_contract_for_recommendation(rec)
    return {
        "schema_version": PROVER_ACTION_SCHEMA_VERSION,
        "id": action_id,
        "category": "inspect",
        "title": "Inspect with tool",
        "tool": tool,
        "command": _normalize_command(command, session_dir=session_dir),
        "state_changed": False,
        "cost": str(_dict(rec.get("metadata")).get("cost") or "cheap"),
        "epistemic_status": _epistemic_status(rec, default="inspection"),
        "confidence": str(rec.get("confidence") or ""),
        "why": str(rec.get("why") or "Structured recommendation requested inspection."),
        "source": str(rec.get("producer") or rec.get("source") or ""),
        "recommendation_id": str(rec.get("id") or ""),
        "goal_hash": goal_hash,
        "requires_instantiation": bool(requires_instantiation),
        "evidence_refs": _string_list(rec.get("evidence_refs")),
        "prover_contract": contract,
        "metadata": _public_metadata(_dict(rec.get("metadata"))),
    }


def _chain_action(
    action_id: str,
    *,
    command: str,
    session_dir: str | Path | None,
    rec: dict[str, Any],
    goal_hash: str,
) -> dict[str, Any]:
    metadata = _dict(rec.get("metadata"))
    contract = _dict(rec.get("prover_contract")) or prover_contract_for_recommendation(rec)
    return {
        "schema_version": PROVER_ACTION_SCHEMA_VERSION,
        "id": action_id,
        "category": "commit",
        "title": "Commit verified tactic chain",
        "tool": "chain",
        "command": _normalize_command(command, session_dir=session_dir),
        "tactic": _chain_body_from_command(command),
        "state_changed": True,
        "cost": str(metadata.get("cost") or "moderate"),
        "epistemic_status": _epistemic_status(
            rec,
            default="daemon_chain_accepted",
        ),
        "confidence": str(rec.get("confidence") or ""),
        "why": str(rec.get("why") or "A daemon-verified tactic chain is ready to commit."),
        "source": str(rec.get("producer") or rec.get("source") or ""),
        "recommendation_id": str(rec.get("id") or ""),
        "goal_hash": goal_hash,
        "requires_instantiation": False,
        "evidence_refs": _string_list(rec.get("evidence_refs")),
        "prover_contract": contract,
        "metadata": _public_metadata(metadata),
    }


def _recommendation_action(
    action_id: str,
    *,
    category: str,
    title: str,
    rec: dict[str, Any],
    goal_hash: str,
    requires_instantiation: bool,
) -> dict[str, Any]:
    metadata = _dict(rec.get("metadata"))
    contract = _dict(rec.get("prover_contract")) or prover_contract_for_recommendation(rec)
    return {
        "schema_version": PROVER_ACTION_SCHEMA_VERSION,
        "id": action_id,
        "category": category,
        "title": title,
        "command": str(rec.get("action") or ""),
        "state_changed": False,
        "cost": str(metadata.get("cost") or "free"),
        "epistemic_status": _epistemic_status(rec, default=category),
        "confidence": str(rec.get("confidence") or ""),
        "why": str(rec.get("why") or "Structured recommendation produced this guidance."),
        "source": str(rec.get("producer") or rec.get("source") or ""),
        "recommendation_id": str(rec.get("id") or ""),
        "goal_hash": goal_hash,
        "requires_instantiation": bool(requires_instantiation),
        "evidence_refs": _string_list(rec.get("evidence_refs")),
        "prover_contract": contract,
        "metadata": _public_metadata(metadata),
    }


def _tool_action(
    action_id: str,
    *,
    category: str,
    tool: str,
    session_dir: str | Path | None,
    why: str,
    goal_hash: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_tool = tool.strip().lstrip("-") or category
    metadata = metadata or {}
    command = _tool_command(normalized_tool, session_dir=session_dir)
    requires_instantiation = False
    if category == "verify":
        verify_lemma = str(metadata.get("verify_lemma") or "").strip()
        command = _verify_command(verify_lemma, session_dir=session_dir)
        requires_instantiation = not bool(verify_lemma)
    return {
        "schema_version": PROVER_ACTION_SCHEMA_VERSION,
        "id": action_id,
        "category": category,
        "title": {
            "diagnose": "Diagnose latest error",
            "verify": "Verify closed proof",
        }.get(category, "Inspect proof state"),
        "tool": normalized_tool,
        "command": command,
        "state_changed": False,
        "cost": "cheap",
        "epistemic_status": "authoritative_tool_call",
        "confidence": "high",
        "why": why,
        "goal_hash": goal_hash,
        "requires_instantiation": requires_instantiation,
        "evidence_refs": [],
        "metadata": _public_metadata(metadata),
    }


def _state_action(action_id: str, *, category: str, title: str, why: str) -> dict[str, Any]:
    return {
        "schema_version": PROVER_ACTION_SCHEMA_VERSION,
        "id": action_id,
        "category": category,
        "title": title,
        "command": "",
        "state_changed": False,
        "cost": "free",
        "epistemic_status": "proof_state_projection",
        "confidence": "verified",
        "why": why,
        "goal_hash": "",
        "requires_instantiation": False,
        "evidence_refs": [],
        "metadata": {},
    }


def _dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for action in actions:
        key = (
            str(action.get("category") or ""),
            str(action.get("tool") or ""),
            str(action.get("tactic") or ""),
            str(action.get("recommendation_id") or action.get("id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(action)
    return out


def _select_diverse_actions(
    actions: list[dict[str, Any]],
    *,
    max_actions: int,
) -> list[dict[str, Any]]:
    """Keep distinct proof routes visible when the action menu is capped."""
    if max_actions <= 0:
        return []
    if len(actions) <= max_actions:
        return list(actions)

    selected: list[dict[str, Any]] = []

    def add_matching(predicate, *, limit: int = 1) -> None:
        for action in actions:
            if len(selected) >= max_actions:
                return
            if action in selected or not predicate(action):
                continue
            selected.append(action)
            if sum(1 for item in selected if predicate(item)) >= limit:
                return

    add_matching(_is_procedure_frontier_context)
    add_matching(_is_verified_action)
    add_matching(_is_non_context_named_call)
    add_matching(_is_invariant_call_route)
    add_matching(_is_non_context_seq_or_alignment)
    add_matching(_is_non_context_instantiation_route)

    for action in actions:
        if len(selected) >= max_actions:
            break
        if action in selected or _is_auto_call_context(action):
            continue
        selected.append(action)

    for action in actions:
        if len(selected) >= max_actions:
            break
        if action not in selected:
            selected.append(action)
    return selected[:max_actions]


def _metadata_family(action: dict[str, Any]) -> str:
    return str(_dict(action.get("metadata")).get("proof_ir_tactic_family") or "")


def _is_auto_call_context(action: dict[str, Any]) -> bool:
    metadata = _dict(action.get("metadata"))
    return (
        str(action.get("source") or "") == "AUTO-CALL-SUGGEST"
        or str(metadata.get("source_name") or "") == "auto_call_suggest"
        or str(metadata.get("epistemic_status") or "") == "context_only_not_daemon_verified"
    )


def _is_procedure_frontier_context(action: dict[str, Any]) -> bool:
    metadata = _dict(action.get("metadata"))
    return (
        str(action.get("source") or "") == "ProofIR"
        and str(metadata.get("scheduler_role") or "") == "semantic_frontier_map"
    )


def _is_verified_action(action: dict[str, Any]) -> bool:
    confidence = str(action.get("confidence") or "")
    epistemic = str(action.get("epistemic_status") or "")
    return confidence == "verified" or epistemic.startswith("daemon_")


def _is_non_context_named_call(action: dict[str, Any]) -> bool:
    return (
        _metadata_family(action) == "call_named_equiv"
        and not _is_auto_call_context(action)
    )


def _is_invariant_call_route(action: dict[str, Any]) -> bool:
    return (
        _metadata_family(action) == "call_invariant_skeleton"
        or "call (_:" in str(action.get("command") or "")
    )


def _is_non_context_seq_or_alignment(action: dict[str, Any]) -> bool:
    command = str(action.get("command") or "")
    return (
        not _is_auto_call_context(action)
        and (
            command.strip().startswith("seq ")
            or " -c 'seq " in command
            or " -c \"seq " in command
            or "swap/seq" in command
        )
    )


def _is_non_context_instantiation_route(action: dict[str, Any]) -> bool:
    return (
        not _is_auto_call_context(action)
        and bool(action.get("requires_instantiation"))
    )


def _tactic_command(tool: str, tactic: str, *, session_dir: str | Path | None) -> str:
    flag = "-try" if tool == "try" else "-next"
    return (
        "python3 core/easycrypt/session_cli.py"
        + _session_part(session_dir)
        + f" {flag} -c {shlex.quote(tactic)}"
    )


def _tool_command(tool: str, *, session_dir: str | Path | None) -> str:
    return (
        "python3 core/easycrypt/session_cli.py"
        + _session_part(session_dir)
        + f" {_tool_flag(tool)}"
    )


def _verify_command(lemma: str, *, session_dir: str | Path | None) -> str:
    arg = lemma or "<lemma>"
    return (
        "python3 core/easycrypt/session_cli.py"
        + _session_part(session_dir)
        + f" -verify {shlex.quote(arg)}"
    )


def _normalize_command(command: str, *, session_dir: str | Path | None) -> str:
    stripped = command.strip()
    if "session_cli.py" in stripped:
        return stripped
    if stripped.startswith("-"):
        return "python3 core/easycrypt/session_cli.py" + _session_part(session_dir) + f" {stripped}"
    return stripped


def _session_part(session_dir: str | Path | None) -> str:
    if session_dir in (None, ""):
        return ""
    return f" -d {shlex.quote(str(session_dir))}"


def _session_lemma(session_dir: str | Path | None) -> str:
    if session_dir in (None, ""):
        return ""
    path = Path(session_dir) / "events.jsonl"
    if not path.exists():
        return ""
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = _json_loads_object(line)
                if event.get("type") != "session.started":
                    continue
                payload = _dict(event.get("payload"))
                lemma = str(payload.get("lemma") or "").strip()
                if lemma:
                    return lemma
    except Exception:
        return ""
    return ""


def _json_loads_object(text: str) -> dict[str, Any]:
    try:
        import json

        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _tool_flag(tool: str) -> str:
    stripped = tool.strip()
    if not stripped:
        return "-agent-view"
    if stripped.startswith("-"):
        return stripped
    return "-" + stripped


def _tool_from_command(command: str) -> str:
    stripped = command.strip()
    match = re.search(r"\s-(agent-view|episode-view|goal-info|diagnose|status|align|bridge-lemmas|suggest-close|lemma-hints|where|members|search|search-skeleton|tactic-forms|chain)\b", f" {stripped}")
    if match:
        return match.group(1)
    if stripped.startswith("-"):
        return stripped.split()[0].lstrip("-")
    return "inspection"


def _epistemic_status(rec: dict[str, Any], *, default: str) -> str:
    metadata = _dict(rec.get("metadata"))
    status = str(metadata.get("epistemic_status") or rec.get("epistemic_status") or "")
    return status or default


def _is_verified_commit_recommendation(rec: dict[str, Any]) -> bool:
    metadata = _dict(rec.get("metadata"))
    status = str(metadata.get("epistemic_status") or rec.get("epistemic_status") or "")
    confidence = str(rec.get("confidence") or "")
    return confidence == "verified" or status in {
        "easycrypt_preflight_accepted",
        "daemon_chain_accepted",
        "easycrypt_verified",
        "verified_by_easycrypt",
    }


def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
    return out


def _looks_like_tactic_kind(rec: dict[str, Any]) -> bool:
    return str(rec.get("kind") or "") in {
        "tactic_candidate",
        "pivot_tactic",
        "closing_tactic",
        "tactic_chain",
    }


def _looks_like_cli_command(action: str) -> bool:
    stripped = action.strip()
    return (
        stripped.startswith("-")
        or stripped.startswith("Run `-")
        or stripped.startswith("run `-")
        or "session_cli.py" in stripped
    )


def _looks_like_chain_command(action: str) -> bool:
    stripped = action.strip()
    return bool(re.search(r"(^|\s)-chain\b", stripped))


def _chain_body_from_command(command: str) -> str:
    stripped = command.strip()
    try:
        parts = shlex.split(stripped)
    except ValueError:
        parts = stripped.split()
    for idx, part in enumerate(parts):
        if part == "-c" and idx + 1 < len(parts):
            return parts[idx + 1]
    return stripped


def _requires_instantiation(action: str) -> bool:
    return requires_placeholder_instantiation(action)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "action"
