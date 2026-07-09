#!/usr/bin/env python3
"""Quantitative inspect-RETURN quality over agent_view_runs (opus-4-8).

For every inspect_context / lookup_symbol PULL: resolve the manager's RETURN
(the bundle-local followup copy), tag its quality deterministically, and compute
whether the agent BUILT ON it (K0 shape-typed sensor) in the next 6 turns.

Quality tags (deterministic, high-precision phrase patterns from the qualitative
audit). A return can be EMPTY xor PLACEHOLDER xor (has-content):
  EMPTY       — producer returned nothing usable ("none passed daemon verification",
                "No errors found", "no named-call candidate", "no mechanical glob frame", ...)
  PLACEHOLDER — a generic template with no real names (`<Inv>`, "add your", `<pre ==> post>`)
  CONTENT     — neither (has real material; useful-vs-incomplete-vs-wrongshape needs the LLM pass)

Per topic we report: pulls, recoverable, empty%, placeholder%, build_on% (of recoverable).
Fix priority = pulls * (1 - build_on_rate)  [volume of pulls that did not transfer].

Usage: .venv/bin/python tools/panel_audit/inspect_quality.py [--model claude-opus-4-8]
"""
import ast, glob, json, os, re, sys
from collections import defaultdict

try:
    from tools.panel_audit.build_on_sensor import build_on
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from build_on_sensor import build_on  # type: ignore

RUNS = os.path.join(os.path.dirname(__file__), "..", "..", "agent_view_runs")

# --- quality phrase patterns (high precision; distinctive manager-return strings) ---
EMPTY_PAT = re.compile(
    r"none passed daemon|no verified bridge|No verified bridge routes|"
    r"No errors found in current session|no named.call candidate|"
    r"Candidate routes exist, but none|no mechanical .{0,12}frame|"
    r"treat direct byequiv as a fallback|No pre.verified|Situation: no |"
    r"didn'?t hand|did not hand|no candidate|returned no |is empty|"
    r"no .{0,20}available", re.I)
PLACEHOLDER_PAT = re.compile(
    r"<Inv>|<loop invariant|<pre |<post>|<pre ==> post>|<mid>|<a Pr|add your|"
    r"needs_frame|<your|<the invariant|<coupling|<bad|<prog|placeholder|"
    r"fill in|<predicate", re.I)


def parse_intent(iv):
    if isinstance(iv, dict): return iv
    if not isinstance(iv, str) or not iv.strip(): return {}
    for p in (json.loads, ast.literal_eval):
        try:
            o = p(iv)
            if isinstance(o, dict): return o
        except Exception: pass
    return {}


def resolve_followup(bundle, turn):
    if turn is None: return None
    try: t = int(turn)
    except (TypeError, ValueError): return None
    for pat in ("views/*/followups/turn_%03d.md", "views/*/*/followups/turn_%03d.md"):
        for p in glob.glob(os.path.join(bundle, pat % t)):
            return p
    return None


def committed(row):
    ij = parse_intent(row.get("intent"))
    if ij.get("intent") != "commit_tactic": return None
    if "reject" in str(row.get("result_summary") or "").lower(): return None
    return (ij.get("payload", {}) or {}).get("tactic", "")


def main(model_filter="claude-opus-4-8"):
    stats = defaultdict(lambda: dict(pulls=0, recov=0, empty=0, ph=0, content=0, built=0))
    for tl in sorted(glob.glob(os.path.join(RUNS, "*", "*", "timeline_report.json"))):
        b = os.path.dirname(tl)
        try: meta = json.load(open(os.path.join(b, "run_meta.json")))
        except Exception: meta = {}
        if model_filter and model_filter not in str(meta.get("model") or ""): continue
        try: t = json.load(open(tl))
        except Exception: continue
        for run in t.get("runs", []):
            rows = run.get("rows", [])
            for i, r in enumerate(rows):
                ij = parse_intent(r.get("intent"))
                if ij.get("intent") not in ("inspect_context", "lookup_symbol"): continue
                pl = ij.get("payload", {}) or {}
                topic = pl.get("topic") or ("lookup_symbol" if pl.get("symbol") else None)
                if not topic: continue
                s = stats[topic]; s["pulls"] += 1
                fu = resolve_followup(b, r.get("turn"))
                if not fu: continue
                ret = open(fu, encoding="utf-8", errors="replace").read()
                s["recov"] += 1
                if EMPTY_PAT.search(ret): s["empty"] += 1
                elif PLACEHOLDER_PAT.search(ret): s["ph"] += 1
                else: s["content"] += 1
                window = [c for c in (committed(x) for x in rows[i+1:i+7]) if c is not None]
                if any(build_on(ret, c) for c in window): s["built"] += 1

    rows = []
    for tp, s in stats.items():
        rec = s["recov"] or 1
        rows.append((tp, s["pulls"], s["recov"], s["empty"]/rec, s["ph"]/rec,
                     s["content"]/rec, s["built"]/rec, s["pulls"]*(1 - s["built"]/rec)))
    rows.sort(key=lambda x: -x[7])  # fix priority = wasted pulls
    print(f"model={model_filter}")
    print(f"\n{'topic':26}{'pulls':>6}{'recov':>6}{'empty%':>7}{'place%':>7}{'content%':>9}{'build_on%':>10}{'FIXpri':>8}")
    for tp, pulls, recov, e, p, c, bo, pri in rows:
        print(f"{tp:26}{pulls:>6}{recov:>6}{e*100:>6.0f}%{p*100:>6.0f}%{c*100:>8.0f}%{bo*100:>9.0f}%{pri:>8.1f}")
    print("\nFIXpri = pulls x (1 - build_on_rate) = volume of pulls that did NOT transfer.")
    print("Read: high empty% -> producer returns nothing; low build_on% + high content% -> returns")
    print("material the agent doesn't use (wrong/incomplete - needs the LLM pass to split).")


if __name__ == "__main__":
    mf = "claude-opus-4-8"
    if "--model" in sys.argv: mf = sys.argv[sys.argv.index("--model")+1]
    if "--all" in sys.argv: mf = None
    main(mf)
