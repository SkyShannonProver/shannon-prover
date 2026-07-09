"""Conservative route-family evidence for proof search diversity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from core.easycrypt.value_shapes import as_dict_copy as _dict
from core.easycrypt.value_shapes import drop_empty as _drop_empty


@dataclass(frozen=True)
class RouteFamilyEvidence:
    family: str = "unknown"
    confidence: str = "low"
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "family": self.family,
            "confidence": self.confidence,
            "evidence": list(self.evidence[:6]),
        })


def infer_route_family(
    tactics: list[str],
    *,
    view: dict[str, Any] | None = None,
) -> RouteFamilyEvidence:
    """Classify the current route shape without claiming proof usefulness."""

    clean = [str(tactic).strip() for tactic in tactics if str(tactic).strip()]
    lowered = [tactic.lower() for tactic in clean]
    view = dict(view or {})
    proof_status = _dict(view.get("proof_status"))
    current_layer = str(proof_status.get("current_layer") or "").strip()
    panels = {key for key, value in view.items() if isinstance(value, dict)}

    if "pure_tail_surface" in panels or current_layer in {
        "ambient_logic",
        "verification_residue",
    }:
        return RouteFamilyEvidence(
            family="pure_tail_repair",
            confidence="medium",
            evidence=[
                "current view is in ambient/residual logic",
                *(_tactic_evidence(clean, limit=2)),
            ],
        )

    early_seq_index = _first_index(lowered, "seq")
    if early_seq_index >= 0 and early_seq_index <= 5:
        return RouteFamilyEvidence(
            family="top_level_seq_route",
            confidence="medium",
            evidence=[
                f"early seq cut at tactic index {early_seq_index + 1}",
                *(_tactic_evidence(clean, limit=3)),
            ],
        )

    call_index = _first_index(lowered, "call")
    if call_index >= 0 or "call_site_surface" in panels or current_layer == "call_site":
        return RouteFamilyEvidence(
            family="call_boundary_route",
            confidence="medium" if call_index >= 0 else "low",
            evidence=[
                (
                    f"call tactic at index {call_index + 1}"
                    if call_index >= 0 else
                    "current view exposes call-site evidence"
                ),
                *(_tactic_evidence(clean, limit=3)),
            ],
        )

    inline_count = sum(1 for tactic in lowered if tactic.startswith("inline"))
    procedure_count = sum(
        1 for tactic in lowered
        if tactic.startswith(("rcond", "while", "wp", "sp", "swap"))
    )
    if inline_count >= 2 or procedure_count >= 4:
        return RouteFamilyEvidence(
            family="procedure_local_route",
            confidence="low",
            evidence=[
                f"inline_count={inline_count}",
                f"procedure_tactic_count={procedure_count}",
                *(_tactic_evidence(clean, limit=3)),
            ],
        )

    if clean:
        return RouteFamilyEvidence(
            family="linear_prefix_route",
            confidence="low",
            evidence=_tactic_evidence(clean, limit=3),
        )
    return RouteFamilyEvidence()


def route_family_score_adjustment(route_family: RouteFamilyEvidence) -> tuple[float, str]:
    """Small diversity-aware score nudge for resume ordering."""

    family = route_family.family
    if family == "top_level_seq_route":
        return 2.0, "route_family=top_level_seq_route"
    if family == "call_boundary_route":
        return 1.0, "route_family=call_boundary_route"
    if family == "pure_tail_repair":
        return 0.5, "route_family=pure_tail_repair"
    if family == "procedure_local_route":
        return -0.5, "route_family=procedure_local_route"
    return 0.0, ""


def _first_index(tactics: list[str], head: str) -> int:
    for index, tactic in enumerate(tactics):
        if tactic.startswith(head):
            return index
    return -1


def _tactic_evidence(tactics: list[str], *, limit: int) -> list[str]:
    return [f"tactic[{idx + 1}]={tactic}" for idx, tactic in enumerate(tactics[:limit])]



