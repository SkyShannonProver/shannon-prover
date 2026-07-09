#!/usr/bin/env python3
"""Figure A — backtracking summary (Morandi palette, paper style).

Two panels: hard proofs require backtracking far more than easy ones.
Dependency-free SVG.
    python3 tools/compiler_metrics/tree_figures/fig_backtracking_summary.py [--out f.svg]
"""
from __future__ import annotations
import argparse, glob, json, os, statistics as st
from collections import Counter

# Morandi palette (sampled from the paper's tactic-pyramid figure)
SAGE   = "#a7b89a"   # easy / calm
CLAY   = "#c19a8b"   # hard / effortful
DELTA  = "#9b6f60"   # muted terracotta (replaces bright red)
TEXT   = "#3b3a36"
LABEL  = "#857d70"
RULE   = "#d8d2c6"

def depth(n): return len(n.replace("Tree-", "").split(".")) if n else 99
def is_root(n): return depth(n) <= 2

def collect(root):
    seen, runs = set(), []
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
        ntac = sum(len(c.get("tactics", [])) for c in (m.get("committed_proofs") or []))
        if ntac <= 0: continue
        spawn = any(not is_root(n) for n in set(r.get("node") for r in rows))
        ic = Counter()
        for r in rows:
            it = r.get("intent") or {}; nm = it.get("intent") if isinstance(it, dict) else None
            if nm: ic[nm] += 1
        rec = ic.get("undo_last_step", 0) + ic.get("undo_to_checkpoint", 0) + ic.get("fresh_restart", 0) + ic.get("request_restart", 0) + (1 if spawn else 0)
        runs.append(dict(ntac=ntac, rec=rec, need=rec > 0))
    return runs

def build(runs, out):
    rmed = st.median(r["ntac"] for r in runs)
    easy = [r for r in runs if r["ntac"] < rmed]; hard = [r for r in runs if r["ntac"] >= rmed]
    se = 100 * sum(1 for r in easy if r["need"]) / len(easy)
    sh = 100 * sum(1 for r in hard if r["need"]) / len(hard)
    me = sum(r["rec"] for r in easy) / len(easy); mh = sum(r["rec"] for r in hard) / len(hard)

    W = 720; H = W   # square canvas (QuickLook SVG thumbnailer clips width at x≈height)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Helvetica,Arial">',
         f'<rect width="{W}" height="{H}" fill="white"/>']
    s.append(f'<text x="{W/2}" y="40" font-size="17" font-weight="bold" fill="{TEXT}" text-anchor="middle">Hard proofs require backtracking; easy proofs derive linearly</text>')
    s.append(f'<text x="{W/2}" y="62" font-size="11.5" fill="{LABEL}" text-anchor="middle">backtracking = undo · backjump-to-checkpoint · restart · branch(fork), beyond a linear forward derivation  ·  n={len(runs)} solved proofs</text>')

    def panel(cx, w, tag, title, ev, hv, fmt, delta):
        bw, gap, base, topb = 78, 44, 300, 130
        maxv = max(ev, hv) * 1.3 or 1
        s.append(f'<text x="{cx+w/2}" y="100" font-size="11" fill="{LABEL}" text-anchor="middle" letter-spacing="1.5">{tag}</text>')
        s.append(f'<text x="{cx+w/2}" y="120" font-size="13.5" font-weight="bold" fill="{TEXT}" text-anchor="middle">{title}</text>')
        xe = cx + w/2 - bw - gap/2; xh = cx + w/2 + gap/2
        he = (base - topb) * ev / maxv; hh = (base - topb) * hv / maxv
        s.append(f'<rect x="{xe}" y="{base-he:.1f}" width="{bw}" height="{he:.1f}" rx="3" fill="{SAGE}"/>')
        s.append(f'<rect x="{xh}" y="{base-hh:.1f}" width="{bw}" height="{hh:.1f}" rx="3" fill="{CLAY}"/>')
        s.append(f'<text x="{xe+bw/2}" y="{base-he-9:.1f}" font-size="17" font-weight="bold" fill="{TEXT}" text-anchor="middle">{fmt(ev)}</text>')
        s.append(f'<text x="{xh+bw/2}" y="{base-hh-9:.1f}" font-size="17" font-weight="bold" fill="{TEXT}" text-anchor="middle">{fmt(hv)}</text>')
        s.append(f'<line x1="{xe-6}" y1="{base}" x2="{xh+bw+6}" y2="{base}" stroke="{RULE}"/>')
        s.append(f'<text x="{xe+bw/2}" y="{base+18}" font-size="12" fill="{LABEL}" text-anchor="middle" letter-spacing="1">EASY</text>')
        s.append(f'<text x="{xh+bw/2}" y="{base+18}" font-size="12" fill="{LABEL}" text-anchor="middle" letter-spacing="1">HARD</text>')
        s.append(f'<text x="{cx+w/2}" y="{base+46}" font-size="16" font-weight="bold" fill="{DELTA}" text-anchor="middle">{delta}</text>')

    panel(20, 340, "(a)", "Proofs requiring backtracking", se, sh, lambda v: f"{v:.0f}%", f"{sh/se:.1f}× more")
    panel(360, 340, "(b)", "Mean backtracking ops / proof", me, mh, lambda v: f"{v:.2f}", f"{mh/me:.1f}× more")
    s.append(f'<text x="{W/2}" y="378" font-size="11" fill="{LABEL}" text-anchor="middle">difficulty split at the median committed-tactic count ({rmed:.0f})</text>')
    s.append('</svg>')
    open(out, "w").write("\n".join(s))
    print(f"easy {se:.0f}%/{me:.2f}  hard {sh:.0f}%/{mh:.2f}  -> {out}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="agent_view_runs")
    ap.add_argument("--out", default="tools/compiler_metrics/tree_figures/fig_backtracking_summary.svg")
    a = ap.parse_args()
    build(collect(a.root), a.out)

if __name__ == "__main__":
    main()
