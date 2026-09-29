## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–2) — absorb with `sp`/`wp`: 2 setup statement(s): n <- head witness<:nonce> l0; x <- (n, C.ofintd 0)
- frontier: both sides at `r0 <$ dpoly_in`
- frontier: both sides at `t0 <$ dpoly_out`
- frontier: both sides at `if (x \notin RO.m) {`

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

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_subgoals` (+invariant) · `align` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
