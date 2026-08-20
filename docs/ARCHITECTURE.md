# Shannon Prover Architecture

This file is the compact public map of the current architecture. The sole
normative compiler design is
[`design/proof_state_compiler_v2.md`](design/proof_state_compiler_v2.md).

```text
orchestrator
  proof-search tree only
        |
ProofNodeManager
  exact agent turn and identity owner
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
      agent
```

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

core/easycrypt/   EasyCrypt backend; session/ holds one proof session's
                  state machine, events, artifacts, and projections;
                  session_cli.py stays at the top as the backend CLI entry

experiments/      research micro/sentinel/evaluator scaffolding — never
                  imported by production code
```

Module basenames are unique across the tree and did not change in the
2026-08-19 restructure; only their directories did.

The retained manager/session/event foundation is not the old compiler. The old
rich workspace, panel, text-derived semantic analysis, inspect/search, analyzer,
and `workflow/surface_*` source paths have been physically removed. Historical
reports preserve their names only as experiment provenance.

OpenAI Codex, managed tree mode, and the `proof_state_compiler` runtime profile
are the defaults. The goal-only no-compiler profile is an experiment control.
Compiler features are independently removable vertical slices with atomic
off/audit/treatment activation. EasyCrypt owns parsing, typing, resolution,
matching, proof-term elaboration, and tactic acceptance.
