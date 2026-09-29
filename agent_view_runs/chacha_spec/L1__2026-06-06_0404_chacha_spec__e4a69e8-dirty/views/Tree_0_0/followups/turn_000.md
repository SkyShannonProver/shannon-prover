Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

k0: key
n0: nonce
p0: message
gs0: globS
------------------------------------------------------------------------
pre = k = k0 /\ n = n0 /\ p = p0 /\ OCC.gs = gs0

    ChaCha(OCC(I)).enc 
    [=] 1%r

post = res = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_ablation/l1_goal_projection/d0_chacha_spec/r01/2026-06-06_0404_chacha_spec/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_ablation/l1_goal_projection/d0_chacha_spec/r01/2026-06-06_0404_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_ablation/l1_goal_projection/d0_chacha_spec/r01/2026-06-06_0404_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_ablation/l1_goal_projection/d0_chacha_spec/r01/2026-06-06_0404_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
