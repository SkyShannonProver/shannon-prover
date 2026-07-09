## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
&1 (left ) : {k : key, n : nonce, c2 : bytes, a : associated_data,
             p2 : message, nap : nonce * associated_data * message, t : tag,
             p, p0, p1 : plaintext, c, c0, c1 : ciphertext}
&2 (right) : {n : nonce, c1 : bytes, t : poly_out, a : associated_data,
             p1 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext}

pre =
  (n0 = n{2} /\ mr0 = SplitC2.I1.RO.m{1} /\ ms0 = SplitC2.I2.RO.m{1}) /\
  p0{2} = p{2} /\
  nap{2} = p0{2} /\
  (n{2}, a{2}, p1{2}) = nap{2} /\
  p0{1} = p{1} /\
  p1{1} = p0{1} /\
  k{1} = Mem.k{1} /\
  nap{1} = p1{1} /\
  (n{1}, a{1}, p2{1}) = nap{1} /\
  (c{2} = witness /\
   c{1} = witness /\
   p{1} = p{2} /\
   inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.
     lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\
   forall (n1 : nonce) (c3 : C.counter),
     (n1, c3) \in SplitD.ROF.RO.m{1} => n1 \in BNR.lenc{1}) /\
  check_plaintext BNR.lenc{1} p{1}


post =
  ((n{2}, p1{2}) = ((k{1}, n{1}, p2{1}).`2, (k{1}, n{1}, p2{1}).`3) /\
   (n{2}, p1{2}).`1 = n0 /\
   size (k{1}, n{1}, p2{1}).`3 <= max_cipher_size /\
   ! (n0 \in BNR.lenc{1}) /\
   (forall (n1 : nonce) (c3 : C.counter),
      (n1, c3) \in ROF.m{1} => n1 \in BNR.lenc{1}) /\
   mr0 = ROin.m{1} /\ ms0 = ROout.m{1}) &&
  forall (result_L result_R : bytes) (m_L : (nonce * C.counter,
    poly_in) fmap) (m_L0 : (nonce * C.counter, poly_out) fmap)
    (m_L1 : (nonce * C.counter, block) fmap),
    (result_L = result_R /\
     size result_L <= max_cipher_size /\
     mr0 = m_L /\
     ms0 = m_L0 /\
     forall (n1 : nonce) (c3 : C.counter),
       (n1, c3) \in m_L1 => n1 \in n0 :: BNR.lenc{1}) =>
    result_L = result_R /\
    n{1} = n{2} /\
    a{1} = a{2} /\
    p0{1} = p0{2} /\
    p{1}.`1 = n{1} /\
    p{2}.`1 = n{2} /\
    Mem.log{1} = Mem.log{2} /\
    Mem.lc{1} = Mem.lc{2} /\
    BNR.lenc{1} = BNR.lenc{2} /\
    BNR.ndec{1} = BNR.ndec{2} /\
    ! (n{1} \in BNR.lenc{1}) /\
    (forall (nn : nonce) (ci : C.counter),
       (nn, ci) \in m_L => nn \in BNR.lenc{1}) /\
    (forall (nn : nonce) (ci : C.counter),
       (nn, ci) \in m_L0 => nn \in BNR.lenc{1}) /\
    forall (nn : nonce) (ci : C.counter),
      (nn, ci) \in m_L1 => nn \in n{1} :: BNR.lenc{1}
[377|check]>
```

## Status
remaining **5** · phase `relational_program` / `prhl_module`

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

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `commit_tactic` `exlim n{2}, SplitC2.I1.RO.m{1}, SplitC2.I2.RO.m{1} => n0 mr0 ms0; call (equ_cc n0 mr0 ms0…`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":50,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"exlim n{2}, SplitC2.I1.RO.m{1}, SplitC2.I2.RO.m{1} => n0 mr0 ms0; call (equ_cc n0 mr0 ms0)."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"391 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
