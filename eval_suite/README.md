# eval_suite — the benchmark runner

Runs a suite of lemma-proving targets through `workflow.orchestrator`, one
subprocess per target × surface profile × repeat, with per-run source
isolation (the target `.ec` is copied and its proofs stripped so the prover
cannot read the answers), metrics, and an auto-generated run bundle under
`agent_view_runs/`.

## Commands

```bash
eval "$(opam env --switch=easycrypt)"          # EasyCrypt on PATH first

# sanity-check a suite without running anything
uv run python -m eval_suite.run --suite eval_suite/suites/demo_pir.json --dry-run

# run it (l4_checked_action_surface = full compiler surface; l1_goal_projection = bare goal)
uv run python -m eval_suite.run --suite eval_suite/suites/demo_pir.json \
    --profiles l4_checked_action_surface

# refresh metrics for a run output dir
uv run python -m eval_suite.metrics artifacts/eval_suite/<run_dir>
```

The verdict file is `eval_metrics.md` in the run's output dir; the committable
replay artifact is the bundle under `agent_view_runs/<lemma>/<ts>__<commit>/`.
Run in a normal terminal (an OS sandbox blocks the `nice()` syscall that
`why3server` needs, so `smt()` would fail).

## Suite JSON

```json
{
  "suite": "demo_pir",
  "defaults": {
    "include_dir": "easycrypt-src/theories",
    "timeout_minutes": 30,
    "eval_mode": true,
    "strip_proofs": true,
    "output_root": "artifacts/eval_suite"
  },
  "targets": [
    {"file": "eval/examples/PIR.ec", "lemma": "PIR_correct"}
  ],
  "profiles": ["l4_checked_action_surface"]
}
```

Useful keys: per-target `timeout_minutes`; `defaults.model` (defaults to the
orchestrator's model); `copy_root` when the target needs sibling files (clone
chains) copied alongside; `tree_initial_provers` / `tree_max_concurrent` for
the tree scheduler. `--targets name1,name2` and `--profiles ...` filter a
suite from the CLI; `--repeats N` runs each target N times.

Checked-in suites live in [`suites/`](suites/): `demo_pir.json` (the
5-minute smoke target) and `chacha_step4_1_l1_l4.json` (a two-profile
L1-vs-L4 template to copy for new lemmas). The corpus itself lives in
`eval/examples/` — `eval/` is data, this package is the runner.
