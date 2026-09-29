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
&1 (left ) : {b : bool, n : nonce, ns, ns1, ns2, l1, l2, l, l0 : nonce list,
             r : poly_in, t : poly_out}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}

pre =
  n{2} = nth witness<:nonce> ns2{2} i{2} /\
  n{1} = head witness<:nonce> l0{1} /\
  (UF.forged{1} = UF.forged{2} /\
   UFCMA.bad2{1} = UFCMA.bad2{2} /\
   UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   RO.m{1} = RO.m{2} /\
   l0{1} = drop i{2} ns2{2} /\
   0 <= i{2} /\
   uniq l0{1} /\
   forall (n0 : nonce),
     n0 \in l0{1} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{1}) /\
  l0{1} <> [] /\ i{2} < size ns2{2}

r <@ RO.get(n, C.ofintd 0)                          (1)  r <@ RO.get(n, C.ofintd 0)                        
t <@                                                (2)  t <@                                              
  UFCMA(RO).set_bad2(map                            ( )    UFCMA(RO).set_bad2(map                          
                       (fun (c : ciphertext) =>     ( )                         (fun (c : ciphertext) =>   
                          c.`4 -                    ( )                            c.`4 -                  
                          poly1305_eval             ( )                            poly1305_eval           
                            r                       ( )                              r                     
                            (topol c.`2             ( )                              (topol c.`2           
                              c.`3))                ( )                                c.`3))              
                       (filter                      ( )                         (filter                    
                          (fun (c : ciphertext) =>  ( )                            (fun (c : ciphertext) =>
                             c.`1 = n)              ( )                               c.`1 = n)            
                          Mem.lc))                  ( )                            Mem.lc))                
ROout.set((n, C.ofintd 0),                          (3)  i <- i + 1                                        
  witness<:poly_out>)                               ( )                                                    
l0 <- drop 1 l0                                     (4)                                                    

post =
  (UF.forged{1} = UF.forged{2} /\
   UFCMA.bad2{1} = UFCMA.bad2{2} /\
   UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   RO.m{1} = RO.m{2} /\
   l0{1} = drop i{2} ns2{2} /\
   0 <= i{2} /\
   uniq l0{1} /\
   forall (n0 : nonce),
     n0 \in l0{1} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{1}) /\
  (l0{1} <> [] <=> i{2} < size ns2{2})
[554|check]>
```

**Last action:** `inline {1} ROout.set; wp; call eqSB2; call eqRO; skip; smt(drop_nth drop_drop i…` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
