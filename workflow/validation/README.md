# Proof Replay and Session Events

This directory contains validation harnesses for replaying known proofs and
auditing the EasyCrypt session toolchain. The main entry point is
`proof_replay.py`.

## Why this exists

The prover used to infer proof progress primarily from human-facing text such
as `No more goals`, `[ALL_GOALS_CLOSED]`, and status lines. That is brittle:
EasyCrypt can print state before prompts, emit an extra prompt after `qed.`, or
print bookkeeping such as `+ added lemma` after the real close marker.

The current architecture treats the text stream as display output and records
proof state changes in an append-only structured event log. Agent-facing proof
interaction goes through `ProofNodeManager`, which returns an authoritative
`ProverWorkspaceView`. In long-lived tree mode, Claude reaches the manager via
the structured `submit_proof_intent` MCP tool; shell scripts, runtime bridge
clients, and session CLI commands are backend/private transport, not the
agent-facing proof interface. Orchestrator code should prefer structured events
and manager summaries when deciding whether a proof candidate is closed,
verified, or failed.

`ProverWorkspaceView` remains current-state-only. Historical attempts,
failures, and recovery breadcrumbs are persisted in the current node's
`node_memory/...` files (`timeline.jsonl`, `attempts.jsonl`, `failures.jsonl`,
`latest_followup.md`, `proof_so_far.md`, and audit-only
`latest_workspace_view.json`). A compacted long-lived agent should recover from
`latest_followup.md` plus `proof_so_far.md`, without adding a history panel to
the view schema.

After a managed tree run, `agent_view_timeline_report.py` can turn those
per-node memory files into the Markdown table used for agent-facing view
review:

```bash
uv run python -m workflow.validation.agent_view_timeline_report \
  --run "12:57 step3=workflow/runs/2026-05-12_1257_step3/iteration_1" \
  --output tmp/step3_view_timeline.md \
  --json-output tmp/step3_view_timeline.json
```

The report generation is deterministic: action times, per-node agent think
durations, manager execution durations, intent summaries, decision-state
summaries, and `workspace_views/turn_NNN.json` links are read from node memory.
Durations use `ms` below one second and `s` otherwise. Each row uses the
decision view the agent saw before submitting the intent; turn `N` usually
links to `workspace_views/turn_(N-1).json`, while the first turn links to the
initial handoff when that artifact is available. The `质量判断` column is left
blank by default for human or LLM review; pass `--quality-file notes.json` to
inject curated judgments without changing the run artifacts.

### Agent View Analysis Workflow

Use this workflow after any managed prover run when evaluating whether the
agent-facing view is helping or confusing the prover. Keep the timeline table
deterministic, and put interpretation in a separate observations file.

Recommended artifact names:

```text
tmp/<lemma>_decision_view_timeline.md
tmp/<lemma>_decision_view_timeline.json
tmp/<lemma>_view_quality_notes.json
tmp/<lemma>_decision_view_timeline_annotated.md
tmp/<lemma>_decision_view_timeline_annotated.json
tmp/<lemma>_long_think_observations.md
```

1. Generate the deterministic decision-view timeline:

```bash
uv run python -m workflow.validation.agent_view_timeline_report \
  --run "<label>=workflow/runs/<run>/iteration_1" \
  --output tmp/<lemma>_decision_view_timeline.md \
  --json-output tmp/<lemma>_decision_view_timeline.json
```

For A/B or before/after comparisons, pass multiple `--run LABEL=PATH`
arguments in the same command.

2. Review rows as causal triples:

```text
Decision View -> Intent -> Result
```

Judge whether the view the agent saw before the action was sufficient for that
action. Do not judge from the result view alone; turn `N`'s result view is
usually turn `N+1`'s decision view.

3. Write `tmp/<lemma>_view_quality_notes.json` with row-id keys such as
`T0.0-9` or `<label>:T0.0-9`. Keep notes actionable:

```json
{
  "<label>:T0.0-9": "view gave call_site_options/call_subgoals/align; agent chose the right inspect route",
  "<label>:T0.1-7": "view supported call route, but call_subgoals was not salient enough before a long invariant probe"
}
```

4. Regenerate the annotated timeline:

```bash
uv run python -m workflow.validation.agent_view_timeline_report \
  --run "<label>=workflow/runs/<run>/iteration_1" \
  --quality-file tmp/<lemma>_view_quality_notes.json \
  --output tmp/<lemma>_decision_view_timeline_annotated.md \
  --json-output tmp/<lemma>_decision_view_timeline_annotated.json
```

5. Create `tmp/<lemma>_long_think_observations.md`. Start with rows whose
`Agent think` is above a threshold such as `60 s`. For each row, inspect:

- the decision view linked in the timeline
- the previous followup under `node_memory/<node>/followups/`
- the current manager result under `node_memory/<node>/manager_results/`
- `payload_audit.jsonl` for observable tool calls or legal node-memory reads

Current run artifacts do not contain Claude's private thinking text. Payload
audit records only an opaque thinking hash/size and coarse markers such as
whether the preceding thinking mentioned node memory, search, or a forbidden
session path. The observation file should therefore distinguish observed
behavior from inference. Prefer language such as "agent read
latest_workspace_view.json and then submitted ..." over claims about hidden
reasoning.

6. Add a health section to the observations file rather than to the table.
Useful metrics:

- accepted `commit_tactic` count per node
- per-node wall-clock commit pace
- aggregate sibling throughput
- commit pace by tactic type, such as `byequiv`, `proc`, `inline *`, `wp`,
  `call`, and `sp; if`

A rough healthy target for a useful prover node is about one accepted commit
per minute. Slightly slower can still be acceptable for large seq/call goals or
invariant synthesis. If commit pace is healthy but `Agent think` spikes before
probes, the bottleneck is probably route synthesis rather than manager/backend
execution.

7. End the observations file with concrete view-surface hypotheses, not broad
complaints. Examples:

- make `call_subgoals` more salient before long `call (_: Inv)` probes
- clarify when a symbol is an unfoldable definition rather than an SMT lemma
- surface valid tactic forms more strongly when pRHL residuals invite invalid
  `sp`/`if` shapes
- reduce repeated manager-note text only if it appears in the decision view or
  followup that the agent actually saw

Inspection tools read the latest EC state through `core/easycrypt/session_state.py`.
That module is the shared boundary for prompt scanning, active-goal extraction,
and closed-proof detection. New tools should use it instead of scanning
`current.out` directly.

## View comparison & audit tools

Four tools inspect the agent-facing `ProverWorkspaceView`. They are
**complementary, not redundant**: capture produces the views, the two
comparators check that the views are stable across versions (one textually, one
semantically), and the policy auditor checks a single version's views against
the panel rules. Pick the tool by the question you are answering.

| Tool | Role | When to use |
|---|---|---|
| `manager_view_replay replay` | **capture** | Drive the real `ProofNodeManager` with a canned proof-intent sequence (no live agent) and save the per-turn agent surface under `workspace_views/turn_*.json`. Run this once per version/commit you want to compare. |
| `manager_view_replay compare` | **textual compare** | Order-aware textual diff of two replay output dirs. Use to see *exactly what changed* in the rendered view between two captures. Respects panel/key order, ignores per-run/path noise, and flags `proof_diverged` when the goal differs at the same turn. |
| `prover_workspace_view_anchor` | **semantic anchor** | Order-insensitive check that panels, goal identity, checkpoints, and candidate move-heads **survive** across versions. This is the documented proof-manager refactor gate; pass `--ordered` to additionally report ordering differences at warning level. Use to gate a refactor, not to read a line-by-line diff. |
| `view_philosophy_audit` | **policy compliance** | Check that **one** version's views obey the panel-policy rules (framing/size/imperative-wording) from `core/easycrypt/panel_policy.py`. Use after changing how panels are rendered. |

`manager_view_replay` captures and textually compares; `prover_workspace_view_anchor`
asks the weaker, refactor-safe question "did the agent-facing meaning survive?";
`view_philosophy_audit` never compares two versions — its `audit_sequence`
checks run **within a single run** and judge that run's views against the policy.

The canonical replay output directory name is `workspace_views/` (per-turn files
`turn_*.json`). For the cross-commit A/B recipe, including the `-m` invocation
footgun, see the "Cross-commit view replay" section in
[`/TESTING.md`](../../TESTING.md).

## Event Log

Each session directory may contain:

```text
events.jsonl
```

Each line is a JSON object with this envelope:

| Field | Meaning |
|---|---|
| `schema_version` | Event schema version. Currently `1`. |
| `event_id` | UUID for deduplication and traceability. |
| `timestamp` | UTC ISO timestamp. |
| `session_id` | Stable session identifier; currently the resolved session directory. |
| `session_dir` | Resolved path to the session directory. |
| `source` | Event producer, normally `session_cli`. |
| `type` | Event type. |
| `payload` | Type-specific structured data. |

Important event types:

| Event | Emitted when | Key payload fields |
|---|---|---|
| `session.started` | `-start` initializes a session | `file`, `lemma`, `include_dirs`, `restart_count` |
| `session.loaded_context` | Context file is loaded into EC | `file`, `context_file`, `bytes`, `lines` |
| `tool.called` | Any `session_cli` action starts | `name`, `mutates_proof_state`, `session_dir` |
| `tool.result` | Any `session_cli` action exits | `name`, `exit_code`, `status`, `mutates_proof_state` |
| `tool.view.produced` | A read-only tool persists a ToolView artifact | `tool`, `schema_version`, `artifact`, `view_hash`, `proof_status`, `recommendation_count` |
| `agent.view.produced` | `-agent-view` or a post-commit snapshot persists an aggregate ProofContextView artifact | `schema_version`, `artifact`, `view_hash`, `proof_status`, `goal_hash`, `recommendation_count` |
| `prover.workspace_view.produced` | A ProverWorkspaceView IDE panel is persisted | `artifact`, `view_hash`, `proof_status`, `current_goal_text_fully_shown`, `workspace_chars` |
| `commit.response.produced` | A mutating command persists a structured CommitResponse artifact | `command`, `status`, `artifact`, `response_hash`, `attempted_count`, `accepted_count` |
| `tactic.execution.produced` | A backend tactic command persists TacticExecutionResult | `mode`, `command`, `status`, `artifact`, `accepted_count`, `workspace_artifact` |
| `command.summary.produced` | Historical compatibility summary artifact | `command`, `command_status`, `artifact`, `proof_status`, `goal_type`, `transition_kind`, `primary_action` |
| `episode.timeline.produced` | `-episode-view` persists an event-ordered proof episode timeline | `artifact`, `step_count`, `final_proof_status`, `final_primary_action` |
| `tactic.submitted` | A tactic is accepted for submission | `tactic`, `history_lines_before`, `line_count` |
| `diagnostic.emitted` | A hook emits a diagnostic block | `source`, `layer`, `text`; optional structured `recommendations`, `evidence`, `notes`, `errors` |
| `goal.changed` | A tactic changes or checks goal state | `goals_before`, `goals_after`, `candidate_closed` |
| `tactic.result` | A tactic finishes | `status`, `candidate_closed`, `has_new_error` |
| `proof.candidate_closed` | EC/session state says no goals remain | `tactic`, `goals_before`, `goals_after` |
| `verification.completed` | `-verify` finishes | `lemma`, `status`, `verifier`, `use_session_proof` |
| `tactic.undone` | `-prev` undoes a tactic | `status`, `undone_tactic`, `remaining_steps` |
| `error.raised` | A precheck/tool/hook error is captured | `phase`, `kind` or error summary |

The event logger is best-effort: failing to write `events.jsonl` must not break
proof execution. Acceptance logic should therefore treat events as a preferred
source of truth, while still keeping conservative fallbacks for old sessions.
For new prover/orchestrator sessions that do write `events.jsonl`, acceptance
is fail-closed: an event-contract error prevents proof acceptance.

## Event Contract

`core/easycrypt/session_events.py` owns the typed event schema and the replay
state-machine validator:

- `validate_event(...)` checks the event envelope and required/optional payload
  fields for every known event type.
- `validate_event_stream(...)` checks ordering and pairing invariants:
  `session.started` comes first, `tool.called` pairs with `tool.result`,
  `tactic.submitted` pairs with `tactic.result`, candidate closure follows a
  successful closing tactic, and passing verification follows a
  `proof.candidate_closed` event.

`proof_replay.py` writes the validator output into `audit_report.json` as
`event_contract`, `event_contract_errors`, and `event_contract_warnings`. A
clean replay should have zero consistency warnings and zero event-contract
issues.

## ToolView Contract

Read-only tools can additionally expose a prover-facing ToolView envelope:

```json
{
  "schema_version": 1,
  "tool": "goal-info",
  "ok": true,
  "proof_state": {},
  "guidance": { "recommendations": [] },
  "evidence": {
    "deterministic": [],
    "context": [],
    "kb": [],
    "retrieval": [],
    "probe": [],
    "event": [],
    "raw": []
  },
  "notes": [],
  "errors": [],
  "debug": {}
}
```

`proof_state` is authoritative. `guidance.recommendations` is advisory and
must be backed by `evidence`. Recommendations may carry producer-owned
`action_type` values: `runnable_tactic`, `inspection_action`, `strategy_hint`,
or `warning`. ProofContextView consumes those fields when building canonical
actions; ProverWorkspaceView renders them as neutral `candidate_moves` and
`inspect_lookup_handles`, while offline audit adapters adapt historical
buckets only at the reader boundary.

Migrated read-only tools write the full envelope under the session directory's
`tool_views/` subdirectory and emit a compact `tool.view.produced` event
carrying the artifact path and SHA-1 hash. The legacy stdout remains for prover
compatibility.

Current migrated ToolView producers include `status`, `goal-info`,
`goal-patterns`, `diagnose`, `align`, `subgoal-gap`, `suggest-close`,
`swap-search`, and `bridge-lemmas`. The replay harness validates
`tool.view.produced` artifacts first and falls back to legacy `goal-info`
stdout JSON only for older runs. It reports `tool_view_checked`,
`tool_view_errors`, and `tool_view_warnings` in `audit_report.json`.

Commit-time AUTO hooks use `diagnostic.emitted` rather than ToolView artifacts.
Migrated hooks include structured `recommendations` and `evidence` alongside
the existing `[AUTO-*]` text. The replay harness validates these payloads and
reports `structured_diagnostic_checked`, `structured_diagnostic_errors`, and
`structured_diagnostic_warnings`.

## ProofContextView Contract

The backend `-agent-view` command persists the aggregate proof-context state:

```json
{
  "schema_version": 1,
  "kind": "proof_context_view",
  "ok": true,
  "proof_state": {},
  "current_goal": {},
  "latest_transition": {},
  "guidance": {
    "recommendations": [],
    "stale_recommendations": [],
    "stale_recommendation_count": 0
  },
  "evidence": {},
  "proof_ir": {},
  "actions": [],
  "safe_next_actions": [],
  "latest_errors": [],
  "notes": [],
  "errors": [],
  "debug_refs": {}
}
```

Fresh context is deliberately stricter than ToolView guidance. A
recommendation is active only when it is tied to the current
`proof_state.goal.active_goal_hash`, to the latest tactic transition, or to a
read-only tool run after that latest transition. Older recommendations remain
in `guidance.stale_recommendations` for debugging, but they are not surfaced as
agent-facing commands. Workspace projection renders active context with neutral
field names such as `candidate_moves`, `inspect_lookup_handles`,
`application_context`, and `evidence`. The command writes full JSON artifacts under
`proof_context_views/` and emits `agent.view.produced`. It also writes the exact
stdout-facing `ProverWorkspaceView` under `prover_workspace_views/` and emits
`prover.workspace_view.produced`. Mutating backend commands also record
best-effort post-commit ProofContextView/ProverWorkspaceView snapshots so the
event stream contains a consistent view even when a managed run does not call
the backend aggregate command directly. Replay reports `agent_view_checked`,
`agent_view_errors`, and `agent_view_warnings`.

## ProverWorkspaceView Contract

`ProverWorkspaceView` is the only authoritative agent-facing workspace panel.
Its current surface is:

```json
{
  "schema_version": 2,
  "kind": "prover_workspace_view",
  "ok": true,
  "last_result": {},
  "proof_status": {},
  "current_goal": {},
  "program_frontier": {},
  "application_context": {},
  "facts_and_diagnostics": {},
  "candidate_moves": {},
  "inspect_lookup_handles": {}
}
```

`last_result` and `proof_status` should stay brief. `current_goal` is the
committed EasyCrypt state; read-only probe previews belong under
`last_result.probe_preview.goal_after_probe`.

The panel is current-state-only. Do not add history menus or long-running
attempt logs to `ProverWorkspaceView`: recent failures, attempted tactics, and
episode summaries belong in runtime/node memory files or replay artifacts, not
in the live IDE panel. A long-lived prover agent may read the current node's
curated `node_memory/...` files when it wants history, while proof-state
mutation and semantic proof inspection remain manager-owned.

Agent-facing views must not expose backend commands, `debug_cli_fallback`,
`session_cli.py`, `next_actions`, `suggested_next_steps`, `next_try`, or
imperative phrasing such as "Lookup first". `inspect_lookup_handles` must expose
semantic manager topics, not low-level wrappers or execution modes such as
`inspect_context` or `try`; declaration reads should appear as lookup
candidates. Replay audits both stdout and `prover.workspace_view.produced`
artifacts for those leaks.

## CommitResponse Contract

Mutating commands (`-next`, `-prev`, `-chain`) persist one structured response
artifact per invocation:

```json
{
  "schema_version": 1,
  "kind": "commit_response",
  "ok": true,
  "command": "chain",
  "status": "ok",
  "proof_state": {},
  "latest_transition": {},
  "mutation": {
    "attempted_count": 0,
    "accepted_count": 0,
    "attempted_tactics": [],
    "failed_tactic": "",
    "failure_reason": "",
    "keep_on_fail": false,
    "rollback_count": 0
  },
  "agent_view": {},
  "notes": [],
  "errors": [],
  "debug": {}
}
```

This is the command-level contract that prevents downstream consumers from
parsing `-chain` display text to learn what happened. The artifact links to the
post-command ProofContextView and records attempted tactics, accepted count,
failure reason, rollback count, and post-state projection. Replay validates
`commit.response.produced` hash/schema/counts and reports
`commit_response_checked`, `commit_response_errors`, and
`commit_response_warnings`.

Upper workflow acceptance uses `workflow.proof_acceptance`:

- `validate_candidate_event_contract(...)` is used by progress tracking and by
  the prover before it writes a candidate proof to the source file.
- `validate_acceptance_event_contract(...)` is used after offline verifier
  success and requires both candidate closure and a passing verification event.

## Acceptance Rule

`proof.candidate_closed` means the interactive proof candidate is structurally
closed. It is not enough to accept a proof.

Final acceptance still requires offline verification:

1. Replay/construct tactics in the session.
2. Validate the candidate event contract and observe `proof.candidate_closed`.
3. Run offline EasyCrypt verification.
4. Emit `verification.completed`.
5. Accept only if the final event contract validates and latest
   `verification.completed.status == "pass"`.

This prevents a session-only close marker, async SMT behavior, or accidental
`qed.` from being treated as a real proof.

## Proof Replay

Run the whole proof bank:

```bash
python3 -m workflow.validation.proof_replay \
  --audit-tools status,agent-view \
  --prover-ux-audit \
  --prover-behavior-audit \
  --write-prover-timeline \
  --artifact-root artifacts/replay/full-proof-bank \
  --timeout 300
```

Run one lemma with deeper tool auditing:

```bash
python3 -m workflow.validation.proof_replay \
  --lemma PIR_secure2 \
  --audit-tools status,agent-view,episode-view,goal-info,goal-patterns,align,subgoal-gap,suggest-close,diagnose \
  --audit-every 2 \
  --artifact-root artifacts/replay/pir-deep-audit \
  --timeout 240
```

The harness reads `workflow/proof_bank.jsonl`, starts a fresh session for each
entry, replays tactics one by one, optionally runs read-only tools at
checkpoints, then runs `-verify`.

## Behavior Audit

`prover_behavior_audit.py` is the reusable minitool for tool-usage and
interaction-shape metrics. It can read either a proof replay artifact root or a
single live EasyCrypt session directory:

```bash
python3 -m workflow.validation.prover_behavior_audit artifacts/replay --write
python3 -m workflow.validation.prover_behavior_audit .ec_session_some_run --write
```

The report is written as `prover_behavior_report.json` and includes:

| Field | Meaning |
|---|---|
| `tool_usage` | Total/read-only/mutating tool calls and result status counts by tool name. |
| `command_summary_metrics` | Primary-action, transition-kind, goal-type, tactic-status, and no-progress counts. |
| `guidance_follow_through` | Whether runnable tactics, inspect/strategy prompts, failed commands, and candidate-closed states were followed by the expected next interaction. |
| `repeated_read_only_tool_calls` | Repeated read-only calls on the same active goal hash, useful for spotting flailing or stale guidance loops. |
| `issues` | Fail-closed errors for impossible behavior such as candidate-closed without later verification, plus warnings for suspicious interaction patterns. |

For live Claude subagent experiments, run this after the prover finishes using
the `ec_session_dir` recorded in `ProverResult`.

By default the replay harness calls the `session_cli` command handlers
in-process. This keeps the same session files and structured events, while
avoiding a new Python interpreter for every tactic and audit tool. Use
`--subprocess` to force the legacy subprocess-per-action runner when comparing
behavior or debugging runner isolation.

In in-process mode, replay also defaults to the same fast hook setting used by
`session_cli -chain`: expensive guidance-only daemon probes inside commit-time
hooks are skipped, while the real tactic execution, state updates, audit tools,
and final `-verify` still run. Use `--full-hooks` when you specifically need
to compare interactive diagnostic output.

If a proof-bank entry lacks `qed.`, the harness appends a synthetic final
`qed.` during replay so the session is verified in the same shape as a normal
interactive proof.

## Artifact Layout

For each proof, the artifact directory contains:

| File | Contents |
|---|---|
| `commands.json` | Every `session_cli` command, return code, stdout/stderr, duration. |
| `events.jsonl` | Copied structured session event log. |
| `history.ec` | Accepted tactic history from the replay session. |
| `current.out` | Final EC current-state output. |
| `tool_views/*.json` | Copied ToolView artifacts produced by read-only tools. |
| `proof_context_views/*.json` | Copied ProofContextView artifacts produced by `-agent-view`. |
| `prover_workspace_views/*.json` | Copied exact agent-facing ProverWorkspaceView artifacts. |
| `commit_responses/*.json` | Copied CommitResponse artifacts produced by mutating commands. |
| `command_summaries/*.json` | Copied CommandSummary artifacts produced by mutating commands. |
| `episode_timelines/*.json` | Copied SessionEpisodeTimeline artifacts produced by `-episode-view`. |
| `step_*.stdout.txt` / `step_*.stderr.txt` | Per-tactic command output. |
| `tool_outputs/<step>/<tool>.*.txt` | Audit-tool output at checkpoints. |
| `audit_report.json` | Consistency checks over commands/events/verification. |
| `summary.json` | Compact proof result summary. |
| `review.md` | Human-readable replay review. |

The root artifact directory also receives a `summary.json` list across all
selected proofs.

Consumers should load replay artifacts through
`workflow.validation.replay_artifacts` rather than opening these JSON files
directly. The typed reader exposes `ReplaySummary`, `AuditReport`, and
`ReplayArtifact`, plus helpers for iterating a replay root and aggregating
pass/warning/event counts.

## Consistency Checks

`proof_replay.py` checks:

- `tactic.submitted` count matches replayed `-next` commands.
- `tactic.result` count matches submitted tactics.
- Submitted tactic text matches the actual session-submitted form after
  session-compatible normalization, such as `\!` to `!`.
- The event stream satisfies the typed schema and state-machine contract.
- Close markers in stdout imply at least one `proof.candidate_closed` event.
- `tactic.result(candidate_closed=true)` count matches
  `proof.candidate_closed` events.
- Passing replays have `verification.completed.status == "pass"`.
- `tool.view.produced` events point to readable ToolView artifacts whose hash,
  schema, tool name, `ok`, and recommendation counts match the event payload.
- `commit.response.produced` events point to readable CommitResponse artifacts
  whose hash, schema, command, status, and mutation counts match the event
  payload.
- `command.summary.produced` events point to readable CommandSummary artifacts
  whose hash, schema, proof status, timeline projection fields, recommendation
  counts, and primary action match the event payload.
- `episode.timeline.produced` events point to readable SessionEpisodeTimeline
  artifacts whose hash, schema, step count, final proof status, final primary
  action, note count, and error count match the event payload.
- Structured `diagnostic.emitted` payloads have well-formed recommendations
  and evidence buckets.

Warnings do not necessarily mean a proof failed, but they mean the toolchain
contract should be inspected before trusting aggregate results.

## Prover UX Audit

`prover_ux_audit.py` audits replay artifacts as if a prover agent consumed the
post-command `CommandSummary` after every mutating step:

```bash
python3 -m workflow.validation.prover_ux_audit \
  --artifact-root /tmp/proof-replay-artifacts
```

It checks that each step tells the prover whether the command succeeded, what
the current proof state is, and what the next action category is. It also
flags misleading views such as closed proofs that still expose tactics,
failed commands that do not point to diagnosis, placeholders in runnable
tactic buckets, missing links back to durable artifacts, and known false
positive guidance such as failure-event hints on `[=] 1%r` phoare goals. The
report is written to `prover_ux_report.json` under the replay artifact root.

`prover_episode_timeline.py` projects the same replay artifacts into an
episode-level timeline:

```bash
python3 -m workflow.validation.prover_episode_timeline \
  --artifact-root /tmp/proof-replay-artifacts
```

The timeline is ordered by `command.summary.produced` events, not by artifact
filename. It records each committed tactic, transition kind, goal-count change,
proof status, primary action, guidance counts, and prover-facing observations.
`proof_replay.py --write-prover-timeline` writes the same report to
`prover_episode_timelines.json`.

For backend/human debugging of a live session, `session_cli.py -episode-view`
emits the current session timeline, persists `episode_timelines/*.json`, and
records an `episode.timeline.produced` event. Managed agents ask the manager for
`inspect_context` with topic `episode_view`.

## Tool Output Expectations

Closed proofs should be explicit and non-suggestive:

- `-status`: reports `Proof COMPLETE` and `Goal type: complete`.
- `-goal-info`: reports `proof_candidate_closed: true` and no suggested tactics.
- `-goal-patterns`: reports that the proof is already complete.
- `-suggest-close`: reports that there are no goals to close.

Any closed-proof tool that suggests another tactic is a bug in the inspection
layer, not a proof obligation.
