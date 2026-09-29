Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

------------------------------------------------------------------------
pre = (glob A){1} = (glob A){2}

    UFCMA(RO).distinguish ~ UFCMA3(RO).distinguish 

post =
  UFCMA.bad2{1} = UFCMA.bad2{2} /\
  res{1} = UF.forged{2} /\ res{2} = (UF.forged{2} \/ UFCMA.bad2{2})
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chacha_steps_a2_fable_l1/l1_goal_projection/cc_equiv_step4/r01/2026-06-10_2349_equiv_step4/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
