"""Probabilistic VC/loss-accounting frontend for EasyCrypt goals.

This module owns goal-shape classification for bounded phoare obligations,
bad-event reductions, query-counter bounds, and final Pr loss accounting.  It
is intentionally a middle-end fact pass: it emits typed obligations and rule
families, not committed tactics.
"""
from __future__ import annotations

import re
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    as_list as _list,
    dedupe_stripped_strings as _dedupe_strings,
    legacy_shape_tactic_templates as _legacy_shape_tactic_templates,
)
from core.easycrypt.analysis.ec_pr_canonical import parse_pr_terms
from core.easycrypt.analysis.ec_pr_obligations import goal_body


PROBABILISTIC_VC_SCHEMA_VERSION = 1
PROBABILISTIC_VC_KIND = "easycrypt_probabilistic_vc_frontend"
_EVENT_TOKEN = r"[A-Za-z_][A-Za-z0-9_'.]*"


def build_probabilistic_vc_frontend(
    parsed: dict[str, Any],
    goal_type: str,
    program_ir: dict[str, Any],
    goal_text: str,
    procedure_frontend: dict[str, Any],
) -> dict[str, Any]:
    """Classify probability/loss-accounting VC structure.

    This lifts common crypto proof shapes into neutral obligations:
    bad-event reductions, query-counter bounds, loop/event preservation,
    bounded phoare sequence cuts, and final Pr loss arithmetic.
    """
    parsed = _dict(parsed)
    body = probabilistic_vc_body(parsed, goal_text)
    if not body:
        return {"available": False, "reason": "empty_goal"}
    pr_terms = probabilistic_vc_pr_terms(body)
    event_terms = probabilistic_vc_event_terms(body)
    counter_terms = probabilistic_vc_counter_terms(body)
    suggested = [
        str(item).strip()
        for item in _legacy_shape_tactic_templates(parsed)
        if str(item).strip()
    ]
    statements = [
        _dict(stmt)
        for stmt in _list(_dict(program_ir).get("statements"))
        if isinstance(stmt, dict)
    ]
    loops = [
        _dict(item)
        for item in _list(_dict(procedure_frontend).get("loop_frontiers"))
        if isinstance(item, dict)
    ]
    branches = [
        _dict(item)
        for item in _list(_dict(procedure_frontend).get("branch_guards"))
        if isinstance(item, dict)
    ]
    samples = [
        _dict(item)
        for item in _list(_dict(procedure_frontend).get("sample_frontiers"))
        if isinstance(item, dict)
    ]
    has_pr_bound = (
        goal_type == "probability"
        and ("<=" in body or "`|" in body)
        and bool(pr_terms)
    )
    has_program_bound = goal_type in {"phoare", "hoare", "pRHL", "equiv", "eager"}
    has_seq_bound = probabilistic_vc_has_seq_bound(suggested, body)
    obligations: list[dict[str, Any]] = []

    if has_pr_bound:
        obligations.append({
            "kind": "pr_loss_accounting",
            "why": (
                "The frontier is a Pr inequality/advantage expression; stay "
                "at Pr layer while composing loss/bad-event lemmas."
            ),
            "evidence": {
                "pr_terms": pr_terms[:4],
                "event_terms": event_terms[:6],
            },
        })
    if event_terms and (has_pr_bound or has_program_bound):
        obligations.append({
            "kind": "bad_event_reduction",
            "why": (
                "The goal mentions bad/win/failure-style events; a proof will "
                "usually preserve the event relation and then bound the event "
                "probability."
            ),
            "evidence": {"event_terms": event_terms[:8]},
        })
    if counter_terms:
        obligations.append({
            "kind": "query_counter_bound",
            "why": (
                "The goal mentions query/counter bounds; expose the counter "
                "invariant before final real arithmetic."
            ),
            "evidence": {"counter_terms": counter_terms[:8]},
        })
    if loops and event_terms:
        obligations.append({
            "kind": "loop_bad_event_bound",
            "why": (
                "A loop frontier and bad-event relation are both visible; the "
                "loop invariant should state event monotonicity/preservation "
                "and any per-iteration loss/counter bound."
            ),
            "evidence": {
                "loops": loops[:3],
                "event_terms": event_terms[:6],
            },
        })
    elif loops and counter_terms:
        obligations.append({
            "kind": "loop_counter_bound",
            "why": (
                "A loop frontier and counter/query terms are visible; the "
                "loop invariant should expose the counter upper bound."
            ),
            "evidence": {
                "loops": loops[:3],
                "counter_terms": counter_terms[:6],
            },
        })
    if has_seq_bound:
        obligations.append({
            "kind": "phoare_seq_bound",
            "why": (
                "The goal/context contains a bounded phoare `seq` shape; use "
                "it as VC generation structure with explicit pre/post and "
                "probability factors, not as a pRHL seq cut."
            ),
            "evidence": {
                "legacy_template_count": len([
                    item for item in suggested if item.startswith("seq")
                ]),
            },
        })
    if branches and event_terms:
        obligations.append({
            "kind": "branch_event_split",
            "why": (
                "Branch guards and event terms are visible; split/control the "
                "branch before proving event preservation on each path."
            ),
            "evidence": {"branches": branches[:3]},
        })
    if samples and (
        has_pr_bound
        or event_terms
        or has_seq_bound
        or goal_type in {"phoare", "hoare"}
    ):
        obligations.append({
            "kind": "sampling_loss_or_coupling",
            "why": (
                "Sampling statements participate in a probability bound; "
                "choose a coupling/lossless/randomness argument and discharge "
                "distribution side conditions."
            ),
            "evidence": {"samples": samples[:4]},
        })

    obligations = dedupe_probabilistic_vc_obligations(obligations)
    if not obligations:
        return {"available": False, "reason": "no_probability_vc_shape"}
    strategy = probabilistic_vc_strategy(obligations, goal_type)
    return {
        "available": True,
        "strategy": strategy,
        "obligations": obligations[:8],
        "event_terms": event_terms[:10],
        "counter_terms": counter_terms[:10],
        "pr_terms": pr_terms[:8],
        "expected_rule_families": probabilistic_vc_rule_families(
            obligations,
            goal_type,
        ),
        "program_signals": {
            "loop_count": len(loops),
            "branch_count": len(branches),
            "sample_count": len(samples),
            "statement_count": len(statements),
        },
        "epistemic_status": "classification_only_not_verified_tactic",
        "source": "goal_shape+program_ir+procedure_frontend",
    }


def probabilistic_vc_body(parsed: dict[str, Any], goal_text: str) -> str:
    parts = [
        str(_dict(parsed).get("raw_text") or ""),
        str(_dict(parsed).get("pre") or ""),
        str(_dict(parsed).get("post") or ""),
        goal_body(goal_text),
    ]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def probabilistic_vc_pr_terms(body: str) -> list[str]:
    out: list[str] = []
    for item in parse_pr_terms(body, require_endpoint=False):
        term = re.sub(r"\s+", " ", str(item.get("pr_text") or "")).strip()
        if term:
            out.append(term)
        if len(out) >= 8:
            break
    return _dedupe_strings(out)


def probabilistic_vc_event_terms(body: str) -> list[str]:
    patterns = [
        _event_keyword_pattern("bad"),
        _event_keyword_pattern("win"),
        _event_keyword_pattern("fail"),
        _event_keyword_pattern("merr"),
        r"!\s*(?:List\.)?uniq\s+[A-Za-z_][A-Za-z0-9_'.]*",
    ]
    out: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, body, flags=re.IGNORECASE):
            term = re.sub(r"\s+", " ", match.group(0)).strip()
            if term:
                out.append(term)
    return _dedupe_strings(out)


def _event_keyword_pattern(keyword: str) -> str:
    return rf"\b(?={_EVENT_TOKEN}\b)(?=[A-Za-z0-9_'.]*{keyword}){_EVENT_TOKEN}\b"


def probabilistic_vc_counter_terms(body: str) -> list[str]:
    out: list[str] = []
    for pattern in (
        r"\b[A-Za-z_][A-Za-z0-9_'.]*(?:counter|count)[A-Za-z0-9_'.]*\b",
        r"\b(?:[A-Za-z_][A-Za-z0-9_']*\.)?[qQ][A-Z][A-Za-z0-9_']*\b",
        r"\bc_[A-Za-z0-9_']+\b",
        r"\b[A-Za-z_][A-Za-z0-9_'.]*\s*<=\s*q[A-Za-z0-9_']*",
        r"\bq[A-Za-z0-9_']*\s*[+*<=]",
    ):
        for match in re.finditer(pattern, body):
            term = re.sub(r"\s+", " ", match.group(0)).strip()
            if term:
                out.append(term)
    return _dedupe_strings(out)


def probabilistic_vc_has_seq_bound(
    suggested: list[str],
    body: str,
) -> bool:
    return any(
        re.match(r"^seq\b.*\b[01]%r\b", item)
        for item in suggested
    ) or bool(re.search(r"\bseq\s+\d+\s*:\s*[^.]*\b[01]%r\b", body))


def dedupe_probabilistic_vc_obligations(
    obligations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for obligation in obligations:
        kind = str(obligation.get("kind") or "")
        if not kind or kind in seen:
            continue
        seen.add(kind)
        out.append(obligation)
    return out


def probabilistic_vc_strategy(
    obligations: list[dict[str, Any]],
    goal_type: str,
) -> str:
    kinds = {str(item.get("kind") or "") for item in obligations}
    if goal_type in {"phoare", "hoare"} and "phoare_seq_bound" in kinds:
        return "bounded phoare VC generation"
    if "loop_bad_event_bound" in kinds:
        return "loop bad-event loss accounting"
    if "query_counter_bound" in kinds:
        return "query-counter loss accounting"
    if "bad_event_reduction" in kinds:
        return "bad-event reduction"
    if "pr_loss_accounting" in kinds:
        return "Pr loss-accounting"
    return f"{goal_type or 'program'} probabilistic VC generation"


def probabilistic_vc_rule_families(
    obligations: list[dict[str, Any]],
    goal_type: str,
) -> list[str]:
    kinds = {str(item.get("kind") or "") for item in obligations}
    rules: list[str] = []
    if "pr_loss_accounting" in kinds:
        rules.extend(["have-chain", "rewrite Pr/mu rules", "real-order smt"])
    if "bad_event_reduction" in kinds:
        rules.extend(["byequiv/bad-event bridge", "event preservation"])
    if "loop_bad_event_bound" in kinds or "loop_counter_bound" in kinds:
        rules.extend(["while invariant", "rcond/case split", "monotonicity"])
    if "phoare_seq_bound" in kinds:
        rules.extend(["byphoare", "phoare seq bound form", "lossless subgoals"])
    if "branch_event_split" in kinds:
        rules.extend(["if/rcondt/rcondf", "branch-local VC"])
    if "sampling_loss_or_coupling" in kinds:
        rules.extend(["rnd coupling", "distribution facts"])
    if goal_type in {"phoare", "hoare"}:
        rules.append("proc/wp before bound subgoals")
    return _dedupe_strings(rules)


__all__ = [
    "PROBABILISTIC_VC_KIND",
    "PROBABILISTIC_VC_SCHEMA_VERSION",
    "build_probabilistic_vc_frontend",
    "dedupe_probabilistic_vc_obligations",
    "probabilistic_vc_body",
    "probabilistic_vc_counter_terms",
    "probabilistic_vc_event_terms",
    "probabilistic_vc_has_seq_bound",
    "probabilistic_vc_pr_terms",
    "probabilistic_vc_rule_families",
    "probabilistic_vc_strategy",
]
