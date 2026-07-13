# Testing Guide for Agents

Instructions for running A/B tests and prover-performance tests. When the user asks you to follow this guide, use these patterns.

## When to use which pattern

- **A/B test (two worktrees)**: comparing two code states on the same lemma(s). Example: "test my changes on branch X against main on pr_Foo".
- **Regression test (one worktree, N reruns)**: measuring variance of a single configuration. Example: "run pr_Foo 5 times on feature-x to check stability".
- **Single-branch evaluation**: one worktree, one or more lemmas, capture metrics. Example: "test br93 lemma on my branch".
- **Compiler smoke matrix**: fast offline tests for ProofIR/semantic-index facts without running EasyCrypt proof search. Use after changes under `core/easycrypt/analysis/`, especially Pr canonicalization, lemma indexing, bound planning, or menu rendering.
- **Proof-bank replay audit**: deterministic replay of known tactics through `session_cli`, with structured event and tool-output checks. Use after changes to `core/easycrypt/`, `workflow/progress.py`, verifier acceptance logic, or inspection tools.
- **Blind skill test (`--eval-mode`)**: measure prover capability on a lemma WITHOUT letting it paste a known proof. Use when you want to test real reasoning rather than "can the prover find the answer in a cached proof". See the "Honest skill testing" section.

The A/B pattern is the most elaborate; the others are simplifications of it.

## Eval run + agent-view report (canonical flow)

To run a lemma with the managed prover and get a clickable, committed timeline
of exactly what the agent saw and did, run a suite via `eval_suite.run`:

```bash
eval "$(opam env --switch=easycrypt)"   # EC on PATH. Disable the OS sandbox: why3server needs nice().
python3 -m eval_suite.run --suite <suite.json>
```

A minimal single-lemma suite (e.g. `tmp/my_suite.json`):

```json
{
  "suite": "my_run",
  "defaults": {"include_dir": "easycrypt-src/theories", "max_iterations": 1,
               "eval_mode": true, 
               "model": "claude-opus-4-8"},
  "profiles": ["l4_checked_action_surface"],
  "targets": [{"id": "chacha_step1", "file": "eval/examples/ChaChaPoly/chacha_poly.ec",
               "lemma": "step1", "copy_root": "eval/examples/ChaChaPoly"}]
}
```

- `eval_mode: true` proof-strips the isolated source copy before the prover
  sees it (real reasoning, not proof-bank paste). Omit `tree_initial_provers`
  to use the default (multi-tree).
- `model` under `defaults` pins the prover model for the run; omit it to use
  the configured default (`claude-opus-4-8`).
- Tests run with `python3 -m pytest` — pytest is NOT in the `uv` env.

Every run auto-writes a **committed, self-contained report bundle** under the
fixed, non-gitignored location `agent_view_runs/` (so a `git push` never drops
it):

```
agent_view_runs/
  INDEX.md                                   # index of every run
  <lemma>/<TS>__<commit8>[-dirty]/
    timeline_report.md      # env header (commit / time / model / profile /
                            # outcome / turns) + step-by-step table
    timeline_report.json
    run_meta.json
    views/<Tree_x_y>/turn_NNN.json            # the exact per-turn ProverWorkspaceView
```

Open `timeline_report.md` and click any `turn_NNN.json` to read that step's
exact agent view — this is the loop for finely tuning the view.

For a direct (non-suite) `workflow.orchestrator` run, build the same bundle
manually from the run's `iteration_1` dir:

```bash
python3 -m workflow.validation.run_report_bundle <run>/iteration_1 \
  --timestamp <run-dir-name> --lemma <L> --model <M> \
  --profile l4_checked_action_surface --eval-mode
```

## Compiler smoke matrix

`tests/test_compiler_smoke_matrix.py` is the fast regression suite for the
compiler layer's generalization claims. It builds ProofIR directly from goal
text and visible project declarations, then checks typed facts rather than
complete proofs. Layer commitments are documented in
`core/easycrypt/analysis/CONTRACTS.md`; core fact shapes and authoring rules
are documented in `core/easycrypt/analysis/SCHEMAS.md` and
`core/easycrypt/analysis/LEMMA_AUTHORING.md`.

Run it after analysis-layer changes:

```bash
python3 -m pytest tests/test_compiler_smoke_matrix.py -q
```

Current matrix rows cover:

- PRG: additive bad-event bound (`Plog_Psample`)
- BR93: union-bound game hop (`pr_Game0_Game1`)
- ChaChaPoly: numbered-step bound lemma (`step2_1`)
- MEE-CBC: named birthday bound (`Bound_by_Birthday`)
- synthetic style variants where the lemma name has no `pr_`/`bound` hint

Each row should assert all three compiler boundaries:

- semantic lemma recall: `semantic_pr_bound_candidates` contains the expected
  project-local lemma by Pr/game/event shape
- obligation planning: `pr_obligation_plan` records bound/union/native-search
  obligations before proof search
- action rendering: `candidate_menu` exposes Pr-layer plans or `-where`
  lookups and does not immediately fall through to generic `byequiv`

When adding a new benchmark family, add one row that points at the real
`eval/examples/...` source file and, if the failure involved naming/style
variation, a small synthetic style row with a deliberately uninformative lemma
name. This keeps the test about compiler facts, not proof-bank retrieval.

## Proof-bank replay audit

`workflow.validation.proof_replay` is the deterministic contract test for the
session toolchain. It reads `workflow/proof_bank.jsonl`, starts a fresh
EasyCrypt session for each entry, replays each tactic, optionally runs
read-only tools at checkpoints, then calls `session_cli -verify`.

Run the full proof bank with a lightweight status audit:

```bash
python3 -m workflow.validation.proof_replay \
  --audit-tools status \
  --artifact-root /tmp/proof-replay-artifacts \
  --timeout 300
```

Run one lemma with deeper tool auditing:

```bash
python3 -m workflow.validation.proof_replay \
  --lemma PIR_secure2 \
  --audit-tools status,goal-info,goal-patterns,align,subgoal-gap,suggest-close,diagnose \
  --audit-every 2 \
  --artifact-root /tmp/proof-replay-audit-pir \
  --timeout 240
```

Passing criteria:

- Every selected proof reports `outcome: PASS`.
- The root `summary.json` has `consistency_warnings: 0` for every proof.
- Every proof has one `verification.completed` event with status `pass`.
- Closed proof tools are non-suggestive: `goal-info` has no suggested tactics,
  `goal-patterns` says the proof is complete, and `suggest-close` says there
  are no goals to close.

Artifacts are written under the requested `--artifact-root`; see
`workflow/validation/README.md` for the event schema and artifact layout.

## Proof-manager refactor gate

Use this gate after changes to `workflow/proof_node_manager.py`,
`workflow/proof_management/`, manager-owned route memory, checkpoint handling,
workspace-view rendering, or refactor-anchor validation. It catches
disappearing panels, stale checkpoint wiring, and accidental replay-battery
holes before expensive prover jobs.

Fast unit gate:

```bash
python3 -m pytest \
  tests/test_proof_checkpoint_manager.py \
  tests/test_proof_event_manager.py \
  tests/test_proof_memory_manager.py \
  tests/test_proof_node_state_manager.py \
  tests/test_proof_view_renderer.py \
  tests/test_call_site_analyzer.py \
  tests/test_frame_obligation_analyzer.py \
  tests/test_pure_tail_analyzer.py \
  tests/test_recovery_diagnosis_analyzer.py \
  tests/test_seq_cut_analyzer.py \
  tests/test_lemma_lineage_store.py \
  tests/test_prover_workspace_view_anchor.py \
  tests/test_proof_node_manager.py
```

Runtime/replay smoke gate:

```bash
python3 -m pytest \
  tests/test_proof_node_resume.py \
  tests/test_proof_node_runtime.py \
  tests/test_trace_replay_battery.py \
  tests/test_proof_view_replay_batch.py \
  tests/test_proof_view_replay_alignment.py \
  tests/test_agent_view_timeline_report.py
```

ChaChaPoly workspace-view anchors:

```bash
python3 -m workflow.validation.prover_workspace_view_anchor manifest \
  --manifest workflow/validation/anchors/proof_manager_refactor_views.json
```

Default trace/replay battery:

```bash
python3 -m workflow.validation.trace_replay_battery --default --json
```

Passing criteria:

- core panels remain present at every anchor
- L4 surfaces do not disappear at the same anchor point
- new panels are additive only
- default replay battery reports zero missing cases

## Cross-commit view replay

Use this to compare, under the **same canned proof-intent sequence and no live
agent**, what the prover agent would see in its `ProverWorkspaceView` across two
commits. It answers "did my change alter the agent-facing view, and if so where?".
`manager_view_replay` is the capture-and-compare tool here; for the weaker,
order-insensitive refactor gate use `prover_workspace_view_anchor` (above), and
for single-version panel-policy compliance use `view_philosophy_audit`. See the
"View comparison & audit tools" section in
[`workflow/validation/README.md`](workflow/validation/README.md) for the full
division of labor.

The capture step bakes the checkout's source into its output, so it must run
**once per commit, inside that commit's own worktree**. Each run writes per-turn
agent surfaces under `workspace_views/turn_*.json` in its output dir.

### 1. One worktree per commit

```bash
git worktree add .worktrees/view-left  <commit-left>
git worktree add .worktrees/view-right <commit-right>
```

### 2. Capture each commit's views (run BY FILE PATH)

Run the replay script by its file path, with `--project-root` pointing at the
matching worktree, once per commit:

```bash
python3 .worktrees/view-left/workflow/validation/manager_view_replay.py replay \
  --project-root .worktrees/view-left \
  --out-dir /tmp/view-left

python3 .worktrees/view-right/workflow/validation/manager_view_replay.py replay \
  --project-root .worktrees/view-right \
  --out-dir /tmp/view-right
```

### 3. Compare the two output dirs

```bash
python3 workflow/validation/manager_view_replay.py compare \
  --left /tmp/view-left \
  --right /tmp/view-right
```

`compare` is an order-aware textual diff: it respects panel/key order, ignores
per-run and path noise, and flags `proof_diverged` when the committed goal
differs at the same turn.

### Footgun: do NOT run capture with `python3 -m`

```bash
# WRONG — silently compares a checkout against itself:
python3 -m workflow.validation.manager_view_replay replay \
  --project-root .worktrees/view-left --out-dir /tmp/view-left
```

Once the `workflow` package is imported under `-m`, the package's own location
on disk wins over `--project-root` on `sys.path`, so `--project-root` is
**silently ignored** and you capture the *current* checkout instead of the
target worktree — both "captures" come from the same source and `compare` shows
no real difference. Always invoke the script **by file path** (the path inside
the target worktree), as in step 2. The tool itself now errors out if it detects
a `-m` invocation with a mismatched `--project-root`, but do not rely on that as
your only guard.

## Honest skill testing (`--eval-mode`)

Ordinary non-eval workflow runs may use broad project context and may record
successful proofs to `workflow/proof_bank.jsonl` for later deterministic replay.
For skill measurement, `--eval-mode` blinds the prover to target-specific proof
material so the run measures proof construction rather than retrieval.

Run an eval-mode attempt with:

```bash
python3 -m workflow.orchestrator \
  --file eval/examples/PIR.ec --lemma Pr_PIR_s \
  --include-dir easycrypt-src/theories \
  --max-iterations 1 \
  --eval-mode
```

What it does:
- Agent file/source policy denies reads of target proof caches
  (`workflow/proof_bank.jsonl`).
- Proof-bank writes are opt-in in eval/live-smoke contexts; use
  `--record-proof-bank` only when intentionally adding the run result to the
  regression corpus.

What it does NOT filter (manual steps if you want to be thorough):
- Sibling lemmas in the target `.ec` file (legitimate context, but may leak proof shape).

If you want maximum blinding, also rename the target lemma temporarily before the run.

## Proof-node resume capsules

Long tree evals automatically archive EC sessions and write proof-node resume
capsules under:

```text
<run_dir>/iteration_N/resume_capsules/
```

These capsules are **not** from-scratch eval data. They are for continuation
debugging: replay a verified accepted tactic prefix, reconstruct the same EC
state in a fresh session, then ask the prover to finish the suffix.

Use this when a hard lemma reaches an interesting frontier near timeout and you
want to avoid burning the next run on the same first 40-60 minutes.

```bash
python3 -u -m workflow.orchestrator \
  --file eval/examples/ChaChaPoly/chacha_poly.ec \
  --lemma step4_badi \
  --include-dir easycrypt-src/theories \
  --max-iterations 1 \
  \
  --eval-mode \
  --prover-timeout-minutes 60 \
  --resume-capsule workflow/runs/<run>/iteration_1/resume_capsules/Tree_0_1_0/resume.json \
  --resume-capsule workflow/runs/<run>/iteration_1/resume_capsules/Tree_0_1_2_0_3/resume.json
```

Notes:
- Passing multiple `--resume-capsule` values starts multiple replayed tree
  roots, one per capsule.
- By default, roots are ordered by capsule score. Use
  `--resume-root-policy diversity` to interleave route families when several
  capsules compete for a limited active-node budget.
- The resumed prover is told this is a continuation run. Do not mix a resumed
  success with from-scratch eval success rates.
- The capsule stores `history.ec`, current-goal hash/preview, recent attempts,
  and the latest structured views. It does not require reading old sibling
  session dirs during the resumed proof.
- If the code commit differs from the capsule's source commit, the run warns
  and relies on replay to validate whether the prefix still reaches the same
  state.

## Single-commit worktree eval flow

Use this for the common workflow: test one code commit on several hard lemmas,
without touching the main checkout. This is the recommended flow for overnight
ChaChaPoly / MEE / similar eval runs.

For reportable benchmark evals, prefer the `eval_suite.run` path below. It creates
isolated proof-stripped source copies, writes artifacts under
`artifacts/eval_suite/...`, and gives stable run containers for timeline and
metrics generation. Direct `workflow.orchestrator` commands are still useful
for backend debugging, but they are the lower-level fallback.

### 1. Create one worktree per lemma

Keep worktrees inside the ignored `.worktrees/` directory, and name them with
the commit plus lemma. One lemma per worktree keeps session dirs, modified
target files, and run artifacts isolated.

```bash
BASE=a014dfb
STAMP=20260508
LEMMA=step1
WT=.worktrees/eval-${STAMP}-${BASE}-${LEMMA}

git worktree add "$WT" "$BASE"
```

Do not run long evals from the main checkout. If the prover writes a proof into
the target `.ec` file, or a session tool creates local state, it should happen
only inside the disposable worktree. Start the worktree from the commit that
contains the framework patch you intend to evaluate; restarting an old worktree
can silently rerun old bugs.

### 2. Create a local suite file

Create one ignored suite JSON per run under the worktree's `tmp/` directory.
Use `l4_checked_action_surface` for standard proof-construction evals
unless the question is explicitly about another compiler layer.  Use canonical
surface profile names only; configure tree topology separately.

Example single-target large-project suite:

```json
{
  "suite": "large_project_mee_cbc",
  "profiles": ["l4_checked_action_surface"],
  "defaults": {
    "eval_mode": true,
    
    "max_iterations": 1,
    "timeout_minutes": 120,
    "repeats": 1,
    "output_dir": "artifacts/eval_suite",
    "source_isolation": true,
    "strip_proofs": true
  },
  "targets": [
    {
      "id": "bound_by_birthday",
      "file": "eval/examples/MEE-CBC/CBC.eca",
      "lemma": "Bound_by_Birthday",
      "include_dir": "easycrypt-src/theories",
      "copy_root": "eval/examples/MEE-CBC"
    }
  ]
}
```

Use `copy_root` whenever the target file imports sibling files, such as
ChaChaPoly or MEE-CBC. The suite runner copies that directory under the run
container, then proof-strips every `.ec`/`.eca` file in the isolated copy.

For an old direct-orchestrator debug run, manually replace only the target
proof body with `admit.` inside the worktree before launch. Do not do this in
the main checkout.

### 3. Dry-run and launch from the worktree

Run from the worktree root. For EasyCrypt commands, load the configured opam
switch first. In sandboxed agent environments, EasyCrypt / `session_cli` /
orchestrator runs must be allowed outside the OS sandbox so Why3 can start.

Preview the expanded commands:

```bash
cd "$WT"
uv run python -m eval_suite.run \
  --suite tmp/<suite>.json \
  --profiles l4_checked_action_surface \
  --dry-run
```

When using the Claude subscription rather than API billing, unset provider API
keys in the launch environment:

```bash
eval "$(opam env --switch=easycrypt)"
env -u ANTHROPIC_API_KEY \
    -u OPENAI_API_KEY \
    -u OPENROUTER_API_KEY \
    -u DEEPSEEK_API_KEY \
  uv run python -m eval_suite.run \
    --suite tmp/<suite>.json \
    --profiles l4_checked_action_surface \
  2>&1 | tee tmp/<target>_l4_checked_action_surface.log
```

The log should show that eval mode is active and that the target source is an
isolated copy under the run artifact, not the main checkout. For runs using the
per-run EasyCrypt daemon, the socket path should live under the repo-level
`tmp/ec_daemons/...` and stay short.

If a suite run immediately says the lemma is already proved, source isolation
or evaluation source stripping failed. Fix the suite/worktree and restart; do
not count a skipped run as a prover success.

### 4. Direct orchestrator fallback

Use this only for low-level debugging or when the suite runner cannot express
the experiment. In that case, proof-strip the evaluation source in the worktree first and
write logs under ignored artifacts:

```bash
mkdir -p artifacts/eval-runs/${STAMP}
python3 -u -m workflow.orchestrator \
  --file eval/examples/MEE-CBC/RCPA_CMA.ec \
  --lemma CTXT_security \
  --include-dir easycrypt-src/theories \
  --max-iterations 1 \
  \
  --eval-mode \
  --prover-timeout-minutes 60 \
  2>&1 | tee artifacts/eval-runs/${STAMP}/CTXT_security.log
```

### 5. Monitor without mixing state

Track each run by its shell session, worktree path, and log path. Do not read
session dirs from sibling worktrees or older runs. For current status, use the
live log plus the current worktree's own `artifacts/eval_suite/...` run
container. If using the direct fallback, use that worktree's own
`workflow/runs/...` artifacts.

Useful log checks:

```bash
grep -E "Phase 1: PROVE|final_proved|final_regression_ok|No prover succeeded|Verification PASSED|Verification FAILED" tmp/<target>_l4_checked_action_surface.log
grep -E "Using per-run EasyCrypt daemon socket|probe_tactic|commit_tactic|finish" tmp/<target>_l4_checked_action_surface.log | tail
```

When analyzing behavior, use both:

- the orchestrator log: accepted tactics, errors, tree kills, time elapsed
- the Claude/session trace for thinking blocks: why the prover chose a path,
  whether it was mechanically searching or making a strategy decision

### 6. Generate run reports

After a run finishes, copy only the interpretation layer back to the main
checkout under the right report bucket:

- compiler/interface matrix and sanity checks:
  `docs/reports/eval_suite/`
- project-scale case studies:
  `docs/reports/large_projects/<project>/`

Generate a deterministic timeline from the selected `iteration_1` directory:

```bash
python3 -m workflow.validation.agent_view_timeline_report \
  --chronological \
  --run <label>=<run_container>/iteration_1 \
  --output docs/reports/<bucket>/<target>_l4_checked_action_surface_timeline.md \
  --json-output docs/reports/<bucket>/<target>_l4_checked_action_surface_timeline.json
```

Collect metrics from the run container:

```bash
python3 -m eval_suite.metrics \
  <run_container> \
  --json-output docs/reports/<bucket>/<target>_l4_checked_action_surface_metrics.json \
  --markdown-output docs/reports/<bucket>/<target>_l4_checked_action_surface_metrics.md
```

Then write the normalized `*_report.md` and, when useful, curated
`*_quality_notes.json` plus `*_timeline_annotated.md`. Solved reports must
include the final EasyCrypt proof block from the winning `history.ec`; partial
reports must label any prefix as incomplete.

For L4 reports, record rollback/recovery episodes with the visible
`recovery_diagnosis_surface.recovery_class` when present. Distinguish
structural recovery evidence such as `boundary_repair_evidence`,
`call_frontier_recovery_evidence`, and `seq_midpoint_repair_evidence` from
current-state work such as `local_pure_surgery_available` and
`residual_program_surgery_available`, and note whether the chosen rollback was
effective.
When a run spends time on one-sided `call{1}`/`call{2}` or `ecall{1}`/`ecall{2}`
proof-term shape, record any visible
`call_site_surface.one_sided_call_surface` evidence separately from recovery:
Hoare/Phoare handles, losslessness handles, recent direct-call shape failures,
and whether the final proof used a packaged `phoare[...] = 1%r` certificate or
an anonymous one-sided call spec.

At minimum, record these paths in the run report:

- worktree path
- log path
- `artifacts/eval_suite/<suite>/<profile>/<target>/.../<run>/`
- winning `history.ec`
- Claude/session trace path when available

To package a run for sharing, prefer a repo-local archive under ignored
`artifacts/`:

```bash
cd "$WT"
tar -czf artifacts/eval_suite/<suite>/<target>-trace.tgz \
  tmp/<target>_l4_checked_action_surface.log \
  artifacts/eval_suite/<suite>/<profile>/<target>/r01/<run>
```

### 7. Cleanup

After analysis, either keep the worktree for reproducibility or remove it
explicitly:

```bash
git worktree remove "$WT"
```

If keeping it, mark the worktree and log path in the report so future agents do
not confuse it with the main checkout or another lemma's run.

## Chaining runs in one worktree: `scripts/run_queue.sh`

To run several suites/orchestrator commands back-to-back in ONE worktree
(e.g. an overnight lane), use `scripts/run_queue.sh` instead of hand-writing a
launcher script. Hand-rolled launchers that wait on `pgrep -f PATTERN` are
banned: in one incident, three of them phase-locked by matching each other's
concurrently-running pgrep cmdlines and waited forever. The queue runs steps
strictly sequentially in a single shell, so there is nothing to poll.

Write a queue file (one bash command per line, `#` comments allowed), with
per-step env inline — a distinct `WHY3EC_SOCKET` per step is mandatory, and
`SHANNON_DISABLE_PROBE=1` marks L4np arms:

```bash
# tmp/night_chain.txt
WHY3EC_SOCKET=/tmp/why3ec_lane_a1.sock uv run python -m eval_suite.run --suite tmp/suite1.json > tmp/suite1.log 2>&1
SHANNON_DISABLE_PROBE=1 WHY3EC_SOCKET=/tmp/why3ec_lane_a2.sock uv run python -m eval_suite.run --suite tmp/suite2.json > tmp/suite2.log 2>&1
```

Launch it (environment is inherited — set the opam switch and unset provider
API keys first, as for any eval run):

```bash
cd "$WT"
eval "$(opam env --switch=easycrypt)"
nohup bash scripts/run_queue.sh --settle 20 tmp/night_chain.txt &
```

Before every step it wipes stale `.ec_session_prover_tree_*` dirs (null-glob
safe via `find -exec`; never use zsh `rm -rf .ec_session_prover_tree_*` in an
`&&` chain — it aborts when nothing matches). Progress lines go to
`tmp/night_chain.txt.out`; a failed step is logged and the queue continues
(use `--stop-on-error` to abort instead).

If the queue must wait for a PRE-EXISTING run it did not start, pass the PID
explicitly — never a pgrep pattern:

```bash
nohup bash scripts/run_queue.sh --wait-pid 12345 tmp/night_chain.txt &
# or --wait-pidfile tmp/current_run.pid
```

Run one queue per worktree (`.ec_session_prover_tree_*` dirs are per-worktree
singletons). `bash scripts/run_queue.sh --help` shows all options; tests live
in `tests/test_run_queue.py`.

## A/B test pattern

### 1. Setup (ONCE per test campaign)

**Why `git worktree`** (not cloning twice or swapping branches in the main repo):
- Two checkouts of different branches on disk SIMULTANEOUSLY — required for parallel A/B runs.
- Shared `.git` dir, so cheap (no disk duplication of history) and keeps branches/tags/remotes in sync.
- Each worktree has its own independent working tree + index, so edits/stashes don't cross-contaminate.
- Cleanup is one command (`git worktree remove`); no risk of leaving loose branches dangling.

Create two parallel worktrees, one for each branch. Use a stable temp location (not the project dir, so you don't accidentally commit test artifacts to main):

```bash
W_A=/tmp/shannon-<branch-a>-worktree      # branch under test, e.g. shannon-feature-x-worktree
W_B=/tmp/shannon-<branch-b>-worktree      # baseline branch, e.g. shannon-main-worktree
git worktree add "$W_A" <branch-a>
git worktree add "$W_B" <branch-b>
```

After the campaign: `git worktree remove --force "$W_A" "$W_B"` (if dirs persist, follow with `rm -rf`). Each worktree is its own cwd; tools like `pkill` do NOT see the cwd in process argv, so always disambiguate by `lsof -p $PID | awk '$4=="cwd"'`.

### 2. Pre-launch cleanup (BEFORE EVERY RUN)

This is where most bugs hide. Run all of these in BOTH worktrees:

```bash
# Nuke ALL session dirs — wildcard is important. Prover agents create
# arbitrary session names (.ec_session_g0g1, .ec_session_red, etc.) beyond
# the standard .ec_session_prover_* pattern.
cd "$W_X" && rm -rf .ec_session* workflow/runs/*_<lemma_name> workflow/lab_notes/<lemma_name>.md

# Remove /tmp caches from prior runs of this lemma
rm -f /tmp/claude/<lemma>_*.log /tmp/claude/verify_<lemma>_extracted.*

# Reset the target .ec file to clean HEAD
cd "$W_X" && git checkout eval/examples/<file>.ec

# Replace the target lemma body with `admit.` (orchestrator skips lemmas
# with working proofs — MUST have admit to trigger the prover)
#   proof.
#   (* COMPLETE THIS *)
#   admit.
#   qed.
# Use the Edit tool with exact old_string/new_string matching the file.
```

### 3. Symmetry verification (BEFORE launch)

Silent asymmetries caused most of our confusion. Verify byte-identity, not just textual diff:

```bash
md5 "$W_A/eval/examples/<file>.ec" "$W_B/eval/examples/<file>.ec"
md5 "$W_A/core/easycrypt/session_cli.py" "$W_B/core/easycrypt/session_cli.py"
```

Both MD5s MUST match before launch. If they don't, the test is compromised.

Also diff code files in `workflow/` and `core/easycrypt/` to be thorough; don't assume the asymmetry is just in one file.

### 4. Launch

```bash
cd "$W_A" && eval "$(opam env --switch=easycrypt)" && \
  nohup python3 -m workflow.orchestrator \
    --file eval/examples/<file>.ec --lemma <lemma_name> \
    --include-dir easycrypt-src/theories \
    --max-iterations 1 \
    > /tmp/claude/<lemma>_A.log 2>&1 &
disown
# Repeat for $W_B → /tmp/claude/<lemma>_B.log

sleep 3 && ps -A -o pid=,command= | grep "workflow.orchestrator" | grep -v grep | wc -l
# Must print 2.
```

Uses `nohup + disown` so the shell tool can return before the orchestrator finishes. Use `--skip-regression` to save time (regression tests don't help the A/B signal).

### 5. Monitoring

Use the `Monitor` tool with an event-based filter, not a polling loop:

```
tail -F /tmp/claude/<lemma>_A.log /tmp/claude/<lemma>_B.log 2>&1 |
  grep -E --line-buffered "Phase 1: PROVE → proved=True|No prover succeeded|FileNotFoundError|Could not extract tactics"
```

You'll get a notification on the first success. For intermediate status checks (e.g., user asks "what's the status"):

```bash
# Identify which PID is which branch (cwd disambiguates)
ps -A -o pid=,command= | grep "workflow.orchestrator" | grep -v grep | awk '{print $1}' | \
  while read pid; do lsof -p $pid 2>/dev/null | awk '$4=="cwd"{print "'$pid' "$NF}'; done

# Current leaf progress
sed 's/\x1b\[[0-9;]*m//g' /tmp/claude/<lemma>_A.log | \
  grep -oE "Tree-0\.[0-9.]+ \(d=[0-9]+\): [0-9]+ tactics, [0-9]+ errors, errs_since_accept=[0-9]+, idle [0-9]+s \([0-9]+s elapsed\)" | tail -3
```

### 6. Kill-on-success pattern (optional — saves ~3–5 min per run)

After the Monitor fires, kill the winning orchestrator to skip post-prover phases:

```bash
# Identify winner's PID by its cwd, then kill
ps -A -o pid=,command= | grep "workflow.orchestrator" | grep -v grep | awk '{print $1}' | \
  while read pid; do
    cwd=$(lsof -p $pid 2>/dev/null | awk '$4=="cwd"{print $NF}')
    if [[ "$cwd" == *"$WINNER_BRANCH"* ]]; then kill -9 $pid; fi
  done
```

Do NOT use `pkill -f "<branch>"` — the cwd is not in the process's args, so the pattern won't match. Always match on `workflow.orchestrator` and disambiguate via `lsof` / cwd.

### 7. Clean up after each run

BEFORE analysis, kill all orchestrators and clean state again.

## Pitfalls we learned the hard way

1. **`pkill -f "shannon-feature-x"` matches nothing.** The process's argv is `python3 -m workflow.orchestrator --file ...` — the worktree name is only in its cwd, not in argv. Use `pkill -f "workflow.orchestrator"` and disambiguate by cwd via `lsof`.

2. **Session cleanup must use `.ec_session*` wildcard, not `.ec_session_prover_*`.** Prover agents create arbitrary session names like `.ec_session_g0g1`, `.ec_session_red`, `.ec_session2`. These can contaminate subsequent runs.

3. **Diff count ≠ symmetry.** `diff | wc -l` may return 0 momentarily, then drift back. Use MD5 hashes instead; they're deterministic.

4. **`.ec` file writes.** The prover writes proofs to the `.ec` file mid-run. If a prior run succeeded, the file has a real proof — the orchestrator's pre-check will skip. You MUST overwrite with `admit.` before each run.

5. **False-positive `[ALL_GOALS_CLOSED]`.** If the target lemma is pre-admitted in the session's context file, `smt(...). qed.` may report success trivially. This happens if `lemma_extract.py` produces an admit-form instead of an open `proof.`. Inspect `<session_dir>/extracted_*.ec` if you suspect this — the target lemma should end with `proof.` (open), not `admit.`.

6. **Multiple orphan orchestrators.** `nohup ... > file.log 2>&1 &` opens a new FD each time. If a prior orchestrator is still writing to the same path, you'll get interleaved logs. Always verify `ps ... | grep orchestrator | wc -l == 2` right after launch; kill any extras.

7. **Don't trust one A/B trial.** LLM sampling variance is large. One A-over-B trial means nothing. Three in a row is suggestive; five is fairly conclusive (p ≈ 0.03 under null). But if prover inputs are byte-identical and results still diverge, suspect orchestrator-level non-determinism, not prover stochasticity.

## Reporting results

For each run record:
- Branch, lemma, wall-clock time to `qed.`, tactic count, error count
- Winning leaf in tree mode (Tree-0.0 vs 0.1 vs spawned child)
- Whether verification passed (orchestrator reports `verified=True/False`)

For A/B campaigns: report cumulative win counts + mean times, not just the last result.

## Recovering from failures

- Stash before risky branch operations: `git stash push -u -m "WIP <date>"`
- Worktree removal: `git worktree remove --force <path>` may leave the directory on disk; follow with `rm -rf <path>` if sandbox restricts permissions.
- Orphan orchestrators: `pkill -9 -f "workflow.orchestrator"` is the nuclear option; always verify with `ps` after.
