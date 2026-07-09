## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–4) — absorb with `sp`/`wp`: 4 setup statement(s): UFCMA.bad1 <- false; UFCMA.cbad1 <- 0; UFCMA.bad2 <- false
- frontier: both sides at `b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA2(RO).O).main()`
- frontier: right side only at `r <@ RO.get(n, C.ofintd 0)`
- frontier: right side only at `t <@ UFCMA(RO).set_bad2(map (fun (c : ciphertext) => c.`4 - `
- frontier: right side only at `while (i < size ns1) {`
- frontier: both sides at `if (size Mem.lc <= qdec) {`

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
Current goal

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, ns, ns1, ns2 : nonce list}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}

pre = (glob A){1} = (glob A){2}

UFCMA.bad1 <- false                        (1----)  UFCMA.bad1 <- false                                   
UFCMA.cbad1 <- 0                           (2----)  UFCMA.cbad1 <- 0                                      
UFCMA.bad2 <- false                        (3----)  UFCMA.bad2 <- false                                   
UFCMA.cbad2 <- 0                           (4----)  UFCMA.cbad2 <- 0                                      
b <@                                       (5----)  b <@                                                  
  CPA_game(CCA_CPA_Adv(BNR_Adv(A)),        (  ---)    CPA_game(CCA_CPA_Adv(BNR_Adv(A)),                   
    UFCMA2(RO).O).main()                   (  ---)      UFCMA3(RO).O).main()                              
UF.forged <- false                         (6----)  UF.forged <- false                                    
if (size Mem.lc <= qdec) {                 (7----)  if (size Mem.lc <= qdec) {                            
  ns <-                                    (7.1--)    ns <-                                               
    undup                                  (    -)      undup                                             
      (map (fun (p : ciphertext) => p.`1)  (    -)        (map (fun (p : ciphertext) => p.`1)             
         Mem.lc)                           (    -)           Mem.lc)                                      
  ns1 <-                                   (7.2--)    ns1 <-                                              
    filter                                 (    -)      filter                                            
      (fun (n0 : nonce) =>                 (    -)        (fun (n0 : nonce) =>                            
         (n0, C.ofintd 0) \in ROout.m) ns  (    -)           (n0, C.ofintd 0) \in ROout.m) ns             
  ns2 <-                                   (7.3--)    ns2 <-                                              
    filter                                 (    -)      filter                                            
      (fun (n0 : nonce) =>                 (    -)        (fun (n0 : nonce) =>                            
         (n0, C.ofintd 0) \notin ROout.m)  (    -)           (n0, C.ofintd 0) \notin ROout.m)             
      ns                                   (    -)        ns                                              
  Iter(Orcl).iter(ns1 ++ ns2)              (7.4--)    i <- 0                                              
                                           (7.5--)    while (i < size ns1) {                              
                                           (7.5.1)      n <- nth witness<:nonce> ns1 i                    
                                           (7.5.2)      r <@ RO.get(n, C.ofintd 0)                        
                                           (7.5.3)      UF.forged <-                                      
                                           (     )        UF.forged ||                                    
                                           (     )        test_poly_in n Mem.lc r                         
                                           (     )          (oget UFCMA.log.[n])                          
                                           (7.5.4)      i <- i + 1                                        
                                           (7.5--)    }                                                   
                                           (7.6--)    i <- 0                                              
                                           (7.7--)    while (i < size ns2) {                              
                                           (7.7.1)      n <- nth witness<:nonce> ns2 i                    
                                           (7.7.2)      r <@ RO.get(n, C.ofintd 0)                        
                                           (7.7.3)      t <@                                              
                                           (     )        UFCMA(RO).set_bad2(map                          
                                           (     )                             (fun (c : ciphertext) =>   
                                           (     )                                c.`4 -                  
                                           (     )                                poly1305_eval           
                                           (     )                                  r                     
                                           (     )                                  (topol c.`2           
                                           (     )                                    c.`3))              
                                           (     )                             (filter                    
                                           (     )                                (fun (c : ciphertext) =>
                                           (     )                                   c.`1 = n)            
                                           (     )                                Mem.lc))                
                                           (7.7.4)      i <- i + 1                                        
                                           (7.7--)    }                                                   
}                                          (7----)  }                                                     

post =
  (UFCMA.bad2{1} = UFCMA.bad2{2} /\ UF.forged{1} = UF.forged{2}) /\
  (UF.forged{2} \/ UFCMA.bad2{2}) = (UF.forged{2} \/ UFCMA.bad2{2})
[546|check]>
```

## Status
remaining **1** · phase `seq_cut` / `call_site`

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

**Last action:** `proc.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
