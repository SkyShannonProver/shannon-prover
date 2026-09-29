## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** smt(size_cat size_map nth_cat nth_map). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

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
- pure tail obligation families: `sampling_bijection`, `constructor_projection`, `quantified_residual_logic`
- membership decomposition sources: `concat_membership`, `map_membership`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Rewind targets:**
- `Before latest branch-local tactic #32` — latest branch-local step inside the current seq scope → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_32_09bca22ba30a8aa5"}}`
- `After seq opened / before branch work #17` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_17_09bca22ba30a8aa5"}}`
- `Before seq cut #16` — seq-cut boundary; selecting it restores the proof state before this cut was committed → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_16_09bca22ba30a8aa5"}}`

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (rewind_targets above name the exact points).

## 🎯 Current Goal
```
Current goal (remaining: 9)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
forall &1 &2,
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
  size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2} =>
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
[450|check]>
```

## Status
remaining **9** · phase `relational_program` / `ambient_logic`

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
- you submitted: `commit_tactic` `smt(size_cat size_map nth_cat nth_map).`
- result: Commit attempt did not change the committed EasyCrypt proof state; use the returned result and latest view before trying the next proof intent.

```json
{"turn":24,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"smt(size_cat size_map nth_cat nth_map)."}},"ok":true,"manager_note":"Commit attempt did not change the committed EasyCrypt proof state; use the returned result and latest view before trying the next proof intent.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.","timing":"5.9 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/resume_loop/BADI-L4/chunk1/2026-06-03_1049_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
