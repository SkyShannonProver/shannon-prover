"""Pr-level path planner for probability proof states.

This pass treats Pr rewrite and bound lemmas as a small graph over game names.
It answers a compiler-style question: before lowering into pRHL/procedure code,
is there a low-cost path through known Pr handles from the current source game
to the target game?

The pass is intentionally conservative.  It plans lemma order and edge
direction, but it does not claim a runnable EasyCrypt tactic unless another
pass has resolved and probed the exact lemma instantiation.
"""
from __future__ import annotations

import re
from collections import deque
from typing import Any

from core.easycrypt.analysis.ec_utils import (
    as_dict as _dict,
    dedupe_present_strings as _dedupe_strings,
    int_or_default as _int_or_default,
)
from core.easycrypt.analysis.ec_pr_canonical import (
    game_key as _game_key,
    pr_game_keys_from_text as _pr_game_keys_from_text,
    pr_terms_with_spans as _pr_terms_with_spans,
)
from core.easycrypt.analysis.ec_pr_obligations import (
    classify_pr_arithmetic_shape as _classify_pr_arithmetic_shape,
)


PR_PATH_PLANNER_SCHEMA_VERSION = 1
PR_PATH_PLANNER_KIND = "easycrypt_pr_path_plan"
MAX_PR_EQUALITY_PATH_HOPS = 10
MAX_PR_INEQUALITY_PATH_HOPS = 6
MAX_PR_FRONTIER_HOPS = 5


def build_pr_path_plan(parsed_goal: dict[str, Any]) -> dict[str, Any]:
    """Build a graph/path plan for Pr-level proof handles."""
    parsed = _dict(parsed_goal)
    if str(parsed.get("goal_type") or "") != "probability":
        return _empty_plan("not_probability")

    endpoints = _goal_endpoints(parsed)
    edges = _candidate_edges(parsed)
    arithmetic_plan = _arithmetic_plan(parsed)
    paths = []
    for idx, endpoint in enumerate(endpoints):
        path = _plan_endpoint(endpoint, edges)
        path["endpoint_index"] = idx
        paths.append(path)
    complete = [path for path in paths if path.get("status") == "complete"]
    recommended = min(
        complete,
        key=lambda path: (
            int(path.get("cost") or 9999),
            int(path.get("hop_count") or 9999),
            _int_or_default(path.get("endpoint_index"), 9999),
            str(path.get("endpoint_id") or ""),
        ),
        default=None,
    )
    partial_paths = _partial_paths(endpoints, paths, edges)
    return {
        "schema_version": PR_PATH_PLANNER_SCHEMA_VERSION,
        "kind": PR_PATH_PLANNER_KIND,
        "goal_form": str(parsed.get("prob_form") or ""),
        "endpoints": endpoints,
        "edges": edges,
        "paths": paths,
        "partial_paths": partial_paths,
        "recommended_path": recommended,
        "arithmetic_plan": arithmetic_plan,
        "summary": {
            "endpoint_count": len(endpoints),
            "edge_count": len(edges),
            "complete_path_count": len(complete),
            "partial_path_count": len(partial_paths),
            "has_recommended_path": recommended is not None,
            "has_arithmetic_plan": bool(arithmetic_plan.get("available")),
            "arithmetic_candidate_count": len(
                _candidate_dicts(arithmetic_plan.get("candidate_lemmas"))
            ),
            "pr_rewrite_edge_count": len([
                edge for edge in edges
                if edge.get("edge_kind") == "pr_rewrite"
            ]),
            "have_chain_edge_count": len([
                edge for edge in edges
                if edge.get("edge_kind") == "have_chain"
            ]),
        },
    }


def _goal_endpoints(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    form = str(parsed.get("prob_form") or "")
    endpoints: list[dict[str, Any]] = []

    def add(endpoint_id: str, relation: str, source: str, target: str) -> None:
        source_key = _game_key(source)
        target_key = _game_key(target)
        if not source_key or not target_key or source_key == target_key:
            return
        endpoints.append({
            "id": endpoint_id,
            "relation": relation,
            "source_game": source,
            "target_game": target,
            "source_key": source_key,
            "target_key": target_key,
        })

    if form == "diff_eq":
        add(
            "diff_eq.pos",
            "equality",
            str(parsed.get("lhs_pos_game") or parsed.get("lhs_game") or ""),
            str(parsed.get("rhs_pos_game") or parsed.get("rhs_game") or ""),
        )
        add(
            "diff_eq.neg",
            "equality",
            str(parsed.get("lhs_neg_game") or ""),
            str(parsed.get("rhs_neg_game") or ""),
        )
    elif form in {"eq", "adv_eq"}:
        lhs = str(parsed.get("lhs_game") or "")
        rhs = str(parsed.get("rhs_game") or "")
        games = _pr_game_keys_from_text(_probability_goal_text(parsed))
        if len(games) >= 2:
            if not lhs or _is_root_only_game(lhs):
                lhs = games[0]
            if not rhs or _is_root_only_game(rhs):
                rhs = games[1]
        add(
            f"{form}.main",
            "equality",
            lhs,
            rhs,
        )
    elif form in {"ineq", "adv_ineq"}:
        add(
            f"{form}.bound",
            "inequality",
            str(parsed.get("lhs_game") or ""),
            str(parsed.get("rhs_game") or ""),
        )
    elif form == "adv_diff_ineq":
        add(
            "adv_diff_ineq.main",
            "inequality",
            str(parsed.get("lhs_game") or ""),
            str(parsed.get("rhs_game") or ""),
        )
    elif form == "compound":
        lhs_addends = _candidate_dicts(parsed.get("lhs_addends"))
        rhs_addends = _candidate_dicts(parsed.get("rhs_addends"))
        if lhs_addends and len(lhs_addends) == len(rhs_addends):
            for idx, (left, right) in enumerate(
                zip(lhs_addends, rhs_addends),
                start=1,
            ):
                add(
                    f"compound.addend.{idx}",
                    "equality",
                    _addend_game(left),
                    _addend_game(right),
                )
    return endpoints


def _is_root_only_game(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and "(" not in text and "." not in text


def _candidate_edges(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for candidate in _candidate_dicts(parsed.get("pr_rewrite_candidates")):
        name = _candidate_name(candidate)
        lhs = _game_key(candidate.get("lhs_game"))
        rhs = _game_key(candidate.get("rhs_game"))
        if not name or not lhs or not rhs or lhs == rhs:
            continue
        edges.append(_edge(
            name=name,
            edge_kind="pr_rewrite",
            relation="equality",
            source=lhs,
            target=rhs,
            direction="forward",
            action_hint=f"rewrite {name}.",
            raw_candidate=candidate,
        ))
        edges.append(_edge(
            name=name,
            edge_kind="pr_rewrite",
            relation="equality",
            source=rhs,
            target=lhs,
            direction="backward",
            action_hint=f"rewrite -{name}.",
            raw_candidate=candidate,
        ))

    for candidate in _candidate_dicts(parsed.get("have_chain_candidates")):
        name = _candidate_name(candidate)
        lhs = _game_key(candidate.get("lhs_game"))
        rhs = _game_key(candidate.get("rhs_game"))
        if not name or not lhs or not rhs or lhs == rhs:
            continue
        edges.append(_edge(
            name=name,
            edge_kind="have_chain",
            relation="inequality",
            source=lhs,
            target=rhs,
            direction="forward",
            action_hint=f"use bound lemma `{name}` for {lhs} <= {rhs}",
            raw_candidate=candidate,
        ))
    for resolved in _candidate_dicts(parsed.get("resolved_name_items")):
        edges.extend(_resolved_item_edges(resolved))
    for candidate in _candidate_dicts(parsed.get("synthetic_pr_bridge_candidates")):
        edge = _synthetic_bridge_edge(candidate)
        if edge:
            edges.append(edge)
    for candidate in _candidate_dicts(parsed.get("instantiated_pr_rewrite_candidates")):
        name = _candidate_name(candidate)
        lhs = _game_key(candidate.get("lhs_game"))
        rhs = _game_key(candidate.get("rhs_game"))
        if not name or not lhs or not rhs or lhs == rhs:
            continue
        edges.append(_edge(
            name=name,
            edge_kind="pr_rewrite",
            relation="equality",
            source=lhs,
            target=rhs,
            direction="forward",
            action_hint=str(candidate.get("action_hint") or f"rewrite {name}."),
            raw_candidate=candidate,
        ))
        edges.append(_edge(
            name=name,
            edge_kind="pr_rewrite",
            relation="equality",
            source=rhs,
            target=lhs,
            direction="backward",
            action_hint=str(candidate.get("backward_action_hint") or f"rewrite -{name}."),
            raw_candidate=candidate,
        ))
    return _dedupe_edges(edges)


def _synthetic_bridge_edge(candidate: dict[str, Any]) -> dict[str, Any]:
    name = _candidate_name(candidate)
    lhs = _game_key(
        candidate.get("lhs_game")
        or candidate.get("source_game")
        or candidate.get("source")
    )
    rhs = _game_key(
        candidate.get("rhs_game")
        or candidate.get("target_game")
        or candidate.get("target")
    )
    if not name or not lhs or not rhs or lhs == rhs:
        return {}
    return _edge(
        name=name,
        edge_kind=str(candidate.get("edge_kind") or "synthetic_bridge"),
        relation=str(candidate.get("relation") or "equality"),
        source=lhs,
        target=rhs,
        direction=str(candidate.get("direction") or "forward"),
        action_hint=str(
            candidate.get("action_hint")
            or candidate.get("tactic")
            or f"bridge {lhs} to {rhs}"
        ),
        raw_candidate=candidate,
    )


def _arithmetic_plan(parsed: dict[str, Any]) -> dict[str, Any]:
    """Classify Pr arithmetic obligations that need a have-chain pipeline.

    EasyCrypt already has native support for probability expressions and
    upto-bad style probability rewrites.  This planner does not reimplement
    those tactics; it tells the prover when the current Pr goal is still an
    arithmetic/bound composition problem and which resolved declarations look
    like the pieces of that composition.
    """
    goal_text = _probability_goal_text(parsed)
    shape = _classify_pr_arithmetic_shape(
        parsed,
        goal_text,
        min_probability_inequality_pr_terms=2,
    )
    if not shape:
        return {"available": False, "reason": "not_pr_arithmetic_shape"}

    goal_games = _goal_game_keys(parsed, goal_text)
    candidates = _arithmetic_candidates(parsed, goal_games)
    if not candidates:
        return {
            "available": False,
            "reason": "no_probability_bound_candidates",
            "shape": shape,
            "goal_pr_games": goal_games,
            "candidate_lemmas": [],
            "recommended_chain": [],
            "native_ec_support": _native_support_for_shape(shape),
            "finish_tactics": _finish_tactics_for_arithmetic(goal_text, []),
            "strategy": _arithmetic_strategy_text(shape, []),
        }

    ordered = sorted(
        candidates,
        key=lambda item: (
            _arithmetic_role_rank(str(item.get("role") or ""), shape),
            -int(item.get("overlap_score") or 0),
            int(item.get("premise_count") or 0),
            str(item.get("name") or ""),
        ),
    )
    chain = [
        str(item.get("name") or "")
        for item in ordered[:6]
        if str(item.get("name") or "")
    ]
    return {
        "available": True,
        "shape": shape,
        "goal_pr_games": goal_games,
        "candidate_lemmas": ordered[:10],
        "recommended_chain": chain,
        "native_ec_support": _native_support_for_shape(shape),
        "finish_tactics": _finish_tactics_for_arithmetic(goal_text, ordered),
        "strategy": _arithmetic_strategy_text(shape, chain),
    }


def _probability_goal_text(parsed: dict[str, Any]) -> str:
    for key in ("goal_text", "raw_text", "active_goal_preview", "preview"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value
    parts: list[str] = []
    for key in (
        "lhs_expr",
        "rhs_expr",
        "lhs_game",
        "rhs_game",
        "lhs_pos_game",
        "rhs_pos_game",
        "lhs_neg_game",
        "rhs_neg_game",
    ):
        value = str(parsed.get(key) or "").strip()
        if value:
            parts.append(value)
    return " ".join(parts)


def _goal_game_keys(parsed: dict[str, Any], goal_text: str) -> list[str]:
    games = _pr_game_keys_from_text(goal_text)
    for key in (
        "lhs_game",
        "rhs_game",
        "lhs_pos_game",
        "rhs_pos_game",
        "lhs_neg_game",
        "rhs_neg_game",
    ):
        game = _game_key(parsed.get(key))
        if game and game not in games:
            games.append(game)
    for key in ("lhs_addends", "rhs_addends"):
        for addend in _candidate_dicts(parsed.get(key)):
            game = _game_key(_addend_game(addend))
            if game and game not in games:
                games.append(game)
    return games


def _arithmetic_candidates(
    parsed: dict[str, Any],
    goal_games: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in _candidate_dicts(parsed.get("resolved_name_items")):
        candidate = _arithmetic_candidate_from_resolved(item, goal_games)
        if not candidate:
            continue
        key = (str(candidate.get("name") or ""), str(candidate.get("role") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    for item in _candidate_dicts(parsed.get("have_chain_candidates")):
        name = _candidate_name(item)
        if not name:
            continue
        lhs = _game_key(item.get("lhs_game"))
        rhs = _game_key(item.get("rhs_game"))
        games = [game for game in (lhs, rhs) if game]
        key = (name, "probability_bound")
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name": name,
            "role": "probability_bound",
            "source_kind": str(item.get("source_kind") or "parsed_candidate"),
            "handle_kind": "have_chain",
            "relation": "inequality",
            "pr_games": games,
            "overlap_score": _overlap_score(games, goal_games),
            "premise_count": 0,
            "requires_lossless_premise": False,
            "argument_risks": [],
        })
    return out


def _arithmetic_candidate_from_resolved(
    item: dict[str, Any],
    goal_games: list[str],
) -> dict[str, Any]:
    name = _candidate_name(item)
    declaration = str(item.get("declaration") or "")
    if not name or "Pr[" not in declaration:
        return {}
    role = _declaration_arithmetic_role(declaration, str(item.get("handle_kind") or ""))
    if not role:
        return {}
    games = _pr_game_keys_from_text(declaration)
    slots = _candidate_dicts(item.get("parameter_slots"))
    argument_risks = [
        str(slot.get("slot_role") or slot.get("kind") or slot.get("name") or "argument")
        for slot in slots
        if isinstance(slot, dict)
        and str(slot.get("slot_role") or slot.get("kind") or slot.get("name") or "")
    ]
    return {
        "name": name,
        "role": role,
        "source_kind": str(item.get("source_kind") or ""),
        "handle_kind": str(item.get("handle_kind") or ""),
        "relation": "inequality" if role.endswith("_bound") else "equality",
        "pr_games": games,
        "overlap_score": _overlap_score(games, goal_games),
        "premise_count": _premise_count(declaration),
        "requires_lossless_premise": bool(re.search(r"\bislossless\b", declaration)),
        "argument_risks": argument_risks,
    }


def _declaration_arithmetic_role(declaration: str, handle_kind: str) -> str:
    text = re.sub(r"\s+", " ", declaration)
    has_pr = "Pr[" in text
    has_le = "<=" in text or "`<=" in text
    has_eq = bool(re.search(r"(?<![<=>])=(?!=|>)", text))
    has_abs_diff = ("`|" in text or "|" in text) and "-" in text
    if has_pr and has_le and has_abs_diff:
        return "advantage_bound"
    if has_pr and has_le:
        return "probability_bound"
    if has_pr and has_eq:
        return "probability_rewrite"
    if handle_kind == "have_chain" and has_pr:
        return "probability_bound"
    return ""


def _arithmetic_role_rank(role: str, shape: str) -> int:
    if shape == "absolute_pr_difference_bound":
        return {
            "advantage_bound": 0,
            "probability_bound": 1,
            "probability_rewrite": 2,
        }.get(role, 5)
    return {
        "probability_bound": 0,
        "advantage_bound": 1,
        "probability_rewrite": 2,
    }.get(role, 5)


def _overlap_score(games: list[str], goal_games: list[str]) -> int:
    if not games or not goal_games:
        return 0
    goal_set = set(goal_games)
    return sum(1 for game in games if game in goal_set)


def _premise_count(declaration: str) -> int:
    before_conclusion = declaration.split(":", 1)[-1].split("=>", 1)[0]
    return len(re.findall(r"\bforall\b|\bislossless\b|->", before_conclusion))


def _native_support_for_shape(shape: str) -> list[str]:
    support = [
        "EasyCrypt represents Pr expressions natively; bound lemmas are route context when they match the outer shape.",
    ]
    if shape in {"additive_pr_inequality", "absolute_pr_difference_bound"}:
        support.append(
            "EasyCrypt has native probability-rewrite/upto-bad support for Pr[_] <= Pr[_] + Pr[_] style shapes.",
        )
    if shape == "absolute_pr_difference_bound":
        support.append(
            "Triangle/absolute-difference real-order lemmas are relevant when they reduce the displayed bound.",
        )
    return support


def _finish_tactics_for_arithmetic(
    goal_text: str,
    candidates: list[dict[str, Any]],
) -> list[str]:
    joined = " ".join(
        [goal_text]
        + [str(item.get("name") or "") for item in candidates]
    )
    tactics = ["smt()."]
    if re.search(r"\bmu\b|mu_", joined):
        tactics.insert(0, "smt(mu_bounded).")
    if re.search(r"\^|\*|\bReal\b|\bint\b", joined):
        tactics.insert(0, "ring.")
    return _dedupe_strings(tactics)


def _arithmetic_strategy_text(shape: str, chain: list[str]) -> str:
    if chain:
        return (
            f"For the {shape}, bound lemmas are route context: "
            + " -> ".join(chain)
            + "."
        )
    return (
        f"For the {shape}, matching bound lemmas are route context only "
        "if they reduce the displayed Pr shape."
    )


def _resolved_item_edges(item: dict[str, Any]) -> list[dict[str, Any]]:
    name = _candidate_name(item)
    declaration = str(item.get("declaration") or "")
    if not name or not declaration:
        return []
    handle_kind = str(item.get("handle_kind") or "")
    if handle_kind not in {"pr_rewrite", "have_chain", "addend_equiv"}:
        return []
    if handle_kind == "pr_rewrite":
        return _resolved_pr_rewrite_edges(name, declaration, item)
    return _resolved_have_chain_edges(name, declaration, item)


def _resolved_pr_rewrite_edges(
    name: str,
    declaration: str,
    item: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block_name, source, target in _simple_pr_equality_edges_from_declaration(
        declaration,
        fallback_name=name,
    ):
        if not source or not target or source == target:
            continue
        raw = {
            "name": block_name,
            "lhs_game": source,
            "rhs_game": target,
            "source_kind": str(item.get("source_kind") or ""),
        }
        out.append(_edge(
            name=block_name,
            edge_kind="pr_rewrite",
            relation="equality",
            source=source,
            target=target,
            direction="forward",
            action_hint=f"rewrite {block_name}.",
            raw_candidate=raw,
        ))
        out.append(_edge(
            name=block_name,
            edge_kind="pr_rewrite",
            relation="equality",
            source=target,
            target=source,
            direction="backward",
            action_hint=f"rewrite -{block_name}.",
            raw_candidate=raw,
        ))
    return out


def _resolved_have_chain_edges(
    name: str,
    declaration: str,
    item: dict[str, Any],
) -> list[dict[str, Any]]:
    games = _pr_game_keys_from_text(declaration)
    if len(games) < 2:
        return []
    relation = "inequality" if "<=" in declaration or "`<=" in declaration else "equality"
    edge_kind = "have_chain"
    source, target = games[0], games[1]
    if not source or not target or source == target:
        return []
    raw = {
        "name": name,
        "lhs_game": source,
        "rhs_game": target,
        "source_kind": str(item.get("source_kind") or ""),
    }
    out = [_edge(
        name=name,
        edge_kind=edge_kind,
        relation=relation,
        source=source,
        target=target,
        direction="forward",
        action_hint=f"use bound lemma `{name}` for {source} <= {target}",
        raw_candidate=raw,
    )]
    if relation == "equality":
        out.append(_edge(
            name=name,
            edge_kind=edge_kind,
            relation=relation,
            source=target,
            target=source,
            direction="backward",
            action_hint=f"use equality lemma `{name}` for {target} = {source}",
            raw_candidate=raw,
        ))
    return out


def _simple_pr_equality_edges_from_declaration(
    declaration: str,
    *,
    fallback_name: str,
) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for block in _declaration_blocks(declaration):
        pair = _simple_pr_equality_pair_from_block(block)
        if not pair:
            continue
        block_name = _declaration_block_name(block) or fallback_name
        if not block_name:
            continue
        out.append((block_name, pair[0], pair[1]))
    return out


def _simple_pr_equality_pair_from_block(block: str) -> tuple[str, str] | None:
    text = str(block or "")
    if "Pr[" not in text or "<=" in text or "`<=" in text:
        return None
    if ">=" in text or "`>=" in text:
        return None
    if not re.search(r"(?<![<>=])=(?!=|>)", text):
        return None
    terms = _pr_terms_with_spans(text)
    if len(terms) != 2:
        return None
    between = text[terms[0][2]:terms[1][1]]
    if not re.fullmatch(r"\s*=\s*", between):
        return None
    after = text[terms[1][2]:].strip().rstrip(".").strip()
    if after and not re.fullmatch(r"(?:\)|\])*\s*", after):
        return None
    return (terms[0][0], terms[1][0])


def _declaration_blocks(declaration: str) -> list[str]:
    text = str(declaration or "")
    if not text.strip():
        return []
    starts = list(re.finditer(
        r"(?:\(\*\s*[A-Za-z_][A-Za-z0-9_'.]*\s*\*\)\s*)?"
        r"\b(?:local\s+)?(?:lemma|axiom|theorem)\s+"
        r"[A-Za-z_][A-Za-z0-9_']*\b",
        text,
    ))
    if len(starts) <= 1:
        return [text]
    out: list[str] = []
    for idx, match in enumerate(starts):
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        block = text[match.start():end].strip()
        if block:
            out.append(block)
    return out or [text]


def _declaration_block_name(block: str) -> str:
    text = str(block or "")
    alias = re.match(
        r"\s*\(\*\s*([A-Za-z_][A-Za-z0-9_'.]*)\s*\*\)",
        text,
    )
    if alias:
        return alias.group(1)
    match = re.search(
        r"\b(?:local\s+)?(?:lemma|axiom|theorem)\s+"
        r"([A-Za-z_][A-Za-z0-9_']*)\b",
        text,
    )
    return match.group(1) if match else ""


def _edge(
    *,
    name: str,
    edge_kind: str,
    relation: str,
    source: str,
    target: str,
    direction: str,
    action_hint: str,
    raw_candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"{edge_kind}.{name}.{direction}.{source}.{target}",
        "lemma": name,
        "edge_kind": edge_kind,
        "relation": relation,
        "source": source,
        "target": target,
        "direction": direction,
        "action_hint": action_hint,
        "cost": 1 if edge_kind == "pr_rewrite" else 2,
        "raw_candidate": {
            key: str(raw_candidate.get(key) or "")
            for key in (
                "name",
                "lemma",
                "lhs_game",
                "rhs_game",
                "file",
                "source_kind",
                "authority",
                "readiness",
                "binding_status",
                "action_hint",
                "tactic",
                "ec_ground_truth",
                "verified",
            )
            if raw_candidate.get(key)
        },
    }


def _plan_endpoint(
    endpoint: dict[str, Any],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    source = str(endpoint.get("source_key") or "")
    target = str(endpoint.get("target_key") or "")
    relation = str(endpoint.get("relation") or "")
    if not source or not target:
        return _missing_path(endpoint, "missing_endpoint")

    allowed_edges = [
        edge for edge in edges
        if _edge_allowed_for_relation(edge, relation)
    ]
    path = _shortest_path(source, target, allowed_edges, relation)
    if not path:
        return _missing_path(endpoint, "no_pr_path")

    return {
        "endpoint_id": str(endpoint.get("id") or ""),
        "status": "complete",
        "relation": relation,
        "source_key": source,
        "target_key": target,
        "hop_count": len(path),
        "cost": sum(int(edge.get("cost") or 1) for edge in path),
        "lemmas": [str(edge.get("lemma") or "") for edge in path],
        "hops": [_compact_hop(edge) for edge in path],
        "agenda": _path_agenda(path, endpoint, complete=True),
        "next_action": _path_next_action(path, endpoint),
        "saturation_condition": (
            "Pr endpoint path is live; stay at the Pr layer until every "
            "agenda hop is consumed, validated, or rejected by EasyCrypt."
        ),
        "strategy": _strategy_text(path, relation, source, target),
    }


def _shortest_path(
    source: str,
    target: str,
    edges: list[dict[str, Any]],
    relation: str,
    *,
    max_hops: int | None = None,
) -> list[dict[str, Any]]:
    if max_hops is None:
        max_hops = (
            MAX_PR_INEQUALITY_PATH_HOPS
            if relation == "inequality" else
            MAX_PR_EQUALITY_PATH_HOPS
        )
    by_source: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        by_source.setdefault(str(edge.get("source") or ""), []).append(edge)
    queue = deque([(source, [])])
    seen: set[tuple[str, tuple[str, ...]]] = {(source, ())}
    best: list[dict[str, Any]] = []
    while queue:
        node, path = queue.popleft()
        if len(path) > max_hops:
            continue
        if node == target and path and _path_satisfies_relation(path, relation):
            best = path
            break
        if len(path) == max_hops:
            continue
        for edge in by_source.get(node, []):
            nxt = str(edge.get("target") or "")
            lemma_path = tuple(str(hop.get("id") or "") for hop in path + [edge])
            state = (nxt, lemma_path)
            if state in seen:
                continue
            seen.add(state)
            queue.append((nxt, path + [edge]))
    return best


def _partial_paths(
    endpoints: list[dict[str, Any]],
    paths: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    complete_endpoint_ids = {
        str(path.get("endpoint_id") or "")
        for path in paths
        if path.get("status") == "complete"
    }
    out: list[dict[str, Any]] = []
    for endpoint_index, endpoint in enumerate(endpoints):
        endpoint_id = str(endpoint.get("id") or "")
        if endpoint_id in complete_endpoint_ids:
            continue
        relation = str(endpoint.get("relation") or "")
        source = str(endpoint.get("source_key") or "")
        target = str(endpoint.get("target_key") or "")
        if not source or not target:
            continue
        for side, root, opposite in (
            ("source", source, target),
            ("target", target, source),
        ):
            for idx, path in enumerate(
                _frontier_paths(root, opposite, edges, relation)[:2]
            ):
                out.append(_partial_path(endpoint, endpoint_index, side, path, idx))
    out.sort(key=lambda path: (
        _int_or_default(path.get("endpoint_index"), 9999),
        0 if str(path.get("side") or "") == "source" else 1,
        -int(path.get("hop_count") or 0),
        int(path.get("cost") or 9999),
        str(path.get("frontier_key") or ""),
    ))
    return out[:6]


def _frontier_paths(
    root: str,
    opposite: str,
    edges: list[dict[str, Any]],
    relation: str,
    *,
    max_hops: int = MAX_PR_FRONTIER_HOPS,
) -> list[list[dict[str, Any]]]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        if not _edge_allowed_for_relation(edge, relation):
            continue
        by_source.setdefault(str(edge.get("source") or ""), []).append(edge)

    queue = deque([(root, [])])
    seen: set[tuple[str, tuple[str, ...]]] = {(root, ())}
    paths: list[list[dict[str, Any]]] = []
    while queue:
        node, path = queue.popleft()
        if len(path) >= max_hops:
            continue
        for edge in by_source.get(node, []):
            nxt = str(edge.get("target") or "")
            if not nxt or nxt == opposite:
                continue
            visited_nodes = {root}
            for hop in path:
                visited_nodes.add(str(hop.get("source") or ""))
                visited_nodes.add(str(hop.get("target") or ""))
            if nxt in visited_nodes:
                continue
            next_path = path + [edge]
            lemma_path = tuple(str(hop.get("id") or "") for hop in next_path)
            state = (nxt, lemma_path)
            if state in seen:
                continue
            seen.add(state)
            paths.append(next_path)
            queue.append((nxt, next_path))

    paths.sort(key=lambda path: (
        -_frontier_similarity(str(path[-1].get("target") or ""), opposite),
        -len(path),
        sum(int(edge.get("cost") or 1) for edge in path),
        " -> ".join(str(edge.get("lemma") or "") for edge in path),
    ))
    return paths


def _partial_path(
    endpoint: dict[str, Any],
    endpoint_index: int,
    side: str,
    path: list[dict[str, Any]],
    local_index: int,
) -> dict[str, Any]:
    root = str(path[0].get("source") or "") if path else ""
    frontier = str(path[-1].get("target") or "") if path else ""
    opposite_key = (
        str(endpoint.get("target_key") or "")
        if side == "source" else
        str(endpoint.get("source_key") or "")
    )
    lemmas = [str(edge.get("lemma") or "") for edge in path if edge.get("lemma")]
    return {
        "endpoint_id": str(endpoint.get("id") or ""),
        "endpoint_index": endpoint_index,
        "local_index": local_index,
        "status": "partial",
        "side": side,
        "root_key": root,
        "frontier_key": frontier,
        "opposite_key": opposite_key,
        "relation": str(endpoint.get("relation") or ""),
        "hop_count": len(path),
        "cost": sum(int(edge.get("cost") or 1) for edge in path),
        "lemmas": lemmas,
        "hops": [_compact_hop(edge) for edge in path],
        "agenda": _path_agenda(path, endpoint, complete=False),
        "next_action": _path_next_action(path, endpoint),
        "missing_frontier": {
            "from": frontier,
            "to": opposite_key,
            "relation": str(endpoint.get("relation") or ""),
            "repair_class": "add_or_prove_bridge_before_lowering",
        },
        "strategy": _partial_strategy_text(side, root, frontier, opposite_key, lemmas),
    }


def _partial_strategy_text(
    side: str,
    root: str,
    frontier: str,
    opposite: str,
    lemmas: list[str],
) -> str:
    lemma_text = " -> ".join(lemmas) if lemmas else "available Pr handles"
    return (
        f"Pr handles can move the {side} endpoint from {root} to {frontier} "
        f"via {lemma_text}; the remaining frontier to {opposite} still needs "
        "a bridge, have-step, or pRHL proof. Treat this as partial route context."
    )


def _frontier_similarity(left: str, right: str) -> int:
    left_atoms = set(_key_atoms(left))
    right_atoms = set(_key_atoms(right))
    return len(left_atoms & right_atoms)


def _key_atoms(key: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_']*", str(key or ""))


def _edge_allowed_for_relation(edge: dict[str, Any], relation: str) -> bool:
    kind = str(edge.get("edge_kind") or "")
    if relation == "equality":
        return kind in {"pr_rewrite", "synthetic_bridge", "verified_bridge"}
    if relation == "inequality":
        return kind in {"pr_rewrite", "have_chain", "synthetic_bridge", "verified_bridge"}
    return False


def _path_satisfies_relation(path: list[dict[str, Any]], relation: str) -> bool:
    if relation == "equality":
        return all(
            str(edge.get("edge_kind") or "") in {
                "pr_rewrite",
                "synthetic_bridge",
                "verified_bridge",
            }
            for edge in path
        )
    if relation == "inequality":
        return any(str(edge.get("edge_kind") or "") == "have_chain" for edge in path)
    return False


def _missing_path(endpoint: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "endpoint_id": str(endpoint.get("id") or ""),
        "status": "missing",
        "reason": reason,
        "relation": str(endpoint.get("relation") or ""),
        "source_key": str(endpoint.get("source_key") or ""),
        "target_key": str(endpoint.get("target_key") or ""),
        "hop_count": 0,
        "cost": 9999,
        "lemmas": [],
        "hops": [],
        "strategy": "No complete Pr path found from available handles.",
    }


def _compact_hop(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "lemma": str(edge.get("lemma") or ""),
        "edge_kind": str(edge.get("edge_kind") or ""),
        "relation": str(edge.get("relation") or ""),
        "source": str(edge.get("source") or ""),
        "target": str(edge.get("target") or ""),
        "direction": str(edge.get("direction") or ""),
        "action_hint": str(edge.get("action_hint") or ""),
        "readiness": _edge_readiness(edge),
        "authority_rank": _edge_authority_rank(edge),
        "source_kind": str(_dict(edge.get("raw_candidate")).get("source_kind") or ""),
    }


def _path_agenda(
    path: list[dict[str, Any]],
    endpoint: dict[str, Any],
    *,
    complete: bool,
) -> list[dict[str, Any]]:
    agenda: list[dict[str, Any]] = []
    total = len(path)
    for index, edge in enumerate(path, start=1):
        raw = _dict(edge.get("raw_candidate"))
        readiness = _edge_readiness(edge)
        agenda.append({
            "index": index,
            "total": total,
            "phase": "pr_path_hop",
            "endpoint_id": str(endpoint.get("id") or ""),
            "complete_path": complete,
            "lemma": str(edge.get("lemma") or ""),
            "edge_kind": str(edge.get("edge_kind") or ""),
            "relation": str(edge.get("relation") or ""),
            "direction": str(edge.get("direction") or ""),
            "from": str(edge.get("source") or ""),
            "to": str(edge.get("target") or ""),
            "action_hint": str(edge.get("action_hint") or ""),
            "readiness": readiness,
            "action_type": _agenda_action_type(readiness),
            "authority_rank": _edge_authority_rank(edge),
            "source_kind": str(raw.get("source_kind") or ""),
            "required_before_commit": _edge_required_before_commit(edge),
            "why": _agenda_why(edge, endpoint),
        })
    return agenda


def _path_next_action(
    path: list[dict[str, Any]],
    endpoint: dict[str, Any],
) -> dict[str, Any]:
    agenda = _path_agenda(path, endpoint, complete=bool(path))
    return agenda[0] if agenda else {}


def _edge_readiness(edge: dict[str, Any]) -> str:
    raw = _dict(edge.get("raw_candidate"))
    explicit = str(raw.get("readiness") or raw.get("binding_status") or "")
    if explicit:
        return explicit
    hint = str(edge.get("action_hint") or "")
    kind = str(edge.get("edge_kind") or "")
    source_kind = str(raw.get("source_kind") or "")
    if _truthy(raw.get("verified")) or source_kind in {"ec_preflight", "verified_bridge"}:
        return "ec_verified"
    if kind == "synthetic_bridge" and hint and "<" not in hint:
        return "preflight_ready_bridge"
    if kind == "pr_rewrite" and hint.startswith("rewrite ("):
        return "typed_instantiation_candidate"
    if kind == "pr_rewrite" and source_kind in {
        "where_lookup_tool",
        "ec_native_search",
        "native_ast_search",
    }:
        return "signature_known_needs_instantiation"
    if kind == "have_chain":
        return "needs_have_or_apply_form"
    return "needs_signature_check"


def _agenda_action_type(readiness: str) -> str:
    if readiness in {
        "ec_verified",
        "preflight_ready_bridge",
        "typed_instantiation_candidate",
    }:
        return "tactic_candidate_if_current_endpoint_matches"
    if readiness in {"signature_known_needs_instantiation", "needs_have_or_apply_form"}:
        return "inspection_then_strategy"
    return "inspection_action"


def _edge_required_before_commit(edge: dict[str, Any]) -> list[str]:
    readiness = _edge_readiness(edge)
    lemma = str(edge.get("lemma") or "")
    requirements: list[str] = []
    if readiness in {"needs_signature_check", "signature_known_needs_instantiation"}:
        requirements.append(f"resolve exact signature/slots for `{lemma}`")
    if str(edge.get("edge_kind") or "") == "have_chain":
        requirements.append(
            "choose EasyCrypt have/apply/rewrite form for this bound/equality hop"
        )
    if str(edge.get("edge_kind") or "") == "synthetic_bridge":
        requirements.append(
            "the bridge remains an unverified path edge until EasyCrypt accepts a manager commit"
        )
    requirements.append(
        "confirm the current Pr endpoint still matches the displayed `from` term"
    )
    return _dedupe_strings(requirements)


def _agenda_why(edge: dict[str, Any], endpoint: dict[str, Any]) -> str:
    return (
        f"This Pr-route hop moves endpoint "
        f"`{edge.get('source')}` to `{edge.get('target')}` for "
        f"{endpoint.get('id')} when that endpoint is still visible."
    )


def _edge_authority_rank(edge: dict[str, Any]) -> int:
    raw = _dict(edge.get("raw_candidate"))
    source = str(raw.get("source_kind") or "")
    if _truthy(raw.get("ec_ground_truth")) or source in {"ec_preflight", "where_lookup_tool"}:
        return 0
    if source in {"ec_native_search", "native_ast_search", "instantiated_binding"}:
        return 1
    if source in {"local_context", "parsed_candidate"}:
        return 2
    if str(edge.get("edge_kind") or "") == "synthetic_bridge":
        return 3
    return 4


def _strategy_text(
    path: list[dict[str, Any]],
    relation: str,
    source: str,
    target: str,
) -> str:
    lemmas = " -> ".join(str(edge.get("lemma") or "") for edge in path)
    if relation == "equality":
        return f"Rewrite Pr terms along {source} = {target}: {lemmas}."
    return f"Build a Pr have-chain from {source} to {target}: {lemmas}."


def _candidate_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, str) and item:
            out.append({"name": item})
    return out


def _candidate_name(candidate: dict[str, Any]) -> str:
    for key in ("name", "lemma", "lemma_name", "id"):
        value = str(candidate.get(key) or "")
        if value:
            return value
    return ""


def _addend_game(addend: dict[str, Any]) -> str:
    for key in ("game", "game_expr", "pr_game", "lhs_game", "rhs_game"):
        value = str(addend.get(key) or "").strip()
        if value:
            return value
    text = str(addend.get("text") or addend.get("expr") or "").strip()
    return text


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for edge in edges:
        edge_id = str(edge.get("id") or "")
        if not edge_id or edge_id in seen:
            continue
        seen.add(edge_id)
        out.append(edge)
    return out


def _empty_plan(reason: str) -> dict[str, Any]:
    return {
        "schema_version": PR_PATH_PLANNER_SCHEMA_VERSION,
        "kind": PR_PATH_PLANNER_KIND,
        "goal_form": "",
        "endpoints": [],
        "edges": [],
        "paths": [],
        "partial_paths": [],
        "recommended_path": None,
        "arithmetic_plan": {"available": False, "reason": reason},
        "summary": {
            "endpoint_count": 0,
            "edge_count": 0,
            "complete_path_count": 0,
            "partial_path_count": 0,
            "has_recommended_path": False,
            "has_arithmetic_plan": False,
            "arithmetic_candidate_count": 0,
            "pr_rewrite_edge_count": 0,
            "have_chain_edge_count": 0,
            "reason": reason,
        },
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "verified"}


__all__ = [
    "PR_PATH_PLANNER_KIND",
    "PR_PATH_PLANNER_SCHEMA_VERSION",
    "build_pr_path_plan",
]
