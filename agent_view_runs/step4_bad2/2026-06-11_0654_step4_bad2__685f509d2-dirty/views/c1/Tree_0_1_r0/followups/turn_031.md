## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** smt(ge0_pr_zeropol). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** the goal is a pure logical residual (NO program frontier) — discharge it with the right lemmas / rewrites; `lookup_symbol` any operator for its definition and lemmas

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `apply <order/pure lemma>` — close by the matching logical/order lemma
- `case (<cond>)` — split a disjunction / membership in the goal

**Evidence:**
- membership source shapes: filter_membership, map_membership
- membership fact: (predC (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr})) (fun (n0 : nonce) =>

**Available local work:**
- pure tail obligation families: `sampling_bijection`, `constructor_projection`, `quantified_residual_logic`
- membership decomposition sources: `map_membership`, `filter_membership`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Rewind targets:**
- `After seq opened / before branch work #13` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_13_8f915181c518ae22"}}`
- `Before latest branch-local tactic #34` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_34_8f915181c518ae22"}}`
- `After seq opened / before branch work #13` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_13_8f915181c518ae22"}}`
- `Before latest branch-local tactic #34` — latest branch-local step inside the current seq scope → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_34_8f915181c518ae22"}}`
- `Before seq cut #12` — seq-cut boundary; selecting it restores the proof state before this cut was committed → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_12_8f915181c518ae22"}}`

**Yours:** the lemmas for `smt`, the rewrite chain, the apply target, the case condition — `lookup_symbol` any operator. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint`. (rewind_targets above name the exact points).

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
&hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list, r : poly_in,
     t : poly_out}
szlc: size Mem.lc{hr} <= qdec
nE: BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})
      (fun (n0 : nonce) =>
         (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
      (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) =
    BRA.big
      (predC (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr}))
      (fun (n0 : nonce) =>
         (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
      (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}))
key: BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr})
       (fun (n0 : nonce) =>
          (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
       (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) +
     BRA.big
       (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})
       (fun (n0 : nonce) =>
          (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
       (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) =
     (size Mem.lc{hr})%r
hA: 0%r <=
    BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr})
      (fun (n0 : nonce) =>
         (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
      (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}))
hB: 0%r <=
    BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})
      (fun (n0 : nonce) =>
         (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
      (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}))
------------------------------------------------------------------------
BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \in SplitC2.I2.RO.m{hr})
  (fun (n0 : nonce) =>
     (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
  (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) *
pr_zeropol +
BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{hr})
  (fun (n0 : nonce) =>
     (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc{hr}))%r)
  (undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})) *
pr1_poly_out <= qdec%r * maxr pr_zeropol pr1_poly_out
[418|check]>
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

**Last action:** `smt(ge0_pr_zeropol).` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `have hB : 0%r <= BRA.big (fun (n0 : nonce) => (n0, C.ofintd 0) \notin SplitC2.I…` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
