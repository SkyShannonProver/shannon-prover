# Shannon Prover — Architecture

Shannon Prover is an event-driven pipeline in which an LLM agent proves
EasyCrypt lemmas through **managed proof sessions**: the agent never touches
EasyCrypt directly. Each turn it reads a rendered proof-state panel (the
*followup*), replies with exactly one JSON intent (`commit_tactic`,
`probe_tactic`, `lookup_symbol`, a context topic, …), and a manager owns
everything else — session mutation, verification, view refresh. The central
experimental axis is the **surface profile**: the same manager can show the
agent a bare goal (`l1_goal_projection`) or the full compiler surface
(`l4_checked_action_surface`), so interface richness can be A/B-measured
against the same backend.

## Process topology

```text
orchestrator (workflow/orchestrator.py, one process per lemma run)
  -> agents/prover.run (in-process launch coordination)
    -> tree.supervisor.NodeSupervisor (spawn/poll/respawn of tree nodes)
      -> managed_prover_worker (one SUBPROCESS per tree node)
        -> ProofNodeRuntime -> ProofNodeManager -> ReplSessionManager
                                                -> WorkspaceViewManager (core)
agent <- one ProverWorkspaceView (rendered followup per turn)
```

Layer by layer:

- **`workflow/orchestrator.py`** — single-pass entry: duplicate-lemma
  precheck, run-dir/env setup, planner phase, prover phase, post-run bundle
  hook. It never holds a manager handle.
- **`workflow/agents/prover.py`** — launch coordination around `run()`. Its
  two heavy concerns live in siblings: `agents/ec_services.py` (why3server +
  EC-daemon process/socket lifecycle, opam env, scratch paths) and
  `agents/prover_writeback.py` (session-history extraction, lemma-scoped
  verification, admit scanning, failing-tactic pruning, final
  write-and-verify).
- **`workflow/tree/supervisor.py`** — `NodeSupervisor` owns the tree: it
  spawns worker subprocesses, polls their streams (`tree/trackers.py`), and
  runs named periodic phases (`_tick_session_hygiene`, `_tick_progress_gap`,
  `_tick_spawn_on_structural_undo`, …) for watchdogs, kills, and child
  spawns. Branch policy vocabulary is pure and separate in `tree/policy.py`.
- **`workflow/managed_prover_worker.py`** — thin subprocess entry; builds a
  `ProofNodeRuntime`.
- **`workflow/proof_node_runtime.py`** — per-node harness: the long-lived
  Claude Code subprocess (`ClaudeAgentSession`, launched with
  `--model`/`--effort` and a fail-closed destructive-tool denylist), node
  memory, and the bridge that forwards each agent intent to the manager.
- **`workflow/proof_node_manager.py`** — the facade the runtime talks to:
  protocol gates (admit/qed/finish), per-turn surface assembly, and the
  services in `workflow/proof_management/` (repl session backend, projection,
  lifecycle, checkpoints, events/memory/lineage, analyzers, escalation).
- **`core/easycrypt/`** — the EasyCrypt backend. Process ownership is
  single-homed: `ec_proc.py` owns argv/spawn, `ec_lifecycle.py` owns
  spawn→drain→replay→teardown, `ec_daemon.py` is the persistent
  `easycrypt -emacs` daemon (Unix-socket JSON RPC, ephemeral fresh-replay
  probes), and `why3server` powers `smt()` (it needs the `nice()` syscall —
  run outside OS sandboxes).

## The layering invariant

`workflow` imports `core`; **core never imports workflow**. The invariant is
pinned by an AST scan in `tests/test_layering_contract.py` (it catches lazy
function-level imports too). A handful of leaf modules are importable from
anywhere by design: `core/context_intents.py` (the agent intent vocabulary),
`core/easycrypt/value_shapes.py` (shape guards), and
`core/easycrypt/committed_history.py` (the single `history.ec` reader).

## The view pipeline (what the agent actually reads)

```text
raw EC output -> projection -> ProofContextView -> ProverWorkspaceView
             -> surface-profile filter (L1..L4) -> rendered followup
```

- `core/easycrypt/session_projection.py` joins the session's current/previous
  output, events, and the goal parser into one read-only projection.
- **`ProofContextView`** (`session_agent_view.py`) is the durable,
  full-fidelity artifact — the *audit twin*, structurally identical across
  profiles.
- **`ProverWorkspaceView`** (`session_prover_workspace_view.py` plus siblings
  `session_frontier_scope.py`, `session_workspace_view_manager.py`) is the
  agent-facing panel: goal, frontier context, candidate moves, inspect
  handles.
- `workflow/surface_profiles.py` erases panels per profile: L1 keeps only the
  goal and a one-line accept/reject; L4 keeps the full workbench.
- The **rendered followup** (via `proof_node_runtime.render_manager_followup`
  and the surface stack below) is the text the agent reads. When comparing
  profiles, always compare followups — the underlying view JSON is
  deliberately profile-invariant.

## The surface stack (one-way imports)

```text
surface_model  ->  surface_panels  ->  surface_whole_program  ->  composer
      (typed leaves)   (panel builders)  (region/shape analysis)   (surface_composer.py:
                                                                    compose_surface_model
                                                                    + phase selection)
   -> surface_turn_model (per-turn contract) / surface_profiles (visibility)
```

Goal-text scanning lives below all of this in `core/easycrypt/analysis/`
(e.g. `ec_pr_terms.py` for `Pr[...]` forms) — presentation modules consume
parsed facts, they do not parse goal text.

## The analysis ("compiler") layer

`core/easycrypt/analysis/` turns raw goal text into typed facts, resources,
obligations, and candidate actions via a four-pass pipeline driven by
`ec_proof_ir.py` (state → handles → liveness → action surface, with a
freeze/thaw guard between passes). Layer contracts are pinned in
`analysis/CONTRACTS.md`, payload shapes in `analysis/SCHEMAS.md`, and the
extension guide in `analysis/EXTENDING.md`. A byte-level golden test
(`tests/test_proof_ir_golden.py`) locks the IR output.

## Inspect engines (commit path stays cheap)

Commit-time hooks (`core/easycrypt/session_hooks.py` +
`session_hook_phases.py`) emit only cheap synchronous context, so an ordinary
commit refreshes like an IDE. The daemon-backed engines are reached only
through explicit read-only inspection (`PivotStrategyPhase.inspect` routing
into `session_pivot_bridge.py` / `session_pivot_invariants.py` /
`session_pivot_routes.py`). Probe-based candidate verification on the commit
path is a research opt-in (`SHANNON_ENABLE_PROBE`), off by default.

## Verifying a change

1. `pytest tests/` — the failure set must not grow (a few environment-bound
   tests skip without EasyCrypt on PATH).
2. **Panel invariance**: `bash tools/panel_audit/replay_baseline_suite.sh OUT`
   replays six recorded runs (correctness equiv, pRHL reduction,
   probability/phoare with a stalled recovery arc, a high-rejection sigma
   protocol, up-to-bad reasoning on an L1-native stream, and a clone-heavy
   eager/swap proof) through the current checkout. Run it before and after a
   change **from equally clean checkouts** and `diff -r` the outputs — some
   route-health suggestions scan the target `.ec` source on disk, so an
   uncommitted corpus edit shows up as a spurious view diff.
3. For supervision/runner changes, a live smoke:
   `uv run python -m eval_suite.run --suite eval_suite/suites/demo_pir.json
   --profiles l4_checked_action_surface` (proves `PIR_correct` end to end and
   auto-writes a replayable bundle under `agent_view_runs/`).

## Historical archaeology

Comments like `backlog #7` or `audit §3.4` reference two internal
point-in-time architecture audits (2026-06-13 and 2026-06-22) whose backlog
drove a long sequence of extractions; the annotations mark where each
landed. The audit documents themselves are not part of this repository —
treat the annotations as historical markers, not descriptions of the
current tree; most findings have since been fixed, and several modules they
name have been split or renamed since.
