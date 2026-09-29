## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Route:** experts decompose this shape as case split then rcond swap wp conseq → local smt.

**Why now:** current pRHL state looks past the main opener: the useful next work is local branch/suffix surgery, not changing proof family.

**Confidence:** medium — The current pRHL goal exposes a bad-event/instrumented branch together with sampling or one-sided suffix evidence; this is the shape where experts use `case`, `rcondt/rcondf`, `swap`, indexed `wp`, `conseq`, or one-sided `rnd` before local SMT. The fast-track tactic is schematic, so confidence is capped until the current view or an inspect result supplies concrete terms.

**Fast track probe:** try `case: (<current branch guard>).` first — Use only when the visible goal has a concrete guard controlling the local branch.

**Where:**
- setup before the frontier (positions 1–8) — absorb with `sp`/`wp`: 8 setup statement(s): p0 <- p; nap <- p0; (n, a, p1) <- nap; ... (5 more)

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Avoid:**
- This is a branch-local/suffix alignment problem; a fresh restart throws away useful opener and invariant work.
- One side has sampling or instrumentation before the suffix; use `rcond`, `swap`, or one-sided `rnd` before plain `wp`.
- `sim` is usually too late/too strong before the guard and suffix shape are aligned.

**Repair if fails:**
- syntax → inspect tactic_forms for swap, rcondt, rcondf, wp, conseq, rnd, or eager
- frontier → inspect align or goal_info for statement indexes before retrying
- invariant → use undo_to_checkpoint {} and choose the checkpoint before the call/loop invariant that should carry the missing guard or size fact
- lemma → inspect lemma_hints or lookup_symbol for the local size/nth/bad-event lemma
- route → downgrade this surgery route only after a smaller prefix and relevant tactic_forms fail

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling (e.g. `t0{1} = t1{2}`), the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}
&2 (right) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}

pre =
  (c{2} = witness /\
   c{1} = witness /\
   p{1} = p{2} /\
   (Mem.log{1} = Mem.log{2} /\
    Mem.lc{1} = Mem.lc{2} /\
    BNR.lenc{1} = BNR.lenc{2} /\
    BNR.ndec{1} = BNR.ndec{2} /\
    UFCMA.log{1} = UFCMA.log{2} /\
    UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
    RO.m{1} = RO.m{2} /\
    SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
    SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
   inv_lbad1 UFCMA_l.lbad1{2} BNR.lenc{2} UFCMA.log{2} Mem.log{2} Mem.lc{2}
     UFCMA.cbad1{2} BNR.ndec{2} /\
   (UFCMA.bad1{1} <=>
    exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2)) /\
  check_plaintext BNR.lenc{1} p{1}

p0 <- p                                    ( 1--)  p0 <- p                                
nap <- p0                                  ( 2--)  nap <- p0                              
(n, a, p1) <- nap                          ( 3--)  (n, a, p1) <- nap                      
n0 <- n                                    ( 4--)  n0 <- n                                
p2 <- p1                                   ( 5--)  p2 <- p1                               
p2 <-                                      ( 6--)  p2 <-                                  
  map (fun (_ : byte) => witness) p2       (   -)    map (fun (_ : byte) => witness) p2   
c2 <- []                                   ( 7--)  c2 <- []                               
i <- 1                                     ( 8--)  i <- 1                                 
while (p2 <> []) {                         ( 9--)  while (p2 <> []) {                     
  z <$ dblock                              ( 9.1)    z <$ dblock                          
  c2 <-                                    ( 9.2)    c2 <-                                
    c2 ++                                  (    )      c2 ++                              
    take (size p2) (bytes_of_block z)      (    )      take (size p2) (bytes_of_block z)  
  p2 <- drop block_size p2                 ( 9.3)    p2 <- drop block_size p2             
  i <- i + 1                               ( 9.4)    i <- i + 1                           
}                                          ( 9--)  }                                      
c1 <- c2                                   (10--)  c1 <- c2                               
lt <-                                      (11--)  lt <-                                  
  map (fun (c3 : ciphertext) => c3.`4)     (   -)    map (fun (c3 : ciphertext) => c3.`4) 
    (filter                                (   -)      (filter                            
       (fun (c3 : ciphertext) =>           (   -)         (fun (c3 : ciphertext) =>       
          c3.`1 = n) Mem.lc)               (   -)            c3.`1 = n) Mem.lc)           
t0 <$ dpoly_out                            (12--)  t0 <$ dpoly_out                        
if (UFCMA.cbad1 < qenc /\                  (13--)  if (UFCMA.cbad1 < qenc /\              
    size lt <= qdec) {                     (   -)      size lt <= qdec) {                 
  UFCMA.bad1 <- UFCMA.bad1 || (t0 \in lt)  (13.1)    UFCMA_l.lbad1 <-                     
                                           (    )      UFCMA_l.lbad1 ++                   
                                           (    )      map (fun (t' : tag) => (t0, t')) lt
  UFCMA.cbad1 <- UFCMA.cbad1 + 1           (13.2)    UFCMA.cbad1 <- UFCMA.cbad1 + 1       
}                                          (13--)  }                                      
t <- t0                                    (14--)  t <- t0                                
x <- (n, C.ofintd 0)                       (15--)  x <- (n, C.ofintd 0)                   
x1 <- x                                    (16--)  x1 <- x                                
r <$ dpoly_in                              (17--)  r <$ dpoly_in                          
if (x1 \notin RO.m) {                      (18--)  if (x1 \notin RO.m) {                  
  RO.m <- RO.m.[x1 <- r]                   (18.1)    RO.m <- RO.m.[x1 <- r]               
}                                          (18--)  }                                      
x0 <- (n, C.ofintd 0)                      (19--)  x0 <- (n, C.ofintd 0)                  
y <- witness                               (20--)  y <- witness                           
SplitC2.I2.RO.m <-                         (21--)  SplitC2.I2.RO.m <-                     
  SplitC2.I2.RO.m.[x0 <- y]                (   -)    SplitC2.I2.RO.m.[x0 <- y]            
UFCMA.log <-                               (22--)  UFCMA.log <-                           
  UFCMA.log.[n <- (a, c1, t)]              (   -)    UFCMA.log.[n <- (a, c1, t)]          
c0 <- (n, a, c1, t)                        (23--)  c0 <- (n, a, c1, t)                    
Mem.log <- Mem.log.[c0 <- p0]              (24--)  Mem.log <- Mem.log.[c0 <- p0]          
c <- c0                                    (25--)  c <- c0                                

post =
  let lenc_R = p{2}.`1 :: BNR.lenc{2} in
  c{1} = c{2} /\
  (Mem.log{1} = Mem.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   p{1}.`1 :: BNR.lenc{1} = lenc_R /\
   BNR.ndec{1} = BNR.ndec{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
  inv_lbad1 UFCMA_l.lbad1{2} lenc_R UFCMA.log{2} Mem.log{2} Mem.lc{2}
    UFCMA.cbad1{2} BNR.ndec{2} /\
  (UFCMA.bad1{1} <=>
   exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2)
[412|check]>
```

## Status
remaining **4** · phase `relational_program` / `procedure_body`

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

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `undo_to_checkpoint`
- result: Checkpoint rewind was handled by the manager; the latest view is authoritative.

```json
{"turn":1,"handled_intent":{"intent":"undo_to_checkpoint","payload":{"checkpoint_id":"cp_10_e0353f8a3e6324bd"}},"ok":true,"manager_note":"Checkpoint rewind was handled by the manager; the latest view is authoritative.","manager_actions":[{"action":"checkpoint rewind","outcome":"The manager rewound this branch to the selected checkpoint.","timing":"1.8 s"},{"action":"replay prefix step 1","outcome":"The manager completed this proof-level request.","timing":"1.6 s"},{"action":"replay prefix step 2","outcome":"The manager completed this proof-level request.","timing":"1.9 s"},{"action":"replay prefix step 3","outcome":"The manager completed this proof-level request.","timing":"1.8 s"},{"action":"replay prefix step 4","outcome":"The manager completed this proof-level request.","timing":"1.8 s"},{"action":"replay prefix step 5","outcome":"The manager completed this proof-level request.","timing":"239 ms"},{"action":"replay prefix step 6","outcome":"The manager completed this proof-level request.","timing":"327 ms"},{"action":"replay prefix step 7","outcome":"The manager completed this proof-level request.","timing":"360 ms"},{"action":"replay prefix step 8","outcome":"The manager completed this proof-level request.","timing":"325 ms"},{"action":"replay prefix step 9","outcome":"The manager completed this proof-level request.","timing":"390 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
