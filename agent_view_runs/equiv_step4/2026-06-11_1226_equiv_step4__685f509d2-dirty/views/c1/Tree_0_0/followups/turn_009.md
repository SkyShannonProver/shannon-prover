## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: n <- head witness<:nonce> l
- frontier: both sides at `r <@ RO.get(n, C.ofintd 0)`
- frontier: left side only at `r <@ RO.get(n, C.ofintd 0)`
- frontier: left side only at `t <@ UFCMA(RO).set_bad2(map (fun (c : ciphertext) => c.`4 - `
- frontier: left side only at `if ((n, C.ofintd 0) \in ROout.m) {`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {b : bool, n : nonce, ns, ns1, ns2, l1, l2, l, l0 : nonce list,
             r : poly_in, t : poly_out}
&2 (right) : {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
             r : poly_in, t : poly_out}

pre =
  ((UF.forged{1} = UF.forged{2} /\
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
  l{1} <> [] /\ i{2} < size ns1{2}

n <- head witness<:nonce> l                           (1--)  n <- nth witness<:nonce> ns1 i
if ((n, C.ofintd 0) \in ROout.m) {                    (2--)  r <@ RO.get(n, C.ofintd 0)    
  r <@ RO.get(n, C.ofintd 0)                          (2.1)                                
  UF.forged <-                                        (2.2)                                
    UF.forged ||                                      (   )                                
    test_poly_in n Mem.lc r                           (   )                                
      (oget UFCMA.log.[n])                            (   )                                
} else {                                              (2--)                                
  r <@ RO.get(n, C.ofintd 0)                          (2?1)                                
  t <@                                                (2?2)                                
    UFCMA(RO).set_bad2(map                            (   )                                
                         (fun (c : ciphertext) =>     (   )                                
                            c.`4 -                    (   )                                
                            poly1305_eval             (   )                                
                              r                       (   )                                
                              (topol c.`2             (   )                                
                                c.`3))                (   )                                
                         (filter                      (   )                                
                            (fun (c : ciphertext) =>  (   )                                
                               c.`1 = n)              (   )                                
                            Mem.lc))                  (   )                                
  ROout.set((n, C.ofintd 0),                          (2?3)                                
    witness<:poly_out>)                               (   )                                
}                                                     (2--)                                
l <- drop 1 l                                         (3--)  UF.forged <-                  
                                                      (  -)    UF.forged ||                
                                                      (  -)    test_poly_in n Mem.lc r     
                                                      (  -)      (oget UFCMA.log.[n])      
                                                      (4--)  i <- i + 1                    

post =
  ((UF.forged{1} = UF.forged{2} /\
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
  (l{1} <> [] <=> i{2} < size ns1{2})
[567|check]>
```

## Status
remaining **3** · phase `relational_program` / `call_site`

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

**Last action:** `inline{1} Orcl.f.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
