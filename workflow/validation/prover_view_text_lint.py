"""Static hygiene checks for prover-facing compiler text.

The structured view contract already checks shapes and action semantics.  This
module checks the next layer: wording that can steer an LLM prover in the wrong
direction even when the JSON is well formed.

The checks are intentionally small and deterministic.  They do not decide
whether a tactic is good; they only enforce that negative guidance is paired
with a reason and a forward route, and that internal analysis tags do not leak
into the prover-facing view.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable
from core.easycrypt.value_shapes import as_dict as _dict


@dataclass(frozen=True)
class TextLintIssue:
    severity: str
    code: str
    message: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


_INTERNAL_TAG_RE = re.compile(r"\bDISJOINT\b")
_NOT_CALLABLE_RE = re.compile(r"\bnot\s+callable\b", re.IGNORECASE)
_NEGATIVE_RE = re.compile(
    r"\b("
    r"avoid|wrong[- ]layer|wrong\s+layer|not\s+available|unavailable|"
    r"not\s+callable|"
    r"not\s+at\s+(?:the\s+)?frontier|not\s+frontier|"
    r"not\s+reachable|unreachable|no\s+progress|"
    r"cannot|can't|destroy|destroys|destroyed|kill|kills|killed|"
    r"erases?|erased"
    r")\b",
    re.IGNORECASE,
)
_REASON_RE = re.compile(
    r"\b("
    r"because|reason|cause|current|frontier|phase|layer|resource|"
    r"handle|live|after|before|until|when|if|while|would|since"
    r")\b",
    re.IGNORECASE,
)
_REPAIR_RE = re.compile(
    r"\b("
    r"try|use|run|inspect|undo|rerun|re-run|prefer|then|after|"
    r"before|expose|route|follow|choose|supply|resolve|check|repair|"
    r"alternative|candidate|continue|read"
    r")\b",
    re.IGNORECASE,
)


def lint_prover_facing_payload(
    payload: dict[str, Any],
    *,
    view_type: str,
) -> list[TextLintIssue]:
    """Return static text-hygiene issues for one structured prover view."""
    issues: list[TextLintIssue] = []
    issues.extend(_lint_internal_tag_leaks(payload))

    guidance = _dict(payload.get("guidance"))
    issues.extend(_lint_recommendations(
        _list(guidance.get("recommendations")),
        path="guidance.recommendations",
    ))
    issues.extend(_lint_recommendations(
        _list(guidance.get("stale_recommendations")),
        path="guidance.stale_recommendations",
        stale=True,
    ))
    issues.extend(_lint_recommendation_conflicts(
        _list(guidance.get("recommendations")),
        path="guidance.recommendations",
    ))

    proof_ir = _dict(payload.get("proof_ir"))
    if proof_ir:
        issues.extend(_lint_proof_ir(proof_ir))

    next_block = _dict(payload.get("next"))
    if next_block:
        issues.extend(_lint_recommendations(
            _list(next_block.get("recommendations")),
            path="next.recommendations",
        ))
        issues.extend(_lint_recommendation_conflicts(
            _list(next_block.get("recommendations")),
            path="next.recommendations",
        ))

    issues.extend(_lint_diagnostics(
        _list(payload.get("diagnostics")),
        path="diagnostics",
    ))
    issues.extend(_lint_diagnostics(
        _list(payload.get("errors")),
        path="errors",
        require_repair=False,
    ))
    issues.extend(_lint_diagnostics(
        _list(payload.get("notes")),
        path="notes",
        require_repair=False,
    ))

    # ToolViews often put diagnostics under guidance or debug-specific keys.
    if view_type == "tool_view":
        issues.extend(_lint_diagnostics(
            _list(guidance.get("diagnostics")),
            path="guidance.diagnostics",
        ))
    return issues



def _lint_internal_tag_leaks(payload: dict[str, Any]) -> list[TextLintIssue]:
    issues: list[TextLintIssue] = []
    for path, text in _iter_strings(payload):
        if _INTERNAL_TAG_RE.search(text):
            issues.append(TextLintIssue(
                "error",
                "internal_analysis_tag_leak",
                "Internal pivot tag `DISJOINT` leaked into prover-facing JSON.",
                path,
            ))
    return issues


def _lint_recommendations(
    recs: list[dict[str, Any]],
    *,
    path: str,
    stale: bool = False,
) -> list[TextLintIssue]:
    issues: list[TextLintIssue] = []
    for idx, rec in enumerate(recs):
        rec_path = f"{path}[{idx}]"
        action_type = _action_type(rec)
        text = _recommendation_text(rec)
        if _NOT_CALLABLE_RE.search(text):
            if not (_REASON_RE.search(text) and _REPAIR_RE.search(text)):
                issues.append(TextLintIssue(
                    "error",
                    "not_callable_without_reason_or_repair",
                    (
                        "`not callable` guidance must say why it is not "
                        "callable at this frontier and how to make progress."
                    ),
                    rec_path,
                ))
        if action_type == "avoid_action" or _negative_without_repair(text):
            if not _has_positive_route(rec):
                severity = "warning" if stale else "error"
                issues.append(TextLintIssue(
                    severity,
                    "negative_guidance_without_repair",
                    (
                        "Negative or avoid guidance must include a positive "
                        "next route such as use/run/inspect/undo."
                    ),
                    rec_path,
                ))
    return issues


def _lint_recommendation_conflicts(
    recs: list[dict[str, Any]],
    *,
    path: str,
) -> list[TextLintIssue]:
    by_action: dict[str, set[str]] = {}
    for rec in recs:
        action = _normalize_action(str(rec.get("action") or ""))
        if not action:
            continue
        by_action.setdefault(action, set()).add(_action_type(rec))
    issues: list[TextLintIssue] = []
    for action, kinds in by_action.items():
        if "avoid_action" in kinds and (
            "tactic_candidate" in kinds or "runnable_tactic" in kinds
        ):
            issues.append(TextLintIssue(
                "error",
                "conflicting_guidance_for_same_action",
                (
                    "The same tactic is exposed as both avoid guidance and a "
                    "positive candidate/commit recommendation."
                ),
                f"{path}[action={action}]",
            ))
    return issues


def _lint_proof_ir(proof_ir: dict[str, Any]) -> list[TextLintIssue]:
    issues: list[TextLintIssue] = []
    phase = _dict(proof_ir.get("phase"))
    prefer = [str(item) for item in (phase.get("prefer") or []) if str(item)]
    avoid = [str(item) for item in (phase.get("avoid") or []) if str(item)]
    if avoid and not prefer:
        issues.append(TextLintIssue(
            "error",
            "phase_avoid_without_positive_prefer",
            "ProofIR phase guidance lists avoid items without positive prefer items.",
            "proof_ir.phase",
        ))

    issues.extend(_lint_diagnostics(
        _list(proof_ir.get("diagnostics")),
        path="proof_ir.diagnostics",
    ))
    menu = _list(proof_ir.get("candidate_menu"))
    for idx, item in enumerate(menu):
        legality = _dict(item.get("legality"))
        text = _join_strings([
            item.get("why"),
            legality.get("reason"),
            *_strings(item.get("preconditions")),
        ])
        if legality.get("status") == "avoid" and _negative_without_repair(text):
            issues.append(TextLintIssue(
                "warning",
                "candidate_avoid_without_local_repair",
                (
                    "Avoid candidate has a negative legality reason without a "
                    "local positive route; phase.prefer may still supply one."
                ),
                f"proof_ir.candidate_menu[{idx}]",
            ))
    return issues


def _lint_diagnostics(
    diagnostics: list[dict[str, Any]],
    *,
    path: str,
    require_repair: bool = True,
) -> list[TextLintIssue]:
    issues: list[TextLintIssue] = []
    for idx, diag in enumerate(diagnostics):
        diag_path = f"{path}[{idx}]"
        repairs = [str(item) for item in _list_or_strings(diag.get("repairs")) if str(item)]
        text = _join_strings([
            diag.get("title"),
            diag.get("message"),
            diag.get("reason"),
            diag.get("cause"),
            *repairs,
        ])
        if _NOT_CALLABLE_RE.search(text):
            if not (_REASON_RE.search(text) and (repairs or _REPAIR_RE.search(text))):
                issues.append(TextLintIssue(
                    "error",
                    "not_callable_without_reason_or_repair",
                    "`not callable` diagnostic must include reason and repair.",
                    diag_path,
                ))
        if require_repair and _NEGATIVE_RE.search(text) and not repairs:
            issues.append(TextLintIssue(
                "error",
                "diagnostic_without_repairs",
                "Negative diagnostic text must include a repairs list.",
                diag_path,
            ))
    return issues


def _negative_without_repair(text: str) -> bool:
    if not _NEGATIVE_RE.search(text):
        return False
    return not (_REASON_RE.search(text) and _REPAIR_RE.search(text))


def _has_positive_route(rec: dict[str, Any]) -> bool:
    text = _recommendation_text(rec)
    # A private preflight no-progress verdict is evidence, not a route the prover
    # can follow.  Strip common evidence phrasing before searching for repairs.
    route_text = re.sub(
        r"\b(?:daemon\s+probe|private\s+easycrypt\s+preflight)\s+predicted\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if _REPAIR_RE.search(route_text):
        return True
    metadata = _dict(rec.get("metadata"))
    if str(metadata.get("repair_hint") or ""):
        return True
    return False


def _recommendation_text(rec: dict[str, Any]) -> str:
    pieces: list[Any] = [
        rec.get("why"),
        rec.get("action"),
        *_strings(rec.get("preconditions")),
    ]
    metadata = _dict(rec.get("metadata"))
    for key in (
        "proof_ir_legality_reason",
        "repair_hint",
        "diagnostic",
        "reason",
        "cause",
    ):
        pieces.append(metadata.get(key))
    for ref in _list(rec.get("source_refs")):
        details = _dict(ref.get("details"))
        pieces.extend(details.values())
        pieces.append(ref.get("title"))
    return _join_strings(pieces)


def _action_type(rec: dict[str, Any]) -> str:
    metadata = _dict(rec.get("metadata"))
    return str(rec.get("action_type") or metadata.get("action_type") or "")


def _normalize_action(action: str) -> str:
    return re.sub(r"\s+", " ", action.strip())


def _join_strings(values: Iterable[Any]) -> str:
    return " ".join(str(item) for item in values if isinstance(item, str) and item)


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, tuple):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, str):
        return [value]
    return []


def _list_or_strings(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value]
    return []



def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _iter_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _iter_strings(item, f"{path}[{idx}]")
