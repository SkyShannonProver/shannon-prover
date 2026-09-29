## 🎯 Current Goal
```
Current goal

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
&1 (left ) : {i : int, c : byte list, k, k0 : key, n, n0 : nonce,
             c0 : C.counter, x, x0, x1, x2, x3, x4, x5 : nonce * C.counter,
             r10, r4 : poly_in, r20, r5 : poly_out, r1 : poly,
             r2, r3 : extra_block, z, result, r, r0 : block, p : message}
&2 (right) : {i : int, c : byte list, n : nonce, z : block, p : message}

pre =
  c{1} = c{2} /\
  size p{1} = size p{2} /\
  size c{1} + size p{1} <= max_cipher_size /\
  1 <= i{1} /\
  i{1} - 1 + (size p{1} + block_size - 1) %/ block_size <= C.max_counter /\
  n{1} = n0 /\
  mr0 = ROin.m{1} /\
  ms0 = ROout.m{1} /\
  (forall (nn : nonce) (cc : C.counter),
     (nn, cc) \in ROF.m{1} => nn \in n0 :: BNR.lenc{1}) /\
  forall (cc : C.counter), (n0, cc) \in ROF.m{1} => C.toint cc < i{1}


post =
  ((c{1} = c{2} /\
    size p{1} = size p{2} /\
    size c{1} + size p{1} <= max_cipher_size /\
    1 <= i{1} /\
    i{1} - 1 + (size p{1} + block_size - 1) %/ block_size <= C.max_counter /\
    n{1} = n0 /\
    mr0 = ROin.m{1} /\
    ms0 = ROout.m{1} /\
    (forall (nn : nonce) (cc : C.counter),
       (nn, cc) \in ROF.m{1} => nn \in n0 :: BNR.lenc{1}) /\
    forall (cc : C.counter), (n0, cc) \in ROF.m{1} => C.toint cc < i{1}) /\
   (p{1} = [] <=> p{2} = [])) /\
  forall (m_L : (nonce * C.counter, poly_in) fmap) (m_L0 : (nonce *
    C.counter, poly_out) fmap) (m_L1 : (nonce * C.counter, block) fmap)
    (c_L : byte list) (i_L : int) (p_L : message) (c_R : byte list)
    (p_R : message),
    p_L = [] =>
    p_R = [] =>
    (c_L = c_R /\
     size p_L = size p_R /\
     size c_L + size p_L <= max_cipher_size /\
     1 <= i_L /\
     i_L - 1 + (size p_L + block_size - 1) %/ block_size <= C.max_counter /\
     n{1} = n0 /\
     mr0 = m_L /\
     ms0 = m_L0 /\
     (forall (nn : nonce) (cc : C.counter),
        (nn, cc) \in m_L1 => nn \in n0 :: BNR.lenc{1}) /\
     forall (cc : C.counter), (n0, cc) \in m_L1 => C.toint cc < i_L) =>
    c_L = c_R /\
    size c_L <= max_cipher_size /\
    mr0 = m_L /\
    ms0 = m_L0 /\
    forall (n1 : nonce) (c1 : C.counter),
      (n1, c1) \in m_L1 => n1 \in n0 :: BNR.lenc{1}
[388|check]>
```

**Last action:** `smt(mem_set C.ofintdK lez_divRL leq_div2r divz_small gt0_block_size size_ge0 si…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
