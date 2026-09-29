## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
Pr[UFCMA_l.f() @ &m :
   let tt = nth (w1, w2) UFCMA_l.lbad1 nth0 in tt.`1 = tt.`2] <=
Pr[UFCMA_li.f(nth0) @ &m : UFCMA_li.badi]
[419|check]>
```

## Opener — reduce the probability goal

**Route:** reduce `Pr[...] <= Pr[...]` to a relational/phoare judgment first.

**Framework strategy:** use pr arithmetic chain

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — to a pRHL `equiv` (most common)
- `byphoare (_: <pre> ==> <post>)` — to a `phoare` bound on one program

**Unfoldable heads:**
- `rewrite /qdec.` (unfolds `qdec`)
- `rewrite /w1.` (unfolds `w1`)
- `rewrite /w2.` (unfolds `w2`)

**Pr shape facts:**
- has_pr_arithmetic_plan
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
- result: Manager handled the previous message and refreshed the latest view.
- ⚠️ I could not read a proof intent from the last message. Please reply with exactly one JSON object like: {"intent": "probe_tactic", "payload": {"tactic": "..."}} or {"intent": "inspect_context", "payload": {"topic": "goal_info"}}

```json
{"turn":2,"ok":false,"repair_prompt":"I could not read a proof intent from the last message. Please reply with exactly one JSON object like:\n{\"intent\": \"probe_tactic\", \"payload\": {\"tactic\": \"...\"}}\nor\n{\"intent\": \"inspect_context\", \"payload\": {\"topic\": \"goal_info\"}}","manager_note":"Manager handled the previous message and refreshed the latest view.","view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
