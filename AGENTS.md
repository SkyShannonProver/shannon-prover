# Shannon Prover: Repository Contract

Shannon Prover is an event-bound EasyCrypt proof-agent harness. The current
proof-state compiler is a clean rewrite. Do not restore the retired rich panel,
text-derived semantic analysis pipeline, inspect menu, or compatibility
profiles.

## Non-negotiable boundaries

- Work only inside this repository.
- In eval mode, never retrieve a cached or public proof of the target lemma.
  Reading the proof-stripped target source and allowed sibling declarations is
  permitted.
- The agent interacts with proof state only through the manager-owned
  `submit_proof_intent` MCP tool. `session_cli.py`, sockets, tokens, and raw
  session artifacts are backend/private.
- OpenAI Codex is the default proof-node agent. Claude is available only when
  an experiment explicitly selects it.
- Only managed tree mode is current. Do not add fallback routing for retired
  run modes or surface profiles.

## Runtime ownership

```text
orchestrator
  owns proof-search topology, capacity, branching, and winner selection
        |
        v
ProofNodeManager
  owns one agent turn, intent binding, view refresh, and protocol repair
        |
        +---------------------------+
        |                           |
        v                           v
ReplSessionManager          ProofStateCompilerService
  sole session/mutation       feature-neutral compile facade
  owner                              |
        |                            v
        +-----------> EasyCrypt <--- P1 -> P2 -> P3 -> P4
                         |                    |
                         v                    v
                  exact managed goal   bounded ActionSurface
                         +----------+---------+
                                    v
                                  agent
```

The event/session/manager foundation is retained infrastructure, not the old
compiler. The retired compiler was the former `core/easycrypt/analysis/`, rich
workspace/panel stack, `workflow/surface_*`, analyzer pipeline, inspect/search
menu, and compatibility profiles. Those source trees have been removed.

Terminal proof outcome has a separate single-owner contract. Session runtime
may report goals discharged or `qed` committed; tree supervision may select a
content-bound `SessionClosureCandidate`; neither may report final proof
success. Only `workflow.agents.prover.run()` publishes the canonical
`ProverResult` after offline EasyCrypt verification. Orchestrator summaries,
eval metrics, automatic reports, and project-level drivers must validate or
project that artifact, never rederive success from logs, `qed` suffixes,
directories, or mutable function attributes. See
[`docs/architecture/proof_terminal_outcome.md`](docs/architecture/proof_terminal_outcome.md).

## Current agent-facing turn

Every turn contains only:

- the brief previous manager result;
- exact current EasyCrypt goal/status and canonical identity;
- manager-owned proof controls that are valid now; and
- at most the bounded compiler `ActionSurface` allowed by the active current
  profile.

The agent submits one intent, normally:

```json
{"intent":"commit_tactic","payload":{"tactic":"TAC."}}
```

Current proof controls include `undo_last_step`, `undo_to_checkpoint`,
`amend_and_replay`, `fresh_restart`, and `finish` when the manager advertises
them. The agent must copy the exact advertised payload for conditional or
confirmation-bearing controls. It never supplies node, request, view, goal, or
state identities; the manager binds those.

There is no generic `inspect_context`, `lookup_symbol`, standing tactic menu,
rich panel, or raw workspace JSON contract. If a feature needs information, it
must obtain it through the compiler/native boundary and satisfy its own
evidence and delivery contract.

## Runtime authority and identity

Semantic results are current-call, event-bound artifacts. Durable files,
stdout, stderr, mtimes, directory scans, and prior artifacts are never semantic
fallbacks.

Current authoritative event families are:

- `tactic.execution.produced` for proof mutation;
- `prover.workspace_view.produced` for the exact minimal managed-goal
  envelope (the retained event name does not imply the retired rich view);
- `tactic.preflight.produced` for an exact read-only tactic preflight;
- `compiler.input.produced` for compiler input;
- native proof-term/state result events for EasyCrypt adapters; and
- `episode.timeline.produced` for the current episode timeline.

Readers validate call boundaries, event cardinality/order, session/action
identity, artifact confinement and hash, payload schema, and process exit. They
fail closed.

Goal identity has one owner: the canonical hash of the normalized active
EasyCrypt goal block. An open boundary explicitly requires a nonempty goal
identity. A closed boundary explicitly says identity is not required. Missing
data never implies closedness.

## Proof-state compiler V2

The canonical design is
[`docs/design/proof_state_compiler_v2.md`](docs/design/proof_state_compiler_v2.md).
Its fixed passes are:

```text
P1 projection -> P2 frontend -> P3 middle end -> P4 backend
```

Each feature is a removable vertical slice through those passes. One atomic
activation controls all feature-exclusive loading, analysis, lowering,
certification, and admission work:

- `off`: no feature work;
- `audit`: hidden work, zero agent bytes;
- `treatment`: audit work plus policy-permitted delivery.

Feature removal must not require changes to manager, service, shared pass
driver, renderer, or another feature. Strategy-selecting outputs are held
unless separately admitted by evidence; M05 is the frozen exception.

## EasyCrypt-native semantic boundary

EasyCrypt owns parsing, environments, typed goal/program state, proof-term
argument kinds, name/module/procedure resolution, formula/type unification,
proof matching, holes, concretization, and final tactic acceptance. Shannon
must not reimplement those semantics from pretty-printed text.

Shannon may:

- make bounded lexical candidate sketches to formulate a native query;
- cache immutable declarations with provenance;
- join native results to current manager identity;
- search for a correction within an already selected operation/commitment;
- certify an exact tactic in the unchanged current state; and
- decide delivery, lifetime, budget, and experiment telemetry.

A lexical sketch is never presented as a typed fact. No source-text or retired
analysis fallback may substitute for a missing native result.

## Backend developer interface

`core/easycrypt/session_cli.py` is a manager/backend tool. Its current command
surface is intentionally small:

```text
-start
-tactic-exec commit|commit_chain|undo
-try
-managed-goal-view
-episode-view
-compiler-input-v2
-compiler-resource-load-v2
-native-semantic-batch-json
-native-state-projection-json
-verify
```

Do not restore `-agent-view`, `-goal-info`, `-where`, `-members`, search or
tactic-form menus, `-next/-prev/-chain`, or old inspect wrappers.

EasyCrypt is repository-locked to `r2026.06`. Bootstrap or verify it with
`uv run python tools/bootstrap_easycrypt.py [--verify-only]`; Python runtime
entry points select this managed environment through `core/easycrypt/ec_env.py`
and never fall back to an ambient opam switch. Use
`eval "$(uv run python tools/bootstrap_easycrypt.py --print-env)"` only for a
developer command that invokes `easycrypt` directly. When SMT/Why3 is blocked
by the OS sandbox, run the bounded backend check with the required permission
rather than adding semantic fallbacks.

The `uv` launcher must live outside the project `.venv` it manages. Never use
`.venv/bin/uv` to recreate that same `.venv`: synchronization can remove the
running launcher's path. Install a stable user/system `uv`, or, after the
environment has already been synchronized, run verification directly with
`.venv/bin/python tools/bootstrap_easycrypt.py --verify-only`.

## Evidence-led development

New compiler work starts from mechanical-work evidence. Every visible feature
needs raw provenance, a precise strategy-coupling class, an abstention
contract, a micro causal test, and only then a managed A/B.

Micro experiments test whether one feature removes its targeted mechanical
burden at an identical state. They do not establish full-route value. Full
managed experiments hold model, proof controls, source permissions, prompt,
budget, and runner behavior fixed between L1 and treatment.

Historical reports under `docs/reports/` retain old names as provenance. They
are not runnable protocols or current architecture.

## Testing and change discipline

Use `apply_patch` for source edits. Preserve unrelated user changes. Prefer
`rg`/`rg --files` for discovery. Never use destructive git resets.

Before a compiler checkpoint:

1. run focused contract/feature tests;
2. run the full test suite;
3. run `git diff --check`;
4. verify no current production import or root documentation references a
   retired compiler module/profile;
5. record architecture/evidence status truthfully; and
6. run live agent experiments only from a clean committed worktree.

After any terminal/session/tree/finalization change, also run the no-model
`workflow.validation.proof_terminal_outcome_sentinel` before a live agent
experiment.

See [`TESTING.md`](TESTING.md) for commands and remote-run discipline.
