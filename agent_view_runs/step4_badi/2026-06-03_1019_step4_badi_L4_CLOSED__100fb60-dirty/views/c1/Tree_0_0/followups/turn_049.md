## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** split. — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** read your goal's first instruction (after `~`, below the `==>`), then find its row below.

**Head to tactic:**
- head `if` (same guard both sides) -> `if`.
- head `if` (divergent guard) -> `case: (<cond>)` then `rcondt{i} N` / `rcondf{i} N`.
- head `while` -> `while (<inv>)`; force the guard with `rcondt`/`rcondf`; never `while(true)` without a variant.
- head assignment `x <- e` -> `sp` / `wp`.
- head sample `x <$ d` -> `rnd`.
- head `call` -> `call (<invariant>)`, or `inline*`/`proc` to step into the body first.
- `invalid first instruction` / `right instruction list is not empty` = a side STILL HAS CODE: you cannot `skip`/`auto`/`sim`/`conseq`-close yet -> reduce the head with the matching tactic above (or `sp`/`wp` to consume statements first).

**Diagnosis:** local_pure_surgery_available

**Confidence:** medium

**Evidence:**
- pure_tail_surface is visible for the current goal
- current proof state has no program-frontier work before the logical residual

**Available local work:**
- pure tail obligation families: `constructor_projection`, `quantified_residual_logic`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Rewind targets:**
- `After seq opened / before branch work #17` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_17_26ba8c80c391c6c1"}}`
- `Before seq cut #16` — seq-cut boundary; selecting it restores the proof state before this cut was committed → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_16_26ba8c80c391c6c1"}}`

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (rewind_targets above name the exact points).

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
- you submitted: `commit_tactic` `split.`
- result: Commit attempt did not change the committed EasyCrypt proof state; use the returned result and latest view before trying the next proof intent.

```json
{"turn":49,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"split."}},"ok":true,"manager_note":"Commit attempt did not change the committed EasyCrypt proof state; use the returned result and latest view before trying the next proof intent.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.","timing":"3.2 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
