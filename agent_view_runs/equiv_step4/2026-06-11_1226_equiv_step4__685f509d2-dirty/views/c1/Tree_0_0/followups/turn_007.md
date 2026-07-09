## Surgery — align or decompose the two sides

**Where:**
- call/proc statement before the frontier (positions 1–2) — this is a procedure call, step into it with `inline`/`call` (NOT `sp`/`wp`, which cannot cross a call): Orcl.f(head witness<:nonce> l)
- frontier: right side only at `r <@ RO.get(n, C.ofintd 0)`

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
&1 (left ) : {b : bool, ns, ns1, ns2, l1, l2, l, l0 : nonce list}
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

Orcl.f(head witness<:nonce> l)  (1)  n <- nth witness<:nonce> ns1 i
l <- drop 1 l                   (2)  r <@ RO.get(n, C.ofintd 0)    
                                (3)  UF.forged <-                  
                                ( )    UF.forged ||                
                                ( )    test_poly_in n Mem.lc r     
                                ( )      (oget UFCMA.log.[n])      
                                (4)  i <- i + 1                    

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
[566|check]>
```

## Status
remaining **3** · phase `relational_program` / `call_site`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `sp 3 1; wp; while (={UF.forged, UFCMA.bad2, UFCMA.cbad2, UFCMA.log, Mem.lc, RO.…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
