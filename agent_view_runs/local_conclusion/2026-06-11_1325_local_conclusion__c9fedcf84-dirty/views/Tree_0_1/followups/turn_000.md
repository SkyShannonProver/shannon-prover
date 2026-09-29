Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
`|Pr[INDR_CPA(MacThenEncrypt(PadThenEncrypt(IV_Wrap(CBC(PseudoRP))), MAC),
       RCPA_QueryBounder(A)).main() @ &m :
     res] -
  Pr[INDR_CPA(Ideal, RCPA_QueryBounder(A)).main() @ &m : res]| <=
`|Pr[IND(PRP, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main
     () @ &m : res] -
  Pr[IND(PRPi, PRPF_Adv(QueryBounder(RCPAa(RCPA_WUF_RCPA.RCPAa(MAC, A))))).main
     () @ &m : res]| +
2%r * ((q * n) ^ 2)%r * mu1 d_block witness<:block>
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_dupfix_fable_l1/l1_goal_projection/mee_local_conclusion/r01/2026-06-11_1325_local_conclusion/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
