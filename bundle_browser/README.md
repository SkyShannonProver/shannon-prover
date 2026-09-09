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

The benchmark landing page presents two expanded sections: **per-lemma
benchmark** first (model results and run links), followed by **end-to-end case
studies**. Case studies have a separate **proof library** for
curated whole-development case studies. It lists files and their lemmas, shows
each declaration and complete proof separately, links unambiguous earlier
lemma names within a file, and provides original source downloads. Hash routes
retain the case, file, lemma and section, so refresh and browser back work.
The lexical outline and source-name links are navigation aids, **not** an
EasyCrypt parser, a semantic dependency graph or a proof-success verifier.
Verification labels and process summaries report archived evidence; the site
does not re-run EasyCrypt. Supplied libraries are distinguished from completed
targets and mixed stitched developments.

The Agent process tab can display a curated, trace-backed account: concrete
reduction steps and failed approaches, an outer/inner work split, links into
the final lemma browser, expandable original public-message excerpts, and
separate accepted/unaccepted job tables. This is an editorial reconstruction,
not a private reasoning transcript or a complete replay of the event stream.

The existing runs browser renders one managed proof-node timeline. It does **not** currently
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

### Local review of new case studies (private checkout only)

To review uncommitted website changes and an explicitly curated local proof
catalog without publishing or changing the public export policy:

```bash
python3 bundle_browser/build_site.py --local-preview \
  --case-studies artifacts/benchmark_case_studies --out artifacts/site-review
python3 -m http.server 8000 --bind 127.0.0.1 --directory artifacts/site-review
```

The ordinary builder still refuses a private checkout. `--local-preview` is an
explicit opt-in; it continues to include only public-tier single-node bundles.
Default builds use only the reviewed catalog in `bundle_browser/case_studies/`.
Its publication marker, source hashes and explicit input list are checked.
The `--case-studies` override requires `--local-preview`; it never changes the
catalog used by Pages. The reviewed release contains ML-KEM, ChaChaPoly and
the separately labeled historical MEE-CBC case.
Never deploy a local-review output. Keep unreviewed catalogs and their sources
under ignored `artifacts/`, not in the publicly labeled `bundle_browser/` tree.

A catalog has `schema_version: 1` and an explicit `cases` list. Each case names
its default file/lemma, display metadata, scoped evidence and process summary,
and a `files` list. Each file has a stable `id`, display `path`, `role`, relative
input `source` and SHA-256. The packager checks every byte hash and confines
every input/output path before copying only the named `.ec`/`.eca` sources.
It never scans raw experiment directories or imports reviewer packs. Archive
input locations are omitted from the served file metadata. Downloads
preserve the exact archived bytes; generated lemma indexes are separate files.

A case may name a relative `process_source` JSON file in the same curated pack.
Its `schema_version: 1` story contains `title`, `deck`, `stats`, `provenance`,
`orderNote`, `stages` and `jobs`. Each stage includes `paragraphs`, `work`,
explicit `{file, lemma}` references and evidence excerpts (`kind`, original
JSONL `line`, `item`, `text`). Job tables separate `merged` from `other` records.
The packager validates the references against the final source index and
inlines the story as `processStory`; it does not copy the input path or raw
traces. Simple cases may retain the existing `[title, description]` process
list. A story's deliberately curated archive identifiers are displayed as
provenance, unlike private input locations.

Curate statements from frozen evidence and distinguish original public agent
messages from editorial summaries. Cross-check job outcomes and final claims
against their verification records; a completion message or an intermediate
check is not final proof certification. Do not invent timestamps, expose
private paths/session data, or infer speedup by subtracting failed-job time.
The builder validates structure and navigation, not the truth of the narrative.
The reviewed case directory contains only the selected final sources and
curated process text; raw run directories and reviewer packs are not shipped.

Run the browser-specific checks from the private checkout:

```bash
python3 -m pytest -q bundle_browser/tests/test_proof_library.py
node --test bundle_browser/tests/proof_browser.test.cjs
```

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
