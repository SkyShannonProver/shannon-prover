## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–2) — absorb with `sp`/`wp`: 2 setup statement(s): n <- t1; x0 <- (n, C.ofintd 0)
- frontier: left side only at `r3 <$ dpoly_in`
- frontier: right side only at `r1 <$ dpoly_in`
- frontier: left side only at `r2 <$ dpoly_in`
- frontier: left side only at `t3 <$ dpoly_out`

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
    ((t2{1}, C.ofintd 0) \in ROout.m{1})) /\
   ((t1{1}, C.ofintd 0) \notin RO.m{1})) /\
  ((t2{1}, C.ofintd 0) \notin RO.m{1})

n <- t1                                  ( 1)  n <- t2                        
x0 <- (n, C.ofintd 0)                    ( 2)  x <- (n, C.ofintd 0)           
r3 <$ dpoly_in                           ( 3)  r1 <$ dpoly_in                 
r2 <$ dpoly_in                           ( 4)  RO.m <- RO.m.[x <- r1]         
RO.m <- RO.m.[x0 <- r2]                  ( 5)  r <- oget RO.m.[x]             
r <- oget RO.m.[x0]                      ( 6)  UF.forged <-                   
                                         (  )    UF.forged ||                 
                                         (  )    test_poly_in n Mem.lc r      
                                         (  )      (oget UFCMA.log.[n])       
lt <-                                    ( 7)  n0 <- t1                       
  map                                    (  )                                 
    (fun (c : ciphertext) =>             (  )                                 
       c.`4 -                            (  )                                 
       poly1305_eval r                   (  )                                 
         (topol c.`2 c.`3))              (  )                                 
    (filter                              (  )                                 
       (fun (c : ciphertext) =>          (  )                                 
          c.`1 = n) Mem.lc)              (  )                                 
t3 <$ dpoly_out                          ( 8)  x3 <- (n0, C.ofintd 0)         
UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)  ( 9)  r4 <$ dpoly_in                 
UFCMA.cbad2 <- UFCMA.cbad2 + 1           (10)  RO.m <- RO.m.[x3 <- r4]        
t <- t3                                  (11)  r0 <- oget RO.m.[x3]           
x1 <- (n, C.ofintd 0)                    (12)  lt0 <-                         
                                         (  )    map                          
                                         (  )      (fun (c : ciphertext) =>   
                                         (  )         c.`4 -                  
                                         (  )         poly1305_eval r0        
                                         (  )           (topol c.`2 c.`3))    
                                         (  )      (filter                    
                                         (  )         (fun (c : ciphertext) =>
                                         (  )            c.`1 = n0) Mem.lc)   
y <- witness<:poly_out>                  (13)  t4 <$ dpoly_out                
SplitC2.I2.RO.m <-                       (14)  UFCMA.bad2 <-                  
  SplitC2.I2.RO.m.[x1 <- y]              (  )    UFCMA.bad2 || (t4 \in lt0)   
n0 <- t2                                 (15)  UFCMA.cbad2 <- UFCMA.cbad2 + 1 
x2 <- (n0, C.ofintd 0)                   (16)  t0 <- t4                       
RO.m <- RO.m.[x2 <- r3]                  (17)  x4 <- (n0, C.ofintd 0)         
r0 <- oget RO.m.[x2]                     (18)  y0 <- witness<:poly_out>       
UF.forged <-                             (19)  SplitC2.I2.RO.m <-             
  UF.forged ||                           (  )    SplitC2.I2.RO.m.[x4 <- y0]   
  test_poly_in n0 Mem.lc r0              (  )                                 
    (oget UFCMA.log.[n0])                (  )                                 

post =
  (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
   Mem.lc{1}, SplitC2.I2.RO.m{1}) =
  (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
   Mem.lc{2}, SplitC2.I2.RO.m{2})
[504|check]>
```

## Status
remaining **5** · phase `relational_program` / `procedure_body`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `rcondt{2} 10; first by auto => />; smt(mem_set).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
