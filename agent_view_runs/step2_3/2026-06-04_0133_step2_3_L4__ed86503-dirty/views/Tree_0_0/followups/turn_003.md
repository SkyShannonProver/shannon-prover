## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main
   () @ &m : res] +
Pr[UFCMA_poly(A, FinRO).main() @ &m : res] =
Pr[Split1.IdealAll.MainD(G8(A), RO_Pair(I1.RO, I2.RO)).distinguish() @ &m :
   res] +
Pr[Split1.IdealAll.MainD(G9(A), RO_Pair(I1.RO, I2.RO)).distinguish() @ &m :
   res]
```

## Opener — reduce the probability goal

**Route:** reduce `Pr[...] <= Pr[...]` to a relational/phoare judgment first.

**Framework strategy:** normalize pr shell

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — to a pRHL `equiv` (most common)
- `byphoare (_: <pre> ==> <post>)` — to a `phoare` bound on one program

**Pr shape facts:**
- has_pr_normal_form
- has_pr_obligation_plan

**Yours:** the reduction (byequiv vs byphoare), the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Current Pr equality may need a manager-verified bridge route (game-hop or scheme/endpoint normalization) before direct …
  submit `{"intent": "inspect_context", "payload": {"topic": "pr_bridge_routes"}}`
- Need pRHL/procedure-equivalence bridge lemma names or context after checking pr_bridge_routes.
  submit `{"intent": "inspect_context", "payload": {"topic": "equiv_bridge_lemmas"}}`
- Need local lemma hints before choosing a Pr-level proof route.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need exact byphoare/phoare-loop tactic syntax before probing the probability route.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "while"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":3,"handled_intent":{"intent":"inspect_context","payload":{"topic":"lemma_index"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect lemma index","outcome":"The manager returned read-only context for the current goal.","timing":"135 ms","content":{"preview":"=== chacha_poly.ec: 51 lemma statement(s) (signatures only \u2014 proofs are NOT shown) === These are every lemma declared in the current file. Use them to plan which lemmas you can apply/rewrite/bridge with; `lookup_symbol` for the exact declaration of any one before using it. L14 [lemma, top_level] map2_zip: lemma map2_zip (f:'a -> 'b -> 'c) s t : map2 f s t = map (fun (p:'a * 'b) => f p.`1 p.`2) (zip s t). L21 [lemma, top_level] size_map2: lemma size_map2 (f:'a -> 'b -> 'c) (l1:'a list) l2 : size (map2 f l1 l2) = min (size l1) (size l2). L27 [lemma, top_level] nth_map2: lemma nth_map2 dfla dflb dflc (f:'a -> 'b -> 'c) (l1:'a list) l2 i: 0 <= i < min (size l1) (size l2) => nth dflc (map2 f l1 l2) i = f (nth dfla l1 i) (nth dflb l2 i). L54 [lemma, top_level] xorK1: lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2. L134 [lemma, top_level] dblock_ll: lemma dblock_ll : is_lossless dblock. L140 [lemma, top_level] dblock_uni: lemma dblock_uni: is_uniform dblock. L146 [lemma, top_level] dblock_fu: lemma dblock_fu: is_full dblock. L152 [lemma, top_level] dblock_funi: lemma dblock_funi: is_funiform dblock. L163 [lemma, top_level] nth_xor: lemma nth_xor x y i : 0 <= i < block_size => nth Byte.zero (b..."}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
