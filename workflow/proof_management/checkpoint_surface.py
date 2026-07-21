"""Checkpoint surface and menu construction.

This module owns the checkpoint coordinate system used by rewind menus,
structural checkpoint panels, and route-health repair references.  It is pure:
callers pass committed tactics and route-health evidence, and receive
ProverWorkspaceView-compatible dictionaries.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from workflow.proof_management.common import coerce_string_list as _string_list
from workflow.proof_management.common import _dict, _drop_empty
from workflow.proof_management.tactic_utils import (
    is_product_budget_seq,
    tactic_head,
)
from workflow.proof_management.transitions import is_broad_inline_tactic


def history_hash(tactics: list[str]) -> str:
    return hashlib.sha1("\n".join(tactics).encode("utf-8")).hexdigest()


def checkpoint_id(history_digest: str, tactic_index: int) -> str:
    return f"cp_{int(tactic_index)}_{history_digest[:16]}"


def parse_checkpoint_id(value: str) -> tuple[int, str] | None:
    match = re.fullmatch(r"cp_(\d+)_([0-9a-f]{16})", str(value or "").strip())
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def structural_checkpoints_surface(
    tactics: list[str],
    *,
    route_health: list[dict[str, Any]] | None = None,
    replay_prefix_count: int = 0,
) -> list[dict[str, Any]]:
    if not tactics:
        return []
    digest = history_hash(tactics)
    overrides = semantic_checkpoint_overrides(
        tactics,
        route_health=route_health,
        replay_prefix_count=replay_prefix_count,
    )
    items: list[dict[str, Any]] = []
    for idx in ordered_checkpoint_indices(tactics, overrides):
        override = overrides.get(idx) or {}
        if 1 <= idx <= len(tactics):
            items.append(checkpoint_surface_item(
                tactics,
                digest,
                idx,
                override=override,
            ))
    return items[:8]


def checkpoint_surface_item(
    tactics: list[str],
    history_digest: str,
    tactic_index: int,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tactic = tactics[tactic_index - 1]
    semantics = checkpoint_semantics(tactic)
    override = override or {}
    semantic_ids = _string_list(override.get("semantic_ids"))
    if not semantic_ids and override.get("semantic_id"):
        semantic_ids = [str(override.get("semantic_id"))]
    cid = checkpoint_id(history_digest, tactic_index)
    return _drop_empty({
        "checkpoint_id": cid,
        "semantic_id": semantic_ids[0] if semantic_ids else "",
        "semantic_ids": semantic_ids,
        "label": override.get("label") or checkpoint_label_for_tactic(tactic, tactic_index),
        "committed_step_index": tactic_index,
        "committed_tactic": tactic,
        "restored_proof_layer": override.get("restored_proof_layer") or restored_layer_for_tactic(tactic),
        "restored_affordances": override.get("restored_affordances"),
        "undo_scope": override.get("undo_scope") or undo_scope_for_tactic(tactic),
        "why_checkpoint": override.get("why_checkpoint") or semantics["why_checkpoint"],
        "effect_if_selected": (
            f"Undo committed tactic #{tactic_index} and every committed "
            "tactic after it in this node."
        ),
        "submit": {
            "intent": "undo_to_checkpoint",
            "payload": {"checkpoint_id": cid},
        },
    })


def checkpoint_options(
    tactics: list[str],
    *,
    route_health: list[dict[str, Any]] | None = None,
    replay_prefix_count: int = 0,
) -> list[dict[str, Any]]:
    if not tactics:
        return []
    digest = history_hash(tactics)
    selected: list[int] = []
    overrides: dict[int, dict[str, Any]] = semantic_checkpoint_overrides(
        tactics,
        route_health=route_health,
        replay_prefix_count=replay_prefix_count,
    )
    for idx in ordered_checkpoint_indices(tactics, overrides):
        semantic_ids = set(_string_list(overrides[idx].get("semantic_ids")))
        if semantic_ids == {"last_call_site_boundary"}:
            continue
        if idx not in selected:
            selected.append(idx)
    for idx in product_budget_seq_indices(tactics):
        if len(selected) >= 12:
            break
        if idx in selected:
            continue
        selected.append(idx)
    recent_start = max(1, len(tactics) - 4)
    for idx in range(len(tactics), recent_start - 1, -1):
        if len(selected) >= 12:
            break
        if idx not in selected:
            selected.append(idx)
    for idx in outer_structural_boundary_indices(tactics):
        overrides.setdefault(idx, {
            "label": checkpoint_label_for_tactic(tactics[idx - 1], idx),
        })
        if idx in selected:
            continue
        if len(selected) >= 12:
            replaceable = replaceable_checkpoint_for_outer_boundary(
                selected,
                tactics,
                overrides,
            )
            if replaceable:
                selected.remove(replaceable)
            else:
                break
        selected.append(idx)
    for idx in range(len(tactics), 0, -1):
        if len(selected) >= 12:
            break
        if idx in selected:
            continue
        if is_structural_tactic(tactics[idx - 1]):
            selected.append(idx)
    selected = selected[:12]
    return [
        checkpoint_option(
            tactics,
            digest,
            tactic_index,
            override=overrides.get(tactic_index),
        )
        for tactic_index in selected
    ]


def checkpoint_option(
    tactics: list[str],
    history_digest: str,
    tactic_index: int,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tactic = tactics[tactic_index - 1]
    semantics = checkpoint_semantics(tactic)
    override = override or {}
    default_label = f"Rewind to before committed tactic #{tactic_index}"
    if is_product_budget_seq(tactic):
        default_label = checkpoint_label_for_tactic(tactic, tactic_index)
    semantic_ids = _string_list(override.get("semantic_ids"))
    if not semantic_ids and override.get("semantic_id"):
        semantic_ids = [str(override.get("semantic_id"))]
    cid = checkpoint_id(history_digest, tactic_index)
    return _drop_empty({
        "checkpoint_id": cid,
        "semantic_id": semantic_ids[0] if semantic_ids else "",
        "semantic_ids": semantic_ids,
        "label": override.get("label") or default_label,
        "committed_tactic": tactic,
        "tactic_index": tactic_index,
        "committed_step_index": tactic_index,
        "restored_proof_layer": override.get("restored_proof_layer") or restored_layer_for_tactic(tactic),
        "restored_affordances": override.get("restored_affordances"),
        "undo_scope": override.get("undo_scope") or undo_scope_for_tactic(tactic),
        "why_checkpoint": override.get("why_checkpoint") or semantics["why_checkpoint"],
        "repair_use_when": override.get("repair_use_when") or semantics["repair_use_when"],
        "after_rewind_next": override.get("after_rewind_next") or semantics["after_rewind_next"],
        "effect_if_selected": (
            f"This will undo committed tactic #{tactic_index} and every "
            "committed tactic after it in this node."
        ),
        "submit": {
            "intent": "undo_to_checkpoint",
            "payload": {
                "checkpoint_id": cid,
            },
        },
    })


def route_health_checkpoint(
    tactics: list[str],
    tactic_index: int,
    *,
    why_here: str,
) -> dict[str, Any]:
    if tactic_index < 1 or tactic_index > len(tactics):
        return {}
    tactic = tactics[tactic_index - 1]
    digest = history_hash(tactics)
    return {
        "label": checkpoint_label_for_tactic(tactic, tactic_index),
        "committed_tactic": tactic,
        "tactic_index": tactic_index,
        "why_here": why_here,
        "submit": {
            "intent": "undo_to_checkpoint",
            "payload": {"checkpoint_id": checkpoint_id(digest, tactic_index)},
        },
    }


def semantic_checkpoint_overrides(
    tactics: list[str],
    *,
    route_health: list[dict[str, Any]] | None = None,
    replay_prefix_count: int = 0,
) -> dict[int, dict[str, Any]]:
    overrides: dict[int, dict[str, Any]] = {}

    def merge(idx: int, data: dict[str, Any]) -> None:
        if idx < 1 or idx > len(tactics):
            return
        current = dict(overrides.get(idx) or {})
        ids = _string_list(current.get("semantic_ids"))
        for semantic_id in _string_list(data.get("semantic_id")) + _string_list(
            data.get("semantic_ids")
        ):
            if semantic_id not in ids:
                ids.append(semantic_id)
        merged = {**current, **data}
        if ids:
            merged["semantic_ids"] = ids
            merged["semantic_id"] = ids[0]
        overrides[idx] = _drop_empty(merged)

    for item in route_health or []:
        checkpoint = _dict(item.get("repair_checkpoint"))
        try:
            idx = int(checkpoint.get("tactic_index") or 0)
        except (TypeError, ValueError):
            idx = 0
        if idx:
            merge(idx, {
                "semantic_id": str(item.get("signal") or "route_health_repair"),
                "label": str(checkpoint.get("label") or ""),
                "why_checkpoint": str(checkpoint.get("why_here") or ""),
                "undo_scope": str(checkpoint.get("undo_scope") or ""),
                "restored_affordances": checkpoint.get("restored_affordances"),
                "route_health_repair": True,
            })

    latest_seq = latest_seq_tactic(tactics)
    seq_idx = int(latest_seq.get("tactic_index") or 0)
    if seq_idx:
        merge(seq_idx, {
            "semantic_id": "before_seq_cut",
            "label": checkpoint_label_for_tactic(tactics[seq_idx - 1], seq_idx),
            "why_checkpoint": (
                "seq-cut boundary; selecting it restores the proof state "
                "before this cut was committed"
            ),
            "undo_scope": "seq_local",
            "restored_proof_layer": "pre_seq_cut",
            "restored_affordances": {
                "seq_cut": "not_committed",
                "call_site_state": "as_before_seq_cut",
            },
        })
        if seq_idx < len(tactics):
            merge(seq_idx + 1, {
                "semantic_ids": ["after_seq_opened", "before_branch_work"],
                "label": f"After seq opened / before branch work #{seq_idx + 1}",
                "why_checkpoint": (
                    "seq-local branch boundary; selecting it keeps the seq "
                    "cut and removes branch-local work after it"
                ),
                "undo_scope": "branch_local",
                "restored_proof_layer": "seq_obligations_opened",
                "restored_affordances": {
                    "seq_cut": "committed",
                    "branch_work": "not_committed",
                },
            })
        if len(tactics) > seq_idx + 1:
            merge(len(tactics), {
                "semantic_id": "before_branch_work",
                "label": f"Before latest branch-local tactic #{len(tactics)}",
                "why_checkpoint": (
                    "latest branch-local step inside the current seq scope"
                ),
                "undo_scope": "branch_local",
                "restored_proof_layer": "seq_branch",
                "restored_affordances": {
                    "seq_cut": "committed",
                    "earlier_branch_work": "preserved",
                },
            })

    latest_call = latest_call_tactic(tactics)
    call_idx = int(latest_call.get("tactic_index") or 0)
    if call_idx:
        merge(call_idx, {
            "semantic_id": "before_call_route",
            "label": checkpoint_label_for_tactic(tactics[call_idx - 1], call_idx),
            "undo_scope": "call_local",
            "restored_proof_layer": "pre_call_route",
            "restored_affordances": {
                "call_route": "not_committed",
                "call_obligation_work": "not_committed",
            },
        })
        if call_idx < len(tactics):
            merge(call_idx + 1, {
                "semantic_id": "after_call_opened",
                "label": f"After call opened / before obligation work #{call_idx + 1}",
                "why_checkpoint": (
                    "call-local boundary; selecting it keeps the call tactic "
                    "and removes work committed after the call opened"
                ),
                "undo_scope": "call_local",
                "restored_proof_layer": "call_obligations_opened",
                "restored_affordances": {
                    "call_route": "committed",
                    "call_obligation_work": "not_committed",
                },
            })
        local_call_work = latest_call_obligation_local_tactic(tactics, call_idx)
        local_call_idx = int(local_call_work.get("tactic_index") or 0)
        if local_call_idx > call_idx + 1:
            merge(local_call_idx, {
                "semantic_id": "before_call_obligation_work",
                "label": f"Before latest call-obligation tactic #{local_call_idx}",
                "why_checkpoint": (
                    "call-obligation local boundary; selecting it keeps the "
                    "opened call obligation and removes later local work"
                ),
                "undo_scope": "call_obligation_local",
                "restored_proof_layer": "call_obligation",
                "restored_affordances": {
                    "call_route": "committed",
                    "call_obligation": "preserved",
                    "later_local_work": "not_committed",
                },
            })

    inline_boundary = latest_inline_boundary(tactics)
    if inline_boundary:
        idx = int(inline_boundary.get("tactic_index") or 0)
        merge(idx, {
            "semantic_id": "last_call_site_boundary",
            "label": checkpoint_label_for_tactic(tactics[idx - 1], idx) if idx else "",
            "why_checkpoint": (
                "inline boundary; selecting it restores the proof state "
                "before this expansion"
            ),
            "undo_scope": "call_site_boundary",
            "restored_proof_layer": "pre_inline_frontier",
            "restored_affordances": {
                "call_site_handles": "as_before_inline",
            },
        })

    return overrides


def ordered_checkpoint_indices(
    tactics: list[str],
    overrides: dict[int, dict[str, Any]],
) -> list[int]:
    def priority(item: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        idx, override = item
        semantic_ids = set(_string_list(override.get("semantic_ids")))
        if not semantic_ids and override.get("semantic_id"):
            semantic_ids = {str(override.get("semantic_id") or "")}
        scope = str(override.get("undo_scope") or "")
        if bool(override.get("route_health_repair")):
            rank = -1
        elif "before_branch_work" in semantic_ids and idx == len(tactics):
            rank = 0
        elif "before_call_obligation_work" in semantic_ids:
            rank = 0
        elif scope == "branch_local" or "after_seq_opened" in semantic_ids:
            rank = 1
        elif "after_call_opened" in semantic_ids:
            rank = 2
        elif "before_call_route" in semantic_ids:
            rank = 3
        elif scope == "seq_local" or "before_seq_cut" in semantic_ids:
            rank = 4
        elif scope == "call_site_boundary" or "last_call_site_boundary" in semantic_ids:
            rank = 5
        else:
            rank = 6
        return (rank, -idx)

    return [
        idx
        for idx, _override in sorted(overrides.items(), key=priority)
        if 1 <= idx <= len(tactics)
    ]



def product_budget_seq_indices(tactics: list[str]) -> list[int]:
    indices = [
        idx
        for idx, tactic in enumerate(tactics, start=1)
        if is_product_budget_seq(tactic)
    ]
    return list(reversed(indices))


def latest_seq_tactic(tactics: list[str]) -> dict[str, Any]:
    for idx in range(len(tactics), 0, -1):
        tactic = str(tactics[idx - 1] or "").strip()
        if tactic_head(tactic) == "seq":
            return {"tactic_index": idx, "tactic": tactic}
    return {}


def latest_call_tactic(tactics: list[str]) -> dict[str, Any]:
    for idx in range(len(tactics), 0, -1):
        tactic = str(tactics[idx - 1] or "").strip()
        if tactic_head(tactic) == "call":
            return {"tactic_index": idx, "tactic": tactic}
    return {}


def rewind_leaves_current_call_scope(
    tactics: list[str],
    tactic_index: int,
) -> bool:
    latest_call = latest_call_tactic(tactics)
    call_idx = int(latest_call.get("tactic_index") or 0)
    return bool(call_idx and int(tactic_index) < call_idx)


def structural_recovery_available(tactics: list[str]) -> bool:
    latest_seq = latest_seq_tactic(tactics)
    latest_call = latest_call_tactic(tactics)
    seq_idx = int(latest_seq.get("tactic_index") or 0)
    call_idx = int(latest_call.get("tactic_index") or 0)
    return bool(
        (seq_idx and len(tactics) > seq_idx)
        or (call_idx and len(tactics) > call_idx)
    )


def latest_call_obligation_local_tactic(
    tactics: list[str],
    call_tactic_index: int,
) -> dict[str, Any]:
    for idx in range(len(tactics), int(call_tactic_index), -1):
        tactic = str(tactics[idx - 1] or "").strip()
        if is_call_obligation_local_tactic(tactic):
            return {"tactic_index": idx, "tactic": tactic}
    return {}


def is_call_obligation_local_tactic(tactic: str) -> bool:
    text = str(tactic or "").strip().lower()
    head = tactic_head(text)
    if head in {
        "seq",
        "case",
        "if",
        "while",
        "wp",
        "sp",
        "inline",
        "rcondt",
        "rcondf",
        "rnd",
        "swap",
        "conseq",
        "smt",
        "auto",
    }:
        return True
    return bool(re.search(r"\binline\b", text))


def latest_inline_boundary(
    tactics: list[str],
    *,
    start_index: int = 1,
) -> dict[str, Any]:
    latest_inline: dict[str, Any] = {}
    for idx in range(len(tactics), 0, -1):
        if idx < max(1, int(start_index)):
            break
        tactic = str(tactics[idx - 1] or "").strip()
        text = tactic.lower()
        if not re.search(r"\binline\b", text):
            continue
        broad = is_broad_inline_tactic(text)
        if broad:
            return {
                "tactic_index": idx,
                "tactic": tactic,
                "broad": True,
            }
        if not latest_inline:
            latest_inline = {
                "tactic_index": idx,
                "tactic": tactic,
                "broad": False,
            }
    return latest_inline


def outer_structural_boundary_indices(tactics: list[str]) -> list[int]:
    indices: list[int] = []
    for idx, tactic in enumerate(tactics, start=1):
        text = str(tactic or "").strip().lower()
        head = tactic_head(tactic)
        if (
            "call (_:" in text
            or head in {"call", "seq", "while", "if"}
            or is_product_budget_seq(tactic)
        ):
            indices.append(idx)
    return list(reversed(indices))


def replaceable_checkpoint_for_outer_boundary(
    selected: list[int],
    tactics: list[str],
    overrides: dict[int, dict[str, Any]],
) -> int:
    outer = set(outer_structural_boundary_indices(tactics))
    for idx in list(selected):
        if idx in outer:
            continue
        if idx in overrides:
            continue
        return idx
    return 0


def restored_layer_for_tactic(tactic: str) -> str:
    head = tactic_head(tactic)
    text = tactic.strip().lower()
    if head == "seq":
        return "pre_seq_cut"
    if head == "inline" or re.search(r"\binline\b", text):
        return "pre_inline_frontier"
    if head == "wp":
        return "pre_wp_frontier"
    if head == "call":
        return "pre_call_frontier"
    if head in {"sp", "swap"}:
        return "pre_frontier_movement"
    if head in {"if", "while"}:
        return "pre_branch_or_loop"
    return "previous_committed_state"


def undo_scope_for_tactic(tactic: str) -> str:
    head = tactic_head(tactic)
    text = tactic.strip().lower()
    if head == "seq":
        return "seq_local"
    if head == "inline" or re.search(r"\binline\b", text):
        return "call_site_boundary"
    if head in {"wp", "sp", "swap", "rcondt", "rcondf", "rnd", "conseq"}:
        return "branch_local"
    if head in {"call", "while", "if"}:
        return "structural_boundary"
    return "recent_step"


def is_structural_tactic(tactic: str) -> bool:
    text = tactic.strip().lower()
    structural = r"\b(call|inline|seq|while|if|sp|wp|swap|rcondt|rcondf|rnd|conseq)\b"
    if re.search(structural, text):
        return True
    head = tactic_head(tactic)
    return head in {"call", "inline", "seq", "while", "if", "proc", "sp", "wp"}


def checkpoint_label_for_tactic(tactic: str, tactic_index: int) -> str:
    text = tactic.strip().lower()
    if "call (_:" in text:
        return f"Before call invariant #{tactic_index}"
    if text.startswith("while"):
        return f"Before while invariant #{tactic_index}"
    if text.startswith("seq"):
        if is_product_budget_seq(tactic):
            return f"Before product-budget seq cut #{tactic_index}"
        return f"Before seq cut #{tactic_index}"
    if text.startswith("conseq"):
        return f"Before conseq reshape #{tactic_index}"
    if text.startswith("inline") or re.search(r"\binline\b", text):
        return f"Before inline expansion #{tactic_index}"
    return f"Before committed tactic #{tactic_index}"


def checkpoint_semantics(tactic: str) -> dict[str, str]:
    text = tactic.strip().lower()
    head = tactic_head(tactic)
    if "call (_:" in text:
        return {
            "why_checkpoint": (
                "call invariant introduction point; later oracle/branch "
                "obligations often reveal missing preserved facts or an "
                "over-strong equality from this tactic"
            ),
            "repair_use_when": (
                "Use this when the current blocker is an invariant gap, a "
                "bad-event fact that should have been preserved, or a local "
                "surgery problem after a call. Prefer this over fresh restart "
                "when the top-level route still looks right."
            ),
            "after_rewind_next": (
                "Inspect `call_subgoals` or `subgoal_gap`, then commit a "
                "revised `call (_: ...)` invariant or a smaller prefix."
            ),
        }
    if text.startswith("while") or re.search(r"\bwhile\b.*\(", text):
        return {
            "why_checkpoint": "loop invariant introduction point",
            "repair_use_when": (
                "Use this when later loop obligations show a missing variant, "
                "bounds fact, frame fact, or too-strong loop invariant."
            ),
            "after_rewind_next": (
                "Inspect `tactic_forms` for while syntax and `subgoal_gap`, "
                "then commit a revised loop invariant."
            ),
        }
    if text.startswith("seq") or re.search(r"\bseq\s+\d+", text):
        if is_product_budget_seq(tactic):
            return {
                "why_checkpoint": (
                    "product-budget sequence cut / midpoint assertion point; "
                    "later probability residuals often reveal a missing live "
                    "fact or an under-specified budget factor at this cut"
                ),
                "repair_use_when": (
                    "Use this when a probability-budget branch is stuck "
                    "because the cut assertion lacks side facts, generator "
                    "facts, size facts, or the budget ledger was charged to "
                    "the wrong residual."
                ),
                "after_rewind_next": (
                    "Inspect `lemma_hints`, then commit a revised `seq` cut "
                    "with a stronger midpoint assertion and explicit remaining "
                    "budget."
                ),
            }
        return {
            "why_checkpoint": "sequence cut / midpoint assertion point",
            "repair_use_when": (
                "Use this when the current branch is stuck because the cut "
                "assertion lacks live facts, exposes the wrong frontier, or "
                "created residual obligations that should have been part of "
                "the midpoint."
            ),
            "after_rewind_next": (
                "Inspect `align`, then commit a revised `seq` cut with the "
                "missing state facts."
            ),
        }
    if text.startswith("call "):
        return {
            "why_checkpoint": "named call route point",
            "repair_use_when": (
                "Use this if the selected named call lemma or frontier route "
                "was wrong, or the call should have been preceded by a wrapper "
                "or alignment step."
            ),
            "after_rewind_next": (
                "Use `lookup_symbol` or `call_site_options` before committing "
                "the next call route."
            ),
        }
    if text.startswith("inline") or re.search(r"\binline\b", text):
        return {
            "why_checkpoint": "inline expansion point",
            "repair_use_when": (
                "Use this when broad inlining exposed too much code, hid a "
                "call handle, or a targeted inline would keep the proof "
                "frontier cleaner."
            ),
            "after_rewind_next": (
                "Commit a targeted `inline{1}`/`inline{2}` or inspect "
                "`call_site_options` before expanding more code."
            ),
        }
    if text.startswith("rcondt") or text.startswith("rcondf"):
        return {
            "why_checkpoint": "forced-condition surgery point",
            "repair_use_when": (
                "Use this when the forced branch condition was proved with "
                "the wrong facts or later branches show the condition should "
                "be split differently."
            ),
            "after_rewind_next": (
                "Inspect `diagnose`, then commit the opposite condition or a "
                "smaller condition proof."
            ),
        }
    if text.startswith("swap"):
        return {
            "why_checkpoint": "statement-order surgery point",
            "repair_use_when": (
                "Use this when the statement alignment after a swap is worse "
                "or later indexed tactics need a different order."
            ),
            "after_rewind_next": (
                "Inspect `align`, then commit a smaller or differently indexed "
                "`swap`."
            ),
        }
    if text.startswith("conseq"):
        return {
            "why_checkpoint": "postcondition/precondition reshaping point",
            "repair_use_when": (
                "Use this when a later goal shows the consequence statement "
                "dropped a needed fact or kept an obligation too strong."
            ),
            "after_rewind_next": (
                "Inspect `subgoal_gap`, then commit a weaker postcondition or "
                "stronger precondition."
            ),
        }
    if text.startswith("rnd"):
        return {
            "why_checkpoint": "sampling alignment point",
            "repair_use_when": (
                "Use this when one-sided or paired random samples were "
                "coupled in the wrong order."
            ),
            "after_rewind_next": (
                "Inspect `tactic_forms` for `rnd`, `rnd{1}`, or `rnd{2}`, "
                "then commit the smallest sampling alignment step."
            ),
        }
    if head == "sp":
        return {
            "why_checkpoint": "program frontier movement point",
            "repair_use_when": (
                "Use this when the proof consumed too many or too few "
                "statements before a branch/call/sampling frontier."
            ),
            "after_rewind_next": (
                "Inspect `align`, then commit indexed `sp i j` with smaller "
                "counts."
            ),
        }
    if head == "wp":
        return {
            "why_checkpoint": "weakest-precondition frontier movement point",
            "repair_use_when": (
                "Use this when `wp` pushed the proof past useful structure or "
                "created a heavy ambient goal before needed branch/call facts "
                "were preserved."
            ),
            "after_rewind_next": (
                "Commit a smaller indexed `wp`, or inspect `align` / "
                "`tactic_forms` before continuing."
            ),
        }
    if head == "if":
        return {
            "why_checkpoint": "branch split point",
            "repair_use_when": (
                "Use this when the branch split happened before the sides "
                "were aligned or before the branch condition facts were live."
            ),
            "after_rewind_next": (
                "Inspect `align`, then commit a smaller prefix or a conditional "
                "proof with explicit side goals."
            ),
        }
    if head == "proc":
        return {
            "why_checkpoint": "procedure entry point",
            "repair_use_when": (
                "Use this only when the chosen procedure-level route was "
                "wrong, not for a local invariant or branch-surgery problem."
            ),
            "after_rewind_next": (
                "Re-enter the procedure with a different high-level route or "
                "inspect `diagnose` first."
            ),
        }
    return {
        "why_checkpoint": "recent committed tactic",
        "repair_use_when": (
            "Use this when the recent local step appears to have introduced "
            "the current blocker."
        ),
        "after_rewind_next": (
            "Try a smaller replacement step or inspect the current goal "
            "before recommitting."
        ),
    }
