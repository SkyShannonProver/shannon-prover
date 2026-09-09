# Shannon Prover: proof-construction architecture and boundaries

Status: release-candidate architecture for the reusable Phase-II/III product
and its ChaChaPoly reference adapter, updated 2026-09-05.

This is a contributor reference. For project setup and interpreting results,
use the [usage guide](../../workflow/interleaved/README.md).

The product implementation and stable entry point live under
[`../../workflow/interleaved/`](../../workflow/interleaved/). The controlled
ChaChaPoly reference protocol lives under
[`../../experiments/interleaved_shannon/`](../../experiments/interleaved_shannon/).

## Scope

Shannon Prover has two related workflows:

| workflow | decomposition owner | tactic-level proof owner | acceptance owner |
|---|---|---|---|
| managed lemma proving | human supplies the target lemma | one managed Shannon proof node | canonical `ProverResult` after offline verification |
| interleaved Phase II/III product | one runner-selected outer LLM invents and revises the decomposition | the outer LLM writes directly and may delegate selected helper-lemma boundaries to runner-selected Shannon nodes | the configured whole-file EasyCrypt verifier |

The product is a separate composition above `$prove`, the ordinary orchestrator
and the proof-state compiler. A versioned `InterleavedProject` contract selects
the target, final lemma, include roots, artifact root, lane limits, prompt and
verifier. The product package has no `experiments` import. Evaluation-only
requirements—known-answer exclusion, fixed task projection, comparison horizon
and immutable benchmark regions—belong to reference adapters.

## System map

```text
operator loads one project contract and selects an outer/inner provider pair
                                |
                                v
outer proof agent in the project worktree
  owns game decomposition, lemma boundaries, global proof assembly
  writes/checks the candidate file and decides when to delegate
                                |
                      immutable handoff snapshot
                                v
bounded Shannon job scheduler
  owns queueing, lane capacity, leases, job identity, cancellation and collection
             |                                      |
             v                                      v
managed Shannon proof node A              managed Shannon proof node B
  ProofNodeManager                          ProofNodeManager
        |                                        |
        +--> ReplSessionManager --> EasyCrypt <--+
        |
        `--> ProofStateCompilerService (P1 -> P2 -> P3 -> P4)
                    |
             bounded ActionSurface
             |                      |
       verified proof        bounded progress/checkpoint capsule
             |                      |
             +-----------> outer agent <-----------+
                                |
                                v
runner-owned whole-file verifier
  final lemma exists + no admits in target + locked EasyCrypt replay
  reference adapter additionally protects target statement and immutable regions
```

This is a composition of two control planes. The outer plane owns the
cross-lemma proof program. Each inner node owns one stateful tactic search. The
compiler remains inside an inner node and has no authority over decomposition,
job scheduling, or winner selection.

The generic verifier does not freeze the original theorem, definitions,
assumptions, or dependency files. A project that requires those protections
must supply a stricter verifier; the ChaChaPoly adapter does so for its fixed
task. A generic successful replay establishes the checked development under
its submitted assumptions, not identity with an earlier security statement.

## Layer 1: proof-state compiler

The compiler is feature-neutral infrastructure for one exact EasyCrypt state.
Its fixed passes are P1 projection, P2 frontend, P3 middle end and P4 backend.
It may remove mechanical burden inside an agent-selected commitment: native
name and argument binding, exact syntax realization, compound-boundary
diagnosis, or a certified current-state repair.

It does not:

- choose a game hop, lemma graph or delegation boundary;
- rank proof strategies;
- read an outer agent's private reasoning;
- mutate the proof session; or
- decide that a theorem has been proved.

The normative compiler contract is
[`../design/proof_state_compiler_v2.md`](../design/proof_state_compiler_v2.md).

## Layer 2: managed proof-node infrastructure

Every inner Shannon job uses the ordinary managed proof stack:

- `ProofNodeManager` binds one advertised intent to the exact current state;
- `ReplSessionManager` is the sole live EasyCrypt mutation owner;
- the private MCP endpoint exposes only the invocation-bound proof tool;
- provider sessions are fixed by the runner and checked against recorded
  binary/model identity;
- safe stop preserves a manager-derived accepted prefix and, when available,
  a compatible open checkpoint; and
- only the canonical run-level verifier may publish a verified node result.

Source navigation is separately manager-owned and confined to the prepared
proof-stripped task plus configured EasyCrypt library roots. It returns bounded
search, numbered-range and native declaration-resolution results; it is not a
generic shell or filesystem escape.

The provider-neutral node/tool contract is documented in
[`proof_tool_infrastructure.md`](proof_tool_infrastructure.md), and final node
success ownership in [`proof_terminal_outcome.md`](proof_terminal_outcome.md).

## Layer 3: interleaved outer/inner product

`workflow/interleaved` adds orchestration above ordinary proof nodes:

1. `python -m workflow.interleaved --project ...` loads and hashes the project
   contract, authenticates the selected profiles, records provenance, renders
   the project prompt and launches the outer agent.
2. A reference adapter may first create a clean sparse worktree and exclude a
   known answer; ordinary product projects do not need evaluation isolation.
3. The outer agent constructs the global proof and may submit coherent lemma
   boundaries to `shannon_jobs.py`.
4. A job snapshots the candidate, handoff note and resource anchors before it
   enters an isolated lane within the project's configured capacity.
5. `warm_handoff.py` natively replays an outer partial proof and binds the exact
   accepted boundary. A Shannon node replays the prefix again and fails closed
   on drift.
6. A running job may expose bounded manager-confirmed live progress. A stopped
   incomplete job returns a bounded progress capsule rather than collapsing to
   a status code.
7. A continuation names its parent job. The scheduler privately resolves the
   matching checkpoint and a fresh manager performs the one cold replay.
8. The outer agent decides whether to integrate the prefix, continue the job,
   redesign the boundary or proceed directly.
9. The runner joins or cancels outstanding work and invokes the project-owned
   whole-file final verifier.

The configured Shannon lanes are bounded capacity, not extra outer agents.

Collection validates the exact imported lemma under its preceding declarations
in a temporary file with the original filename, independently of unfinished
downstream source. Section/theory framing is closed for this native check; the
target proof must contain neither `admit` nor `abort`. This is explicitly
`target_lemma_under_declared_dependencies`, not whole-project verification.
Source/statement binding and the proof-body lease still apply. A source edit
during checking causes a retry without overwriting the outer's work. Final
task success still requires the project-owned whole-file verifier.

The scheduler owns candidate snapshots, source leases and atomic writeback;
`workflow.interleaved.verify` owns the configured verifier invocation and the
shared native import check. Collection calls the project's `--check-import`
entry point, so reference-specific source restrictions remain in the reference
verifier, not in the scheduler or the generic product. Only the current child
response is consumed; missing support or malformed evidence fails closed.

Delegation is nonblocking, but an active boundary lease prevents the outer
agent from silently editing the same proof body while a job is working on its
snapshot. The ChaChaPoly reference contract fixes capacity at two.

## Layer 4: artifacts, evidence and browsing

The repository currently has three distinct artifact shapes. They should not
be called one generic "trace":

| artifact | purpose | current browser support |
|---|---|---|
| `agent_view_runs/<lemma>/<run>/` | one managed proof-node timeline: rendered turns, intents, manager results and reconstructed proof | supported by `bundle_browser/` |
| configured product artifact root | complete local outer-run directory: project identity, outer events, scheduler state, inner job artifacts and final verification | ignored/raw; not browser-compatible |
| `artifacts/interleaved_shannon/official_<timestamp>/` | complete local outer-run directory: manifest, outer events, scheduler state, inner job artifacts and final verification | ignored/raw; not browser-compatible |

The bundle browser therefore shows proof-node behavior, not the complete
outer/inner lineage. A reviewer-facing interleaved browser would need a new
manifest schema with an outer timeline, job spans, handoff edges, checkpoint
growth and final-verifier evidence. Reinterpreting an interleaved directory as
an ordinary lemma bundle would lose those relationships.

## Evidence boundary

A final verified theorem establishes feasibility for that pinned run. It does
not by itself establish that interleaving is faster than pure Opus, that the
compiler caused the result, or that an incomplete Shannon job independently
proved its delegated lemma. Timing comparisons must disclose continuation
segments, runner commit, provider builds, prompt, model-visible horizon,
watchdog, queue time and final verification.

Use these outcome labels consistently:

- **verified theorem**: the runner's final whole-file gate passed;
- **verified Shannon lemma**: one inner canonical `ProverResult` verified the
  delegated declaration;
- **useful incomplete contribution**: manager-derived accepted progress was
  integrated into the final proof;
- **valid incomplete**: proof search ran but did not verify;
- **infrastructure invalid**: the intended proof search did not run under the
  declared contract.

## Release boundary

The selected release-candidate surface is the **interleaved product plus one
reference adapter**: `workflow/interleaved/`, this architecture document, the
exact `experiments/interleaved_shannon/` subtree, its pinned three-file
ChaChaPoly task, and existing locked runtime dependencies. The allowlist does
not make the rest of `experiments/` public.

Raw `artifacts/interleaved_shannon/` directories, historical development
reports and all unrelated experiment scaffolding are outside this surface.
The bundle browser continues to support managed single-lemma bundles only; it
must not flatten an outer/inner run into that schema. Publication still
requires forbidden-content verification, built-export link checking and fresh
export preflights for both the product entry point and the reference adapter.
These checks establish packaging and reproducibility; they do not show that
every decomposition succeeds or make a causal speed claim.
