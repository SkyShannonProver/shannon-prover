Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

_mk: mK
_ek: block
_c: block list
------------------------------------------------------------------------
pre = key = (_ek, _mk) /\ c = _c

    MEE(PRPc.PseudoRP, MAC).dec 
    [=] 1%r

post =
  res =
  mee_dec AESi hmac_sha256 _ek _mk (head witness<:block> _c) (behead _c)
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/mee_samples_fable_l1/l1_goal_projection/mee_decrypt_correct/r01/2026-06-10_2153_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/mee_samples_fable_l1/l1_goal_projection/mee_decrypt_correct/r01/2026-06-10_2153_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/mee_samples_fable_l1/l1_goal_projection/mee_decrypt_correct/r01/2026-06-10_2153_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/mee_samples_fable_l1/l1_goal_projection/mee_decrypt_correct/r01/2026-06-10_2153_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
