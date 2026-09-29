## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 3–6) — absorb with `sp`/`wp`: 4 setup statement(s): h <- g ^ w0; (x, w) <- (h, w0); h0 <- x; ... (1 more)
- frontier: both sides at `b <@ D.distinguish(x, t)`
- frontier: both sides at `w0 <$ dt`
- frontier: both sides at `r <$ dt`
- frontier: both sides at `if (w0 = zero) {`

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

D : SigmaTraceDistinguisher
&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, v, v0 : bool, i : int,
             h, a, a0, v1, v', a2, v2, v'0 : group,
             w0, r, z1, z3 : ZModE.exp,
             x, h0, x0, x1, h1, h2, h3, h4 : statement, w, w1 : witness,
             m, m0, m1, a1, a3 : message, s : secret,
             e, e0, e1, e2, e3, e4, e5 : challenge, z, z0, z2, z4 : response,
             t : message * challenge * response,
             to, to0, to1 : (message * challenge * response) option}
&2 (right) : {b : bool, h, a : group, w0, r, e1, z1 : ZModE.exp,
             x, x0, h0, h1 : statement, w, w1, w2 : witness,
             m, m0, a0 : message, s, r0 : secret, e, e0, e2 : challenge,
             z, z0 : response, t : message * challenge * response,
             sw : statement * witness, ms : message * secret}

pre = (glob D){2} = (glob D){m} /\ (glob D){1} = (glob D){m}

w0 <$ dt                              ( 1--)  w0 <$ dt                        
if (w0 = zero) {                      ( 2--)  if (w0 = zero) {                
  w0 <- zero                          ( 2.1)    w0 <- zero                    
}                                     ( 2--)  }                               
h <- g ^ w0                           ( 3--)  h <- g ^ w0                     
(x, w) <- (h, w0)                     ( 4--)  (x0, w) <- (h, w0)              
h0 <- x                               ( 5--)  h0 <- x0                        
w1 <- w                               ( 6--)  w1 <- w                         
r <$ dt                               ( 7--)  r <$ dt                         
a <- g ^ r                            ( 8--)  a <- g ^ r                      
(m, s) <- (a, r)                      ( 9--)  (m0, s) <- (a, r)               
e <$ de                               (10--)  h1 <- x0                        
x0 <- x                               (11--)  a0 <- m0                        
e0 <- e                               (12--)  e1 <$ dt                        
h1 <- x0                              (13--)  e0 <- e1                        
e2 <- e0                              (14--)  sw <- (x0, w)                   
z1 <$ dt                              (15--)  ms <- (m0, s)                   
a0 <- g ^ z1 * h1 ^ -e2               (16--)  e2 <- e0                        
(m0, e0, z) <- (a0, e2, z1)           (17--)  w2 <- sw.`2                     
h2 <- x0                              (18--)  r0 <- ms.`2                     
a1 <- m0                              (19--)  z1 <- r0 + e2 * w2              
e3 <- e0                              (20--)  z0 <- z1                        
z2 <- z                               (21--)  (x, m, e, z) <- (x0, m0, e0, z0)
v1 <- a1 * h2 ^ e3                    (22--)  t <- (m, e, z)                  
v' <- g ^ z2                          (23--)  b <@ D.distinguish(x, t)        
v <- v1 = v'                          (24--)                                  
if (v) {                              (25--)                                  
  to0 <- Some (m0, e0, z)             (25.1)                                  
} else {                              (25--)                                  
  to0 <- None<:message * challenge *  (25?1)                                  
    response>                         (    )                                  
}                                     (25--)                                  
to <- to0                             (26--)                                  
i <- 0                                (27--)                                  
t <- oget to                          (28--)                                  
b <@ D.distinguish(x, t)              (29--)                                  

post = b{1} = b{2}
[45|check]>
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

**Last action:** `auto => />; smt(expN expD exp0 mulcA mulVc mulcV mulc1).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_heroes/l4_checked_action_surface/schnorr_shvzk/r01/2026-06-09_1149_schnorr_proof_of_knowledge_shvzk/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
