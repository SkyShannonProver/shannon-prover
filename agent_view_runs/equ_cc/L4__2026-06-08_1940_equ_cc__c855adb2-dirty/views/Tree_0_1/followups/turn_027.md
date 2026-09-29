## 🎯 Current Goal
```
Current goal

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
&1 (left ) : {i : int, c : byte list, k : key, n : nonce, z : block,
             p : message}
&2 (right) : {i : int, c : byte list, n : nonce, z : block, p : message}

pre =
  exists (p_R : message),
    p{2} = map (fun (_ : byte) => witness<:byte>) p_R /\
    c{2} = [] /\
    i{2} = 1 /\
    c{1} = [] /\
    i{1} = 1 /\
    (n{2}, p_R) = ((k{1}, n{1}, p{1}).`2, (k{1}, n{1}, p{1}).`3) /\
    (n{2}, p_R).`1 = n0 /\
    size (k{1}, n{1}, p{1}).`3 <= max_cipher_size /\
    ! (n0 \in BNR.lenc{1}) /\
    (forall (n1 : nonce) (c0 : C.counter),
       (n1, c0) \in ROF.m{1} => n1 \in BNR.lenc{1}) /\
    mr0 = ROin.m{1} /\ ms0 = ROout.m{1}


post =
  ((c{1} = c{2} /\
    i{1} = i{2} /\
    n{1} = n0 /\
    size p{1} = size p{2} /\
    1 <= i{1} /\
    size c{1} + size p{1} <= max_cipher_size /\
    (p{1} = [] \/ size c{1} = (i{1} - 1) * block_size) /\
    mr0 = ROin.m{1} /\
    ms0 = ROout.m{1} /\
    (forall (c0 : C.counter), (n0, c0) \in ROF.m{1} => C.toint c0 < i{1}) /\
    forall (n1 : nonce) (c0 : C.counter),
      (n1, c0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\
   (p{1} = [] <=> p{2} = [])) /\
  forall (m_L : (nonce * C.counter, poly_in) fmap) (m_L0 : (nonce *
    C.counter, poly_out) fmap) (m_L1 : (nonce * C.counter, block) fmap)
    (c_L : byte list) (i_L : int) (p_L : message) (c_R : byte list)
    (i_R : int) (p_R : message),
    p_L = [] =>
    p_R = [] =>
    (c_L = c_R /\
     i_L = i_R /\
     n{1} = n0 /\
     size p_L = size p_R /\
     1 <= i_L /\
     size c_L + size p_L <= max_cipher_size /\
     (p_L = [] \/ size c_L = (i_L - 1) * block_size) /\
     mr0 = m_L /\
     ms0 = m_L0 /\
     (forall (c0 : C.counter), (n0, c0) \in m_L1 => C.toint c0 < i_L) /\
     forall (n1 : nonce) (c0 : C.counter),
       (n1, c0) \in m_L1 => n1 \in n0 :: BNR.lenc{1}) =>
    c_L = c_R /\
    size c_L <= max_cipher_size /\
    mr0 = m_L /\
    ms0 = m_L0 /\
    forall (n1 : nonce) (c0 : C.counter),
      (n1, c0) \in m_L1 => n1 \in n0 :: BNR.lenc{1}
[376|check]>
```

## Status
remaining **1** · phase `relational_program` / `prhl_module`

### Need more? submit one of these read-only requests
- No fresh recommendation is available for an equivalence goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "equiv_bridge_lemmas"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `smt(size_drop size_eq0 size_ge0 ge0_block_size gt0_block_size).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
