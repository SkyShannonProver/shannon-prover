# Project: Shannon Prover

Event-driven EasyCrypt proof-agent pipeline using managed proof sessions,
structured workspace views, workflow orchestration, replay/audit validation,
and the Knowledge Base.

## Scope Restriction

- Do NOT write files outside this directory.
- Do NOT fetch proof scripts or solutions for eval lemmas from the internet
  (the eval corpus originates from public EasyCrypt developments; fetching
  them defeats eval-mode blinding).

## Current Prover Boundary

The current architecture is manager-owned. The full process topology:

```text
orchestrator (workflow/orchestrator.py, one process)
  -> agents/prover.run (in-process launch coordination)
    -> tree.supervisor.NodeSupervisor (spawn/poll/respawn of nodes)
      -> managed_prover_worker (one SUBPROCESS per tree node)
        -> ProofNodeRuntime -> ProofNodeManager -> ReplSessionManager
                                                -> WorkspaceViewManager (core)
agent <- one ProverWorkspaceView (rendered followup per turn)
```

The orchestrator owns proof-search strategy and tree topology; it never
holds a manager handle itself. The ProofNodeManager is the only manager
visible to the agent-facing runtime. ReplSessionManager owns EasyCrypt
lifecycle and mutation. WorkspaceViewManager (in core/) projects completed
snapshots into the agent-facing `ProverWorkspaceView`.

The agent does not manage session directories, node ids, goal hashes, view
hashes, request ids, or raw EasyCrypt lifecycle.

## Agent-Facing Interaction

The prover-agent protocol is generated at runtime from the current surface
profile, MCP tool schema, and manager workspace view. Do not maintain a static
intent or topic menu in this file.

Each managed prover turn should still have the same boundary:

- the agent reads the latest `ProverWorkspaceView`
- the agent sends one proof-level JSON intent through the manager-owned
  transport
- the manager owns session mutation, metadata binding, repair prompts, and view
  refresh

Use runtime-generated MCP metadata and the current workspace view as the
authoritative source for allowed intents, context topics, and payload shapes.

## Session CLI Policy

`core/easycrypt/session_cli.py` is retained for backend/human debugging and for
manager internals. It is not the agent-facing protocol. If a prover agent calls
it directly, record `session_cli.agent_call_debug_signal`; that means the
framework boundary leaked or the view was insufficient.

## EasyCrypt Environment

EasyCrypt is installed via opam. The switch name is configured in
`core/easycrypt/ec_env.py` (default: `easycrypt`).

For human/backend debugging:

```bash
eval "$(opam env --switch=easycrypt)"
```

When running EasyCrypt/session backend commands in sandboxed environments,
disable the OS sandbox or request escalation as required. The OS sandbox blocks
the `nice()` syscall, which prevents `why3server` from starting; without this,
`smt()` can fail with "cannot start & connect to why3server".

## Backend Debug Tools

Backend/human debug tools still exist behind the manager:

| Need | Tool |
|---|---|
| Workspace panel | `-agent-view` |
| Goal parser/details | `-goal-info` |
| Latest failure diagnosis | `-diagnose` |
| Exact symbol lookup | `-where NAME` |
| Tactic forms | `-tactic-forms NAME` |
| Alignment | `-align` |
| Subgoal gaps | `-subgoal-gap` |
| Bridge candidates | `-bridge-lemmas` |
| Invariant extraction | `-inv-from-lemma LEMMA` |

Expose these through runtime-generated manager context topics or exact
`lookup_symbol` requests when the active protocol advertises them.

## Run Reports (post-run timeline/proof bundle)

To review what a prover run did, the canonical, committable artifact is the
**bundle**:

```bash
python3 -m workflow.validation.run_report_bundle <run_iteration_dir> \
    --timestamp <TS> [--lemma L --model M --profile P ...]
```

It writes `agent_view_runs/<lemma>/<TS>__<commit>/` containing: the per-step
agent-view timeline table (each row clickable to that turn's `ProverWorkspaceView`
**and** to the agent's per-step reasoning), the reconstructed committed proof
(`## Agent's committed proof`), an environment header, copied views/thinking, and
portable relative links. `eval_suite.run` invokes it automatically post-run; run
it by hand if a run was killed before the hook fired.

`workflow/validation/agent_view_timeline_report` is only the bare table engine
that the bundle wraps — running it directly gives a partial table (no proof, env,
thinking, or portable links). Prefer the bundle.

The per-step reasoning comes from the prover's Claude session transcript (the run
artifacts deliberately never store thinking text); `agent_thinking_trace` joins it
back per turn. New runs record the prover `session_id` into
`node_memory/<tree>/agent_sessions.jsonl` so the transcript is found directly;
older runs fall back to a time-window + intent-sequence content match.

## `admit.` Policy Is Prover-Runtime

The `admit.` policy is a prover-runtime concern, not a rule for this coding
agent. The final proof must contain no committed `admit.` tactics: the manager
scans committed history and gates `qed.`/`finish` while any admit remains, and
the orchestrator rejects a final proof still containing `admit.`. Agent-facing
contract: the prover prompt (`workflow/agents/prover.py`).

## Lemma Lookup Discipline

Before applying or rewriting with a non-trivial external/clone/sibling lemma,
inspect its declaration. Agent-facing route: `lookup_symbol` for exact names;
use the runtime-advertised tactic-form context when tricky tactic syntax matters.

## Do NOT Read Other Session Directories

Never inspect sibling/stale `.ec_session_*` directories for tactics. In
manager-owned runs, rely on `ProverWorkspaceView` and semantic manager
requests. For backend debugging, read only the session you explicitly started.

## Eval Mode

When `[EVAL MODE ACTIVE]` is present or `EVAL_TARGET_LEMMA` is set:

- Do NOT read target-specific prior traces or proof-bank entries.
- Do NOT retrieve cached proofs or hints for the target lemma.
- Reading the target `.ec` file and sibling lemmas is OK.

## Testing

See `TESTING.md` for replay, regression, A/B, and long-run procedures.

## Key Directories

- `core/easycrypt/` — EasyCrypt backend, session runtime, views, analysis
- `workflow/` — orchestrator, tree/racing supervisor, agents, manager facade
- `workflow/validation/` — replay and audit validators
- `eval/` — local EasyCrypt benchmark corpus
