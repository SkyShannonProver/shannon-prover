## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Where:**
- setup before the frontier (positions 1–8) — absorb with `sp`/`wp`: 11 setup statement(s): k0 <- k; n0 <- n; a0 <- a; ... (8 more)

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

k0 <- k                    ( 1)                           
n0 <- n                    ( 2)                           
a0 <- a                    ( 3)                           
c3 <- c2                   ( 4)                           
k1 <- k0                   ( 5)                           
n1 <- n0                   ( 6)                           
c4 <- C.ofintd 0           ( 7)                           
x <- (n1, c4)              ( 8)                           
x0 <- x                    ( 9)                           
x2 <- x0                   (10)                           
x4 <- x2                   (11)                           

post =
  forall (r5_0 : poly_in),
    r5_0 \in dpoly_in =>
    let m_L = SplitC2.I1.RO.m{1}.[x4{1} <- r5_0] in
    (forall (tR : poly_out),
       tR \in dpoly_out =>
       tR =
       tR - poly1305_eval r5_0 (topol a0{1} c3{1}) +
       poly1305_eval r5_0 (topol a0{1} c3{1})) &&
    forall (r6L : poly_out),
      r6L \in dpoly_out =>
      r6L =
      r6L + poly1305_eval r5_0 (topol a0{1} c3{1}) -
      poly1305_eval r5_0 (topol a0{1} c3{1}) &&
      let m_L0 = SplitC2.I2.RO.m{1}.[x2{1} <- r6L] in
      let r1_L = SplitC2.ofpair (oget m_L.[x4{1}], oget m_L0.[x2{1}]) in
      forall (r4_0 : extra_block),
        r4_0 \in dextra_block =>
        let c0_R =
          (n{2}, a{2}, c1{2}, r6L + poly1305_eval r5_0 (topol a0{1} c3{1}))
        in
        let log_R = Mem.log{2}.[c0_R <- p0{2}] in
        let lenc_R = p{2}.`1 :: BNR.lenc{2} in
        if x0{1} \notin SplitC1.I2.RO.m{1} then
          let tpl =
            mk_rs
              (SplitC1.ofpair
                 (r1_L, oget SplitC1.I2.RO.m{1}.[x0{1} <- r4_0].[x0{1}])) in
          let c0_L =
            (n{1}, a{1}, c2{1}, poly1305 tpl.`1 tpl.`2 (topol a0{1} c3{1}))
          in
          let lenc_L = p{1}.`1 :: BNR.lenc{1} in
          c0_L = c0_R /\
          inv_cpa m_L m_L0 Mem.log{1}.[c0_L <- p0{1}] log_R Mem.lc{1} Mem.
            lc{2} lenc_L lenc_R BNR.ndec{1} BNR.ndec{2} /\
          forall (n2 : nonce) (c5 : C.counter),
            (n2, c5) \in SplitD.ROF.RO.m{1} => n2 \in lenc_L
        else
          let tpl =
            mk_rs (SplitC1.ofpair (r1_L, oget SplitC1.I2.RO.m{1}.[x0{1}])) in
          let c0_L =
            (n{1}, a{1}, c2{1}, poly1305 tpl.`1 tpl.`2 (topol a0{1} c3{1}))
          in
          let lenc_L = p{1}.`1 :: BNR.lenc{1} in
          c0_L = c0_R /\
          inv_cpa m_L m_L0 Mem.log{1}.[c0_L <- p0{1}] log_R Mem.lc{1} Mem.
            lc{2} lenc_L lenc_R BNR.ndec{1} BNR.ndec{2} /\
          forall (n2 : nonce) (c5 : C.counter),
            (n2, c5) \in SplitD.ROF.RO.m{1} => n2 \in lenc_L
[386|check]>
```

## Status
remaining **4** · phase `relational_program` / `procedure_body`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
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
- you submitted: `probe_tactic` `auto => /=; rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add…`
- result: Read-only tactic probe. Use any goal-after-probe text as a preview only; there is no probe step to undo.

```json
{"turn":44,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"auto => /=; rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_setE mem_set)."}},"ok":true,"manager_note":"Read-only tactic probe. Use any goal-after-probe text as a preview only; there is no probe step to undo.","manager_actions":[{"action":"tactic probe","outcome":"The read-only probe tool failed before EasyCrypt could validate this tactic. The committed proof state was not changed; use the error summary as a backend health signal, not as proof that the tactic is invalid.","timing":"5.9 s","error_summary":"cannot prove goal (strict)"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
