## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &2,
  DoubleQuery.bad{2} =>
  phoare[ CBC_Oracle(DoubleQuery(PRFi)).enc {&1}:
           DoubleQuery.bad = DoubleQuery.bad{2} ==>
           DoubleQuery.bad = DoubleQuery.bad{2}] = 1%r
[149|check]>
```

**Last action:** `auto; smt().` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cbc_upto_l1_rerun/l1_goal_projection/cbc_upto/r01/2026-06-05_0958_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cbc_upto_l1_rerun/l1_goal_projection/cbc_upto/r01/2026-06-05_0958_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cbc_upto_l1_rerun/l1_goal_projection/cbc_upto/r01/2026-06-05_0958_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cbc_upto_l1_rerun/l1_goal_projection/cbc_upto/r01/2026-06-05_0958_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
