# Compiler-contribution metrics (L1 vs L4 / adaptive)

Offline analysis tooling that turns prover-run **bundles** (`agent_view_runs/...`)
into the "how much does the proof-state compiler help" metrics used for the paper.
Operates purely on committed bundle artifacts (+ the Claude transcript for tokens);
runs no EasyCrypt.

## Handing this to a collaborator
See **`COLLABORATOR_INSTRUCTIONS.md`** — paste-ready steps to run an L1/L4
ablation and auto-pull the figure. `ablation_suite_template.json` is the suite
template they edit to pick lemmas.

## `stuck_pipeline.py` — the main pipeline
**Turnkey:** `python3 stuck_pipeline.py all` auto-discovers bundles under
`./agent_view_runs` (+ `./artifacts/eval_suite`) and writes the 4-panel figure
`stuck_out/stuck_clean_subset.png`. Override roots with positional args or
`BUNDLE_ROOTS="/dir1:/dir2"` — no source editing needed.

Individual stages (`python3 stuck_pipeline.py <stage> [roots...]`):
- `collect`  — dedupe discovered bundles into a symlink collection (`bundles/`).
- `compute`  — per-bundle metrics → `stuck_out/metrics.json`. Anchors "progress" to
  the committed-goal fingerprint (`current_goal.lines`); separates destructive
  rejects from cheap probe-exploration; reads REAL per-turn tokens from the
  timeline `usage` field when present (the report-bundle token-fix records it).
- `annotate` — spawns `claude -p` to label "clean-undo" episodes as wrong-path (2)
  vs strategic (3); only needed for the `combine` figure, NOT for the 4-panel one.
- `clean_chart` — 4-panel figure on the same-commit / both-proved subset:
  ③ error-generation rate (CONTROL, ≈equal), ① committed rejects / progress,
  ② blind-retry depth, ④ destructive token share (real tokens on mcp-v0; falls
  back to a think-time proxy on older bundles).

## `(removed) compute_metrics.py` + `make_outputs.py`
Earlier M1–M5 friction/quality version, superseded by `stuck_pipeline.py`; kept for
reference.

## `PANEL_AUDIT_ISSUES.md`
Recorded panel/parser audit findings (bd-hoare seq-subgoal flatten; pr_bridge_routes
probability-layer coverage gap; etc.) for later fixing.

## Notes
- Outputs (`stuck_out/`, charts, `metrics.json`) and the `bundles/` symlink
  collection are regenerable and NOT committed.
- Methodology summary lives in the project memory note "L1 vs L4 speed analysis".
