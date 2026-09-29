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
------------------------------------------------------------------------
&1 (left ) : {t1, t2, n, n0 : nonce,
             x, x0, x1, x2, x3, x4 : nonce * C.counter,
             r, r0, r1, r2, r3, r4 : poly_in,
             t, t0, t3, y, t4, y0 : poly_out, lt, lt0 : tag list}
&2 (right) : {t1, t2, n, n0 : nonce,
             x, x0, x1, x2, x3, x4 : nonce * C.counter,
             r, r0, r1, r2, r3, r4 : poly_in,
             t, t0, t3, y, t4, y0 : poly_out, lt, lt0 : tag list}

pre =
  ((((((UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
        Mem.lc{1}, SplitC2.I2.RO.m{1}) =
       (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
        Mem.lc{2}, SplitC2.I2.RO.m{2}) /\
       (t1{1}, t2{1}).`1 = (t1{2}, t2{2}).`1 /\
       (t1{1}, t2{1}).`2 = (t1{2}, t2{2}).`2) /\
      t1{1} <> t2{1}) /\
     ((t1{1}, C.ofintd 0) \notin ROout.m{1})) /\
    ((t2{1}, C.ofintd 0) \notin ROout.m{1})) /\
   ((t1{1}, C.ofintd 0) \notin RO.m{1})) /\
  ((t2{1}, C.ofintd 0) \notin RO.m{1})

n <- t1                                  ( 1--)  n <- t2                                
x0 <- (n, C.ofintd 0)                    ( 2--)  x0 <- (n, C.ofintd 0)                  
r2 <$ dpoly_in                           ( 3--)  r4 <$ dpoly_in                         
RO.m <- RO.m.[x0 <- r2]                  ( 4--)  t4 <$ dpoly_out                        
r <- oget RO.m.[x0]                      ( 5--)  r2 <$ dpoly_in                         
lt <-                                    ( 6--)  if (x0 \notin RO.m) {                  
  map                                    (   -)                                         
    (fun (c : ciphertext) =>             (   -)                                         
       c.`4 -                            (   -)                                         
       poly1305_eval r                   (   -)                                         
         (topol c.`2 c.`3))              (   -)                                         
    (filter                              (   -)                                         
       (fun (c : ciphertext) =>          (   -)                                         
          c.`1 = n) Mem.lc)              (   -)                                         
                                         ( 6.1)    RO.m <- RO.m.[x0 <- r2]              
                                         ( 6--)  }                                      
t3 <$ dpoly_out                          ( 7--)  r <- oget RO.m.[x0]                    
UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)  ( 8--)  lt <-                                  
                                         (   -)    map                                  
                                         (   -)      (fun (c : ciphertext) =>           
                                         (   -)         c.`4 -                          
                                         (   -)         poly1305_eval r                 
                                         (   -)           (topol c.`2 c.`3))            
                                         (   -)      (filter                            
                                         (   -)         (fun (c : ciphertext) =>        
                                         (   -)            c.`1 = n) Mem.lc)            
UFCMA.cbad2 <- UFCMA.cbad2 + 1           ( 9--)  t3 <$ dpoly_out                        
t <- t3                                  (10--)  UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)
x1 <- (n, C.ofintd 0)                    (11--)  UFCMA.cbad2 <- UFCMA.cbad2 + 1         
y <- witness<:poly_out>                  (12--)  t <- t3                                
SplitC2.I2.RO.m <-                       (13--)  x1 <- (n, C.ofintd 0)                  
  SplitC2.I2.RO.m.[x1 <- y]              (   -)                                         
n0 <- t2                                 (14--)  y <- witness<:poly_out>                
x3 <- (n0, C.ofintd 0)                   (15--)  SplitC2.I2.RO.m <-                     
                                         (   -)    SplitC2.I2.RO.m.[x1 <- y]            
r4 <$ dpoly_in                           (16--)  n0 <- t1                               
if (x3 \notin RO.m) {                    (17--)  x3 <- (n0, C.ofintd 0)                 
  RO.m <- RO.m.[x3 <- r4]                (17.1)                                         
}                                        (17--)                                         
r0 <- oget RO.m.[x3]                     (18--)  RO.m <- RO.m.[x3 <- r4]                
lt0 <-                                   (19--)  r0 <- oget RO.m.[x3]                   
  map                                    (   -)                                         
    (fun (c : ciphertext) =>             (   -)                                         
       c.`4 -                            (   -)                                         
       poly1305_eval r0                  (   -)                                         
         (topol c.`2 c.`3))              (   -)                                         
    (filter                              (   -)                                         
       (fun (c : ciphertext) =>          (   -)                                         
          c.`1 = n0) Mem.lc)             (   -)                                         
t4 <$ dpoly_out                          (20--)  lt0 <-                                 
                                         (   -)    map                                  
                                         (   -)      (fun (c : ciphertext) =>           
                                         (   -)         c.`4 -                          
                                         (   -)         poly1305_eval r0                
                                         (   -)           (topol c.`2 c.`3))            
                                         (   -)      (filter                            
                                         (   -)         (fun (c : ciphertext) =>        
                                         (   -)            c.`1 = n0) Mem.lc)           
UFCMA.bad2 <-                            (21--)  UFCMA.bad2 <-                          
  UFCMA.bad2 || (t4 \in lt0)             (   -)    UFCMA.bad2 || (t4 \in lt0)           
UFCMA.cbad2 <- UFCMA.cbad2 + 1           (22--)  UFCMA.cbad2 <- UFCMA.cbad2 + 1         
t0 <- t4                                 (23--)  t0 <- t4                               
x4 <- (n0, C.ofintd 0)                   (24--)  x4 <- (n0, C.ofintd 0)                 
y0 <- witness<:poly_out>                 (25--)  y0 <- witness<:poly_out>               
SplitC2.I2.RO.m <-                       (26--)  SplitC2.I2.RO.m <-                     
  SplitC2.I2.RO.m.[x4 <- y0]             (   -)    SplitC2.I2.RO.m.[x4 <- y0]           

post =
  (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
   Mem.lc{1}, SplitC2.I2.RO.m{1}) =
  (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
   Mem.lc{2}, SplitC2.I2.RO.m{2})
[488|check]>
```

**Last action:** `move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; rewrite !get_set_sameE…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0654_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
