## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
`|Pr[INDR_CPA_direct(CBC_Oracle(PRFi), A).main() @ &m : res] -
  Pr[INDR_CPA_direct(CBC_Oracle(Sample), A).main() @ &m : res]| <=
Pr[INDR_CPA_direct(Compute, A).main() @ &m : Compute.bad]
```

## Opener — reduce the probability goal

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — to a pRHL `equiv` (most common)
- `byphoare (_: <pre> ==> <post>)` — to a `phoare` bound on one program

**Yours:** the reduction (byequiv vs byphoare), the pre/post, the numeric bound.

## Status
remaining **1** · phase `probability` / `pr`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
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
{"turn":2,"handled_intent":{"intent":"inspect_context","payload":{"topic":"lemma_index"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect lemma index","outcome":"The manager returned read-only context for the current goal.","timing":"189 ms","content":{"preview":"=== CBC.eca: 24 lemma statement(s) (signatures only \u2014 proofs are NOT shown) === These are every lemma declared in the current file. Use them to plan which lemmas you can apply/rewrite/bridge with; `lookup_symbol` for the exact declaration of any one before using it. L42 [lemma, top_level] addrA: lemma addrA <- addbA, L43 [lemma, top_level] addrC: lemma addrC <- addbC, L44 [lemma, top_level] add0r: lemma add0r <- add0b, L45 [lemma, top_level] addNr: lemma addNr <- addbK. (* -------------------------------------------------------------------- *) (** Let P, Pi: key -> block -> block be a PRP and its inverse **) op P : key -> block -> block. op Pi: key -> block -> block. (* TODO: if dBlock is modified to not cover the whole type block, modify the axiom below to restrict the bijection *) L143 [lemma, top_level] dBlocks_ll: lemma dBlocks_ll l: is_lossless (dBlocks l) L187 [equiv, in_section] Random_Ideal: equiv Random_Ideal: Random.enc ~ Ideal.enc: size p{1} = size p{2} ==> ={res}. L261 [lemma, top_level] CBC_Oracle_enc_eq: lemma CBC_Oracle_enc_eq (P <: PRF) (P' <: PRF) (I: (glob P) -> (glob P') -> bool): equiv [P.f ~ P'.f: ={arg} /\\ I (glob P){1} (glob P'){2} ==> ={res} /\\ I (glob P)..."}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
