## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
Hll: forall (_ : nonce * C.counter), is_lossless dblock
------------------------------------------------------------------------
Pr[MainD(G5(A), FinRO).distinguish() @ &m : res] =
Pr[Split0.IdealAll.MainD(G5(A), Split0.IdealAll.RO).distinguish() @ &m : res]
[322|check]>
```

## Opener — reduce the probability goal

**Route:** reduce `Pr[...] <= Pr[...]` to a relational/phoare judgment first.

**Framework strategy:** no pr obligation

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — to a pRHL `equiv` (most common)
- `byphoare (_: <pre> ==> <post>)` — to a `phoare` bound on one program

**Unfoldable heads:**
- `rewrite /dblock.` (unfolds `dblock`)

**Yours:** the reduction (byequiv vs byphoare), the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

### Need more? submit one of these read-only requests
- proof-state analysis extracted a distinctive EC operator token from the current goal; native AST search is more precise…
  submit `{"intent": "inspect_context", "payload": {"topic": "rewrite_candidates"}}`
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
- you submitted: `commit_tactic` `have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.db…`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":40,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"have Hll : forall (x : nonce * C.counter), is_lossless dblock by move=> ?; exact Block.dblock_ll."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"552 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
