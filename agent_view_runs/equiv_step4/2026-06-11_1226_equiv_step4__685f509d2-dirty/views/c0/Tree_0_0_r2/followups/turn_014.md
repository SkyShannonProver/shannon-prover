## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

------------------------------------------------------------------------
forall &1 &m &2,
  UF.forged{1} = UF.forged{m} /\ UFCMA.bad2{1} = UFCMA.bad2{m} =>
  UF.forged{m} = UF.forged{2} /\ UFCMA.bad2{m} = UFCMA.bad2{2} =>
  (UFCMA.bad2{1} = UFCMA.bad2{2} /\ UF.forged{1} = UF.forged{2}) /\
  (UF.forged{2} \/ UFCMA.bad2{2}) = (UF.forged{2} \/ UFCMA.bad2{2})
[554|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `UF.forged`
- `UFCMA.bad2`

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `relational_program` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `(have ens: ns{1} = ns{2} by rewrite hns1 hns2 hlc); (have ens1: ns1{1} = ns1{2}…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
