## Pure Logic — close with smt / rewrite

**Goal operators:**
- `t1`
- `t2`
- `C.ofintd`
- `notin`
- `SplitC2.I2.RO.m`
- `RO.m`
- `poly_in`
- `dpoly_in`

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
Current goal (remaining: 6)

Type variables: <none>

------------------------------------------------------------------------
forall &2,
  t1{2} <> t2{2} =>
  (t1{2}, C.ofintd 0) \notin SplitC2.I2.RO.m{2} =>
  (t2{2}, C.ofintd 0) \notin SplitC2.I2.RO.m{2} =>
  (t1{2}, C.ofintd 0) \in RO.m{2} =>
  (t2{2}, C.ofintd 0) \in RO.m{2} =>
  forall (r4L : poly_in),
    r4L \in dpoly_in =>
    forall (t4L : poly_out),
      t4L \in dpoly_out =>
      forall (r2L : poly_in),
        r2L \in dpoly_in =>
        forall (t3L : poly_out),
          t3L \in dpoly_out =>
          ((UFCMA.bad2{2} ||
            (t3L \in
             map
               (fun (c : ciphertext) =>
                  c.`4 -
                  poly1305_eval (oget RO.m{2}.[t1{2}, C.ofintd 0])
                    (topol c.`2 c.`3))
               (filter (fun (c : ciphertext) => c.`1 = t1{2}) Mem.lc{2}))) ||
           (t4L \in
            map
              (fun (c : ciphertext) =>
                 c.`4 -
                 poly1305_eval (oget RO.m{2}.[t2{2}, C.ofintd 0])
                   (topol c.`2 c.`3))
              (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) =
          ((UFCMA.bad2{2} ||
            (t4L \in
             map
               (fun (c : ciphertext) =>
                  c.`4 -
                  poly1305_eval (oget RO.m{2}.[t2{2}, C.ofintd 0])
                    (topol c.`2 c.`3))
               (filter (fun (c : ciphertext) => c.`1 = t2{2}) Mem.lc{2}))) ||
           (t3L \in
            map
              (fun (c : ciphertext) =>
                 c.`4 -
                 poly1305_eval (oget RO.m{2}.[t1{2}, C.ofintd 0])
                   (topol c.`2 c.`3))
              (filter (fun (c : ciphertext) => c.`1 = t1{2}) Mem.lc{2}))) /\
          SplitC2.I2.RO.m{2}.[t1{2}, C.ofintd 0 <- witness<:poly_out>].[t2{2}, 
            C.ofintd 0 <- witness<:poly_out>] =
          SplitC2.I2.RO.m{2}.[t2{2}, C.ofintd 0 <- witness<:poly_out>].[t1{2}, 
            C.ofintd 0 <- witness<:poly_out>]
[519|check]>
```

## Status
remaining **6** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `auto => />.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_equiv_step4_fable_l4np/l4_checked_action_surface/cc_equiv_step4_l4np/r01/2026-06-11_0754_equiv_step4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
