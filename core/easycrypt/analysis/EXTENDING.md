# Extending The EasyCrypt Analysis Compiler

This is the entry map for future agents adding compiler features.  Start here
before editing `ec_proof_ir.py`.

## Pass Taxonomy

```text
EC/native state boundary
  -> canonical frontend
  -> resource/symbol pass
  -> planner/obligation pass
  -> action renderer
  -> ProofIR facade
  -> prover-facing view / backend
```

Each pass should emit typed JSON-like facts.  Tactic strings belong only in the
action renderer or backend compatibility boundary.

## Where A New Feature Belongs

Use this placement rule before writing code:

| Need | Add or change |
| --- | --- |
| EC ground truth, native artifact provenance, pretty-text fallback labels | state boundary: `session_projection.py`, `ec_native_state.py` |
| Parse or normalize `Pr[...]`, program statements, loop/sample/branch shapes | canonical frontend: `ec_pr_canonical.py`, `ec_program_ir.py`, `ec_procedure_frontend.py` |
| Find project declarations, names, clone-resolved signatures, instantiation slots | resource/symbol pass: `ec_lemma_index.py`, `ec_name_resolution.py`, `ec_instantiation_binding.py`, `ec_pr_elaborator.py` |
| Compose bridge paths, bound obligations, invariant skeletons, VC plans | planner/obligation pass: `ec_pr_obligations.py`, `ec_pr_path_planner.py`, `ec_pr_bridge_frontend.py`, `ec_dataflow_invariant.py` |
| Turn existing facts into `-where`, `rewrite`, `call`, `while`, `byequiv` menu items | action renderer: `ec_menu_actions.py`, `ec_pr_actions.py`, `ec_procedure_actions.py` |
| Assemble pass outputs into stable JSON for AgentView/CommandSummary | facade: `ec_proof_ir.py` |

## Do Not Add To ProofIR Unless

Only edit `ec_proof_ir.py` directly when the change is one of these:

- wiring a new pass into the build sequence
- merging pass facts into `resources.handles`
- preserving or adapting compatibility output
- adding phase/liveness summary glue that consumes already-typed facts

Do not add these to ProofIR:

- source or pretty-goal parsers
- project lemma/name lookup
- bridge/path synthesis
- tactic rendering rules
- action ranking or phase deferral policy

If a feature feels like an `if goal_kind == ...` block, first ask what typed
fact it should produce and which pass owns that fact.

## Required Checklist

Before landing a compiler feature:

1. Name the typed fact it produces.
2. State the producing pass and consuming pass.
3. Mark authority/provenance: EC-native ground truth, legacy lookup, current
   source scan, out-of-context source scan, or heuristic.
4. Decide whether the user-facing result is `inspection_action`,
   `strategy_hint`, `probe_tactic`, `runnable_tactic`, or `avoid_action`.
5. Add a direct pass test and, for benchmark generalization, a smoke matrix row.
6. Update `SCHEMAS.md` or `CONTRACTS.md` when a fact shape or layer contract is
   new.

## Ground-Truth Rule

EC-native wrappers (`-where`, `-members`, `-search-skeleton`, and future native
goal/program JSON) outrank local parsing.  Source scans are recall fallbacks:
they may propose inspection actions, but they must not become runnable tactics
until EC scope/signature evidence is available.
