# Hypothesis-Driven Proving

**Updated:** 2026-07-09 — refreshed against the live view/profile code: removed
navigation-heuristic fields that no longer exist and marked probe previews as a
research-mode option (off by default).

This document is the friendly guide to hypothesis-driven proving in Shannon.
It explains the agent-facing proof loop in the same vocabulary used by the
current code: map, navigator, workbench, surgery workbench, preview, and route
health.

## The Short Version

Think of each proof node as an IDE for EasyCrypt, not a raw terminal.

The **map** is the compiler-style picture of the proof terrain: current goal
family, program frontier, call sites, declarations, live handles, residual
obligations, and recent failures. The **navigator** reads that map and lists
the factual candidate moves that are legal in this exact state. The
**workbench** is the
`ProverWorkspaceView` shown to the prover. The prover still chooses proof
intents; the manager owns all mutation and refresh.

For large pRHL proofs, the metaphor becomes a **surgery table**. Once the main
opener exposes a branch, call, loop, sample, or suffix frontier, the right work
is usually precise local surgery: split the branch, force a guard, swap a
statement, use indexed `wp`, weaken with `conseq`, or couple a one-sided
sample. In research runs with probes enabled (they are off by default), the
system can preview those moves before committing; either way it should repair
the local boundary when facts are missing instead of restarting the whole
proof branch.

## Vocabulary Map

| Metaphor | Code surface | What it means |
|---|---|---|
| Map | `ProofIR`, ToolViews, `program_frontier`, `application_context` | The factual terrain for the current completed EasyCrypt snapshot. |
| Navigator | `candidate_moves.moves` from `session_prover_workspace_view.py` | The factual option menu for the current view, sourced from the typed ProofIR `candidate_menu`. No ranking, self-rated confidence, or anti-routes. |
| Workbench | `ProverWorkspaceView` | The ordered IDE panel the prover reads each turn. |
| Surgery table | pRHL branch/suffix route families | Local frontier work such as `case`, `rcondt`, `rcondf`, `swap`, indexed `wp`, `conseq`, and one-sided `rnd`. |
| Preview window | `probe_tactic`, `last_result.probe_preview`, `candidate_moves.probe_alternatives` | A research-mode way to see what a move would expose before changing the committed proof state. Probes are disabled by default; `SHANNON_ENABLE_PROBE=1` opts in. |
| Vital signs | `candidate_moves.route_health` | Manager-added diagnosis of the current route, such as boundary gap or frontier placement trouble. |
| Phase door | `candidate_moves.structural_transitions` | A reversible entrance into a new proof phase, for example `wp.` before entering post-`wp` surgery. |
| Pure-tail surface | `pure_tail_surface` | L4 evidence for map/projection/list alignment, membership decomposition, existential witness candidates, lookup key cases, sampling side conditions, and memory-decoration facts after program work has become pure logic. |

## Turn Lifecycle

1. `ProofNodeManager` refreshes the latest authoritative
   `ProverWorkspaceView`.
2. The prover reads `current_goal.lines`, `proof_status`,
   `program_frontier`, `application_context`, `facts_and_diagnostics`, and
   `candidate_moves`.
3. The prover chooses one current-view hypothesis, then either asks for
   semantic context (`inspect_context` / `lookup_symbol`) or commits a tactic
   with `commit_tactic`. In research runs with probes enabled
   (`SHANNON_ENABLE_PROBE=1`, off by default) it can first preview a tactic
   with `probe_tactic`.
4. `ReplSessionManager` is the only component that probes, commits, undoes,
   restarts, or replays EasyCrypt state. Tree sibling creation belongs to the
   orchestrator; a child node rebuilds state by replaying a verified prefix.
5. When probes are enabled, accepted probes remain read-only. Their
   speculative after-goals live under
   `last_result.probe_preview.goal_after_probe`; manager-kept accepted and
   rejected probes may be listed in `candidate_moves.probe_alternatives`.
6. The prover commits a tactic (in probe runs, only the exact accepted one)
   when the resulting `structural_transition` is the phase it actually wants
   to enter.
7. The manager refreshes the workbench and may add route health or a new phase
   door for the next turn.

## Current Candidate-Move Menu

The navigator surface is deliberately factual and state-conditioned. It does
not try to solve the lemma or rank routes. It only reads the current completed
snapshot — through the typed ProofIR `candidate_menu` — and lists moves that
are plausible now:

- module-equivalence opener, usually `proc.` before a real procedure frontier;
- top-level probability-to-program route (`Pr[...]` rewrites, bridge chains,
  and `byequiv`-style bridges);
- bounded hoare/phoare probabilistic-VC route;
- ambient named-closer or local lemma route;
- ambient definition-unfold route;
- ambient residual close route;
- pRHL mid-surgery route for branch/suffix work;
- pRHL branch/call frontier route.

Each menu item should be read like a trail sign, not a command. Check
`category`, `tactic` / `tactic_shape`, `guidance`, `applicability`,
`runnable_status`, and `missing_input` before acting; a daemon-checked move
additionally carries `epistemic_status` and a verification-evidence
`confidence` (`verified_by_probe` / `verified_by_easycrypt`).

## Surgery Workbench And Previews

The surgery workbench appears when a pRHL proof has moved past the broad
opener and the remaining problem is local frontier manipulation. Typical tools
are:

- `case` for splitting a visible branch guard;
- `rcondt` / `rcondf` for forced branch conditions;
- `swap` or `eager` when statement order is wrong;
- indexed `sp i j` or `wp` when only part of a suffix should be exposed;
- `conseq` when the current postcondition is too large for the local step;
- `rnd{1}` / `rnd{2}` for one-sided sampling obligations;
- `call (_: Inv)` after the invariant has been made concrete.

There are two important preview paths:

- `probe_tactic` (a research-mode option, disabled by default; enable with
  `SHANNON_ENABLE_PROBE=1`) asks EasyCrypt whether a concrete tactic is
  accepted and shows the speculative after-goal without mutating committed
  state.
- `inspect_context` topic `call_subgoals` previews the obligations created by
  a concrete `call (_: Inv)` invariant. This is the invariant preview table:
  it exposes pre/init, call-preservation, oracle-side, postcondition,
  missing-fact, and extra-conjunct obligations before the prover commits.

If a preview shows that required guard, size, map, or oracle state facts are
missing, prefer route-local repair. `route_health` may offer an
`undo_to_checkpoint` menu so the prover can revisit the boundary that should
have preserved those facts.

## Ownership Boundaries

The system stays safe because each layer owns only one job:

- Orchestrator owns tree/racing policy: spawn, kill, stuck detection,
  capacity, and winner selection.
- `ProofNodeManager` owns the agent turn boundary, intent parsing and repair,
  metadata binding, route health, structural transitions, and view refresh.
- `ReplSessionManager` owns all EasyCrypt lifecycle and state mutation.
- `WorkspaceViewManager` and `ProverWorkspaceView` own projection, ordering,
  wording, linting, and the current-view candidate-move menu.
- The prover agent owns proof choices: which route to inspect, which tactic to
  probe or commit, which symbol to look up, and when to report a blocker.

No agent-facing prompt or workspace view should ask the prover to use
`session_cli.py`, sockets, bridge tokens, or raw backend files as the proof
protocol. Those are backend tools. The prover speaks in proof-level JSON
intents through the manager.

## Where To Read Next

- [`README.md`](../../README.md) for the project map and directory layout.
- [`workflow/DESIGN.md`](../../workflow/DESIGN.md) for the architecture and
  ownership contract.
- [`core/easycrypt/TOOLS.md`](../../core/easycrypt/TOOLS.md) for the detailed
  EasyCrypt tool catalog and semantic inspect topics.
- [`workflow/validation/README.md`](../../workflow/validation/README.md) for
  replay, view, behavior, and KB validation.
