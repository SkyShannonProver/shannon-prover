#!/usr/bin/env python3
"""Panel ERGONOMICS audit: ordering, proportion (占比), signal/noise, length.

Not a fidelity check (is the content true?) but a layout check (is it laid out so
an agent can read it fast?). Splits each captured `current_panel.md` into sections
and measures, per turn-type:
  - line budget per section + % share (proportion / 占比)
  - WHERE the current goal and the last-action verdict sit (line offset = how far
    the agent must read to reach the two things it needs first)
  - boilerplate share (anchors / legal block / submit reminder / static menus)
  - total length distribution
"""
from __future__ import annotations
import glob, json, os, sys
from collections import defaultdict

RUNS = sys.argv[1:] or [
    "artifacts/panel_audit/mee_decrypt_correct/Tree_0_0",
    "artifacts/panel_audit/FCBC_Perm6_L4",
    "artifacts/panel_audit/pr_G4_L4",
]

# Classify a line into a section bucket by the markers the renderer emits.
def section_of(line: str, cur: str) -> str:
    s = line.strip()
    if s.startswith("## 🎯 Current Goal") or s.startswith("## 🔍 Probe preview"):
        return "GOAL/preview"
    if s.startswith("## Status"):
        return "Status"
    if s.startswith("### Need more?") or s.startswith("### Proof Workbench"):
        return "inspect-menu/workbench"
    if s.startswith("## Already tried"):
        return "already-tried"
    if s.startswith("### Manager result"):
        return "manager-result"
    if s.startswith("### Legal Node Memory Anchor") or s.startswith("LEGAL_"):
        return "legal-anchor"
    if s.startswith("## Requested:"):
        return "inspect/lookup-answer"
    if s.startswith("## Call Frontier") or s.startswith("## Surgery") or \
       s.startswith("## Seq Cut") or s.startswith("## Pure Tail") or \
       s.startswith("## Application Context") or s.startswith("## Facts") or \
       s.startswith("## Candidate") or s.startswith("## Program") or \
       "Surgery" in s and s.startswith("##"):
        return "focus-panel"
    if s.startswith("**Last action:**") or s.startswith("### Proof Workbench"):
        return "last-action"
    if "Submit exactly ONE proof intent" in s or "Submit exactly one proof intent" in s:
        return "submit-reminder"
    if "Compaction recovery" in s or "complete structured view" in s:
        return "legal-anchor"
    return cur  # continuation of the current section

BOILERPLATE = {"legal-anchor", "submit-reminder"}

def turn_type(intent_path: str) -> str:
    try:
        return json.load(open(intent_path)).get("intent", "?")
    except Exception:
        return "?"

def analyze(run: str):
    per_type_sec = defaultdict(lambda: defaultdict(int))     # type -> section -> lines
    per_type_total = defaultdict(int)
    per_type_n = defaultdict(int)
    goal_offset = defaultdict(list)   # type -> [line index where GOAL/preview starts]
    action_offset = defaultdict(list)
    totals = []
    for f in sorted(glob.glob(f"{run}/steps/turn_*/current_panel.md")):
        d = os.path.dirname(f)
        tt = turn_type(os.path.join(d, "intent.json"))
        lines = open(f, encoding="utf-8").read().splitlines()
        if not lines:
            continue
        cur = "header"
        secs = defaultdict(int)
        first_goal = first_action = None
        for i, ln in enumerate(lines):
            cur = section_of(ln, cur)
            secs[cur] += 1
            if first_goal is None and cur in ("GOAL/preview",):
                first_goal = i
            if first_action is None and (ln.strip().startswith("**Last action:**")
                                         or cur == "GOAL/preview" and "→" in ln):
                first_action = i
        n = len(lines)
        per_type_n[tt] += 1
        per_type_total[tt] += n
        totals.append((tt, n))
        for k, v in secs.items():
            per_type_sec[tt][k] += v
        if first_goal is not None:
            goal_offset[tt].append(first_goal)
    return per_type_sec, per_type_total, per_type_n, goal_offset, totals

for run in RUNS:
    name = run.split("/")[-1] if run.split("/")[-1] != "Tree_0_0" else run.split("/")[-2]
    per_type_sec, per_type_total, per_type_n, goal_offset, totals = analyze(run)
    print("=" * 78)
    print(f"RUN: {name}   ({sum(per_type_n.values())} turns, "
          f"avg {sum(t for _,t in totals)//max(len(totals),1)} lines/panel)")
    for tt in sorted(per_type_n):
        n = per_type_n[tt]; tot = per_type_total[tt]
        avg = tot / n
        print(f"\n  [{tt}]  {n} turns, avg {avg:.0f} lines/panel")
        secs = per_type_sec[tt]
        bp = sum(v for k, v in secs.items() if k in BOILERPLATE)
        for k, v in sorted(secs.items(), key=lambda kv: -kv[1]):
            print(f"      {k:24s} {v/tot*100:4.0f}%  ({v/n:4.1f} ln/turn)")
        print(f"      -> boilerplate(legal+submit) = {bp/tot*100:.0f}% of every {tt} panel")
        if goal_offset[tt]:
            go = goal_offset[tt]
            print(f"      -> goal/preview first appears at line "
                  f"{sum(go)/len(go):.0f} on avg (0=top)")
