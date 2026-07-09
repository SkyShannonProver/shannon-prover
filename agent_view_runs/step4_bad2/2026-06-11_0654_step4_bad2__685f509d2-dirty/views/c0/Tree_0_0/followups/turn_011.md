## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
              r : poly_in, t : poly_out}
Bound   : [<=] qdec%r * maxr pr_zeropol pr1_poly_out

pre = true

(1----)  UFCMA.bad1 <- false                                                            
(2----)  UFCMA.cbad1 <- 0                                                               
(3----)  UFCMA.bad2 <- false                                                            
(4----)  UFCMA.cbad2 <- 0                                                               
(5----)  b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA3(LRO).O).main()                   
(6----)  UF.forged <- false                                                             
(7----)  if (size Mem.lc <= qdec) {                                                     
(7.1--)    ns <- undup (map (fun (p : ciphertext) => p.`1) Mem.lc)                      
(7.2--)    ns1 <- filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m) ns          
(7.3--)    ns2 <- filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m) ns       
(7.4--)    i <- 0                                                                       
(7.5--)    while (i < size ns1) {                                                       
(7.5.1)      n <- nth witness<:nonce> ns1 i                                             
(7.5.2)      r <@ LRO.get(n, C.ofintd 0)                                                
(7.5.3)      UF.forged <- UF.forged || test_poly_in n Mem.lc r (oget UFCMA.log.[n])     
(7.5.4)      i <- i + 1                                                                 
(7.5--)    }                                                                            
(7.6--)    i <- 0                                                                       
(7.7--)    while (i < size ns2) {                                                       
(7.7.1)      n <- nth witness<:nonce> ns2 i                                             
(7.7.2)      r <@ LRO.get(n, C.ofintd 0)                                                
(7.7.3)      t <@                                                                       
(     )        UFCMA(LRO).set_bad2(map                                                  
(     )                              (fun (c : ciphertext) =>                           
(     )                                 c.`4 - poly1305_eval r (topol c.`2 c.`3))       
(     )                              (filter (fun (c : ciphertext) => c.`1 = n) Mem.lc))
(7.7.4)      i <- i + 1                                                                 
(7.7--)    }                                                                            
(7----)  }                                                                              

post = UF.forged \/ UFCMA.bad2
[390|check]>
```

## Status
remaining **1** · phase `procedure_frontier` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_subgoals` (+invariant) · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `proc.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
