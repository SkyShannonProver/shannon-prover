# compiler_metrics — file index

## Paper figures

Scripts that produce final figures for the paper. Each has a run command at the
top of the file.

### Compiler ablation (§5.2) — 2 figures

All in `paper_figures/`. Output: matplotlib PNG.

| script | paper figure | what it draws |
|---|---|---|
| `paper_figures/fig1_headlines.py` | Fig 1 top | 4-panel aggregate bars: error-gen rate, destructive token share %, abs destructive tokens, speed-up (L1 baseline vs L4 ours) |
| `paper_figures/fig1_perlemma.py` | Fig 1 bottom | per-lemma horizontal bars tiered structural/easy, plus per-lemma speed-up |

Data pipeline (run in order from repo root):

1. `paper_figures/build_dataset.py` → `paper_figures/data/master_metrics.csv`
2. `paper_figures/compute_tokens.py` → `paper_figures/data/token_metrics.csv`
3. `paper_figures/fig1_headlines.py` → `paper_figures/out/fig1_headlines.png`
4. `paper_figures/fig1_perlemma.py` → `paper_figures/out/fig1_perlemma.png`

Shared config (palette, tiers, metric getters): `paper_figures/_shared.py`.

### Tree-search ablation (§5.3) — 2 figures

All in `tree_figures/`. Output: dependency-free SVG (no matplotlib).

| script | paper figure | what it draws |
|---|---|---|
| `tree_figures/fig_backtracking_summary.py` | Fig A | 2-panel bars: hard proofs need ~4× more backtracking than easy ones |
| `tree_figures/fig_fork_casestudy.py` | Fig B | fork case studies: at the hard tail, only forks close the proof (3 examples) |

Run from repo root:

```bash
python3 tools/compiler_metrics/tree_figures/fig_backtracking_summary.py
python3 tools/compiler_metrics/tree_figures/fig_fork_casestudy.py
```

Both read directly from `agent_view_runs/`. Morandi palette.

---

## NOT paper figures

Analysis, debugging, and data-extraction tools. Do not produce paper figures.

| file | purpose |
|---|---|
| `compute_metrics.py` | older seconds-based metrics computation |
| `make_outputs.py` | older output/plot generation |
| `stuck_pipeline.py` | stuck-episode analysis and diagnosis plots |
| `tree_ablation_extract.py` | exploratory single-vs-multi-tree analysis (documented the early-stop censoring gap) |
| `tree_tradeoff_extract.py` | latency-vs-cost extraction for the controlled tree-search sweep |
| `ablation_suite_template.json` | eval suite template for ablation runs |
| `metrics.json` | cached metrics output |
| `stuck_out/` | stuck_pipeline output artifacts |
| `bundles/` | copied run bundles used by build_dataset |
| `tree_figures/archive/` | superseded figure drafts (scatter, bar+bands, pre-Morandi) |
