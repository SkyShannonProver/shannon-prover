## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** by move=> &1 &2 H; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.lc{2} ROout.m{2} ns1{2} ns2{2}; smt(filter_uniq undup_uniq mem_filter). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** the goal is a pure logical residual (NO program frontier) — discharge it with the right lemmas / rewrites; `lookup_symbol` any operator for its definition and lemmas

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `apply <order/pure lemma>` — close by the matching logical/order lemma
- `case (<cond>)` — split a disjunction / membership in the goal

**Evidence:**
- membership source shapes: filter_membership, map_membership
- membership fact: ns1{2} = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m{2}) ns{2} /\ ns2{2} = filter (fun (n0 : nonce) => (...

**Available local work:**
- pure tail obligation families: `constructor_projection`, `quantified_residual_logic`
- membership decomposition sources: `map_membership`, `filter_membership`
- existential witness sources: `membership_member`, `membership_member`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Rewind targets:**
- `Before latest branch-local tactic #175` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_175_2a67223b02b08df9"}}`
- `After seq opened / before branch work #171` → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_171_2a67223b02b08df9"}}`
- `Before latest branch-local tactic #175` — latest branch-local step inside the current seq scope → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_175_2a67223b02b08df9"}}`
- `After seq opened / before branch work #171` — seq-local branch boundary; selecting it keeps the seq cut and removes branch-local work after it → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_171_2a67223b02b08df9"}}`
- `Before seq cut #170` — seq-cut boundary; selecting it restores the proof state before this cut was committed → submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_170_2a67223b02b08df9"}}`

**Yours:** the lemmas for `smt`, the rewrite chain, the apply target, the case condition — `lookup_symbol` any operator. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint`. (rewind_targets above name the exact points).

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
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
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

**Last action:** `by move=> &1 &2 H; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2…` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `transitivity{1} { Iter(Orcl).iters(ns1, ns2); } (={ns1, ns2, UF.forged, UFCMA.b…` → accepted
- commit `by move=> &1 &2 />; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{…` → REJECTED: [error] not an existential

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
