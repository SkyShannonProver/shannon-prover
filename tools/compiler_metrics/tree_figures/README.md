# Tree-search evaluation figures (§5.3)

Two final figures for the tree-search story. **Use these two; ignore `archive/`.**
Both read committed bundles under `agent_view_runs/` and emit dependency-free SVG
(no matplotlib). Morandi palette sampled from the paper's tactic-pyramid figure
(Fig 3): sage `#a7b89a`, clay `#c19a8b`, warm gray `#b3a99c`, terracotta delta `#9b6f60`.

| file | figure | what it shows |
|---|---|---|
| `fig_backtracking_summary.py` | **Figure A** | Hard proofs require backtracking far more than easy ones: (a) % of proofs needing any backtracking (easy ~11% vs hard ~41%), (b) mean backtracking ops/proof. Difficulty = committed-tactic count, split at median. |
| `fig_fork_casestudy.py` | **Figure B** | The fork-wins as search-tree case studies: on the hard tail only a forked child closes the proof; **0/3 closed by a root prover alone**. step3 / step4_lbad1_sum (parallel fork, hard) + chacha_spec (single-tree backjump-repair, medium). |

Run from the repo root:

```bash
python3 tools/compiler_metrics/tree_figures/fig_backtracking_summary.py
python3 tools/compiler_metrics/tree_figures/fig_fork_casestudy.py
```

## Narrative the two figures tell

1. **Figure A (setup, n≈75, full corpus):** proof search for hard lemmas is *non-linear*
   — it needs backtracking (undo · backjump-to-checkpoint · restart · branch), 3–5× more
   than easy lemmas. Honest: a single tree can also backtrack; this only sets up the need.
2. **Figure B (hard tail, N=3, existence proof):** backtracking escalates to *branching*.
   Roots make monotone progress (0 rejects) on a route that cannot close; only a fork to a
   different route from an earlier checkpoint closes it. No root closed any of these alone.

Honest boundary (state it in the paper): the aggregate single-tree-vs-multi-tree
solve-rate / speed comparison is **not** in the existing bundles (solve rate is censored
by early-stop; wall-clock is confounded by non-parallel hardware). That comparison needs
the controlled runs — see the data tools below.

## Rendering for the paper

The SVGs are padded to a square canvas only because the macOS `qlmanage` preview
thumbnailer clips width at x≈height. For the paper, render the `.svg` directly with a
real renderer (no clipping, no whitespace), e.g.:

```bash
rsvg-convert -f pdf fig_backtracking_summary.svg -o figA.pdf   # or inkscape / cairosvg
```

## Not figures (live data tools, kept one level up)

- `../tree_tradeoff_extract.py` — extracts the latency-vs-cost plane from the **controlled
  single/multi/orchestrator sweep** (suites: `eval/suites/tree_tradeoff_*.json`). This is
  the real answer to the reviewer's single-vs-multi ablation; run it after those suites.
- `../tree_ablation_extract.py` — exploratory analysis that documented the early-stop
  censoring (why single-vs-multi can't be read off existing bundles).

## `archive/` — superseded iterations, DO NOT USE

Earlier drafts kept for provenance: `tree_recovery_ladder_plot.py` (scatter),
`tree_recovery_figure.py` (bar + per-lemma bands), `tree_fork_casestudy_plot.py` (pre-Morandi
fork), `tree_combined_figure.py` (A+B in one). Superseded by `fig_backtracking_summary.py`
and `fig_fork_casestudy.py`.
