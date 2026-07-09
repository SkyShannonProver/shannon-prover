"""Shadow-mode route diversity summaries for resume/root selection."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from core.easycrypt.value_shapes import as_dict_copy as _dict
from core.easycrypt.value_shapes import drop_empty as _drop_empty


@dataclass(frozen=True)
class ResumeRouteCandidate:
    path: str
    score: float = 0.0
    tactic_count: int = 0
    route_family: dict[str, Any] = field(default_factory=dict)

    def family(self) -> str:
        return str(self.route_family.get("family") or "unknown")

    def to_dict(self) -> dict[str, Any]:
        return _drop_empty({
            "path": self.path,
            "score": float(self.score),
            "tactic_count": int(self.tactic_count),
            "route_family": dict(self.route_family),
        })


def build_resume_diversity_index(
    candidates: list[ResumeRouteCandidate],
) -> dict[str, Any]:
    """Build a route-family-aware resume index without changing scheduling."""

    score_order = sorted(
        candidates,
        key=lambda item: (item.score, item.tactic_count),
        reverse=True,
    )
    groups: dict[str, list[ResumeRouteCandidate]] = {}
    for candidate in score_order:
        groups.setdefault(candidate.family(), []).append(candidate)

    group_order = sorted(
        groups,
        key=lambda family: (
            groups[family][0].score if groups[family] else 0.0,
            len(groups[family]),
        ),
        reverse=True,
    )
    diversity_order: list[ResumeRouteCandidate] = []
    pending = {family: list(items) for family, items in groups.items()}
    while any(pending.values()):
        for family in group_order:
            if pending[family]:
                diversity_order.append(pending[family].pop(0))

    return {
        "kind": "resume_route_diversity_index",
        "mode": "shadow",
        "score_order": [
            {
                **candidate.to_dict(),
                "score_rank": rank,
            }
            for rank, candidate in enumerate(score_order)
        ],
        "diversity_order": [
            {
                **candidate.to_dict(),
                "diversity_rank": rank,
            }
            for rank, candidate in enumerate(diversity_order)
        ],
        "route_family_groups": {
            family: {
                "count": len(groups[family]),
                "best_score": groups[family][0].score if groups[family] else 0.0,
                "paths": [candidate.path for candidate in groups[family]],
            }
            for family in group_order
        },
        "interpretation": (
            "Shadow resume ordering: score_order preserves current behavior; "
            "diversity_order interleaves route families for future resume-root "
            "selection."
        ),
    }


def resume_diversity_handoff_note(
    diversity_index: dict[str, Any],
    *,
    capsule_path: str,
) -> str:
    """Summarize one capsule's route-diversity position for agent handoff."""

    summary = resume_diversity_candidate_summary(
        diversity_index,
        capsule_path=capsule_path,
    )
    if not summary:
        return ""
    parts = [
        "Resume diversity shadow: current behavior still follows score order",
    ]
    score_rank = summary.get("score_rank")
    score_total = summary.get("score_total")
    if score_rank is not None:
        parts.append(f"score-rank {int(score_rank) + 1}/{score_total}")
    diversity_rank = summary.get("diversity_rank")
    diversity_total = summary.get("diversity_total")
    if diversity_rank is not None:
        parts.append(
            f"diversity-rank {int(diversity_rank) + 1}/{diversity_total}"
        )
    family = str(summary.get("route_family") or "")
    family_count = int(summary.get("family_candidate_count") or 0)
    if family:
        parts.append(
            f"family `{family}`"
            + (
                f" has {family_count} candidate(s)"
                if family_count else ""
            )
        )
    parts.append(
        "treat diversity order as evidence for future sibling/root choice, "
        "not as an already-applied scheduler decision"
    )
    return "; ".join(parts) + "."


def resume_diversity_candidate_summary(
    diversity_index: dict[str, Any],
    *,
    capsule_path: str,
) -> dict[str, Any]:
    """Return stable rank/group coordinates for one resume capsule."""

    focus = _candidate_for_path(diversity_index, capsule_path)
    if not focus:
        return {}
    score_order = _dict_list(diversity_index.get("score_order"))
    diversity_order = _dict_list(diversity_index.get("diversity_order"))
    family = _candidate_family(focus)
    groups = _dict(diversity_index.get("route_family_groups"))
    group = _dict(groups.get(family))
    return _drop_empty({
        "mode": str(diversity_index.get("mode") or "shadow"),
        "score_rank": _candidate_rank(score_order, capsule_path, "score_rank"),
        "score_total": len(score_order),
        "diversity_rank": _candidate_rank(
            diversity_order,
            capsule_path,
            "diversity_rank",
        ),
        "diversity_total": len(diversity_order),
        "route_family": family,
        "family_candidate_count": _safe_int(group.get("count")),
        "family_best_score": _safe_float(group.get("best_score"), 0.0),
    })


def resume_diversity_markdown(diversity_index: dict[str, Any]) -> str:
    """Render a durable resume-route diversity briefing."""

    score_order = _dict_list(diversity_index.get("score_order"))
    diversity_order = _dict_list(diversity_index.get("diversity_order"))
    groups = _dict(diversity_index.get("route_family_groups"))
    lines = [
        "# Resume Route Diversity",
        "",
        "Shadow-mode briefing. Score order preserves current behavior; "
        "diversity order is evidence for future resume-root selection.",
        "",
    ]
    if groups:
        lines.append("## Route Families")
        for family, group_value in sorted(groups.items()):
            group = _dict(group_value)
            lines.append(
                "- "
                + str(family)
                + f": {int(group.get('count') or 0)} candidate(s), "
                + f"best_score={float(group.get('best_score') or 0.0):.2f}"
            )
        lines.append("")
    if score_order:
        lines.append("## Score Order")
        for rank, candidate in enumerate(score_order, start=1):
            lines.append(_candidate_markdown_row(rank, candidate))
        lines.append("")
    if diversity_order:
        lines.append("## Diversity Order")
        for rank, candidate in enumerate(diversity_order, start=1):
            lines.append(_candidate_markdown_row(rank, candidate))
        lines.append("")
    interpretation = str(diversity_index.get("interpretation") or "").strip()
    if interpretation:
        lines.append(interpretation)
        lines.append("")
    return "\n".join(lines)


def resume_route_candidate_from_manifest(
    *,
    path: str,
    manifest: dict[str, Any],
    fallback_score: float = 0.0,
) -> ResumeRouteCandidate:
    score = _dict(manifest.get("score"))
    replay = _dict(manifest.get("replay"))
    route_family = _dict(score.get("route_family"))
    if not route_family:
        route_family = _dict(_dict(manifest.get("lineage")).get("route_family"))
    return ResumeRouteCandidate(
        path=path,
        score=_safe_float(score.get("value"), fallback_score),
        tactic_count=_safe_int(replay.get("tactic_count")),
        route_family=route_family,
    )



def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0



def _candidate_for_path(
    diversity_index: dict[str, Any],
    capsule_path: str,
) -> dict[str, Any]:
    for key in ("score_order", "diversity_order"):
        for item in _dict_list(diversity_index.get(key)):
            if str(item.get("path") or "") == capsule_path:
                return item
    return {}


def _candidate_rank(
    candidates: list[dict[str, Any]],
    capsule_path: str,
    rank_key: str,
) -> int | None:
    for index, item in enumerate(candidates):
        if str(item.get("path") or "") != capsule_path:
            continue
        try:
            return int(item.get(rank_key))
        except (TypeError, ValueError):
            return index
    return None


def _candidate_family(candidate: dict[str, Any]) -> str:
    return str(_dict(candidate.get("route_family")).get("family") or "unknown")


def _candidate_markdown_row(rank: int, candidate: dict[str, Any]) -> str:
    family = _candidate_family(candidate)
    score = _safe_float(candidate.get("score"), 0.0)
    tactics = _safe_int(candidate.get("tactic_count"))
    path = str(candidate.get("path") or "")
    return (
        f"{rank}. `{family}` score={score:.2f} tactics={tactics} "
        f"path={path}"
    )
