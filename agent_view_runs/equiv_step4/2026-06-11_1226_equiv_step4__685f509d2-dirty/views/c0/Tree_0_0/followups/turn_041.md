## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; (have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{2}, C.ofintd 0 <- r4L] = RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r2L] by rewrite set_setE /#); rewrite !get_setE /=; smt(). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** the goal is a pure logical residual (NO program frontier) — discharge it with the right lemmas / rewrites; `lookup_symbol` any operator for its definition and lemmas

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `apply <order/pure lemma>` — close by the matching logical/order lemma
- `case (<cond>)` — split a disjunction / membership in the goal

**Evidence:**
- membership source shapes: filter_membership, map_membership, map_update_membership
- map update keys: t1{2}, C.ofintd 0, t2{2}, C.ofintd 0
- membership fact: r4L \in dpoly_in =>

**Available local work:**
- pure tail obligation families: `sampling_bijection`, `map_update_projection`, `constructor_projection`, `map_membership_preservation`, `quantified_residual_logic`
- membership decomposition sources: `map_membership`, `filter_membership`, `map_update_membership`
- map update lookup cases: `t1{2}, C.ofintd 0`, `t2{2}, C.ofintd 0`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Rewind targets:**
- `After seq opened / before branch work #19` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_19_172aee0d91d343ce"}}`
- `Before seq cut #18` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_18_172aee0d91d343ce"}}`
- `After seq opened / before branch work #19` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_19_172aee0d91d343ce"}}`
- `Before seq cut #18` — seq-cut boundary; selecting it restores the proof state before this cut was committed → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_18_172aee0d91d343ce"}}`

**Yours:** the lemmas for `smt`, the rewrite chain, the apply target, the case condition — `lookup_symbol` any operator. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint`. (rewind_targets above name the exact points).

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

------------------------------------------------------------------------
forall &2,
  t1{2} <> t2{2} =>
  (t1{2}, C.ofintd 0) \notin SplitC2.I2.RO.m{2} =>
  (t2{2}, C.ofintd 0) \notin SplitC2.I2.RO.m{2} =>
  (t1{2}, C.ofintd 0) \notin RO.m{2} =>
  (t2{2}, C.ofintd 0) \notin RO.m{2} =>
  forall (r4L : poly_in),
    r4L \in dpoly_in =>
    forall (t4L : poly_out),
      t4L \in dpoly_out =>
      forall (r2L : poly_in),
        r2L \in dpoly_in =>
        forall (t3L : poly_out),
          t3L \in dpoly_out =>
          ((UFCMA.bad2{2} ||
            (t3L \in
             map
               (fun (c : ciphertext) =>
                  c.`4 -
                  poly1305_eval
                    (oget
                       RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t1{2}, C.ofintd 0])
                    (topol c.`2 c.`3))
               (filter (fun (c : ciphertext) => c.`1 = t1{2}) Mem.lc{2}))) ||
           (t4L \in
            map
              (fun (c : ciphertext) =>
                 c.`4 -
                 poly1305_eval
                   (oget
                      RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{2}, C.ofintd 0 <-
                        r4L].[t2{2}, C.ofintd 0]) (topol c.`2 c.`3))
              (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) =
          ((UFCMA.bad2{2} ||
            (t4L \in
             map
               (fun (c : ciphertext) =>
                  c.`4 -
                  poly1305_eval
                    (oget
                       RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t2{2}, C.ofintd 0])
                    (topol c.`2 c.`3))
               (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) ||
           (t3L \in
            map
              (fun (c : ciphertext) =>
                 c.`4 -
                 poly1305_eval
                   (oget
                      RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <-
                        r2L].[t1{2}, C.ofintd 0]) (topol c.`2 c.`3))
              (filter (fun (c : ciphertext) => c.`1 = t1{2}) Mem.lc{2}))) /\
          RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{2}, C.ofintd 0 <- r4L] =
          RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r2L] /\
          SplitC2.I2.RO.m{2}.[t1{2}, C.ofintd 0 <- witness<:poly_out>].[t2{2}, 
            C.ofintd 0 <- witness<:poly_out>] =
          SplitC2.I2.RO.m{2}.[t2{2}, C.ofintd 0 <- witness<:poly_out>].[t1{2}, 
            C.ofintd 0 <- witness<:poly_out>]
[538|check]>
```

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `move=> &2 ne h1 h2 h3 h4 r4L _ t4L _ r2L _ t3L _; (have ->: RO.m{2}.[t1{2}, C.o…` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `auto => />.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
