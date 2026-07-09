## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {b, b0, b1, b2 : bool}
&2 (right) : {b, b0, b1, b2 : bool, i0 : int}

pre =
  ((glob A){1} = (glob A){2} /\
   Mem.lc{1} = Mem.lc{2} /\
   Mem.log{1} = Mem.log{2} /\
   (BNR.lenc{1}, BNR.ndec{1}) = (BNR.lenc{2}, BNR.ndec{2}) /\
   UFCMA.log{1} = UFCMA.log{2} /\
   UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
   UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\
  UFCMA_li.i{2} = nth0 /\
  UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
  UFCMA_li.badi{2} =
  (nth0 < size UFCMA_l.lbad1{2} /\
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)


post =
  (true /\
   (glob A){1} = (glob A){2} /\
   Mem.lc{1} = Mem.lc{2} /\
   Mem.log{1} = Mem.log{2} /\
   BNR.lenc{1} = BNR.lenc{2} /\
   BNR.ndec{1} = BNR.ndec{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   UFCMA.cbad1{1} = UFCMA.cbad1{2} /\
   UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\
   RO.m{1} = RO.m{2} /\
   SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\
   SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\
   UFCMA_li.i{2} = nth0 /\
   UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\
   UFCMA_li.badi{2} =
   (nth0 < size UFCMA_l.lbad1{2} /\
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
    (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)) &&
  forall (result_L result_R : bool) (A_L : (glob A)) (lenc_L : nonce list)
    (ndec_L cbad1_L : int) (log_L : (nonce, associated_data * message *
    tag) fmap) (lbad1_L : (tag * tag) list) (m_L : (nonce * C.counter,
    poly_in) fmap) (lc_L : ciphertext list) (log_L0 : (ciphertext,
    plaintext) fmap) (m_L0 : (nonce * C.counter, poly_out) fmap)
    (A_R : (glob A)) (lenc_R : nonce list) (ndec_R cbad1_R : int)
    (log_R : (nonce, associated_data * message * tag) fmap) (lbad1_R : (tag *
    tag) list) (badi_R : bool) (cbadi_R : int) (m_R : (nonce * C.counter,
    poly_in) fmap) (lc_R : ciphertext list) (log_R0 : (ciphertext,
    plaintext) fmap) (m_R0 : (nonce * C.counter, poly_out) fmap),
    result_L = result_R /\
    A_L = A_R /\
    lc_L = lc_R /\
    log_L0 = log_R0 /\
    lenc_L = lenc_R /\
    ndec_L = ndec_R /\
    log_L = log_R /\
    cbad1_L = cbad1_R /\
    lbad1_L = lbad1_R /\
    m_L = m_R /\
    m_L0 = m_R0 /\
    SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\
    UFCMA_li.i{2} = nth0 /\
    cbadi_R = b2i (nth0 < size lbad1_R) /\
    badi_R =
    (nth0 < size lbad1_R /\
     (nth (w1, w2) lbad1_R nth0).`1 = (nth (w1, w2) lbad1_R nth0).`2) =>
    (let tt = nth (w1, w2) lbad1_L nth0 in tt.`1 = tt.`2) => badi_R
[468|check]>
```

## Status
remaining **3** · phase `relational_program` / `prhl_module`

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
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":52,"handled_intent":{"intent":"inspect_context","payload":{"topic":"goal_info"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect goal info","outcome":"The manager returned read-only context for the current goal.","timing":"2.0 s","content":{"title":"Parsed Goal Information","goal_info":{"goal_type":"pRHL","num_remaining":3,"num_remaining_determined":true,"pre":"pre = ((glob A){1} = (glob A){2} /\\ Mem.lc{1} = Mem.lc{2} /\\ Mem.log{1} = Mem.log{2} /\\ (BNR.lenc{1}, BNR.ndec{1}) = (BNR.lenc{2}, BNR.ndec{2}) /\\ UFCMA.log{1} = UFCMA.log{2} /\\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\\ UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\\ RO.m{1} = RO.m{2} /\\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2}) /\\ UFCMA_li.i{2} = nth0 /\\ UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\\ UFCMA_li.badi{2} = (nth0 < size UFCMA_l.lbad1{2} /\\ (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)","post":"post = (true /\\ (glob A){1} = (glob A){2} /\\ Mem.lc{1} = Mem.lc{2} /\\ Mem.log{1} = Mem.log{2} /\\ BNR.lenc{1} = BNR.lenc{2} /\\ BNR.ndec{1} = BNR.ndec{2} /\\ UFCMA.log{1} = UFCMA.log{2} /\\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\\ UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\\ RO.m{1} = RO.m{2} /\\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\\ UFCMA_li.i{2} = nth0 /\\ UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\\ UFCMA_li.badi{2} = (nth0 < size UFCMA_l.lbad1{2} /\\ (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)) && forall (result_L result_R : bool) (A_L : (glob A)) (lenc_L : nonce list) (ndec_L cbad1_L : int) (log_L : (nonce, associated_data * message * tag) fmap) (lbad1_L : (tag * tag) list) (m_L : (nonce * C.counter, poly_in) fmap) (lc_L : ciphertext list) (log_L0 : (ciphertext, plaintext) fmap) (m_L0 : (nonce * C.counter, poly_out) fmap) (A_R : (glob A)) (lenc_R : nonce list) (ndec_R cbad1_R : int) (log_R : (nonce, associated_data * message * tag) fmap) (lbad1_R : (tag * tag) list) (badi_R : bool) (cbadi_R : int) (m_R : (nonce * C.counter, poly_in) fmap) (lc_R : ciphertext list) (log_R0 : (ciphertext, plaintext) fmap) (m_R0 : (nonce * C.counter, poly_out) fmap), result_L = result_R /\\ A_L = A_R /\\ lc_L = lc_R /\\ log_L0 = log_R0 /\\ lenc_L = lenc_R /\\ ndec_L = ndec_R /\\ log_L = log_R /\\ cbad1_L = cbad1_R /\\ lbad1_L = lbad1_R /\\ m_L = m_R /\\ m_L0 = m_R0 /\\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\\ UFCMA_li.i{2} = nth0 /\\ cbadi_R = b2i (nth0 < size lbad1_R) /\\ badi_R = (nth0 < size lbad1_R /\\ (nth (w1, w2) lbad1_R nth0).`1 = (nth (w1, w2) lbad1_R nth0).`2) => (let tt = nth (w1, w2) lbad1_L nth0 in tt.`1 = tt.`2) => badi_R","remaining_goals_note":"You have 3 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 2 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress.","remaining_goals_inference":[{"subgoal_n":1,"predicted_type":"(inherits prior goal type)","description":"Conjunct 1 of N (split decomposition)","origin_tactic":"split."},{"subgoal_n":2,"predicted_type":"(inherits prior goal type)","description":"Conjunct 2 of N (split decomposition)","origin_tactic":"split."},{"subgoal_n":3,"predicted_type":"(inherits prior goal type)","description":"Conjunct 3 of N (split decomposition)","origin_tactic":"split."}],"remaining_goals_inference_caveat":"These subgoal shapes are INFERRED from the last branching tactic's known pattern, NOT read from EC directly (EC's emacs output only exposes the current goal). Use as hints, not ground truth. Ground truth is obtained by closing the current subgoal and running -goal-info on the next. Known-wrong cases: 3-arg `call (_: bad, Inv)`, nested branchers, while-variants with different arg counts."},"goal_state":{"state_kind":"open","goal_type":"pRHL","num_remaining":3,"num_remaining_determined":true,"proof_candidate_closed":false,"active_goal_hash":"6eee0d0062076d8d02b122546bc7f452e61a3c3c","authority":"pretty_text_fallback","ec_ground_truth":false},"history":{"tactic_count":50,"has_qed":false,"latest_tactic":"proc; inline*; auto."},"latest_transition":{"kind":"error","status":"error","goals_before":3,"goals_after":3,"candidate_closed":false,"no_progress":false,"latest_error":"[error] nothing to introduce","tactic":"move=> &1 &2 HP2; split; first by smt()."},"items":[{"candidate":"Phase-ordering hint: a named oracle-equivalence handle, if present in the current context, usually applies while the oracle call is still a single frontier call. Inspect the current call handles/signatures first; use `call <oracle_equiv>` or `ecall (<oracle_equiv> <args>)` before inlining the call body. Inlining first can expand the call into several statements and make the named handle no longer directly callable. For residual branch or predicate obligations, combine the generic idioms `unfold_op_invariant_sp_if_done_auto` and `ecall_oracle_equiv_then_unfold_ambient_close` as needed. Run `-tactic-forms call` / `-where <oracle_equiv>` rather than guessing argument order.","why":"Oracle-state invariant maintenance with multiple live maps/logs/counters on both sides","verification":"not daemon-verified against the current goal"}],"notes":[{"message":"You have 3 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 2 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress."}]}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
