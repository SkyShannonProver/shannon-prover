#!/usr/bin/env python3
"""When do agents ACTUALLY inspect? — to decide when the commit panel should
carry the full inspect menu vs a compact pointer.

Reads the real recorded intent stream from EVERY bundle's manager_results
(handled_intent per turn, per tree) — no replay, no EC. Answers:
  1. base rates of each intent
  2. after a COMMIT, what is the next intent? (is the menu on commit used?)
  3. what PRECEDES an inspect/lookup? (commit / rejected-commit / probe / stall)
  4. do inspect/lookups cluster at goal-state CHANGES or at STALLS?
  5. which inspect topics are actually chosen
"""
from __future__ import annotations
import glob, json, os
from collections import Counter, defaultdict

ROOT = "agent_view_runs"

def trees():
    for mr_dir in glob.glob(f"{ROOT}/*/*/views/*/manager_results"):
        run = mr_dir.split("/")[1] + "/" + mr_dir.split("/")[2]
        tree = mr_dir.split("/")[-2]
        # profile from run_meta
        meta_path = os.path.join(ROOT, *mr_dir.split("/")[1:3], "run_meta.json")
        try:
            prof = json.load(open(meta_path)).get("surface_profile", "?")
        except Exception:
            prof = "?"
        steps = []
        for f in sorted(glob.glob(f"{mr_dir}/turn_*.json")):
            try:
                d = json.load(open(f))
            except Exception:
                continue
            t = d.get("turn")
            hi = d.get("handled_intent") or {}
            intent = hi.get("intent")
            if not isinstance(t, int) or not intent:
                continue
            # was the commit accepted? read error_summary in manager_actions
            err = ""
            for a in (d.get("manager_actions") or []):
                if isinstance(a, dict) and a.get("error_summary"):
                    err = str(a["error_summary"]); break
            ok = bool(d.get("ok"))
            accepted = ok and not err
            topic = (hi.get("payload") or {}).get("topic") or (hi.get("payload") or {}).get("symbol")
            steps.append((t, intent, accepted, err, topic))
        steps.sort()
        if steps:
            yield run, tree, prof, steps

intent_counts = Counter()
after_commit = Counter()         # next intent after an accepted commit
after_reject = Counter()         # next intent after a rejected/no-op commit
before_retrieval = Counter()     # intent immediately before an inspect/lookup
topics = Counter()
retrieval_at_state_change = Counter()  # does a retrieval happen where goal just changed?
n_commits = n_retr = n_trees = 0
prof_intent = defaultdict(Counter)

RETR = {"inspect_context", "lookup_symbol"}

for run, tree, prof, steps in trees():
    n_trees += 1
    seq = [s[1] for s in steps]
    acc = [s[2] for s in steps]
    for i, (t, intent, accepted, err, topic) in enumerate(steps):
        intent_counts[intent] += 1
        prof_intent[prof][intent] += 1
        if intent == "commit_tactic":
            n_commits += 1
            nxt = seq[i+1] if i+1 < len(seq) else "(end)"
            (after_commit if accepted else after_reject)[nxt] += 1
        if intent in RETR:
            n_retr += 1
            prev = seq[i-1] if i > 0 else "(start)"
            before_retrieval[prev] += 1
            if topic:
                topics[topic] += 1

def pct(c, tot): return f"{c/tot*100:.0f}%" if tot else "0%"

print(f"== corpus: {n_trees} trees ==")
tot = sum(intent_counts.values())
print(f"\n-- intent base rates ({tot} turns) --")
for k, v in intent_counts.most_common():
    print(f"   {k:18s} {v:5d}  {pct(v,tot)}")

print(f"\n-- after an ACCEPTED commit ({sum(after_commit.values())} cases), next intent: --")
for k, v in after_commit.most_common():
    print(f"   {k:18s} {v:5d}  {pct(v,sum(after_commit.values()))}")
retr_after_commit = after_commit['inspect_context'] + after_commit['lookup_symbol']
print(f"   => retrieval-after-accepted-commit: {pct(retr_after_commit, sum(after_commit.values()))}")

print(f"\n-- after a REJECTED / no-op commit ({sum(after_reject.values())} cases), next intent: --")
for k, v in after_reject.most_common():
    print(f"   {k:18s} {v:5d}  {pct(v,sum(after_reject.values()))}")
retr_after_reject = after_reject['inspect_context'] + after_reject['lookup_symbol']
print(f"   => retrieval-after-rejected-commit: {pct(retr_after_reject, sum(after_reject.values()))}")

print(f"\n-- what PRECEDES an inspect/lookup ({n_retr} retrievals): --")
for k, v in before_retrieval.most_common():
    print(f"   {k:18s} {v:5d}  {pct(v,n_retr)}")

print(f"\n-- inspect topics chosen --")
for k, v in topics.most_common(20):
    print(f"   {str(k):28s} {v:4d}")

print(f"\n-- L4-only intent mix (menu only exists at L4) --")
for prof in sorted(prof_intent):
    if "l4" not in prof and "adaptive" not in prof:
        continue
    c = prof_intent[prof]; t = sum(c.values())
    retr = c['inspect_context'] + c['lookup_symbol']
    print(f"   {prof:30s} {t:5d} turns | retrieval {pct(retr,t)} | commit {pct(c['commit_tactic'],t)} | probe {pct(c['probe_tactic'],t)}")
