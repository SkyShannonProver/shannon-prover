Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

------------------------------------------------------------------------
pre =
  (glob A){1} = (glob A){2} /\
  (glob I){1} = (glob I){2} /\ OCC.gs{1} = OCC.gs{2} /\ arg{1} = arg{2}

    A(GenChaChaPoly(OCC(I))).main ~ A(OChaChaPoly(I)).main 

post =
  res{1} = res{2} /\
  (glob A){1} = (glob A){2} /\
  (glob I){1} = (glob I){2} /\ OCC.gs{1} = OCC.gs{2}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/CCP_OCCP/r01/2026-06-08_2013_CCP_OCCP/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
