## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &hr,
  ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
  ns1{hr} =
  filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m{hr}) ns{hr} /\
  ns2{hr} =
  filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m{hr}) ns{hr} /\
  i{hr} = 0 /\
  (UF.forged{hr} = false /\
   UFCMA.bad2{hr} = false /\ RO.m{hr} = empty<:nonce * C.counter, poly_in>) /\
  size Mem.lc{hr} <= qdec =>
  BRA.big predT<:nonce>
    (fun (n0 : nonce) =>
       (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
    ns1{hr} *
  pr_zeropol +
  BRA.big predT<:nonce>
    (fun (n0 : nonce) =>
       (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
    ns2{hr} *
  pr1_poly_out <= qdec%r * maxr pr_zeropol pr1_poly_out
[410|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `ns`
- `undup`
- `map`
- `ciphertext`
- `Mem.lc`
- `ns1`
- `filter`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `auto => />; smt(size_ge0).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
