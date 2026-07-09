## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

hff: equiv[ Orcl.f  ~ Orcl.f :
             arg{1} = arg{2} /\
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2}) ==>
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2})]
------------------------------------------------------------------------
&1 (left ) : {t1, t2, n, n0 : nonce, r, r0 : poly_in, t, t0 : poly_out}
&2 (right) : {t1, t2, n, n0 : nonce, r, r0 : poly_in, t, t0 : poly_out}

pre =
  ((((UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
      Mem.lc{1}, SplitC2.I2.RO.m{1}) =
     (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
      Mem.lc{2}, SplitC2.I2.RO.m{2}) /\
     (t1{1}, t2{1}).`1 = (t1{2}, t2{2}).`1 /\
     (t1{1}, t2{1}).`2 = (t1{2}, t2{2}).`2) /\
    t1{1} <> t2{1}) /\
   ((t1{1}, C.ofintd 0) \in SplitC2.I2.RO.m{1})) /\
  ((t2{1}, C.ofintd 0) \in SplitC2.I2.RO.m{1})

n <- t1                       (1--)  n <- t2                                             
r <@ RO.get(n, C.ofintd 0)    (2--)  r <@ RO.get(n, C.ofintd 0)                          
UF.forged <-                  (3--)  UF.forged <-                                        
  UF.forged ||                (  -)    UF.forged ||                                      
  test_poly_in n Mem.lc r     (  -)    test_poly_in n Mem.lc r                           
    (oget UFCMA.log.[n])      (  -)      (oget UFCMA.log.[n])                            
n0 <- t2                      (4--)  n0 <- t1                                            
r0 <@ RO.get(n0, C.ofintd 0)  (5--)  if ((n0, C.ofintd 0) \in ROout.m) {                 
                              (5.1)    r0 <@ RO.get(n0, C.ofintd 0)                      
                              (5.2)    UF.forged <-                                      
                              (   )      UF.forged ||                                    
                              (   )      test_poly_in n0 Mem.lc r0                       
                              (   )        (oget UFCMA.log.[n0])                         
                              (5--)  } else {                                            
                              (5?1)    r0 <@ RO.get(n0, C.ofintd 0)                      
                              (5?2)    t0 <@                                             
                              (   )      UFCMA(RO).set_bad2(map                          
                              (   )                           (fun (c : ciphertext) =>   
                              (   )                              c.`4 -                  
                              (   )                              poly1305_eval           
                              (   )                                r0                    
                              (   )                                (topol c.`2           
                              (   )                                  c.`3))              
                              (   )                           (filter                    
                              (   )                              (fun (c : ciphertext) =>
                              (   )                                 c.`1 = n0)           
                              (   )                              Mem.lc))                
                              (5?3)    ROout.set((n0, C.ofintd 0),                       
                              (   )      witness<:poly_out>)                             
                              (5--)  }                                                   
UF.forged <-                  (6--)                                                      
  UF.forged ||                (  -)                                                      
  test_poly_in n0 Mem.lc r0   (  -)                                                      
    (oget UFCMA.log.[n0])     (  -)                                                      

post =
  (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
   Mem.lc{1}, SplitC2.I2.RO.m{1}) =
  (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
   Mem.lc{2}, SplitC2.I2.RO.m{2})
[389|check]>
```

**Last action:** `rcondt{1} 5; first by move=> &m; inline *; auto => /#.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
