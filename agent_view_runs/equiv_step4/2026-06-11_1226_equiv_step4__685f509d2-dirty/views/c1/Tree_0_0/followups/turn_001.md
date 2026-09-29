## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** by auto => />; smt(drop_nth drop_drop size_drop size_eq0 mem_set head_behead). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

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
- map update keys: x, x0
- membership fact: forall (n0 : nonce), n0 \in l0{1} => (n0, C.ofintd 0) \notin ROout.m{1}) /\ l0{1} <> [] /\ i{2} < size ns2{2}

**Available local work:**
- pure tail obligation families: `sampling_bijection`, `map_update_projection`, `constructor_projection`, `map_membership_preservation`, `quantified_residual_logic`
- membership decomposition sources: `map_membership`, `filter_membership`, `map_update_membership`
- map update lookup cases: `x`, `x0`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Rewind targets:**
- `After seq opened / before branch work #171` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_171_4211548f8eb814c6"}}`
- `Before seq cut #170` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_170_4211548f8eb814c6"}}`
- `After seq opened / before branch work #171` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_171_4211548f8eb814c6"}}`
- `Before seq cut #170` — seq-cut boundary; selecting it restores the proof state before this cut was committed → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_170_4211548f8eb814c6"}}`

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (rewind_targets above name the exact points).

## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, n : nonce, ns, ns1, ns2, l1, l2, l, l0 : nonce list,
             x, x0 : nonce * C.counter, r, r0 : poly_in, t, t0, y : poly_out,
             lt : tag list}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             x : nonce * C.counter, r, r0 : poly_in, t, t0 : poly_out,
             lt : tag list}

pre =
  ((UF.forged{1} = UF.forged{2} /\
    UFCMA.bad2{1} = UFCMA.bad2{2} /\
    UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
    UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2}) /\
   l0{1} = drop i{2} ns2{2} /\
   0 <= i{2} /\
   uniq l0{1} /\
   forall (n0 : nonce), n0 \in l0{1} => (n0, C.ofintd 0) \notin ROout.m{1}) /\
  l0{1} <> [] /\ i{2} < size ns2{2}

n <- head witness<:nonce> l0             ( 1--)  n <- nth witness<:nonce> ns2 i         
x <- (n, C.ofintd 0)                     ( 2--)  x <- (n, C.ofintd 0)                   
r0 <$ dpoly_in                           ( 3--)  r0 <$ dpoly_in                         
if (x \notin RO.m) {                     ( 4--)  if (x \notin RO.m) {                   
  RO.m <- RO.m.[x <- r0]                 ( 4.1)    RO.m <- RO.m.[x <- r0]               
}                                        ( 4--)  }                                      
r <- oget RO.m.[x]                       ( 5--)  r <- oget RO.m.[x]                     
lt <-                                    ( 6--)  lt <-                                  
  map                                    (   -)    map                                  
    (fun (c : ciphertext) =>             (   -)      (fun (c : ciphertext) =>           
       c.`4 -                            (   -)         c.`4 -                          
       poly1305_eval r                   (   -)         poly1305_eval r                 
         (topol c.`2 c.`3))              (   -)           (topol c.`2 c.`3))            
    (filter                              (   -)      (filter                            
       (fun (c : ciphertext) =>          (   -)         (fun (c : ciphertext) =>        
          c.`1 = n) Mem.lc)              (   -)            c.`1 = n) Mem.lc)            
t0 <$ dpoly_out                          ( 7--)  t0 <$ dpoly_out                        
UFCMA.bad2 <- UFCMA.bad2 || (t0 \in lt)  ( 8--)  UFCMA.bad2 <- UFCMA.bad2 || (t0 \in lt)
UFCMA.cbad2 <- UFCMA.cbad2 + 1           ( 9--)  UFCMA.cbad2 <- UFCMA.cbad2 + 1         
t <- t0                                  (10--)  t <- t0                                
x0 <- (n, C.ofintd 0)                    (11--)  i <- i + 1                             
y <- witness<:poly_out>                  (12--)                                         
SplitC2.I2.RO.m <-                       (13--)                                         
  SplitC2.I2.RO.m.[x0 <- y]              (   -)                                         
l0 <- drop 1 l0                          (14--)                                         

post =
  ((UF.forged{1} = UF.forged{2} /\
    UFCMA.bad2{1} = UFCMA.bad2{2} /\
    UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
    UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2}) /\
   l0{1} = drop i{2} ns2{2} /\
   0 <= i{2} /\
   uniq l0{1} /\
   forall (n0 : nonce), n0 \in l0{1} => (n0, C.ofintd 0) \notin ROout.m{1}) /\
  (l0{1} <> [] <=> i{2} < size ns2{2})
[561|check]>
```

## Status
remaining **3** · phase `seq_cut` / `procedure_body`

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

**Last action:** `by auto => />; smt(drop_nth drop_drop size_drop size_eq0 mem_set head_behead).` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
