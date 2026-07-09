"""Panel philosophy audit for ProverWorkspaceView.

Checks one or a sequence of ``workspace_views/turn_*.json`` against the panel
design philosophy in ``core/easycrypt/TOOLS.md`` ("Panel design philosophy").

``core/easycrypt/panel_policy.py`` holds the panel-design rules (the size
budgets, framing-strip targets, imperative-wording patterns, and the read-only
predicates). This audit enforces those rules *read-only*: it reports findings
and never mutates a view. ``panel_policy`` also defines a runtime ``enforce()``
function, but the runtime gate
(``WorkspaceViewManager.sanitize_agent_view``) does NOT yet import or call it —
wiring the runtime gate to ``panel_policy.enforce()`` so the CI audit and the
runtime share a single source of truth is a tracked follow-up, not yet done.
Until then this audit and the runtime may drift.

Severities follow the panel-policy enforcement policy:
  - framing / size / wording  -> ERROR  (HARD gate)
  - provenance / budgets       -> WARN   (FLAG, transition period)

Unlike the anchor manifest (panels did not *disappear*), this confirms panels
did not *violate the contract*. Part of the proof-manager refactor gate.

Scope note: ``audit_sequence`` (the constant-string and monotonic-growth
checks) operates WITHIN ONE replay run — i.e. across the turns of a single
canned tactic sequence — not across commits. Cross-commit comparison is the
job of the separate view-diff tooling.

Usage:
  python3 -m workflow.validation.view_philosophy_audit <view.json | dir> ...
  python3 -m workflow.validation.view_philosophy_audit --json <dir>
Exit code is non-zero if any ERROR-severity finding is present.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from core.easycrypt.panel_policy import (
        SIZE_TARGET, SIZE_HARD, MAX_CANDIDATE_MOVES, MAX_INSPECT_TOPICS,
        FRAMING_STRIP, FRAMING_STRIP_TOPLEVEL,
        framing_size, imperative_findings, provenance_flags, walk_strings,
    )
except Exception:  # run with core/easycrypt on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core" / "easycrypt"))
    from panel_policy import (  # type: ignore
        SIZE_TARGET, SIZE_HARD, MAX_CANDIDATE_MOVES, MAX_INSPECT_TOPICS,
        FRAMING_STRIP, FRAMING_STRIP_TOPLEVEL,
        framing_size, imperative_findings, provenance_flags, walk_strings,
    )

# constant-framing check is scoped to the strategy panels (a fixed goal
# separator / static button help / generic checks are legitimately constant).
STRATEGY_SCOPE = re.compile(r"^\.(application_context|candidate_moves)\b")
IGNORE_PATHS = re.compile(
    r"\.(effect|manager_note|note|fact_note|source|kind|authority|"
    r"schema_version|label|role|category|use_when|applicability|returns)\b")


def audit_view(view: dict[str, Any], label: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(sev: str, code: str, msg: str, where: str = ""):
        findings.append({"view": label, "severity": sev, "code": code,
                         "where": where, "message": msg})

    # A turn file may legitimately contain a null/non-object payload (or an
    # envelope whose "view" key is null); guard so the predicates below never
    # crash on a None view, and surface it as a finding instead.
    if not isinstance(view, dict):
        add("ERROR", "view.malformed",
            f"not a JSON object (got {type(view).__name__})")
        return findings

    # size budget — framing panels only (truth layers are exempt)
    fsize = framing_size(view)
    if fsize > SIZE_HARD:
        add("ERROR", "size.hard",
            f"framing panels are {fsize} chars (> {SIZE_HARD} hard ceiling)")
    elif fsize > SIZE_TARGET:
        add("WARN", "size.target",
            f"framing panels are {fsize} chars (> {SIZE_TARGET} target)")

    # standing L3 / risk framing
    for panel, sub in FRAMING_STRIP:
        node = view.get(panel)
        if isinstance(node, dict) and sub in node:
            add("ERROR", "framing.l3_standing",
                f"standing framing `{panel}.{sub}` present; must be goal-state "
                "gated / stripped by the manager", where=f"{panel}.{sub}")
    blob = json.dumps(view, ensure_ascii=False)
    for key in FRAMING_STRIP_TOPLEVEL:
        if f'"{key}"' in blob:
            add("ERROR", "framing.l3_standing",
                f"standing framing `{key}` present in view", where=key)

    # imperative / ordering wording
    for jpath, s in imperative_findings(view):
        add("ERROR", "wording.imperative",
            f"imperative/ordering wording: '{s[:80]}'", where=jpath)

    # verified-tactic provenance — FLAG (transition), not hard
    for jpath, missing in provenance_flags(view):
        add("WARN", "tactic.no_provenance",
            f"committable tactic option missing markers {missing}", where=jpath)

    # count budgets
    moves = (((view.get("candidate_moves") or {}).get("moves")) or [])
    if isinstance(moves, list) and len(moves) > MAX_CANDIDATE_MOVES:
        add("WARN", "budget.moves",
            f"candidate_moves has {len(moves)} options (> {MAX_CANDIDATE_MOVES})")
    topics = (((view.get("inspect_lookup_handles") or {}).get("ask_manager_for")) or [])
    if isinstance(topics, list) and len(topics) > MAX_INSPECT_TOPICS:
        add("WARN", "budget.inspect",
            f"inspect has {len(topics)} topics (> {MAX_INSPECT_TOPICS})")
    return findings


def audit_sequence(views: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Cross-turn checks WITHIN A SINGLE replay run.

    The ``views`` are the successive turns of one canned tactic sequence
    (e.g. ``workspace_views/turn_001.json``, ``turn_002.json``, ...). These
    checks detect framing that does not respond to proof state — constant
    strategy strings repeated unchanged across the run, or framing that only
    ever grows with proof depth. This is NOT a cross-commit comparison; it
    never looks at views from a different commit/run.
    """
    findings: list[dict[str, Any]] = []
    if len(views) < 2:
        return findings

    # framing-size monotonic growth across turns
    sizes = [framing_size(v) for _, v in views]
    if all(b >= a for a, b in zip(sizes, sizes[1:])) and sizes[-1] > sizes[0]:
        findings.append({
            "view": "<sequence>", "severity": "WARN", "code": "size.growth",
            "where": "", "message": (
                f"framing grows monotonically with depth: {sizes}")})

    # constant strategy strings (non-context-derived)
    per_view = [{jp: s for jp, s in walk_strings(v)} for _, v in views]
    common = set(per_view[0])
    for d in per_view[1:]:
        common &= set(d)
    for jp in sorted(common):
        if not STRATEGY_SCOPE.search(jp) or IGNORE_PATHS.search(jp):
            continue
        vals = {d[jp] for d in per_view}
        if len(vals) == 1 and len(next(iter(vals))) >= 40:
            findings.append({
                "view": "<sequence>", "severity": "ERROR",
                "code": "framing.constant_string", "where": jp,
                "message": (f"constant strategy string across {len(views)} "
                            f"states: '{next(iter(vals))[:80]}'")})
    return findings


# Replay/compare runs (see workflow/validation/manager_view_replay.py) drop
# non-view JSON alongside the per-turn views: a run report, the bootstrap dump,
# and a cross-commit compare report. These are NOT ProverWorkspaceViews; loading
# them as views produces nonsense findings, so they are excluded by name.
NON_VIEW_FILES = frozenset({"bootstrap.json", "report.json", "compare_report.json"})


def _dir_view_paths(p: Path) -> list[Path]:
    """Collect per-turn view files from a replay/compare output directory.

    The canonical writer puts views under a ``workspace_views/`` (or, in older
    runs, ``views/``) subdir, named ``turn_*.json``. We prefer those scoped
    dirs, then fall back to top-level ``turn_*.json``, and only as a last resort
    to other ``*.json`` files — and even then we keep only ``turn_*.json`` names
    and drop the run's report/bootstrap/compare artifacts, so pointing the audit
    at a replay output dir never scoops up ``report.json`` & friends as views.
    """
    # Scoped subdir globs are restricted to a `workspace_views/`|`views/` parent
    # so we do not pick up sibling `manager_results/turn_*.json` (those are
    # manager action dumps, not views).
    scoped = (sorted(p.glob("**/workspace_views/turn_*.json")) or
              sorted(p.glob("**/views/turn_*.json")))
    if scoped:
        return scoped
    top_turn = sorted(p.glob("turn_*.json"))
    if top_turn:
        return top_turn
    # Last resort: a flat dir of views. Keep only turn_*.json names and exclude
    # known non-view artifacts, so a replay dir with report.json yields nothing
    # bogus.
    return [q for q in sorted(p.glob("*.json"))
            if q.name not in NON_VIEW_FILES and q.name.startswith("turn_")]


def _load_views(args: list[str]) -> list[tuple[str, dict[str, Any]]]:
    paths: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            paths.extend(_dir_view_paths(p))
        elif p.is_file():
            # An explicitly named file is loaded as-is (the caller pointed at
            # it), even if its name would be filtered out of a dir glob.
            paths.append(p)
    out: list[tuple[str, dict[str, Any]]] = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"skip {p}: {exc}", file=sys.stderr)
            continue
        view = data.get("view") if isinstance(data, dict) and "view" in data else data
        out.append((p.name, view))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if not argv:
        print(__doc__)
        return 2
    views = _load_views(argv)
    if not views:
        print("no workspace views found", file=sys.stderr)
        return 2

    findings: list[dict[str, Any]] = []
    for label, v in views:
        findings.extend(audit_view(v, label))
    findings.extend(audit_sequence(views))
    errors = [f for f in findings if f["severity"] == "ERROR"]

    if as_json:
        print(json.dumps({"views": len(views), "findings": findings,
                          "errors": len(errors)}, indent=2, ensure_ascii=False))
    else:
        print(f"=== panel philosophy audit: {len(views)} view(s) ===")
        for f in findings:
            print(f"  [{f['severity']:5}] {f['code']:24} {f['view']:16} "
                  f"{f['where']}\n           {f['message']}")
        print(f"\n{len(errors)} ERROR, {len(findings)-len(errors)} WARN")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
