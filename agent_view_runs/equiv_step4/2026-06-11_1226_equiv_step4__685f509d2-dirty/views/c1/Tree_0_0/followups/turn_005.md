## Pure Logic — close with smt / rewrite

**Goal operators:**
- `poly_in`
- `dpoly_in`
- `nth`
- `witness`
- `nonce`
- `ns2`
- `C.ofintd`
- `notin`

**Visible hypotheses:**
- `hge: 0 <= i{2}`
- `hne: drop i{2} ns2{2} <> []`
- `hlt: i{2} < size ns2{2}`
- `hhd: head witness<:nonce> (drop i{2} ns2{2}) =`

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
Current goal (remaining: 3)

Type variables: <none>

&1: {b : bool, n : nonce, ns, ns1, ns2, l1, l2, l, l0 : nonce list,
    x, x0 : nonce * C.counter, r, r0 : poly_in, t, t0, y : poly_out,
    lt : tag list}
&2: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
    x : nonce * C.counter, r, r0 : poly_in, t, t0 : poly_out, lt : tag list}
hge: 0 <= i{2}
huniq: uniq (drop i{2} ns2{2})
hout: forall (n0 : nonce),
        n0 \in drop i{2} ns2{2} => (n0, C.ofintd 0) \notin SplitC2.I2.RO.m{1}
hne: drop i{2} ns2{2} <> []
hlt: i{2} < size ns2{2}
hhd: head witness<:nonce> (drop i{2} ns2{2}) =
     nth witness<:nonce> ns2{2} i{2}
------------------------------------------------------------------------
forall (r0L : poly_in),
  r0L \in dpoly_in =>
  ((nth witness<:nonce> ns2{2} i{2}, C.ofintd 0) \notin RO.m{2} =>
   ((nth witness<:nonce> ns2{2} i{2}, C.ofintd 0) \notin RO.m{2} =>
    forall (t0L : poly_out),
      t0L \in dpoly_out =>
      (drop 1 (drop i{2} ns2{2}) = drop (i{2} + 1) ns2{2} /\
       0 <= i{2} + 1 /\
       uniq (drop 1 (drop i{2} ns2{2})) /\
       forall (n0 : nonce),
         n0 \in drop 1 (drop i{2} ns2{2}) =>
         (n0, C.ofintd 0) \notin
         SplitC2.I2.RO.m{1}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <-
           witness<:poly_out>]) /\
      (drop 1 (drop i{2} ns2{2}) <> [] => i{2} + 1 < size ns2{2}) /\
      (i{2} + 1 < size ns2{2} => drop 1 (drop i{2} ns2{2}) <> [])) /\
   ((nth witness<:nonce> ns2{2} i{2}, C.ofintd 0) \in RO.m{2} =>
    forall (t0L : poly_out),
      t0L \in dpoly_out =>
      (((UFCMA.bad2{2} ||
         (t0L \in
          map
            (fun (c : ciphertext) =>
               c.`4 -
               poly1305_eval
                 (oget RO.m{2}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0])
                 (topol c.`2 c.`3))
            (filter
               (fun (c : ciphertext) =>
                  c.`1 = nth witness<:nonce> ns2{2} i{2}) Mem.lc{2}))) =
        (UFCMA.bad2{2} ||
         (t0L \in
          map
            (fun (c : ciphertext) =>
               c.`4 -
               poly1305_eval
                 (oget
                    RO.m{2}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <-
                      r0L].[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0])
                 (topol c.`2 c.`3))
            (filter
               (fun (c : ciphertext) =>
                  c.`1 = nth witness<:nonce> ns2{2} i{2}) Mem.lc{2}))) /\
        RO.m{2} =
        RO.m{2}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <- r0L]) /\
       drop 1 (drop i{2} ns2{2}) = drop (i{2} + 1) ns2{2} /\
       0 <= i{2} + 1 /\
       uniq (drop 1 (drop i{2} ns2{2})) /\
       forall (n0 : nonce),
         n0 \in drop 1 (drop i{2} ns2{2}) =>
         (n0, C.ofintd 0) \notin
         SplitC2.I2.RO.m{1}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <-
           witness<:poly_out>]) /\
      (drop 1 (drop i{2} ns2{2}) <> [] => i{2} + 1 < size ns2{2}) /\
      (i{2} + 1 < size ns2{2} => drop 1 (drop i{2} ns2{2}) <> []))) /\
  ((nth witness<:nonce> ns2{2} i{2}, C.ofintd 0) \in RO.m{2} =>
   ((nth witness<:nonce> ns2{2} i{2}, C.ofintd 0) \notin RO.m{2} =>
    forall (t0L : poly_out),
      t0L \in dpoly_out =>
      (((UFCMA.bad2{2} ||
         (t0L \in
          map
            (fun (c : ciphertext) =>
               c.`4 -
               poly1305_eval
                 (oget
                    RO.m{2}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <-
                      r0L].[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0])
                 (topol c.`2 c.`3))
            (filter
               (fun (c : ciphertext) =>
                  c.`1 = nth witness<:nonce> ns2{2} i{2}) Mem.lc{2}))) =
        (UFCMA.bad2{2} ||
         (t0L \in
          map
            (fun (c : ciphertext) =>
               c.`4 -
               poly1305_eval
                 (oget RO.m{2}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0])
                 (topol c.`2 c.`3))
            (filter
               (fun (c : ciphertext) =>
                  c.`1 = nth witness<:nonce> ns2{2} i{2}) Mem.lc{2}))) /\
        RO.m{2}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <- r0L] =
        RO.m{2}) /\
       drop 1 (drop i{2} ns2{2}) = drop (i{2} + 1) ns2{2} /\
       0 <= i{2} + 1 /\
       uniq (drop 1 (drop i{2} ns2{2})) /\
       forall (n0 : nonce),
         n0 \in drop 1 (drop i{2} ns2{2}) =>
         (n0, C.ofintd 0) \notin
         SplitC2.I2.RO.m{1}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <-
           witness<:poly_out>]) /\
      (drop 1 (drop i{2} ns2{2}) <> [] => i{2} + 1 < size ns2{2}) /\
      (i{2} + 1 < size ns2{2} => drop 1 (drop i{2} ns2{2}) <> [])) /\
   ((nth witness<:nonce> ns2{2} i{2}, C.ofintd 0) \in RO.m{2} =>
    forall (t0L : poly_out),
      t0L \in dpoly_out =>
      (drop 1 (drop i{2} ns2{2}) = drop (i{2} + 1) ns2{2} /\
       0 <= i{2} + 1 /\
       uniq (drop 1 (drop i{2} ns2{2})) /\
       forall (n0 : nonce),
         n0 \in drop 1 (drop i{2} ns2{2}) =>
         (n0, C.ofintd 0) \notin
         SplitC2.I2.RO.m{1}.[nth witness<:nonce> ns2{2} i{2}, C.ofintd 0 <-
           witness<:poly_out>]) /\
      (drop 1 (drop i{2} ns2{2}) <> [] => i{2} + 1 < size ns2{2}) /\
      (i{2} + 1 < size ns2{2} => drop 1 (drop i{2} ns2{2}) <> [])))
[564|check]>
```

## Status
remaining **3** · phase `relational_program` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `rewrite hhd /=.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_1226_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
