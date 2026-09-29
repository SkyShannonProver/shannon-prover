## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Where:**
- setup before the frontier (positions 1–8) — absorb with `sp`/`wp`: 11 setup statement(s): k0 <- k; n0 <- n; a0 <- a; ... (8 more)
- frontier: both sides at `no matching left-side sample at this frontier`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling (e.g. `t0{1} = t1{2}`), the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {k, k0, k1 : key, n, n0, n1 : nonce, c4 : C.counter,
             x, x0, x1, x2, x3, x4, x5 : nonce * C.counter, c2 : bytes,
             r, r10, r5 : poly_in, s, r20, r6 : poly_out, r1 : poly,
             r2, r4 : extra_block, b, result, r0, r3 : block,
             a, a0 : associated_data, p2, c3 : message,
             nap : nonce * associated_data * message, t : tag,
             p, p0, p1 : plaintext, c, c0, c1 : ciphertext}
&2 (right) : {n : nonce, c1 : bytes, t : poly_out, a : associated_data,
             p1 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext}

pre =
  c2{1} = c1{2} /\
  n{1} = n{2} /\
  a{1} = a{2} /\
  p0{1} = p0{2} /\
  p{1}.`1 = n{1} /\
  p{2}.`1 = n{2} /\
  Mem.log{1} = Mem.log{2} /\
  Mem.lc{1} = Mem.lc{2} /\
  BNR.lenc{1} = BNR.lenc{2} /\
  BNR.ndec{1} = BNR.ndec{2} /\
  ! (n{1} \in BNR.lenc{1}) /\
  (forall (nn : nonce) (ci : C.counter),
     (nn, ci) \in SplitC2.I1.RO.m{1} => nn \in BNR.lenc{1}) /\
  (forall (nn : nonce) (ci : C.counter),
     (nn, ci) \in SplitC2.I2.RO.m{1} => nn \in BNR.lenc{1}) /\
  forall (nn : nonce) (ci : C.counter),
    (nn, ci) \in SplitD.ROF.RO.m{1} => nn \in n{1} :: BNR.lenc{1}

k0 <- k                           ( 1--)  t <$ dpoly_out               
n0 <- n                           ( 2--)  c0 <- (n, a, c1, t)          
a0 <- a                           ( 3--)  Mem.log <- Mem.log.[c0 <- p0]
c3 <- c2                          ( 4--)  c <- c0                      
k1 <- k0                          ( 5--)  BNR.lenc <- p.`1 :: BNR.lenc 
n1 <- n0                          ( 6--)                               
c4 <- C.ofintd 0                  ( 7--)                               
x <- (n1, c4)                     ( 8--)                               
x0 <- x                           ( 9--)                               
x2 <- x0                          (10--)                               
x4 <- x2                          (11--)                               
r5 <$ dpoly_in                    (12--)                               
SplitC2.I1.RO.m <-                (13--)                               
  SplitC2.I1.RO.m.[x4 <- r5]      (   -)                               
r10 <- oget SplitC2.I1.RO.m.[x4]  (14--)                               
x5 <- x2                          (15--)                               
r6 <$ dpoly_out                   (16--)                               
SplitC2.I2.RO.m <-                (17--)                               
  SplitC2.I2.RO.m.[x5 <- r6]      (   -)                               
r20 <- oget SplitC2.I2.RO.m.[x5]  (18--)                               
r1 <- SplitC2.ofpair (r10, r20)   (19--)                               
x3 <- x0                          (20--)                               
r4 <$ dextra_block                (21--)                               
if (x3 \notin SplitC1.I2.RO.m) {  (22--)                               
  SplitC1.I2.RO.m <-              (22.1)                               
    SplitC1.I2.RO.m.[x3 <- r4]    (    )                               
}                                 (22--)                               
r2 <- oget SplitC1.I2.RO.m.[x3]   (23--)                               
r0 <- SplitC1.ofpair (r1, r2)     (24--)                               
result <- r0                      (25--)                               
b <- result                       (26--)                               
(r, s) <- mk_rs b                 (27--)                               
t <- poly1305 r s (topol a0 c3)   (28--)                               
c1 <- (n, a, c2, t)               (29--)                               
c0 <- c1                          (30--)                               
Mem.log <- Mem.log.[c0 <- p0]     (31--)                               
c <- c0                           (32--)                               
BNR.lenc <- p.`1 :: BNR.lenc      (33--)                               

post =
  c{1} = c{2} /\
  inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.
    lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\
  forall (n2 : nonce) (c5 : C.counter),
    (n2, c5) \in SplitD.ROF.RO.m{1} => n2 \in BNR.lenc{1}
[379|check]>
```

## Status
remaining **4** · phase `seq_cut` / `procedure_body`

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

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `commit_tactic` `inline*; rcondt{1} 9; 1:(by auto; smt(C.ofintdK C.gt0_max_counter)); rcondt{1} 13; 1:(by …`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":53,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"inline*; rcondt{1} 9; 1:(by auto; smt(C.ofintdK C.gt0_max_counter)); rcondt{1} 13; 1:(by auto; smt()); rcondt{1} 17; 1:(by auto; smt())."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"8.0 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
