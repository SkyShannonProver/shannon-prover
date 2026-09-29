## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–4) — absorb with `sp`/`wp`: 4 setup statement(s): k0 <- k; n0 <- n; c0 <- C.ofintd i; ... (1 more)
- frontier: right side only at `z <$ dblock`
- frontier: left side only at `r4 <$ dpoly_in`
- frontier: left side only at `r5 <$ dpoly_out`
- frontier: left side only at `r3 <$ dextra_block`
- frontier: left side only at `r0 <$ dblock`
- frontier: left side only at `if (SplitD.test x) {`
- frontier: left side only at `if (x4 \notin SplitC2.I1.RO.m) {`

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
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
&1 (left ) : {i : int, c : byte list, k, k0 : key, n, n0 : nonce,
             c0 : C.counter, x, x0, x1, x2, x3, x4, x5 : nonce * C.counter,
             r10, r4 : poly_in, r20, r5 : poly_out, r1 : poly,
             r2, r3 : extra_block, z, result, r, r0 : block, p : message}
&2 (right) : {i : int, c : byte list, n : nonce, z : block, p : message}

pre =
  ((c{1} = c{2} /\ i{1} = i{2}) /\
   n{1} = n0 /\
   p{2} = map (fun (_ : byte) => witness<:byte>) p{1} /\
   1 <= i{1} /\
   size c{1} + size p{1} <= max_cipher_size /\
   (p{1} <> [] => size c{1} = (i{1} - 1) * block_size) /\
   ROin.m{1} = mr0 /\
   ROout.m{1} = ms0 /\
   (forall (n1 : nonce) (c0_0 : C.counter),
      (n1, c0_0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\
   forall (c0_0 : C.counter), (n0, c0_0) \in ROF.m{1} => C.toint c0_0 < i{1}) /\
  p{1} <> [] /\ p{2} <> []

k0 <- k                               ( 1-----)  z <$ dblock                            
n0 <- n                               ( 2-----)  c <-                                   
                                      (   ----)    c ++ take (size p) (bytes_of_block z)
c0 <- C.ofintd i                      ( 3-----)  p <- drop block_size p                 
x <- (n0{!1}, c0)                     ( 4-----)  i <- i + 1                             
if (SplitD.test x) {                  ( 5-----)                                         
  x0 <- x                             ( 5. 1--)                                         
  x2 <- x0                            ( 5. 2--)                                         
  x4 <- x2                            ( 5. 3--)                                         
  r4 <$ dpoly_in                      ( 5. 4--)                                         
  if (x4 \notin SplitC2.I1.RO.m) {    ( 5. 5--)                                         
    SplitC2.I1.RO.m <-                ( 5. 5.1)                                         
      SplitC2.I1.RO.m.[x4 <- r4]      (       )                                         
  }                                   ( 5. 5--)                                         
  r10 <- oget SplitC2.I1.RO.m.[x4]    ( 5. 6--)                                         
  x5 <- x2                            ( 5. 7--)                                         
  r5 <$ dpoly_out                     ( 5. 8--)                                         
  if (x5 \notin SplitC2.I2.RO.m) {    ( 5. 9--)                                         
    SplitC2.I2.RO.m <-                ( 5. 9.1)                                         
      SplitC2.I2.RO.m.[x5 <- r5]      (       )                                         
  }                                   ( 5. 9--)                                         
  r20 <- oget SplitC2.I2.RO.m.[x5]    ( 5.10--)                                         
  r1 <- SplitC2.ofpair (r10, r20)     ( 5.11--)                                         
  x3 <- x0                            ( 5.12--)                                         
  r3 <$ dextra_block                  ( 5.13--)                                         
  if (x3 \notin SplitC1.I2.RO.m) {    ( 5.14--)                                         
    SplitC1.I2.RO.m <-                ( 5.14.1)                                         
      SplitC1.I2.RO.m.[x3 <- r3]      (       )                                         
  }                                   ( 5.14--)                                         
  r2 <- oget SplitC1.I2.RO.m.[x3]     ( 5.15--)                                         
  r <- SplitC1.ofpair (r1, r2)        ( 5.16--)                                         
} else {                              ( 5-----)                                         
  x1 <- x                             ( 5? 1--)                                         
  r0 <$ dblock                        ( 5? 2--)                                         
  if (x1 \notin SplitD.ROF.RO.m) {    ( 5? 3--)                                         
    SplitD.ROF.RO.m <-                ( 5? 3.1)                                         
      SplitD.ROF.RO.m.[x1 <- r0]      (       )                                         
  }                                   ( 5? 3--)                                         
  r <- oget SplitD.ROF.RO.m.[x1]      ( 5? 4--)                                         
}                                     ( 5-----)                                         
result <- r                           ( 6-----)                                         
z <- result                           ( 7-----)                                         
c <-                                  ( 8-----)                                         
  c ++                                (   ----)                                         
  take (size p)                       (   ----)                                         
    (bytes_of_block (extend p +^ z))  (   ----)                                         
p <- drop block_size p                ( 9-----)                                         
i <- i + 1                            (10-----)                                         

post =
  ((c{1} = c{2} /\ i{1} = i{2}) /\
   n{1} = n0 /\
   p{2} = map (fun (_ : byte) => witness<:byte>) p{1} /\
   1 <= i{1} /\
   size c{1} + size p{1} <= max_cipher_size /\
   (p{1} <> [] => size c{1} = (i{1} - 1) * block_size) /\
   ROin.m{1} = mr0 /\
   ROout.m{1} = ms0 /\
   (forall (n1 : nonce) (c0_0 : C.counter),
      (n1, c0_0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\
   forall (c0_0 : C.counter), (n0, c0_0) \in ROF.m{1} => C.toint c0_0 < i{1}) /\
  (p{1} = [] <=> p{2} = [])
[359|check]>
```

## Status
remaining **2** · phase `relational_program` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `inline{1}.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
