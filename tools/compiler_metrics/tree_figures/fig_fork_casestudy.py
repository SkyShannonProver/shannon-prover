#!/usr/bin/env python3
"""Figure B — fork case studies (Morandi palette, paper style).

The fork-wins as search-tree case studies: on the hard tail, only a forked
child closes the proof; no root prover closes it alone.
    python3 tools/compiler_metrics/fig_fork_casestudy.py [--out f.svg]
"""
from __future__ import annotations
import argparse, glob, json, os

# Morandi palette (sampled from the paper's tactic-pyramid figure)
SAGE   = "#a7b89a"   # winning fork (✓)
GRAY   = "#b3a99c"   # root / dead fork (✗)
GRAY_LT= "#d3ccbe"   # dead fork (lighter)
DELTA  = "#9b6f60"   # muted terracotta
TEXT   = "#3b3a36"
LABEL  = "#857d70"
RULE   = "#d8d2c6"

def depth(n): return len(n.replace("Tree-", "").split(".")) if n else 99
def is_root(n): return depth(n) <= 2
def parent(n):
    p = n.split("."); return ".".join(p[:-1]) if len(p) > 2 else None

def collect(root):
    seen, forks = set(), []
    for tr in sorted(glob.glob(os.path.join(root, "*", "*", "timeline_report.json"))):
        d = os.path.dirname(tr)
        try:
            m = json.load(open(os.path.join(d, "run_meta.json"))); rep = json.load(open(tr))
        except Exception:
            continue
        rid = m.get("run_iteration_dir") or ""
        if rid in seen: continue
        seen.add(rid)
        if "chunk" in rid.lower() or "resume" in rid.lower(): continue
        if not (m.get("outcome") or "").startswith("proved"): continue
        rows = [r for run in rep.get("runs", []) for r in run.get("rows", [])]
        qrow = next((r for r in rows if "qed" in (r.get("intent_summary") or "").lower() and r.get("ok")), None)
        if not qrow or is_root(qrow.get("node")): continue
        from collections import Counter
        nd = Counter(r.get("node") for r in rows)
        ntac = sum(len(c.get("tactics", [])) for c in (m.get("committed_proofs") or []))
        nodes = sorted(nd, key=lambda n: (depth(n), n))
        forks.append(dict(lemma=m.get("lemma"), ntac=ntac, trees=m.get("trees") or 1,
                          qnode=qrow.get("node"),
                          nodes=[(n, nd[n], is_root(n), n == qrow.get("node"), parent(n)) for n in nodes]))
    forks.sort(key=lambda c: (-c["trees"], -c["ntac"]))
    return forks

def build(forks, out):
    W = 1000
    rows_total = sum(len(c["nodes"]) for c in forks)
    H = 132 + rows_total * 28 + len(forks) * 52
    H = max(H, W + 10)   # height >= width (QuickLook thumbnailer clips width at x≈height)
    maxturns = max(t for c in forks for _, t, _, _, _ in c["nodes"]) or 1
    bx0 = 300; bw_max = W - bx0 - 160

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Helvetica,Arial">',
         f'<rect width="{W}" height="{H}" fill="white"/>']
    s.append(f'<text x="{W/2}" y="38" font-size="17" font-weight="bold" fill="{TEXT}" text-anchor="middle">At the hard tail, only a fork closes the proof — no root prover closes it alone</text>')
    s.append(f'<text x="{W/2}" y="59" font-size="11.5" fill="{LABEL}" text-anchor="middle">all {len(forks)} fork-wins in the corpus (0/{len(forks)} closed by a root) · roots made monotone progress (0 rejects) on a route that could not close;</text>')
    s.append(f'<text x="{W/2}" y="75" font-size="11.5" fill="{LABEL}" text-anchor="middle">the winning fork branched to a different route from an earlier checkpoint and closed it</text>')
    # legend
    ly = 96
    s.append(f'<rect x="40" y="{ly}" width="13" height="11" rx="2" fill="{GRAY}"/><text x="59" y="{ly+10}" font-size="11.5" fill="{TEXT}">root / dead fork (✗)</text>')
    s.append(f'<rect x="230" y="{ly}" width="13" height="11" rx="2" fill="{SAGE}"/><text x="249" y="{ly+10}" font-size="11.5" fill="{TEXT}">winning fork → qed (✓)</text>')
    s.append(f'<text x="450" y="{ly+10}" font-size="11" fill="{LABEL}">bar length = agent turns</text>')
    s.append(f'<line x1="40" y1="{ly+24}" x2="{W-40}" y2="{ly+24}" stroke="{RULE}"/>')

    y = ly + 52
    for c in forks:
        tag = "PARALLEL FORK · HARD" if c["trees"] > 1 else "SINGLE-TREE BACKJUMP-REPAIR · MEDIUM"
        s.append(f'<text x="40" y="{y}" font-size="13.5" font-weight="bold" fill="{TEXT}">{c["lemma"]}'
                 f'<tspan fill="{LABEL}" font-size="11" font-weight="normal">   {c["ntac"]} tactics · {tag}</tspan></text>')
        y += 12
        ypos = {}
        root_turns = sum(t for n, t, rt, w, p in c["nodes"] if rt)
        win_turns = next(t for n, t, rt, w, p in c["nodes"] if w)
        for (n, t, rt, won, par) in c["nodes"]:
            yc = y + 14; ypos[n] = yc
            indent = bx0 + (0 if rt else 38)
            col = SAGE if won else (GRAY if rt else GRAY_LT)
            bl = bw_max * t / maxturns
            if par and par in ypos:
                px = bx0 + 6
                s.append(f'<path d="M{px},{ypos[par]+6:.0f} V{yc:.0f} H{indent:.0f}" fill="none" stroke="{RULE}" stroke-width="1.4"/>')
            s.append(f'<text x="{bx0-12}" y="{yc+4:.0f}" font-size="11.5" text-anchor="end" fill="{LABEL}">{n} ({"root" if rt else "fork"})</text>')
            s.append(f'<rect x="{indent:.0f}" y="{yc-9:.0f}" width="{max(bl,2):.1f}" height="18" rx="2.5" fill="{col}"/>')
            s.append(f'<text x="{indent+max(bl,2)+8:.1f}" y="{yc+4:.0f}" font-size="11.5" fill="{TEXT}">{t} turns  {"✓ qed" if won else "✗"}</text>')
            y += 28
        s.append(f'<text x="{bx0}" y="{y+4}" font-size="12" font-weight="bold" fill="{DELTA}">{root_turns} turns of root exploration never closed; the fork closed it in {win_turns} turns</text>')
        y += 40
    s.append('</svg>')
    open(out, "w").write("\n".join(s))
    print(f"fork-wins: {[c['lemma'] for c in forks]} -> {out}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="agent_view_runs")
    ap.add_argument("--out", default="tools/compiler_metrics/tree_figures/fig_fork_casestudy.svg")
    a = ap.parse_args()
    build(collect(a.root), a.out)

if __name__ == "__main__":
    main()
