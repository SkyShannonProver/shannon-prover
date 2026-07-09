# Bundle browser

A panel-style explorer for every prover run bundle under `agent_view_runs/` —
instead of clicking through files on GitHub. Filter the runs, pick one, step
through its turns, and click a turn to open closable panels:

- **What the agent saw** — the rendered followup (the surface the agent read).
- **Thinking** — the agent's per-turn reasoning.
- **Manager result** — the manager's response that turn.
- **Audit view** — the `workspace_view` snapshot, *identical across L1–L4* and
  **not** what the agent saw (clearly labelled).

It is a static SPA — no build backend. `build_manifest.py` scans each bundle's
`run_meta.json` into a manifest; the page then reads each bundle's own
`timeline_report.json` and lazily fetches one artifact file per open panel.

## Run it

Via the playground server (one process serves the live playground **and** the
static results browser):

```bash
eval "$(opam env --switch=easycrypt)"   # only needed for the /play playground
uv run --with fastapi --with "uvicorn[standard]" \
    uvicorn playground.server:app --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000/results/
```

The server builds the manifest live at `/results/manifest.json`, so new runs
appear without a rebuild. Standalone (any static server from the repo root) also
works once you generate the manifest:

```bash
python3 bundle_browser/build_manifest.py          # local: all bundles
python3 bundle_browser/build_manifest.py --public  # hosted: public tier-A only
```

## Tiers / redaction

Tier is **fail-closed**: a bundle is `public` only when its source file is on the
allowlist in `build_manifest.py` (the classic `eval/examples/` files plus
ChaChaPoly / MEE-CBC); everything else (the private held-out corpus, the private
benchmark repo, unknown sources) is `private`. `--public` drops private bundles entirely so a hosted
build can never leak them; locally they show with a 🔒 badge. `manifest.json` is
git-ignored because it lists private bundles — regenerate it, don't commit it.
Review `PUBLIC_SOURCE` before any public deploy.
