#!/usr/bin/env python3
"""
Stuck-metric pipeline for the proof-state compiler (L4) vs bare goal (L1).

Implements the design we converged on:

  * Progress is anchored to EasyCrypt ground truth: the committed-goal fingerprint
    (current_goal.lines hash). Probes/inspects/lookups do NOT move it; only an
    accepted, *surviving* commit does.
  * DURABLE progress = a commit that is never popped by a later undo (survives to
    the final committed stack). "Advanced then undone" yields zero durable progress.
  * First error on an obstacle = the model's prior (excluded from compiler credit).
    What the compiler is judged on = how often / how long the agent stays stuck
    AFTER the first error.
  * A stuck episode = a span between durable-progress points that contains >=1 error
    (commit_REJ / probe_FAIL)  -> FRICTION (mechanical, type (1)).
  * A clean undo (depth drop with NO error in the undone span) is AMBIGUOUS:
    (2) wrong-path  vs  (3) strategic-restructure  -> flagged for the LLM layer.

Stages:
  collect   build a deduped symlink collection of all bundles
  compute   mechanical stuck metrics + export flagged episodes for the LLM
  annotate  run `claude -p` on flagged episodes (cause + (2)/(3) classification)
  clean_chart  render the 4-panel L1 vs L4 figure (the paper figure)
  all       collect -> compute -> clean_chart in one shot (TURNKEY)

Usage:
  # TURNKEY: auto-discover bundles under ./agent_view_runs + ./artifacts/eval_suite,
  # then write stuck_out/stuck_clean_subset.png  (the 4-panel figure)
  python3 stuck_pipeline.py all

  # point at explicit bundle dir(s) (positional, after the stage name):
  python3 stuck_pipeline.py all /path/to/agent_view_runs /another/dir
  #   or via env:  BUNDLE_ROOTS="/dir1:/dir2" python3 stuck_pipeline.py all
"""
import json, os, glob, hashlib, sys, subprocess, re
from collections import Counter, defaultdict

HOME = os.path.expanduser("~")
ROOT = os.path.dirname(os.path.abspath(__file__))
COLL = os.path.join(ROOT, "bundles")          # deduped symlink collection
OUT  = os.path.join(ROOT, "stuck_out")
os.makedirs(OUT, exist_ok=True)

def resolve_roots(extra):
    """Bundle search roots, in priority order:
       1. positional args after the stage name
       2. env BUNDLE_ROOTS  (colon-separated)
       3. ./agent_view_runs and ./artifacts/eval_suite under the CWD
    eval_suite.run writes bundles into <repo>/agent_view_runs/, so the default
    'just works' when run from the repo root after an ablation."""
    if extra:
        return [os.path.abspath(p) for p in extra]
    env = os.environ.get("BUNDLE_ROOTS", "").strip()
    if env:
        return [os.path.abspath(p) for p in env.split(":") if p]
    cwd = os.getcwd()
    return [os.path.join(cwd, "agent_view_runs"),
            os.path.join(cwd, "artifacts", "eval_suite")]

# destructive (unambiguously wasteful) turn intents = hard restarts only.
# Rejects handled separately via cls. undo is EXCLUDED: mechanically it cannot be told
# apart from a *strategic* restructure undo, and undo-stuck is the weak-invariant/(2)
# semantic bucket we deliberately do NOT headline.
DESTR_INTENTS = {"fresh_restart", "request_restart"}

# ---------- shared helpers ----------
def is_bundle(d):
    return (os.path.isfile(os.path.join(d, "run_meta.json"))
            and os.path.isfile(os.path.join(d, "timeline_report.json"))
            and os.path.isdir(os.path.join(d, "views")))

def find_bundles(root):
    out = []
    if not os.path.isdir(root): return out
    for f in glob.glob(os.path.join(root, "**", "run_meta.json"), recursive=True):
        d = os.path.dirname(f)
        if is_bundle(d): out.append(d)
    return out

def arm_of(profile):
    p = (profile or "")
    return "L1" if p.startswith("l1") else ("L4" if p.startswith("l4") else "??")

def gi(r):
    it = r.get("intent"); return it.get("intent", "?") if isinstance(it, dict) else (it if isinstance(it, str) else "?")

def gtac(r):
    it = r.get("intent"); return it.get("payload", {}).get("tactic", "") if isinstance(it, dict) else ""

def cls_of(mr):
    o = " ".join(a.get("outcome", "") for a in mr.get("manager_actions", []))
    if "accepted the committed" in o: return "commit_ok"
    if "rejected the committed" in o: return "commit_REJ"
    if "accepted this read-only probe" in o: return "probe_ok"
    if "probe tool failed" in o: return "probe_FAIL"
    return "other"

def node_dir(node): return node.replace("Tree-", "Tree_").replace(".", "_")

def goal_hash(bundle, ndir, turn):
    try:
        d = json.load(open(os.path.join(bundle, "views", ndir, f"turn_{turn:03d}.json")))
    except Exception:
        return None
    return hashlib.md5("\n".join(d.get("current_goal", {}).get("lines", [])).encode()).hexdigest()[:10]

# ============================================================ COLLECT
def collect(roots=None):
    roots = roots or resolve_roots(None)
    print("collect: searching roots:")
    for r in roots:
        print(f"   {r}  {'(missing)' if not os.path.isdir(r) else ''}")
    os.makedirs(COLL, exist_ok=True)
    seen, made = {}, 0
    for root in roots:
        for b in find_bundles(root):
            try: m = json.load(open(os.path.join(b, "run_meta.json")))
            except Exception: continue
            ident = (m.get("timestamp"), m.get("lemma"), m.get("surface_profile"),
                     m.get("commit_full") or m.get("commit"))
            if ident in seen: continue
            seen[ident] = b
            arm = arm_of(m.get("surface_profile"))
            name = f"{arm}__{m.get('lemma','?')}__{m.get('timestamp','?')}__{(m.get('commit') or '')[:8]}"
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
            link = os.path.join(COLL, name)
            if not os.path.lexists(link):
                os.symlink(b, link); made += 1
    print(f"collect: {len(seen)} unique bundles, {made} new symlinks -> {COLL}")
    # summary
    rows = []
    for link in sorted(glob.glob(os.path.join(COLL, "*"))):
        m = json.load(open(os.path.join(link, "run_meta.json")))
        rows.append((arm_of(m.get("surface_profile")), m.get("lemma"), m.get("outcome"),
                     (m.get("commit") or "")[:7], os.path.basename(link)))
    for r in sorted(rows):
        print(f"  {r[0]:3} {str(r[1]):26} {str(r[2]):26} {r[3]:8} {r[4]}")

# ============================================================ COMPUTE
def analyze_node(bundle, ndir, rows):
    # per-turn record
    mc = {}
    for f in glob.glob(os.path.join(bundle, "views", ndir, "manager_results", "turn_*.json")):
        try: d = json.load(open(f))
        except Exception: continue
        mc[d.get("turn")] = cls_of(d)
    seq = []
    for r in rows:
        t = r["turn"]
        seq.append(dict(turn=t, intent=gi(r), tac=gtac(r), cls=mc.get(t, "other"),
                        think=(r.get("agent_think_seconds") or 0.0),
                        mgr=(r.get("manager_seconds") or 0.0),
                        vc=(r.get("view_chars") or 0),
                        usage=(r.get("usage") or {}),
                        gh=goal_hash(bundle, ndir, t)))
    # ---- push/pop: mark durable vs retracted commits ----
    stack = []  # indices into seq of live commits
    for i, s in enumerate(seq):
        if s["cls"] == "commit_ok":
            stack.append(i); s["durable"] = True   # provisional
        elif s["intent"] == "undo_last_step":
            if stack:
                seq[stack.pop()]["durable"] = False
        # undo_to_checkpoint = menu in observed data; real pops come as undo_last_step
    # commits still on stack are durable; popped ones already set False
    for i, s in enumerate(seq):
        if s["cls"] != "commit_ok":
            s["durable"] = False
    # ---- segment into episodes between DURABLE progress events ----
    episodes = []
    cur = []
    for s in seq:
        cur.append(s)
        if s["cls"] == "commit_ok" and s["durable"] and s["gh"] is not None:
            # a durable progress step closes the current segment
            episodes.append(cur); cur = []
    tail = cur  # trailing segment with no closing durable progress (terminal)
    # ---- classify each closed segment ----
    results = []
    for ep in episodes:
        body = ep[:-1]  # turns before the closing durable-progress step
        errs = [s for s in body if s["cls"] in ("commit_REJ", "probe_FAIL")]
        undos = [s for s in body if s["intent"] in ("undo_last_step", "undo_to_checkpoint")]
        if errs:
            kind = "friction"           # type (1), mechanical
        elif undos:
            kind = "clean_undo"         # type (2)/(3) -> LLM
        else:
            kind = "progress"           # healthy (inspect/think then advance)
        if kind == "progress":
            continue
        # recovery time = time AFTER the first error, THROUGH the durable fix (inclusive).
        # The first error's own think is the model's prior, so it is excluded.
        first_err_i = next((k for k, s in enumerate(ep) if s["cls"] in ("commit_REJ", "probe_FAIL")), None)
        if first_err_i is not None:
            rec = ep[first_err_i+1:]
        else:
            rec = body  # clean undo: the whole detour (undo + rework) is the cost
        recover_time = sum(s["think"] + s["mgr"] for s in rec)
        destr_time = sum(s["think"] + s["mgr"] for s in rec
                         if s["cls"] == "commit_REJ" or s["intent"] in DESTR_INTENTS)
        results.append(dict(
            kind=kind,
            turns=[s["turn"] for s in body],
            n_err=len(errs),
            n_commit_rej=sum(1 for s in body if s["cls"] == "commit_REJ"),
            n_probe_fail=sum(1 for s in body if s["cls"] == "probe_FAIL"),
            n_undo=len(undos),
            recover_time=recover_time,
            destr_time=destr_time,
            recovered=True,
        ))
    # ---- terminal stuck (tail with errors/undos, never recovered) ----
    terminal = None
    if tail:
        errs = [s for s in tail if s["cls"] in ("commit_REJ", "probe_FAIL")]
        undos = [s for s in tail if s["intent"] in ("undo_last_step", "undo_to_checkpoint")]
        if errs or undos:
            first_err_i = next((k for k, s in enumerate(tail) if s["cls"] in ("commit_REJ", "probe_FAIL")), None)
            rec = tail[first_err_i+1:] if first_err_i is not None else tail
            terminal = dict(kind="terminal_stuck",
                            turns=[s["turn"] for s in tail],
                            n_err=len(errs), n_undo=len(undos),
                            n_commit_rej=sum(1 for s in tail if s["cls"] == "commit_REJ"),
                            n_probe_fail=sum(1 for s in tail if s["cls"] == "probe_FAIL"),
                            recover_time=sum(s["think"]+s["mgr"] for s in rec),
                            destr_time=sum(s["think"]+s["mgr"] for s in rec
                                           if s["cls"] == "commit_REJ" or s["intent"] in DESTR_INTENTS),
                            recovered=False)
    total_think = sum(s["think"] + s["mgr"] for s in seq)
    durable_progress = sum(1 for s in seq if s.get("durable"))
    # longest run of CONSECUTIVE committed rejects = the true "blind-retry depth"
    # (worst single retry storm; length-robust, unlike the total reject count).
    max_consec_rej = 0; _c = 0
    for s in seq:
        if s["cls"] == "commit_REJ":
            _c += 1; max_consec_rej = max(max_consec_rej, _c)
        else:
            _c = 0
    # CONTROL: first-contact error rate over UNIQUE tactics (dedup probe-then-commit-same).
    # Surface-agnostic proxy for "how often the model proposes a wrong tactic" = model capability.
    seen, uniq, first_fail = set(), 0, 0
    for s in seq:
        if s["intent"] in ("probe_tactic", "commit_tactic") and s["tac"]:
            if s["tac"] not in seen:
                seen.add(s["tac"]); uniq += 1
                if s["cls"] in ("commit_REJ", "probe_FAIL"): first_fail += 1
    # REAL per-turn tokens from the timeline `usage` field (written by the patched
    # report bundle). Use OUTPUT tokens: not cached, exact, = the model's generation
    # effort. Destructive share = output tokens on reject/restart turns / total output.
    tok_total = sum((s["usage"] or {}).get("output_tokens", 0) for s in seq)
    tok_destr = sum((s["usage"] or {}).get("output_tokens", 0) for s in seq
                    if s["cls"] == "commit_REJ" or s["intent"] in DESTR_INTENTS)
    has_tokens = any(s["usage"] for s in seq)
    # total SEGMENTS the proof was cut into (each closed episode = one forward-progress
    # segment; +1 for a non-empty trailing segment). This is the segment-unit denominator
    # so that "reject segments / total segments" is unit-consistent (segment ÷ segment).
    n_segments = len(episodes) + (1 if tail else 0)
    return results, terminal, dict(total_time=total_think, durable_progress=durable_progress,
                                   n_turns=len(seq), uniq_tac=uniq, first_fail=first_fail,
                                   tok_total=tok_total, tok_destr=tok_destr, has_tokens=has_tokens,
                                   max_consec_rej=max_consec_rej, n_segments=n_segments)

def compute():
    bundles = sorted(glob.glob(os.path.join(COLL, "*")))
    per_bundle = {}
    flagged = []   # clean_undo episodes for LLM
    stuck_eps = [] # all destructive/terminal stuck episodes for cause-labeling
    for link in bundles:
        m = json.load(open(os.path.join(link, "run_meta.json")))
        tl = json.load(open(os.path.join(link, "timeline_report.json")))["runs"][0]["rows"]
        byn = defaultdict(list)
        for r in tl: byn[node_dir(r["node"])].append(r)
        all_eps, terminals, agg = [], [], dict(total_time=0.0, durable_progress=0, n_turns=0,
                                               uniq_tac=0, first_fail=0, tok_total=0, tok_destr=0,
                                               has_tokens=0, n_segments=0)
        max_consec_rej = 0
        for ndir, rows in byn.items():
            eps, term, a = analyze_node(link, ndir, rows)
            for e in eps: e["node"] = ndir
            all_eps += eps
            if term: term["node"] = ndir; terminals.append(term)
            for k in agg: agg[k] += a[k]
            max_consec_rej = max(max_consec_rej, a.get("max_consec_rej", 0))
        all_with_term = all_eps + terminals
        clean = [e for e in all_eps if e["kind"] == "clean_undo"]
        # destructive obstacle = a stall containing a real committed reject (arm-fair:
        # probe-fails are cheap exploration, NOT counted as being stuck)
        destructive = [e for e in all_with_term if e.get("n_commit_rej", 0) > 0]
        prog = max(1, agg["durable_progress"])
        rec = dict(
            arm=arm_of(m.get("surface_profile")), lemma=m.get("lemma"),
            outcome=m.get("outcome"), commit=(m.get("commit") or "")[:7],
            bundle=os.path.basename(link),
            n_turns=agg["n_turns"], total_time_min=agg["total_time"]/60,
            durable_progress=agg["durable_progress"],
            # raw event counts
            n_commit_rej=sum(e.get("n_commit_rej", 0) for e in all_with_term),
            n_probe_fail=sum(e.get("n_probe_fail", 0) for e in all_with_term),
            n_clean_undo=len(clean),
            # ---- arm-FAIR headline metrics ----
            # stall time = time-not-making-durable-progress after first hitch (probe time included
            # but it is the SAME currency for both arms; long stalls = stuck regardless of how filled)
            stall_time_min=sum(e["recover_time"] for e in all_with_term)/60,
            stall_per_progress_min=sum(e["recover_time"] for e in all_with_term)/60/prog,
            # destructive stall time = reject + restart only (read-only probe/inspect/undo excluded)
            destr_stall_time_min=sum(e.get("destr_time", 0) for e in all_with_term)/60,
            destr_stall_per_progress_min=sum(e.get("destr_time", 0) for e in all_with_term)/60/prog,
            # dimensionless, cross-lemma fair: share of total effort bled on destructive dead-ends
            destr_pct_of_total=100*sum(e.get("destr_time", 0) for e in all_with_term)/max(1.0, agg["total_time"]),
            # destructive stalls (the mechanical, reject-anchored core)
            n_destructive=len(destructive),
            n_segments=agg["n_segments"],
            # UNIT-CONSISTENT (segment ÷ segment): fraction of the proof's forward-progress
            # SEGMENTS that contained a committed reject. Numerator = reject-containing
            # segments, denominator = total segments -- both in segment units.
            reject_seg_frac=len(destructive)/max(1, agg["n_segments"]),
            destructive_per_progress=len(destructive)/prog,  # (legacy: segments ÷ tactics, mixed units)
            # raw committed-reject COUNT / durable-progress tactic (tactic ÷ tactic, also consistent)
            commit_rej_per_progress=sum(e.get("n_commit_rej", 0) for e in all_with_term)/prog,
            destructive_thrash=sum(e.get("n_commit_rej", 0) for e in destructive),  # TOTAL rejects
            max_consec_rej=max_consec_rej,  # blind-retry DEPTH = worst consecutive-reject storm
            # terminal stuck = never recovered (ran out on an obstacle)
            n_terminal=len(terminals),
            terminal_time_min=sum(e["recover_time"] for e in terminals)/60,
            # CONTROL variable: model error-generation rate (should be ~equal L1 vs L4)
            error_gen_rate=(agg["first_fail"]/agg["uniq_tac"]) if agg["uniq_tac"] else 0.0,
            uniq_tac=agg["uniq_tac"],
            # REAL output-token share bled on destructive dead-ends (0 if bundle has no usage)
            destr_tok_pct=100*agg["tok_destr"]/agg["tok_total"] if agg["tok_total"] else 0.0,
            tok_total=agg["tok_total"], tok_destr=agg["tok_destr"],
            has_token_data=bool(agg["has_tokens"]),
        )
        per_bundle[os.path.basename(link)] = rec
        for e in clean:
            flagged.append(dict(bundle=os.path.basename(link), arm=rec["arm"], lemma=rec["lemma"], **e))
        # export ALL stuck episodes (destructive + terminal) for cause-labeling
        for e in destructive + [t for t in terminals if t.get("n_commit_rej", 0) == 0]:
            stuck_eps.append(dict(bundle=os.path.basename(link), arm=rec["arm"], lemma=rec["lemma"],
                                  node=e.get("node"), kind=e["kind"], turns=e["turns"],
                                  n_commit_rej=e.get("n_commit_rej", 0)))
    json.dump(per_bundle, open(os.path.join(OUT, "metrics.json"), "w"), indent=1)
    json.dump(flagged, open(os.path.join(OUT, "flagged_clean_undos.json"), "w"), indent=1)
    json.dump(stuck_eps, open(os.path.join(OUT, "stuck_episodes.json"), "w"), indent=1)
    # print table
    print(f"{'arm':3} {'lemma':20} {'outcome':10} {'prog':>4} {'cREJ':>4} {'pFAIL':>5} "
          f"{'destr':>5} {'d/prog':>6} {'dThrash':>7} {'term':>4} {'stallT_m':>8} {'cleanU':>6}")
    for r in sorted(per_bundle.values(), key=lambda x: (str(x["lemma"]), x["arm"])):
        print(f"{r['arm']:3} {str(r['lemma'])[:20]:20} {str(r['outcome'])[:10]:10} "
              f"{r['durable_progress']:>4} {r['n_commit_rej']:>4} {r['n_probe_fail']:>5} "
              f"{r['n_destructive']:>5} {r['destructive_per_progress']:>6.2f} {r['destructive_thrash']:>7} "
              f"{r['n_terminal']:>4} {r['stall_time_min']:>8.1f} {r['n_clean_undo']:>6}")
    print(f"\ncompute: {len(per_bundle)} bundles, {len(flagged)} clean-undo episodes flagged for LLM -> {OUT}")

# ============================================================ ANNOTATE (claude -p)
ANNOT_SCHEMA = ('{"classification":"wrong_path|strategic","cause":'
                '"missing_lemma|unknown_tactic_form|weak_invariant|wrong_direction|'
                'structure_confusion|deliberate_restructure|other","confidence":0.0,"why":"..."}')

def annotate(limit=None):
    flagged = json.load(open(os.path.join(OUT, "flagged_clean_undos.json")))
    coll = COLL
    out = []
    items = flagged if limit is None else flagged[:limit]
    for i, ep in enumerate(items):
        ndir = ep["node"]; bundle = os.path.join(coll, ep["bundle"])
        # gather tactics + thinking for the episode turns
        lines = []
        for t in ep["turns"]:
            tac = ""
            tf = os.path.join(bundle, "views", ndir, "thinking", f"turn_{t:03d}.md")
            think = open(tf).read().strip()[:500] if os.path.isfile(tf) else "(no thinking)"
            lines.append(f"[turn {t}] thinking: {think}")
        prompt = (
            "You audit one EasyCrypt proof-search episode where the agent UNDID committed steps "
            "with NO compiler error in the undone span. Decide if this undo was:\n"
            " - wrong_path: the agent realized the approach was a dead end / lost a needed fact / "
            "the route cannot close (counts as being stuck), or\n"
            " - strategic: the path worked but the agent deliberately backed out to restructure / "
            "do it more cleanly (NOT stuck, healthy planning).\n"
            "Also give the cause. Reply with ONLY one JSON object:\n" + ANNOT_SCHEMA + "\n\n"
            "Episode (agent reasoning per turn):\n" + "\n".join(lines)
        )
        try:
            p = subprocess.run(["claude", "-p", prompt, "--model", "claude-opus-4-8"],
                               capture_output=True, text=True, timeout=180)
            txt = p.stdout.strip()
            mobj = re.search(r"\{.*\}", txt, re.S)
            label = json.loads(mobj.group(0)) if mobj else {"classification": "parse_error", "raw": txt[:200]}
        except Exception as e:
            label = {"classification": "error", "err": str(e)[:120]}
        label.update(bundle=ep["bundle"], arm=ep["arm"], lemma=ep["lemma"], turns=ep["turns"])
        out.append(label)
        print(f"  [{i+1}/{len(items)}] {ep['arm']} {ep['lemma']} turns{ep['turns'][:3]}... -> "
              f"{label.get('classification')} / {label.get('cause','?')}")
    json.dump(out, open(os.path.join(OUT, "llm_labels.json"), "w"), indent=1)
    print(f"annotate: {len(out)} episodes labeled -> {OUT}/llm_labels.json")

# ============================================================ CHART
def chart():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; import numpy as np
    M = json.load(open(os.path.join(OUT, "metrics.json")))
    rows = list(M.values())
    # pick ONE representative run per (lemma, arm): prefer proved, else most durable progress
    rep = {}
    for r in rows:
        key = (r["lemma"], r["arm"])
        cur = rep.get(key)
        better = (cur is None
                  or (r["outcome"] == "proved" and cur["outcome"] != "proved")
                  or (r["outcome"] == cur["outcome"] and r["durable_progress"] > cur["durable_progress"]))
        if better: rep[key] = r
    bylemma = defaultdict(dict)
    for (lemma, arm), r in rep.items(): bylemma[lemma][arm] = [r]
    # Error-study rule: a lemma counts only if BOTH arms PROVED. A side that gave up
    # logs errors incomparably (few errors because it quit, not because it had less
    # friction) -> exclude from the error chart (it is Part-2 case-study material).
    paired = {l: a for l, a in bylemma.items()
              if "L1" in a and "L4" in a
              and a["L1"][0]["outcome"] == "proved" and a["L4"][0]["outcome"] == "proved"}
    dropped = [l for l, a in bylemma.items() if "L1" in a and "L4" in a and l not in paired]
    if dropped:
        print(f"chart: excluded {dropped} (not both-proved) from the error chart -> case study")
    plt.rcParams.update({"font.size": 11})
    metrics = [("destructive_per_progress","Destructive stalls per progress step  (reject-anchored)","down"),
               ("destructive_thrash","Blind retry depth  (committed rejects)","down"),
               ("n_terminal","Terminal-stuck episodes  (never recovered)","down"),
               ("stall_per_progress_min","Stall time per progress step (min)  (arm-fair)","down")]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10)); axes = axes.flatten()
    lemmas = sorted(paired); x = np.arange(len(lemmas)); w = 0.38
    for ax, (key, title, _) in zip(axes, metrics):
        v1 = [np.mean([r[key] for r in paired[l].get("L1",[{key:0}])]) for l in lemmas]
        v4 = [np.mean([r[key] for r in paired[l].get("L4",[{key:0}])]) for l in lemmas]
        ax.bar(x-w/2, v1, w, label="L1 (bare goal)", color="#4C72B0")
        ax.bar(x+w/2, v4, w, label="L4 (compiler)", color="#DD8452")
        ax.set_title(title+"  (↓ better)", fontsize=12, fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels(lemmas, rotation=25, ha="right", fontsize=9)
        ax.grid(axis="y", alpha=.3); ax.legend(fontsize=9)
        a1=np.mean(v1); a4=np.mean(v4)
        ax.text(0.5,0.95,f"mean L1={a1:.2f}  L4={a4:.2f}",transform=ax.transAxes,ha="center",
                va="top",fontsize=10,bbox=dict(boxstyle="round",fc="#fff3cd"))
    fig.suptitle("Stuck metrics — L1 (bare goal) vs L4 (proof-state compiler), matched lemmas",
                 fontsize=15, fontweight="bold")
    fig.tight_layout(rect=[0,0,1,0.96])
    png = os.path.join(OUT, "stuck_metrics.png"); fig.savefig(png, dpi=200, bbox_inches="tight")
    print("chart ->", png, "| paired lemmas:", lemmas)

# ============================================================ COMBINE (interim: fold wrong_path + cause dist)
FACT_CAUSES = ["missing_lemma", "unknown_tactic_form", "wrong_direction", "structure_confusion"]
SEMANTIC_CAUSES = ["weak_invariant"]

def combine():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; import numpy as np
    M = json.load(open(os.path.join(OUT, "metrics.json")))
    labels = json.load(open(os.path.join(OUT, "llm_labels.json")))
    # wrong_path clean-undos per bundle (strategic excluded)
    wp_by_bundle = Counter(L["bundle"] for L in labels if L.get("classification") == "wrong_path")
    rows = list(M.values())
    rep = {}
    for r in rows:
        key = (r["lemma"], r["arm"]); cur = rep.get(key)
        if (cur is None or (r["outcome"]=="proved" and cur["outcome"]!="proved")
            or (r["outcome"]==cur["outcome"] and r["durable_progress"]>cur["durable_progress"])):
            rep[key] = r
    bylemma = defaultdict(dict)
    for (lemma, arm), r in rep.items(): bylemma[lemma][arm] = r
    # Error-study rule: both arms must have PROVED (a give-up's error counts are not
    # comparable). Non-both-proved lemmas are case-study material, not error data.
    paired = sorted(l for l, a in bylemma.items()
                    if "L1" in a and "L4" in a
                    and a["L1"]["outcome"] == "proved" and a["L4"]["outcome"] == "proved")
    fig, axes = plt.subplots(1, 2, figsize=(17, 6.5))
    # Panel A: combined stuck per progress = destructive (1) + wrong_path (2), stacked
    x = np.arange(len(paired)); w = 0.38
    axA = axes[0]
    for off, arm, c1, c2 in [(-w/2,"L1","#4C72B0","#9ec0e8"), (w/2,"L4","#DD8452","#f2c39c")]:
        d = [bylemma[l][arm]["n_destructive"]/max(1,bylemma[l][arm]["durable_progress"]) for l in paired]
        wp = [wp_by_bundle.get(bylemma[l][arm]["bundle"],0)/max(1,bylemma[l][arm]["durable_progress"]) for l in paired]
        axA.bar(x+off, d, w, color=c1, label=f"{arm} destructive (1)")
        axA.bar(x+off, wp, w, bottom=d, color=c2, hatch="//", label=f"{arm} wrong_path (2)")
    axA.set_title("Combined stuck per progress step  (1 destructive + 2 wrong_path)  ↓ better", fontsize=12, fontweight="bold")
    axA.set_xticks(x); axA.set_xticklabels(paired, rotation=25, ha="right", fontsize=9)
    axA.legend(fontsize=8); axA.grid(axis="y", alpha=.3)
    # Panel B: the labeled wrong_path by cause x arm
    axB = axes[1]
    causes = ["weak_invariant","wrong_direction","unknown_tactic_form","missing_lemma","structure_confusion","other"]
    L1c = Counter(L.get("cause") for L in labels if L.get("classification")=="wrong_path" and L["arm"]=="L1")
    L4c = Counter(L.get("cause") for L in labels if L.get("classification")=="wrong_path" and L["arm"]=="L4")
    xc = np.arange(len(causes))
    axB.bar(xc-0.2,[L1c.get(c,0) for c in causes],0.4,color="#4C72B0",label="L1")
    axB.bar(xc+0.2,[L4c.get(c,0) for c in causes],0.4,color="#DD8452",label="L4")
    axB.set_title("wrong_path (2) episodes by cause  [interim: clean-undos only, n=7]", fontsize=12, fontweight="bold")
    axB.set_xticks(xc); axB.set_xticklabels(causes, rotation=30, ha="right", fontsize=8)
    axB.legend(fontsize=9); axB.grid(axis="y", alpha=.3)
    axB.axvspan(-0.5,0.5,color="#ffe0e0",alpha=.5)  # highlight weak_invariant = semantic
    axB.text(0,axB.get_ylim()[1]*0.9,"SEMANTIC\n(model, not\ncompiler)",ha="center",fontsize=8,color="#a00")
    fig.suptitle("Interim: combined stuck + cause split (weak_invariant = semantic, NOT compiler-attributable)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0,0,1,0.95])
    png = os.path.join(OUT,"stuck_combined_interim.png"); fig.savefig(png, dpi=200, bbox_inches="tight")
    print("combine ->", png)

# ============================================================ CLEAN CHART (same-commit, both-proved)
def clean_chart():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; import numpy as np
    M = json.load(open(os.path.join(OUT, "metrics.json")))
    rows = list(M.values())
    by = defaultdict(list)
    for r in rows: by[r["lemma"]].append(r)
    subset = {}
    for lemma, rs in by.items():
        for a in [r for r in rs if r["arm"]=="L1" and r["outcome"]=="proved"]:
            for b in [r for r in rs if r["arm"]=="L4" and r["outcome"]=="proved"]:
                if a["commit"] == b["commit"]:
                    subset[lemma] = {"L1": a, "L4": b, "commit": a["commit"]}; break
            if lemma in subset: break
    lemmas = sorted(subset)
    if not lemmas:
        print("clean_chart: NO lemma has BOTH a proved L1 and a proved L4 run at the "
              "same commit. Need paired (l1_goal_projection + l4_checked_action_surface) "
              "runs that both proved. Check `compute`'s table above.")
        return
    print("clean subset (same-commit, both proved):")
    for l in lemmas: print(f"  {l:20} commit={subset[l]['commit']}")
    # panel ④: prefer the REAL output-token share (needs the report-bundle token-fix,
    # present on mcp-v0); fall back to a think-time proxy for older bundles.
    has_tok = any(subset[l][arm].get("has_token_data") for l in lemmas for arm in ("L1", "L4"))
    if has_tok:
        p4_key, p4_ylab = "destr_tok_pct", "% of tokens"
    else:
        p4_key, p4_ylab = "destr_pct_of_total", "% of think-time (proxy)"
        print("  [warn] these bundles carry no real per-turn tokens -> panel ④ uses the "
              "think-time proxy.\n         For real tokens, run the ablation on mcp-v0 "
              "(it has the token-fix) and re-run.")
    metrics = [
        ("error_gen_rate",           "③ Error-generation rate", "fraction wrong", "CONTROL — expect ≈ equal", "%.2f"),
        ("commit_rej_per_progress", "① Committed rejects / progress step", "rejected ÷ surviving tactics (each reject counts)", "↓ better", "%.2f"),
        ("max_consec_rej",           "② Blind-retry depth", "# consecutive rejects", "↓ better", "%.0f"),
        (p4_key,                     "④ Destructive token share", p4_ylab, "↓ better", "%.1f"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(15, 11.5)); axes = axes.flatten()
    x = np.arange(len(lemmas)); w = 0.38
    for ax, (key, title, ylab, suffix, fmt) in zip(axes, metrics):
        v1 = [subset[l]["L1"][key] for l in lemmas]
        v4 = [subset[l]["L4"][key] for l in lemmas]
        b1 = ax.bar(x-w/2, v1, w, color="#4C72B0", label="L1 (bare goal — no compiler)")
        b4 = ax.bar(x+w/2, v4, w, color="#DD8452", label="L4 (proof-state compiler)")
        for bars in (b1,b4):
            for bar in bars:
                ax.annotate(fmt % bar.get_height(),(bar.get_x()+bar.get_width()/2,bar.get_height()),
                            ha="center",va="bottom",fontsize=8)
        ax.set_title(f"{title}   ({suffix})", fontsize=13, fontweight="bold")
        ax.set_ylabel(ylab, fontsize=10)
        ax.set_xticks(x); ax.set_xticklabels(lemmas, rotation=25, ha="right", fontsize=9)
        ax.grid(axis="y", alpha=.3); ax.legend(fontsize=8.5, loc="upper right")
        ax.margins(y=0.18)
        a1, a4 = np.mean(v1), np.mean(v4)
        ax.text(0.02,0.97,f"mean  L1={a1:.2f}   L4={a4:.2f}",transform=ax.transAxes,ha="left",va="top",
                fontsize=10.5,fontweight="bold",bbox=dict(boxstyle="round",fc="#fff3cd"))
    fig.suptitle(f"Where the proof-state compiler helps: cost of the model's mistakes  "
                 f"(same code, same lemma, both proved; {len(lemmas)} lemmas)  —  L1 vs L4",
                 fontsize=14.5, fontweight="bold", y=0.995)
    # ---- ONE consolidated definitions / how-to-read box at the bottom ----
    defs = (
        f"HOW TO READ  (all four on the same {len(lemmas)} lemmas; read ③ first).   "
        "L1 = bare goal, no compiler.   L4 = proof-state compiler.\n"
        "③ Error-generation rate (CONTROL): of the model's distinct tactic ideas, the fraction WRONG on first try "
        "(cheap probes counted). Measures the MODEL's ability, not the tool — ≈ equal ⇒ same-strength model in both arms.\n"
        "① Committed rejects / progress step: real tactics EasyCrypt rejected, per forward step — how often it wastes a REAL move.\n"
        "② Blind-retry depth: total tactics submitted that got rejected ('blind' = committed without checking first).\n"
        "④ Destructive token share: % of the model's tokens spent on dead-ends (rejected commits + restarts); cheap probing/inspecting "
        "excluded. Char-based proxy reported only as a ratio (robust to proxy error and to prompt caching).\n"
        "“progress step” = a committed tactic that moved the proof forward AND survived to the final proof (not later undone).\n"
        "TAKEAWAY: ③ shows the model errs equally often → ①②④ show the compiler makes each error far cheaper."
    )
    fig.text(0.012, 0.012, defs, ha="left", va="bottom", fontsize=9.2,
             bbox=dict(boxstyle="round", fc="#f4f4f4", ec="#bbb"))
    fig.tight_layout(rect=[0, 0.20, 1, 0.96])
    png = os.path.join(OUT,"stuck_clean_subset.png"); fig.savefig(png, dpi=200, bbox_inches="tight")
    print("clean_chart ->", png)

def run_all(roots):
    collect(roots)
    compute()
    clean_chart()

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    extra = sys.argv[2:]
    roots = resolve_roots(extra)
    if stage == "all":
        run_all(roots)
    elif stage == "collect":
        collect(roots)
    elif stage == "annotate":
        annotate(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    else:
        {"compute": compute, "chart": chart, "combine": combine,
         "clean_chart": clean_chart}[stage]()
