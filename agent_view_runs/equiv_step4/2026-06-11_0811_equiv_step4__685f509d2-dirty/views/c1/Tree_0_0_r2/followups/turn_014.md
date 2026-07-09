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
  ((((UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
      Mem.lc{1}, SplitC2.I2.RO.m{1}) =
     (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
      Mem.lc{2}, SplitC2.I2.RO.m{2}) /\
     (t1{1}, t2{1}).`1 = (t1{2}, t2{2}).`1 /\
     (t1{1}, t2{1}).`2 = (t1{2}, t2{2}).`2) /\
    t1{1} <> t2{1}) /\
   ((t1{1}, C.ofintd 0) \notin ROout.m{1})) /\
  ((t2{1}, C.ofintd 0) \in ROout.m{1})

n <- t1                                  ( 1-----)  n <- t2                                  
x0 <- (n, C.ofintd 0)                    ( 2-----)  if ((n, C.ofintd 0) \in ROout.m) {       
                                         ( 2. 1--)    x <- (n, C.ofintd 0)                   
                                         ( 2. 2--)    r1 <$ dpoly_in                         
                                         ( 2. 3--)    if (x \notin RO.m) {                   
                                         ( 2. 3.1)      RO.m <- RO.m.[x <- r1]               
                                         ( 2. 3--)    }                                      
                                         ( 2. 4--)    r <- oget RO.m.[x]                     
                                         ( 2. 5--)    UF.forged <-                           
                                         (      -)      UF.forged ||                         
                                         (      -)      test_poly_in n Mem.lc r              
                                         (      -)        (oget UFCMA.log.[n])               
                                         ( 2-----)  } else {                                 
                                         ( 2? 1--)    x0 <- (n, C.ofintd 0)                  
                                         ( 2? 2--)    r2 <$ dpoly_in                         
                                         ( 2? 3--)    if (x0 \notin RO.m) {                  
                                         ( 2? 3.1)      RO.m <- RO.m.[x0 <- r2]              
                                         ( 2? 3--)    }                                      
                                         ( 2? 4--)    r <- oget RO.m.[x0]                    
                                         ( 2? 5--)    lt <-                                  
                                         (      -)      map                                  
                                         (      -)        (fun (c : ciphertext) =>           
                                         (      -)           c.`4 -                          
                                         (      -)           poly1305_eval r                 
                                         (      -)             (topol c.`2 c.`3))            
                                         (      -)        (filter                            
                                         (      -)           (fun (c : ciphertext) =>        
                                         (      -)              c.`1 = n) Mem.lc)            
                                         ( 2? 6--)    t3 <$ dpoly_out                        
                                         ( 2? 7--)    UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)
                                         ( 2? 8--)    UFCMA.cbad2 <- UFCMA.cbad2 + 1         
                                         ( 2? 9--)    t <- t3                                
                                         ( 2?10--)    x1 <- (n, C.ofintd 0)                  
                                         ( 2?11--)    y <- witness<:poly_out>                
                                         ( 2?12--)    SplitC2.I2.RO.m <-                     
                                         (      -)      SplitC2.I2.RO.m.[x1 <- y]            
                                         ( 2-----)  }                                        
r2 <$ dpoly_in                           ( 3-----)  n0 <- t1                                 
if (x0 \notin RO.m) {                    ( 4-----)  if ((n0, C.ofintd 0) \in ROout.m) {      
  RO.m <- RO.m.[x0 <- r2]                ( 4. 1--)    x2 <- (n0, C.ofintd 0)                 
                                         ( 4. 2--)    r3 <$ dpoly_in                         
                                         ( 4. 3--)    if (x2 \notin RO.m) {                  
                                         ( 4. 3.1)      RO.m <- RO.m.[x2 <- r3]              
                                         ( 4. 3--)    }                                      
                                         ( 4. 4--)    r0 <- oget RO.m.[x2]                   
                                         ( 4. 5--)    UF.forged <-                           
                                         (      -)      UF.forged ||                         
                                         (      -)      test_poly_in n0 Mem.lc r0            
                                         (      -)        (oget UFCMA.log.[n0])              
}                                        ( 4-----)  } else {                                 
                                         ( 4? 1--)    x3 <- (n0, C.ofintd 0)                 
                                         ( 4? 2--)    r4 <$ dpoly_in                         
                                         ( 4? 3--)    if (x3 \notin RO.m) {                  
                                         ( 4? 3.1)      RO.m <- RO.m.[x3 <- r4]              
                                         ( 4? 3--)    }                                      
                                         ( 4? 4--)    r0 <- oget RO.m.[x3]                   
                                         ( 4? 5--)    lt0 <-                                 
                                         (      -)      map                                  
                                         (      -)        (fun (c : ciphertext) =>           
                                         (      -)           c.`4 -                          
                                         (      -)           poly1305_eval r0                
                                         (      -)             (topol c.`2 c.`3))            
                                         (      -)        (filter                            
                                         (      -)           (fun (c : ciphertext) =>        
                                         (      -)              c.`1 = n0) Mem.lc)           
                                         ( 4? 6--)    t4 <$ dpoly_out                        
                                         ( 4? 7--)    UFCMA.bad2 <-                          
                                         (      -)      UFCMA.bad2 || (t4 \in lt0)           
                                         ( 4? 8--)    UFCMA.cbad2 <- UFCMA.cbad2 + 1         
                                         ( 4? 9--)    t0 <- t4                               
                                         ( 4?10--)    x4 <- (n0, C.ofintd 0)                 
                                         ( 4?11--)    y0 <- witness<:poly_out>               
                                         ( 4?12--)    SplitC2.I2.RO.m <-                     
                                         (      -)      SplitC2.I2.RO.m.[x4 <- y0]           
                                         ( 4-----)  }                                        
r <- oget RO.m.[x0]                      ( 5-----)                                           
lt <-                                    ( 6-----)                                           
  map                                    (   ----)                                           
    (fun (c : ciphertext) =>             (   ----)                                           
       c.`4 -                            (   ----)                                           
       poly1305_eval r                   (   ----)                                           
         (topol c.`2 c.`3))              (   ----)                                           
    (filter                              (   ----)                                           
       (fun (c : ciphertext) =>          (   ----)                                           
          c.`1 = n) Mem.lc)              (   ----)                                           
t3 <$ dpoly_out                          ( 7-----)                                           
UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)  ( 8-----)                                           
UFCMA.cbad2 <- UFCMA.cbad2 + 1           ( 9-----)                                           
t <- t3                                  (10-----)                                           
x1 <- (n, C.ofintd 0)                    (11-----)                                           
y <- witness<:poly_out>                  (12-----)                                           
SplitC2.I2.RO.m <-                       (13-----)                                           
  SplitC2.I2.RO.m.[x1 <- y]              (   ----)                                           
n0 <- t2                                 (14-----)                                           
if ((n0, C.ofintd 0) \in ROout.m) {      (15-----)                                           
  x2 <- (n0, C.ofintd 0)                 (15. 1--)                                           
  r3 <$ dpoly_in                         (15. 2--)                                           
  if (x2 \notin RO.m) {                  (15. 3--)                                           
    RO.m <- RO.m.[x2 <- r3]              (15. 3.1)                                           
  }                                      (15. 3--)                                           
  r0 <- oget RO.m.[x2]                   (15. 4--)                                           
  UF.forged <-                           (15. 5--)                                           
    UF.forged ||                         (      -)                                           
    test_poly_in n0 Mem.lc r0            (      -)                                           
      (oget UFCMA.log.[n0])              (      -)                                           
} else {                                 (15-----)                                           
  x3 <- (n0, C.ofintd 0)                 (15? 1--)                                           
  r4 <$ dpoly_in                         (15? 2--)                                           
  if (x3 \notin RO.m) {                  (15? 3--)                                           
    RO.m <- RO.m.[x3 <- r4]              (15? 3.1)                                           
  }                                      (15? 3--)                                           
  r0 <- oget RO.m.[x3]                   (15? 4--)                                           
  lt0 <-                                 (15? 5--)                                           
    map                                  (      -)                                           
      (fun (c : ciphertext) =>           (      -)                                           
         c.`4 -                          (      -)                                           
         poly1305_eval r0                (      -)                                           
           (topol c.`2 c.`3))            (      -)                                           
      (filter                            (      -)                                           
         (fun (c : ciphertext) =>        (      -)                                           
            c.`1 = n0) Mem.lc)           (      -)                                           
  t4 <$ dpoly_out                        (15? 6--)                                           
  UFCMA.bad2 <-                          (15? 7--)                                           
    UFCMA.bad2 || (t4 \in lt0)           (      -)                                           
  UFCMA.cbad2 <- UFCMA.cbad2 + 1         (15? 8--)                                           
  t0 <- t4                               (15? 9--)                                           
  x4 <- (n0, C.ofintd 0)                 (15?10--)                                           
  y0 <- witness<:poly_out>               (15?11--)                                           
  SplitC2.I2.RO.m <-                     (15?12--)                                           
    SplitC2.I2.RO.m.[x4 <- y0]           (      -)                                           
}                                        (15-----)                                           

post =
  (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
   Mem.lc{1}, SplitC2.I2.RO.m{1}) =
  (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
   Mem.lc{2}, SplitC2.I2.RO.m{2})
[435|check]>
```

**Last action:** `rcondf{1} 2; first by auto => /#.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-11_0054_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
