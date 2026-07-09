# Eval Interface Ladder

The evaluation ladder measures ShannonProver's central claim, not a long
shopping list of individual tools.  The claim is that proof-state compilation
turns raw verifier terrain into a cumulative agent-facing surface: a current
goal projection, a semantic proof-state IR, flow-sensitive navigation, and a
verifier-checked action surface.

## Travel Model

An EasyCrypt proof attempt is a trip from the lemma statement to a replayed
`qed`.  EasyCrypt is the terrain and the traffic authority: it decides which
roads really exist.  The prover agent is the traveler.  The proof-state
compiler is the map stack that makes the terrain actionable without turning
into an answer oracle.

| Profile | Travel analogy | Prover surface |
|---|---|---|
| `l1_goal_projection` | A location snapshot and the last stumble report, but no road system. | L1 Goal-State Projection: `current_goal`, `proof_status`, and `last_result` only. |
| `l2_semantic_ir` | Road signs: bridge ahead, call frontier, local closure lane. | L2 Semantic Proof-State IR: proof layer, program frontier, live handles, diagnostics, and basic inspect topics. |
| `l3_flow_navigation` | Turn-by-turn navigation and on/off-ramp warnings. | L3 Flow-Sensitive Navigation: route hypotheses, phase doors, liveness/cost warnings, and structural transitions. |
| `l4_checked_action_surface` | Navigation plus a checked driving simulator and road-health warnings. | L4 Verifier-Checked Action Surface: non-mutating probes, post-probe goals, call-site and seq-cut evidence, route health, recovery signals, and selected diagnostics. |

Diagnostic profiles remain available for engineering analysis but are not
headline ladder levels: `l4_preview_diagnostic` is the old preview-only
intermediate profile, while `diagnostic_full_surface` measures unrestricted
interface behavior. Tree/search driver behavior is a separate orchestrator
dimension.

The highway metaphor is proof-layer preservation.  Highways are high-level
resources such as Pr bridges, module equivalences, call lemmas, oracle handles,
and invariant skeletons.  Dirt roads are low-level proof work such as broad
`inline *`, early `wp`, or premature `smt()`.  Sometimes the proof must leave
the highway, but leaving too early can destroy exactly the handles that made a
short proof possible.

## Compiler Analogy

The evaluation ladder mirrors a traditional compiler pipeline:

| Compiler idea | ShannonProver analogue | Profile |
|---|---|---|
| AST / current-state projection | active goal, open goals, last transition | `l1_goal_projection` |
| typed IR and symbol table | proof layer, resolved handles, tactic forms, local obligations | `l2_semantic_ir` |
| control-flow, data-flow, liveness | program frontier, live bridge/call/oracle handles, phase doors | `l3_flow_navigation` |
| checked local-action evidence | non-mutating verifier probes, post-probe goals, call-site/seq-cut surfaces, route health, recovery labels | `l4_checked_action_surface` |

The compiler does not compile proofs into trusted code.  It compiles proof
states into decisions.  EasyCrypt remains the only component that accepts
tactics and replayed proof scripts.

## Main Measurements

Reports should connect each surface to the failure mode it is meant to
reduce.  Keep the headline table compact; put the full metric JSON and
timeline notes in the run artifact.

| Surface | Failure mode | Metrics |
|---|---|---|
| L2 semantic IR | semantic mislocalization | wrong-object attempts, signature lookup churn, failed named-lemma attempts |
| L3 flow navigation | unconscious lowering | early `inline *`, early `wp`/`smt`, live-handle loss, time to first structural progress |
| L4 checked actions | bad commits and stuck recovery | failed committed tactics, undo count, accepted-probe-to-commit rate, time from failure to next accepted step |

The L4 surface now includes three explicit recovery/evidence panels.  The
`call_site_surface` separates live frontier handles from handles that are
directly callable after binding, records tail-blocked named calls, and exposes
wrapper/frontier facts without turning them into a proof script. It also
records one-sided call certificate evidence, such as visible Hoare/Phoare
handles, losslessness handles, and direct one-sided call shape failures, so the
agent can distinguish certificate packaging facts from route recovery. The
`seq_cut_surface` records the current seq-cut scope and post-probe obligation
shape.  `structural_checkpoints` exposes semantic rewind points, including
seq-local and branch-local boundaries, so a bad branch step does not force a
restart from the lemma head.
`pure_tail_surface` covers the proof-state after program-frontier work has
turned into pure logic: it records sampling side conditions, finite-map update
and projection structure, membership decomposition sources, existential
witness candidates, finite-map lookup key cases, ambient memory-decoration
facts, and visible map/list alignment gaps. `recovery_diagnosis_surface`
classifies the scale of the current recovery evidence: boundary repair,
call-frontier recovery, seq-midpoint repair, local pure-tail surgery, residual
program surgery, or ambiguous recovery. This lets timeline reports separate
productive local surgery from real structural rewinds without turning the
surface into a proof script.

### Metric Tiers

Use three tiers so reports can stay small while the artifact remains useful:

| Tier | Metric family | Examples |
|---|---|---|
| Main result | verifier outcome and cost | solved/verified, wall time, thinking tokens, manager turns, accepted commits, final proof length |
| Mechanism | compiler-surface effect | destructive lowering count, failed committed tactics, probe acceptance, accepted-probe-to-commit rate, blind retry spikes |
| Manual annotation | semantic quality | wrong semantic object, live-handle loss, bad invariant commit, diagnostic follow-through, strategic-vs-mechanical time |

The current automatic extractor supports the first two tiers from ordinary run
artifacts.  Manual annotation slots are emitted as explicit `null` fields so
case studies can fill them without changing the schema.

Reasoning effort is reported separately from wall time.  Wall time is the
traveler's clock: it includes EasyCrypt, queueing, backend calls, and waiting.
Thinking tokens are the traveler's mental mileage: how much internal search
the agent spent deciding where to go.  When the Claude trace exposes exact
thinking-token usage, the extractor records it as `thinking_tokens_exact` and
uses that as `thinking_tokens`.  If the trace only contains thinking text, the
extractor records `thinking_chars`, computes `thinking_token_estimate` with
`ceil(chars / 4)`, and uses that estimate as `thinking_tokens`.  Reports
should call this a proxy unless `thinking_token_source` is `usage_field`.

Recommended headline columns:

| Column | Why |
|---|---|
| `Solved` | the hard verifier outcome |
| `Time` | practical proof-construction cost |
| `Thinking tokens` | reasoning effort and internal search pressure |
| `Turns` | interaction efficiency |
| `Failed commits` | preview/interface waste |
| `Destructive lowering` | navigator/liveness failure |
| `Blind spikes` | diagnostic/recovery failure |

For lemma-type analysis, group targets by proof shape:

| Lemma type | Expected strongest surface | Metrics to emphasize |
|---|---|---|
| Pr bridge/algebra | L2 and L3 | wrong object, bridge latency, destructive lowering |
| pRHL call frontier | L3 and L4 | live-handle loss, failed calls, call-subgoal preview use |
| loop invariant | L4 | bad invariant commits, failure-to-next-accept latency |
| oracle equivalence | L2 and L3 | handle preservation, wrong-layer spikes |
| local SMT residue | smaller benefit expected | overhead, proof length |
| large reduction | L4 plus tree/resume driver | solved count, best prefix, timeout rate |

## Code Entry Points

- `workflow.surface_profiles` defines the supported profile registry and the
  ProverWorkspaceView filters.
- `workflow.orchestrator --surface-profile PROFILE` applies a profile to a
  normal eval-mode proof run.
- `python3 -m eval_suite.run --suite eval_suite/suites/chacha_step4_1_l1_l4.json
  --dry-run` expands the current L1-vs-L4 interface-ladder suite without
  launching provers; `--profiles` and `--targets` select a subset.  Non-dry
  runs write `eval_metrics.json` and `eval_metrics.md` under each suite output
  directory.
- `python3 -m eval_suite.run --suite eval_suite/suites/demo_pir.json` runs a
  small single-target demo (`PIR_correct` under `l4_checked_action_surface`);
  use it to check the ladder machinery before spending budget on larger
  crypto targets.
- `python3 -m eval_suite.metrics RUN_DIR ...` extracts or refreshes metrics
  from existing run directories.  It reads `iteration_*/session_id.txt` and,
  for new race/tree runs, `iteration_*/agent_session_ids.json`, then looks up
  the corresponding Claude JSONL traces to populate `agent_trace`.

The suite runner isolates target sources by default.  For each profile/repeat
it copies the target source, optionally copies a target-specific `copy_root`
directory for local dependencies, and rewrites the target proof block to a
minimal admitted body before launching the prover.  This keeps the experiment
from becoming a relay race where one profile leaves the proof solved for the
next profile, and it removes target proof-body hints from the copied source.

The main Markdown table reports `thinking_tokens`, not total trace tokens.
The `agent_trace` JSON block still contains fresh `input_tokens`,
`output_tokens`, cache-token counters, `effective_input_tokens`, and
`total_tokens` for audit and budget planning, but those are context-throughput
figures rather than the headline reasoning-effort metric.  For tree or racing
runs, new artifacts record every worker session so reasoning effort can be
summed across all travelers, not only the winner.

Use canonical surface profile names on the command line.  Tree topology is a
separate setting: use the orchestrator's `--prover-mode` flag and the
suite-level `tree_initial_provers` / `tree_max_concurrent` defaults, not a
surface-profile suffix.
