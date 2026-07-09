## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–2) — absorb with `sp`/`wp`: 2 setup statement(s): n <- t1; x0 <- (n, C.ofintd 0)
- frontier: both sides at `r2 <$ dpoly_in`
- frontier: both sides at `t3 <$ dpoly_out`
- frontier: both sides at `if (x0 \notin RO.m) {`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

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
  ((t2{1}, C.ofintd 0) \notin ROout.m{1})

n <- t1                                  ( 1-----)  n <- t2                                
x0 <- (n, C.ofintd 0)                    ( 2-----)  x0 <- (n, C.ofintd 0)                  
r2 <$ dpoly_in                           ( 3-----)  r2 <$ dpoly_in                         
if (x0 \notin RO.m) {                    ( 4-----)  if (x0 \notin RO.m) {                  
  RO.m <- RO.m.[x0 <- r2]                ( 4. 1--)    RO.m <- RO.m.[x0 <- r2]              
}                                        ( 4-----)  }                                      
r <- oget RO.m.[x0]                      ( 5-----)  r <- oget RO.m.[x0]                    
lt <-                                    ( 6-----)  lt <-                                  
  map                                    (   ----)    map                                  
    (fun (c : ciphertext) =>             (   ----)      (fun (c : ciphertext) =>           
       c.`4 -                            (   ----)         c.`4 -                          
       poly1305_eval r                   (   ----)         poly1305_eval r                 
         (topol c.`2 c.`3))              (   ----)           (topol c.`2 c.`3))            
    (filter                              (   ----)      (filter                            
       (fun (c : ciphertext) =>          (   ----)         (fun (c : ciphertext) =>        
          c.`1 = n) Mem.lc)              (   ----)            c.`1 = n) Mem.lc)            
t3 <$ dpoly_out                          ( 7-----)  t3 <$ dpoly_out                        
UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)  ( 8-----)  UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)
UFCMA.cbad2 <- UFCMA.cbad2 + 1           ( 9-----)  UFCMA.cbad2 <- UFCMA.cbad2 + 1         
t <- t3                                  (10-----)  t <- t3                                
x1 <- (n, C.ofintd 0)                    (11-----)  x1 <- (n, C.ofintd 0)                  
y <- witness<:poly_out>                  (12-----)  y <- witness<:poly_out>                
SplitC2.I2.RO.m <-                       (13-----)  SplitC2.I2.RO.m <-                     
  SplitC2.I2.RO.m.[x1 <- y]              (   ----)    SplitC2.I2.RO.m.[x1 <- y]            
n0 <- t2                                 (14-----)  n0 <- t1                               
x3 <- (n0, C.ofintd 0)                   (15-----)  if ((n0, C.ofintd 0) \in ROout.m) {    
                                         (15. 1--)    x2 <- (n0, C.ofintd 0)               
                                         (15. 2--)    r3 <$ dpoly_in                       
                                         (15. 3--)    if (x2 \notin RO.m) {                
                                         (15. 3.1)      RO.m <- RO.m.[x2 <- r3]            
                                         (15. 3--)    }                                    
                                         (15. 4--)    r0 <- oget RO.m.[x2]                 
                                         (15. 5--)    UF.forged <-                         
                                         (      -)      UF.forged ||                       
                                         (      -)      test_poly_in n0 Mem.lc r0          
                                         (      -)        (oget UFCMA.log.[n0])            
                                         (15-----)  } else {                               
                                         (15? 1--)    x3 <- (n0, C.ofintd 0)               
                                         (15? 2--)    r4 <$ dpoly_in                       
                                         (15? 3--)    if (x3 \notin RO.m) {                
                                         (15? 3.1)      RO.m <- RO.m.[x3 <- r4]            
                                         (15? 3--)    }                                    
                                         (15? 4--)    r0 <- oget RO.m.[x3]                 
                                         (15? 5--)    lt0 <-                               
                                         (      -)      map                                
                                         (      -)        (fun (c : ciphertext) =>         
                                         (      -)           c.`4 -                        
                                         (      -)           poly1305_eval r0              
                                         (      -)             (topol c.`2 c.`3))          
                                         (      -)        (filter                          
                                         (      -)           (fun (c : ciphertext) =>      
                                         (      -)              c.`1 = n0) Mem.lc)         
                                         (15? 6--)    t4 <$ dpoly_out                      
                                         (15? 7--)    UFCMA.bad2 <-                        
                                         (      -)      UFCMA.bad2 || (t4 \in lt0)         
                                         (15? 8--)    UFCMA.cbad2 <- UFCMA.cbad2 + 1       
                                         (15? 9--)    t0 <- t4                             
                                         (15?10--)    x4 <- (n0, C.ofintd 0)               
                                         (15?11--)    y0 <- witness<:poly_out>             
                                         (15?12--)    SplitC2.I2.RO.m <-                   
                                         (      -)      SplitC2.I2.RO.m.[x4 <- y0]         
                                         (15-----)  }                                      
r4 <$ dpoly_in                           (16-----)                                         
if (x3 \notin RO.m) {                    (17-----)                                         
  RO.m <- RO.m.[x3 <- r4]                (17. 1--)                                         
}                                        (17-----)                                         
r0 <- oget RO.m.[x3]                     (18-----)                                         
lt0 <-                                   (19-----)                                         
  map                                    (   ----)                                         
    (fun (c : ciphertext) =>             (   ----)                                         
       c.`4 -                            (   ----)                                         
       poly1305_eval r0                  (   ----)                                         
         (topol c.`2 c.`3))              (   ----)                                         
    (filter                              (   ----)                                         
       (fun (c : ciphertext) =>          (   ----)                                         
          c.`1 = n0) Mem.lc)             (   ----)                                         
t4 <$ dpoly_out                          (20-----)                                         
UFCMA.bad2 <-                            (21-----)                                         
  UFCMA.bad2 || (t4 \in lt0)             (   ----)                                         
UFCMA.cbad2 <- UFCMA.cbad2 + 1           (22-----)                                         
t0 <- t4                                 (23-----)                                         
x4 <- (n0, C.ofintd 0)                   (24-----)                                         
y0 <- witness<:poly_out>                 (25-----)                                         
SplitC2.I2.RO.m <-                       (26-----)                                         
  SplitC2.I2.RO.m.[x4 <- y0]             (   ----)                                         

post =
  (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
   Mem.lc{1}, SplitC2.I2.RO.m{1}) =
  (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
   Mem.lc{2}, SplitC2.I2.RO.m{2})
[509|check]>
```

## Status
remaining **4** · phase `relational_program` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `rcondf{1} 15; first by auto => />; smt(mem_set).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
