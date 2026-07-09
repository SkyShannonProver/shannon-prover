## 🎯 Current Goal
```
Current goal

Type variables: <none>

------------------------------------------------------------------------
&1 (left ) : {k, k0 : key, n, n0 : nonce, c0 : C.counter, r : poly_in,
             s : poly_out, b : block, a : associated_data, c : message}
&2 (right) : {n : nonce, x : nonce * C.counter, r : poly_in, s : poly_out,
             b : block, a : associated_data, c : message}

pre =
  OCC.gs{1} = RO.m{2} /\
  (k{1}, n{1}, a{1}, c{1}).`2 = (n{2}, a{2}, c{2}).`1 /\
  (k{1}, n{1}, a{1}, c{1}).`3 = (n{2}, a{2}, c{2}).`2 /\
  (k{1}, n{1}, a{1}, c{1}).`4 = (n{2}, a{2}, c{2}).`3

k0 <- k                    (1)  x <- (n, C.ofintd 0)     
n0 <- n                    (2)  b <- oget RO.m.[x]       
c0 <- C.ofintd 0           (3)  (r, s) <- mk_rs b        
b <- oget OCC.gs.[n0, c0]  (4)                           
(r, s) <- mk_rs b          (5)                           

post =
  poly1305 r{1} s{1} (topol a{1} c{1}) = poly1305 r{2} s{2} (topol a{2} c{2})
[282|check]>
```

**Last action:** `inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/poly_mac2/r01/2026-06-25_0402_poly_mac2/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/poly_mac2/r01/2026-06-25_0402_poly_mac2/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/poly_mac2/r01/2026-06-25_0402_poly_mac2/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/poly_mac2/r01/2026-06-25_0402_poly_mac2/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
