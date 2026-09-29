## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] =
Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]
[316|check]>
```

## Opener — reduce the probability goal

**Route:** reduce `Pr[...] <= Pr[...]` to a relational/phoare judgment first.

**Framework strategy:** no pr obligation

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — to a pRHL `equiv` (most common)
- `byphoare (_: <pre> ==> <post>)` — to a `phoare` bound on one program

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
{"turn":41,"handled_intent":{"intent":"inspect_context","payload":{"topic":"pr_bridge_routes"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect pr bridge routes","outcome":"The manager returned read-only context for the current goal.","timing":"1.5 s","content":{"title":"Verified Pr Bridge Routes","notes":[{"message":"Every surfaced bridge option was accepted by the daemon against the current goal. Direct byequiv remains a risky fallback, not the preferred route."}],"items":[{"candidate":"have -> : Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = Pr[MainD(G2, RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.","why":"Local adapter `G2` normalizes wrapper `Indist.Distinguish(D(A),IndRO)` to `MainD(G2,RO)`, exposing generic Pr rewrite `pr_RO_FinRO_D`. The full chain was accepted by the daemon on the live goal.","effect":"commits a verified Pr bridge route; proof state changes only if the agent submits the shown manager intent","verification":"daemon-verified against the current goal","submit":{"intent":"commit_tactic","payload":{"tactic":"have -> : Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = Pr[MainD(G2, RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim."}}}]}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
