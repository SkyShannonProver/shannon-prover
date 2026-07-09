# EDA Regression Experiment Protocol

This protocol measures whether the event-driven architecture made the prover
experience worse, better, or unchanged. The default goal is regression safety:
the EDA path is the desired architecture, so the experiment asks whether it
breaks existing proof behavior or creates confusing prover views.

Planner context is part of the default EDA prover contract, including eval
mode. Eval mode redacts target-specific cached proof material, but it still
runs the deterministic planner and injects the planner's structured context
brief. Use `--no-planner` only for explicit planner-ablation experiments, e.g.
when measuring the planner's effect for a paper.

## 1. Contract Preflight

Run deterministic proof-bank replay before any live Claude run:

```bash
mkdir -p artifacts/tmp
env TMPDIR=artifacts/tmp python3 -m workflow.validation.proof_replay \
  --audit-tools status,agent-view,episode-view \
  --prover-ux-audit \
  --prover-behavior-audit \
  --write-prover-timeline \
  --artifact-root artifacts/replay/eda-preflight \
  --timeout 300
```

Pass criteria:

- all selected proof-bank entries pass offline verification;
- `audit_report.json` has zero event, ToolView, ProofContextView,
  CommitResponse, CommandSummary, and EpisodeTimeline contract errors;
- `prover_ux_report.json` has zero errors;
- `prover_behavior_report.json` has zero errors.

Warnings are reviewed, not automatically fatal. They are useful for spotting
flailing patterns, repeated read-only tool calls, and guidance follow-through
rates.

## 2. Live Claude Smoke

Use a copied proof file or an intentionally disposable worktree target so the
smoke run can write proofs without changing benchmark sources. Keep the first
smoke small:

```bash
python3 -m workflow.orchestrator \
  --file artifacts/live_smoke/SchnorrPK_smoke.ec \
  --lemma schnorr_proof_of_knowledge_completeness_ll \
  --include-dir easycrypt-src/theories \
  --max-iterations 1 \
  --skip-regression \
  --prover-model claude-sonnet-4-6 \
  --prover-timeout-minutes 5 \
  --eval-mode
```

For a planner ablation only:

```bash
python3 -m workflow.orchestrator \
  --file artifacts/live_smoke/SchnorrPK_smoke.ec \
  --lemma schnorr_proof_of_knowledge_completeness_ll \
  --include-dir easycrypt-src/theories \
  --max-iterations 1 \
  --skip-regression \
  --prover-model claude-sonnet-4-6 \
  --prover-timeout-minutes 5 \
  --eval-mode \
  --no-planner
```

After the run, audit the recorded EasyCrypt session:

```bash
python3 -m workflow.validation.prover_behavior_audit <ec_session_dir> --write
python3 -m workflow.tools.trace_analyzer --format json <claude_trace.jsonl>
```

Record the model, prompt hash or commit SHA, target file/lemma, timeout,
`SHANNON_LEGACY_DISPLAY` value, `ec_session_dir`, Claude trace path, and whether
the run was eval-mode.

`prover.run` archives project-root `.ec_session_*` directories under
`<run_dir>/ec_sessions/` before the next run can clean them. Inspect archived
`events.jsonl`, `proof_context_views/`, `prover_workspace_views/`,
`command_summaries/`, and `commit_responses/` there for postmortems.

Eval-mode and `artifacts/live_smoke/*` runs do not write
`workflow/proof_bank.jsonl` by default. Opt in explicitly with
`--record-proof-bank` or `record_proof_bank=True` only when the run should
become regression corpus material.

## 3. Compare To Baseline

If a pre-EDA branch or commit is available, run the same target set with the
same model/timeout and compare:

- proof success and offline verifier status;
- number of accepted tactics;
- wall-clock time;
- manager intents by name and any `session_cli.agent_call_debug_signal` events;
- repeated read-only calls on the same goal hash;
- failed-command to `inspect_context(diagnose)` follow-through;
- candidate-closed to verify follow-through;
- Claude trace stats: proof intents, malformed repairs, `lookup_symbol` calls,
  `inspect_context` topics, CommandSummary/backend blocks, thinking blocks, and
  surfaced error messages.

If no runnable pre-EDA baseline is available, use deterministic proof-bank
replay as the golden regression gate and compare live runs against prior saved
EDA reports.

## 4. Artifact Convention

Keep generated experiment outputs under repo-local artifact directories:

```text
artifacts/replay/<run-name>/
artifacts/live_smoke/<run-name>/
artifacts/tmp/
```

The prover scratch root defaults to `artifacts/tmp/claude`. Override with
`SHANNON_TMP_DIR` only when the alternative path is intentionally allowed by
the run environment.
