## Pure Logic — close with smt / rewrite

**Goal operators:**
- `UFCMA.bad2`
- `map`
- `ciphertext`
- `poly1305_eval`
- `oget`
- `RO.m`
- `t1`
- `C.ofintd`

**Visible hypotheses:**
- `ne: t1{2} <> t2{2}`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Memory translation:**
- memories in play: `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&2: {t1, t2, n, n0 : nonce, x, x0, x1, x2, x3, x4 : nonce * C.counter,
    r, r0, r1, r2, r3, r4 : poly_in, t, t0, t3, y, t4, y0 : poly_out,
    lt, lt0 : tag list}
ne: t1{2} <> t2{2}
h1: (t1{2}, C.ofintd 0) \notin SplitC2.I2.RO.m{2}
h2: (t2{2}, C.ofintd 0) \notin SplitC2.I2.RO.m{2}
h3: (t1{2}, C.ofintd 0) \notin RO.m{2}
h4: (t2{2}, C.ofintd 0) \notin RO.m{2}
r4L: poly_in
t4L: poly_out
r2L: poly_in
t3L: poly_out
------------------------------------------------------------------------
((UFCMA.bad2{2} ||
  (t3L \in
   map
     (fun (c : ciphertext) =>
        c.`4 -
        poly1305_eval
          (oget RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t1{2}, C.ofintd 0])
          (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = t1{2}) Mem.lc{2}))) ||
 (t4L \in
  map
    (fun (c : ciphertext) =>
       c.`4 -
       poly1305_eval
         (oget
            RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r2L].[t2{2}, 
            C.ofintd 0]) (topol c.`2 c.`3))
    (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) =
((UFCMA.bad2{2} ||
  (t4L \in
   map
     (fun (c : ciphertext) =>
        c.`4 -
        poly1305_eval
          (oget RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t2{2}, C.ofintd 0])
          (topol c.`2 c.`3))
     (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) ||
 (t3L \in
  map
    (fun (c : ciphertext) =>
       c.`4 -
       poly1305_eval
         (oget
            RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r2L].[t1{2}, 
            C.ofintd 0]) (topol c.`2 c.`3))
    (filter (fun (c : ciphertext) => c.`1 = t1{2}) Mem.lc{2}))) /\
RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r2L] =
RO.m{2}.[t2{2}, C.ofintd 0 <- r4L].[t1{2}, C.ofintd 0 <- r2L] /\
SplitC2.I2.RO.m{2}.[t1{2}, C.ofintd 0 <- witness<:poly_out>].[t2{2}, 
  C.ofintd 0 <- witness<:poly_out>] =
SplitC2.I2.RO.m{2}.[t2{2}, C.ofintd 0 <- witness<:poly_out>].[t1{2}, 
  C.ofintd 0 <- witness<:poly_out>]
[540|check]>
```

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `have ->: RO.m{2}.[t1{2}, C.ofintd 0 <- r2L].[t2{2}, C.ofintd 0 <- r4L] = RO.m{2…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
