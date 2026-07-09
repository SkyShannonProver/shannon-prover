Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
pre =
  arg{2} = (n{1}, p{1}) /\
  n{2} = n0 /\
  size p{1} <= max_cipher_size /\
  ! (n0 \in BNR.lenc{1}) /\
  (forall (n1 : nonce) (c : C.counter),
     (n1, c) \in ROF.m{1} => n1 \in BNR.lenc{1}) /\
  mr0 = ROin.m{1} /\ ms0 = ROout.m{1}

    ChaCha(
      CCRO(
        SplitD.RO_DOM(
                 SplitC1.RO_Pair(SplitC2.RO_Pair(ROin, ROout), SplitC1.I2.RO),
                 ROF))).enc ~ EncRnd.cc 

post =
  res{1} = res{2} /\
  size res{1} <= max_cipher_size /\
  mr0 = ROin.m{1} /\
  ms0 = ROout.m{1} /\
  forall (n : nonce) (c : C.counter),
    (n, c) \in ROF.m{1} => n \in n0 :: BNR.lenc{1}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.
