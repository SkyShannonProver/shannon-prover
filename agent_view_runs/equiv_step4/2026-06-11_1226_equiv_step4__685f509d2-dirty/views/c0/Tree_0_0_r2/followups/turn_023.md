## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: n <- head witness<:nonce> l0
- frontier: both sides at `r <@ RO.get(n, C.ofintd 0)`
- frontier: both sides at `t <@ UFCMA(RO).set_bad2(map (fun (c : ciphertext) => c.`4 - `

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
Current goal (remaining: 3)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, n : nonce, ns, ns1, ns2, l1, l2, l, l0 : nonce list,
             r : poly_in, t : poly_out}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}

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

n <- head witness<:nonce> l0                        (1)  n <- nth witness<:nonce> ns2 i                    
r <@ RO.get(n, C.ofintd 0)                          (2)  r <@ RO.get(n, C.ofintd 0)                        
t <@                                                (3)  t <@                                              
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
ROout.set((n, C.ofintd 0),                          (4)  i <- i + 1                                        
  witness<:poly_out>)                               ( )                                                    
l0 <- drop 1 l0                                     (5)                                                    

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
[560|check]>
```

## Status
remaining **3** · phase `seq_cut` / `call_site`

### Need more? submit one of these read-only requests
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

**Last action:** `rcondf{1} 2; first by auto => />; smt(head_behead).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
