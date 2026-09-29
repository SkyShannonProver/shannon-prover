## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** rcondf{2} 4; first by auto => />. — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** framework reads the head as left=`assignment` right=`assignment` (both_sides_at_assignment) — find its row below.

**Head to tactic:**
- head `if` (same guard both sides) -> `if`.
- head `if` (divergent guard) -> `case: (<cond>)` then `rcondt{i} N` / `rcondf{i} N`.
- head `while` -> `while (<inv>)`; force the guard with `rcondt`/`rcondf`; never `while(true)` without a variant.
- head assignment `x <- e` -> `sp` / `wp`.
- head sample `x <$ d` -> `rnd`.
- head `call` -> `call (<invariant>)`, or `inline*`/`proc` to step into the body first.
- `invalid first instruction` / `right instruction list is not empty` = a side STILL HAS CODE: you cannot `skip`/`auto`/`sim`/`conseq`-close yet -> reduce the head with the matching tactic above (or `sp`/`wp` to consume statements first).

**Evidence:**
- membership source shapes: filter_membership, map_membership, map_update_membership
- map update keys: x0, x1, x3
- membership fact: ((t2{1}, C.ofintd 0) \in RO.m{1}) n <- t1 ( 1--) n <- t2

**Available local work:**
- pure tail obligation families: `sampling_bijection`, `map_update_projection`, `constructor_projection`, `map_membership_preservation`, `quantified_residual_logic`
- membership decomposition sources: `map_membership`, `filter_membership`, `map_update_membership`
- map update lookup cases: `x0`, `x1`, `x3`, `x4`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Rewind targets:**
- `After seq opened / before branch work #19` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_19_f70c9599e5333f86"}}`
- `Before seq cut #18` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_18_f70c9599e5333f86"}}`
- `After seq opened / before branch work #19` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_19_f70c9599e5333f86"}}`
- `Before seq cut #18` — seq-cut boundary; selecting it restores the proof state before this cut was committed → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_18_f70c9599e5333f86"}}`

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (rewind_targets above name the exact points).

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
t4 <$ dpoly_out                          ( 4--)  r <- oget RO.m.[x0]                    
r2 <$ dpoly_in                           ( 5--)  lt <-                                  
                                         (   -)    map                                  
                                         (   -)      (fun (c : ciphertext) =>           
                                         (   -)         c.`4 -                          
                                         (   -)         poly1305_eval r                 
                                         (   -)           (topol c.`2 c.`3))            
                                         (   -)      (filter                            
                                         (   -)         (fun (c : ciphertext) =>        
                                         (   -)            c.`1 = n) Mem.lc)            
RO.m <- RO.m.[x0 <- r2]                  ( 6--)  t3 <$ dpoly_out                        
r <- oget RO.m.[x0]                      ( 7--)  UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)
lt <-                                    ( 8--)  UFCMA.cbad2 <- UFCMA.cbad2 + 1         
  map                                    (   -)                                         
    (fun (c : ciphertext) =>             (   -)                                         
       c.`4 -                            (   -)                                         
       poly1305_eval r                   (   -)                                         
         (topol c.`2 c.`3))              (   -)                                         
    (filter                              (   -)                                         
       (fun (c : ciphertext) =>          (   -)                                         
          c.`1 = n) Mem.lc)              (   -)                                         
t3 <$ dpoly_out                          ( 9--)  t <- t3                                
UFCMA.bad2 <- UFCMA.bad2 || (t3 \in lt)  (10--)  x1 <- (n, C.ofintd 0)                  
UFCMA.cbad2 <- UFCMA.cbad2 + 1           (11--)  y <- witness<:poly_out>                
t <- t3                                  (12--)  SplitC2.I2.RO.m <-                     
                                         (   -)    SplitC2.I2.RO.m.[x1 <- y]            
x1 <- (n, C.ofintd 0)                    (13--)  n0 <- t1                               
y <- witness<:poly_out>                  (14--)  x3 <- (n0, C.ofintd 0)                 
SplitC2.I2.RO.m <-                       (15--)  r4 <$ dpoly_in                         
  SplitC2.I2.RO.m.[x1 <- y]              (   -)                                         
n0 <- t2                                 (16--)  if (x3 \notin RO.m) {                  
                                         (16.1)    RO.m <- RO.m.[x3 <- r4]              
                                         (16--)  }                                      
x3 <- (n0, C.ofintd 0)                   (17--)  r0 <- oget RO.m.[x3]                   
r0 <- oget RO.m.[x3]                     (18--)  lt0 <-                                 
                                         (   -)    map                                  
                                         (   -)      (fun (c : ciphertext) =>           
                                         (   -)         c.`4 -                          
                                         (   -)         poly1305_eval r0                
                                         (   -)           (topol c.`2 c.`3))            
                                         (   -)      (filter                            
                                         (   -)         (fun (c : ciphertext) =>        
                                         (   -)            c.`1 = n0) Mem.lc)           
lt0 <-                                   (19--)  t4 <$ dpoly_out                        
  map                                    (   -)                                         
    (fun (c : ciphertext) =>             (   -)                                         
       c.`4 -                            (   -)                                         
       poly1305_eval r0                  (   -)                                         
         (topol c.`2 c.`3))              (   -)                                         
    (filter                              (   -)                                         
       (fun (c : ciphertext) =>          (   -)                                         
          c.`1 = n0) Mem.lc)             (   -)                                         
UFCMA.bad2 <-                            (20--)  UFCMA.bad2 <-                          
  UFCMA.bad2 || (t4 \in lt0)             (   -)    UFCMA.bad2 || (t4 \in lt0)           
UFCMA.cbad2 <- UFCMA.cbad2 + 1           (21--)  UFCMA.cbad2 <- UFCMA.cbad2 + 1         
t0 <- t4                                 (22--)  t0 <- t4                               
x4 <- (n0, C.ofintd 0)                   (23--)  x4 <- (n0, C.ofintd 0)                 
y0 <- witness<:poly_out>                 (24--)  y0 <- witness<:poly_out>               
SplitC2.I2.RO.m <-                       (25--)  SplitC2.I2.RO.m <-                     
  SplitC2.I2.RO.m.[x4 <- y0]             (   -)    SplitC2.I2.RO.m.[x4 <- y0]           

post =
  (UF.forged{1}, UFCMA.bad2{1}, UFCMA.cbad2{1}, UFCMA.log{1}, RO.m{1},
   Mem.lc{1}, SplitC2.I2.RO.m{1}) =
  (UF.forged{2}, UFCMA.bad2{2}, UFCMA.cbad2{2}, UFCMA.log{2}, RO.m{2},
   Mem.lc{2}, SplitC2.I2.RO.m{2})
[530|check]>
```

## Status
remaining **5** · phase `seq_cut` / `procedure_body`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The current cut or frontier context may expose a call route.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- The visible cut may depend on LHS/RHS statement alignment or missing live facts.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`
- Need the valid form for call, seq, while, rnd, or rewrite.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The visible cut/frontier may need indexed `sp i j` before branch tactics.
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

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `rcondf{2} 4; first by auto => />.` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] the targetted instruction is not a conditionnal`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `rcondf{2} 4; first by auto => />.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
