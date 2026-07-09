## 🎯 Current Goal
```
Current goal

Type variables: <none>

k0: key
n0: nonce
a0: associated_data
c0: message
gs0: globS
------------------------------------------------------------------------
Context : hr: {k, k0 : key, n, n0 : nonce, c0 : C.counter, r : poly_in,
              s : poly_out, b : block, a : associated_data, c : message}
Bound   : [=] 1%r

pre =
  (k, n, a, c).`1 = k0 /\
  (k, n, a, c).`2 = n0 /\
  (k, n, a, c).`3 = a0 /\ (k, n, a, c).`4 = c0 /\ OCC.gs = gs0

(1)  k0 <- k                               
(2)  n0 <- n                               
(3)  c0 <- C.ofintd 0                      
(4)  b <- cc OCC.gs k0{!hr} n0{!hr} c0{!hr}
(5)  (r, s) <- mk_rs b                     

post = poly1305 r s (topol a c) = genpoly1305 (cc gs0) k0 n0 (topol a0 c0)
[206|check]>
```

## Status
remaining **1** · phase `procedure_frontier` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_subgoals` (+invariant) · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `inline *.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/night_specs_fable_l4np/l4_checked_action_surface/cc_poly_spec/r01/2026-06-11_0152_poly_spec/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/night_specs_fable_l4np/l4_checked_action_surface/cc_poly_spec/r01/2026-06-11_0152_poly_spec/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/night_specs_fable_l4np/l4_checked_action_surface/cc_poly_spec/r01/2026-06-11_0152_poly_spec/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/night_specs_fable_l4np/l4_checked_action_surface/cc_poly_spec/r01/2026-06-11_0152_poly_spec/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
