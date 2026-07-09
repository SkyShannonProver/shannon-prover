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
{"turn":2,"handled_intent":{"intent":"inspect_context","payload":{"topic":"equiv_bridge_lemmas"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect equiv bridge lemmas","outcome":"The manager returned read-only context for the current goal.","timing":"163 ms","content":{"preview":"{ \"schema_version\": 1, \"tool\": \"bridge-lemmas\", \"ok\": true, \"proof_state\": { \"status\": \"open\", \"candidate_ready\": false, \"final_ready\": false, \"goal\": { \"state_kind\": \"open\", \"goal_type\": \"probability\", \"num_remaining\": 1, \"num_remaining_determined\": true, \"proof_candidate_closed\": false, \"active_goal_hash\": \"b5e5de34dbe423d5b297e2abf89872f97fe3b885\", \"fact_source\": \"pretty_goal_text\", \"authority\": \"pretty_text_fallback\", \"authority_rank\": 10, \"ec_ground_truth\": false, \"native_artifact\": \"\" }, \"history\": { \"tactic_count\": 0, \"has_qed\": false, \"latest_tactic\": \"\" }, \"latest_transition\": { \"kind\": \"none\", \"tactic\": \"\", \"status\": \"\", \"goals_before\": null, \"goals_after\": null, \"candidate_closed\": false, \"no_progress\": false, \"no_progress_reason\": \"\", \"history_committed\": null, \"latest_error\": \"\" }, \"event_contract\": { \"ok\": true, \"exists\": true, \"event_count\": 16, \"candidate_closed\": false, \"verification_status\": null, \"error_count\": 0, \"warning_count\": 0, \"latest_error\": \"\", \"latest_error_tactic\": \"\", \"latest_attempt\": {}, \"recent_failed_attempts\": [], \"errors\": [], \"warnings\": [] }, \"consistency\": { \"ok\": true, \"error_count\": 0, \"warning_count\": 0, \"note_count\": 0, \"errors\": [], \"..."}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step2_3/r01/2026-06-04_0133_step2_3/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
