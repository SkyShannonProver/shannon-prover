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
  Pr[INDR_CPA(Ideal, RCPA_QueryBounder(A)).main() @ &m : res]| =
`|Pr[SKEa.RCPA.INDR_CPA(PadThenEncrypt(IV_Wrap(CBC(PseudoRP))),
                 RCPA_WUF_RCPA.RCPAa(MAC, RCPA_QueryBounder(A))).main
     () @ &m : res] -
  Pr[SKEa.RCPA.INDR_CPA(SKEa.RCPA.Ideal,
                 RCPA_WUF_RCPA.RCPAa(MAC, RCPA_QueryBounder(A))).main
     () @ &m : res]|
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_MtE_security/r01/2026-06-11_1818_MtE_security/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_MtE_security/r01/2026-06-11_1818_MtE_security/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_MtE_security/r01/2026-06-11_1818_MtE_security/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_sweep_l1_v2/l1_goal_projection/mee_MtE_security/r01/2026-06-11_1818_MtE_security/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
