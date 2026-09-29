## Pure Logic — close with smt / rewrite

**Goal operators:**
- `ns`
- `undup`
- `map`
- `ciphertext`
- `Mem.lc`
- `ns1`
- `filter`
- `nonce`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

------------------------------------------------------------------------
forall &1 &2,
  ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
  ns1{2} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m{2}) ns{2} /\
  ns2{2} =
  filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m{2}) ns{2} /\
  ns{1} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{1}) /\
  ns1{1} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m{1}) ns{1} /\
  ns2{1} =
  filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m{1}) ns{1} /\
  (UF.forged{2} = false /\
   UF.forged{1} = false /\
   UFCMA.bad2{1} = UFCMA.bad2{2} /\
   UFCMA.cbad2{1} = UFCMA.cbad2{2} /\
   UFCMA.log{1} = UFCMA.log{2} /\
   Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\ ROout.m{1} = ROout.m{2}) /\
  size Mem.lc{1} <= qdec =>
  exists (forged bad2 : bool) (cbad2 : int) (log : (nonce, associated_data *
    message * tag) fmap) (m : (nonce * C.counter, poly_in) fmap)
    (lc : ciphertext list) (m0 : (nonce * C.counter, poly_out) fmap) (ns1_0
    ns2_0 : nonce list),
    (ns1{1} = ns1_0 /\
     ns2{1} = ns2_0 /\
     UF.forged{1} = forged /\
     UFCMA.bad2{1} = bad2 /\
     UFCMA.cbad2{1} = cbad2 /\
     UFCMA.log{1} = log /\ Mem.lc{1} = lc /\ RO.m{1} = m /\ ROout.m{1} = m0) /\
    (ns1_0 = ns1{2} /\
     ns2_0 = ns2{2} /\
     forged = UF.forged{2} /\
     bad2 = UFCMA.bad2{2} /\
     cbad2 = UFCMA.cbad2{2} /\
     log = UFCMA.log{2} /\ lc = Mem.lc{2} /\ m = RO.m{2} /\ m0 = ROout.m{2}) /\
    uniq ns2{2} /\
    (forall (n0 : nonce), n0 \in ns1{2} => (n0, C.ofintd 0) \in ROout.m{2}) /\
    forall (n0 : nonce), n0 \in ns2{2} => (n0, C.ofintd 0) \notin ROout.m{2}
[552|check]>
```

## Status
remaining **5** · phase `relational_program` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
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

**Last action:** `transitivity{1} { Iter(Orcl).iters(ns1, ns2); } (={ns1, ns2, UF.forged, UFCMA.b…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
