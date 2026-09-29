## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

eqRO: equiv[ RO.get  ~ RO.get :
              arg{1} = arg{2} /\ RO.m{1} = RO.m{2} ==>
              res{1} = res{2} /\ RO.m{1} = RO.m{2}]
eqSB2: equiv[ UFCMA(RO).set_bad2  ~ UFCMA(RO).set_bad2 :
               arg{1} = arg{2} /\
               UFCMA.bad2{1} = UFCMA.bad2{2} /\
               UFCMA.cbad2{1} = UFCMA.cbad2{2} ==>
               res{1} = res{2} /\
               UFCMA.bad2{1} = UFCMA.bad2{2} /\
               UFCMA.cbad2{1} = UFCMA.cbad2{2}]
eqf: equiv[ Orcl.f  ~ Orcl.f :
             arg{1} = arg{2} /\
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2}) ==>
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2})]
Hsw: equiv[ Iter(Orcl).iter_12  ~ Iter(Orcl).iter_21 :
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2}) /\
             t1{1} = t1{2} /\ t2{1} = t2{2} ==>
             (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1},
              RO.m{1}, Mem.lc{1}, SplitC2.I2.RO.m{1}) =
             (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2},
              RO.m{2}, Mem.lc{2}, SplitC2.I2.RO.m{2})]
------------------------------------------------------------------------
&1 (left ) : {b : bool, ns, ns1, ns2, l1, l2, l, l0 : nonce list}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}

pre =
  (UF.forged{1} = UF.forged{2} /\
   UFCMA.bad2{1} = UFCMA.bad2{2} /\
   UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   ns{1} = ns{2} /\ ns1{1} = ns1{2} /\ ns2{1} = ns2{2}) /\
  uniq ns{2} /\
  ns1{2} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m{2}) ns{2} /\
  ns2{2} =
  filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m{2}) ns{2}

l1 <- ns1                         (1--)  i <- 0                          
l2 <- ns2                         (2--)  while (i < size ns1) {          
                                  (2.1)    n <- nth witness<:nonce> ns1 i
                                  (2.2)    r <@ RO.get(n, C.ofintd 0)    
                                  (2.3)    UF.forged <-                  
                                  (   )      UF.forged ||                
                                  (   )      test_poly_in n Mem.lc r     
                                  (   )        (oget UFCMA.log.[n])      
                                  (2.4)    i <- i + 1                    
                                  (2--)  }                               
l <- l1                           (3--)                                  
while (l <> []) {                 (4--)                                  
  Orcl.f(head witness<:nonce> l)  (4.1)                                  
  l <- drop 1 l                   (4.2)                                  
}                                 (4--)                                  

post =
  UF.forged{1} = UF.forged{2} /\
  UFCMA.bad2{1} = UFCMA.bad2{2} /\
  UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
  UFCMA.log{1} = UFCMA.log{2} /\
  Mem.lc{1} = Mem.lc{2} /\
  RO.m{1} = RO.m{2} /\
  SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
  l2{1} = ns2{2} /\
  uniq ns2{2} /\
  forall (n0 : nonce),
    n0 \in ns2{2} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{2}
[536|check]>
```

**Last action:** `seq 4 2 : (UF.forged{1} = UF.forged{2} /\ UFCMA.bad2{1} = UFCMA.bad2{2} /\ UFCM…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
