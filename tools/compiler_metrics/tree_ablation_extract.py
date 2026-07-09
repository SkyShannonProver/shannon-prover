#!/usr/bin/env python3
"""Tree-search ablation extractor.

Statically pulls the *computable* parts of the proposed tree-search ablation
metric out of committed run-report bundles under ``agent_view_runs/``. It does
NOT re-run anything. Its job is to show, on the clean controlled comparisons we
actually have, what the metric machinery produces today -- and to make the data
gaps explicit (which cells lack token data, which lack a single-vs-multi-tree
pair).

What it computes per run (when the bundle carries per-step ``usage`` tokens):
  * deduped outcome (solved = committed ``qed.``), with resume-chunk detection
  * total output / input / cache tokens
  * cumulative-token-to-qed  (output-token budget consumed at the qed turn,
    merged chronologically across tree nodes)
  * per-node output-token breakdown, winning node, and losing-branch share
    (= output tokens spent on nodes that did NOT reach qed / total) -- the
    "budget burned on a dead route" mechanism number, only meaningful for
    trees > 1.

Headline caveat surfaced by the report: with token data present there is
currently *no* clean single-tree-vs-multi-tree controlled cell, so the actual
tree metric (pass@budget, single vs multi) cannot be produced from existing
bundles -- only the per-run primitives and the L1/L4 (probe) control can.

Usage:
    python3 tools/compiler_metrics/tree_ablation_extract.py [--root agent_view_runs] [--json out.json]
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import glob
import json
import os
from typing import Any, Optional


# --------------------------------------------------------------------------- io

def _load(path: str) -> Optional[dict]:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def _rows(report: dict) -> list[dict]:
    return [r for run in report.get("runs", []) for r in run.get("rows", [])]


def _ts(row: dict) -> Optional[_dt.datetime]:
    """Best-effort chronological key for a row."""
    for key in ("action_submitted_at", "manager_result_at"):
        v = row.get(key)
        if not v:
            continue
        try:
            return _dt.datetime.fromisoformat(v)
        except Exception:
            pass
    return None


def _u(row: dict, field: str) -> int:
    return int((row.get("usage") or {}).get(field, 0) or 0)


def _is_qed_commit(row: dict) -> bool:
    summ = (row.get("intent_summary") or "").lower()
    return "qed" in summ and bool(row.get("ok"))


# ---------------------------------------------------------------- per-run record

class Run:
    __slots__ = ("lemma", "profile", "model", "trees", "commit", "outcome",
                 "solved", "resumed", "has_tokens", "run_iter", "bundle",
                 "out_tok", "in_tok", "cache_tok", "tok_to_qed",
                 "per_node_out", "qed_node", "losing_share")

    def __init__(self, meta: dict, report: dict, bundle: str):
        self.bundle = bundle
        self.lemma = meta.get("lemma")
        self.profile = meta.get("surface_profile") or None
        self.model = meta.get("model") or None
        self.trees = meta.get("trees")
        self.commit = meta.get("commit")
        self.outcome = meta.get("outcome") or ""
        self.solved = self.outcome.startswith("proved")
        self.run_iter = meta.get("run_iteration_dir") or ""
        low = self.run_iter.lower()
        self.resumed = ("chunk" in low) or ("resume" in low)

        rows = _rows(report)
        self.has_tokens = bool(rows and (rows[0].get("usage")))

        self.out_tok = self.in_tok = self.cache_tok = 0
        self.tok_to_qed: Optional[int] = None
        self.per_node_out: dict[str, int] = {}
        self.qed_node: Optional[str] = None
        self.losing_share: Optional[float] = None
        if not self.has_tokens:
            return

        per_node: dict[str, int] = collections.defaultdict(int)
        for r in rows:
            self.out_tok += _u(r, "output_tokens")
            self.in_tok += _u(r, "input_tokens")
            self.cache_tok += _u(r, "cache_creation_input_tokens")
            per_node[r.get("node")] += _u(r, "output_tokens")
            if self.qed_node is None and _is_qed_commit(r):
                self.qed_node = r.get("node")
        self.per_node_out = dict(per_node)

        # cumulative output-token budget at the qed turn (chronological merge)
        ordered = sorted(rows, key=lambda r: (_ts(r) or _dt.datetime.min, r.get("turn", 0)))
        cum = 0
        for r in ordered:
            cum += _u(r, "output_tokens")
            if _is_qed_commit(r):
                self.tok_to_qed = cum
                break

        if self.trees and self.trees > 1 and self.out_tok > 0 and self.qed_node:
            winner = self.per_node_out.get(self.qed_node, 0)
            self.losing_share = round((self.out_tok - winner) / self.out_tok, 3)

    # convenience
    def cell(self) -> tuple:
        return (self.lemma, self.profile, self.model, self.trees)


# ------------------------------------------------------------------- collection

def collect(root: str) -> list[Run]:
    runs: list[Run] = []
    seen_iter: set[str] = set()
    for tr in sorted(glob.glob(os.path.join(root, "*", "*", "timeline_report.json"))):
        d = os.path.dirname(tr)
        meta = _load(os.path.join(d, "run_meta.json"))
        report = _load(tr)
        if meta is None or report is None:
            continue
        rec = Run(meta, report, os.path.basename(d))
        # drop duplicate bundles of the same underlying run iteration
        if rec.run_iter and rec.run_iter in seen_iter:
            continue
        if rec.run_iter:
            seen_iter.add(rec.run_iter)
        runs.append(rec)
    return runs


# ---------------------------------------------------------------------- reports

def _fmt_int(n: Optional[int]) -> str:
    return "-" if n is None else f"{n:,}"


def report(runs: list[Run]) -> None:
    tok = [r for r in runs if r.has_tokens]
    print("=" * 78)
    print("TREE-SEARCH ABLATION  -- statically computable parts from committed bundles")
    print("=" * 78)
    print(f"deduped run bundles      : {len(runs)}")
    print(f"  with per-step tokens   : {len(tok)}   (the rest cannot feed any token metric)")
    print(f"  solved (committed qed) : {sum(1 for r in runs if r.solved)}")
    print(f"  resume chunks (partial): {sum(1 for r in runs if r.resumed)}")
    td = collections.Counter(r.trees for r in runs)
    print(f"  trees distribution     : {dict(sorted(td.items(), key=lambda kv: (kv[0] is None, kv[0])))}")

    # ---- 1. THE TREE AXIS: L4 single-vs-multi controlled cells ---------------
    # The ablation is one tree vs many trees, BOTH under L4. We must also hold
    # the model fixed -- multi-tree runs are heavily opus-4-6, single-tree are
    # opus-4-8, so an uncontrolled split would measure the model, not the tree.
    L4 = "l4_checked_action_surface"
    print("\n" + "-" * 78)
    print("1) L4 SINGLE-vs-MULTI-TREE cells  (profile=L4, hold MODEL fixed, vary trees)")
    print("-" * 78)
    by_lm = collections.defaultdict(set)
    by_lm_tok = collections.defaultdict(set)
    for r in runs:
        if r.profile != L4 or r.resumed:
            continue
        by_lm[(r.lemma, r.model)].add(r.trees)
        if r.has_tokens:
            by_lm_tok[(r.lemma, r.model)].add(r.trees)
    pairs = {k: v for k, v in by_lm.items()
             if 1 in v and any(t and t > 1 for t in v)}
    pairs_tok = {k: v for k, v in by_lm_tok.items()
                 if 1 in v and any(t and t > 1 for t in v)}
    if not pairs:
        print("  NONE -- no lemma has L4 trees=1 and L4 trees>1 at the same model.")
    else:
        for k, v in sorted(pairs.items(), key=lambda kv: str(kv[0])):
            print(f"  {k}  trees={sorted(t for t in v if t)}")
    print(f"  ...of which with token data on BOTH arms: {len(pairs_tok)}")
    print("  => pass@budget (single vs multi, L4) is NOT computable today.")

    # ---- 2. L4 single vs multi, per lemma, outcomes + tokens + model exposed -
    print("\n" + "-" * 78)
    print("2) L4 SINGLE vs MULTI per lemma  (model shown to expose the confound)")
    print("   each run: outcome / out_tok / trees / model-tail")
    print("-" * 78)
    arms = collections.defaultdict(lambda: {"single": [], "multi": []})
    for r in runs:
        if r.profile != L4 or r.resumed:
            continue
        if r.trees == 1:
            arms[r.lemma]["single"].append(r)
        elif r.trees and r.trees > 1:
            arms[r.lemma]["multi"].append(r)

    def _cell(lst: list[Run]) -> str:
        if not lst:
            return "-"
        out = []
        for r in lst:
            t = f"{r.out_tok // 1000}k" if r.has_tokens else "noT"
            tail = (r.model or "?").split("-")[-1]
            out.append(f"{'OK' if r.solved else 'x'}/{t}/t{r.trees}/{tail}")
        return " ".join(out)

    both = {L: a for L, a in arms.items() if a["single"] and a["multi"]}
    print(f"  {'lemma':24s} | {'SINGLE trees=1':30s} | MULTI trees>1")
    for L, a in sorted(both.items()):
        print(f"  {L:24s} | {_cell(a['single']):30s} | {_cell(a['multi'])}")
    print(f"  lemmas with BOTH L4 arms: {len(both)}   "
          "(OK/x=solved, out_tok, t=#trees, model-tail; noT=no token data)")

    # ---- 3. Multi-tree runs: losing-branch share (dead-route budget) ---------
    print("\n" + "-" * 78)
    print("3) MULTI-TREE RUNS (trees>1) WITH TOKENS  -- losing-branch output-token share")
    print("   = fraction of generation budget spent on nodes that never reached qed")
    print("-" * 78)
    mt = [r for r in tok if r.trees and r.trees > 1]
    if mt:
        print(f"  {'lemma':22s} {'prof':6s} trees {'out_tok':>9s}  qed_node  losing%  outcome")
        for r in sorted(mt, key=lambda r: str(r.lemma)):
            pf = "L1" if r.profile == "l1_goal_projection" else ("L4" if r.profile == "l4_checked_action_surface" else "-")
            share = "-" if r.losing_share is None else f"{r.losing_share*100:4.0f}%"
            print(f"  {str(r.lemma):22s} {pf:6s} {r.trees:^5d} {_fmt_int(r.out_tok):>9s}  "
                  f"{str(r.qed_node or '-'):8s}  {share:>6s}  {r.outcome}")
        print("  (losing% only defined when a node reached qed; '-' = no qed / single survivor)")
    else:
        print("  (none)")

    # ---- 4. Seed-repeat cells: token spread at identical config --------------
    print("\n" + "-" * 78)
    print("4) SEED-REPEAT CELLS WITH TOKENS  (>=2 runs at identical lemma+profile+model+trees)")
    print("   the only place we can see run-to-run spread today")
    print("-" * 78)
    cells = collections.defaultdict(list)
    for r in tok:
        if r.profile and r.model:
            cells[r.cell()].append(r)
    rep = {k: v for k, v in cells.items() if len(v) >= 2}
    if rep:
        for k, v in sorted(rep.items(), key=lambda kv: str(kv[0])):
            outs = collections.Counter("solved" if x.solved else "fail" for x in v)
            otoks = sorted(x.out_tok for x in v)
            print(f"  {k}  n={len(v)}  outcomes={dict(outs)}  out_tok={[f'{t:,}' for t in otoks]}")
    else:
        print("  (no real seed-repeat cell with token data)")

    print("\n" + "=" * 78)
    print("BOTTOM LINE: token primitives work; the L1/L4 control is clean; but the")
    print("single-vs-multi-tree cell is empty -> the tree ablation needs a purpose-run")
    print("sweep (fix lemma/model/profile/commit, token cap, vary trees, K seeds).")
    print("=" * 78)


# ---------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="agent_view_runs")
    ap.add_argument("--json", default=None, help="optional path to dump per-run records")
    args = ap.parse_args()

    runs = collect(args.root)
    report(runs)

    if args.json:
        dump = [{k: getattr(r, k) for k in Run.__slots__} for r in runs]
        with open(args.json, "w") as fh:
            json.dump(dump, fh, indent=2)
        print(f"\nwrote {len(dump)} records -> {args.json}")


if __name__ == "__main__":
    main()
