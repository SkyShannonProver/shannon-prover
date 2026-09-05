# Bundle browser

A panel-style explorer for every compatible managed proof-node bundle under
`agent_view_runs/` — instead of clicking through files on GitHub. Filter the
runs, pick one, step
through its turns, and click a turn to open closable panels:

- **What the agent saw** — the rendered followup (the surface the agent read).
- **Thinking** — the agent's per-turn reasoning.
- **Manager result** — the manager's response that turn.
- **Audit view** — the manager-owned `workspace_view` snapshot, shared across
  matched experiment profiles and **not** what the agent saw (clearly labelled).

It is a static SPA — no build backend. `build_manifest.py` scans each bundle's
`run_meta.json` into a manifest; the page then reads each bundle's own
`timeline_report.json` and lazily fetches one artifact file per open panel.

## Scope boundary

The browser renders one managed proof-node timeline. It does **not** currently
render a complete interleaved Phase-II/III run: the outer-agent event stream,
two-lane job schedule, handoff/resume edges, checkpoint growth and whole-file
final verifier use a different artifact schema. Raw
`artifacts/interleaved_shannon/official_*` directories and curated reviewer
packs are therefore not silently treated as ordinary lemma bundles.

An interleaved trace may contain inner node artifacts, but those nodes alone do
not show who invented the decomposition, what work overlapped, how a partial
prefix returned to the outer agent, or what established final success. See
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the layer boundary.

## Preview the complete public website

From a public checkout or an exported public tree, build the same directory
layout used by GitHub Pages:

```bash
python3 bundle_browser/build_site.py --out artifacts/site
python3 -m http.server 8000 --directory artifacts/site
# Home:      http://127.0.0.1:8000/
# Benchmark: http://127.0.0.1:8000/results/
```

Choose a new or empty output directory for each build. The builder copies the
homepage, benchmark browser and public bundles, creates both manifests, and
checks that every listed run has a readable timeline. It generates browser
sidecars in the output, without modifying captured source bundles.

Use the public export procedure first when working in the private repository.
The builder refuses the private checkout. Serving the raw `website/` directory
does not provide `results/`; that route exists only in the assembled site.
GitHub Pages uses this same builder, including when mounted below the
`/shannon-prover/` project prefix.

## Browse local proof bundles only

Generate the manifest, serve the repository with any static HTTP server, and
open `/bundle_browser/`:

```bash
python3 bundle_browser/build_manifest.py          # local: all bundles
python3 bundle_browser/build_manifest.py --public  # hosted: public tier-A only
python3 -m http.server 8000
# open http://127.0.0.1:8000/bundle_browser/
```

## Tiers / redaction

Tier is **fail-closed**: a bundle is `public` only when its source file is on the
allowlist in `build_manifest.py` (the classic `eval/examples/` files plus
ChaChaPoly / MEE-CBC); everything else (the private held-out corpus, the private
benchmark repo, unknown sources) is `private`. `--public` drops private bundles entirely so a hosted
build can never leak them; locally they show with a 🔒 badge. `manifest.json` is
git-ignored because it lists private bundles — regenerate it, don't commit it.
Review `PUBLIC_SOURCE` before any public deploy.
