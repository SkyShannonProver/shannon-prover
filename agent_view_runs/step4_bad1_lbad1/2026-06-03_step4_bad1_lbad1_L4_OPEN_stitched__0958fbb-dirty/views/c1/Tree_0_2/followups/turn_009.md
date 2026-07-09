## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list} [programs are in sync]
&2 (right) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}

pre =
  exists (cbad1_R : int) (lbad1_R : (tag * tag) list),
    UFCMA_l.lbad1{2} = lbad1_R ++ map (fun (t' : tag) => (t0{2}, t')) lt{2} /\
    UFCMA.cbad1{2} = cbad1_R + 1 /\
    t{2} = t0{2} /\
    x{2} = (n{2}, C.ofintd 0) /\
    x1{2} = x{2} /\
    exists (cbad1_L : int) (bad1_L : bool),
      UFCMA.bad1{1} = (bad1_L || (t0{1} \in lt{1})) /\
      UFCMA.cbad1{1} = cbad1_L + 1 /\
      t{1} = t0{1} /\
      x{1} = (n{1}, C.ofintd 0) /\
      x1{1} = x{1} /\
      ((n{1} = n{2} /\
        a{1} = a{2} /\
        c1{1} = c1{2} /\
        lt{1} = lt{2} /\
        t0{1} = t0{2} /\
        p0{1} = p0{2} /\
        p{1} = p{2} /\
        Mem.log{1} = Mem.log{2} /\
        Mem.lc{1} = Mem.lc{2} /\
        BNR.lenc{1} = BNR.lenc{2} /\
        BNR.ndec{1} = BNR.ndec{2} /\
        UFCMA.log{1} = UFCMA.log{2} /\
        cbad1_L = cbad1_R /\
        RO.m{1} = RO.m{2} /\
        SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
        SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
       inv_lbad1 lbad1_R BNR.lenc{2} UFCMA.log{2} Mem.log{2} Mem.lc{2}
         cbad1_R BNR.ndec{2} /\
       (bad1_L <=> exists (tt : tag * tag), (tt \in lbad1_R) /\ tt.`1 = tt.`2) /\
       check_plaintext BNR.lenc{1} p{1} /\
       n{1} = p{1}.`1 /\
       lt{2} =
       map (fun (c3 : ciphertext) => c3.`4)
         (filter (fun (c3 : ciphertext) => c3.`1 = n{2}) Mem.lc{2})) /\
      cbad1_L < qenc /\ size lt{1} <= qdec


post =
  (forall (rR : poly_in), rR \in dpoly_in => rR = rR) &&
  forall (rL : poly_in),
    rL \in dpoly_in =>
    rL = rL &&
    if x1{2} \notin RO.m{2} then
      let m_R = RO.m{2}.[x1{2} <- rL] in
      let m_R0 = SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] in
      let log_R = UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] in
      let c0_R = (n{2}, a{2}, c1{2}, t{2}) in
      let log_R0 = Mem.log{2}.[c0_R <- p0{2}] in
      if x1{1} \notin RO.m{1} then
        let c0_L = (n{1}, a{1}, c1{1}, t{1}) in
        let lenc_R = p{2}.`1 :: BNR.lenc{2} in
        c0_L = c0_R /\
        (Mem.log{1}.[c0_L <- p0{1}] = log_R0 /\
         Mem.lc{1} = Mem.lc{2} /\
         p{1}.`1 :: BNR.lenc{1} = lenc_R /\
         BNR.ndec{1} = BNR.ndec{2} /\
         UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = log_R /\
         UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
         RO.m{1}.[x1{1} <- rL] = m_R /\
         SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = m_R0 /\
         SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
        inv_lbad1 UFCMA_l.lbad1{2} lenc_R log_R log_R0 Mem.lc{2}
          UFCMA.cbad1{2} BNR.ndec{2} /\
        (UFCMA.bad1{1} <=>
         exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2)
      else
        let c0_L = (n{1}, a{1}, c1{1}, t{1}) in
        let lenc_R = p{2}.`1 :: BNR.lenc{2} in
        c0_L = c0_R /\
        (Mem.log{1}.[c0_L <- p0{1}] = log_R0 /\
         Mem.lc{1} = Mem.lc{2} /\
         p{1}.`1 :: BNR.lenc{1} = lenc_R /\
         BNR.ndec{1} = BNR.ndec{2} /\
         UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = log_R /\
         UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
         RO.m{1} = m_R /\
         SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = m_R0 /\
         SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
        inv_lbad1 UFCMA_l.lbad1{2} lenc_R log_R log_R0 Mem.lc{2}
          UFCMA.cbad1{2} BNR.ndec{2} /\
        (UFCMA.bad1{1} <=>
         exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2)
    else
      let m_R = SplitC2.I2.RO.m{2}.[n{2}, C.ofintd 0 <- witness] in
      let log_R = UFCMA.log{2}.[n{2} <- (a{2}, c1{2}, t{2})] in
      let c0_R = (n{2}, a{2}, c1{2}, t{2}) in
      let log_R0 = Mem.log{2}.[c0_R <- p0{2}] in
      if x1{1} \notin RO.m{1} then
        let c0_L = (n{1}, a{1}, c1{1}, t{1}) in
        let lenc_R = p{2}.`1 :: BNR.lenc{2} in
        c0_L = c0_R /\
        (Mem.log{1}.[c0_L <- p0{1}] = log_R0 /\
         Mem.lc{1} = Mem.lc{2} /\
         p{1}.`1 :: BNR.lenc{1} = lenc_R /\
         BNR.ndec{1} = BNR.ndec{2} /\
         UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = log_R /\
         UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
         RO.m{1}.[x1{1} <- rL] = RO.m{2} /\
         SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = m_R /\
         SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
        inv_lbad1 UFCMA_l.lbad1{2} lenc_R log_R log_R0 Mem.lc{2}
          UFCMA.cbad1{2} BNR.ndec{2} /\
        (UFCMA.bad1{1} <=>
         exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2)
      else
        let c0_L = (n{1}, a{1}, c1{1}, t{1}) in
        let lenc_R = p{2}.`1 :: BNR.lenc{2} in
        c0_L = c0_R /\
        (Mem.log{1}.[c0_L <- p0{1}] = log_R0 /\
         Mem.lc{1} = Mem.lc{2} /\
         p{1}.`1 :: BNR.lenc{1} = lenc_R /\
         BNR.ndec{1} = BNR.ndec{2} /\
         UFCMA.log{1}.[n{1} <- (a{1}, c1{1}, t{1})] = log_R /\
         UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
         RO.m{1} = RO.m{2} /\
         SplitC2.I2.RO.m{1}.[n{1}, C.ofintd 0 <- witness] = m_R /\
         SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
        inv_lbad1 UFCMA_l.lbad1{2} lenc_R log_R log_R0 Mem.lc{2}
          UFCMA.cbad1{2} BNR.ndec{2} /\
        (UFCMA.bad1{1} <=>
         exists (tt : tag * tag), (tt \in UFCMA_l.lbad1{2}) /\ tt.`1 = tt.`2)
[418|check]>
```

## Status
remaining **5** · phase `relational_program` / `verification_residue`

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
- you submitted: `probe_tactic` `move=> />.`
- result: Read-only tactic probe. Use any goal-after-probe text as a preview only; there is no probe step to undo.

```json
{"turn":9,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"move=> />."}},"ok":true,"manager_note":"Read-only tactic probe. Use any goal-after-probe text as a preview only; there is no probe step to undo.","manager_actions":[{"action":"tactic probe","outcome":"EasyCrypt rejected this probe or could not use it. The committed proof state was not changed; use the error summary to revise the tactic.","timing":"1.1 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/resume-chunks/step4_extend60/2026-06-03_1301_step4_bad1_lbad1/iteration_1/node_memory/Tree_0_2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
