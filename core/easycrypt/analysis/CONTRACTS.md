# EasyCrypt Analysis Compiler Contracts

This document pins the layer boundaries for the EasyCrypt analysis compiler.
The goal is to keep the pipeline extensible without letting every new proof
failure become another local if/else in `ec_proof_ir.py`.

The short rule is:

```text
parse/canonicalize -> index/resolve resources -> plan obligations -> project typed facts -> verify mutations in backend
```

Each layer may enrich typed facts. Only the backend may mutate an EasyCrypt
session or treat a tactic as verified.

Ground-truth rule:

- If EasyCrypt exposes a fact through a native command or wrapper (`print` via
  `-where`, `print theory` via `-members`, native AST `search` via
  `-search-skeleton`, and future goal/program JSON wrappers), that artifact is
  the authoritative source for the fact.
- Source/pretty-text scans may still exist as recall-oriented fallbacks, but
  they must mark themselves as fallback evidence and must not outrank an EC
  native artifact for the same name/statement.
- Shannon-owned layers may score, canonicalize, rank, or explain EC facts; they
  must not silently replace EC's symbol resolution, type state, or program AST
  with a local regex interpretation when an EC fact is available.
- Shannon adapter commands such as `-goal-json` and `-program-json` are stable
  envelopes, not EC-native facts by themselves. They may carry fallback parser
  facts, and only artifacts whose producer is an EC-native wrapper may set
  `authority = ec_native_ground_truth`.

See `SCHEMAS.md` for the stable fact inventory, `EXTENDING.md` for the
feature-placement map, and `LEMMA_AUTHORING.md` for project-facing lemma
declaration shapes.

## Contract Checklist

When adding a new capability, answer these questions before writing code:

1. What typed fact does this layer produce?
2. Which downstream layer consumes that fact?
3. Does the code depend on a project-specific name, or on declaration/goal
   shape visible in the current context?
4. Is the output a typed fact, an inspection action, or a strategy hint?
5. Which smoke test pins the behavior across benchmark styles?

If a feature cannot answer these questions, it probably belongs in a different
layer or needs a smaller typed fact first.

Do not add to `ec_proof_ir.py` unless the change is pass wiring, fact merging,
phase/liveness summary glue, or compatibility output.  Parser logic, resource
lookup, bridge synthesis, and tactic rendering belong in focused
passes listed below.

## Raw Goal Frontend

Modules:

- `session_projection.py`
- `ec_goal_parser.py`
- `ec_native_state.py`

Inputs:

- EC-native goal/program artifacts when present
- raw EasyCrypt goal text and daemon stdout

Outputs:

- coarse parsed goal dictionaries such as goal type, probability form,
  procedure names, current statements, and parser-provided candidates
- provenance fields: `fact_source`, `authority`, `authority_rank`,
  `ec_ground_truth`, and `native_artifact`

May:

- classify goal family
- extract shallow syntactic fields from stdout
- preserve source snippets for later canonical passes
- fall back to pretty-text parsing when no EC-native artifact exists

Must not:

- choose project lemmas
- rank proof actions
- call EasyCrypt tools
- assume a benchmark-specific lemma naming convention
- present pretty-text facts as authoritative when an EC-native fact exists
- treat `-goal-json` / `-program-json` adapter artifacts as EC-native merely
  because they are JSON

Primary tests:

- `tests/test_goal_pattern_detectors.py`
- `tests/test_session_projection.py`
- `tests/test_proof_ir.py`

## Canonical Frontends

Modules:

- `ec_pr_canonical.py`
- `ec_program_ir.py`
- `ec_procedure_frontend.py`
- `ec_sampling_obligations.py`
- `ec_probabilistic_vc.py`

Inputs:

- parsed goal fields
- raw goal/declaration text when canonical parsing is needed
- ProgramIR statement facts for procedure/sampling frontends

Outputs:

- canonical probability terms, game keys, memories, events, and endpoints
- program statements, call sites, frontiers, and procedure regions
- sampling/coupling motifs and probabilistic VC facts
- ProgramIR provenance showing whether statements came from an EC-native AST
  artifact or the legacy pretty-program fallback

May:

- parse balanced `Pr[...]` syntax and procedure-call syntax
- normalize equivalent endpoint spellings into stable keys
- classify structural motifs such as loops, branches, samples, bad events, and
  bounded query counters

Must not:

- select a project-local lemma name
- emit final proof tactics
- run `-where`, `-search`, `-search-skeleton`, or tactic probes
- treat pretty-printed program listings as ground truth over EC-native program
  AST artifacts
- encode names such as `PLog`, `BR93`, `PRG`, or `ChaChaPoly` unless they
  appear in the current input text

Primary tests:

- `tests/test_ec_pr_canonical.py`
- `tests/test_ec_program_ir.py`
- `tests/test_ec_procedure_frontend.py`
- `tests/test_ec_sampling_obligations.py`
- `tests/test_ec_probabilistic_vc.py`

## Resource And Symbol Layer

Modules:

- `ec_lemma_index.py`
- `ec_name_resolution.py`
- `ec_instantiation_binding.py`
- `ec_pr_elaborator.py`

Inputs:

- visible session context files
- EC-native lookup artifacts from prior `-where`, `-members`, or
  `-search-skeleton` calls
- source file declarations as recall-oriented fallback evidence
- canonical goal facts
- legacy signature lookup artifacts when no native `-where` artifact exists

Outputs:

- `SemanticLemmaCandidate`-style facts with semantic tags and scores
- `NameResolutionFact`-style facts with declaration/signature status
- `InstantiationBinding`-style facts for module, memory, type, and value slots
- Pr elaboration facts that separate abstract lemma slots from concrete
  procedure endpoints

May:

- consume EC-native lookup/search artifacts as ground truth
- scan declarations visible to the current session as fallback recall
- classify lemmas by statement shape, such as Pr equality, Pr inequality,
  additive bound, event union, or bad-event bound
- match a complete loaded losslessness implication against the current
  obligation and instantiate its module/premise slots
- suggest read-only signature lookup actions
- attach conservative instantiation candidates

Must not:

- require lemma names to begin with `pr_`, `bound`, `step`, or any benchmark
  prefix
- commit `apply`, `rewrite`, `have`, `call`, or `byequiv`
- treat an unresolved declaration as runnable
- let a source scan override an EC-native `-where` or `-search-skeleton` fact
  for the same lemma
- inspect stale `.ec_session_*` directories outside the current session
- return the target lemma itself as a closing candidate

`ec_lemma_index.py::mechanical_goal_candidates` is the sole loaded-declaration
owner for exact current-goal conclusion matches. Downstream proof-management
analyzers consume its workspace projection; they must not reopen the target
source and maintain a second conclusion matcher. Procedure-specific one-sided
losslessness matching and EasyCrypt module-argument packaging are likewise
owned by `semantic_one_sided_losslessness_candidates` in this layer.

Primary tests:

- `tests/test_ec_lemma_index.py`
- `tests/test_ec_name_resolution.py`
- `tests/test_ec_instantiation_binding.py`
- `tests/test_compiler_smoke_matrix.py`

## Middle-End Planners

Modules:

- `ec_pr_obligations.py`
- `ec_pr_path_planner.py`
- `ec_pr_bridge_frontend.py`
- `ec_dataflow_invariant.py`
- selected obligation facts from `ec_probabilistic_vc.py`

Inputs:

- canonical goal facts
- semantic candidates
- name-resolution and instantiation facts
- current proof phase and liveness facts

Outputs:

- Pr normalization facts
- Pr union/bound/arithmetic obligations
- Pr path plans and partial frontiers
- invariant skeletons and residual proof obligations

May:

- say that a goal needs a Pr union-bound plan, semantic bound lookup, bridge,
  arithmetic chain, or invariant skeleton
- compose known handles into a path plan
- expose missing frontiers or unresolved obligations as typed facts

Must not:

- hide a missing resource by falling through to a low-level tactic
- decide a project-specific lemma name by convention
- apply native-search hits directly
- mark a tactic as verified

Primary tests:

- `tests/test_ec_pr_obligations.py`
- `tests/test_ec_pr_path_planner.py`
- `tests/test_ec_dataflow_invariant.py`
- `tests/test_compiler_smoke_matrix.py`

## Native Search Bridge

Modules:

- `ec_native_ast_search.py`
- backend wrappers in `session_cli.py` and `../search/`

Inputs:

- current goal/operator shape
- previous search artifacts in the current session

Outputs:

- conservative `-search-skeleton` queries
- typed search hits rendered as `-where <lemma>` inspection actions

May:

- propose native EasyCrypt AST/operator search
- consume current-session search artifacts as evidence
- route promising hits to declaration inspection

Must not:

- make frontend canonicalization depend on a live EasyCrypt subprocess
- turn a search hit directly into `apply` or `rewrite`
- search public repositories or external network sources

Primary tests:

- `tests/test_ec_native_ast_search.py`
- `tests/test_ec_menu_actions.py`
- `tests/test_compiler_smoke_matrix.py`

## Action Rendering Layer

Modules:

- `ec_menu_actions.py`
- `ec_pr_actions.py`
- `ec_procedure_actions.py`
- `ec_action_contracts.py`

Inputs:

- already-computed handles, obligations, liveness, and resource facts

Outputs:

- stable `ActionCandidate` menu-item dictionaries

May:

- render inspection actions such as `-where <lemma>`
- render strategy hints for non-atomic plans
- render typed tactic templates only when their preconditions are explicit;
  templates are evidence and are not an agent-facing probe intent
- preserve cost, precondition, and proof-state preservation metadata

Must not:

- discover new semantic facts
- parse new goal syntax
- run EasyCrypt
- silently upgrade inspection actions into runnable tactics
- erase incomplete Pr handles by offering only generic pRHL lowering

Primary tests:

- `tests/test_ec_menu_actions.py`
- `tests/test_ec_pr_actions.py`
- `tests/test_ec_procedure_actions.py`
- `tests/test_compiler_smoke_matrix.py`

## ProofIR Facade

Modules:

- `ec_proof_ir.py`

Inputs:

- current proof state
- current goal projection
- session directory metadata
- external recommendations

Outputs:

- `easycrypt_proof_ir` JSON-like summary
- phase/liveness/resource summaries
- candidate menu (structural build order; the factual Pr-bridge chain order
  is applied by `_order_instantiated_pr_bridges`)

May:

- orchestrate frontend/resource/planner/action passes
- apply phase legality, liveness, and negative evidence
- preserve stable output shape for AgentView and CommandSummary

Must not:

- become the home for new parser/resource/action logic once a focused module
  exists
- call EasyCrypt directly
- decide project-specific lemma names by convention
- mask missing resources with a generic fallback when a typed obligation says a
  Pr-layer resource is still needed

Primary tests:

- `tests/test_proof_ir.py`
- `tests/test_session_agent_view.py`
- `tests/test_session_command_summary.py`
- `tests/test_compiler_smoke_matrix.py`

## Backend And Tool Boundary

Modules:

- `session_cli.py`
- EasyCrypt daemon/session wrappers
- `../search/`

Inputs:

- concrete proof mutations and read-only inspections selected through the
  manager protocol

Outputs:

- EasyCrypt state transitions
- tool artifacts such as `-where`, native search, goal info, and verification
  results

May:

- run EasyCrypt
- mutate proof state for committed proof intents
- run hidden developer/backend checks when required by validation tooling;
  these checks never become an advertised agent probe capability
- verify proof files
- cache current-session tool artifacts

Must not:

- use stale sessions as proof sources
- accept `admit.`
- turn failed internal checks into accepted proof facts
- feed unstructured backend text into frontend logic without a typed artifact

Primary tests:

- `tests/test_session_command_summary.py`
- `tests/test_session_agent_view.py`
- `tests/test_proof_replay.py`
- `tests/test_prover_view_smoke.py`

## Stable Fact Shapes

The code still uses JSON-like dictionaries for AgentView compatibility. These
names describe the intended contracts even when they are not implemented as
Python classes yet. Field-level details live in `SCHEMAS.md`.

| Fact | Producer | Consumer | Required idea |
| --- | --- | --- | --- |
| `PrTerm` | `ec_pr_canonical.py` | lemma index, Pr obligations, path planner | endpoint, memory, event, canonical game key |
| `ProgramIR` | `ec_program_ir.py` | procedure frontend/actions, VC frontend | call sites, statements, frontiers |
| `SemanticLemmaCandidate` | `ec_lemma_index.py` | Pr obligations, menu actions, ProofIR | lemma, declaration, semantic tags, score, source |
| `NameResolutionFact` | `ec_name_resolution.py` | candidate name resolution, instantiation binding | exact-signature status, lookup action, declaration slots |
| `InstantiationBinding` | `ec_instantiation_binding.py` | ProofIR/action enrichment | slot type, candidate values, confidence |
| `PrObligation` | `ec_pr_obligations.py` | Pr actions, diagnostics | obligation kind, evidence, action boundary |
| `PrPathPlan` | `ec_pr_path_planner.py` | Pr actions, recommendations | complete/partial paths, lemmas, hops, arithmetic plan |
| `PrBridgeCandidate` | `ec_pr_bridge_frontend.py` | Pr path planner, Pr actions | typed wrapper/adapter bridge edge with tactic or structural hint |
| `EquivExactCloser` | `ec_equiv_closers.py` | action rendering, ProofIR | pRHL/equiv lemma matching current procedure pair |
| `NativeSearchFact` | `ec_native_ast_search.py` | menu actions, resource feedback | search queries, hits, artifact evidence |
| `ActionCandidate` | action modules + `ec_action_contracts.py` | ProofIR candidate menu, AgentView | id, tactic text, action type, readiness, effect, provenance |

## Adding A New Benchmark Family

1. Add a real-source row to `tests/test_compiler_smoke_matrix.py`.
2. Add a synthetic style-variant row if the failure involved a new lemma naming
   or declaration style.
3. Assert semantic recall, obligation planning, and action rendering. Do not
   assert the complete proof.
4. If the test fails because the fact belongs in a new layer, add the typed fact
   first; do not patch `ec_proof_ir.py` with benchmark-specific logic.
5. If the test fails because the authoring style hides essential structure,
   document the required lemma declaration shape instead of guessing.

## Known Partial Boundaries

These areas are intentionally not fully split yet:

- `ec_proof_ir.py` still owns phase legality, some liveness glue, negative
  evidence application, and AgentView compatibility wrapping.
- Native search currently feeds back as inspection actions; the fuller loop
  `search hit -> where declaration -> semantic candidate -> obligation/action`
  should remain typed when it is expanded.

Future extractions should preserve the contracts above before moving code.
