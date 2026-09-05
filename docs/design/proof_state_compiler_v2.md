# Proof-State Compiler V2

Status: **current canonical architecture specification for the clean rewrite**

Architecture decision current through: 2026-08-14

Primary conceptual reference: [*ShannonProver: Towards Automating Formal
Cryptographic Proofs*](https://arxiv.org/pdf/2607.02847), Section 3 and Figures
4-5. The paper supplies the four-pass semantic organization. This document is
the implementation authority when it makes runtime, certification, exposure,
or module boundaries more explicit.

### Authority and reading order

This is the one normative design document that implementation agents must
follow. When another design note, experiment checkpoint, historical report,
or current code disagrees with this document, this document controls the target
architecture. Code disagreement is implementation debt, not an alternate
contract.

Use this file for compiler architecture, ownership, dependency direction, and
allowed production behavior. Use
[`proof_terminal_outcome.md`](../architecture/proof_terminal_outcome.md) for
the harness-wide boundary between session closure, tree selection, and final
verified run outcome. Dated checkpoint and experiment records are historical
evidence, not additional architecture authorities.

Checkpoint documents may describe capabilities that were implemented for an
earlier experiment but are no longer authorized as production extension
points. In particular, older references to general SC2 optional advisories are
superseded by the strategy boundary below.

Empirical feature admission is tracked separately from this architecture.
Experiment results are evidence about features; they do not define production
behavior.

### Three program pillars

The rewrite has three independent proof obligations:

| Pillar | Required proof | Current state |
|---|---|---|
| Value/evidence | L1 bundles identify real mechanical cost; one isolated Shannon delta repays its hidden and visible cost in matched micro and diverse full-route experiments. | Evidence inventory is substantial; efficacy remains feature-specific and continuously gated. |
| Clean rewrite/removal | V2 is a fixed P1-P4 skeleton with isolated removable features, and the legacy compiler can be physically deleted without deleting the neutral managed-prover foundation. | **Complete at the source/runtime boundary.** The old parser/ProofIR/analyzer/panel/presentation, inspect/search, compatibility profile, and mixed runtime branches have been removed. Historical reports retain names only as provenance. |
| Native reuse/contribution | EasyCrypt supplies every semantic result it already owns; Shannon adds only bounded search/commitment logic and harness delivery/economics, stated and measured separately. | Architecture-level ownership, M01-M25 decomposition, N1a/N1b, N1c typed-state endpoint, N1d native P1/P2 lowering, N1e proof-term descriptors, and N2b.1-N2b.3a SC1 application migrations are complete locally; the frozen remote N2b.3a trigger-parity gate remains. Historical N2a M05 validation is maintained only on `compiler-proactive`. |

Success in one pillar never substitutes for another. A locally helpful feature
does not justify architectural coupling; a clean feature does not establish
token benefit; an EasyCrypt-accepted action does not mean Shannon contributed
the underlying elaboration.

## 1. Mission and non-goals

The proof-state compiler removes state-dependent mechanical proof work. It
turns one authoritative EasyCrypt state and its loaded environment into a
small structured interface of currently relevant resources, native-resolved
bindings, checked local actions, and neutral diagnostics.

The compiler does not:

- own or mutate an EasyCrypt session;
- choose an invariant, coupling, cut, witness, or global proof route;
- own tree search, backtracking policy, or agent lifecycle;
- turn accepted local progress into a claim that a route is good; or
- expose everything it can compute.

It also does not implement speculative route-selection producers merely so
they can remain hidden. A route-selecting idea stays in the evidence ledger
until an explicit architecture decision changes this boundary. Shared IR is
implemented only when an active SC0/SC1 consumer or a correctness contract
requires it.

EasyCrypt remains the only proof-state, proof-term elaboration, typing,
matching, and proof-acceptance authority. The agent remains the owner of proof
strategy.

### Native EasyCrypt semantic authority

Native execution and reuse reduce boundary crossings without reducing semantic
authority, in the fixed order avoid → coalesce → sound reuse → evidence-gated
persistence. This is runtime orchestration around P1–P4, not an additional
compiler pass.

Native planning capacity is likewise a shared compiler contract, never a
feature-local magic number. Producers receive one immutable remaining budget,
return a complete typed production or a typed abstention, and may not select a
candidate prefix merely because only that prefix fits. Consumer fan-out and
distinct EasyCrypt execution units have separate bounds. Allocation is
feature-owned and order-independent; insufficient capacity is an auditable
abstention, while exceptions are reserved for identity or contract violations.

“Use native EasyCrypt” means invoking the native semantic implementation in
the exact current proof environment and retaining its state/build/event
provenance. Reimplementing an EasyCrypt algorithm over pretty-printed text in
Python is not inheritance.

Native EasyCrypt owns:

- local hypothesis and global lemma resolution;
- proof-term product/binder decomposition and argument-kind discrimination;
- formula parsing, typing, and unification;
- module resolution, module-signature conversion, and restriction checking;
- memory resolution;
- proof-argument formula matching;
- implicit arguments, holes, metavariables, and concretization; and
- tactic-specific proof-term consumption and proof-state effects.

The proof-state compiler owns the surrounding harness concerns: event-bound
state/provenance, bounded query planning, feature activation, the
strategy/commitment boundary, recovery ownership, delivery lifetime and
budgets, caching, presentation, telemetry, and L1/audit/treatment composition.

### Current managed state envelope

Current L1 and compiler-V2 arms must take this exact runtime path:

```text
ReplSessionManager
  -> -start
       initialize/restart only; no discarded rich-view construction
  -> -managed-goal-view
       current projection only
       exact active goal text + canonical goal hash + status/event consistency
  -> event-bound ProverWorkspaceView carrier
  -> ManagedGoalViewManager
  -> project_current_workspace_view
  -> optional P4-admitted compiler Markdown
  -> current turn-presentation backend
       current_turn_contract
       current_turn_composer
       current_turn_markdown
       exact goal + manager outcome/control menu + byte-identical compiler block
```

The current path has the following negative contract:

- it cannot import the removed `core.easycrypt.analysis` tree;
- it does not build the old text-derived GoalIR/ProgramIR/ProofIR;
- it cannot run the removed analyzer or rich renderer trees;
- it does not assemble a full hidden workspace and then strip panels; and
- its audit copy is the same lean projected view, not a secret rich view.
- its worker, agent prompt, MCP schema, turn composer, and Markdown renderer do
  not import `WorkspaceViewManager`, `workflow.surface_profiles`,
  `surface_composer`, `surface_model`, or `surface_turn_model`.

The durable managed goal artifact contains only the current carrier required by
the current turn contract. It has no hidden rich-view twin.

Current surface identities and their matched controls are owned only by:

```text
workflow/proof_state_compiler/profile_ids.py
workflow/proof_state_compiler/surface_contract.py
workflow/proof_state_compiler/surface_profiles.py
workflow/proof_state_compiler/current_turn_contract.py
workflow/proof_state_compiler/current_turn_composer.py
workflow/proof_state_compiler/current_turn_markdown.py
workflow/proof_state_compiler/current_turn_presentation.py  # public facade only
core/easycrypt/proof_state_compiler/backend/presentation.py # sole compiler renderer
```

`eval_suite.run` and the orchestrator accept only the current registry. Retired
suite JSON lives under report archives and is rejected as executable input.
Unsupported profile IDs fail closed; there is no lazy non-current dispatcher,
ordinary rich-view debug path, or compatibility adapter.

The retained event/session/manager/checkpoint foundation is intentionally not a
deletion target. It supplies neutral proof-state authority used equally by L1
and compiler arms. Historical reports and offline historical-run parsers may
name retired fields, but they do not define or import runtime capabilities.

### EasyCrypt revision contract for N-series work

The **N-series is a native-integration programme and is therefore revision
bound at its EasyCrypt-facing edge**.  N0.5/N1 adapters compile against
EasyCrypt OCaml types and, where no stable public export exists, selected
internal modules.  N2 checkpoints then prove that an M/B feature consumes
those native results.  An N checkpoint is not portable evidence for an
arbitrary `easycrypt.dev`, a moving `main`, or another commit with a similar
printed CLI.

That dependency stops at the native boundary:

| Layer | Revision policy |
|---|---|
| EasyCrypt source, executable, `ecLib`, native companions | Must match one repository-locked, audited upstream revision and its declared native-adapter ABI. |
| Native request/result transport and projection lowering | Versioned Shannon contracts; an EasyCrypt upgrade requires adapter parity tests and an explicit contract migration when the exported shape changes. |
| Shared `ProofIR`, feature eligibility, admission and delivery | EasyCrypt-version-neutral. They consume stable native-derived meaning and must not branch on upstream commits or OCaml constructors. |
| Mechanical-work evidence and experiment claims | Lemma/agent evidence remains historical, but native trigger/parity and no-mutation gates must be rerun after every EasyCrypt revision change before new efficacy runs. |

Shannon deliberately supports **one locked EasyCrypt revision at a time**.
There is no silent multi-version compatibility layer and no fallback to old
text parsing.  A missing lock, a runtime/library revision mismatch, an
unidentifiable `n/a` build, or an adapter compiled against a different ABI
fails before feature analysis.  Upgrading EasyCrypt is a foundation
checkpoint: update the lock and source audit, rebuild executable and `ecLib`
together, migrate affected adapters, rerun N1 sentinels, and then reopen the
affected N2 feature gates.

The current lock is the official EasyCrypt **`r2026.06`** release at exact
commit `1c7e6d78eb1cfb44a4c98e00e1b5ef8b5bfd30c9`, recorded in
`core/easycrypt/easycrypt.lock.json`. The repository vendors that exact source
snapshot and hashes its full path/byte manifest. `tools/bootstrap_easycrypt.py`
builds it with the lock's exact OCaml compiler package in a project-local opam
root and writes an ignored receipt binding
the lock identity to both the EasyCrypt executable SHA-256 and `ecLib.cmxa`
SHA-256. Runtime calls and native companions independently verify those two
artifacts against the same receipt. Python entry points do not consult an
ambient opam switch.

Receipts are host-specific because executable and native-library bytes differ
across macOS and Linux. Cross-machine parity requires the same committed lock,
release, upstream source commit, vendored source manifest, and native-adapter
ABI; it does not require cross-platform binary hashes to be equal. Within one
host and every A/B arm, executable and `ecLib` hashes must agree exactly with
that host's receipt.

`EcVersion.hash` is not treated as an ecLib ABI identity: when an external
companion links the release library, Dune build-info can report `n/a` even
though the EasyCrypt executable from the same installation reports
`r2026.06`. The executable build ID remains a lock check; executable/ecLib
agreement is established by the joint cryptographic receipt, not by comparing
an unstable package label.

The local/remote N2b.3 discrepancy exposed this contract debt: the earlier
local sentinel used installed commit `641f178...`, while the remote rsync-pinned
`easycrypt.dev` exposed the newer exceptional-postcondition API.  Therefore
the N2b.3 feature migration is implemented. The locked-version foundation and
local adapter migration are now complete; remote must bootstrap and verify the
same lock before the cross-machine native gate is rerun. The earlier failed
remote run remains environment/foundation evidence, not N2b.3 efficacy
evidence.

Python parsing and structural matching may be used as a measured candidate
discovery optimization. Such a result is a lexical sketch, not a native typed
fact. It may narrow a native query, but it may not establish type
compatibility, module compatibility, proof-premise matching, placeholder
solvability, or application validity.

Current implementation status must not be overstated. B1 namespace repair,
B2 losslessness/module repair (including bounded one-module calls with
one or two deferred proof premises), and the frozen probability/multi-slot
B2/B4 recovery consume
event-bound native proof-term descriptors before forming actions. Python
declaration parsing, token alignment, and proof-fact
ranking remain only bounded candidate sketches; their values are never
exposed as checked slots. A visible action requires the descriptor policy plus
mandatory exact EasyCrypt preflight. The native boundary is one
manager-internal, event-bound, read-only semantic adapter over the current
proof environment. Typed goal/program state, effects, frame, restriction,
call, `seq`/`sim`, arithmetic, normalization, and search all obey that same
source-level ownership boundary.

Runtime identity is an implemented prerequisite to that adapter. A new
managed session records EasyCrypt's self-reported build ID and exact executable
SHA-256 in session metadata and the `session.started` event. Every live
compiler-input occurrence rechecks stored/start-event/current-executable
agreement and transports the canonical identity into
`CompilationEnvironment`; whole-result, material-state, and resource cache
keys include it. Sessions predating this contract restart rather than silently
adopting the currently installed binary. An A/B bundle is comparable only when
all arms report the same runtime identity.

The shipped CLI/`-emacs` protocol does not provide a structured proof-term
elaboration or `apperror` endpoint. The Python daemon is a persistent transport
over that textual protocol, not a native semantic export. N1a therefore adds a
repository-local, read-only OCaml companion linked to the installed
`easycrypt.ecLib`. It replays the exact manager context/prefix, checks the
replayed goal, calls `EcProofTerm` in current `tcenv1`, and emits an
event/artifact-bound structured result. This process/event foundation is
implemented for exact `apply`, `exact`, and named `call` terms.

N1b is implemented as a feature-neutral P3 dependency cycle: an active feature contributes bounded
`NativeSemanticRequest` producers; the compiler creates one plan and executes
all requests for one `StateRef` as one ordered native batch; the manager
returns one event-bound batch whose members become `NativeSemanticObservation`
values; P2 rebuilds the same
`ProofIR` with those observations before ordinary P3 analysis. A request is
discharged only by the same request ID and complete request identity hash.
Multi-round dependency discovery, cross-state results, build drift, and missing
event authority fail closed. The shared contracts contain no M05/M15 fields.

Activation owns feature-requested native work at the producer level: OFF features contribute no
native request and perform no native process work; audit and treatment run the
same compiler/native/certification path and differ only at delivery. The
native proof-state projection is different: it is mandatory P1 authority for
every open state, not feature-requested work. Open states never reuse a whole
compiled bundle because that would retain an old native event provenance;
materially identical verifier certifications may still use their separate
bounded cache.
Telemetry records the plan, runtime/companion identities, status, provenance,
and elapsed time. The four-family source audit established the mandatory
sequence N1c typed-state export -> N1d native P1/P2 lowering -> N1e proof-term
descriptors -> N2 feature migration. N1c-N1e, N2a M05, and N2b.1-N2b.3
application migrations are complete locally. The frozen remote N2b.3a
trigger/parity sentinel is the current gate before a new efficacy cohort.

N1c is implemented as a second feature-neutral native endpoint. It exports
the focused typed goal, `LDecl` locals, statement/instruction/expression trees,
native judgment/procedure identity, structural paths and explicit
complete/truncated status. The result has the same runtime, input-hash,
canonical-goal, event/artifact and no-mutation authority as N1a. N1d now joins
one such occurrence to every open compiler input and lowers it into `GoalIR`,
`TypedTermIR`, local `ProofFact`, `ProgramStatement`, and `ProofCoordinate`.
The V2 pretty-text goal/program semantic parsers and the empty
`verifier_scope`/`program_snapshot` input fields are deleted. Incomplete native
projection makes consuming P2 capabilities abstain; it never reactivates text
inference.

N1e extends the feature-neutral proof-term endpoint with an immutable
`NativeProofTermDescriptor`: native resolved head, ordered formula/memory/
module/proof arguments, inserted implicit count, allowed residual proof
premises, concretization status, and native result judgment. The descriptor is
event-bound and lowered into shared `ProofIR`; it neither enumerates candidates
nor selects a proof route.

The current proof-term protocol additionally carries an EasyCrypt-native
result/current-goal convertibility fact. It is computed over the concretized
result and current `tcenv1` goal with native hypotheses and compatible
reduction; printer text remains audit material only. Protocol v4 accepts one
bounded ordered request batch, replays context/history once, isolates semantic
rejection per member, and emits one authoritative batch result. There is no
single-request compatibility endpoint. Native-adapter ABI remains 2 because
the pinned r2026.06 OCaml interfaces did not change; Shannon transport schema
and upstream native ABI are independent version axes.

Typed-state protocol v2 also exports the structured module path for each
probability procedure. Shared middle-end code may collect only exact leaf
module terms and probability-boundary memories from that native AST. A feature
may enumerate a complete bounded product of those spellings, but it may not
match theorem conclusions to goals in Python. For B24 the pool is capped and
every member is sent through one ordered native proof-term batch; zero or multiple
native-convertible survivors make the feature abstain. This is Shannon's
bounded search contribution, while module typing/restrictions, proof-term
matching, and result/goal convertibility remain EasyCrypt-owned.

N2a connects the first production consumer. M05 performs only bounded lexical
resource/application discovery, asks EasyCrypt to elaborate the exact
`Alossless_F` application, and admits a binding only when the native head,
module/proof slots, one residual losslessness premise and canonical result
procedure satisfy the frozen feature policy. Source-local syntax is query
spelling, never identity authority. The old M05 feature-local semantic binder
is deleted.

N2b.1 connects the first commitment-relative recovery consumer. B1 keeps the
exact attempted operation and selected basename, permits only a unique
namespace-only correction of a bare proof-term head, and requires EasyCrypt to
return the resolved global head before lowering. Attempts with arguments
abstain rather than dropping or rewriting them lexically. The old Python
namespace binder is deleted.

N2b.2 migrated the first B2 losslessness/module family. Direct `apply` accepts only
the exact failed bare commitment and requires native result/current-goal
convertibility. The exact unqualified two-hole `call` family consumes the
native parsed argument kinds, certificate/callee descriptor, and complete-call
preflight; it does not reparse the raw tactic or compare printed module
identities in Python. Native side/position qualifiers abstain because the
lowered correction does not preserve them. Both paths use
declaration/procedure syntax only to spell one bounded query. An explicit
proof hole makes EasyCrypt return the typed residual premise; the descriptor
owns the head, slot kinds, canonical module identity, premise, and result
procedure. The shared old Python losslessness binder is deleted after a
zero-consumer audit.

The later bounded extension preserves that architecture and owner while
admitting a selected certificate with one module slot and one or two ordered
losslessness proof premises. Python may spell the unique structural module
candidate and retain declaration order; EasyCrypt still owns the exact head,
canonical module, residual premises, and callee result, followed by unchanged-
state exact tactic preflight. Bare and all-placeholder calls are eligible;
concrete arguments, other slot kinds, more than two proof premises, ambiguity,
or descriptor drift abstain.

The later theorem-start audit exposed a different B2 subtype: the agent had
already written the exact `call`, certificate, concrete first module term and
remaining suffix, but omitted EasyCrypt's `(<: M)` module grammar. The ML
adapter may formulate one native query by inserting only that punctuation.
The feature package independently reconstructs the same transformation from
the exact rejected text and requires resource, module term, suffix and full
candidate identity before native proof-term elaboration. The same head, native
first module slot and ordinary exact unchanged-state preflight remain
mandatory. This stays inside `operation_binding_repair`; arbitrary or
ambiguous parse errors abstain.

Native semantic protocol/artifact schema 14 is canonical rather than
branch-local. Every attempted-operation payload includes both mutually
exclusive nullable fields `intro_pattern_realization` and
`application_syntax_repair`. Every batch member also carries an exact
`evaluation_prefix`: normally empty, or the native-confirmed source prefix of
one compound-boundary handoff. No earlier-schema compatibility path remains.
Successful responses and top-level error envelopes report schema 14.

Native companion stdout is a framed transport, not a bare JSON assumption.
EasyCrypt commands replayed from the source may themselves print text, so each
companion emits one kind-specific prefixed result frame and the Python boundary
requires exactly one occurrence. Missing, duplicate, malformed, wrong-build,
wrong-request, or wrong-goal results fail closed.

The adapter is a migration of semantic ownership, not a fifth compiler pass:

```text
P1 exact state + P2 bounded candidate/resource request
  -> native EasyCrypt elaboration in the same proof environment
  -> native-derived P2/P3 transport values
  -> feature predicate and generic lowering
  -> exact native tactic preflight
  -> admission and presentation
```

Legacy Shannon goal parsers, inspect-panel analyzers, and compatibility
adapters are not fallbacks. A needed computation must come from native
EasyCrypt or be redesigned as a new v2 lexical/planning computation with an
explicit non-authoritative status.

The historical `analysis/ec_native_state.py` overlay is physically deleted.
There is exactly one typed goal/program implementation:
`native_semantics/native_state_projection_adapter.ml` transported and
event-bound by `session_native_state.py`. The remaining `-goal-json` and
`-program-json` commands are display-only human/debug projections and cannot
populate a `NativeProofStateSnapshot`.

Native adapters remain runtime infrastructure rather than feature slices.
Typed proof-state projection enriches P1; proof-term, effect, tactic-preview,
normalization, and typed-search queries serve bounded P2/P3 dependencies; and
exact tactic certification remains P4 authority. Active feature capabilities
control whether each producer runs, so OFF removes both semantic work and
cost without teaching the manager any M identifier.

## 2. One architecture, three independent axes

Two concepts must never be conflated again.

### Compiler passes

P1-P4 are permanent implementation stages:

1. P1 State Projection
2. P2 ProofIR Frontend
3. P3 Resource and Binding Analysis
4. P4 Action-Surface Backend

Every admitted feature travels through this same pipeline.

### Experiment arms

L1, audit, and treatment use the same manager, proof runtime, controls, model,
topology, source contract, and budgets. They intentionally differ at the
compiler boundary:

| Arm | Compiler service | Dependency load / certification | Agent exposure |
|---|---|---|---|
| L1 | absent | absent | none |
| feature audit | present | activation mode `audit` | none |
| feature treatment | identical pass/certification set to audit | activation mode `treatment` | admitted feature only |

This three-arm design separates total hidden compiler cost (`audit - L1`), the
behavioral effect of exposure (`treatment - audit`), and net harness value
(`treatment - L1`). A declarative profile is resolved once into an immutable
`ActivationPlan`. Audit and treatment select the same complete feature
definitions for dependency loading, P2, P3, P4, and certification; only
treatment admits delivery. No pass has an independent human-facing feature
switch.

### Delivery triggers

Delivery is independent of both passes and experiment arms. A compiled fact
may remain silent, answer one explicit query, elaborate one agent-selected
proof operation, or repair one current-state failure. These are backend
lifetimes over the same typed candidates; they are not four feature
architectures.

The trigger classes are:

```text
StateRefresh
ExplicitContextRequest
AgentSelectedOperation
CurrentStateFailure
```

Delivery eligibility is not permission to execute every active feature on
every turn. Before compiler input, native projection, loading, P1-P4, or
certification, the service resolves a cheap invocation execution plan from the
same active feature definitions and event-bound turn evidence. A recovery-only
feature whose required `CurrentStateFailure` is absent is not executed merely
because its audit/treatment profile is enabled.

Execution gating remains feature-pluggable and manager-agnostic:

- the manager still calls only `compile_current_state()` and knows no feature;
- each feature definition declares its required trigger class and optional
  bounded syntactic prefilter;
- audit and treatment resolve the same executed feature set;
- a combined profile executes only features eligible for this occurrence;
- no eligible feature means a typed generic skipped result with no projected
  `ActionSurface` payload and zero compiler input/native/loading/P1-P4/
  certification calls; and
- after a terminal delivery or abstention decision, the same exact occurrence
  does not repeat expensive producers.

The prefilter has no semantic authority. It may only avoid work. A positive
decision still enters the complete authoritative compiler path and all native
and certification checks fail closed. `operation_binding_repair` therefore
runs only for a current unchanged rejected/no-progress tactic occurrence whose
strict cheap classifier is in the supported B1/B2/B4 family. Initial state,
successful tactics, control/malformed turns, and unrelated failures do not
start its native projection, declaration loading, proof-term elaboration, or
exact certification.

The current implementation expresses this boundary with
`FeatureExecutionGate -> FeatureExecutionPlan` before P1. Each decision names
its stable gate, bounded trigger class, reason, and execution lifetime.
`once_per_turn_occurrence` records only successfully completed invocations in
a bounded service-local ledger; a compiler exception is not terminal and is
therefore retryable. Standing `StateRefresh` consumers remain repeatable. The
service selects the eligible feature subset, so an unrelated recovery slice
does not run merely because another feature in a combined profile is eligible.

`StateRefresh` is byte-silent by default, except for an economical intrinsic
delta whose production treatment has been separately authorized. It is not a
general route-advisory trigger. The fact that only one registered candidate
exists, or that EasyCrypt accepts it, does not prove route neutrality. This
branch contains no proactive exception, SC2 producer, delivery rule, or
profile. The frozen M05 research exception is maintained only on the private
`compiler-proactive` branch.

### Strategy ownership boundary

The strategy classification is a permission boundary, not a menu of three
equally supported output types:

| Class | Compiler role | Production disposition |
|---|---|---|
| SC0 `intrinsic` | Derive a fact uniquely from authoritative state | May stay internal or enter an evidence-gated compact delta/query |
| SC1 `commitment_relative` | Check, bind, elaborate, or repair the exact operation/resource/contract already selected or attempted by the agent | May enter D2/D3 while the exact commitment anchor is current |
| SC2 `route_selecting` | Foreground, rank, synthesize, or choose an uncommitted theorem, invariant, midpoint, witness, transform, normalizer, or proof route | Reject/abstain; retain the research idea and provenance in the ledger only |

`HOLD` for an SC2 idea means **not implemented in production code**. It does
not mean “implement the producer and hide its output.” There is no feature
directory, resource-loading request, P2/P3 producer, candidate lowerer,
certification work, or dormant profile unless an active SC0/SC1 consumer needs
that exact shared capability. This rule currently excludes proactive M03
opener selection, M06 bridge selection, M08 invariant/frame synthesis, M14
normalization-route selection, M23 union-bound/measure selection, and M24
arithmetic-lemma bundles.

Mixed ideas must be split. For example, invariant synthesis is absent, while
checking whether a previously accepted invariant conjunct was dropped may be
an SC1 retention feature. Selecting a union-bound route is absent, while
repairing the exact union-bound theorem application already attempted by the
agent may be SC1.

Consequences for the current codebase:

- keep M05 physically absent from `main`; its frozen implementation and
  evidence harness belong only to `compiler-proactive`;
- remove or disable M07's state-only proactive producer/profile, while keeping
  its generic declaration parser, application signature, proof-slot binder,
  lowerer, and certifier only where an SC1 selected-operation or same-resource
  recovery consumer uses them;
- do not create producers/profiles for the route-selecting portions of M03,
  M06, M08, M14, M23, or M24; and
- retain `optional_advisory` only as a schema-level rejection vocabulary; no
  helper, feature, policy, or profile on `main` may construct it.

### Runtime authority prerequisites

The compiler begins only after the managed runtime has produced one canonical
proof-state projection. These are foundation contracts, not feature passes:

```text
closed goal identity
  goal_identity_required = false
  active_goal_hash = ""

open goal identity
  goal_identity_required = true
  active_goal_hash = hash(canonical non-empty active-goal body)

authoritatively open source goal for exact certification
  goal.state_kind = open
  goal.proof_candidate_closed = false
  goal_identity_required = true
  active_goal_hash is non-empty
  event contract and projection consistency are valid

current candidate close
  whole event and consistency contract is valid
  latest tactic.result(candidate_closed = true)
    immediately paired with proof.candidate_closed
  or that exact pair preserved by the immediately following saved qed transition
```

The aggregate projection `status` may remain `error` after a rejected tactic
while the unchanged current source goal satisfies the open-goal contract.
Certification and preflight use the orthogonal source-goal facts above; they
must not reinterpret that aggregate transition diagnostic as goal liveness.
Historical close counts, display status, an unpaired `goals_after=0`, an empty
text hash, and a raw-file hash are never semantic substitutes. Projection or
pairing failure may suppress candidate readiness; it may not invent a fallback
identity.

## 3. End-to-end dataflow

```text
EasyCrypt session
  |
  | compiler.input.produced + hash-bound artifact
  v
InputGateway                         workflow authority boundary
  |
  | AuthoritativeSnapshotInput + CompilationEnvironment
  | + event-bound CompilerTrigger
  v
ExactStateCache                     service optimization, not a compiler pass
  | miss: continue through P1-P4 and certification
  | hit: reuse the prior immutable bundle/certification for this exact state
  v
FRONTEND
  NativeSemanticGateway            target P1 typed-state enrichment
  | current tcenv1 -> native goal/local-context/program projection
  | exact StateRef + native build/event identity; no mutation
  v
  P1 StateProjector
  P2 dependency discovery
  |  DeclarationLoadRequest[]
  v
ResourceEnvironmentCache           incremental-frontend optimization
  | hit: reuse immutable hash-bound declarations only
  | miss: runtime resolves bounded namespaces and emits a fresh,
  |       hash-bound compiler.resources.loaded occurrence tied to the
  |       original compiler input and exact StateRef
  v
  P2 base ProofIR + ResourceDiscoverers
  |
  v
NativeSemanticGateway              proof-term descriptors implemented; consumers migrate in N2
  | current proof environment + bounded ordered proof-term request batch
  | native head/argument/matching/concretization result or structured error
  | exact StateRef + native build/event identity; no mutation
  v
  P2 ProofIR rebuild
                                    native-derived semantics or explicitly
                                    lexical/non-authoritative sketches
  |
  | ProofIR
  v
MIDDLE END
  CoordinateAnalysis                    one canonical ProofCoordinate
  ResourceAnalysis
  BindingAnalysis
  FeatureAnalysisProducers              consume ProofCoordinate; never reparse it
  |
  | AnalyzedProofState
  v
BACKEND
  P4 SurfaceLowerers
  |
  | CandidateSurface                 internal, never rendered
  v
CertificationGateway                read-only EasyCrypt checks
  |
  | CertificationResults
  v
AdmissionPolicy                     trigger + manifest + evidence gate + budget
                                    + bounded lifetime snapshot
  |
  | ActionSurface                    compiler's only agent-facing output
  v
SurfaceTurnModel                    goal + action surface + result + controls
  |
  v
agent chooses one proof intent
```

`CandidateSurface` is the internal P4 output. `ActionSurface` is the final
paper-facing compiler surface after certification and admission. There is no
third surface layer between them. `SurfaceTurnModel` is the manager's complete
turn envelope and is not a compiler pass.

The manager calls exactly one facade.  The implemented delivery-aware signature
is:

```python
ProofStateCompilerService.compile_current_state(turn_evidence=None)
```

The no-argument form binds `StateRefresh` to the exact authoritative compiler
input event. A completed manager turn may additionally supply one
`CompilerTurnEvidence` carrying the complete post-turn `StateRef`; the service
accepts it only when that `StateRef` equals the fresh compiler input exactly.
For an authoritative accepted/rejected `commit_tactic` occurrence, the generic
delivery contract constructs an `AgentSelectedOperation` or
`CurrentStateFailure` trigger. The exact event occurrence participates in its
trigger and commitment-anchor identity, so repeated equal payloads do not
collapse. The manager still knows no feature IDs, resource families, tactic
syntax, certification methods, byte budgets, or evidence-ledger ordinals.
Informal intent strings cannot act as commitment anchors.

Goal identity is also single-owner. One `ProofStateProjection` read produces
the exact goal text, hash, and explicit open/closed identity class. Workspace
v3 projects those values into `proof_status`; `ProofStateSnapshot`, manager
caches, turn evidence, compiler input, and `StateRef` consume them without
status inference or display-text fallback. Candidate readiness is a separate
event-authority claim and requires the latest close occurrence. The complete
owner matrix follows the fail-closed rules in this section.

Every facade invocation still reads and validates a fresh event-bound compiler
input. After that authority boundary, the service owns three bounded reuse
caches with deliberately different identities—exact observation, material proof
state, and resource environment—plus a bounded ledger of presentation IDs.
They are not MCP/model conversation caches and none is a fifth compiler pass.

The separation is semantic. A manager view refresh changes observation
identity without necessarily changing EasyCrypt proof state. An accepted
tactic normally changes proof state without changing the source environment.
P1-P4 therefore rebuild current-state objects for every new observation;
expensive exact-tactic certification may be reused only after a fresh complete
material-state equivalence check; immutable hash-bound declarations may be
reused across materially different proof states in the same environment.

## 4. Package boundaries

The current first-slice physical layout is:

```text
core/easycrypt/proof_state_compiler/
  contracts/
    state_ref.py                   StateRef and provenance
    environment.py                 loaded source/index authority
    projected_state.py             P1 output
    native_state.py                event-bound native typed-state source
    proof_ir.py                    shared P2 domain model
    analyzed_state.py              shared P3 domain model
    application_applicability.py   state/population-bound application assessment
    candidate_surface.py           internal P4 candidates
    certification.py               certification requests/results
    strategy.py                    SC0/SC1 permission contracts + SC2 rejection classification
    delivery.py                    triggers, anchors, rules, and lifetimes
    delivery_policy.py             registered policy + aggregate surface budget contracts
    action_surface.py              final agent-facing compiler output
    compilation.py                 audit bundle

  frontend/
    state_projector.py             runtime/native authority join -> P1
    native_state_lowering.py       sole native-schema owner; typed state -> P2
    fact_parser.py                 source-declaration lexical candidates only
    declaration_stream.py          uniform source/resolved declaration input
    resource_loading.py            structured P2 dependency-request aggregation
    resource_discovery.py          discovery protocol and aggregation
    resource_syntax.py             loaded declaration scanning primitives
    proof_ir_builder.py            P2 assembly

  syntax/
    formulas.py                    shared relation/judgment syntax
    attempted_operation.py         bounded operation/resource syntax
    module_terms.py                non-authoritative source-spelling candidates

  middle_end/
    coordinate.py                  current semantic/program coordinate
    contributions.py               structured feature analysis contributions
    resource_analysis.py           liveness/applicability protocol
    application_applicability.py   exact native-plan/observation applicability join
    procedure_binding.py           lexical procedure candidate narrowing
    native_application.py          native descriptor -> shared application IR
    proof_slot_binding.py          lexical fact candidate scoring
    binding_analysis.py            binding transport aggregation
    recovery_ownership.py          exact failure-occurrence claim resolver
    analysis_pipeline.py           P3 assembly
    diagnostics/application.py     assessment -> bounded diagnostic rendering
    diagnostics/argument_alignment.py
                                   native head slots -> factual layout only

  backend/
    application_lowering.py        structured application -> exact tactic
    surface_lowering.py            generic P3 -> CandidateSurface aggregation
    admission.py                   evidence/strategy/trigger/lifetime/budget policy
    action_surface.py              Candidate + certifications -> ActionSurface

  features/
    registry.py                    FeatureSpec + immutable FeatureCatalog
    catalog.py                     only production feature composition root
    losslessness_certificate_application/
      resource_discovery.py        losslessness declaration discovery
      candidate_discovery.py       bounded lexical native-query planning
      native_binding.py            native descriptor policy/transport
      surface_lowering.py          register generic application lowering
      feature.py                   one registration bundle
    operation_binding_repair/
      resource_loading.py          exact attempted-resource request
      resource_discovery.py        shared declaration/signature parsing
      namespace_repair.py          native B1 namespace-only family
      losslessness_module_repair.py native B2 losslessness/module family
      losslessness_call_repair.py  native B2 bounded one-module call family
      application_module_syntax_repair.py native B2 selected-call grammar family
      probability_multislot_repair.py bounded spelling -> native B2/B4 descriptor
      analysis.py                  thin native-family dispatch
      surface_lowering.py          uniquely owned repair lowering
      feature.py                   independent SC1 semantic slice
    pure_tail_recovery/
      syntax.py                    plain selected-rewrite lexical gate
      native_attempt.py            exact failure-bound native request
      analysis.py                  unique-target claim and preservation witness
      surface_lowering.py          one certified `Do you mean?` action
      feature.py                   removable SC1 semantic slice
    intro_pattern_repair/
      syntax.py                    bounded failed nested-`move` lexical gate
      native_attempt.py            exact failure-bound native request
      analysis.py                  ordered-binder realization witness and claim
      surface_lowering.py          one certified `Do you mean?` action
      feature.py                   removable SC1 semantic slice

  compiler.py                      pure P1-P4 orchestration
  serialization.py

workflow/proof_state_compiler/
  activation.py                    off/audit/treatment profile + derived plan
  delivery_policy.py               independent policy-plan resolver
  delivery_policies.py             production treatment policy catalog
  assembly.py                      atomic activation+delivery composition
  input_gateway.py                 event-bound live input conversion
  cache.py                         observation, certification, resource reuse
  lifetime.py                      bounded presentation IDs only
  certification_gateway.py         manager-owned read-only EasyCrypt checks
  manifests.py                     generic evidence-gated manifest construction
  profile_ids.py                   public profile identities only
  profile_registry.py              production composition root + shared contract
  release_manifest.py              public profile/feature/policy allowlist
  configuration.py                 lazy production/research assembly projection
  presentation.py                  generic delivery copy shared by runtime/micro
  service.py                       compile_current_state() facade
  native_semantic_gateway.py       target feature-agnostic request dispatch
  telemetry.py

workflow/validation/
  proof_state_compiler_research_profile_ids.py
                                   private audit/ablation identities
  proof_state_compiler_research_profile_registry.py
                                   private research composition root
  proof_state_compiler_research_feature_catalog.py
                                   private superset for reproducible experiments

core/easycrypt/native_semantics/   shared runtime boundary, not a compiler pass
  native_proof_term_adapter.ml     implemented bounded batch proof-term endpoint
  proof_term_adapter.py            implemented process/build validation
  native_state_projection_adapter.ml
                                   implemented N1c typed-state endpoint
  state_projection_adapter.py      implemented process/schema validation
  tactic_preview_adapter.*         target only for admitted SC1 consumers
  typed_search_adapter.*           target only for an admitted requested-search consumer

core/easycrypt/compiler_resource_loader.py
                                   manager-internal EasyCrypt namespace resolver
```

The package names are architectural roles. Feature code is not allowed in
`manager`, `renderer`, or shared contracts merely because one experiment needs
it.

The proactive `losslessness_certificate_application` package is absent from
`main`; there is no alias or compatibility package. M05 remains here only as
historical evidence-ledger provenance. Its executable slice is maintained on
`compiler-proactive`.
The proactive `probability_theorem_application` package and profiles are
removed. Its declaration/signature parsing, proof-slot binding, generic
application lowering, and certification path remain shared infrastructure and
are used by the SC1 `operation_binding_repair` slice.

## 5. Contracts by stage

### 5.1 P1 State Projection

P1 answers: which exact verifier state is current?

Input:

- one current-call, event-bound compiler input occurrence;
- exact goal and open-goal state;
- session, target, state version, goal identity, and committed-prefix identity;
- validated transition and adoption lineage; and
- EasyCrypt runtime identity. Declaration resources are a distinct P2
  occurrence and never enter the P1 state artifact.

Output: immutable `ProjectedProofState`.

Invariants:

- every output corresponds to exactly one `StateRef`;
- no old error, probe after-goal, rolled-back fact, or sibling-session fact is
  merged;
- missing authority fails closed;
- P1 performs no goal classification, resource discovery, or recommendation;
- all downstream objects retain the same state and source occurrence.

#### Observation and material-state reuse contract

Repeated rejected tactics and view refreshes can advance manager
`state_version` while leaving the EasyCrypt state unchanged. Treating that
version as both observation identity and proof semantics caused every managed
compiler call to miss and repeat speculative EasyCrypt checks. The service now
uses three non-interchangeable identities:

| Cache | Identity | Reuses | Must miss when |
|---|---|---|---|
| Exact observation | complete `StateRef`, exact snapshot/environment, selected pass/certification feature sets | immutable P1-P4 bundle plus certifications, never presentation | `state_version` or any material/compilation configuration field changes |
| Material proof state | session/target, goal identity and exact goal, committed prefix/history, verifier scope, program snapshot, source/declaration hashes, exact eligible candidate payload/policy | exact-tactic verifier witness only | any proof, source, candidate, or certification-policy fact changes |
| Resource environment | session/target, source hashes, canonical load requests, producer feature set | immutable loaded declarations and their original reports | source, request, target, feature set, or declaration authority changes |

Every lookup starts after a fresh current-call `compiler.input.produced`
occurrence. `state_version` and per-read event/artifact occurrence IDs are
excluded only from the material proof-state fingerprint. They remain part of
the exact-observation identity. Session lineage, goal identity/text/count,
closedness, committed-prefix identity and history, verifier/program snapshot,
and all source/declaration hashes remain material and fail closed on drift.

On a new observation of an unchanged material state:

1. P1-P4 run again and every output carries the new `StateRef` and current
   compiler-input provenance.
2. Candidate identity, intent, payload hash, unresolved premises, policy, and
   eligible feature set are checked against the cached certification set.
3. Reuse is legal only when the old set completely covers the current eligible
   candidate set. Partial/unknown gateway output is never cached.
4. The current `CertificationResult` keeps the original `verification_ref` and
   carries a `CertificationReuse` record containing the material-state hash,
   origin `StateRef`, origin input event, and current input event. No new
   verifier event is invented.
5. Admission runs against the current P4 candidate and current `StateRef`.

The exact-observation cache remains a fast path for repeated service calls at
the same manager observation. It first validates a fresh input and then may
return the immutable original bundle/provenance because the complete
observation key, including `state_version`, is equal. Every path rechecks that
the compiler call changed neither committed history nor manager state version.

Telemetry reports exact-observation, material-certification, and resource
caches separately. It distinguishes new certification work (`performed`) from
reused verifier witnesses (`reused`) and records both origin/current event IDs
for material-state reuse.

#### Resource-environment reuse contract

The post-cache M07 managed repeat showed that an exact-observation cache is
necessary but not sufficient: 255 ordinary managed compiler calls produced
255 misses, while 59 dependency requests repeatedly loaded the same
hash-bound theorem declaration.  Audit and treatment directly spent 379,296 ms
of loader wall time.  Resource loading is therefore an incremental-frontend
concern, not a proof-state result cache and not an MCP/model cache.

`ProofStateCompilerService` maintains a bounded cache whose material key is:

- the manager-owned session and target identity;
- all source-unit refs and SHA-256 values;
- the complete canonical `DeclarationLoadRequest` set, including producer,
  query kind, scope or exact symbols, declaration kinds, structural name terms,
  and budget; and
- the registered compiler feature identities that produced the plan.

An entry contains immutable `LoadedDeclaration` values, their original
verifier-resolved source refs and hashes, the original load report, and the
origin environment ID. A hit is legal only after a fresh current-call
`compiler.input.produced` occurrence confirms the same session, target, and
source hashes. Reuse does not mint a new verifier event and does not rewrite
declaration provenance. The current state event remains the authority for P1;
the original `compiler.resources.loaded` occurrence remains the authority for
the cached resource.

On a resource-cache hit:

- dependency planning still runs against the fresh state;
- runtime declaration loading is skipped;
- P2 receives a new current-state `CompilationEnvironment` containing the
  immutable cached declarations;
- P2-P4 and admission run normally; certification either runs or reuses a
  material-state witness under the independent contract above; and
- telemetry distinguishes performed loads from reused declarations.

Any source hash, target, request, feature set, or declaration hash drift is a
miss.  Cache entries are service-instance/session scoped and bounded; there is
no cross-node or cross-evaluation global cache.

The request object owns one `identity_payload()`. Runtime submission and the
resource-cache key consume that representation instead of independently
listing request fields. Adding a new material query field without changing the
cache identity is therefore a contract-test failure.

Failure occurrence identity is deliberately absent from that material request
identity. The current failure event remains in `EvidenceRef`,
`AttemptedOperationIR.recovery_key`, recovery ownership, trigger, and delivery
lifetime. The declaration request ID is derived only from its producer, query,
and exact symbol set. Likewise, an exact-action candidate ID is derived from
its material target and payload, while its `trigger_id` retains the current
failure occurrence. This permits declaration and verifier-witness reuse across
two authoritative rejected occurrences without pretending they are the same
recovery event.

### 5.2 P2 ProofIR Frontend

P2 answers: what proof-domain structure, bounded candidates, and
native-derived resources exist at this state?

`ProofIR` is a typed Shannon transport contract, not evidence that its contents
have been EasyCrypt-typechecked. Every semantic value must distinguish native
derivation from lexical candidate planning. During the native-adapter
migration, existing declaration-parsed signatures are provisional sketches
and cannot support an agent-visible binding claim without exact native
certification.

`ProofIR` uses proof-domain concepts, never feature-specific result fields:

```text
GoalIR
  goal kind, exact normalized formula, top-level relation, bound,
  pre/postcondition

ProofFact
  name, structural ProofJudgment, origin (current context or loaded source),
  exact evidence

ProgramStatement
  side, position, statement kind, qualified procedure identity

ProofResource
  canonical resource identity, declaration kind, ProofJudgment conclusion

ApplicationSignature
  ordered transport of native-derived ArgumentSlot values for module, term,
  formula, type, memory, proof, or implicit inputs; a declaration-text parser
  may produce only a lexical sketch, never a native typed signature
```

Resource discoverers consume one uniform declaration stream. A declaration may
come from a hash-checked source unit or a verifier-resolved, hash-bound
`LoadedDeclaration`. Discoverers contribute `ProofResource` objects to shared
IR; no feature may add a feature-named result field to `ProofIR`.

P2 dependency discovery is part of the frontend driver, not a fifth compiler
pass. The service activates dependency producers only for feature IDs in the
manifest's certification set. Therefore L1 performs no compiler I/O, an empty
control manifest cannot silently invoke a registered feature's loader, and
audit/treatment loading is identical. A `DeclarationLoadRequest` may name only
a bounded query class, scope,
declaration kinds, structural member-name terms, and result budget. It cannot
contain a theorem identity, theorem application, or tactic. Scope discovery
constrains the namespace; member-name terms constrain which declarations in
that namespace may be resolved. `ProofStateCompilerService` executes a
non-empty plan by asking the runtime for one authoritative
`compiler.resources.loaded` occurrence. That resource result binds the
original compiler snapshot ID and source event, the exact `StateRef`, runtime
identity, and target. It reports exactly the planned request IDs, terms, and
scopes and returns only symbols under requested scopes. The runtime loader uses
EasyCrypt namespace membership, filters member names before its result budget,
and uses `print` resolution only for matches. It then binds declaration text
and hashes into the resource artifact without minting a second state
observation. Missing, ambiguous, or failed loads yield no resource rather than
a guessed declaration.

P2 records structural relevance. It does not claim live, blocked, stale,
callable, type-compatible, module-compatible, proof-matched, or verified
status and emits no tactic. Native EasyCrypt owns those semantic judgments.

`ProofIR.statements` is syntax, not the current program coordinate. P3
`CoordinateAnalysis` is the only owner of `forward_frontier` and
`tactic_active_boundary`; it checks the two sides of relational goals and may
return `unknown`. Every feature analysis receives that exact
`ProofCoordinate`. A feature must not select `statements[0]`, `statements[-1]`,
or independently reconstruct an active boundary.

The fact parser builds one shared `ProofFact` index.  Facts before the current
goal separator come from the authoritative goal occurrence; lemma/axiom facts
scanned from a hash-bound source unit retain source evidence.  P2 records both
origins without claiming that a source name is verifier-live at this state.
Duplicate textual occurrences with the same name and proposition collapse to
one semantic fact; conflicting facts remain distinct.  P4 preflight, not the
source scanner, remains authoritative for actual tactic acceptance.

### 5.3 P3 Middle End

P3 answers: which structural candidates are relevant at the current coordinate,
and what did native EasyCrypt resolve or reject for the bounded application
query?

Shared output types:

```text
ProofCoordinate
  semantic layer, forward frontier, tactic-active boundary

ResourceAssessment
  live | blocked | stale | unknown, with checked local reason

BindingResolution
  application signature, target, ordered SlotResolution values, and structural
  completeness only at the current checkpoint; the target adds explicit native
  authority, and semantic completeness requires that native result

ApplicationCandidate
  projection of one native-valid or native-certifiable structural binding into a structured local
  operation (`apply`, `exact`, or `call`) plus an application term;
  unresolved premises must equal exactly its deferred proof slots

ApplicationApplicability
  state-bound assessment of the selected theorem/application family over one
  exact declared bounded native request population: applicable, inapplicable,
  or indeterminate, plus completeness, population identity, and audit-only
  request identities

StructuredDiagnostic
  code, primary, bounded notes/help, applicability, optional native-typed
  placeholder shape, trigger identity, and evidence references
```

Feature analysis producers return typed contributions to these shared tables.
They do not replace the P3 pipeline. `AnalyzedProofState` must not contain
feature-private result tables or renderer-shaped dictionaries.

Invariants:

- only the coordinate analysis owns forward-versus-active-boundary meaning;
- procedure/module string binding narrows candidates only; native EasyCrypt
  resolves module symbols, signatures, and restrictions;
- proof-slot candidate discovery consumes `ProofFact` values through one
  shared index, while native proof-term matching decides compatibility;
- P3 represents an application operation and term but never embeds a rendered
  EasyCrypt tactic string;
- application applicability is established before any argument-repair action,
  placeholder, reordering, or completion advice; a selected head and its slot
  kinds do not establish that the theorem can be used at the current
  `StateRef`. When no checked application is established, an explanation-only
  diagnostic may still contrast EasyCrypt's expected ordered slots with the
  arguments EasyCrypt parsed, but it must lead with the missing applicability
  result and state that no binding or reordering was selected;
- `live` requires native evidence for every semantic condition it asserts;
- semantic choices remain unresolved premises;
- unsupported analysis yields `unknown` or no contribution;
- P3 executes no tactic and chooses no route.

A Python-produced `mechanically_complete` value means only that lexical
candidate slots were filled or deferred. It is never a typechecking claim and
cannot feed a production action directly. Every active application consumer
now requires an event-bound native descriptor before constructing its exposed
`BindingResolution` and `ApplicationCandidate`.

#### Shared application assessment and diagnostic rendering (crosses P2-P4)

The diagnostic framework is shared compiler infrastructure, not a fifth pass
and not a feature. A feature owns the meaning and applicability of its
failure class. Shared ordinary P3 analysis owns the exact planning/native join
and `ApplicationApplicability`; the `middle_end/diagnostics` package only maps
that established assessment to bounded presentation. Generic P4 owns the
fail-closed action-versus-diagnostic invariant.

The design follows three compiler-diagnostic rules:

1. ambiguity is a first-class result; the compiler does not pick an accepted
   candidate merely because more than one exists;
2. output is graded as one exact `VerifiedAction`, one structured placeholder
   or explanation, or silence; and
3. internal candidate populations and budget counts remain telemetry; only a
   complete, small set of native-checked same-operation/same-resource
   alternatives may cross the diagnostic boundary as explicit choices.

The normative order is transaction state, execution boundary, native error,
structural diagnosis, repair outcome, mechanical explanation, and terminal
form. Feature wording may specialize that sequence but may not reorder it.

The grades are ordered by authority. A head-only descriptor can support a
factual `explanation_only` layout (expected slots versus supplied syntactic
argument kinds), but never a placeholder promise, a `Do you mean?`, or an
argument permutation. Those stronger forms require native current-state
applicability and, for an action, one exact checked completion.

The native `attempt_diagnostic` transaction may attach one
`NativeApplicationHeadDescriptor` even when a selected `apply`, `exact`, or
named `call` cannot be concretized. EasyCrypt owns the resolved global/local
head, ordered formula/module/memory/proof slots, expected native shapes,
supplied arguments, implicits, and holes. Python must not reconstruct typed
slots from declaration text. This head inspection reuses the existing native
transaction and does not add a manager intent, MCP call, or replay.
The head descriptor is optional enrichment: if EasyCrypt cannot safely
materialize the complete head/result descriptor, it remains absent and cannot
authorize slot claims. That absence does not erase an independently established
native tactic blocker or the parsed operation/resource identity.
The manager-owned attempt outcome (`rejected` or `no_progress`) and native
diagnostic disposition are two independent typed facts bound to the same
attempt occurrence. The manager owns only transition outcome and state effect;
it does not decide whether native diagnosis runs. The native adapter owns one
of `blocker`, `no_blocker`, or `indeterminate` plus any EasyCrypt-derived error
kind. It does not relabel the manager outcome. In particular, `no_progress`
must not be used as an instruction to skip native diagnosis, and manager error
text must not classify B1/B2/B4.

An EasyCrypt/native assertion is represented explicitly as `indeterminate`,
not as an absent error. Feature analysis owns whether a `blocker` belongs to
its semantic class. An `indeterminate` result can support only bounded
uncertainty or silence; it cannot authorize an argument skeleton or compiler
action. `no_blocker` produces no failure-recovery claim. Thus transition
authority, native semantic authority, and feature policy remain separate
without adding a second attempt owner.

Native planning is kept epistemically separate. The immutable
`NativeSemanticPlanningReport` records the exact `StateRef`, stage, budget
provenance, exact canonical proposed request IDs, their population hash, and
typed ready/abstained decisions. It is compiler-derived evidence about search
completeness, not a native EasyCrypt observation. Population completeness is
set equality between those planned request IDs and observations for those
exact IDs; equal cardinality is never identity evidence, and observations from
another planning stage cannot satisfy the current population.

For direct theorem applications, P3 first joins the report with exact native
observations into one `ApplicationApplicability` value. This is the mandatory
phase order:

```text
resolve selected theorem
        |
        v
establish current-state applicability
        |-- inapplicable
        |     -> blocker diagnostic; optional factual slot layout;
        |        no argument skeleton or repair
        |-- indeterminate
        |     -> bounded uncertainty, optional factual slot layout, or silence;
        |        no argument skeleton or repair
        `-- applicable
              |
              v
        resolve proof slots from native accepted descriptors
              |-- one complete checked result -> VerifiedAction
              |-- non-unique completion       -> choice-required diagnostic
              `-- unresolved native premise   -> typed prerequisite diagnostic
```

`applicable` is existential: one accepted, result-convertible native member
establishes that at least one application exists. A compiler action additionally
requires a complete bounded population with exactly one accepted member.
`inapplicable` requires a complete checked population whose observations were
safely joined to the feature contract and contain zero matches. Zero matches
in an incomplete/budget-abstained population, or a native result that cannot be
safely joined to the feature validator, are `indeterminate`, never
`inapplicable`. A complete-but-unjoinable result is an internal fail-closed
condition and produces silence rather than an agent diagnosis. The scope is
the feature-declared bounded population; the compiler does not turn that
result into a global theorem about all possible EasyCrypt instantiations.
Agent-facing wording must preserve that bounded scope; it may say the compiler
did not establish an application from its complete bounded candidate set, but
not that EasyCrypt exhausted every possible theorem instantiation.

For an inference-seeking bare failed `apply L.` or `exact L.` whose selected
native head has module slots, `operation_binding_repair` may use the shared
`selected_application_binding_set` query. P2 supplies a complete bounded
inventory of exact module spellings from hash-bound source declarations and
native goal module terms. This inventory has no typing authority. In one
native transaction EasyCrypt resolves `L`, walks the proof-term product,
checks every module term against the required signature/restrictions, leaves
non-module premises as native holes, matches the resulting conclusion to the
exact scratch goal, and preflights the complete tactic. Search has a fixed
native branch bound and never exposes a truncated prefix.

The query admits no supplied arguments. Concrete native-parsed arguments first
pass one structural alignment gate. A concrete kind/position contradiction
may receive only the shared factual expected-versus-supplied diagnostic;
alternative theorem/module search, reordering, and guessed completion abstain.
An explicit hole is compatible with every slot, and an omitted trailing
argument is an inference request rather than an alignment error. The current
binding-set contract does not preserve arbitrary partial applications, so an
aligned partial application outside another exact feature contract fails
closed instead of being silently reconstructed from the selected head.

The resulting `NativeSelectedApplicationBindingSetDescriptor` has one of four
P3 interpretations:

```text
complete checked set = 0
  -> current-state bounded inapplicability diagnostic

complete checked set = 1
  -> ordinary ApplicationCandidate -> exact P4 certification

complete checked set = 2..4
  -> one choice-required diagnostic listing every checked suffix;
     compiler selects none

incomplete, or complete set larger than the presentation bound
  -> no partial candidate list; bounded explanation or silence
```

The displayed alternatives are not arbitrary examples: each preserves the
agent-selected direct operation and theorem, is result-convertible in the
exact state, and passed native tactic execution. Candidate/check counts and
budget state remain audit telemetry. A complete zero-result diagnostic may
state the ordered module slots, bounded search scope, and absence of a
completed application; it never lists typed-but-rejected tuples or implies
that every possible module expression was searched. Under a compound
`RecoveryHandoff`, the same query
is evaluated after the exact accepted prefix; a unique result is recomposed
and certified from the original `StateRef`, while a multi-result diagnostic
explicitly describes choices for the failing suffix only.

A certificate-backed `call` has a different semantic boundary. Its certificate
conclusion describes the callee, so result/current-goal convertibility against
the caller goal is neither required nor meaningful. P3 instead requires an
exact request-bound native certificate/callee descriptor; P4 exact-tactic
preflight establishes applicability of the complete repaired `call (...)` on
the unchanged caller state. Nothing is presented before that certification.

Only after applicability is established may argument repair consume native
proof-term arguments. Before that gate, a concrete alignment mismatch routes
away from binding search, and shared
`diagnostics/argument_alignment.py` may render the already-native ordered head
slots beside the native-parsed input kinds as an `explanation_only` fact. It
does not call itself a repair, show a fillable skeleton, or say that completing
those slots would make the theorem applicable. Existing shared
`SlotResolution` is the transport for a
unique accepted descriptor: native residual proof premises become `deferred`,
and native-resolved proof heads become `resolved`. A future prerequisite
diagnostic may summarize those native dispositions, but a bare
`NativeApplicationHeadDescriptor` is insufficient for either result. In
particular, head-only slot-kind placeholders are not a current presentation
path; head-only factual layout explanations are.

`StructuredDiagnostic` is the only diagnostic contract from P3 through
presentation. It contains `code`, `primary`, deduplicated bounded `notes`,
`help`, `applicability`, an optional `placeholder_shape`, evidence references,
trigger identity, and an optional P4-owned explanation `terminal`. The
canonical renderer emits that terminal last; feature analysis does not use it
to bypass ordinary diagnostic structure. No flat message-schema fallback
exists. A placeholder shape is legal only after an applicable state-bound
application and native slot-resolution evidence; a head descriptor alone
cannot produce one.
Untyped candidates, rejected/nonmatching members, candidate/check population
sizes, and planning-budget numbers are audit telemetry only. A complete small
set of native-checked same-resource alternatives may be shown as a
`choice_required` diagnostic, never ranked or auto-selected. A complete
zero-result set may expose its ordered slot requirements and bounded
no-completion result, but never the rejected tuples themselves.

At most one diagnostic is admitted for one trigger. A recovery owner must
lower either an action or a diagnostic before P4 certification, never both.
An overlap, duplicate, stale identity, or ownership conflict fails closed.
Diagnostics use the same trigger/lifetime/admission path as actions; the
generic manager, turn model, orchestrator, and renderer contain no feature
branch.

#### Compound-boundary recovery and scratch evaluation

A rejected compound is one manager occurrence at the original `StateRef`.
The native prefix query may establish that an exact, agent-written proper
prefix is accepted and may diagnose the first rejected extension in the
scratch proof produced by that prefix. This does not create a second manager
state and does not authorize the compiler to commit the prefix.

```text
original StateRef + exact rejected compound
        |
        v
native longest contiguous accepted prefix
        |
        +-- first rejected extension gets a typed descriptor
        |
        v
RecoveryHandoff(prefix, effect, suffix, native evidence)
        |
        v
suffix feature classifies the typed failure
        |
        +-- unique checked suffix
        |       -> recompose prefix ; repaired-suffix
        |       -> exact preflight at original StateRef
        |       -> one VerifiedAction
        |
        +-- feature forms one specific diagnostic
        |       -> that suffix feature owns it
        `-- feature forms no P3 result
                -> compound source owns one generic factual fallback
```

All subsequent native work requested by the suffix owner is evaluated under
`original StateRef + exact accepted prefix`. The shared planner, not the
feature producer, attaches this prefix; it is part of request, coalescing,
observation, cache and telemetry identity. The native companion independently
replays it in a read-only proof context for every affected semantic unit.
Failure to replay it is an authority failure, not a suffix rejection.

The handoff records one `source_feature_id`. A suffix feature earns ownership
of a delegated compound occurrence only by forming a concrete P3 action,
diagnostic, or action realization. Merely recognizing a broad failure class is
not enough. If no registered suffix slice forms such a result, shared recovery
ownership installs the source feature as the sole fallback owner and retains
the native accepted-prefix/first-rejected-extension diagnostic. This prevents
a handoff sink without giving the compound feature permission to interpret
`apply`, `conseq`, `call`, or any other suffix family. Multiple concrete suffix
claims still conflict and fail closed; catalog order never selects one.

For a state-changing prefix, a suffix-only action is never certified or
presented. Generic P4 composition reconstructs the complete compound without
interpreting its tactic family, and ordinary exact preflight checks that full
tactic from the original manager state. No manager, renderer or consumer
feature contains a compound-specific branch.

Failure-linked diagnostics additionally have a material recovery lifetime.
At one goal and committed prefix, repeated spellings with the same feature,
operation/resource, native blocker class and accepted compound boundary share
one presentation identity. A different blocker or a strictly different or
longer native-accepted prefix forms a new lifetime scope. Exact trigger IDs
remain in provenance; they no longer force repeated agent-visible wording
when no material recovery evidence changed.

A standalone checked-prefix continuation is intentionally not implemented by
this checkpoint. It is a separate candidate action and requires its own
evidence gate. The current framework either presents a fully recomposed,
certified repair, a bounded fact, or silence; it never mutates the proof merely
because a prefix was accepted in scratch evaluation.

### 5.4 P4 Backend

P4 has four substeps with distinct contracts.

#### P4a Surface lowering

Generic lowerers convert P3 facts into `CandidateSurface` entries:

- `ResourceReferenceCandidate`;
- `BindingReferenceCandidate`;
- `ActionCandidate`; and
- `DiagnosticCandidate`.

An `ActionCandidate` contains an exact manager intent/payload, unresolved
premises, state scope, evidence, feature attribution, and a declared
certification policy. Every candidate kind also carries a mandatory
`StrategyContract`. Production candidates are `intrinsic` or
`commitment_relative`. `route_selecting` is retained as a boundary/audit
classification so that an accidental route proposal can fail closed; it is
not a production feature contract or a reason to implement a hidden producer.
There is no proactive M05 implementation on `main`. No candidate is
agent-visible before admission.

The generic application lowerer is the only owner of tactic spelling for
structured application operations:

```text
apply(term)                    -> apply (term).
exact(term)                    -> exact (term).
call(term)                     -> call (term).
```

Feature code may select an operation only under its evidence-gated state
predicate.  It may not concatenate a tactic or add a renderer field.

#### P4b Certification

`CertificationGateway` executes only declared read-only verifier checks. A
result is bound to candidate ID, exact payload, exact `StateRef`, and the
authoritative verifier-result occurrence.

It rejects:

- state drift;
- candidate or payload drift;
- missing or ambiguous event authority;
- unknown proof-state effect where the policy requires a known effect; and
- any change to committed history.

Certification never repairs or rewrites a candidate.

#### P4c Admission

`AdmissionPolicy` is deterministic. It consumes candidates, certification
results, exact-state `CompilerTrigger` values, and an immutable
`ResolvedDeliveryPlan`. The plan was independently resolved from a registered
`DeliveryPolicyCatalog`; it owns trigger kind, strategy class, presentation,
lifetime, compatibility, audit rejection reasons, and per-policy item/byte
budgets. `ActivationPlan` owns pass and certification execution only. This
makes audit-only execution a real protocol state rather than a treatment run
whose output merely happened not to reach an agent.

Policy-bound admission rejections are executable contracts, not descriptive
metadata: lifetime, local budget, aggregate budget, and certification
rejections may be emitted only when the selected policy declares that reason.
Feature/ownership audit reasons produced before a delivery policy is selected
remain owned by P3/P4 and are not mislabeled as policy rejections.

Per-policy budgets do not add together. `ResolvedDeliveryPlan` derives one
aggregate `ActionSurface` envelope equal to the largest single selected-policy
envelope, and admission enforces both the local policy limit and this complete
surface limit. Adding a second feature therefore cannot silently double panel
items or bytes.

It decides visibility and lifetime. It cannot discover resources, construct
tactics, infer an unexpressed proof strategy, or call EasyCrypt. Every excluded
candidate receives an audit reason.

Admission modes are shared policy values:

| Mode | Required trigger | Lifetime |
|---|---|---|
| silent | `StateRefresh` | audit/cache only, zero agent bytes |
| requested | `ExplicitContextRequest` | one manager result |
| elaborated | `AgentSelectedOperation` | the current proof intent only |
| failure-linked | `CurrentStateFailure` | one same-state manager result |

`optional_advisory` remains only a schema-level rejection vocabulary. No
helper, feature, validation runner, production policy, or profile on `main`
constructs it. New route-selecting proposals remain ledger entries, not
compiler registrations.

`CompilerProfile` contains feature activations and registered delivery-policy
IDs only. It has no inline rules or budgets. The assembler resolves the feature
and policy catalogs once; unknown policies, incompatible feature/policy pairs,
duplicate delivery ownership, and treatment features without a policy fail
closed. A feature cannot declare itself proactive merely because its candidate
is certified. An
agent-selected operation is frontend input: P2 represents the selected
operation/resource, P3 resolves only its mechanical slots, P4 lowers and
certifies it, and the manager-owned runtime remains the sole mutation owner.

#### P4d Action surface

`ActionSurface` is the compiler's only agent-facing output. It contains only
admitted generic entries. Each entry retains a `DeliveryPresentation`; actions
expose only a compact checked local effect. Full compiler bundles, rejected
candidates, certification internals, provenance expansion, and alternatives
stay in audit artifacts.

Vocabulary is frozen at this boundary. `CandidateSurface` means internal P4
pre-admission candidates. `ActionSurface` means the certified, admitted,
bounded compiler output. Current-turn presentation means the manager envelope
that may carry an `ActionSurface`; it is not another compiler IR. Runtime
profile means one experiment arm's matched compiler and turn configuration.
New design text must not use bare “surface” as an additional abstraction.

The renderer switches on generic entry kind. It never switches on feature ID.

## 6. Feature registration

A feature is one registration bundle, not a new pipeline:

```text
FeatureDefinition
  spec
    feature_id                    semantic snake_case identity
    evidence_ledger_ids
    correctness_contract
    provenance_contract
    required_ir_capabilities
    certification_policy
    strategy_contracts             SC0/SC1 output classes the feature may emit
                                   (M05 is the sole frozen SC2 exception)
    experiment_gate
    native_semantic_dependencies   target: exact native owners/results reused
    shannon_delta_contract         target: candidate/commitment work added here
    lexical_prefilter_contract     target: optional, non-authoritative, measured

  producers
    resource_load_request_producers[]
    resource_discoverers[]
    native_semantic_request_producers[]
    analysis_producers[]
    surface_lowerers[]
```

Catalog registration does not imply execution or exposure. One profile-level
`FeatureActivation(feature_id, off|audit|treatment)` controls the whole
registered vertical slice. The assembler first selects complete
`FeatureDefinition` values; the fixed pass manager then collects every loading,
P2, P3, and P4 producer only from that set. Certification is derived from the
activation plan. Admission is derived only from the separately resolved
delivery plan.

`off` means no feature producer runs. `audit` and `treatment` run the same pass
and certification sets; only treatment references a compatible registered
delivery policy. Resource loading is part of the registered slice, not a
separate choice the person configuring or deleting a feature must understand.

Registration has exactly three composition roots, each with one responsibility:

```text
core feature catalog
  semantic FeatureDefinition, producers, native dependencies, contracts

workflow delivery-policy catalog
  trigger, lifetime, budget, compatibility, rejection audit reasons

workflow runtime-profile registry
  one experiment arm's activation/policy projection + matched turn envelope
```

Publication adds an audience boundary without adding a fourth compiler root:

```text
production profile registry
  l1_goal_projection
  proof_state_compiler
  treatment activations only

private research registry
  hidden audit controls
  single-feature treatment ablations
  loaded lazily only by an exact eval-mode identity
```

Ordinary configuration and CLI discovery consume only the production
projection. They cannot name an audit arm, and the production aggregate never
runs an `AUDIT` activation. The eval harness uses a separate hidden transport
argument to select a private research registration; a normal config file
cannot persist that identity. The research registry and superset feature
catalog live under `workflow.validation` so a future public source package can
omit them physically without modifying manager, compiler, renderer, or feature
contracts.

The machine-readable `production_release_manifest()` must equal the feature
set activated as `TREATMENT` by `proof_state_compiler`. Packages absent from
that manifest—including held audit substrates—are not part of a public code
release even though their research implementation and evidence remain in the
private repository.

Each audience has one runtime-profile composition root. The production root
owns the public pair; the research root imports its shared contracts and owns
only experiments. `configuration.py` and `surface_profiles.py` consume those
registrations; they do not redeclare an arm.
Feature identity constants and profile identity constants may remain separate
vocabularies, but neither is a second structural registry.

Do not merge these roots into one giant descriptor. Delivery policies may be
shared only where their compatibility contract permits it, and recovery
ownership is determined per exact attempted-operation occurrence and output,
not by a static feature-wide ownership key. A feature is universally OFF when
absent from a profile; “default activation” is therefore not feature metadata.

Deleting a feature removes its package, its semantic-catalog entry, any
delivery-policy compatibility entry that exists only for it, its runtime
profiles, and feature-specific tests. No person deleting it needs to trace its
producer through P2/P3/P4: `FeatureDefinition` is the complete producer bundle,
and assembly selects that bundle atomically.

The three native-boundary fields are required and implemented in the current
`FeatureSpec` dataclass. Every feature specification
must answer separately:

1. which native EasyCrypt semantic result it consumes;
2. what bounded candidate search or commitment-relative transformation Shannon
   adds;
3. whether any lexical prefilter remains, why it is safe, and what measured
   cost it saves; and
4. which delivery policy exposes the Shannon delta.

`NativeProofStateSnapshot` is the passive typed P1/P2 substrate. Any declared
request-bound native dependency beyond that substrate requires at least one
registered `native_semantic_request_producer`. A lexical observation may only
bound such a request. It cannot directly satisfy a native dependency, become a
typed binding, or lower to `CandidateSurface`; missing/unresolved native
observations cause abstention before P3/P4.

An M ledger ID is provenance for the burden, not proof that all computation in
that row belongs to Shannon.

Strategy coupling belongs to the individual P4 output, not to a broad feature
family. One feature may declare several SC0/SC1 contracts, but the compiler
rejects a candidate whose exact contract is absent from its `FeatureSpec`.
Route-selecting portions of a mixed concept are split away before registration;
they are not made safe by an audit flag, a zero-byte renderer, or an explicit
warning. In particular, checking whether a conjunct from an accepted invariant
was later dropped is `commitment_relative`; choosing a new conjunct to
strengthen the invariant is `route_selecting` and therefore absent from the
production compiler.

### 6.1 Feature naming contract

Three namespaces must remain separate:

| Namespace | Purpose | Example | Where it belongs |
|---|---|---|---|
| Semantic feature identity | Stable description of the mechanical operation | `losslessness_certificate_application` | `features/<feature_id>/` and `FeatureSpec.feature_id` |
| Evidence ledger identity | Links the implementation to observed burden and treatment evidence | `M05`, `M07` | `FeatureSpec.evidence_ledger_ids` and evidence reports |
| Experiment arm identity | Names one frozen exposure/control configuration | `l1_goal_projection`, `l1_plus_losslessness_certificate_application` | workflow manifests and eval-suite configuration |

A feature package uses `<proof-object-or-boundary>_<mechanical-operation>` in
snake case. It must not use:

- a ledger ordinal such as `m05`;
- implementation-quality adjectives such as `typed` or `generic`;
- pipeline-stage words such as `candidate` or `surface`;
- vague outcome claims such as `smart` or `helpful` (a precise semantic
  operation such as `binding_repair` is allowed); or
- an experiment profile name.

Examples of consistent semantic names, if those treatments are later
authorized, are:

| Mechanical treatment | Semantic feature name | Not the package name |
|---|---|---|
| Apply one exact losslessness certificate | `losslessness_certificate_application` | `m05` |
| Instantiate and apply one theorem | `theorem_application` | `typed_theorem` |
| Validate one agent-selected call frame | `call_frame_validation` | `frame_candidate` |
| Discharge the explicit prerequisites for one `sim` action | `sim_precondition_discharge` | `sim_repair` |

The latter three are naming examples, not registered or admitted features.
For an SC0/SC1 proposal, a feature directory is created only after an evidence
specification authorizes an audit implementation. An SC2 proposal remains in
the ledger and does not receive even an audit-only production feature. Shared
IR may still be introduced when a separate admitted SC0/SC1 consumer requires
it.

### 6.2 First non-strategic batch identities

The August 6 non-strategic batch freezes the following ledger-to-semantic
mapping before any feature package is created. Ledger ordinals remain evidence
metadata and do not appear in package names, shared IR fields, manager code, or
renderer branches.

| Ledger evidence | Semantic feature identity | Narrow owned output |
|---|---|---|
| M04 | `program_operation_readiness` | Audit/internal legality and exact current blocker; no standing treatment |
| M09 | `accepted_contract_retention` | Missing conjunct from one exact accepted structural contract, relative to a lineage-valid anchor |
| M15 delivery + B1/B2/B4 evidence | `operation_binding_repair` | Certified correction preserving the exact attempted operation/resource, including losslessness apply/call families; M15 owns only failure delivery |

`accepted_contract_retention` does not synthesize a strengthening fact.
`operation_binding_repair` repairs an already rejected commitment; it is not a
broad error helper and does not select a replacement resource. Rejected tactic
parsing is shared P2 `FailureObservation`/`AttemptedOperationIR`, not feature
code. M15 is the horizontal `failure_linked_repair_rule()`; numerical
complete-Markdown envelopes remain feature-specific. Evidence and result-free
experiment gates remain feature-specific as well.

Adding a normal feature may change only:

- its feature package;
- one entry in `features/catalog.py`;
- its tests and fixtures;
- its evidence-ledger record; and
- declarative experiment-profile rows.

It must not require changes to:

- `ProofNodeManager`;
- `ProofStateCompilerService`;
- shared pass orchestration;
- `SurfaceTurnModel`;
- generic markdown rendering; or
- proof intent execution.

Physical removal has the same boundary in reverse: delete the feature package,
its single catalog entry, profiles that name it, and feature-specific
tests/runners. Historical evidence reports remain. It must not require locating
or editing separate P2/P3/P4/resource-loading switches; if it does, the
composition contract has failed.

If a feature requires one of those changes, it either introduces a genuinely
new shared proof-domain concept, or it is connected at the wrong boundary. A
shared-contract extension requires an architecture decision and a synthetic
cross-feature test before feature implementation proceeds.

Historical M07 work triggered one such shared extension: bounded P2 declaration
dependency loading. The service/runtime request/resolve/re-snapshot protocol is
feature-neutral and remains because the SC1 operation-binding slice consumes
it. The M07 producer itself is deleted.

The experiment boundary follows the same rule. Shared
`proof_state_compiler_one_step_trial.py` and
`proof_state_compiler_one_step_model.py` own the packet, provider invocation,
tool prohibition, JSONL decoding, and metrics. Proactive validation modules
exist only on `compiler-proactive`; `main` has no feature-specific manager or
renderer.

## 7. Evidence feature lifecycle

Every evidence item follows the same route.

### E0: Observation

Record concrete L1 burden with file/turn provenance, comparison target, and
whether any treatment has already shown improvement. An inferred opportunity
is labelled as a hypothesis, not evidence.

### E1: Feature specification

Define the mechanical question, state predicate, expected saved work,
correctness contract, required inputs, abstention cases, maximum surface size,
delivery mode and lifetime, and failure risks. Link ledger IDs.  If the feature
requires an agent-selected operation, identify which fields are semantic
choices and which slots the compiler may fill mechanically.

### E2: IR capability check

Map every required input to an existing shared P2/P3 concept. Add a shared
domain type only when the concept is reusable and cannot be represented
without losing semantics. Never add a feature-named field to a shared state.

### E3: Producer implementation

Implement the smallest resource discovery, analysis, and lowering producers.
Each producer consumes only its immediate upstream contract and returns typed
contributions. Unknown cases abstain.

### E4: Correctness and provenance tests

Test positive, negative, ambiguous, stale, and state-drift cases. Test that
all evidence is attached to the current `StateRef` and loaded-source hashes.

### E5: Certification policy

Declare whether the entry needs no verifier call, declaration checking, exact
tactic preflight, or closed-obligation proof. Implement no feature-specific
certification branch; policies select generic gateway operations.

### E6: Audit-only execution

Run the producer without exposure. Measure eligibility frequency, correctness,
candidate count, certification cost, and would-be byte size. Wrong facts block
the feature regardless of expected benefit.

### E7: Micro experiment

Use an identical authoritative proof state and vary only admission of that one
feature. Micro tests measure the narrow causal claim, for example:

- exact-action consumption;
- rejected attempts avoided;
- lookup or argument-instantiation work avoided;
- next-action tokens/time; and
- checked residual state.

A micro experiment does not establish solve-rate or route efficacy and does
not determine production architecture.

For an agent-selected elaboration, both arms must begin after the same semantic
operation/resource choice.  Control manually composes the EasyCrypt form;
treatment may use the typed compiler intent.  Count the entire request and
result exchange.  For a failure-linked feature, compare against the observed
L1 self-repair latency for that exact failure class rather than assuming that
every rejected tactic is costly.

### E8: Full managed three-arm experiment

Run real no-compiler L1, compiler audit, and compiler treatment from the same
commit, model, effort, source contract, proof controls, topology, budgets, and
seeds. Audit and treatment share the exact feature compiler and certification
set; only treatment admits its output. Measure route-level outcome, total
tokens/cost/time, cache behavior, source inspection, rejections,
semantic-boundary progress, loader/certification cost, presentation, and exact
next-intent consumption. Counterbalance scheduling when the slate is small.

A launched eval run is not countable when it captures no provider session or
completes no managed agent turn. A zero-turn backend early exit is
infrastructure failure, not an unusually cheap treatment. Report bundles may
read session history only from the current run's confined `ec_sessions/`
archive; they never scan same-named worktree-root sessions or choose the
largest available history. A confined session is accepted only when its
`session_meta.json` file/lemma identity matches the current run configuration.
Missing or mismatched history falls back to the current run's
timeline/bootstrap reconstruction.

Suite runners defer tracked report generation until all prover arms finish and
freeze the pre-run git identity for every bundle. Bundle identity includes the
row, profile, and repeat, so same-minute arms cannot collide and generated
reports cannot make later prover arms appear code-dirty. If the repository git
identity changes during the prover slate, the runner stops before another arm
and refuses to generate bundles carrying a misleading frozen identity.

### E9: Admission decision

Promote audit-only -> treatment -> admitted only with correctness, consumption,
targeted mechanical improvement, no solve-rate regression, and acceptable
end-to-end economics. A feature that is correct but noisy is shrunk, made
pull-only, or removed. A failed experiment does not trigger compensating
features.

### E10: Continuous removal

Every admitted feature retains versioned telemetry and negative controls. A
regression or loss of consumption can demote or delete it without changing the
compiler architecture.

## 8. Ledger-to-pipeline routing contract

The table below says where each ledger item would enter the fixed compiler. It
is a routing contract, not an instruction to implement or expose every row.
`Hold` means the architecture has a typed route but evidence does not authorize
an agent-visible treatment. `Outside` means the item must remain fixed across
compiler A/B arms.

| Ledger | Typed route through the compiler | Exposure boundary | Current decision |
|---|---|---|---|
| M01 state authority | `InputGateway -> ProjectedProofState -> StateRef/provenance checks on every stage` | none | Active internal correctness prerequisite |
| M02 proof coordinate | `ProgramStatement -> ProofCoordinate(forward_frontier, tactic_active_boundary)` | optional diagnostic/reference candidate | Active internal; proactive display unvalidated |
| M03 outer goal/opener | `GoalIR -> coordinate/applicability analysis -> ActionCandidate` | exact or pull action after certification | Hold; classification is valid, benefit is not |
| M04 tactic readiness | `ProgramStatement + ProofCoordinate -> ResourceAssessment/TransformAssessment` | internal/audit only | `program_operation_readiness` may analyze with zero agent bytes; the standing changed-fact treatment is removed and any future D3 consumer requires an exact failed operation plus a separately registered policy |
| M05 exact certificate | `ProofResource -> structural procedure binding -> ApplicationCandidate -> ActionCandidate` | agent-selected elaboration or separately admitted proactive exception | Hold; implementation and sentinel retained, with no current profile or production delivery policy |
| M06 bridge lemma | `ProofResource(equiv) -> BindingResolution -> ApplicationCandidate` | exact checked action | Hold; historical positive not revalidated |
| M07 theorem/operator binding | `DeclarationLoadRequest -> LoadedDeclaration -> ProofResource + ApplicationSignature -> SlotResolution -> BindingResolution` | agent-selected application elaboration; declaration query on demand | Binder/certifier passes and the local action is useful; early/late proactive managed runs do not establish route benefit, so D2 delivery is the next gate |
| M08 call-frame fragment | `ScopeAssessment + BoundaryContractAssessment` | pull resource/binding reference | Hold; local gain with end-to-end regression |
| M09 fact retention | accepted contract anchor plus `ScopeAssessment` across lineage-valid structural coordinates | missing old-conjunct result | `accepted_contract_retention` fixture/audit only; re-audit found no natural positive and reclassified prior examples as SC2 strengthening |
| M10 up-to-bad contract | `BoundaryContractAssessment(required slots, unresolved choices)` | pull reference only | Hold; diagnostic-only evidence |
| M11 live names/memories | `NativeProofStateSnapshot.local_declarations -> typed scope/binding blockers` | normally none; diagnostic only when a candidate needs it | Native locals are active P2 authority; broader scope analysis remains internal/hold |
| M12 guard direction | `ProgramStatement(if) + coordinate -> TransformAssessment` | exact checked action only when direction is determined | Hypothesis; no isolated treatment |
| M13 eager/transitivity form | `ProofResource + application grammar -> ApplicationCandidate` | agent-selected elaboration, with one-turn failure fallback | Hold; observed self-repair must be the baseline |
| M14 pure normalization | `GoalIR residual structure -> TransformAssessment/ApplicationCandidate`; failed selected rewrites may instead enter event-bound recovery | pull/elaboration only after an explicit operation/resource choice; current `pure_tail_recovery` candidate handles only a failed plain rewrite with one native-unique hypothesis target | Broad/proactive normalization remains Hold; the narrow rewrite-target slice is SC1 because it preserves the exact agent-selected lemma and direction |
| M15 failure diagnosis | event-bound rejected transition -> shared `FailureObservation`/`AttemptedOperationIR`; semantic slice claim -> exact certification | shared failure-linked rule, one complete feature-budgeted item | M15 is thin delivery only; numerical envelopes are feature-specific; `operation_binding_repair` owns B1/B2/B4 semantics and `intro_pattern_repair` owns the native-unique ordered-binder dialect slice; recovery-owner conflicts fail closed |
| M16 proof document | manager-owned accepted spine and remaining goals | fixed manager surface | Outside compiler |
| M17 recovery execution | manager/runtime checkpoint, undo, amend, replay | fixed controls | Outside compiler |
| M18 action granularity | P4/action packaging and experiment design | admission/output policy, not a proof fact | Opt-in candidate for continued treatment testing; the frozen natural-trigger route gate still showed no closures and a 9.49% tokens/action regression, so this is not a full-route value claim |
| M19 payload economics | candidate counts -> admission budgets -> compact payload telemetry | cardinality and byte gates | Active exposure constraint |
| M20 concrete procedure identity | `ProgramStatement.procedure -> procedure_binding -> BindingResolution` | silent input to an agent-selected call/inline operation, or explicit query | Active narrow infrastructure for M05; B3 often self-repairs on the next attempt, so general treatment is lower priority than B2 |
| M21 boundary slots | `ProgramStatement + ProofCoordinate -> BoundaryContractAssessment` | pull contract reference or exact checked action | Hold; test one boundary kind at a time |
| M22 tactic dialect | `ApplicationCandidate -> certification failure class` | agent-selected elaboration first; error-linked fallback | Hold; B7 repairs within two attempts in 19/19 strict events and needs a strong negative control |
| M23 probability normal form | `GoalIR probability structure -> TransformAssessment/ApplicationCandidate` | query or elaboration after explicit probability operation/resource selection | Hold |
| M24 arithmetic prerequisites | `ApplicationSignature/ProofJudgment -> deferred or blocked slots` | elaboration of an already selected application, or requested blocker result | Hold |
| M25 transform applicability | `ProgramStatement + resource/scope facts -> TransformAssessment` | preflight of an agent-selected transform or compact same-state failure result | Hold; never a default transform recommender |

This routing prevents evidence items from becoming top-level fields. For
example, M12, M21, and M25 share the same `ProgramStatement`, `ProofCoordinate`,
`BoundaryContractAssessment`, and `TransformAssessment` vocabulary; they do
not create three parallel panel architectures.

## 9. Binding is one shared middle-end subsystem

“Binding work” is the evidence umbrella for determining what a proof object
means at one exact state and how it can be instantiated there. The semantic
part of that determination belongs to native EasyCrypt. Shannon owns the
bounded request, structured transport, candidate narrowing, commitment
boundary, and delivery. Binding is not one feature, one panel, a Python
unification algorithm, or the whole middle end.

The stable compiler relation is:

```text
P2 FRONTEND
  declarations + qualified program identities + lexical candidate sketches
       |
       v
NATIVE EASYCRYPT SEMANTIC ADAPTER
  local/global resolution + argument kinds + typing/unification
  + module/restriction checks + proof matching + concretization
       |
       v
P3 MIDDLE END
  coordinate + resource + binding
  + peer scope/effects/contracts/transforms/residual/feedback analyses
       |
       v
P3 BINDING SUBSYSTEM
  symbol/procedure/application-slot resolution only
       |
       v
  BindingResolution / ApplicationCandidate
       |
       v
FEATURE ANALYSIS
  consumes shared resolutions under a narrow state predicate
       |
       v
P4 BACKEND
  generic candidate -> certification -> admission -> ActionSurface
```

The evidence taxonomy deliberately maps to several resolver families:

| Evidence class | Mechanical question | Frontend input | Middle-end owner | Shared result | Default exposure |
|---|---|---|---|---|---|
| B1 symbol/namespace identity | Which live local/global declaration does this name denote? | bounded candidate names and current proof environment | native `LDecl`/`EcEnv.Ax` resolution; Shannon transports identity | canonical native resource or structured lookup failure | none; consumed by an exact candidate or pull lookup |
| B2 module/functor arguments | Which explicit or implicit module slots instantiate this declaration? | candidate resource/application plus qualified module spelling | native `EcProofTerm`/`EcTyping` module resolution, signature, and restriction checks; Python structure may narrow | native-derived per-slot `BindingResolution` | none unless a narrow feature consumes the complete resolution |
| B3 concrete procedure target | Which fully applied procedure is at the tactic-active call site? | `ProgramStatement.procedure` and procedure-bearing resource conclusion | procedure binding | structural procedure resolution | internal applicability evidence |
| B4 application kind/arity | Does each supplied object inhabit the required module, term, formula, type, memory, or proof slot? | exact candidate application request | native proof-term elaboration | resolved/implicit/residual slots or structured native error | exact/pull candidate only after native validation |
| B5 proof-fact and local binder liveness | Which current/source fact can inhabit a proof slot, and is a local name or memory decoration verifier-visible here? | lexical `ProofFact` candidate index plus current proof environment | native local/global lookup and `pf_form_match`; Shannon scope/provenance transport | native-resolved proof slot, `ScopeAssessment`, or blocker | checked local application only |
| B6 frame/restriction slots | Which frame facts and write restrictions remain valid across this proof boundary? | coordinate, program effects, and visible hypotheses | boundary-contract analysis | `BoundaryContractAssessment` | hold/pull; never inferred from lexical application matching |
| B7 transform input/applicability | Are the operands and prerequisites of `sim`, `inline`, rewrite, or another transform present? | goal/program IR plus resolved resources and scope | transform analysis | `TransformAssessment` | one checked action or diagnostic, never a standing menu |

This table defines ownership rather than implementation priority. B1-B4 are
the core application-binding request/transport subsystem, backed by native
EasyCrypt semantics; B3 is its structural procedure candidate resolver. B5-B7
remain in the
evidence audit because the agent experiences them as “what does this action
refer to here?”, but their implementations are peer middle-end subsystems, not
children of binding. The frontend discovers and indexes; native EasyCrypt
resolves semantic application questions; the middle end classifies and
transports the result; a feature selects a commitment-valid local use; the
backend checks and exposes it. No analysis subsystem renders text or chooses a
proof route.

### 9.1 Shared application transport contracts

The second evidence-backed consumer forced the first slice's module-only
contract to become a shared application interface. These are Shannon transport
types, not a replacement for EasyCrypt's proof-term types. The current P2/P3
vocabulary is:

```text
ApplicationSignature
  resource identity
  ordered ArgumentSlot[]

ArgumentSlot
  stable slot identity
  kind: module | term | formula | type | memory | proof | implicit
  expected structural type, explicitness, and source provenance

SlotResolution
  slot identity
  resolved | deferred | blocked | unknown
  value or reason plus evidence

BindingResolution
  application signature + target coordinate
  ordered SlotResolution[]
  structural-completeness flag only (current)
  explicit native semantic authority (transport exists; production binding not migrated)

ApplicationCandidate
  operation: apply | exact | call
  exact application term
  ordered slot resolutions and exact deferred premises
```

These are implemented shared transport concepts. Only proof slots may be
marked `deferred_obligation`; required unknown/blocked slots make a structural
candidate incomplete. A complete Python candidate is still not semantically
valid. Native elaboration must establish argument kinds, typing, module
constraints, proof matching, and concretization. Exact tactic preflight then
establishes final tactic acceptance and local effect.

`proof_slot_binding.py` currently proposes an instantiated proof expectation
from the shared fact index. Exact normalized propositions are strongest. For
Hoare
and equivalence facts, a unique current-context fact with the same judgment
kind and procedure subject may be used as a structural candidate when clone
instantiation changes the printed global-state expression; exact-tactic
preflight is mandatory. This score is not native proof matching and must be
replaced by or submitted to the native adapter. Ambiguity remains unresolved.
The matcher never
chooses a proof method, synthesizes a premise, or searches model history.

The current physical organization is deliberately small:

```text
middle_end/
  coordinate.py            semantic layer and tactic-active boundary
  resource_analysis.py     resource liveness aggregation
  procedure_binding.py     structural procedure candidate narrowing (B2/B3)
  native_application.py    native descriptor -> application transport
  proof_slot_binding.py    lexical fact candidate scoring (B4/B5)
  binding_analysis.py      resolution/application aggregation
  contributions.py
  analysis_pipeline.py
```

The flat files are modules with one responsibility, not one-feature helpers.
The native adapter and P3 dependency cycle now sit at the frontend/middle-end
boundary; production binders have not yet migrated to them. Native algorithms
must not be copied into these modules.
They may become subpackages when a peer subsystem has several real algorithms;
empty `scope/`, `effects/`, `contracts/`, or `transforms/` packages are not
created in anticipation. A peer subsystem requires a typed contract,
evidence-backed producer, tests, and a real consumer.

### 9.2 Middle-end dependency direction

The middle end is a dependency DAG, not a set of analyzers that all inspect
everything:

```text
ProjectedProofState
  -> coordinate
  -> resource -> binding
  -> scope -> effects -> contracts
                    \-> transforms
       binding ------> transforms
  -> residuals
  -> authoritative rejected transition -> feedback

all typed contributions -> AnalyzedProofState
```

`analysis_pipeline.py` schedules and aggregates this DAG. It contains no proof
semantics of its own. Shared contracts stay in `contracts/`; algorithms stay
inside the owning middle-end subsystem.

### 9.3 Feature relationship to binding

The losslessness feature owns only its domain-specific edges:

- discovery of the losslessness-certificate resource subtype;
- the exact state predicate under which that subtype is relevant; and
- lowering a structurally complete, subsequently native-certified application
  into one generic candidate.

The reactive probability multi-slot recovery owns only bounded candidate
edges after an exact same-resource bare-`apply` B2/B4 failure: parsing the
selected declaration as a lexical sketch, aligning its conclusion to the
current probability goal to spell one native query, and optionally proposing
one uniquely ranked proof fact. EasyCrypt then owns all slot kinds, typing,
proof matching, holes, residual premises and the exact result. There is no
proactive probability-theorem feature or endpoint-anchor operation.

The subsystem must not become a global search panel, candidate ranker, tactic
planner, or cumulative context dump. It runs only the resolvers requested by
registered feature capabilities; admission still defaults to silence.

## 10. Branch-confined proactive slice

The proactive M05 `losslessness_certificate_application` slice is physically
absent from `main`. The shared native proof-term descriptor, application
lowering, and exact preflight infrastructure remain because the
commitment-relative `operation_binding_repair` feature consumes them.

The frozen M05 implementation, experiment manifest, sentinel, fixture-specific
tests, and optional-advisory delivery helper are maintained only on the private
`compiler-proactive` branch. That branch is a compiler-only delta from
`main`; it is not part of the default runtime or the interleaved product.

Historical M05 reports remain in this branch as evidence provenance. They do
not make M05 runnable and do not authorize another proactive feature.


## 11. Second-consumer and recovery-removal proof

Three independent checks protect extensibility:

1. A test-only diagnostic feature uses generic admission/rendering without a
   boundary branch or any real feature dependency.
2. `operation_binding_repair` consumes native proof-term semantics for B1,
   B2 losslessness apply/bounded one-module-call families, and the frozen
   probability/multi-slot B2/B4 family.
   Declaration/signature/proof-slot code can only enumerate a bounded native
   request after an exact rejected operation/resource commitment.
3. A synthetic second recovery feature claims the same authoritative failed
   occurrence. The generic ownership resolver rejects both claimants
   independently of feature/catalog order, with no manager, service, turn-model,
   renderer, or existing-feature change.

Historical M07 experiments remain evidence for the shared frontend/binder
capabilities and for the decision not to retain proactive theorem
foregrounding. They do not authorize an M07 production feature or profile.

## 12. Telemetry

The current service records:

- state, environment, compiler feature-set, and manifest identity;
- declaration-load request, scope, member/loaded cardinality, latency, and
  hash-bound loaded-declaration identities;
- exact-observation, material-certification, and resource-environment cache
  hits/misses; material hashes; origin/current observation versions and event
  IDs; origin environment; performed loads; and reused cardinalities;
- input, P1-P4 aggregate, certification, admission, and total duration;
- candidate counts by generic entry kind and feature attribution;
- certification policy, verdict, checked effect, and verifier event reference;
- admission or exclusion reason for every candidate;
- final item count, exact compact agent-payload bytes, and exact presented
  generic intent/payload identities; and
- aggregate eval metrics for service calls/failures, planned and completed
  loader calls, internal and wall loader latency, P1-P4/certification/total
  time, candidate/certification/presentation counts, and byte-identical
  next-intent consumption by feature.

Recovery performance closure additionally requires initial compiler-input
transport and native-state projection to be separated; native request count,
per-request/batch elapsed time and status to be retained; skipped feature and
backend-call counts to be explicit; and cold/warm resource, native, and
certification state to be distinguishable. A total duration without this
attribution is insufficient for a managed economics claim.

Native observation telemetry keeps two identities distinct:

- `request_id` is the feature consumer request;
- `execution_unit_id` is the coalesced native member that EasyCrypt executed.

One execution unit may fan out to several consumers. Offline evaluators join
the retained artifact by exact `execution_unit_id` plus `batch_index`, then
cross-check query kind and status. They never require consumer/member ID
equality. A failure-linked compiler occurrence is compared with its exact
manager attempt occurrence and unchanged before/after authority, not with an
adjacent earlier compiler invocation.

Managed Codex evaluation also separates proof-semantic tools from host
metadata. `proof_node_manager.submit_proof_intent` is the sole proof tool.
Bounded empty resource/template discovery performed by the Codex MCP host is
recorded as provider overhead only after the shared runtime policy verifies
the exact private server scope and empty result. It never advances a proof
turn or becomes compiler input; non-empty or cross-server discovery fails
closed.

Eval metrics also record provider-normalized source-inspection calls, returned
result characters/lines, source-tree searches, and scratch-checker calls. New
runs use the semantic information-source policy. Retrospective Codex runs whose
outer `/bin/bash -lc` wrapper erased that policy are explicitly labelled
`legacy_command_heuristic`; missing tool-use authority is `available=false`,
not zero. Per-producer timing remains a planned extension. Telemetry extends the audit sink, not the agent surface, and
reasoning text is never used as source-read authority.

Feature evaluation derives from these records rather than guessing from prompt
text.

## 13. Testing pyramid

1. Contract tests: immutability, state/event provenance, typed invariants.
2. Producer unit tests: positive, negative, ambiguous, and abstention cases.
3. Pipeline tests: multiple features compose without pass replacement.
4. Certification tests: exact state/payload/event binding and no mutation.
5. Admission tests: manifest isolation, deduplication, byte/cardinality caps.
6. Presentation tests: generic rendering and byte-identical empty treatment.
7. Synthetic plus real second-consumer architecture tests.
8. Deterministic live sentinel per exact-action family.
9. Single-state micro A/B.
10. Full managed L1/audit/treatment with counterbalanced arm scheduling.

Higher levels never substitute for lower-level correctness, and micro efficacy
never substitutes for full-route economics.

## 14. Recovery-foundation checkpoint

The current implementation has completed the strategy-boundary migration:

1. M05 `losslessness_certificate_application` is absent from `main`; its
   frozen SC2 implementation and validation material live only on
   `compiler-proactive`.
2. The proactive M07 package, audit/treatment profiles, and active validation
   launchers are removed. Generic declaration parsing, application signatures,
   proof-slot binding, lowering, and certification remain shared.
3. M04 `program_operation_readiness` is internal/audit-only. The old standing
   changed-fact treatment profile is removed.
4. `CompilerProfile` contains only feature activations and delivery-policy IDs.
   `ActivationPlan` owns loading/P2/P3/P4/certification execution;
   `ResolvedDeliveryPlan` independently owns exposure, lifetime, compatibility,
   checked policy rejection reasons, per-policy budgets, and a non-additive
   aggregate compiler-Markdown budget.
5. Rejected-operation parsing is shared typed P2 state:
   `FailureObservation -> AttemptedOperationIR`. It preserves event, occurrence,
   `StateRef`, committed prefix, operation, and resource identity. P2 and P4
   share one balanced single-operation scanner; a second dot-terminated tactic,
   tactical combinator, comment, newline, or malformed delimiter fails closed.
6. The B1/B2/B4 policy lives in the removable SC1
   `operation_binding_repair` feature; B1 and B2 losslessness apply/call
   semantic resolution and probability/multi-slot B2/B4 resolution are native
   and share that one recovery owner. Direct applications require native
   result/current-goal convertibility; certificate-backed calls require exact
   native certificate/callee matching followed by complete-call preflight.
   Multi-candidate B24 additionally materializes an exact-population
   `ApplicationApplicability`. Generic P4 rejects an action whose actual
   tactic changes the attempted operation/resource or contains an unbounded
   route-changing tactic chain.
7. M15 is only the shared failure-linked delivery composition: exact
   `CurrentStateFailure`, `commitment_relative`, once per exact occurrence,
   and at most one item. Each semantic feature owns a separate complete-
   Markdown numerical policy; the global compiler-Markdown ceiling is not a
   feature budget.
   The inventory and dependency formula are frozen by tests and feature
   registration contracts.
8. Recovery slices submit typed claims for the exact attempted-operation
   occurrence. Zero owners abstain; one consistent owner may lower; multiple,
   duplicate (including two evidence variants from one feature), or inconsistent
   claims fail closed with an audit reason. Catalog
   order and presentation cardinality never choose the semantic owner.
9. Manager, service, generic P1-P4 orchestration, renderer, and shared
   contracts contain no semantic feature-ID branch. EasyCrypt mutation remains
   solely manager-owned.
10. Historical M07/M04/M15 reports and result artifacts are retained as
    provenance. Superseded active producers, profiles, runners, and tests are
    removed rather than preserved through compatibility paths.

The read-only typed-state and proof-term foundations are complete through N1e;
historical N2a validated the branch-confined M05 consumer, while
N2b.1-N2b.3 migrated every implemented SC1 application family. The old shared
Python losslessness and probability semantic binders
are deleted. The next checkpoint is the frozen remote N2b.3
trigger/parity/no-mutation sentinel. Only after it passes should a newly
preregistered L1/hidden-audit/treatment experiment run. This does not authorize
bundling another recovery slice or adding another SC2 producer.

## 15. Architecture acceptance criteria

The foundation is ready for managed experiments only when:

- shared P2/P3 contracts contain no feature-named fields;
- a feature activation atomically controls all of its registered loading,
  P2, P3, P4, and certification contributions, while an independently resolved
  delivery policy controls admission;
- OFF executes no producer, while audit and treatment have identical pass and
  certification sets;
- feature execution is trigger-first: an ineligible recovery-only turn starts
  no compiler input, native projection, loading, P1-P4, or certification work,
  and audit/treatment resolve the same eligible feature set;
- deleting one feature changes no shared pass, manager, service, renderer, or
  other feature;
- feature package names are semantic identities, while ledger and experiment
  IDs remain metadata/configuration;
- P1-P4 preserve the exact `StateRef` and source occurrence;
- every semantic application result records native EasyCrypt build/event
  authority, and that identity participates in semantic cache keys;
- Python declaration/formula/module/proof matching is explicitly lexical and
  no Python-only binding reference is agent-visible;
- proof-term lookup, argument kinds, typing/unification, module restrictions,
  proof matching, holes, and concretization come from native EasyCrypt rather
  than duplicated Python algorithms;
- no old Shannon goal parser, analysis panel, or compatibility adapter is a
  compiler semantic fallback;
- the manager has one feature-agnostic service call;
- every agent-visible compiler value is bound to an exact-state delivery
  trigger and expires with that trigger;
- every candidate has a declared strategy contract, and every
  `commitment_relative` candidate is bound to an authoritative accepted or
  explicit agent commitment;
- CandidateSurface cannot reach presentation without certification/admission;
- ActionSurface rendering is generic by entry kind;
- empty and non-eligible treatments render byte-identically to L1;
- an ordinary `StateRefresh` renders zero proactive compiler bytes and no
  `main` manifest can admit an SC2 exception;
- agent-selected elaboration resolves only the selected operation's mechanical
  slots, abstains on unresolved semantic choices, and leaves mutation to the
  manager-owned runtime;
- compilation and certification never change committed history;
- after the shared native-semantic dependency extension, a synthetic and a real
  consumer need no feature-specific manager/service/turn/renderer branch;
- the losslessness and operation-binding live/no-model sentinels pass;
- M07 proactive treatment cannot be assembled and its historical artifacts do
  not reactivate deleted production code;
- recovery ownership conflict tests pass independently of feature order;
- the historical M05 micro and managed evidence remain reproducible on the
  private `compiler-proactive` branch; and
- L1 has no compiler service, while audit/treatment use the same feature
  compiler and certification set and differ in exposure only through the
  independently resolved delivery plan.

Architectural completeness is not the number of facts emitted. It is the
ability to place every evidence-backed fact on one structured route, delegate
semantic truth to native EasyCrypt, prove exact-state validity, measure its
economic value independently, and remove it without changing the compiler
skeleton.
