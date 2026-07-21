"""Structural transition descriptors for agent-facing proof moves."""
from __future__ import annotations

import re
from typing import Any

from workflow.proof_management.frame_facts import strip_easycrypt_comments
from core.easycrypt.value_shapes import drop_empty as _drop_empty


def structural_transition_surface(
    tactic: str,
    *,
    status: str,
    submit_intent: str,
    why_here: str = "",
) -> dict[str, Any]:
    descriptor = transition_descriptor(tactic)
    submit: dict[str, Any] = {
        "intent": submit_intent,
        "payload": {"tactic": tactic},
    }
    if descriptor.get("kind") == "closing_or_checking":
        return _drop_empty({
            "id": descriptor.get("id"),
            "kind": descriptor.get("kind"),
            "status": status,
            "tactic": tactic,
            "phase": descriptor.get("phase"),
            "valid_for": "current_view_only",
            "why_here": why_here,
            "decision": (
                "Commit this exact tactic only if you want to try closing or "
                "checking this obligation."
                if submit_intent == "commit_tactic"
                else "Use this candidate only if it matches the intended closing step."
            ),
            "recommended_next": {
                "label": "Commit this exact tactic",
                "submit": submit,
            } if submit_intent == "commit_tactic" else {
                "label": "Use this candidate",
                "submit": submit,
            },
            "after_commit": descriptor.get("after_commit"),
            "if_wrong_after_commit": descriptor.get("if_wrong"),
        })
    phase = str(descriptor.get("phase") or "post-tactic")
    if submit_intent == "commit_tactic":
        decision = (
            f"Commit this exact accepted tactic only if you want to enter the "
            f"{phase} phase."
        )
        label = "Enter this transition"
    else:
        decision = f"Use this candidate only if you want to enter the {phase} phase."
        label = "Use this transition"
    return _drop_empty({
        "id": descriptor.get("id"),
        "kind": "structural_transition",
        "status": status,
        "tactic": tactic,
        "phase": phase,
        "valid_for": "current_view_only",
        "why_here": why_here,
        "decision": decision,
        "recommended_next": {
            "label": label,
            "submit": submit,
        },
        "after_commit": descriptor.get("after_commit"),
        "if_wrong_after_commit": descriptor.get("if_wrong"),
    })


def transition_descriptor(tactic: str) -> dict[str, str]:
    text = normalize_tactic_for_transition(tactic)
    if matches_tactic_head(text, ("smt", "auto", "done", "trivial")):
        return {
            "id": "closing_or_checking",
            "kind": "closing_or_checking",
            "phase": "closing/checking",
            "after_commit": (
                "This is a closing/checking step; it may close the current "
                "goal or expose the next remaining goal, but it does not "
                "promise a new surgery workbench."
            ),
            "if_wrong": (
                "Use `undo_last_step` if the committed closing/checking step "
                "does not match the intended route."
            ),
        }
    if re.search(r"\bcall\s*\(_:", text):
        return _transition_descriptor(
            "call_obligations",
            "call-obligation and invariant-subgoal",
            extra=(
                "The next view should show the real call obligations or "
                "residual invariant subgoals."
            ),
        )
    if matches_tactic_head(text, ("byequiv", "byphoare", "phoare", "hoare")):
        return _transition_descriptor(
            "proof_family_workbench",
            "chosen proof-family",
            extra=(
                "The next view should expose the authoritative workbench for "
                "the selected proof family."
            ),
        )
    if matches_tactic_head(text, ("proc",)):
        return _transition_descriptor(
            "procedure_body_frontier",
            "procedure-body frontier",
            extra=(
                "The next view should expose the real procedure frontier and "
                "program-structure handles."
            ),
        )
    if matches_tactic_head(text, ("inline",)):
        return _transition_descriptor(
            "lower_level_procedure_workbench",
            "lower-level procedure",
            extra=(
                "The next view should expose lower-level procedure statements; "
                "`inline *` may erase live call handles, so commit it only if "
                "that descent is intended."
            ),
        )
    if matches_tactic_head(text, ("wp",)):
        return _transition_descriptor(
            "post_wp_surgery",
            "post-wp surgery",
            extra=(
                "The next authoritative view will expose the real post-wp "
                "surgery workbench, so you do not need to mentally simulate "
                "now what will happen."
            ),
        )
    if matches_tactic_head(text, ("sp",)):
        return _transition_descriptor(
            "prefix_consumed_alignment",
            "prefix-consumed alignment",
            extra=(
                "The next view should show the frontier after the prefix is "
                "consumed, including any alignment or branch handles."
            ),
        )
    if matches_tactic_head(text, ("seq", "case", "if", "while")):
        return _transition_descriptor(
            "split_branch_or_loop_obligations",
            "split/branch/loop-obligation",
            extra=(
                "The next view should show the resulting branch, split, or "
                "loop obligations."
            ),
        )
    if matches_tactic_head(
        text,
        ("rcondt", "rcondf", "swap", "conseq", "rnd", "eager"),
    ):
        return _transition_descriptor(
            "prhl_mid_surgery",
            "pRHL mid-surgery",
            extra=(
                "The next view should expose the real pRHL mid-surgery "
                "workbench for the updated frontier."
            ),
        )
    return _transition_descriptor(
        "post_tactic",
        "post-tactic",
        extra=(
            "The next authoritative view will show the real workbench after "
            "this tactic is committed."
        ),
    )


def normalize_tactic_for_transition(tactic: str) -> str:
    text = strip_easycrypt_comments(str(tactic or "")).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.lstrip("+- ").strip()
    return text


def matches_tactic_head(text: str, names: tuple[str, ...]) -> bool:
    for name in names:
        if re.match(rf"^(?:by\s+)?{re.escape(name)}(?:\b|\{{|\s|\.|;|\()", text):
            return True
    return False


def is_broad_inline_tactic(text: str) -> bool:
    return bool(re.search(r"\binline(?:\{[12]\})?\s+\*", str(text or "")))


def _transition_descriptor(
    transition_id: str,
    phase: str,
    *,
    extra: str,
) -> dict[str, str]:
    return {
        "id": transition_id,
        "kind": "structural",
        "phase": phase,
        "after_commit": extra,
        "if_wrong": (
            "Use `undo_last_step` or `undo_to_checkpoint` if the committed "
            "route is wrong."
        ),
    }

