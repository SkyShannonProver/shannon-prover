## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
eqLRO: equiv[ UFCMA3(RO).distinguish  ~ UFCMA3(LRO).distinguish :
               ((glob A){1}, BNR.lenc{1}, BNR.ndec{1}, UF.forged{1},
                UFCMA.bad1{1}, UFCMA.bad2{1}, UFCMA.cbad1{1}, UFCMA.cbad2{1},
                UFCMA.log{1}, Mem.lc{1}, Mem.log{1}, SplitC2.I2.RO.m{1},
                SplitD.ROF.RO.m{1}) =
               ((glob A){2}, BNR.lenc{2}, BNR.ndec{2}, UF.forged{2},
                UFCMA.bad1{2}, UFCMA.bad2{2}, UFCMA.cbad1{2}, UFCMA.cbad2{2},
                UFCMA.log{2}, Mem.lc{2}, Mem.log{2}, SplitC2.I2.RO.m{2},
                SplitD.ROF.RO.m{2}) /\
               RO.m{1} = RO.m{2} /\ arg{1} = arg{2} ==>
               res{1} = res{2} /\
               ((glob A){1}, BNR.lenc{1}, BNR.ndec{1}, UF.forged{1},
                UFCMA.bad1{1}, UFCMA.bad2{1}, UFCMA.cbad1{1}, UFCMA.cbad2{1},
                UFCMA.log{1}, Mem.lc{1}, Mem.log{1}, SplitC2.I2.RO.m{1},
                SplitD.ROF.RO.m{1}) =
               ((glob A){2}, BNR.lenc{2}, BNR.ndec{2}, UF.forged{2},
                UFCMA.bad1{2}, UFCMA.bad2{2}, UFCMA.cbad1{2}, UFCMA.cbad2{2},
                UFCMA.log{2}, Mem.lc{2}, Mem.log{2}, SplitC2.I2.RO.m{2},
                SplitD.ROF.RO.m{2})]
------------------------------------------------------------------------
Context : hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
              r : poly_in, t : poly_out}
Bound   : [<=] qdec%r * maxr pr_zeropol pr1_poly_out

pre =
  (UFCMA.bad2 = false /\
   UF.forged = false /\ RO.m = empty<:nonce * C.counter, poly_in>) /\
  size Mem.lc <= qdec

(1--)  ns <- undup (map (fun (p : ciphertext) => p.`1) Mem.lc)                      
(2--)  ns1 <- filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m) ns          
(3--)  ns2 <- filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m) ns       
(4--)  i <- 0                                                                       
(5--)  while (i < size ns1) {                                                       
(5.1)    n <- nth witness<:nonce> ns1 i                                             
(5.2)    r <@ LRO.get(n, C.ofintd 0)                                                
(5.3)    UF.forged <- UF.forged || test_poly_in n Mem.lc r (oget UFCMA.log.[n])     
(5.4)    i <- i + 1                                                                 
(5--)  }                                                                            
(6--)  i <- 0                                                                       
(7--)  while (i < size ns2) {                                                       
(7.1)    n <- nth witness<:nonce> ns2 i                                             
(7.2)    r <@ LRO.get(n, C.ofintd 0)                                                
(7.3)    t <@                                                                       
(   )      UFCMA(LRO).set_bad2(map                                                  
(   )                            (fun (c : ciphertext) =>                           
(   )                               c.`4 - poly1305_eval r (topol c.`2 c.`3))       
(   )                            (filter (fun (c : ciphertext) => c.`1 = n) Mem.lc))
(7.4)    i <- i + 1                                                                 
(7--)  }                                                                            

post = UF.forged \/ UFCMA.bad2
[395|check]>
```

## Status
remaining **4** · phase `relational_program` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `if.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
