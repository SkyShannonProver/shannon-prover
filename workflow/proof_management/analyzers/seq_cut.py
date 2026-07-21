"""Seq-cut evidence analyzer.

This pass reports reversible seq-cut structure as evidence. It does not mutate
the proof state, execute tactics, or render directly into the workspace view.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from workflow.proof_management.analyzers.common import (
    _dict,
    _drop_empty,
    _list,
)
from workflow.proof_management.node_state import ProofNodeState
# Checkpoint-id coordinate system lives in checkpoint_surface — import rather
# than re-deriving, so a seq-cut candidate id can never drift from the rewind
# menu / replay-prefix hash (audit §8 #7).
from workflow.proof_management.checkpoint_surface import (
    checkpoint_id as _checkpoint_id,
    history_hash as _history_hash,
)
from workflow.proof_management.frame_facts import view_goal_text
from workflow.proof_management.tactic_utils import tactic_head as _tactic_head


class SeqCutAnalyzer:
    """Builds the `seq_cut_surface` L4 panel."""

    def analyze(
        self,
        *,
        state: ProofNodeState,
        view: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace_view = dict(view or state.base_workspace_view)
        return _seq_cut_surface(
            workspace_view,
            route_event_facts=state.route_event_facts,
            tactics=state.committed_tactics,
        )


def _seq_cut_surface(
    view: dict[str, Any],
    *,
    route_event_facts: list[dict[str, Any]],
    tactics: list[str],
) -> dict[str, Any]:
    proof_status = _dict(view.get("proof_status") or view.get("proof_position"))
    view_focus = str(proof_status.get("view_focus") or "").lower()
    current_layer = str(proof_status.get("current_layer") or "").lower()
    latest_seq = _latest_seq_tactic(tactics)
    last_result = _dict(view.get("last_result"))
    rewound_seq = _rewound_seq_cut_observation(last_result)
    accepted_tactic = str(last_result.get("accepted_tactic") or "").strip()
    accepted_is_seq = bool(accepted_tactic and _tactic_head(accepted_tactic) == "seq")
    if (
        "seq" not in view_focus
        and not latest_seq
        and not accepted_is_seq
        and not rewound_seq
    ):
        return {}
    goal_text = view_goal_text(view)
    if rewound_seq:
        seq_tactic = str(rewound_seq.get("tactic") or "")
        seq_idx = int(rewound_seq.get("tactic_index") or 0)
    else:
        seq_tactic = str(latest_seq.get("tactic") or accepted_tactic or "")
        seq_idx = int(latest_seq.get("tactic_index") or 0)
    history_hash = _history_hash(tactics) if tactics else ""
    if rewound_seq and rewound_seq.get("checkpoint_id"):
        seq_candidate_id = str(rewound_seq.get("checkpoint_id") or "")
    elif seq_idx and history_hash:
        seq_candidate_id = _checkpoint_id(history_hash, seq_idx)
    elif seq_tactic:
        seq_candidate_id = "accepted_" + hashlib.sha1(
            seq_tactic.encode("utf-8")
        ).hexdigest()[:12]
    else:
        seq_candidate_id = ""
    state_name = ""
    if rewound_seq:
        state_name = "before_rewound_seq_cut"
    elif seq_idx and len(tactics) > seq_idx:
        state_name = "inside_seq_scope"
    elif seq_idx:
        state_name = "after_seq_opened"
    else:
        state_name = "seq_view"
    frontier = _dict(view.get("program_frontier"))
    live_call_sites = _list(frontier.get("call_sites"))
    preview_summary = _dict(last_result.get("preview_summary"))
    return _drop_empty({
        "seq_candidate_id": seq_candidate_id,
        "state": state_name,
        "restored_boundary": _drop_empty({
            "kind": "checkpoint_rewind",
            "rewound_tactic_index": rewound_seq.get("tactic_index"),
            "undone_tactic_count": rewound_seq.get("undone_tactic_count"),
            "boundary_status": "not_committed_in_current_state",
            "restored_proof_layer": "pre_seq_cut",
        }) if rewound_seq else {},
        "cut_position": _seq_cut_position(seq_tactic),
        "obligation_count": (
            preview_summary.get("remaining_goals")
            or proof_status.get("remaining_goals")
            or proof_status.get("num_remaining")
        ),
        "obligation_kinds": _seq_obligation_kinds(goal_text, view),
        "branch_focus": _seq_branch_focus(proof_status, route_event_facts),
        "residual_frontier": _drop_empty({
            "current_layer": current_layer,
            "view_focus": proof_status.get("view_focus"),
            "live_call_site_count": len(live_call_sites),
            "goal_contains_call_site": _goal_text_contains_call_site(goal_text),
            "latest_seq_tactic_index": (
                None if rewound_seq else (seq_idx or None)
            ),
            "latest_committed_seq_tactic_index": (
                int(latest_seq.get("tactic_index") or 0) or None
            ) if rewound_seq else None,
            "rewound_seq_tactic_index": (
                int(rewound_seq.get("tactic_index") or 0) or None
            ) if rewound_seq else None,
            "tactics_after_latest_seq": (
                len(tactics) - seq_idx if (seq_idx and not rewound_seq) else None
            ),
        }),
    })


def _rewound_seq_cut_observation(last_result: dict[str, Any]) -> dict[str, Any]:
    if str(last_result.get("kind") or "") != "checkpoint_rewind":
        return {}
    tactic = str(last_result.get("committed_tactic") or "").strip()
    if _tactic_head(tactic) != "seq":
        return {}
    payload = _dict(last_result.get("payload"))
    return _drop_empty({
        "tactic": tactic,
        "tactic_index": int(last_result.get("tactic_index") or 0),
        "undone_tactic_count": int(last_result.get("undone_tactic_count") or 0),
        "checkpoint_id": str(payload.get("checkpoint_id") or ""),
    })


def _latest_seq_tactic(tactics: list[str]) -> dict[str, Any]:
    for idx in range(len(tactics), 0, -1):
        tactic = str(tactics[idx - 1] or "").strip()
        if _tactic_head(tactic) == "seq":
            return {"tactic_index": idx, "tactic": tactic}
    return {}


def _seq_cut_position(tactic: str) -> dict[str, Any]:
    text = str(tactic or "").strip()
    match = re.match(r"seq\s+(\d+)(?:\s+(\d+))?", text, flags=re.I)
    if not match:
        return _drop_empty({"tactic": text})
    return _drop_empty({
        "left_count": int(match.group(1)),
        "right_count": int(match.group(2)) if match.group(2) else None,
        "tactic": text,
    })


def _seq_obligation_kinds(goal_text: str, view: dict[str, Any]) -> list[str]:
    lower = str(goal_text or "").lower()
    kinds: list[str] = []
    if "{1}" in goal_text or "{2}" in goal_text:
        kinds.append("relational")
    if _goal_text_contains_call_site(goal_text) or _dict(view.get("program_frontier")).get("call_sites"):
        kinds.append("call_site")
    if "post =" in lower:
        kinds.append("postcondition")
    if "forall" in lower:
        kinds.append("quantified")
    if "if " in lower or "branch" in lower:
        kinds.append("branch")
    if any(token in lower for token in ("pr[", "lossless", "mu ", "size ")):
        kinds.append("probability_or_loss")
    return kinds[:6]


def _seq_branch_focus(
    proof_status: dict[str, Any],
    route_event_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    latest = route_event_facts[-1] if route_event_facts else {}
    return _drop_empty({
        "goal_index": proof_status.get("goal_index") or proof_status.get("current_goal_index"),
        "remaining_goals": proof_status.get("remaining_goals") or proof_status.get("num_remaining"),
        "latest_event_head": latest.get("tactic_head"),
        "latest_event_status": latest.get("status"),
    })


def _goal_text_contains_call_site(text: str) -> bool:
    return "<@" in str(text or "") or bool(
        re.search(r"\bcall\s+[A-Za-z_][A-Za-z0-9_.'`]*", str(text or ""))
    )
