# Prove one EasyCrypt security theorem

## Objective and edit boundary

Complete `conclusion` in `experiments/interleaved_shannon/task/chacha_poly.ec`. Produce a complete, machine-checked IND-CCA proof; discovering the decomposition is your responsibility.

You may add declarations between:

```easycrypt
(* SCRATCHPAD BEGIN — your own declarations may go below this line *)
(* SCRATCHPAD END *)
```

You may also replace the proof body of `conclusion`. Do not change the markers,
target statement, existing declarations, `ske.ec`, or `indistinguishability.eca`.

## Your role

You are the outer proof engineer. You own the game sequence, helper statements, modules, invariants, decomposition, source edits, and final assembly.

Never submit `conclusion` to Shannon. Do not ask Shannon to invent the overall reduction. It may test a route, find a prefix or blocker, refine an invariant, or finish a residual goal.

## Operating model

Use coarse-grained outer development and fine-grained Shannon proof-state work as complementary,
interleaved lanes. You need not finish decomposition before calling Shannon or stop outer work while it
runs. Use the stateless verifier for coherent outer batches; delegate a named local obligation when persistent exact-state interaction would help.

Shannon submissions are nonblocking. While a job runs, continue genuinely independent decomposition,
later games or helpers, or an unrelated proof. You may use both Shannon lanes while continuing coarse work.
Do not edit a running job's lemma, statement, or preceding dependencies. Interleave freely; wait only when your next step depends on a job.

## Coarse development verifier

Write coherent proof batches and run:

```sh
.venv/bin/python experiments/interleaved_shannon/verify_task.py --check
```

This stateless replay permits temporary `admit` shells in editable regions. On failure,
`easycrypt_error_output` contains the native error and `easycrypt_goal_output` contains all native open
goals immediately before the rejected command. This is not a persistent Shannon session or a
compiler-enriched view. Repair an understood parser, type, name, or simple tactic error directly; a verifier error alone does not require Shannon. If direct edits repeatedly return to the same semantic boundary, stop blind repair and choose a qualified Shannon handoff or redesign.

To inspect an earlier source boundary:

```sh
.venv/bin/python experiments/interleaved_shannon/verify_task.py --upto LINE[:COL]
```

This stops before the first command beginning at or beyond that location. `easycrypt_replay_outcome.status`
is `reached_upto`, `failed_before_upto`, or `completed_before_upto`. If replay fails earlier, the report
retains native last goals. Use `--upto` to inspect or bracket tactics already in the file; it does not
automatically find the longest accepted prefix. If `--check` already exposes the needed failure and goals, do not repeat `--upto` mechanically.

## Choose the Shannon handoff class

Maturity comes from machine-checked semantic progress, not time spent, tactic count, or a detailed prose plan.

- **Not ready:** the reduction, helper statement, required declarations, or
  local transformation is undefined. Continue decomposition yourself.
- **Scout:** a named, loadable helper and one coherent local uncertainty exist,
  but the route, invariant, meaningful accepted prefix, or exact blocker is
  still uncertain. Recommended initial scout timeout: 8–15 minutes.
- **Warm completion:** accepted work has crossed a semantic milestone that
  fixes the main route; the exact residual goals are known; required
  declarations exist; and finishing should stay inside the proof body.
  Recommended warm-completion timeout: 15–30 minutes.
- **Progressing continuation:** a continuation-capable checkpoint materially
  advanced the prefix, goals, invariant, or blocker while source stayed
  unchanged. Recommended continuation timeout: 15–30 minutes by default,
  30–60 after substantial progress, and 60–120 only with strong accepted
  evidence for the remaining route.

A prefix containing only boilerplate such as `proc` or `move=>` is not
automatically warm. A zero-prefix handoff remains a scout even if its strategy
note is excellent.

### Scout modes

Use one primary type and ask one bounded question:

| Type | Purpose and required handoff | Planning reference |
|---|---|---|
| Boundary | Test one proposed hop; give the exact claim, transformation, route, and supporting declarations. | 8–12 min |
| Invariant | Test/refine one loop, call, simulation, or up-to-bad invariant; give related variables, globals, and preservation facts. | 10–15 min |
| Binding | Resolve a known mathematical step's theorem/module/procedure binding or tactic form; give the native goal/error and attempted application. | 8–12 min |
| Prefix | Explore the first uncertain part of one plausible tactic route; give any accepted prefix and the next milestone. | 8–12 min |

For a strategy-informed scout, provide the named helper, one type and objective, proposed route or
invariant, exact local fragment, truthful maturity evidence, exact anchors, prior attempts, and expected
result. Use `empty`, `unknown`, or `n/a` rather than inventing proof-state facts. If it returns no prefix,
narrower goal, or concrete discovery, redesign instead of blindly extending it.

The accepted prefix and residual goals may be established by `--check`,
`--upto`, or manager-owned handoff preparation; manual `--upto` replay is
not mandatory.

Resume only after material progress. Elapsed time alone is not progress.

## Submit and hand off

A cold scout is allowed only when the helper source itself fully states one
bounded question and no strategy note, anchors, or alternate candidate are
needed:

```sh
.venv/bin/python experiments/interleaved_shannon/shannon_jobs.py submit \
  --lemma <NAME> --timeout-minutes <MINUTES>
```

Otherwise transfer the current candidate and guidance:

```sh
.venv/bin/python experiments/interleaved_shannon/shannon_jobs.py submit \
  --lemma <NAME> --handoff-current \
  --strategy-note {{RUN_DIR}}/handoff_<NAME>.md \
  --timeout-minutes <MINUTES>
```

`--handoff-current` transports the candidate; manager preparation certifies its replayed prefix and open
boundary, not its unaccepted remainder. It does not classify maturity; always state `Scout` or `Warm completion` explicitly in the strategy note. Add `--resource-anchors <PATH>` for known declarations
or `--candidate-source <PATH>` for an alternate allowed candidate. These
options require `--handoff-current`. Notes and anchors must be in the current run; a candidate may also come from its disclosed continuation.

Use this concise strategy-note schema:

```text
Target and handoff class:
Scout type/objective, if applicable:
Maturity evidence and machine-checked prefix:
First rejected/next tactic and residual goal:
Intended route or invariant:
Resource anchors, attempts, and blockers:
Freedom granted to Shannon:
Expected useful result:
```

Put exact known declarations in a resource-anchor JSON file rather than prose:

```json
[{"symbol":"CCA_UFCMA.dec_enc","intended_use":"call",
  "role":"encryption correctness for this hop"}]
```

At most eight anchors are allowed. Intended uses are `apply`, `call`,
`exact`, `rewrite`, `smt`, and `reference`. Never guess a symbol.

## Schedule, resume, and collect

The scheduler provides two Shannon lanes; later jobs queue automatically. Run at most one immature scout;
prefer the other lane for mature work. Do not background scheduler commands manually.

```sh
.venv/bin/python experiments/interleaved_shannon/shannon_jobs.py status
.venv/bin/python experiments/interleaved_shannon/shannon_jobs.py wait --after-sequence <CURSOR> --timeout-seconds 30
.venv/bin/python experiments/interleaved_shannon/shannon_jobs.py cancel --job-id <JOB_ID>
```

Use `status`'s `terminal_cursor` as `<CURSOR>`; wait only when your next step depends on the job. For a running job, manager-confirmed `live_progress` reports `accepted_tactic_count`, `checkpoint_tactic_count`, `inner_turns`, and `last_progress_at`. Check at natural work boundaries or before depending on the result: accepted/checkpoint growth is proof progress, while turn growth alone is only activity. Do not poll continuously or cancel solely because a suggested duration elapsed; use handoff maturity and observed progress. Interpret results:

- `verified`: collect unless your own proof already verifies.
- `incomplete` or `cancelled`: `accepted_prefix` is the longest
  manager-derived prefix. A manager-owned `checkpoint`, when present, is
  resumable and may lag it by `uncheckpointed_tail_tactics`; without one, use
  `verify_task.py --check` or a fresh warm handoff, not `--resume-job`. Replay
  returned proof text through `--check` before reuse. Treat untrusted
  `agent_guidance.blockers`, `agent_guidance.discoveries`, and bounded
  `source_breadcrumbs` as guidance, not proof-state authority.
- `infrastructure_invalid`: repair or retry the public harness error; it is
  not evidence about the proof. A valid `progress` checkpoint may still be
  resumed.

If `checkpoint.continuation_available`, resume an unchanged, materially progressing checkpoint with:

```sh
.venv/bin/python experiments/interleaved_shannon/shannon_jobs.py submit \
  --lemma <NAME> --resume-job <JOB_ID> \
  --continuation-note <PATH> --timeout-minutes <MINUTES>
```

Omit `--continuation-note` when there is no new guidance. Otherwise redesign
or make a fresh handoff rather than blindly repeating a stalled checkpoint. If
`uncheckpointed_tail_tactics` is nonzero, note the useful accepted tail so
Shannon can re-submit it after resume.

```sh
.venv/bin/python experiments/interleaved_shannon/shannon_jobs.py collect --job-id <JOB_ID>
```

Only `collect` merges a verified result, rejects source drift, and rechecks
the file. Collect same-snapshot results in reverse source order. Before
finishing, resolve all jobs you intend to use and leave none running or queued.

## Runtime boundary, autonomy, and finish

The runner fixes Shannon's agent, `--eval-mode`, source projection, and capacity. There is no per-job model
or provider setting. Do not bypass the scheduler, build another harness, launch another proof agent, or
read backend private data such as `manager_prepare`, `attempts.json`, raw sessions, sockets, or tokens.

Work independently through failed tactics and bad decompositions. Revise,
split, combine, cancel, retry with justification, or fall back to a direct
EasyCrypt proof. If an assumption is wrong, figure out a sound replacement.
Do not wait for human clarification or finish with only a blocker report.

Modify only the scratchpad and `conclusion` proof body. Temporary `admit` is development-only; final
editable regions may not contain `admit`, `axiom`, `pragma`, `exit`, `abort`, or `require`. Do not modify
infrastructure, `workflow/`, `core/`, `tools/`, or `easycrypt-src/`. Read only the three task files,
`easycrypt-src/theories`, fixed Shannon infrastructure, and public same-run artifacts. Do not read history,
other worktrees, excluded or answer-bearing sources, related implementations, caches, or the web. Do not
use ambient EasyCrypt, opam, `session_cli.py`, raw session interfaces, `source_projection.py`,
`workflow.orchestrator`, or `run_shannon.py`.

Keep `{{RUN_DIR}}/notes.md` concise: proved facts, next work, useful jobs, and
abandoned routes. You have the fixed 12-hour task budget. Treat it as a work
budget, not merely an upper bound; do not exit early while safe proof work
remains.

{{CONTINUATION_CONTEXT}}

Before finishing:

```sh
.venv/bin/python experiments/interleaved_shannon/verify_task.py --final
```

Success requires exit code zero. A failed final verification is feedback:
continue proof work and run final verification again. Do not stop at an
outline, unchecked proof, or personal estimate that time expired.
