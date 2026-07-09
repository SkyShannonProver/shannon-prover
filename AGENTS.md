# Project: Shannon Prover

Event-driven EasyCrypt proof-agent pipeline using managed proof sessions,
structured workspace views, workflow orchestration, replay/audit validation,
and the Knowledge Base.

## Scope Restriction

- Do NOT write files outside this directory.
- Do NOT fetch proof scripts or solutions for eval lemmas from the internet
  (the eval corpus originates from public EasyCrypt developments; fetching
  them defeats eval-mode blinding).

## Managed Prover Architecture

The current proof-agent boundary is manager-owned:

```text
orchestrator
  owns proof-search strategy and tree topology

ProofNodeManager
  the only manager visible to agent/orchestrator

  ReplSessionManager
    internal: EasyCrypt REPL/session lifecycle

  WorkspaceViewManager
    internal: ProofContextView -> ProverWorkspaceView projection

agent
  calls submit_proof_intent and sees one ProverWorkspaceView
  chooses proof-level intents only
```

Ownership rules:

- Orchestrator owns racing/tree policy: spawn, kill, stuck detection,
  capacity, winner selection.
- ProofNodeManager owns the agent turn boundary, metadata binding, view
  refresh, malformed-intent repair, and node health/progress events.
- ReplSessionManager is the only component that starts, checks, commits,
  undoes, restarts, or replays EasyCrypt sessions. Tree sibling creation is
  orchestrator-owned; a child node rebuilds state by replaying a verified
  prefix through its manager-owned session.
- WorkspaceViewManager only projects completed proof snapshots into
  `ProverWorkspaceView`; it does not execute tactics.
- Agent owns proof choices: which tactic to commit, which symbol to look up,
  and which context topic to inspect.

## Agent-Facing Protocol

The prover agent should feel like it is using an IDE. Each turn it receives:

- a short result or repair prompt from the manager
- the latest authoritative `ProverWorkspaceView`

The agent should read:

- `last_result` for the previous manager result, kept brief
- `proof_status` for the minimal lemma/status/view-focus/remaining-goal facts
- `current_goal.lines` for the exact EasyCrypt goal text
- `program_frontier` for visible program/call/frontier structure
- `application_context` for selected handles, requirements, anchors, and
  residual obligations relevant to the current route
- `facts_and_diagnostics` for available evidence, gaps, and recent failures
- `candidate_moves` for neutral proof options
- `call_site_surface`, when present, for L4 call-site facts: live call sites,
  named handles, directly callable handles, frontier-live handles that still
  need binding, frontier blockers, wrapper depth, one-sided call certificate
  evidence, and preview effects
- `seq_cut_surface`, when present, for L4 seq-cut facts: the current seq scope,
  obligation shape, branch focus, and residual frontier after a checked cut
- `pure_tail_surface`, when present, for L4 pure-tail facts after program
  frontier work: sampling side conditions, map-update/projection structure,
  membership decomposition sources, existential witness candidates,
  map-update lookup cases, memory-decoration translation, and visible
  alignment gaps
- `frame_obligation_ledger`, when present, for L4 frame-retention facts:
  frame equalities visible in required context, structural boundary assertions
  that carry them, and reversible boundaries related to possibly dropped facts
  only when those facts are visible in current local goal evidence
- `recovery_diagnosis_surface`, when present, for L4 recovery classification:
  whether the current evidence looks like a boundary repair, call-frontier
  recovery, seq-midpoint repair, local pure-tail surgery, residual program
  surgery, or an ambiguous recovery point
- `structural_checkpoints`, when present, for L4 recovery facts: semantic
  checkpoints such as `before_seq_cut`, `after_seq_opened`,
  `before_branch_work`, `before_call_route`, `after_call_opened`,
  `before_call_obligation_work`, `last_call_site_boundary`, and
  `restore_before_last_rewind`
- `route_replay_memory`, when present, for L4 recovery after checkpoint rewind:
  old discarded route chunks that can be checked in a scratch verifier session
  before any replay commit
- `inspect_lookup_handles` for semantic inspect or lookup requests

`candidate_moves` is information, not an imperative plan. Read
`applicability`, `effect`, `limitations`, and `use_when` before acting. When
`candidate_moves.structural_transitions` is the current-state menu of
reversible proof-phase entrances, such as a checked `wp.` transition that
enters a real post-wp surgery workbench, use one only when its phase is the
phase you want to enter.
If `candidate_moves.route_health` is present, it is the manager's current
route diagnosis for this view only. It may recommend inspect/checkpoint
rewind actions, and may list context lookups under `useful_inspections`. It is
advisory: it can say "a previous boundary may need to be revisited", and may
show a boundary-vs-residual concept diff, but it does not decide how to
strengthen the invariant and is not a proof script or history panel. Route
health entries may include a `recovery_class` and `checkpoint_policy`. Treat
boundary/call-frontier/seq-midpoint classes as evidence that a reversible
boundary is relevant. Treat local pure-tail and residual-program classes as
evidence that current-state local work is still available unless a separate
checked failure shows the boundary itself is too weak.
`call_site_surface` is also evidence, not a proof plan. In that panel,
`frontier_live_named_handles` means a named handle is visibly attached to the
current frontier, while `callable_now` means the handle has enough checked
binding information to be a direct current-call candidate. If a call-site entry
shows `named_call_templates`, treat the displayed tactic shape as current-state
evidence and inspect the relevant context before committing.
When `call_site_surface.one_sided_call_surface` is present, it reports a
one-sided live call frontier plus visible Hoare, Phoare, losslessness, or recent
direct-call shape-failure evidence. It may show generic certificate shapes such
as `phoare[PROC : PRE ==> POST] = 1%r` or an anonymous one-sided call spec, but
these are proof-term shape evidence only. It does not choose the pre/post
formula, the losslessness lemma, or whether to package a Hoare fact before an
`ecall`.
`seq_cut_surface` and `structural_checkpoints` describe reversible proof
boundaries. Prefer seq-local, branch-local, or call-local checkpoints when
repairing work inside an opened seq cut or call obligation; a full
`fresh_restart` still requires explicit confirmation.
`pure_tail_surface` is evidence for pure logical residuals after program
actions disappear from the current goal. It may report map/projection/list
alignment facts, membership source cases, existential witness sources, and
map-update lookup cases. It may link a reversible boundary, but it is not a
proof plan and does not select a destructor, witness, rewrite, or SMT lemma.
`frame_obligation_ledger` is evidence about whether frame facts such as
`={glob A}` remain visible across structural boundaries. It does not decide a
replacement invariant or midpoint assertion.
`recovery_diagnosis_surface` is evidence for estimating the scale of recovery.
`boundary_repair_evidence`, `call_frontier_recovery_evidence`, and
`seq_midpoint_repair_evidence` identify structural facts linked to local
checkpoints. `local_pure_surgery_available` and
`residual_program_surgery_available` identify current-state proof work and
list visible local resources. The surface links checkpoints as recovery
references; it does not select a tactic, witness, rewrite, invariant, or cut
formula.
`route_replay_memory` is evidence about old verified suffix chunks saved before
a checkpoint rewind. Use replay chunks only when that replay intent is
profile-visible; commit a chunk only when replaying that chunk matches the
current route.
`inspect_lookup_handles` should contain concrete semantic topics such as
`goal_info`, `call_subgoals`, or `tactic_forms`; protocol wrappers such as
`inspect_context` and backend labels such as `try` are not agent-facing
topics.

The long-lived prover agent submits exactly one JSON proof intent through the
manager-owned transport. In the current runtime this transport is the
per-node `submit_proof_intent` MCP tool; the proof-intent JSON shape is:

```json
{"intent": "commit_tactic", "payload": {"tactic": "byequiv=>//."}}
```

Allowed intents:

```json
{"intent": "commit_tactic", "payload": {"tactic": "TAC."}}
{"intent": "commit_replay_suffix_chunk", "payload": {"chunk_id": "CHUNK_ID_FROM_VIEW"}}
{"intent": "goal_info", "payload": {}}
{"intent": "operator_lemmas", "payload": {"operator": "OPERATOR_OR_TERM_SKELETON"}}
{"intent": "tactic_forms", "payload": {"name": "TACTIC_NAME"}}
{"intent": "call_subgoals", "payload": {"invariant": "CALL_INVARIANT"}}
{"intent": "lookup_symbol", "payload": {"symbol": "LEMMA_NAME"}}
{"intent": "undo_last_step", "payload": {}}
{"intent": "undo_to_checkpoint", "payload": {}}
{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "CHECKPOINT_ID_FROM_MENU"}}
{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "CHECKPOINT_ID_FROM_MENU", "confirm": true, "confirmation_id": "CONFIRMATION_ID_FROM_MENU"}}
{"intent": "undo_to_checkpoint", "payload": {"restore_id": "RESTORE_ID_FROM_MENU"}}
{"intent": "fresh_restart", "payload": {}}
{"intent": "fresh_restart", "payload": {"confirm": true, "confirmation_id": "CONFIRMATION_ID_FROM_MENU"}}
{"intent": "finish", "payload": {}}
```

Use `undo_last_step` for a one-step repair. Use `undo_to_checkpoint` with an
empty payload when you want the manager to show committed tactics you can
rewind before; copy a `submit` object from that menu instead of inventing a
checkpoint id. Some checkpoint rewinds that leave the current call obligation
scope require a confirmation payload from the manager. After a checkpoint
rewind, the menu may include a restore option for the proof state saved before
that rewind. If `route_replay_memory` exposes an old suffix chunk and the
profile exposes replay intents, use `commit_replay_suffix_chunk` only when
replaying that chunk matches the current route. Use `fresh_restart` with an
empty payload only when you intend to erase this node's entire committed branch;
the manager will ask for
confirmation before doing so.

The agent does not provide `node_id`, `view_hash`, `goal_hash`,
`state_version`, `request_id`, or a separate `reason`; the manager and audit
layer record those automatically.

Do not use Bash, `session_cli.py`, runtime bridge clients, sockets, tokens, MCP
config files, or submit scripts to interact with proof state. Those are
backend/private transport. If the agent needs more context after a bounded MCP
tool result, it may read only the current node's legal `node_memory/...` files
advertised in the runtime prompt, primarily `latest_followup.md` for the latest
agent-readable surface and `proof_so_far.md` for the accepted tactic spine. The
raw workspace-view JSON files are audit/replay data, not the normal recovery
surface for proof work.

Useful context topic intents include `goal_info`, `diagnose`, `episode_view`,
`proof_frontier`, `align`, `subgoal_gap`, `lemma_hints`, `pr_bridge_routes`
(verified Pr bridge routes), `equiv_bridge_lemmas` (context-only equiv bridge
lemma names), `inv_from_lemma`, `operator_lemmas`, `call_subgoals`, and
`tactic_forms`. The legacy `inspect_context` wrapper is accepted only for
replay/back-compat; it is not an agent-facing topic.

If an agent message is malformed, the manager returns the same latest
workspace view plus a short repair prompt. Repeated malformed messages become
`agent_protocol_stuck`, leaving the orchestrator to decide whether to kill or
spawn siblings.

## Session CLI Policy

`core/easycrypt/session_cli.py` remains a backend and human-debug tool. It
should not appear as the agent-facing protocol in prompts or workspace views.

Agent-side `session_cli` calls are treated as a node-fatal debug signal:

- audit code: `session_cli.agent_call_debug_signal`
- interpretation: framework boundary leaked, or the view did not provide
  enough information

Do not try to hide this by telling the agent "never call session_cli". If it
happens, the audit signal is useful.

## EasyCrypt Environment

EasyCrypt is installed via opam. The switch name is configured in
`core/easycrypt/ec_env.py` (default: `easycrypt`).

For human/backend debugging, run:

```bash
eval "$(opam env --switch=easycrypt)"
```

When running EasyCrypt or `session_cli.py` in a sandboxed environment, disable
the OS sandbox / request escalation as required by the current runner. The OS
sandbox blocks the `nice()` syscall, which prevents `why3server` from
starting; without this, `smt()` can fail with "cannot start & connect to
why3server".

## Backend Debug Cheat Sheet

Use these only as developer/human tools or inside manager code:

| Need | Backend tool |
|---|---|
| Current IDE panel | `-agent-view` |
| Parse current goal | `-goal-info` |
| Diagnose latest failure | `-diagnose` |
| Symbol declaration/body | `-where NAME` |
| Theory/clone members | `-members SCOPE` |
| Clone declarations | `-clones` |
| Name regex search | `-search REGEX` |
| AST/operator search | `-search-skeleton QUERY` |
| Tactic forms | `-tactic-forms NAME` |
| Program alignment | `-align` |
| Subgoal gap analysis | `-subgoal-gap` |
| Bridge candidates | `-bridge-lemmas` |
| Invariant from equiv lemma | `-inv-from-lemma LEMMA` |

For agent-facing runs, expose these through direct context topic intents or
`lookup_symbol`, not as shell commands.

## `admit.` Policy Is Prover-Runtime

The `admit.` policy is a prover-runtime concern, not a rule for the coding agent.
The manager scans the committed proof and gates `qed.`/`finish` while any
committed `admit.` remains; the orchestrator rejects any final proof still
containing `admit.`. The agent-facing contract lives in the prover prompt
(`workflow/agents/prover.py`).

## Lemma Lookup Discipline

Before proposing `apply LEMMA`, `have := LEMMA ...`, `rewrite LEMMA`, or
`call LEMMA` on a non-trivial external/clone/sibling lemma, inspect its
declaration first. Agent-facing route: use `lookup_symbol` for exact names or
the direct `tactic_forms` context topic for tricky tactic forms.

Rule of thumb: if a lemma application fails once with unknown identifier,
arity, or unification trouble and you have not seen the declaration, inspect
the declaration before trying shape variants.

## Do NOT Read Other Session Directories

Never inspect sibling or stale `.ec_session_*` directories for proof tactics.
They may contain old branches, failed attempts, or cached solutions. In
manager-owned runs, the agent should rely on `ProverWorkspaceView` and semantic
manager requests. For backend debugging, read only the session you explicitly
started.

## Eval Mode

When `[EVAL MODE ACTIVE]` is present or `EVAL_TARGET_LEMMA` is set:

- Do NOT read `knowledge/session_trace/processed/by_problem/`.
- Do NOT read `knowledge/base/sources/proof_bank.jsonl`.
- Do NOT search for the target lemma name in knowledge stores.
- `knowledge/base/search_guide.py` is OK; it redacts target-naming lines.
- Reading the target `.ec` file and sibling lemmas in that file is OK.

Violating these rules invalidates the eval result.

## Testing

See `TESTING.md` for replay, regression, A/B, and long-run procedures.
For long eval-mode proof runs, use the worktree flow in `TESTING.md`: one
lemma per ignored `.worktrees/...` checkout, started from the commit being
evaluated. Do not run paper-facing long evals from the main checkout.

## Key Directories

- `core/` — shared prover infrastructure
- `core/easycrypt/` — EasyCrypt backend, session runtime, events, projection,
  views, analysis, and search
- `workflow/` — orchestrator, tree/racing supervisor, agents, manager facade,
  replay/audit tools
- `workflow/validation/` — proof replay, session artifacts, prover UX/behavior,
  and KB validators
- `eval/` — local benchmark harness and proof examples
- `knowledge/` — knowledge base and trace corpora
- `easycrypt-src/theories/` — EasyCrypt standard library
- `easycrypt-src/tests/` — EasyCrypt tactic examples
