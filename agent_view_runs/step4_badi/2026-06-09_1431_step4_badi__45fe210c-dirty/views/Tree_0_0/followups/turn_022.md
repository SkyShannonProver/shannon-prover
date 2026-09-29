## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
nth0: int
h0nth0: 0 <= nth0
hnth0q: nth0 < qdec
&2: {t, t0 : poly_out, ti : tag, lt : tag list}
hinv: nth0 < size UFCMA_l.lbad1{2} =>
      (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 =
      (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2 => UFCMA_li.badi{2}
hc1: UFCMA.cbad1{2} < qenc
hltq: size lt{2} <= qdec
hge: size UFCMA_l.lbad1{2} <= nth0
hlt: nth0 < size UFCMA_l.lbad1{2} + size lt{2}
t1: poly_out
tL: poly_out
------------------------------------------------------------------------
(1 = if nth0 < size UFCMA_l.lbad1{2} + size lt{2} then 1 else 0) /\
(nth0 < size UFCMA_l.lbad1{2} + size lt{2} =>
 (nth (w1, w2) (map (fun (t' : tag) => (tL, t')) lt{2})
    (nth0 - size UFCMA_l.lbad1{2})).`1 =
 (nth (w1, w2) (map (fun (t' : tag) => (tL, t')) lt{2})
    (nth0 - size UFCMA_l.lbad1{2})).`2 =>
 UFCMA_li.badi{2} ||
 tL = nth witness<:tag> lt{2} (nth0 - size UFCMA_l.lbad1{2}))
[438|check]>
```

**Last action:** `move=> &2 hinv hc1 hltq hge hlt t1 _ tL _; rewrite size_cat size_map nth_cat; h…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step4_badi_fable_l1/l1_goal_projection/chacha_step4_badi/r01/2026-06-09_1431_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
