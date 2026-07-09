#!/usr/bin/env python3
"""Tree-search tradeoff extractor (3-config sweep).

Reads the committed run-report bundles produced by the three tradeoff suites
(tree_tradeoff_single / _racing / _orch) and places each configuration on the
latency-vs-cost plane:

    x = total output tokens consumed   (COST)
    y = wall-clock seconds to qed      (LATENCY)
    (+ critical-path turns on the winning tree = infra-robust latency proxy)

Per (config, lemma) it aggregates over the K seeds (the r01..rNN repeats):
  * solve rate          (#qed / #runs)
  * total output tokens (median over runs)            -- cost axis
  * wall-clock to qed   (median over SOLVED runs)     -- latency axis
  * critical-path turns (median over SOLVED runs)     -- robust latency proxy

Config is read from the run_iteration_dir path (which contains the suite name),
so NO code change to the prover is needed -- just run the three suites.

Usage:
    python3 tools/compiler_metrics/tree_tradeoff_extract.py \
        [--root agent_view_runs] [--json tradeoff_points.json]
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import glob
import json
import os
import re
import statistics
from typing import Optional

# suite-name substring  ->  human config label (sorted display order by key)
CONFIG_MAP = {
    "tree_tradeoff_single": "1_single",
    "tree_tradeoff_racing": "2_racing",
    "tree_tradeoff_orch":   "3_orch",
}


def _load(p: str) -> Optional[dict]:
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return None


def _ts(s: Optional[str]) -> Optional[_dt.datetime]:
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s)
    except Exception:
        return None


def _u(row: dict, f: str) -> int:
    return int((row.get("usage") or {}).get(f, 0) or 0)


def _is_qed(row: dict) -> bool:
    return "qed" in (row.get("intent_summary") or "").lower() and bool(row.get("ok"))


def _config_of(run_iter: str) -> Optional[str]:
    for sub, label in CONFIG_MAP.items():
        if sub in run_iter:
            return label
    return None


def _seed_of(run_iter: str) -> Optional[str]:
    m = re.search(r"/r(\d+)/", run_iter)
    return m.group(1) if m else None


class Run:
    def __init__(self, meta: dict, report: dict, bundle: str):
        self.bundle = bundle
        self.lemma = meta.get("lemma")
        self.run_iter = meta.get("run_iteration_dir") or ""
        self.config = _config_of(self.run_iter)
        self.seed = _seed_of(self.run_iter)
        self.trees = meta.get("trees")
        self.solved = (meta.get("outcome") or "").startswith("proved")
        self.timeout_capped = False

        rows = [r for run in report.get("runs", []) for r in run.get("rows", [])]
        self.has_tokens = bool(rows and rows[0].get("usage"))
        self.total_out = sum(_u(r, "output_tokens") for r in rows)

        # wall-clock + critical path to qed (winning tree only)
        self.wall_s: Optional[float] = None
        self.crit_turns: Optional[int] = None
        self.qed_node: Optional[str] = None
        starts = [_ts(r.get("action_submitted_at")) for r in rows]
        starts = [t for t in starts if t]
        t0 = min(starts) if starts else None
        qed_row = next((r for r in rows if _is_qed(r)), None)
        if qed_row and t0:
            self.qed_node = qed_row.get("node")
            done = _ts(qed_row.get("manager_result_at")) or _ts(qed_row.get("action_submitted_at"))
            if done:
                self.wall_s = (done - t0).total_seconds()
            qturn = qed_row.get("turn", 0)
            self.crit_turns = sum(
                1 for r in rows
                if r.get("node") == self.qed_node and (r.get("turn", 0) <= qturn)
            )

        # crude wall-clock-cap flag: ran long, never solved (likely killed, not give-up)
        end = max((_ts(r.get("manager_result_at")) for r in rows
                   if _ts(r.get("manager_result_at"))), default=None)
        if (not self.solved) and t0 and end and (end - t0).total_seconds() > 80 * 60:
            self.timeout_capped = True


def collect(root: str) -> list[Run]:
    out, seen = [], set()
    for tr in sorted(glob.glob(os.path.join(root, "*", "*", "timeline_report.json"))):
        d = os.path.dirname(tr)
        meta, rep = _load(os.path.join(d, "run_meta.json")), _load(tr)
        if meta is None or rep is None:
            continue
        r = Run(meta, rep, os.path.basename(d))
        if r.config is None:           # not one of our three suites
            continue
        if r.run_iter in seen:         # de-dup re-bundled runs
            continue
        seen.add(r.run_iter)
        out.append(r)
    return out


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _fmt(x, unit=""):
    if x is None:
        return "-"
    if unit == "k":
        return f"{x/1000:.0f}k"
    if unit == "s":
        return f"{x:.0f}s"
    return f"{x:.0f}"


def report(runs: list[Run]) -> dict:
    by_cfg_lemma = collections.defaultdict(list)
    for r in runs:
        by_cfg_lemma[(r.config, r.lemma)].append(r)

    configs = sorted({r.config for r in runs})
    lemmas = sorted({r.lemma for r in runs})

    print("=" * 96)
    print("TREE-SEARCH TRADEOFF  -  latency (wall-clock to qed)  vs  cost (total output tokens)")
    print("=" * 96)
    notok = [r for r in runs if not r.has_tokens]
    capped = [r for r in runs if r.timeout_capped]
    print(f"runs: {len(runs)}   configs: {configs}   lemmas: {len(lemmas)}")
    if notok:
        print(f"WARNING: {len(notok)} runs have NO per-step tokens -> cost axis missing for them")
    if capped:
        print(f"WARNING: {len(capped)} unsolved runs ran >80min -> likely wall-clock-CAPPED (censored cost)")

    # ---- per (config, lemma) -------------------------------------------------
    print("\n" + "-" * 96)
    print("PER LEMMA  (median over seeds; latency/turns over SOLVED runs only)")
    print("-" * 96)
    print(f"  {'lemma':22s} {'config':9s} {'n':>2s} {'solved':>7s}  "
          f"{'cost(out_tok)':>13s}  {'latency':>8s}  {'crit_turns':>10s}")
    points = []
    for lemma in lemmas:
        for cfg in configs:
            rs = by_cfg_lemma.get((cfg, lemma), [])
            if not rs:
                continue
            n = len(rs)
            nsolved = sum(1 for r in rs if r.solved)
            cost = _med([r.total_out for r in rs if r.has_tokens])
            lat = _med([r.wall_s for r in rs if r.solved])
            turns = _med([r.crit_turns for r in rs if r.solved])
            print(f"  {str(lemma):22s} {cfg:9s} {n:>2d} {f'{nsolved}/{n}':>7s}  "
                  f"{_fmt(cost,'k'):>13s}  {_fmt(lat,'s'):>8s}  {_fmt(turns):>10s}")
            points.append(dict(config=cfg, lemma=lemma, n=n, solved=nsolved,
                               cost_out_tok=cost, latency_s=lat, crit_turns=turns))
        print()

    # ---- per config aggregate (the 3 points on the plane) --------------------
    print("-" * 96)
    print("PER CONFIG  (the three points on the tradeoff plane; medians across all runs/lemmas)")
    print("-" * 96)
    print(f"  {'config':9s} {'n':>3s} {'solve_rate':>10s}  {'cost(out_tok)':>13s}  "
          f"{'latency':>8s}  {'crit_turns':>10s}")
    agg = {}
    for cfg in configs:
        rs = [r for r in runs if r.config == cfg]
        n = len(rs)
        sr = sum(1 for r in rs if r.solved) / n if n else 0
        cost = _med([r.total_out for r in rs if r.has_tokens])
        lat = _med([r.wall_s for r in rs if r.solved])
        turns = _med([r.crit_turns for r in rs if r.solved])
        print(f"  {cfg:9s} {n:>3d} {sr*100:>9.0f}%  {_fmt(cost,'k'):>13s}  "
              f"{_fmt(lat,'s'):>8s}  {_fmt(turns):>10s}")
        agg[cfg] = dict(n=n, solve_rate=sr, cost_out_tok=cost, latency_s=lat, crit_turns=turns)

    print("\n" + "=" * 96)
    print("READ: config 1=single(serial), 2=racing(dumb parallel), 3=orch(smart).")
    print("WIN for the orchestrator (3): lower cost than 2 at comparable latency,")
    print("i.e. point 3 sits to the LOWER-LEFT of the 1--2 line (Pareto improvement).")
    print("=" * 96)
    return {"points": points, "config_aggregate": agg}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="agent_view_runs")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    runs = collect(args.root)
    if not runs:
        print("No runs from the tree_tradeoff_* suites found under", args.root)
        print("(Have the three suites been run, and are their bundles in agent_view_runs/?)")
        return
    out = report(runs)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=2)
        print(f"\nwrote plane coordinates -> {args.json}")


if __name__ == "__main__":
    main()
