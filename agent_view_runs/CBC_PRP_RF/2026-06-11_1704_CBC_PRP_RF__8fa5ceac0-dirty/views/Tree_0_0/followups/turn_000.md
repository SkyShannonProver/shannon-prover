Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
`|Pr[INDR_CPA_direct(CBC_Oracle(PRP), A).main() @ &m : res] -
  Pr[INDR_CPA_direct(CBC_Oracle(Sample), A).main() @ &m : res]| <=
`|Pr[INDR_CPA_direct(CBC_Oracle(PRFi), A).main() @ &m : res] -
  Pr[INDR_CPA_direct(CBC_Oracle(Sample), A).main() @ &m : res]| +
`|Pr[IND(PRP, PRPF_Adv(A)).main() @ &m : res] -
  Pr[IND(PRPi, PRPF_Adv(A)).main() @ &m : res]| +
`|Pr[IND(PRPi, PRPF_Adv(A)).main() @ &m : res] -
  Pr[IND(PRFi, PRPF_Adv(A)).main() @ &m : res]|
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_CBC_PRP_RF/r01/2026-06-11_1704_CBC_PRP_RF/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_CBC_PRP_RF/r01/2026-06-11_1704_CBC_PRP_RF/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_CBC_PRP_RF/r01/2026-06-11_1704_CBC_PRP_RF/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_CBC_PRP_RF/r01/2026-06-11_1704_CBC_PRP_RF/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
