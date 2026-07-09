# EasyCrypt Analysis Schema Inventory

The analysis layer uses JSON-like dictionaries because AgentView,
CommandSummary, and tool artifacts need stable serializable data.  This file
names the core fact shapes and the fields downstream passes may rely on.

These are contracts, not closed classes. Producers may add fields, but they
should not remove or repurpose the fields listed here without updating tests
and consumers.

## Conventions

- Every top-level frontend/planner result should include `schema_version` and
  `kind` when it is a standalone resource.
- Empty lists and empty dictionaries are preferred over missing keys for known
  optional collections.
- `action_type` must be one of `inspection_action`, `strategy_hint`,
  `probe_tactic`, or a documented avoid/compatibility value.
- A fact that came from search or static analysis is evidence, not a verified
  proof step.
- String fields preserve EasyCrypt spelling where useful; canonical fields use
  normalized keys for comparison.

## `GoalStateFact`

Producer:

- `session_projection.py`
- `ec_native_state.py`
- `ec_goal_parser.py` as fallback parser input

Consumers:

- `session_agent_view.py`
- `ec_proof_ir.py`
- `session_tool_view.py`

Required fields:

| Field | Meaning |
| --- | --- |
| `goal_type` | Current goal family, such as `pRHL`, `phoare`, or `probability` |
| `num_remaining` | Open goal count when determined |
| `num_remaining_determined` | Whether the count is known |
| `fact_source` | `ec_native_goal_state` or fallback source such as `pretty_goal_text` |
| `authority` | `ec_native_ground_truth` for EC facts, otherwise fallback authority |
| `authority_rank` | Numeric ordering where EC-native artifacts outrank fallback parser facts |
| `ec_ground_truth` | Whether the fact came from an EC-native wrapper artifact |
| `native_artifact` | ToolView artifact path when available |

Contract:

- EC-native goal artifacts are authoritative over pretty stdout parsing.
- Pretty parsing remains a recall/compatibility fallback and must be labeled
  as such.
- Downstream passes may canonicalize or score goal facts, but must not silently
  replace EC's typed state when it is available.

## `PrTerm`

Producer:

- `ec_pr_canonical.py::parse_pr_terms`

Consumers:

- `ec_lemma_index.py`
- `ec_pr_obligations.py`
- `ec_pr_path_planner.py`
- `ec_pr_elaborator.py`

Required fields:

| Field | Meaning |
| --- | --- |
| `game_expr` | Raw expression inside `Pr[...]` before memory/event splitting |
| `game_key` | Canonical game/module key used for matching endpoints |
| `memory` | Memory expression, usually `&m` |
| `event` | Event/predicate after `:`; defaults may fill this |
| `endpoint` | Structured procedure endpoint |

`endpoint` fields:

| Field | Meaning |
| --- | --- |
| `module_expr` | Module/functor expression before the final procedure call |
| `procedure` | Final procedure name |
| `procedure_args` | Arguments to the final procedure call |
| `canonical` | Stable endpoint rendering |
| `module_root` | Outermost module/functor name |

Contract:

- `game_key` is for structural matching, not user display.
- `event` must stay visible for bad-event and bound matching.
- Producers must handle balanced brackets rather than regex-only splitting.

## `ProgramIR`

Producer:

- `ec_program_ir.py::build_program_ir`

Consumers:

- `ec_procedure_frontend.py`
- `ec_probabilistic_vc.py`
- `ec_procedure_actions.py`
- `ec_proof_ir.py`

Required top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | ProgramIR schema version |
| `kind` | `easycrypt_program_ir` |
| `fact_source` | `ec_native_program_ast` or fallback source such as `pretty_program_text` |
| `authority` | `ec_native_ground_truth` or fallback authority |
| `authority_rank` | Numeric ordering where EC-native AST artifacts outrank fallback parsing |
| `ec_ground_truth` | Whether statement facts came from an EC-native wrapper artifact |
| `native_artifact` | ToolView artifact path when available |
| `call_sites` | Calls found in left/right programs |
| `frontier` | Current side-local frontier statements |
| `program_diff` | Alignment/edit-script facts |

Important `call_sites` fields:

| Field | Meaning |
| --- | --- |
| `procedure` | Canonical procedure path |
| `side` | Left or right side |
| `is_frontier_call` | Whether the call is currently callable |
| `requires_cut_to_frontier` | Whether wp/seq/sp work is needed first |
| `frontier_status` | Human-readable frontier classification |

Contract:

- ProgramIR describes program shape. It does not choose named lemmas.
- If a call is not at the frontier, ProgramIR should expose why, not hide it.
- If EC-native program AST facts are available, ProgramIR treats them as the
  source of truth and labels pretty-program extraction as fallback only.

## `SemanticLemmaCandidate`

Producer:

- `ec_lemma_index.py`

Consumers:

- `ec_pr_obligations.py`
- `ec_menu_actions.py`
- `ec_proof_ir.py`
- compiler smoke tests

Required fields:

| Field | Meaning |
| --- | --- |
| `lemma` | Declaration name |
| `name` | Alias for consumers expecting a generic name field |
| `source` | Where the candidate came from |
| `source_path` | File or session artifact path |
| `fact_source` | Fact provenance such as `ec_native_print`, `ec_native_search`, or `source_scan` |
| `authority` | Authority tier; EC-native artifacts use `ec_native_ground_truth` |
| `authority_rank` | Numeric ordering where EC-native artifacts outrank source fallback |
| `ec_ground_truth` | Whether this declaration came from an EC-native wrapper artifact |
| `declaration_kind` | `lemma`, `local lemma`, `equiv`, `axiom`, etc. |
| `declaration` | Source declaration text |
| `semantic_tags` | Shape tags such as `pr_bound` or `pr_rewrite` |
| `pr_game_keys` | Canonical game keys seen in the declaration |
| `pr_events` | Events seen in declaration `Pr` terms |

Candidate-query fields:

| Field | Meaning |
| --- | --- |
| `score` | Structural match score against the current goal |
| `goal_shape` | Bound/rewrite shape used for scoring |
| `reason` | Why this candidate is relevant |

Contract:

- Names are identifiers only. Matching must come from declaration shape, game
  keys, events, tags, and scores.
- If an EC-native artifact and a source-scan fallback describe the same lemma,
  the EC-native artifact is the ground truth and must be ranked first.
- A candidate is not runnable until name resolution and instantiation binding
  say enough about its signature.

## `NameResolutionFact`

Producer:

- `ec_name_resolution.py::resolve_proof_ir_names`

Consumers:

- `ec_instantiation_binding.py`
- action rendering
- ProofIR ranking and diagnostics

Required fields:

| Field | Meaning |
| --- | --- |
| `name` | Requested handle name |
| `unqualified_name` | Name without clone/module prefix |
| `handle_kind` | Intended use family, such as `pr_rewrite` or `call_equiv` |
| `resolution_status` | Exact status, e.g. `resolved_local_declaration` |
| `signature_lookup_action` | Read-only action such as `-where Foo` |
| `exact_signature_known` | Whether the declaration/signature is known |
| `requires_instantiation` | Whether explicit arguments are needed |
| `tactic_template` | Template before binding, if known |
| `parameter_slots` | Typed signature slots |

Contract:

- Unknown or cloned names should become lookup actions, not guessed tactics.
- `exact_signature_known = false` should downgrade apply/rewrite/call actions
  to inspection or strategy guidance.

## `InstantiationBinding`

Producer:

- `ec_instantiation_binding.py::build_instantiation_bindings`

Consumers:

- ProofIR candidate enrichment
- action ranking

Required top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Instantiation binding schema version |
| `kind` | `easycrypt_instantiation_binding` |
| `items` | Per-name binding facts |
| `summary` | Slot/candidate counts |

Per-item fields:

| Field | Meaning |
| --- | --- |
| `name` | Handle name |
| `slots` | Typed module/memory/type/value slots |
| `instantiated_templates` | Concrete tactic templates only when high-confidence |

Slot fields:

| Field | Meaning |
| --- | --- |
| `kind` | `module_arg`, `memory_arg`, `type_arg`, `value_arg`, etc. |
| `placeholder` | Placeholder in the unresolved tactic template |
| `candidates` | Candidate bindings with value and confidence |

Contract:

- Low-confidence value slots must not emit runnable tactic templates.
- Binding suggests arguments; backend probes still decide whether tactics work.

## `PrObligation`

Producer:

- `ec_pr_obligations.py`

Consumers:

- Pr action rendering
- ProofIR phase guidance
- diagnostics and smoke tests

Required top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Pr obligation schema version |
| `kind` | `easycrypt_pr_obligation_plan` |
| `available` | Whether there is a live Pr obligation |
| `primary_strategy` | Main middle-end strategy |
| `obligations` | Ordered obligation facts |
| `summary` | Boolean/count summary for phase guidance |

Per-obligation fields:

| Field | Meaning |
| --- | --- |
| `kind` | Such as `pr_union_bound_plan`, `pr_semantic_bound_lookup` |
| `why` | Planner explanation |
| `evidence` | Typed facts supporting the obligation |
| `action_boundary` | `strategy_only`, `inspection_before_apply`, etc. |

Contract:

- The planner may say what is needed. It must not commit the proof step.
- Missing bound resources should stay visible as obligations.

## `PrPathPlan`

Producer:

- `ec_pr_path_planner.py::build_pr_path_plan`

Consumers:

- `ec_pr_actions.py`
- ProofIR recommendations
- diagnostics

Required fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Path planner schema version |
| `kind` | `easycrypt_pr_path_plan` |
| `endpoints` | Source/target endpoint pairs |
| `edges` | Rewrite/have/synthetic edges |
| `paths` | Complete path candidates |
| `partial_paths` | Useful but incomplete frontiers |
| `recommended_path` | Preferred complete path, if any |
| `arithmetic_plan` | Bound/arithmetic chain facts |
| `summary` | Counts and shape flags |

Important path fields:

| Field | Meaning |
| --- | --- |
| `status` | `complete` or `partial` |
| `relation` | Equality, inequality, or arithmetic relation |
| `lemmas` | Lemmas on the path |
| `hops` | Edge details |
| `frontier_key` | Current unmatched frontier for partial paths |

Contract:

- Compound arithmetic lemmas should not be downgraded into simple rewrite edges.
- Partial paths are useful resources and should not suppress visibility of the
  missing bridge/bound obligation.

## `NativeSearchFact`

Producer:

- `ec_native_ast_search.py`

Consumers:

- `ec_menu_actions.py`
- future resource feedback loop

Required fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Native-search schema version |
| `kind` | `easycrypt_native_ast_search` |
| `available` | Whether search is relevant |
| `suggested_queries` | Queries not yet observed |
| `observed_queries` | Current-session queries already run |
| `hits` | Parsed search hits |

Hit fields:

| Field | Meaning |
| --- | --- |
| `name` | Lemma/declaration name |
| `kind` | Declaration kind |
| `declaration` | Parsed hit declaration, if available |
| `query` | Query that produced the hit |
| `artifact` | Tool artifact path |

Contract:

- Search facts produce inspection actions. They do not produce `apply` or
  `rewrite` actions directly.
- Search artifacts must come from the current session.

## `ActionCandidate`

Producer:

- `ec_menu_actions.py`
- `ec_pr_actions.py`
- `ec_procedure_actions.py`
- ProofIR compatibility wrappers

Consumers:

- ProofIR ranking and legality
- AgentView recommendations
- CommandSummary workspace slices through ProofContextView actions

Required fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable action identifier |
| `tactic` | Command text or strategy text |
| `tactic_family` | Phase/family classification |
| `action_type` | Inspection, strategy, or probe classification |
| `cost` | Rough cost tier |
| `why` | Why this action is shown |
| `preconditions` | Conditions before use |
| `preserves` | Abstractions/resources preserved |
| `destroys` | Abstractions/resources destroyed |
| `cost_factors` | Machine-readable ranking details |
| `confidence` | Confidence tier |
| `readiness` | Stable user-facing readiness (`inspect_first`, `probe_first`, etc.) |
| `effect` | Whether the action is read-only, planning-only, probe-only, mutating, or avoid |
| `provenance` | Source/authority metadata used by contract validation |

Contract:

- `inspection_action` must not mutate proof state.
- `strategy_hint` may be non-tactic prose and should not be sent directly as a
  tactic.
- `probe_tactic` means probeable, not proven.
- fallback or unresolved source/name facts must not become `probe_tactic` or
  `runnable_tactic` before inspection.
- Action renderers consume existing facts; they do not discover new ones.

## `PrBridgeCandidate`

Producer:

- `ec_pr_bridge_frontend.py`

Consumers:

- `ec_pr_path_planner.py`
- `ec_pr_actions.py`
- ProofIR resources

Required fields:

| Field | Meaning |
| --- | --- |
| `edge_kind` | `synthetic_bridge`, `verified_bridge`, or `pr_rewrite` |
| `relation` | Equality/inequality relation |
| `lhs_game` | Source game key |
| `rhs_game` | Target game key |
| `tactic` | Probeable tactic when the bridge is complete |
| `action_hint` | Tactic or structural explanation for path planning |
| `adapter_module` | Adapter module that instantiates the bridge, if any |
| `bridge_lemma` | Underlying declaration used as a bridge/rewrite, if any |
| `reason` | Why this bridge edge is relevant |

Contract:

- A structural bridge without a concrete tactic is planner context, not a
  probeable action.
- Bridge candidates describe endpoint movement; action modules decide how to
  expose them to the prover.

## `EquivExactCloser`

Producer:

- `ec_equiv_closers.py`

Consumers:

- ProofIR handles
- pRHL/equiv action rendering

Required fields:

| Field | Meaning |
| --- | --- |
| `lemma` | Matching equiv lemma |
| `tactic` | Suggested exact tactic |
| `lhs_proc` | Lemma left procedure |
| `rhs_proc` | Lemma right procedure |
| `arguments` | Arguments inferred from binders/current hypotheses |
| `missing_arguments` | Required equiv premises not found in context |
| `fully_bound` | Whether the tactic can be probed as-is |
| `fact_source` | Declaration source |
| `authority` | Authority tier |

Contract:

- Fully-bound closers may become `probe_tactic`.
- Closers with missing arguments must remain `strategy_hint`.
- Source-scan closers are resource facts; future EC-native `-where` evidence may
  upgrade their authority.

## `ProofIR`

Producer:

- `ec_proof_ir.py::build_proof_ir`

Consumers:

- AgentView
- CommandSummary workspace slices
- tests and diagnostics

Required fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | ProofIR schema version |
| `kind` | `easycrypt_proof_ir` |
| `current_layer` | Current abstraction layer |
| `goal_kind` | Normalized goal family |
| `goal_type` | Parser goal type |
| `resources` | ProgramIR, Pr plans, handles, bindings |
| `liveness` | Which resources remain usable |
| `destructive_moves` | Moves already taken |
| `phase` | Phase guidance and legality |
| `candidate_menu` | Ranked action candidates |
| `diagnostics` | Structured diagnostics |

Contract:

- ProofIR is the assembler and compatibility surface.
- New parser/resource/action behavior should go into focused modules and then
  be assembled here.

## Schema Evolution Rules

1. Add fields instead of changing meanings.
2. Prefer explicit `available`, `status`, and `reason` fields over absent data.
3. Keep existing IDs stable unless a test is updated for a deliberate breaking
   change.
4. If a field becomes required by another layer, add a direct module test and a
   compiler smoke row when benchmark generalization is involved.
5. Keep docs, producer tests, and consumer tests moving together.
