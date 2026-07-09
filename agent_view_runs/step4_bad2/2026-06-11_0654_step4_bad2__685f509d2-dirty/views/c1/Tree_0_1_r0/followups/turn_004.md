## 🎯 Current Goal
```
Current goal (remaining: 8)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b : bool, i : int, n : nonce, ns, ns1, ns2 : nonce list,
              r : poly_in, t : poly_out}
Bound   : [<=] BRA.big predT<:nonce>
                 (fun (n0 : nonce) =>
                    (size (filter (fun (c : ciphertext) => c.`1 = n0) Mem.lc))%r)
                 ns1 *
               pr_zeropol

pre =
  ns = undup (map (fun (p : ciphertext) => p.`1) Mem.lc) /\
  ns1 = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \in ROout.m) ns /\
  ns2 = filter (fun (n0 : nonce) => (n0, C.ofintd 0) \notin ROout.m) ns /\
  i = 0 /\
  (UF.forged = false /\
   UFCMA.bad2 = false /\ RO.m = empty<:nonce * C.counter, poly_in>) /\
  size Mem.lc <= qdec


post =
  forall (forged : bool) (i0 : int),
    (size ns1 - i0 <= 0 => ! i0 < size ns1) /\ (! i0 < size ns1 => forged)
[400|check]>
```

## Status
remaining **8** · phase `procedure_frontier` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_subgoals` (+invariant) · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> z; inline *; auto => />; smt(dpoly_in_ll).` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-11_0048_step4_bad2/iteration_1/node_memory/Tree_0_1_r0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
