"""Frame-obligation ledger analyzer."""
from __future__ import annotations

import re
from typing import Any

from workflow.proof_management.analyzers.common import (
    _drop_empty_precheck as _drop_empty,
    _string_list,
)
from workflow.proof_management.checkpoint_surface import checkpoint_id, history_hash
from workflow.proof_management.frame_facts import (
    extract_frame_facts,
    frame_boundary_facts,
    frame_fact_carried,
    frame_ledger_scope_start,
    frame_recent_manager_goal_text,
    merge_frame_fact_sources,
    pre_post_sections,
    transitively_equal_terms,
    view_goal_text,
)
from workflow.proof_management.node_state import ProofNodeState
from workflow.proof_management.tactic_utils import (
    is_product_budget_seq as _is_product_budget_seq,
)


class FrameObligationAnalyzer:
    """Builds the `frame_obligation_ledger` L4 panel."""

    def analyze(
        self,
        *,
        state: ProofNodeState,
        view: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace_view = dict(view or state.base_workspace_view)
        return _frame_obligation_ledger(
            workspace_view,
            tactics=state.committed_tactics,
        )


def _frame_obligation_ledger(
    view: dict[str, Any],
    *,
    tactics: list[str],
) -> dict[str, Any]:
    if not tactics:
        return {}
    goal_text = view_goal_text(view)
    recent_goal_text = frame_recent_manager_goal_text(view)
    required = merge_frame_fact_sources([
        ("top_level_contract", extract_frame_facts(tactics[0])),
        ("current_goal", extract_frame_facts(goal_text)),
        ("recent_manager_goal", extract_frame_facts(recent_goal_text)),
    ])
    if not required:
        return {}
    scope_start = frame_ledger_scope_start(tactics)
    boundaries = frame_boundary_facts(tactics, start_index=scope_start)
    if not boundaries:
        return {}
    dropped: list[dict[str, Any]] = []
    all_carried = {
        c for item in boundaries for c in _string_list(item.get("canonical_facts"))
    }
    # A fact derivable from the PRECONDITION by transitivity through a middle memory
    # (`X{1}=X{m} ∧ X{2}=X{m}` ⊢ `={X}`) is NOT dropped — it is provable, just not
    # re-asserted at a boundary (cpa_ddh0: `={glob A}` from the pre). Scan only the PRE of
    # the goal/recent (never the post), so a required `={X}` in the post is not self-proving.
    transitive = (
        transitively_equal_terms(pre_post_sections(goal_text)[0])
        | transitively_equal_terms(pre_post_sections(recent_goal_text)[0])
    )
    for fact in required:
        sources = set(_string_list(fact.get("sources")))
        if not sources.intersection({"current_goal", "recent_manager_goal"}):
            continue
        canonical = str(fact.get("canonical") or "")
        if frame_fact_carried(canonical, all_carried):
            continue
        if canonical in transitive:
            continue
        missing = next(
            (
                item for item in boundaries
                if fact["canonical"] not in set(_string_list(item.get("canonical_facts")))
            ),
            {},
        )
        if not missing:
            continue
        checkpoint = _route_health_checkpoint(
            tactics,
            int(missing.get("tactic_index") or 0),
            why_here=(
                "Frame fact is visible in required context and absent from "
                "this structural boundary assertion."
            ),
        )
        dropped.append(_drop_empty({
            "fact": fact["display"],
            "required_sources": fact["sources"],
            "boundary": (
                f"{missing.get('kind')} #{missing.get('tactic_index')}"
                if missing.get("kind") else ""
            ),
            "boundary_tactic": missing.get("tactic"),
            "evidence": (
                "required fact is visible in the listed source(s), while this "
                "boundary assertion does not carry the same frame fact"
            ),
            "related_checkpoint": checkpoint,
        }))
    if not dropped:
        return {}
    return _drop_empty({
        "kind": "frame_obligation_ledger",
        "scope": "structural_boundary_frame_facts",
        "active_segment_start": scope_start,
        "required_later": [
            {
                "fact": fact["display"],
                "sources": fact["sources"],
            }
            for fact in required
        ],
        "current_boundary_carries": [
            {
                "tactic_index": item.get("tactic_index"),
                "kind": item.get("kind"),
                "carried_facts": item.get("carried_facts"),
                "tactic": item.get("tactic"),
            }
            for item in boundaries[-6:]
        ],
        "possibly_dropped": dropped[:4],
        "interpretation": (
            "This ledger compares visible frame facts with the frame facts "
            "carried by committed structural boundary assertions. Possible "
            "drops are reported only for facts visible in the current local "
            "goal evidence. It is evidence about retained facts, not a proof "
            "script."
        ),
    })


def _route_health_checkpoint(
    tactics: list[str],
    tactic_index: int,
    *,
    why_here: str,
) -> dict[str, Any]:
    if tactic_index < 1 or tactic_index > len(tactics):
        return {}
    tactic = tactics[tactic_index - 1]
    return {
        "label": _checkpoint_label_for_tactic(tactic, tactic_index),
        "committed_tactic": tactic,
        "tactic_index": tactic_index,
        "why_here": why_here,
        "submit": {
            "intent": "undo_to_checkpoint",
            "payload": {
                "checkpoint_id": checkpoint_id(history_hash(tactics), tactic_index),
            },
        },
    }


def _checkpoint_label_for_tactic(tactic: str, tactic_index: int) -> str:
    text = tactic.strip().lower()
    if "call (_:" in text:
        return f"Before call invariant #{tactic_index}"
    if text.startswith("while"):
        return f"Before while invariant #{tactic_index}"
    if text.startswith("seq"):
        if _is_product_budget_seq(tactic):
            return f"Before product-budget seq cut #{tactic_index}"
        return f"Before seq cut #{tactic_index}"
    if text.startswith("conseq"):
        return f"Before conseq reshape #{tactic_index}"
    if text.startswith("inline") or re.search(r"\binline\b", text):
        return f"Before inline expansion #{tactic_index}"
    return f"Before committed tactic #{tactic_index}"
