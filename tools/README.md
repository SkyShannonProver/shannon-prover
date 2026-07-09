# tools/ — offline audit & analysis tooling

Post-hoc analysis tools for Shannon Prover runs. Everything here operates on
**committed run bundles** under `agent_view_runs/<lemma>/<timestamp>__<commit>/`
(produced automatically by `eval_suite.run`, or by hand via
`python3 -m workflow.validation.run_report_bundle`). With two exceptions
(`panel_audit/replay_audit.py` and the `audit_harness/` capture scripts),
nothing in this directory runs EasyCrypt or an LLM — these are deterministic
readers of recorded artifacts.

Three toolboxes:

| dir | question it answers |
|---|---|
| [`panel_audit/`](panel_audit/) | Is the agent-facing workspace panel *faithful* (vs raw EasyCrypt output) and *used* (does the agent build on what it returns)? |
| [`audit_harness/`](audit_harness/) | Is the panel *valuable* — demand coverage: when the agent needed help, was the right thing offered (under-delivered vs nothing-to-give)? |
| [`compiler_metrics/`](compiler_metrics/) | How much does the proof-state compiler (L4 surface) help vs a bare goal (L1)? Plus the tree-search figures. |

---

## panel_audit/ — panel fidelity & usage audits

### replay_audit.py — deterministic replay harness (the main tool)

Takes a recorded bundle, extracts the *exact* agent action script (the
`handled_intent` stream: probe / commit / inspect / lookup / undo …) and
replays it through a fresh `ProofNodeManager` built from the **current
checkout**. No LLM in the loop. For every turn it writes, side by side:

- `raw_ec.txt` / `raw_ec_actions.json` — genuine raw EasyCrypt output
  (ground truth),
- `current_panel.md` (+ `current_panel_l1.md`) — the panel the prover would
  see on *current* code, rendered at L4 and L1,
- `current_view.json` — the full `ProverWorkspaceView`,
- `recorded_view.json` / `recorded_panel.md` — what the original run captured.

```bash
eval "$(opam env --switch=easycrypt)"   # needs a working EasyCrypt
python3 tools/panel_audit/replay_audit.py \
  --bundle agent_view_runs/<lemma>/<run> \
  --tree Tree_0_0 \
  --file eval/examples/<target>.ec \
  --lemma <lemma> \
  --include-dir easycrypt-src/theories \
  --surface-profile l4_checked_action_surface \
  --out-dir artifacts/panel_audit/<name>
```

Options: `--max-steps N` truncates the script. Run unsandboxed (why3server
needs the `nice()` syscall). Output layout for auditors: `AUDITOR_GUIDE.md`.

### replay_baseline_suite.sh — the panel-regression gate

Replays six deliberately diverse recorded runs (correctness equiv, pRHL
reduction, probability/phoare with a stalled recovery arc, high-rejection
sigma protocol, up-to-bad reasoning on an L1-native stream, clone-heavy
eager/swap proof) through the current checkout. Byte-diff two runs of this
suite — before/after a change, from **equally clean checkouts** — to prove
the agent-facing surface is unchanged:

```bash
bash tools/panel_audit/replay_baseline_suite.sh /tmp/panels_before
# ... apply your change ...
bash tools/panel_audit/replay_baseline_suite.sh /tmp/panels_after
diff -r /tmp/panels_before /tmp/panels_after --exclude=_run --exclude='*.log'
```

### scorecard.py — offer / pull / uptake metrics

Deterministic panel metrics over every bundle in `agent_view_runs/`: which
inspect topics were *offered*, which were *pulled*, and whether pulled
content *transferred* into a later accepted commit.

```bash
python3 tools/panel_audit/scorecard.py [--all] [--uptake TOPIC ...] [--model <substr>]
```

### inspect_quality.py / inspect_usage.py / ergonomics.py

- `inspect_quality.py` — tags every `inspect_context`/`lookup_symbol` return
  as EMPTY / PLACEHOLDER / CONTENT and ranks topics by fix priority.
- `inspect_usage.py` — when agents actually inspect: intent base rates,
  next-intent after accepted/rejected commits (run from repo root).
- `ergonomics.py` — panel layout audit (section line budgets, goal offset)
  over `replay_audit.py` output dirs.
- `build_on_sensor.py` — shared library: the shape-typed "did this commit
  build on that returned content" predicate (regression-tested).

### Reference documents

Point-in-time records from the 2026-06 panel-audit program (model- and
commit-specific; methodology examples, not current truth): `CONTRACT.md`
(the panel-presentation contract), `AUDITOR_GUIDE.md`, `REGISTRY.md` +
`registry_blocks.json` (census of the agent-facing panel blocks),
`FINDINGS_SUMMARY.md`, `INSPECT_QUALITY.md`, `MISLEADING_L4_vs_L1.md`,
`VERDICT_opus48.md`.

---

## audit_harness/ — panel *value* measurement

Captures the exact followup the prover reads at live frontiers, then runs
multi-agent adversarial judges over the captured corpus. Complements
panel_audit: fidelity asks "is it true?", this asks "was it what the agent
needed?". See `audit_harness/README.md` for the capture → judge pipeline
(`capture_frontier.py`, `capture_proof_steps.py`, `rerender_diff.py`, and the
three Claude-Code workflow scripts under `workflows/`). Capture needs live
EasyCrypt; corpora live gitignored under `.panel_audit_handoff/` and are
regenerated per run.

---

## compiler_metrics/ — L1-vs-L4 ablation & tree-search figures

See `compiler_metrics/README.md` and `INDEX.md` for the per-file index.
Highlights:

- **`stuck_pipeline.py`** — the main L1/L4 pipeline: durable-progress /
  stuck-episode metrics anchored to EasyCrypt ground truth, plus the 4-panel
  comparison figure. `python3 tools/compiler_metrics/stuck_pipeline.py all`
  (auto-discovers `./agent_view_runs`; stages: collect / compute /
  clean_chart / annotate).
- **`paper_figures/`** — the compiler-ablation figure pipeline
  (`build_dataset.py` → `compute_tokens.py` → `fig1_*.py`; matplotlib only;
  inclusion rules in `_shared.py`).
- **`tree_figures/`** — dependency-free SVG figures for the tree-search
  section (`fig_backtracking_summary.py`, `fig_fork_casestudy.py`).
- **`tree_tradeoff_extract.py` / `tree_ablation_extract.py`** — place tree
  configs on the latency-vs-cost plane / per-run extraction primitives.
- **`ablation_suite_template.json`** + `COLLABORATOR_INSTRUCTIONS.md` — the
  paste-ready L1/L4 ablation runbook.
- `PANEL_AUDIT_ISSUES.md` — recorded parser/panel findings with fix-commit
  provenance.

## Conventions

- Scripts are stdlib-only unless noted (matplotlib for `paper_figures/` and
  `stuck_pipeline.py clean_chart`).
- Generated outputs (`artifacts/panel_audit/`, `stuck_out/`, figure
  PNGs/SVGs) are regenerable; committed copies are reference snapshots.
- Findings documents describe specific historical commits/models; numbers
  there do not automatically describe current code.
