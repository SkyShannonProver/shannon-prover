Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
`|Pr[INDR_CPA(IV_Wrap(CBC(PseudoRP)), A).main() @ &m : res] -
  Pr[INDR_CPA(Random, A).main() @ &m : res]| =
`|Pr[INDR_CPA_direct(CBC_Oracle(PRP), A).main() @ &m : res] -
  Pr[INDR_CPA_direct(CBC_Oracle(Sample), A).main() @ &m : res]|
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_cleanup/r01/2026-06-11_1700_cleanup/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_cleanup/r01/2026-06-11_1700_cleanup/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_cleanup/r01/2026-06-11_1700_cleanup/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_cleanup/r01/2026-06-11_1700_cleanup/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
