# Bundle browser — design

A panel-style explorer for every prover run bundle under `agent_view_runs/`, so a
run can be reviewed like an IDE session (pick a run, step through turns, open the
per-step artifacts) instead of clicking through files on GitHub. It is the
**results surface** of the open-source site — sibling to the live playground and
the code-grounded Q&A.

Status: v1. Files:
`bundle_browser/{build_manifest.py, index.html, README.md}`, wired into
`playground/server.py`.

## 1. Why static (the architecture decision)

The playground needs a live EasyCrypt process (it *drives* a proof). Browsing
results does not — every artifact already exists on disk as JSON/Markdown. So the
browser is a **static SPA over files**, with a small build step:

```
agent_view_runs/<lemma>/<ts>__<commit>/    one run bundle (already written by run_report_bundle)
  run_meta.json            outcome, lemma, surface_profile, model, turn_count, committed_proofs, ...
  timeline_report.json     per-turn rows (intent, summaries, timing, artifact paths)
  views/<tree>/            turn_NNN.json (workspace_view), followups/, thinking/, manager_results/

build_manifest.py  -->  manifest.json   (one record per bundle + classification tags)
index.html (SPA)   -->  reads manifest.json for the list;
                        reads each bundle's timeline_report.json on select;
                        lazily fetches one artifact file per panel open.
```

Consequences:
- **No build backend.** Deployable as flat files (school host, GitHub Pages, any
  CDN). The playground's FastAPI *can* serve it for convenience, but isn't required.
- **The manifest is the only generated file.** Everything else is read live, so the
  browser never drifts from the bundles on disk.

## 2. Data sources

| Need | Source | Notes |
|---|---|---|
| Bundle list + classification | `run_meta.json` | one read per bundle; all facets come from here |
| Per-turn timeline | `<bundle>/timeline_report.json` | `runs[].rows[]`; each row has `turn`, `node`, `intent_summary`, `ok`, `agent_think`, and artifact `*_path` fields |
| What the agent saw | `views/<tree>/followups/turn_NNN.md` | the rendered followup — the agent's actual surface |
| Agent thinking | `views/<tree>/thinking/turn_NNN.md` | per-turn reasoning |
| Manager result | `views/<tree>/manager_results/turn_NNN.json` | the turn's manager response |
| Audit view | `views/<tree>/turn_NNN.json` | the `workspace_view` snapshot |

### 2.1 The artifact-path rewrite (the one tricky bit)

The row's `*_path` fields point at the **original run dir**
(`artifacts/.../node_memory/Tree_0_0/followups/turn_001.md`), not the bundle's
copied files. The SPA rewrites them to bundle-relative, using the row's own turn
numbering (no off-by-one guessing):

```
take the path after  node_memory/   ->  Tree_0_0/followups/turn_001.md
replace  /workspace_views/  with  /   (the audit view is copied to views/<tree>/turn_NNN.json)
prefix with  views/                 ->  views/Tree_0_0/followups/turn_001.md
```

Most bundles are **flat** (`views/<tree>/...`). Aggregated multi-candidate bundles
nest under a candidate dir (`views/c0/<tree>/...`), and the row path does not carry
the candidate. So `build_manifest.py` records each bundle's `view_roots` (the
candidate dirs, e.g. `["c0","c1","c2"]`, empty for flat), and the SPA tries the
flat path first, then `views/<root>/<tail>` for each root, taking the first that
exists. A missing file (older bundles that predate followup capture) renders
"not captured for this run" rather than an error.

## 3. Classification

Cheap facets straight from `run_meta.json`; an optional taxonomy join is deferred
to v2.

| Facet | Field | Use |
|---|---|---|
| Outcome | `outcome` (+ per-tree `committed_proofs[].proved`) | proved / incomplete / verify-failed |
| Surface | `surface_profile` → L1–L4 / adaptive | the human↔compiler axis |
| Lemma / source | `lemma`, `source_file` (basename only) | grouping + the public/private split |
| Model | `model` | opus-4-6/7/8, fable-5 |
| Effort | `turn_count` | hardness proxy |
| Sealed | `eval_mode` | isolated runs |
| Provenance | `timestamp`, `commit` | date + code version |
| **Visibility tier** | derived from `source_file` | **redaction gate** (see §5) |

### v2 (deferred): join `tools/taxonomy.py` by lemma to add `proof_archetype`
(game_hop / up_to_bad / coupling / …) and the `D_static` / `struct_tier` axes, so
the browser's facets line up with the benchmark leaderboard.

## 4. UI and the panel UX

Three regions: a filterable **bundle list** (grouped by lemma, sorted by date),
a selected-bundle **header + per-turn timeline**, and a per-turn **panel** that
opens on click and closes with ✕. The panel has four tabs:

- 👁 **What the agent saw** — the followup (the rendered surface).
- 🧠 **Thinking** — the agent's reasoning.
- ⚙ **Manager result** — the manager's response.
- `{}` **Audit view** — the `workspace_view` snapshot.

### The one correctness rule

"What the agent saw" is the **followup**, never the `workspace_view`. The
`workspace_view` is an **audit twin: identical across L1–L4**, so showing it as
"what the agent saw" makes the L1↔L4 contrast look fake. The audit tab is a
separate, explicitly-labelled view ("NOT what the agent saw"). This is the same
trap hit in the playground and the inspect-handle gates; the renderer bakes the
warning in.

## 5. Privacy / redaction (fail-closed)

The `PUBLIC_SOURCE` allowlist in `bundle_browser/build_manifest.py` controls
which bundles a hosted build includes: `tier_of(source_file)` returns `public`
**only** on an allowlist match, and everything else — including absolute paths
and any unknown/empty source — fails closed to `private`.
`build_manifest.py --public` drops private bundles entirely; a local build (no
flag) keeps them and the browser badges them with 🔒. `manifest.json` is
git-ignored and rebuilt live, so it is never committed; a deploy regenerates it
with `--public`. Review `PUBLIC_SOURCE` before any public deploy.

## 6. Serving

1. **Playground server (dev):** one `uvicorn` serves both surfaces —
   `/play` (live), `/results/` (the SPA), `/agent_view_runs/` (static bundles),
   `/results/manifest.json` (built live, so new runs appear without a rebuild).
2. **Standalone (any static server):** generate `manifest.json` once, then serve
   the repo root; relative URLs (`./manifest.json`, `../agent_view_runs/`) resolve.
3. **Public deploy:** `build_manifest.py --public`, ship `bundle_browser/` + the
   public subset of `agent_view_runs/` as flat files.

`bundle_browser/` is classified feature-only in `playground/sync.sh`, so it is
never pushed to the compiler trunk.

## 7. v1 limitations / roadmap

- Older bundles predate followup/thinking capture → those panels show
  "not captured." Expected; not an error.
- Multi-candidate bundles: a turn present under several candidates shows the
  first match (precise row→candidate mapping is a v2 item).
- v2: aggregate-stats strip (pass-rate by surface/model/lemma — a mini
  leaderboard), the taxonomy join (§3), and the row→candidate refinement.
