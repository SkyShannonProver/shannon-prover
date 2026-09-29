## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
&hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list, r : poly_in,
     t : poly_out}
szlc: size Mem.lc{hr} <= qdec
nE: BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})
      (fun (n0 : nonce) =>
         (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
      (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) =
    BRA.big
      (predC (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr}))
      (fun (n0 : nonce) =>
         (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
      (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}))
------------------------------------------------------------------------
BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr})
  (fun (n0 : nonce) =>
     (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
  (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) +
BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})
  (fun (n0 : nonce) =>
     (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
  (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) =
(size Mem.lc{hr})%r
[413|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `BRA.big`
- `nonce`
- `C.ofintd`
- `SplitC2.I2.RO.m`
- `hr`
- `size`
- `filter`
- `ciphertext`

**Visible hypotheses:**
- `szlc: size Mem.lc{hr} <= qdec`
- `nE: BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **5** · phase `ambient_logic` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `have key : BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
