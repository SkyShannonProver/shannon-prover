"""Semantic anchors for prover-facing workspace views.

This module compares two saved ``ProverWorkspaceView`` JSON payloads at the
same proof point.  It is intentionally stricter than a smoke test and less
brittle than raw JSON equality: timestamps, hashes, paths, and added panels are
ignored, while goal identity, required panels, surfaced checkpoint semantics,
route-health signals, and candidate move heads are treated as compatibility
anchors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from workflow.validation.replay_artifacts import dig as _dig
from typing import Any, Iterable


VOLATILE_TOP_LEVEL_KEYS = {
    "surface_profile",
    "debug_refs",
    "kind",
    "view_hash",
    "schema_version",
}

CORE_PANELS = {
    "last_result",
    "proof_status",
    "current_goal",
    "program_frontier",
    "application_context",
    "facts_and_diagnostics",
    "candidate_moves",
    "inspect_lookup_handles",
}

SURFACE_PANELS = {
    "call_site_surface",
    "seq_cut_surface",
    "pure_tail_surface",
    "frame_obligation_ledger",
    "recovery_diagnosis_surface",
    "structural_checkpoints",
    "route_replay_memory",
}

IMPORTANT_PROOF_STATUS_KEYS = {
    "status",
    "remaining_goals",
    "remaining_goals_known",
    "goal_type",
    "view_focus",
    "current_layer",
}


@dataclass(frozen=True)
class AnchorDiff:
    severity: str
    path: str
    message: str
    baseline: Any = None
    candidate: Any = None

    def to_dict(self) -> dict[str, Any]:
        item = {
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }
        if self.baseline is not None:
            item["baseline"] = self.baseline
        if self.candidate is not None:
            item["candidate"] = self.candidate
        return item


def load_view(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"view must be a JSON object: {path}")
    return data


def semantic_fingerprint(view: dict[str, Any]) -> dict[str, Any]:
    """Return the stable, agent-relevant shape of a workspace view."""
    panels = sorted(k for k in view if k not in VOLATILE_TOP_LEVEL_KEYS)
    surface_payloads = _surface_payloads(view)
    surfaces = sorted(k for k, payload in surface_payloads.items() if payload)
    status = _pick_dict(view.get("proof_status"), IMPORTANT_PROOF_STATUS_KEYS)
    goal_lines = _string_list(_dig(view, "current_goal", "lines"))
    candidate = view.get("candidate_moves") if isinstance(view.get("candidate_moves"), dict) else {}
    app_context = view.get("application_context") if isinstance(view.get("application_context"), dict) else {}
    facts = view.get("facts_and_diagnostics") if isinstance(view.get("facts_and_diagnostics"), dict) else {}
    return {
        "panel_keys": panels,
        "core_panels": sorted(k for k in panels if k in CORE_PANELS),
        "surface_panels": surfaces,
        "proof_status": status,
        "goal": _goal_signature(goal_lines),
        "candidate_moves": {
            "keys": sorted(candidate.keys()),
            "move_heads": _candidate_move_heads(candidate),
            "navigation_intents": _navigation_intents(candidate),
            "probe_heads": _probe_heads(candidate),
            "route_health_signals": _route_health_signals(candidate),
        },
        "surface_signals": _surface_signals(surface_payloads),
        "structural_checkpoints": _checkpoint_signature(view.get("structural_checkpoints")),
        "inspect_topics": _inspect_topics(view.get("inspect_lookup_handles")),
        "application_context": {
            "keys": sorted(app_context.keys()),
            "handles": _handle_names(app_context),
        },
        "facts_and_diagnostics": {
            "keys": sorted(facts.keys()),
        },
        "surface_shapes": {
            key: _surface_shape(surface_payloads.get(key))
            for key in surfaces
        },
    }


def _surface_payloads(view: dict[str, Any]) -> dict[str, Any]:
    payloads = {
        key: view.get(key)
        for key in SURFACE_PANELS
        if view.get(key) not in ({}, [], None, "")
    }
    legacy = view.get("rewind_route_memory")
    if (
        "route_replay_memory" not in payloads
        and legacy not in ({}, [], None, "")
    ):
        if isinstance(legacy, dict):
            migrated = dict(legacy)
            migrated["kind"] = "route_replay_memory"
            payloads["route_replay_memory"] = migrated
        else:
            payloads["route_replay_memory"] = legacy
    return payloads


def compare_views(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    require_core_panels: bool = True,
    require_order: bool = False,
) -> dict[str, Any]:
    base_fp = semantic_fingerprint(baseline)
    cand_fp = semantic_fingerprint(candidate)
    diffs: list[AnchorDiff] = []

    if require_core_panels:
        _require_subset(
            diffs,
            "panel_keys",
            sorted(CORE_PANELS.intersection(base_fp["panel_keys"])),
            cand_fp["panel_keys"],
            "core prover-facing panel disappeared",
            severity="blocking",
        )

    _compare_equal(
        diffs,
        "proof_status",
        base_fp["proof_status"],
        cand_fp["proof_status"],
        "proof status changed at the same anchor point",
    )
    _compare_equal(
        diffs,
        "current_goal",
        base_fp["goal"],
        cand_fp["goal"],
        "current goal signature changed at the same anchor point",
    )
    _require_subset(
        diffs,
        "surface_panels",
        base_fp["surface_panels"],
        _compatible_surface_panels(base_fp, cand_fp),
        "surface panel disappeared",
        severity="blocking",
    )
    _require_subset(
        diffs,
        "candidate_moves.move_heads",
        base_fp["candidate_moves"]["move_heads"],
        cand_fp["candidate_moves"]["move_heads"],
        "candidate move head disappeared",
        severity="warning",
    )
    _require_subset(
        diffs,
        "candidate_moves.probe_heads",
        base_fp["candidate_moves"]["probe_heads"],
        cand_fp["candidate_moves"]["probe_heads"],
        "probe alternative head disappeared",
        severity="warning",
    )
    _require_subset(
        diffs,
        "candidate_moves.navigation_intents",
        base_fp["candidate_moves"]["navigation_intents"],
        cand_fp["candidate_moves"]["navigation_intents"],
        "navigation intent disappeared",
        severity="blocking",
    )
    _require_subset(
        diffs,
        "candidate_moves.route_health_signals",
        base_fp["candidate_moves"]["route_health_signals"],
        _compatible_route_health_signals(cand_fp),
        "route-health signal disappeared",
        severity="blocking",
    )
    _require_subset(
        diffs,
        "structural_checkpoints.semantic_ids",
        base_fp["structural_checkpoints"]["semantic_ids"],
        _compatible_structural_checkpoint_ids(cand_fp),
        "structural checkpoint semantic id disappeared",
        severity="blocking",
    )
    _require_subset(
        diffs,
        "inspect_topics",
        base_fp["inspect_topics"],
        cand_fp["inspect_topics"],
        "inspect topic disappeared",
        severity="warning",
    )

    for panel in base_fp["surface_panels"]:
        _require_subset(
            diffs,
            f"surface_shapes.{panel}.keys",
            base_fp["surface_shapes"].get(panel, {}).get("keys", []),
            cand_fp["surface_shapes"].get(panel, {}).get("keys", []),
            f"{panel} top-level evidence key disappeared",
            severity="warning",
        )

    if require_order:
        _check_ordering(diffs, baseline, candidate)

    blocking = [d for d in diffs if d.severity == "blocking"]
    warnings = [d for d in diffs if d.severity == "warning"]
    additive = _additive_summary(base_fp, cand_fp)
    return {
        "status": "fail" if blocking else "pass",
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "diffs": [diff.to_dict() for diff in diffs],
        "additive": additive,
        "baseline_fingerprint": base_fp,
        "candidate_fingerprint": cand_fp,
    }


def compare_paths(
    baseline_path: Path,
    candidate_path: Path,
    *,
    require_core_panels: bool = True,
    require_order: bool = False,
) -> dict[str, Any]:
    result = compare_views(
        load_view(baseline_path),
        load_view(candidate_path),
        require_core_panels=require_core_panels,
        require_order=require_order,
    )
    result["baseline_path"] = str(baseline_path)
    result["candidate_path"] = str(candidate_path)
    return result


def compare_manifest(path: Path, *, require_order: bool = False) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("anchor manifest must contain a JSON list")
    base_dir = path.parent
    cases: list[dict[str, Any]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"manifest[{idx}] must be an object")
        baseline = _resolve_manifest_path(base_dir, str(item.get("baseline") or ""))
        candidate = _resolve_manifest_path(base_dir, str(item.get("candidate") or ""))
        if not baseline or not candidate:
            raise ValueError(f"manifest[{idx}] must include baseline and candidate")
        result = compare_paths(
            baseline,
            candidate,
            require_core_panels=bool(item.get("require_core_panels", True)),
            require_order=require_order or bool(item.get("require_order", False)),
        )
        result["label"] = str(item.get("label") or f"case_{idx}")
        cases.append(result)
    return {
        "status": "fail" if any(case["status"] == "fail" for case in cases) else "pass",
        "case_count": len(cases),
        "blocking_count": sum(int(case["blocking_count"]) for case in cases),
        "warning_count": sum(int(case["warning_count"]) for case in cases),
        "cases": cases,
    }


def _resolve_manifest_path(base_dir: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else base_dir / path


def _goal_signature(lines: list[str]) -> dict[str, Any]:
    normalized = [
        line.rstrip()
        for line in lines
        if not _is_easycrypt_prompt_line(line)
    ]
    text = "\n".join(normalized).strip()
    return {
        "line_count": len(normalized),
        "sha1": hashlib.sha1(text.encode("utf-8")).hexdigest() if text else "",
        "head": normalized[:12],
    }


_EASYCRYPT_PROMPT_RE = re.compile(r"^\[\d+\|[^\]]+\]>\s*$")


def _is_easycrypt_prompt_line(line: str) -> bool:
    return bool(_EASYCRYPT_PROMPT_RE.match(line.strip()))


def _surface_shape(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"kind": type(value).__name__, "keys": []}
    return {
        "kind": "dict",
        "keys": sorted(value.keys()),
        "nested_keys": {
            key: sorted(child.keys())
            for key, child in value.items()
            if isinstance(child, dict)
        },
    }


def _candidate_move_heads(candidate: dict[str, Any]) -> list[str]:
    heads: set[str] = set()
    for move in _iter_dicts(candidate.get("moves")):
        head = _first_string(
            move.get("head"),
            move.get("tactic_head"),
            _dig(move, "submit", "payload", "tactic"),
            move.get("tactic"),
        )
        if head:
            heads.add(_tactic_head(head))
    return sorted(heads)


def _probe_heads(candidate: dict[str, Any]) -> list[str]:
    heads: set[str] = set()
    for move in _iter_dicts(candidate.get("probe_alternatives")):
        head = _first_string(
            move.get("head"),
            move.get("tactic_head"),
            _dig(move, "submit", "payload", "tactic"),
            move.get("tactic"),
        )
        if head:
            heads.add(_tactic_head(head))
    return sorted(heads)


def _navigation_intents(candidate: dict[str, Any]) -> list[str]:
    intents: set[str] = set()
    navigation = candidate.get("navigation")
    for item in _iter_dicts(navigation):
        intent = _first_string(
            item.get("intent"),
            _dig(item, "submit", "intent"),
        )
        if intent:
            intents.add(intent)
    return sorted(intents)


def _route_health_signals(candidate: dict[str, Any]) -> list[str]:
    return sorted(
        signal
        for signal in (
            _first_string(item.get("signal"), item.get("recovery_class"))
            for item in _iter_dicts(candidate.get("route_health"))
        )
        if signal
    )


def _surface_signals(surface_payloads: dict[str, Any]) -> list[str]:
    signals: set[str] = set()
    for panel, payload in surface_payloads.items():
        if panel == "call_site_surface":
            for item in _iter_dicts(_dig(payload, "frontier_blockers")):
                if _first_string(item.get("kind")) == "named_handle_not_callable_in_current_view":
                    signals.add("stale_named_call_not_callable")
        for item in _iter_dicts(payload):
            signal = _first_string(item.get("signal"), item.get("recovery_class"))
            if signal:
                signals.add(signal)
    return sorted(signals)


def _compatible_route_health_signals(fp: dict[str, Any]) -> list[str]:
    """Return route-health signals plus equivalent evidence in newer panels."""
    signals = set(fp["candidate_moves"]["route_health_signals"])
    surface_signals = set(fp.get("surface_signals") or [])
    surface_panels = set(fp.get("surface_panels") or [])
    if "map_key_membership_head_alignment" in surface_signals:
        signals.add("pure_tail_alignment_gap")
    if "stale_named_call_not_callable" in surface_signals:
        signals.add("lost_call_abstraction_boundary")
    if "seq_cut_mismatch" in signals:
        signals.add("prhl_surgery_sequence_needed")
    if "frame_boundary_gap" in signals and "seq_cut_surface" in surface_panels:
        signals.add("prhl_surgery_sequence_needed")
    return sorted(signals)


def _compatible_surface_panels(
    base_fp: dict[str, Any],
    cand_fp: dict[str, Any],
) -> list[str]:
    panels = set(cand_fp["surface_panels"])
    base_signals = set(base_fp.get("surface_signals") or [])
    cand_panels = set(cand_fp.get("surface_panels") or [])
    cand_signals = set(cand_fp.get("surface_signals") or [])
    if (
        "call_site_surface" in base_fp["surface_panels"]
        and "stale_named_call_not_callable" in base_signals
        and (
            "call_site_surface" in cand_panels
            or "pure_tail_surface" in cand_panels
            or "recovery_diagnosis_surface" in cand_panels
            or "pure_tail_alignment_gap" in cand_signals
        )
    ):
        panels.add("call_site_surface")
    if (
        "pure_tail_surface" in base_fp["surface_panels"]
        and "stale_named_call_not_callable" in base_signals
        and (
            "call_site_surface" in cand_panels
            or "seq_cut_surface" in cand_panels
            or "lost_call_abstraction_boundary" in cand_signals
        )
    ):
        panels.add("pure_tail_surface")
    return sorted(panels)


def _compatible_structural_checkpoint_ids(fp: dict[str, Any]) -> list[str]:
    ids = set(fp["structural_checkpoints"]["semantic_ids"])
    surface_signals = set(fp.get("surface_signals") or [])
    route_signals = set(fp["candidate_moves"]["route_health_signals"])
    if (
        "pure_tail_alignment_gap" in route_signals
        or "map_key_membership_head_alignment" in surface_signals
    ) and "before_seq_cut" in ids:
        ids.add("pure_tail_alignment_gap")
    surface_signals = set(fp.get("surface_signals") or [])
    if (
        "lost_call_abstraction_boundary" in route_signals
        or "stale_named_call_not_callable" in surface_signals
    ) and "before_call_route" in ids:
        ids.add("lost_call_abstraction_boundary")
    return sorted(ids)


def _checkpoint_signature(value: Any) -> dict[str, Any]:
    semantic_ids: set[str] = set()
    scopes: set[str] = set()
    checkpoint_ids: set[str] = set()
    for item in _iter_dicts(value):
        checkpoint_id = _first_string(item.get("checkpoint_id"))
        if checkpoint_id:
            checkpoint_ids.add(checkpoint_id)
        scope = _first_string(item.get("undo_scope"))
        if scope:
            scopes.add(scope)
        for semantic_id in _semantic_ids_from_checkpoint(item):
            semantic_ids.add(semantic_id)
    return {
        "semantic_ids": sorted(semantic_ids),
        "undo_scopes": sorted(scopes),
        "checkpoint_count": len(checkpoint_ids) if checkpoint_ids else len(list(_iter_dicts(value))),
    }


def _semantic_ids_from_checkpoint(item: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for raw in (item.get("semantic_id"), item.get("semantic_ids")):
        if isinstance(raw, str):
            ids.append(raw)
        elif isinstance(raw, list):
            ids.extend(str(x) for x in raw if isinstance(x, str))
    return ids


def _inspect_topics(value: Any) -> list[str]:
    topics: set[str] = set()
    if isinstance(value, dict):
        candidates = value.get("topics") or value.get("handles") or value.get("items")
    else:
        candidates = value
    for item in _iter_any(candidates):
        if isinstance(item, str):
            topics.add(item)
        elif isinstance(item, dict):
            topic = _first_string(item.get("topic"), item.get("name"), item.get("handle"))
            if topic:
                topics.add(topic)
    return sorted(topics)


def _handle_names(value: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for key in ("selected_handles", "visible_call_frontier", "frontier_live_named_handles"):
        for item in _iter_any(value.get(key)):
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict):
                name = _first_string(item.get("name"), item.get("handle"), item.get("id"))
                if name:
                    names.add(name)
    return sorted(names)


def _check_ordering(
    diffs: list[AnchorDiff],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    """Emit warning diffs when the relative order of shared elements differs.

    Only invoked when ``require_order=True``.  These diffs are always
    ``warning`` severity and never affect ``status``; they exist so a refactor
    that silently reshuffles agent-facing panels, candidate moves, or inspect
    topics can be caught even though the order-insensitive fingerprint treats
    such a reshuffle as equivalent.
    """
    _order_diff(
        diffs,
        "ordering.panel_order",
        _panel_order(baseline),
        _panel_order(candidate),
        "top-level panel order changed for shared panels",
    )
    _order_diff(
        diffs,
        "ordering.candidate_moves",
        _ordered_candidate_move_heads(baseline.get("candidate_moves")),
        _ordered_candidate_move_heads(candidate.get("candidate_moves")),
        "candidate_moves.moves order changed for shared moves",
    )
    _order_diff(
        diffs,
        "ordering.inspect_topics",
        _ordered_inspect_topics(baseline.get("inspect_lookup_handles")),
        _ordered_inspect_topics(candidate.get("inspect_lookup_handles")),
        "inspect_lookup_handles topic order changed for shared topics",
    )


def _order_diff(
    diffs: list[AnchorDiff],
    path: str,
    baseline: list[str],
    candidate: list[str],
    message: str,
) -> None:
    """Append a warning diff if shared elements appear in a different order.

    Only elements present in both sequences are compared, so added or removed
    panels/moves/topics do not by themselves count as a reorder.
    """
    shared = set(baseline) & set(candidate)
    base_shared = [item for item in baseline if item in shared]
    cand_shared = [item for item in candidate if item in shared]
    if base_shared != cand_shared:
        diffs.append(
            AnchorDiff(
                "warning",
                path,
                message,
                base_shared,
                cand_shared,
            )
        )


def _panel_order(view: dict[str, Any]) -> list[str]:
    """Return non-volatile top-level panel keys in document order."""
    if not isinstance(view, dict):
        return []
    return [key for key in view if key not in VOLATILE_TOP_LEVEL_KEYS]


def _ordered_candidate_move_heads(candidate: Any) -> list[str]:
    """Return candidate move tactic heads in document order (with repeats)."""
    if not isinstance(candidate, dict):
        return []
    moves = candidate.get("moves")
    items = moves if isinstance(moves, list) else _iter_dicts(moves)
    heads: list[str] = []
    for move in items:
        if not isinstance(move, dict):
            continue
        head = _first_string(
            move.get("head"),
            move.get("tactic_head"),
            _dig(move, "submit", "payload", "tactic"),
            move.get("tactic"),
        )
        if head:
            heads.append(_tactic_head(head))
    return heads


def _ordered_inspect_topics(value: Any) -> list[str]:
    """Return inspect-lookup topics in document order (with repeats)."""
    if isinstance(value, dict):
        candidates = value.get("topics") or value.get("handles") or value.get("items")
    else:
        candidates = value
    topics: list[str] = []
    for item in _iter_any(candidates):
        if isinstance(item, str):
            topics.append(item)
        elif isinstance(item, dict):
            topic = _first_string(item.get("topic"), item.get("name"), item.get("handle"))
            if topic:
                topics.append(topic)
    return topics


def _pick_dict(value: Any, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: value.get(key) for key in sorted(keys) if key in value}


def _compare_equal(
    diffs: list[AnchorDiff],
    path: str,
    baseline: Any,
    candidate: Any,
    message: str,
) -> None:
    if baseline != candidate:
        diffs.append(AnchorDiff("blocking", path, message, baseline, candidate))


def _require_subset(
    diffs: list[AnchorDiff],
    path: str,
    baseline: Iterable[str],
    candidate: Iterable[str],
    message: str,
    *,
    severity: str,
) -> None:
    baseline_set = set(baseline)
    candidate_set = set(candidate)
    missing = sorted(baseline_set - candidate_set)
    if missing:
        diffs.append(
            AnchorDiff(
                severity,
                path,
                message,
                missing,
                sorted(candidate_set),
            )
        )


def _additive_summary(base_fp: dict[str, Any], cand_fp: dict[str, Any]) -> dict[str, Any]:
    return {
        "panel_keys": sorted(set(cand_fp["panel_keys"]) - set(base_fp["panel_keys"])),
        "surface_panels": sorted(set(cand_fp["surface_panels"]) - set(base_fp["surface_panels"])),
        "route_health_signals": sorted(
            set(cand_fp["candidate_moves"]["route_health_signals"])
            - set(base_fp["candidate_moves"]["route_health_signals"])
        ),
        "structural_checkpoint_semantic_ids": sorted(
            set(cand_fp["structural_checkpoints"]["semantic_ids"])
            - set(base_fp["structural_checkpoints"]["semantic_ids"])
        ),
    }


def _iter_any(value: Any) -> Iterable[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return value.values()
    return []


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        for child in value.values():
            if isinstance(child, dict):
                yield child
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        yield item
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _first_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _tactic_head(text: str) -> str:
    compact = text.strip()
    if not compact:
        return ""
    for prefix in ("by ", "+ ", "- ", "* "):
        if compact.startswith(prefix):
            compact = compact[len(prefix):].strip()
    head = compact.split(None, 1)[0]
    return head.rstrip(".:;")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("--baseline", type=Path, required=True)
    p_compare.add_argument("--candidate", type=Path, required=True)
    p_compare.add_argument("--out", type=Path)
    p_compare.add_argument("--no-core-panel-check", action="store_true")
    p_compare.add_argument(
        "--ordered",
        action="store_true",
        help="also emit warning diffs when shared panel/move/topic order differs",
    )

    p_manifest = sub.add_parser("manifest")
    p_manifest.add_argument("--manifest", type=Path, required=True)
    p_manifest.add_argument("--out", type=Path)
    p_manifest.add_argument(
        "--ordered",
        action="store_true",
        help="also emit warning diffs when shared panel/move/topic order differs",
    )

    args = parser.parse_args(argv)
    if args.cmd == "compare":
        result = compare_paths(
            args.baseline,
            args.candidate,
            require_core_panels=not args.no_core_panel_check,
            require_order=args.ordered,
        )
    else:
        result = compare_manifest(args.manifest, require_order=args.ordered)
    payload = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 1 if result.get("status") == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
