## 🎯 Current Goal
```
Current goal (remaining: 6)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
              r : poly_in, t : poly_out}
Bound   : [<=] 1%r

pre =
  ns = undup (map (fun (p : ciphertext) => p.`1) Mem.lc) /\
  ns1 = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m) ns /\
  ns2 = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m) ns /\
  i = 0 /\
  (UF.forged = false /\
   UFCMA.bad2 = false /\ RO.m = empty<:nonce * C.counter, poly_in>) /\
  size Mem.lc <= qdec

(1--)  while (i < size ns1) {                                                  
(1.1)    n <- nth witness<:nonce> ns1 i                                        
(1.2)    r <@ LRO.get(n, C.ofintd 0)                                           
(1.3)    UF.forged <- UF.forged || test_poly_in n Mem.lc r (oget UFCMA.log.[n])
(1.4)    i <- i + 1                                                            
(1--)  }                                                                       
(2--)  i <- 0                                                                  

post = !UF.forged
[404|check]>
```

## Status
remaining **6** · phase `procedure_frontier` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_subgoals` (+invariant) · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `conseq (_: _ ==> true) => //.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
