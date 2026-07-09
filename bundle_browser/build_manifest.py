#!/usr/bin/env python3
"""Scan agent_view_runs/ -> manifest.json for the bundle browser.

Every prover run bundle (agent_view_runs/<lemma>/<timestamp>__<commit>/) carries a
run_meta.json; this collects them into one manifest the static browser loads to
render the filterable list. Per-step artifacts are NOT indexed here — the browser
reads each bundle's own timeline_report.json on demand.

TIER (public vs private) is FAIL-CLOSED: a bundle is `public` ONLY when its source
file is on the PUBLIC_SOURCE allowlist below; everything else -> `private` (the
private held-out corpus, the private benchmark repo, absolute paths,
unknown/empty source). `--public` drops private bundles entirely so a hosted build
can never leak them. Locally (no flag) private bundles are kept and the browser
badges them with a lock. REVIEW the allowlist before any public/hosted build.

  python3 bundle_browser/build_manifest.py            # local: all bundles
  python3 bundle_browser/build_manifest.py --public   # hosted: public tier-A only
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = "agent_view_runs"

# --- TIER CONFIG (edit me) ---------------------------------------------------
# A bundle is PUBLIC only when its source_file contains one of these substrings.
# Only the private held-out corpus is contamination tier-C; ChaChaPoly / MEE-CBC
# are public tier-A corpus (owner confirmed 2026-07-08). Absolute-path / unknown sources
# still fail closed to private. Locally everything shows regardless (with a
# lock badge).
PUBLIC_SOURCE = (
    "eval/examples/PIR.ec",
    "eval/examples/br93.ec",
    "eval/examples/elgamal.ec",
    "eval/examples/Pedersen.ec",
    "eval/examples/SchnorrPK.ec",
    "eval/examples/PRG.ec",
    "eval/examples/Dice4_6.ec",
    "eval/examples/cramer-shoup/",
    "eval/examples/ChaChaPoly/",
    "eval/examples/MEE-CBC/",
)


def tier_of(source_file: str) -> str:
    s = source_file or ""
    return "public" if any(p in s for p in PUBLIC_SOURCE) else "private"
# ----------------------------------------------------------------------------

PROFILE = {
    "l1_goal_projection": "L1",
    "l2_semantic_ir": "L2",
    "l3_flow_navigation": "L3",
    "l4_checked_action_surface": "L4",
    "adaptive": "adaptive",
    "": "?",
}
OUTCOME = {
    "proved": "proved",
    "incomplete (timeout/open)": "open",
    "proved_in_session (final verification failed)": "verify_failed",
}


def date_of(ts: str) -> str:
    parts = (ts or "").split("_")
    d = parts[0] if parts else ""
    hm = parts[1] if len(parts) > 1 and parts[1].isdigit() and len(parts[1]) == 4 else ""
    return f"{d} {hm[:2]}:{hm[2:]}" if hm else d


def view_roots(bundle_abs: str) -> list[str]:
    """Candidate sub-dirs under views/ that nest the trees (e.g. ["c0", "c2"] for
    an aggregated multi-candidate bundle). Empty for the common flat layout
    (views/Tree_x/...). The browser tries the flat path first, then these, so a
    file stored at views/<cand>/Tree_x/... is still reachable."""
    vdir = os.path.join(bundle_abs, "views")
    roots: list[str] = []
    if not os.path.isdir(vdir):
        return roots
    for nm in sorted(os.listdir(vdir)):
        if nm == "_bootstrap" or nm.startswith("Tree"):
            continue
        sub = os.path.join(vdir, nm)
        if os.path.isdir(sub) and any(c.startswith("Tree") for c in os.listdir(sub)):
            roots.append(nm)
    return roots


def record(meta: dict, bundle_dir: str, bundle_abs: str) -> dict:
    cps = meta.get("committed_proofs") or []
    src = meta.get("source_file") or ""
    prof = meta.get("surface_profile") or ""
    out = meta.get("outcome") or ""
    return {
        "id": bundle_dir.replace("/", "__"),
        "dir": bundle_dir,                       # relative to agent_view_runs/
        "lemma": meta.get("lemma") or "?",
        "source": os.path.basename(src) or "?",  # basename only — never leak an absolute private path
        "profile": PROFILE.get(prof, prof or "?"),
        "model": meta.get("model") or "?",
        "outcome": OUTCOME.get(out, out or "?"),
        "turns": meta.get("turn_count") or 0,
        "trees": meta.get("trees") or len(cps) or 1,
        "date": date_of(meta.get("timestamp") or os.path.basename(bundle_dir)),
        "timestamp": meta.get("timestamp") or "",
        "commit": meta.get("commit") or "",
        "eval_mode": bool(meta.get("eval_mode")),
        "tier": tier_of(src),
        "proved": out == "proved",
        "view_roots": view_roots(bundle_abs),
        "per_tree": [
            {
                "tree": c.get("tree"),
                "proved": bool(c.get("proved")),
                "tactics": c.get("tactics") or [],
            }
            for c in cps
        ],
    }


def build(root: str, public_only: bool) -> dict:
    recs: list[dict] = []
    pattern = os.path.join(root, RUNS_DIR, "*", "*", "run_meta.json")
    for mp in sorted(glob.glob(pattern)):
        try:
            meta = json.load(open(mp))
        except Exception as exc:  # noqa: BLE001
            print(f"skip {mp}: {exc}", file=sys.stderr)
            continue
        bundle_abs = os.path.dirname(mp)
        bundle_dir = os.path.relpath(bundle_abs, os.path.join(root, RUNS_DIR))
        recs.append(record(meta, bundle_dir, bundle_abs))
    if public_only:
        recs = [r for r in recs if r["tier"] == "public"]
    recs.sort(key=lambda r: r["timestamp"], reverse=True)
    return {
        "generated_for": "public" if public_only else "local",
        "runs_base": RUNS_DIR,
        "count": len(recs),
        "bundles": recs,
    }


def build_multi(roots: list, public_only: bool) -> dict:
    """Merge bundles from several repo roots (each scanned at <root>/agent_view_runs/).

    `roots` is a list of (base_url, root) pairs. A bundle's artifacts are fetched
    from `base_url + dir + ...` so the browser reaches the right worktree mount; an
    empty base_url means the default served mount (../agent_view_runs/). The SAME
    committed bundle exists in every worktree, so dedup by id and let the FIRST root
    win — list the primary/served root first. Dedup happens BEFORE reading run_meta,
    so scanning many worktrees only reads each unique bundle once.
    """
    seen: set[str] = set()
    merged: list[dict] = []
    for base_url, root in roots:
        pattern = os.path.join(root, RUNS_DIR, "*", "*", "run_meta.json")
        for mp in sorted(glob.glob(pattern)):
            bundle_abs = os.path.dirname(mp)
            bundle_dir = os.path.relpath(bundle_abs, os.path.join(root, RUNS_DIR))
            bid = bundle_dir.replace("/", "__")
            if bid in seen:
                continue
            try:
                meta = json.load(open(mp))
            except Exception as exc:  # noqa: BLE001
                print(f"skip {mp}: {exc}", file=sys.stderr)
                continue
            seen.add(bid)
            rec = record(meta, bundle_dir, bundle_abs)
            rec["base"] = base_url
            merged.append(rec)
    if public_only:
        merged = [r for r in merged if r["tier"] == "public"]
    merged.sort(key=lambda r: r["timestamp"], reverse=True)
    return {
        "generated_for": "public" if public_only else "local",
        "runs_base": RUNS_DIR,
        "count": len(merged),
        "bundles": merged,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--public", action="store_true", help="drop private (tier-C) bundles")
    ap.add_argument("--root", default=REPO_ROOT, help="repo root (default: parent of bundle_browser/)")
    ap.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json"),
    )
    args = ap.parse_args()
    data = build(args.root, args.public)
    with open(args.out, "w") as fh:
        json.dump(data, fh, indent=2)
    pub = sum(1 for r in data["bundles"] if r["tier"] == "public")
    priv = data["count"] - pub
    print(f"wrote {args.out}: {data['count']} bundles ({pub} public, {priv} private)")


if __name__ == "__main__":
    main()
