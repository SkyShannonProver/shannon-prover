## 🎯 Current Goal
```
Current goal (remaining: 4)

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
eqSet: equiv[ ROout.set  ~ ROout.set :
               arg{1} = arg{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} ==>
               SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}]
------------------------------------------------------------------------
&1 (left ) : {b, forged : bool, i : int, n : nonce, ns : nonce list,
             r : poly_in, t : poly_out}
&2 (right) : {b : bool, n : nonce, ns, ns1, ns2, l : nonce list, r : poly_in,
             t : poly_out}

pre =
  forged{1} = UF.forged{2} /\
  (UFCMA.bad2{1} = UFCMA.bad2{2} /\
   UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   RO.m{1} = RO.m{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2}) /\
  ns{1} = ns{2}

i <- 0                                                  (1----)  l <- ns                                               
while (i < size ns) {                                   (2----)  while (l <> []) {                                     
  n <- nth witness<:nonce> ns i                         (2.1--)    n <- head witness<:nonce> l                         
  if ((n, C.ofintd 0) \in ROout.m) {                    (2.2--)    if ((n, C.ofintd 0) \in ROout.m) {                  
    r <@ RO.get(n, C.ofintd 0)                          (2.2.1)      r <@ RO.get(n, C.ofintd 0)                        
    forged <-                                           (2.2.2)      UF.forged <-                                      
      forged ||                                         (     )        UF.forged ||                                    
      test_poly_in n Mem.lc r                           (     )        test_poly_in n Mem.lc r                         
        (oget UFCMA.log.[n])                            (     )          (oget UFCMA.log.[n])                          
  } else {                                              (2.2--)    } else {                                            
    r <@ RO.get(n, C.ofintd 0)                          (2.2?1)      r <@ RO.get(n, C.ofintd 0)                        
    t <@                                                (2.2?2)      t <@                                              
      UFCMA(RO).set_bad2(map                            (     )        UFCMA(RO).set_bad2(map                          
                           (fun (c : ciphertext) =>     (     )                             (fun (c : ciphertext) =>   
                              c.`4 -                    (     )                                c.`4 -                  
                              poly1305_eval             (     )                                poly1305_eval           
                                r                       (     )                                  r                     
                                (topol c.`2             (     )                                  (topol c.`2           
                                  c.`3))                (     )                                    c.`3))              
                           (filter                      (     )                             (filter                    
                              (fun (c : ciphertext) =>  (     )                                (fun (c : ciphertext) =>
                                 c.`1 = n)              (     )                                   c.`1 = n)            
                              Mem.lc))                  (     )                                Mem.lc))                
    ROout.set((n, C.ofintd 0),                          (2.2?3)      ROout.set((n, C.ofintd 0),                        
      witness<:poly_out>)                               (     )        witness<:poly_out>)                             
  }                                                     (2.2--)    }                                                   
  i <- i + 1                                            (2.3--)    l <- drop 1 l                                       
}                                                       (2----)  }                                                     

post = UFCMA.bad2{1} = UFCMA.bad2{2} /\ forged{1} = UF.forged{2}
[510|check]>
```

**Last action:** `inline{2} Iter(Orcl).iter; inline{2} Orcl.f.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0811_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
