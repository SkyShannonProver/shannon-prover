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

The retained manager/session/event foundation is not the old compiler. The old
rich workspace, panel, text-derived semantic analysis, inspect/search, analyzer,
and `workflow/surface_*` source paths have been physically removed. Historical
reports preserve their names only as experiment provenance.

OpenAI Codex, managed tree mode, and the `proof_state_compiler` runtime profile
are the defaults. The goal-only no-compiler profile is an experiment control.
Compiler features are independently removable vertical slices with atomic
off/audit/treatment activation. EasyCrypt owns parsing, typing, resolution,
matching, proof-term elaboration, and tactic acceptance.
