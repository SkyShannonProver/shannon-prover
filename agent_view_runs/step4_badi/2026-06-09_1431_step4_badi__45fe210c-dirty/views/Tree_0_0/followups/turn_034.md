## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
nth0: int
h0nth0: 0 <= nth0
hnth0q: nth0 < qdec
------------------------------------------------------------------------
forall &2,
  (nth0 < size UFCMA_l.lbad1{2} =>
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
   (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2}) =>
  ! (UFCMA.cbad1{2} < qenc /\
     size lt{2} <= qdec /\
     size UFCMA_l.lbad1{2} <= nth0 < size UFCMA_l.lbad1{2} + size lt{2}) =>
  UFCMA.cbad1{2} < qenc =>
  size lt{2} <= qdec =>
  ((if nth0 < size UFCMA_l.lbad1{2} then 1 else 0) =
   if nth0 <
      size (UFCMA_l.lbad1{2} ++ map (fun (t' : tag) => (t{2}, t')) lt{2})
     then 1
   else 0) /\
  (nth0 < size (UFCMA_l.lbad1{2} ++ map (fun (t' : tag) => (t{2}, t')) lt{2}) =>
   (nth (w1, w2)
      (UFCMA_l.lbad1{2} ++ map (fun (t' : tag) => (t{2}, t')) lt{2}) nth0).`1 =
   (nth (w1, w2)
      (UFCMA_l.lbad1{2} ++ map (fun (t' : tag) => (t{2}, t')) lt{2}) nth0).`2 =>
   UFCMA_li.badi{2})
[444|check]>
```

**Last action:** `move=> &2 hinv hneg hc1 hltq; rewrite size_cat size_map nth_cat; smt().` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
