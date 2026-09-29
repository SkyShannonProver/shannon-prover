## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
`|Pr[INDR_CPA_direct(CBC_Oracle(DoubleQuery(PRFi)), A).main() @ &m : res] -
  Pr[INDR_CPA_direct(CBC_Oracle(DoubleQuery(Sample)), A).main() @ &m : res]| <=
Pr[INDR_CPA_direct(CBC_Oracle(DoubleQuery(Sample)), A).main() @ &m :
   DoubleQuery.bad]
[116|check]>
```

## Opener — reduce the probability goal

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — to a pRHL `equiv` (most common)
- `byphoare (_: <pre> ==> <post>)` — to a `phoare` bound on one program

**Yours:** the reduction (byequiv vs byphoare), the pre/post, the numeric bound.

## Status
remaining **1** · phase `failure_diagnostic` / `pr`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":13,"handled_intent":{"intent":"inspect_context","payload":{"topic":"diagnose"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect diagnose","outcome":"The manager returned read-only context for the current goal.","timing":"385 ms","content":{"preview":"No known diagnosis for this error. Error: [error] invalid goal shape Tactic: byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\\ (!DoubleQuery.bad{2} => ={res})) => //. === ProofIR Diagnostic === byequiv failed while Pr-route context is still visible TACTIC REJECTED: `byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\\ (!DoubleQuery.bad{2} => ={res})) => //.`. Reason: ProofIR sees Pr normalization, rewrite, or path options as route context, not mandatory prerequisites. Cause: `byequiv` opens pRHL. On some goals this is intended; on others a matching Pr handle gives a smaller proof. Repair: 1. If pursuing a Pr rewrite/path route, relevant handle(s) include: DQ_Sample_Compute_pr, doublequery_eq, success_eq_random, CPA_direct_eq. 2. If direct program equivalence remains cleaner, refine the byequiv pre/post or inspect the pRHL goal instead of exhausting every Pr handle. General suggestions: - Read the goal state carefully - Try a simpler version of the tactic - Use -search to verify lemma names - Step back: if stuck >5 min, reconsider the approach (Pitfall P4)"}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
