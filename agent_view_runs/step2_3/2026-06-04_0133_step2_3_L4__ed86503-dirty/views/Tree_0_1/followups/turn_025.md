## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[MainD(G4(A), FinRO).distinguish() @ &m : res] =
Pr[Split0.IdealAll.MainD(G4(A), Split0.IdealAll.RO).distinguish() @ &m : res]
[312|check]>
```

## Opener — reduce the probability goal

**Route:** reduce `Pr[...] <= Pr[...]` to a relational/phoare judgment first.

**Framework strategy:** no pr obligation

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — to a pRHL `equiv` (most common)
- `byphoare (_: <pre> ==> <post>)` — to a `phoare` bound on one program

**Yours:** the reduction (byequiv vs byphoare), the pre/post, the numeric bound.

## Status
remaining **2** · phase `probability` / `pr`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
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
- you submitted: `probe_tactic` `rewrite -(FiniteRO.pr_RO_FinRO_D (fun _ => Block.dblock_ll) (G4(A)) &m () (fun b => b)) /…`
- result: Read-only tactic probe. Use any goal-after-probe text as a preview only; there is no probe step to undo.

```json
{"turn":25,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"rewrite -(FiniteRO.pr_RO_FinRO_D (fun _ => Block.dblock_ll) (G4(A)) &m () (fun b => b)) /=."}},"ok":true,"manager_note":"Read-only tactic probe. Use any goal-after-probe text as a preview only; there is no probe step to undo.","manager_actions":[{"action":"tactic probe","outcome":"The read-only probe tool failed before EasyCrypt could validate this tactic. The committed proof state was not changed; use the error summary as a backend health signal, not as proof that the tactic is invalid.","timing":"1.6 s","error_summary":"expecting a `proof-term', not a `formula'"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
