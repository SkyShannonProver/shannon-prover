## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b, b0, b1, b2 : bool, i : int, n : nonce,
              ns, ns1, ns2 : nonce list, r : poly_in, t : poly_out}

pre = true

( 1)  UFCMA.bad1 <- false                                        
( 2)  UFCMA.cbad1 <- 0                                           
( 3)  UFCMA.bad2 <- false                                        
( 4)  UFCMA.cbad2 <- 0                                           
( 5)  UFCMA.log <- empty<:nonce, associated_data * message * tag>
( 6)  RO.m <- empty<:nonce * C.counter, poly_in>                 
( 7)  SplitC2.I2.RO.m <- empty<:nonce * C.counter, poly_out>     
( 8)  SplitD.ROF.RO.m <- empty<:nonce * C.counter, block>        
( 9)  Mem.log <- empty<:ciphertext, plaintext>                   
(10)  Mem.lc <- []                                               
(11)  BNR.lenc <- []                                             
(12)  BNR.ndec <- 0                                              
(13)  b2 <@ A(BNR(CPA_CCA_Orcls(UFCMA(LRO).O))).main()           
(14)  b1 <- b2                                                   
(15)  b0 <- b1                                                   
(16)  b <- b0                                                    

post =
  ! ! (false = false /\
       UFCMA.bad2 = false /\ RO.m = empty<:nonce * C.counter, poly_in>)

[425|check]>
```

## Status
remaining **2** · phase `procedure_frontier` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_subgoals` (+invariant) · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `wp; inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
