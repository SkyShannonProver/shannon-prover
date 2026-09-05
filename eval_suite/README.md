# eval_suite — research benchmark runner

This guide covers controlled benchmarks of individual EasyCrypt lemmas.
For ordinary proof construction, start with the [project overview](../README.md).

`eval_suite.run` exists for controlled research evaluation. It expands a
checked-in target/profile matrix into managed `workflow.orchestrator` runs.
Each arm receives proof-stripped source isolation, the same manager controls,
metrics, and a reproducible bundle under `agent_view_runs/`.

## Current boundary

Normal use discovers only the production profiles registered by
`workflow/proof_state_compiler/profile_registry.py`. The suite runner may also
resolve exact private identities from
`workflow/validation/proof_state_compiler_research_profile_registry.py` and
passes them through an eval-only hidden transport. Ordinary config files and
the public `--surface-profile` option cannot select those audit or ablation
profiles.

Current suite inputs live in [`suites/`](suites/). Archived protocols are
evidence, not runnable suite templates, and the runner rejects archive paths.

## Commands

```bash
uv run python tools/bootstrap_easycrypt.py --verify-only

# inspect the public demo without launching an agent
uv run python -m eval_suite.run \
  --suite eval_suite/suites/demo_pir.json \
  --dry-run

# run the default proof-state compiler
uv run python -m eval_suite.run \
  --suite eval_suite/suites/demo_pir.json

# refresh metrics for an existing run output directory
uv run python -m eval_suite.metrics artifacts/eval_suite/<run_dir>
```

Strict live evaluation currently requires Linux and `bubblewrap` so the model
process can be proven unable to read the original checkout or cached proofs.
The runner fails closed before launching a model when that selective namespace
cannot be established. This requirement does not apply to ordinary `$prove`
or `/prove` use on macOS.

For a reproducible evaluation, start from a clean committed checkout, keep
generated outputs under `artifacts/`, and record the commit, suite, model,
and time limits. Run the dry run first to inspect the selected tasks. Start
long attempts in a persistent terminal session on the evaluation machine.
The EasyCrypt process needs permission to run `why3server`, including its
`nice()` call; the model's answer-source confinement is a separate requirement
and remains enabled.

## Suite JSON

```json
{
  "suite": "compiler_v2_example",
  "defaults": {
    "include_dir": "easycrypt-src/theories",
    "timeout_minutes": 30,
    "eval_mode": true,
    "source_isolation": true,
    "strip_proofs": true,
    "output_root": "artifacts/eval_suite"
  },
  "targets": [
    {"file": "eval/examples/PIR.ec", "lemma": "PIR_correct"}
  ],
  "profiles": ["proof_state_compiler"]
}
```

Useful keys include per-target `timeout_minutes`, `defaults.model`,
`copy_root`, `tree_initial_provers`, and `tree_max_concurrent`. CLI
`--targets` and `--repeats` select a checked-in subset. Compiler experiment
suites may additionally select registered profiles and counterbalance their
order.

The runner freezes repository/environment identity before live arms, rejects
mid-slate code drift, performs target-load preflight, and writes the verdict to
`eval_metrics.md` in the output directory.
