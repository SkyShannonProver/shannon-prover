## Surgery — align or decompose the two sides

**Route:** align or decompose the two sides; don't transform the whole goal at once.

**Toolbox:**
- `case:` the divergent branch, then `rcondt`/`rcondf` to force guards.
- `conseq(:_==> ={<few equal vars>})` + `sim` on the identical prefix.
- `wp` (incl. `wp -N -N`) to absorb tails before `call`/`sim`.

**Yours:** which guard to `case`/`rcond`, the coupling, the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, ns, ns1, ns2, l1, l2, l, l0 : nonce list}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}

pre =
  i{2} = 0 /\
  l1{1} = ns1{1} /\
  l2{1} = ns2{1} /\
  l{1} = l1{1} /\
  (ns1{1} = ns1{2} /\
   ns2{1} = ns2{2} /\
   UF.forged{1} = UF.forged{2} /\
   UFCMA.bad2{1} = UFCMA.bad2{2} /\
   UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ ROout.m{1} = ROout.m{2}) /\
  uniq ns2{2} /\
  (forall (n0 : nonce), n0 \in ns1{2} => (n0, C.ofintd 0) \in ROout.m{2}) /\
  forall (n0 : nonce), n0 \in ns2{2} => (n0, C.ofintd 0) \notin ROout.m{2}


post =
  (((UF.forged{1} = UF.forged{2} /\
     UFCMA.bad2{1} = UFCMA.bad2{2} /\
     UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
     UFCMA.log{1} = UFCMA.log{2} /\
     Mem.lc{1} = Mem.lc{2} /\
     RO.m{1} = RO.m{2} /\
     ROout.m{1} = ROout.m{2} /\ ns1{1} = ns1{2} /\ ns2{1} = ns2{2}) /\
    l2{1} = ns2{2} /\
    l{1} = drop i{2} ns1{2} /\
    0 <= i{2} /\
    uniq ns2{2} /\
    (forall (n0 : nonce), n0 \in ns1{2} => (n0, C.ofintd 0) \in ROout.m{2}) /\
    forall (n0 : nonce), n0 \in ns2{2} => (n0, C.ofintd 0) \notin ROout.m{2}) /\
   (l{1} <> [] <=> i{2} < size ns1{2})) /\
  forall (forged_L bad2_L : bool) (cbad2_L : int) (m_L : (nonce * C.counter,
    poly_in) fmap) (m_L0 : (nonce * C.counter, poly_out) fmap)
    (l_L : nonce list) (forged_R : bool) (m_R : (nonce * C.counter,
    poly_in) fmap) (i_R : int),
    l_L = [] =>
    ! i_R < size ns1{2} =>
    ((forged_L = forged_R /\
      bad2_L = UFCMA.bad2{2} /\
      cbad2_L = UFCMA.cbad2{2} /\
      UFCMA.log{1} = UFCMA.log{2} /\
      Mem.lc{1} = Mem.lc{2} /\
      m_L = m_R /\ m_L0 = ROout.m{2} /\ ns1{1} = ns1{2} /\ ns2{1} = ns2{2}) /\
     l2{1} = ns2{2} /\
     l_L = drop i_R ns1{2} /\
     0 <= i_R /\
     uniq ns2{2} /\
     (forall (n0 : nonce), n0 \in ns1{2} => (n0, C.ofintd 0) \in ROout.m{2}) /\
     forall (n0 : nonce), n0 \in ns2{2} => (n0, C.ofintd 0) \notin ROout.m{2}) =>
    (((forged_L = forged_R /\
       bad2_L = UFCMA.bad2{2} /\
       cbad2_L = UFCMA.cbad2{2} /\
       UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ m_L = m_R) /\
      l2{1} = drop 0 ns2{2} /\
      0 <= 0 /\
      uniq l2{1} /\
      forall (n0 : nonce), n0 \in l2{1} => (n0, C.ofintd 0) \notin m_L0) /\
     (l2{1} <> [] <=> 0 < size ns2{2})) /\
    forall (forged_L0 bad2_L0 : bool) (cbad2_L0 : int) (m_L1 : (nonce *
      C.counter, poly_in) fmap) (m_L2 : (nonce * C.counter, poly_out) fmap)
      (l0_L : nonce list) (bad2_R : bool) (cbad2_R : int) (m_R0 : (nonce *
      C.counter, poly_in) fmap) (i_R0 : int),
      l0_L = [] =>
      ! i_R0 < size ns2{2} =>
      ((forged_L0 = forged_R /\
        bad2_L0 = bad2_R /\
        cbad2_L0 = cbad2_R /\
        UFCMA.log{1} = UFCMA.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ m_L1 = m_R0) /\
       l0_L = drop i_R0 ns2{2} /\
       0 <= i_R0 /\
       uniq l0_L /\
       forall (n0 : nonce), n0 \in l0_L => (n0, C.ofintd 0) \notin m_L2) =>
      forged_L0 = forged_R /\ bad2_L0 = bad2_R
[570|check]>
```

## Status
remaining **2** · phase `relational_program` / `procedure_body`

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

**Last action:** `by inline *; auto => />; smt(drop_nth head_cons drop_drop size_drop size_eq0 ge…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0_r1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0_r1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0_r1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0_r1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
