# Testing and Experiment Workflow

This guide covers the current managed runtime and proof-state compiler V2.
Removed panel/profile/replay workflows are not supported test modes.

For any session-lifecycle, tree-selection, writeback, verification, or terminal
report change, run the live no-model terminal gate before an agent experiment:

```bash
uv run python -m workflow.validation.proof_terminal_outcome_sentinel \
  --run-dir artifacts/proof_terminal_outcome_foundation/<fresh-name>
```

It must show `goals_discharged_pending_qed`, an accepted committed `qed.`, a
bound completion candidate, passing offline verification, unchanged session
history during finalization, and matching `ProverResult`/summary/report output.

## Test layers

Run the cheapest layer that can falsify the change first, then widen.

### 1. Pure contracts and architecture

```bash
python3 -m pytest -q \
  tests/test_proof_state_compiler_foundation.py \
  tests/test_proof_state_compiler_service.py \
  tests/test_current_managed_envelope_foundation.py
```

These tests must cover pass boundaries, feature isolation, activation,
delivery, identity, and the absence of retired compiler imports.

### 2. Feature and native-adapter tests

Select the exact feature, native descriptor, state projection, resource loader,
certification, and abstention tests affected by the change. Examples:

```bash
python3 -m pytest -q \
  tests/test_proof_state_compiler_m05_trial.py \
  tests/test_proof_state_compiler_feature_micro.py \
  tests/test_compiler_resource_loader.py \
  tests/test_session_tactic_preflight.py
```

Mocks may test schema and failure boundaries. A native semantic claim also
needs at least one real EasyCrypt sentinel; Python parsing of printed text is
not a substitute.

### 3. Manager/event/replay integration

```bash
python3 -m pytest -q \
  tests/test_proof_node_manager.py \
  tests/test_proof_projection_pipeline.py \
  tests/test_authoritative_artifact_events.py \
  tests/test_workspace_episode_invocation_authority.py \
  tests/test_prover_ux_audit.py
```

Integration tests must prove current-call event authority, goal identity,
no-mutation behavior for compiler reads, and fail-closed stale/missing/multiple
artifact handling.

### 4. Full deterministic suite

```bash
python3 -m pytest -q
git diff --check
```

Do not compensate for failures by skipping tests that still exercise a current
contract. Delete a test only when its complete production capability was
intentionally retired.

## Required architecture sentinels

The suite must make these regressions difficult:

- default `ProverConfig` selects Codex and a current surface profile;
- unsupported proof modes and retired profiles fail rather than route through
  compatibility code;
- current worker, manager, MCP, compiler, and renderer imports do not load a
  retired analysis/panel module;
- L1 constructs no compiler service and exposes no compiler bytes;
- a feature set to OFF performs no loading, analysis, lowering, certification,
  or presentation work;
- audit and treatment share computation but audit exposes zero bytes;
- adding or deleting a feature does not modify manager, service facade, current
  turn contract, or renderer;
- every visible action has exact same-state EasyCrypt preflight evidence; and
- native adapter failures cannot fall back to source-text semantics.

## Real EasyCrypt tests

Bootstrap once, then verify the repository-managed EasyCrypt toolchain:

```bash
uv run python tools/bootstrap_easycrypt.py
uv run python tools/bootstrap_easycrypt.py --verify-only
```

The `uv` executable must not live inside the target project `.venv`; do not
let `.venv/bin/uv` recreate its own containing environment. Use a stable
user/system installation. Once synchronization has completed, direct
verification with `.venv/bin/python tools/bootstrap_easycrypt.py
--verify-only` is equivalent and avoids launcher self-removal.

Python tests and Shannon runtime entry points select the verified environment
through `core/easycrypt/ec_env.py`; do not activate an ambient opam switch.
For a developer-only command that invokes `easycrypt` directly, use:

```bash
eval "$(uv run python tools/bootstrap_easycrypt.py --print-env)"
```

Use the precise test or sentinel command documented by the relevant checkpoint.
If the OS sandbox blocks `why3server`/`nice()`, request permission for that
bounded command. Do not weaken the test or introduce a semantic fallback.

A real sentinel records:

- repository commit and dirty state;
- EasyCrypt build/version identity;
- source and target lemma identity;
- manager/session/goal identity;
- exact request and current-call event/artifact references;
- no-mutation evidence; and
- outcome/abstention reason.

## Micro experiments

A micro experiment answers one narrow causal question at a frozen proof state:

> Does this single feature replace the identified mechanical work, with a
> smaller total interaction cost, while preserving exact EasyCrypt validity?

Required controls:

- identical proof-stripped source and replay prefix;
- identical exact current goal and goal hash;
- same model/backend/effort and prompt except for the compiler payload;
- same source permissions and no hidden proof retrieval;
- control sees only the goal; treatment sees only the admitted feature item;
- each returned tactic is checked on the unchanged frozen state; and
- tokens, latency, candidate/certification/admission telemetry, and validity
  are recorded.

A positive micro result supports the local mechanical claim only. It does not
prove that the feature improves a complete proof route.

The current identical-state micro boundary is declarative. A campaign owns
its proof-stripped source, accepted prefix, rejected tactic, recovery owner,
output kind, provenance, profiles, and byte budget; the runner and independent
evaluator contain no feature-specific execution branch. Run the no-model gate
from a clean worktree before any provider call:

```bash
python3 -m workflow.validation.proof_state_compiler_feature_micro \
  --campaign operation_binding_repair \
  --prepare-only \
  --output tmp/operation_binding.prepare.json
```

After an authorized model batch, evaluate the immutable model and preparation
bundles separately:

```bash
python3 -m workflow.validation.proof_state_compiler_feature_micro_evaluator \
  --bundle tmp/operation_binding.micro.json \
  --preparation tmp/operation_binding.prepare.json \
  --json-output tmp/operation_binding.evaluation.json \
  --markdown-output tmp/operation_binding.evaluation.md
```

The action gate requires exact compiler-action consumption and an
EasyCrypt-accepted matching effect. The historical/default diagnostic gate
requires a measured control repetition burden; merely submitting a different
next tactic is not evidence of diagnostic consumption. A campaign may freeze a
stricter evaluator policy before sampling. The premature-apply recovery policy,
for example, requires every treatment tactic to be EasyCrypt-accepted, leave
the rejected selected-operation family, and use fewer aggregate tokens than
both L1 and hidden audit. The registry retains the original operation-binding
and structured-diagnostic provenance campaigns plus the separately
preregistered losslessness-call, original premature-apply explanation, and
native phase-redirect follow-up campaigns. The two premature-apply campaigns
are distinct interventions and must never share model rows. All use the same
semantic feature owner.

## Managed L1/A/B experiments

Run managed experiments only after deterministic and micro gates pass. L1 and
treatment must differ only at the compiler boundary. Hold fixed:

- OpenAI model and effort;
- long-lived agent/runtime and proof controls;
- source visibility and eval isolation;
- tree topology, time/turn/token budgets;
- prompt and manager behavior;
- runner, commit, EasyCrypt build, and environment; and
- target/repeat order or preregistered counterbalancing.

Report invalid infrastructure arms separately. Never replace a failed sample
by silently rerunning it. A completed trace can remain useful for descriptive
route/runtime evidence even when a block is invalid, but it cannot estimate a
causal feature delta.

## Suite runner

Only JSON protocols under `eval_suite/suites/` are runnable. First inspect the
plan:

```bash
python3 -m eval_suite.run --suite SUITE.json --dry-run
```

Then execute the same committed suite:

```bash
python3 -m eval_suite.run --suite SUITE.json
```

For a suite with a frozen `parallel_execution` contract, use the block
scheduler. It runs each target block's arms sequentially, runs only the
suite-declared blocks concurrently, and waits at every declared wave barrier:

```bash
python3 -m eval_suite.parallel_blocks --suite SUITE.json
```

Do not simulate this with shell background jobs. Independent top-level suite
runners would each own a partial manifest and could race tracked report-bundle
generation. The block scheduler gives every child an exact manifest path,
defers bundle generation, and produces one evaluator-facing aggregate manifest
in frozen arm order.

Before a remote model run, execute the same source-preparation, EasyCrypt-load,
and selective-namespace gates without starting an orchestrator or provider:

```bash
python3 -m eval_suite.run \
  --suite SUITE.json \
  --preflight-only \
  --preflight-output tmp/SUITE.preflight.json
```

For a parallel suite, the mandatory remote gate is the parallel form so source
preparation, EasyCrypt load checks, and confinement probes are exercised under
the same bounded wave concurrency without a model process:

```bash
python3 -m eval_suite.parallel_blocks \
  --suite SUITE.json \
  --preflight-only \
  --preflight-output tmp/SUITE.parallel-preflight.json
```

The report must say `preflight_valid=true`, retain one record per selected
arm, and say `model_process_launched=false`. This mode creates no experiment
execution manifest, so the subsequent long-run manifest set difference remains
unambiguous. A normal long run repeats the confinement probe immediately
before every model launch; `--skip-preflight` skips only the EasyCrypt batch
load check and never bypasses confinement.

Proof stripping covers declaration proofs and residual realization/clone
proofs, including one-line `proof. ... qed.` forms. A strict failure caused by
an intentional proof shell is only an inconclusive batch-load observation; it
is never positive target evidence. The manager's exact target bootstrap remains
the fail-closed authority before the provider starts.

The runner rejects archived protocols. Do not copy an old report configuration
back into the current suite namespace to make it executable.

## Remote long-run discipline

Use one dedicated ignored worktree per long experiment. The remote operator or
agent may resolve local environment details (Python environment, opam setup,
available pytest executable, output directory) without changing the scientific
design.

At the start:

1. `git fetch origin`;
2. create a worktree at the exact full commit hash;
3. verify `git rev-parse HEAD` against the full hash;
4. verify the worktree is clean;
5. run focused deterministic tests;
6. run the suite's no-model preflight and require every record to pass; and
7. record Python, EasyCrypt, model/backend, and suite provenance.

At the end:

1. preserve raw runs and the runner manifest;
2. generate a concise report without rewriting raw evidence;
3. classify invalid/environment/feature outcomes explicitly;
4. commit only experiment artifacts and intended report changes;
5. confirm `git status --short`; and
6. push by normal fast-forward, never force.

If the base checkout is dirty, create a separate worktree; do not stash,
overwrite, or clean someone else's changes. If a prerequisite command differs
on the remote host, find the equivalent environment command and continue while
recording it. Stop only when the scientific protocol or source commit would
change.

## Checkpoint checklist

Before pushing a foundation or feature checkpoint:

- focused tests pass;
- full tests pass;
- real EasyCrypt sentinels required by the claim pass;
- `git diff --check` is clean;
- current docs and implementation agree;
- historical reports remain provenance-only;
- no untracked experiment secrets or proof caches are included; and
- the commit message names the architectural or evidence boundary closed.
