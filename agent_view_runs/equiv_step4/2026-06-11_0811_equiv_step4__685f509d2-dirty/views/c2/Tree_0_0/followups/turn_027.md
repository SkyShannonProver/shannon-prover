## 🎯 Current Goal
```
Current goal (remaining: 2)

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
&1 (left ) : {b, forged : bool, i : int, n : nonce, ns : nonce list,
             r : poly_in, t : poly_out}
&2 (right) : {b : bool, ns, ns1, ns2 : nonce list}

pre = (glob A){1} = (glob A){2}

UFCMA.bad1 <- false                                       (1------)  UFCMA.bad1 <- false                      
UFCMA.cbad1 <- 0                                          (2------)  UFCMA.cbad1 <- 0                         
UFCMA.bad2 <- false                                       (3------)  UFCMA.bad2 <- false                      
UFCMA.cbad2 <- 0                                          (4------)  UFCMA.cbad2 <- 0                         
b <@                                                      (5------)  b <@                                     
  CPA_game(CCA_CPA_Adv(BNR_Adv(A)),                       (  -----)    CPA_game(CCA_CPA_Adv(BNR_Adv(A)),      
    UFCMA(RO).O).main()                                   (  -----)      UFCMA2(RO).O).main()                 
forged <- false                                           (6------)  UF.forged <- false                       
if (size Mem.lc <= qdec) {                                (7------)  if (size Mem.lc <= qdec) {               
  ns <-                                                   (7.1----)    ns <-                                  
    undup                                                 (    ---)      undup                                
      (map (fun (p : ciphertext) => p.`1)                 (    ---)        (map (fun (p : ciphertext) => p.`1)
         Mem.lc)                                          (    ---)           Mem.lc)                         
  i <- 0                                                  (7.2----)    ns1 <-                                 
                                                          (    ---)      filter                               
                                                          (    ---)        (fun (n0 : nonce) =>               
                                                          (    ---)           (n0, C.ofintd 0) \in ROout.m) ns
  while (i < size ns) {                                   (7.3----)    ns2 <-                                 
                                                          (    ---)      filter                               
                                                          (    ---)        (fun (n0 : nonce) =>               
                                                          (    ---)           (n0, C.ofintd 0) \notin ROout.m)
                                                          (    ---)        ns                                 
    n <- nth witness<:nonce> ns i                         (7.3.1--)                                           
    if ((n, C.ofintd 0) \in ROout.m) {                    (7.3.2--)                                           
      r <@ RO.get(n, C.ofintd 0)                          (7.3.2.1)                                           
      forged <-                                           (7.3.2.2)                                           
        forged ||                                         (       )                                           
        test_poly_in n Mem.lc r                           (       )                                           
          (oget UFCMA.log.[n])                            (       )                                           
    } else {                                              (7.3.2--)                                           
      r <@ RO.get(n, C.ofintd 0)                          (7.3.2?1)                                           
      t <@                                                (7.3.2?2)                                           
        UFCMA(RO).set_bad2(map                            (       )                                           
                             (fun (c : ciphertext) =>     (       )                                           
                                c.`4 -                    (       )                                           
                                poly1305_eval             (       )                                           
                                  r                       (       )                                           
                                  (topol c.`2             (       )                                           
                                    c.`3))                (       )                                           
                             (filter                      (       )                                           
                                (fun (c : ciphertext) =>  (       )                                           
                                   c.`1 = n)              (       )                                           
                                Mem.lc))                  (       )                                           
      ROout.set((n, C.ofintd 0),                          (7.3.2?3)                                           
        witness<:poly_out>)                               (       )                                           
    }                                                     (7.3.2--)                                           
    i <- i + 1                                            (7.3.3--)                                           
  }                                                       (7.3----)                                           
                                                          (7.4----)    Iter(Orcl).iter(ns1 ++ ns2)            
}                                                         (7------)  }                                        

post = UFCMA.bad2{1} = UFCMA.bad2{2} /\ forged{1} = UF.forged{2}
[495|check]>
```

**Last action:** `proc.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
