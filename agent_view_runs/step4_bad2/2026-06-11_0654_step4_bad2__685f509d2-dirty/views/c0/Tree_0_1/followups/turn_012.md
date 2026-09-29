## 🎯 Current Goal
```
Current goal (remaining: 5)

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

pre = true

(1)  UFCMA.bad1 <- false                                         
(2)  UFCMA.cbad1 <- 0                                            
(3)  UFCMA.bad2 <- false                                         
(4)  UFCMA.cbad2 <- 0                                            
(5)  b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA3(LRO).O).main()
(6)  UF.forged <- false                                          

post = true

[392|check]>
```

## Status
remaining **5** · phase `relational_program` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `seq 6 : (UFCMA.bad2 = false /\ UF.forged = false /\ ROIN.RO.m = empty) 1%r (qde…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
