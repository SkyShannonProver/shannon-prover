"""PASS 1 — state projection (§3.1): parse the raw goal/history into the
typed projection (layer, goal kind, call sites, destructive moves, PR normal
form) that the later passes build on.

Carved out of ec_proof_ir.py (the funcs reachable ONLY from the projection
entries). Imports only what these funcs use and NOTHING from ec_proof_ir, so
there is no cycle; ec_proof_ir re-exports this module's own defs so
build_proof_ir + consumers see them at the same path unchanged.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

# Pure leaf utilities live in ec_proof_ir_util now (carve step: break the
# import cycle for per-pass modules); the leaves this module's passes use are
# imported below.
from core.easycrypt.analysis.ec_proof_ir_util import (
    _legacy_shape_tactic_templates,
    _list,
    _dict,
)
from core.easycrypt.analysis.ec_utils import (
    looks_like_program_residual as _goal_text_looks_like_program_residual,
)

from core.easycrypt.analysis.ec_pr_obligations import (
    build_pr_normal_form,
)
from core.easycrypt.analysis.ec_procedure_ref import (
    parse_call_statement as _parse_call_statement,
)
from core.easycrypt.analysis.ec_procedure_frontend import (
    procedure_statements_from_pretty_goal as _procedure_statements_from_pretty_goal,
)
from core.easycrypt.analysis.ec_native_state import (
    annotate_program_fallback,
    has_program_fields,
    load_native_goal_fact,
    load_native_program_fact,
    merge_native_goal_fact,
    merge_native_program_fact,
)
from core.easycrypt.analysis.ec_program_ir import (
    build_program_ir,
)


def project_state(
    *,
    session_dir: str | Path | None = None,
    proof_state: dict[str, Any] | None = None,
    current_goal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """PASS 1 — project the raw proof_state/current_goal into the typed state
    the later passes build on: parsed goal (+ native ground-truth merge), goal
    type/text, history-derived destructive moves, program IR, PR normal form,
    call sites, and the latest transition."""
    state = _dict(proof_state)
    goal = _dict(state.get("goal"))
    current = _dict(current_goal)
    parsed = _dict(current.get("parsed_goal"))
    active_goal_hash = str(
        current.get("active_goal_hash")
        or goal.get("active_goal_hash")
        or parsed.get("active_goal_hash")
        or ""
    )
    native_goal = load_native_goal_fact(session_dir, active_goal_hash)
    if native_goal:
        parsed = merge_native_goal_fact(parsed, native_goal)
    native_program = load_native_program_fact(session_dir, active_goal_hash)
    if not native_program and native_goal and has_program_fields(native_goal):
        native_program = native_goal
    if native_program:
        parsed = merge_native_program_fact(parsed, native_program)
    else:
        parsed = annotate_program_fallback(parsed)
    if parsed.get("ec_ground_truth") and parsed.get("goal_type"):
        goal_type = str(parsed.get("goal_type") or "unknown")
    else:
        goal_type = str(
            current.get("goal_type")
            or parsed.get("goal_type")
            or goal.get("goal_type")
            or "unknown"
        )
    goal_text = _goal_text(current, parsed)
    history = _read_history_tactics(session_dir)
    destructive_moves = _destructive_moves(history)
    program_ir = build_program_ir(parsed, goal_type, goal_text=goal_text)
    pr_normal_form = _pr_normal_form(parsed, goal_type, goal_text)
    call_sites = _list(program_ir.get("call_sites"))
    latest_transition = _dict(state.get("latest_transition"))
    return {
        "parsed": parsed,
        "goal_type": goal_type,
        "goal_text": goal_text,
        "destructive_moves": destructive_moves,
        "program_ir": program_ir,
        "pr_normal_form": pr_normal_form,
        "call_sites": call_sites,
        "latest_transition": latest_transition,
    }


def _goal_kind(goal_type: str, parsed: dict[str, Any]) -> str:
    if goal_type == "probability":
        form = str(parsed.get("prob_form") or "")
        if "ineq" in form:
            return "Pr_ineq"
        if form in {"eq", "diff_eq", "adv_eq"} or form.endswith("_eq"):
            return "Pr_eq"
        if form == "compound":
            return "Pr_compound"
        if form == "prob_eq_const":
            return "Pr_eq_const"
        return "Pr"
    if goal_type in {"pRHL", "equiv", "phoare", "hoare", "eager"}:
        return goal_type
    if goal_type == "ambient":
        shape = str(parsed.get("ambient_shape") or "")
        return f"ambient:{shape}" if shape else "ambient"
    return goal_type or "unknown"


def _infer_layer(
    goal_type: str,
    parsed: dict[str, Any],
    *,
    call_sites: list[dict[str, Any]],
    destructive_moves: list[dict[str, Any]],
    goal_text: str = "",
) -> str:
    if goal_type == "probability":
        return "pr"
    if goal_type == "equiv":
        return "prhl_module"
    if goal_type in {"phoare", "hoare", "eager"}:
        if (
            not _has_program_statements(parsed)
            and _suggested_body_transform_available(parsed)
        ):
            return "procedure_body"
        if (
            not _has_program_statements(parsed)
            and any(
                str(item).strip().startswith("proc")
                for item in _legacy_shape_tactic_templates(parsed)
            )
        ):
            return "procedure_entry"
        if not _has_program_statements(parsed) and not any(
            m.get("kind") == "proc" for m in destructive_moves
        ):
            return "procedure_entry"
        return "procedure_body"
    if goal_type == "ambient":
        return "ambient_logic"
    if goal_type == "pRHL":
        if _is_synchronized_prhl_residue(parsed, goal_text, call_sites):
            return "verification_residue"
        if call_sites:
            return "call_site"
        stmt_types = {
            str(stmt.get("type") or "")
            for stmt in _iter_program_statements(parsed)
            if isinstance(stmt, dict)
        }
        if stmt_types & {"ASSIGN", "SAMPLE", "IF", "WHILE", "ASSERT", "ABSTRACT"}:
            return "procedure_body"
        if _procedure_statements_from_pretty_goal(goal_text, goal_type):
            return "procedure_body"
        if _goal_text_looks_like_program_residual(goal_text, goal_type):
            return "procedure_entry"
        if any(m.get("kind") == "inline_all" for m in destructive_moves):
            return "procedure_body"
        return "prhl_module"
    return "unknown"


def _is_synchronized_prhl_residue(
    parsed: dict[str, Any],
    goal_text: str,
    call_sites: list[dict[str, Any]],
) -> bool:
    if call_sites:
        return False
    if any(True for _ in _iter_program_statements(parsed)):
        return False
    text = goal_text or str(parsed.get("raw_text") or "")
    return "[programs are in sync]" in text


def _has_program_statements(parsed: dict[str, Any]) -> bool:
    return any(True for _ in _iter_program_statements(parsed))


def _suggested_body_transform_available(parsed: dict[str, Any]) -> bool:
    for item in _legacy_shape_tactic_templates(parsed):
        tactic = str(item or "").strip().lower()
        if re.match(
            r"^(wp|sp|seq|splitwhile|while|if|rnd|rcondt|rcondf|swap|skip|case\b|case:|conseq|inline)\b",
            tactic,
        ):
            return True
    return False


def _goal_text(current: dict[str, Any], parsed: dict[str, Any]) -> str:
    for key in (
        "active_goal_text",
        "active_goal_preview",
        "raw_current",
        "raw_text",
        "preview",
    ):
        value = current.get(key)
        if isinstance(value, str) and value.strip():
            return value
    value = parsed.get("raw_text")
    return value if isinstance(value, str) else ""


def _pr_normal_form(
    parsed: dict[str, Any],
    goal_type: str,
    goal_text: str,
) -> dict[str, Any]:
    return build_pr_normal_form(parsed, goal_type, goal_text)


def _destructive_moves(history: list[str]) -> list[dict[str, Any]]:
    moves: list[dict[str, Any]] = []
    for idx, tactic in enumerate(history, start=1):
        text = tactic.strip()
        lowered = text.lower()
        if re.search(r"\binline\s+\*", lowered):
            moves.append({
                "tactic_index": idx,
                "kind": "inline_all",
                "tactic": text,
                "effect": "kills all visible call-site handles",
            })
        elif re.search(r"\binline\b", lowered):
            moves.append({
                "tactic_index": idx,
                "kind": "targeted_inline",
                "tactic": text,
                "effect": "lowers selected procedure body",
            })
        if re.search(r"\bproc\b", lowered):
            moves.append({
                "tactic_index": idx,
                "kind": "proc",
                "tactic": text,
                "effect": "opens procedure structure",
            })
        if re.search(r"\b(wp|sp|rnd|seq|while|if)\b", lowered):
            moves.append({
                "tactic_index": idx,
                "kind": "procedure_transform",
                "tactic": text,
                "effect": "rewrites procedure body obligation",
            })
    return moves


def _read_history_tactics(session_dir: str | Path | None) -> list[str]:
    if session_dir is None:
        return []
    path = Path(session_dir) / "history.ec"
    if not path.exists():
        return []
    try:
        return [
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
    except Exception:
        return []


def _iter_program_statements(parsed: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("left_statements", "right_statements"):
        for stmt in _list(parsed.get(key)):
            if isinstance(stmt, dict):
                yield stmt


def _fallback_proc_from_call_text(text: str) -> str:
    call = _parse_call_statement(text, strip_outer=False)
    return call.procedure if call is not None else ""
