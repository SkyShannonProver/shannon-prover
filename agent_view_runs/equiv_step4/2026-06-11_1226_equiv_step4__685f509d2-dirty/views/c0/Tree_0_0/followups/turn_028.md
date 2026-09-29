## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–2) — absorb with `sp`/`wp`: 2 setup statement(s): n <- t1; x0 <- (n, C.ofintd 0)
- frontier: both sides at `r2 <$ dpoly_in`
- frontier: left side only at `r4 <$ dpoly_in`
- frontier: left side only at `t4 <$ dpoly_out`
- frontier: right side only at `t3 <$ dpoly_out`
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
Current goal (remaining: 5)

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
  ((t2{1}, C.ofintd 0) \in RO.m{1})

n <- t1                                  ( 1--)  n <- t2                                
x0 <- (n, C.ofintd 0)                    ( 2--)  x0 <- (n, C.ofintd 0)                  
r4 <$ dpoly_in                           ( 3--)  r2 <$ dpoly_in                         
t4 <$ dpoly_out                          ( 4--)  if (x0 \notin RO.m) {                  
                                         ( 4.1)    RO.m <- RO.m.[x0 <- r2]              
                                         ( 4--)  }                                      
r2 <$ dpoly_in                           ( 5--)  r <- oget RO.m.[x0]                    
if (x0 \notin RO.m) {                    ( 6--)  lt <-                                  
                                         (   -)    map                                  
                                         (   -)      (fun (c : ciphertext) =>           
                                         (   -)         c.`4 -                          
                                         (   -)         poly1305_eval r                 
                                         (   -)           (topol c.`2 c.`3))            
                                         (   -)      (filter                            
                                         (   -)         (fun (c : ciphertext) =>        
                                         (   -)            c.`1 = n) Mem.lc)            
  RO.m <- RO.m.[x0 <- r2]                ( 6.1)                                         
}                                        ( 6--)                                         
r <- oget RO.m.[x0]                      ( 7--)  t3 <$ dpoly_out                        
lt <-                                    ( 8--)  UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)
  map                                    (   -)                                         
    (fun (c : ciphertext) =>             (   -)                                         
       c.`4 -                            (   -)                                         
       poly1305_eval r                   (   -)                                         
         (topol c.`2 c.`3))              (   -)                                         
    (filter                              (   -)                                         
       (fun (c : ciphertext) =>          (   -)                                         
          c.`1 = n) Mem.lc)              (   -)                                         
t3 <$ dpoly_out                          ( 9--)  UFCMA.cbad2 <- UFCMA.cbad2 + 1         
UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)  (10--)  t <- t3                                
UFCMA.cbad2 <- UFCMA.cbad2 + 1           (11--)  x1 <- (n, C.ofintd 0)                  
t <- t3                                  (12--)  y <- witness<:poly_out>                
x1 <- (n, C.ofintd 0)                    (13--)  SplitC2.I2.RO.m <-                     
                                         (   -)    SplitC2.I2.RO.m.[x1 <- y]            
y <- witness<:poly_out>                  (14--)  n0 <- t1                               
SplitC2.I2.RO.m <-                       (15--)  x3 <- (n0, C.ofintd 0)                 
  SplitC2.I2.RO.m.[x1 <- y]              (   -)                                         
n0 <- t2                                 (16--)  r4 <$ dpoly_in                         
x3 <- (n0, C.ofintd 0)                   (17--)  if (x3 \notin RO.m) {                  
                                         (17.1)    RO.m <- RO.m.[x3 <- r4]              
                                         (17--)  }                                      
if (x3 \notin RO.m) {                    (18--)  r0 <- oget RO.m.[x3]                   
  RO.m <- RO.m.[x3 <- r4]                (18.1)                                         
}                                        (18--)                                         
r0 <- oget RO.m.[x3]                     (19--)  lt0 <-                                 
                                         (   -)    map                                  
                                         (   -)      (fun (c : ciphertext) =>           
                                         (   -)         c.`4 -                          
                                         (   -)         poly1305_eval r0                
                                         (   -)           (topol c.`2 c.`3))            
                                         (   -)      (filter                            
                                         (   -)         (fun (c : ciphertext) =>        
                                         (   -)            c.`1 = n0) Mem.lc)           
lt0 <-                                   (20--)  t4 <$ dpoly_out                        
  map                                    (   -)                                         
    (fun (c : ciphertext) =>             (   -)                                         
       c.`4 -                            (   -)                                         
       poly1305_eval r0                  (   -)                                         
         (topol c.`2 c.`3))              (   -)                                         
    (filter                              (   -)                                         
       (fun (c : ciphertext) =>          (   -)                                         
          c.`1 = n0) Mem.lc)             (   -)                                         
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
[527|check]>
```

## Status
remaining **5** · phase `relational_program` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `case (((t2, C.ofintd 0) \in RO.m){1}).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
