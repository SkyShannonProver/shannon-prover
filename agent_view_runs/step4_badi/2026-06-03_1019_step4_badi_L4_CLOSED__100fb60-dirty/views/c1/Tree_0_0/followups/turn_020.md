## 🎯 Current Goal
```
Current goal (remaining: 9)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}
&2 (right) : {i : int, c2 : byte list, n, n0 : nonce,
             x, x0, x1 : nonce * C.counter, c1 : bytes, r : poly_in,
             t, t0, y, t1 : poly_out, z : block, a : associated_data,
             p1, p2 : message, nap : nonce * associated_data * message,
             ti : tag, p, p0 : plaintext, c, c0 : ciphertext, lt : tag list}

pre =
  (((Mem.lc{1} = Mem.lc{2} /\
     Mem.log{1} = Mem.log{2} /\
     (BNR.lenc{1}, BNR.ndec{1}) = (BNR.lenc{2}, BNR.ndec{2}) /\
     UFCMA.log{1} = UFCMA.log{2} /\
     UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
     UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
     RO.m{1} = RO.m{2} /\
     SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
     SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
    (n{1} = n{2} /\
     a{1} = a{2} /\ c1{1} = c1{2} /\ p0{1} = p0{2} /\ lt{1} = lt{2}) /\
    p{1} = p{2} /\
    UFCMA_li.i{2} = nth0 /\
    UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
    UFCMA_li.badi{2} =
    (nth0 < size UFCMA_l.lbad1{2} /\
     (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
     (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)) /\
   UFCMA.cbad1{1} < qenc /\ size lt{1} <= qdec) /\
  size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2}


post =
  forall (t0_0 : poly_out),
    t0_0 \in dpoly_out =>
    (forall (t1R : poly_out), t1R \in dpoly_out => t1R = t1R) &&
    forall (t0L : poly_out),
      t0L \in dpoly_out =>
      t0L = t0L &&
      let lbad1_R =
        UFCMA_l.lbad1{2} ++ map (fun (t' : tag) => (t0L, t')) lt{2} in
      (Mem.lc{1} = Mem.lc{2} /\
       Mem.log{1} = Mem.log{2} /\
       (BNR.lenc{1}, BNR.ndec{1}) = (BNR.lenc{2}, BNR.ndec{2}) /\
       UFCMA.log{1} = UFCMA.log{2} /\
       UFCMA.cbad1{1} + 1 = UFCMA.cbad1{2} + 1 /\
       UFCMA_l.lbad1{1} ++ map (fun (t' : tag) => (t0L, t')) lt{1} = lbad1_R /\
       RO.m{1} = RO.m{2} /\
       SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
       SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
      (n{1} = n{2} /\
       a{1} = a{2} /\ c1{1} = c1{2} /\ p0{1} = p0{2} /\ t0L = t0L) /\
      p{1} = p{2} /\
      UFCMA_li.i{2} = nth0 /\
      UFCMA_li.cbadi{2} + 1 = b2i (nth0 < size lbad1_R) /\
      (UFCMA_li.badi{2} ||
       t0L = nth witness lt{2} (UFCMA_li.i{2} - size UFCMA_l.lbad1{2})) =
      (nth0 < size lbad1_R /\
       (nth (w1, w2) lbad1_R nth0).`1 = (nth (w1, w2) lbad1_R nth0).`2)
[449|check]>
```

## Status
remaining **9** · phase `relational_program` / `prhl_module`

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
- you submitted: `commit_tactic` `rnd{2}.`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":20,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"rnd{2}."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"691 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
