#!/usr/bin/env python3
"""Panel-audit deterministic metrics over agent_view_runs bundles.

OMISSION lens (offer-rate) is fully deterministic: inspect_topics on each timeline
row is the per-turn OFFERED menu, so a topic that never appears was never offered.
PULLED is parsed from intent. UPTAKE is the FAIR name-overlap: module.proc names in
the manager-RETURNED followup that reappear in a subsequent NON-REJECTED commit_tactic
within 6 turns — resolving the bundle-local followup copy and excluding rejected
commits. (Pilot wf_2410c7f9-eb9 found 3 bugs this version fixes: runs-vs-files counter,
unresolved followups, no reject-gate.)

Usage: python3 tools/panel_audit/scorecard.py [--all] [--uptake TOPIC ...]
"""
import ast
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter

try:
    from tools.panel_audit.build_on_sensor import build_on, names
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from build_on_sensor import build_on, names  # type: ignore

RUNS = os.path.join(os.path.dirname(__file__), "..", "..", "agent_view_runs")


def git_sha():
    try:
        return subprocess.run(
            ["git", "-C", os.path.dirname(__file__), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True).stdout.strip() or "?"
    except Exception:
        return "?"


def load_runs():
    """Yield (bundle_dir, run_dir, profile, model, rows). bundle_dir resolves the
    bundle-local followup copies; model (from run_meta) enables per-model splits —
    the corpus mixes opus-4-8 / opus-4-6 / fable-5 and they fail differently."""
    for tl in sorted(glob.glob(os.path.join(RUNS, "*", "*", "timeline_report.json"))):
        bundle_dir = os.path.dirname(tl)
        try:
            t = json.load(open(tl))
        except Exception:
            continue
        try:
            model = str(json.load(open(os.path.join(bundle_dir, "run_meta.json"))).get("model") or "?")
        except Exception:
            model = "?"
        for run in t.get("runs", []):
            rd = str(run.get("run_dir", ""))
            profile = "l4" if "l4" in rd else ("l1" if "l1" in rd else "?")
            yield bundle_dir, rd, profile, model, run.get("rows", [])


def parse_intent(iv):
    if isinstance(iv, dict):
        return iv
    if not isinstance(iv, str) or not iv.strip():
        return {}
    for p in (json.loads, ast.literal_eval):
        try:
            o = p(iv)
            if isinstance(o, dict):
                return o
        except Exception:
            pass
    return {}


def resolve_followup(bundle_dir, row):
    """The timeline's result_followup_path is an original artifacts/... path; the
    bundle COPIES followups to <bundle>/views/<Tree>/followups/turn_NNN.md."""
    fu = row.get("result_followup_path") or row.get("decision_followup_path") or ""
    m = re.search(r'/(Tree_\d+_\d+)/followups/(turn_\d+\.md)', fu)
    if m:
        p = os.path.join(bundle_dir, "views", m.group(1), "followups", m.group(2))
        if os.path.exists(p):
            return p
    turn = row.get("turn")
    if turn is not None:
        try:
            for p in glob.glob(os.path.join(bundle_dir, "views", "*", "followups",
                                            "turn_%03d.md" % int(turn))):
                return p
        except (ValueError, TypeError):
            pass
    return None


# --- the value sensor (K0) ---------------------------------------------------
# Dotted-name FAIR alone was BLIND to frame-/name-/syntax-shaped transfer: it
# scored a verbatim `call (_: ={glob OCC, glob I}).` commit and a lemma_index-driven
# `rewrite (doublequery_eq ...)` as MISSES. build_on() is shape-typed:
#   (a) IDENTIFIER overlap — dotted Module.proc OR bare lemma/op names (>=4 chars,
#       incl. the EC prime), minus ubiquitous tactic keywords;
#   (b) STRUCTURAL-FRAGMENT overlap — a distinctive bracketed clause of the returned
#       content (={...}, {...}, (...)) reappearing (whitespace-normalized) in the commit.
# names() is RETAINED as the legacy dotted-only metric, reported beside build_on so
# the move is visible (build_on is a proxy: dotted-FAIR under-counts, intent over-counts).


def committed_tactic(row):
    """The committed tactic text on this row, or None if not a (non-rejected) commit."""
    ij = parse_intent(row.get("intent"))
    if ij.get("intent") != "commit_tactic":
        return None
    if "reject" in str(row.get("result_summary") or "").lower():
        return None
    return (ij.get("payload", {}) or {}).get("tactic", "")


def main(show_all=False, uptake_topics=None, model_filter=None):
    offered = Counter()
    pulled = Counter()
    files = set()
    runs = turns = parse_ok = 0
    prof = Counter()
    models = Counter()
    pull_sites = {t: [] for t in (uptake_topics or [])}

    for bundle_dir, rd, profile, model, rows in load_runs():
        if model_filter and model_filter not in model:
            continue
        models[model] += 1
        files.add(bundle_dir)
        runs += 1
        for i, r in enumerate(rows):
            turns += 1
            prof[profile] += 1
            for tp in set(r.get("inspect_topics") or []):
                offered[tp] += 1
            ij = parse_intent(r.get("intent"))
            if ij:
                parse_ok += 1
            if ij.get("intent") in ("inspect_context", "lookup_symbol"):
                pl = ij.get("payload", {}) or {}
                tp = pl.get("topic") or pl.get("symbol")
                if tp:
                    pulled[tp] += 1
                    if tp in pull_sites:
                        pull_sites[tp].append((bundle_dir, i, rows))

    print(f"snapshot: files={len(files)} runs={runs} turns={turns} git={git_sha()} "
          f"model_filter={model_filter or 'ALL'} intent_parse_ok={parse_ok}")
    print(f"  profiles={dict(prof)}  models={dict(models)}\n")

    pilot = ["inv_from_lemma", "bridge_probe", "lemma_index", "subgoal_gap", "proof_frontier"]
    comp = ["call_subgoals", "call_site_options", "call_invariant_skeleton",
            "goal_info", "tactic_forms", "align"]
    print(f"{'topic':28} {'offered':>8} {'offer%':>7} {'pulled':>7}")
    for tp in pilot + ["--"] + comp:
        if tp == "--":
            print()
            continue
        ot = offered.get(tp, 0)
        print(f"{tp:28} {ot:>8} {ot / max(turns,1) * 100:>6.1f}% {pulled.get(tp, 0):>7}")

    # FAIR uptake: name-overlap of the RETURNED followup into a non-rejected commit
    # within 6 turns, alongside the cheap (inflated) intent-overlap.
    for tp, sites in (pull_sites or {}).items():
        recov = dotted_hit = buildon_hit = intent_hit = 0
        n = len(sites)
        for bundle_dir, i, rows in sites:
            window = [c for c in (committed_tactic(r) for r in rows[i + 1:i + 7])
                      if c is not None]
            if window:
                intent_hit += 1
            fu = resolve_followup(bundle_dir, rows[i])
            if not fu:
                continue
            recov += 1
            ret = open(fu, encoding="utf-8", errors="replace").read()
            if any(names(ret) & names(c) for c in window):
                dotted_hit += 1
            if any(build_on(ret, c) for c in window):
                buildon_hit += 1
        denom = recov if recov else "-"
        print(f"\nUPTAKE {tp}: pulls={n} content_recoverable={recov}/{n}  "
              f"intent_overlap={intent_hit}/{n}  "
              f"dotted_FAIR(legacy)={dotted_hit}/{denom}  "
              f"build_on(shape-typed)={buildon_hit}/{denom}")

    if show_all:
        print("\nALL offered:", dict(offered.most_common()))
        blind = [t for t in pulled if offered.get(t, 0) == 0]
        print("PULLED-but-NEVER-OFFERED:", {t: pulled[t] for t in blind})


if __name__ == "__main__":
    ut = []
    if "--uptake" in sys.argv:
        ut = [a for a in sys.argv[sys.argv.index("--uptake") + 1:] if not a.startswith("--")]
    mf = None
    if "--model" in sys.argv:
        mf = sys.argv[sys.argv.index("--model") + 1]
    main(show_all="--all" in sys.argv,
         uptake_topics=ut or ["call_subgoals", "call_invariant_skeleton"],
         model_filter=mf)
