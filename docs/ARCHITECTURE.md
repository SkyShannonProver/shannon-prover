# Shannon Prover Architecture

This file is an implementation reference for contributors. For installation
and proof construction, start with the [user guide](../workflow/interleaved/README.md).
The sole
normative compiler design is
[`design/proof_state_compiler_v2.md`](design/proof_state_compiler_v2.md).

Shannon Prover automates proof decomposition (Phase II) and tactic-level
proof construction (Phase III) together. An outer proof-construction agent
chooses the game hops and auxiliary lemmas, constructs the final proof, and
can delegate auxiliary lemmas through a bounded scheduler to managed proof
nodes. The standalone `$prove` workflow starts one such node for a
human-supplied lemma. ChaChaPoly supplies one reference task and stricter
verification rules on top of the reusable interleaved implementation.

```text
interleaved coordination plane (workflow/interleaved product)
  outer agent: decomposition + whole-file construction
        |
        +--> direct locked EasyCrypt checks
        |
        `--> bounded scheduler: snapshots, leases, handoff, continuation
                       |
             one or more managed proof nodes
                       |
             verified lemma or bounded progress
                       |
                 outer integration
                       |
              whole-file final verifier

managed proof-node plane (also the default standalone workflow)
  node orchestrator: proof-search tree only
        |
  ProofNodeManager: exact agent turn and identity owner
        |
        +--> ReplSessionManager --> EasyCrypt
        |      sole mutation          semantic authority
        |
        `--> ProofStateCompilerService
                 P1 -> P2 -> P3 -> P4
                            |
                     bounded ActionSurface
        |
  current turn presenter
        |
  runner-selected proof agent
```

The outer agent owns cross-lemma strategy and delegation boundaries. The
scheduler owns capacity and immutable job identity. A proof node owns one
stateful tactic search. The compiler assists only with bounded mechanical work
at one exact node state. Final success belongs to the canonical node verifier
for a delegated lemma and to the runner's whole-file verifier for the
end-to-end interleaved theorem.

## Package map

```text
workflow/
  orchestrator.py, project_driver.py   entry points (-m paths are stable)
  proof_tool/     the one MCP tool per node: contract, launch, stdio child,
                  loopback endpoint, serialized serving session
  provider/       Claude/Codex subprocess sessions, event normalization and
                  the fail-closed lifecycle guard, respawn policy, IO policy
  node/           node runtime assembly + generation loop, the semantic turn
                  manager, node memory, prompt/followup rendering, resume,
                  the worker process entry
  agents/         run-level prover orchestration, write-back, EC OS services
  proof_management/  manager semantic layer (admission, execution, events,
                  checkpoints, recovery) — sole EasyCrypt mutation owner
  tree/           proof-search tree supervision, trackers, session observer
  reporting/      run bundle, timeline report, thinking-trace extraction
  validation/     product-mandated no-model gates (terminal-outcome sentinel)
  schemas/        run configuration and terminal-result contracts
  proof_state_compiler/  compiler frontend/profiles (+ research/ plugin)
  interleaved/    Phase-II/III project contract, outer runner, scheduler,
                  lane workers, handoff, resumption and whole-file verifier

core/easycrypt/   EasyCrypt backend; session/ holds one proof session's
                  state machine, events, artifacts, and projections;
                  session_cli.py stays at the top as the backend CLI entry

experiments/interleaved_shannon/
                  ChaChaPoly reference evaluation adapter, prompt and task
experiments/      all other private research micro/sentinel/evaluator
                  scaffolding — never imported by production code
```

The retained manager/session/event foundation is not the old compiler. The old
rich workspace, panel, text-derived semantic analysis, inspect/search, analyzer,
and `workflow/surface_*` source paths have been physically removed. Historical
reports preserve their names only as experiment provenance.

OpenAI Codex, managed tree mode, and the `proof_state_compiler` runtime profile
are the proof-node defaults. New interleaved runs also default to Codex for
both the outer agent and inner proof nodes. Their model and effort settings
come from [`workflow/interleaved/agent_profiles.json`](../workflow/interleaved/agent_profiles.json).
Claude is available for either role through an explicit provider selection.
The goal-only no-compiler profile is an experiment control.
Compiler features are independently removable vertical slices with atomic
off/audit/treatment activation. EasyCrypt owns parsing, typing, resolution,
matching, proof-term elaboration, and tactic acceptance.

## Proof-node turn

The long-lived proof agent submits exactly one manager intent per turn. The
manager:

1. validates the intent grammar exposed for this turn;
2. binds node, session, request, state, and goal identities;
3. executes the manager-owned operation;
4. refreshes the exact event-bound managed goal;
5. optionally calls the single compiler service for the active profile;
6. composes a small result, goal/status, controls, and bounded ActionSurface;
7. persists current node memory and audit events; and
8. returns the new turn to the same agent session.

Malformed input produces a repair turn without changing proof state. Repeated
protocol failures become node-health evidence for the orchestrator; they do
not give the manager proof-strategy ownership. The presenter only renders that
turn: it does not know feature names, run producers, select routes, or expose
audit items.

## Change rules

A runtime change is acceptable only if:

- identity has one owner across manager/session/compiler;
- a read-only call is event-bound and demonstrably non-mutating;
- unsupported old modes fail instead of silently translating;
- the experiment control remains compiler-free and goal-only;
- features remain removable without manager/presenter edits; and
- deterministic tests cover both valid and fail-closed paths.
